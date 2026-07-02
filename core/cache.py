"""Simple disk-backed JSON cache with TTL for ONC API results.

Keeps ``generate_dashboard.py`` fast: expensive ONC calls (device discovery,
archive-file listings, scalar data) are memoised to ``cache/`` so repeat runs
and refreshes are near-instant. Delete the ``cache/`` directory (or call
``clear()``) to force a cold rebuild.

Environment:
    CACHE_ENABLED   set to "0" to bypass the cache entirely.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"


def enabled() -> bool:
    return os.getenv("CACHE_ENABLED", "1") not in ("0", "false", "False", "no")


def _path_for(key: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def get(key: str, ttl_seconds: float) -> Any | None:
    if not enabled() or ttl_seconds <= 0:
        return None
    path = _path_for(key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if time.time() - payload.get("_ts", 0) > ttl_seconds:
        return None
    return payload.get("value")


def put(key: str, value: Any) -> None:
    if not enabled():
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _path_for(key).write_text(
            json.dumps({"_ts": time.time(), "key": key, "value": value}, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass


def cached(key: str, ttl_seconds: float, producer: Callable[[], Any]) -> Any:
    """Return the cached value for ``key`` or compute + store it via ``producer``."""
    hit = get(key, ttl_seconds)
    if hit is not None:
        return hit
    value = producer()
    put(key, value)
    return value


def clear() -> int:
    """Delete all cache entries. Returns the number of files removed."""
    if not CACHE_DIR.exists():
        return 0
    count = 0
    for path in CACHE_DIR.glob("*.json"):
        try:
            path.unlink()
            count += 1
        except OSError:
            pass
    return count
