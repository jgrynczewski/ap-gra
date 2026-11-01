"""Scenario format (docs/format.md): a Markdown-like text file -> Scenario."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

MAX_OPTIONS = 4  # visible at once - more is too long to scan and listen to

_ID = r"[a-z0-9_]+"
_SCENE = re.compile(rf"^##\s+({_ID})\s*$")
# * [conditions] text -> target +set -clear
_OPTION = re.compile(rf"^\*\s+(?:\[([^\]]*)\]\s*)?(.+?)\s*->\s*({_ID})((?:\s+[+-]{_ID})*)\s*$")
_DIRECTIVE = re.compile(r"^>\s*(\w+)\s*:\s*(.*?)\s*$")
_CONDITIONAL = re.compile(r"^\[([^\]]*)\]\s*(.*)$")  # [conditions] text line
_FLAG = re.compile(rf"^!?{_ID}$")

DIRECTIVES = ("ustaw", "usun", "koniec", "obraz")

Conditions = list[tuple[str, bool]]  # (flag, required): set (True) / not set (False)


def _met(conditions: Conditions, flags: set[str]) -> bool:
    return all((flag in flags) == required for flag, required in conditions)


class ScenarioError(Exception):
    def __init__(self, message: str, line: int | None = None, source: str = ""):
        where = f"{source}:{line}: " if line else (f"{source}: " if source else "")
        super().__init__(where + message)
        self.line = line


@dataclass
class Line:
    text: str
    verse: bool  # "| ..." - keeps its line break
    conditions: Conditions  # "[flag] ..." - shown only when met


@dataclass
class Option:
    text: str
    target: str
    conditions: Conditions  # visible when met
    line: int
    set_flags: list[str] = field(default_factory=list)  # +flag - when chosen
    clear_flags: list[str] = field(default_factory=list)  # -flag

    def visible(self, flags: set[str]) -> bool:
        return _met(self.conditions, flags)

    def apply(self, flags: set[str]) -> set[str]:
        """Flags after choosing this option (before entering the target)."""
        return (flags | set(self.set_flags)) - set(self.clear_flags)


@dataclass
class Scene:
    id: str
    line: int
    paragraphs: list[list[Line]] = field(default_factory=list)
    options: list[Option] = field(default_factory=list)
    set_flags: list[str] = field(default_factory=list)
    clear_flags: list[str] = field(default_factory=list)
    ending: str | None = None  # title of the ending - the scene ends the game
    image: str | None = None

    def enter(self, flags: set[str]) -> set[str]:
        """Flags after entering this scene."""
        return (flags | set(self.set_flags)) - set(self.clear_flags)

    def visible_options(self, flags: set[str]) -> list[Option]:
        return [o for o in self.options if o.visible(flags)]

    def lines(self, flags: set[str]) -> list[tuple[str, Line]]:
        """Lines shown for these flags, each with the separator before it:
        "" (first), " " (same paragraph), "\\n" (verse), "\\n\\n" (new paragraph)."""
        result: list[tuple[str, Line]] = []
        for paragraph in self.paragraphs:
            shown = [line for line in paragraph if _met(line.conditions, flags)]
            for i, line in enumerate(shown):
                if i == 0:
                    before = "\n\n" if result else ""
                else:
                    before = "\n" if line.verse or shown[i - 1].verse else " "
                result.append((before, line))
        return result

    def render(self, flags: set[str]) -> str:
        """Text for these flags: lines joined into paragraphs, verse lines
        and paragraphs (blank line) kept apart."""
        return "".join(before + line.text for before, line in self.lines(flags))

    def text_conditions(self) -> list[str]:
        return [flag for p in self.paragraphs for line in p for flag, _ in line.conditions]


@dataclass
class Scenario:
    title: str
    scenes: dict[str, Scene]  # in file order
    start: str

    @property
    def endings(self) -> dict[str, str]:
        """Scene id -> ending title, in file order."""
        return {s.id: s.ending for s in self.scenes.values() if s.ending}


def _flags(value: str, line: int, source: str) -> list[str]:
    flags = [f.strip() for f in value.split(",") if f.strip()]
    for flag in flags:
        if not _FLAG.match(flag) or flag.startswith("!"):
            raise ScenarioError(f"Zła nazwa flagi: {flag!r}", line, source)
    return flags


def _conditions(value: str | None, line: int, source: str) -> Conditions:
    if value is None:
        return []
    result = []
    for item in (c.strip() for c in value.split(",")):
        if not _FLAG.match(item):
            raise ScenarioError(f"Zły warunek: {item!r}", line, source)
        result.append((item.lstrip("!"), not item.startswith("!")))
    return result


def _option(match, number: int, source: str) -> Option:
    conditions, text, target, effects = match.groups()
    option = Option(text, target, _conditions(conditions, number, source), number)
    for effect in effects.split():
        (option.set_flags if effect[0] == "+" else option.clear_flags).append(effect[1:])
    return option


def parse(text: str, source: str = "") -> Scenario:
    title = None
    scenes: dict[str, Scene] = {}
    scene: Scene | None = None

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("//"):
            continue
        if title is None:
            if not line:
                continue
            if not line.startswith("# "):
                raise ScenarioError("Plik musi zaczynać się od tytułu: # Tytuł", number, source)
            title = line[2:].strip()
            continue

        match = _SCENE.match(line)
        if match:
            if match.group(1) in scenes:
                raise ScenarioError(f"Scena {match.group(1)!r} już istnieje", number, source)
            scene = scenes[match.group(1)] = Scene(match.group(1), number, [[]])
            continue
        if line.startswith("#"):
            raise ScenarioError(f"Nagłówek sceny: ## identyfikator (małe litery, cyfry, _): {line!r}",
                                number, source)
        if scene is None:
            if line:
                raise ScenarioError("Tekst przed pierwszą sceną", number, source)
            continue

        if line.startswith("*"):
            match = _OPTION.match(line)
            if not match:
                raise ScenarioError(f"Opcja: * [warunek] tekst -> scena +flaga -flaga: {line!r}",
                                    number, source)
            scene.options.append(_option(match, number, source))
        elif line.startswith(">"):
            match = _DIRECTIVE.match(line)
            if not match or match.group(1) not in DIRECTIVES:
                raise ScenarioError(f"Dyrektywa: > {' / '.join(DIRECTIVES)}: wartość: {line!r}",
                                    number, source)
            name, value = match.groups()
            if name == "ustaw":
                scene.set_flags += _flags(value, number, source)
            elif name == "usun":
                scene.clear_flags += _flags(value, number, source)
            elif name == "koniec":
                scene.ending = value or scene.id
            else:
                scene.image = value
        elif not line:
            scene.paragraphs.append([])
        elif scene.options or scene.set_flags or scene.clear_flags or scene.ending:
            raise ScenarioError("Tekst sceny musi być przed dyrektywami (>) i opcjami (*)",
                                number, source)
        else:
            conditions = []
            match = _CONDITIONAL.match(line)
            if match:
                conditions = _conditions(match.group(1), number, source)
                line = match.group(2)
            verse = line.startswith("|")
            scene.paragraphs[-1].append(Line(line[1:].strip() if verse else line, verse, conditions))

    if title is None:
        raise ScenarioError("Pusty plik - brak tytułu", source=source)
    if not scenes:
        raise ScenarioError("Brak scen (## identyfikator)", source=source)
    return Scenario(title, scenes, next(iter(scenes)))


def load(path: str | Path) -> Scenario:
    path = Path(path)
    return parse(path.read_text(encoding="utf-8"), path.name)
