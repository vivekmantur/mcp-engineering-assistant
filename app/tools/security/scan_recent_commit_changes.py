"""MCP tool for scanning Python files changed in the latest commit."""

import httpx
import os
import re
import sys

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
async def scan_recent_commit_changes(
    owner: str,
    repo: str
):
    """Scan Python files changed in the latest commit for risk patterns.

    Args:
        owner: GitHub account or organization that owns the repository.
        repo: Repository name.

    Returns:
        A status dictionary containing the latest commit SHA, scanned files,
        and any findings. This tool performs lightweight pattern checks only.
    """

    print(
        "scan_recent_commit_changes tool invoked",
        file=sys.stderr
    )

    findings = []

    async with httpx.AsyncClient() as client:

        # Step 1: Get the latest commit SHA.
        commits_url = (
            f"https://api.github.com/repos/"
            f"{owner}/{repo}/commits"
        )

        commits_response = await client.get(
            commits_url,
            headers=GITHUB_HEADERS
        )

        commits_response.raise_for_status()

        commits = commits_response.json()

        if not commits:

            return {
                "status": "error",
                "message": "No commits found."
            }

        latest_commit_sha = commits[0]["sha"]

        print(
            f"LATEST COMMIT: {latest_commit_sha}",
            file=sys.stderr
        )

        # Step 2: Fetch details for the latest commit.
        commit_url = (
            f"https://api.github.com/repos/"
            f"{owner}/{repo}/commits/"
            f"{latest_commit_sha}"
        )

        commit_response = await client.get(
            commit_url,
            headers=GITHUB_HEADERS
        )

        commit_response.raise_for_status()

        commit_data = commit_response.json()

        changed_files = commit_data.get(
            "files",
            []
        )

        scanned_files = []

        # Step 3: Scan changed Python files.
        for file in changed_files:

            filename = file["filename"]

            print(
                f"PROCESSING FILE: {filename}",
                file=sys.stderr
            )

            # Only scan Python files.
            if not filename.endswith(".py"):

                print(
                    f"SKIPPED NON PYTHON FILE: {filename}",
                    file=sys.stderr
                )

                continue

            scanned_files.append(filename)

            # Read the current file content from GitHub.
            file_data = await get_github_file(
                owner,
                repo,
                filename
            )

            code = file_data.get(
                "content",
                ""
            )

            print(
                f"SCANNING FILE: {filename}",
                file=sys.stderr
            )

            print(
                code[:500],
                file=sys.stderr
            )

            # Security check: eval().
            if "eval(" in code:

                print(
                    "FOUND eval()",
                    file=sys.stderr
                )

                findings.append({
                    "file": filename,
                    "issue": "Avoid using eval()"
                })

            # Security check: os.system().
            if "os.system(" in code:

                print(
                    "FOUND os.system()",
                    file=sys.stderr
                )

                findings.append({
                    "file": filename,
                    "issue": "Avoid using os.system()"
                })

            # Security check: hardcoded API keys.
            if re.search(
                r'api[_-]?key\s*=\s*["\']',
                code,
                re.IGNORECASE
            ):

                print(
                    "FOUND API KEY",
                    file=sys.stderr
                )

                findings.append({
                    "file": filename,
                    "issue": "Possible hardcoded API key"
                })

        # Return a structured response that describes scan coverage and results.
        if not scanned_files:

            return {
                "status": "warning",
                "message": (
                    "No Python files found "
                    "in latest commit."
                ),
                "latest_commit": latest_commit_sha
            }

        if not findings:

            return {
                "status": "success",
                "message": (
                    "No obvious security "
                    "issues detected."
                ),
                "latest_commit": latest_commit_sha,
                "scanned_files": scanned_files,
                "findings": []
            }

        return {
            "status": "issues_found",
            "latest_commit": latest_commit_sha,
            "scanned_files": scanned_files,
            "findings": findings
        }
