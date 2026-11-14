"""What Kompan knows about the user (docs/kompan.md -> Pamięć).

The AI adds entries during the conversation; it notes how it knows (the user
chose it, or it is a guess). The code keeps the limits, a copy of every
previous version and what the user said was wrong, so the AI does not save it
again. The user reviews new entries from time to time and can read and delete
all of them (CO O MNIE WIESZ). The start notes (notatki_startowe.txt) are
separate: written by hand and only read here.
"""

from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_hex
from typing import Callable

NOTE_CHARS = 80  # a review reads up to REVIEW_MAX entries on one screen
MAX_NEW = 3  # entries in one AI answer
REVIEW_AT = 5  # entries waiting for a review before the AI is told about it
REVIEW_MAX = 5
POSTPONE = timedelta(hours=2)  # "Nie teraz"
REJECTED_KEEP = 20

USER, GUESS = "uzytkownik", "przypuszczenie"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Notes:
    def __init__(self, data: Path, now: Callable[[], datetime] = _now):
        self.path = data / "notatki.json"
        self.versions = data / "notatki-wersje"
        self.now = now
        self._lock = threading.RLock()

    # --- the file ---------------------------------------------------------

    def _load(self) -> dict:
        if self.path.is_file():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"wpisy": [], "odrzucone": [], "przeglad_po": None}

    def _store(self, data: dict) -> None:
        """Save; the previous version stays in notatki-wersje/."""
        if self.path.is_file():
            self.versions.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.path, self.versions / f"{self.now():%Y%m%d-%H%M%S-%f}.json")
        partial = self.path.with_name(self.path.name + ".part")
        partial.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        partial.replace(self.path)

    # --- reading ----------------------------------------------------------

    def entries(self) -> list[dict]:
        with self._lock:
            return self._load()["wpisy"]

    def get(self, ids: list[str]) -> list[dict]:
        found = {entry["id"]: entry for entry in self.entries()}
        return [found[i] for i in ids if i in found]

    def pending(self) -> list[dict]:
        """Not reviewed yet, oldest first."""
        return [entry for entry in self.entries() if not entry["potwierdzony"]]

    def new_texts(self, notes: list[dict]) -> list[str]:
        """What add(notes) would add (without the repeats), saving nothing."""
        known = {e["tekst"].casefold() for e in self.entries()}
        texts = []
        for note in notes:
            text = note["tekst"].strip()
            if text.casefold() not in known:
                known.add(text.casefold())
                texts.append(text)
        return texts

    def review_due(self) -> bool:
        with self._lock:
            data = self._load()
            waiting = sum(not entry["potwierdzony"] for entry in data["wpisy"])
            after = data["przeglad_po"]
            return waiting >= REVIEW_AT and (after is None or self.now() >= datetime.fromisoformat(after))

    def for_ai(self) -> str:
        with self._lock:
            data = self._load()
        lines = [f"- {e['tekst']}" + (" (przypuszczenie)" if e["skad"] == GUESS and not e["potwierdzony"] else "")
                 for e in data["wpisy"]]
        text = "\n".join(lines) or "Jeszcze nic."
        if data["odrzucone"]:
            text += ("\n\nUżytkownik powiedział, że to nieprawda (nie zapisuj tego ponownie):\n"
                     + "\n".join(f"- {t}" for t in data["odrzucone"]))
        return text

    # --- changes ----------------------------------------------------------

    def add(self, notes: list[dict], conversation: str) -> list[dict]:
        """New entries from the AI; repeats of what is known are skipped."""
        with self._lock:
            data = self._load()
            texts = self.new_texts(notes)
            added = []
            for note in notes:
                text = note["tekst"].strip()
                if text not in texts:
                    continue
                texts.remove(text)
                added.append({"id": token_hex(4), "tekst": text, "skad": note["skad"],
                              "czas": self.now().isoformat(timespec="seconds"),
                              "potwierdzony": False, "rozmowa": conversation})
            if added:
                data["wpisy"].extend(added)
                self._store(data)
            return added

    def confirm(self, ids: list[str]) -> None:
        with self._lock:
            data = self._load()
            for entry in data["wpisy"]:
                if entry["id"] in ids:
                    entry["potwierdzony"] = True
            self._store(data)

    def remove(self, nid: str) -> dict | None:
        """The user says it is wrong: gone, and the AI is told not to save it again."""
        with self._lock:
            data = self._load()
            found = next((e for e in data["wpisy"] if e["id"] == nid), None)
            if found is None:
                return None
            data["wpisy"].remove(found)
            data["odrzucone"] = (data["odrzucone"] + [found["tekst"]])[-REJECTED_KEEP:]
            self._store(data)
            return found

    def postpone(self) -> None:
        with self._lock:
            data = self._load()
            data["przeglad_po"] = (self.now() + POSTPONE).isoformat(timespec="seconds")
            self._store(data)
