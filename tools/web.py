"""A game for the browser (AbleLab Studio, wicero docs/adr/0014).

    python -m tools.web paczka <gra> <out>         a game -> its web version
    python -m tools.web przejscia <scenariusz.md>... --out <dir>
                                                   playthroughs for the test of
                                                   the browser player (wicero studio/)

<gra> is a user game directory (dane/gry/<id>/: scenariusz.md, audio/,
animacja/, kafelek.png, gra.json) or a built-in scenario file
(scenariusz/<id>.md, recordings in AP_GRA_AUDIO).

The web version holds ONLY what is listed in WEB_FILES: the scenario as JSON
(parsed by the engine, so the browser needs no parser), the narrator's
recordings as MP3, the animation as one animated WebP and the tile. Nothing
else from the game directory goes out - above all not the conversation with
the AI (rozmowa.jsonl) and not the drawing code (rysunek.py).

Playthroughs: for every game a path to each ending and some random paths,
each step being the engine's view (without recordings). The browser player
must give the same views - the logic lives in two languages, this keeps them
equal.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import wave
from collections import deque
from pathlib import Path

from engine.game import Game
from engine.scenario import Scenario, load
from engine.voice import INTERFACE, ending_label, key, texts

FORMAT = 1
LANGUAGE = "pl"
MP3_KBPS = 48  # speech, mono: about 6 kB per second
WEBP_QUALITY = 80
# Everything a web version may contain (file names, or "dir/" for a directory
# whose files have the given suffix)
WEB_FILES = {"gra.json": None, "animacja.webp": None, "kafelek.webp": None, "audio/": ".mp3"}


def _conditions(conditions) -> list:
    return [[flag, required] for flag, required in conditions]


def scenario_json(scenario: Scenario) -> dict:
    """The scenario as data: the browser follows it the way engine.Game does."""
    scenes = {}
    for scene in scenario.scenes.values():
        scenes[scene.id] = {
            "paragraphs": [[{"text": line.text, "verse": line.verse, "if": _conditions(line.conditions)}
                            for line in paragraph] for paragraph in scene.paragraphs],
            "options": [{"text": o.text, "target": o.target, "if": _conditions(o.conditions),
                         "set": o.set_flags, "clear": o.clear_flags} for o in scene.options],
            "set": scene.set_flags, "clear": scene.clear_flags, "ending": scene.ending,
        }
    endings = list(scenario.endings)
    return {"title": scenario.title, "start": scenario.start, "scenes": scenes, "endings": endings,
            # Polish words for "ending third of seven" - not computed again in the browser
            "ending_labels": [ending_label(n, len(endings)) for n in range(1, len(endings) + 1)]}


def mp3(wav_path: Path, out: Path) -> None:
    import lameenc  # only here: the engine and the API do not need it

    with wave.open(str(wav_path), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise ValueError(f"{wav_path.name}: tylko 16-bitowe nagrania")
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(MP3_KBPS)
        encoder.set_in_sample_rate(wav.getframerate())
        encoder.set_channels(wav.getnchannels())
        encoder.set_quality(2)
        data = encoder.encode(wav.readframes(wav.getnframes())) + encoder.flush()
    out.write_bytes(data)


def animation(frames_dir: Path, fps: int, out: Path) -> None:
    from PIL import Image

    frames = sorted(frames_dir.glob("[0-9][0-9][0-9][0-9].png"))
    if not frames:
        raise ValueError("brak klatek animacji")
    images = [Image.open(path).convert("RGB") for path in frames]
    images[0].save(out, format="WEBP", save_all=True, append_images=images[1:], loop=0,
                   duration=round(1000 / fps), quality=WEBP_QUALITY, method=4)


def tile(png: Path, out: Path) -> None:
    from PIL import Image

    Image.open(png).convert("RGB").save(out, format="WEBP", quality=WEBP_QUALITY + 5, method=4)


def _source(game: Path) -> tuple[Path, Path, Path | None]:
    """(scenario, recordings dir, user game dir or None)."""
    if game.is_dir():
        return game / "scenariusz.md", game / "audio", game
    return game, Path(os.environ.get("AP_GRA_AUDIO", "audio")), None


def build(game: Path, out: Path) -> dict:
    """Write the web version of the game to out (emptied first). Returns its gra.json."""
    scenario_path, audio_dir, user_dir = _source(game)
    scenario = load(scenario_path)
    if out.exists():
        shutil.rmtree(out)
    (out / "audio").mkdir(parents=True)

    recordings = {}
    narrated = [t for t in texts(scenario) if t not in INTERFACE.values()]
    for text in narrated:
        wav = audio_dir / f"{key(text)}.wav"
        if wav.exists():
            name = f"audio/{key(text)}.mp3"
            if name not in recordings.values():
                mp3(wav, out / name)
            recordings[text] = name

    meta = {}
    if user_dir and (user_dir / "gra.json").exists():
        meta = json.loads((user_dir / "gra.json").read_text(encoding="utf-8"))
    picture = None
    if user_dir and (user_dir / "animacja").is_dir():
        animation(user_dir / "animacja", (meta.get("animacja") or {}).get("fps", 12), out / "animacja.webp")
        picture = "animacja.webp"
    tile_file = None
    if user_dir and (user_dir / "kafelek.png").exists():
        tile(user_dir / "kafelek.png", out / "kafelek.webp")
        tile_file = "kafelek.webp"

    data = {"format": FORMAT, "language": LANGUAGE,
            # gra.json of a user game: the summary of the idea becomes the description
            "description": meta.get("streszczenie", ""), "made": meta.get("utworzona", ""),
            **scenario_json(scenario),
            "audio": recordings, "animation": picture, "tile": tile_file}
    (out / "gra.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    check_contents(out)
    return data


def check_contents(out: Path) -> None:
    """Fail if the web version holds anything not in WEB_FILES."""
    for path in out.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(out).as_posix()
        top, _, rest = relative.partition("/")
        allowed = (relative in WEB_FILES if not rest
                   else f"{top}/" in WEB_FILES and "/" not in rest and rest.endswith(WEB_FILES[f"{top}/"]))
        if not allowed:
            raise ValueError(f"Niedozwolony plik w wersji web: {relative}")


# --- playthroughs for the browser player test ---------------------------------

def _plain(view: dict) -> dict:
    """The engine's view without recordings - what the browser must give."""
    ending = view["ending"]
    return {"scene": view["scene"], "text": view["text"],
            "lines": [{"before": line["before"], "text": line["text"]} for line in view["lines"]],
            "options": [{"number": o["number"], "text": o["text"]} for o in view["options"]],
            "ending": None if ending is None else
            {k: ending[k] for k in ("id", "title", "number", "total", "label")},
            "state": view["state"]}


def _path_to_each_ending(game: Game) -> list[list[int]]:
    """The shortest choices to every reachable ending (breadth-first over states)."""
    start = game.start()
    seen = {(start["scene"], tuple(start["state"]["flags"]))}
    queue = deque([(start, [])])
    found: dict[str, list[int]] = {}
    while queue:
        view, choices = queue.popleft()
        if view["ending"]:
            found.setdefault(view["scene"], choices)
            continue
        for option in view["options"]:
            after = game.choose(view["state"], option["number"])
            state = (after["scene"], tuple(after["state"]["flags"]))
            if state not in seen:
                seen.add(state)
                queue.append((after, choices + [option["number"]]))
    return [found[scene] for scene in game.scenario.endings if scene in found]


def playthroughs(scenario: Scenario, random_paths: int = 20, seed: int = 1, limit: int = 200) -> list:
    game = Game(scenario)
    rng = random.Random(seed)
    paths = _path_to_each_ending(game)
    for _ in range(random_paths):
        view, choices = game.start(), []
        while not view["ending"] and view["options"] and len(choices) < limit:
            choices.append(rng.randint(1, len(view["options"])))
            view = game.choose(view["state"], choices[-1])
        paths.append(choices)
    result = []
    for choices in paths:
        view = game.start()
        views = [_plain(view)]
        for number in choices:
            view = game.choose(view["state"], number)
            views.append(_plain(view))
        # Continuing a saved game: the view of the last state again
        result.append({"choices": choices, "views": views, "continued": _plain(game.view(view["state"]))})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.web")
    commands = parser.add_subparsers(dest="command", required=True)
    package = commands.add_parser("paczka", help="gra -> wersja web")
    package.add_argument("gra", type=Path)
    package.add_argument("out", type=Path)
    paths = commands.add_parser("przejscia", help="przejścia do testu odtwarzacza")
    paths.add_argument("scenariusze", type=Path, nargs="+")
    paths.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "paczka":
        data = build(args.gra, args.out)
        size = sum(p.stat().st_size for p in args.out.rglob("*") if p.is_file())
        print(f"{data['title']}: {len(data['audio'])} nagrań, {size / 1e6:.1f} MB -> {args.out}")
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        for path in args.scenariusze:
            scenario_path = _source(path)[0]
            scenario = load(scenario_path)
            name = path.name if path.is_dir() else path.stem
            data = {"format": FORMAT, "game": scenario_json(scenario), "playthroughs": playthroughs(scenario)}
            (args.out / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
            print(f"{name}: {len(data['playthroughs'])} przejść")
    return 0


if __name__ == "__main__":
    sys.exit(main())
