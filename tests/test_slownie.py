import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import voice  # noqa: E402
from engine.slownie import cardinal, ordinal_genitive, spoken  # noqa: E402


class SpokenTest(unittest.TestCase):
    def test_times(self):
        self.assertEqual(spoken("16:00"), "szesnasta")
        self.assertEqual(spoken("17:15"), "siedemnasta piętnaście")
        self.assertEqual(spoken("godzina 8:05"), "godzina ósma zero pięć")
        self.assertEqual(spoken("0:45"), "zero czterdzieści pięć")
        self.assertEqual(spoken("21:30"), "dwudziesta pierwsza trzydzieści")

    def test_the_case_after_a_preposition(self):
        self.assertEqual(spoken("Spotkanie o 17:15"), "Spotkanie o siedemnastej piętnaście")
        self.assertEqual(spoken("od 23:59 do 1:00"),
                         "od dwudziestej trzeciej pięćdziesiąt dziewięć do pierwszej")
        self.assertEqual(spoken("przed 9:30, Na 12:00"), "przed dziewiątą trzydzieści, Na dwunastą")
        self.assertEqual(spoken("po 22:00"), "po dwudziestej drugiej")

    def test_dates(self):
        self.assertEqual(spoken("Pisze Jurek, 22.11, 16:00"),
                         "Pisze Jurek, dwudziestego drugiego listopada, szesnasta")
        self.assertEqual(spoken("3.05"), "trzeciego maja")
        self.assertEqual(spoken("12.11.2026, 18:40"),
                         "dwunastego listopada dwa tysiące dwudziestego szóstego roku, osiemnasta czterdzieści")
        self.assertEqual(spoken("31.12.2000."), "trzydziestego pierwszego grudnia dwutysięcznego roku.")

    def test_years(self):
        self.assertEqual(spoken("z 2026 roku"), "z dwa tysiące dwudziestego szóstego roku")
        self.assertEqual(spoken("od 2026 r. pojechaliśmy"),
                         "od dwa tysiące dwudziestego szóstego roku pojechaliśmy")
        self.assertEqual(spoken("To było w 2026 r."), "To było w dwa tysiące dwudziestym szóstym roku.")
        self.assertEqual(spoken("prawdę o 1983 roku"),
                         "prawdę o tysiąc dziewięćset osiemdziesiątym trzecim roku")
        self.assertEqual(spoken("W 2000 r. Potem"), "W dwutysięcznym roku. Potem")
        self.assertEqual(spoken("po 2022 roku"), "po dwa tysiące dwudziestym drugim roku")
        self.assertEqual(spoken("23 listopada 2026"),
                         "dwudziestego trzeciego listopada dwa tysiące dwudziestego szóstego roku")
        self.assertEqual(spoken("1 maja 2026 r., 15:00"),
                         "pierwszego maja dwa tysiące dwudziestego szóstego roku, piętnasta")
        self.assertEqual(spoken("w maju 1999"), "w maju tysiąc dziewięćset dziewięćdziesiątego dziewiątego roku")
        self.assertEqual(spoken("Listopad 2026"), "Listopad dwa tysiące dwudziestego szóstego roku")
        self.assertEqual(spoken("2026-11-23, 16:00"),
                         "dwudziestego trzeciego listopada dwa tysiące dwudziestego szóstego roku, szesnasta")
        self.assertEqual(spoken("12.11.2026 r. o 9:00"),
                         "dwunastego listopada dwa tysiące dwudziestego szóstego roku o dziewiątej")
        self.assertEqual(spoken("Rok 2026, a liceum w 1900"),
                         "Rok dwa tysiące dwadzieścia sześć, a liceum w tysiąc dziewięćset")
        self.assertEqual(spoken("2000"), "dwa tysiące")

    def test_other_numbers_stay(self):
        for text in ["wersja 2.6.0", "cena 3,50 zł", "1.5 kg", "Mecz 2:1", "Zakończenie 3 z 7.",
                     "32.11", "22.13", "24:00", "12:60", "tel. 601.123.456",
                     "1850", "3050", "12026", "wersja 2026.11", "2026-13-01", "tel. 2026-123"]:
            self.assertEqual(spoken(text), text)

    def test_words(self):
        self.assertEqual([cardinal(n) for n in (0, 9, 15, 20, 47, 99)],
                         ["zero", "dziewięć", "piętnaście", "dwadzieścia", "czterdzieści siedem",
                          "dziewięćdziesiąt dziewięć"])
        self.assertEqual(ordinal_genitive(26), "dwudziestego szóstego")

    def test_the_recording_follows_what_is_spoken(self):
        self.assertEqual(voice.key("Pisze Jurek, 22.11, 16:00"),
                         voice.key("Pisze Jurek, dwudziestego drugiego listopada, szesnasta"))
        self.assertNotEqual(voice.key("Dalej"), voice.key("Wróć"))


if __name__ == "__main__":
    unittest.main()
