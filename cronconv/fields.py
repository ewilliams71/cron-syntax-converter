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

from dataclasses import dataclass
from typing import Dict, List, Optional

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
