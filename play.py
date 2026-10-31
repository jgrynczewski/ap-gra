"""Play a scenario in the terminal - for writing and testing the story.

    python play.py scenariusz/sala_pod_zegarem.md

Choose with the option number; q - quit, r - start again.
"""

import sys
import textwrap

from engine.game import Game, GameError
from engine.scenario import ScenarioError, load


def show(view: dict) -> None:
    print()
    for paragraph in view["text"].split("\n\n"):
        for line in paragraph.split("\n"):  # verse lines stay separate
            print(textwrap.fill(line, 78))
        print()
    if view["ending"]:
        ending = view["ending"]
        print(f"*** KONIEC: {ending['title']} (zakończenie {ending['number']} z {ending['total']}) ***")
        return
    for option in view["options"]:
        print(f"  {option['number']}. {option['text']}")


def main(path: str) -> int:
    try:
        game = Game(load(path))
    except ScenarioError as e:
        print(f"BŁĄD FORMATU: {e}")
        return 1
    print(f"=== {game.scenario.title} ===")
    view = game.start()
    show(view)
    while True:
        prompt = "\n> " if not view["ending"] else "\n[r - od nowa, q - koniec] > "
        answer = input(prompt).strip().lstrip("﻿")  # BOM from a PowerShell pipe
        if answer == "q":
            return 0
        if answer == "r":
            view = game.start()
            show(view)
        elif answer.isdigit() and not view["ending"]:
            try:
                view = game.choose(view["state"], int(answer))
                show(view)
            except GameError as e:
                print(e)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "scenariusz/sala_pod_zegarem.md"))
