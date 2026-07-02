"""Tiny helper to run IO-bound ONC calls concurrently.

ONC discovery / archive / scalar calls are network-bound, so a thread pool
gives a large speedup without the complexity of asyncio. Order is preserved.

Environment:
    MAX_WORKERS   thread pool size (default 8).
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def thread_map(fn: Callable[[T], R], items: Iterable[T], max_workers: int | None = None) -> list[R]:
    materialized = list(items)
    if not materialized:
        return []
    if max_workers is None:
        max_workers = int(os.getenv("MAX_WORKERS", "8"))
    max_workers = max(1, min(max_workers, len(materialized)))
    if max_workers == 1:
        return [fn(item) for item in materialized]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(fn, materialized))
