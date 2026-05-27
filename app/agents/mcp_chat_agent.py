"""Approval-based MCP chat agent for the frontend."""

import ast
import json
import os
import re
import uuid

from dotenv import load_dotenv
from groq import Groq
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()


client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

MODEL_NAME = os.getenv(
    "GROQ_MODEL",
    "meta-llama/llama-4-scout-17b-16e-instruct"
)

# In-memory sessions are enough for local development. A production version
# should move this state to durable storage so approvals survive restarts.
CHAT_SESSIONS = {}

SYSTEM_PROMPT = """
You are an Engineering MCP Assistant.

You ONLY support:
- GitHub repository analysis
- Code review
- Non-destructive code change proposals
- Python review
- Security scanning
- Software engineering workflows
- Repository browsing
- File inspection
- Approved GitHub file updates
- Architecture discussions

STRICT RULES:

1. If the user asks anything unrelated to software engineering,
repositories, code, GitHub, security, APIs, backend, frontend,
or architecture:
    - DO NOT answer the question
    - DO NOT call any MCP tools
    - Respond with:

    "This assistant only supports engineering and repository analysis tasks."

2. Never invent repositories, owners, or filenames.

3. Only use MCP tools when necessary.

4. Before calling a tool:
    - Decide whether the request is actually engineering-related.
    - If not engineering-related, reject it.

5. Ask for missing repository details when needed.

6. Use tools carefully and minimally.

7. When the user asks to make code changes from an existing review,
request propose_python_code_changes with the provided code and review.
Never paste revised code directly into chat for code-change requests.

8. When the user asks to list repository files, request list_repository_files.

9. When the user asks to read or open a repository file, request
read_github_file.

10. When the user asks to review Python code, request review_python_code
after file content is available.

11. When the user confirms pushing edited code to GitHub, request
push_github_file.
"""


def _new_session():
    """Create and register a new approval-chat session."""

    session_id = str(uuid.uuid4())

    CHAT_SESSIONS[session_id] = {
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ],
        "pending_tool": None
    }

    return session_id


def _get_session(session_id: str | None):
    """Return an existing session, or create one when the ID is missing."""

    if not session_id or session_id not in CHAT_SESSIONS:
        session_id = _new_session()

    return session_id, CHAT_SESSIONS[session_id]


def _mcp_tool_to_groq_tool(tool):
    """Convert an MCP tool definition into Groq function-call schema."""

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema
        }
    }


def _content_to_text(content_items):
    """Flatten MCP content items into a text payload.

    FastMCP can return structured content, text content, or SDK model objects.
    The chat agent normalizes all of those shapes before extracting UI state.
    """

    text_parts = []

    for item in content_items:

        if hasattr(item, "text"):
            text_parts.append(item.text)
            continue

        if hasattr(item, "model_dump"):
            text_parts.append(
                json.dumps(item.model_dump())
            )
            continue

        text_parts.append(str(item))

    return "\n".join(text_parts)


def _normalize_payload(payload):
    """Recursively unwrap common MCP and SDK response wrappers.

    The MCP SDK may represent tool results as text blocks, structured content,
    dictionaries, or lists of content items. This function preserves real file
    payloads while unwrapping transport-level wrappers.
    """

    if isinstance(payload, str):
        try:
            return _normalize_payload(
                json.loads(payload)
            )
        except json.JSONDecodeError:
            pass

        try:
            return _normalize_payload(
                ast.literal_eval(payload)
            )
        except (SyntaxError, ValueError):
            return payload

    if isinstance(payload, list):
        if (
            len(payload) == 1
            and isinstance(payload[0], dict)
            and (
                "text" in payload[0]
                or "content" in payload[0]
                or "structuredContent" in payload[0]
            )
        ):
            return _normalize_payload(payload[0])

        return [
            _normalize_payload(item)
            for item in payload
        ]

    if isinstance(payload, dict):
        if (
            "name" in payload
            and "path" in payload
            and "content" in payload
        ):
            return {
                key: _normalize_payload(value)
                for key, value in payload.items()
            }

        if "structuredContent" in payload:
            return _normalize_payload(payload["structuredContent"])

        if "structured_content" in payload:
            return _normalize_payload(payload["structured_content"])

        if "text" in payload and (
            len(payload) == 1
            or payload.get("type") == "text"
        ):
            return _normalize_payload(payload["text"])

        if "content" in payload and len(payload) == 1:
            return _normalize_payload(payload["content"])

    return payload


def _parse_json_payload(text: str):
    """Parse a tool result into the most structured payload possible."""

    try:
        return _normalize_payload(
            json.loads(text)
        )
    except json.JSONDecodeError:
        pass

    normalized = _normalize_payload(text)

    if not isinstance(normalized, str):
        return normalized

    for candidate in _extract_structured_text_candidates(normalized):
        try:
            return _normalize_payload(
                json.loads(candidate)
            )
        except json.JSONDecodeError:
            pass

        try:
            return _normalize_payload(
                ast.literal_eval(candidate)
            )
        except (SyntaxError, ValueError):
            pass

    return normalized


def _extract_structured_text_candidates(text: str):
    """Find JSON/Python-literal fragments embedded in model/tool text."""

    candidates = []

    for match in re.finditer(
        r"```(?:json|python)?\s*(.*?)```",
        text,
        re.DOTALL | re.IGNORECASE
    ):
        candidates.append(match.group(1).strip())

    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)

        if start != -1 and end > start:
            candidates.append(text[start:end + 1])

    result_match = re.search(
        r"(?:result|files|items|data)\s*=\s*(\[.*\])",
        text,
        re.DOTALL | re.IGNORECASE
    )

    if result_match:
        candidates.append(result_match.group(1).strip())

    return candidates


def _extract_ui_update(tool_name: str, tool_text: str):
    """Translate raw tool output into frontend state fields."""

    payload = _parse_json_payload(tool_text)

    if tool_name == "list_repository_files":
        files = _extract_file_list(payload)

        if files is not None:
            return {
                "files": files
            }

    if tool_name == "read_github_file":
        if isinstance(payload, dict):
            return {
                "selected_file": {
                    "name": payload.get("name"),
                    "path": payload.get("path")
                },
                "code": payload.get("content", "")
            }

    if tool_name == "review_python_code":
        if isinstance(payload, dict):
            if payload.get("review"):
                return {
                    "review": payload["review"]
                }

            suggestions = payload.get("suggestions", [])
            return {
                "review": "\n\n".join(suggestions)
            }

    if tool_name == "propose_python_code_changes":
        if isinstance(payload, dict):
            return {
                "changed_code": payload.get("changed_code", ""),
                "change_summary": payload.get("summary", "")
            }

    if tool_name == "push_github_file":
        if isinstance(payload, dict):
            return {
                "pushed_file": {
                    "owner": payload.get("owner"),
                    "repo": payload.get("repo"),
                    "path": payload.get("path"),
                    "commit_sha": payload.get("commit_sha"),
                    "commit_url": payload.get("commit_url")
                },
                "code": payload.get("content", "")
            }

    return {}


def _looks_like_file_item(item):
    """Return True when a payload item looks like a sidebar file entry."""

    return (
        isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and item.get("type") in {"file", "dir"}
    )


def _extract_file_list(payload):
    """Extract a repository file list from common MCP result shapes."""

    if isinstance(payload, str):
        parsed = _parse_json_payload(payload)

        if parsed != payload:
            return _extract_file_list(parsed)

        files = _extract_concatenated_json_files(payload)

        if files is not None:
            return files

        return _extract_file_list_from_lines(payload)

    if isinstance(payload, list):
        if all(_looks_like_file_item(item) for item in payload):
            return payload

        for item in payload:
            files = _extract_file_list(item)

            if files is not None:
                return files

    if isinstance(payload, dict):
        for key in (
            "files",
            "items",
            "result",
            "data",
            "content",
            "structuredContent"
        ):
            if key not in payload:
                continue

            files = _extract_file_list(payload[key])

            if files is not None:
                return files

    return None


def _extract_concatenated_json_files(text: str):
    """Parse FastMCP text that contains adjacent JSON objects.

    Some list responses arrive as:
        {"name": "...", "type": "file"}
        {"name": "...", "type": "dir"}

    This parser walks the text with JSONDecoder.raw_decode and rebuilds a list.
    """

    decoder = json.JSONDecoder()
    index = 0
    files = []

    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1

        if index >= len(text):
            break

        try:
            item, end_index = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            return None

        if not _looks_like_file_item(item):
            return None

        files.append(item)
        index = end_index

    return files or None


def _extract_file_list_from_lines(text: str):
    """Fallback parser for simple line-based file listings."""

    files = []

    for line in text.splitlines():
        clean_line = line.strip()

        if not clean_line:
            continue

        match = re.match(
            r"^(?:[-*]\s*)?(?P<name>[^\s:]+)\s*(?:[:(-]\s*)?"
            r"(?P<type>file|dir|directory|folder)\b",
            clean_line,
            re.IGNORECASE
        )

        if not match:
            continue

        item_type = match.group("type").lower()
        files.append({
            "name": match.group("name").rstrip("):"),
            "path": match.group("name").rstrip("):"),
            "type": "dir" if item_type in {"dir", "directory", "folder"} else "file"
        })

    return files or None


def _tool_complete_message(
    tool_name: str,
    ui_update: dict
):
    """Build the user-facing completion message for an executed tool."""

    if "error" in ui_update:
        return ui_update["error"]

    if tool_name == "list_repository_files":
        if "files" not in ui_update:
            return (
                "list_repository_files executed, but I could not parse the "
                "file list for the sidebar. Check the tool result or backend "
                "logs."
            )

        return (
            "Repository files are loaded in the sidebar. "
            "Select a file when you want me to request read_github_file."
        )

    if tool_name == "read_github_file":
        if "code" not in ui_update:
            return (
                "read_github_file executed, but I could not parse the file "
                "content for the editor."
            )

        return (
            "File content is loaded in the editor. "
            "Ask for code review when you are ready."
        )

    if tool_name == "review_python_code":
        return "Code review is complete."

    if tool_name == "propose_python_code_changes":
        if "changed_code" not in ui_update:
            return (
                "propose_python_code_changes executed, but I could not parse "
                "the proposed code for the modal."
            )

        return (
            "Code change proposal is ready. Review it in the modal; the "
            "current editor code was not changed."
        )

    if tool_name == "push_github_file":
        if "pushed_file" not in ui_update:
            return (
                "push_github_file executed, but I could not parse the GitHub "
                "commit result."
            )

        pushed_file = ui_update["pushed_file"]
        commit_sha = pushed_file.get("commit_sha") or ""
        short_sha = commit_sha[:7]

        if short_sha:
            return f"Changes pushed to GitHub at commit {short_sha}."

        return "Changes pushed to GitHub."

    return f"{tool_name} executed successfully."


async def _list_tools():
    """Start the MCP server over stdio and return Groq-compatible tools."""

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "main"]
    )

    async with stdio_client(server_params) as (
        read_stream,
        write_stream
    ):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            await session.initialize()

            tools_response = await session.list_tools()

            return [
                _mcp_tool_to_groq_tool(tool)
                for tool in tools_response.tools
            ]


async def _call_tool(tool_name: str, tool_input: dict):
    """Execute one MCP tool through a short-lived stdio MCP session."""

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "main"]
    )

    async with stdio_client(server_params) as (
        read_stream,
        write_stream
    ):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            await session.initialize()

            result = await session.call_tool(
                tool_name,
                tool_input
            )

            structured_content = (
                getattr(result, "structuredContent", None)
                or getattr(result, "structured_content", None)
            )

            if structured_content is not None:
                return json.dumps(structured_content)

            return _content_to_text(result.content)


def _assistant_response_from_model(
    messages,
    tools
):
    """Ask the LLM for a response or tool call."""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0.2
    )

    message = response.choices[0].message
    tool_calls = message.tool_calls or []

    if tool_calls:
        tool_call = tool_calls[0]
        arguments = tool_call.function.arguments or "{}"

        try:
            tool_input = json.loads(arguments)
        except json.JSONDecodeError:
            tool_input = {}

        return {
            "assistant_message": (
                message.content
                or f"I want to use {tool_call.function.name}."
            ),
            "pending_tool": {
                "id": tool_call.id,
                "name": tool_call.function.name,
                "arguments": tool_input
            },
            "raw_message": message
        }

    inline_tool = _extract_inline_tool_request(
        message.content or "",
        tools
    )

    if inline_tool:
        return {
            "assistant_message": (
                f"I want to use {inline_tool['name']}."
            ),
            "pending_tool": {
                "id": f"inline-{uuid.uuid4()}",
                "name": inline_tool["name"],
                "arguments": inline_tool["arguments"]
            },
            "raw_message": message
        }

    return {
        "assistant_message": message.content or "",
        "pending_tool": None,
        "raw_message": message
    }


def _shortcut_tool_request(
    message: str,
    tools: list[dict]
):
    """Create deterministic tool requests for button-driven UI actions.

    Review, code-change, and push actions are controlled by explicit frontend
    shortcuts. This avoids LLM tool-selection drift for high-value operations.
    """

    tool_names = {
        tool["function"]["name"]
        for tool in tools
    }

    review_match = re.search(
        r"__MCP_REVIEW_PYTHON_CODE__\s*(?P<arguments>{.*})\s*$",
        message,
        re.DOTALL
    )

    if review_match and "review_python_code" in tool_names:
        return _build_shortcut_tool_result(
            "review_python_code",
            review_match.group("arguments")
        )

    change_match = re.search(
        r"__MCP_PROPOSE_PYTHON_CODE_CHANGES__\s*(?P<arguments>{.*})\s*$",
        message,
        re.DOTALL
    )

    if change_match and "propose_python_code_changes" in tool_names:
        return _build_shortcut_tool_result(
            "propose_python_code_changes",
            change_match.group("arguments")
        )

    push_match = re.search(
        r"__MCP_PUSH_GITHUB_FILE__\s*(?P<arguments>{.*})\s*$",
        message,
        re.DOTALL
    )

    if push_match and "push_github_file" in tool_names:
        return _build_shortcut_tool_result(
            "push_github_file",
            push_match.group("arguments")
        )

    return None


def _build_shortcut_tool_result(
    tool_name: str,
    arguments_text: str
):
    """Build a pending-tool response from serialized shortcut arguments."""

    try:
        tool_input = json.loads(arguments_text)
    except json.JSONDecodeError:
        tool_input = {}

    return {
        "assistant_message": f"I want to use {tool_name}.",
        "pending_tool": {
            "id": f"shortcut-{uuid.uuid4()}",
            "name": tool_name,
            "arguments": tool_input
        },
        "raw_message": None
    }


def _extract_inline_tool_request(
    content: str,
    tools: list[dict]
):
    """Recover tool calls when a model emits inline function syntax as text."""

    tool_names = {
        tool["function"]["name"]
        for tool in tools
    }

    match = re.search(
        r"<function=(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)>"
        r"(?P<arguments>.*?)"
        r"</function>",
        content,
        re.DOTALL
    )

    if not match:
        return None

    tool_name = match.group("name")

    if tool_name not in tool_names:
        return None

    arguments_text = match.group("arguments").strip()

    try:
        tool_input = json.loads(arguments_text)
    except json.JSONDecodeError:
        tool_input = {}

    return {
        "name": tool_name,
        "arguments": tool_input
    }


async def send_chat_message(
    message: str,
    session_id: str | None = None
):
    """Send a user message and return an answer or pending tool request."""

    session_id, chat_session = _get_session(session_id)

    chat_session["messages"].append({
        "role": "user",
        "content": message
    })

    tools = await _list_tools()

    model_result = (
        _shortcut_tool_request(
            message,
            tools
        )
        or _assistant_response_from_model(
            chat_session["messages"],
            tools
        )
    )

    pending_tool = model_result["pending_tool"]

    if pending_tool:
        chat_session["pending_tool"] = pending_tool
        chat_session["messages"].append({
            "role": "assistant",
            "content": model_result["assistant_message"],
            "tool_calls": [
                {
                    "id": pending_tool["id"],
                    "type": "function",
                    "function": {
                        "name": pending_tool["name"],
                        "arguments": json.dumps(
                            pending_tool["arguments"]
                        )
                    }
                }
            ]
        })
    else:
        chat_session["pending_tool"] = None
        chat_session["messages"].append({
            "role": "assistant",
            "content": model_result["assistant_message"]
        })

    return {
        "session_id": session_id,
        "message": model_result["assistant_message"],
        "pending_tool": pending_tool
    }


async def decide_pending_tool(
    approved: bool,
    session_id: str
):
    """Approve or reject the current pending MCP tool call."""

    session_id, chat_session = _get_session(session_id)
    pending_tool = chat_session.get("pending_tool")

    if not pending_tool:
        return {
            "session_id": session_id,
            "message": "There is no pending tool to approve.",
            "pending_tool": None
        }

    if not approved:
        chat_session["messages"].append({
            "role": "tool",
            "tool_call_id": pending_tool["id"],
            "content": "User rejected this tool call."
        })
        chat_session["pending_tool"] = None

        return {
            "session_id": session_id,
            "message": (
                f"Rejected tool: {pending_tool['name']}. "
                "Tell me what you want to do next."
            ),
            "pending_tool": None
        }

    tool_text = await _call_tool(
        pending_tool["name"],
        pending_tool["arguments"]
    )

    chat_session["messages"].append({
        "role": "tool",
        "tool_call_id": pending_tool["id"],
        "content": tool_text
    })
    chat_session["pending_tool"] = None

    ui_update = _extract_ui_update(
        pending_tool["name"],
        tool_text
    )

    if tool_text.startswith("Error executing tool"):
        ui_update = {
            **ui_update,
            "error": tool_text
        }

    message = _tool_complete_message(
        pending_tool["name"],
        ui_update
    )

    chat_session["messages"].append({
        "role": "assistant",
        "content": message
    })

    return {
        "session_id": session_id,
        "message": message,
        "pending_tool": None,
        "tool_result": {
            "name": pending_tool["name"],
            "arguments": pending_tool["arguments"],
            "content": tool_text
        },
        **ui_update
    }
