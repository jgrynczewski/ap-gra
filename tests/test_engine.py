"""Engine tests: scenario format, game, checks. Run from the repo root:

    python -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.check import check  # noqa: E402
from engine.game import Game, GameError  # noqa: E402
from engine.scenario import ScenarioError, load, parse  # noqa: E402

SMALL = """
# Próba

// komentarz autora
## start
Pierwsza linia
i druga.

Nowy akapit.

> ustaw: klucz

* Otwórz drzwi -> sala
* [klucz] Użyj klucza -> sala
* [!klucz] Szukaj klucza -> start

## sala
Jesteś w sali.
> usun: klucz
> obraz: sala.png
* [!klucz] Wyjdź -> koniec_dobry

## koniec_dobry
Koniec.
> koniec: Dobre zakończenie
"""


class ScenarioTest(unittest.TestCase):
    def test_parse(self):
        scenario = parse(SMALL)
        self.assertEqual(scenario.title, "Próba")
        self.assertEqual(scenario.start, "start")
        start = scenario.scenes["start"]
        self.assertEqual(start.render(set()), "Pierwsza linia i druga.\n\nNowy akapit.")
        self.assertEqual(start.set_flags, ["klucz"])
        self.assertEqual([o.target for o in start.options], ["sala", "sala", "start"])
        self.assertEqual(start.options[1].conditions, [("klucz", True)])
        self.assertEqual(start.options[2].conditions, [("klucz", False)])
        self.assertEqual(scenario.scenes["sala"].image, "sala.png")
        self.assertEqual(scenario.endings, {"koniec_dobry": "Dobre zakończenie"})

    def test_verse_lines_keep_breaks(self):
        text = "# T\n## start\nProza\ndalej.\n| Wers pierwszy\n| Wers drugi\nI proza.\n\n| Sam wers\n"
        self.assertEqual(parse(text).scenes["start"].render(set()),
                         "Proza dalej.\nWers pierwszy\nWers drugi\nI proza.\n\nSam wers")

    def test_conditional_lines(self):
        text = "# T\n## start\n[zart] Klasa chichocze.\n[!zart] Cisza.\nDzwonek.\n\n[zart] | Wers\n"
        scene = parse(text).scenes["start"]
        self.assertEqual(scene.render({"zart"}), "Klasa chichocze. Dzwonek.\n\nWers")
        self.assertEqual(scene.render(set()), "Cisza. Dzwonek.")  # empty paragraph dropped

    def test_option_effects(self):
        option = parse("# T\n## start\n* Żartuj -> dalej +zart -powaga\n").scenes["start"].options[0]
        self.assertEqual((option.target, option.set_flags, option.clear_flags),
                         ("dalej", ["zart"], ["powaga"]))
        self.assertEqual(option.apply({"powaga", "x"}), {"zart", "x"})

    def test_errors_point_to_line(self):
        cases = {
            "## start\n": "tytułu",
            "# T\nTekst\n": "przed pierwszą sceną",
            "# T\n## start\n* bez celu\n": "Opcja",
            "# T\n## start\n> dziwne: x\n": "Dyrektywa",
            "# T\n## start\n* A -> b\nTekst po opcjach\n": "przed dyrektywami",
            "# T\n## a\n## a\n": "już istnieje",
            "# T\n## Duże\n": "Nagłówek sceny",
            "# T\n## start\n* [zła flaga] A -> b\n": "warunek",
        }
        for text, message in cases.items():
            with self.subTest(text=text):
                with self.assertRaises(ScenarioError) as ctx:
                    parse(text)
                self.assertIn(message, str(ctx.exception))

    def test_real_scenario_loads(self):
        scenario = load(ROOT / "scenariusz" / "sala_pod_zegarem.md")
        self.assertEqual(scenario.title, "Sala pod zegarem")


class GameTest(unittest.TestCase):
    def setUp(self):
        self.game = Game(parse(SMALL))

    def test_start_applies_flags_and_filters_options(self):
        view = self.game.start()
        self.assertEqual(view["scene"], "start")
        self.assertEqual(view["state"], {"scene": "start", "flags": ["klucz"]})
        # [!klucz] hidden - klucz set when entering the scene
        self.assertEqual([o["text"] for o in view["options"]], ["Otwórz drzwi", "Użyj klucza"])
        self.assertEqual([o["number"] for o in view["options"]], [1, 2])
        self.assertIsNone(view["ending"])

    def test_choose_numbers_visible_options(self):
        view = self.game.choose(self.game.start()["state"], 2)
        self.assertEqual(view["scene"], "sala")
        self.assertEqual(view["state"]["flags"], [])  # > usun: klucz
        self.assertEqual(view["image"], "sala.png")
        view = self.game.choose(view["state"], 1)
        self.assertEqual(view["ending"], {"id": "koniec_dobry", "title": "Dobre zakończenie",
                                          "number": 1, "total": 1, "audio": None})
        self.assertEqual(view["options"], [])

    def test_option_effects_and_reaction_text(self):
        game = Game(parse("""# T
## start
* Żartuj -> klasa +zart
* Milcz -> klasa
## klasa
[zart] Wszyscy się śmieją.
Dzwoni dzwonek.
* [zart] Ukłoń się -> koniec
* Wyjdź -> koniec
## koniec
> koniec: K
"""))
        view = game.choose(game.start()["state"], 1)
        self.assertEqual(view["text"], "Wszyscy się śmieją. Dzwoni dzwonek.")
        self.assertEqual(view["state"]["flags"], ["zart"])
        self.assertEqual(len(view["options"]), 2)
        view = game.choose(game.start()["state"], 2)
        self.assertEqual(view["text"], "Dzwoni dzwonek.")
        self.assertEqual([o["text"] for o in view["options"]], ["Wyjdź"])

    def test_bad_requests(self):
        state = self.game.start()["state"]
        for bad in (0, 3, "1", None):
            with self.subTest(option=bad), self.assertRaises(GameError):
                self.game.choose(state, bad)
        with self.assertRaises(GameError):
            self.game.choose({"scene": "nie_ma"}, 1)
        with self.assertRaises(GameError):
            self.game.choose({"scene": "koniec_dobry", "flags": []}, 1)


class CheckTest(unittest.TestCase):
    def test_small_scenario_is_fine(self):
        report = check(parse(SMALL))
        self.assertEqual(report.errors, [])
        self.assertEqual(report.stats["zakończenia"], 1)
        self.assertEqual(report.stats["najkrótsza rozgrywka (wybory)"], 2)
        # [!klucz] Szukaj klucza never shows - klucz is set when entering start
        self.assertEqual(report.stats["najdłuższa rozgrywka (wybory)"], 2)

    def test_loop_with_way_out_has_no_longest(self):
        text = "# T\n## start\n* Jeszcze raz -> start\n* Koniec -> koniec\n## koniec\n> koniec: K\n"
        report = check(parse(text))
        self.assertEqual(report.errors, [])
        self.assertIsNone(report.stats["najdłuższa rozgrywka (wybory)"])

    def test_finds_problems(self):
        text = """# T
## start
> ustaw: a
* [b] Nie do pokazania -> koniec
* Do nikąd -> brak
## sierota
* Wróć -> start
## petla
* Kręć się -> petla
## bez_opcji
Nic.
## koniec
> koniec: K
"""
        report = check(parse(text))
        errors = "\n".join(report.errors)
        self.assertIn("nieistniejącej sceny 'brak'", errors)
        self.assertIn("sierota", errors)  # unreachable
        self.assertIn("bez_opcji", errors)  # no options, not an ending
        self.assertIn("zakończenie nieosiągalne", errors)  # [b] never set
        warnings = "\n".join(report.warnings)
        self.assertIn("'b' jest sprawdzana", warnings)
        self.assertIn("'a' jest ustawiana", warnings)

    def test_stuck_and_trap(self):
        text = """# T
## start
* Idź -> rozdroze
## rozdroze
* [a] Tylko z flagą -> koniec
* [!a] Pętla -> krag
## krag
* Dalej -> krag2
## krag2
* Wróć -> krag
## koniec
> koniec: K
"""
        report = check(parse(text))
        errors = "\n".join(report.errors)
        self.assertIn("pętla bez wyjścia", errors)
        self.assertIn("nieosiągalne", errors)

    def test_option_effects_reach_flagged_options(self):
        text = "# T\n## start\n* Weź klucz -> drzwi +klucz\n* Idź -> drzwi\n" \
               "## drzwi\n* [klucz] Otwórz -> koniec\n* [!klucz] Wróć -> start\n## koniec\n> koniec: K\n"
        report = check(parse(text))
        self.assertEqual(report.errors, [])

    def test_single_option_scenes_in_a_row(self):
        text = "# T\n## start\n* Dalej -> b\n## b\n* Dalej -> koniec\n## koniec\n> koniec: K\n"
        report = check(parse(text))
        self.assertIn("dwie sceny z jedną opcją pod rząd", "\n".join(report.warnings))
        self.assertEqual(report.stats["sceny z jedną opcją"], "2 z 2")

    def test_stuck_player(self):
        text = "# T\n## start\n* [a] Ukryta -> koniec\n## koniec\n> koniec: K\n"
        errors = "\n".join(check(parse(text)).errors)
        self.assertIn("gracz utknął", errors)

    def test_too_many_options(self):
        options = "".join(f"* Opcja {i} -> koniec\n" for i in range(5))
        errors = "\n".join(check(parse(f"# T\n## start\n{options}## koniec\n> koniec: K\n")).errors)
        self.assertIn("5 widoczne opcje", errors)

    def test_real_scenario_has_no_errors(self):
        report = check(load(ROOT / "scenariusz" / "sala_pod_zegarem.md"))
        self.assertEqual(report.errors, [])


if __name__ == "__main__":
    unittest.main()
