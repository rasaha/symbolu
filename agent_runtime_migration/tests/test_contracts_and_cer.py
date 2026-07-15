"""Commit B tests: typed contracts + native CER boundary + control-plane client."""
from __future__ import annotations

import copy

import pytest

from agent_runtime_migration.contracts import (
    Action, ContractError, Goal, Plan, ProposalError, RiskClass, GovernanceBoundaryError,
)
from agent_runtime_migration.proposal import (
    ProposalContext, build_cer, cer_identity, provenance_variant, same_identity, assert_binding,
)
from agent_runtime_migration.control_plane import ControlPlaneClient, ExecutionReceipt

NOW = "2026-01-01T00:10:00.000Z"


# ---------------- contracts ----------------
def test_goal_validation():
    Goal(goal_id="g1", objective="do a thing")
    with pytest.raises(ContractError):
        Goal(goal_id="", objective="x")
    with pytest.raises(ContractError):
        Goal(goal_id="g", objective="x", purpose_type="nonsense")


def test_governed_action_requires_profile():
    with pytest.raises(ContractError):
        Action(action_id="a1", kind="k", tool_name="t",
               risk_class=RiskClass.GOVERNED_CONSEQUENTIAL)  # no profile


def test_plan_next_action_respects_dependencies():
    a = Action(action_id="a", kind="k", tool_name="t", risk_class=RiskClass.LOCAL_READ_ONLY)
    b = Action(action_id="b", kind="k", tool_name="t", risk_class=RiskClass.LOCAL_READ_ONLY)
    plan = Plan(plan_id="p", goal_id="g", steps=[a, b], dependencies={"b": ("a",)})
    assert plan.next_action().action_id == "a"
    plan.mark_done("a")
    assert plan.next_action().action_id == "b"
    plan.mark_done("b")
    assert plan.is_complete


# ---------------- CER building ----------------
def _db_actuation(**over):
    a = {"operation": "DB_MUTATION",
         "target": {"connection_ref": "prod-orders", "schema": "public", "table": "orders"},
         "sql_operation": "UPDATE", "statement_digest": "sha256:" + "aa" * 32,
         "affected_scope": {"estimated_rows": "42", "unbounded": False},
         "transaction": {"mode": "in_transaction", "isolation": "SERIALIZABLE"},
         "expected_row_version": "orders@v17", "compensation_ref": "backup:orders",
         "reversibility": "REVERSIBLE_WITH_COST"}
    a.update(over)
    return a


def _db_ctx():
    op = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
          "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
          "migration_active": False, "freeze_active": False, "replication_healthy": True,
          "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
          "backup_available": True, "observation_time_s": 600.0}
    return ProposalContext(
        authority={"principal": "agent:data-ops", "permissions": ["db.write"],
                   "delegator": {"id": "dba", "type": "HUMAN"}, "delegation_chain": [{"grant": "*"}]},
        state_binding={"resource_version": "row-1001", "state_hash": "sha-256:" + "bb" * 32,
                       "as_of": "2026-01-01T00:09:30.000Z", "source": "database",
                       "correlation_id": "prod-orders/public/orders", "sequence_id": "1",
                       "operational": op},
        policy_ref={"version": "1.0.0+abc", "digest": "pd"},
        provenance={"runtime": "agent-runtime-migration", "model_provider": "ugence",
                    "model": "m", "objective": "update orders"})


def _db_action(**over):
    return Action(action_id="a1", kind="database.mutation", tool_name="db.mutation",
                  risk_class=RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1",
                  arguments={"actuation": _db_actuation(**over)})


def test_build_cer_valid():
    cer = build_cer(_db_action(), _db_ctx())
    assert cer["profile"] == "database.mutation.v1"
    assert len(cer_identity(cer)) == 64


def test_build_cer_fails_closed_on_invalid():
    bad = Action(action_id="a", kind="k", tool_name="t",
                 risk_class=RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1",
                 arguments={"actuation": {"operation": "DB_MUTATION"}})  # incomplete
    with pytest.raises(ProposalError):
        build_cer(bad, _db_ctx())


def test_build_cer_unsupported_profile():
    a = Action(action_id="a", kind="k", tool_name="t",
               risk_class=RiskClass.GOVERNED_CONSEQUENTIAL, profile="unknown.v9",
               arguments={"actuation": {"operation": "X"}})
    with pytest.raises(ProposalError):
        build_cer(a, _db_ctx())


def test_provenance_only_change_preserves_identity():
    cer = build_cer(_db_action(), _db_ctx())
    variant = provenance_variant(cer, {"runtime": "other", "model_provider": "x", "objective": "y"})
    assert same_identity(cer, variant)


def test_material_change_alters_identity():
    base = cer_identity(build_cer(_db_action(), _db_ctx()))
    changed = cer_identity(build_cer(_db_action(statement_digest="sha256:" + "99" * 32), _db_ctx()))
    assert base != changed


def test_assert_binding_fails_on_modified_action():
    cer = build_cer(_db_action(), _db_ctx())
    ident = cer_identity(cer)
    modified = copy.deepcopy(cer)
    modified["actuation"]["affected_scope"]["estimated_rows"] = "99"
    with pytest.raises(GovernanceBoundaryError):
        assert_binding(modified, ident)


# ---------------- control-plane boundary ----------------
def test_control_plane_proceed_yields_execution_reference():
    cer = build_cer(_db_action(), _db_ctx())
    decision = ControlPlaneClient().submit(cer, now=NOW)
    assert decision.composed_eligibility == "PROCEED"
    assert decision.eligible and decision.execution_reference
    assert decision.required_next_step == "execute"
    ControlPlaneClient.ensure_not_self_authorized(decision)


def test_control_plane_deny_blocks():
    cer = build_cer(_db_action(affected_scope={"estimated_rows": "42", "unbounded": True}), _db_ctx())
    decision = ControlPlaneClient().submit(cer, now=NOW)
    assert decision.composed_eligibility == "BLOCKED_BY_AUTHORIZATION"
    assert not decision.eligible and decision.execution_reference is None
    assert decision.required_next_step == "replan_or_stop"


def test_control_plane_hold():
    ctx = _db_ctx()
    ctx.state_binding["operational"]["freeze_active"] = True
    decision = ControlPlaneClient().submit(build_cer(_db_action(), ctx), now=NOW)
    assert decision.composed_eligibility == "HELD_BY_ACP"
    assert decision.required_next_step == "wait_or_reobserve"
    receipt = ExecutionReceipt.from_decision(decision)
    assert not receipt.permits_execution


def test_control_plane_pending_without_evidence():
    client = ControlPlaneClient(auto_evidence=False)
    decision = client.submit(build_cer(_db_action(), _db_ctx()), now=NOW)
    assert decision.composed_eligibility == "PENDING_AUTHORIZATION"
    assert decision.required_next_step == "provide_evidence_or_request_human"
