"""Card selection (Leitner boxes) and distractor choice.

Every option shown in a question comes from the user's own deck — nothing is generated.
"""
import json
import os
import random
import re
import time

from .store import DATA_DIR

PROGRESS = os.path.join(DATA_DIR, "progress.json")
MAX_BOX = 4


def _words(s):
    return {w for w in re.findall(r"\w+", s.lower()) if len(w) > 2}


class Deck:
    def __init__(self, cards, metas=None, settings=None):
        self.settings = settings or {}
        self.set_cards(cards, metas or {})
        self.progress = self._load()

    def set_cards(self, cards, metas):
        self.items = cards
        self.metas = metas
        self.by_deck = {}
        for c in cards:
            self.by_deck.setdefault(c["deck"], []).append(c)

    # ---- progress ----
    def _load(self):
        try:
            with open(PROGRESS, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        data.setdefault("items", {})
        data.setdefault("stats", {"correct": 0, "wrong": 0})
        data.setdefault("recent", [])
        return data

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = PROGRESS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=1)
        os.replace(tmp, PROGRESS)

    def reset(self):
        self.progress = {"items": {}, "stats": {"correct": 0, "wrong": 0}, "recent": []}
        self.save()

    def record(self, item_id, correct):
        p = self.progress["items"].setdefault(item_id, {"box": 1, "seen": 0, "right": 0})
        p["seen"] += 1
        if correct:
            p["right"] += 1
            p["box"] = min(MAX_BOX, p["box"] + 1)
            self.progress["stats"]["correct"] += 1
        else:
            p["box"] = 0
            self.progress["stats"]["wrong"] += 1
        p["last"] = int(time.time())
        recent = self.progress["recent"]
        recent.append(item_id)
        del recent[:-15]
        self.save()

    # ---- selection ----
    def _weight(self, item_id):
        p = self.progress["items"].get(item_id)
        if p is None:
            return 4.0                              # never asked: medium weight
        return float(2 ** (MAX_BOX - p["box"]))     # box 0 → 16, box 4 → 1

    def _retired(self, item_id):
        if not self.settings.get("retire"):
            return False
        p = self.progress["items"].get(item_id)
        return bool(p) and p.get("right", 0) >= int(self.settings.get("retire_after", 3))

    def learned_count(self):
        ids = {i["id"] for i in self.items}
        if self.settings.get("retire"):
            return sum(1 for k in ids if self._retired(k))
        return sum(1 for k, v in self.progress["items"].items() if k in ids and v["box"] >= 3)

    def pick(self):
        if not self.items:
            return None
        recent = set(self.progress["recent"])
        active = [i for i in self.items if not self._retired(i["id"])]
        all_done = not active
        if all_done:
            active = self.items
        pool = [i for i in active if i["id"] not in recent] or active
        if self.settings.get("mode") == "random":
            target = random.choice(pool)
        else:
            target = random.choices(pool, weights=[self._weight(i["id"]) for i in pool], k=1)[0]
        q = self.question(target)
        q["all_done"] = all_done
        return q

    def distractors(self, target, ask, k=3):
        """k wrong options from the same deck (whole collection if the deck is tiny)."""
        same = self.by_deck.get(target["deck"], [])
        pool = same if len(same) >= k + 1 else self.items
        tw = _words(target["back"])
        tnorm = target["back"].lower()
        fnorm = target["front"].lower()
        tlen = len(target[ask])

        def ok(c):
            if c["id"] == target["id"]:
                return False
            cn = c["back"].lower()
            if cn == tnorm or cn in tnorm or tnorm in cn or c["front"].lower() == fnorm:
                return False
            cw = _words(c["back"])
            if tw and cw and len(tw & cw) / min(len(tw), len(cw)) >= 0.5:
                return False                        # meaning too close → can't be a wrong option
            return True

        same_kind = [c for c in pool if c["kind"] == target["kind"] and ok(c)]
        cands = same_kind if len(same_kind) >= k else [c for c in pool if ok(c)]
        cands.sort(key=lambda c: abs(len(c[ask]) - tlen) + random.random() * 25)
        near = cands[:40]
        random.shuffle(near)
        out, used = [], {target[ask].lower()}
        for c in near:
            n = c[ask].lower()
            if n in used:
                continue
            out.append(c)
            used.add(n)
            if len(out) == k:
                break
        return out

    def question(self, target):
        d = self.settings.get("direction", "front")
        if d == "mixed":
            d = random.choice(("front", "back"))
        show, ask = ("front", "back") if d == "front" else ("back", "front")
        options = [target] + self.distractors(target, ask)
        random.shuffle(options)
        meta = self.metas.get(target["deck"], {})
        st = self.progress["stats"]
        return {
            "id": target["id"],
            "direction": d,
            "shown": target[show],          # text on the card
            "front": target["front"],
            "back": target["back"],
            "note": target["note"],
            "deck": meta.get("name") or target["deck"],
            "labels": {"front": meta.get("front", ""), "back": meta.get("back", ""), "prompt": meta.get("prompt", "")},
            "sound_answer": bool(self.settings.get("sound_answer", True)),
            "sound_open": bool(self.settings.get("sound_open", True)),
            "answer": options.index(target),
            # "text" is what the button shows; "other" is its pair, revealed after answering
            "options": [{"text": o[ask], "other": o[show]} for o in options],
            "stats": {"correct": st["correct"], "wrong": st["wrong"],
                      "learned": self.learned_count(), "total": len(self.items)},
        }
