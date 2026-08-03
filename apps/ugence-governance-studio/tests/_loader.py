"""Load committed demo fixtures from JSON back into real AWC schema objects.

The tests deliberately consume the *serialized* fixtures (not the in-memory
authoring objects) so they verify exactly what is committed under
``demo_data/``. Loading uses the AWC public model classes' ``model_validate``;
there is no bespoke deserialization and no policy logic here.
"""
from __future__ import annotations

import json
import os

import ugence_agent_workforce_composer.api as awc

_TESTS = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.dirname(_TESTS)
DEMO_DATA = os.path.join(_APP, "demo_data")
EXPECTED = os.path.join(_APP, "expected_outputs")

SCENARIOS = (
    "procurement",
    "customer_support",
    "cybersecurity_success",
    "cybersecurity_no_feasible_team",
)

_POLICY_FILES = {
    "enterprise_policy": ("enterprise_agent_policy.json", awc.EnterpriseAgentPolicy),
    "eligibility_policy": ("eligibility_policy.json", awc.EligibilityPolicy),
    "ranking_policy": ("ranking_policy.json", awc.AgentRankingPolicy),
    "composition_policy": ("composition_policy.json", awc.TeamCompositionPolicy),
    "permission_policy": ("permission_policy.json", awc.PermissionBoundingPolicy),
    "fallback_policy": ("fallback_policy.json", awc.AgentFallbackPolicy),
}


def _read(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_inputs(scenario_id: str) -> dict:
    base = os.path.join(DEMO_DATA, scenario_id)
    s = {
        "scenario_id": scenario_id,
        "workflow": _read(os.path.join(base, "compiled_workflow.json")),
        "overlay": _read(os.path.join(base, "enterprise_role_overlay.json")),
        "registry": awc.AgentRegistrySnapshot.model_validate(
            _read(os.path.join(base, "agent_registry_snapshot.json"))),
    }
    for key, (fname, cls) in _POLICY_FILES.items():
        s[key] = cls.model_validate(_read(os.path.join(base, fname)))
    return s


def scenario_manifest(scenario_id: str) -> dict:
    return _read(os.path.join(DEMO_DATA, scenario_id, "scenario_manifest.json"))


def expected(scenario_id: str, artifact: str) -> dict:
    return _read(os.path.join(EXPECTED, scenario_id, artifact))


def manifest() -> dict:
    return _read(os.path.join(EXPECTED, "MANIFEST.json"))


def run_pipeline(s: dict) -> dict:
    """Run the real P1/P2 pipeline over loaded inputs (delegates to the same
    routine the generator uses, so tests and freeze share one code path)."""
    import generate_fixtures
    return generate_fixtures._run_pipeline(s)
