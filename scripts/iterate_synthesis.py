"""BE-09 prompt-iteration harness.

Runs the synthesis agent against the four required test cases (PRD §9) and
prints a side-by-side report. Use this every time `prompts/synthesis.md`
changes. The check is human-in-the-loop — the rubric in the PRD says the
output passes if severity is correct, citations are faithful, and
disagreement is explicit where it exists.

Requires NVIDIA_API_KEY (or OPENAI_API_KEY) in the environment. Without it
the script falls through to the deterministic synthesizer and prints a
warning — useful for smoke-testing the pipeline plumbing, not for prompt
iteration.

Usage: `python scripts/iterate_synthesis.py`
"""

from __future__ import annotations

import asyncio
import os
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.fanout import fanout_pair  # noqa: E402
from backend.synthesis import synthesize_pair  # noqa: E402

# (label, drug_a, drug_b, expected_severity_floor, notes)
CASES = [
    (
        "calibration baseline",
        "warfarin", "aspirin",
        "major",
        "All three sources agree on major bleeding risk. If model says < major, prompt is broken.",
    ),
    (
        "subtle reasoning",
        "fluoxetine", "tramadol",
        "major",
        "Label cites serotonin syndrome narratively; FAERS surfaces it explicitly; TWOSIDES PRR=8.81. "
        "Watch for reasoning that explains *why* this beats the noisier FAERS signals.",
    ),
    (
        "calibration check",
        "metformin", "lisinopril",
        "minor",  # we want minor, not moderate or major
        "Commonly co-prescribed, real but modest risk. Watch for over-calling. "
        "Acceptable: minor with monitoring. Unacceptable: major.",
    ),
    (
        "deliberate disagreement — sparse coverage",
        "warfarin", "omeprazole",
        "minor",
        "TWOSIDES has both drugs but no seeded association (full coverage, zero findings). "
        "Label is silent. FAERS shows weak GI signal. The model must reason explicitly "
        "about partial silence and avoid silently picking a winner.",
    ),
]


def _api_key_present() -> bool:
    return bool(os.environ.get("NVIDIA_API_KEY") or os.environ.get("OPENAI_API_KEY"))


async def main() -> int:
    key = _api_key_present()
    if not key:
        print(
            "⚠  NVIDIA_API_KEY not set — running the deterministic fallback, "
            "not the Nemotron path. Set the key to iterate the prompt.\n"
        )

    overall_ok = True
    for label, a, b, floor, notes in CASES:
        print("=" * 78)
        print(f"CASE: {label}  ({a} + {b})")
        print(f"  expected severity ≥ {floor}")
        print(f"  notes: {notes}")
        print("-" * 78)

        sources = await fanout_pair(a, b)
        for s in sources:
            print(f"  {s.source:14s} coverage={s.coverage.value:8s} "
                  f"confidence={s.confidence.value:6s} findings={len(s.findings)}")

        synth = await synthesize_pair((a, b), sources)
        print()
        print(f"  → severity:           {synth.severity.value}")
        print(f"  → agreement:          {synth.sources_agreement}")
        print(f"  → predicted_unverif.: {synth.predicted_but_unverified}")
        print(f"  → headline:           {synth.headline}")
        print("  → reasoning:")
        for line in textwrap.wrap(synth.reasoning, width=72):
            print(f"      {line}")
        print(f"  → citations ({len(synth.citations)}):")
        for c in synth.citations:
            print(f"      [{c.source}#{c.finding_index}] {c.quote[:120]}")

        # Soft check (informational; the human in the loop is the real gate).
        sev_rank = {
            "no_concern": 0, "minor": 1, "moderate": 2, "major": 3, "contraindicated": 4
        }
        floor_rank = sev_rank[floor]
        actual_rank = sev_rank[synth.severity.value]
        if actual_rank < floor_rank:
            print(f"\n  ❌ severity below expected floor ({synth.severity.value} < {floor})")
            overall_ok = False
        print()

    print("=" * 78)
    print(f"overall: {'OK' if overall_ok else 'NEEDS WORK'}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
