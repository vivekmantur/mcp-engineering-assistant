"""FastAPI bridge between the React UI and MCP approval agent."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agents.mcp_chat_agent import (
    decide_pending_tool,
    send_chat_message
)
from app.tools.github.list_repo_files import (
    list_repository_files
)
from app.tools.github.read_file import (
    read_github_file
)


app = FastAPI()

# ----------------------------------------
# CORS CONFIGURATION
# ----------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------
# REQUEST MODELS
# ----------------------------------------

class RepoRequest(BaseModel):
    """Request body for repository-level operations."""

    owner: str
    repo: str


class FileRequest(BaseModel):
    """Request body for reading a file from a repository."""

    owner: str
    repo: str
    path: str


class ChatRequest(BaseModel):
    """Request body for chat messages and deterministic tool shortcuts."""

    message: str
    session_id: str | None = None


class ToolDecisionRequest(BaseModel):
    """Request body for approving or rejecting a pending MCP tool."""

    session_id: str
    approved: bool


# ----------------------------------------
# API -> LIST FILES
# ----------------------------------------

@app.post("/list-files")
async def list_files(
    data: RepoRequest
):
    """List root-level repository files through the GitHub MCP tool."""

    return await list_repository_files(
        data.owner,
        data.repo
    )


# ----------------------------------------
# API -> READ FILE
# ----------------------------------------

@app.post("/read-file")
async def read_file(
    data: FileRequest
):
    """Read one repository file through the GitHub MCP tool."""

    return await read_github_file(
        data.owner,
        data.repo,
        data.path
    )


# ----------------------------------------
# API -> MCP CHAT AGENT
# ----------------------------------------

@app.post("/agent-chat")
async def agent_chat(
    data: ChatRequest
):
    """Send a chat message or deterministic shortcut to the approval agent."""

    return await send_chat_message(
        data.message,
        data.session_id
    )


# ----------------------------------------
# API -> APPROVE OR REJECT MCP TOOL
# ----------------------------------------

@app.post("/agent-tool-decision")
async def agent_tool_decision(
    data: ToolDecisionRequest
):
    """Approve or reject the current pending MCP tool call."""

    return await decide_pending_tool(
        data.approved,
        data.session_id
    )
