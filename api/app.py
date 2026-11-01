"""HTTP API of the game - a thin layer over engine.Game (docs/api.md).

    uvicorn api.app:app --port 8766

Stateless: the client keeps the state from the last view and sends it back
with the choice - nothing is stored on the server.
"""

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.game import Game, GameError
from engine.scenario import load
from engine.voice import Recordings

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = Path(os.environ.get("AP_GRA_SCENARIO", ROOT / "scenariusz" / "sala_pod_zegarem.md"))
# Narrator recordings (tools/nagraj.py, made in the Docker build); without
# them the game works, views just have "audio": null
AUDIO = Path(os.environ.get("AP_GRA_AUDIO", ROOT / "audio"))
AUDIO_URL = "/v1/audio"

recordings = Recordings(AUDIO, AUDIO_URL)
game = Game(load(SCENARIO), audio=recordings)

app = FastAPI(title="ap-gra", description=game.scenario.title)
# The future browser front may be served from another origin; no cookies -
# any origin is safe
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"],
                   allow_headers=["*"])
if AUDIO.is_dir():
    app.mount(AUDIO_URL, StaticFiles(directory=AUDIO), name="audio")


class Choice(BaseModel):
    state: dict  # "state" from the last view, unchanged
    option: int  # number of the visible option, from 1


@app.exception_handler(GameError)
def game_error(request: Request, error: GameError) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=400)


@app.get("/v1/health")
def health() -> dict:
    return {"ok": True, "title": game.scenario.title, "endings": len(game.scenario.endings),
            "recordings": len(recordings.durations)}


@app.post("/v1/start")
def start() -> dict:
    return game.start()


@app.post("/v1/choose")
def choose(choice: Choice) -> dict:
    return game.choose(choice.state, choice.option)
