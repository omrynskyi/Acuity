#!/usr/bin/env python3
"""Persist an Acuity Personal Access Token to ~/.openclaw/.env.

Usage:
    python3 set_pat.py --pat <token>

Creates ~/.openclaw/.env if it does not exist. Replaces any existing
ACUITY_PAT line. Sets the file mode to 0600 so other users on the
sandbox host cannot read the token.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys


ENV_PATH = pathlib.Path.home() / ".openclaw" / ".env"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Save ACUITY_PAT to ~/.openclaw/.env")
    p.add_argument("--pat", required=True, help="Personal Access Token from https://tryacuity.vercel.app/settings")
    return p.parse_args()


def upsert_pat(env_path: pathlib.Path, token: str) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)

    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text().splitlines()

    new_lines: list[str] = []
    replaced = False
    for line in existing_lines:
        stripped = line.strip()
        key_part = stripped[len("export "):].lstrip() if stripped.startswith("export ") else stripped
        if key_part.startswith("ACUITY_PAT="):
            if not replaced:
                new_lines.append(f"ACUITY_PAT={token}")
                replaced = True
            continue
        new_lines.append(line)

    if not replaced:
        new_lines.append(f"ACUITY_PAT={token}")

    env_path.write_text("\n".join(new_lines) + "\n")
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        # best-effort — landlock or non-owner FS may refuse chmod
        pass


def main() -> None:
    args = parse_args()
    token = args.pat.strip()
    if not token:
        print("ERROR: --pat is empty", file=sys.stderr)
        sys.exit(1)

    try:
        upsert_pat(ENV_PATH, token)
    except OSError as e:
        print(f"ERROR: could not write {ENV_PATH}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"OK: ACUITY_PAT saved to {ENV_PATH}")


if __name__ == "__main__":
    main()
