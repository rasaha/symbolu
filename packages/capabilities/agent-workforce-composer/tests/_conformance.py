"""Loader for the committed compiler-v2 conformance fixtures (self-contained;
needs neither the compiler nor the Governance Studio app at test time)."""
from __future__ import annotations

import json
import os

import ugence_agent_workforce_composer.api as awc

_PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(_PKG, "conformance", "governance_studio_v2")
SCENARIOS = ("procurement", "customer_support", "cybersecurity_success",
             "cybersecurity_no_feasible_team")
LT = 1_000_000.0


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def manifest():
    return _read(os.path.join(CONF, "EQUIVALENCE_MANIFEST.json"))


def load(scenario_id: str) -> dict:
    base = os.path.join(CONF, scenario_id)
    return {
        "v1_workflow": _read(os.path.join(base, "v1_workflow.json")),
        "v1_overlay": _read(os.path.join(base, "v1_overlay.json")),
        "v2_workflow": _read(os.path.join(base, "v2_workflow.json")),
        "v2_overlay": _read(os.path.join(base, "v2_overlay.json")),
        "registry": awc.AgentRegistrySnapshot.model_validate(_read(os.path.join(base, "registry.json"))),
        "enterprise_policy": awc.EnterpriseAgentPolicy.model_validate(_read(os.path.join(base, "enterprise_policy.json"))),
        "eligibility_policy": awc.EligibilityPolicy.model_validate(_read(os.path.join(base, "eligibility_policy.json"))),
        "ranking_policy": awc.AgentRankingPolicy.model_validate(_read(os.path.join(base, "ranking_policy.json"))),
        "composition_policy": awc.TeamCompositionPolicy.model_validate(_read(os.path.join(base, "composition_policy.json"))),
        "permission_policy": awc.PermissionBoundingPolicy.model_validate(_read(os.path.join(base, "permission_policy.json"))),
        "fallback_policy": awc.AgentFallbackPolicy.model_validate(_read(os.path.join(base, "fallback_policy.json"))),
    }


def plan(adaptation, s: dict):
    return awc.build_agent_team_plan(
        adaptation, s["registry"], s["enterprise_policy"], s["eligibility_policy"],
        s["ranking_policy"], s["composition_policy"], s["permission_policy"],
        s["fallback_policy"], LT)
