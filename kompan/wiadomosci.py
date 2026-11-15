"""Messages from Kompan to people from a list (docs/kompan.md -> Wiadomości).

Only people from dane-kompan/osoby.json, only after the user chose Wyślij; the
AI cannot send anything, it only proposes a text. One file per recipient in
dane-kompan/wiadomosci/, so a failed send waits there and is retried. The
conversation hears about failures (and a late success) once, as a note in the
next message to the AI.

osoby.json (written by hand on the AP computer, never in the repo):

    {"uzytkownik": "Radek",
     "osoby": [{"imie": "Jurek", "kto": "brat", "email": "...",
                "wiadomosci": true,
                "opis": "Kim jest dla Radka i jak do niego pisać (nieobowiązkowe)."}]}

The description goes to the AI with the list of people (cached part of the
system prompt): it sets the tone of a message, never its content.
"""

from __future__ import annotations

import json
import smtplib
import threading
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from typing import Callable

from engine.log import Log

RETRY = 300  # [s] how often waiting messages are sent again
SMTP_HOST, SMTP_PORT, SMTP_TIMEOUT = "smtp.gmail.com", 465, 30

WAITING, SENT = "czeka", "wyslana"  # a message's state
# What the conversation was told about a message: nothing, its failure
TOLD_FAILURE = "blad"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, data: dict) -> None:
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    partial.replace(path)


class People:
    """dane-kompan/osoby.json, read on every use - a change needs no restart."""

    def __init__(self, data: Path):
        self.path = data / "osoby.json"

    def _load(self) -> dict:
        if not self.path.is_file():
            return {"uzytkownik": "", "osoby": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            people = [p for p in data.get("osoby", [])
                      if str(p.get("imie", "")).strip() and "@" in str(p.get("email", ""))]
            return {"uzytkownik": str(data.get("uzytkownik", "")).strip(), "osoby": people}
        except (ValueError, AttributeError, TypeError):
            return {"uzytkownik": "", "osoby": [], "blad": "osoby.json to nie poprawny JSON"}

    def problem(self) -> str:
        return self._load().get("blad", "")

    def user(self) -> str:
        return self._load()["uzytkownik"]

    def for_messages(self) -> list[dict]:
        return [p for p in self._load()["osoby"] if p.get("wiadomosci")]

    def names(self) -> list[str]:
        return [p["imie"] for p in self.for_messages()]

    def find(self, name: str) -> dict | None:
        return next((p for p in self.for_messages() if p["imie"] == name), None)

    def all_names(self) -> list[str]:
        return [p["imie"] for p in self._load()["osoby"]]

    def by_address(self, address: str) -> dict | None:
        """The person on the list with this address."""
        address = address.strip().lower()
        return next((p for p in self._load()["osoby"]
                     if str(p["email"]).strip().lower() == address), None)

    def for_ai(self) -> str:
        people = self.for_messages()
        if not people:
            return "Lista jest pusta: nie proponuj przekazania (pole przekaz zostaw puste)."
        lines = []
        for p in people:
            lines.append(f"- {p['imie']}" + (f" ({p['kto']})" if p.get("kto") else ""))
            if str(p.get("opis", "")).strip():
                lines.append(f"  Opis: {str(p['opis']).strip()}")
        return "\n".join(lines)


# Under every message, as ordinary text (no "-- " signature line, which mail
# programs often grey out): the words come from the AI, so they may be off.
# Short, neutral grammatically - the same for every user. Replying is normal,
# so nothing about it.
AI_NOTE = "Ta wiadomość powstała z pomocą Kompana, asystenta AI. W sformułowaniach mogą zdarzyć się nieścisłości."


def mail_text(user: str, text: str, title: str = "", reply_subject: str = "") -> tuple[str, str]:
    """(subject, body). The text (with its greeting) is in the first person,
    as the user's own message, signed with the name; under it - that the AI
    helped write it.
    A reply keeps the subject of the topic ("Re: ..."), so it stays in the
    same thread for the person too."""
    if reply_subject:
        subject = reply_subject if reply_subject.lower().startswith("re:") else f"Re: {reply_subject}"
    else:
        subject = title or f"Wiadomość od: {user}"
    body = (f"{text}\n\n"
            f"{user}\n\n\n"
            f"{AI_NOTE}\n")
    return subject, body


def sender_name(user: str) -> str:
    """The name the person sees as the sender."""
    return f"{user} (przez Kompana)" if user else "Kompan"


class Gmail:
    """Sends through the separate Gmail account of Kompan (app password in .env.kompan)."""

    def __init__(self, user: str, password: str):
        self.user, self.password = user, password

    def configured(self) -> bool:
        return bool(self.user and self.password)

    def __call__(self, to: str, subject: str, body: str, headers: dict | None = None) -> None:
        headers = dict(headers or {})
        # "Od" - the name shown as the sender; the address is always Kompan's
        name = headers.pop("Od", "")
        mail = EmailMessage()
        mail["From"] = formataddr((name, self.user)) if name else self.user
        mail["To"], mail["Subject"] = to, subject
        for header, value in headers.items():  # Message-ID, In-Reply-To, References
            mail[header] = value
        mail.set_content(body)
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as smtp:
            smtp.login(self.user, self.password)
            smtp.send_message(mail)


class Outbox:
    """dane-kompan/wiadomosci/<id>.json, one per recipient."""

    def __init__(self, data: Path, send: Callable[..., None], log: Log,
                 run: Callable[[Callable[[], None]], None] | None = None, sender: str = ""):
        self.sender = sender  # Kompan's address - the domain of the Message-IDs
        self.dir = data / "wiadomosci"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.send = send
        self.log = log  # dane-kompan/wiadomosci.jsonl - every attempt
        self.run = run or (lambda work: threading.Thread(target=work, daemon=True).start())
        self._sending = threading.Lock()  # one sending at a time (may take long without internet)
        self._files = threading.Lock()  # short: reading and changing the files

    def _all(self) -> list[dict]:
        with self._files:
            return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.dir.glob("*.json"))]

    def _update(self, mid: str, **fields) -> None:
        """Change some fields of a message as it is now on the disk (the
        sending and the conversation change different fields)."""
        with self._files:
            path = self.dir / f"{mid}.json"
            message = json.loads(path.read_text(encoding="utf-8"))
            message.update(fields)
            _write_json(path, message)

    def _store(self, message: dict) -> None:
        with self._files:
            _write_json(self.dir / f"{message['id']}.json", message)

    def add(self, user: str, people: list[dict], text: str, conversation: str, title: str = "",
            reply: dict | None = None) -> list[dict]:
        """reply: {"temat_maila", "message_id", "odnosniki"} of the message answered."""
        added = []
        for n, person in enumerate(people):
            subject, body = mail_text(user, text, title, (reply or {}).get("temat_maila", ""))
            message_id = make_msgid(domain=self.sender.rpartition("@")[2] or "kompan.local")
            headers = {"Od": sender_name(user), "Message-ID": message_id}
            if reply and reply.get("message_id"):
                headers["In-Reply-To"] = reply["message_id"]
                headers["References"] = " ".join([*reply.get("odnosniki", []), reply["message_id"]])
            message = {"id": f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S-%f}-{n}", "do": person["imie"],
                       "email": person["email"], "temat": subject, "tresc": body, "naglowki": headers,
                       "message_id": message_id, "stan": WAITING,
                       "proby": 0, "blad": "", "zgloszono": "", "rozmowa": conversation,
                       "utworzona": _now(), "wyslana": ""}
            self._store(message)
            added.append(message)
        self.run(self.send_waiting)
        return added

    def send_waiting(self) -> None:
        with self._sending:
            for message in self.waiting():
                try:
                    self.send(message["email"], message["temat"], message["tresc"], message.get("naglowki"))
                except Exception as error:  # noqa: BLE001 - no internet, wrong password, ...
                    error_text = f"{type(error).__name__}: {error}"
                    self._update(message["id"], proby=message["proby"] + 1, blad=error_text)
                    self.log.write("wysylka_blad", id=message["id"], do=message["do"], blad=error_text)
                else:
                    self._update(message["id"], proby=message["proby"] + 1, stan=SENT, wyslana=_now())
                    self.log.write("wyslana", id=message["id"], do=message["do"])

    def retry_forever(self) -> None:
        """The service's background loop."""
        stop = threading.Event()
        while not stop.wait(RETRY):
            self.send_waiting()

    def waiting(self) -> list[dict]:
        return [m for m in self._all() if m["stan"] == WAITING]

    def news(self) -> str:
        """What the conversation should hear about sending since it last
        heard: failures once, and a late success of a failed one."""
        failed, late = [], []
        for message in self._all():
            if message["stan"] == WAITING and message["proby"] and not message["zgloszono"]:
                self._update(message["id"], zgloszono=TOLD_FAILURE)
                failed.append(message["do"])
            elif message["stan"] == SENT and message["zgloszono"] == TOLD_FAILURE:
                self._update(message["id"], zgloszono=SENT)
                late.append(message["do"])
        parts = []
        if failed:
            parts.append(f"(Nie udało się wysłać wiadomości do: {', '.join(failed)}. "
                         "Czeka i będzie wysłana, gdy się uda.)")
        if late:
            parts.append(f"(Wiadomość do: {', '.join(late)} w końcu została wysłana.)")
        return (" " + " ".join(parts)) if parts else ""
