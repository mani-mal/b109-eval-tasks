"""Format rows as a GitHub-flavoured markdown table.

Columns are padded so the raw markdown lines up. Pipes inside a cell are
escaped as ``\\|`` and newlines become spaces, so every row stays on one line.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["format_table"]

_ALIGNMENTS = ("left", "right")
_MIN_WIDTH = 3


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\r\n", " ").replace("\n", " ")


def _escape(text: str) -> str:
    return text.replace("|", "\\|")


def _pad(text: str, width: int, align: str) -> str:
    return text.rjust(width) if align == "right" else text.ljust(width)


def _separator(width: int, align: str) -> str:
    if align == "right":
        return "-" * (width - 1) + ":"
    return "-" * width


def format_table(
    headers: Sequence[Any],
    rows: Sequence[Sequence[Any]],
    align: Sequence[str] | Mapping[str, str] | None = None,
) -> str:
    """Return the table as a string ending in a newline.

    ``align`` gives one of ``"left"`` or ``"right"`` per column; the default
    is left for every column. Every row must have as many cells as there are
    headers.
    """
    if not headers:
        raise ValueError("a table needs at least one column")
    ncols = len(headers)
    if isinstance(align, Mapping):
        names = [_cell(h) for h in headers]
        unknown = sorted(set(align) - set(names))
        if unknown:
            raise ValueError(f"no column named {unknown[0]!r}")
        aligns = [align.get(name, "left") for name in sorted(names)]
    else:
        aligns = list(align) if align is not None else ["left"] * ncols
    if len(aligns) != ncols:
        raise ValueError("align must give one entry per column")
    for a in aligns:
        if a not in _ALIGNMENTS:
            raise ValueError(f"unknown alignment {a!r}")

    header_cells = [_cell(h) for h in headers]
    body = []
    for i, row in enumerate(rows):
        if len(row) != ncols:
            raise ValueError(f"row {i} has {len(row)} cells, expected {ncols}")
        body.append([_cell(v) for v in row])

    widths = [max(_MIN_WIDTH, len(h)) for h in header_cells]
    for row_cells in body:
        for c, text in enumerate(row_cells):
            widths[c] = max(widths[c], len(text))

    def line(cells: list[str]) -> str:
        padded = [_pad(_escape(t), widths[c], aligns[c]) for c, t in enumerate(cells)]
        return "| " + " | ".join(padded) + " |"

    out = [line(header_cells)]
    out.append("| " + " | ".join(_separator(w, a) for w, a in zip(widths, aligns)) + " |")
    out.extend(line(r) for r in body)
    return "\n".join(out) + "\n"
