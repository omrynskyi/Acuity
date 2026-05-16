---
name: deep_research
description: Run a deep pharmacological research agent on a single drug using Brave web search and Nemotron synthesis. Returns a DeepResearchReport JSON. Does NOT call the Acuity API.
---

## DeepResearch

Run a multi-query research loop for a single drug across mechanism, indications, contraindications, adverse events, drug interactions, and pharmacokinetics. Synthesizes results with Nemotron into a structured `DeepResearchReport`.

### Prerequisites

Environment variables required:
- `BRAVE_API_KEY` — Brave Search API subscription token
- `NVIDIA_API_KEY` — for Nemotron synthesis
- `NEMOTRON_SUPER_MODEL` — model ID (default: `nvidia/nemotron-3-super-120b-a12b`)

### Inputs

| Argument | Type | Required | Description |
|---|---|---|---|
| `--drug` | string | Yes | Drug name to research |
| `--out` | file path | No | Write JSON to file instead of stdout |
| `--depth` | integer | No | Number of Brave results per query (default: 5) |

### Outputs

Prints a `DeepResearchReport` JSON to **stdout** (or to `--out`). Exits 0 on success, non-zero on failure.

Schema: see `backend/schemas.py::DeepResearchReport`.

### Invocation

```bash
python skills/deep_research/scripts/deep_research.py --drug "metformin"
python skills/deep_research/scripts/deep_research.py --drug "rivaroxaban" --out /tmp/riv.json --depth 8
```

### Side Effects

- Makes HTTP GET requests to `https://api.search.brave.com/res/v1/web/search` (6 queries per run).
- Makes one HTTPS POST to `https://integrate.api.nvidia.com` for synthesis.
- No filesystem writes unless `--out` is specified.

### Failure Modes

- Exit 1 if `BRAVE_API_KEY` is missing or Brave returns non-200.
- Falls back to partial report if Nemotron is unreachable (rule-based summary per aspect using search snippets).
- Partial results (some aspects) are acceptable — the report will contain fewer findings rather than failing entirely.
