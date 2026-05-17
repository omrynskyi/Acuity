# Acuity

**Know your medicine. All of it, at once.**

135 million Americans take 2 or more prescription drugs every day. A third of adults 65 and older take 5 or more — and a 10-drug regimen produces 45 unique drug pairs that can interact. Physicians have roughly five seconds to review a medication list before discharge. No single data source has complete coverage.

Acuity fans out across three independent data sources in parallel, uses Nemotron to reconcile conflicting findings, and returns a severity-ranked interaction report with citations — in seconds.

**[Try it free at tryacuity.vercel.app](https://tryacuity.vercel.app)**

---

## The Problem

Polypharmacy is one of the fastest-growing challenges in personal medicine. As people live longer and manage more conditions simultaneously, the combination of drugs they take grows faster than any clinician can track in real time:

- **135 million** Americans take 2+ prescription drugs daily
- **1 in 3** adults 65+ take 5+ drugs per day
- **45 interaction pairs** exist in a 10-drug regimen
- Drug-drug interactions are a leading cause of preventable hospitalizations

The existing tools are either too shallow (simple pairwise lookups), too slow (waiting for a pharmacist consult), or too opaque (no citations, no reasoning).

---

## What Acuity Does

Acuity is a multi-agent drug interaction checker built around a centralized API hosted on Render. Both the web app and Nemotron-powered agents query this single API — keeping analysis results, session memory, and citations in sync across every interface.

**Web app** — enter a medication list, get a ranked report with severity levels and sourced reasoning. No account required.

**NemoClaw agent** — the same backend, accessible to a Nemotron agent running under NemoClaw policy. Bring your own credentials, run the agent in your own sandbox, get the same results with full audit logging.

---

## Architecture

```
                    ┌─────────────────────────────┐
                    │   Acuity API  (Render)       │
                    │                              │
                    │  RxNorm normalisation        │
                    │  ┌──────────┬──────────────┐ │
                    │  │ OpenFDA  │ OpenFDA FAERS │ │  ← parallel fan-out
                    │  │  Label   │              │ │
                    │  └──────────┴──────────────┘ │
                    │       TWOSIDES / Decagon      │
                    │                              │
                    │  Nemotron super-120b          │  ← synthesis
                    │  severity-ranked report       │
                    └──────────────┬───────────────┘
                                   │
               ┌───────────────────┼───────────────────┐
               │                   │                   │
        ┌──────▼──────┐   ┌────────▼────────┐         │
        │  Web App    │   │ NemoClaw Agent  │         │
        │  (Vercel)   │   │  (your sandbox) │         │
        └─────────────┘   └─────────────────┘         │
                                                        │
                                             session memory synced
```

The LangGraph pipeline inside the API handles intake → fan-out → synthesis → report. A follow-up query on an extended drug list only evaluates the new pairs — cached findings are reused.

---

## NemoClaw: Medical AI That's Actually Safe

Medical AI has been too risky for agentic systems — until now.

A medication list is protected health information. Drug labels and FAERS adverse-event narratives are realistic surfaces for prompt injection: a malicious label could instruct the synthesis agent to exfiltrate the patient's regimen to an attacker-controlled host. Without runtime isolation, that attack succeeds silently.

NemoClaw closes this at the runtime layer:

- **API allowlist** — exactly four hosts are reachable from inside the sandbox: `api.fda.gov`, `rxnav.nlm.nih.gov`, `pubchem.ncbi.nlm.nih.gov`, and the Nemotron inference endpoint. Any other outbound connection is blocked at the L4 policy engine before TLS is negotiated.
- **Filesystem containment** — agents write only to `/sandbox`, `/session`, `/tmp`. Host filesystem is read-only or invisible.
- **Audit logging** — every allowed and denied network event is emitted in OCSF format. You can verify exactly what the agent touched.

OpenShell and NemoClaw make this security posture portable: the same YAML policy file governs local dev, Brev cloud, and production — no per-host setup scripts.

See [`README-NEMOCLAW.md`](README-NEMOCLAW.md) for the full bonus-track submission, policy structure, and attack-case demo.

### BYO-Claw

Acuity is a BYO-Claw product. To run the agent in your own NemoClaw sandbox:

1. **NVIDIA API key** — get a free key at [build.nvidia.com](https://build.nvidia.com) → **API Keys → Generate Key**
2. **Acuity PAT** — generate a Personal Access Token from **My Profile → NemoClaw Token → Generate** in the web app
3. **Custom skills** — the repo ships skills that tell NemoClaw how to call the Acuity API endpoints, so the agent knows what it's allowed to query without you writing a policy from scratch

```bash
# .env
NVIDIA_API_KEY=nvapi-...
ACUITY_PAT=...
ACUITY_API_BASE_URL=https://acuity-api.onrender.com
```

---

## Data Sources

| Source | Used for |
|---|---|
| RxNorm (`rxnav.nlm.nih.gov`) | Brand → ingredient normalisation |
| OpenFDA Label (`api.fda.gov/drug/label.json`) | Regulatory warnings, boxed warnings |
| OpenFDA FAERS (`api.fda.gov/drug/event.json`) | Adverse-event co-reports |
| TWOSIDES / SNAP Decagon | 4.65M observed polypharmacy side effects across 645 drugs (Zitnik et al., *Bioinformatics* 2018) |
| Nemotron (`integrate.api.nvidia.com`) | Source parsing + cross-source synthesis |

No single source has complete coverage. Acuity surfaces `NO_DATA` honestly when a pair falls outside a source's scope rather than fabricating signal.

---

## Try It

**Web app:** [tryacuity.vercel.app](https://tryacuity.vercel.app) — no account required.

**NemoClaw agent:** see [README-NEMOCLAW.md](README-NEMOCLAW.md) for step-by-step setup.

---

## Developer Quick Start (self-hosted)

### Prerequisites
- Python 3.11+
- `uv` (recommended) or `pip`
- `NVIDIA_API_KEY` in `.env`

### Install and run

```bash
uv venv --python 3.11 && source .venv/bin/activate
uv pip install langgraph fastapi 'uvicorn[standard]' httpx pydantic python-dotenv openai pytest pytest-asyncio
python scripts/build_decagon.py --all   # builds data/decagon.sqlite (~50s)

uvicorn backend.main:app --port 8000
```

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"drugs":["warfarin","aspirin","fluoxetine","tramadol"],"session_id":"demo"}' \
  | jq .
```

### Repo layout

```
backend/          FastAPI + LangGraph pipeline
  sources/        rxnorm, openfda_label, openfda_faers, twosides
  schemas.py      Pydantic contract (locked)
  synthesis.py    Nemotron super-120b synthesis + deterministic fallback
  memory.py       session memory
frontend/         React web app (Vercel)
policies/         NemoClaw policy YAML
prompts/          synthesis prompt
scripts/          Decagon build, synthesis iteration harness
docs/             demo cases, data source notes
```

Primary demo case: warfarin + aspirin (major), fluoxetine + tramadol (serotonin syndrome, major), metformin + lisinopril (minor calibration). See [`docs/demo-cases.md`](docs/demo-cases.md).

```bash
pytest tests/ -v
```

---

## Team

Backend / agents: Cyrus Correll  
Frontend / demo:  Oleg Mrynskyi

This is a 24-hour hackathon prototype. Not clinical software — use for research and education only.
