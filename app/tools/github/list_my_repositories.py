"""MCP tool for listing repositories accessible to the GitHub token."""

import httpx
import os

from dotenv import load_dotenv

from app.server.mcp_instance import mcp

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


@mcp.tool()
async def list_my_repositories():
    """List repositories for the authenticated GitHub user.

    Returns:
        A list of dictionaries containing repository name, privacy flag, and
        GitHub URL.
    """

    url = "https://api.github.com/user/repos"

    async with httpx.AsyncClient() as client:

        response = await client.get(
            url,
            headers=GITHUB_HEADERS
        )

        response.raise_for_status()

        data = response.json()

        return [
            {
                "name": repo["name"],
                "private": repo["private"],
                "url": repo["html_url"]
            }
            for repo in data
        ]
