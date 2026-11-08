"""Kompan (kompan/) with a fake AI - no internet, no key, no cost. The AI work
runs synchronously, so a test reads the state right after an answer."""

import json
import os
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ["AP_KOMPAN_DATA"] = tempfile.mkdtemp()

from engine.log import Log  # noqa: E402
from kompan.koszty import Costs, cost  # noqa: E402
from kompan.rozmowa import (BLAD, BLISKO, FIXED, INNE_PROPOZYCJE, LIMIT, MYSLI, PYTANIE,  # noqa: E402
                            WINDOW_KEEP, WINDOW_MAX, ZMIEN_TEMAT, ConversationError, Kompan,
                            problems, stamp)
from kreator.ai import AI  # noqa: E402
from test_kreator import FakeClient, response  # noqa: E402

try:
    from fastapi.testclient import TestClient

    from kompan.app import app
except ImportError:
    TestClient = None


def said(text, *options, title="Mecz"):
    return {"wypowiedz": text, "opcje": list(options), "tytul_rozmowy": title}


A1 = said("Cześć. Oglądałeś wczoraj mecz?", "Tak, cały", "Tylko końcówkę", "Nie")
A2 = said("I jak było?", "Świetnie", "Słabo")
A3 = said("Co poszło nie tak?", "Obrona", "Sędzia", "Pogoda", "Wszystko")
SUMMARY = {"streszczenie": "Rozmawiali o meczu."}


def make(*answers, limit=5.0, narrator=None, data=None, now=None):
    client = FakeClient(*answers)
    data = data or Path(tempfile.mkdtemp())
    kwargs = {"costs": Costs(data / "koszty.jsonl", limit, now)} if now else {"limit": limit}
    return Kompan(data, AI(client=client), narrator=narrator, run=lambda work: work(), **kwargs), client


def kinds(conversation):
    return [e["rodzaj"] for e in conversation.log.entries()]


def texts(buttons):
    return [b["tekst"] for b in buttons]


class ConversationTest(unittest.TestCase):
    def test_answers_and_fixed_buttons(self):
        kompan, _ = make(A1)
        view = kompan.new().view()
        self.assertEqual(view["status"], PYTANIE)
        self.assertEqual(view["tekst"], A1["wypowiedz"])
        self.assertEqual(view["tytul"], "Mecz")
        self.assertEqual(texts(view["opcje"]), A1["opcje"])
        self.assertEqual(texts(view["stale"]), FIXED)
        # One numbering across both groups
        self.assertEqual([b["numer"] for b in view["opcje"] + view["stale"]], [1, 2, 3, 4, 5, 6])
        self.assertFalse(view["mozna_wrocic"])

    def test_choice_goes_to_the_ai_with_the_time(self):
        kompan, client = make(A1, A2)
        conversation = kompan.new()
        conversation.answer(2)
        self.assertEqual(conversation.view()["tekst"], "I jak było?")
        messages = client.calls[1]["messages"]
        self.assertIn("Zacznij nową rozmowę.", messages[0]["content"])
        self.assertEqual(json.loads(messages[1]["content"]), A1)
        last = messages[2]["content"][0]["text"]
        self.assertTrue(last.endswith("Wybór: Tylko końcówkę"), last)
        self.assertTrue(last.startswith("("), last)

    def test_fixed_buttons_go_to_the_ai_by_name(self):
        for button, number in ((BLISKO, 4), (INNE_PROPOZYCJE, 5), (ZMIEN_TEMAT, 6)):
            kompan, client = make(A1, A2)
            conversation = kompan.new()
            conversation.answer(number)
            last = client.calls[1]["messages"][-1]["content"][0]["text"]
            self.assertTrue(last.endswith(") " + button), last)

    def test_the_log_has_question_all_options_and_choice(self):
        kompan, _ = make(A1, A2)
        conversation = kompan.new()
        conversation.answer(1)
        entries = conversation.log.entries()
        shown = next(e for e in entries if e["rodzaj"] == "pokazane")
        self.assertEqual(shown["tekst"], A1["wypowiedz"])
        self.assertEqual(shown["opcje"], A1["opcje"] + FIXED)
        chosen = next(e for e in entries if e["rodzaj"] == "odpowiedz_uzytkownika")
        self.assertEqual(chosen["tekst"], "Tak, cały")

    def test_wrong_requests(self):
        kompan, _ = make(A1)
        conversation = kompan.new()
        with self.assertRaises(ConversationError):
            conversation.answer(7)
        with self.assertRaises(ConversationError):
            conversation.back()  # the first question

    def test_back_does_not_ask_the_ai(self):
        kompan, client = make(A1, A2)
        conversation = kompan.new()
        conversation.answer(1)
        self.assertTrue(conversation.view()["mozna_wrocic"])
        conversation.back()
        self.assertEqual(conversation.view()["tekst"], A1["wypowiedz"])
        self.assertEqual(len(client.calls), 2)

    def test_answer_after_back_is_dropped(self):
        kompan, client = make(A1, A2)
        works = []
        kompan.run = works.append
        conversation = kompan.new()
        works.pop()()
        conversation.answer(1)
        self.assertEqual(conversation.status, MYSLI)
        conversation.back()
        works.pop()()  # the AI answers after WRÓĆ
        self.assertEqual(conversation.view()["tekst"], A1["wypowiedz"])
        self.assertIn("odpowiedz_ai_pominieta", kinds(conversation))

    def test_bad_answer_is_corrected(self):
        kompan, client = make(said("Dwa? Pytania?", "Tak", "Nie"), A1)
        conversation = kompan.new()
        self.assertEqual(conversation.view()["tekst"], A1["wypowiedz"])
        self.assertIn("jedno pytanie", client.calls[1]["messages"][-1]["content"])
        self.assertIn("odpowiedz_ai_odrzucona", kinds(conversation))

    def test_ai_failure_and_coming_back(self):
        kompan, _ = make(RuntimeError("awaria"), A1)
        conversation = kompan.new()
        self.assertEqual(conversation.status, BLAD)
        self.assertEqual(conversation.view()["opcje"], [])
        conversation.come_back()
        self.assertEqual(conversation.view()["tekst"], A1["wypowiedz"])

    def test_leaving_changes_nothing(self):
        kompan, client = make(A1)
        conversation = kompan.new()
        before = conversation.view()
        conversation.leave()
        conversation.come_back()
        self.assertEqual(conversation.view(), before)
        self.assertEqual(len(client.calls), 1)
        self.assertLess(kinds(conversation).index("wyjscie"), kinds(conversation).index("powrot"))


class ProblemsTest(unittest.TestCase):
    def test_good(self):
        self.assertEqual(problems(A1), [])
        self.assertEqual(problems(A3), [])

    def test_bad(self):
        cases = [
            said("", "A", "B"),
            said("x " * 300, "A", "B"),
            said("Jeden? Dwa?", "A", "B"),
            said("Co?", "A"),
            said("Co?", "A", "B", "C", "D", "E"),
            said("Co?", "A", "a"),
            said("Co?", "A", "y" * 61),
            said("Co?", "A", "Zmień temat"),
            said("Co?", "A", "B", title=""),
        ]
        for case in cases:
            self.assertTrue(problems(case), case)


class WhatTheAIKnowsTest(unittest.TestCase):
    def test_start_notes_and_cache(self):
        kompan, client = make(A1)
        (kompan.data / "notatki_startowe.txt").write_text("Lubi Legię.", encoding="utf-8")
        kompan.new()
        system = client.calls[0]["system"]
        self.assertIn("Jesteś Kompan", system[0]["text"])
        self.assertIn("Lubi Legię.", system[1]["text"])
        self.assertEqual(system[1]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(client.calls[0]["messages"][-1]["content"][0]["cache_control"], {"type": "ephemeral"})

    def test_nothing_known(self):
        kompan, client = make(A1)
        kompan.new()
        self.assertIn("Jeszcze nic.", client.calls[0]["system"][1]["text"])

    def test_prompt_uses_no_banned_words(self):
        kompan, client = make(A1)
        kompan.new()
        prompt = client.calls[0]["system"][0]["text"].lower()
        for word in ("opiekun", "niepełnospraw"):
            self.assertNotIn(word, prompt)

    def test_new_conversation_folds_the_old_one_first(self):
        kompan, client = make(A1, A2, SUMMARY, A3)
        old = kompan.new()
        old.answer(1)
        new = kompan.new()
        self.assertEqual(new.view()["tekst"], A3["wypowiedz"])
        self.assertEqual(old.folded, 1)
        self.assertEqual(kompan.summary(), "Rozmawiali o meczu.")
        self.assertIn("Wybór: Tak, cały", client.calls[2]["messages"][0]["content"])
        # The new conversation knows the summary and not the old messages
        self.assertIn("Rozmawiali o meczu.", client.calls[3]["system"][1]["text"])
        self.assertEqual(len(client.calls[3]["messages"]), 1)

    def test_summary_failure_does_not_stop_the_conversation(self):
        kompan, client = make(A1, A2, RuntimeError("awaria"), A3)
        old = kompan.new()
        old.answer(1)
        new = kompan.new()
        self.assertEqual(new.view()["status"], PYTANIE)
        self.assertEqual(old.folded, 0)
        self.assertEqual(kompan.summary(), "")

    def test_long_conversation_keeps_a_window(self):
        count = WINDOW_MAX + 1
        # The first question and answers to count - 1 choices, then the fold, then the last answer
        kompan, client = make(*[A2] * count, SUMMARY, A1)
        conversation = kompan.new()
        for _ in range(count):
            conversation.answer(1)
        self.assertEqual(conversation.folded, count - WINDOW_KEEP)
        self.assertEqual(conversation.view()["tekst"], A1["wypowiedz"])
        request = client.calls[-1]
        self.assertEqual(request["messages"][0]["content"], "Wcześniejsza część tej rozmowy jest w streszczeniu.")
        # Opening + WINDOW_KEEP answers of the AI + the same number of choices
        self.assertEqual(len(request["messages"]), 1 + 2 * WINDOW_KEEP)
        self.assertEqual(request["messages"][1]["role"], "assistant")
        self.assertEqual(request["messages"][-1]["role"], "user")


class RestartTest(unittest.TestCase):
    def test_conversation_survives_a_restart(self):
        kompan, _ = make(A1, A2)
        old = kompan.new()
        old.answer(1)
        again, client = make(A3, data=kompan.data)
        found = again.latest()
        self.assertEqual(found.id, old.id)
        self.assertEqual(found.view()["tekst"], A2["wypowiedz"])
        found.answer(1)
        self.assertEqual(found.view()["tekst"], A3["wypowiedz"])
        self.assertEqual(len(client.calls[0]["messages"]), 5)

    def test_restart_in_the_middle_of_the_ai_work(self):
        kompan, _ = make(A1)
        old = kompan.new()
        works = []
        kompan.run = works.append
        old.answer(1)  # the AI never answers - the service stops
        self.assertEqual(old.status, MYSLI)
        again, _ = make(A2, data=kompan.data)
        found = again.get(old.id)
        self.assertEqual(found.status, MYSLI)
        found.come_back()
        self.assertEqual(found.view()["tekst"], A2["wypowiedz"])

    def test_come_back_while_the_ai_works_does_not_ask_twice(self):
        kompan, client = make(A1, A2)
        conversation = kompan.new()
        works = []
        kompan.run = works.append
        conversation.answer(1)
        conversation.come_back()
        self.assertEqual(len(works), 1)

    def test_state_can_be_read_during_the_summary(self):
        # AP asks for the state every second; the summary may take a long time
        kompan, _ = make(A1, A2, A3)
        conversation = kompan.new()
        conversation.answer(1)
        results = []

        def ask(*args, **kwargs):
            thread = threading.Thread(target=lambda: results.append(kompan.get(conversation.id).view()))
            thread.start()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive(), "reading the state waits for the AI")
            return SUMMARY

        kompan.ai.ask = ask
        kompan.fold(conversation, 1)
        self.assertEqual(len(results), 1)

    def test_no_conversation_to_go_back_to(self):
        kompan, _ = make()
        self.assertIsNone(kompan.latest())


USAGE = SimpleNamespace(input_tokens=1000, output_tokens=500, cache_creation_input_tokens=2000,
                        cache_read_input_tokens=10000)


class CostsTest(unittest.TestCase):
    def test_cost_of_an_answer(self):
        # Opus 5.5: 4 + 10 + 10 + 2 (USD per million, in thousandths)
        self.assertAlmostEqual(cost("claude-opus-5-5", USAGE), 0.004 + 0.010 + 0.010 + 0.002)

    def test_unknown_model_counts_high(self):
        self.assertGreater(cost("inny-model", USAGE), cost("claude-opus-5-5", USAGE))

    def test_usage_without_cache_fields(self):
        self.assertAlmostEqual(cost("claude-opus-5-5", SimpleNamespace(input_tokens=1000, output_tokens=0)), 0.004)

    def test_every_ai_answer_is_counted(self):
        kompan, _ = make(A1, A2)
        conversation = kompan.new()
        conversation.answer(1)
        # Fake answers: 120 in, 40 out, on Opus 5.5
        self.assertAlmostEqual(kompan.costs.today(), 2 * (120 * 4 + 40 * 20) / 1_000_000)

    def test_limit_stops_and_keeps_the_conversation(self):
        kompan, client = make(A1, A2, limit=0.001)
        conversation = kompan.new()
        self.assertEqual(conversation.status, PYTANIE)
        conversation.answer(1)
        self.assertEqual(conversation.status, LIMIT)
        self.assertEqual(len(client.calls), 1)
        self.assertIn("limit_dzienny", kinds(conversation))
        # WRÓĆ still works and shows the question
        conversation.back()
        self.assertEqual(conversation.view()["tekst"], A1["wypowiedz"])

    def test_limit_resets_the_next_day(self):
        today = [datetime(2026, 11, 8, 20, 0, tzinfo=timezone.utc)]
        kompan, _ = make(A1, A2, limit=0.001, now=lambda: today[0])
        conversation = kompan.new()
        conversation.answer(1)
        self.assertEqual(conversation.status, LIMIT)
        conversation.come_back()  # still today
        self.assertEqual(conversation.status, LIMIT)
        today[0] += timedelta(days=1)
        # The log has the real time of the entry, so count it as "yesterday"
        lines = kompan.costs.log.entries()
        kompan.costs.log.path.unlink()
        log = Log(kompan.costs.log.path)
        for line in lines:
            with open(log.path, "a", encoding="utf-8") as f:
                f.write(json.dumps({**line, "czas": "2026-11-08T20:00:00+00:00"}) + "\n")
        conversation.come_back()
        self.assertEqual(conversation.view()["tekst"], A2["wypowiedz"])


class StampTest(unittest.TestCase):
    def test_polish_time_and_day(self):
        self.assertEqual(stamp(datetime(2026, 11, 8, 17, 40, tzinfo=timezone.utc)), "(niedziela 08.11.2026, 18:40)")


@unittest.skipIf(TestClient is None, "no fastapi")
class ApiTest(unittest.TestCase):
    def setUp(self):
        self.kompan, self.client_ai = make(A1, A2, A3)
        self.old = app.state.kompan
        app.state.kompan = self.kompan
        self.api = TestClient(app)

    def tearDown(self):
        app.state.kompan = self.old

    def test_whole_flow(self):
        health = self.api.get("/v1/kompan/health").json()
        self.assertTrue(health["ok"])
        self.assertIsNone(health["ostatnia"])
        self.assertIn("zmien_temat", health["interface"])

        view = self.api.post("/v1/kompan/rozmowy").json()
        cid = view["id"]
        self.assertEqual(view["status"], PYTANIE)
        view = self.api.post(f"/v1/kompan/rozmowy/{cid}/odpowiedz", json={"opcja": 1}).json()
        self.assertEqual(view["tekst"], A2["wypowiedz"])
        view = self.api.post(f"/v1/kompan/rozmowy/{cid}/wroc").json()
        self.assertEqual(view["tekst"], A1["wypowiedz"])
        self.assertEqual(self.api.get(f"/v1/kompan/rozmowy/{cid}").json()["tekst"], A1["wypowiedz"])
        self.api.post(f"/v1/kompan/rozmowy/{cid}/wyjscie")
        self.api.post(f"/v1/kompan/rozmowy/{cid}/powrot")

        latest = self.api.get("/v1/kompan/health").json()["ostatnia"]
        self.assertEqual(latest["id"], cid)
        self.assertEqual(latest["etykieta"], "Wróć do rozmowy: Mecz")

    def test_errors(self):
        self.assertEqual(self.api.get("/v1/kompan/rozmowy/nie-ma").status_code, 404)
        self.assertEqual(self.api.get("/v1/kompan/rozmowy/..%2F..").status_code, 404)
        self.assertEqual(self.api.get("/v1/kompan/audio/nie-ma.wav").status_code, 404)
        cid = self.api.post("/v1/kompan/rozmowy").json()["id"]
        response_ = self.api.post(f"/v1/kompan/rozmowy/{cid}/odpowiedz", json={"opcja": 99})
        self.assertEqual(response_.status_code, 409)


if __name__ == "__main__":
    unittest.main()
