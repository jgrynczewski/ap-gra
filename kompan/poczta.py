"""Kompan's correspondence (docs/kompan.md -> Poczta przychodząca).

Every message to and from the people on the list, by person and topic: what
came by mail (read from Kompan's own Gmail by IMAP) and what Radek sent (stage
4). A topic is a mail thread - replies are found by the In-Reply-To and
References headers; a new mail from someone starts a new topic. Nothing is ever
deleted: "Nie odpowiadam" only takes a message off the waiting list.

Kompan is the user's mailbox, not a gate (decision 2026-11-15): every mail
in the inbox is taken, from anyone - also auto-replies ("I am on holiday" says
why there is no answer yet). Spam is kept out by Gmail itself: only INBOX is
read, never the Spam folder. A person from the list (osoby.json) is named by
the list only when Gmail confirmed the sender (DMARC, or DKIM / SPF of the
sender's own domain); anyone else by the name in the mail, and with the
address when that name is taken by someone on the list ("Mama
(obcy@example.com)"), so nobody can pass for a close person. No AI here:
reading works without it.

dane-kompan/poczta/<id>.json - one file per message.
"""

from __future__ import annotations

import email
import email.policy
import imaplib
import json
import re
import threading
from datetime import datetime, timezone
from email.utils import make_msgid, parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from secrets import token_hex
from typing import Callable

from engine.log import Log
from engine.screen import text_lines

IMAP_HOST, IMAP_PORT, IMAP_TIMEOUT = "imap.gmail.com", 993, 30
CHECK = 60  # [s] how often the mailbox is checked
PART_LINES = 8  # screen lines of one part of a message (the header takes the rest)
TITLE_WORDS = 6  # a topic without a subject is named by the first words
TITLE_CHARS = 40

FROM, TO = "od", "do"  # direction: from a person to Radek, from Radek to a person
NEW, WAITING, CLOSED = "nowa", "czeka", "zamknieta"  # state of a received message

LINK = re.compile(r"https?://\S+|www\.\S+")
QUOTE_START = [
    re.compile(r"^W dniu .*(napisał|napisała|napisał\(a\)|pisze)\b.*:\s*$", re.I),
    re.compile(r"^On .* wrote:\s*$", re.I),
    re.compile(r"^-{2,}\s*(Original Message|Wiadomość oryginalna|Oryginalna wiadomość|Forwarded message|"
               r"Wiadomość przekazana dalej)\s*-{2,}\s*$", re.I),
    re.compile(r"^_{10,}\s*$"),  # Outlook puts a line before "Od: ..."
]
HEADER_BLOCK = re.compile(r"^(Od|From):\s")
HEADER_NEXT = re.compile(r"^(Wysłano|Wysłane|Sent|Data|Date|Do|To|Temat|Subject):\s", re.I)
SENT_FROM = re.compile(r"^(Wysłane z|Wysłano z|Sent from)\b.*$", re.I)
SUBJECT_PREFIX = re.compile(r"^\s*((re|odp|fw|fwd|pd|przekaż|aw|wg)\s*:\s*)+", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, data: dict) -> None:
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    partial.replace(path)


# --- reading a mail -------------------------------------------------------

class _Text(HTMLParser):
    """HTML to plain text: paragraphs and line breaks kept, scripts and styles dropped."""

    BREAKS = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.quote = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.skip += 1
        if tag == "blockquote" or (tag == "div" and ("class", "gmail_quote") in attrs):
            self.quote += 1  # quoted earlier messages
        if tag in self.BREAKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self.skip = max(0, self.skip - 1)
        if tag == "blockquote":
            self.quote = max(0, self.quote - 1)
        if tag in self.BREAKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip and not self.quote:
            self.parts.append(data)


def html_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    text = "".join(parser.parts)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line.strip() for line in text.splitlines()))


def strip_quotes(text: str) -> str:
    """Only what the person wrote now: without the quoted earlier messages,
    the signature and "Sent from my phone"."""
    lines = text.replace("\r\n", "\n").split("\n")
    kept = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        joined = " ".join(l.strip() for l in lines[i:i + 3])  # "W dniu ..." may wrap
        if any(p.match(stripped) for p in QUOTE_START) or (
                stripped.startswith(("W dniu ", "On ")) and re.search(r"(napisał\S*|wrote)\s*:", joined)):
            break
        if HEADER_BLOCK.match(stripped) and any(HEADER_NEXT.match(l.strip()) for l in lines[i + 1:i + 4]):
            break
        if stripped in ("--", "-- "):
            break
        if stripped.startswith(">") or SENT_FROM.match(stripped):
            continue
        kept.append(line.rstrip())
    text = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def readable(text: str) -> str:
    """What the narrator reads: links as "link"."""
    return LINK.sub("(link)", text)


def parts(text: str, lines: int = PART_LINES) -> list[str]:
    """The text in parts that fit the screen, cut at paragraphs, then
    sentences, then words."""
    def pieces(paragraph: str) -> list[str]:
        if text_lines(paragraph) <= lines:
            return [paragraph]
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        if len(sentences) == 1:
            words, out, current = paragraph.split(), [], ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if current and text_lines(candidate) > lines:
                    out.append(current)
                    current = word
                else:
                    current = candidate
            return out + ([current] if current else [])
        out = []
        for sentence in sentences:
            out.extend(pieces(sentence))
        return out

    result, current = [], ""
    for paragraph in [p.strip() for p in text.split("\n\n") if p.strip()]:
        for piece in pieces(paragraph):
            candidate = f"{current}\n\n{piece}" if current else piece
            if current and text_lines(candidate) > lines:
                result.append(current)
                current = piece
            else:
                current = candidate
    return result + ([current] if current else []) or [""]


def title_of(subject: str, text: str) -> str:
    """The topic's name: the subject without Re:/Fw:, or the first words."""
    subject = SUBJECT_PREFIX.sub("", subject or "").strip()
    if subject:
        return subject[:TITLE_CHARS].rstrip()
    words = readable(text).split()[:TITLE_WORDS]
    return " ".join(words)[:TITLE_CHARS].rstrip(" ,.;:") + ("..." if words else "")


def sender_confirmed(mail: email.message.Message, address: str) -> bool:
    """Whether Gmail confirmed the sender. Only Gmail's own header counts (the
    first Authentication-Results from mx.google.com - a sender can add fake
    ones below it): DMARC pass, or DKIM / SPF pass for the sender's domain."""
    domain = address.rpartition("@")[2].lower()
    for header in mail.get_all("Authentication-Results", []):
        header = str(header)
        if not header.strip().lower().startswith("mx.google.com"):
            continue
        lower = header.lower()
        if re.search(r"\bdmarc=pass\b", lower):
            return True
        for match in re.finditer(r"\bdkim=pass\b[^;]*?header\.(?:i|d)=@?([\w.-]+)", lower):
            if match.group(1).endswith(domain):
                return True
        for match in re.finditer(r"\bspf=pass\b[^;]*?smtp\.mailfrom=(?:[^@\s;]*@)?([\w.-]+)", lower):
            if match.group(1).endswith(domain):
                return True
        return False
    return False


def automatic(mail) -> bool:
    """Sent by a machine, not by the person: auto-replies (RFC 3834), bulk
    mail and newsletters. Taken like any mail; the header says it."""
    submitted = str(mail.get("Auto-Submitted", "")).strip().lower()
    precedence = str(mail.get("Precedence", "")).strip().lower()
    return ((bool(submitted) and submitted != "no")
            or precedence in ("bulk", "junk", "list", "auto_reply")
            or any(mail.get(h) is not None for h in ("X-Autoreply", "X-Autorespond", "List-Unsubscribe")))


def parse(raw: bytes) -> dict:
    """The parts of a mail that matter here."""
    mail = email.message_from_bytes(raw, policy=email.policy.default)
    name, address = parseaddr(str(mail.get("From", "")))
    body, html, attachments = None, None, []
    for part in mail.walk():
        if part.is_multipart():
            continue
        disposition = part.get_content_disposition()
        if disposition == "attachment" or (disposition == "inline" and part.get_filename()):
            attachments.append({"nazwa": part.get_filename() or "", "typ": part.get_content_type()})
            continue
        kind = part.get_content_type()
        if kind == "text/plain" and body is None:
            body = part.get_content()
        elif kind == "text/html" and html is None:
            html = part.get_content()
    text = strip_quotes(body) if body is not None else strip_quotes(html_text(html or ""))
    references = " ".join(str(mail.get(h, "")) for h in ("In-Reply-To", "References"))
    try:
        when = parsedate_to_datetime(str(mail["Date"])).astimezone(timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        when = _now()
    return {"adres": address.lower(), "nazwa": name, "temat_maila": str(mail.get("Subject", "")),
            "message_id": str(mail.get("Message-ID", "")).strip(),
            "odnosniki": re.findall(r"<[^>]+>", references), "czas": when, "tresc": text,
            "zalaczniki": attachments, "potwierdzony": sender_confirmed(mail, address),
            "automat": automatic(mail)}


def attachments_text(attachments: list[dict]) -> str:
    if not attachments:
        return ""
    photos = sum(a["typ"].startswith("image/") for a in attachments)
    others = len(attachments) - photos
    said = []
    if photos:
        said.append("1 zdjęcie" if photos == 1 else f"{photos} zdjęcia" if photos < 5 else f"{photos} zdjęć")
    if others:
        said.append("1 plik" if others == 1 else f"{others} pliki" if others < 5 else f"{others} plików")
    return f"Są załączniki: {' i '.join(said)}, których nie pokażę."


# --- the store -------------------------------------------------------------

class Correspondence:
    def __init__(self, data: Path, people, log: Log):
        self.dir = data / "poczta"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.people = people  # wiadomosci.People
        self.log = log  # dane-kompan/poczta.jsonl
        self._lock = threading.RLock()

    def _all(self) -> list[dict]:
        with self._lock:
            return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.dir.glob("*.json"))]

    def get(self, mid: str) -> dict | None:
        path = self.dir / f"{mid}.json"
        with self._lock:
            return json.loads(path.read_text(encoding="utf-8")) if re.fullmatch(r"[0-9a-z-]+", mid) \
                and path.is_file() else None

    def _store(self, message: dict) -> None:
        with self._lock:
            _write_json(self.dir / f"{message['id']}.json", message)

    def update(self, mid: str, **fields) -> dict:
        with self._lock:
            message = self.get(mid)
            message.update(fields)
            self._store(message)
            return message

    def _topic_of(self, references: list[str]) -> dict | None:
        known = {m["message_id"]: m for m in self._all() if m.get("message_id")}
        for reference in reversed(references):  # the closest first
            if reference in known:
                return known[reference]
        return None

    # --- adding --------------------------------------------------------------

    def sender(self, mail: dict) -> tuple[str, bool]:
        """(the name to show, whether it is a person from the list)."""
        person = self.people.by_address(mail["adres"])
        if person and mail["potwierdzony"]:
            return person["imie"], True
        name = mail["nazwa"].strip().strip('"').strip() or mail["adres"]
        if name.lower() in {n.lower() for n in self.people.all_names()}:
            name = f"{name} ({mail['adres']})"
        return name, False

    def receive(self, raw: bytes) -> dict | None:
        """A mail from the inbox - every one is taken; None only when it is
        already here."""
        mail = parse(raw)
        name, known = self.sender(mail)
        with self._lock:
            if mail["message_id"] and any(m.get("message_id") == mail["message_id"] for m in self._all()):
                return None  # already here
            parent = self._topic_of(mail["odnosniki"])
            message = {"id": f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S-%f}-{token_hex(2)}", "kierunek": FROM,
                       "osoba": name, "email": mail["adres"], "message_id": mail["message_id"],
                       "z_listy": known, "potwierdzony": mail["potwierdzony"], "automat": mail["automat"],
                       "temat_id": parent["temat_id"] if parent else mail["message_id"] or token_hex(8),
                       "temat": parent["temat"] if parent else title_of(mail["temat_maila"], mail["tresc"]),
                       "temat_maila": mail["temat_maila"], "tresc": mail["tresc"], "czas": _now(),
                       "zalaczniki": mail["zalaczniki"], "stan": NEW, "ogloszona": False, "w_rozmowie": False,
                       "czas_nadania": mail["czas"]}
            self._store(message)
        self.log.write("mail_przyjety", id=message["id"], osoba=name, adres=mail["adres"], z_listy=known,
                       potwierdzony=mail["potwierdzony"], automat=mail["automat"], temat=message["temat"])
        return message

    def sent(self, person: dict, title: str, text: str, message_id: str, subject: str,
             topic: dict | None = None) -> dict:
        """What Radek sent (stage 4), so the topic shows it ("Twoja wiadomość do: ...")."""
        message = {"id": f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S-%f}-{token_hex(2)}", "kierunek": TO,
                   "osoba": person["imie"], "email": person["email"], "message_id": message_id,
                   "temat_id": topic["temat_id"] if topic else message_id, "temat_maila": subject,
                   "temat": topic["temat"] if topic else title, "tresc": text, "czas": _now(),
                   "zalaczniki": [], "stan": CLOSED, "ogloszona": True, "w_rozmowie": True}
        self._store(message)
        return message

    # --- reading -------------------------------------------------------------

    def waiting(self) -> list[dict]:
        """Received, not answered and not closed - oldest first."""
        return [m for m in self._all() if m["kierunek"] == FROM and m["stan"] in (NEW, WAITING)]

    def new(self) -> list[dict]:
        return [m for m in self._all() if m["kierunek"] == FROM and m["stan"] == NEW]

    def people_list(self) -> list[dict]:
        """[{"osoba", "nowe", "ostatnia"}]: with new messages first, then by the last message."""
        by_person: dict[str, dict] = {}
        for message in self._all():
            entry = by_person.setdefault(message["osoba"], {"osoba": message["osoba"], "nowe": 0, "ostatnia": ""})
            entry["nowe"] += message["kierunek"] == FROM and message["stan"] in (NEW, WAITING)
            entry["ostatnia"] = max(entry["ostatnia"], message["czas"])
        return sorted(by_person.values(), key=lambda e: (e["nowe"] > 0, e["ostatnia"]), reverse=True)

    def topics(self, person: str) -> list[dict]:
        """[{"temat_id", "temat", "nowe", "ostatnia"}] of a person, the freshest first."""
        by_topic: dict[str, dict] = {}
        for message in self._all():
            if message["osoba"] != person:
                continue
            entry = by_topic.setdefault(message["temat_id"], {"temat_id": message["temat_id"],
                                                              "temat": message["temat"], "nowe": 0, "ostatnia": ""})
            entry["nowe"] += message["kierunek"] == FROM and message["stan"] in (NEW, WAITING)
            entry["ostatnia"] = max(entry["ostatnia"], message["czas"])
        return sorted(by_topic.values(), key=lambda e: e["ostatnia"], reverse=True)

    def topic(self, topic_id: str) -> list[dict]:
        """The messages of a topic, the newest first."""
        return sorted((m for m in self._all() if m["temat_id"] == topic_id), key=lambda m: m["id"], reverse=True)

    def last_from(self, topic_id: str) -> dict | None:
        """The newest message from the person in a topic (what a reply answers)."""
        return next((m for m in self.topic(topic_id) if m["kierunek"] == FROM), None)

    # --- announcements (AP's Notifier) ----------------------------------------

    def announcements(self, startup: bool) -> list[str]:
        """What AP should say outside Kompan: each new message once; at the
        start of AP also what still waits."""
        said = []
        for message in self.new():
            if not message["ogloszona"]:
                said.append(f"Masz nową wiadomość. Pisze {message['osoba']}. Przeczytasz ją w Kompanie.")
                self.update(message["id"], ogloszona=True)
        if startup and not said:
            names = sorted({m["osoba"] for m in self.waiting()})
            if names:
                said.append(f"W Kompanie czekają wiadomości od: {', '.join(names)}.")
        return said


# --- the mailbox ------------------------------------------------------------

class Inbox:
    """New mails in Kompan's Gmail inbox, by IMAP (the same app password as for sending)."""

    def __init__(self, user: str, password: str):
        self.user, self.password = user, password

    def __call__(self, handle: Callable[[bytes], None]) -> None:
        """handle(raw) for every unread mail; a mail is marked as read only
        after it was handled, so a failure leaves it for the next check."""
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=IMAP_TIMEOUT) as imap:
            imap.login(self.user, self.password)
            imap.select("INBOX")
            _, found = imap.search(None, "UNSEEN")
            for number in found[0].split():
                _, data = imap.fetch(number, "(BODY.PEEK[])")
                raw = next(item[1] for item in data if isinstance(item, tuple))
                handle(raw)
                imap.store(number, "+FLAGS", "\\Seen")


class Checker:
    """The service's background loop: every CHECK seconds the mailbox."""

    def __init__(self, fetch: Callable[[Callable[[bytes], None]], None], correspondence: Correspondence,
                 on_new: Callable[[dict], None] | None = None):
        self.fetch = fetch
        self.correspondence = correspondence
        self.on_new = on_new  # e.g. recordings of the new message

    def check(self) -> None:
        def handle(raw: bytes) -> None:
            message = self.correspondence.receive(raw)
            if message and self.on_new:
                self.on_new(message)

        try:
            self.fetch(handle)
        except Exception as error:  # noqa: BLE001 - no internet, wrong password, ...
            self.correspondence.log.write("poczta_blad", blad=f"{type(error).__name__}: {error}")

    def forever(self) -> None:
        stop = threading.Event()
        while True:
            self.check()
            stop.wait(CHECK)


def new_message_id(sender: str) -> str:
    return make_msgid(domain=sender.rpartition("@")[2] or "kompan.local")
