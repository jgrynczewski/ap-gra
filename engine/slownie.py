"""Times and dates in words, for the narrator only (the screen keeps digits).

The voice reads ordinary numbers well, but "16:00" or "22.11" come out as
digits with punctuation. Before a recording:

    spoken("Pisze Jurek, 22.11, 16:00")
    -> "Pisze Jurek, dwudziestego drugiego listopada, szesnasta"
    spoken("Spotkanie o 17:15")  -> "Spotkanie o siedemnastej piętnaście"

Only times with a colon (0:00-23:59) and dates with dots: day.month with a
two-digit month (22.11, 3.05), or day.month.year (22.11.2026). Decimal
numbers in Polish have a comma, version numbers (2.6.0) are left alone.
"""

from __future__ import annotations

import re

_CARDINAL = ["zero", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć",
             "dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście",
             "szesnaście", "siedemnaście", "osiemnaście", "dziewiętnaście"]
_TENS = {2: "dwadzieścia", 3: "trzydzieści", 4: "czterdzieści", 5: "pięćdziesiąt"}

# The hour: a feminine ordinal ("godzina szesnasta")
_HOURS = ["zero", "pierwsza", "druga", "trzecia", "czwarta", "piąta", "szósta", "siódma", "ósma",
          "dziewiąta", "dziesiąta", "jedenasta", "dwunasta", "trzynasta", "czternasta", "piętnasta",
          "szesnasta", "siedemnasta", "osiemnasta", "dziewiętnasta", "dwudziesta",
          "dwudziesta pierwsza", "dwudziesta druga", "dwudziesta trzecia"]
# The case after a preposition: o / po / od / do ... szesnastej, przed / na ... szesnastą
_GENITIVE = {"o", "po", "od", "do", "około", "koło"}
_INSTRUMENTAL = {"przed", "na", "między", "pomiędzy", "za"}

# Days and years: a masculine ordinal in the genitive ("dwudziestego drugiego listopada")
_ORD = ["", "pierwszego", "drugiego", "trzeciego", "czwartego", "piątego", "szóstego", "siódmego",
        "ósmego", "dziewiątego", "dziesiątego", "jedenastego", "dwunastego", "trzynastego",
        "czternastego", "piętnastego", "szesnastego", "siedemnastego", "osiemnastego",
        "dziewiętnastego"]
_ORD_TENS = {2: "dwudziestego", 3: "trzydziestego", 4: "czterdziestego", 5: "pięćdziesiątego",
             6: "sześćdziesiątego", 7: "siedemdziesiątego", 8: "osiemdziesiątego",
             9: "dziewięćdziesiątego"}
_MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
           "września", "października", "listopada", "grudnia"]

_TIME = re.compile(r"(?<![\d:.,])(?:\b(?P<prep>[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)\s+)?"
                   r"(?P<h>[01]?\d|2[0-3]):(?P<m>[0-5]\d)(?![\d:])")
_DATE = re.compile(r"(?<![\d.,])(?P<d>0?[1-9]|[12]\d|3[01])\."
                   r"(?:(?P<m>0?[1-9]|1[0-2])\.(?P<y>\d{4})|(?P<m2>0[1-9]|1[0-2]))"
                   r"(?![\d]|\.\d)")


def cardinal(n: int) -> str:
    """0-59 in words."""
    if n < 20:
        return _CARDINAL[n]
    tens, unit = divmod(n, 10)
    return _TENS[tens] + (f" {_CARDINAL[unit]}" if unit else "")


def _hour(n: int, case: str) -> str:
    words = _HOURS[n].split()
    if words == ["zero"]:
        return "zero"
    if case == "gen":
        words = ["drugiej" if w == "druga" else w[:-1] + "ej" for w in words]
    elif case == "ins":
        words = [w[:-1] + "ą" for w in words]
    return " ".join(words)


def ordinal_genitive(n: int) -> str:
    """1-99: pierwszego ... dziewięćdziesiątego dziewiątego."""
    if n < 20:
        return _ORD[n]
    tens, unit = divmod(n, 10)
    return _ORD_TENS[tens] + (f" {_ORD[unit]}" if unit else "")


def _year(y: int) -> str:
    if y == 2000:
        return "dwutysięcznego roku"
    if 2000 < y < 2100:
        return f"dwa tysiące {ordinal_genitive(y - 2000)} roku"
    return f"{y} roku"


def _time(match: re.Match) -> str:
    prep = match["prep"] or ""
    case = "gen" if prep.lower() in _GENITIVE else "ins" if prep.lower() in _INSTRUMENTAL else "nom"
    minutes = int(match["m"])
    said = _hour(int(match["h"]), case)
    if minutes:
        said += f" zero {cardinal(minutes)}" if minutes < 10 else f" {cardinal(minutes)}"
    return f"{prep} {said}" if prep else said


def _date(match: re.Match) -> str:
    month = int(match["m"] or match["m2"])
    said = f"{ordinal_genitive(int(match['d']))} {_MONTHS[month - 1]}"
    return f"{said} {_year(int(match['y']))}" if match["y"] else said


def spoken(text: str) -> str:
    """The text as the narrator should read it."""
    return _DATE.sub(_date, _TIME.sub(_time, text))
