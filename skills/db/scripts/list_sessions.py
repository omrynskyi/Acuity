#!/usr/bin/env python3
"""List the user's past drug-interaction analysis sessions.

Usage:
    python skills/db/scripts/list_sessions.py
    python skills/db/scripts/list_sessions.py --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _client import api_get


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="List past analysis sessions")
    p.add_argument("--limit", type=int, default=20, help="Max results (default 20)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    sessions = api_get("/api/user/sessions", limit=args.limit)
    print(json.dumps(sessions, indent=2, default=str))


if __name__ == "__main__":
    main()
