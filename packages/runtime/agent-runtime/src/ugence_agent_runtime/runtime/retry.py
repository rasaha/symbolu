"""Deterministic retry policy (attempt counting; no wall clock).

The policy only counts attempts; it makes no scheduling decision and reads no
clock, so retry behavior is fully deterministic and testable. Backoff timing, when
a deployment needs it, is supplied by an injected scheduler — not baked in here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("RetryPolicy.max_attempts must be >= 1")

    def should_retry(self, attempts: int) -> bool:
        """True if another attempt is permitted given the attempts already made."""
        return attempts < self.max_attempts
