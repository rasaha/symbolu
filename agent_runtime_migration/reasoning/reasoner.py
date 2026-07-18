"""Minimal reasoner hook (optional; runtime-owned). No governance."""
from __future__ import annotations
from ..contracts.goal import Goal


class Reasoner:
    def summarize(self, goal: Goal) -> str:
        return f"objective: {goal.objective} (purpose={goal.purpose_type})"
