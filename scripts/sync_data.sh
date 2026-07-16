#!/usr/bin/env bash
# Copy harness content into the Python package data dir (for wheel installs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/src/xp/data"
mkdir -p "$DEST"
cp "$ROOT/AGENTS.md" "$DEST/AGENTS.md"
rsync -a --delete "$ROOT/skills/" "$DEST/skills/"
rsync -a --delete "$ROOT/agents/" "$DEST/agents/"
echo "Synced → $DEST"
