#!/usr/bin/env bash
set -euo pipefail

# Sync all local Anki add-ons from this directory into Anki's addons21 folder
# by creating/updating symlinks for each subdirectory.
#
# Usage:
#   cd ~/anki-plugins
#   ./sync-anki-addons.sh
#
# Notes:
# - Existing non-symlink folders in addons21 are left untouched (e.g. AnkiWeb add-ons).
# - Existing symlinks with the same name are replaced.

DEV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANKI_ADDONS="$HOME/Library/Application Support/Anki2/addons21"

echo "Dev root:    $DEV_ROOT"
echo "Anki addons: $ANKI_ADDONS"
echo

if [ ! -d "$ANKI_ADDONS" ]; then
  echo "Error: Anki addons directory does not exist at:"
  echo "  $ANKI_ADDONS"
  echo "Open Anki once to create it, then rerun this script."
  exit 1
fi

for dir in "$DEV_ROOT"/*; do
  # Only consider directories
  [ -d "$dir" ] || continue

  name="$(basename "$dir")"

  # Skip known non-add-on directories
  case "$name" in
    .git|.cursor|node_modules|assets|__pycache__) continue ;;
  esac

  src="$dir"
  dst="$ANKI_ADDONS/$name"

  # If there's an existing symlink, remove it so we can recreate it cleanly.
  if [ -L "$dst" ]; then
    echo "Removing existing symlink: $dst"
    rm "$dst"
  elif [ -e "$dst" ]; then
    # Real directory or file: leave it alone (probably an installed add-on).
    echo "Skipping $name: $dst exists and is not a symlink."
    continue
  fi

  ln -s "$src" "$dst"
  echo "Linked $name -> $dst"
done

echo
echo "Done. Restart Anki to load updated dev add-ons."

