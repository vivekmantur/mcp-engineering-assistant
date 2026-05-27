"""MCP tools for LLM-based Python code review and safe code change proposals."""

import os
import re
import sys

from dotenv import load_dotenv
from groq import Groq

from app.resources.resource_loader import load_resource
from app.server.mcp_instance import mcp

load_dotenv()


MODEL_NAME = os.getenv(
    "GROQ_MODEL",
    "qwen/qwen3-32b"
)

REVIEW_MAX_TOKENS = 1500
CODE_CHANGE_MAX_TOKENS = 3000


def load_review_resources():
    """Load local standards/resources used for AI review."""

    return {
        "coding_standards": load_resource(
            "coding_standards.md"
        ),
        "security_guidelines": load_resource(
            "security_guidelines.md"
        ),
        "python_best_practices": load_resource(
            "python_best_practices.md"
        ),
        "review_constraints": load_resource(
            "review_constraints.md"
        )
    }


def build_review_prompt(
    code: str,
    resources: dict[str, str]
):
    """Build prompt for AI-based Python code review."""

    return (
        "Review the following Python code using ONLY the standards and "
        "guidelines provided below.\n\n"

        "Your responsibilities:\n"
        "- Identify security issues\n"
        "- Identify code quality issues\n"
        "- Identify Python best-practice violations\n"
        "- Identify maintainability concerns\n"
        "- Suggest SAFE fixes\n\n"

        "IMPORTANT RULES:\n"
        "- Preserve existing functionality\n"
        "- Preserve API behavior\n"
        "- Preserve routes and response formats\n"
        "- Preserve configuration-driven behavior\n"
        "- Do NOT introduce breaking changes\n"
        "- Do NOT rewrite architecture unless absolutely required\n"
        "- Do NOT include revised code blocks\n"
        "- Do NOT include implementation examples\n"
        "- Keep code changes for propose_python_code_changes tool\n\n"

        "Return the review STRICTLY in this format:\n\n"

        "1. Summary\n"
        "2. Findings\n"
        "3. Recommended fixes\n\n"

        "=== coding_standards.md ===\n"
        f"{resources['coding_standards']}\n\n"

        "=== security_guidelines.md ===\n"
        f"{resources['security_guidelines']}\n\n"

        "=== python_best_practices.md ===\n"
        f"{resources['python_best_practices']}\n\n"

        "=== review_constraints.md ===\n"
        f"{resources['review_constraints']}\n\n"

        "=== Python code to review ===\n"
        f"```python\n{code}\n```"
    )


def build_code_change_prompt(
    code: str,
    review: str
):
    """Build prompt for safe code-change proposal generation."""

    return (
        "Apply the following review feedback to the Python code.\n\n"

        "IMPORTANT RULES:\n"
        "- Preserve existing functionality\n"
        "- Preserve API contracts\n"
        "- Preserve authentication behavior unless insecure\n"
        "- Preserve configuration behavior\n"
        "- Preserve runtime flow\n"
        "- Preserve business logic\n"
        "- Avoid unnecessary refactoring\n"
        "- Avoid architectural rewrites\n"
        "- Apply MINIMAL safe fixes\n\n"

        "Return ONLY the complete revised Python file content.\n"
        "The first line of your response must be valid Python code.\n"
        "Do NOT include:\n"
        "- <think> blocks\n"
        "- reasoning text\n"
        "- markdown fences\n"
        "- explanations\n"
        "- summaries\n"
        "- partial snippets\n\n"

        "=== Review feedback ===\n"
        f"{review}\n\n"

        "=== Original Python code ===\n"
        f"{code}"
    )


def create_groq_client():
    """Create Groq client using environment API key."""

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:

        raise ValueError(
            "GROQ_API_KEY is not configured. "
            "Add GROQ_API_KEY to .env"
        )

    return Groq(
        api_key=api_key
    )


def review_with_llm(
    code: str,
    resources: dict[str, str]
):
    """Run AI-powered code review."""

    try:

        client = create_groq_client()

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior Python security reviewer and "
                        "software architect.\n\n"

                        "Use the provided local resource files as the "
                        "source of truth.\n\n"

                        "Focus on:\n"
                        "- security\n"
                        "- maintainability\n"
                        "- safe fixes\n"
                        "- preserving functionality\n"
                        "- avoiding breaking changes"
                    )
                },
                {
                    "role": "user",
                    "content": build_review_prompt(
                        code,
                        resources
                    )
                }
            ],
            temperature=0.1,
            max_tokens=REVIEW_MAX_TOKENS
        )

        return _strip_think_blocks(
            response
            .choices[0]
            .message
            .content
            or ""
        )

    except Exception as ex:

        return (
            "LLM review failed:\n"
            f"{str(ex)}"
        )


def propose_changes_with_llm(
    code: str,
    review: str
):
    """Generate safe revised Python code proposal."""

    try:

        client = create_groq_client()

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior Python engineer.\n\n"

                        "Your task is to apply review feedback safely "
                        "while preserving existing functionality.\n\n"

                        "Avoid:\n"
                        "- chain-of-thought or <think> output\n"
                        "- breaking changes\n"
                        "- unnecessary rewrites\n"
                        "- changing runtime behavior\n"
                        "- changing API contracts\n"
                        "- changing configuration behavior\n\n"

                        "Prefer minimal safe fixes."
                    )
                },
                {
                    "role": "user",
                    "content": build_code_change_prompt(
                        code,
                        review
                    )
                }
            ],
            temperature=0.1,
            max_tokens=CODE_CHANGE_MAX_TOKENS
        )

        # Some models can still emit reasoning or markdown despite prompt
        # instructions, so sanitize before the UI shows this as editable code.
        return _extract_python_code(
            response
            .choices[0]
            .message
            .content
            or ""
        )

    except Exception as ex:

        return (
            "LLM code generation failed:\n"
            f"{str(ex)}"
        )


def _strip_think_blocks(text: str):
    """Remove model reasoning tags from a text response."""

    return re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE
    ).strip()


def _extract_python_code(text: str):
    """Return only Python source code from an LLM code-change response."""

    cleaned = _strip_think_blocks(text)

    fence_match = re.search(
        r"```(?:python)?\s*(.*?)```",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE
    )

    if fence_match:
        return fence_match.group(1).strip()

    lines = cleaned.splitlines()

    for index, line in enumerate(lines):
        stripped = line.strip()

        if (
            stripped.startswith("import ")
            or stripped.startswith("from ")
            or stripped.startswith("#")
            or stripped.startswith('"""')
            or stripped.startswith("@")
            or stripped.startswith("def ")
            or stripped.startswith("class ")
            or stripped.startswith("app =")
        ):
            return "\n".join(lines[index:]).strip()

    return cleaned.strip()


@mcp.tool()
async def review_python_code(code: str):
    """Review Python code using local standards and AI reasoning.

    Args:
        code: Python source code.

    Returns:
        AI-generated review response.
    """

    print(
        "review_python_code tool invoked",
        file=sys.stderr
    )

    resources = load_review_resources()

    review = review_with_llm(
        code,
        resources
    )

    return {
        "resources_used": list(
            resources.keys()
        ),
        "review": review
    }


@mcp.tool()
async def propose_python_code_changes(
    code: str,
    review: str
):
    """Generate a revised Python file proposal safely.

    Args:
        code: Original Python source code.
        review: AI review feedback.

    Returns:
        Revised code proposal.
    """

    print(
        "propose_python_code_changes tool invoked",
        file=sys.stderr
    )

    changed_code = propose_changes_with_llm(
        code,
        review
    )

    return {
        "changed_code": changed_code,
        "summary": (
            "Generated revised Python code proposal "
            "while attempting to preserve original behavior."
        )
    }
