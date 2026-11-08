"""A conversation with the AI about a new game (docs/kreator-gier.md).

The AI asks one question at a time with 2-3 answers; the code adds "Inne
propozycje". When the AI has enough, it gives a title and a summary - the
user picks ROZPOCZNIJ (the game will be made, stage 4) or INNY POMYSŁ.

AP never waits for the AI: an answer only starts the AI in the background
(status "mysli"), AP asks for the status every second. WRÓĆ never asks the
AI - it drops the last step and shows the question before it again; an AI
answer that comes after WRÓĆ is logged and ignored.

Each step: a checked AI answer (question or summary) and what the user chose
then. The messages for the AI are rebuilt from the steps, so going back
simply sends a shorter conversation.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from secrets import token_hex
from typing import Callable

from engine import voice
from engine.screen import text_lines

from .ai import AI, AIError
from engine.log import Log

PROMPT = (Path(__file__).parent / "prompty" / "rozmowa.md").read_text(encoding="utf-8")

SCHEMA = {
    "type": "object",
    "properties": {
        "pytanie": {"type": "string"},
        "opcje": {"type": "array", "items": {"type": "string"}},
        "koniec": {"type": "boolean"},
        "tytul": {"type": "string"},
        "streszczenie": {"type": "string"},
    },
    "required": ["pytanie", "opcje", "koniec", "tytul", "streszczenie"],
    "additionalProperties": False,
}

# Limits: the question with options and the summary must fit the game screen
# (engine/screen.py, 10 lines of 55 characters)
QUESTION_LINES = 4
OPTION_CHARS = 45
TITLE_CHARS = 40
SUMMARY_LINES = 8
ATTEMPTS = 3  # AI answers per step: the first and up to 2 corrections

# What the code says to the AI (kreator/prompty/rozmowa.md -> "Wiadomości od systemu")
START = "Zacznij rozmowę."
CHOICE = "Wybór: "
OTHER_OPTIONS = "Inne propozycje"
OTHER_IDEA = "Inny pomysł"

# Buttons added by the code
INNE_PROPOZYCJE = "Inne propozycje"
ROZPOCZNIJ = "Rozpocznij"
INNY_POMYSL = "Inny pomysł"
# Fixed texts of the conversation board in AP, read in the narrator's voice
INTERFACE = {
    "inne_propozycje": INNE_PROPOZYCJE,
    "rozpocznij": ROZPOCZNIJ,
    "inny_pomysl": INNY_POMYSL,
    "wroc": "Wróć",
    "przerwij": "Przerwij",
    "mysle": "Myślę...",
    "wybrales": "Wybrałeś:",  # potwierdzenie wyboru - jak w grze (engine/voice.py)
    "blad": "Coś poszło nie tak. Wróć albo przerwij.",
    # Making the game (kreator/tworzenie.py)
    "tworze": "Tworzę grę. To potrwa kilkanaście minut. Gotowa gra pojawi się jako nowy kafelek.",
    "w_trakcie": "Ta gra jeszcze się tworzy.",
    "nieudana": "Nie udało się stworzyć tej gry.",
}

# Statuses
MYSLI = "mysli"  # the AI is working; AP shows "Myślę..." and asks again
PYTANIE = "pytanie"
PODSUMOWANIE = "podsumowanie"
BLAD = "blad"  # the AI failed; WRÓĆ shows the last question again
PRZERWANA = "przerwana"
ZATWIERDZONA = "zatwierdzona"  # ROZPOCZNIJ - the game goes to be made


class ConversationError(Exception):
    """A request that does not fit the state (e.g. an answer while the AI is
    working) - a client error, the conversation is unchanged."""


def problems(answer: dict) -> list[str]:
    """What breaks the rules in a (schema-valid) AI answer; [] = fine."""
    found = []
    if answer["koniec"]:
        if not 1 <= len(answer["tytul"].strip()) <= TITLE_CHARS:
            found.append(f"tytuł musi mieć od 1 do {TITLE_CHARS} znaków")
        if not answer["streszczenie"].strip():
            found.append("brak streszczenia")
        elif text_lines(answer["streszczenie"]) > SUMMARY_LINES:
            found.append("streszczenie za długie - skróć je")
        if answer["opcje"]:
            found.append("przy końcu opcje mają być puste")
        return found
    if not answer["pytanie"].strip():
        found.append("brak pytania")
    elif text_lines(answer["pytanie"]) > QUESTION_LINES:
        found.append("pytanie za długie - najwyżej dwa krótkie zdania")
    options = [o.strip() for o in answer["opcje"]]
    if not 2 <= len(options) <= 3:
        found.append("podaj 2 albo 3 odpowiedzi do wyboru")
    for option in options:
        if not 1 <= len(option) <= OPTION_CHARS:
            found.append(f"odpowiedź {option!r} musi mieć od 1 do {OPTION_CHARS} znaków")
    if len({o.lower() for o in options}) != len(options):
        found.append("odpowiedzi się powtarzają")
    return found


def _thread(work: Callable[[], None]) -> None:
    threading.Thread(target=work, daemon=True).start()


class Conversation:
    def __init__(self, directory: Path, ai: AI, narrator=None, audio_url: str = "",
                 run: Callable[[Callable[[], None]], None] = _thread):
        self.id = directory.name
        self.directory = directory
        self.log = Log(directory / "log.jsonl")
        self.ai = ai
        self.narrator = narrator  # tools.nagraj.Narrator or None (no recordings)
        self.audio_url = audio_url.rstrip("/")
        self._run = run
        self._lock = threading.RLock()
        self.steps: list[dict] = []  # {"ai": answer, "wybor": message to the AI or None}
        self.status = MYSLI
        self._generation = 0  # bumped by WRÓĆ / PRZERWIJ - older AI answers are dropped

    # --- the AI in the background ---------------------------------------

    def _messages(self) -> list[dict]:
        messages = [{"role": "user", "content": START}]
        for step in self.steps:
            messages.append({"role": "assistant", "content": json.dumps(step["ai"], ensure_ascii=False)})
            if step["wybor"]:
                messages.append({"role": "user", "content": step["wybor"]})
        return messages

    def _ask(self) -> None:
        """Start the AI on the current conversation (called under the lock)."""
        self.status = MYSLI
        self._save()
        generation, messages = self._generation, self._messages()
        self._run(lambda: self._work(generation, messages))

    def _work(self, generation: int, messages: list[dict]) -> None:
        try:
            answer = None
            for attempt in range(1, ATTEMPTS + 1):
                answer = self.ai.ask(self.log, "rozmowa", PROMPT, messages, SCHEMA)
                found = problems(answer)
                if not found:
                    break
                self.log.write("odpowiedz_ai_odrzucona", proba=attempt, problemy=found)
                messages = messages + [
                    {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)},
                    {"role": "user", "content": "Popraw: " + "; ".join(found)}]
            else:
                raise AIError(f"odpowiedź AI łamie zasady po {ATTEMPTS} próbach")
            answer = {**answer, "opcje": [o.strip() for o in answer["opcje"]]}
            self._record(answer)
        except AIError as error:
            with self._lock:
                if generation == self._generation:
                    self.status = BLAD
                    self.log.write("blad", blad=str(error))
                    self._save()
            return
        with self._lock:
            if generation != self._generation:
                self.log.write("odpowiedz_ai_pominieta", powod="użytkownik wrócił albo przerwał")
                return
            self.steps.append({"ai": answer, "wybor": None})
            self.status = PODSUMOWANIE if answer["koniec"] else PYTANIE
            self.log.write("pokazane", status=self.status, tekst=self._text(), opcje=self._options())
            self._save()

    def _record(self, answer: dict) -> None:
        """Recordings of the new texts before AP shows them; a failure only
        means no recording (AP reads with its own voice then)."""
        if not self.narrator:
            return
        texts = ([_summary_text(answer)] if answer["koniec"] else [answer["pytanie"], *answer["opcje"]])
        for text in texts + list(INTERFACE.values()):
            try:
                self.narrator.recording(text)
            except Exception as error:  # noqa: BLE001
                self.log.write("blad_nagrania", tekst=text, blad=f"{type(error).__name__}: {error}")

    # --- what AP does -----------------------------------------------------

    def start(self) -> None:
        with self._lock:
            self.log.write("start")
            self._ask()

    def answer(self, number: int) -> None:
        with self._lock:
            options = self._options()
            if self.status not in (PYTANIE, PODSUMOWANIE):
                raise ConversationError(f"Teraz nie można odpowiadać (stan: {self.status}).")
            if not 1 <= number <= len(options):
                raise ConversationError(f"Nie ma opcji {number}.")
            chosen = options[number - 1]
            self.log.write("odpowiedz_uzytkownika", numer=number, tekst=chosen)
            step = self.steps[-1]
            if self.status == PODSUMOWANIE and chosen == ROZPOCZNIJ:
                self.status = ZATWIERDZONA
                self._save()
                return
            if self.status == PODSUMOWANIE:
                step["wybor"] = OTHER_IDEA
            elif chosen == INNE_PROPOZYCJE:
                step["wybor"] = OTHER_OPTIONS
            else:
                step["wybor"] = CHOICE + chosen
            self._ask()

    def back(self) -> None:
        """WRÓĆ: the question before the current one (or, while the AI works
        or after its failure, the question just answered) - without the AI."""
        with self._lock:
            if not self.can_go_back():
                raise ConversationError("Nie ma do czego wrócić.")
            self._generation += 1
            if self.status in (PYTANIE, PODSUMOWANIE):
                self.steps.pop()
            self.steps[-1]["wybor"] = None
            self.status = PODSUMOWANIE if self.steps[-1]["ai"]["koniec"] else PYTANIE
            self.log.write("wroc", status=self.status, tekst=self._text(), opcje=self._options())
            self._save()

    def stop(self) -> None:
        with self._lock:
            if self.status in (PRZERWANA, ZATWIERDZONA):
                raise ConversationError(f"Rozmowa jest już zakończona (stan: {self.status}).")
            self._generation += 1
            self.status = PRZERWANA
            self.log.write("przerwij")
            self._save()

    def idea(self) -> dict:
        """The approved idea for making the game: title, summary and the
        questions with what the user chose."""
        with self._lock:
            if self.status != ZATWIERDZONA:
                raise ConversationError(f"Pomysł nie jest zatwierdzony (stan: {self.status}).")
            final = self.steps[-1]["ai"]
            return {"tytul": final["tytul"].strip(), "streszczenie": final["streszczenie"].strip(),
                    # Only real choices ("Inne propozycje" asked the same again)
                    "rozmowa": [{"pytanie": s["ai"]["pytanie"], "odpowiedz": s["wybor"][len(CHOICE):]}
                                for s in self.steps if (s["wybor"] or "").startswith(CHOICE)]}

    def can_go_back(self) -> bool:
        if self.status in (PYTANIE, PODSUMOWANIE):
            return len(self.steps) >= 2
        return self.status in (MYSLI, BLAD) and len(self.steps) >= 1

    # --- the view for AP --------------------------------------------------

    def _text(self) -> str:
        if self.status not in (PYTANIE, PODSUMOWANIE):
            return ""
        answer = self.steps[-1]["ai"]
        return _summary_text(answer) if answer["koniec"] else answer["pytanie"]

    def _options(self) -> list[str]:
        if self.status == PYTANIE:
            return [*self.steps[-1]["ai"]["opcje"], INNE_PROPOZYCJE]
        if self.status == PODSUMOWANIE:
            return [ROZPOCZNIJ, INNY_POMYSL]
        return []

    def audio(self, text: str) -> dict | None:
        return audio_of(self.narrator, text, self.audio_url)

    def view(self) -> dict:
        with self._lock:
            text = self._text()
            return {
                "id": self.id,
                "status": self.status,
                "tekst": text,
                "audio": self.audio(text),
                "opcje": [{"numer": n, "tekst": t, "audio": self.audio(t)}
                          for n, t in enumerate(self._options(), start=1)],
                "mozna_wrocic": self.can_go_back(),
                "pytanie_nr": sum(1 for s in self.steps if not s["ai"]["koniec"]),
                "tytul": self.steps[-1]["ai"]["tytul"] if self.status in (PODSUMOWANIE, ZATWIERDZONA) else "",
            }

    def _save(self) -> None:
        """A snapshot for people and for making the game (stage 4); the log
        stays the full history."""
        state = {"id": self.id, "status": self.status, "kroki": self.steps}
        partial = self.directory / "stan.json.part"
        partial.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        partial.replace(self.directory / "stan.json")


def audio_of(narrator, text: str, url_prefix: str) -> dict | None:
    """{"url", "duration"} of a recording already made, or None (never
    records - that is done before a question is shown)."""
    if not (narrator and text):
        return None
    path = narrator.cache / f"{voice.key(text)}.wav"
    if not path.exists():
        return None
    return {"url": f"{url_prefix.rstrip('/')}/{path.name}", "duration": round(voice.duration(path), 2)}


def _summary_text(answer: dict) -> str:
    return f"{answer['tytul'].strip()}\n\n{answer['streszczenie'].strip()}"


def new_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + token_hex(2)
