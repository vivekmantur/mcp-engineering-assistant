const API_BASE = "http://localhost:8000";

export async function sendAgentMessage(
    sessionId,
    message
) {

    const response = await fetch(
        `${API_BASE}/agent-chat`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                session_id: sessionId,
                message
            })
        }
    );

    return response.json();
}


export async function decideAgentTool(
    sessionId,
    approved
) {

    const response = await fetch(
        `${API_BASE}/agent-tool-decision`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                session_id: sessionId,
                approved
            })
        }
    );

    return response.json();
}
