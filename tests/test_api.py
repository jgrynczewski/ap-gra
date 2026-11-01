"""HTTP API tests (needs requirements-dev.txt; skipped without fastapi)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import voice  # noqa: E402
from tests.test_voice import write_wav  # noqa: E402

# One fake recording (option 1 of the first scene), read when the app loads
AUDIO = tempfile.mkdtemp()
write_wav(Path(AUDIO) / f"{voice.key('Powiedz o tym Kubie')}.wav", 1.25)
os.environ["AP_GRA_AUDIO"] = AUDIO

try:
    from fastapi.testclient import TestClient

    from api.app import app
except ImportError:  # API dependencies not installed - engine tests still run
    TestClient = None


@unittest.skipIf(TestClient is None, "brak fastapi / httpx (requirements-dev.txt)")
class ApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        body = self.client.get("/v1/health").json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["title"], "Sala pod zegarem")

    def test_play_round_trip(self):
        view = self.client.post("/v1/start").json()
        self.assertEqual(view["scene"], "start")
        self.assertEqual(len(view["options"]), 4)
        # Kuba, then "Obróć wszystko w żart" - the reaction is in the next scene
        view = self.client.post("/v1/choose", json={"state": view["state"], "option": 1}).json()
        view = self.client.post("/v1/choose", json={"state": view["state"], "option": 2}).json()
        self.assertEqual(view["scene"], "radiowezel")
        self.assertIn("chichocze", view["text"])
        self.assertIn("zart", view["state"]["flags"])

    def test_audio(self):
        health = self.client.get("/v1/health").json()
        self.assertEqual(health["recordings"], 1)
        self.assertEqual(health["interface"]["powtorz"], {"text": "Powtórz", "audio": None})
        view = self.client.post("/v1/start").json()
        audio = view["options"][0]["audio"]
        self.assertEqual(audio["duration"], 1.25)
        self.assertIsNone(view["options"][1]["audio"])
        response = self.client.get(audio["url"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content[:4], b"RIFF")

    def test_errors(self):
        state = self.client.post("/v1/start").json()["state"]
        response = self.client.post("/v1/choose", json={"state": state, "option": 9})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Nie ma opcji", response.json()["error"])
        response = self.client.post("/v1/choose", json={"state": {"scene": "nie_ma"}, "option": 1})
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/v1/choose", json={"option": 1})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
