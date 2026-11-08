"""Statistics of the playthroughs from the logs of the game server
(dane/rozgrywki/<game>.jsonl, api/app.py): how many times a game was played
and finished, which endings were reached, how many times and when first.

On the AP computer (the server container reads the same dane/):

    docker exec ap-gra python -m tools.statystyki                    # all games
    docker exec ap-gra python -m tools.statystyki sala_pod_zegarem   # one game
    docker exec ap-gra python -m tools.statystyki --json             # for other programs

Times are shown in Polish time. stats() gives the same as data - for a page
or an API later.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.log import Log  # noqa: E402
from engine.scenario import ScenarioError, load  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = Path(os.environ.get("AP_GRA_SCENARIOS", ROOT / "scenariusz"))
DATA = Path(os.environ.get("AP_GRA_DATA", ROOT / "dane"))
ZONE = ZoneInfo("Europe/Warsaw")


def scenario_endings(game: str) -> tuple[str, dict[str, str]]:
    """(title, {ending id: title}) of the game now; ("", {}) when it is gone."""
    for path in (SCENARIOS / f"{game}.md", DATA / "gry" / game / "scenariusz.md"):
        if path.is_file():
            try:
                scenario = load(path)
            except ScenarioError:
                break
            return scenario.title, scenario.endings
    return "", {}


def stats(entries: list[dict], endings: dict[str, str] | None = None) -> dict:
    """Numbers from the log entries of one game. endings - all endings of the
    game (to show the ones never reached too), in the game's order."""
    counted = {kind: [e for e in entries if e["rodzaj"] == kind]
               for kind in ("start", "kontynuacja", "wybor", "zakonczenie")}
    reached: dict[str, dict] = {}
    for e in counted["zakonczenie"]:
        found = reached.setdefault(e["zakonczenie"], {"id": e["zakonczenie"], "tytul": e["tytul"], "razy": 0,
                                                     "pierwszy_raz": e["czas"]})
        found["razy"] += 1
        found["ostatni_raz"] = e["czas"]
    order = list(endings or {}) + [eid for eid in reached if eid not in (endings or {})]
    all_endings = [reached.get(eid) or {"id": eid, "tytul": (endings or {}).get(eid, eid), "razy": 0,
                                        "pierwszy_raz": None, "ostatni_raz": None}
                   for eid in order]
    times = [e["czas"] for e in entries]
    return {
        "rozgrywki": len(counted["start"]),  # games started from the beginning
        "kontynuacje": len(counted["kontynuacja"]),  # saved games continued
        "ukonczone": len(counted["zakonczenie"]),
        "wybory": len(counted["wybor"]),
        "pierwsza_gra": min(times) if times else None,
        "ostatnia_gra": max(times) if times else None,
        "odkryte": sum(1 for e in all_endings if e["razy"]),
        "zakonczenia": all_endings,
    }


def _local(time: str | None) -> str:
    if not time:
        return "-"
    return datetime.fromisoformat(time).astimezone(ZONE).strftime("%d.%m.%Y %H:%M")


def report(game: str, numbers: dict, title: str) -> str:
    lines = [f"== {title or game} ({game})",
             f"rozgrywki: {numbers['rozgrywki']}, ukończone: {numbers['ukonczone']}, "
             f"kontynuacje zapisanej gry: {numbers['kontynuacje']}, wybory: {numbers['wybory']}",
             f"pierwsza gra: {_local(numbers['pierwsza_gra'])}, ostatnia: {_local(numbers['ostatnia_gra'])}",
             f"zakończenia - odkryte {numbers['odkryte']} z {len(numbers['zakonczenia'])}:"]
    for n, ending in enumerate(numbers["zakonczenia"], start=1):
        if ending["razy"]:
            times = "1 raz" if ending["razy"] == 1 else f"{ending['razy']} razy"
            lines.append(f"  {n}. {ending['tytul']} - {times}, pierwszy raz "
                         f"{_local(ending['pierwszy_raz'])}, ostatni {_local(ending['ostatni_raz'])}")
        else:
            lines.append(f"  {n}. {ending['tytul']} - jeszcze nie")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("games", nargs="*", help="identyfikatory gier (domyślnie wszystkie z logami)")
    parser.add_argument("--json", action="store_true", help="dane zamiast opisu")
    args = parser.parse_args(argv)
    plays = DATA / "rozgrywki"
    games = args.games or sorted(p.stem for p in plays.glob("*.jsonl"))
    if not games:
        print("Brak zapisanych rozgrywek.")
        return 0
    result = {}
    for game in games:
        title, endings = scenario_endings(game)
        result[game] = {"tytul": title, **stats(Log(plays / f"{game}.jsonl").entries(), endings)}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(report(game, numbers, numbers["tytul"]) for game, numbers in result.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
