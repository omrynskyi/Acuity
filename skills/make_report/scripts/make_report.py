#!/usr/bin/env python3
"""MakeReport skill — parse a report JSON and generate a PDF.

Usage:
    python skills/make_report/scripts/make_report.py --in /tmp/report.json
    python skills/make_report/scripts/make_report.py --in /tmp/report.json --out /session/reports/out.pdf
    cat report.json | python skills/make_report/scripts/make_report.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Scripts in the same directory are importable when running from the project root
# via `python skills/make_report/scripts/make_report.py`, but the CWD may vary.
# We insert the scripts dir so sibling modules are always found.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import render_deep_research
import render_regimen


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Acuity make_report skill")
    p.add_argument("--in", dest="infile", default=None, help="Path to report JSON (omit to read stdin)")
    p.add_argument("--out", dest="outfile", default=None, help="Output PDF path")
    return p.parse_args()


def _default_out() -> str:
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path("/session/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    return str(out_dir / f"report_{ts}.pdf")


def detect_schema(data: dict) -> str:
    """Return 'regimen' or 'deep_research'; raise ValueError on unrecognised shape."""
    if data.get("report_type") == "deep_research":
        return "deep_research"
    if data.get("schema_version") == "1.0" and "interactions" in data:
        return "regimen"
    raise ValueError(
        "Unrecognised report schema. Expected schema_version='1.0' with 'interactions' key "
        "(RegimenReport) or report_type='deep_research' (DeepResearchReport)."
    )


def main() -> None:
    args = parse_args()

    if args.infile:
        try:
            raw = Path(args.infile).read_text()
        except OSError as e:
            print(f"ERROR: cannot read {args.infile}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        raw = sys.stdin.read()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        schema = detect_schema(data)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = args.outfile or _default_out()

    try:
        if schema == "regimen":
            render_regimen.render(data, out_path)
        else:
            render_deep_research.render(data, out_path)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: PDF generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(out_path)


if __name__ == "__main__":
    main()
