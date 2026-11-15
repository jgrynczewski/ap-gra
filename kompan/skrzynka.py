"""The screens of the correspondence (docs/kompan.md -> Poczta przychodząca).

Made by the code, without the AI, like the review of notes: AP only shows a
text and buttons and sends back the number of the chosen one.

- Reader: one message in parts that fit the screen; at the end the buttons
  for a new message (ODPOWIEDZ, PRZECZYTAJ JESZCZE RAZ, PÓŹNIEJ, NIE
  ODPOWIADAM) or for browsing (Wcześniejsza, ODPISZ Z KOMPANEM, ...).
- Mailbox: WIADOMOŚCI - the new ones one after another, or the list person ->
  topics -> messages. WRÓĆ goes one level up.
"""

from __future__ import annotations

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from .poczta import CLOSED, FROM, NEW, WAITING, Correspondence, attachments_text, parts, readable

ZONE = ZoneInfo("Europe/Warsaw")

NEXT = "Dalej"
REPLY, AGAIN, LATER, NO_REPLY = "Odpowiedz", "Przeczytaj jeszcze raz", "Później", "Nie odpowiadam"
EARLIER, WRITE, ENOUGH = "Wcześniejsza", "Odpisz z Kompanem", "Wystarczy"
MORE_PEOPLE, MORE_TOPICS = "Inne osoby", "Inne tematy"
PEOPLE_TEXT = "Wiadomości. Od kogo?"
TOPICS_TEXT = "Tematy: {}."
NOTHING = "Nie masz jeszcze żadnych wiadomości."
ALL_READ = "To wszystkie nowe wiadomości."
CLOSED_TEXT = "Dobrze. Gdybyś zmienił zdanie, znajdziesz ją w Wiadomościach, u: {}."
NEW_MARK = " (nowa)"
MAIL_BUTTON = "Wiadomości"
READ = "Przeczytaj"
MAX_OPTIONS = 4

# Fixed texts recorded at the start of the service (rozmowa.INTERFACE)
TEXTS = {"dalej_poczta": NEXT, "odpowiedz": REPLY, "jeszcze_raz": AGAIN, "pozniej": LATER,
         "nie_odpowiadam": NO_REPLY, "wczesniejsza": EARLIER, "odpisz": WRITE, "wystarczy_poczta": ENOUGH,
         "inne_tematy": MORE_TOPICS, "wiadomosci": PEOPLE_TEXT, "brak_wiadomosci": NOTHING,
         "wszystkie_przeczytane": ALL_READ, "przeczytaj": READ, "wiadomosci_przycisk": MAIL_BUTTON}

# Statuses of the mailbox view (AP)
POCZTA, KONIEC, ROZMOWA = "poczta", "koniec", "rozmowa"


def announcement(names: list[str], count: int) -> str:
    """At the entry of Kompan: "Masz nową wiadomość. Pisze Mama." """
    if count == 1:
        return f"Masz nową wiadomość. Pisze {names[0]}."
    if len(names) == 1:
        return f"Masz nowe wiadomości. Pisze {names[0]}."
    return f"Masz nowe wiadomości. Piszą: {', '.join(names)}."


def when(iso: str) -> str:
    """15.11, 18:40 - fixed (not "today"), so the recording stays valid."""
    return f"{datetime.fromisoformat(iso).astimezone(ZONE):%d.%m, %H:%M}"


def header(message: dict) -> str:
    if message["kierunek"] == FROM:
        machine = " To wiadomość automatyczna." if message.get("automat") else ""
        return f"Pisze {message['osoba']}, {when(message['czas'])}. Temat: {message['temat']}.{machine}"
    return f"Twoja wiadomość do: {message['osoba']}, {when(message['czas'])}. Temat: {message['temat']}."


def pages(message: dict) -> list[str]:
    """The texts of all the screens of a message."""
    pieces = parts(readable(message["tresc"]))
    count = len(pieces)
    texts = []
    for i, piece in enumerate(pieces):
        text = piece
        if i == 0:
            first = header(message) + (f" To dłuższa wiadomość, {count} części." if count > 1 else "")
            text = f"{first}\n\n{piece}" if piece else first
        if i == count - 1 and message.get("zalaczniki"):
            text += "\n\n" + attachments_text(message["zalaczniki"])
        texts.append(text)
    return texts


def page_of(items: list[str], page: int, last: list[str], more: str) -> list[str]:
    """Options with paging: everything if it fits, else 2 per page + "more"."""
    room = MAX_OPTIONS - len(last)
    if len(items) <= room:
        return items + last
    per = room - 1
    count = -(-len(items) // per)
    start = page % count * per
    return items[start:start + per] + [more] + last


class Reader:
    """One message on screens. mode: "nowa" (a received message to deal
    with) or "lista" (browsing; earlier - an older message in the topic)."""

    def __init__(self, message: dict, mode: str, earlier: bool = False):
        self.message = message
        self.mode = mode
        self.earlier = earlier
        self.part = 0

    def screen(self) -> tuple[str, list[str]]:
        texts = pages(self.message)
        text = texts[self.part]
        if self.part < len(texts) - 1:
            return text, [NEXT]
        if self.mode == "nowa":
            return text, [REPLY, AGAIN, LATER, NO_REPLY]
        return text, ([EARLIER] if self.earlier else []) + [WRITE, AGAIN, ENOUGH]

    def choose(self, chosen: str) -> str | None:
        """Handles Dalej and Przeczytaj jeszcze raz; other choices are returned
        for the caller, None - nothing for the caller to do."""
        if chosen == NEXT:
            self.part += 1
            return None
        if chosen == AGAIN:
            self.part = 0
            return None
        return chosen


class Mailbox:
    """WIADOMOŚCI in AP. One at a time (one user); kept in memory - AP starts
    it again after a restart."""

    def __init__(self, correspondence: Correspondence, reply):
        self.correspondence = correspondence
        self.reply = reply  # reply(message) -> a new conversation answering it
        self._lock = threading.RLock()
        self.state: dict = {}
        self.reader: Reader | None = None
        self.result: dict = {}  # "koniec" / "rozmowa" - the mailbox is left

    # --- start ---------------------------------------------------------------

    def start(self, mode: str) -> dict:
        """mode "nowe": the waiting messages one after another; "lista": the people."""
        with self._lock:
            self.result = {}
            self.reader = None
            waiting = [m["id"] for m in self.correspondence.waiting()]
            if mode == "nowe" and waiting:
                self.state = {"ekran": "kolejka", "kolejka": waiting}
                self._open_queue()
            else:
                self.state = {"ekran": "osoby", "strona": 0}
                if not self.correspondence.people_list():
                    self.result = {"status": KONIEC, "tekst": NOTHING}
            return self.view()

    def later_all(self) -> None:
        """PÓŹNIEJ on the announcement at the entry: the new ones become waiting."""
        for message in self.correspondence.new():
            self.correspondence.update(message["id"], stan=WAITING)

    def _open_queue(self) -> None:
        queue = self.state["kolejka"]
        if not queue:
            self.result = {"status": KONIEC, "tekst": ALL_READ}
            return
        message = self.correspondence.get(queue[0])
        if message["stan"] == NEW:
            message = self.correspondence.update(message["id"], stan=WAITING, ogloszona=True, w_rozmowie=True)
        self.reader = Reader(message, "nowa")

    # --- screens -------------------------------------------------------------

    def _people(self) -> list[dict]:
        return self.correspondence.people_list()

    def _person_label(self, entry: dict) -> str:
        return entry["osoba"] + (NEW_MARK if entry["nowe"] else "")

    def _topic_label(self, entry: dict) -> str:
        return entry["temat"] + (NEW_MARK if entry["nowe"] else "")

    def _screen(self) -> tuple[str, list[str]]:
        screen = self.state["ekran"]
        if screen in ("kolejka", "wiadomosc"):
            return self.reader.screen()
        if screen == "info":
            return self.state["info"], [NEXT]
        if screen == "osoby":
            labels = [self._person_label(e) for e in self._people()]
            return PEOPLE_TEXT, page_of(labels, self.state["strona"], [ENOUGH], MORE_PEOPLE)
        labels = [self._topic_label(e) for e in self.correspondence.topics(self.state["osoba"])]
        return TOPICS_TEXT.format(self.state["osoba"]), page_of(labels, self.state["strona"], [ENOUGH],
                                                                 MORE_TOPICS)

    def texts(self) -> list[str]:
        """What may be shown now - for the recordings."""
        with self._lock:
            if self.result:
                return [self.result.get("tekst", "")]
            text, options = self._screen()
            return [text, *options]

    def view(self) -> dict:
        with self._lock:
            if self.result:
                return dict(self.result)
            text, options = self._screen()
            return {"status": POCZTA, "tekst": text, "opcje": options, "mozna_wrocic": self.can_go_back()}

    def can_go_back(self) -> bool:
        return self.state.get("ekran") in ("tematy", "wiadomosc")

    # --- choices -------------------------------------------------------------

    def answer(self, number: int) -> dict:
        with self._lock:
            if self.result:
                raise ValueError("Skrzynka jest zamknięta.")
            _, options = self._screen()
            if not 1 <= number <= len(options):
                raise ValueError(f"Nie ma opcji {number}.")
            chosen = options[number - 1]
            self.correspondence.log.write("poczta_wybor", ekran=self.state["ekran"], tekst=chosen)
            screen = self.state["ekran"]
            if chosen == ENOUGH:
                self.result = {"status": KONIEC, "tekst": ""}
            elif screen in ("kolejka", "wiadomosc"):
                self._message_choice(self.reader.choose(chosen))
            elif screen == "info":
                self.state["ekran"] = "kolejka"
                self._open_queue()
            elif chosen in (MORE_PEOPLE, MORE_TOPICS):
                self.state["strona"] += 1
            elif screen == "osoby":
                person = {self._person_label(e): e["osoba"] for e in self._people()}.get(chosen)
                if person:  # None - the list changed meanwhile (a new mail): show it again
                    self._open_person(person)
            else:  # a topic
                topic = {self._topic_label(e): e["temat_id"]
                         for e in self.correspondence.topics(self.state["osoba"])}.get(chosen)
                if topic:
                    self._open_topic(topic, 0)
            return self.view()

    def _open_person(self, person: str) -> None:
        topics = self.correspondence.topics(person)
        self.state.update(ekran="tematy", osoba=person, strona=0)
        if len(topics) == 1:  # one topic - straight to it
            self._open_topic(topics[0]["temat_id"], 0)

    def _open_topic(self, topic_id: str, index: int) -> None:
        messages = self.correspondence.topic(topic_id)
        message = messages[index]
        if message["kierunek"] == FROM and message["stan"] == NEW:
            message = self.correspondence.update(message["id"], stan=WAITING, ogloszona=True, w_rozmowie=True)
        self.state.update(ekran="wiadomosc", temat_id=topic_id, i=index)
        self.reader = Reader(message, "lista", earlier=index < len(messages) - 1)

    def _message_choice(self, chosen: str | None) -> None:
        if chosen is None:
            return
        message = self.reader.message
        if chosen == EARLIER:
            self._open_topic(self.state["temat_id"], self.state["i"] + 1)
        elif chosen in (REPLY, WRITE):
            conversation = self.reply(message)
            self.result = {"status": ROZMOWA, "rozmowa": conversation.id}
        elif chosen in (LATER, NO_REPLY):
            if chosen == NO_REPLY:
                self.correspondence.update(message["id"], stan=CLOSED)
                self.correspondence.log.write("nie_odpowiadam", id=message["id"])
            self.state["kolejka"] = self.state["kolejka"][1:]
            if chosen == NO_REPLY:
                self.state.update(ekran="info", info=CLOSED_TEXT.format(message["osoba"]))
            else:
                self._open_queue()

    def back(self) -> dict:
        """WRÓĆ: a message -> its topics (or the people, with one topic), topics -> people."""
        with self._lock:
            if not self.can_go_back():
                raise ValueError("Nie ma do czego wrócić.")
            if self.state["ekran"] == "wiadomosc" and len(self.correspondence.topics(self.state["osoba"])) > 1:
                self.state.update(ekran="tematy", strona=0)
            else:
                self.state.update(ekran="osoby", strona=0)
            self.reader = None
            return self.view()
