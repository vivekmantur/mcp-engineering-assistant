export async function callTool(
  toolName,
  args
) {

  if (!window.mcp) {

    throw new Error(
      "MCP client not available"
    );
  }

  const result = await window.mcp.callTool({
    name: toolName,
    arguments: args,
  });

  return result;
}