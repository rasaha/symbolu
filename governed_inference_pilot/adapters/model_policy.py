"""ModelPolicy adapter (read-only). Selects among ExecutionGate-eligible models using a constrained
quality-floor objective consistent with the reconciliation study (argmin cost s.t. quality >= q_min).
Abstains when no eligible model meets the floor. Uses the registry's quality/cost fields; does not
re-implement routing logic beyond the frozen objective's shape."""
from __future__ import annotations

from typing import Any, Dict, List

from .base import AdapterResult

_STAGE = "model_policy"


def run(registry: List[Dict[str, Any]], eligible_models: List[str], telemetry: Dict[str, Any],
        request: Dict[str, Any]) -> AdapterResult:
    q_min = float(telemetry.get("q_min", request.get("acceptable_quality_threshold", 0.6)))
    eligible = [m for m in registry if m["model_id"] in eligible_models]
    qualifying = [m for m in eligible if m.get("quality", 0.0) >= q_min]
    if not eligible:
        return AdapterResult(_STAGE, "reconciliation_v1", "abstain", ["MODEL.NO_ELIGIBLE"],
                             source_repr={"eligible_models": eligible_models})
    if not qualifying:
        return AdapterResult(
            _STAGE, "reconciliation_v1", "abstain", ["MODEL.NO_MODEL_MEETS_FLOOR"],
            source_repr={"q_min": q_min, "qualities": {m["model_id"]: m.get("quality") for m in eligible}},
            extra={"q_min": q_min})
    chosen = min(qualifying, key=lambda m: (m.get("cost", 0.0), -m.get("quality", 0.0)))
    return AdapterResult(
        _STAGE, "reconciliation_v1", "selected", ["MODEL.SELECTED"],
        source_repr={"q_min": q_min, "candidates": [m["model_id"] for m in qualifying]},
        transformed_repr={"selected_model": chosen["model_id"], "quality": chosen.get("quality"),
                          "cost": chosen.get("cost")},
        extra={"selected_model": chosen["model_id"], "quality": chosen.get("quality")})
