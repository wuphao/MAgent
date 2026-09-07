from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor


def make_executor(max_workers: int = 4) -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=max_workers)
