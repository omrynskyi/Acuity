#!/usr/bin/env python3
"""Update dose or frequency for a medication in the active list.

Usage:
    python skills/db/scripts/update_medicine.py --id <uuid> --dose "1000mg"
    python skills/db/scripts/update_medicine.py --id <uuid> --frequency "once daily"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _client import api_patch


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Update a medication entry")
    p.add_argument("--id", required=True, dest="entry_id", help="Regimen entry UUID")
    p.add_argument("--dose", default=None)
    p.add_argument("--frequency", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    patch = {}
    if args.dose:
        patch["dose"] = args.dose
    if args.frequency:
        patch["frequency"] = args.frequency
    if not patch:
        print("ERROR: provide --dose or --frequency", file=sys.stderr)
        sys.exit(1)
    updated = api_patch(f"/api/user/medicines/{args.entry_id}", patch)
    print(json.dumps(updated, indent=2, default=str))


if __name__ == "__main__":
    main()
