"""MCP tool for listing root-level GitHub repository contents."""

import os

import httpx
from dotenv import load_dotenv

from app.server.mcp_instance import mcp

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


@mcp.tool()
async def list_repository_files(
    owner: str,
    repo: str
):
    """List root-level files and folders for a GitHub repository.

    Args:
        owner: GitHub account or organization that owns the repository.
        repo: Repository name.

    Returns:
        A list of dictionaries with each item's name, path, and GitHub content
        type. The current implementation lists only root-level contents.
    """

    url = f"https://api.github.com/repos/{owner}/{repo}/contents"

    async with httpx.AsyncClient() as client:

        response = await client.get(
            url,
            headers=GITHUB_HEADERS
        )

        response.raise_for_status()

        data = response.json()

        return [
            {
                "name": item["name"],
                "path": item["path"],
                "type": item["type"]
            }
            for item in data
        ]
