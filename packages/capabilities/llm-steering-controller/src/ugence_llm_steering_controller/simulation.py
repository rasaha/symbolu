"""Deterministic offline simulation / replay over local fixtures.

Every simulation result is explicitly labelled as fixture-derived and never as real
production routing validation. No provider is contacted; no model is executed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .api import build_controller
from .contracts import SteeringRequest
from .policy import RoutingPolicy
from .version import POLICY_VERSION, SCHEMA_VERSION

# Mandatory evidence labels stamped onto every simulation output.
FIXTURE_LABELS = {
    "evidence_class": "FAKE_LOCAL_FIXTURE",
    "provider_status": "NO_PROVIDER_CALLED",
    "execution_status": "NO_MODEL_EXECUTED",
}


def _policy_from(d: Optional[Dict[str, Any]], req: SteeringRequest) -> Optional[RoutingPolicy]:
    if not d:
        return None
    return RoutingPolicy(
        preference=d.get("preference", req.quality_preference),
        weight_overrides=d.get("weight_overrides", {}) or {},
        policy_version=d.get("policy_version", "") or "",
    )


def run_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Run one fixture scenario: ``{name, registry, request, policy?}``.

    Returns a labelled record with the resulting :class:`SteeringResult` as a dict.
    """
    name = scenario.get("name", "unnamed")
    registry = scenario["registry"]
    request = SteeringRequest.from_dict(scenario["request"])
    controller = build_controller(registry)
    policy = _policy_from(scenario.get("policy"), request)
    result = controller.recommend(request, policy)
    record = {
        "scenario": name,
        "labels": dict(FIXTURE_LABELS),
        "schema_version": SCHEMA_VERSION,
        "policy_version": result.policy_version or POLICY_VERSION,
        "status": result.status,
        "decision_id": result.decision_id,
        "result": result.to_dict(),
    }
    if "expect" in scenario:
        record["expect"] = scenario["expect"]
        record["expectation_met"] = _check_expectation(result, scenario["expect"])
    return record


def _check_expectation(result, expect: Dict[str, Any]) -> bool:
    if "status" in expect and result.status != expect["status"]:
        return False
    rec = result.recommendation
    if "recommended_model" in expect:
        if rec is None or rec.recommended_model != expect["recommended_model"]:
            return False
    return True


def run_suite(scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run a list of fixture scenarios deterministically."""
    records = [run_scenario(s) for s in scenarios]
    checked = [r for r in records if "expectation_met" in r]
    return {
        "labels": dict(FIXTURE_LABELS),
        "schema_version": SCHEMA_VERSION,
        "total": len(records),
        "checked": len(checked),
        "expectations_met": sum(1 for r in checked if r["expectation_met"]),
        "scenarios": records,
    }


__all__ = ["run_scenario", "run_suite", "FIXTURE_LABELS"]
