"""Unit tests: asymmetric crypto, durable replay, authz, policy, audit ledger.

No cluster or process isolation required.
"""

from __future__ import annotations

import tempfile

import pytest

from action_gateway_isolated import authz, crypto, policy_semantic
from action_gateway_isolated.audit_ledger import AuditLedger
from action_gateway_isolated.replaystore import ReplayStore

pytestmark = pytest.mark.skipif(not crypto.ASYMMETRIC_AVAILABLE,
                                reason="asymmetric crypto (ecdsa) unavailable -> ISOLATION_NOT_PROVEN")


# ---- asymmetric signing: verification != forgery ----

def test_ed25519_sign_verify_public_only():
    sk, vk = crypto.generate_keypair()
    obj = {"action_hash": "abc", "n": "1"}
    sig = crypto.sign(sk, obj)
    assert crypto.verify(vk, obj, sig)
    assert not crypto.verify(vk, {"action_hash": "abc", "n": "2"}, sig)  # tamper


def test_cross_key_forgery_rejected():
    sk1, _ = crypto.generate_keypair()
    _, vk2 = crypto.generate_keypair()
    sig = crypto.sign(sk1, {"x": "1"})
    assert not crypto.verify(vk2, {"x": "1"}, sig)  # a different key cannot verify


def test_public_keyring_has_no_private_keys(tmp_path):
    sk, vk = crypto.generate_keypair()
    (tmp_path / "gateway.pub").write_bytes(vk.to_pem())
    kr = crypto.PublicKeyring(str(tmp_path))
    assert kr.verify("gateway", {"x": "1"}, crypto.sign(sk, {"x": "1"}))
    assert not kr.has_private_key()


# ---- durable replay ----

def test_nonce_single_use_across_reopen():
    db = tempfile.mktemp(suffix=".sqlite")
    r = ReplayStore(db)
    assert r.claim_nonce("exec_token", "n1", at="t0")
    assert not r.claim_nonce("exec_token", "n1", at="t1")   # replay rejected
    r2 = ReplayStore(db)  # reopen == restart
    assert not r2.claim_nonce("exec_token", "n1", at="t2")  # durable across restart


def test_single_commit_claim():
    r = ReplayStore(tempfile.mktemp(suffix=".sqlite"))
    assert r.claim_commit("ah1", at="t0")
    assert not r.claim_commit("ah1", at="t1")   # duplicate commit rejected
    r.release_commit("ah1")                      # only releases if not finalized
    assert r.claim_commit("ah1", at="t2")


def test_global_sequence_no_reset():
    r = ReplayStore(tempfile.mktemp(suffix=".sqlite"))
    assert r.advance_sequence("stream", 5)
    assert not r.advance_sequence("stream", 5)   # rollback/equal rejected
    assert not r.advance_sequence("stream", 3)   # rollback rejected
    assert r.advance_sequence("stream", 6)


# ---- authorization artifacts ----

def _kr(tmp_path, purposes):
    keys = {}
    for p in purposes:
        sk, vk = crypto.generate_keypair()
        (tmp_path / f"{p.replace(':', '__')}.pub").write_bytes(vk.to_pem())
        keys[p] = sk
    return crypto.PublicKeyring(str(tmp_path)), keys


def test_approval_verify_and_forgery(tmp_path):
    kr, keys = _kr(tmp_path, ["approver:security-lead"])
    ap = authz.build_approval("approver:security-lead", keys["approver:security-lead"],
                              action_hash="ah", policy_hash="ph", issued_at="t0",
                              expiry="t9", nonce="n")
    assert authz.verify_approval(kr, ap, action_hash="ah", policy_hash="ph", now="t1")
    assert not authz.verify_approval(kr, ap, action_hash="OTHER", policy_hash="ph", now="t1")
    # forged by a non-approver key
    other, _ = crypto.generate_keypair()
    forged = authz.build_approval("approver:security-lead", other, action_hash="ah",
                                  policy_hash="ph", issued_at="t0", expiry="t9", nonce="n2")
    assert not authz.verify_approval(kr, forged, action_hash="ah", policy_hash="ph", now="t1")


def test_exec_authz_gateway_signature(tmp_path):
    kr, keys = _kr(tmp_path, ["gateway"])
    intent = {"action_hash": "ah", "gateway_identity": "spiffe://x/gateway", "expiry": "t9",
              "namespace": "protected", "kind": "ConfigMap", "name": "c", "verb": "update"}
    doc = authz.build_exec_authz(keys["gateway"], intent, [])
    ok, reason = authz.verify_exec_authz(kr, doc, now="t1",
                                         expected_gateway_identity="spiffe://x/gateway")
    assert ok, reason
    # tamper the intent -> signature invalid
    doc["intent"]["name"] = "evil"
    ok2, reason2 = authz.verify_exec_authz(kr, doc, now="t1",
                                           expected_gateway_identity="spiffe://x/gateway")
    assert not ok2 and reason2 == "E_AUTHZ_BAD_GATEWAY_SIGNATURE"


def test_exec_authz_identity_and_expiry(tmp_path):
    kr, keys = _kr(tmp_path, ["gateway"])
    intent = {"action_hash": "ah", "gateway_identity": "spiffe://x/gateway", "expiry": "t0"}
    doc = authz.build_exec_authz(keys["gateway"], intent, [])
    ok, reason = authz.verify_exec_authz(kr, doc, now="t9",
                                         expected_gateway_identity="spiffe://x/gateway")
    assert not ok and reason == "E_AUTHZ_EXPIRED"
    ok2, reason2 = authz.verify_exec_authz(kr, doc, now="t0", expected_gateway_identity="OTHER")
    assert not ok2 and reason2 == "E_AUTHZ_IDENTITY"


# ---- semantic policy ----

def test_policy_blocks_high_value_risks():
    checks = lambda m, kind="Pod", name="p": {c["check"] for c in policy_semantic.check(
        {"namespace": "protected", "kind": kind, "name": name}, m,
        allowed_namespaces={"protected"})}
    priv = {"kind": "Pod", "spec": {"containers": [{"name": "c", "image": "x",
            "securityContext": {"privileged": True}}]}}
    got = checks(priv)
    assert "privileged" in got and "image_provenance" in got
    host = {"kind": "Pod", "spec": {"hostNetwork": True, "containers": []}}
    assert "host_namespaces" in checks(host)
    rb = {"kind": "RoleBinding", "roleRef": {"name": "cluster-admin"}}
    assert "powerful_rolebinding" in checks(rb, kind="RoleBinding", name="rb")
    role = {"kind": "Role", "rules": [{"verbs": ["escalate"], "resources": ["x"], "apiGroups": [""]}]}
    assert "dangerous_verb" in checks(role, kind="Role", name="r")


def test_pinned_image_allowed():
    ok = {"kind": "Pod", "spec": {"containers": [{"name": "c",
          "image": "registry.example.com/app@sha256:" + "a" * 64,
          "resources": {"limits": {"cpu": "1"}}}]}}
    got = {c["check"] for c in policy_semantic.check(
        {"namespace": "protected", "kind": "Pod", "name": "p"}, ok,
        allowed_namespaces={"protected"})}
    assert "image_provenance" not in got


def test_rollback_requires_real_backup():
    assert not policy_semantic.rollback_verified({"backup_ref": "x"}, backup_exists=lambda r: False)
    assert policy_semantic.rollback_verified({"backup_ref": "x"}, backup_exists=lambda r: True)
    assert not policy_semantic.rollback_verified({}, backup_exists=lambda r: True)


# ---- audit ledger + separate checkpoint key ----

def test_audit_chain_and_checkpoint(tmp_path):
    led = AuditLedger(tempfile.mktemp(suffix=".sqlite"))
    for i in range(3):
        led.append({"event": "COMMIT", "i": i})
    assert led.verify_chain()
    cp_sk, cp_vk = crypto.generate_keypair()
    (tmp_path / "checkpoint.pub").write_bytes(cp_vk.to_pem())
    kr = crypto.PublicKeyring(str(tmp_path))
    led.sign_checkpoint(cp_sk, at="t0")
    v = led.verify_against_checkpoint(kr)
    assert v["intact"] and v["checkpoint_sig_ok"] and not v["truncated"]


def test_audit_worm_blocks_rewrite(tmp_path):
    import sqlite3
    path = tempfile.mktemp(suffix=".sqlite")
    led = AuditLedger(path)
    led.append({"event": "COMMIT", "x": 1})
    c = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("UPDATE records SET payload='tampered'")
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("DELETE FROM records")
