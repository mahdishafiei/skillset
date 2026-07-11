#!/usr/bin/env bash
# Locate the abstar venv and run annotate.py under it.
# Override detection with:  ABSTAR_HOME=/path/to/abstar  (must contain .venv/bin/python)
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

find_home() {
  if [[ -n "${ABSTAR_HOME:-}" && -x "$ABSTAR_HOME/.venv/bin/python" ]]; then
    echo "$ABSTAR_HOME"; return 0
  fi
  local c
  for c in \
    "$HOME/abstar" \
    "$HOME/code/abstar" \
    "$HOME/src/abstar" \
    "$HOME/Library/CloudStorage"/GoogleDrive-*/"My Drive/06_VS_code/abstar" \
    "$HOME/Library/CloudStorage"/GoogleDrive-*/"My Drive"/*/abstar ; do
    if [[ -x "$c/.venv/bin/python" ]]; then echo "$c"; return 0; fi
  done
  return 1
}

if ! home="$(find_home)"; then
  echo "abstar venv not found. Install abstar and set ABSTAR_HOME=/path/to/abstar" \
       "(the folder that contains .venv/bin/python)." >&2
  exit 1
fi

exec "$home/.venv/bin/python" "$here/annotate.py" "$@"
