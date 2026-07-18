"""Cross-profile security tests (deliverable 13) — §9 assertions."""
from __future__ import annotations

import copy

import pytest

from cer_v0_2 import envelope as e2
from cer_v0_2.actuation import EnvelopeContext, RolloutActuation, ScaleActuation
from cer_v0_2.producers.ugence import UgenceCERProducer
from cer_v0_2.profiles.base import CERValidationError

import sys
sys.path.insert(0, "cyber_security/action_gate_reference")
from action_gate_ref import evidence as ev_mod, projection  # noqa: E402
from action_gate_ref import approval as approval_mod  # noqa: E402

NOW = "2026-01-01T00:10:00.000Z"


def _ctx():
    op = {"generation": 1, "desired_replicas": 10, "current_replicas": 10,
          "available_replicas": 10, "readiness_plasticity": 0.95,
          "active_rollback_watches": 0, "seconds_since_last_action": 600.0,
          "dependency_healthy": True, "freeze_active": False, "observation_time_s": 600.0}
    return EnvelopeContext(principal="agent:web-ops", permissions=("deploy",), delegator_id="sre",
                           resource_version="1001", state_hash="sha-256:" + "ab" * 32,
                           as_of="2026-01-01T00:09:30.000Z", operational=op,
                           policy_version="1.0.0+abc", policy_digest="pd",
                           correlation_id="protected/web")


def _scale_cer():
    return UgenceCERProducer().propose(_ctx(), ScaleActuation(
        cluster="fixture", namespace="protected", deployment="web",
        from_replicas=10, to_replicas=12))


def _rollout_cer():
    return UgenceCERProducer().propose(_ctx(), RolloutActuation(
        cluster="fixture", namespace="protected", deployment="web",
        image_digest="sha256:" + "cd" * 32, current_manifest_digest="sha256:" + "ef" * 32,
        rollback_ref="web-rev-41"))


def _ah(cer):
    return projection.action_hash(e2.to_envelope(cer), identity_profile="v2")


def test_scale_evidence_cannot_authorize_rollout():
    ev = ev_mod.build_evidence(bound_to=_ah(_scale_cer()), producer="p", generated_at=NOW,
                               valid_until="2030-01-01T00:00:00.000Z", evidence_version="1",
                               kind="signed_artifact", fidelity_or_confidence="HIGH",
                               content={"a": "b"})
    from action_gate_ref.errors import EvidenceBindingError
    # bound to scale action; does not bind the rollout action (raises, fail closed)
    assert ev_mod.verify_binding(ev, _ah(_scale_cer()))
    with pytest.raises(EvidenceBindingError):
        ev_mod.verify_binding(ev, _ah(_rollout_cer()))


def test_rollout_approval_cannot_authorize_scale():
    ah_roll = _ah(_rollout_cer())
    ap = approval_mod.build_approval(
        action_hash=ah_roll, policy_hash="ph", approver_policy="single",
        approvers=[{"id": "security-lead", "key_id": "approver:security-lead"}],
        approval_scope={"operation": "DEPLOY", "target": ["protected/web"]},
        constraints={}, issued_at=NOW, expiration="2030-01-01T00:00:00.000Z", nonce="n1")
    from action_gate_ref.errors import ActionHashMismatchError
    # verifies against the rollout action
    assert approval_mod.verify_approval(ap, e2.to_envelope(_rollout_cer()),
                                        active_policy_hash="ph", now=NOW, identity_profile="v2")
    # but NOT against the scale action
    with pytest.raises(ActionHashMismatchError):
        approval_mod.verify_approval(ap, e2.to_envelope(_scale_cer()),
                                     active_policy_hash="ph", now=NOW, identity_profile="v2")


def test_profile_participates_in_domain_separation():
    # same target, different profile -> different digest
    assert e2.action_digest(_scale_cer()) != e2.action_digest(_rollout_cer())


def test_identical_field_names_no_collision():
    # both have identical target; digests still differ (tool_name separates)
    assert _scale_cer()["actuation"]["target"] == _rollout_cer()["actuation"]["target"]
    assert e2.action_digest(_scale_cer()) != e2.action_digest(_rollout_cer())


def test_unsupported_profile_fails_closed():
    bad = {**_scale_cer(), "profile": "kubernetes.delete.v9"}
    with pytest.raises(CERValidationError):
        e2.validate_cer(bad)


def test_profile_downgrade_fails_closed():
    downgrade = copy.deepcopy(_scale_cer())
    downgrade["actuation"]["image_digest"] = "sha256:" + "00" * 32  # rollout-only
    with pytest.raises(CERValidationError):
        e2.validate_cer(downgrade)


def test_v01_and_v02_cannot_be_confused():
    # a V0.1-shaped CER (cer_version 0.1) is rejected by the V0.2 validator
    v01_like = {"cer_version": "0.1", "profile": "cer.k8s.scale/0.1", "identity": {}}
    with pytest.raises(CERValidationError):
        e2.validate_cer(v01_like)


def test_legacy_actiongate_profile_remains_verifiable():
    # v1 (legacy) identity still computes and differs from v2 for the same envelope
    env = e2.to_envelope(_scale_cer())
    assert projection.action_hash(env, identity_profile="v1") != \
        projection.action_hash(env, identity_profile="v2")


def test_provenance_cannot_alter_digest():
    a = _rollout_cer()
    b = copy.deepcopy(a)
    b["provenance"] = {"runtime": "evil", "model": "x", "objective": "y"}
    assert e2.action_digest(a) == e2.action_digest(b)


def test_material_change_always_alters_digest():
    base = e2.action_digest(_rollout_cer())
    changed = copy.deepcopy(_rollout_cer())
    changed["actuation"]["image_digest"] = "sha256:" + "99" * 32
    assert e2.action_digest(changed) != base
