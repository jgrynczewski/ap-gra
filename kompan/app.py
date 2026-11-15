"""HTTP API of Kompan (docs/kompan.md, docs/api.md).

    uvicorn kompan.app:app --port 8768

The ap-gra-kompan service: its own key (.env.kompan) and its own data
(dane-kompan/), which no other service sees. Every request returns at once;
the AI works in the background and AP asks for the state of the conversation.
"""

from __future__ import annotations

import os
import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from kreator.ai import AI, configured
from kreator.rozmowa import audio_of

from .notatki import GUESS
from .rozmowa import INTERFACE, RETURN_LABEL, ConversationError, Conversation, Kompan
from .poczta import Inbox
from .skrzynka import MAIL_BUTTON, POCZTA, ROZMOWA, announcement
from .wiadomosci import Gmail

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("AP_KOMPAN_DATA", ROOT / "dane-kompan"))
MODELS = Path(os.environ.get("AP_GRA_MODELS", ROOT / "models"))
MODEL = os.environ.get("AP_KOMPAN_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("AP_KOMPAN_EFFORT", "medium")
LIMIT_USD = float(os.environ.get("AP_KOMPAN_LIMIT_USD", "5"))
# Kompan's own Gmail account and its app password (only in .env.kompan)
GMAIL = Gmail(os.environ.get("AP_KOMPAN_GMAIL", ""), os.environ.get("AP_KOMPAN_GMAIL_HASLO", ""))
INBOX = Inbox(GMAIL.user, GMAIL.password)  # the same account, read by IMAP (stage 5)
# The test instance (service ap-gra-kompan-test, docs/kompan.md -> Testy bez
# psucia danych): own data, key and costs; AP says it on the entry screen
TEST = os.environ.get("AP_KOMPAN_TEST", "") == "1"
if TEST:
    INTERFACE["kompan"] = "Kompan, wersja testowa"
AUDIO_URL = "/v1/kompan/audio"
RECORDING = re.compile(r"[0-9a-f]+\.wav")
CONVERSATION_ID = re.compile(r"[0-9a-z-]+")
NOTE_ID = re.compile(r"[0-9a-f]+")


def _narrator():
    """Piper in the image; without it - no recordings, AP reads with its own voice."""
    try:
        import piper  # noqa: F401

        from tools.nagraj import Narrator, model_path
    except ImportError:
        return None
    return Narrator(MODELS, DATA / "nagrania") if model_path(MODELS).exists() else None


def record_interface(narrator) -> None:
    for text in INTERFACE.values():
        try:
            narrator.recording(text)
        except Exception as error:  # noqa: BLE001 - AP reads with its own voice then
            print(f"kompan: nie nagrano {text!r}: {error}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    narrator = app.state.kompan.narrator
    if narrator is not None:
        threading.Thread(target=record_interface, args=(narrator,), daemon=True).start()
    # Messages that failed (no internet) are sent again every few minutes
    threading.Thread(target=app.state.kompan.outbox.retry_forever, daemon=True).start()
    # New mails: the mailbox every minute
    if app.state.kompan.checker:
        threading.Thread(target=app.state.kompan.checker.forever, daemon=True).start()
    yield


app = FastAPI(title="ap-gra-kompan", lifespan=lifespan)
app.state.kompan = Kompan(DATA, AI(model=MODEL, effort=EFFORT), _narrator(), AUDIO_URL, LIMIT_USD,
                          send=GMAIL if GMAIL.configured() else None,
                          fetch=INBOX if GMAIL.configured() else None)


class NotFound(Exception):
    pass


@app.exception_handler(ConversationError)
def conversation_error(request: Request, error: ConversationError) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=409)


@app.exception_handler(ValueError)
def mailbox_error(request: Request, error: ValueError) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=409)


@app.exception_handler(NotFound)
def not_found(request: Request, error: NotFound) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=404)


def _conversation(cid: str) -> Conversation:
    found = app.state.kompan.get(cid) if CONVERSATION_ID.fullmatch(cid) else None
    if found is None:
        raise NotFound(f"Nie ma rozmowy {cid!r}.")
    return found


class Answer(BaseModel):
    opcja: int  # number of the option, from 1


@app.get("/v1/kompan/health")
def health() -> dict:
    kompan = app.state.kompan
    narrator = kompan.narrator
    latest = kompan.latest()
    label = RETURN_LABEL + latest.title() if latest else ""
    return {"ok": True, "ai": configured(), "nagrania": narrator is not None, "test": TEST,
            "interface": {name: {"text": text, "audio": audio_of(narrator, text, AUDIO_URL)}
                          for name, text in INTERFACE.items()},
            # What WRÓĆ DO ROZMOWY goes back to; null - the first visit
            "ostatnia": {"id": latest.id, "tytul": latest.title(), "etykieta": label,
                         "audio": audio_of(narrator, label, AUDIO_URL)} if latest else None,
            "notatki": len(kompan.notes.entries()),
            # Messages (stage 4): mail account set, people from osoby.json, waiting to be sent
            "poczta": kompan.messages_on, "osoby": kompan.people.names(),
            "osoby_blad": kompan.people.problem(),
            "wiadomosci_czekaja": len(kompan.outbox.waiting()),
            # Incoming (stage 5): who wrote new ones (the announcement at the entry), how
            # many wait for an answer (WIADOMOŚCI (n)), whether there is any correspondence
            "poczta_nowe": list(dict.fromkeys(m["osoba"] for m in kompan.correspondence.new())),
            "poczta_czeka": len(kompan.correspondence.waiting()),
            "poczta_jest": bool(kompan.correspondence.people_list()),
            # Ready texts with recordings: the announcement at the entry and the WIADOMOŚCI button
            **_mail_entry(kompan)}


def _mail_entry(kompan) -> dict:
    new = kompan.correspondence.new()
    names = list(dict.fromkeys(m["osoba"] for m in new))
    waiting = len(kompan.correspondence.waiting())
    news = (announcement(names, len(new)) if names else "")
    button = ((f"{MAIL_BUTTON} ({waiting})" if waiting else MAIL_BUTTON)
              if kompan.correspondence.people_list() else "")
    kompan.record_texts([news, button])
    return {"poczta_ogloszenie": {"text": news, "audio": audio_of(kompan.narrator, news, AUDIO_URL)} if news else None,
            "poczta_przycisk": {"text": button, "audio": audio_of(kompan.narrator, button, AUDIO_URL)}
            if button else None}


def _notes() -> dict:
    """CO O MNIE WIESZ: the entries saved by the AI (not the start notes), oldest first."""
    kompan = app.state.kompan
    return {"wpisy": [{"id": e["id"], "tekst": e["tekst"],
                       "przypuszczenie": e["skad"] == GUESS and not e["potwierdzony"],
                       "audio": audio_of(kompan.narrator, e["tekst"], AUDIO_URL)}
                      for e in kompan.notes.entries()]}


@app.get("/v1/kompan/notatki")
def notes() -> dict:
    return _notes()


@app.post("/v1/kompan/notatki/{nid}/usun")
def remove_note(nid: str) -> dict:
    if not (NOTE_ID.fullmatch(nid) and app.state.kompan.notes.remove(nid)):
        raise NotFound(f"Nie ma wpisu {nid!r}.")
    return _notes()


@app.post("/v1/kompan/rozmowy")
def start() -> dict:
    return app.state.kompan.new().view()


@app.get("/v1/kompan/rozmowy/{cid}")
def state(cid: str) -> dict:
    return _conversation(cid).view()


@app.post("/v1/kompan/rozmowy/{cid}/odpowiedz")
def answer(cid: str, body: Answer) -> dict:
    conversation = _conversation(cid)
    conversation.answer(body.opcja)
    return conversation.view()


@app.post("/v1/kompan/rozmowy/{cid}/wroc")
def back(cid: str) -> dict:
    conversation = _conversation(cid)
    conversation.back()
    return conversation.view()


@app.post("/v1/kompan/rozmowy/{cid}/powrot")
def come_back(cid: str) -> dict:
    conversation = _conversation(cid)
    conversation.come_back()
    return conversation.view()


@app.post("/v1/kompan/rozmowy/{cid}/wyjscie")
def leave(cid: str) -> dict:
    conversation = _conversation(cid)
    conversation.leave()
    return conversation.view()


# --- WIADOMOŚCI (stage 5) ------------------------------------------------------

class MailboxStart(BaseModel):
    tryb: str = "nowe"  # "nowe": the waiting messages one after another; "lista": by person


class Startup(BaseModel):
    startup: bool = False


def _mailbox_view() -> dict:
    """Like a conversation's view (AP shows it the same way). After ODPOWIEDZ:
    the view of the new conversation; at the end: status "koniec"."""
    kompan = app.state.kompan
    mailbox = kompan.mailbox
    kompan.record_texts(mailbox.texts())  # short labels; a message's parts are recorded when it came
    view = mailbox.view()
    if view["status"] == ROZMOWA:
        return kompan.get(view["rozmowa"]).view()
    audio = lambda text: audio_of(kompan.narrator, text, AUDIO_URL)  # noqa: E731
    if view["status"] != POCZTA:
        return {**view, "audio": audio(view.get("tekst", ""))}
    return {"id": "poczta", "status": POCZTA, "tekst": view["tekst"], "audio": audio(view["tekst"]),
            "opcje": [{"numer": n, "tekst": t, "audio": audio(t)} for n, t in enumerate(view["opcje"], 1)],
            "stale": [], "mozna_wrocic": view["mozna_wrocic"], "tytul": ""}


@app.post("/v1/kompan/poczta/start")
def mailbox_start(body: MailboxStart) -> dict:
    app.state.kompan.mailbox.start("lista" if body.tryb == "lista" else "nowe")
    return _mailbox_view()


@app.post("/v1/kompan/poczta/odpowiedz")
def mailbox_answer(body: Answer) -> dict:
    app.state.kompan.mailbox.answer(body.opcja)
    return _mailbox_view()


@app.post("/v1/kompan/poczta/wroc")
def mailbox_back() -> dict:
    app.state.kompan.mailbox.back()
    return _mailbox_view()


@app.post("/v1/kompan/poczta/pozniej")
def mailbox_later() -> dict:
    """PÓŹNIEJ on the announcement at the entry."""
    app.state.kompan.mailbox.later_all()
    return {"ok": True}


@app.post("/v1/kompan/powiadomienia")
def announcements(body: Startup) -> dict:
    """For AP's Notifier (outside Kompan) - the same contract as Wicero's v1/notifications."""
    return {"say": app.state.kompan.correspondence.announcements(body.startup)}


@app.get("/v1/kompan/audio/{name}")
def audio(name: str) -> FileResponse:
    narrator = app.state.kompan.narrator
    path = narrator.cache / name if narrator else None
    if not (RECORDING.fullmatch(name) and path and path.is_file()):
        raise NotFound(f"Nie ma nagrania {name!r}.")
    return FileResponse(path, media_type="audio/wav")
