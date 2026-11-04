"""HTTP API of the games - a thin layer over engine.Game (docs/api.md).

    uvicorn api.app:app --port 8766

Every scenario in scenariusz/*.md is a game; its id is the file name
(sala_pod_zegarem, ostatnia_zwrotka). Routes take ?game=<id>; without it -
the default game (AP_GRA_DEFAULT), so older clients keep working.

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
from engine.voice import INTERFACE, Recordings

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = Path(os.environ.get("AP_GRA_SCENARIOS", ROOT / "scenariusz"))
DEFAULT_GAME = os.environ.get("AP_GRA_DEFAULT", "sala_pod_zegarem")
# Narrator recordings (tools/nagraj.py, made in the Docker build); without
# them the game works, views just have "audio": null
AUDIO = Path(os.environ.get("AP_GRA_AUDIO", ROOT / "audio"))
AUDIO_URL = "/v1/audio"

recordings = Recordings(AUDIO, AUDIO_URL)
GAMES = {path.stem: Game(load(path), audio=recordings) for path in sorted(SCENARIOS.glob("*.md"))}

app = FastAPI(title="ap-gra", description=", ".join(g.scenario.title for g in GAMES.values()))
# The future browser front may be served from another origin; no cookies -
# any origin is safe
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"],
                   allow_headers=["*"])
if AUDIO.is_dir():
    app.mount(AUDIO_URL, StaticFiles(directory=AUDIO), name="audio")


class UnknownGame(Exception):
    pass


def _game(game: str | None) -> Game:
    found = GAMES.get(game or DEFAULT_GAME)
    if found is None:
        raise UnknownGame(f"Nie ma gry {game!r}.")
    return found


class Choice(BaseModel):
    state: dict  # "state" from the last view, unchanged
    option: int  # number of the visible option, from 1


class Saved(BaseModel):
    state: dict  # "state" saved by the client


@app.exception_handler(GameError)
def game_error(request: Request, error: GameError) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=400)


@app.exception_handler(UnknownGame)
def unknown_game(request: Request, error: UnknownGame) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=404)


@app.get("/v1/games")
def games() -> dict:
    return {"default": DEFAULT_GAME,
            "games": [{"id": gid, "title": g.scenario.title, "endings": len(g.scenario.endings)}
                      for gid, g in GAMES.items()]}


@app.get("/v1/health")
def health(game: str | None = None) -> dict:
    g = _game(game)
    return {"ok": True, "game": game or DEFAULT_GAME, "title": g.scenario.title,
            "endings": len(g.scenario.endings), "recordings": len(recordings.durations),
            # Buttons of the game board, read in the narrator's voice
            "interface": {name: {"text": text, "audio": recordings(text)}
                          for name, text in INTERFACE.items()}}


@app.post("/v1/start")
def start(game: str | None = None) -> dict:
    return _game(game).start()


@app.post("/v1/view")
def view(saved: Saved, game: str | None = None) -> dict:
    return _game(game).view(saved.state)


@app.post("/v1/choose")
def choose(choice: Choice, game: str | None = None) -> dict:
    return _game(game).choose(choice.state, choice.option)
