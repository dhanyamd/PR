import logging
from contextlib import AsyncExitStack
from typing import Any

import opik
import utils.opik_utils as opik_utils
from config import settings
from fastmcp import FastMCP
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

opik_utils.configure()
logger = logging.getLogger("github_server")
logging.basicConfig(level=logging.INFO)

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "openWorldHint": True,
}

github_mcp = FastMCP("github_proxy")


def _github_headers() -> dict[str, str]:
    token = (settings.GITHUB_ACCESS_TOKEN or "").strip()
    if not token:
        raise ValueError(
            "GITHUB_ACCESS_TOKEN is not set. Configure a GitHub token before calling GitHub MCP tools."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
    }


def mcp_tool_result_to_payload(result: Any) -> Any:
    """Convert MCP CallToolResult into JSON-serializable data for downstream LLMs."""
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


async def _call_github_upstream(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Proxy a single tool call to GitHub's hosted MCP server."""
    headers = _github_headers()
    context = streamablehttp_client(GITHUB_MCP_URL, headers=headers)
    async with AsyncExitStack() as exit_stack:
        read_stream, write_stream, _ = await exit_stack.enter_async_context(context)
        session = await exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        logger.info("Proxying GitHub MCP tool %s", tool_name)
        result = await session.call_tool(tool_name, arguments=arguments)
        return mcp_tool_result_to_payload(result)


def _register_pr_proxy(
    *,
    upstream_name: str,
    description: str,
    title: str,
    tags: set[str],
    opik_name: str,
):
    @github_mcp.tool(
        description=description,
        tags=tags,
        annotations={"title": title, **READ_ONLY_ANNOTATIONS},
    )
    @opik.track(name=opik_name, type="tool")
    async def handler(owner: str, repo: str, pullNumber: int, **kwargs):
        args: dict[str, Any] = {
            "owner": owner,
            "repo": repo,
            "pullNumber": pullNumber,
            **kwargs,
        }
        return await _call_github_upstream(upstream_name, args)

    handler.__name__ = upstream_name
    return handler


get_pull_request = _register_pr_proxy(
    upstream_name="get_pull_request",
    description="Get pull request details",
    title="Get Pull Request",
    tags={"github", "pull_request", "details"},
    opik_name="github-get-pull-request",
)

get_pull_request_comments = _register_pr_proxy(
    upstream_name="get_pull_request_comments",
    description="Get pull request comments",
    title="Get Pull Request Comments",
    tags={"github", "pull_request", "comments"},
    opik_name="github-get-pull-request-comments",
)

get_pull_request_diff = _register_pr_proxy(
    upstream_name="get_pull_request_diff",
    description="Get pull request diff",
    title="Get Pull Request Diff",
    tags={"github", "pull_request", "diff"},
    opik_name="github-get-pull-request-diff",
)


@github_mcp.tool(
    description="Get pull request files",
    tags={"github", "pull_request", "files"},
    annotations={"title": "Get Pull Request Files", **READ_ONLY_ANNOTATIONS},
)
@opik.track(name="github-get-pull-request-files", type="tool")
async def get_pull_request_files(
    owner: str,
    repo: str,
    pullNumber: int,
    page: int = 1,
    perPage: int = 100,
):
    return await _call_github_upstream(
        "get_pull_request_files",
        {
            "owner": owner,
            "repo": repo,
            "pullNumber": pullNumber,
            "page": page,
            "perPage": perPage,
        },
    )


get_pull_request_reviews = _register_pr_proxy(
    upstream_name="get_pull_request_reviews",
    description="Get pull request reviews",
    title="Get Pull Request Reviews",
    tags={"github", "pull_request", "reviews"},
    opik_name="github-get-pull-request-reviews",
)

get_pull_request_status = _register_pr_proxy(
    upstream_name="get_pull_request_status",
    description="Get pull request status checks",
    title="Get Pull Request Status",
    tags={"github", "pull_request", "status"},
    opik_name="github-get-pull-request-status",
)

# github_mcp.run(transport="streamable-http", host="localhost", port=8004)
