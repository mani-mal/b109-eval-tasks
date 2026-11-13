"""List the contents of a zip archive, refusing archives with unsafe paths.

An archive is unsafe if any member name could escape the directory it would
be extracted into: absolute paths, Windows drive paths, or ``..`` traversal.
Member names may use ``/`` or ``\\`` as separators.
"""

from __future__ import annotations

import fnmatch
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

__all__ = ["Entry", "UnsafeArchiveError", "find", "is_safe_member", "list_archive", "total_size"]

_DRIVE = re.compile(r"^[A-Za-z]:")


class UnsafeArchiveError(ValueError):
    def __init__(self, member: str) -> None:
        super().__init__(f"unsafe member path: {member!r}")
        self.member = member


@dataclass(frozen=True)
class Entry:
    name: str
    size: int
    compressed_size: int
    is_dir: bool


def is_safe_member(name: str) -> bool:
    """True if extracting ``name`` would stay inside the target directory."""
    if not name:
        return False
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or _DRIVE.match(normalized):
        return False
    if normalized == ".." or normalized.startswith("../"):
        return False
    return True


def list_archive(source: str | Path | BinaryIO, *, max_entries: int = 10_000,
                 pattern: str | None = None) -> list[Entry]:
    """Return the archive's entries sorted by name.

    Raises :class:`UnsafeArchiveError` if any member is unsafe and
    ``ValueError`` if there are more than ``max_entries`` members.
    """
    with zipfile.ZipFile(source) as zf:
        infos = zf.infolist()
        if len(infos) > max_entries:
            raise ValueError(f"archive has {len(infos)} entries (limit {max_entries})")
        entries = []
        for info in infos:
            if not is_safe_member(info.filename):
                raise UnsafeArchiveError(info.filename)
            entries.append(
                Entry(
                    name=info.filename,
                    size=info.file_size,
                    compressed_size=info.compress_size,
                    is_dir=info.is_dir(),
                )
            )
    if pattern is not None:
        entries = find(entries, pattern)
  return sorted(entries, key=lambda e: e.name)


def total_size(entries: list[Entry]) -> int:
    """Uncompressed size of all file entries."""
    return sum(e.size for e in entries if not e.is_dir)


def find(entries: list[Entry], pattern: str) -> list[Entry]:
    """Entries whose name matches the shell-style ``pattern``."""
    return [e for e in entries if fnmatch.fnmatchcase(e.name, pattern)]
