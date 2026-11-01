"""Recordings: which texts are read, names, lines in the view."""

import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import voice  # noqa: E402
from engine.game import Game  # noqa: E402
from engine.scenario import load, parse  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = """# Test
## a
Pierwsze zdanie.
Drugie w tym samym akapicie.

| Wers jeden,
| wers dwa.
[f] Tylko z flagą.
* Dalej -> b +f
## b
Koniec.
> koniec: Finał
"""


def write_wav(path: Path, seconds: float, rate: int = 22050) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(int(rate * seconds) * 2))


class VoiceTest(unittest.TestCase):
    def test_texts(self):
        texts = voice.texts(parse(SAMPLE))
        self.assertEqual(texts, ["Pierwsze zdanie.", "Drugie w tym samym akapicie.", "Wers jeden,",
                                 "wers dwa.", "Tylko z flagą.", "Dalej", "Koniec.", "Finał"])

    def test_key_depends_on_text_and_voice(self):
        self.assertEqual(voice.key("Ala"), voice.key("Ala"))
        self.assertNotEqual(voice.key("Ala"), voice.key("Ala."))
        self.assertRegex(voice.key("Ala"), r"^[0-9a-f]{16}$")

    def test_lines_rebuild_text(self):
        game = Game(load(ROOT / "scenariusz" / "sala_pod_zegarem.md"))
        view = game.start()
        self.assertEqual("".join(l["before"] + l["text"] for l in view["lines"]), view["text"])
        self.assertEqual([l["before"] for l in view["lines"][:4]], ["", "\n\n", "\n\n", "\n"])

    def test_view_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            write_wav(Path(directory) / f"{voice.key('Pierwsze zdanie.')}.wav", 1.5)
            write_wav(Path(directory) / f"{voice.key('Dalej')}.wav", 0.5)
            write_wav(Path(directory) / f"{voice.key('Finał')}.wav", 0.75)
            game = Game(parse(SAMPLE), audio=voice.Recordings(Path(directory), "/v1/audio/"))
            view = game.start()
            self.assertEqual(view["lines"][0]["audio"],
                             {"url": f"/v1/audio/{voice.key('Pierwsze zdanie.')}.wav", "duration": 1.5})
            self.assertIsNone(view["lines"][1]["audio"])  # not recorded
            self.assertEqual(view["options"][0]["audio"]["duration"], 0.5)
            end = game.choose(view["state"], 1)
            self.assertEqual(end["ending"]["audio"]["duration"], 0.75)

    def test_no_recordings(self):
        view = Game(parse(SAMPLE)).start()
        self.assertIsNone(view["lines"][0]["audio"])
        recordings = voice.Recordings(Path("nie-ma-takiego-katalogu"), "/v1/audio")
        self.assertIsNone(recordings("Pierwsze zdanie."))


if __name__ == "__main__":
    unittest.main()
