"""How many games may be made: per day and per week (Monday-Sunday), Polish time.

    AP_GRA_LIMIT_DZIEN=1     games a day (0 - no limit)
    AP_GRA_LIMIT_TYDZIEN=5   games a week, Monday to Sunday (0 - no limit)

Set in the .env of ap-gra-kreator on the AP computer. A game counts from
ROZPOCZNIJ (dane/zadania/<id>/stan.json, "utworzona"); a failed one does not
count - that is not the user's fault. Checked when the conversation starts,
so a used-up limit costs nothing.

The message says when the next game can be made: the daily limit - tomorrow;
the weekly one - on Monday, counted from today ("za 3 dni", "jutro").
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Warsaw")
DAY_LIMIT, WEEK_LIMIT = 1, 5
FAILED = "nieudana"  # kreator/tworzenie.py NIEUDANA


def _setting(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


def limits() -> tuple[int, int]:
    return _setting("AP_GRA_LIMIT_DZIEN", DAY_LIMIT), _setting("AP_GRA_LIMIT_TYDZIEN", WEEK_LIMIT)


def _local_date(created: str):
    """The Polish date of "utworzona"; without a zone it is the container's UTC."""
    try:
        when = datetime.fromisoformat(created)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(ZONE).date()


def games(n: int) -> str:
    """"powstała już 1 gra", "powstały już 3 gry", "powstało już 5 gier"."""
    if n == 1:
        return "powstała już 1 gra"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"powstały już {n} gry"
    return f"powstało już {n} gier"


def when(days: int) -> str:
    return "jutro" if days == 1 else "za tydzień" if days == 7 else f"za {days} dni"


def blocked(tasks: list[dict], now: datetime | None = None) -> str:
    """The message for the user when no game may be made now, else ""."""
    day_limit, week_limit = limits()
    today = (now or datetime.now(timezone.utc)).astimezone(ZONE).date()
    monday = today - timedelta(days=today.weekday())
    dates = [_local_date(t.get("utworzona")) for t in tasks if t.get("status") != FAILED]
    this_week = sum(1 for d in dates if d and monday <= d <= today)
    today_count = sum(1 for d in dates if d == today)
    if week_limit and this_week >= week_limit:
        return f"W tym tygodniu {games(this_week)}. Następną stworzymy {when(7 - today.weekday())}."
    if day_limit and today_count >= day_limit:
        if today_count == 1:
            return "Dzisiejsza gra już powstała. Następną stworzymy jutro."
        return f"Dzisiaj {games(today_count)}. Następną stworzymy jutro."
    return ""
