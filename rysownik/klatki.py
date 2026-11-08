"""Animation of a game: frames drawn by a function, checks of the code and
of the frames (docs/kreator-gier.md, stage 5).

The drawing function (written by the AI, or ours - rysownik/zapasowy.py):

    def rysuj(d, t, w, h):
        # d - PIL.ImageDraw.ImageDraw on an RGB picture w x h, empty each frame
        # t - moment of the loop, from 0 (first frame) to just below 1;
        #     everything that moves is periodic in t, so the loop is seamless

Frames are drawn twice as big and scaled down (smooth edges - ImageDraw has
no antialiasing). The panel of the scene in AP is about 1/3 of the screen
wide and a bit less high; AP scales the frames to it.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable

WIDTH, HEIGHT = 540, 500
FPS = 12
SECONDS = 8
FRAMES = FPS * SECONDS
SCALE = 2  # drawn at 2x, then scaled down

# What the AI code may use: no files, no imports beyond these, no dunders
ALLOWED_IMPORTS = {"math", "random"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars",
                   "getattr", "setattr", "delattr", "input", "breakpoint", "exit", "quit", "help"}
MAX_CODE_CHARS = 30_000


def frame_name(number: int) -> str:
    return f"{number:04d}.png"


def code_problems(code: str) -> list[str]:
    """What breaks the rules of the drawing code, before running it."""
    if len(code) > MAX_CODE_CHARS:
        return [f"kod za długi (ponad {MAX_CODE_CHARS} znaków)"]
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return [f"błąd składni w linii {error.lineno}: {error.msg}"]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            names = []
        for name in names:
            if name.split(".")[0] not in ALLOWED_IMPORTS:
                found.append(f"linia {node.lineno}: import {name} - wolno tylko {', '.join(sorted(ALLOWED_IMPORTS))}")
        if isinstance(node, ast.Name) and (node.id in FORBIDDEN_NAMES or node.id.startswith("__")):
            found.append(f"linia {node.lineno}: nie wolno używać {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            found.append(f"linia {node.lineno}: nie wolno używać {node.attr}")
    if not any(isinstance(n, ast.FunctionDef) and n.name == "rysuj" for n in tree.body):
        found.append("brak funkcji rysuj(d, t, w, h)")
    return found


def render(draw: Callable, out: Path, frames: int = FRAMES) -> None:
    """Frames 0000.png ... into out (made empty first)."""
    from PIL import Image, ImageDraw

    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    w, h = WIDTH * SCALE, HEIGHT * SCALE
    for number in range(frames):
        picture = Image.new("RGB", (w, h), "white")
        draw(ImageDraw.Draw(picture), number / frames, w, h)
        picture.resize((WIDTH, HEIGHT), Image.LANCZOS).save(out / frame_name(number), optimize=True)


def frame_problems(out: Path, frames: int = FRAMES) -> list[str]:
    """Are the frames there, not empty, and does something move?"""
    from PIL import Image, ImageChops

    def picture(path: Path):
        with Image.open(path) as opened:
            return opened.convert("RGB")

    paths = sorted(out.glob("*.png"))
    if len(paths) != frames:
        return [f"jest {len(paths)} klatek, ma być {frames}"]
    first = picture(paths[0])
    if first.size != (WIDTH, HEIGHT):
        return [f"klatka ma rozmiar {first.size}, ma być {(WIDTH, HEIGHT)}"]
    found = []
    # A picture of shapes has many colours (with smooth edges); a few = empty
    if first.getcolors(maxcolors=16) is not None:  # None = more than 16 colours
        found.append("pierwsza klatka jest prawie pusta - narysuj scenę")
    moving = 0
    for path in paths[1:]:
        box = ImageChops.difference(first, picture(path)).getbbox()
        if box:
            moving += 1
    if moving < len(paths[1:]) // 2:
        found.append("prawie nic się nie rusza - niech coś się porusza przez całą pętlę")
    return found
