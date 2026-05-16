#!/usr/bin/env bash
# Downloads decagon.sqlite before the server starts (Render deploy).
# Skips silently if the file already exists or DECAGON_DB_URL is not set.
set -euo pipefail

DB_PATH="${DECAGON_DB_PATH:-$(pwd)/data/decagon.sqlite}"
DB_DIR="$(dirname "$DB_PATH")"

if [ -f "$DB_PATH" ]; then
  echo "[prestart] decagon.sqlite already present — skipping download."
  exit 0
fi

if [ -z "${DECAGON_DB_URL:-}" ]; then
  echo "[prestart] DECAGON_DB_URL not set — Decagon/TWOSIDES source will be unavailable."
  exit 0
fi

echo "[prestart] Downloading decagon.sqlite (~619 MB) ..."
mkdir -p "$DB_DIR"
curl -fL --progress-bar "$DECAGON_DB_URL" -o "$DB_PATH"
echo "[prestart] Done: $(du -sh "$DB_PATH" | cut -f1)"
