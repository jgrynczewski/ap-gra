"""Limits of games (kreator/limity.py): a day and a week Monday-Sunday, Polish time."""

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kreator.limity import blocked, games, when  # noqa: E402

# 2026-11-23 is a Monday
MONDAY_EVENING = datetime(2026, 11, 23, 20, 0, tzinfo=timezone.utc)


def at(day, hour=10, status="gotowa"):
    """A game made on 2026-11-<day> at <hour> UTC."""
    return {"status": status, "utworzona": f"2026-11-{day:02d}T{hour:02d}:00:00+00:00"}


def evening(day):
    return datetime(2026, 11, day, 20, 0, tzinfo=timezone.utc)


class LimitsTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"AP_GRA_LIMIT_DZIEN": "1", "AP_GRA_LIMIT_TYDZIEN": "5"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_free(self):
        self.assertEqual(blocked([], MONDAY_EVENING), "")
        self.assertEqual(blocked([at(22)], MONDAY_EVENING), "")  # Sunday - yesterday

    def test_one_a_day(self):
        self.assertEqual(blocked([at(23)], MONDAY_EVENING),
                         "Dzisiejsza gra już powstała. Następną stworzymy jutro.")

    def test_a_failed_game_does_not_count(self):
        self.assertEqual(blocked([at(23, status="nieudana")], MONDAY_EVENING), "")
        # One still being made counts - it was approved
        self.assertNotEqual(blocked([at(23, status="w_toku")], MONDAY_EVENING), "")

    def test_the_day_is_polish(self):
        # 23:30 UTC on Sunday is 00:30 on Monday in Poland
        self.assertNotEqual(blocked([at(22, hour=23)], MONDAY_EVENING), "")
        # Without a zone (older games) - the container's UTC
        old = {"status": "gotowa", "utworzona": "2026-11-22T23:30:00"}
        self.assertNotEqual(blocked([old], MONDAY_EVENING), "")

    def test_five_a_week_says_when(self):
        week = [at(day) for day in (23, 24, 25, 26, 27)]  # Monday to Friday
        self.assertEqual(blocked(week, evening(27)),
                         "W tym tygodniu powstało już 5 gier. Następną stworzymy za 3 dni.")
        self.assertEqual(blocked(week, evening(28)),
                         "W tym tygodniu powstało już 5 gier. Następną stworzymy za 2 dni.")
        self.assertEqual(blocked(week, evening(29)),
                         "W tym tygodniu powstało już 5 gier. Następną stworzymy jutro.")
        self.assertEqual(blocked(week, evening(30)), "")  # Monday - a new week

    def test_last_week_does_not_count(self):
        self.assertEqual(blocked([at(day) for day in (17, 18, 19, 20, 21)], MONDAY_EVENING), "")

    def test_settings(self):
        with mock.patch.dict(os.environ, {"AP_GRA_LIMIT_DZIEN": "0", "AP_GRA_LIMIT_TYDZIEN": "0"}):
            self.assertEqual(blocked([at(23)] * 9, MONDAY_EVENING), "")
        with mock.patch.dict(os.environ, {"AP_GRA_LIMIT_DZIEN": "3", "AP_GRA_LIMIT_TYDZIEN": "zle"}):
            self.assertEqual(blocked([at(23)] * 2, MONDAY_EVENING), "")
            self.assertEqual(blocked([at(23)] * 3, MONDAY_EVENING),
                             "Dzisiaj powstały już 3 gry. Następną stworzymy jutro.")

    def test_words(self):
        self.assertEqual([games(n) for n in (1, 2, 5, 12, 22)],
                         ["powstała już 1 gra", "powstały już 2 gry", "powstało już 5 gier",
                          "powstało już 12 gier", "powstały już 22 gry"])
        self.assertEqual([when(n) for n in (1, 3, 7)], ["jutro", "za 3 dni", "za tydzień"])


if __name__ == "__main__":
    unittest.main()
