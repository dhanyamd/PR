from typing import Any


def mcp_tool_result_to_payload(result: Any) -> Any:
    """Convert MCP CallToolResult into JSON-serializable data for Gemini function responses."""
    if result is None:
        return None
    if hasattr(result, "isError") and hasattr(result, "content"):
        blocks: list[Any] = []
        for block in result.content:
            if hasattr(block, "text") and block.text is not None:
                blocks.append(block.text)
            elif hasattr(block, "model_dump"):
                blocks.append(block.model_dump())
            else:
                blocks.append(str(block))
        return {"isError": result.isError, "content": blocks}
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result
