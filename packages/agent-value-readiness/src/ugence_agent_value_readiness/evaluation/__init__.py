"""The GV-3R-b deterministic readiness-determination evaluator.

One canonical entry point (:func:`evaluate_readiness`) over an immutable
:class:`ReadinessEvaluationCase`. It selects the readiness tier itself — the case
carries no classification field — and returns an advisory determination plus a
deterministic explanatory trace.

It is a determination evaluator over **structurally supplied** gate results: it
performs no evidence admission or verification, no benchmark resolution, no
metric-to-threshold comparison, no policy-authenticity verification, no causal
attribution, and no deployment authorization.
"""

from __future__ import annotations

from .case import ReadinessEvaluationCase
from .codes import (
    EVALUATOR_FORMULA_VERSION,
    EVALUATOR_ID,
    ConditionDecisionCode,
    ReadinessAdvisoryCode,
    ReadinessReasonCode,
    ReadinessRuleId,
)
from .errors import ReadinessEvaluationError
from .evaluator import evaluate_readiness
from .trace import ConditionDecision, ReadinessEvaluationResult, ReadinessEvaluationTrace

__all__ = [
    "EVALUATOR_ID",
    "EVALUATOR_FORMULA_VERSION",
    "ReadinessEvaluationError",
    "ReadinessEvaluationCase",
    "ReadinessEvaluationTrace",
    "ReadinessEvaluationResult",
    "ConditionDecision",
    "ReadinessRuleId",
    "ReadinessReasonCode",
    "ReadinessAdvisoryCode",
    "ConditionDecisionCode",
    "evaluate_readiness",
]
