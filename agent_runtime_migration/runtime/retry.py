"""Deterministic retry policy (attempt counting; no wall clock)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class RetryPolicy:
    max_attempts: int = 1
    _attempts: int = 0

    def should_retry(self) -> bool:
        return self._attempts < self.max_attempts

    def record_attempt(self) -> None:
        self._attempts += 1

    def reset(self) -> None:
        self._attempts = 0
