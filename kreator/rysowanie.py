"""The creator's side of the drawing service (rysownik/serwis.py): a job is
a directory in dane/rysownik/<id>/ - the code first, then zlecenie.json; the
service writes the frames and wynik.json. The service has no network, so
files are the only way to it."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Callable

WAIT = 300  # seconds for one drawing (the service itself stops a job after 2 minutes)
POLL = 1.0


def _write_json(path: Path, data) -> None:
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    partial.replace(path)


class Painter:
    def __init__(self, work: Path, wait: float = WAIT, poll: float = POLL,
                 run_job: Callable[[Path], dict] | None = None):
        self.work = work
        self.wait = wait
        self.poll = poll
        self._run_job = run_job  # tests: run the job here instead of the service

    def frames(self, job_id: str) -> Path:
        return self.work / job_id / "klatki"

    def paint(self, job_id: str, attempt: int, code: str) -> dict:
        """{"ok", "problemy"} of this code; "brak_rysownika": True when the
        service did not answer in time."""
        job = self.work / job_id
        job.mkdir(parents=True, exist_ok=True)
        for old in ("wynik.json", "zlecenie.json"):
            (job / old).unlink(missing_ok=True)
        if self.frames(job_id).exists():
            shutil.rmtree(self.frames(job_id))
        (job / "kod.py").write_text(code, encoding="utf-8")
        _write_json(job / "zlecenie.json", {"proba": attempt})  # last: the job is ready
        if self._run_job:
            return self._run_job(job)
        deadline = time.monotonic() + self.wait
        while time.monotonic() < deadline:
            result_path = job / "wynik.json"
            if result_path.exists():
                result = json.loads(result_path.read_text(encoding="utf-8"))
                if result.get("proba") == attempt:
                    return result
            time.sleep(self.poll)
        return {"ok": False, "brak_rysownika": True,
                "problemy": [f"rysownik nie odpowiedział w {self.wait:g} s"]}
