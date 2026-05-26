import hashlib
import hmac
import logging
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from host.host import MCPHost
from config.settings import settings
import utils.opik_utils as opik_utils

# Registry imports agent_scope_mcp with prefix "scope" (see tool_registry.py)
SYSTEM_PROMPT_NAME = "scope_pr_review_prompt"

# PR actions that should trigger a review
REVIEWABLE_ACTIONS = {"opened", "reopened", "synchronize"}

client = MCPHost()
logger = logging.getLogger("webhook")
logging.basicConfig(level=logging.INFO)
opik_utils.configure()


def _verify_github_signature(payload_bytes: bytes, signature_header: str | None, secret: str | None) -> bool:
    """
    Verify the HMAC-SHA256 signature GitHub sends with every webhook delivery.

    Returns True if the signature is valid or if no secret is configured (dev mode).
    Returns False if a secret is configured but the signature is missing or invalid.
    """
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET not set — skipping signature verification (dev mode).")
        return True
    if not signature_header:
        logger.error("Missing X-Hub-Signature-256 header.")
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await client.initialize()
    try:
        yield
    finally:
        await client.cleanup()


app = FastAPI(lifespan=lifespan)


@app.post("/webhook")
async def handle_github_webhook(request: Request):
    # Read the raw body first so we can verify the signature.
    payload_bytes = await request.body()

    # Verify GitHub webhook signature when a secret is configured.
    signature = request.headers.get("X-Hub-Signature-256")
    webhook_secret = getattr(settings, "GITHUB_WEBHOOK_SECRET", None)
    if not _verify_github_signature(payload_bytes, signature, webhook_secret):
        logger.error("Webhook signature verification failed.")
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    try:
        import json
        payload = json.loads(payload_bytes)
    except Exception as e:
        logger.error("Failed to parse webhook payload: %s", e)
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    action = payload.get("action", "unknown")
    logger.info("Received webhook — action: %s", action)

    if action not in REVIEWABLE_ACTIONS:
        logger.info("Action '%s' is not reviewable — skipping.", action)
        return {"status": "ok", "skipped": True, "reason": f"action '{action}' not reviewable"}

    pr = payload.get("pull_request", {})
    repository = payload.get("repository", {})
    owner = repository.get("owner", {}).get("login", "")
    repo = repository.get("name", "")
    pull_number = pr.get("number", "")

    logger.info(
        "Processing PR %s event: %s/%s#%s url=%s",
        action, owner, repo, pull_number, pr.get("url"),
    )

    try:
        logger.info("Requesting system prompt from MCPHost...")
        system_prompt = await client.get_system_prompt(
            SYSTEM_PROMPT_NAME,
            {
                "pr_id": str(pr.get("id", "")),
                "pr_url": str(pr.get("url", "")),
                "owner": str(owner),
                "repo": str(repo),
                "pull_number": str(pull_number),
            },
        )
        logger.info("System prompt received. Processing with Gemini...")

        review = await client.process_query(system_prompt.messages[0].content.text)
        logger.info("Review generated: %s", review)

        if review:
            logger.info("Posting review to Slack channel %s...", settings.SLACK_CHANNEL_ID)
            await client.call_tool(
                "slack_post_message",
                {"channel_name": settings.SLACK_CHANNEL_ID, "message": review},
            )
            logger.info("Review posted to Slack successfully.")

        return {"status": "ok"}

    except Exception as e:
        logger.error("Error handling webhook: %s", e, exc_info=True)
        return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
