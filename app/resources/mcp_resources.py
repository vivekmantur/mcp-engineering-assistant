"""MCP resources that expose local engineering guideline documents."""

from app.server.mcp_instance import mcp

from app.resources.resource_loader import load_resource


@mcp.resource("standards://coding")
def coding_standards():
    """Return the local Python coding standards document."""

    return load_resource(
        "coding_standards.md"
    )


@mcp.resource("standards://security")
def security_guidelines():
    """Return the local secure coding guidelines document."""

    return load_resource(
        "security_guidelines.md"
    )


@mcp.resource("standards://python")
def python_best_practices():
    """Return the local Python best practices document."""

    return load_resource(
        "python_best_practices.md"
    )

@mcp.resource("standards://review_constraints")
def review_constraints():
    """Return the local document outlining constraints for AI code review."""

    return load_resource(
        "review_constraints.md"
    )