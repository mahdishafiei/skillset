#!/usr/bin/env bash
# Install skills from this repo into ~/.claude/skills/ by symlinking.
# Usage:
#   ./install.sh <skill-name>   # link one skill
#   ./install.sh --all          # link every skill in ./skills
set -euo pipefail

SKILLS_DIR="$HOME/.claude/skills"
REPO_SKILLS="$(cd "$(dirname "$0")/skills" && pwd)"
mkdir -p "$SKILLS_DIR"

link() {
  local name="$1"
  if [[ ! -d "$REPO_SKILLS/$name" ]]; then
    echo "skip: no skill named '$name' in $REPO_SKILLS" >&2
    return 1
  fi
  ln -sfn "$REPO_SKILLS/$name" "$SKILLS_DIR/$name"
  echo "linked  $name  ->  $SKILLS_DIR/$name"
}

case "${1:-}" in
  --all) for d in "$REPO_SKILLS"/*/; do link "$(basename "$d")"; done ;;
  "")    echo "usage: ./install.sh <skill-name> | --all" >&2; exit 1 ;;
  *)     link "$1" ;;
esac

echo "Done. Start a new Claude Code session to load the skill(s)."
