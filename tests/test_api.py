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

    def test_view_continues_saved_game(self):
        view = self.client.post("/v1/start").json()
        view = self.client.post("/v1/choose", json={"state": view["state"], "option": 1}).json()
        again = self.client.post("/v1/view", json={"state": view["state"]}).json()
        self.assertEqual(again, view)
        response = self.client.post("/v1/view", json={"state": {"scene": "nie_ma", "flags": []}})
        self.assertEqual(response.status_code, 400)

    def test_games(self):
        body = self.client.get("/v1/games").json()
        self.assertEqual(body["default"], "sala_pod_zegarem")
        ids = {g["id"]: g for g in body["games"]}
        self.assertEqual(ids["ostatnia_zwrotka"]["title"], "Ostatnia zwrotka")
        self.assertEqual(ids["ostatnia_zwrotka"]["endings"], 9)
        health = self.client.get("/v1/health", params={"game": "ostatnia_zwrotka"}).json()
        self.assertEqual(health["title"], "Ostatnia zwrotka")

    def test_second_game_round_trip(self):
        params = {"game": "ostatnia_zwrotka"}
        view = self.client.post("/v1/start", params=params).json()
        self.assertIn("Bigos", view["text"])
        view = self.client.post("/v1/choose", params=params,
                                json={"state": view["state"], "option": 2}).json()
        self.assertEqual(view["scene"], "bigos")
        again = self.client.post("/v1/view", params=params, json={"state": view["state"]}).json()
        self.assertEqual(again, view)
        # The state of one game is not a state of the other
        response = self.client.post("/v1/view", json={"state": view["state"]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post("/v1/start", params={"game": "nie_ma"}).status_code, 404)

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
