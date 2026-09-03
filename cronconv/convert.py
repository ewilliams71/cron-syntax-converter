"""Conversion between standard 5-field cron and Quartz 6/7-field cron.

Standard cron (minute hour dom month dow) and Quartz cron (second minute hour
dom month dow [year]) differ in more than field count:

  - Quartz adds a seconds field in front and an optional year field at the end.
  - Quartz numbers day-of-week 1-7 with Sunday=1; standard cron uses 0-6 with
    Sunday=0.
  - Quartz requires exactly one of day-of-month/day-of-week to be the literal
    '?' placeholder, since it can't otherwise tell which of the two AND'd
    fields you meant to leave unrestricted. Standard cron has no such
    placeholder: both fields are always active and combine with OR semantics
    when both are restricted.

That last point is the sharp edge. A standard cron expression that restricts
both day-of-month and day-of-week (e.g. "run on the 1st AND every Monday")
has no exact Quartz equivalent, because Quartz fields are ANDed once you take
'?' out of the picture. In strict mode we refuse to guess; --lenient keeps
the day-of-month restriction and drops day-of-week, which is a common enough
convention that it's a reasonable default guess but is still a lossy one.
"""

from dataclasses import dataclass
from typing import List, Optional

from .errors import CronFormatError
from .fields import DAY_NAMES, MONTH_NAMES, QUARTZ_DAY_NAMES, Term, parse_field, render_field


@dataclass
class StandardCron:
    minute: List[Term]
    hour: List[Term]
    dom: List[Term]
    month: List[Term]
    dow: List[Term]


@dataclass
class QuartzCron:
    second: List[Term]
    minute: List[Term]
    hour: List[Term]
    dom: Optional[List[Term]]  # None means the field was '?'
    month: List[Term]
    dow: Optional[List[Term]]  # None means the field was '?'
    year: Optional[List[Term]]  # None means the field was omitted


def parse_standard(expr: str, lenient: bool = False) -> StandardCron:
    fields = expr.split()
    if len(fields) != 5:
        raise CronFormatError(
            f"standard cron expressions have 5 fields (minute hour dom month dow), got {len(fields)}"
        )
    minute_s, hour_s, dom_s, month_s, dow_s = fields
    strict = not lenient

    minute = parse_field(minute_s, 0, 59, strict=strict)
    hour = parse_field(hour_s, 0, 23, strict=strict)
    dom = parse_field(dom_s, 1, 31, strict=strict)
    month = parse_field(month_s, 1, 12, names=MONTH_NAMES, strict=strict)

    # POSIX allows 7 as an alias for Sunday alongside 0; we only accept that
    # alias in lenient mode, and only for a plain value, not inside a range.
    dow_max = 7 if lenient else 6
    dow = parse_field(dow_s, 0, dow_max, names=DAY_NAMES, strict=strict)
    if lenient:
        for term in dow:
            if term.kind == "value" and term.start == 7:
                term.start = 0

    return StandardCron(minute, hour, dom, month, dow)


def parse_quartz(expr: str, lenient: bool = False) -> QuartzCron:
    fields = expr.split()
    strict = not lenient

    if len(fields) == 6:
        second_s, minute_s, hour_s, dom_s, month_s, dow_s = fields
        year_s = None
    elif len(fields) == 7:
        second_s, minute_s, hour_s, dom_s, month_s, dow_s, year_s = fields
    else:
        raise CronFormatError(
            f"quartz cron expressions have 6 or 7 fields (second minute hour dom month dow [year]), "
            f"got {len(fields)}"
        )

    dom_is_placeholder = dom_s == "?"
    dow_is_placeholder = dow_s == "?"
    if strict and dom_is_placeholder == dow_is_placeholder:
        raise CronFormatError(
            "quartz requires exactly one of day-of-month/day-of-week to be '?' "
            "(pass --lenient to relax this)"
        )

    second = parse_field(second_s, 0, 59, strict=strict)
    minute = parse_field(minute_s, 0, 59, strict=strict)
    hour = parse_field(hour_s, 0, 23, strict=strict)
    dom = None if dom_is_placeholder else parse_field(dom_s, 1, 31, strict=strict)
    month = parse_field(month_s, 1, 12, names=MONTH_NAMES, strict=strict)
    dow = None if dow_is_placeholder else parse_field(dow_s, 1, 7, names=QUARTZ_DAY_NAMES, strict=strict)
    year = parse_field(year_s, 1970, 2099, strict=strict) if year_s is not None else None

    return QuartzCron(second, minute, hour, dom, month, dow, year)


def to_quartz(standard: StandardCron, lenient: bool = False) -> str:
    strict = not lenient
    dom_wild = _is_wildcard(standard.dom)
    dow_wild = _is_wildcard(standard.dow)

    if not dom_wild and not dow_wild:
        if strict:
            raise CronFormatError(
                "cannot convert: both day-of-month and day-of-week are restricted, which quartz "
                "cannot express with AND semantics (pass --lenient to keep day-of-month and drop "
                "day-of-week)"
            )
        dom_out = render_field(standard.dom)
        dow_out = "?"
    elif dom_wild and dow_wild:
        dom_out, dow_out = "*", "?"
    elif dom_wild:  # only day-of-week restricted
        dom_out = "?"
        dow_out = render_field(_shift_terms(standard.dow, 1))
    else:  # only day-of-month restricted
        dom_out = render_field(standard.dom)
        dow_out = "?"

    parts = [
        "0",  # standard cron has no seconds field; always fire on second 0
        render_field(standard.minute),
        render_field(standard.hour),
        dom_out,
        render_field(standard.month),
        dow_out,
    ]
    return " ".join(parts)


def to_standard(quartz: QuartzCron, lenient: bool = False) -> str:
    strict = not lenient

    if not _is_zero_or_wildcard(quartz.second) and strict:
        raise CronFormatError(
            "cannot convert: seconds field is more precise than standard cron supports "
            "(pass --lenient to drop it)"
        )
    if quartz.year is not None and not _is_wildcard(quartz.year) and strict:
        raise CronFormatError(
            "cannot convert: standard cron has no year field (pass --lenient to drop it)"
        )

    dom_out = "*" if quartz.dom is None else render_field(quartz.dom)
    dow_out = "*" if quartz.dow is None else render_field(_shift_terms(quartz.dow, -1))

    parts = [
        render_field(quartz.minute),
        render_field(quartz.hour),
        dom_out,
        render_field(quartz.month),
        dow_out,
    ]
    return " ".join(parts)


def _is_wildcard(terms: List[Term]) -> bool:
    return len(terms) == 1 and terms[0].kind == "wildcard" and terms[0].step is None


def _is_zero_or_wildcard(terms: List[Term]) -> bool:
    if _is_wildcard(terms):
        return True
    return len(terms) == 1 and terms[0].kind == "value" and terms[0].start == 0


def _shift_terms(terms: List[Term], delta: int) -> List[Term]:
    shifted = []
    for term in terms:
        shifted.append(
            Term(
                kind=term.kind,
                start=None if term.start is None else term.start + delta,
                end=None if term.end is None else term.end + delta,
                step=term.step,
            )
        )
    return shifted
