"""A small least-recently-used cache with hit/miss statistics."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any

__all__ = ["LRUCache"]

EvictCallback = Callable[[Hashable, Any], None]


class LRUCache:
    """Map with a fixed capacity that evicts the least recently used entry.

    Both ``get`` and ``put`` count as a use of the key. ``key in cache`` does
    not. ``on_evict`` is called with ``(key, value)`` for every entry removed
    because the cache was full or was shrunk with :meth:`resize`.
    """

    def __init__(self, capacity: int, *, on_evict: EvictCallback | None = None) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._capacity = capacity
        self._data: OrderedDict[Hashable, Any] = OrderedDict()
        self._on_evict = on_evict
        self.hits = 0
        self.misses = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def get(self, key: Hashable, default: Any = None) -> Any:
        if key in self._data:
            self.hits += 1
            return self._data[key]
        self.misses += 1
        return default

    def put(self, key: Hashable, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
            self._data[key] = value
            return
        self._data[key] = value
        self._shrink_to(self._capacity)

    def delete(self, key: Hashable) -> bool:
        """Remove ``key``. Returns True if it was present. Not an eviction."""
        if key in self._data:
            del self._data[key]
            return True
        return False

    def resize(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._capacity = capacity
        self._shrink_to(capacity)

    def _shrink_to(self, size: int) -> None:
        while len(self._data) > size:
            key, value = self._data.popitem(last=False)
            if self._on_evict is not None:
                self._on_evict(key, value)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def keys(self) -> list[Hashable]:
        """Keys from least to most recently used."""
        return list(self._data.keys())

    def clear(self) -> None:
        """Drop every entry and reset the statistics. Not an eviction."""
        self._data.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> dict[str, float]:
        lookups = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": len(self._data),
            "hit_rate": (self.hits / lookups) if lookups else 0.0,
        }
