"""Conversations with Kompan (docs/kompan.md).

Like the creator's conversation (kreator/rozmowa.py): the AI says something
and gives 2-4 answers, the code adds the fixed buttons; AP never waits for the
AI (status "mysli", AP asks every second); WRÓĆ never asks the AI; the log has
everything: every question, all the options, the chosen answer.

What is different: there is no end. ZAKOŃCZ only means "I am leaving for now",
the conversation is on the disk and WRÓĆ DO ROZMOWY goes on with it even the
next day, after a restart too. So that a long conversation does not get more
and more expensive, the AI gets the notes, a summary of what came before and
only the recent exchanges; older ones are folded into the summary.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from engine.log import Log
from engine.screen import text_lines
from kreator.ai import AI, AIError
from kreator.rozmowa import audio_of, new_id

from .koszty import Costs
from .notatki import GUESS, MAX_NEW, NOTE_CHARS, REVIEW_MAX, USER, Notes

PROMPT = (Path(__file__).parent / "prompty" / "rozmowa.md").read_text(encoding="utf-8")
SUMMARY_PROMPT = (Path(__file__).parent / "prompty" / "streszczenie.md").read_text(encoding="utf-8")

SCHEMA = {
    "type": "object",
    "properties": {
        "wypowiedz": {"type": "string"},
        "opcje": {"type": "array", "items": {"type": "string"}},
        "tytul_rozmowy": {"type": "string"},
        # New entries of the notes (docs/kompan.md -> Pamięć); usually none
        "zapamietaj": {"type": "array", "items": {
            "type": "object",
            "properties": {"tekst": {"type": "string"}, "skad": {"type": "string", "enum": [USER, GUESS]}},
            "required": ["tekst", "skad"],
            "additionalProperties": False}},
        # A good moment to show the review of new entries
        "pora_na_przeglad": {"type": "boolean"},
    },
    "required": ["wypowiedz", "opcje", "tytul_rozmowy", "zapamietaj", "pora_na_przeglad"],
    "additionalProperties": False,
}
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"streszczenie": {"type": "string"}},
    "required": ["streszczenie"],
    "additionalProperties": False,
}

# Limits: the text with up to 4 options must fit the screen (engine/screen.py)
TEXT_LINES = 7
OPTION_CHARS = 60
TITLE_CHARS = 60
SUMMARY_CHARS = 4000  # the prompt asks for 2000; much more than that is a bad answer
MIN_OPTIONS, MAX_OPTIONS = 2, 4
ATTEMPTS = 3  # AI answers per step: the first and up to 2 corrections

# Exchanges sent to the AI: fold when there are more than WINDOW_MAX, down to
# WINDOW_KEEP. In batches, so the beginning of the conversation stays the same
# between questions and the prompt cache works.
WINDOW_MAX = 30
WINDOW_KEEP = 20

# Fixed buttons added by the code; the AI gets the same words (prompt ->
# "Wiadomości od systemu")
BLISKO = "Blisko"
INNE_PROPOZYCJE = "Inne propozycje"
ZMIEN_TEMAT = "Zmień temat"
FIXED = [BLISKO, INNE_PROPOZYCJE, ZMIEN_TEMAT]
START = "Zacznij nową rozmowę."
CONTINUED = "Wcześniejsza część tej rozmowy jest w streszczeniu."
CHOICE = "Wybór: "
WAITING = " (Wpisów czekających na przegląd: {})"

# The review of new entries: screens made by the code, no AI
REVIEW_LIST = "Przy okazji, zapamiętałem:"
REVIEW_ASK = "Zgadza się?"
REVIEW_ONE = "Zapamiętałem: "
ALL_GOOD, SOMETHING_WRONG, NOT_NOW = "Wszystko dobrze", "Coś jest źle", "Nie teraz"
GOOD, WRONG, REST_GOOD = "Dobrze", "To nieprawda, usuń", "Reszta jest dobra"

RETURN_LABEL = "Wróć do rozmowy: "
# Fixed texts of the boards in AP, read in the narrator's voice
INTERFACE = {
    "co_o_mnie_wiesz": "Co o mnie wiesz",
    "dalej": "Dalej",
    "usun": WRONG,
    "wystarczy": "Wystarczy",
    "przypuszczenie": "To moje przypuszczenie.",
    "koniec_notatek": "To wszystko, co zapamiętałem.",
    "brak_notatek": "Jeszcze nic o Tobie nie zapamiętałem.",
    "usunalem": "Usunąłem.",
    "wszystko_dobrze": ALL_GOOD,
    "cos_jest_zle": SOMETHING_WRONG,
    "nie_teraz": NOT_NOW,
    "dobrze": GOOD,
    "reszta_dobra": REST_GOOD,
    "kompan": "Kompan",
    "wroc_do_rozmowy": "Wróć do rozmowy",
    "nowa_rozmowa": "Nowa rozmowa",
    "blisko": BLISKO,
    "inne_propozycje": INNE_PROPOZYCJE,
    "zmien_temat": ZMIEN_TEMAT,
    "wroc": "Wróć",
    "zakoncz": "Zakończ",
    "mysle": "Myślę...",
    "wybrales": "Wybrałeś:",
    "blad": "Coś poszło nie tak. Wróć albo zakończ.",
    "limit": "Na dziś muszę już kończyć. Wróćmy do tego jutro.",
}

# Statuses
MYSLI = "mysli"  # the AI is working; AP shows "Myślę..." and asks again
PYTANIE = "pytanie"
BLAD = "blad"  # the AI failed; WRÓĆ shows the last question, coming back tries again
LIMIT = "limit"  # the daily cost limit; coming back the next day tries again
PRZEGLAD = "przeglad"  # the review of new entries, before the AI's question

ZONE = ZoneInfo("Europe/Warsaw")
DAYS = ("poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela")


class ConversationError(Exception):
    """A request that does not fit the state - the conversation is unchanged."""


def stamp(now: datetime | None = None) -> str:
    """(czwartek 12.11.2026, 18:40) - Polish time, for the AI."""
    local = (now or datetime.now(timezone.utc)).astimezone(ZONE)
    return f"({DAYS[local.weekday()]} {local:%d.%m.%Y, %H:%M})"


def problems(answer: dict) -> list[str]:
    """What breaks the rules in a (schema-valid) AI answer; [] = fine."""
    found = []
    text = answer["wypowiedz"].strip()
    if not text:
        found.append("brak wypowiedzi")
    elif text_lines(text) > TEXT_LINES:
        found.append("wypowiedź za długa - najwyżej trzy krótkie zdania")
    if text.count("?") > 1:
        found.append("najwyżej jedno pytanie w wypowiedzi")
    options = [o.strip() for o in answer["opcje"]]
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        found.append(f"podaj od {MIN_OPTIONS} do {MAX_OPTIONS} odpowiedzi do wyboru")
    for option in options:
        if not 1 <= len(option) <= OPTION_CHARS:
            found.append(f"odpowiedź {option!r} musi mieć od 1 do {OPTION_CHARS} znaków")
        if option.lower() in {f.lower() for f in FIXED}:
            found.append(f"nie dodawaj odpowiedzi {option!r} - system dodaje ją sam")
    if len({o.lower() for o in options}) != len(options):
        found.append("odpowiedzi się powtarzają")
    if not 1 <= len(answer["tytul_rozmowy"].strip()) <= TITLE_CHARS:
        found.append(f"tytuł rozmowy musi mieć od 1 do {TITLE_CHARS} znaków")
    notes = answer.get("zapamietaj", [])
    if len(notes) > MAX_NEW:
        found.append(f"najwyżej {MAX_NEW} wpisy w polu zapamietaj")
    for note in notes:
        if not 1 <= len(note["tekst"].strip()) <= NOTE_CHARS:
            found.append(f"wpis {note['tekst']!r} musi mieć od 1 do {NOTE_CHARS} znaków")
    return found


def review_text(texts: list[str]) -> str:
    return "\n".join([REVIEW_LIST, *texts]) + "\n\n" + REVIEW_ASK


def review_texts(texts: list[str]) -> list[str]:
    """Everything a review of these entries can show - recorded before it is shown."""
    return [review_text(texts), *(REVIEW_ONE + text for text in texts)]


def _thread(work: Callable[[], None]) -> None:
    threading.Thread(target=work, daemon=True).start()


def _write_json(path: Path, data: dict) -> None:
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    partial.replace(path)


class Kompan:
    """What all the conversations share: notes, the summary, the AI, costs."""

    def __init__(self, data: Path, ai: AI, narrator=None, audio_url: str = "", limit: float = 5.0,
                 run: Callable[[Callable[[], None]], None] = _thread, costs: Costs | None = None):
        self.data = data
        self.ai = ai
        self.narrator = narrator  # tools.nagraj.Narrator or None (no recordings)
        self.audio_url = audio_url.rstrip("/")
        self.run = run
        self.costs = costs or Costs(data / "koszty.jsonl", limit)
        self.ai.on_usage = self.costs.add
        self.notes = Notes(data)
        self.conversations_dir = data / "rozmowy"
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self._conversations: dict[str, Conversation] = {}
        self._lock = threading.RLock()
        self._summary_lock = threading.Lock()  # one summary at a time; never held by a read of the state

    # --- what the AI knows ------------------------------------------------

    def start_notes(self) -> str:
        """Start notes, written once by hand from anything readable (docs/kompan.md)."""
        path = self.data / "notatki_startowe.txt"
        return path.read_text(encoding="utf-8").strip() if path.is_file() else ""

    def summary(self) -> str:
        path = self.data / "streszczenie.json"
        return json.loads(path.read_text(encoding="utf-8"))["tekst"] if path.is_file() else ""

    def system(self) -> list[dict]:
        start = self.start_notes()
        known = ("## Co wiesz o tej osobie\n\n"
                 + (f"Notatki startowe:\n{start}\n\n" if start else "")
                 + f"Twoje notatki (pole zapamietaj):\n{self.notes.for_ai()}\n\n"
                 f"## Streszczenie wcześniejszych rozmów\n\n{self.summary() or 'To Wasza pierwsza rozmowa.'}")
        # The cache ends here: the rules and what is known change rarely
        return [{"type": "text", "text": PROMPT},
                {"type": "text", "text": known, "cache_control": {"type": "ephemeral"}}]

    # --- conversations ----------------------------------------------------

    def get(self, cid: str) -> Conversation | None:
        with self._lock:
            found = self._conversations.get(cid)
            if found is None and (self.conversations_dir / cid / "stan.json").is_file():
                found = self._conversations[cid] = Conversation(self.conversations_dir / cid, self)
            return found

    def all(self) -> list[Conversation]:
        """Oldest first (the ids start with the time)."""
        paths = sorted(self.conversations_dir.glob("*/stan.json"))
        return [self.get(path.parent.name) for path in paths]

    def latest(self) -> Conversation | None:
        """The last conversation that has something to go back to."""
        for conversation in reversed(self.all()):
            if conversation.steps:
                return conversation
        return None

    def new(self) -> Conversation:
        with self._lock:
            conversation = Conversation(self.conversations_dir / new_id(), self)
            self._conversations[conversation.id] = conversation
            conversation.start()
            return conversation

    # --- the summary ------------------------------------------------------

    def fold_finished(self, current: Conversation) -> None:
        """Before a new conversation: what the old ones said goes to the summary."""
        for conversation in self.all():
            if conversation is not current:
                self.fold(conversation, conversation.answered())

    def fold(self, conversation: Conversation, upto: int) -> None:
        """Move the exchanges up to `upto` into the summary. A failure only
        means they stay in the conversation and it is tried again later."""
        with self._summary_lock:
            start = conversation.folded
            if upto <= start or self.costs.over_limit():
                return
            exchanges = "\n\n".join(conversation.exchange(step) for step in conversation.steps[start:upto])
            message = (f"Dotychczasowe streszczenie:\n{self.summary() or '(jeszcze puste)'}\n\n"
                       f"Nowy fragment rozmowy:\n{exchanges}")
            try:
                answer = self.ai.ask(conversation.log, "streszczenie", SUMMARY_PROMPT,
                                     [{"role": "user", "content": message}], SUMMARY_SCHEMA)
            except AIError:
                return  # the error is in the log
            text = answer["streszczenie"].strip()
            if not 1 <= len(text) <= SUMMARY_CHARS:
                conversation.log.write("streszczenie_odrzucone", znakow=len(text))
                return
            _write_json(self.data / "streszczenie.json", {
                "tekst": text, "czas": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            conversation.set_folded(upto)


class Conversation:
    def __init__(self, directory: Path, kompan: Kompan):
        self.id = directory.name
        self.directory = directory
        self.kompan = kompan
        self.log = Log(directory / "log.jsonl")
        self._lock = threading.RLock()
        self.steps: list[dict] = []  # {"ai": answer, "wybor": message to the AI or None}
        self.status = MYSLI
        self.opening = ""  # the first message to the AI
        self.folded = 0  # this many first steps are already in the summary
        # The review in progress: {"wpisy": [ids], "etap": "lista" | "wpis", "i": entry shown}
        self.review: dict | None = None
        self._generation = 0  # bumped by WRÓĆ - older AI answers are dropped
        self._working: int | None = None  # the generation an AI work runs for
        state = directory / "stan.json"
        if state.is_file():
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.steps, self.status = saved["kroki"], saved["status"]
            self.opening, self.folded = saved["otwarcie"], saved["streszczone"]
            self.review = saved.get("przeglad")

    # --- the AI in the background ---------------------------------------

    def _messages(self) -> list[dict]:
        first = CONTINUED if self.folded else self.opening
        messages = [{"role": "user", "content": first}]
        for step in self.steps[self.folded:]:
            messages.append({"role": "assistant", "content": json.dumps(step["ai"], ensure_ascii=False)})
            if step["wybor"]:
                messages.append({"role": "user", "content": step["wybor"]})
        # The cache ends at the last message, so the next question reads it all back
        last = messages[-1]
        messages[-1] = {"role": "user", "content": [
            {"type": "text", "text": last["content"], "cache_control": {"type": "ephemeral"}}]}
        return messages

    def _ask(self, before: Callable[[], None] | None = None) -> None:
        """Start the AI on the current conversation (called under the lock)."""
        self.status = MYSLI
        self._save()
        generation = self._working = self._generation
        self.kompan.run(lambda: self._work(generation, before))

    def _work(self, generation: int, before: Callable[[], None] | None) -> None:
        try:
            if before:
                before()
            if self.kompan.costs.over_limit():
                with self._lock:
                    if generation == self._generation:
                        self.status = LIMIT
                        self.log.write("limit_dzienny", usd=round(self.kompan.costs.today(), 4))
                        self._save()
                return
            with self._lock:
                if len(self.steps) - self.folded > WINDOW_MAX:
                    upto = len(self.steps) - WINDOW_KEEP
                else:
                    upto = 0
            if upto:
                self.kompan.fold(self, upto)
            answer = self._valid_answer()
            notes = self.kompan.notes
            new = notes.new_texts(answer["zapamietaj"])
            # What a review would show if it starts now (the oldest waiting entries)
            reviewed = ([e["tekst"] for e in notes.pending()] + new)[:REVIEW_MAX]
            self._record([answer["wypowiedz"], *answer["opcje"], RETURN_LABEL + answer["tytul_rozmowy"], *new,
                          *(review_texts(reviewed) if answer["pora_na_przeglad"] else [])])
        except AIError as error:
            with self._lock:
                if generation == self._generation:
                    self.status = BLAD
                    self.log.write("blad", blad=str(error))
                    self._save()
            return
        finally:
            with self._lock:
                if self._working == generation:
                    self._working = None
        with self._lock:
            if generation != self._generation:
                self.log.write("odpowiedz_ai_pominieta", powod="użytkownik wrócił")
                return
            self.steps.append({"ai": answer, "wybor": None})
            added = notes.add(answer["zapamietaj"], self.id)
            if added:
                self.log.write("zapamietane", wpisy=added)
            self.status = PYTANIE
            if answer["pora_na_przeglad"] and notes.review_due():
                entries = notes.pending()[:REVIEW_MAX]
                self.review = {"wpisy": [e["id"] for e in entries], "etap": "lista", "i": 0}
                self.status = PRZEGLAD
                self.log.write("przeglad_start", wpisy=entries)
            self._shown()
            self._save()

    def _valid_answer(self) -> dict:
        with self._lock:
            messages = self._messages()
        for attempt in range(1, ATTEMPTS + 1):
            answer = self.kompan.ai.ask(self.log, "rozmowa", self.kompan.system(), messages, SCHEMA)
            found = problems(answer)
            if not found:
                return {"wypowiedz": answer["wypowiedz"].strip(),
                        "opcje": [o.strip() for o in answer["opcje"]],
                        "tytul_rozmowy": answer["tytul_rozmowy"].strip(),
                        "zapamietaj": [{"tekst": n["tekst"].strip(), "skad": n["skad"]}
                                       for n in answer.get("zapamietaj", [])],
                        "pora_na_przeglad": bool(answer.get("pora_na_przeglad"))}
            self.log.write("odpowiedz_ai_odrzucona", proba=attempt, problemy=found)
            messages = messages + [
                {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)},
                {"role": "user", "content": "Popraw: " + "; ".join(found)}]
        raise AIError(f"odpowiedź AI łamie zasady po {ATTEMPTS} próbach")

    def _record(self, texts: list[str]) -> None:
        """Recordings of the new texts before AP shows them; a failure only
        means no recording (AP reads with its own voice then)."""
        narrator = self.kompan.narrator
        if not narrator:
            return
        for text in texts:
            try:
                narrator.recording(text)
            except Exception as error:  # noqa: BLE001
                self.log.write("blad_nagrania", tekst=text, blad=f"{type(error).__name__}: {error}")

    # --- what the summary needs -----------------------------------------

    def answered(self) -> int:
        """How many first steps have an answer."""
        with self._lock:
            count = 0
            for step in self.steps:
                if not step["wybor"]:
                    break
                count += 1
            return count

    def exchange(self, step: dict) -> str:
        answer = step["ai"]
        chosen = step["wybor"] or ""
        return (f"Kompan: {answer['wypowiedz']}\n"
                f"Do wyboru: {' | '.join(answer['opcje'])}\n"
                f"Odpowiedź: {chosen}")

    def set_folded(self, upto: int) -> None:
        with self._lock:
            self.folded = upto
            self.log.write("streszczone", do_kroku=upto)
            self._save()

    # --- what AP does -----------------------------------------------------

    def start(self) -> None:
        with self._lock:
            self.opening = f"{stamp()} {START}"
            self.log.write("start")
            self._ask(before=lambda: self.kompan.fold_finished(self))

    def answer(self, number: int) -> None:
        with self._lock:
            options = self._options()
            if self.status not in (PYTANIE, PRZEGLAD):
                raise ConversationError(f"Teraz nie można odpowiadać (stan: {self.status}).")
            if not 1 <= number <= len(options):
                raise ConversationError(f"Nie ma opcji {number}.")
            chosen = options[number - 1]
            self.log.write("odpowiedz_uzytkownika", numer=number, tekst=chosen)
            if self.status == PRZEGLAD:
                self._review_answer(chosen)
                return
            message = chosen if chosen in FIXED else CHOICE + chosen
            if self.kompan.notes.review_due():
                message += WAITING.format(len(self.kompan.notes.pending()))
            self.steps[-1]["wybor"] = f"{stamp()} {message}"
            self._ask()

    # --- the review of new entries (no AI) --------------------------------

    def _review_entries(self) -> list[dict]:
        return self.kompan.notes.get(self.review["wpisy"])

    def _review_screen(self) -> tuple[str, list[str]]:
        entries = self._review_entries()
        if self.review["etap"] == "lista":
            return review_text([e["tekst"] for e in entries]), [ALL_GOOD, SOMETHING_WRONG, NOT_NOW]
        i = self.review["i"]
        last = i == len(self.review["wpisy"]) - 1
        text = REVIEW_ONE + entries[i]["tekst"] if i < len(entries) else ""
        return text, [GOOD, WRONG] + ([] if last else [REST_GOOD])

    def _review_answer(self, chosen: str) -> None:
        notes = self.kompan.notes
        ids = self.review["wpisy"]
        i = self.review["i"]
        done = True
        if chosen == ALL_GOOD:
            notes.confirm(ids)
        elif chosen == NOT_NOW:
            notes.postpone()
        elif chosen == SOMETHING_WRONG:
            self.review["etap"] = "wpis"
            done = False
        elif chosen == REST_GOOD:
            notes.confirm(ids[i:])
        else:
            if chosen == GOOD:
                notes.confirm([ids[i]])
            else:  # WRONG
                removed = notes.remove(ids[i])
                self.log.write("wpis_usuniety", wpis=removed)
                ids = self.review["wpisy"] = ids[:i] + ids[i + 1:]
                i -= 1
            self.review["i"] = i + 1
            done = self.review["i"] >= len(ids)
        if done or not self._review_entries():
            self.review = None
            self.status = PYTANIE
            self.log.write("przeglad_koniec")
        self._shown()
        self._save()

    def _shown(self) -> None:
        self.log.write("pokazane", tekst=self._text(), opcje=self._options(), tytul=self.title())

    def back(self) -> None:
        """WRÓĆ: the question before the current one (or, while the AI works
        or after its failure, the question just answered) - without the AI."""
        with self._lock:
            if not self.can_go_back():
                raise ConversationError("Nie ma do czego wrócić.")
            self._generation += 1
            if self.status == PYTANIE:
                self.steps.pop()
            self.steps[-1]["wybor"] = None
            self.status = PYTANIE
            self.log.write("wroc", tekst=self._text(), opcje=self._options())
            self._save()

    def come_back(self) -> None:
        """WRÓĆ DO ROZMOWY. After a failure, the limit or a restart in the
        middle of the AI work - ask the AI again."""
        with self._lock:
            self.log.write("powrot", status=self.status)
            working = self._working == self._generation and self._working is not None
            if self.status in (BLAD, LIMIT) or (self.status == MYSLI and not working):
                self._ask()

    def leave(self) -> None:
        """ZAKOŃCZ: nothing ends, AI work in progress will wait for the return."""
        with self._lock:
            self.log.write("wyjscie", status=self.status)

    def can_go_back(self) -> bool:
        if self.status == PRZEGLAD:
            return False
        active = len(self.steps) - self.folded
        return active >= 2 if self.status == PYTANIE else active >= 1

    # --- the view for AP --------------------------------------------------

    def title(self) -> str:
        return self.steps[-1]["ai"]["tytul_rozmowy"] if self.steps else ""

    def _text(self) -> str:
        if self.status == PRZEGLAD:
            return self._review_screen()[0]
        return self.steps[-1]["ai"]["wypowiedz"] if self.status == PYTANIE else ""

    def _answers(self) -> list[str]:
        if self.status == PRZEGLAD:
            return self._review_screen()[1]
        return self.steps[-1]["ai"]["opcje"] if self.status == PYTANIE else []

    def _options(self) -> list[str]:
        return [*self._answers(), *(FIXED if self.status == PYTANIE else [])]

    def _audio(self, text: str) -> dict | None:
        return audio_of(self.kompan.narrator, text, self.kompan.audio_url)

    def _buttons(self, texts: list[str], first: int) -> list[dict]:
        return [{"numer": n, "tekst": t, "audio": self._audio(t)} for n, t in enumerate(texts, start=first)]

    def view(self) -> dict:
        with self._lock:
            text, answers = self._text(), self._answers()
            return {
                "id": self.id,
                "status": self.status,
                "tekst": text,
                "audio": self._audio(text),
                # The AI's answers (in a column in AP) and the fixed buttons
                # (in the row below); one numbering for /odpowiedz
                "opcje": self._buttons(answers, 1),
                "stale": self._buttons(FIXED if self.status == PYTANIE else [], len(answers) + 1),
                "mozna_wrocic": self.can_go_back(),
                "tytul": self.title(),
            }

    def _save(self) -> None:
        _write_json(self.directory / "stan.json", {
            "id": self.id, "status": self.status, "otwarcie": self.opening,
            "streszczone": self.folded, "przeglad": self.review, "kroki": self.steps})
