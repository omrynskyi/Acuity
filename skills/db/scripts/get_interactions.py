#!/usr/bin/env python3
"""Get the severity-sorted interaction rows for a past analysis session.

Usage:
    python skills/db/scripts/get_interactions.py --session-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _client import api_get


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Get interactions for a session")
    p.add_argument("--session-id", required=True, dest="session_id", help="Session UUID")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    interactions = api_get(f"/api/user/sessions/{args.session_id}/interactions")
    print(json.dumps(interactions, indent=2, default=str))


if __name__ == "__main__":
    main()
