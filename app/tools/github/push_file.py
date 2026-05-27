"""MCP tool for pushing updated file content to GitHub."""

from app.server.mcp_instance import mcp
from app.utils.github_client import update_github_file


@mcp.tool()
async def push_github_file(
    owner: str,
    repo: str,
    path: str,
    content: str,
    commit_message: str,
    branch: str | None = None
):
    """Push updated content for an existing GitHub repository file.

    Args:
        owner: GitHub account or organization that owns the repository.
        repo: Repository name.
        path: File path inside the repository.
        content: Complete updated file content to commit.
        commit_message: Commit message for the GitHub update.
        branch: Optional branch name. When omitted, GitHub uses default branch.

    Returns:
        Commit metadata and the pushed file content.
    """

    return await update_github_file(
        owner=owner,
        repo=repo,
        path=path,
        content=content,
        commit_message=commit_message,
        branch=branch
    )
