#!/usr/bin/env python3
"""Soft-delete a medication from the user's active list (sets removed_at = now()).

Usage:
    python skills/db/scripts/remove_medicine.py --id <uuid>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _client import api_delete


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Remove a medication from the active list")
    p.add_argument("--id", required=True, dest="entry_id", help="Regimen entry UUID")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    api_delete(f"/api/user/medicines/{args.entry_id}")
    print(f"Removed medication {args.entry_id}")


if __name__ == "__main__":
    main()
