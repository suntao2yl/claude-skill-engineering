#!/usr/bin/env bash
# install.sh — install the engineering skill and verify harness dependency
#
# Usage:
#   ./install.sh                 # install engineering to ~/.claude/skills/engineering/
#   ./install.sh --prefix <dir>  # install to a custom skills dir
#   ./install.sh --with-harness <path>  # also copy harness from <path>
#   ./install.sh --dry-run       # show what would happen, no changes

set -euo pipefail

# ── args ──────────────────────────────────────────────────────
PREFIX="${HOME}/.claude/skills"
HARNESS_SRC=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --with-harness) HARNESS_SRC="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

# ── paths ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENG_DEST="$PREFIX/engineering"
HARNESS_DEST="$PREFIX/harness"

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[dry-run] $*"
  else
    eval "$@"
  fi
}

say() { printf '%s\n' "$*"; }

say "engineering skill installer"
say "  source: $SCRIPT_DIR"
say "  prefix: $PREFIX"
say ""

# ── install engineering ───────────────────────────────────────
if [[ -d "$ENG_DEST" ]]; then
  say "⚠  $ENG_DEST already exists."
  if [[ "$DRY_RUN" == "1" ]]; then
    say "   [dry-run] would prompt to overwrite"
  else
    read -r -p "   Overwrite? [y/N] " ans
    if [[ "$ans" != "y" && "$ans" != "Y" ]]; then
      say "   Skipping engineering install."
    else
      run "rm -rf '$ENG_DEST'"
    fi
  fi
fi

if [[ ! -d "$ENG_DEST" ]]; then
  run "mkdir -p '$PREFIX'"
  run "rsync -a \
        --exclude='validation' --exclude='.engineering*' \
        --exclude='__pycache__' --exclude='.DS_Store' \
        --exclude='docs' --exclude='.git' --exclude='install.sh' \
        '$SCRIPT_DIR/' '$ENG_DEST/'"
  say "✓ engineering installed to $ENG_DEST"
fi

# ── install harness (optional) ────────────────────────────────
if [[ -n "$HARNESS_SRC" ]]; then
  if [[ ! -d "$HARNESS_SRC" ]]; then
    say "✗ --with-harness: $HARNESS_SRC does not exist" >&2
    exit 1
  fi
  if [[ -d "$HARNESS_DEST" ]]; then
    say "⚠  $HARNESS_DEST already exists, skipping harness copy."
  else
    run "rsync -a '$HARNESS_SRC/' '$HARNESS_DEST/'"
    say "✓ harness installed to $HARNESS_DEST"
  fi
fi

# ── verify harness dependency ─────────────────────────────────
say ""
if [[ -d "$HARNESS_DEST" && -f "$HARNESS_DEST/SKILL.md" ]]; then
  say "✓ harness dependency found at $HARNESS_DEST"
else
  say "✗ HARNESS DEPENDENCY MISSING"
  say ""
  say "  engineering's implementation phase delegates to the harness skill."
  say "  Without harness, you can still run discovery/design/architecture/test/"
  say "  release/ops phases, but implementation will not work."
  say ""
  say "  To install harness:"
  say "    ./install.sh --with-harness /path/to/harness-skill"
  say "  or manually copy the harness skill to $HARNESS_DEST"
  say ""
fi

say "Done."
