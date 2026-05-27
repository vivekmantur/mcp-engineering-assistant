"""Async GitHub API client helpers used by MCP tools."""

import base64
import os
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


async def get_github_file(
    owner: str,
    repo: str,
    path: str
):
    """Fetch and decode a file from a GitHub repository.

    Args:
        owner: GitHub account or organization that owns the repository.
        repo: Repository name.
        path: File path inside the repository.

    Returns:
        A dictionary containing the GitHub file name, path, and decoded text
        content. Non-text bytes are ignored during UTF-8 decoding.
    """

    encoded_path = quote(
        path,
        safe="/"
    )

    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/contents/{encoded_path}"
    )

    async with httpx.AsyncClient() as client:

        response = await client.get(
            url,
            headers=GITHUB_HEADERS
        )

        response.raise_for_status()

        data = response.json()

        content = ""

        # The GitHub contents API returns file content as base64 text.
        if "content" in data:

            content = base64.b64decode(
                data["content"]
            ).decode(
                "utf-8",
                errors="ignore"
            )

        return {
            "name": data.get("name"),
            "path": data.get("path"),
            "content": content
        }


async def update_github_file(
    owner: str,
    repo: str,
    path: str,
    content: str,
    commit_message: str,
    branch: str | None = None
):
    """Update an existing GitHub repository file using the Contents API.

    Args:
        owner: GitHub account or organization that owns the repository.
        repo: Repository name.
        path: File path inside the repository.
        content: Complete file content to commit.
        commit_message: Commit message for the file update.
        branch: Optional target branch. GitHub uses the default branch when
            this is omitted.

    Returns:
        A dictionary containing commit metadata and the pushed file content.
    """

    encoded_path = quote(
        path,
        safe="/"
    )

    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/contents/{encoded_path}"
    )

    params = {}

    if branch:
        params["ref"] = branch

    async with httpx.AsyncClient() as client:

        current_response = await client.get(
            url,
            headers=GITHUB_HEADERS,
            params=params
        )

        current_response.raise_for_status()
        current_data = current_response.json()

        payload = {
            "message": commit_message,
            "content": base64.b64encode(
                content.encode("utf-8")
            ).decode("ascii"),
            "sha": current_data["sha"]
        }

        if branch:
            payload["branch"] = branch

        update_response = await client.put(
            url,
            headers=GITHUB_HEADERS,
            json=payload
        )

        update_response.raise_for_status()
        update_data = update_response.json()

        commit = update_data.get(
            "commit",
            {}
        )
        updated_content = update_data.get(
            "content",
            {}
        )

        return {
            "owner": owner,
            "repo": repo,
            "path": updated_content.get("path", path),
            "branch": branch,
            "commit_sha": commit.get("sha"),
            "commit_url": commit.get("html_url"),
            "content": content,
            "message": commit_message
        }
