"""Parsing and normalization for a single cron field (minute, hour, day-of-month, ...).

A field is a comma-separated list of items, where each item is one of:
    *           any value
    N           a single value (or name, where names are allowed)
    N-M         an inclusive range
    X/S         X (a wildcard or range) stepped by S

Parsing produces a list of Term objects rather than re-normalizing straight to
a string, because converting day-of-week values between standard cron (SUN=0)
and Quartz (SUN=1) needs to shift the numeric start/end of each term without
disturbing wildcards or step values.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from .errors import CronFormatError

MONTH_NAMES: Dict[str, int] = {
    name: i
    for i, name in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"],
        start=1,
    )
}

# Standard (POSIX/Vixie) cron: Sunday is 0.
DAY_NAMES: Dict[str, int] = {
    name: i
    for i, name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"], start=0)
}

# Quartz cron: Sunday is 1.
QUARTZ_DAY_NAMES: Dict[str, int] = {
    name: i
    for i, name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"], start=1)
}


@dataclass
class Term:
    kind: str  # "wildcard", "value", or "range"
    start: Optional[int] = None
    end: Optional[int] = None
    step: Optional[int] = None

    def render(self) -> str:
        if self.kind == "wildcard":
            base = "*"
        elif self.kind == "range":
            base = f"{self.start}-{self.end}"
        else:
            base = str(self.start)
        if self.step is not None:
            return f"{base}/{self.step}"
        return base


@dataclass
class QuartzDomSpecial:
    """A Quartz day-of-month special value: L, L-n, LW, or nW.

    These only make sense relative to a specific month's calendar (the last
    day, the last weekday, the weekday nearest a given day), so unlike Term
    they aren't part of a comma list -- Quartz doesn't allow combining them
    with other day-of-month values, and neither do we.
    """

    kind: str  # "last", "last_offset", "last_weekday", "weekday_of"
    day: Optional[int] = None  # for "weekday_of"
    offset: Optional[int] = None  # for "last_offset"

    def render(self) -> str:
        if self.kind == "last":
            return "L"
        if self.kind == "last_offset":
            return f"L-{self.offset}"
        if self.kind == "last_weekday":
            return "LW"
        return f"{self.day}W"


@dataclass
class QuartzDowSpecial:
    """A Quartz day-of-week special value: nL (last weekday n of the month)
    or n#k (the kth occurrence of weekday n in the month). Stored with
    Quartz's own day numbering (SUN=1).
    """

    kind: str  # "last_weekday_of_month", "nth_weekday_of_month"
    day: int
    nth: Optional[int] = None  # for "nth_weekday_of_month"

    def render(self) -> str:
        if self.kind == "last_weekday_of_month":
            return f"{self.day}L"
        return f"{self.day}#{self.nth}"


_DOM_LAST_RE = re.compile(r"^L(?:-(\d{1,2}))?$")
_DOM_WEEKDAY_RE = re.compile(r"^(\d{1,2})W$")
_DOW_LAST_RE = re.compile(r"^([A-Z]{3}|[1-7])L$")
_DOW_NTH_RE = re.compile(r"^([A-Z]{3}|[1-7])#([1-5])$")


def parse_quartz_dom(spec: str, strict: bool = True) -> Union[List[Term], QuartzDomSpecial]:
    spec = spec.upper()
    if spec == "LW":
        return QuartzDomSpecial(kind="last_weekday")

    match = _DOM_LAST_RE.match(spec)
    if match:
        offset_str = match.group(1)
        if offset_str is None:
            return QuartzDomSpecial(kind="last")
        offset = int(offset_str)
        if offset < 1 or offset > 30:
            raise CronFormatError(f"'{spec}': offset must be between 1 and 30 days before the last")
        return QuartzDomSpecial(kind="last_offset", offset=offset)

    match = _DOM_WEEKDAY_RE.match(spec)
    if match:
        day = int(match.group(1))
        if day < 1 or day > 31:
            raise CronFormatError(f"value {day} is outside the allowed range [1, 31]")
        return QuartzDomSpecial(kind="weekday_of", day=day)

    return parse_field(spec, 1, 31, strict=strict)


def parse_quartz_dow(spec: str, strict: bool = True) -> Union[List[Term], QuartzDowSpecial]:
    spec = spec.upper()

    match = _DOW_NTH_RE.match(spec)
    if match:
        day = _resolve_quartz_dow_token(match.group(1))
        return QuartzDowSpecial(kind="nth_weekday_of_month", day=day, nth=int(match.group(2)))

    match = _DOW_LAST_RE.match(spec)
    if match:
        day = _resolve_quartz_dow_token(match.group(1))
        return QuartzDowSpecial(kind="last_weekday_of_month", day=day)

    return parse_field(spec, 1, 7, names=QUARTZ_DAY_NAMES, strict=strict)


def _resolve_quartz_dow_token(token: str) -> int:
    if token.isdigit():
        return int(token)
    day = QUARTZ_DAY_NAMES.get(token)
    if day is None:
        raise CronFormatError(f"'{token}' is not a recognized day-of-week name")
    return day


def parse_field(
    spec: str,
    minval: int,
    maxval: int,
    names: Optional[Dict[str, int]] = None,
    strict: bool = True,
) -> List[Term]:
    if spec == "":
        raise CronFormatError("field cannot be empty")
    return [_parse_item(part, minval, maxval, names, strict) for part in spec.split(",")]


def render_field(terms: List[Term]) -> str:
    return ",".join(term.render() for term in terms)


def _parse_item(item: str, minval: int, maxval: int, names, strict: bool) -> Term:
    if item == "":
        raise CronFormatError("empty item in field list")

    if "/" in item:
        base, step_str = item.split("/", 1)
        if not step_str.isdigit() or int(step_str) == 0:
            raise CronFormatError(f"invalid step '{step_str}' in '{item}'")
        step = int(step_str)
    else:
        base, step = item, None

    if base == "*":
        return Term(kind="wildcard", step=step)

    if "-" in base:
        lo_str, hi_str = base.split("-", 1)
        lo = _parse_value(lo_str, minval, maxval, names, strict)
        hi = _parse_value(hi_str, minval, maxval, names, strict)
        if lo > hi and strict:
            raise CronFormatError(
                f"descending range '{base}' is not allowed in strict mode "
                "(pass --lenient to keep it as a wraparound range)"
            )
        return Term(kind="range", start=lo, end=hi, step=step)

    value = _parse_value(base, minval, maxval, names, strict)
    return Term(kind="value", start=value, step=step)


def _parse_value(token: str, minval: int, maxval: int, names, strict: bool) -> int:
    if names is not None:
        looked_up = names.get(token.upper())
        if looked_up is not None:
            return looked_up
        if not token.lstrip("-").isdigit():
            raise CronFormatError(f"'{token}' is not a recognized name or number")

    if not token.lstrip("-").isdigit():
        raise CronFormatError(f"'{token}' is not a valid number")

    value = int(token)
    if value < minval or value > maxval:
        raise CronFormatError(f"value {value} is outside the allowed range [{minval}, {maxval}]")
    return value
