"""Making a game from an approved idea (docs/kreator-gier.md, stage 4).

A fixed line of steps, each saving its result to dane/zadania/<id>/:

    zarys       the AI writes an outline                  -> zarys.json
    scenariusz  the AI writes the scenario; engine.check
                and our limits; errors go back to the AI,
                up to 3 answers                           -> scenariusz.md
    kontrola    the AI reads the story; serious problems
                go back to the writer once; a failed fix
                keeps the checked scenario                -> kontrola.json, gotowy.md
    nagrania    the narrator records every text           -> audio/, nagrania.json
    publikacja  gry/<game>.tmp, then one rename           -> gry/<game>/

A step whose result is on disk is not done again, so after a restart of the
computer the work goes on from the step it stopped at. Games are made one at
a time (one AI job, one narrator). Everything - the AI requests and answers
too - goes to the log of the conversation (rozmowy/<id>/log.jsonl), so one
file tells the whole story of the game; a copy goes into the game.
"""

from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from engine import voice
from engine.check import check
from engine.scenario import Scenario, ScenarioError, parse

from .ai import AI, AIError, GAME_EFFORT, GAME_MAX_TOKENS
from engine.log import Log

PROMPTS = Path(__file__).parent / "prompty"

STEPS = ("zarys", "scenariusz", "kontrola", "nagrania", "publikacja")

# Statuses
W_TOKU = "w_toku"
GOTOWA = "gotowa"
NIEUDANA = "nieudana"

# What a scenario must be - like our two games (docs/kreator-gier.md ->
# "Ustawienia domyślne"); engine.check does the rest
SCENES = (18, 32)
ENDINGS = (3, 9)
SHORTEST = 5  # choices in the shortest playthrough
OPTION_CHARS = 60
ATTEMPTS = 3  # scenario answers per step: the first and up to 2 corrections
SHOWN_PROBLEMS = 15  # sent back to the AI at once

OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {"zarys": {"type": "string"}},
    "required": ["zarys"],
    "additionalProperties": False,
}
SCENARIO_SCHEMA = {
    "type": "object",
    "properties": {"scenariusz": {"type": "string"}},
    "required": ["scenariusz"],
    "additionalProperties": False,
}
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "uwagi": {"type": "array", "items": {"type": "string"}}},
    "required": ["ok", "uwagi"],
    "additionalProperties": False,
}


class CreationError(Exception):
    """A step that cannot be done - the game is not made (the message is for
    the log)."""


def _prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def game_id(task_id: str) -> str:
    """20261108-153000-ab12 -> g20261108_153000_ab12 (a game id: [a-z0-9_])."""
    return "g" + task_id.replace("-", "_")


def scenario_problems(text: str, title: str) -> tuple[list[str], Scenario | None]:
    """What is wrong with a scenario from the AI; ([], scenario) = fine."""
    try:
        scenario = parse(text, "scenariusz.md")
    except ScenarioError as error:
        return [f"błąd formatu: {error}"], None
    report = check(scenario)
    found = list(report.errors)
    if scenario.title != title:
        found.append(f"pierwsza linia ma brzmieć: # {title}")
    scenes, endings = len(scenario.scenes), len(scenario.endings)
    if not SCENES[0] <= scenes <= SCENES[1]:
        found.append(f"scen jest {scenes}, ma być od {SCENES[0]} do {SCENES[1]}")
    if not ENDINGS[0] <= endings <= ENDINGS[1]:
        found.append(f"zakończeń jest {endings}, ma być od {ENDINGS[0]} do {ENDINGS[1]}")
    shortest = report.stats.get("najkrótsza rozgrywka (wybory)")
    if shortest is not None and shortest < SHORTEST:
        found.append(f"najkrótsza rozgrywka ma {shortest} wyborów, ma mieć co najmniej {SHORTEST}")
    for scene in scenario.scenes.values():
        for option in scene.options:
            if len(option.text) > OPTION_CHARS:
                found.append(f"{scene.id} (linia {option.line}): opcja dłuższa niż {OPTION_CHARS} znaków "
                             f"- skróć: {option.text!r}")
    return found, scenario


def _correction(prefix: str, found: list[str]) -> str:
    shown = found[:SHOWN_PROBLEMS]
    more = f"\n... i {len(found) - len(shown)} innych" if len(found) > len(shown) else ""
    return prefix + "\n- " + "\n- ".join(shown) + more


def _write_json(path: Path, data) -> None:
    """Whole file or nothing: a half-written result must not count as done."""
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    partial.replace(path)


def _write_text(path: Path, text: str) -> None:
    partial = path.with_name(path.name + ".part")
    partial.write_text(text, encoding="utf-8")
    partial.replace(path)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Task:
    """One game being made: dane/zadania/<id>/ (id = id of the conversation)."""

    def __init__(self, directory: Path, data: Path, ai: AI, narrator=None):
        self.id = directory.name
        self.directory = directory
        self.games = data / "gry"
        self.game = game_id(self.id)
        self.log = Log(data / "rozmowy" / self.id / "log.jsonl")
        self.ai = ai
        self.narrator = narrator

    # --- state ------------------------------------------------------------

    @property
    def idea(self) -> dict:
        return _read_json(self.directory / "pomysl.json")

    def state(self) -> dict:
        return _read_json(self.directory / "stan.json")

    def _set(self, **changes) -> None:
        _write_json(self.directory / "stan.json", {**self.state(), **changes})

    def view(self) -> dict:
        state = self.state()
        step = state.get("krok")
        return {"id": self.id, "gra": self.game, "tytul": self.idea["tytul"], "status": state["status"],
                "krok": step, "krok_nr": STEPS.index(step) + 1 if step in STEPS else None,
                "krokow": len(STEPS), "utworzona": state.get("utworzona")}

    def done(self, step: str) -> bool:
        files = {"zarys": "zarys.json", "scenariusz": "scenariusz.md", "kontrola": "gotowy.md",
                 "nagrania": "nagrania.json"}
        if step == "publikacja":
            return (self.games / self.game).is_dir()
        return (self.directory / files[step]).exists()

    # --- the work ---------------------------------------------------------

    def run(self) -> None:
        """All steps not done yet; the status ends as gotowa or nieudana."""
        if self.state()["status"] != W_TOKU:
            return
        self.log.write("tworzenie", gra=self.game, kroki_zrobione=[s for s in STEPS if self.done(s)])
        try:
            for step in STEPS:
                if self.done(step):
                    continue
                self._set(krok=step)
                self.log.write("krok_start", krok=step)
                getattr(self, "_" + step)()
                self.log.write("krok_koniec", krok=step)
        except (AIError, CreationError, OSError) as error:
            self.log.write("tworzenie_nieudane", krok=self.state().get("krok"),
                           blad=f"{type(error).__name__}: {error}")
            self._set(status=NIEUDANA)
            return
        self._set(status=GOTOWA, krok=None)
        self.log.write("tworzenie_gotowe", gra=self.game)

    def _ask(self, purpose: str, messages: list[dict], schema: dict) -> dict:
        return self.ai.ask(self.log, purpose, _prompt(purpose), messages, schema,
                           effort=GAME_EFFORT, max_tokens=GAME_MAX_TOKENS)

    def _brief(self) -> str:
        """The idea (and the outline, once there is one) for the AI."""
        idea = self.idea
        lines = [f"Tytuł: {idea['tytul']}", f"Streszczenie: {idea['streszczenie']}", "",
                 "Pytania i odpowiedzi użytkownika:"]
        lines += [f"- {q['pytanie']} -> {q['odpowiedz']}" for q in idea["rozmowa"]]
        outline = self.directory / "zarys.json"
        if outline.exists():
            lines += ["", "Zarys:", _read_json(outline)["zarys"]]
        return "\n".join(lines)

    def _zarys(self) -> None:
        answer = self._ask("zarys", [{"role": "user", "content": self._brief()}], OUTLINE_SCHEMA)
        if not answer["zarys"].strip():
            raise CreationError("pusty zarys")
        _write_json(self.directory / "zarys.json", {"zarys": answer["zarys"].strip()})

    def _write_scenario(self, messages: list[dict]) -> str:
        """The AI writes until the scenario passes the checks (ATTEMPTS answers)."""
        title = self.idea["tytul"]
        for attempt in range(1, ATTEMPTS + 1):
            text = self._ask("scenariusz", messages, SCENARIO_SCHEMA)["scenariusz"].strip() + "\n"
            found, _ = scenario_problems(text, title)
            if not found:
                return text
            self.log.write("scenariusz_odrzucony", proba=attempt, problemy=found)
            messages = messages + [
                {"role": "assistant", "content": json.dumps({"scenariusz": text}, ensure_ascii=False)},
                {"role": "user", "content": _correction("Popraw:", found)}]
        raise CreationError(f"scenariusz z błędami po {ATTEMPTS} próbach")

    def _scenariusz(self) -> None:
        text = self._write_scenario([{"role": "user", "content": self._brief()}])
        _write_text(self.directory / "scenariusz.md", text)

    def _kontrola(self) -> None:
        """The story read by the AI. Not being able to check or fix it keeps
        the scenario that passed the checks - the game is still made."""
        text = (self.directory / "scenariusz.md").read_text(encoding="utf-8")
        final = text
        try:
            review = self._ask("kontrola", [{"role": "user", "content":
                                             f"{self._brief()}\n\nScenariusz:\n{text}"}], REVIEW_SCHEMA)
            notes = [n.strip() for n in review["uwagi"] if n.strip()]
            _write_json(self.directory / "kontrola.json", {"ok": review["ok"], "uwagi": notes})
            if not review["ok"] and notes:
                final = self._write_scenario([
                    {"role": "user", "content": self._brief()},
                    {"role": "assistant", "content": json.dumps({"scenariusz": text}, ensure_ascii=False)},
                    {"role": "user", "content": _correction("Popraw fabułę:", notes)}])
        except (AIError, CreationError) as error:
            self.log.write("kontrola_pominieta", blad=f"{type(error).__name__}: {error}",
                           powod="zostaje scenariusz sprawdzony programem")
        _write_text(self.directory / "gotowy.md", final)

    def _nagrania(self) -> None:
        """Recordings of the whole game. Without them the game still works
        (AP reads with its own voice), so a failure only goes to the log."""
        audio = self.directory / "audio"
        texts = voice.texts(parse((self.directory / "gotowy.md").read_text(encoding="utf-8")))
        result = {"tekstow": len(texts), "nagrania": 0, "blad": None}
        if self.narrator is None:
            result["blad"] = "brak Pipera albo modelu głosu"
        else:
            try:
                self.narrator.record_all(texts, audio)
            except Exception as error:  # noqa: BLE001 - Piper can fail in many ways
                result["blad"] = f"{type(error).__name__}: {error}"
        result["nagrania"] = len(list(audio.glob("*.wav"))) if audio.is_dir() else 0
        if result["blad"]:
            self.log.write("blad_nagrania", blad=result["blad"])
        _write_json(self.directory / "nagrania.json", result)

    def _publikacja(self) -> None:
        """The game is put together in gry/<game>.tmp (the games API skips
        such names) and renamed in one move - AP never sees half a game."""
        idea = self.idea
        temporary = self.games / f"{self.game}.tmp"
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir(parents=True)
        shutil.copy2(self.directory / "gotowy.md", temporary / "scenariusz.md")
        if (self.directory / "audio").is_dir():
            shutil.copytree(self.directory / "audio", temporary / "audio")
        _write_json(temporary / "gra.json", {
            "id": self.game, "tytul": idea["tytul"], "streszczenie": idea["streszczenie"],
            "rozmowa": self.id, "model": self.ai.model,
            "utworzona": datetime.now().isoformat(timespec="seconds")})
        self.log.write("publikacja", gra=self.game)
        shutil.copy2(self.log.path, temporary / "rozmowa.jsonl")
        temporary.rename(self.games / self.game)


def _thread(work: Callable[[], None]) -> None:
    threading.Thread(target=work, daemon=True).start()


class Workshop:
    """The queue of games being made (dane/zadania/), one at a time."""

    def __init__(self, data: Path, ai: AI, narrator=None,
                 run: Callable[[Callable[[], None]], None] = _thread):
        self.data = data
        self.tasks_dir = data / "zadania"
        self.ai = ai
        self.narrator = narrator
        self._run = run
        self._lock = threading.Lock()
        self._queue: list[Task] = []
        self._busy = False

    def _task(self, task_id: str) -> Task:
        return Task(self.tasks_dir / task_id, self.data, self.ai, self.narrator)

    def add(self, task_id: str, idea: dict) -> Task:
        """A new game from an approved conversation (again for the same
        conversation - the game already being made)."""
        task = self._task(task_id)
        if not (task.directory / "stan.json").exists():
            task.directory.mkdir(parents=True, exist_ok=True)
            _write_json(task.directory / "pomysl.json", idea)
            _write_json(task.directory / "stan.json", {
                "status": W_TOKU, "krok": None, "utworzona": datetime.now().isoformat(timespec="seconds")})
            task.log.write("tworzenie_zlecone", gra=task.game, pomysl=idea)
            self._enqueue(task)
        return task

    def resume(self) -> int:
        """Games left unfinished (e.g. the computer was turned off) - on start
        of the service; returns how many."""
        found = [self._task(path.parent.name) for path in sorted(self.tasks_dir.glob("*/stan.json"))]
        unfinished = [task for task in found if task.state()["status"] == W_TOKU]
        for task in unfinished:
            self._enqueue(task)
        return len(unfinished)

    def get(self, task_id: str) -> Task | None:
        task = self._task(task_id)
        return task if (task.directory / "stan.json").exists() else None

    def views(self) -> list[dict]:
        return [self._task(path.parent.name).view() for path in sorted(self.tasks_dir.glob("*/stan.json"))]

    def _enqueue(self, task: Task) -> None:
        with self._lock:
            self._queue.append(task)
            if self._busy:
                return
            self._busy = True
        self._run(self._work)

    def _work(self) -> None:
        while True:
            with self._lock:
                if not self._queue:
                    self._busy = False
                    return
                task = self._queue.pop(0)
            try:
                task.run()
            except Exception as error:  # noqa: BLE001 - one broken game must not stop the queue
                task.log.write("tworzenie_nieudane", blad=f"{type(error).__name__}: {error}")
                try:
                    task._set(status=NIEUDANA)
                except OSError:
                    pass
