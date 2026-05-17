"""Thin async wrapper around the Nemotron inference endpoint.

Speaks OpenAI's `/v1/chat/completions` schema, which both NVIDIA's hosted
NIM (`https://integrate.api.nvidia.com/v1`) and the local OpenShell gateway
expose. Configurable via env so the same code runs against:

  • NVIDIA integrate API (dev path) — set `NVIDIA_API_KEY` + `NEMOTRON_*`.
  • OpenShell gateway inside the NemoClaw sandbox (demo path) — uses the
    in-sandbox routing automatically; we only need to override
    `OPENAI_BASE_URL` and the gateway-injected token.

If `NVIDIA_API_KEY` is missing the client raises on use. Callers that want
an offline fallback should catch `LLMUnavailable`.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import os
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv


def _load_project_env() -> None:
    """Load the repo's .env no matter which entrypoint imported this module.

    The FastAPI app loads dotenv in `backend.main`, but scripts like
    `scripts/iterate_synthesis.py` and direct `backend.graph` imports bypass
    that file entirely. Loading here keeps the LLM path consistent across the
    API, local scripts, and sandbox smoke tests.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


_load_project_env()

DEFAULT_BASE = "https://integrate.api.nvidia.com/v1"
SUPER_MODEL = os.environ.get("NEMOTRON_SUPER_MODEL", "nvidia/nemotron-3-super-120b-a12b")
NANO_MODEL = os.environ.get("NEMOTRON_NANO_MODEL", "nvidia/nemotron-3-nano-30b-a3b")

# ContextVar lets each SSE request register its own rate-limit notification queue.
# asyncio.create_task copies the current context, so child tasks automatically
# inherit whatever queue the SSE generator set before spawning the pipeline.
rate_limit_sink: contextvars.ContextVar[asyncio.Queue | None] = contextvars.ContextVar(
    "rate_limit_sink", default=None
)

# Parallel sink for agent decision events (quality-check, research steps, drug repair).
agent_decision_sink: contextvars.ContextVar[asyncio.Queue | None] = contextvars.ContextVar(
    "agent_decision_sink", default=None
)


def emit_agent_decision(payload: dict) -> None:
    """Non-blocking push of an agent decision event to the current SSE sink."""
    sink = agent_decision_sink.get()
    if sink is not None:
        sink.put_nowait(payload)


class _RateLimiter:
    """Leaky-bucket meter: spaces LLM requests evenly to stay under rpm/minute."""

    def __init__(self, rpm: int) -> None:
        self._interval = 60.0 / rpm
        self._next_allowed: float = 0.0
        self._lock: asyncio.Lock | None = None  # created lazily inside the event loop

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def acquire(self) -> float:
        """Reserve a slot. Returns seconds waited (0.0 if no wait needed)."""
        async with self._get_lock():
            now = asyncio.get_event_loop().time()
            wait = max(0.0, self._next_allowed - now)
            self._next_allowed = max(now, self._next_allowed) + self._interval

        if wait > 0.1:
            sink = rate_limit_sink.get()
            if sink is not None:
                sink.put_nowait({"waiting_seconds": round(wait, 1)})
            await asyncio.sleep(wait)

        return wait


_limiter = _RateLimiter(int(os.environ.get("LLM_RPM", "40")))


class LLMUnavailable(RuntimeError):
    """Raised when no API key/base is configured. Callers may fall back."""


def _base_url() -> str:
    return os.environ.get("OPENAI_BASE_URL") or os.environ.get("NEMOTRON_BASE_URL") or DEFAULT_BASE


def _api_key() -> str:
    key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise LLMUnavailable(
            "Neither NVIDIA_API_KEY nor OPENAI_API_KEY set — Nemotron unreachable. "
            "Set one in .env or run inside the NemoClaw sandbox."
        )
    return key


def _extract_message_text(message: dict[str, Any]) -> str | None:
    """Return assistant text across providers' message shapes."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        joined = "".join(parts).strip()
        return joined or None
    return None


async def chat(
    *,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    response_format: Optional[dict[str, Any]] = None,
    client: Optional[httpx.AsyncClient] = None,
    timeout: float = 45.0,
) -> str:
    """Single round-trip chat call. Returns the assistant message content."""
    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if response_format is not None:
        payload["response_format"] = response_format

    await _limiter.acquire()

    owned = client is None
    if owned:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=timeout, write=30.0, pool=5.0)
        )
    try:
        r = await client.post(
            f"{_base_url()}/chat/completions",
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        choice = data["choices"][0]
        message = choice["message"]
        content = _extract_message_text(message)
        if content is not None:
            return content

        finish_reason = choice.get("finish_reason")
        has_reasoning = bool(message.get("reasoning_content"))
        raise RuntimeError(
            "LLM response did not include assistant content "
            f"(finish_reason={finish_reason!r}, reasoning_only={has_reasoning})"
        )
    finally:
        if owned:
            await client.aclose()


def _supports_json_object_format() -> bool:
    """LM Studio only accepts json_schema/text; hosted NVIDIA NIM accepts json_object."""
    base = _base_url()
    return "127.0.0.1" not in base and "localhost" not in base


async def chat_json(
    *,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    client: Optional[httpx.AsyncClient] = None,
    timeout: float = 45.0,
) -> Any:
    """Chat call that expects a JSON-parseable response. Strips code fences."""
    raw = await chat(
        model=model,
        system=system,
        user=user,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"} if _supports_json_object_format() else None,
        client=client,
        timeout=timeout,
    )
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # ```json\n{...}\n```
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)
