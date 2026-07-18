"""Cross-domain security invariants (deliverable 15, §11) + the cross-domain run."""
from __future__ import annotations

import copy

import pytest

from cer_v0_3 import cleanroom as cr
from cer_v0_3 import control_plane as cp
from cer_v0_3 import envelope as e3
from cer_v0_3.conformance import cross_domain
from cer_v0_3.profiles.base import CERValidationError, SecretMaterialError

from action_gate_ref import approval as approval_mod, evidence as ev_mod
from action_gate_ref.errors import ActionHashMismatchError, EvidenceBindingError

NOW = "2026-01-01T00:10:00.000Z"


def _db_op(**over):
    d = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
         "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
         "migration_active": False, "freeze_active": False, "replication_healthy": True,
         "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
         "backup_available": True, "observation_time_s": 600.0}
    d.update(over)
    return d


def _db_cer(**actover):
    act = {"operation": "DB_MUTATION",
           "target": {"connection_ref": "prod-orders", "schema": "public", "table": "orders"},
           "sql_operation": "UPDATE", "statement_digest": "sha256:" + "aa" * 32,
           "affected_scope": {"estimated_rows": "42", "unbounded": False},
           "transaction": {"mode": "in_transaction", "isolation": "SERIALIZABLE"},
           "expected_row_version": "orders@v17", "compensation_ref": "backup:orders",
           "reversibility": "REVERSIBLE_WITH_COST"}
    act.update(actover)
    return {"cer_version": "0.2", "profile": "database.mutation.v1", "risk_tier": "GOVERNED",
            "authority": {"principal": "agent:data-ops", "permissions": ["db.write"],
                          "delegator": {"id": "dba", "type": "HUMAN"},
                          "delegation_chain": [{"grant": "*"}]},
            "state_binding": {"resource_version": "row-1001", "state_hash": "sha-256:" + "bb" * 32,
                              "as_of": "2026-01-01T00:09:30.000Z", "source": "database",
                              "correlation_id": "prod-orders/public/orders", "sequence_id": "1",
                              "operational": _db_op()},
            "policy_ref": {"version": "1.0.0+abc", "digest": "pd"}, "actuation": act,
            "provenance": {"runtime": "r", "model_provider": "p", "model": "m", "objective": "o"}}


def _k8s_scale():
    return cross_domain._v2_scale_cer()


# 1. clean-room and original agree for every valid vector; both fail closed on invalid
def test_cross_domain_run_all_passed():
    r = cross_domain.run()
    assert r["all_passed"] is True
    assert r["metrics"]["cleanroom_agreement"] > 0
    assert r["metrics"]["invalid_ok"] == r["metrics"]["invalid_total"] > 0


# 2. no secret enters identity, canonical bytes, or output
def test_no_secret_in_identity():
    with pytest.raises(SecretMaterialError):
        e3.validate_cer(_db_cer(password="hunter2"))
    ok = _db_cer()
    assert "password" not in cr.canonical_bytes(ok).decode()


# 3. same actuation, independent producers -> same digest (from the runner)
def test_producer_agreement():
    r = cross_domain.run()
    assert r["metrics"]["producer_agreement"] > 0


# 4. material change -> different digest
def test_material_change_alters_digest():
    base = e3.action_digest(_db_cer())
    assert e3.action_digest(_db_cer(statement_digest="sha256:" + "99" * 32)) != base
    assert e3.action_digest(_db_cer(sql_operation="INSERT")) != base


# 5/6. cross-domain evidence + approval cannot transfer
def test_k8s_evidence_cannot_authorize_db():
    k8s_ah = e3.action_digest(_k8s_scale())
    db_ah = e3.action_digest(_db_cer())
    ev = ev_mod.build_evidence(bound_to=k8s_ah, producer="p", generated_at=NOW,
                               valid_until="2030-01-01T00:00:00.000Z", evidence_version="1",
                               kind="signed_artifact", fidelity_or_confidence="HIGH",
                               content={"a": "b"})
    with pytest.raises(EvidenceBindingError):
        ev_mod.verify_binding(ev, db_ah)


def test_db_approval_cannot_authorize_k8s():
    db_ah = e3.action_digest(_db_cer())
    ap = approval_mod.build_approval(
        action_hash=db_ah, policy_hash="ph", approver_policy="single",
        approvers=[{"id": "sec", "key_id": "approver:security-lead"}],
        approval_scope={"operation": "DB_MUTATION", "target": ["prod-orders/public/orders"]},
        constraints={}, issued_at=NOW, expiration="2030-01-01T00:00:00.000Z", nonce="n1")
    from cer_v0_2 import envelope as e2
    with pytest.raises(ActionHashMismatchError):
        approval_mod.verify_approval(ap, e2.to_envelope(_k8s_scale()),
                                     active_policy_hash="ph", now=NOW, identity_profile="v2")


# 7. Kubernetes and database actions cannot collide
def test_no_cross_domain_collision():
    assert e3.action_digest(_db_cer()) != e3.action_digest(_k8s_scale())


# 8/9. unknown profile + profile downgrade fail closed
def test_unknown_profile_and_downgrade_fail_closed():
    with pytest.raises(CERValidationError):
        e3.validate_cer({**_db_cer(), "profile": "database.delete.v9"})
    with pytest.raises(CERValidationError):
        e3.validate_cer(_db_cer(replicas="3"))  # K8s-only field


# 10. runtime provenance does not affect identity
def test_provenance_invariant():
    a = _db_cer()
    b = copy.deepcopy(a)
    b["provenance"] = {"runtime": "evil", "model_provider": "x", "objective": "y"}
    assert e3.action_digest(a) == e3.action_digest(b)


# 11/12. ActionGate DENY cannot be overridden; ACP cannot grant authorization
def test_actiongate_deny_final():
    r = cp.run_control_plane(_db_cer(affected_scope={"estimated_rows": "42", "unbounded": True}),
                             now=NOW, auto_evidence=True)
    assert r.combined_outcome == "BLOCKED_BY_AUTHORIZATION"


def test_acp_cannot_authorize_pending():
    # gate pending (no simulation) -> ACP permissive cannot make it PROCEED
    r = cp.run_control_plane(_db_cer(), now=NOW, auto_evidence=False)
    assert r.combined_outcome == "PENDING_AUTHORIZATION"
    assert not r.eligible


# 13. stale state invalidates execution eligibility
def test_stale_state_holds():
    cer = _db_cer()
    cer["state_binding"]["operational"] = _db_op(observed_row_version="orders@v18")
    r = cp.run_control_plane(cer, now=NOW, auto_evidence=True)
    assert not r.eligible


# 14. no runtime-specific branch in frozen AG/ACP
def test_no_runtime_branch():
    r = cross_domain.run()
    assert r["ownership_no_runtime_switch"] is True
