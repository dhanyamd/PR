import asyncio
import logging
import uuid
from typing import Any

import opik
from opik import opik_context
from google import genai
from google.genai import types
from google.genai.types import Tool

from config.settings import settings
from host.connection_manager import ConnectionManager
from utils.mcp_compat import mcp_tool_result_to_payload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_host")

SKIPPABLE_PROPS = ["additional_properties", "additionalProperties", "$schema"]
MAX_LLM_CALLS = 5

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_BACKOFF_FACTOR = 2.0


def strip_additional_properties(schema: dict) -> dict[Any, dict] | list[dict] | dict | list:
    if isinstance(schema, dict):
        return {
            k: strip_additional_properties(v)
            for k, v in schema.items()
            if k not in SKIPPABLE_PROPS
        }
    elif isinstance(schema, list):
        return [strip_additional_properties(item) for item in schema]
    else:
        return schema


async def _with_retry(coro_fn, *args, max_retries: int = MAX_RETRIES, label: str = "operation", **kwargs):
    """
    Execute an async coroutine with exponential backoff retry logic.

    Args:
        coro_fn: Async callable to retry.
        *args: Positional arguments to pass to coro_fn.
        max_retries: Maximum number of retry attempts.
        label: Human-readable label for logging.
        **kwargs: Keyword arguments to pass to coro_fn.

    Returns:
        Result of coro_fn on success.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = RETRY_BASE_DELAY * (RETRY_BACKOFF_FACTOR ** attempt)
                logger.warning(
                    "[%s] Attempt %d/%d failed: %s — retrying in %.1fs",
                    label, attempt + 1, max_retries + 1, exc, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "[%s] All %d attempts failed. Last error: %s",
                    label, max_retries + 1, exc,
                )
    raise last_exc


class MCPHost:
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.connection_manager = ConnectionManager()
        self.thread_id = str(uuid.uuid4())

    @opik.track(name="host-initialize", type="general")
    async def initialize(self):
        opik_context.update_current_trace(thread_id=self.thread_id)
        await self.connection_manager.initialize_all()

    @opik.track(name="get-system-prompt", type="general")
    async def get_system_prompt(self, name, args) -> str:
        if not self.connection_manager.is_initialized:
            raise RuntimeError("ConnectionManager is not initialized. Call initialize_all() first.")
        return await self.connection_manager.get_prompt(name, args)

    @opik.track(name="process-query", type="llm")
    async def process_query(self, query: str) -> str:
        if not self.connection_manager.is_initialized:
            raise RuntimeError("ConnectionManager is not initialized. Call initialize_all() first.")
        opik_context.update_current_trace(thread_id=self.thread_id)
        tools = await self.get_mcp_tools()
        config = types.GenerateContentConfig(
            temperature=0,
            tools=tools,
        )
        contents = [
            types.Content(
                role="user", parts=[types.Part(text=query)]
            )
        ]

        llm_calls = 0
        while llm_calls < MAX_LLM_CALLS:
            try:
                response = await _with_retry(
                    self._generate_content,
                    contents=contents,
                    config=config,
                    label=f"LLM call #{llm_calls + 1}",
                )
            except Exception as e:
                logger.error("LLM call failed after all retries: %s", e)
                return f"[Error during LLM call: {e}]"

            llm_calls += 1
            contents.append(response.candidates[0].content)
            function_call_found = False

            for part in response.candidates[0].content.parts:
                if getattr(part, "function_call", None):
                    function_call_found = True
                    function_call = part.function_call
                    try:
                        raw = await _with_retry(
                            self.connection_manager.call_tool,
                            function_call.name,
                            dict(function_call.args),
                            label=f"tool:{function_call.name}",
                        )
                        result = mcp_tool_result_to_payload(raw)
                    except Exception as e:
                        logger.error("Tool call '%s' failed after all retries: %s", function_call.name, e)
                        result = {"error": str(e)}
                    function_response_part = types.Part.from_function_response(
                        name=function_call.name,
                        response={"result": result},
                    )
                    contents.append(types.Content(role="user", parts=[function_response_part]))

            if not function_call_found:
                parts = response.candidates[0].content.parts
                text_result = "".join([p.text for p in parts if hasattr(p, "text") and p.text])
                logger.info("Final response after %d LLM calls: %s", llm_calls, text_result)
                return text_result

        logger.error("Maximum LLM call limit reached without a final answer.")
        return None

    async def _generate_content(self, contents, config):
        """Thin wrapper around the Gemini SDK so it can be passed to _with_retry."""
        return self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

    @opik.track(name="get-mcp-tools", type="general")
    async def get_mcp_tools(self) -> list[Tool]:
        tools = await self.connection_manager.get_mcp_tools()
        gemini_tools: list[Tool] = []
        for tool in tools.tools:
            schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
            if not isinstance(schema, dict):
                logger.warning("Skipping tool %s: missing input schema", tool.name)
                continue
            gemini_tools.append(
                types.Tool(
                    function_declarations=[
                        {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": strip_additional_properties({
                                k: v for k, v in schema.items() if k not in SKIPPABLE_PROPS
                            }),
                        }
                    ]
                )
            )
        return gemini_tools

    @opik.track(name="call-tool", type="tool")
    async def call_tool(self, function_name: str, function_args: dict) -> Any:
        if not self.connection_manager.is_initialized:
            raise RuntimeError("ConnectionManager is not initialized. Call initialize_all() first.")
        raw = await _with_retry(
            self.connection_manager.call_tool,
            function_name,
            function_args,
            label=f"tool:{function_name}",
        )
        return mcp_tool_result_to_payload(raw)

    @opik.track(name="cleanup", type="general")
    async def cleanup(self):
        await self.connection_manager.cleanup_all()
