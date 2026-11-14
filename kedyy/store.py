"""Settings and deck (file) management."""
import glob
import json
import os
import re
import shutil

from .parser import SUPPORTED, deck_name, parse_file

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(PKG_DIR)
EXAMPLES_DIR = os.path.join(REPO_DIR, "examples")

DATA_DIR = os.path.expanduser(os.environ.get("KEDYY_DATA_DIR") or
                              os.path.join(os.environ.get("XDG_DATA_HOME") or "~/.local/share", "kedyy"))
DECKS_DIR = os.path.join(DATA_DIR, "decks")
SETTINGS = os.path.join(DATA_DIR, "settings.json")

DEFAULTS = {
    "language": "auto",       # interface language: "auto" or a locale code ("en", "tr", ...)
    "enabled": True,          # ask questions at all
    "min_gap": 10,            # minutes
    "max_gap": 30,            # minutes
    "idle_limit": 3,          # minutes without keyboard/mouse = away; 0 = don't check
    "mode": "smart",          # "smart" = weak cards more often, "random"
    "direction": "front",     # "front" = show front, pick back; "back" = reverse; "mixed"
    "retire": True,           # stop asking a card after N correct answers
    "retire_after": 3,
    "sound_answer": True,
    "sound_open": True,
    "corner": "bottom-right", # popup position
    "disabled_decks": [],
}


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            s.update(json.load(f))
    except (OSError, ValueError):
        pass
    return s


def save_settings(new):
    s = load_settings()
    for k, v in new.items():
        if k in DEFAULTS:
            s[k] = v
    s["min_gap"] = max(1, min(600, int(s["min_gap"])))
    s["max_gap"] = max(s["min_gap"], min(600, int(s["max_gap"])))
    s["idle_limit"] = max(0, min(120, int(s["idle_limit"])))
    s["retire_after"] = max(1, min(20, int(s["retire_after"])))
    if s["mode"] not in ("smart", "random"):
        s["mode"] = "smart"
    if s["direction"] not in ("front", "back", "mixed"):
        s["direction"] = "front"
    if s["corner"] not in ("bottom-right", "bottom-left", "top-right", "top-left"):
        s["corner"] = "bottom-right"
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SETTINGS)
    return s


def ensure_decks():
    """On first run, start with the bundled example decks."""
    if os.path.isdir(DECKS_DIR):
        return
    os.makedirs(DECKS_DIR, exist_ok=True)
    for p in sorted(glob.glob(os.path.join(EXAMPLES_DIR, "*"))):
        if p.lower().endswith(SUPPORTED):
            shutil.copy2(p, os.path.join(DECKS_DIR, os.path.basename(p)))


def deck_files():
    ensure_decks()
    return sorted(p for p in glob.glob(os.path.join(DECKS_DIR, "*"))
                  if p.lower().endswith(SUPPORTED) and os.path.isfile(p))


def decks():
    """[{file, name, front, back, count}] — every file is a deck."""
    out = []
    for p in deck_files():
        meta, cards = parse_file(p)
        out.append({"file": os.path.basename(p), **meta, "count": len(cards)})
    return out


def load_cards(settings=None):
    """(cards, metas) for all enabled decks. metas: {deck: meta}."""
    s = settings or load_settings()
    off = set(s.get("disabled_decks", []))
    cards, metas = [], {}
    for p in deck_files():
        if os.path.basename(p) in off:
            continue
        meta, cs = parse_file(p)
        metas[deck_name(p)] = meta
        cards.extend(cs)
    return cards, metas


def import_file(path):
    """Copy a deck file into the decks folder. Returns (file name, card count)."""
    if not path.lower().endswith(SUPPORTED):
        raise ValueError("unsupported")
    _, cards = parse_file(path)
    if not cards:
        raise ValueError("empty")
    ensure_decks()
    base = re.sub(r"[^\w.\-]+", "_", os.path.basename(path)).strip("_") or "deck.txt"
    stem, ext = os.path.splitext(base)
    dest, i = os.path.join(DECKS_DIR, base), 2
    while os.path.exists(dest):
        dest = os.path.join(DECKS_DIR, f"{stem}_{i}{ext}")
        i += 1
    shutil.copy2(path, dest)
    return os.path.basename(dest), len(cards)


def delete_deck(name):
    p = os.path.join(DECKS_DIR, os.path.basename(name))
    if os.path.isfile(p):
        os.remove(p)
    s = load_settings()
    if name in s["disabled_decks"]:
        s["disabled_decks"].remove(name)
        save_settings(s)
