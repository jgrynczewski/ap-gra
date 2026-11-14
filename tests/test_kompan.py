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
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ["AP_KOMPAN_DATA"] = tempfile.mkdtemp()

from kompan.koszty import Costs, cost  # noqa: E402
from kompan.notatki import GUESS, POSTPONE, REVIEW_AT, USER  # noqa: E402
from kompan.rozmowa import (ALL_GOOD, ANYONE_ELSE, BLAD, BLISKO, DONT_SEND, FIX, FIXED, GOOD,  # noqa: E402
                            INNE_PROPOZYCJE, LIMIT, MORE_PEOPLE, MYSLI, NOBODY, NOT_NOW, PRZEGLAD,
                            PRZEKAZ, PYTANIE, REST_GOOD, SEND, SOMETHING_WRONG, THATS_ALL, WINDOW_KEEP,
                            WINDOW_MAX, WRONG, ZMIEN_TEMAT, ConversationError, Kompan, problems,
                            review_text, stamp)
from kompan.wiadomosci import SENT, WAITING, Gmail  # noqa: E402
from kreator.ai import AI  # noqa: E402
from test_kreator import FakeClient, response  # noqa: E402

try:
    from fastapi.testclient import TestClient

    from kompan.app import app
except ImportError:
    TestClient = None


def said(text, *options, title="Mecz", notes=(), review=False, message=None):
    """message: (question, text, [names]) - a proposal to pass something on."""
    ask, body, names = message or ("", "", [])
    return {"wypowiedz": text, "opcje": list(options), "tytul_rozmowy": title,
            "zapamietaj": [{"tekst": t, "skad": s} for t, s in notes], "pora_na_przeglad": review,
            "przekaz": {"pytanie": ask, "tresc": body, "dla": list(names)}}


A1 = said("Cześć. Oglądałeś wczoraj mecz?", "Tak, cały", "Tylko końcówkę", "Nie")
A2 = said("I jak było?", "Świetnie", "Słabo")
A3 = said("Co poszło nie tak?", "Obrona", "Sędzia", "Pogoda", "Wszystko")
SUMMARY = {"streszczenie": "Rozmawiali o meczu."}


def make(*answers, limit=5.0, narrator=None, data=None, now=None, send=None):
    client = FakeClient(*answers)
    data = data or Path(tempfile.mkdtemp())
    kwargs = {"costs": Costs(data / "koszty.jsonl", limit, now)} if now else {"limit": limit}
    return Kompan(data, AI(client=client), narrator=narrator, run=lambda work: work(), send=send,
                  **kwargs), client


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
        self.assertIn("jedno pytanie", client.calls[1]["messages"][-1]["content"][0]["text"])
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
            said("Co?", "A", "B", notes=[("x", USER)] * 4),
            said("Co?", "A", "B", notes=[("x" * 81, USER)]),
            said("Co?", "A", "B", notes=[(" ", GUESS)]),
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
        self.assertIn("Jeszcze nic.", client.calls[0]["messages"][-1]["content"][-1]["text"])

    def test_notes_are_after_the_cache_point(self):
        # A new note must not change the cached part (system and earlier messages)
        kompan, client = make(said("Legia?", "Tak", "Nie", notes=[("Kibicujesz Legii.", USER)]), A2)
        kompan.new().answer(1)
        first, second = client.calls
        self.assertEqual(first["system"], second["system"])
        self.assertNotIn("- Kibicujesz", json.dumps(second["system"], ensure_ascii=False))
        cached, notes = second["messages"][-1]["content"]
        self.assertIn("cache_control", cached)
        self.assertNotIn("cache_control", notes)
        self.assertIn("- Kibicujesz Legii.", notes["text"])
        # The earlier messages carry no notes, so they match what was cached before
        self.assertEqual(second["messages"][0]["content"], first["messages"][0]["content"][0]["text"])

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


FIVE = [(f"Wpis {n}.", GUESS if n % 2 else USER) for n in range(1, 6)]


class Recorder:
    """A narrator that only notes what it was asked to record."""

    def __init__(self):
        self.cache = Path(tempfile.mkdtemp())
        self.texts = []

    def recording(self, text):
        self.texts.append(text)
        return self.cache / "x.wav"


class MemoryTest(unittest.TestCase):
    def review(self, *after, narrator=None):
        """Five new entries (three from earlier, two now) and the AI saying it is a good moment."""
        kompan, client = make(said("A co u Ciebie?", "Dobrze", "Źle", notes=FIVE[3:], review=True), *after,
                              narrator=narrator)
        kompan.notes.add([{"tekst": t, "skad": s} for t, s in FIVE[:3]], "wczesniej")
        return kompan, client, kompan.new()

    def test_entries_are_saved_with_their_source(self):
        kompan, client = make(said("Legia?", "Tak", "Nie", notes=[("Kibicujesz Legii.", USER),
                                                                  ("Masz brata.", GUESS)]), A2)
        conversation = kompan.new()
        entries = kompan.notes.entries()
        self.assertEqual([(e["tekst"], e["skad"]) for e in entries],
                         [("Kibicujesz Legii.", USER), ("Masz brata.", GUESS)])
        self.assertEqual(entries[0]["rozmowa"], conversation.id)
        self.assertIn("zapamietane", kinds(conversation))
        conversation.answer(1)
        known = client.calls[1]["messages"][-1]["content"][-1]["text"]
        self.assertIn("- Kibicujesz Legii.\n", known)
        self.assertIn("- Masz brata. (przypuszczenie)", known)

    def test_repeats_are_not_saved_and_versions_are_kept(self):
        kompan, _ = make(said("A?", "B", "C", notes=[("Kibicujesz Legii.", USER)]),
                         said("A?", "B", "C", notes=[("kibicujesz legii.", GUESS), ("Masz psa.", USER)]))
        conversation = kompan.new()
        conversation.answer(1)
        self.assertEqual([e["tekst"] for e in kompan.notes.entries()], ["Kibicujesz Legii.", "Masz psa."])
        self.assertEqual(len(list((kompan.data / "notatki-wersje").iterdir())), 1)

    def test_the_ai_hears_when_entries_wait(self):
        kompan, client, conversation = self.review(A2, A3)
        conversation.answer(3)  # Nie teraz
        conversation.answer(1)
        self.assertNotIn("przegląd", client.calls[1]["messages"][-1]["content"][0]["text"])
        kompan.notes.now = lambda: datetime.now(timezone.utc) + POSTPONE
        conversation.answer(1)
        self.assertTrue(client.calls[2]["messages"][-1]["content"][0]["text"].endswith(
            f"(Wpisów czekających na przegląd: {REVIEW_AT})"))

    def test_review_needs_the_ai_and_enough_entries(self):
        kompan, _ = make(said("A?", "B", "C", notes=FIVE[:3], review=True))
        self.assertEqual(kompan.new().status, PYTANIE)  # 3 entries
        kompan, _ = make(said("A?", "B", "C", notes=FIVE[3:]))
        kompan.notes.add([{"tekst": t, "skad": s} for t, s in FIVE[:3]], "wczesniej")
        self.assertEqual(kompan.new().status, PYTANIE)  # the AI did not say it is a good moment

    def test_review_all_good(self):
        kompan, client, conversation = self.review()
        view = conversation.view()
        self.assertEqual(view["status"], PRZEGLAD)
        self.assertEqual(view["tekst"], review_text([t for t, _ in FIVE]))
        self.assertEqual(texts(view["opcje"]), [ALL_GOOD, SOMETHING_WRONG, NOT_NOW])
        self.assertEqual(view["stale"], [])
        self.assertFalse(view["mozna_wrocic"])
        with self.assertRaises(ConversationError):
            conversation.back()
        conversation.answer(1)
        self.assertEqual(conversation.view()["tekst"], "A co u Ciebie?")
        self.assertTrue(all(e["potwierdzony"] for e in kompan.notes.entries()))
        self.assertEqual(len(client.calls), 1)  # the review never asks the AI
        self.assertIn("przeglad_koniec", kinds(conversation))

    def test_review_one_by_one(self):
        kompan, _, conversation = self.review()
        conversation.answer(2)  # Coś jest źle
        view = conversation.view()
        self.assertEqual(view["tekst"], "Zapamiętałem: Wpis 1.")
        self.assertEqual(texts(view["opcje"]), [GOOD, WRONG, REST_GOOD])
        conversation.answer(1)  # Dobrze
        conversation.answer(2)  # To nieprawda, usuń - Wpis 2
        self.assertEqual(conversation.view()["tekst"], "Zapamiętałem: Wpis 3.")
        conversation.answer(3)  # Reszta jest dobra
        self.assertEqual(conversation.status, PYTANIE)
        entries = kompan.notes.entries()
        self.assertEqual([e["tekst"] for e in entries], ["Wpis 1.", "Wpis 3.", "Wpis 4.", "Wpis 5."])
        self.assertTrue(all(e["potwierdzony"] for e in entries))
        self.assertIn("Wpis 2.", kompan.notes.for_ai().split("nieprawda")[1])
        self.assertIn("wpis_usuniety", kinds(conversation))

    def test_review_last_entry_and_removing_it(self):
        kompan, _, conversation = self.review()
        conversation.answer(2)
        for _ in range(4):
            conversation.answer(1)
        view = conversation.view()
        self.assertEqual(view["tekst"], "Zapamiętałem: Wpis 5.")
        self.assertEqual(texts(view["opcje"]), [GOOD, WRONG])  # nothing left after it
        conversation.answer(2)
        self.assertEqual(conversation.status, PYTANIE)
        self.assertEqual(len(kompan.notes.entries()), 4)

    def test_not_now_waits(self):
        kompan, _, conversation = self.review()
        conversation.answer(3)
        self.assertEqual(conversation.status, PYTANIE)
        self.assertFalse(kompan.notes.review_due())
        kompan.notes.now = lambda: datetime.now(timezone.utc) + POSTPONE
        self.assertTrue(kompan.notes.review_due())

    def test_review_is_recorded_before_it_is_shown(self):
        kompan, _, conversation = self.review(narrator=Recorder())
        self.assertEqual(conversation.status, PRZEGLAD)
        recorded = kompan.narrator.texts
        self.assertIn(review_text([t for t, _ in FIVE]), recorded)
        self.assertIn("Zapamiętałem: Wpis 3.", recorded)
        self.assertIn("Wpis 5.", recorded)  # for CO O MNIE WIESZ

    def test_review_survives_a_restart(self):
        kompan, _, conversation = self.review()
        conversation.answer(2)
        again, _ = make(data=kompan.data)
        found = again.get(conversation.id)
        self.assertEqual(found.view()["tekst"], "Zapamiętałem: Wpis 1.")

    def test_dropped_answer_saves_nothing(self):
        kompan, client = make(A1, said("A?", "B", "C", notes=[("Masz psa.", USER)]))
        works = []
        kompan.run = works.append
        conversation = kompan.new()
        works.pop()()
        conversation.answer(1)
        conversation.back()
        works.pop()()
        self.assertEqual(kompan.notes.entries(), [])


class Mailbox:
    """A fake Gmail: remembers the mails; can be switched off (no internet)."""

    def __init__(self):
        self.mails = []
        self.down = False

    def __call__(self, to, subject, body):
        if self.down:
            raise OSError("brak sieci")
        self.mails.append((to, subject, body))


PEOPLE = ["Jurek", "Mama", "Tata"]
LEKI = ("To ważna sprawa. Przekazać komuś, że leki dostajesz za późno?",
        "Radek mówi, że leki dostaje z dużym opóźnieniem.", ["Mama"])


def people(data, *names, user="Radek"):
    (data / "osoby.json").write_text(json.dumps({"uzytkownik": user, "osoby": [
        {"imie": n, "kto": "", "email": f"{n.lower()}@example.com", "wiadomosci": True} for n in names]}),
        encoding="utf-8")


class MessagesTest(unittest.TestCase):
    def flow(self, *after, names=PEOPLE, message=LEKI):
        """The AI's first answer proposes passing something on."""
        mailbox = Mailbox()
        data = Path(tempfile.mkdtemp())
        people(data, *names)
        kompan, client = make(said("Coś jeszcze?", "Tak", "Nie", message=message), *after,
                              data=data, send=mailbox)
        return kompan, client, mailbox, kompan.new()

    def test_without_mail_nothing_is_proposed(self):
        data = Path(tempfile.mkdtemp())
        people(data, *PEOPLE)
        kompan, client = make(said("Coś jeszcze?", "Tak", "Nie", message=LEKI), data=data)
        conversation = kompan.new()
        self.assertEqual(conversation.status, PYTANIE)
        self.assertIn("Lista jest pusta", client.calls[0]["system"][1]["text"])

    def test_the_ai_knows_who_is_on_the_list(self):
        _, client, _, _ = self.flow()
        self.assertIn("- Jurek", client.calls[0]["system"][1]["text"])
        self.assertNotIn("@", client.calls[0]["system"][1]["text"])  # never the addresses

    def test_choose_send(self):
        kompan, client, mailbox, conversation = self.flow(A2)
        view = conversation.view()
        self.assertEqual(view["status"], PRZEKAZ)
        self.assertEqual(view["tekst"], LEKI[0])
        self.assertEqual(texts(view["opcje"]), ["Mama", "Jurek", "Tata", NOBODY])  # the AI's choice first
        self.assertEqual(view["stale"], [])
        self.assertFalse(view["mozna_wrocic"])
        conversation.answer(1)  # Mama
        view = conversation.view()
        self.assertEqual((view["tekst"], texts(view["opcje"])), (ANYONE_ELSE, ["Jurek", "Tata", THATS_ALL]))
        conversation.answer(1)  # Jurek
        conversation.answer(2)  # To wszystko
        view = conversation.view()
        self.assertTrue(view["tekst"].startswith("Wiadomość dla: Mama, Jurek\n\n" + LEKI[1]), view["tekst"])
        self.assertEqual(texts(view["opcje"]), [SEND, FIX, DONT_SEND])
        conversation.answer(1)  # Wyślij
        self.assertEqual([m[0] for m in mailbox.mails], ["mama@example.com", "jurek@example.com"])
        to, subject, body = mailbox.mails[0]
        self.assertEqual(subject, "Radek przekazuje przez Kompana")
        self.assertIn(LEKI[1], body)
        self.assertIn("prosimy na nią nie odpowiadać", body)
        # Now the AI's own question; the AI hears what happened with the next choice
        self.assertEqual(conversation.view()["tekst"], "Coś jeszcze?")
        conversation.answer(1)
        self.assertIn("przekazana do wysyłki, do: Mama, Jurek",
                      client.calls[1]["messages"][-1]["content"][0]["text"])
        self.assertIn("wiadomosc_do_wysylki", kinds(conversation))

    def test_nobody(self):
        kompan, client, mailbox, conversation = self.flow(A2)
        conversation.answer(4)  # Nikomu
        self.assertEqual(conversation.status, PYTANIE)
        conversation.answer(1)
        self.assertEqual(mailbox.mails, [])
        self.assertIn("Nic nie zostało wysłane", client.calls[1]["messages"][-1]["content"][0]["text"])

    def test_the_only_person_goes_straight_to_the_confirmation(self):
        _, _, _, conversation = self.flow(names=["Mama"])
        conversation.answer(1)
        self.assertEqual(texts(conversation.view()["opcje"]), [SEND, FIX, DONT_SEND])

    def test_fix_asks_the_ai_and_keeps_the_people(self):
        better = ("Przekazać to?", "Radek mówi, że leki dostaje za późno, czasem o godzinę.", ["Mama"])
        kompan, client, mailbox, conversation = self.flow(
            said("Co poprawić?", "Za mało szczegółów", "Coś jest nieprawdą"),
            said("Dobrze.", "OK", "Dalej", message=better))
        conversation.answer(2)  # Jurek
        conversation.answer(3)  # To wszystko
        conversation.answer(2)  # Popraw
        self.assertIn("Popraw wiadomość.", client.calls[1]["messages"][-1]["content"][0]["text"])
        self.assertEqual(conversation.view()["tekst"], "Co poprawić?")
        conversation.answer(1)
        view = conversation.view()
        self.assertTrue(view["tekst"].startswith("Wiadomość dla: Jurek\n\n" + better[1]), view["tekst"])
        conversation.answer(1)
        self.assertEqual([m[0] for m in mailbox.mails], ["jurek@example.com"])

    def test_more_people_than_fit(self):
        names = ["A", "B", "C", "D", "E"]
        _, _, _, conversation = self.flow(names=names, message=(LEKI[0], LEKI[1], []))
        pages = []
        for _ in range(4):
            options = texts(conversation.view()["opcje"])
            pages.append(options)
            conversation.answer(options.index(MORE_PEOPLE) + 1)
        self.assertEqual(pages, [["A", "B", MORE_PEOPLE, NOBODY], ["C", "D", MORE_PEOPLE, NOBODY],
                                 ["E", MORE_PEOPLE, NOBODY], ["A", "B", MORE_PEOPLE, NOBODY]])

    def test_failed_send_waits_and_the_ai_hears_once(self):
        kompan, client, mailbox, conversation = self.flow(A2, A3, A1)
        mailbox.down = True
        conversation.answer(1)  # Mama
        conversation.answer(3)  # To wszystko
        conversation.answer(1)  # Wyślij
        self.assertEqual([m["stan"] for m in kompan.outbox.waiting()], [WAITING])
        conversation.answer(1)
        self.assertIn("Nie udało się wysłać wiadomości do: Mama",
                      client.calls[1]["messages"][-1]["content"][0]["text"])
        conversation.answer(1)
        self.assertNotIn("Nie udało się", client.calls[2]["messages"][-1]["content"][0]["text"])
        mailbox.down = False
        kompan.outbox.send_waiting()  # the service retries every few minutes
        self.assertEqual(len(mailbox.mails), 1)
        conversation.answer(1)
        self.assertIn("w końcu została wysłana", client.calls[3]["messages"][-1]["content"][0]["text"])
        self.assertEqual([m["stan"] for m in kompan.outbox._all()], [SENT])

    def test_a_new_conversation_hears_about_waiting_messages(self):
        kompan, client, mailbox, conversation = self.flow(A1)
        mailbox.down = True
        conversation.answer(1)
        conversation.answer(3)
        conversation.answer(1)
        new = kompan.new()
        self.assertIn("Wciąż nie udało się wysłać wiadomości do: Mama", new.opening)

    def test_the_flow_survives_a_restart(self):
        kompan, _, mailbox, conversation = self.flow()
        conversation.answer(1)
        again, _ = make(data=kompan.data, send=mailbox)
        view = again.get(conversation.id).view()
        self.assertEqual((view["status"], view["tekst"]), (PRZEKAZ, ANYONE_ELSE))

    def test_every_screen_is_recorded_before_it_is_shown(self):
        recorder = Recorder()
        data = Path(tempfile.mkdtemp())
        people(data, *PEOPLE)
        kompan, _ = make(said("Coś jeszcze?", "Tak", "Nie", message=LEKI), data=data, send=Mailbox(),
                         narrator=recorder)
        conversation = kompan.new()
        self.assertIn(LEKI[0], recorder.texts)
        self.assertTrue(set(PEOPLE) <= set(recorder.texts))
        conversation.answer(1)
        conversation.answer(3)  # To wszystko
        self.assertEqual(recorder.texts[-1], conversation.view()["tekst"])

    def test_slow_sending_does_not_hold_the_conversation(self):
        release = threading.Event()
        kompan, _, mailbox, conversation = self.flow(A2)
        kompan.outbox.run = lambda work: threading.Thread(target=work, daemon=True).start()
        kompan.outbox.send = lambda *mail: release.wait(5)  # no internet: a long timeout
        conversation.answer(1)
        conversation.answer(3)
        conversation.answer(1)  # Wyślij - the sending hangs
        done = threading.Event()
        threading.Thread(target=lambda: (conversation.answer(1), done.set()), daemon=True).start()
        self.assertTrue(done.wait(2), "the answer waits for the sending")
        release.set()

    def test_gmail(self):
        sent = []

        class FakeSMTP:
            def __init__(self, host, port, timeout):
                sent.append((host, port))

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def login(self, user, password):
                sent.append((user, password))

            def send_message(self, mail):
                sent.append((mail["From"], mail["To"], mail["Subject"], mail.get_content()))

        with mock.patch("kompan.wiadomosci.smtplib.SMTP_SSL", FakeSMTP):
            Gmail("kompan@gmail.com", "haslo")("mama@example.com", "Temat", "Treść")
        self.assertEqual(sent, [("smtp.gmail.com", 465), ("kompan@gmail.com", "haslo"),
                                ("kompan@gmail.com", "mama@example.com", "Temat", "Treść\n")])
        self.assertFalse(Gmail("", "").configured())

    def test_bad_osoby_json(self):
        data = Path(tempfile.mkdtemp())
        (data / "osoby.json").write_text("{zepsuty", encoding="utf-8")
        kompan, _ = make(data=data, send=Mailbox())
        self.assertEqual(kompan.message_people(), [])
        self.assertTrue(kompan.people.problem())

    def test_bad_proposals(self):
        cases = [
            said("A?", "B", "C", message=("Bez pytania.", "Treść.", [])),
            said("A?", "B", "C", message=("Jedno? Dwa?", "Treść.", [])),
            said("A?", "B", "C", message=("Przekazać?", "x" * 251, [])),
            said("A?", "B", "C", message=("Przekazać?", "Treść.", ["Zosia"])),
        ]
        for case in cases:
            self.assertTrue(problems(case, PEOPLE), case)
            self.assertEqual(problems(case), [], case)  # nobody to send to - ignored
        self.assertEqual(problems(said("A?", "B", "C", message=LEKI), PEOPLE), [])


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
        # The log has the real time of an entry, so "today" is the real day
        start = datetime.now(timezone.utc)
        today = [start]
        kompan, _ = make(A1, A2, limit=0.001, now=lambda: today[0])
        conversation = kompan.new()
        conversation.answer(1)
        self.assertEqual(conversation.status, LIMIT)
        conversation.come_back()  # still today
        self.assertEqual(conversation.status, LIMIT)
        today[0] += timedelta(days=1)
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
        self.assertIn("wyslij", health["interface"])
        self.assertEqual((health["poczta"], health["osoby"], health["wiadomosci_czekaja"]), (False, [], 0))

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

    def test_notes(self):
        self.kompan.notes.add([{"tekst": "Kibicujesz Legii.", "skad": USER},
                               {"tekst": "Masz psa.", "skad": GUESS}], "c")
        self.assertEqual(self.api.get("/v1/kompan/health").json()["notatki"], 2)
        entries = self.api.get("/v1/kompan/notatki").json()["wpisy"]
        self.assertEqual([(e["tekst"], e["przypuszczenie"]) for e in entries],
                         [("Kibicujesz Legii.", False), ("Masz psa.", True)])
        left = self.api.post(f"/v1/kompan/notatki/{entries[1]['id']}/usun").json()["wpisy"]
        self.assertEqual([e["tekst"] for e in left], ["Kibicujesz Legii."])
        self.assertEqual(self.api.post(f"/v1/kompan/notatki/{entries[1]['id']}/usun").status_code, 404)
        self.assertEqual(self.api.post("/v1/kompan/notatki/..%2F/usun").status_code, 404)

    def test_errors(self):
        self.assertEqual(self.api.get("/v1/kompan/rozmowy/nie-ma").status_code, 404)
        self.assertEqual(self.api.get("/v1/kompan/rozmowy/..%2F..").status_code, 404)
        self.assertEqual(self.api.get("/v1/kompan/audio/nie-ma.wav").status_code, 404)
        cid = self.api.post("/v1/kompan/rozmowy").json()["id"]
        response_ = self.api.post(f"/v1/kompan/rozmowy/{cid}/odpowiedz", json={"opcja": 99})
        self.assertEqual(response_.status_code, 409)


if __name__ == "__main__":
    unittest.main()
