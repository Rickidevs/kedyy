#!/usr/bin/env bash
# Remove KEDYY's menu entry, icon and autostart entry.
# Your decks and progress stay in ~/.local/share/kedyy unless you pass --purge.
set -euo pipefail

APP_ID="io.github.kedyy.Kedyy"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

pkill -f "bin/kedyy" 2>/dev/null || true
rm -f "$DATA_HOME/applications/$APP_ID.desktop" \
      "$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg" \
      "$CONFIG_HOME/autostart/$APP_ID.desktop"

if [[ "${1:-}" == "--purge" ]]; then
  rm -rf "$DATA_HOME/kedyy"
  echo "Removed KEDYY and all its data."
else
  echo "Removed KEDYY. Your decks and progress are still in $DATA_HOME/kedyy (use --purge to delete them)."
fi
