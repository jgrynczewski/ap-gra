"""Making a game (kreator/tworzenie.py) with a fake AI - no internet, no key,
no cost. The work runs synchronously, so a test reads the result right away."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_kreator import Q1, S1, FakeClient, TestClient  # noqa: E402 - also sets AP_GRA_DATA

from engine import voice  # noqa: E402
from engine.scenario import load  # noqa: E402
from kreator.ai import AI  # noqa: E402
from kreator.tworzenie import (GOTOWA, NIEUDANA, W_TOKU, Workshop, game_id,  # noqa: E402
                               scenario_problems)

TITLE = "Latarnik"
IDEA = {"tytul": TITLE, "streszczenie": "Jesteś latarnikiem. W noc sztormu ktoś daje sygnały z morza.",
        "rozmowa": [{"pytanie": "Jaką historię chcesz przeżyć?", "odpowiedz": "Przygoda"}]}
OUTLINE = {"zarys": "Latarnia na skale, sztorm. Gracz - latarnik. Trzy zakończenia."}
OK = {"ok": True, "uwagi": []}


def scenario(title=TITLE, scenes=18, text="Wiatr wyje za oknem."):
    """A scenario that passes the checks: a line of scenes, then 3 endings."""
    normal = scenes - 3
    lines = [f"# {title}", ""]
    for i in range(1, normal + 1):
        lines += [f"## s{i}", f"Scena {i}. {text}", ""]
        if i < normal:
            lines += [f"* Idź schodami w górę -> s{i + 1}", f"* Zejdź na dół -> s{i + 1}", ""]
        else:
            lines += ["* Zapal lampę -> k1", "* Wypłyń łodzią -> k2", "* Czekaj do rana -> k3", ""]
    for k in range(1, 4):
        lines += [f"## k{k}", "Sztorm cichnie.", "", f"> koniec: Zakończenie {k}", ""]
    return {"scenariusz": "\n".join(lines)}


BROKEN = {"scenariusz": f"# {TITLE}\n\n## a\nTekst.\n\n* Dalej -> nie_ma\n"}


def workshop(*answers, narrator=None):
    client = FakeClient(*answers)
    data = Path(tempfile.mkdtemp())
    return Workshop(data, AI(client=client), narrator, run=lambda work: work()), client, data


def kinds(task):
    return [e["rodzaj"] for e in task.log.entries()]


class ScenarioProblemsTest(unittest.TestCase):
    def test_good(self):
        found, parsed = scenario_problems(scenario()["scenariusz"], TITLE)
        self.assertEqual(found, [])
        self.assertEqual(len(parsed.scenes), 18)

    def test_problems(self):
        self.assertIn("pierwsza linia ma brzmieć: # Latarnik",
                      scenario_problems(scenario(title="Inny")["scenariusz"], TITLE)[0])
        self.assertTrue(any("scen jest 10" in p for p in scenario_problems(scenario(scenes=10)["scenariusz"], TITLE)[0]))
        self.assertTrue(any("nieistniejącej sceny" in p for p in scenario_problems(BROKEN["scenariusz"], TITLE)[0]))
        self.assertTrue(scenario_problems("bez tytułu", TITLE)[0][0].startswith("błąd formatu"))
        long_option = scenario()["scenariusz"].replace("Zejdź na dół", "Zejdź " + "bardzo " * 10 + "nisko")
        self.assertTrue(any("opcja dłuższa" in p for p in scenario_problems(long_option, TITLE)[0]))
        too_long = scenario(text="Bardzo długie zdanie o morzu i latarni. " * 20)["scenariusz"]
        self.assertTrue(any("tekst za długi" in p for p in scenario_problems(too_long, TITLE)[0]))


class TaskTest(unittest.TestCase):
    def test_whole_game(self):
        w, client, data = workshop(OUTLINE, BROKEN, scenario(), OK)
        task = w.add("20261108-120000-ab12", IDEA)
        self.assertEqual(task.view()["status"], GOTOWA)
        game = data / "gry" / game_id(task.id)
        self.assertEqual(game.name, "g20261108_120000_ab12")
        self.assertEqual(load(game / "scenariusz.md").title, TITLE)
        info = json.loads((game / "gra.json").read_text(encoding="utf-8"))
        self.assertEqual(info["tytul"], TITLE)
        self.assertEqual(info["rozmowa"], task.id)
        self.assertFalse((data / "gry" / f"{game.name}.tmp").exists())
        # The scenario with errors went back to the AI with them
        self.assertEqual([c["system"].split()[0] for c in client.calls], ["Piszesz", "Piszesz", "Piszesz", "Sprawdzasz"])
        correction = client.calls[2]["messages"][-1]["content"]
        self.assertTrue(correction.startswith("Popraw:"))
        self.assertIn("nie_ma", correction)
        # The idea and the outline reached the writer
        self.assertIn("Zarys:", client.calls[1]["messages"][0]["content"])
        self.assertIn("Przygoda", client.calls[1]["messages"][0]["content"])
        # Writing the game: more thinking, longer answers
        self.assertTrue(all(c["output_config"]["effort"] == "high" and c["max_tokens"] == 64000
                            for c in client.calls))
        # Everything in the log of the conversation, a copy in the game
        log = kinds(task)
        for kind in ("tworzenie_zlecone", "ai_zapytanie", "ai_odpowiedz", "scenariusz_odrzucony",
                     "publikacja", "tworzenie_gotowe"):
            self.assertIn(kind, log)
        self.assertEqual(task.log.path, data / "rozmowy" / task.id / "log.jsonl")
        self.assertIn("scenariusz_odrzucony", (game / "rozmowa.jsonl").read_text(encoding="utf-8"))

    def test_story_check_fixes_the_scenario(self):
        fixed = scenario(text="Fale biją o skały.")
        w, client, data = workshop(OUTLINE, scenario(), {"ok": False, "uwagi": ["s3: latarnik nie może znać imienia"]},
                                   fixed)
        task = w.add("t1", IDEA)
        self.assertEqual(task.view()["status"], GOTOWA)
        self.assertIn("Fale biją", (data / "gry" / "gt1" / "scenariusz.md").read_text(encoding="utf-8"))
        self.assertTrue(client.calls[3]["messages"][-1]["content"].startswith("Popraw fabułę:"))

    def test_failed_story_fix_keeps_the_checked_scenario(self):
        notes = {"ok": False, "uwagi": ["za mało napięcia"]}
        w, client, data = workshop(OUTLINE, scenario(), notes, BROKEN, BROKEN, BROKEN)
        task = w.add("t1", IDEA)
        self.assertEqual(task.view()["status"], GOTOWA)
        self.assertIn("Wiatr wyje", (data / "gry" / "gt1" / "scenariusz.md").read_text(encoding="utf-8"))
        self.assertIn("kontrola_pominieta", kinds(task))

    def test_failure(self):
        w, client, data = workshop(OUTLINE, BROKEN, BROKEN, BROKEN)
        task = w.add("t1", IDEA)
        self.assertEqual(task.view()["status"], NIEUDANA)
        self.assertEqual(task.view()["krok"], "scenariusz")
        self.assertFalse((data / "gry").exists())
        self.assertIn("tworzenie_nieudane", kinds(task))
        w, client, data = workshop(ConnectionError("brak sieci"))
        self.assertEqual(w.add("t2", IDEA).view()["status"], NIEUDANA)

    def test_resume_after_restart(self):
        data = Path(tempfile.mkdtemp())
        # Before the restart: the outline and the scenario were done
        before = Workshop(data, AI(client=FakeClient(OUTLINE, scenario())), run=lambda work: None)
        task = before.add("t1", IDEA)
        task._zarys()
        task._scenariusz()
        self.assertEqual(task.view()["status"], W_TOKU)
        # After: only the story check is asked for, the rest goes on
        client = FakeClient(OK)
        after = Workshop(data, AI(client=client), run=lambda work: work())
        self.assertEqual(after.resume(), 1)
        self.assertEqual(after.get("t1").view()["status"], GOTOWA)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(after.resume(), 0)

    def test_same_conversation_twice(self):
        w, client, data = workshop(OUTLINE, scenario(), OK)
        w.add("t1", IDEA)
        w.add("t1", IDEA)
        self.assertEqual(len(client.calls), 3)
        self.assertEqual([v["id"] for v in w.views()], ["t1"])

    def test_leftover_of_an_interrupted_publication(self):
        w, client, data = workshop(OUTLINE, scenario(), OK)
        leftover = data / "gry" / "gt1.tmp"
        leftover.mkdir(parents=True)
        (leftover / "scenariusz.md").write_text("pół gry", encoding="utf-8")
        w.add("t1", IDEA)
        self.assertFalse(leftover.exists())
        self.assertEqual(load(data / "gry" / "gt1" / "scenariusz.md").title, TITLE)


class RecordingsTest(unittest.TestCase):
    def test_recordings_go_into_the_game(self):
        from tests.test_voice import write_wav

        class FakeNarrator:
            def record_all(self, texts, out):
                out.mkdir(parents=True, exist_ok=True)
                for text in texts:
                    write_wav(out / f"{voice.key(text)}.wav", 0.2)

        w, client, data = workshop(OUTLINE, scenario(), OK, narrator=FakeNarrator())
        w.add("t1", IDEA)
        audio = data / "gry" / "gt1" / "audio"
        self.assertEqual(len(list(audio.glob("*.wav"))), len(voice.texts(load(data / "gry" / "gt1" / "scenariusz.md"))))

    def test_no_recordings_is_not_a_failure(self):
        class BrokenNarrator:
            def record_all(self, texts, out):
                raise RuntimeError("Piper nie działa")

        w, client, data = workshop(OUTLINE, scenario(), OK, narrator=BrokenNarrator())
        task = w.add("t1", IDEA)
        self.assertEqual(task.view()["status"], GOTOWA)
        result = json.loads((task.directory / "nagrania.json").read_text(encoding="utf-8"))
        self.assertIn("Piper nie działa", result["blad"])
        self.assertIn("blad_nagrania", kinds(task))


@unittest.skipIf(TestClient is None, "brak fastapi / httpx (requirements-dev.txt)")
class ApiTest(unittest.TestCase):
    def test_start_makes_the_game(self):
        import kreator.app as kreator_app

        app = kreator_app.app
        ai = AI(client=FakeClient(Q1, S1, OUTLINE, scenario(), OK))
        app.state.ai, app.state.narrator, app.state.run = ai, None, (lambda work: work())
        app.state.workshop = Workshop(kreator_app.DATA, ai, run=lambda work: work())
        client = TestClient(app)
        cid = client.post("/v1/kreator/rozmowy").json()["id"]
        client.post(f"/v1/kreator/rozmowy/{cid}/odpowiedz", json={"opcja": 1})  # Kryminał -> S1
        view = client.post(f"/v1/kreator/rozmowy/{cid}/odpowiedz", json={"opcja": 1}).json()  # Rozpocznij
        self.assertEqual(view["status"], "zatwierdzona")
        made = client.get(f"/v1/kreator/gry/{cid}").json()
        self.assertEqual((made["status"], made["tytul"], made["gra"]), (GOTOWA, TITLE, game_id(cid)))
        self.assertIn(made, client.get("/v1/kreator/gry").json()["gry"])
        self.assertTrue((kreator_app.DATA / "gry" / game_id(cid) / "scenariusz.md").exists())
        self.assertEqual(client.get("/v1/kreator/gry/nie-ma").status_code, 404)
        self.assertEqual(client.get("/v1/kreator/gry/..").status_code, 404)
        health = client.get("/v1/kreator/health").json()
        self.assertEqual(health["interface"]["nieudana"]["text"], "Nie udało się stworzyć tej gry.")


if __name__ == "__main__":
    unittest.main()
