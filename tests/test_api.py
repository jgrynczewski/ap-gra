"""HTTP API tests (needs requirements-dev.txt; skipped without fastapi)."""

import os
import shutil
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
# User games (dane/gry/<id>/) - empty at start, tests add games while the app runs
DATA = Path(tempfile.mkdtemp())
os.environ["AP_GRA_DATA"] = str(DATA)

USER_GAME = """# Wieża
## start
Stoisz pod wieżą.
* Wejdź -> szczyt
* Odejdź -> dom
## szczyt
Widać całe miasto.
> koniec: Na szczycie
## dom
Wracasz do domu.
> koniec: Powrót
"""

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


@unittest.skipIf(TestClient is None, "brak fastapi / httpx (requirements-dev.txt)")
class PlaysTest(unittest.TestCase):
    """Playthroughs logged by the server, numbers by tools/statystyki.py."""

    def test_log_and_statistics(self):
        import io
        from contextlib import redirect_stdout

        import api.app as api_app
        from engine.log import Log
        from tools import statystyki

        add_user_game("wieza_stat")
        client = TestClient(app)
        params = {"game": "wieza_stat"}
        first = client.post("/v1/start", params=params).json()
        play = first["state"]["rozgrywka"]
        ended = client.post("/v1/choose", params=params, json={"state": first["state"], "option": 1}).json()
        self.assertEqual(ended["state"]["rozgrywka"], play)
        second = client.post("/v1/start", params=params).json()
        self.assertNotEqual(second["state"]["rozgrywka"], play)
        client.post("/v1/choose", params=params, json={"state": second["state"], "option": 1})
        # A save from before the log: continued, gets an id
        old = client.post("/v1/view", params=params, json={"state": {"scene": "start", "flags": []}}).json()
        self.assertTrue(old["state"]["rozgrywka"])
        client.post("/v1/choose", params=params, json={"state": old["state"], "option": 2})

        entries = Log(api_app.PLAYS / "wieza_stat.jsonl").entries()
        self.assertEqual([e["rodzaj"] for e in entries],
                         ["start", "wybor", "zakonczenie", "start", "wybor", "zakonczenie",
                          "kontynuacja", "wybor", "zakonczenie"])
        self.assertEqual(entries[1]["tekst"], "Wejdź")
        self.assertEqual((entries[1]["scena"], entries[1]["cel"]), ("start", "szczyt"))
        self.assertEqual(entries[2]["tytul"], "Na szczycie")
        self.assertTrue(entries[6]["stary_zapis"])

        numbers = statystyki.stats(entries, {"szczyt": "Na szczycie", "dom": "Powrót", "las": "W lesie"})
        self.assertEqual((numbers["rozgrywki"], numbers["ukonczone"], numbers["kontynuacje"],
                          numbers["odkryte"]), (2, 3, 1, 2))
        by_id = {e["id"]: e for e in numbers["zakonczenia"]}
        self.assertEqual(by_id["szczyt"]["razy"], 2)
        self.assertEqual(by_id["szczyt"]["pierwszy_raz"], entries[2]["czas"])
        self.assertEqual(by_id["las"]["razy"], 0)
        # The text report, in Polish time
        statystyki.DATA = DATA
        out = io.StringIO()
        with redirect_stdout(out):
            statystyki.main(["wieza_stat"])
        text = out.getvalue()
        self.assertIn("== Wieża (wieza_stat)", text)
        self.assertIn("odkryte 2 z 2", text)
        self.assertIn("Na szczycie - 2 razy", text)
        self.assertIn("Powrót - 1 raz", text)

    def test_choices_of_the_default_game_are_logged(self):
        import api.app as api_app
        from engine.log import Log

        client = TestClient(app)
        view = client.post("/v1/start").json()
        client.post("/v1/choose", json={"state": view["state"], "option": 1})
        entries = Log(api_app.PLAYS / "sala_pod_zegarem.jsonl").entries()
        self.assertIn(view["state"]["rozgrywka"], {e["rozgrywka"] for e in entries})


def add_user_game(game_id: str, text: str = USER_GAME) -> Path:
    directory = DATA / "gry" / game_id
    (directory / "audio").mkdir(parents=True)
    (directory / "scenariusz.md").write_text(text, encoding="utf-8")
    return directory


@unittest.skipIf(TestClient is None, "brak fastapi / httpx (requirements-dev.txt)")
class UserGamesTest(unittest.TestCase):
    """Games from dane/gry/ - they appear and disappear without a restart."""

    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(shutil.rmtree, DATA / "gry", ignore_errors=True)

    def ids(self):
        return {g["id"]: g for g in self.client.get("/v1/games").json()["games"]}

    def test_new_game_without_restart(self):
        self.assertNotIn("wieza", self.ids())
        directory = add_user_game("wieza")
        write_wav(directory / "audio" / f"{voice.key('Wejdź')}.wav", 0.5)
        games = self.ids()
        self.assertEqual(games["wieza"]["title"], "Wieża")
        self.assertEqual(games["wieza"]["endings"], 2)
        self.assertFalse(games["wieza"]["builtin"])
        self.assertTrue(games["sala_pod_zegarem"]["builtin"])

        params = {"game": "wieza"}
        view = self.client.post("/v1/start", params=params).json()
        self.assertEqual(view["scene"], "start")
        audio = view["options"][0]["audio"]
        self.assertEqual(audio["url"], f"/v1/gry/wieza/audio/{voice.key('Wejdź')}.wav")
        response = self.client.get(audio["url"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content[:4], b"RIFF")
        view = self.client.post("/v1/choose", params=params,
                                json={"state": view["state"], "option": 1}).json()
        self.assertEqual(view["ending"]["title"], "Na szczycie")

        shutil.rmtree(directory)
        self.assertNotIn("wieza", self.ids())
        self.assertEqual(self.client.post("/v1/start", params=params).status_code, 404)

    def test_changed_scenario_is_read_again(self):
        directory = add_user_game("wieza")
        self.assertEqual(self.ids()["wieza"]["title"], "Wieża")
        scenario = directory / "scenariusz.md"
        scenario.write_text(USER_GAME.replace("# Wieża", "# Stara wieża"), encoding="utf-8")
        stat = scenario.stat()
        os.utime(scenario, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        self.assertEqual(self.ids()["wieza"]["title"], "Stara wieża")

    def test_broken_and_unfinished_games_skipped(self):
        add_user_game("dobra")
        add_user_game("zepsuta", "bez tytułu")
        add_user_game("w_trakcie.tmp")
        (DATA / "gry" / "bez_scenariusza").mkdir()
        # A user game cannot replace a built-in one
        add_user_game("sala_pod_zegarem")
        games = self.ids()
        self.assertIn("dobra", games)
        for skipped in ("zepsuta", "w_trakcie.tmp", "bez_scenariusza"):
            self.assertNotIn(skipped, games)
        self.assertEqual(games["sala_pod_zegarem"]["title"], "Sala pod zegarem")

    def test_audio_names_checked(self):
        add_user_game("wieza")
        for url in ("/v1/gry/wieza/audio/scenariusz.md", "/v1/gry/wieza/audio/abc.wav",
                    "/v1/gry/nie_ma/audio/abc.wav", "/v1/gry/..%2F..%2Fetc/audio/abc.wav"):
            self.assertEqual(self.client.get(url).status_code, 404, url)


if __name__ == "__main__":
    unittest.main()
