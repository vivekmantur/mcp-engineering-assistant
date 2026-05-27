"""MCP tool for basic security scanning of repository Python files."""

import httpx
import os
import re

from dotenv import load_dotenv

from app.server.mcp_instance import mcp
from app.utils.github_client import get_github_file

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


@mcp.tool()
async def scan_repository_security(
    owner: str,
    repo: str
):
    """Scan root-level Python files in a repository for simple risk patterns.

    Args:
        owner: GitHub account or organization that owns the repository.
        repo: Repository name.

    Returns:
        A list of security findings. Each finding contains a file and issue.
        This is a lightweight heuristic scan, not a full SAST analysis.
    """

    url = f"https://api.github.com/repos/{owner}/{repo}/contents"

    findings = []

    async with httpx.AsyncClient() as client:

        response = await client.get(
            url,
            headers=GITHUB_HEADERS
        )

        response.raise_for_status()

        files = response.json()

        for file in files:

            if file["type"] != "file":
                continue

            name = file["name"]

            if not name.endswith(".py"):
                continue

            data = await get_github_file(
                owner,
                repo,
                name
            )

            code = data["content"]

            if "eval(" in code:
                findings.append({
                    "file": name,
                    "issue": "Avoid using eval()"
                })

            if "os.system(" in code:
                findings.append({
                    "file": name,
                    "issue": "Avoid using os.system()"
                })

            if re.search(
                r'api[_-]?key\s*=\s*["\']',
                code,
                re.IGNORECASE
            ):

                findings.append({
                    "file": name,
                    "issue": "Possible hardcoded API key"
                })

    return findings
