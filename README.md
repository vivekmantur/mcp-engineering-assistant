# MCP Engineering Assistant

MCP Engineering Assistant is a Python MCP server that exposes GitHub repository utilities, basic Python code review checks, security scanning tools, and reusable engineering guideline resources.

The server is built with `FastMCP` and is started from the root-level `main.py` file.

## Features

- List repositories for the authenticated GitHub user.
- List files and folders at the root of a GitHub repository.
- Read a file from a GitHub repository and decode its content.
- Review Python code for simple issues such as `print()` usage and `eval()`.
- Scan repository Python files for basic security issues.
- Scan Python files changed in the latest commit for basic security issues.
- Expose MCP resources for coding standards, security guidelines, and Python best practices.

## Project Structure

```text
mcp-engineering-assistant/
|-- app/
|   |-- resources/
|   |   |-- coding_standards.md
|   |   |-- mcp_resources.py
|   |   |-- python_best_practices.md
|   |   |-- resource_loader.py
|   |   `-- security_guidelines.md
|   |-- server/
|   |   `-- mcp_instance.py
|   |-- tools/
|   |   |-- github/
|   |   |   |-- list_my_repositories.py
|   |   |   |-- list_repo_files.py
|   |   |   `-- read_file.py
|   |   |-- review/
|   |   |   `-- review_python_code.py
|   |   `-- security/
|   |       |-- scan_recent_commit_changes.py
|   |       `-- scan_repository_security.py
|   `-- utils/
|       `-- github_client.py
|-- main.py
|-- requirements.txt
`-- README.md
```

## Requirements

- Python 3.10 or later
- A GitHub personal access token
- Python packages:
  - `mcp`
  - `httpx`
  - `python-dotenv`

If `requirements.txt` is empty, install the dependencies manually:

```bash
pip install mcp httpx python-dotenv
```

## Environment Variables

Create a `.env` file in the project root:

```env
GITHUB_TOKEN=your_github_personal_access_token
```

Do not commit `.env` or expose your GitHub token publicly.

## Running the Server

From the project root, run:

```bash
python main.py
```

This starts the MCP server named `EngineeringAssistant`.

## Available MCP Tools

### `list_my_repositories`

Lists repositories available to the authenticated GitHub user.

Returns:

```json
[
  {
    "name": "repo-name",
    "private": false,
    "url": "https://github.com/user/repo-name"
  }
]
```

### `list_repository_files`

Lists files and folders at the root of a GitHub repository.

Parameters:

- `owner`: GitHub repository owner.
- `repo`: GitHub repository name.

### `read_github_file`

Reads a file from a GitHub repository.

Parameters:

- `owner`: GitHub repository owner.
- `repo`: GitHub repository name.
- `path`: File path inside the repository.

Returns the file name, path, and decoded text content.

### `review_python_code`

Reviews a Python code string against simple coding checks and the local coding standards resource.

Parameters:

- `code`: Python code as a string.

Current checks:

- Suggests logging instead of `print()`.
- Warns against `eval()`.

### `scan_repository_security`

Scans Python files in the root of a GitHub repository for basic security issues.

Parameters:

- `owner`: GitHub repository owner.
- `repo`: GitHub repository name.

Current checks:

- `eval()`
- `os.system()`
- Possible hardcoded API keys

### `scan_recent_commit_changes`

Scans Python files changed in the latest commit for basic security issues.

Parameters:

- `owner`: GitHub repository owner.
- `repo`: GitHub repository name.

Returns status, latest commit SHA, scanned files, and any findings.

## Available MCP Resources

### `standards://coding`

Returns Python coding standards from `app/resources/coding_standards.md`.

### `standards://security`

Returns security guidelines from `app/resources/security_guidelines.md`.

### `standards://python`

Returns Python best practices from `app/resources/python_best_practices.md`.

## Notes

- GitHub API calls are asynchronous and use `httpx.AsyncClient`.
- GitHub file contents are decoded from base64 before being returned.
- The security scanner currently checks only Python files.
- `scan_repository_security` currently scans Python files at the repository root, not nested directories.
- The checks are lightweight heuristics and should be treated as a first-pass review, not a complete security audit.
