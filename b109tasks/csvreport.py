"""Build simple CSV reports from rows of dicts.

Each column names the row key it reads, an optional title for the header, and
an optional format:

    int       whole number                      1234
    decimal2  two decimal places                1234.50
    percent   a fraction shown as a percentage  12.5%
    money     a Money value, amount only        1234.50

Missing keys and ``None`` values are written as empty cells.

Reports render as CSV (:meth:`Report.to_csv`) or as a markdown table
(:meth:`Report.to_markdown`). Both can end with a totals row.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .mdtable import format_table
from .money import CurrencyMismatch, Money

__all__ = ["Column", "Report", "register_format"]

Formatter = Callable[[Any], str]


def _int(value: Any) -> str:
    return str(int(value))


def _decimal2(value: Any) -> str:
    return f"{Decimal(str(value)):.2f}"


def _percent(value: Any) -> str:
    text = f"{Decimal(str(value)) * 100:.1f}"
    return text + "%"


def _money(value: Any) -> str:
    if not isinstance(value, Money):
        raise TypeError(f"money column got {type(value).__name__}")
    return value.to_plain()


_FORMATTERS: dict[str, Formatter] = {
    "int": _int,
    "decimal2": _decimal2,
    "percent": _percent,
    "money": _money,
}


def register_format(name: str, func: Formatter) -> None:
    """Make ``name`` usable as a column format."""
    if name in _FORMATTERS:
        raise ValueError(f"format {name!r} already registered")
    _FORMATTERS[name] = func
_RIGHT_ALIGNED = {"int", "decimal2", "percent", "money"}


@dataclass(frozen=True)
class Column:
    key: str
    title: str | None = None
    fmt: str | None = None

    def __post_init__(self) -> None:
        if self.fmt is not None and self.fmt not in _FORMATTERS:
            raise ValueError(f"unknown format {self.fmt!r}")

    @property
    def header(self) -> str:
        return self.title if self.title is not None else self.key


def format_value(value: Any, fmt: str | None) -> str:
    if fmt is None:
        return "" if value is None else str(value)
    return _FORMATTERS[fmt](value)


class Report:
    def __init__(self, columns: Iterable[Column | str]) -> None:
        self.columns = [c if isinstance(c, Column) else Column(c) for c in columns]
        if not self.columns:
            raise ValueError("a report needs at least one column")
        keys = [c.key for c in self.columns]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate column key")
        self.rows: list[dict[str, Any]] = []

    def add_row(self, row: Mapping[str, Any]) -> None:
        self.rows.append(dict(row))

    def add_rows(self, rows: Iterable[Mapping[str, Any]]) -> None:
        for row in rows:
            self.add_row(row)

    def sort_by(self, key: str, *, reverse: bool = False) -> None:
        """Sort rows by ``key``; rows missing the key go last."""
        present = [r for r in self.rows if r.get(key) is not None]
        missing = [r for r in self.rows if r.get(key) is None]
        present.sort(key=lambda r: r[key], reverse=reverse)
        self.rows = present + missing

    def formatted_rows(self) -> list[list[str]]:
        return [[format_value(row.get(c.key), c.fmt) for c in self.columns] for row in self.rows]

    def totals_row(self, keys: Iterable[str]) -> list[str]:
        """A row labelled ``Total`` with the sum of each column in ``keys``.

        Missing and None values are skipped; a column with no values gets an
        empty cell. Money columns are summed as Money. The first column holds
        the label, so it cannot be totalled.
        """
        wanted = list(keys)
        known = {c.key for c in self.columns}
        for key in wanted:
            if key not in known:
                raise ValueError(f"unknown column {key!r}")
            if key == self.columns[0].key:
                raise ValueError("the first column holds the totals label")
        row = ["Total"]
        for col in self.columns[1:]:
            values = [r[col.key] for r in self.rows if r.get(col.key) is not None]
            if col.key not in wanted or not values:
                row.append("")
                continue
            total = values[0]
            for value in values[1:]:
                total = total + value
            row.append(format_value(total, col.fmt))
        return row

    def _table(self, totals: Iterable[str]) -> list[list[str]]:
        wanted = list(totals)
        cells = self.formatted_rows()
        if wanted:
            cells.append(self.totals_row(wanted))
        return cells

    def to_csv(self, *, delimiter: str = ",", totals: Iterable[str] = ()) -> str:
        cells = self._table(totals)
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
        writer.writerow([c.header for c in self.columns])
        writer.writerows(cells)
        return buffer.getvalue()

    def markdown_headers(self) -> list[str]:
        """Column headers, with the currency appended to money columns, e.g. ``Revenue (EUR)``."""
        headers = []
        for col in self.columns:
            header = col.header
            if col.fmt == "money":
                codes = sorted({r[col.key].currency for r in self.rows
                                if isinstance(r.get(col.key), Money)})
                if len(codes) > 1:
                    raise CurrencyMismatch(f"column {col.key!r} mixes {', '.join(codes)}")
                if codes:
                    header = f"{header} ({codes[0]})"
            headers.append(header)
        return headers

    def to_markdown(self, *, totals: Iterable[str] = ()) -> str:
        """The report as a markdown table; numeric columns are right-aligned."""
        cells = self._table(totals)
        align = ["right" if c.fmt in _RIGHT_ALIGNED else "left" for c in self.columns]
        return format_table(self.markdown_headers(), cells, align=align)
