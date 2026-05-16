#!/usr/bin/env python3
"""Add a drug to the user's active medication list.

Usage:
    python skills/db/scripts/add_medicine.py --drug "metformin"
    python skills/db/scripts/add_medicine.py --drug "metformin" --dose "500mg" --frequency "twice daily"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _client import api_post


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Add a medication to the active list")
    p.add_argument("--drug", required=True, help="Drug name (generic or brand)")
    p.add_argument("--dose", default=None, help='e.g. "500mg"')
    p.add_argument("--frequency", default=None, help='e.g. "twice daily"')
    return p.parse_args()


def main() -> None:
    args = parse_args()
    body: dict = {"drug": args.drug}
    if args.dose:
        body["dose"] = args.dose
    if args.frequency:
        body["frequency"] = args.frequency
    entry = api_post("/api/user/medicines", body)
    print(json.dumps(entry, indent=2, default=str))


if __name__ == "__main__":
    main()
