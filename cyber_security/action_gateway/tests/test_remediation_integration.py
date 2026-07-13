"""R1.5 runtime integration tests — gateway.

Proves the gateway attaches advisory remediation AFTER the finalized decision without
changing the decision, hashes, token/approval binding, or backward compatibility.
"""

from __future__ import annotations

import copy
import json
import tempfile

import pytest

from action_gateway import Gateway
from action_gateway import remediation_runtime as RR
from action_gateway._ref import evidence as ref_evidence, projection
from action_gateway.clock import FixedClock
from action_gateway.mapping import ToolRequest

NOW = "2026-07-12T14:00:00.000Z"


def _gw():
    return Gateway(sandbox_root=tempfile.mkdtemp(prefix="gw-rem-"), clock=FixedClock(NOW))


def _deploy_req():
    return ToolRequest(tool="terraform", verb="apply", target=["svc://billing"], args={},
                       principal="agent://sre/1", agent_id="agent://sre/1", key_id="k7")


def _artifact(ah, gw):
    return ref_evidence.build_evidence(
        bound_to=ah, producer="registry", generated_at=gw.clock.now(),
        valid_until=gw.clock.plus(3600), evidence_version="1", kind="signed_artifact",
        fidelity_or_confidence="HIGH", content={"artifact": "sha256:abc", "signed": "yes"})


def _sim(ah, gw, fidelity="HIGH"):
    return ref_evidence.build_evidence(
        bound_to=ah, producer="terraform-plan", generated_at=gw.clock.now(),
        valid_until=gw.clock.plus(3600), evidence_version="1", kind="simulation",
        fidelity_or_confidence=fidelity, is_simulation=True,
        content={"coverage": "0.9", "predicted_changes": [], "affected_resources": []})


_DECISION_KEYS = {"request_id", "outcome", "state", "dispositive_rules",
                  "applied_constraints", "action_hash", "token_hash", "reason"}
_REM_KEYS = {"response_schema_version", "all_unmet_conditions", "required_changes",
             "retryability", "disclosure", "retry_budget"}


# --------------------------------------------------------------------------- #
def test_gateway_off_is_byte_identical():
    g1 = _gw(); s1 = g1.submit_action(_deploy_req())
    off = g1.evaluate_action(s1["request_id"])
    g2 = _gw(); s2 = g2.submit_action(_deploy_req())
    off2 = g2.evaluate_action(s2["request_id"], remediation_mode="OFF")
    assert off == off2
    assert set(off) == _DECISION_KEYS                 # no remediation keys leak


def test_gateway_standard_adds_fields_without_changing_decision():
    g1 = _gw(); s1 = g1.submit_action(_deploy_req())
    off = g1.evaluate_action(s1["request_id"])
    g2 = _gw(); s2 = g2.submit_action(_deploy_req())
    std = g2.evaluate_action(s2["request_id"], remediation_mode="STANDARD")
    assert set(std) - set(off) == _REM_KEYS
    for k in _DECISION_KEYS:                           # decision fields identical
        assert std[k] == off[k]
    assert std["response_schema_version"] == "1.1"


def test_gateway_decision_and_hash_unchanged_off_vs_full():
    g1 = _gw(); s1 = g1.submit_action(_deploy_req())
    g1.evaluate_action(s1["request_id"])
    g2 = _gw(); s2 = g2.submit_action(_deploy_req())
    g2.evaluate_action(s2["request_id"], remediation_mode="FULL", remediation_trusted=True)
    assert g1.audit_log()["head"] == g2.audit_log()["head"]        # audit hash unchanged
    assert g1.status(s1["request_id"])["action_hash"] == \
        g2.status(s2["request_id"])["action_hash"]                 # action hash unchanged


def test_full_untrusted_is_clamped_to_standard():
    g = _gw(); s = g.submit_action(_deploy_req())
    r = g.evaluate_action(s["request_id"], remediation_mode="FULL", remediation_trusted=False)
    assert r["disclosure"]["mode"] == "STANDARD"


def test_full_trusted_reveals_bounds_standard_hides_them():
    # DB_MUTATION scope-exceeded exposes a threshold; STANDARD must hide it, FULL reveal it
    req = ToolRequest(tool="filesystem", verb="write", target=["db://prod/orders#t"],
                      args={"unbounded": False, "affected_count": "25000"},
                      principal="agent://sre/1", agent_id="agent://sre/1", key_id="k7")
    g = _gw(); s = g.submit_action(req); ah = s["action_hash"]
    ev = [_sim(ah, g, "MEDIUM")]
    full = g.evaluate_action(s["request_id"], evidence=ev, remediation_mode="FULL",
                             remediation_trusted=True)
    g2 = _gw(); s2 = g2.submit_action(req)
    std = g2.evaluate_action(s2["request_id"], evidence=[_sim(s2["action_hash"], g2, "MEDIUM")],
                             remediation_mode="STANDARD")
    assert "25000" in json.dumps(full) and "10000" in json.dumps(full)
    assert "25000" not in json.dumps(std) and "10000" not in json.dumps(std)


def test_remediation_carries_no_authority_and_cannot_execute():
    g = _gw(); s = g.submit_action(_deploy_req())
    r = g.evaluate_action(s["request_id"], remediation_mode="FULL", remediation_trusted=True)
    blob = json.dumps({k: r[k] for k in _REM_KEYS}).lower()
    for bad in ("execution_token", "token_hash", "credential", "signature", "\"sig\"", "key_id"):
        assert bad not in blob
    # remediation on a non-ALLOW outcome still yields no token
    assert r["outcome"] == "REQUEST_MORE_EVIDENCE" and r["token_hash"] is None


def test_approval_binding_and_token_unchanged_on_allow_path():
    # full ALLOW path (artifact + HIGH sim) must mint an identical token with remediation on
    g1 = _gw(); s1 = g1.submit_action(_deploy_req()); ah1 = s1["action_hash"]
    off = g1.evaluate_action(s1["request_id"], evidence=[_artifact(ah1, g1), _sim(ah1, g1)])
    g2 = _gw(); s2 = g2.submit_action(_deploy_req()); ah2 = s2["action_hash"]
    on = g2.evaluate_action(s2["request_id"], evidence=[_artifact(ah2, g2), _sim(ah2, g2)],
                            remediation_mode="FULL", remediation_trusted=True)
    assert off["outcome"] == "ALLOW" and on["outcome"] == "ALLOW"
    assert off["token_hash"] == on["token_hash"]      # token binding unchanged
    assert on["required_changes"] == []                # nothing to remediate on ALLOW
    # and the ALLOW request actually executes with remediation enabled
    res = g2.execute_action(s2["request_id"])
    assert res["state"] == "COMPLETED"


def test_response_size_limiting_truncates_and_marks():
    req = ToolRequest(tool="filesystem", verb="write", target=["db://prod/orders#t"],
                      args={"unbounded": False, "affected_count": "25000"},
                      principal="agent://sre/1", agent_id="agent://sre/1", key_id="k7")
    g = _gw(); s = g.submit_action(req)
    tiny = RR.RemediationLimits(max_required_changes=0, max_payload_bytes=64)
    r = g.evaluate_action(s["request_id"], evidence=[_sim(s["action_hash"], g, "MEDIUM")],
                          remediation_mode="FULL", remediation_trusted=True,
                          remediation_limits=tiny)
    assert r["required_changes"] == []
    assert r["disclosure"]["truncated"] is True
    assert any(m.startswith("required_changes[>0]") for m in r["disclosure"]["redacted_fields"])


def test_backward_compat_default_call_signature():
    # the pre-R1.5 call (no remediation kwargs) behaves exactly as before
    g = _gw(); s = g.submit_action(_deploy_req())
    r = g.evaluate_action(s["request_id"], evidence=None, approvals=None)
    assert set(r) == _DECISION_KEYS


def test_clamp_and_normalize_helpers():
    from action_gateway._ref import remediation as R
    assert RR.clamp_mode("FULL", False) == R.STANDARD
    assert RR.clamp_mode("FULL", True) == R.FULL
    assert RR.clamp_mode("standard", False) == R.STANDARD
    assert RR.normalize_mode("bogus") == R.OFF
    assert RR.normalize_mode("human-only") == R.HUMAN_ONLY
