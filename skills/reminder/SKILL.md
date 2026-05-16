---
name: reminder
description: Create, list, and cancel NemoClaw-isolated medication reminders that fire via Telegram. Reminders do not touch the frontend or database.
---

## Reminder

Schedule recurring or one-time reminders that send Telegram messages. All state is kept in `/session/reminders/`. No frontend or Supabase writes.

### Prerequisites

Environment variables required:
- `TELEGRAM_BOT_TOKEN` — bot token from BotFather
- `TELEGRAM_CHAT_ID` — target chat ID

### Sub-commands

#### create

```bash
python skills/reminder/scripts/create.py \
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
python skills/reminder/scripts/list.py
```

Prints a JSON array of all active reminders from `/session/reminders/`.

#### cancel

```bash
python skills/reminder/scripts/cancel.py --id <reminder_id>
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
