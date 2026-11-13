"""Semantic version parsing, ordering and range matching (SemVer 2.0.0).

Range syntax accepted by :func:`satisfies`:

    1.2.3            exactly 1.2.3
    >=1.2.0 <2.0.0   every comparator must hold (space separated)
    ^1.2.3           >=1.2.3 <2.0.0   (^0.2.3 means <0.3.0, ^0.0.3 means <0.0.4)
    ~1.2.3           >=1.2.3 <1.3.0
    A || B           either range matches
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import total_ordering

__all__ = ["Version", "VersionError", "compare", "max_satisfying", "satisfies"]

_PATTERN = re.compile(
    r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


class VersionError(ValueError):
    pass


@total_ordering
@dataclass(frozen=True, eq=False)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: tuple[str, ...] = field(default=())

    @classmethod
    def parse(cls, text: str) -> Version:
        m = _PATTERN.match(text.strip())
        if not m:
            raise VersionError(f"not a semantic version: {text!r}")
        pre = tuple(m[4].split(".")) if m[4] else ()
        build = tuple(m[5].split(".")) if m[5] else ()
        return cls(int(m[1]), int(m[2]), int(m[3]), pre, build)

    @property
    def core(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    @property
    def release(self) -> Version:
        """The same version without prerelease or build metadata."""
        return Version(self.major, self.minor, self.patch)

    def __str__(self) -> str:
        text = ".".join(str(n) for n in self.core)
        if self.prerelease:
            text += "-" + "-".join(self.prerelease)
        return text

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.core == other.core and self.prerelease == other.prerelease

    def __hash__(self) -> int:
        return hash((self.core, self.prerelease))

    def __lt__(self, other: Version) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        if self.core != other.core:
            return self.core < other.core
        # A version without a prerelease ranks above any prerelease of it.
        if not self.prerelease or not other.prerelease:
            return bool(self.prerelease) and not other.prerelease
        return self.prerelease < other.prerelease


def _coerce(v: Version | str) -> Version:
    return v if isinstance(v, Version) else Version.parse(v)


def compare(a: Version | str, b: Version | str) -> int:
    """Return -1, 0 or 1 as ``a`` is lower than, equal to or higher than ``b``."""
    va, vb = _coerce(a), _coerce(b)
    return (va > vb) - (va < vb)


def _expand(token: str) -> list[tuple[str, Version]]:
    """Turn one range token into (operator, version) comparators."""
    if token.startswith("^"):
        low = Version.parse(token[1:])
        if low.major:
            high = Version(low.major + 1, 0, 0)
        elif low.minor:
            high = Version(0, low.minor + 1, 0)
        else:
            high = Version(0, 0, low.patch + 1)
        return [(">=", low), ("<", high)]
    if token.startswith("~"):
        low = Version.parse(token[1:])
        return [(">=", low), ("<", Version(low.major, low.minor + 1, 0))]
    for op in (">=", "<=", ">", "<", "="):
        if token.startswith(op):
            return [(op, Version.parse(token[len(op):]))]
    return [("=", Version.parse(token))]


_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "=": lambda a, b: a == b,
}


def satisfies(version: Version | str, constraint: str) -> bool:
    v = _coerce(version)
    for alternative in constraint.split("||"):
        tokens = alternative.split()
        if not tokens:
            continue
        comparators = [c for t in tokens for c in _expand(t)]
        if all(_OPS[op](v, bound) for op, bound in comparators):
            return True
    return False


def max_satisfying(versions: Iterable[Version | str], constraint: str) -> Version | None:
    matching = [v for v in map(_coerce, versions) if satisfies(v, constraint)]
    return max(matching) if matching else None
