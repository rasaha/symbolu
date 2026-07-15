"""Advisory budget accountant — a runtime-local safeguard, NOT authorization.

Stopping a run for exceeding a step/token budget is a runtime safeguard (like
cancellation). It never authorizes an action; it can only stop the loop early.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class BudgetAccountant:
    max_steps: int = 100
    max_tokens: int = 1_000_000
    steps: int = 0
    tokens: int = 0

    def charge(self, *, steps: int = 0, tokens: int = 0) -> None:
        self.steps += steps
        self.tokens += tokens

    @property
    def exceeded(self) -> bool:
        return self.steps > self.max_steps or self.tokens > self.max_tokens
