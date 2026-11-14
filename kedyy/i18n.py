"""Interface translations. Each locale is a JSON file in kedyy/locales/; English is the fallback."""
import glob
import json
import locale
import os

LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")


def available():
    """{code: display name} for every locale file."""
    out = {}
    for p in sorted(glob.glob(os.path.join(LOCALES_DIR, "*.json"))):
        code = os.path.splitext(os.path.basename(p))[0]
        try:
            with open(p, encoding="utf-8") as f:
                out[code] = json.load(f).get("_name", code)
        except (OSError, ValueError):
            pass
    return out


def system_language():
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var)
        if v:
            return v.split(":")[0].split(".")[0].split("_")[0].lower()
    try:
        return (locale.getlocale()[0] or "en").split("_")[0].lower()
    except (ValueError, TypeError):
        return "en"


def resolve(setting):
    code = system_language() if setting in ("", "auto", None) else setting
    return code if code in available() else "en"


def load(setting="auto"):
    """Merged strings for the chosen language (missing keys fall back to English)."""
    code = resolve(setting)

    def read(c):
        try:
            with open(os.path.join(LOCALES_DIR, c + ".json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    strings = read("en")
    if code != "en":
        strings.update(read(code))
    strings["_code"] = code
    return strings
