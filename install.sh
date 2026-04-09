#!/usr/bin/env bash
# install.sh — install the harness-engineering skill and verify harness-plan dependency
#
# Usage:
#   ./install.sh                              # install harness-engineering to ~/.claude/skills/harness-engineering/
#   ./install.sh --prefix <dir>               # install to a custom skills dir
#   ./install.sh --with-harness-plan <path>   # also copy harness-plan from <path>
#   ./install.sh --dry-run                    # show what would happen, no changes

set -euo pipefail

# ── args ──────────────────────────────────────────────────────
PREFIX="${HOME}/.claude/skills"
HARNESS_SRC=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --with-harness-plan) HARNESS_SRC="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

# ── paths ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$SCRIPT_DIR/skills/harness-engineering"
ENG_DEST="$PREFIX/harness-engineering"
HARNESS_DEST="$PREFIX/harness-plan"

run() {
  if (( DRY_RUN )); then
    echo "[dry-run] $*"
  else
    eval "$@"
  fi
}

say() { printf '%s\n' "$*"; }

say "harness-engineering skill installer"
say "  source: $SKILL_SRC"
say "  prefix: $PREFIX"
say ""

# ── install harness-engineering ───────────────────────────────
install_eng=1
if [[ -d "$ENG_DEST" ]]; then
  say "⚠  $ENG_DEST already exists."
  if (( DRY_RUN )); then
    say "   [dry-run] would prompt to overwrite"
  else
    read -r -p "   Overwrite? [y/N] " ans
    if [[ "$ans" != "y" && "$ans" != "Y" ]]; then
      say "   Skipping harness-engineering install."
      install_eng=0
    else
      run "rm -rf '$ENG_DEST'"
    fi
  fi
fi

if (( install_eng )) && [[ ! -d "$ENG_DEST" ]]; then
  run "mkdir -p '$PREFIX'"
  run "rsync -a \
        --exclude='validation' --exclude='.engineering*' \
        --exclude='__pycache__' --exclude='.DS_Store' \
        '$SKILL_SRC/' '$ENG_DEST/'"
  say "✓ harness-engineering installed to $ENG_DEST"
fi

# ── install harness-plan (optional) ───────────────────────────
if [[ -n "$HARNESS_SRC" ]]; then
  if [[ ! -d "$HARNESS_SRC" ]]; then
    say "✗ --with-harness-plan: $HARNESS_SRC does not exist" >&2
    exit 1
  fi
  if [[ -d "$HARNESS_DEST" ]]; then
    say "⚠  $HARNESS_DEST already exists."
    if (( DRY_RUN )); then
      say "   [dry-run] would prompt to overwrite"
    else
      read -r -p "   Overwrite? [y/N] " ans
      if [[ "$ans" != "y" && "$ans" != "Y" ]]; then
        say "   Skipping harness-plan install."
      else
        run "rm -rf '$HARNESS_DEST'"
        run "rsync -a '$HARNESS_SRC/' '$HARNESS_DEST/'"
        say "✓ harness-plan installed to $HARNESS_DEST"
      fi
    fi
  else
    run "rsync -a '$HARNESS_SRC/' '$HARNESS_DEST/'"
    say "✓ harness-plan installed to $HARNESS_DEST"
  fi
fi

# ── verify harness-plan dependency ────────────────────────────
say ""
if [[ -d "$HARNESS_DEST" && -f "$HARNESS_DEST/SKILL.md" ]]; then
  say "✓ harness-plan dependency found at $HARNESS_DEST"
else
  say "✗ HARNESS-PLAN DEPENDENCY MISSING"
  say ""
  say "  harness-engineering's implementation phase delegates to the harness-plan skill."
  say "  Without harness-plan, you can still run discovery/design/architecture/test/"
  say "  release/ops phases, but implementation will not work."
  say ""
  say "  To install harness-plan:"
  say "    ./install.sh --with-harness-plan /path/to/harness-plan-skill"
  say "  or manually copy the harness-plan skill to $HARNESS_DEST"
  say ""
fi

say "Done."
