"""Public-API freeze + maturity tests (§20, §23)."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import ugence_agent_workforce_composer as pkg
import ugence_agent_workforce_composer.api as api

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_ARTIFACT = _ROOT / "artifacts" / "public_api.json"


def _snapshot():
    script = _ROOT / "scripts" / "public_api_snapshot.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                            cwd=str(_ROOT), env={"PYTHONPATH": str(_ROOT / "src"),
                                                 "PATH": ""})
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_public_api_matches_frozen_artifact():
    frozen = json.loads(_ARTIFACT.read_text())
    assert _snapshot() == frozen, "public API drifted from artifacts/public_api.json"


def test_all_exports_importable_and_public():
    for name in api.__all__:
        assert hasattr(api, name), name
        # dunder version markers are allowed; no single-underscore internals
        assert name.startswith("__") or not name.startswith("_"), name


def test_required_public_surface_present():
    required = {
        "CompilerWorkflowAdapter", "adapt_compiled_workflow", "WorkflowRoleRequirement",
        "NonAgentDisposition", "AgentProfile", "AgentCapability", "AgentCapabilityEvidence",
        "AgentRegistrySnapshot", "EnterpriseAgentPolicy", "EligibilityPolicy",
        "EligibilityState", "EliminationReason", "AgentEligibilityResult",
        "RoleEligibilityReport", "EligibilityExplanation", "EligibilityReplayRecord",
        "evaluate_agent_eligibility", "evaluate_registry_for_role",
        "evaluate_workflow_eligibility", "version_info",
    }
    assert required.issubset(set(api.__all__))


def test_no_ranking_or_team_surface_leaked():
    for banned in ("rank_agents", "score_agents", "compose_team", "select_agent",
                   "AgentTeamPlan", "PolicyWeights", "assign_permissions"):
        assert banned not in api.__all__


def test_version_and_contract():
    assert pkg.__version__ == "0.1.0"
    assert pkg.CONTRACT_VERSION == "awc.v1"


def test_maturity_is_honest():
    info = api.version_info().to_dict()
    for k in ("canonical_object_model_implemented", "compiler_adapter_implemented",
              "hard_constraint_eligibility_implemented", "deterministic_replay_verified"):
        assert info[k] is True, k
    for k in ("agent_ranking_implemented", "team_composition_implemented",
              "permission_assignment_implemented", "runtime_handoff_implemented",
              "h16_migration_implemented", "live_registry_implemented",
              "pilot_validated", "production_certified"):
        assert info[k] is False, k
