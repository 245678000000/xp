#!/usr/bin/env bash
# Install xp harness into ~/.grok for Grok Build.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${GROK_HOME:-$HOME/.grok}"
MODE="copy" # copy | link

usage() {
  cat <<'EOF'
Usage: ./install.sh [--link|--copy] [--dest DIR]

  --copy   Copy files into ~/.grok (default)
  --link   Symlink skills/agents/personas/roles; copy AGENTS.md only if missing
  --dest   Target Grok home (default: ~/.grok or $GROK_HOME)

Examples:
  ./install.sh
  ./install.sh --link
  GROK_HOME=/tmp/grok-test ./install.sh --copy
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --link) MODE="link"; shift ;;
    --copy) MODE="copy"; shift ;;
    --dest)
      DEST="${2:?--dest requires a path}"
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

mkdir -p "$DEST"/{agents,skills,personas,roles}

install_tree() {
  local src="$1"
  local dst="$2"
  if [[ "$MODE" == "link" ]]; then
    # Replace destination with symlink to repo path
    rm -rf "$dst"
    ln -sfn "$src" "$dst"
  else
    if [[ -d "$src" ]]; then
      mkdir -p "$dst"
      # Copy contents; do not wipe unrelated user files in parent
      if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete "$src"/ "$dst"/
      else
        rm -rf "$dst"
        mkdir -p "$dst"
        cp -R "$src"/. "$dst"/
      fi
    else
      mkdir -p "$(dirname "$dst")"
      cp "$src" "$dst"
    fi
  fi
}

echo "Installing xp → $DEST (mode=$MODE)"

# Skills: install each named skill (does not wipe whole skills dir)
for skill_dir in "$ROOT"/skills/*/; do
  [[ -d "$skill_dir" ]] || continue
  name="$(basename "$skill_dir")"
  install_tree "$skill_dir" "$DEST/skills/$name"
  echo "  skill: $name"
done

# Agents
for f in "$ROOT"/agents/*.md; do
  [[ -f "$f" ]] || continue
  name="$(basename "$f")"
  if [[ "$MODE" == "link" ]]; then
    ln -sfn "$f" "$DEST/agents/$name"
  else
    cp "$f" "$DEST/agents/$name"
  fi
  echo "  agent: $name"
done

# Personas
for f in "$ROOT"/personas/*.toml; do
  [[ -f "$f" ]] || continue
  name="$(basename "$f")"
  if [[ "$MODE" == "link" ]]; then
    ln -sfn "$f" "$DEST/personas/$name"
  else
    cp "$f" "$DEST/personas/$name"
  fi
  echo "  persona: $name"
done

# Roles
for f in "$ROOT"/roles/*.toml; do
  [[ -f "$f" ]] || continue
  name="$(basename "$f")"
  if [[ "$MODE" == "link" ]]; then
    ln -sfn "$f" "$DEST/roles/$name"
  else
    cp "$f" "$DEST/roles/$name"
  fi
  echo "  role: $name"
done

# AGENTS.md: never clobber a customized global file without backup
if [[ -f "$DEST/AGENTS.md" ]]; then
  if ! cmp -s "$ROOT/AGENTS.md" "$DEST/AGENTS.md"; then
    backup="$DEST/AGENTS.md.xp-backup.$(date +%Y%m%d%H%M%S)"
    cp "$DEST/AGENTS.md" "$backup"
    echo "  AGENTS.md: existing file backed up → $backup"
  fi
fi
cp "$ROOT/AGENTS.md" "$DEST/AGENTS.md"
echo "  AGENTS.md: installed"

echo
echo "Done. Start a new grok session, then try: /commit  /fix  /ship  /pr"
echo "Agents: /config-agents   Personas: /personas"
