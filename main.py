"""Application entry point for the Engineering Assistant MCP server."""

from app.server.mcp_instance import mcp
# Import modules for their side effects: each module registers MCP tools or
# resources against the shared FastMCP instance.
import app.tools.github.list_repo_files
import app.tools.github.read_file
import app.tools.github.list_my_repositories
import app.tools.github.push_file
import app.resources.mcp_resources
import app.tools.review.review_python_code
import app.tools.security.scan_repository_security
import app.tools.security.scan_recent_commit_changes


if __name__ == "__main__":
    mcp.run()
