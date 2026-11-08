"""A log: one JSON line per event, appended and never edited.

Used for the creator conversations (every AI request and response and every
user answer, docs/kreator-gier.md -> "Historia rozmowy z AI zawsze zapisana")
and for the playthroughs of the games (api/app.py, tools/statystyki.py). The
line is written and flushed to disk before the code goes on, so a crash right
after an event still leaves it in the log. Time in UTC with the offset.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path


class Log:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, kind: str, **data) -> None:
        entry = {"czas": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                 "rodzaj": kind, **data}
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
