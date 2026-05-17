---
name: reminder
description: Create, list, and cancel NemoClaw-isolated medication reminders that fire via Telegram. Reminders do not touch the frontend or database.
---

## Reminder

Schedule recurring or one-time reminders that send Telegram messages. All state is kept in `/session/reminders/`. No frontend or Supabase writes.

### Sandbox Runtime

- This skill runs inside a NemoClaw sandbox. The active user is `sandbox`, **home is `/sandbox`** (not `/home/sandbox`, not `/root`). The skills root is `/sandbox/.openclaw/skills/`.
- Always invoke scripts with an **absolute path**: `python3 /sandbox/.openclaw/skills/reminder/scripts/<script>.py …` (where `<script>` is `create`, `list`, or `cancel`). Do not search `/root/.openclaw/...` — that path does not exist here.
- When you use the `exec` / shell tool, pass the actual command as the `command` argument. Do **not** emit raw RPC strings like `exec --host host --command "…"` — that is an internal envelope, and bash will reject `--host` as an invalid option.
- Stderr lines like `bash: cannot create /proc/self/oom_score_adj: Permission denied` are harmless kernel notices from the sandbox's rootless container. They do not indicate script failure — ignore them and check the script's exit code instead.

### Prerequisites

Environment variables required:
- `TELEGRAM_BOT_TOKEN` — bot token from BotFather
- `TELEGRAM_CHAT_ID` — target chat ID

### Sub-commands

#### create

```bash
python3 /sandbox/.openclaw/skills/reminder/scripts/create.py \
  --date "2026-05-17T09:00:00" \
  --frequency once|daily|weekly|monthly \
  --content "Take your metformin"
```

| Argument | Type | Required | Description |
|---|---|---|---|
| `--date` | ISO 8601 datetime | Yes | First (or only) fire time |
| `--frequency` | `once`, `daily`, `weekly`, `monthly` | Yes | Recurrence |
| `--content` | string | Yes | Message text to send via Telegram |

**Output:** prints `reminder_id` to stdout.

#### list

```bash
python3 /sandbox/.openclaw/skills/reminder/scripts/list.py
```

Prints a JSON array of all active reminders from `/session/reminders/`.

#### cancel

```bash
python3 /sandbox/.openclaw/skills/reminder/scripts/cancel.py --id <reminder_id>
```

Removes the crontab entry and deletes `/session/reminders/<id>.json`.

### Side Effects

- **create**: writes `/session/reminders/<id>.json`, appends a crontab line that calls `send.py <id>` at the scheduled time.
- **cancel**: removes crontab line and deletes JSON file.
- **send.py** (invoked by cron): POSTs to `https://api.telegram.org/bot.../sendMessage`. Appends a log line to `/session/reminders/_log.jsonl`. For `once` reminders: self-cancels after success.

### Failure Modes

- Exit 1 with stderr if `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is not set.
- Exit 1 if the crontab cannot be read or written.
- `send.py` logs failures to `_log.jsonl` and exits non-zero; the crontab entry is left intact for retry.
