import { useState } from "react";

import Editor from "@monaco-editor/react";

import {
    FaBolt,
    FaCheck,
    FaCode,
    FaEdit,
    FaFileCode,
    FaFolder,
    FaGithub,
    FaPaperPlane,
    FaPython,
    FaSave,
    FaSpinner,
    FaTimes,
    FaWrench
} from "react-icons/fa";

import {
    decideAgentTool,
    sendAgentMessage
} from "./services/mcpApi";

import "./App.css";

function App() {

    const [owner, setOwner] = useState("");

    const [repo, setRepo] = useState("");

    const [files, setFiles] = useState([]);

    const [selectedFile, setSelectedFile] =
        useState(null);

    const [code, setCode] = useState("");

    const [review, setReview] = useState("");

    const [changedCode, setChangedCode] = useState("");

    const [changeSummary, setChangeSummary] = useState("");

    const [isCodeChangeModalOpen, setIsCodeChangeModalOpen] =
        useState(false);

    const [isChangedCodeEditable, setIsChangedCodeEditable] =
        useState(false);

    const [chatInput, setChatInput] = useState("");

    const [chatMessages, setChatMessages] = useState([
        {
            role: "assistant",
            text: (
                "Enter a GitHub owner and repo, then ask me to list files. " +
                "I will request the MCP tool and wait for your approval."
            )
        }
    ]);

    const [sessionId, setSessionId] = useState(null);

    const [pendingTool, setPendingTool] = useState(null);

    const [agentBusy, setAgentBusy] = useState(false);

    const [error, setError] = useState("");

    function appendMessage(role, text) {

        if (!text) {
            return;
        }

        setChatMessages((messages) => [
            ...messages,
            {
                role,
                text
            }
        ]);
    }

    function applyAgentData(data) {

        if (data.session_id) {
            setSessionId(data.session_id);
        }

        setPendingTool(data.pending_tool || null);

        if (data.files) {
            setFiles(data.files);
            setSelectedFile(null);
            setCode("");
            setReview("");
            setChangedCode("");
            setChangeSummary("");
            setIsCodeChangeModalOpen(false);
            setIsChangedCodeEditable(false);
        }

        if (data.error) {
            setError(data.error);
        }

        if (data.selected_file) {
            setSelectedFile({
                name: data.selected_file.name,
                path: data.selected_file.path,
                type: "file"
            });
        }

        if (typeof data.code === "string") {
            setCode(data.code);
            setReview("");
            setChangedCode("");
            setChangeSummary("");
            setIsCodeChangeModalOpen(false);
            setIsChangedCodeEditable(false);
        }

        if (typeof data.review === "string") {
            setReview(data.review);
            setChangedCode("");
            setChangeSummary("");
            setIsCodeChangeModalOpen(false);
            setIsChangedCodeEditable(false);
        }

        if (typeof data.changed_code === "string") {
            setChangedCode(data.changed_code);
            setChangeSummary(data.change_summary || "");
            setIsCodeChangeModalOpen(true);
            setIsChangedCodeEditable(false);
        }

        if (data.pushed_file) {
            setChangedCode("");
            setChangeSummary("");
            setIsChangedCodeEditable(false);
            setIsCodeChangeModalOpen(false);
        }

        if (data.tool_result) {
            appendMessage(
                "tool",
                data.error
                    ? `${data.tool_result.name} failed.`
                    : `${data.tool_result.name} executed successfully.`
            );
        }

        appendMessage(
            "assistant",
            data.message
        );

        if (typeof data.review === "string") {
            appendMessage(
                "review",
                data.review
            );
        }
    }

    async function askAgent(
        message,
        options = {}
    ) {

        if (!message.trim()) {
            return;
        }

        setAgentBusy(true);
        setError("");
        appendMessage(
            "user",
            options.visibleMessage || message
        );

        try {

            const data = await sendAgentMessage(
                sessionId,
                message
            );

            applyAgentData(data);

        } catch {

            setError("Agent request failed.");

        } finally {

            setAgentBusy(false);
        }
    }

    async function handleRepositorySubmit(event) {

        event.preventDefault();

        if (!owner.trim() || !repo.trim()) {

            setError("Enter both owner and repository.");
            return;
        }

        await askAgent(
            (
                `GitHub owner: ${owner.trim()}. `
                + `Repository: ${repo.trim()}. `
                + "List the repository files using the right MCP tool."
            )
        );
    }

    async function handleFileClick(file) {

        if (file.type === "dir") {

            await askAgent(
                (
                    `GitHub owner: ${owner.trim()}. `
                    + `Repository: ${repo.trim()}. `
                    + `I selected folder ${file.name}. `
                    + "If folder browsing is available, request the correct MCP tool."
                )
            );
            return;
        }

        setSelectedFile(file);
        setCode("");
        setReview("");
        setChangedCode("");
        setChangeSummary("");
        setIsCodeChangeModalOpen(false);
        setIsChangedCodeEditable(false);

        await askAgent(
                (
                    `GitHub owner: ${owner.trim()}. `
                    + `Repository: ${repo.trim()}. `
                    + `Read file ${file.path || file.name} using the right MCP tool.`
                )
            );
    }

    async function handleReview() {

        if (!selectedFile || !code) {

            setError("Load a file before asking for review.");
            return;
        }

        // Button-driven actions use deterministic shortcuts so the backend can
        // create the correct pending MCP tool without relying on LLM routing.
        await askAgent(
            "__MCP_REVIEW_PYTHON_CODE__ "
            + JSON.stringify({
                code
            }),
            {
                visibleMessage: (
                    `Review file ${selectedFile.name} from `
                    + `${owner.trim()}/${repo.trim()}.`
                )
            }
        );
    }

    async function handleCodeChange() {

        if (!selectedFile || !code || !review) {

            setError("Run a review before asking for code changes.");
            return;
        }

        if (changedCode) {

            setIsCodeChangeModalOpen(true);
            return;
        }

        await askAgent(
            "__MCP_PROPOSE_PYTHON_CODE_CHANGES__ "
            + JSON.stringify({
                code,
                review
            }),
            {
                visibleMessage: (
                    `Create a code change proposal for ${selectedFile.name}.`
                )
            }
        );
    }

    async function handlePushCodeChange() {

        if (!selectedFile || !changedCode) {

            setError("Generate an updated code proposal before pushing.");
            return;
        }

        // Push is intentionally gated twice: browser confirmation first, then
        // the MCP approval card created by the backend.
        const confirmed = window.confirm(
            (
                `Are you sure you want to push changes to `
                + `${owner.trim()}/${repo.trim()}/`
                + `${selectedFile.path || selectedFile.name}?`
            )
        );

        if (!confirmed) {
            return;
        }

        await askAgent(
            "__MCP_PUSH_GITHUB_FILE__ "
            + JSON.stringify({
                owner: owner.trim(),
                repo: repo.trim(),
                path: selectedFile.path || selectedFile.name,
                content: changedCode,
                commit_message: (
                    `Apply reviewed changes to ${selectedFile.name}`
                )
            }),
            {
                visibleMessage: (
                    `Push edited changes to ${selectedFile.name}.`
                )
            }
        );
    }

    async function handleChatSubmit(event) {

        event.preventDefault();

        const message = chatInput;
        setChatInput("");

        await askAgent(message);
    }

    async function handleToolDecision(approved) {

        if (!sessionId || !pendingTool) {
            return;
        }

        setAgentBusy(true);
        setError("");

        appendMessage(
            "user",
            approved
                ? `Approved tool: ${pendingTool.name}`
                : `Rejected tool: ${pendingTool.name}`
        );

        try {

            const data = await decideAgentTool(
                sessionId,
                approved
            );

            applyAgentData(data);

        } catch {

            setError("Tool decision failed.");

        } finally {

            setAgentBusy(false);
        }
    }

    function getPendingToolArgumentsPreview() {

        if (!pendingTool) {
            return "";
        }

        if (pendingTool.name === "propose_python_code_changes") {
            return JSON.stringify(
                {
                    code: "Current editor code",
                    review: "Latest review feedback"
                },
                null,
                2
            );
        }

        if (pendingTool.name === "review_python_code") {
            return JSON.stringify(
                {
                    code: "Current editor code"
                },
                null,
                2
            );
        }

        if (pendingTool.name === "push_github_file") {
            return JSON.stringify(
                {
                    owner: pendingTool.arguments.owner,
                    repo: pendingTool.arguments.repo,
                    path: pendingTool.arguments.path,
                    content: "Edited updated code",
                    commit_message: pendingTool.arguments.commit_message
                },
                null,
                2
            );
        }

        return JSON.stringify(
            pendingTool.arguments,
            null,
            2
        );
    }

    return (

        <div className="app-container">

            <div className="sidebar">

                <div className="brand">

                    <span className="brand-icon">
                        <FaGithub />
                    </span>

                    <span>MCP File Browser</span>

                </div>

                <section className="repo-panel">

                    <p className="eyebrow">
                        Repository
                    </p>

                    <p className="hint">
                        Enter owner + repo. The agent will request tools.
                    </p>

                </section>

                <div className="file-list">

                    {
                        files.length === 0 && (

                            <p className="empty-sidebar">
                                Approved list_repository_files results appear here.
                            </p>
                        )
                    }

                    {
                        files.map((file) => (

                            <button
                                key={`${file.type}-${file.name}`}
                                className={
                                    (
                                        selectedFile?.path ||
                                        selectedFile?.name
                                    ) === (file.path || file.name)
                                        ? "file-item active"
                                        : "file-item"
                                }
                                type="button"
                                onClick={() =>
                                    handleFileClick(file)
                                }
                            >

                                {
                                    file.type === "dir"
                                        ? <FaFolder />
                                        : file.name.endsWith(".py")
                                            ? <FaPython />
                                            : <FaFileCode />
                                }

                                <span>
                                    {file.name}
                                </span>

                            </button>
                        ))
                    }

                </div>

                <form
                    className="repository-form"
                    onSubmit={handleRepositorySubmit}
                >

                    <p className="tool-label">
                        MCP approval flow
                    </p>

                    <input
                        aria-label="Repository owner"
                        value={owner}
                        onChange={(event) =>
                            setOwner(event.target.value)
                        }
                        placeholder="owner (e.g. octocat)"
                    />

                    <input
                        aria-label="Repository name"
                        value={repo}
                        onChange={(event) =>
                            setRepo(event.target.value)
                        }
                        placeholder="repo (e.g. hello-world)"
                    />

                    <button
                        className="load-button"
                        type="submit"
                        disabled={agentBusy}
                    >

                        {
                            agentBusy
                                ? <FaSpinner className="spin" />
                                : <FaBolt />
                        }

                        <span>
                            Ask Agent To List
                        </span>

                    </button>

                </form>

            </div>

            <main className="workspace">

                <header className="topbar">

                    <div>

                        <p className="eyebrow">
                            MCP client chat workflow
                        </p>

                        <h1>
                            {
                                selectedFile?.name ||
                                "No file selected"
                            }
                        </h1>

                    </div>

                    <div className="topbar-actions">

                        <button
                            className="code-change-button"
                            type="button"
                            disabled={!review || !code || agentBusy}
                            onClick={handleCodeChange}
                        >

                            {
                                agentBusy
                                    ? <FaSpinner className="spin" />
                                    : <FaWrench />
                            }

                                        <span>
                                            Codechange
                                        </span>

                        </button>

                        <button
                            className="review-button"
                            type="button"
                            disabled={!selectedFile || agentBusy}
                            onClick={handleReview}
                        >

                            {
                                agentBusy
                                    ? <FaSpinner className="spin" />
                                    : <FaCode />
                            }

                            <span>
                                Ask Agent To Review
                            </span>

                        </button>

                    </div>

                </header>

                {
                    error && (

                        <div className="error-banner">
                            {error}
                        </div>
                    )
                }

                <div className="content-grid">

                    <section className="editor-container">

                        {
                            selectedFile ? (

                                <>

                                    <div className="editor-header">

                                        <span>
                                            {selectedFile.name}
                                        </span>

                                        <small>
                                            Tool approval required before file read
                                        </small>

                                    </div>

                                    <Editor
                                        height="100%"
                                        defaultLanguage={
                                            selectedFile.name.endsWith(".py")
                                                ? "python"
                                                : "javascript"
                                        }
                                        theme="vs-dark"
                                        value={
                                            code ||
                                            "Approve read_github_file to view file content."
                                        }
                                        options={{
                                            readOnly: true,
                                            minimap: {
                                                enabled: false
                                            },
                                            fontSize: 14,
                                            scrollBeyondLastLine: false,
                                            automaticLayout: true
                                        }}
                                    />

                                </>
                            ) : (

                                <div className="empty-state">

                                    <div className="folder-mark">
                                        <FaFolder />
                                    </div>

                                    <h2>
                                        Ask the agent to list repository files
                                    </h2>

                                    <p>
                                        Approve the proposed MCP tool to continue
                                    </p>

                                    <small>
                                        Model decides tools · You approve execution
                                    </small>

                                </div>
                            )
                        }

                    </section>

                    <aside className="chat-panel">

                        <div className="chat-header">

                            <p className="eyebrow">
                                Agent Chat
                            </p>

                            <h2>
                                MCP Approval
                            </h2>

                        </div>

                        <div className="chat-messages">

                            {
                                chatMessages.map((message, index) => (

                                    <div
                                        key={index}
                                        className={`chat-message ${message.role}`}
                                    >

                                        {message.text}

                                    </div>
                                ))
                            }

                            {
                                pendingTool && (

                                    <div className="tool-approval">

                                        <p>
                                            Tool requested
                                        </p>

                                        <strong>
                                            {pendingTool.name}
                                        </strong>

                                        <pre>
                                            {getPendingToolArgumentsPreview()}
                                        </pre>

                                        <div className="approval-actions">

                                            <button
                                                type="button"
                                                className="approve-button"
                                                disabled={agentBusy}
                                                onClick={() =>
                                                    handleToolDecision(true)
                                                }
                                            >

                                                <FaCheck />
                                                Approve

                                            </button>

                                            <button
                                                type="button"
                                                className="reject-button"
                                                disabled={agentBusy}
                                                onClick={() =>
                                                    handleToolDecision(false)
                                                }
                                            >

                                                <FaTimes />
                                                Reject

                                            </button>

                                        </div>

                                    </div>
                                )
                            }

                        </div>

                        <form
                            className="chat-form"
                            onSubmit={handleChatSubmit}
                        >

                            <input
                                aria-label="Chat message"
                                value={chatInput}
                                onChange={(event) =>
                                    setChatInput(event.target.value)
                                }
                                placeholder="Ask the agent what to do next..."
                            />

                            <button
                                type="submit"
                                disabled={agentBusy || !chatInput.trim()}
                            >

                                {
                                    agentBusy
                                        ? <FaSpinner className="spin" />
                                        : <FaPaperPlane />
                                }

                            </button>

                        </form>

                    </aside>

                </div>

                <footer className="statusbar">

                    <span>
                        <i />
                        MCP client approval mode
                    </span>

                    <span>
                        LLM proposes tool · User approves · MCP executes
                    </span>

                </footer>

                {
                    isCodeChangeModalOpen && (

                        <div
                            className="modal-backdrop"
                            role="presentation"
                            onClick={() =>
                                setIsCodeChangeModalOpen(false)
                            }
                        >

                            <section
                                className="code-change-modal"
                                role="dialog"
                                aria-modal="true"
                                aria-labelledby="code-change-title"
                                onClick={(event) =>
                                    event.stopPropagation()
                                }
                            >

                                <div className="modal-header">

                                    <div>

                                        <p className="eyebrow">
                                            Proposed change
                                        </p>

                                        <h2 id="code-change-title">
                                            {selectedFile?.name || "Code"}
                                        </h2>

                                    </div>

                                    <button
                                        className="modal-close-button"
                                        type="button"
                                        aria-label="Close code change modal"
                                        onClick={() =>
                                            setIsCodeChangeModalOpen(false)
                                        }
                                    >
                                        <FaTimes />
                                    </button>

                                </div>

                                {
                                    changeSummary && (

                                        <p className="change-summary">
                                            {changeSummary}
                                        </p>
                                    )
                                }

                                <div className="code-compare-grid">

                                    <div className="compare-pane">

                                        <div className="compare-pane-header">
                                            Old code
                                        </div>

                                        <div className="modal-editor">

                                            <Editor
                                                height="100%"
                                                defaultLanguage={
                                                    selectedFile?.name?.endsWith(".py")
                                                        ? "python"
                                                        : "javascript"
                                                }
                                                theme="vs-dark"
                                                value={code}
                                                options={{
                                                    readOnly: true,
                                                    minimap: {
                                                        enabled: false
                                                    },
                                                    fontSize: 14,
                                                    scrollBeyondLastLine: false,
                                                    automaticLayout: true
                                                }}
                                            />

                                        </div>

                                    </div>

                                    <div className="compare-pane">

                                        <div className="compare-pane-header updated">
                                            Updated code
                                        </div>

                                        <div className="modal-editor">

                                            <Editor
                                                height="100%"
                                                defaultLanguage={
                                                    selectedFile?.name?.endsWith(".py")
                                                        ? "python"
                                                        : "javascript"
                                                }
                                                theme="vs-dark"
                                                value={changedCode}
                                                onChange={(value) =>
                                                    setChangedCode(value || "")
                                                }
                                                options={{
                                                    readOnly: !isChangedCodeEditable,
                                                    minimap: {
                                                        enabled: false
                                                    },
                                                    fontSize: 14,
                                                    scrollBeyondLastLine: false,
                                                    automaticLayout: true
                                                }}
                                            />

                                        </div>

                                    </div>

                                </div>

                                <div className="modal-footer">

                                    <button
                                        className="edit-change-button"
                                        type="button"
                                        onClick={() =>
                                            setIsChangedCodeEditable(
                                                (editable) => !editable
                                            )
                                        }
                                    >

                                        <FaEdit />

                                        <span>
                                            {
                                                isChangedCodeEditable
                                                    ? "Lock Edit"
                                                    : "Edit"
                                            }
                                        </span>

                                    </button>

                                    <button
                                        className="push-change-button"
                                        type="button"
                                        disabled={agentBusy || !changedCode}
                                        onClick={handlePushCodeChange}
                                    >

                                        {
                                            agentBusy
                                                ? <FaSpinner className="spin" />
                                                : <FaSave />
                                        }

                                        <span>
                                            Push
                                        </span>

                                    </button>

                                </div>

                            </section>

                        </div>
                    )
                }

            </main>

        </div>
    );
}

export default App;
