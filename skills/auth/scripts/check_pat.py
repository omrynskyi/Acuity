#!/usr/bin/env python3
"""Verify that ACUITY_PAT is set and accepted by the Acuity API.

Exit codes:
    0 — token is loadable AND the API accepts it.
    1 — no token is loadable from env or ~/.openclaw/.env.
    2 — token is loadable but the API rejected it or could not be reached.
"""

from __future__ import annotations

import os
import pathlib
import sys

import httpx


API_BASE = "https://acuity.onrender.com"
TIMEOUT = 15.0
SETTINGS_URL = "https://tryacuity.vercel.app/settings"


def _load_dotenv() -> None:
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


def main() -> None:
    _load_dotenv()
    pat = os.environ.get("ACUITY_PAT", "").strip()
    if not pat:
        print(
            f"NOT AUTHENTICATED: no ACUITY_PAT found. Generate one at {SETTINGS_URL} "
            f"and run `python3 /sandbox/.openclaw/skills/auth/scripts/set_pat.py --pat <token>`.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with httpx.Client(timeout=TIMEOUT, headers={"x-api-key": pat}) as c:
            resp = c.get(f"{API_BASE}/api/user/profile")
    except httpx.HTTPError as e:
        print(f"ERROR: could not reach Acuity API at {API_BASE}: {e}", file=sys.stderr)
        sys.exit(2)

    if resp.status_code in (401, 403):
        print(
            f"TOKEN REJECTED (HTTP {resp.status_code}). Generate a new PAT at {SETTINGS_URL} "
            f"and run `python3 /sandbox/.openclaw/skills/auth/scripts/set_pat.py --pat <token>`.",
            file=sys.stderr,
        )
        sys.exit(2)

    if resp.status_code >= 400:
        print(f"ERROR: Acuity API returned HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        sys.exit(2)

    print("OK: ACUITY_PAT is set and accepted by the Acuity API.")


if __name__ == "__main__":
    main()
