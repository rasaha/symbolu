"""Realistic model-shaped mock planner.

Emits plan JSON in the same shape a real planner model would (an ``actions`` array
of {tool, description, arguments}). Deterministic given the task text. This is a
mock (option 4), used alongside the recorded-replay adapter (option 3) for
reproducibility. It is NOT a live model.
"""
from __future__ import annotations
import json
from typing import Any, Dict, List


class RealisticPlannerModel:
    name = "realistic-mock"

    def __init__(self, plan: List[Dict[str, Any]] | None = None):
        # Optional explicit plan for a task; else a single read step.
        self._plan = plan

    def generate(self, prompt: str) -> str:
        # A real model would read the task from the prompt; here we return a
        # deterministic plan payload. The runtime parses this like any model output.
        if self._plan is not None:
            payload = {"actions": self._plan}
        else:
            payload = {"purpose_type": "task",
                       "actions": [{"tool": "respond", "description": "answer the request",
                                    "arguments": {}}]}
        return json.dumps(payload)

    call = generate
