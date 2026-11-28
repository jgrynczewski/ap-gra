"""Times and dates in words, for the narrator only (the screen keeps digits).

The voice reads ordinary numbers well, but "16:00" or "22.11" come out as
digits with punctuation. Before a recording:

    spoken("Pisze Jurek, 22.11, 16:00")
    -> "Pisze Jurek, dwudziestego drugiego listopada, szesnasta"
    spoken("Spotkanie o 17:15")  -> "Spotkanie o siedemnastej piętnaście"

Only times with a colon (0:00-23:59) and dates with dots: day.month with a
two-digit month (22.11, 3.05), or day.month.year (22.11.2026). Decimal
numbers in Polish have a comma, version numbers (2.6.0) are left alone.

Years 1900-2099 also: in 2026-11-23, after a month's name ("23 listopada 2026",
"w listopadzie 2026"), before "r." / "roku" ("z 2026 r.", "w 2026 roku" - with
the case after w / o / po / przy) and on their own
("2026" -> "dwa tysiące dwadzieścia sześć"). Other four-digit numbers stay.
"""

from __future__ import annotations

import re

_CARDINAL = ["zero", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć",
             "dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście",
             "szesnaście", "siedemnaście", "osiemnaście", "dziewiętnaście"]
_TENS = {2: "dwadzieścia", 3: "trzydzieści", 4: "czterdzieści", 5: "pięćdziesiąt",
         6: "sześćdziesiąt", 7: "siedemdziesiąt", 8: "osiemdziesiąt", 9: "dziewięćdziesiąt"}

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
                   r"(?:(?P<m>0?[1-9]|1[0-2])\.(?P<y>\d{4})(?P<r>\s*(?:r\.|roku\b))?"
                   r"|(?P<m2>0[1-9]|1[0-2]))"
                   r"(?![\d]|\.\d)")

# Years: only 1900-2099, so that amounts and numbers stay as they are
_Y = r"(?P<y>19\d\d|20\d\d)"
# "r." or "roku" after a year: said as "roku" (a following "roku" would repeat it)
_R = r"(?P<r>\s*(?:r\.|roku\b))?"
_ISO = re.compile(r"(?<![\d.,:-])" + _Y + r"-(?P<m>0[1-9]|1[0-2])-(?P<d>0[1-9]|[12]\d|3[01])"
                  + r"(?![\d-])" + _R)
_MONTH_FORMS = ("styczeń stycznia styczniu luty lutego lutym marzec marca marcu "
                "kwiecień kwietnia kwietniu maj maja maju czerwiec czerwca czerwcu "
                "lipiec lipca lipcu sierpień sierpnia sierpniu wrzesień września wrześniu "
                "październik października październiku listopad listopada listopadzie "
                "grudzień grudnia grudniu").split()
_MONTH_YEAR = re.compile(r"(?:(?<![\d.,:])(?P<d>0?[1-9]|[12]\d|3[01])\s+(?=(?i:"
                         + "|".join(_MONTHS) + r")\b))?"
                         r"(?P<month>\b(?i:" + "|".join(_MONTH_FORMS) + r"))\s+"
                         + _Y + r"(?![\d.,:]\d|\d)" + _R)
# "w 2026 roku", "o 1983 roku": the locative ("w dwa tysiące dwudziestym szóstym roku")
_LOCATIVE = {"w", "we", "o", "po", "przy"}
_YEAR_R = re.compile(r"(?:\b(?P<prep>[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)\s+)?(?<![\d.,:-])"
                     + _Y + r"\s*(?P<r>r\.|roku\b)")
_YEAR = re.compile(r"(?<![\d.,:-])" + _Y + r"(?![\d]|[.,:-]\d|\s*(?:rok|r\.))")


def cardinal(n: int) -> str:
    """0-99 in words."""
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
    if y == 1900:
        return "tysiąc dziewięćsetnego roku"
    if 1900 < y < 2000:
        return f"tysiąc dziewięćset {ordinal_genitive(y - 1900)} roku"
    return f"{y} roku"


def _year_locative(y: int) -> str:
    """ "dwa tysiące dwudziestym szóstym roku" (after w / o / po / przy)."""
    words = _year(y).split()
    return " ".join(w[:-3] + "m" if w.endswith("iego") else w[:-3] + "ym" if w.endswith("ego") else w
                    for w in words)


def _year_r(match: re.Match) -> str:
    prep = match["prep"] or ""
    y = int(match["y"])
    said = (_year_locative(y) if prep.lower() in _LOCATIVE else _year(y)) + _keep_dot(match)
    return f"{prep} {said}" if prep else said


def _year_cardinal(y: int) -> str:
    """1900-2099 as a number: "dwa tysiące dwadzieścia sześć"."""
    head, rest = ("tysiąc dziewięćset", y - 1900) if y < 2000 else ("dwa tysiące", y - 2000)
    return f"{head} {cardinal(rest)}" if rest else head


def _keep_dot(match: re.Match) -> str:
    """ "r." at the end of a sentence: the dot stays as the sentence's end."""
    r = match["r"] or ""
    if not r.endswith("."):
        return ""
    after = match.string[match.end():]
    return "." if re.match(r"\s*$|\s+[A-ZĄĆĘŁŃÓŚŹŻ]", after) else ""


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
    return f"{said} {_year(int(match['y']))}{_keep_dot(match)}" if match["y"] else said


def _month_year(match: re.Match) -> str:
    said = f"{match['month']} {_year(int(match['y']))}{_keep_dot(match)}"
    return f"{ordinal_genitive(int(match['d']))} {said}" if match["d"] else said


def spoken(text: str) -> str:
    """The text as the narrator should read it."""
    text = _DATE.sub(_date, _TIME.sub(_time, text))
    text = _ISO.sub(_date, text)
    text = _MONTH_YEAR.sub(_month_year, text)
    text = _YEAR_R.sub(_year_r, text)
    return _YEAR.sub(lambda m: _year_cardinal(int(m["y"])), text)
