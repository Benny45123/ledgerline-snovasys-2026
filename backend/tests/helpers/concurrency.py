"""
How this works / why it is safe:
This module provides a multi-threaded concurrency test harness using threading.Barrier.
It releases N worker threads at the exact same instant to attack the system under
maximum race conditions. No 'sleep' guessing is used; the barrier guarantees true concurrency.
Worker exceptions and results are collected deterministically.
"""

import threading
from collections.abc import Callable
from typing import Any


def fire_concurrent(
    n: int,
    fn: Callable[[int], Any],
    start_barrier: bool = True,
) -> list[tuple[int, Any, Any]]:
    """Execute fn(i) across n concurrent threads released at the same instant.

    Returns:
        List of (thread_index, result, exception) tuples.
    """
    barrier = threading.Barrier(n) if start_barrier else None
    results: list[tuple[int, Any, Any]] = [None] * n  # type: ignore

    def worker(i: int) -> None:
        try:
            if barrier:
                barrier.wait(timeout=10.0)
            res = fn(i)
            results[i] = (i, res, None)
        except Exception as e:
            results[i] = (i, None, e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)

    return results
