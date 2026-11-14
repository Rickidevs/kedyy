#!/usr/bin/env bash
# Install KEDYY for the current user (no root needed).
# It runs from this folder, so keep the folder where it is after installing.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="io.github.kedyy.Kedyy"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
APPS="$DATA_HOME/applications"
ICONS="$DATA_HOME/icons/hicolor/scalable/apps"
AUTOSTART="$CONFIG_HOME/autostart"

echo "Checking dependencies…"
if ! python3 - <<'PY' 2>/dev/null
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gtk, WebKit2
PY
then
  cat <<'MSG'
KEDYY needs Python 3 with GTK 3 and WebKitGTK (4.1) bindings. Install them with:

  Debian / Ubuntu / Mint / Zorin / Pop!_OS:
    sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
  Fedora:
    sudo dnf install python3-gobject gtk3 webkit2gtk4.1
  Arch / Manjaro:
    sudo pacman -S python-gobject gtk3 webkit2gtk-4.1
  openSUSE:
    sudo zypper install python3-gobject typelib-1_0-Gtk-3_0 typelib-1_0-WebKit2-4_1

Then run ./install.sh again.
MSG
  exit 1
fi

chmod +x "$HERE/bin/kedyy"
mkdir -p "$APPS" "$ICONS" "$AUTOSTART"
cp "$HERE/kedyy/kedyy.svg" "$ICONS/$APP_ID.svg"

cat > "$APPS/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=KEDYY
GenericName=Flashcard cat
Comment=A cat that quizzes you on your own flashcards during the day
Keywords=flashcards;quiz;language;learn;vocabulary;spaced;repetition;
Exec="$HERE/bin/kedyy"
Icon=$APP_ID
Terminal=false
Categories=Education;
StartupWMClass=kedyy
Actions=ask;

[Desktop Action ask]
Name=Ask me now
Name[tr]=Şimdi soru sor
Exec="$HERE/bin/kedyy" --now
EOF

if [[ "${1:-}" != "--no-autostart" ]]; then
  cat > "$AUTOSTART/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=KEDYY
Comment=Start KEDYY in the background
Exec="$HERE/bin/kedyy" --background
Icon=$APP_ID
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=20
EOF
  echo "KEDYY will start automatically when you log in (use --no-autostart to skip)."
fi

command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true

echo "Done! Open KEDYY from your app menu, or run: $HERE/bin/kedyy"
