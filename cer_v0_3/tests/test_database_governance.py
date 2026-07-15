"""Cross-domain governance tests for database.mutation.v1 (deliverable 13/15).

Proves the four composed outcomes reproduce in the database domain using the FROZEN
ActionGate gate + the new database ACP adapter composed with the frozen compose().
"""
from __future__ import annotations

import copy

import pytest

from cer_v0_3 import control_plane as cp
from cer_v0_3 import envelope as e3

NOW = "2026-01-01T00:10:00.000Z"


def _op(**over):
    d = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
         "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
         "migration_active": False, "freeze_active": False, "replication_healthy": True,
         "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
         "backup_available": True, "observation_time_s": 600.0}
    d.update(over)
    return d


def _cer(op=None, **actover):
    act = {"operation": "DB_MUTATION",
           "target": {"connection_ref": "prod-orders", "schema": "public", "table": "orders"},
           "sql_operation": "UPDATE", "statement_digest": "sha256:" + "aa" * 32,
           "affected_scope": {"estimated_rows": "42", "unbounded": False},
           "transaction": {"mode": "in_transaction", "isolation": "SERIALIZABLE"},
           "expected_row_version": "orders@v17", "compensation_ref": "backup:orders:2026-01-01",
           "reversibility": "REVERSIBLE_WITH_COST"}
    act.update(actover)
    return {"cer_version": "0.2", "profile": "database.mutation.v1", "risk_tier": "GOVERNED",
            "authority": {"principal": "agent:data-ops", "permissions": ["db.write"],
                          "delegator": {"id": "dba", "type": "HUMAN"},
                          "delegation_chain": [{"grant": "*"}]},
            "state_binding": {"resource_version": "row-1001", "state_hash": "sha-256:" + "bb" * 32,
                              "as_of": "2026-01-01T00:09:30.000Z", "source": "database",
                              "correlation_id": "prod-orders/public/orders", "sequence_id": "1",
                              "operational": op or _op()},
            "policy_ref": {"version": "1.0.0+abc", "digest": "pd"}, "actuation": act,
            "provenance": {"runtime": "ugence-agent-runtime", "model_provider": "ugence",
                           "model": "m", "objective": "update orders"}}


def _run(cer, **kw):
    return cp.run_control_plane(cer, now=NOW, auto_evidence=True, **kw)


def test_valid_safe_proceeds():
    r = _run(_cer())
    assert r.combined_outcome == "PROCEED" and r.eligible
    assert r.actiongate_outcome == "ALLOW_WITH_CONSTRAINTS"


def test_freeze_held_by_acp():
    r = _run(_cer(op=_op(freeze_active=True)))
    assert r.combined_outcome == "HELD_BY_ACP"
    assert "NO_ACTIVE_FREEZE_FAILED" in r.reason_codes


def test_migration_held_by_acp():
    r = _run(_cer(op=_op(migration_active=True)))
    assert r.combined_outcome == "HELD_BY_ACP"


def test_state_drift_held_by_acp():
    r = _run(_cer(op=_op(observed_row_version="orders@v18")))
    assert r.combined_outcome == "HELD_BY_ACP"
    assert not r.eligible


def test_scope_over_bound_held_by_acp():
    # within ActionGate's 10000 cap but over the ACP fixture's max_affected_rows
    r = _run(_cer(op=_op(max_affected_rows=10),
                  affected_scope={"estimated_rows": "42", "unbounded": False}))
    assert r.combined_outcome == "HELD_BY_ACP"


def test_unbounded_blocked_by_authorization():
    r = _run(_cer(affected_scope={"estimated_rows": "42", "unbounded": True}))
    assert r.combined_outcome == "BLOCKED_BY_AUTHORIZATION"
    assert r.actiongate_outcome == "DENY"


def test_missing_simulation_pending():
    r = cp.run_control_plane(_cer(), now=NOW, auto_evidence=False)
    assert r.combined_outcome == "PENDING_AUTHORIZATION"


def test_high_risk_without_rollback_held():
    # irreversible + no compensation + no backup -> ROLLBACK_AVAILABLE fails
    cer = _cer(op=_op(backup_available=False), reversibility="IRREVERSIBLE")
    del cer["actuation"]["compensation_ref"]
    r = _run(cer)
    assert r.combined_outcome == "HELD_BY_ACP"


def test_unreachable_db_held():
    r = _run(_cer(op=_op(reachable=False)))
    assert r.combined_outcome == "HELD_BY_ACP"


def test_secret_material_fails_closed():
    from cer_v0_3.profiles.base import SecretMaterialError
    bad = _cer()
    bad["actuation"]["password"] = "hunter2"
    with pytest.raises(SecretMaterialError):
        e3.validate_cer(bad)


def test_unsupported_sql_operation_fails_closed():
    from cer_v0_3.profiles.base import CERValidationError
    with pytest.raises(CERValidationError):
        e3.validate_cer(_cer(sql_operation="DELETE"))
