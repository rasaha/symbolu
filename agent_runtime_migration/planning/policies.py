"""Planning policies (runtime-owned; no governance)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class PlanningPolicy:
    max_steps: int = 32
    allow_replan: bool = True
