# Acuity — handoff to Person B

Hey — Person A here. Backend is in. This doc tells you what's wired, what's
still on you, and the gotchas I'd hit if I were picking up where you are
right now. Cross-reference [`TASKS.md`](TASKS.md) for the full task list;
all my IDs below match.

## TL;DR

- All backend `BE-*` tasks except **BE-09** are `[DONE]` in TASKS.md.
- `BE-09` (synthesis prompt iteration) is human-in-the-loop and needs a
  live `NVIDIA_API_KEY` — see "Things still on someone (maybe you)" below.
- Everything you need to build the frontend against is real and running:
  `POST /api/analyze`, `GET /api/policy`, `GET /api/audit-log`,
  `POST /api/attack-case`.
- Fixtures and the locked JSON schema are committed. Build against
  `samples/fixtures.json` first, swap to the real backend at FE-05.

## ✓ TWOSIDES leg is now real (was previously hand-authored)

**Resolved.** The TWOSIDES source agent now queries `data/decagon.sqlite`,
built from the **SNAP Decagon dataset** (Zitnik et al., *Bioinformatics*
2018, [snap.stanford.edu/decagon](https://snap.stanford.edu/decagon/)) — a
curated 4.65M-row TWOSIDES extract covering 645 drugs and 1,317 UMLS-coded
condition types. Every effect citation in the report panel is now a real
observed polypharmacy side effect from a peer-reviewed dataset; no
fabricated PRR values anywhere.

To rebuild from scratch (one-time, ~50s end-to-end):

```bash
python scripts/build_decagon.py --all   # CSV load + PubChem name-to-CID bridge
pytest tests/test_decagon.py -v          # 17 tests, all pass with SQLite present
```

**Coverage gap to flag:** Decagon's 645 drugs are a 2018 snapshot. Several
common drugs from our demo regimen — tramadol, lisinopril, clopidogrel,
atorvastatin — are *not* in the dataset. Pairs involving them surface
`Coverage.NO_DATA` from the TWOSIDES leg honestly; OpenFDA Label + FAERS
still cover them, and synthesis reconciles from two sources instead of
three. This is now a documented limitation rather than a fabrication.

### ⚠ Remaining TODO(synthetic-data) — `samples/fixtures.json`

The frontend dev fixture (`samples/fixtures.json`, built by
`scripts/build_fixtures.py`) is still hand-authored. Trivial to regenerate
from the now-real pipeline:

```bash
uvicorn backend.main:app --port 8000 &
curl -s -X POST http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"drugs":["warfarin","aspirin","fluoxetine","tramadol","metformin","lisinopril"],"session_id":"fixture-gen"}' \
  | jq '.report' > samples/fixtures.json
```

After that, every value in the repo is real. `grep -rn "TODO(synthetic-data)" .`
should return only the `scripts/build_fixtures.py` and
`scripts/build_twosides.py` (deprecated, kept as fallback) markers.

## What's already done on the backend (so you can rely on it)

| Task | Where it lives | What you can do with it |
|---|---|---|
| JOINT-00 | `docs/access-verification.md` | Confirm Brev + NemoClaw are reachable; provider creds live in OpenShell. |
| BE-01 | repo scaffold, `pyproject.toml`, `.env.example` | `uv venv` + `uv pip install` (recipe in `README.md`). |
| BE-02 | `samples/openfda_*.json`, `samples/rxnorm_*.json`, `samples/pubchem_*.json` | Real responses for mocking offline. |
| BE-03 | `data/decagon.sqlite` (built by `scripts/build_decagon.py --all`) | Real SNAP Decagon TWOSIDES extract — 4.65M observed pair-effect rows. |
| JOINT-01 | `backend/schemas.py` + `samples/fixtures.json` (`scripts/build_fixtures.py`) | **The contract.** 9 source findings + 1 full report ready to render. Locked at H1 — ping me before changing. |
| JOINT-02 (joint slice) | `docs/demo-cases.md` | Primary regimen, follow-up case, attack case all picked. Design slice (visual identity, mockups) is still on you. |
| BE-04 | `backend/sources/rxnorm.py` | `normalize_drug("Tylenol")` → acetaminophen; `normalize_regimen([...])` batches. |
| BE-05/06/07 | `backend/sources/{openfda_label,openfda_faers,twosides}.py` | All three return `SourceFindings`. Fanout helper at `backend/fanout.py`. |
| BE-08 | `backend/synthesis.py`, prompt at `prompts/synthesis.md` | `synthesize_pair(pair, sources)` → `SynthesizedInteraction`. Falls back deterministically when no API key. |
| BE-10 | `backend/report.py` | `build_report(...)` → `RegimenReport`. Patient-friendly text via nano-30b with template fallback. |
| BE-11 | `backend/graph.py` + `backend/main.py` | `POST /api/analyze` runs the full LangGraph. ~2.3s on host for a 4-drug regimen. |
| BE-12 | `backend/memory.py` | Per-`session_id` cache. Send the same `session_id` on follow-up and you'll get delta-only `new_pairs` + `cached_pairs`. |
| BE-13 | `policies/policy.yaml` (+ `policy-bootstrap.yaml`) | Locked NemoClaw policy — 4 hosts allowlisted, everything else denied. Already applied to the live sandbox. |
| BE-14 | `samples/nemoclaw_audit_full_run.log` | Real audit log with both ALLOWED and DENIED entries. Backend confirmed running end-to-end *inside* the NemoClaw sandbox under the locked policy. |
| BE-15 | `/api/policy`, `/api/audit-log`, `/api/attack-case` | All three FastAPI endpoints. The attack endpoint returns a structured `{attempted, blocked, detail, audit_excerpt}` payload — easy to render. |
| BE-16/17 | `README.md`, `README-NEMOCLAW.md` | Both track READMEs. Update the demo-video link when FE-07 is recorded. |

## What's still on someone (maybe you, maybe me, mostly humans)

### BE-09 — synthesis prompt iteration (needs API key + human eyes)
**Status:** `[IN PROGRESS]`. The harness, prompt, and parser are ready.
The hardening I added handles the malformed `": major"` strings that
Nemotron occasionally emitted during my sandbox run, so it won't crash —
but the prompt still needs a real iteration loop. To run:

```
openshell sandbox exec -n nemoclaw -- /bin/sh -c \
  'cd /sandbox/Acuity && PYTHONPATH=. .venv-sandbox/bin/python \
   scripts/iterate_synthesis.py'
```

You'll see four cases (warfarin+aspirin, fluoxetine+tramadol,
metformin+lisinopril, warfarin+omeprazole). Edit `prompts/synthesis.md`,
re-run, watch the severity / reasoning / citations. PRD §9 has the
rubric. **This is the task to protect** — if we're behind, this is what
we keep iterating, per the TASKS.md note at the bottom of BE-09.

### JOINT-02 design slice
Person B subtasks 5–7 (visual identity, layout sketch, key-state mockups).
Joint demo cases are documented; design direction isn't.

### All `FE-*` tasks (yours)

Order matches dependencies in TASKS.md:

- **FE-01** — Vite/React scaffold, no Tailwind. Load
  `samples/fixtures.json` (committed). Mock API module with an env toggle
  for swapping to the real backend at FE-05.
- **FE-02** — Agent graph + report-panel scaffolds. The graph has 5 nodes
  matching the LangGraph node names: `intake`, `memory`, `fanout`,
  `synthesis`, `report`. The `/api/analyze` response includes
  `durations_ms` keyed exactly like that — feed it straight into node
  state.
- **FE-03** — synthesis moment (the demo peak) and the patient/clinician
  toggle. `RegimenReport.interactions[].reasoning` is the chain-of-thought
  payload to reveal here. `patient_friendly_summary` is the toggle target.
- **FE-04** — written 3-min demo script. PRD §15 has the structure.
- **FE-05** — swap mock for real `POST /api/analyze`. Send a stable
  `session_id` to make the memory demo work. Follow-up = same
  `session_id` + extra drug → `report.new_pairs` is the delta.
- **FE-06** — NemoClaw moment. `POST /api/attack-case` takes a `target`
  query param, returns `{target, attempted, blocked, detail,
  audit_excerpt}`. Render `audit_excerpt` lines verbatim — they include
  `DENIED ... -> attacker.invalid:443 [policy:- engine:opa]` which is the
  visual money shot. `GET /api/policy` returns
  `{yaml, allowlist}` — use the `allowlist` array to render the four hosts
  as chips/badges, and surface the raw `yaml` on demand.
- **FE-07** — record backup video after JOINT-04. Update the README link.

### Joint tasks coming up
JOINT-03 (full run-through), JOINT-04 (fix top 3 issues), JOINT-05
(rehearse 3×), JOINT-06 (submit). All require both of us.

## Stuff I learned the hard way — read before you build

1. **PRD §11 specifies no Tailwind.** I haven't picked a CSS approach for
   you — CSS modules is the lowest-friction option, but yours to choose
   per FE-01 step 2.
2. **The schema is locked** (`backend/schemas.py`). If you need to add a
   field, ping me first (CLAUDE.md hard rule, and `tests/test_schemas.py`
   will fail loudly).
3. **`drug_pair` is normalized to `(lowercase, sorted)`** in
   `SourceFindings`. So when you render
   `interaction.drug_pair[0]` + `drug_pair[1]`, expect alphabetical
   order. If you want the user's input order, look at the original
   `report.regimen[].input_name` list.
4. **Synthesis latency under NemoClaw was ~45s** for 6 pairs in my
   sandbox run because Nemotron round-trips serialize on the gateway path.
   On the host with a direct API key it's a couple of seconds. Two
   reasonable knobs: (a) pre-cache the primary regimen's report at H21
   and serve it locally during the live demo (PRD §15 explicitly endorses
   this), or (b) tighten the synthesis `asyncio.gather` parallelism.
   Either way, the agent-graph node states should animate to mask the
   wait — the synthesis node is supposed to be the theatrical peak
   anyway.
5. **Patient summary** falls back to a template string when no API key is
   present. Will look flat in dev. Don't panic — it gets rich in the
   sandbox.
6. **The attack-case endpoint** behaves differently on host vs. sandbox.
   On host you'll see `"detail": "Name or service not known"` and
   `blocked: false` (DNS just fails). Inside the NemoClaw sandbox the
   policy intercepts at CONNECT and `audit_excerpt` carries the actual
   DENIED line. For dev, my endpoint falls back to surfacing DENIED
   lines from `samples/nemoclaw_audit_full_run.log` so the panel never
   renders empty.
7. **The bootstrap policy** (`policies/policy-bootstrap.yaml`) is
   bootstrap-only. Don't ship it. The demo-time policy is
   `policies/policy.yaml`, and it's already applied (`openshell policy
   get nemoclaw` confirms version 4 loaded).

## Quick sanity loop (paste into a shell)

```bash
source .venv/bin/activate

# 1) Backend
uvicorn backend.main:app --port 8000 &

# 2) Initial analyze
curl -s -X POST http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"drugs":["warfarin","aspirin","fluoxetine","tramadol"],"session_id":"demo"}' \
  | jq '.report.interactions[] | {severity, drug_pair, headline}'

# 3) Memory delta (add ibuprofen, same session)
curl -s -X POST http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"drugs":["warfarin","aspirin","fluoxetine","tramadol","ibuprofen"],"session_id":"demo"}' \
  | jq '{new_pairs: .report.new_pairs, cached: .report.cached_pairs|length}'

# 4) NemoClaw demo surfaces
curl -s http://localhost:8000/api/policy     | jq '.allowlist'
curl -s 'http://localhost:8000/api/audit-log?limit=5' | jq '.lines'
curl -s -X POST 'http://localhost:8000/api/attack-case' | jq
```

Good luck — ping me if anything in the schema or pipeline isn't doing what
the docstring says.

— Person A
