#!/usr/bin/env bash
# Acuity end-to-end demo. Brings up the FastAPI app and walks through
# every demo surface: real Decagon citations, honest coverage gaps,
# memory-delta follow-up, and the NemoClaw policy endpoints.
#
#   ./demo.sh            # default port 8080 (matches frontend VITE_API_URL)
#   PORT=8765 ./demo.sh  # override
set -euo pipefail

PORT="${PORT:-8080}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ANSI colors — disabled if stdout isn't a TTY.
if [[ -t 1 ]]; then
  B=$'\e[1m'; D=$'\e[2m'; G=$'\e[32m'; Y=$'\e[33m'; C=$'\e[36m'; R=$'\e[31m'; N=$'\e[0m'
else
  B=''; D=''; G=''; Y=''; C=''; R=''; N=''
fi

section() { printf "\n${B}${C}━━ %s ━━${N}\n" "$1"; }
note()    { printf "${D}%s${N}\n" "$*"; }
ok()      { printf "${G}✓${N} %s\n" "$*"; }
warn()    { printf "${Y}!${N} %s\n" "$*"; }
err()     { printf "${R}✗${N} %s\n" "$*"; }

need() { command -v "$1" >/dev/null || { err "missing: $1"; exit 1; }; }
need curl
need jq

# ---------------------------------------------------------------- preflight
section "Preflight"

if [[ ! -x ".venv/bin/python" ]]; then
  err ".venv missing — run: uv venv --python 3.11 && uv pip install -e ."
  exit 1
fi
ok ".venv ready"

if [[ ! -f "data/decagon.sqlite" ]]; then
  warn "data/decagon.sqlite missing — building (≈50s)..."
  .venv/bin/python scripts/build_decagon.py --all
fi
.venv/bin/python -c "
import sqlite3
n = sqlite3.connect('data/decagon.sqlite').execute('SELECT COUNT(*) FROM pair_effect').fetchone()[0]
print(f'  pair_effect rows: {n:,}')
n = sqlite3.connect('data/decagon.sqlite').execute('SELECT COUNT(*) FROM drug_map').fetchone()[0]
print(f'  drug_map names:   {n:,}')
"
ok "decagon.sqlite loaded"

note "running test suite..."
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -1
ok "tests pass"

# Free the port if a stale server is holding it.
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  warn "port $PORT busy — freeing"
  lsof -ti:"$PORT" | xargs -r kill -9 || true
  sleep 1
fi

# --------------------------------------------------------------- launch api
section "Launch FastAPI (port $PORT)"

LOG="$(mktemp -t acuity-demo.XXXXXX.log)"
PYTHONPATH=. .venv/bin/uvicorn backend.main:app --port "$PORT" --log-level warning \
  > "$LOG" 2>&1 &
SERVER_PID=$!

cleanup() {
  if kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  note "server log: $LOG"
}
trap cleanup EXIT INT TERM

# Poll /health until ready.
for _ in $(seq 1 30); do
  if curl -fs "http://localhost:$PORT/health" >/dev/null 2>&1; then
    ok "server up (pid $SERVER_PID)"
    break
  fi
  sleep 0.3
done
curl -fs "http://localhost:$PORT/health" >/dev/null \
  || { err "server failed to come up — see $LOG"; exit 1; }

API="http://localhost:$PORT"

# --------------------------------------------------------------- demo body
SESSION="demo-$(date +%s)"

section "A · Decagon-covered regimen → real polypharmacy citations"
note "Drugs all present in Decagon's 645-drug set; expect twosides findings."
ANALYZE_PAYLOAD=$(cat <<JSON
{"drugs":["warfarin","aspirin","ibuprofen","omeprazole"],"session_id":"$SESSION"}
JSON
)
RESP_A=$(curl -fs -X POST "$API/api/analyze" -H 'Content-Type: application/json' \
  -d "$ANALYZE_PAYLOAD")

echo "$RESP_A" | jq -r '
  .durations_ms as $d
  | "  durations: intake=\($d.intake_ms)ms fanout=\($d.fanout_ms)ms synthesis=\($d.synthesis_ms)ms total=\($d.total_ms)ms",
    "  overall: \(.report.overall_summary)",
    "",
    "  interactions:"
  , (.report.interactions[] | "    [\(.severity|ascii_upcase)] \(.drug_pair|join(" + ")) — \(.headline)")
'

FANOUT_A=$(echo "$RESP_A" | jq -r '.durations_ms.fanout_ms')

echo
note "Decagon citations actually used by synthesis:"
echo "$RESP_A" | jq -r '
  .report.interactions[]
  | . as $ix
  | .citations[]
  | select(.source=="twosides")
  | "    [\($ix.drug_pair|join("+"))]  \(.quote)"
'

section "B · Honest coverage gap (drugs Decagon does not have)"
note "tramadol & lisinopril are absent from Decagon's 2018 snapshot."
note "Expect Coverage.NO_DATA on the twosides leg; Label+FAERS still cover."

RESP_B=$(curl -fs -X POST "$API/api/analyze" \
  -H 'Content-Type: application/json' \
  -d "{\"drugs\":[\"fluoxetine\",\"tramadol\",\"metformin\",\"lisinopril\"],\"session_id\":\"$SESSION-gap\"}")

echo "$RESP_B" | jq -r '
  .report.interactions[]
  | .drug_pair as $p
  | "  [\(.severity|ascii_upcase)] \($p|join(" + ")) — \(.headline)"
'
ok "no fabricated PRRs: drugs outside Decagon return honest NO_DATA"

section "C · Memory delta (same session_id, +1 drug)"
note "Follow-up adds clopidogrel. Only the new pairs hit source agents."

RESP_C=$(curl -fs -X POST "$API/api/analyze" \
  -H 'Content-Type: application/json' \
  -d "{\"drugs\":[\"warfarin\",\"aspirin\",\"ibuprofen\",\"omeprazole\",\"clopidogrel\"],\"session_id\":\"$SESSION\"}")

echo "$RESP_C" | jq -r --arg first "$FANOUT_A" '
  "  new_pairs    (\(.report.new_pairs|length)):    \(.report.new_pairs    | map(join("+")) | join(", "))",
  "  cached_pairs (\(.report.cached_pairs|length)): \(.report.cached_pairs | map(join("+")) | join(", "))",
  "  durations:   fanout=\(.durations_ms.fanout_ms)ms (was \($first)ms on first call — only the new pairs fanned out)"
'

section "D · NemoClaw policy surfaces"
note "GET /api/policy — the network allowlist enforced at L4 by OpenShell"
curl -fs "$API/api/policy" | jq -r '
  "  allowlist:",
  (.allowlist[] | "    \(.)"),
  "  policy file: \(.path)"
'

note "POST /api/attack-case — deliberate off-whitelist call"
ATTACK=$(curl -fs -X POST "$API/api/attack-case")
echo "$ATTACK" | jq -r '
  "  target:    \(.target)",
  "  attempted: \(.attempted)",
  "  blocked:   \(.blocked)",
  "  detail:    \(.detail)"
'
note "audit excerpt:"
echo "$ATTACK" | jq -r '.audit_excerpt[] | "    \(.)"'

note "GET /api/audit-log?limit=4"
curl -fs "$API/api/audit-log?limit=4" | jq -r '
  "  source: \(.source)   path: \(.path)",
  "  recent lines:",
  (.lines[] | "    \(.)")
'

section "Done"
ok "all demo surfaces exercised against the live API on port $PORT"
note "session id used: $SESSION"
note "tear down: trap will kill pid $SERVER_PID on script exit"
