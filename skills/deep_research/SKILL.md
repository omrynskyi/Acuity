---
name: deep_research
description: Run a deep pharmacological research agent on a single drug using Brave web search and Nemotron synthesis. Returns a DeepResearchReport JSON. Does NOT call the Acuity API.
---

## DeepResearch

Run a multi-query research loop for a single drug across mechanism, indications, contraindications, adverse events, drug interactions, and pharmacokinetics. Synthesizes results with Nemotron into a structured `DeepResearchReport`.

### Sandbox Runtime

- This skill runs inside a NemoClaw sandbox. The active user is `sandbox`, **home is `/sandbox`** (not `/home/sandbox`, not `/root`). The skills root is `/sandbox/.openclaw/skills/`.
- Always invoke scripts with an **absolute path**: `python3 /sandbox/.openclaw/skills/deep_research/scripts/deep_research.py …`. Do not search `/root/.openclaw/...` — that path does not exist here.
- When you use the `exec` / shell tool, pass the actual command as the `command` argument. Do **not** emit raw RPC strings like `exec --host host --command "…"` — that is an internal envelope, and bash will reject `--host` as an invalid option.
- Stderr lines like `bash: cannot create /proc/self/oom_score_adj: Permission denied` are harmless kernel notices from the sandbox's rootless container. They do not indicate script failure — ignore them and check the script's exit code instead.

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
python3 /sandbox/.openclaw/skills/deep_research/scripts/deep_research.py --drug "metformin"
python3 /sandbox/.openclaw/skills/deep_research/scripts/deep_research.py --drug "rivaroxaban" --out /tmp/riv.json --depth 8
```

### Side Effects

- Makes HTTP GET requests to `https://api.search.brave.com/res/v1/web/search` (6 queries per run).
- Makes one HTTPS POST to `https://integrate.api.nvidia.com` for synthesis.
- No filesystem writes unless `--out` is specified.

### Failure Modes

- Exit 1 if `BRAVE_API_KEY` is missing or Brave returns non-200.
- Falls back to partial report if Nemotron is unreachable (rule-based summary per aspect using search snippets).
- Partial results (some aspects) are acceptable — the report will contain fewer findings rather than failing entirely.
