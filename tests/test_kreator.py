"""The game creator conversation (kreator/) with a fake AI - no internet,
no key, no cost. The AI work runs synchronously, so a test reads the state
right after an answer."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA = Path(tempfile.mkdtemp())
os.environ["AP_GRA_DATA"] = str(DATA)

from kreator.ai import AI, AIError  # noqa: E402
from engine.log import Log  # noqa: E402
from kreator.rozmowa import (BLAD, INNE_PROPOZYCJE, MYSLI, PODSUMOWANIE, PRZERWANA,  # noqa: E402
                             PYTANIE, ROZPOCZNIJ, ZATWIERDZONA, Conversation,
                             ConversationError, problems)

try:
    from fastapi.testclient import TestClient

    from kreator.app import app
except ImportError:
    TestClient = None


def question(text, *options):
    return {"pytanie": text, "opcje": list(options), "koniec": False, "tytul": "", "streszczenie": ""}


def summary(title, text):
    return {"pytanie": "", "opcje": [], "koniec": True, "tytul": title, "streszczenie": text}


def response(answer, stop_reason="end_turn"):
    text = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=120, output_tokens=40, cache_read_input_tokens=0),
        stop_reason=stop_reason, model="claude-opus-5-5", _request_id="req_test")


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


class FakeClient:
    """Gives the prepared answers in order; remembers what was sent. Like
    the SDK: client.beta.messages.stream(...) -> with ... as s: s.get_final_message()."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self.stream))

    def stream(self, **request):
        self.calls.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, SimpleNamespace):
            return FakeStream(answer)
        return FakeStream(response(answer))


Q1 = question("Jaką historię chcesz przeżyć?", "Kryminał", "Romans", "Przygoda")
Q2 = question("Gdzie toczy się akcja?", "Stary dworzec", "Latarnia morska")
Q2B = question("Gdzie toczy się akcja?", "Statek", "Zamek w górach", "Szpital")
S1 = summary("Latarnik", "Jesteś latarnikiem. W noc sztormu ktoś daje sygnały z morza.")
S2 = summary("Ostatni rejs", "Płyniesz statkiem. Ktoś zniknął z kabiny numer siedem.")


def conversation(*answers, narrator=None):
    client = FakeClient(*answers)
    directory = Path(tempfile.mkdtemp()) / "r1"
    c = Conversation(directory, AI(client=client), narrator=narrator, run=lambda work: work())
    return c, client


def kinds(c):
    return [e["rodzaj"] for e in c.log.entries()]


class ConversationTest(unittest.TestCase):
    def test_questions_summary_and_start(self):
        c, client = conversation(Q1, Q2, S1)
        c.start()
        view = c.view()
        self.assertEqual(view["status"], PYTANIE)
        self.assertEqual(view["tekst"], "Jaką historię chcesz przeżyć?")
        self.assertEqual([o["tekst"] for o in view["opcje"]], ["Kryminał", "Romans", "Przygoda", INNE_PROPOZYCJE])
        self.assertFalse(view["mozna_wrocic"])

        c.answer(1)
        self.assertEqual(c.view()["tekst"], "Gdzie toczy się akcja?")
        # The AI got the whole conversation: its question and the choice
        sent = client.calls[-1]["messages"]
        self.assertEqual(sent[-1], {"role": "user", "content": "Wybór: Kryminał"})
        self.assertEqual(json.loads(sent[-2]["content"])["pytanie"], "Jaką historię chcesz przeżyć?")
        self.assertEqual(client.calls[-1]["model"], "claude-opus-5-5")
        self.assertEqual(client.calls[-1]["output_config"]["format"]["type"], "json_schema")

        c.answer(2)
        view = c.view()
        self.assertEqual(view["status"], PODSUMOWANIE)
        self.assertEqual(view["tytul"], "Latarnik")
        self.assertTrue(view["tekst"].startswith("Latarnik\n\nJesteś latarnikiem."))
        self.assertEqual([o["tekst"] for o in view["opcje"]], [ROZPOCZNIJ, "Inny pomysł"])

        c.answer(1)
        self.assertEqual(c.view()["status"], ZATWIERDZONA)
        saved = json.loads((c.directory / "stan.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], ZATWIERDZONA)
        self.assertEqual(saved["kroki"][-1]["ai"]["tytul"], "Latarnik")

    def test_idea_for_making_the_game(self):
        c, client = conversation(Q1, Q2, Q2B, S1)
        c.start()
        with self.assertRaises(ConversationError):
            c.idea()  # not approved yet
        c.answer(1)  # Kryminał
        c.answer(3)  # Inne propozycje - not a choice
        c.answer(2)  # Zamek w górach
        c.answer(1)  # Rozpocznij
        self.assertEqual(c.idea(), {
            "tytul": "Latarnik", "streszczenie": S1["streszczenie"],
            "rozmowa": [{"pytanie": "Jaką historię chcesz przeżyć?", "odpowiedz": "Kryminał"},
                        {"pytanie": "Gdzie toczy się akcja?", "odpowiedz": "Zamek w górach"}]})

    def test_everything_is_logged(self):
        c, client = conversation(Q1, Q2)
        c.start()
        c.answer(2)
        c.back()
        c.stop()
        log = c.log.entries()
        self.assertEqual(kinds(c), ["start", "ai_zapytanie", "ai_odpowiedz", "pokazane",
                                    "odpowiedz_uzytkownika", "ai_zapytanie", "ai_odpowiedz", "pokazane",
                                    "wroc", "przerwij"])
        request = log[1]
        self.assertEqual(request["zapytanie"]["messages"], [{"role": "user", "content": "Zacznij rozmowę."}])
        self.assertIn("Pomagasz użytkownikowi", request["zapytanie"]["system"])
        answer = log[2]
        self.assertEqual(json.loads(answer["odpowiedz"]), Q1)
        self.assertEqual(answer["tokeny"], {"wejscie": 120, "wyjscie": 40, "z_pamieci": 0, "do_pamieci": None})
        self.assertEqual(answer["id_zapytania"], "req_test")
        self.assertEqual(log[4]["tekst"], "Romans")
        self.assertTrue(all("czas" in e for e in log))

    def test_back_does_not_ask_the_ai(self):
        c, client = conversation(Q1, Q2, Q2B)
        c.start()
        c.answer(1)
        self.assertTrue(c.view()["mozna_wrocic"])
        c.back()
        self.assertEqual(len(client.calls), 2)
        view = c.view()
        self.assertEqual(view["tekst"], "Jaką historię chcesz przeżyć?")
        self.assertFalse(view["mozna_wrocic"])
        # A different choice this time - the AI sees only this one
        c.answer(3)
        sent = client.calls[-1]["messages"]
        self.assertEqual([m["content"] for m in sent if m["role"] == "user"],
                         ["Zacznij rozmowę.", "Wybór: Przygoda"])

    def test_other_options_and_back_from_them(self):
        c, client = conversation(Q1, Q2, Q2B)
        c.start()
        c.answer(1)
        c.answer(3)  # "Inne propozycje" (2 options + this one)
        self.assertEqual(client.calls[-1]["messages"][-1]["content"], "Inne propozycje")
        self.assertEqual([o["tekst"] for o in c.view()["opcje"]][:3], ["Statek", "Zamek w górach", "Szpital"])
        c.back()  # the first set of options again
        self.assertEqual([o["tekst"] for o in c.view()["opcje"]], ["Stary dworzec", "Latarnia morska", INNE_PROPOZYCJE])

    def test_other_idea(self):
        c, client = conversation(Q1, S1, S2)
        c.start()
        c.answer(1)
        c.answer(2)  # "Inny pomysł"
        self.assertEqual(client.calls[-1]["messages"][-1]["content"], "Inny pomysł")
        self.assertEqual(c.view()["tytul"], "Ostatni rejs")
        c.back()
        self.assertEqual(c.view()["tytul"], "Latarnik")

    def test_bad_answer_is_corrected(self):
        too_many = question("Jaka historia?", "A", "B", "C", "D")
        c, client = conversation(too_many, Q1)
        c.start()
        self.assertEqual(c.view()["status"], PYTANIE)
        self.assertEqual(c.view()["tekst"], Q1["pytanie"])
        self.assertTrue(client.calls[1]["messages"][-1]["content"].startswith("Popraw: podaj 2 albo 3"))
        self.assertIn("odpowiedz_ai_odrzucona", kinds(c))

    def test_failure_then_back(self):
        bad = question("", "A", "B")
        c, client = conversation(Q1, bad, bad, bad)
        c.start()
        c.answer(1)
        view = c.view()
        self.assertEqual(view["status"], BLAD)
        self.assertEqual(view["opcje"], [])
        self.assertTrue(view["mozna_wrocic"])
        c.back()  # the question just answered, to choose again
        self.assertEqual(c.view()["tekst"], Q1["pytanie"])
        self.assertEqual(c.view()["status"], PYTANIE)

    def test_api_errors_and_refusal(self):
        c, client = conversation(ConnectionError("brak sieci"))
        c.start()
        self.assertEqual(c.view()["status"], BLAD)
        self.assertFalse(c.view()["mozna_wrocic"])
        self.assertIn("ai_blad", kinds(c))
        c, client = conversation(response(Q1, stop_reason="refusal"))
        c.start()
        self.assertEqual(c.view()["status"], BLAD)
        c, client = conversation("to nie jest JSON")
        c.start()
        self.assertEqual(c.view()["status"], BLAD)

    def test_late_answer_after_back_is_ignored(self):
        pending = []
        client = FakeClient(Q1, Q2)
        c = Conversation(Path(tempfile.mkdtemp()) / "r", AI(client=client), run=pending.append)
        c.start()
        pending.pop()()
        c.answer(1)
        self.assertEqual(c.view()["status"], MYSLI)
        self.assertTrue(c.view()["mozna_wrocic"])
        c.back()  # while the AI is working
        self.assertEqual(c.view()["tekst"], Q1["pytanie"])
        pending.pop()()  # the AI answers now - too late
        self.assertEqual(c.view()["tekst"], Q1["pytanie"])
        self.assertIn("odpowiedz_ai_pominieta", kinds(c))

    def test_wrong_requests(self):
        c, client = conversation(Q1)
        c.start()
        with self.assertRaises(ConversationError):
            c.answer(9)
        with self.assertRaises(ConversationError):
            c.back()
        c.stop()
        self.assertEqual(c.view()["status"], PRZERWANA)
        with self.assertRaises(ConversationError):
            c.answer(1)
        with self.assertRaises(ConversationError):
            c.stop()

    def test_problems(self):
        self.assertEqual(problems(Q1), [])
        self.assertEqual(problems(S1), [])
        self.assertTrue(problems(question("Pytanie?", "A")))
        self.assertTrue(problems(question("Pytanie?", "Tak", "tak")))
        self.assertTrue(problems(question("Pytanie?", "A", "x" * 46)))
        self.assertTrue(problems(question("Bardzo długie pytanie. " * 12, "A", "B")))
        self.assertTrue(problems(summary("", "Treść.")))
        self.assertTrue(problems(summary("Tytuł", "Zdanie numer jeden. " * 30)))


class RecordingsTest(unittest.TestCase):
    def test_question_recorded_before_it_is_shown(self):
        recorded = []

        class FakeNarrator:
            cache = Path(tempfile.mkdtemp())

            def recording(self, text):
                from engine import voice
                from tests.test_voice import write_wav

                path = self.cache / f"{voice.key(text)}.wav"
                write_wav(path, 0.5)
                recorded.append(text)
                return path

        c, client = conversation(Q1, narrator=FakeNarrator())
        c.start()
        self.assertIn("Jaką historię chcesz przeżyć?", recorded)
        view = c.view()
        self.assertEqual(view["audio"]["duration"], 0.5)
        self.assertTrue(all(o["audio"] for o in view["opcje"]))


class LogTest(unittest.TestCase):
    def test_lines_appended(self):
        log = Log(Path(tempfile.mkdtemp()) / "a" / "log.jsonl")
        log.write("jeden", x=1)
        log.write("dwa", tekst="zażółć")
        self.assertEqual([e["rodzaj"] for e in log.entries()], ["jeden", "dwa"])
        self.assertIn("zażółć", log.path.read_text(encoding="utf-8"))


@unittest.skipIf(TestClient is None, "brak fastapi / httpx (requirements-dev.txt)")
class KreatorApiTest(unittest.TestCase):
    def setUp(self):
        self.client_ai = FakeClient(Q1, Q2)
        app.state.ai = AI(client=self.client_ai)
        app.state.narrator = None
        app.state.run = lambda work: work()
        self.client = TestClient(app)

    def test_conversation(self):
        view = self.client.post("/v1/kreator/rozmowy").json()
        self.assertEqual(view["status"], PYTANIE)
        cid = view["id"]
        self.assertTrue((DATA / "rozmowy" / cid / "log.jsonl").exists())
        view = self.client.post(f"/v1/kreator/rozmowy/{cid}/odpowiedz", json={"opcja": 2}).json()
        self.assertEqual(view["tekst"], "Gdzie toczy się akcja?")
        self.assertEqual(self.client.get(f"/v1/kreator/rozmowy/{cid}").json(), view)
        view = self.client.post(f"/v1/kreator/rozmowy/{cid}/wroc").json()
        self.assertEqual(view["tekst"], Q1["pytanie"])
        response = self.client.post(f"/v1/kreator/rozmowy/{cid}/wroc")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.post(f"/v1/kreator/rozmowy/{cid}/odpowiedz",
                                          json={"opcja": 9}).status_code, 409)
        view = self.client.post(f"/v1/kreator/rozmowy/{cid}/przerwij").json()
        self.assertEqual(view["status"], PRZERWANA)

    def test_errors_and_health(self):
        self.assertEqual(self.client.get("/v1/kreator/rozmowy/nie_ma").status_code, 404)
        self.assertEqual(self.client.get("/v1/kreator/audio/abc.wav").status_code, 404)
        health = self.client.get("/v1/kreator/health").json()
        self.assertTrue(health["ok"])
        self.assertEqual(health["interface"]["wroc"], {"text": "Wróć", "audio": None})


class AiTest(unittest.TestCase):
    def test_request_shape(self):
        client = FakeClient(Q1)
        log = Log(Path(tempfile.mkdtemp()) / "log.jsonl")
        AI(client=client).ask(log, "test", "system", [{"role": "user", "content": "x"}], {"type": "object"})
        request = client.calls[0]
        self.assertEqual(request["fallbacks"], "default")
        self.assertEqual(request["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(request["output_config"]["effort"], "medium")
        self.assertNotIn("temperature", request)

    def test_text_after_a_fallback(self):
        # The first model stopped mid-answer, the fallback model answered again
        message = SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"pytanie": "Jaka'),
                     SimpleNamespace(type="fallback"),
                     SimpleNamespace(type="text", text=json.dumps(Q1, ensure_ascii=False))],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0),
            stop_reason="end_turn", model="claude-opus-4-8", _request_id="r")
        answer = AI(client=FakeClient(message)).ask(Log(Path(tempfile.mkdtemp()) / "l.jsonl"), "t", "s", [], {})
        self.assertEqual(answer, Q1)

    def test_game_settings(self):
        client = FakeClient(Q1)
        AI(client=client).ask(Log(Path(tempfile.mkdtemp()) / "l.jsonl"), "t", "s", [], {},
                              effort="high", max_tokens=64000)
        self.assertEqual(client.calls[0]["output_config"]["effort"], "high")
        self.assertEqual(client.calls[0]["max_tokens"], 64000)

    def test_cut_off_answer(self):
        client = FakeClient(response(Q1, stop_reason="max_tokens"))
        with self.assertRaises(AIError):
            AI(client=client).ask(Log(Path(tempfile.mkdtemp()) / "l.jsonl"), "t", "s", [], {})


if __name__ == "__main__":
    unittest.main()
