"""The game: scenario + player's state -> what to show and read.

Stateless: the state (current scene, flags) goes to the client with every
view and comes back with the choice - so the same engine serves the
terminal, the HTTP API and later a browser, locally or in the cloud.
"""

from __future__ import annotations

from typing import Callable

from .scenario import Scenario

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

    def _enter(self, scene_id: str, flags: set[str]) -> dict:
        scene = self._scene(scene_id)
        flags = scene.enter(flags)
        endings = list(self.scenario.endings)
        return {
            "scene": scene.id,
            "text": scene.render(flags),
            "lines": [{"before": before, "text": line.text, "audio": self.audio(line.text)}
                      for before, line in scene.lines(flags)],
            "image": scene.image,
            "options": [{"number": i, "text": o.text, "audio": self.audio(o.text)}
                        for i, o in enumerate(scene.visible_options(flags), start=1)],
            "ending": {"id": scene.id, "title": scene.ending,
                       "number": endings.index(scene.id) + 1, "total": len(endings),
                       "audio": self.audio(scene.ending)}
                      if scene.ending else None,
            "state": {"scene": scene.id, "flags": sorted(flags)},
        }
