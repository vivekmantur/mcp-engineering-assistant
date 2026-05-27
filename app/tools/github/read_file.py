"""MCP tool for reading a file from a GitHub repository."""

from app.server.mcp_instance import mcp
from app.utils.github_client import get_github_file


@mcp.tool()
async def read_github_file(
    owner: str,
    repo: str,
    path: str
):
    """Read and return a decoded file from a GitHub repository.

    Args:
        owner: GitHub account or organization that owns the repository.
        repo: Repository name.
        path: File path inside the repository.

    Returns:
        A dictionary containing the file name, path, and decoded content.
    """

    data = await get_github_file(owner, repo, path)

    return data
