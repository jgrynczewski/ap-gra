"""The ap-gra-rysownik service: runs the drawing code written by the AI
(docs/kreator-gier.md, stage 5).

    python -m rysownik.serwis /praca

The container has no network and sees only its work directory (dane/rysownik/
on the disk). The creator talks to it with files - one directory per game:

    <id>/kod.py        the drawing code (the creator writes it first)
    <id>/zlecenie.json {"proba": n} - the job is ready
    <id>/klatki/       frames (this service)
    <id>/wynik.json    {"proba": n, "ok", "problemy": [...]} - done (this service)

Every code runs in a separate process with limits of memory, processor time
and wall time, so a broken or endless drawing cannot stop the service.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from .klatki import code_problems, frame_problems

RUNNER = Path(__file__).resolve().parent / "uruchom.py"
TIMEOUT = 120  # seconds for the whole animation
MEMORY = 512 * 1024 * 1024  # bytes of address space for the drawing process
POLL = 1.0


def _limits() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT + 5, TIMEOUT + 5))
    resource.setrlimit(resource.RLIMIT_FSIZE, (20 * 1024 * 1024, 20 * 1024 * 1024))


def _write_json(path: Path, data) -> None:
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    partial.replace(path)


def run_job(job: Path, timeout: float = TIMEOUT) -> dict:
    """Check and run the code of one job, write wynik.json, return it."""
    attempt = json.loads((job / "zlecenie.json").read_text(encoding="utf-8")).get("proba")
    found = code_problems((job / "kod.py").read_text(encoding="utf-8"))
    if not found:
        out = job / "klatki"
        try:
            process = subprocess.run([sys.executable, "-I", str(RUNNER), str(job / "kod.py"), str(out)],
                                     capture_output=True, text=True, timeout=timeout,
                                     preexec_fn=_limits if sys.platform != "win32" else None)
        except subprocess.TimeoutExpired:
            found = [f"rysowanie trwało dłużej niż {timeout:g} s - uprość rysunek"]
        else:
            if process.returncode != 0:
                error = process.stderr.strip()[-2000:] or f"proces zakończył się kodem {process.returncode}"
                if process.returncode < 0 and not process.stderr.strip():
                    error = "rysowanie przerwane (za dużo pamięci albo czasu) - uprość rysunek"
                found = ["błąd podczas rysowania:\n" + error]
            else:
                found = frame_problems(out)
    result = {"proba": attempt, "ok": not found, "problemy": found}
    _write_json(job / "wynik.json", result)
    return result


def pending(work: Path) -> list[Path]:
    return sorted(path.parent for path in work.glob("*/zlecenie.json")
                  if not (path.parent / "wynik.json").exists())


def main(work: str) -> None:
    directory = Path(work)
    directory.mkdir(parents=True, exist_ok=True)
    print(f"rysownik: czekam na zadania w {directory}", flush=True)
    while True:
        for job in pending(directory):
            try:
                result = run_job(job)
                print(f"rysownik: {job.name} - {'OK' if result['ok'] else 'błędy'}", flush=True)
            except (OSError, ValueError) as error:  # a broken job must not stop the service
                print(f"rysownik: {job.name} - {type(error).__name__}: {error}", flush=True)
                _write_json(job / "wynik.json", {"proba": None, "ok": False,
                                                 "problemy": [f"zadanie uszkodzone: {error}"]})
        time.sleep(POLL)


if __name__ == "__main__":
    main(sys.argv[1])
