"""The web version of a game (tools/web.py, AbleLab Studio)."""

import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from engine.game import Game  # noqa: E402
from engine.scenario import load, parse  # noqa: E402
from engine.voice import key  # noqa: E402
from tools import web  # noqa: E402

SMALL = """# Latarnia

## start
Morze szumi.
[byl] Znowu tu jesteś.

| Światło miga,
| statek płynie.

> ustaw: byl

* Wejdź na górę -> gora +odwaga
* [odwaga] Zawołaj -> koniec_dobry
* Wróć -> koniec_zly

## gora
Wiatr.

* [odwaga] Zejdź -> start
* Skocz -> koniec_zly -odwaga

## koniec_dobry
Ktoś odpowiada.
> koniec: Odpowiedź

## koniec_zly
Cisza.
> koniec: Cisza
"""


def silence(path: Path, seconds: float = 0.3, rate: int = 22050) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * int(rate * seconds))


def user_game(directory: Path) -> Path:
    game = directory / "g1"
    (game / "audio").mkdir(parents=True)
    (game / "animacja").mkdir()
    (game / "scenariusz.md").write_text(SMALL, encoding="utf-8")
    for text in ("Latarnia", "Morze szumi.", "Wejdź na górę", "Cisza"):
        silence(game / "audio" / f"{key(text)}.wav")
    for number in range(3):
        Image.new("RGB", (54, 50), (number * 80, 40, 90)).save(game / "animacja" / f"{number:04d}.png")
    Image.new("RGB", (54, 50), (10, 20, 30)).save(game / "kafelek.png")
    (game / "gra.json").write_text(json.dumps({"tytul": "Latarnia", "streszczenie": "Gra o latarni.",
                                               "animacja": {"fps": 12}, "utworzona": "2026-11-15T20:00:00"}))
    # Never in the web version
    (game / "rozmowa.jsonl").write_text('{"tresc": "prywatna rozmowa"}\n')
    (game / "rysunek.py").write_text("def rysuj(d, t, w, h): pass\n")
    return game


class WebPackageTest(unittest.TestCase):
    def test_only_listed_files_go_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "web"
            data = web.build(user_game(Path(tmp)), out)
            files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
            self.assertEqual(files, sorted(["gra.json", "animacja.webp", "kafelek.webp"] +
                                           [f"audio/{key(t)}.mp3" for t in
                                            ("Latarnia", "Morze szumi.", "Wejdź na górę", "Cisza")]))
            everything = b"".join(p.read_bytes() for p in out.rglob("*") if p.is_file())
            self.assertNotIn("prywatna rozmowa".encode(), everything)
            self.assertNotIn(b"def rysuj", everything)
            self.assertEqual((data["title"], data["description"], data["language"]),
                             ("Latarnia", "Gra o latarni.", "pl"))
            self.assertEqual(data["audio"]["Cisza"], f"audio/{key('Cisza')}.mp3")
            self.assertNotIn("Ktoś odpowiada.", data["audio"])  # no recording -> no entry

    def test_recordings_and_pictures_for_the_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "web"
            web.build(user_game(Path(tmp)), out)
            sound = (out / "audio" / f"{key('Cisza')}.mp3").read_bytes()
            self.assertTrue(sound[:3] == b"ID3" or (sound[0] == 0xFF and sound[1] & 0xE0 == 0xE0), sound[:4])
            with Image.open(out / "animacja.webp") as picture:
                self.assertEqual((picture.format, picture.n_frames, picture.size), ("WEBP", 3, (54, 50)))
            with Image.open(out / "kafelek.webp") as picture:
                self.assertEqual(picture.format, "WEBP")

    def test_anything_else_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "web"
            web.build(user_game(Path(tmp)), out)
            for extra in ("rozmowa.jsonl", "audio/x.wav", "audio/sub/x.mp3", "rysunek.py"):
                path = out / extra
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x")
                with self.assertRaises(ValueError, msg=extra):
                    web.check_contents(out)
                path.unlink()
            web.check_contents(out)

    def test_a_built_in_game_without_animation(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "audio"
            audio.mkdir()
            scenario = Path(tmp) / "latarnia.md"
            scenario.write_text(SMALL, encoding="utf-8")
            silence(audio / f"{key('Wiatr.')}.wav")
            import os
            os.environ["AP_GRA_AUDIO"] = str(audio)
            try:
                data = web.build(scenario, Path(tmp) / "web")
            finally:
                del os.environ["AP_GRA_AUDIO"]
            self.assertEqual((data["animation"], data["tile"], data["description"]), (None, None, ""))
            self.assertEqual(list(data["audio"]), ["Wiatr."])


class ScenarioJsonTest(unittest.TestCase):
    def test_the_scenario_as_data(self):
        data = web.scenario_json(parse(SMALL))
        self.assertEqual((data["title"], data["start"], data["endings"]),
                         ("Latarnia", "start", ["koniec_dobry", "koniec_zly"]))
        self.assertEqual(data["ending_labels"], ["Zakończenie pierwsze z dwóch.", "Zakończenie drugie z dwóch."])
        start = data["scenes"]["start"]
        self.assertEqual(start["paragraphs"][0][1], {"text": "Znowu tu jesteś.", "verse": False, "if": [["byl", True]]})
        self.assertTrue(start["paragraphs"][1][0]["verse"])
        self.assertEqual(start["options"][0], {"text": "Wejdź na górę", "target": "gora", "if": [],
                                               "set": ["odwaga"], "clear": []})
        self.assertEqual(start["set"], ["byl"])
        self.assertEqual(data["scenes"]["koniec_zly"]["ending"], "Cisza")


class PlaythroughsTest(unittest.TestCase):
    def test_every_ending_and_the_same_views_as_the_engine(self):
        scenario = parse(SMALL)
        paths = web.playthroughs(scenario, random_paths=5)
        reached = {p["views"][-1]["scene"] for p in paths[:2]}
        self.assertEqual(reached, {"koniec_dobry", "koniec_zly"})
        game = Game(scenario)
        for path in paths:
            view = game.start()
            for number, expected in zip(path["choices"], path["views"][1:]):
                view = game.choose(view["state"], number)
                self.assertEqual(web._plain(view), expected)
            self.assertEqual(path["continued"], path["views"][-1])
            self.assertNotIn("audio", json.dumps(path))

    def test_built_in_games_reach_all_their_endings(self):
        for path in sorted((ROOT / "scenariusz").glob("*.md")):
            scenario = load(path)
            endings = web._path_to_each_ending(Game(scenario))
            self.assertEqual(len(endings), len(scenario.endings), path.name)


if __name__ == "__main__":
    unittest.main()
