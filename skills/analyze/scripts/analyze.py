#!/usr/bin/env python3
"""Analyze skill — POST to Acuity /api/analyze and print the RegimenReport to stdout.

Usage:
    python skills/analyze/scripts/analyze.py --drugs '["aspirin","warfarin"]'
    python skills/analyze/scripts/analyze.py --drugs '["aspirin","warfarin"]' --session-id abc123
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


API_BASE = os.environ.get("ACUITY_API_BASE_URL", "http://localhost:8081").rstrip("/")
TIMEOUT = 120.0  # pipeline can take time on cold start


def _auth_headers() -> dict[str, str]:
    pat = os.environ.get("ACUITY_PAT", "")
    if not pat:
        print("ERROR: ACUITY_PAT environment variable is not set", file=sys.stderr)
        sys.exit(1)
    return {"x-api-key": pat}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Acuity drug-interaction analyze skill")
    p.add_argument("--drugs", required=True, help="JSON array of drug name strings")
    p.add_argument("--session-id", dest="session_id", default=None, help="Reuse an existing session")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    try:
        drugs: list[str] = json.loads(args.drugs)
    except json.JSONDecodeError as e:
        print(f"ERROR: --drugs must be a JSON array of strings: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(drugs, list) or not all(isinstance(d, str) for d in drugs):
        print("ERROR: --drugs must be a JSON array of strings", file=sys.stderr)
        sys.exit(1)

    payload: dict = {"drugs": drugs}
    if args.session_id:
        payload["session_id"] = args.session_id

    url = f"{API_BASE}/api/analyze"
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_auth_headers()) as client:
            resp = client.post(url, json=payload)
    except httpx.ConnectError as e:
        print(f"ERROR: could not connect to {url}: {e}", file=sys.stderr)
        sys.exit(2)
    except httpx.HTTPError as e:
        print(f"ERROR: HTTP error calling {url}: {e}", file=sys.stderr)
        sys.exit(2)

    if resp.status_code >= 400:
        print(f"ERROR: API returned HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(2)

    body = resp.json()
    report = body.get("report", body)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
