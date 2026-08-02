"""Cooperative cancellation token (runtime-local safeguard). Thread-safe.

Cancellation is cooperative: the engine checks the token at deterministic points
(before starting each task) and unwinds the workflow to CANCELLED. Setting the
token does not itself interrupt an in-flight provider call.
"""
from __future__ import annotations

import threading


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()
