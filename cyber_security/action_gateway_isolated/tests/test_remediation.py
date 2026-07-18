"""Unit coverage for the N1/N2/N3/N8 remediations (no cluster required).

Cluster-dependent proofs (broker teardown against real RBAC, two-broker replay) run
in the end-to-end suite; these lock in the pieces that can be verified in isolation.
"""

from __future__ import annotations

import tempfile

import pytest

from action_gateway_isolated import crypto, policy_semantic
from action_gateway_isolated.audit_ledger import AuditLedger
from action_gateway_isolated.replaystore import ReplayStore

pytestmark = pytest.mark.skipif(not crypto.ASYMMETRIC_AVAILABLE,
                                reason="asymmetric crypto unavailable -> ISOLATION_NOT_PROVEN")


def _checks(m, kind, name="p"):
    return {c["check"] for c in policy_semantic.check(
        {"namespace": "protected", "kind": kind, "name": name}, m,
        allowed_namespaces={"protected"})}


# ---- N1: full workload surface, fail closed ----

def test_init_and_ephemeral_containers_validated():
    img = "registry.example.com/x@sha256:" + "a" * 64
    m = {"kind": "Pod", "spec": {
        "containers": [{"name": "c", "image": img}],
        "initContainers": [{"name": "i", "image": "evil:latest"}],
        "ephemeralContainers": [{"name": "e", "image": img,
                                 "securityContext": {"privileged": True}}]}}
    got = _checks(m, "Pod")
    assert "image_provenance" in got   # from the init container's unpinned image
    assert "privileged" in got         # from the ephemeral container


def test_envfrom_secret_and_serviceaccount_and_automount():
    img = "registry.example.com/x@sha256:" + "a" * 64
    m = {"kind": "Pod", "spec": {
        "serviceAccountName": "powerful", "automountServiceAccountToken": True,
        "containers": [{"name": "c", "image": img,
                        "envFrom": [{"secretRef": {"name": "creds"}}]}]}}
    got = _checks(m, "Pod")
    assert {"secret_envfrom", "service_account", "automount_token"} <= got


def test_projected_secret_and_csi_and_hostpath_volumes():
    img = "registry.example.com/x@sha256:" + "a" * 64
    m = {"kind": "Pod", "spec": {
        "containers": [{"name": "c", "image": img}],
        "volumes": [
            {"name": "h", "hostPath": {"path": "/"}},
            {"name": "c2", "csi": {"driver": "x"}},
            {"name": "p", "projected": {"sources": [{"secret": {"name": "s"}}]}}]}}
    got = _checks(m, "Pod")
    assert {"host_path", "csi_volume", "secret_mount"} <= got


def test_unknown_field_fails_closed():
    got = _checks({"kind": "Pod", "spec": {"containers": [], "wormhole": True}}, "Pod")
    assert any(c.startswith("unrecognized_pod_spec_field") for c in got)


def test_added_capabilities_and_privilege_escalation():
    img = "registry.example.com/x@sha256:" + "a" * 64
    m = {"kind": "Pod", "spec": {"containers": [{"name": "c", "image": img,
         "securityContext": {"capabilities": {"add": ["SYS_ADMIN"]},
                             "allowPrivilegeEscalation": True}}]}}
    got = _checks(m, "Pod")
    assert {"added_capabilities", "privilege_escalation"} <= got


def test_supported_fields_documented():
    # every table the validator enforces is enumerated for the README/docs
    assert set(policy_semantic.SUPPORTED_FIELDS) >= {
        "pod_spec", "container", "volume", "pod_security_context",
        "container_security_context", "env", "env_from"}
    assert "initContainers" in policy_semantic.SUPPORTED_FIELDS["pod_spec"]
    assert "ephemeralContainers" in policy_semantic.SUPPORTED_FIELDS["pod_spec"]


# ---- N2: durable orphan ledger lifecycle ----

def test_orphan_ledger_lifecycle():
    r = ReplayStore(tempfile.mktemp(suffix=".sqlite"))
    r.record_orphan("cap-1", "protected", at="t0", action_hash="ah", detail="boom")
    assert [o["sa"] for o in r.open_orphans()] == ["cap-1"]
    assert r.stats()["open_orphans"] == 1
    r.resolve_orphan("cap-1", "protected", at="t1")
    assert r.open_orphans() == []


def test_finalized_commit_never_released():
    r = ReplayStore(tempfile.mktemp(suffix=".sqlite"))
    r.claim_commit("ah", at="t0")
    r.finalize_commit("ah", "rh", audit_seq=5)
    r.release_commit("ah")                       # must NOT drop a finalized commit
    assert r.commit_record("ah")["result_hash"] == "rh"
    assert not r.claim_commit("ah", at="t1")     # still single-commit


# ---- N3: commit/audit divergence is detectable ----

def test_commit_audit_link_and_divergence_detection():
    from action_gateway_isolated import broker_core
    replay = ReplayStore(tempfile.mktemp(suffix=".sqlite"))
    audit = AuditLedger(tempfile.mktemp(suffix=".sqlite"))

    # a healthy commit: audit first, then finalize with the linked seq
    replay.claim_commit("ah1", at="t0")
    seq, _ = audit.append_record({"event": "COMMIT", "action_hash": "ah1"})
    replay.finalize_commit("ah1", "rh1", audit_seq=seq)

    # borrow the pure detector via a lightweight shim (no cluster)
    class _Shim(broker_core.BrokerCore):
        def __init__(self, replay, audit):
            self.replay = replay
            self.audit = audit
    shim = _Shim(replay, audit)
    assert shim.detect_divergence() == []

    # inject divergence: a finalized commit with NO audit record
    replay.claim_commit("ah2", at="t0")
    replay.finalize_commit("ah2", "rh2", audit_seq=None)
    div = shim.detect_divergence()
    assert any(d["action_hash"] == "ah2" and d["type"] == "commit_without_audit" for d in div)


# ---- N8: trust-root pinning ----

def test_trust_manifest_pins_and_rejects_swapped_key(tmp_path):
    for p in ("gateway", "policy_root"):
        _, vk = crypto.generate_keypair()
        (tmp_path / f"{p}.pub").write_bytes(vk.to_pem())
    crypto.write_trust_manifest(str(tmp_path), ("gateway", "policy_root"))
    kr = crypto.PublicKeyring(str(tmp_path))
    assert kr.pinned
    sk, vk = crypto.generate_keypair()
    sig = crypto.sign(sk, {"x": "1"})
    (tmp_path / "gateway.pub").write_bytes(vk.to_pem())  # swap in a different key
    kr2 = crypto.PublicKeyring(str(tmp_path))
    assert not kr2.verify("gateway", {"x": "1"}, sig)     # fingerprint mismatch -> refused


def test_unpinned_purpose_refused_when_manifest_present(tmp_path):
    _, vk = crypto.generate_keypair()
    (tmp_path / "gateway.pub").write_bytes(vk.to_pem())
    crypto.write_trust_manifest(str(tmp_path), ("gateway",))
    # add a key NOT in the manifest
    sk2, vk2 = crypto.generate_keypair()
    (tmp_path / "checkpoint.pub").write_bytes(vk2.to_pem())
    kr = crypto.PublicKeyring(str(tmp_path))
    assert not kr.verify("checkpoint", {"x": "1"}, crypto.sign(sk2, {"x": "1"}))
