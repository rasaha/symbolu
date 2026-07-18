"""Commit E tests: legacy compatibility (supported / unsupported / warnings / refusal)."""
from __future__ import annotations

import warnings

import pytest

from agent_runtime_migration.compatibility import (
    AgentRuntimeDeprecationWarning, get_legacy, to_goal,
)
from agent_runtime_migration.contracts import Action, ContractError, GovernanceBoundaryError, RiskClass
from agent_runtime_migration.runtime import AgentRuntime
from agent_runtime_migration.runtime import state as st
from agent_runtime_migration.control_plane import ControlPlaneClient, GovernedExecutor
from agent_runtime_migration.tools import ToolRegistry


# --- duck-typed legacy shapes (no import of the legacy package) ---
class _LegacyAction:
    def __init__(self, action_id, action_type, parameters=None):
        self.action_id = action_id
        self.action_type = action_type
        self.description = action_type
        self.parameters = parameters or {}


class _LegacyGoal:
    def __init__(self, purpose, actions, purpose_type="task"):
        self.purpose = purpose
        self.purpose_type = purpose_type
        self.actions = actions


def _envelope_sections():
    op = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
          "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
          "migration_active": False, "freeze_active": False, "replication_healthy": True,
          "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
          "backup_available": True, "observation_time_s": 600.0}
    return {
        "actuation": {"operation": "DB_MUTATION",
                      "target": {"connection_ref": "prod-orders", "schema": "public", "table": "orders"},
                      "sql_operation": "UPDATE", "statement_digest": "sha256:" + "aa" * 32,
                      "affected_scope": {"estimated_rows": "42", "unbounded": False},
                      "transaction": {"mode": "in_transaction", "isolation": "SERIALIZABLE"},
                      "expected_row_version": "orders@v17", "compensation_ref": "backup:orders",
                      "reversibility": "REVERSIBLE_WITH_COST"},
        "authority": {"principal": "agent:data-ops", "permissions": ["db.write"],
                      "delegator": {"id": "dba", "type": "HUMAN"}, "delegation_chain": [{"grant": "*"}]},
        "state_binding": {"resource_version": "row-1001", "state_hash": "sha-256:" + "bb" * 32,
                          "as_of": "2026-01-01T00:09:30.000Z", "source": "database",
                          "correlation_id": "prod-orders/public/orders", "sequence_id": "1",
                          "operational": op},
        "policy_ref": {"version": "1.0.0+abc", "digest": "pd"}}


def test_supported_legacy_local_workflow_migrates_and_runs():
    legacy = _LegacyGoal("summarize docs", [_LegacyAction("s", "read.doc")])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        goal = to_goal(legacy)
    assert goal.metadata["plan"][0].risk_class is RiskClass.LOCAL_READ_ONLY
    reg = ToolRegistry()
    reg.register("read.doc", lambda a: "DOC", RiskClass.LOCAL_READ_ONLY, fast_path_permitted=True)
    out = AgentRuntime(executor=GovernedExecutor(registry=reg, client=ControlPlaneClient(),
                                                 now_provider=lambda: "2026-01-01T00:10:00.000Z")).run(goal)
    assert out.status == st.COMPLETED


def test_legacy_governed_action_routes_through_cer():
    legacy = _LegacyGoal("apply update",
                         [_LegacyAction("m", "database.mutation", _envelope_sections())])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        goal = to_goal(legacy)
    action = goal.metadata["plan"][0]
    assert action.risk_class is RiskClass.GOVERNED_CONSEQUENTIAL
    assert action.profile == "database.mutation.v1"


def test_unsupported_legacy_governed_action_fails_explicitly():
    # governed action_type but missing CER envelope sections -> explicit failure, not silent run
    legacy = _LegacyGoal("bad", [_LegacyAction("m", "database.mutation", {"foo": "bar"})])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(ContractError):
            to_goal(legacy)


def test_deprecation_warning_emitted():
    legacy = _LegacyGoal("x", [_LegacyAction("s", "read.doc")])
    with pytest.warns(AgentRuntimeDeprecationWarning):
        to_goal(legacy)


def test_legacy_governance_authority_refused():
    with pytest.raises(GovernanceBoundaryError):
        get_legacy("SafeMCPGateway")
    with pytest.raises(GovernanceBoundaryError):
        get_legacy("GovernanceService")
