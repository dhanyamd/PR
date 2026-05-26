import opik
from fastmcp import FastMCP
from servers.prompts import PR_REVIEW_PROMPT
import utils.opik_utils as opik_utils

opik_utils.configure()
agent_scope_mcp = FastMCP("agent_scope_prompts")


@agent_scope_mcp.prompt(
    name="pr_review_prompt",
    description="Prompt for reviewing pull requests"
)
@opik.track(name="pr_review_prompt", type="general")
def pr_review_prompt(
    pr_id: str,
    pr_url: str,
    owner: str,
    repo: str,
    pull_number: str,
) -> str:
    """Build the PR review prompt for the given pull request."""
    return PR_REVIEW_PROMPT.get().format(
        pr_id=pr_id,
        pr_url=pr_url,
        owner=owner,
        repo=repo,
        pull_number=pull_number,
    )


# agent_scope_mcp.run(transport="streamable-http", host="localhost", port=8002)