#!/usr/bin/env python3
"""DeepResearch skill — run a multi-query Brave research loop for a single drug.

Usage:
    python skills/deep_research/scripts/deep_research.py --drug "metformin"
    python skills/deep_research/scripts/deep_research.py --drug "rivaroxaban" --out /tmp/riv.json --depth 8
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "WARNING"), stream=sys.stderr)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from brave_search import BraveSearchError, search  # noqa: E402
from synthesize import ASPECTS, synthesize_drug  # noqa: E402

QUERY_TEMPLATES = {
    "mechanism": "{drug} mechanism of action pharmacology",
    "indications": "{drug} clinical indications uses approved",
    "contraindications": "{drug} contraindications who should not take",
    "adverse_events": "{drug} adverse effects side effects safety",
    "interactions": "{drug} drug interactions pharmacokinetic clinical",
    "pharmacokinetics": "{drug} pharmacokinetics absorption distribution metabolism excretion",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Acuity DeepResearch skill")
    p.add_argument("--drug", required=True, help="Drug name to research")
    p.add_argument("--out", default=None, help="Write JSON to file (default: stdout)")
    p.add_argument("--depth", type=int, default=5, help="Brave results per query (default: 5)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    drug = args.drug.strip()

    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        print("ERROR: NVIDIA_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("NEMOTRON_SUPER_MODEL", "nvidia/nemotron-3-super-120b-a12b")

    # Fan out Brave searches per aspect
    evidence: dict[str, list[dict]] = {}
    for aspect in ASPECTS:
        query = QUERY_TEMPLATES[aspect].format(drug=drug)
        try:
            results = search(query, count=args.depth)
            evidence[aspect] = results
        except BraveSearchError as e:
            print(f"ERROR: Brave search failed for aspect '{aspect}': {e}", file=sys.stderr)
            sys.exit(1)

    # Deduplicate URLs across aspects (keep first occurrence per URL)
    seen_urls: set[str] = set()
    for aspect, results in evidence.items():
        deduped = []
        for r in results:
            url = r.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                deduped.append(r)
        evidence[aspect] = deduped

    # Synthesize with Nemotron
    try:
        report = synthesize_drug(drug, evidence, model, api_key)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: synthesis failed: {e}", file=sys.stderr)
        sys.exit(1)

    output = json.dumps(report, indent=2, default=str)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(output)
        print(args.out)
    else:
        print(output)


if __name__ == "__main__":
    main()
