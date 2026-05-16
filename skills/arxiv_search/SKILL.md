---
name: arxiv_search
description: Search arXiv for peer-reviewed papers on a drug pair interaction or a free-form pharmacology query. Returns structured paper metadata and optional Nemotron synthesis. Does NOT call the Acuity API.
---

## ArxivSearch

Search `export.arxiv.org` for peer-reviewed papers on a drug-drug interaction or any pharmacology topic. Returns paper titles, authors, abstracts, and URLs as structured JSON. Optionally synthesizes findings with Nemotron into a clinical summary.

### Prerequisites

Environment variables required:
- `NVIDIA_API_KEY` — required only when `--synthesize` is passed

No API key is needed for the base arXiv search.

### Inputs

| Argument | Type | Required | Description |
|---|---|---|---|
| `--drug-a` | string | Yes* | First drug name. Use with `--drug-b`. |
| `--drug-b` | string | Yes* | Second drug name. Required when `--drug-a` is set. |
| `--query` | string | Yes* | Free-form arXiv search query (mutually exclusive with `--drug-a/b`). |
| `--max-results` | integer | No | Max papers to fetch (default: 5). |
| `--synthesize` | flag | No | Run Nemotron synthesis on returned papers. Requires `NVIDIA_API_KEY`. |
| `--out` | file path | No | Write JSON to file instead of stdout. Prints the path on success. |

*Either `--drug-a` + `--drug-b` **or** `--query` must be provided.

### Outputs

Prints an `ArxivSearchReport` JSON to **stdout** (or to `--out`). Exits 0 on success, non-zero on failure.

```json
{
  "report_type": "arxiv_search",
  "schema_version": "1.0",
  "generated_at": "2026-05-16T00:00:00+00:00",
  "drug_a": "warfarin",
  "drug_b": "aspirin",
  "query": "all:\"warfarin\" AND all:\"aspirin\" AND all:\"drug interaction\"",
  "total_results": 5,
  "papers": [
    {
      "arxiv_id": "2301.12345",
      "title": "...",
      "authors": ["Smith J", "Lee A"],
      "published": "2023-01-15",
      "abstract": "...",
      "url": "https://arxiv.org/abs/2301.12345"
    }
  ],
  "synthesis": {
    "clinical_summary": "...",
    "severity_signal": "major|moderate|minor|none|unclear",
    "key_findings": ["..."],
    "citations": [{"title": "...", "arxiv_id": "...", "url": "...", "quote": "..."}]
  }
}
```

`synthesis` is omitted unless `--synthesize` is passed.

### Invocation

```bash
# Drug pair search
python skills/arxiv_search/scripts/arxiv_search.py --drug-a "warfarin" --drug-b "aspirin"

# Drug pair search with Nemotron synthesis
python skills/arxiv_search/scripts/arxiv_search.py --drug-a "warfarin" --drug-b "aspirin" --synthesize

# Free-form query, more results, write to file
python skills/arxiv_search/scripts/arxiv_search.py --query "metformin CYP2C8 interaction" --max-results 10 --out /tmp/results.json

# Pipe into make_report for PDF
python skills/arxiv_search/scripts/arxiv_search.py --drug-a "warfarin" --drug-b "aspirin" --synthesize \
  | python skills/make_report/scripts/make_report.py
```

### Side Effects

- Makes HTTP GET requests to `https://export.arxiv.org/api/query` (1 request per run).
- Makes one HTTPS POST to `https://integrate.api.nvidia.com` only when `--synthesize` is passed.
- No filesystem writes unless `--out` is specified.

### Failure Modes

- Exit 1 if `--drug-a` is provided without `--drug-b`, or if `NVIDIA_API_KEY` is missing with `--synthesize`.
- Exit 2 if arXiv returns a non-200 response.
- If Nemotron synthesis fails, falls back to a rule-based summary from paper abstracts (no exit error).
- Returns an empty `papers` list (exit 0) if arXiv finds no matching papers.
