"""Quick smoke test: run the LangGraph pipeline inside the NemoClaw sandbox.

Uploaded to /sandbox/Acuity and invoked from there. Exists so the demo can
prove the backend runs under the locked policy.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.graph import run_analysis


async def main() -> None:
    t0 = time.perf_counter()
    state = await run_analysis(
        "sandbox-smoke", ["warfarin", "aspirin", "fluoxetine", "tramadol"]
    )
    dt = time.perf_counter() - t0
    report = state["report"]
    print(f"== sandbox run finished in {dt:.2f}s ==")
    print("overall:", report.overall_summary)
    print("durations:", state["durations_ms"])
    for i in report.interactions:
        print(f"  {i.severity.value:13s} {i.drug_pair[0]} + {i.drug_pair[1]}")


if __name__ == "__main__":
    asyncio.run(main())
