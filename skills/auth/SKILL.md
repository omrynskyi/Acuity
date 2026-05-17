---
name: auth
description: Save the user's Acuity Personal Access Token (ACUITY_PAT) into the sandbox's persistent .env so all other skills can authenticate to the Acuity API. Use this whenever the user provides a fresh token from https://tryacuity.vercel.app/settings.
---

## Auth

Persist the user's `ACUITY_PAT` to `~/.openclaw/.env` so subsequent skill runs (db, analyze, etc.) can authenticate without re-prompting.

### Sandbox Runtime

- This skill runs inside a NemoClaw sandbox. The active user is `sandbox`, **home is `/sandbox`** (not `/home/sandbox`, not `/root`). The skills root is `/sandbox/.openclaw/skills/`.
- Always invoke scripts with an **absolute path**: `python3 /sandbox/.openclaw/skills/auth/scripts/<script>.py …`. Do not search `/root/.openclaw/...` — that path does not exist here.
- When you use the `exec` / shell tool, pass the actual command as the `command` argument. Do **not** emit raw RPC strings like `exec --host host --command "…"` — that is an internal envelope, and bash will reject `--host` as an invalid option.
- Stderr lines like `bash: cannot create /proc/self/oom_score_adj: Permission denied` are harmless kernel notices from the sandbox's rootless container. They do not indicate script failure — ignore them and check the script's exit code instead.

### When to use

- Any other skill (db, analyze) fails with `ACUITY_PAT environment variable is not set` or HTTP 401/403.
- The user mentions logging in, signing in, authenticating, or hands you a fresh token.
- The stored token has been revoked and a new one was generated.

If a token is missing, **tell the user**:

> Generate a Personal Access Token at **https://tryacuity.vercel.app/settings**, then paste it back here so I can save it.

Then call `set_pat.py` with the token.

### Sub-commands

#### set_pat

Write a token to `~/.openclaw/.env` (creates the file if needed, replaces any existing `ACUITY_PAT` line).

```bash
python3 /sandbox/.openclaw/skills/auth/scripts/set_pat.py --pat "<token>"
```

| Argument | Required | Description |
|---|---|---|
| `--pat` | Yes | The full PAT string copied from https://tryacuity.vercel.app/settings |

**Output:** prints `OK: ACUITY_PAT saved to <path>` on success. Exits non-zero with an error on stderr on failure.

#### check_pat

Verify that a token is loaded *and* accepted by the Acuity API (calls `GET /api/user/profile`).

```bash
python3 /sandbox/.openclaw/skills/auth/scripts/check_pat.py
```

Exit codes:
- `0` — token is set and the API accepts it.
- `1` — no token is loadable from env or `~/.openclaw/.env`.
- `2` — token is loadable but the API rejected it (401/403) or could not be reached.

On exit 1 or 2, the script prints a one-line instruction telling the user to visit https://tryacuity.vercel.app/settings.

### Files Touched

- `~/.openclaw/.env` — single line `ACUITY_PAT=<token>` is added or replaced. File permissions are set to `0600`.
- No other state is written.

### Failure Modes

- Exit 1 if `--pat` is empty or whitespace-only.
- Exit 1 if `~/.openclaw/` cannot be created or `.env` cannot be written.
- `check_pat.py` exits 2 if the token is rejected by the API or the API is unreachable.
