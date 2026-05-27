"""Legacy experimental file-review agent.

The active frontend approval workflow uses ``app.agents.mcp_chat_agent``.
This module is kept as an experimental/reference path for direct file analysis
through MCP tools, but it is not currently wired into ``bridge_api.py``.
"""

import asyncio
import json
import os

from dotenv import load_dotenv
from groq import Groq
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()


client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

async def analyze_file(
    owner: str,
    repo: str,
    path: str
):
    """Analyze a GitHub file by allowing an LLM to call MCP tools.

    Args:
        owner: GitHub account or organization that owns the repository.
        repo: Repository name.
        path: File path inside the repository.

    Returns:
        Combined textual review from the experimental agent flow.
    """

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

            anthropic_tools = []

            for tool in tools_response.tools:

                anthropic_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                })

            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Review the GitHub file "
                        f"{path} from repository "
                        f"{owner}/{repo}. "
                        f"Find security issues, "
                        f"code quality problems, "
                        f"architecture concerns, "
                        f"and best practice violations. "
                        f"Use MCP tools when needed."
                    )
                }
            ]

            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                tools=anthropic_tools,
                messages=messages
            )

            final_text = []

            while True:

                tool_used = False

                for content in response.content:

                    if content.type == "text":

                        final_text.append(
                            content.text
                        )

                    elif content.type == "tool_use":

                        tool_used = True

                        tool_name = content.name
                        tool_input = content.input

                        result = await session.call_tool(
                            tool_name,
                            tool_input
                        )

                        messages.append({
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": content.id,
                                    "name": tool_name,
                                    "input": tool_input
                                }
                            ]
                        })

                        messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": content.id,
                                    "content": json.dumps(
                                        result.content
                                    )
                                }
                            ]
                        })

                if not tool_used:
                    break
                
                response = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=messages,
                    temperature=0.2
                )

            return "\n".join(final_text)
