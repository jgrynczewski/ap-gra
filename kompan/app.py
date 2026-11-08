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

from .rozmowa import INTERFACE, RETURN_LABEL, ConversationError, Conversation, Kompan

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("AP_KOMPAN_DATA", ROOT / "dane-kompan"))
MODELS = Path(os.environ.get("AP_GRA_MODELS", ROOT / "models"))
MODEL = os.environ.get("AP_KOMPAN_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("AP_KOMPAN_EFFORT", "medium")
LIMIT_USD = float(os.environ.get("AP_KOMPAN_LIMIT_USD", "5"))
AUDIO_URL = "/v1/kompan/audio"
RECORDING = re.compile(r"[0-9a-f]+\.wav")
CONVERSATION_ID = re.compile(r"[0-9a-z-]+")


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
    yield


app = FastAPI(title="ap-gra-kompan", lifespan=lifespan)
app.state.kompan = Kompan(DATA, AI(model=MODEL, effort=EFFORT), _narrator(), AUDIO_URL, LIMIT_USD)


class NotFound(Exception):
    pass


@app.exception_handler(ConversationError)
def conversation_error(request: Request, error: ConversationError) -> JSONResponse:
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
    return {"ok": True, "ai": configured(), "nagrania": narrator is not None,
            "interface": {name: {"text": text, "audio": audio_of(narrator, text, AUDIO_URL)}
                          for name, text in INTERFACE.items()},
            # What WRÓĆ DO ROZMOWY goes back to; null - the first visit
            "ostatnia": {"id": latest.id, "tytul": latest.title(), "etykieta": label,
                         "audio": audio_of(narrator, label, AUDIO_URL)} if latest else None}


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


@app.get("/v1/kompan/audio/{name}")
def audio(name: str) -> FileResponse:
    narrator = app.state.kompan.narrator
    path = narrator.cache / name if narrator else None
    if not (RECORDING.fullmatch(name) and path and path.is_file()):
        raise NotFound(f"Nie ma nagrania {name!r}.")
    return FileResponse(path, media_type="audio/wav")
