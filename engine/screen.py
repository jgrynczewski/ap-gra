"""How much of the game screen a scene's text takes - so the whole text is
always visible (no scrolling, the player cannot scroll).

A model of the AP game screen (modules/gra.py): text on the left 2/3 of a
1920x1080 screen, above 4 options. Measured on the user's computer
(2026-11-01): about 10 lines of LINE_CHARS characters fit. A blank line
between paragraphs takes half a line. The client also shrinks the font a
little if a text still does not fit - this limit keeps that rare.
"""

from __future__ import annotations

from .scenario import Scene

LINE_CHARS = 55  # characters in one screen line
MAX_LINES = 10  # screen lines for the text of a scene
PARAGRAPH_GAP = 0.5  # a blank line between paragraphs, in screen lines
ENDING_LINES = 3  # an ending adds: title, "Zakończenie ... z ...", endings found


def wrapped_lines(line: str, width: int = LINE_CHARS) -> int:
    """Screen lines of one text line wrapped at word boundaries."""
    count, length = 1, 0
    for word in line.split():
        if length and length + 1 + len(word) > width:
            count, length = count + 1, len(word)
        else:
            length += (1 if length else 0) + len(word)
    return count


def text_lines(text: str) -> float:
    """Screen lines of a rendered scene text ("\\n\\n" paragraphs, "\\n" verses)."""
    if not text:
        return 0
    paragraphs = text.split("\n\n")
    lines = sum(wrapped_lines(line) for paragraph in paragraphs for line in paragraph.split("\n"))
    return lines + PARAGRAPH_GAP * (len(paragraphs) - 1)


def scene_lines(scene: Scene, flags: set[str]) -> float:
    """Screen lines of the scene as the player sees it with these flags."""
    lines = text_lines(scene.render(flags))
    if scene.ending:
        lines += PARAGRAPH_GAP + ENDING_LINES
    return lines
