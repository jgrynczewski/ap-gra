"""Animation of user games (rysownik/, kreator step "animacja"): the code is
really run in a separate process with limits, like in ap-gra-rysownik; the
AI is fake."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_kreator import FakeClient  # noqa: E402 - also sets AP_GRA_DATA
from tests.test_tworzenie import IDEA, OK, OUTLINE, scenario  # noqa: E402

try:
    import PIL  # noqa: F401

    from kreator.ai import AI
    from kreator.rysowanie import Painter
    from kreator.tworzenie import GOTOWA, Workshop
    from rysownik import klatki, serwis, zapasowy
except ImportError:  # Pillow not installed - run in the container
    PIL = None

MOVING = '''import math
import random

STARS = [(random.Random(7).random(), i / 10) for i in range(8)]

def rysuj(d, t, w, h):
    d.rectangle([0, 0, w, h], fill="#14213D")
    for x, y in STARS:
        d.ellipse([x * w, y * h, x * w + w * 0.02, y * h + w * 0.02], fill="#FFFFFF")
    x = w * (0.5 + 0.3 * math.sin(2 * math.pi * t))
    d.ellipse([x - w * 0.06, h * 0.5, x + w * 0.06, h * 0.62], fill="#FF6B6B")
'''
STILL = MOVING.replace("math.sin(2 * math.pi * t)", "0")
EMPTY = 'def rysuj(d, t, w, h):\n    d.rectangle([0, 0, w, h], fill="#14213D")\n'
BROKEN = 'def rysuj(d, t, w, h):\n    return 1 / 0\n'


def job(code, attempt=1):
    directory = Path(tempfile.mkdtemp()) / "t1"
    directory.mkdir()
    (directory / "kod.py").write_text(code, encoding="utf-8")
    (directory / "zlecenie.json").write_text(json.dumps({"proba": attempt}), encoding="utf-8")
    return directory


@unittest.skipIf(PIL is None, "brak Pillow (requirements.txt)")
class CodeProblemsTest(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(klatki.code_problems(MOVING), [])
        self.assertIn("import os", klatki.code_problems("import os\n" + MOVING)[0])
        self.assertTrue(klatki.code_problems("from pathlib import Path\n" + MOVING))
        self.assertTrue(klatki.code_problems(MOVING + "\nopen('x')\n"))
        self.assertTrue(klatki.code_problems(MOVING + "\n().__class__\n"))
        self.assertTrue(klatki.code_problems(MOVING + "\n__builtins__\n"))
        self.assertEqual(klatki.code_problems("x = 1\n"), ["brak funkcji rysuj(d, t, w, h)"])
        self.assertTrue(klatki.code_problems("def rysuj(:\n")[0].startswith("błąd składni"))


@unittest.skipIf(PIL is None, "brak Pillow (requirements.txt)")
class ServiceTest(unittest.TestCase):
    def test_good_animation(self):
        directory = job(MOVING, attempt=2)
        result = serwis.run_job(directory)
        self.assertEqual(result, {"proba": 2, "ok": True, "problemy": []})
        frames = sorted((directory / "klatki").glob("*.png"))
        self.assertEqual(len(frames), klatki.FRAMES)
        from PIL import Image

        with Image.open(frames[0]) as first:
            self.assertEqual(first.size, (klatki.WIDTH, klatki.HEIGHT))
        self.assertEqual(json.loads((directory / "wynik.json").read_text(encoding="utf-8")), result)
        self.assertEqual(serwis.pending(directory.parent), [])

    def test_problems_go_back_to_the_ai(self):
        error = serwis.run_job(job(BROKEN))["problemy"][0]
        self.assertIn("ZeroDivisionError", error)
        self.assertIn("rysunek.py", error)
        self.assertNotIn("/app/rysownik", error)  # only the AI's own code
        self.assertIn("nic się nie rusza", serwis.run_job(job(STILL))["problemy"][-1])
        self.assertIn("prawie pusta", serwis.run_job(job(EMPTY))["problemy"][0])
        self.assertIn("import os", serwis.run_job(job("import os\n" + MOVING))["problemy"][0])

    def test_limits(self):
        endless = 'def rysuj(d, t, w, h):\n    while True:\n        pass\n'
        self.assertIn("dłużej niż", serwis.run_job(job(endless), timeout=3)["problemy"][0])
        greedy = 'def rysuj(d, t, w, h):\n    x = bytearray(3_000_000_000)\n'
        self.assertIn("MemoryError", serwis.run_job(job(greedy))["problemy"][0])

    def test_still_picture(self):
        out = Path(tempfile.mkdtemp())
        klatki.render(zapasowy.rysuj, out, frames=1)
        self.assertEqual(klatki.code_problems(Path(zapasowy.__file__).read_text(encoding="utf-8")), [])
        from PIL import Image

        with Image.open(out / "0000.png") as picture:
            self.assertIsNone(picture.getcolors(maxcolors=16))  # not empty
            rgb = picture.convert("RGB")
            white = [x for x in range(klatki.WIDTH) for y in range(klatki.HEIGHT)
                     if rgb.getpixel((x, y)) == (255, 255, 255)]
            self.assertEqual(white, [])  # the background is covered everywhere


def workshop(*answers, painter="local"):
    data = Path(tempfile.mkdtemp())
    if painter == "local":  # the job is run here, the same way as by the service
        painter = Painter(data / "rysownik", run_job=serwis.run_job)
    client = FakeClient(*answers)
    return Workshop(data, AI(client=client), run=lambda work: work(), painter=painter), client, data


@unittest.skipIf(PIL is None, "brak Pillow (requirements.txt)")
class AnimationStepTest(unittest.TestCase):
    def test_animation_in_the_game(self):
        w, client, data = workshop(OUTLINE, scenario(), OK, {"kod": BROKEN}, {"kod": MOVING})
        task = w.add("t1", IDEA)
        self.assertEqual(task.view()["status"], GOTOWA)
        game = data / "gry" / "gt1"
        self.assertEqual(len(list((game / "animacja").glob("*.png"))), klatki.FRAMES)
        self.assertEqual((game / "kafelek.png").read_bytes(), (game / "animacja" / "0000.png").read_bytes())
        self.assertEqual((game / "rysunek.py").read_text(encoding="utf-8"), MOVING)
        info = json.loads((game / "gra.json").read_text(encoding="utf-8"))["animacja"]
        self.assertEqual(info, {"fps": 12, "klatki": klatki.FRAMES, "szerokosc": klatki.WIDTH,
                                "wysokosc": klatki.HEIGHT, "zapasowa": False})
        # The error went back to the AI, with the idea and the outline at the start
        self.assertTrue(client.calls[3]["system"].startswith("Piszesz kod"))
        self.assertIn("Zarys:", client.calls[3]["messages"][0]["content"])
        correction = client.calls[4]["messages"][-1]["content"]
        self.assertTrue(correction.startswith("Popraw:"))
        self.assertIn("ZeroDivisionError", correction)
        self.assertIn("animacja_odrzucona", [e["rodzaj"] for e in task.log.entries()])

    def test_failed_animation_gives_the_still_picture(self):
        w, client, data = workshop(OUTLINE, scenario(), OK, {"kod": BROKEN}, {"kod": BROKEN}, {"kod": EMPTY})
        task = w.add("t1", IDEA)
        self.assertEqual(task.view()["status"], GOTOWA)
        game = data / "gry" / "gt1"
        self.assertEqual(len(list((game / "animacja").glob("*.png"))), 1)
        self.assertTrue((game / "kafelek.png").exists())
        self.assertFalse((game / "rysunek.py").exists())
        self.assertTrue(json.loads((game / "gra.json").read_text(encoding="utf-8"))["animacja"]["zapasowa"])
        self.assertIn("animacja_zapasowa", [e["rodzaj"] for e in task.log.entries()])

    def test_no_drawing_service(self):
        data = Path(tempfile.mkdtemp())
        painter = Painter(data / "rysownik", wait=0.2, poll=0.05)  # nobody runs the jobs
        w, client, _ = workshop(OUTLINE, scenario(), OK, {"kod": MOVING}, painter=painter)
        task = w.add("t1", IDEA)
        self.assertEqual(task.view()["status"], GOTOWA)
        self.assertEqual(len(client.calls), 4)  # the code was asked for once, not three times
        self.assertTrue(json.loads((task.directory / "animacja.json").read_text(encoding="utf-8"))["zapasowa"])


if __name__ == "__main__":
    unittest.main()
