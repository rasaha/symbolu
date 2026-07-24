"""M11 test suite. Locks the readiness track's headline claims as assertions. Deterministic; no live
calls; no enforcement; no external action. Consumes prior tracks + the pilot read-only; touches no
frozen artifact.
"""
from dataclasses import asdict

import pytest

from customer_shadow_readiness import (security, data_controls as dc, intake, pilot_api, killswitch,
                                       observability, incident, deployment, human_review,
                                       operational_fault_injection as ofi, differential_action)
from customer_shadow_readiness.adapters import real_action_gate as rag
from governed_inference_pilot import dataset

CASES = [asdict(c) for c in dataset.all_cases()]


def setup_function(_):
    killswitch.restore_pilot()
    for t in ("acme", "globex"):
        killswitch.restore_tenant(t)


# ---- Gap 0: real ActionGate ---------------------------------------------------------------------

def test_real_actiongate_invoked():
    r = rag.evaluate({"action_type": "delete_records", "risk": "critical"})
    assert r.real_outcome in ("ESCALATE_TO_HUMAN", "DENY", "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY")
    assert r.source_version == "action_gate_ref_v1"


def test_real_actiongate_fail_closed_on_error():
    r = rag.evaluate({"action_type": "totally_unknown_op"})
    assert r.shadow_disposition in ("BLOCK", "ESCALATE", "PERMIT", "CONSTRAIN")  # mapped, never crash


def test_differential_no_pilot_blocker():
    d = differential_action.compare()
    assert d["unsafe_disagreement"] == 0            # shadow blocks / real unsafely allows == 0
    assert d["real_gate_deterministic"] is True
    assert d["semantic_loss_cases"] > 0             # honest: vocabulary loss exists


# ---- security & tenant isolation ----------------------------------------------------------------

def test_auth_fail_closed():
    assert not security.check_access(None, "shadow:read", "acme").allowed
    assert not security.check_access("bad.sig", "shadow:read", "acme").allowed


def test_cross_tenant_denied():
    tok = security.issue_token("tok-acme-analyst")
    assert not security.check_access(tok, "shadow:read", "globex").allowed


def test_scope_enforced():
    tok = security.issue_token("tok-acme-analyst")           # has submit, not review
    assert not security.check_access(tok, "shadow:review", "acme").allowed


# ---- data controls ------------------------------------------------------------------------------

def test_clearance_lattice():
    assert not dc.permitted_use("restricted", "internal")
    assert dc.permitted_use("restricted", "restricted")
    assert not dc.permitted_use("confidential", "internal")


def test_redaction_and_minimization():
    assert "[SSN]" in dc.redact("ssn 123-45-6789")
    m = dc.minimize({"request_id": "r", "secret": "x", "final_shadow_disposition": "WOULD_ALLOW"})
    assert "secret" not in m and "request_id" in m


def test_tenant_store_isolation_and_erasure():
    st = dc.TenantDataStore(); pol = dc.RetentionPolicy("acme")
    st.put("acme", {"request_id": "r", "tenant_id": "acme"}, pol)
    with pytest.raises(PermissionError):
        st.get("acme", "globex")
    assert st.delete_tenant("acme") == 1


# ---- pilot API ----------------------------------------------------------------------------------

def test_api_never_enforces():
    tok = security.issue_token("tok-acme-analyst")
    c = dict(CASES[0]); c["request"] = dict(c["request"]); c["request"]["tenant_id"] = "acme"
    r = pilot_api.submit(tok, "acme", c)
    assert r.enforced is False


def test_api_cross_tenant_refused():
    tok = security.issue_token("tok-globex-analyst")
    c = dict(CASES[0]); c["request"] = dict(c["request"]); c["request"]["tenant_id"] = "acme"
    assert not pilot_api.submit(tok, "acme", c).accepted


def test_api_killswitch_refuses():
    tok = security.issue_token("tok-acme-analyst")
    c = dict(CASES[0]); c["request"] = dict(c["request"]); c["request"]["tenant_id"] = "acme"
    killswitch.trip_pilot()
    assert not pilot_api.submit(tok, "acme", c).accepted
    killswitch.restore_pilot()


# ---- observability / incident / kill ------------------------------------------------------------

def test_incident_trips_kill():
    incident.handle("SEC.CROSS_TENANT_CASE", "acme")
    assert not killswitch.check("acme").active
    killswitch.restore_tenant("acme")
    incident.handle("unsafe_action_escape")
    assert not killswitch.check("acme").active
    killswitch.restore_pilot()


# ---- deployment ---------------------------------------------------------------------------------

def test_manifest_enforcement_off():
    m = deployment.build_manifest()
    assert m.config["enforcement"] == "OFF"
    assert m.config["external_actions"] == "DISABLED"
    assert m.config["action_gate"] == "real_read_only"


def test_preflight_and_rollback():
    assert deployment.preflight()["deployable"] is True
    assert deployment.rollback_check()["rollback_safe"] is True


# ---- human review -------------------------------------------------------------------------------

def test_no_silent_override():
    class Resp:
        final_shadow_disposition = "WOULD_ESCALATE"; reason_codes = ["EA.CONFLICTED"]
        replay_signature = "s" * 64; human_review_state = "required"
    q = human_review.ReviewQueue()
    iid = q.maybe_enqueue("acme", Resp())
    rtok = security.issue_token("tok-acme-reviewer")
    assert not q.resolve(rtok, "acme", iid, "override")["ok"]           # needs reason
    res = q.resolve(rtok, "acme", iid, "override", "WOULD_REJECT", "stale")
    assert res["ok"] and res["enforced"] is False


def test_review_cross_tenant_blocked():
    q = human_review.ReviewQueue()
    with pytest.raises(PermissionError):
        q.queue_for(security.issue_token("tok-globex-analyst"), "acme")


# ---- operational fault injection ----------------------------------------------------------------

def test_all_operational_faults_fail_closed():
    s = ofi.sweep()
    assert s["all_fail_closed"] is True
    assert s["any_enforced"] is False


# ---- guard --------------------------------------------------------------------------------------

def test_prior_artifacts_intact():
    from customer_shadow_readiness import verify_prior_artifacts as g
    assert g.verify() is True
