"""Result cache to avoid burning free-tier quotas on repeat lookups.

Uses `diskcache` when available (fast, safe across processes); otherwise falls
back to a tiny SQLite-backed store. TTL is configurable via settings.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .config import cache_dir

try:
    import diskcache  # type: ignore

    _HAVE_DISKCACHE = True
except Exception:  # pragma: no cover
    _HAVE_DISKCACHE = False


class Cache:
    """Simple key/value cache with per-entry TTL."""

    def __init__(self, directory: Path | None = None) -> None:
        self._dir = directory or cache_dir()
        self._dir.mkdir(parents=True, exist_ok=True)
        if _HAVE_DISKCACHE:
            self._dc = diskcache.Cache(str(self._dir / "diskcache"))
            self._sqlite = None
        else:
            self._dc = None
            self._sqlite = sqlite3.connect(
                str(self._dir / "cache.sqlite"), check_same_thread=False
            )
            self._sqlite.execute(
                "CREATE TABLE IF NOT EXISTS cache "
                "(k TEXT PRIMARY KEY, v TEXT, expires REAL)"
            )
            self._sqlite.commit()

    def get(self, key: str) -> Any | None:
        if self._dc is not None:
            return self._dc.get(key)
        cur = self._sqlite.execute(
            "SELECT v, expires FROM cache WHERE k = ?", (key,)
        )
        row = cur.fetchone()
        if not row:
            return None
        value, expires = row
        if expires and expires < time.time():
            self._sqlite.execute("DELETE FROM cache WHERE k = ?", (key,))
            self._sqlite.commit()
            return None
        return json.loads(value)

    def set(self, key: str, value: Any, ttl: int) -> None:
        if self._dc is not None:
            self._dc.set(key, value, expire=ttl)
            return
        expires = time.time() + ttl if ttl else 0
        self._sqlite.execute(
            "INSERT OR REPLACE INTO cache (k, v, expires) VALUES (?, ?, ?)",
            (key, json.dumps(value), expires),
        )
        self._sqlite.commit()

    def clear(self) -> None:
        if self._dc is not None:
            self._dc.clear()
        else:
            self._sqlite.execute("DELETE FROM cache")
            self._sqlite.commit()
