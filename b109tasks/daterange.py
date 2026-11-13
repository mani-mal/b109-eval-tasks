"""Parse human-friendly date ranges.

Supported forms (all bounds are inclusive):

    2024-03-05                  a single day
    2024-03                     a whole month
    2024                        a whole year
    2024-03-05..2024-03-09      an explicit range
    2024-03..2024-05            start of the first month to end of the last

Whitespace around the ``..`` separator is ignored.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Iterator
from dataclasses import dataclass

__all__ = ["DateRange", "DateRangeError", "parse_range", "split_by_month"]


class DateRangeError(ValueError):
    """Raised when a range cannot be parsed or is empty."""


@dataclass(frozen=True)
class DateRange:
    start: _dt.date
    end: _dt.date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise DateRangeError(f"range ends before it starts: {self.start}..{self.end}")

    @property
    def days(self) -> int:
        """Number of days in the range, counting both ends."""
        return (self.end - self.start).days + 1

    def __contains__(self, day: object) -> bool:
        if not isinstance(day, _dt.date):
            return False
        return self.start <= day <= self.end

    def overlaps(self, other: DateRange) -> bool:
        return self.start <= other.end and other.start <= self.end

    def intersection(self, other: DateRange) -> DateRange | None:
        if not self.overlaps(other):
            return None
        return DateRange(max(self.start, other.start), min(self.end, other.end))

    def iter_days(self) -> Iterator[_dt.date]:
        day = self.start
        one = _dt.timedelta(days=1)
        while day <= self.end:
            yield day
            day += one

    def __str__(self) -> str:
        return f"{self.start.isoformat()}..{self.end.isoformat()}"


_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR = re.compile(r"^(\d{4})$")

_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and year % 100 != 0


def _last_day(year: int, month: int) -> int:
    if month == 2 and _is_leap(year):
        return 29
    return _DAYS_IN_MONTH[month - 1]


def _parse_point(text: str, *, end: bool) -> _dt.date:
    """Parse one bound. ``end`` selects the last day of a month or year."""
    try:
        if m := _DAY.match(text):
            return _dt.date(int(m[1]), int(m[2]), int(m[3]))
        if m := _MONTH.match(text):
            year, month = int(m[1]), int(m[2])
            if not 1 <= month <= 12:
                raise DateRangeError(f"bad month in {text!r}")
            return _dt.date(year, month, _last_day(year, month) if end else 1)
        if m := _YEAR.match(text):
            year = int(m[1])
            return _dt.date(year, 12, 31) if end else _dt.date(year, 1, 1)
    except ValueError as exc:
        if isinstance(exc, DateRangeError):
            raise
        raise DateRangeError(f"invalid date {text!r}: {exc}") from None
    raise DateRangeError(f"unrecognised date {text!r}")


def parse_range(text: str) -> DateRange:
    """Parse ``text`` into a :class:`DateRange`."""
    text = text.strip()
    if not text:
        raise DateRangeError("empty range")
    if ".." in text:
        left, _, right = text.partition("..")
        left, right = left.strip(), right.strip()
        if not left or not right:
            raise DateRangeError(f"both bounds are required: {text!r}")
        start = _parse_point(left, end=False)
        stop = _parse_point(right, end=True)
    else:
        start = _parse_point(text, end=False)
        stop = _parse_point(text, end=True)
    if stop < start:
        raise DateRangeError(f"range ends before it starts: {text!r}")
    return DateRange(start, stop)


def split_by_month(rng: DateRange) -> list[DateRange]:
    """Split ``rng`` into pieces that each stay within one calendar month."""
    pieces: list[DateRange] = []
    cursor = rng.start
    while cursor <= rng.end:
        month_end = _dt.date(cursor.year, cursor.month, _last_day(cursor.year, cursor.month))
        piece_end = min(month_end, rng.end)
        pieces.append(DateRange(cursor, piece_end))
        cursor = piece_end + _dt.timedelta(days=1)
    return pieces
