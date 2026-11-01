"""The game: scenario + player's state -> what to show and read.

Stateless: the state (current scene, flags) goes to the client with every
view and comes back with the choice - so the same engine serves the
terminal, the HTTP API and later a browser, locally or in the cloud.
"""

from __future__ import annotations

from typing import Callable

from .scenario import Scenario
from .voice import ending_label

# text -> {"url", "duration"} of its recording, or None (engine.voice.Recordings)
Audio = Callable[[str], "dict | None"]


class GameError(Exception):
    """Bad request from the client (unknown scene, no such option)."""


class Game:
    def __init__(self, scenario: Scenario, audio: Audio | None = None):
        self.scenario = scenario
        self.audio = audio or (lambda text: None)

    def start(self) -> dict:
        return self._enter(self.scenario.start, set())

    def view(self, state: dict) -> dict:
        """The view for a saved state - continuing a game. Entering a scene
        again does not change the flags (it sets / clears the same ones)."""
        flags = state.get("flags", [])
        if not isinstance(flags, list):
            raise GameError("Zły zapis gry.")
        return self._enter(self._scene(state.get("scene")).id, set(flags))

    def choose(self, state: dict, option: int) -> dict:
        """option - number of the visible option, from 1."""
        scene = self._scene(state.get("scene"))
        if scene.ending:
            raise GameError("Gra skończona - zacznij od nowa.")
        flags = set(state.get("flags", []))
        options = scene.visible_options(flags)
        if not isinstance(option, int) or not 1 <= option <= len(options):
            raise GameError(f"Nie ma opcji {option!r}.")
        chosen = options[option - 1]
        return self._enter(chosen.target, chosen.apply(flags))

    def _scene(self, scene_id):
        scene = self.scenario.scenes.get(scene_id) if isinstance(scene_id, str) else None
        if scene is None:
            raise GameError(f"Nie ma sceny {scene_id!r}.")
        return scene

    def _ending(self, scene) -> dict | None:
        if not scene.ending:
            return None
        endings = list(self.scenario.endings)
        number = endings.index(scene.id) + 1
        label = ending_label(number, len(endings))
        return {"id": scene.id, "title": scene.ending, "number": number, "total": len(endings),
                "audio": self.audio(scene.ending), "label": label, "label_audio": self.audio(label)}

    def _enter(self, scene_id: str, flags: set[str]) -> dict:
        scene = self._scene(scene_id)
        flags = scene.enter(flags)
        return {
            "scene": scene.id,
            "text": scene.render(flags),
            "lines": [{"before": before, "text": line.text, "audio": self.audio(line.text)}
                      for before, line in scene.lines(flags)],
            "image": scene.image,
            "options": [{"number": i, "text": o.text, "audio": self.audio(o.text)}
                        for i, o in enumerate(scene.visible_options(flags), start=1)],
            "ending": self._ending(scene),
            "state": {"scene": scene.id, "flags": sorted(flags)},
        }
