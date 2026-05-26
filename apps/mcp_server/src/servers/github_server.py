import logging
from typing import Any

import httpx
import opik
import utils.opik_utils as opik_utils
from config import settings
from fastmcp import FastMCP

opik_utils.configure()
logger = logging.getLogger("github_server")
logging.basicConfig(level=logging.INFO)

GITHUB_API_BASE = "https://api.github.com"

github_mcp = FastMCP("github_proxy")


def _github_headers() -> dict[str, str]:
    token = (settings.GITHUB_ACCESS_TOKEN or "").strip()
    if not token:
        raise ValueError(
            "GITHUB_ACCESS_TOKEN is not set. Configure a GitHub token before calling GitHub MCP tools."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def _github_get(path: str, params: dict | None = None) -> Any:
    """Make a GET request to the GitHub REST API."""
    url = f"{GITHUB_API_BASE}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_github_headers(), params=params or {})
        if resp.status_code >= 400:
            logger.error("GitHub API error %s: %s", resp.status_code, resp.text)
            return {"error": resp.status_code, "message": resp.text}
        return resp.json()


@github_mcp.tool(
    description="Get pull request details including title, body, state, and metadata.",
    tags={"github", "pull_request", "details"},
    annotations={"title": "Get Pull Request", "readOnlyHint": True, "openWorldHint": True},
)
@opik.track(name="github-get-pull-request", type="tool")
async def github_handler(owner: str, repo: str, pullNumber: int) -> Any:
    """Get pull request details."""
    logger.info("Getting PR details for %s/%s #%d", owner, repo, pullNumber)
    return await _github_get(f"/repos/{owner}/{repo}/pulls/{pullNumber}")


@github_mcp.tool(
    description="Get the list of files changed in a pull request, including diffs and patch content.",
    tags={"github", "pull_request", "files"},
    annotations={"title": "Get Pull Request Files", "readOnlyHint": True, "openWorldHint": True},
)
@opik.track(name="github-get-pull-request-files", type="tool")
async def github_get_pull_request_files(
    owner: str,
    repo: str,
    pullNumber: int,
    page: int = 1,
    perPage: int = 100,
) -> Any:
    """Get files changed in a pull request."""
    logger.info("Getting PR files for %s/%s #%d", owner, repo, pullNumber)
    return await _github_get(
        f"/repos/{owner}/{repo}/pulls/{pullNumber}/files",
        params={"per_page": perPage, "page": page},
    )


@github_mcp.tool(
    description="Get comments on a pull request.",
    tags={"github", "pull_request", "comments"},
    annotations={"title": "Get Pull Request Comments", "readOnlyHint": True, "openWorldHint": True},
)
@opik.track(name="github-get-pull-request-comments", type="tool")
async def get_pull_request_comments(owner: str, repo: str, pullNumber: int) -> Any:
    """Get pull request review comments."""
    logger.info("Getting PR comments for %s/%s #%d", owner, repo, pullNumber)
    return await _github_get(f"/repos/{owner}/{repo}/pulls/{pullNumber}/comments")


@github_mcp.tool(
    description="Get the diff of a pull request.",
    tags={"github", "pull_request", "diff"},
    annotations={"title": "Get Pull Request Diff", "readOnlyHint": True, "openWorldHint": True},
)
@opik.track(name="github-get-pull-request-diff", type="tool")
async def get_pull_request_diff(owner: str, repo: str, pullNumber: int) -> Any:
    """Get pull request diff."""
    logger.info("Getting PR diff for %s/%s #%d", owner, repo, pullNumber)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pullNumber}"
    async with httpx.AsyncClient(timeout=30) as client:
        headers = _github_headers()
        headers["Accept"] = "application/vnd.github.diff"
        resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            return {"error": resp.status_code, "message": resp.text}
        return {"diff": resp.text}


@github_mcp.tool(
    description="Get reviews on a pull request.",
    tags={"github", "pull_request", "reviews"},
    annotations={"title": "Get Pull Request Reviews", "readOnlyHint": True, "openWorldHint": True},
)
@opik.track(name="github-get-pull-request-reviews", type="tool")
async def get_pull_request_reviews(owner: str, repo: str, pullNumber: int) -> Any:
    """Get pull request reviews."""
    logger.info("Getting PR reviews for %s/%s #%d", owner, repo, pullNumber)
    return await _github_get(f"/repos/{owner}/{repo}/pulls/{pullNumber}/reviews")


@github_mcp.tool(
    description="Get status checks for a pull request.",
    tags={"github", "pull_request", "status"},
    annotations={"title": "Get Pull Request Status", "readOnlyHint": True, "openWorldHint": True},
)
@opik.track(name="github-get-pull-request-status", type="tool")
async def get_pull_request_status(owner: str, repo: str, pullNumber: int) -> Any:
    """Get pull request status checks."""
    logger.info("Getting PR status for %s/%s #%d", owner, repo, pullNumber)
    pr = await _github_get(f"/repos/{owner}/{repo}/pulls/{pullNumber}")
    if "head" not in pr:
        return pr
    sha = pr["head"]["sha"]
    return await _github_get(f"/repos/{owner}/{repo}/commits/{sha}/check-runs")
