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

import json
import os
from typing import Any, Optional

import httpx

DEFAULT_BASE = "https://integrate.api.nvidia.com/v1"
SUPER_MODEL = os.environ.get("NEMOTRON_SUPER_MODEL", "nvidia/nemotron-3-super-120b-a12b")
NANO_MODEL = os.environ.get("NEMOTRON_NANO_MODEL", "nvidia/nemotron-3-nano-30b-a3b")


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

    owned = client is None
    if owned:
        client = httpx.AsyncClient(timeout=timeout)
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
        content = data["choices"][0]["message"].get("content")
        return content or ""
    finally:
        if owned:
            await client.aclose()


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
        response_format={"type": "json_object"},
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
