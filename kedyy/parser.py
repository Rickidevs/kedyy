"""Deck file parser.

A deck is a plain text (or CSV/TSV) file. Each line is one card: a *front*
(what KEDYY shows) and a *back* (the answer), in any language or script.

    001. no way — not at all (informal)       numbered, em dash
    break a leg - good luck                    hyphen
    der Hund = the dog                         equals sign
    capital of France: Paris                   colon + space
    猫<TAB>cat                                  tab
    .csv / .tsv: column 1 = front, column 2 = back, column 3 (optional) = note

A trailing "( ... )" on the back becomes the card's note.

Optional header lines set deck metadata:

    #! name: German basics
    #! front: Deutsch
    #! back: English
    #! prompt: What does it mean?

Any other line starting with "#" is a comment.
"""
import csv
import os
import re

PREFIX_RE = re.compile(r"^\s*(?:\d+\s*[.)-]\s*|[-*•·]\s+)?")
NUM_RE = re.compile(r"^\s*\d+\s*[.)-]\s")
META_RE = re.compile(r"^\s*#!\s*([\w-]+)\s*[:=]\s*(.*?)\s*$")
# tried in order; the first separator that splits the line wins
SEPARATORS = [
    re.compile(r"\s+[—–]\s+"),
    re.compile(r"\s*[—–]\s*"),
    re.compile(r"\t+"),
    re.compile(r"\s+=\s+|\s*=\s*"),
    re.compile(r"\s+-{1,2}\s+"),
    re.compile(r"\s*;\s*"),
    re.compile(r"\s*[:：]\s+"),
    re.compile(r"\s*\|\s*"),
]
HEADER_WORDS = {"front", "back", "question", "answer", "en", "english", "word", "term",
                "ön", "arka", "soru", "cevap", "kelime"}
SUPPORTED = (".txt", ".csv", ".tsv", ".md", ".text")
META_KEYS = {"name", "front", "back", "prompt"}


def split_note(text):
    """Split a trailing '( ... )' note off the back (nested parentheses safe)."""
    text = text.strip()
    if not text.endswith(")"):
        return text, ""
    depth = 0
    for i in range(len(text) - 1, -1, -1):
        c = text[i]
        if c == ")":
            depth += 1
        elif c == "(":
            depth -= 1
            if depth == 0:
                main, note = text[:i].strip(), text[i + 1:-1].strip()
                return (text, "") if not main else (main, note)
    return text, ""


def _card(front, back, note, deck):
    front = front.strip().strip('"').strip()
    back = back.strip().strip('"').strip()
    if not re.search(r"\b\w\.$", back):      # keep abbreviations like "D.C."
        back = back.rstrip(" .;")
    if not front or not back or len(front) > 300:
        return None
    if not note:
        back, note = split_note(back)
    if not back:
        return None
    key = front.lower().strip(" .!?。！？")
    return {
        "id": f"{deck}::{key}",
        "front": front,
        "back": back,
        "note": note.strip(),
        "deck": deck,
        "kind": "word" if not re.search(r"\s", front) else "phrase",
    }


def _parse_line(line):
    line = line.replace("﻿", "").strip()
    if not line or line.startswith("#") or set(line) <= set("=-_*~ "):
        return None
    if line.isupper() and len(line.split()) > 1:   # SECTION HEADINGS
        return None
    body = PREFIX_RE.sub("", line, count=1)
    for sep in SEPARATORS:
        parts = sep.split(body, maxsplit=1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return parts[0], parts[1]
    return None


def deck_name(path):
    return os.path.splitext(os.path.basename(path))[0]


def parse_file(path):
    """Return (meta, cards) for one deck file. Duplicate fronts are merged."""
    deck = deck_name(path)
    meta = {"name": deck.replace("_", " "), "front": "", "back": "", "prompt": ""}
    ext = os.path.splitext(path)[1].lower()
    cards = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        text = f.read()
    lines = text.splitlines()
    for ln in lines:
        m = META_RE.match(ln)
        if m and m.group(1).lower() in META_KEYS:
            meta[m.group(1).lower()] = m.group(2)

    if ext in (".csv", ".tsv"):
        body = [ln for ln in lines if not ln.lstrip().startswith("#")]
        sample = "\n".join(body[:30])
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel_tab if ext == ".tsv" else csv.excel
        for i, row in enumerate(csv.reader(body, dialect)):
            row = [c.strip() for c in row]
            heads = HEADER_WORDS | {meta["front"].lower(), meta["back"].lower()}
            if len(row) < 2 or (i == 0 and row[0].lower() in heads):
                continue
            c = _card(row[0], row[1], row[2] if len(row) > 2 else "", deck)
            if c:
                cards.append(c)
    else:
        parsed = []
        for raw in lines:
            p = _parse_line(raw)
            if p:
                parsed.append((bool(NUM_RE.match(raw.replace("﻿", ""))), p))
        numbered = sum(1 for n, _ in parsed if n)
        # in a numbered list, un-numbered lines are notes, not cards
        only_numbered = numbered >= 5 and numbered >= len(parsed) * 0.6
        for n, (front, back) in parsed:
            if only_numbered and not n:
                continue
            c = _card(front, back, "", deck)
            if c:
                cards.append(c)

    seen, out = {}, []
    for c in cards:
        old = seen.get(c["id"])
        if old:
            if not old["note"] and c["note"]:
                old["note"] = c["note"]
            continue
        seen[c["id"]] = c
        out.append(c)
    return meta, out


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        meta, cards = parse_file(p)
        print(p, meta, len(cards))
        for c in cards[:3]:
            print("   ", c)
