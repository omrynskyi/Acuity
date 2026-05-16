"""Shared HTTP client for DB skill scripts.

All calls go to the Acuity API (ACUITY_API_BASE_URL) with the user's PAT
as the ``x-api-key`` header. The Acuity API validates the PAT and scopes
all DB queries to the matching profile.
"""

from __future__ import annotations

import json
import os
import sys

import httpx

API_BASE = os.environ.get("ACUITY_API_BASE_URL", "http://localhost:8081").rstrip("/")
TIMEOUT = 30.0


def auth_headers() -> dict[str, str]:
    pat = os.environ.get("ACUITY_PAT", "")
    if not pat:
        print("ERROR: ACUITY_PAT environment variable is not set", file=sys.stderr)
        sys.exit(1)
    return {"x-api-key": pat, "Content-Type": "application/json"}


def _handle(resp: httpx.Response) -> dict | list:
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
