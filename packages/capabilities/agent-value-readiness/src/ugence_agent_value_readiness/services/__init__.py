"""Deterministic services for the Agent Value Readiness engine (GV-3R-b).

The single canonical evaluator entry point :func:`evaluate_readiness` selects one
advisory readiness classification from a complete, structurally supplied
evaluation case. Advisory only — it authorizes no deployment and verifies no
evidence or policy authenticity.
"""

from __future__ import annotations

from .evaluator import EVALUATOR_VERSION, evaluate_readiness

__all__ = ["evaluate_readiness", "EVALUATOR_VERSION"]
