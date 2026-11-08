"""What the AI costs per day, counted from the tokens of every answer.

One line per AI answer in koszty.jsonl (engine/log.py). The day is the Polish
one, so the limit resets at midnight for the user. The API console stays the
source of truth for the bill; this is only for the daily limit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from engine.log import Log

ZONE = ZoneInfo("Europe/Warsaw")
MILLION = 1_000_000

# USD per million tokens: input, output, cache write (5 minutes), cache read
# (platform.claude.com/docs/en/about-claude/pricing, 2026-11-08)
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 5.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 2.50, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
}
# An unknown model (e.g. a server-side fallback) counts at the highest price:
# better to stop a little early than to pass the limit
UNKNOWN_PRICE = (10.0, 50.0, 12.50, 1.0)


def cost(model: str, usage) -> float:
    """USD of one answer. usage: input_tokens, output_tokens and optionally
    cache_creation_input_tokens, cache_read_input_tokens."""
    prices = PRICES.get(model, UNKNOWN_PRICE)
    amounts = (usage.input_tokens, usage.output_tokens,
               getattr(usage, "cache_creation_input_tokens", 0) or 0,
               getattr(usage, "cache_read_input_tokens", 0) or 0)
    return sum(price * amount for price, amount in zip(prices, amounts)) / MILLION


class Costs:
    def __init__(self, path: Path, limit: float, now=lambda: datetime.now(timezone.utc)):
        self.log = Log(path)
        self.limit = limit
        self.now = now

    def add(self, model: str, usage) -> None:
        self.log.write("koszt", model=model, usd=round(cost(model, usage), 6))

    def today(self) -> float:
        day = self.now().astimezone(ZONE).date()
        return sum(e["usd"] for e in self.log.entries()
                   if datetime.fromisoformat(e["czas"]).astimezone(ZONE).date() == day)

    def over_limit(self) -> bool:
        return self.today() >= self.limit
