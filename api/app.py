"""HTTP API of the games - a thin layer over engine.Game (docs/api.md).

    uvicorn api.app:app --port 8766

Built-in games: every scenario in scenariusz/*.md, its id is the file name
(sala_pod_zegarem, ostatnia_zwrotka). User games (made by the game creator,
docs/kreator-gier.md): dane/gry/<id>/scenariusz.md with recordings in
dane/gry/<id>/audio/ - read on every request, so a new game shows up without
a restart. Routes take ?game=<id>; without it - the default game
(AP_GRA_DEFAULT), so older clients keep working.

Stateless: the client keeps the state from the last view and sends it back
with the choice - the server keeps no game state.

Playthroughs are logged (dane/rozgrywki/<game>.jsonl, read by
tools/statystyki.py): start, continuing a saved game, every choice and every
ending, with the time. The id of the playthrough travels in the state
("rozgrywka"), so the client needs no change; a state without it (a save from
before) gets a new one. A failure to write the log never stops the game.
"""

import logging
import os
import re
import threading
from pathlib import Path
from secrets import token_hex

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.game import Game, GameError
from engine.log import Log
from engine.scenario import ScenarioError, load
from engine.voice import INTERFACE, Recordings

log = logging.getLogger("ap-gra")

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = Path(os.environ.get("AP_GRA_SCENARIOS", ROOT / "scenariusz"))
DEFAULT_GAME = os.environ.get("AP_GRA_DEFAULT", "sala_pod_zegarem")
# Narrator recordings (tools/nagraj.py, made in the Docker build); without
# them the game works, views just have "audio": null
AUDIO = Path(os.environ.get("AP_GRA_AUDIO", ROOT / "audio"))
AUDIO_URL = "/v1/audio"
# Data shared with the game creator (docker-compose.yml mounts it)
DATA = Path(os.environ.get("AP_GRA_DATA", ROOT / "dane"))
USER_GAMES = DATA / "gry"
PLAYS = DATA / "rozgrywki"  # logs of the playthroughs, one file per game
# A game id is also a directory name; anything else there (e.g. a game being
# published, <id>.tmp) is not a game
GAME_ID = re.compile(r"[a-z0-9_]+")
RECORDING = re.compile(r"[0-9a-f]+\.wav")

recordings = Recordings(AUDIO, AUDIO_URL)
GAMES = {path.stem: Game(load(path), audio=recordings) for path in sorted(SCENARIOS.glob("*.md"))}

# id -> (mtime of the scenario, Game): a user game is parsed again only when
# its scenario file changes
_user_cache: dict[str, tuple[int, Game]] = {}


def _user_game(directory: Path) -> Game | None:
    scenario = directory / "scenariusz.md"
    try:
        mtime = scenario.stat().st_mtime_ns
        cached = _user_cache.get(directory.name)
        if cached and cached[0] == mtime:
            return cached[1]
        game = Game(load(scenario),
                    audio=Recordings(directory / "audio", f"/v1/gry/{directory.name}/audio"))
    except (OSError, ScenarioError) as error:
        # A broken game must not take the other games down
        log.warning("pomijam grę %s: %s", directory.name, error)
        return None
    _user_cache[directory.name] = (mtime, game)
    return game


def all_games() -> dict[str, Game]:
    """Built-in games first (a user game cannot replace one), then user games
    by id."""
    games = dict(GAMES)
    if USER_GAMES.is_dir():
        for directory in sorted(USER_GAMES.iterdir()):
            if directory.is_dir() and GAME_ID.fullmatch(directory.name) and directory.name not in games:
                game = _user_game(directory)
                if game:
                    games[directory.name] = game
    return games


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
    found = all_games().get(game or DEFAULT_GAME)
    if found is None:
        raise UnknownGame(f"Nie ma gry {game!r}.")
    return found


_play_logs: dict[str, Log] = {}
_play_logs_lock = threading.Lock()


def _played(game: str | None, kind: str, **data) -> None:
    """One event of a playthrough to the log of the game."""
    gid = game or DEFAULT_GAME
    try:
        with _play_logs_lock:
            if gid not in _play_logs:
                _play_logs[gid] = Log(PLAYS / f"{gid}.jsonl")
            play_log = _play_logs[gid]
        play_log.write(kind, **data)
    except OSError as error:
        log.warning("nie zapisano rozgrywki (%s, %s): %s", gid, kind, error)


def _play_id(state: dict) -> str:
    play = state.get("rozgrywka")
    return play if isinstance(play, str) and 0 < len(play) <= 40 else token_hex(6)


def _with_play(view: dict, play: str) -> dict:
    view["state"]["rozgrywka"] = play
    return view


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
            "games": [{"id": gid, "title": g.scenario.title, "endings": len(g.scenario.endings),
                       "builtin": gid in GAMES}
                      for gid, g in all_games().items()]}


@app.get("/v1/gry/{game}/audio/{name}")
def user_game_audio(game: str, name: str) -> FileResponse:
    # Names checked before touching the disk - no paths outside dane/gry
    path = USER_GAMES / game / "audio" / name
    if not (GAME_ID.fullmatch(game) and RECORDING.fullmatch(name) and path.is_file()):
        raise UnknownGame(f"Nie ma nagrania {name!r}.")
    return FileResponse(path, media_type="audio/wav")


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
    view = _with_play(_game(game).start(), token_hex(6))
    _played(game, "start", rozgrywka=view["state"]["rozgrywka"], scena=view["scene"])
    return view


@app.post("/v1/view")
def view(saved: Saved, game: str | None = None) -> dict:
    play = _play_id(saved.state)
    view = _with_play(_game(game).view(saved.state), play)
    _played(game, "kontynuacja", rozgrywka=play, scena=view["scene"],
            stary_zapis="rozgrywka" not in saved.state)
    return view


@app.post("/v1/choose")
def choose(choice: Choice, game: str | None = None) -> dict:
    g = _game(game)
    play = _play_id(choice.state)
    view = _with_play(g.choose(choice.state, choice.option), play)
    # The choice was valid (choose raises otherwise) - its text for the log
    scene = g.scenario.scenes[choice.state["scene"]]
    chosen = scene.visible_options(set(choice.state.get("flags", [])))[choice.option - 1]
    _played(game, "wybor", rozgrywka=play, scena=scene.id, opcja=choice.option, tekst=chosen.text,
            cel=view["scene"])
    if view["ending"]:
        ending = view["ending"]
        _played(game, "zakonczenie", rozgrywka=play, zakonczenie=ending["id"], tytul=ending["title"],
                numer=ending["number"], wszystkich=ending["total"])
    return view
