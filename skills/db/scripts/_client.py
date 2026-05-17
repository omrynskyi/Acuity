"""Shared HTTP client for DB skill scripts.

All calls go to the Acuity API (ACUITY_API_BASE_URL) with the user's PAT
as the ``x-api-key`` header. The Acuity API validates the PAT and scopes
all DB queries to the matching profile.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

import httpx


def _load_dotenv() -> None:
    # Non-interactive bash shells (e.g. the OpenClaw exec tool's `bash -c`) do not
    # source ~/.bashrc, so interactively-exported vars are invisible there. Read
    # ~/.openclaw/.env into os.environ for any keys not already set.
    candidates = [
        pathlib.Path.home() / ".openclaw" / ".env",
        pathlib.Path("/sandbox/.openclaw/.env"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        break


_load_dotenv()

API_BASE = "https://acuity.onrender.com"
TIMEOUT = 30.0


SETTINGS_URL = "https://tryacuity.vercel.app/settings"
SET_PAT_CMD = "python3 /sandbox/.openclaw/skills/auth/scripts/set_pat.py --pat <token>"


def _print_login_prompt(reason: str) -> None:
    print(
        f"NOT AUTHENTICATED: {reason}\n"
        f"  1. Generate a Personal Access Token at {SETTINGS_URL}\n"
        f"  2. Save it with: {SET_PAT_CMD}",
        file=sys.stderr,
    )


def auth_headers() -> dict[str, str]:
    pat = os.environ.get("ACUITY_PAT", "")
    if not pat:
        _print_login_prompt("ACUITY_PAT is not set.")
        sys.exit(1)
    return {"x-api-key": pat, "Content-Type": "application/json"}


def _handle(resp: httpx.Response) -> dict | list:
    if resp.status_code in (401, 403):
        _print_login_prompt(f"the stored ACUITY_PAT was rejected (HTTP {resp.status_code}).")
        sys.exit(2)
    if resp.status_code >= 400:
        print(f"ERROR: API returned HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(2)
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


def api_get(path: str, **params) -> dict | list:
    url = f"{API_BASE}{path}"
    try:
        with httpx.Client(timeout=TIMEOUT, headers=auth_headers()) as c:
            return _handle(c.get(url, params=params or None))
    except httpx.ConnectError as e:
        print(f"ERROR: could not connect to {url}: {e}", file=sys.stderr)
        sys.exit(2)


def api_post(path: str, body: dict) -> dict | list:
    url = f"{API_BASE}{path}"
    try:
        with httpx.Client(timeout=TIMEOUT, headers=auth_headers()) as c:
            return _handle(c.post(url, json=body))
    except httpx.ConnectError as e:
        print(f"ERROR: could not connect to {url}: {e}", file=sys.stderr)
        sys.exit(2)


def api_patch(path: str, body: dict) -> dict | list:
    url = f"{API_BASE}{path}"
    try:
        with httpx.Client(timeout=TIMEOUT, headers=auth_headers()) as c:
            return _handle(c.patch(url, json=body))
    except httpx.ConnectError as e:
        print(f"ERROR: could not connect to {url}: {e}", file=sys.stderr)
        sys.exit(2)


def api_delete(path: str) -> None:
    url = f"{API_BASE}{path}"
    try:
        with httpx.Client(timeout=TIMEOUT, headers=auth_headers()) as c:
            _handle(c.delete(url))
    except httpx.ConnectError as e:
        print(f"ERROR: could not connect to {url}: {e}", file=sys.stderr)
        sys.exit(2)
