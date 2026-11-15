"""Kompan's correspondence (stage 5) with a fake AI, a fake Gmail and mails
made here - no internet, no key, no cost."""

import email
import json
import sys
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.screen import text_lines  # noqa: E402
from kompan.poczta import (CLOSED, FROM, NEW, PART_LINES, TO, WAITING, Checker, Inbox,  # noqa: E402
                           attachments_text, html_text, parse, parts, sender_confirmed, strip_quotes, title_of)
from kompan.rozmowa import CZYTANIE, PRZEKAZ, PYTANIE, SEND, YES  # noqa: E402
from kompan.skrzynka import (AGAIN, ALL_READ, EARLIER, ENOUGH, KONIEC, LATER, NEXT, NO_REPLY,  # noqa: E402
                             POCZTA, REPLY, WRITE)
from test_kompan import Mailbox, make, said, texts  # noqa: E402

try:
    from fastapi.testclient import TestClient

    from kompan.app import app
except ImportError:
    TestClient = None

GOOD = "mx.google.com; dkim=pass header.i=@example.com; spf=pass smtp.mailfrom=mama@example.com; dmarc=pass"


def mail(sender="mama@example.com", subject="Obiad", body="Przyjdziesz w niedzielę?", reply_to="",
         auth=GOOD, html=None, message_id=None, attachments=()):
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = f"Mama <{sender}>", "kompan@gmail.com", subject
    message["Message-ID"] = message_id or f"<{abs(hash((sender, subject, body)))}@example.com>"
    message["Date"] = "Sun, 15 Nov 2026 17:40:00 +0000"
    if auth:
        message["Authentication-Results"] = auth
    if reply_to:
        message["In-Reply-To"] = reply_to
        message["References"] = reply_to
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")
    for name in attachments:
        message.add_attachment(b"x", maintype="image", subtype="jpeg", filename=name)
    return bytes(message)


def people(data, user="Radek"):
    (data / "osoby.json").write_text(json.dumps({"uzytkownik": user, "osoby": [
        {"imie": "Mama", "email": "mama@example.com", "wiadomosci": True, "pisze": True},
        {"imie": "Jurek", "email": "jurek@example.com", "wiadomosci": True, "pisze": True},
        {"imie": "Sąsiad", "email": "sasiad@example.com", "wiadomosci": True, "pisze": False}]}),
        encoding="utf-8")


def setup(*answers):
    data = Path(tempfile.mkdtemp())
    people(data)
    mailbox = Mailbox()
    kompan, client = make(*answers, data=data, send=mailbox)
    return kompan, client, mailbox


class ReadingTest(unittest.TestCase):
    def test_quotes_and_signatures_are_cut(self):
        text = ("Dobrze, przyjdę.\n\nPozdrawiam\n\nWysłane z iPhone'a\n\n"
                "W dniu niedz., 15 lis 2026 o 18:40 Kompan <kompan@gmail.com>\nnapisał(a):\n> Radek przekazuje...")
        self.assertEqual(strip_quotes(text), "Dobrze, przyjdę.\n\nPozdrawiam")
        self.assertEqual(strip_quotes("Tak.\n-- \nJan Kowalski\ntel. 123"), "Tak.")
        self.assertEqual(strip_quotes("OK\n\nOn Sun, Nov 15, 2026 at 6:40 PM Kompan wrote:\n> x"), "OK")
        self.assertEqual(strip_quotes("Jasne\n\nOd: Kompan\nWysłano: niedziela\nTemat: x\n\ntreść"), "Jasne")
        self.assertEqual(strip_quotes("Odpowiedź\n> cytat\n> cytat"), "Odpowiedź")

    def test_html_only(self):
        html = ('<html><head><style>p{}</style></head><body><p>Cześć!</p><p>Do jutra.<br>Mama</p>'
                '<div class="gmail_quote">W dniu ... napisał: stare</div></body></html>')
        self.assertEqual(html_text(html).strip(), "Cześć!\n\nDo jutra.\nMama")

    def test_parse(self):
        raw = mail(body="Przyjdziesz?\n\nW dniu niedz. Kompan napisał:\n> stare", attachments=["a.jpg"])
        found = parse(raw)
        self.assertEqual((found["adres"], found["tresc"], found["potwierdzony"]),
                         ("mama@example.com", "Przyjdziesz?", True))
        self.assertEqual(found["zalaczniki"], [{"nazwa": "a.jpg", "typ": "image/jpeg"}])

    def test_sender_check(self):
        def confirmed(auth, sender="mama@example.com"):
            return sender_confirmed(email.message_from_bytes(mail(sender=sender, auth=auth)), sender)

        self.assertTrue(confirmed(GOOD))
        self.assertFalse(confirmed(""))
        self.assertFalse(confirmed("mx.google.com; dkim=fail; spf=softfail; dmarc=fail"))
        self.assertFalse(confirmed("evil.example; dmarc=pass"))  # not Gmail's own header
        self.assertTrue(confirmed("mx.google.com; dkim=pass header.i=@example.com; dmarc=none"))
        self.assertFalse(confirmed("mx.google.com; dkim=pass header.i=@inny.pl; spf=pass smtp.mailfrom=x@inny.pl"))

    def test_parts_fit_the_screen(self):
        text = "\n\n".join(f"Akapit {n}. " + "Bardzo długie zdanie o niczym. " * 12 for n in range(5))
        pieces = parts(text)
        self.assertGreater(len(pieces), 2)
        self.assertTrue(all(text_lines(piece) <= PART_LINES for piece in pieces))
        self.assertEqual(" ".join(" ".join(pieces).split()), " ".join(text.split()))

    def test_titles(self):
        self.assertEqual(title_of("Re: Odp: Leki", ""), "Leki")
        self.assertEqual(title_of("", "Cześć Radek, jak się masz dzisiaj po wczoraj?"),
                         "Cześć Radek, jak się masz dzisiaj...")
        self.assertEqual(attachments_text([{"typ": "image/jpeg"}] * 2 + [{"typ": "application/pdf"}]),
                         "Są załączniki: 2 zdjęcia i 1 plik, których nie pokażę.")


class CorrespondenceTest(unittest.TestCase):
    def test_who_is_taken(self):
        kompan, _, _ = setup()
        correspondence = kompan.correspondence
        self.assertIsNone(correspondence.receive(mail(sender="obcy@example.com")))
        self.assertIsNone(correspondence.receive(mail(sender="sasiad@example.com")))  # not "pisze"
        self.assertIsNone(correspondence.receive(mail(auth="")))  # sender not confirmed
        message = correspondence.receive(mail())
        self.assertEqual((message["osoba"], message["stan"], message["temat"]), ("Mama", NEW, "Obiad"))
        self.assertIsNone(correspondence.receive(mail()))  # the same mail again
        rejected = [json.loads(line) for line in (kompan.data / "poczta.jsonl").read_text().splitlines()]
        self.assertEqual([r["powod"] for r in rejected if r["rodzaj"] == "mail_odrzucony"],
                         ["spoza listy", "spoza listy", "niepotwierdzony nadawca"])

    def test_a_reply_to_a_sent_message_joins_its_topic(self):
        kompan, _, mailbox = setup(said("Coś jeszcze?", "Tak", "Nie", title="Leki",
                                        message=("Przekazać?", "Radek dostaje leki za późno.", ["Mama"])))
        conversation = kompan.new()
        conversation.answer(1)  # Mama
        conversation.answer(3)  # To wszystko
        conversation.answer(1)  # Wyślij
        sent_id = mailbox.headers[0]["Message-ID"]
        [ours] = kompan.correspondence.topics("Mama")
        self.assertEqual(ours["temat"], "Leki")
        reply = kompan.correspondence.receive(mail(subject="Re: Leki",
                                                   body="Zadzwonię do przychodni.", reply_to=sent_id))
        self.assertEqual((reply["temat_id"], reply["temat"]), (ours["temat_id"], "Leki"))
        messages = kompan.correspondence.topic(ours["temat_id"])
        self.assertEqual([m["kierunek"] for m in messages], [FROM, TO])  # the newest first
        # Mama "pisze": replying is normal, nothing about it under the message
        self.assertNotIn("Odpowiedzi na ten adres", mailbox.mails[0][2])
        self.assertTrue(mailbox.mails[0][2].endswith("mogą zdarzyć się nieścisłości.\n"), mailbox.mails[0][2])

    def test_announcements_once_and_at_the_start(self):
        kompan, _, _ = setup()
        kompan.correspondence.receive(mail())
        self.assertEqual(kompan.correspondence.announcements(False),
                         ["Masz nową wiadomość. Pisze Mama. Przeczytasz ją w Kompanie."])
        self.assertEqual(kompan.correspondence.announcements(False), [])
        self.assertEqual(kompan.correspondence.announcements(True), ["W Kompanie czekają wiadomości od: Mama."])

    def test_checker(self):
        kompan, _, _ = setup()
        recorded = []
        checker = Checker(lambda handle: handle(mail()), kompan.correspondence, recorded.append)
        checker.check()
        self.assertEqual(len(recorded), 1)

        def broken(handle):
            raise OSError("brak sieci")

        Checker(broken, kompan.correspondence).check()
        self.assertIn("poczta_blad", (kompan.data / "poczta.jsonl").read_text())


class InboxTest(unittest.TestCase):
    def test_reads_unseen_and_marks_after_handling(self):
        calls = []

        class FakeIMAP:
            def __init__(self, host, port, timeout):
                calls.append(("connect", host, port))

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def login(self, user, password):
                calls.append(("login", user, password))

            def select(self, box):
                calls.append(("select", box))

            def search(self, charset, criteria):
                calls.append(("search", criteria))
                return "OK", [b"1 2"]

            def fetch(self, number, what):
                calls.append(("fetch", number, what))
                return "OK", [(b"1 (BODY[] {3}", b"raw" + number), b")"]

            def store(self, number, flags, value):
                calls.append(("store", number, value))

        handled = []
        with mock.patch("kompan.poczta.imaplib.IMAP4_SSL", FakeIMAP):
            Inbox("kompan@gmail.com", "haslo")(handled.append)
        self.assertEqual(handled, [b"raw1", b"raw2"])
        self.assertEqual(calls[:4], [("connect", "imap.gmail.com", 993), ("login", "kompan@gmail.com", "haslo"),
                                     ("select", "INBOX"), ("search", "UNSEEN")])
        # PEEK - not marked as read by fetching; marked only after handling
        self.assertEqual(calls[4:], [("fetch", b"1", "(BODY.PEEK[])"), ("store", b"1", "\\Seen"),
                                     ("fetch", b"2", "(BODY.PEEK[])"), ("store", b"2", "\\Seen")])


class MailboxTest(unittest.TestCase):
    def test_new_ones_one_after_another(self):
        kompan, _, _ = setup()
        kompan.correspondence.receive(mail())
        kompan.correspondence.receive(mail(sender="jurek@example.com", subject="Mecz", body="Oglądasz?",
                                           auth=GOOD.replace("mama", "jurek")))
        box = kompan.mailbox
        view = box.start("nowe")
        self.assertEqual(view["status"], POCZTA)
        self.assertRegex(view["tekst"], r"^Pisze Mama, \d\d\.\d\d, \d\d:\d\d\. Temat: Obiad\.\n\nPrzyjdziesz")
        self.assertEqual(view["opcje"], [REPLY, AGAIN, LATER, NO_REPLY])
        view = box.answer(3)  # Później - the next one
        self.assertTrue(view["tekst"].startswith("Pisze Jurek"))
        view = box.answer(4)  # Nie odpowiadam
        self.assertEqual((view["tekst"], view["opcje"]),
                         ("Dobrze. Gdybyś zmienił zdanie, znajdziesz ją w Wiadomościach, u: Jurek.", [NEXT]))
        view = box.answer(1)
        self.assertEqual((view["status"], view["tekst"]), (KONIEC, ALL_READ))
        states = {m["osoba"]: m["stan"] for m in kompan.correspondence._all()}
        self.assertEqual(states, {"Mama": WAITING, "Jurek": CLOSED})
        # Nothing is lost: Jurek is still in the list
        view = box.start("lista")
        self.assertEqual(view["opcje"], ["Mama (nowa)", "Jurek", ENOUGH])

    def test_long_message_in_parts(self):
        kompan, _, _ = setup()
        kompan.correspondence.receive(mail(body="\n\n".join("Zdanie o pogodzie. " * 15 for _ in range(4))))
        view = kompan.mailbox.start("nowe")
        self.assertIn("To dłuższa wiadomość,", view["tekst"])
        self.assertEqual(view["opcje"], [NEXT])
        while view["opcje"] == [NEXT]:
            view = kompan.mailbox.answer(1)
        self.assertEqual(view["opcje"], [REPLY, AGAIN, LATER, NO_REPLY])
        view = kompan.mailbox.answer(2)  # Przeczytaj jeszcze raz
        self.assertIn("To dłuższa wiadomość,", view["tekst"])

    def test_browsing_person_topics_messages(self):
        kompan, _, _ = setup()
        first = kompan.correspondence.receive(mail(body="Pierwsza."))
        kompan.correspondence.receive(mail(subject="Re: Obiad", body="Druga.", reply_to=first["message_id"]))
        kompan.correspondence.receive(mail(subject="Wakacje", body="Gdzie jedziemy?"))
        box = kompan.mailbox
        box.start("lista")
        view = box.answer(1)  # Mama
        self.assertEqual(view["tekst"], "Tematy: Mama.")
        self.assertEqual(sorted(view["opcje"][:2]), ["Obiad (nowa)", "Wakacje (nowa)"])
        view = box.answer(view["opcje"].index("Obiad (nowa)") + 1)
        self.assertIn("Druga.", view["tekst"])  # the newest first
        self.assertEqual(view["opcje"], [EARLIER, WRITE, AGAIN, ENOUGH])
        view = box.answer(1)
        self.assertIn("Pierwsza.", view["tekst"])
        self.assertEqual(view["opcje"], [WRITE, AGAIN, ENOUGH])
        self.assertTrue(view["mozna_wrocic"])
        view = box.back()
        self.assertEqual(view["tekst"], "Tematy: Mama.")
        view = box.back()
        self.assertEqual(view["opcje"][0], "Mama (nowa)")
        self.assertFalse(view["mozna_wrocic"])

    def test_one_topic_goes_straight_to_it(self):
        kompan, _, _ = setup()
        kompan.correspondence.receive(mail())
        kompan.mailbox.start("lista")
        self.assertIn("Przyjdziesz", kompan.mailbox.answer(1)["tekst"])

    def test_nothing_yet(self):
        kompan, _, _ = setup()
        self.assertEqual(kompan.mailbox.start("lista")["status"], KONIEC)


class ReplyTest(unittest.TestCase):
    def test_reply_from_the_mailbox(self):
        answer = ("Odpisać tak?", "Przyjdę w niedzielę.", ["Mama"], "Cześć Mamo,")
        kompan, client, mailbox = setup(said("Co odpowiesz?", "Przyjdę", "Nie dam rady"),
                                        said("Dobrze.", "OK", "Dalej", message=answer))
        message = kompan.correspondence.receive(mail())
        kompan.mailbox.start("nowe")
        view = kompan.mailbox.answer(1)  # Odpowiedz
        conversation = kompan.get(kompan.mailbox.view()["rozmowa"])
        opening = client.calls[0]["messages"][0]["content"][0]["text"]
        self.assertIn("chce odpowiedzieć na wiadomość. Pisze Mama, temat: Obiad", opening)
        self.assertIn("«Przyjdziesz w niedzielę?»", opening)
        self.assertIn("jeszcze nie pisała w tym temacie: odpowiedź zaczyna się od powitania", opening)
        conversation.answer(1)
        view = conversation.view()
        self.assertEqual(view["status"], PRZEKAZ)
        self.assertTrue(view["tekst"].startswith("Wiadomość dla: Mama"))  # no choosing people
        conversation.answer(1)  # Wyślij
        to, subject, body = mailbox.mails[0]
        self.assertEqual((to, subject), ("mama@example.com", "Re: Obiad"))
        self.assertTrue(body.startswith("Cześć Mamo,\n\nPrzyjdę w niedzielę.\n\nRadek\n"), body)
        self.assertEqual(mailbox.headers[0]["In-Reply-To"], message["message_id"])
        self.assertEqual(kompan.correspondence.get(message["id"])["stan"], CLOSED)
        topic = kompan.correspondence.topic(message["temat_id"])
        self.assertEqual([m["kierunek"] for m in topic], [TO, FROM])
        self.assertTrue(topic[0]["tresc"].startswith("Cześć Mamo,"))  # Radek sees what went

    def test_no_greeting_when_the_thread_goes_on(self):
        kompan, client, _ = setup(said("Co dopiszesz?", "Że przyjdę", "Nic"))
        message = kompan.correspondence.receive(mail())
        kompan.correspondence.sent({"imie": "Mama", "email": "mama@example.com"}, "Obiad", "Przyjdę.",
                                   "<r1@x>", "Re: Obiad", {"temat_id": message["temat_id"], "temat": "Obiad"})
        kompan.reply(message)
        opening = client.calls[0]["messages"][0]["content"][0]["text"]
        self.assertIn("już pisała w tym temacie: bez powitania", opening)

    def test_a_message_during_a_conversation(self):
        answer = ("Odpisać tak?", "Radek przyjdzie.", ["Mama"])
        kompan, client, mailbox = setup(said("Jak minął dzień?", "Dobrze", "Źle"),
                                        said("A co jutro?", "Nic", "Spacer", mail=True),
                                        said("Co odpiszesz?", "Przyjdę", "Nie wiem"),
                                        said("Gotowe.", "OK", "Dalej", message=answer))
        conversation = kompan.new()
        kompan.correspondence.receive(mail())
        conversation.answer(1)
        self.assertIn("(Przyszła wiadomość. Pisze Mama.)", client.calls[1]["messages"][-1]["content"][0]["text"])
        view = conversation.view()
        self.assertEqual((view["status"], view["tekst"], texts(view["opcje"])),
                         (CZYTANIE, "Przyszła wiadomość. Pisze Mama. Przeczytać teraz?", [YES, LATER]))
        self.assertFalse(view["mozna_wrocic"])
        conversation.answer(1)  # Tak
        self.assertIn("Przyjdziesz", conversation.view()["tekst"])
        conversation.answer(1)  # Odpowiedz
        self.assertIn("chce odpowiedzieć na wiadomość", client.calls[2]["messages"][-1]["content"][0]["text"])
        conversation.answer(1)
        self.assertTrue(conversation.view()["tekst"].startswith("Wiadomość dla: Mama"))
        options = texts(conversation.view()["opcje"])
        conversation.answer(options.index(SEND) + 1)
        self.assertEqual(mailbox.mails[0][1], "Re: Obiad")

    def test_later_during_a_conversation(self):
        kompan, client, _ = setup(said("Jak minął dzień?", "Dobrze", "Źle"),
                                  said("A co jutro?", "Nic", "Spacer", mail=True), said("OK?", "Tak", "Nie"))
        conversation = kompan.new()
        kompan.correspondence.receive(mail())
        conversation.answer(1)
        conversation.answer(2)  # Później
        self.assertEqual((conversation.status, conversation.view()["tekst"]), (PYTANIE, "A co jutro?"))
        conversation.answer(1)
        last = client.calls[2]["messages"][-1]["content"][0]["text"]
        self.assertIn("(Wiadomość od: Mama odłożona na później.)", last)
        self.assertNotIn("Przyszła wiadomość", last)  # told once
        self.assertEqual(kompan.correspondence.waiting()[0]["stan"], WAITING)


@unittest.skipIf(TestClient is None, "no fastapi")
class ApiTest(unittest.TestCase):
    def setUp(self):
        self.kompan, _, _ = setup(said("Co odpowiesz?", "Przyjdę", "Nie"))
        self.old = app.state.kompan
        app.state.kompan = self.kompan
        self.api = TestClient(app)

    def tearDown(self):
        app.state.kompan = self.old

    def test_flow(self):
        health = self.api.get("/v1/kompan/health").json()
        self.assertEqual((health["poczta_nowe"], health["poczta_czeka"], health["poczta_jest"]), ([], 0, False))
        self.kompan.correspondence.receive(mail())
        health = self.api.get("/v1/kompan/health").json()
        self.assertEqual((health["poczta_nowe"], health["poczta_czeka"], health["poczta_jest"]),
                         (["Mama"], 1, True))
        self.assertEqual(health["poczta_ogloszenie"]["text"], "Masz nową wiadomość. Pisze Mama.")
        self.assertEqual(health["poczta_przycisk"]["text"], "Wiadomości (1)")
        said_now = self.api.post("/v1/kompan/powiadomienia", json={"startup": False}).json()["say"]
        self.assertEqual(len(said_now), 1)
        self.api.post("/v1/kompan/poczta/pozniej")
        self.assertEqual(self.api.get("/v1/kompan/health").json()["poczta_nowe"], [])
        view = self.api.post("/v1/kompan/poczta/start", json={"tryb": "nowe"}).json()
        self.assertEqual((view["status"], view["stale"], [o["numer"] for o in view["opcje"]]),
                         (POCZTA, [], [1, 2, 3, 4]))
        view = self.api.post("/v1/kompan/poczta/odpowiedz", json={"opcja": 1}).json()  # Odpowiedz
        self.assertEqual(view["status"], PYTANIE)  # the new conversation's view
        self.assertEqual(view["tekst"], "Co odpowiesz?")
        self.assertEqual(self.api.post("/v1/kompan/poczta/odpowiedz", json={"opcja": 1}).status_code, 409)


if __name__ == "__main__":
    unittest.main()
