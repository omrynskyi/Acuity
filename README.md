# Acuity

**Cloud track:** Brev + Nemotron multi-agent drug-interaction checker.
**NemoClaw track:** the same agent system wrapped in OpenShell policy for
PHI containment and API whitelist enforcement (see
[`README-NEMOCLAW.md`](README-NEMOCLAW.md)).

Polypharmacy patients (5+ concurrent meds) account for roughly 40% of
adults 65+. A 10-drug regimen has 45 unique drug pairs. Physicians have
about five seconds to review a list before discharge, and no single data
source has complete interaction coverage. Acuity fans out across three
heterogeneous sources in parallel, uses Nemotron to reconcile the conflicts,
and returns a severity-ranked report with citations.

## Architecture

```
USER INPUT  →  medication list

INTAKE                LangGraph: intake_node
  ├── RxNorm normalisation (brand → ingredient)
  ├── pairwise combination generation
  └── memory check (skip pairs already evaluated)

PARALLEL QUERY        LangGraph: fanout_node  →  backend.fanout.fanout_pairs
  ├── OpenFDA Label   regulatory warnings, Nemotron nano-30b parses sections
  ├── OpenFDA FAERS   adverse-event co-reports via /count aggregation
  └── TWOSIDES        curated statistical signals (PRR), SQLite

SYNTHESIS             LangGraph: synthesis_node  →  backend.synthesis
  Nemotron super-120b reasons over all source findings for each pair,
  produces severity + reasoning + citations in strict JSON. Falls back to a
  deterministic synthesiser when no NVIDIA_API_KEY is set.

REPORT                LangGraph: report_node
  Sorted by severity, plain-language patient summary via nano-30b.

MEMORY                backend.memory.SessionMemory
  Keyed by session_id; follow-up queries only fan-out on the delta.
```

Live demo on a 6-drug regimen runs in under 5 seconds on host with cached
synthesis; ~50s under the NemoClaw policy when synthesis hits Nemotron live.

## Quick start

### Prerequisites
- Python 3.11+
- `uv` (recommended) or `pip`
- `NVIDIA_API_KEY` (set in `.env`) for the synthesis Nemotron path

### Install
```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install langgraph fastapi 'uvicorn[standard]' httpx pydantic python-dotenv openai pytest pytest-asyncio
python scripts/build_decagon.py --all   # builds data/decagon.sqlite (~50s)
python scripts/build_fixtures.py        # builds samples/fixtures.json (frontend dev only)
```

### Run
```bash
uvicorn backend.main:app --port 8000

# in another shell
curl -X POST http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"drugs":["warfarin","aspirin","fluoxetine","tramadol"],"session_id":"demo"}' \
  | jq .
```

Follow-up queries reuse the cached findings:

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"drugs":["warfarin","aspirin","fluoxetine","tramadol","ibuprofen"],"session_id":"demo"}' \
  | jq '.report.new_pairs, .report.cached_pairs'
```

The follow-up evaluates only the 4 new ibuprofen pairs.

### Run the synthesis prompt iteration harness (BE-09)

```bash
python scripts/iterate_synthesis.py
```

Exercises four adversarial cases: warfarin+aspirin (anchor), fluoxetine+
tramadol (subtle serotonin syndrome), metformin+lisinopril (calibration),
warfarin+omeprazole (sparse coverage / disagreement).

## Data sources

| Source | Endpoint | Auth | Used for |
|---|---|---|---|
| RxNorm | `rxnav.nlm.nih.gov/REST/` | none | brand → ingredient normalisation |
| OpenFDA Label | `api.fda.gov/drug/label.json` | none (key bumps limit) | regulatory warnings, boxed warnings |
| OpenFDA FAERS | `api.fda.gov/drug/event.json` | none | adverse-event co-reports |
| TWOSIDES (via SNAP Decagon) | local SQLite at `data/decagon.sqlite` | none | observed polypharmacy side effects (Zitnik et al., *Bioinformatics* 2018) |
| Nemotron | `integrate.api.nvidia.com/v1/chat/completions` | `NVIDIA_API_KEY` | source parsing + synthesis |

The "TWOSIDES" leg is now backed by the **SNAP Decagon** extract (Zitnik et
al., *Bioinformatics* 2018, [snap.stanford.edu/decagon](https://snap.stanford.edu/decagon/)):
~4.65M observed polypharmacy side effects across 645 drugs and 1,317 UMLS-
coded condition types. Built with `scripts/build_decagon.py` into
`data/decagon.sqlite` (gitignored — see Quick start to rebuild). The schema
literal `source: "twosides"` is preserved in the API since Decagon *is* a
curated TWOSIDES extract; the data underneath is fully real.

Decagon's drug coverage is a 2018 snapshot, so a handful of newer or rarer
drugs (e.g. tramadol, lisinopril, clopidogrel, atorvastatin) aren't in its
645-drug set — pairs involving them return `Coverage.NO_DATA` from the
TWOSIDES leg, and synthesis falls back to the OpenFDA Label + FAERS legs
without fabricating numbers.

> **TODO(synthetic-data):** `samples/fixtures.json` is still hand-authored
> frontend dev material, not a captured `/api/analyze` response. It MUST
> be regenerated from a live pipeline run before any judge-facing
> presentation. Find every occurrence with:
> `grep -r "TODO(synthetic-data)" .`

## Repo layout

```
backend/                  FastAPI + LangGraph backend
  schemas.py              Pydantic contract (JOINT-01, locked at H1)
  llm.py                  Nemotron client (OpenAI-compatible)
  fanout.py               parallel source-agent fan-out
  synthesis.py            super-120b synthesis + deterministic fallback
  graph.py                LangGraph pipeline definition
  memory.py               in-process session memory (BE-12)
  report.py               regimen-report assembly (BE-10)
  sources/                rxnorm, openfda_label, openfda_faers, twosides (Decagon-backed), decagon_db
  main.py                 FastAPI app

prompts/synthesis.md      synthesis prompt (BE-09 target)
policies/policy.yaml      NemoClaw locked-down policy
policies/policy-bootstrap.yaml   bootstrap-only variant (adds PyPI)

scripts/                  one-shot tools (Decagon build, fixtures, iter loop)
samples/                  real API samples + NemoClaw audit excerpts
data/decagon.sqlite       SNAP Decagon TWOSIDES extract (gitignored; build_decagon.py)
docs/                     data-sources, demo-cases, access-verification notes
tests/                    pytest schema-lock tests

frontend/                 (Person B)
```

## Demo cases

See [`docs/demo-cases.md`](docs/demo-cases.md). Primary case is a 6-drug
regimen including warfarin + aspirin (major), fluoxetine + tramadol (major,
serotonin syndrome), and metformin + lisinopril (minor calibration check).

## Known limitations + production roadmap

- **TODO(synthetic-data):** `samples/fixtures.json` is still hand-authored
  frontend dev material — regenerate from `/api/analyze` before presenting.
  `grep -r "TODO(synthetic-data)" .` finds every remaining marker.
- **TWOSIDES/Decagon coverage** is a 2018 snapshot of 645 drugs. Common
  modern molecules (e.g. tramadol, lisinopril, clopidogrel, atorvastatin)
  fall outside it; those pairs surface `Coverage.NO_DATA` honestly rather
  than fabricating signal. Production swaps in the full live TWOSIDES
  pipeline (or a paid alternative like DrugBank).
- **FAERS noise** — popular drug pairs return tens of thousands of cases
  with generic symptoms (headache, nausea) drowning out specific signals.
  We mitigate via the `/count` aggregation + serious-event promotion; full
  PRR computation is the production fix.
- **Real-world deployment** would feed regimens via FHIR rather than free
  text, retain the audit log per-session, and run the agent inside the
  NemoClaw sandbox at the point of care.

## Tests

```bash
pytest tests/ -v
```

## Team

Backend / agents lead: Person A.
Frontend / demo lead: Person B.

This is a 24-hour hackathon prototype, not clinical software. Use for
research and education only.
