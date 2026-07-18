"""Clean-room standalone tests (independent of the reference).

These pin the clean-room to the FROZEN V0.2 base digests and prove it fails closed
on invalid input — using only the clean-room package and the frozen conformance
constants (no reference import needed for the assertions themselves).
"""
from __future__ import annotations

import copy

import pytest

from cer_v0_3 import cleanroom as cr
from cer_v0_3.cleanroom.errors import (
    CleanRoomError,
    ProhibitedFieldError,
    UnknownProfileError,
)

# Frozen V0.2 base digests (CER_V0_2_RESULTS.md).
SCALE_DIGEST = "07f7a6aaf20a55a8f03fc31f232420774c7361264cabf66b3a2ac74ffd3f7b51"
ROLLOUT_DIGEST = "72ddae264f4bb757fdeb137bbea0d44dfb36bf60161571447a82be0695c770e3"


def _sections():
    op = {"generation": 1, "desired_replicas": 10, "current_replicas": 10,
          "available_replicas": 10, "readiness_plasticity": 0.95,
          "active_rollback_watches": 0, "seconds_since_last_action": 600.0,
          "dependency_healthy": True, "freeze_active": False, "observation_time_s": 600.0}
    return {
        "cer_version": "0.2",
        "authority": {"principal": "agent:web-ops", "permissions": ["deploy"],
                      "delegator": {"id": "sre", "type": "HUMAN"},
                      "delegation_chain": [{"grant": "*"}]},
        "state_binding": {"resource_version": "1001", "state_hash": "sha-256:" + "ab" * 32,
                          "as_of": "2026-01-01T00:09:30.000Z", "source": "kubernetes",
                          "correlation_id": "protected/web", "sequence_id": "1",
                          "operational": op},
        "policy_ref": {"version": "1.0.0+abc", "digest": "pd"},
        "provenance": {"runtime": "r", "model_provider": "p", "objective": "o"},
    }


def _scale_cer():
    c = _sections()
    c.update(profile="kubernetes.scale.v1", risk_tier="GOVERNED", actuation={
        "operation": "DEPLOY",
        "target": {"cluster": "fixture", "namespace": "protected", "deployment": "web"},
        "arguments": {"replicas": "12"},
        "requested_state_transition": {"replicas": {"from": "10", "to": "12"}},
        "reversibility": "REVERSIBLE"})
    return c


def _rollout_cer():
    c = _sections()
    c.update(profile="kubernetes.rollout.v1", risk_tier="GOVERNED", actuation={
        "operation": "DEPLOY",
        "target": {"cluster": "fixture", "namespace": "protected", "deployment": "web"},
        "image_digest": "sha256:" + "cd" * 32,
        "current_manifest_digest": "sha256:" + "ef" * 32,
        "rollout_strategy": "RollingUpdate", "max_surge": "1", "max_unavailable": "0",
        "timeout_s": "600", "rollback_ref": "web-rev-41",
        "reversibility": "REVERSIBLE_WITH_COST"})
    return c


def test_cleanroom_matches_frozen_scale_digest():
    assert cr.action_digest(_scale_cer()) == SCALE_DIGEST


def test_cleanroom_matches_frozen_rollout_digest():
    assert cr.action_digest(_rollout_cer()) == ROLLOUT_DIGEST


def test_cleanroom_deterministic():
    c = _rollout_cer()
    assert cr.canonical_bytes(c) == cr.canonical_bytes(copy.deepcopy(c))


def test_cleanroom_provenance_excluded():
    a = _scale_cer()
    b = copy.deepcopy(a)
    b["provenance"] = {"runtime": "evil", "model_provider": "x", "objective": "y"}
    assert cr.action_digest(a) == cr.action_digest(b)


def test_cleanroom_profiles_domain_separated():
    assert cr.action_digest(_scale_cer()) != cr.action_digest(_rollout_cer())


def test_cleanroom_unknown_profile_fails_closed():
    bad = {**_scale_cer(), "profile": "kubernetes.delete.v9"}
    with pytest.raises(UnknownProfileError):
        cr.validate(bad)


def test_cleanroom_profile_downgrade_fails_closed():
    bad = copy.deepcopy(_scale_cer())
    bad["actuation"]["image_digest"] = "sha256:" + "00" * 32  # rollout-only
    with pytest.raises(ProhibitedFieldError):
        cr.validate(bad)


def test_cleanroom_unsupported_extension_fails_closed():
    bad = copy.deepcopy(_rollout_cer())
    bad["extensions"] = {"x-evil": {"a": "1"}}
    with pytest.raises(CleanRoomError):
        cr.validate(bad)


def test_cleanroom_bare_number_rejected():
    # A bare integer in arguments must be rejected (numerics are typed strings).
    bad = copy.deepcopy(_scale_cer())
    bad["actuation"]["arguments"] = {"replicas": 12}  # int, not "12"
    with pytest.raises(CleanRoomError):
        cr.canonical_bytes(bad)
