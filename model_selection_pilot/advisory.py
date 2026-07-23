"""Bounded cold-start self-assessment (task-shape fields ONLY).

In a REAL run this is produced by a preflight call to each candidate model
("assess this task's shape"), charged to arm G's cost/latency. Offline it is a
deterministic, intentionally OVERCONFIDENT stand-in so the ablation can run.

It emits ONLY allowed task-shape fields. It never emits price, latency,
compliance, eligibility, deployment, availability, context limit, or deprecation.
"""
from __future__ import annotations

from typing import Any, Dict

from common import clamp, det_signed, det_unit

ALLOWED_FIELDS = {"suggested_decomposition", "likely_tool_requirement",
                  "anticipated_reasoning_difficulty", "anticipated_execution_weakness",
                  "recommended_prompting_strategy"}
FORBIDDEN_FIELDS = {"price", "pricing", "cost", "latency", "expected_latency", "compliance",
                    "eligibility", "enterprise_eligibility", "deployment", "deployment_facts",
                    "provider_availability", "availability", "context_limit", "hard_context_limit",
                    "deprecation", "deprecation_status"}

# preflight tax charged to G (per candidate assessed)
PREFLIGHT_TOKENS_IN = 120
PREFLIGHT_TOKENS_OUT = 40
PREFLIGHT_LATENCY_MS = 300


class SelfAssessmentViolation(ValueError):
    pass


def validate(advisory: Dict[str, Any]) -> None:
    """Enforce the task-shape-only restriction: reject any forbidden field."""
    for k in advisory:
        if k in FORBIDDEN_FIELDS:
            raise SelfAssessmentViolation(f"advisory supplied forbidden field '{k}'")


def synth_advisory(model_id: str, task_view: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic overconfident advisory for (model, task). Task-shape only."""
    tc = task_view["task_class"]
    size = task_view.get("input_tokens_k", 0.0)
    # a bounded, biased self-difficulty read (overconfident => leans 'low')
    raw = 0.5 + det_signed(model_id, task_view["task_id"], "diff") * 0.25 - 0.08  # bias toward low
    difficulty = "low" if raw < 0.45 else "high" if raw > 0.72 else "medium"
    return {
        "suggested_decomposition": "decompose" if size > 6 else "single_pass",
        "likely_tool_requirement": tc in ("long_document_qa", "grounded_comparison"),
        "anticipated_reasoning_difficulty": difficulty,
        "anticipated_execution_weakness": "long-context recall" if size > 6 else "none",
        "recommended_prompting_strategy": "structured_json",
    }


def difficulty_to_quality_prior(difficulty: str) -> float:
    """Map an advisory self-difficulty into a small quality-prior adjustment."""
    return {"low": 0.10, "medium": 0.0, "high": -0.15}.get(difficulty, 0.0)
