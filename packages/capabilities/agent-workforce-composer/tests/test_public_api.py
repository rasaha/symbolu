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


def test_no_execution_or_grant_surface_leaked():
    # P2 migration: ranking/composition/AgentTeamPlan are now deliverables; the
    # meaningful boundary is that NO execution / granting / scheduling surface leaks.
    for banned in ("execute_agent", "run_agent", "dispatch", "grant_permission",
                   "assign_permission", "invoke_model", "schedule_workflow",
                   "authorize_action", "reassign_agent"):
        assert banned not in api.__all__


def test_version_and_contract():
    # P2: distribution/product moved to 0.2.0; P1 contract awc.v1 preserved; the
    # additive composition contract is awc.composition.v1.
    assert pkg.__version__ == "0.2.0"
    assert pkg.CONTRACT_VERSION == "awc.v1"
    assert pkg.version_info().to_dict()["composition_contract_version"] == "awc.composition.v1"


def test_maturity_is_honest():
    info = api.version_info().to_dict()
    for k in ("canonical_object_model_implemented", "compiler_adapter_implemented",
              "hard_constraint_eligibility_implemented", "deterministic_replay_verified",
              # P2 capabilities now implemented:
              "deterministic_ranking_implemented", "agent_ranking_implemented",
              "team_composition_implemented", "permission_bound_proposal_implemented",
              "fallback_planning_implemented", "agent_team_plan_implemented"):
        assert info[k] is True, k
    for k in ("permission_assignment_implemented", "permission_granting_implemented",
              "runtime_handoff_implemented", "runtime_execution_implemented",
              "live_availability_implemented", "h16_migration_implemented",
              "model_selection_integration_implemented", "h22_integration_implemented",
              "live_registry_implemented", "pilot_validated", "production_certified"):
        assert info[k] is False, k
