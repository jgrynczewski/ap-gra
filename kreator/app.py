"""HTTP API of the game creator (docs/kreator-gier.md, docs/api.md).

    uvicorn kreator.app:app --port 8767

The ap-gra-kreator service: the only one with internet and the API key.
Every request returns at once (well within the 10 s of AP's gra_client); the
AI works in the background and AP asks for the conversation state.

Conversations live in dane/rozmowy/<id>/ (log.jsonl - the full history,
stan.json - the current state). The conversations of this run are kept in
memory; after a restart AP starts a new conversation (the old logs stay).

ROZPOCZNIJ hands the idea to the workshop (kreator/tworzenie.py): the game
is made in the background in dane/zadania/<id>/ (the same id) and appears
in dane/gry/ when ready. Unfinished games go on when the service starts.
"""

from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .ai import AI, configured
from .rozmowa import INTERFACE, ZATWIERDZONA, Conversation, ConversationError, audio_of, new_id
from .tworzenie import Workshop

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("AP_GRA_DATA", ROOT / "dane"))
CONVERSATIONS = DATA / "rozmowy"
RECORDINGS = DATA / "nagrania"  # cache of the narrator's recordings of questions
MODELS = Path(os.environ.get("AP_GRA_MODELS", ROOT / "models"))
AUDIO_URL = "/v1/kreator/audio"
RECORDING = re.compile(r"[0-9a-f]+\.wav")
GAME_TASK = re.compile(r"[0-9a-z-]+")  # id of a conversation (rozmowa.new_id) - no paths


def _narrator():
    """Piper in the image (stage 2); without it - no recordings, AP reads
    with its own voice."""
    try:
        import piper  # noqa: F401

        from tools.nagraj import Narrator, model_path
    except ImportError:
        return None
    return Narrator(MODELS, RECORDINGS) if model_path(MODELS).exists() else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.workshop.resume()
    yield


app = FastAPI(title="ap-gra-kreator", lifespan=lifespan)
app.state.ai = AI()
app.state.narrator = _narrator()
app.state.run = None  # tests: run the AI work synchronously
app.state.workshop = Workshop(DATA, app.state.ai, app.state.narrator)
conversations: dict[str, Conversation] = {}


class NotFound(Exception):
    pass


@app.exception_handler(ConversationError)
def conversation_error(request: Request, error: ConversationError) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=409)


@app.exception_handler(NotFound)
def not_found(request: Request, error: NotFound) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=404)


def _conversation(cid: str) -> Conversation:
    found = conversations.get(cid)
    if found is None:
        raise NotFound(f"Nie ma rozmowy {cid!r}.")
    return found


class Answer(BaseModel):
    opcja: int  # number of the option, from 1


@app.get("/v1/kreator/health")
def health() -> dict:
    narrator = app.state.narrator
    return {"ok": True, "ai": configured(), "nagrania": narrator is not None,
            # Buttons of the conversation board, read in the narrator's voice
            # (recorded with the first question)
            "interface": {name: {"text": text, "audio": audio_of(narrator, text, AUDIO_URL)}
                          for name, text in INTERFACE.items()}}


@app.post("/v1/kreator/rozmowy")
def start() -> dict:
    kwargs = {"run": app.state.run} if app.state.run else {}
    conversation = Conversation(CONVERSATIONS / new_id(), app.state.ai, app.state.narrator,
                                AUDIO_URL, **kwargs)
    conversations[conversation.id] = conversation
    conversation.start()
    return conversation.view()


@app.get("/v1/kreator/rozmowy/{cid}")
def state(cid: str) -> dict:
    return _conversation(cid).view()


@app.post("/v1/kreator/rozmowy/{cid}/odpowiedz")
def answer(cid: str, body: Answer) -> dict:
    conversation = _conversation(cid)
    conversation.answer(body.opcja)
    if conversation.status == ZATWIERDZONA:
        app.state.workshop.add(conversation.id, conversation.idea())
    return conversation.view()


@app.post("/v1/kreator/rozmowy/{cid}/wroc")
def back(cid: str) -> dict:
    conversation = _conversation(cid)
    conversation.back()
    return conversation.view()


@app.post("/v1/kreator/rozmowy/{cid}/przerwij")
def stop(cid: str) -> dict:
    conversation = _conversation(cid)
    conversation.stop()
    return conversation.view()


@app.get("/v1/kreator/gry")
def games_being_made() -> dict:
    """Games made by the creator: in progress, ready and failed."""
    return {"gry": app.state.workshop.views()}


@app.get("/v1/kreator/gry/{cid}")
def game_being_made(cid: str) -> dict:
    task = app.state.workshop.get(cid) if GAME_TASK.fullmatch(cid) else None
    if task is None:
        raise NotFound(f"Nie ma tworzonej gry {cid!r}.")
    return task.view()


@app.get("/v1/kreator/audio/{name}")
def audio(name: str) -> FileResponse:
    narrator = app.state.narrator
    path = narrator.cache / name if narrator else None
    if not (RECORDING.fullmatch(name) and path and path.is_file()):
        raise NotFound(f"Nie ma nagrania {name!r}.")
    return FileResponse(path, media_type="audio/wav")
