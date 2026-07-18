"""Ugence native CER producer tests (deliverable 12)."""
from __future__ import annotations

from cer_v0_1 import spec
from cer_v0_1.actuation import ActuationRequest
from cer_v0_1.producers.ugence import UgenceCERProducer


def _req(**over):
    op = {"generation": 1, "desired_replicas": 10, "current_replicas": 10,
          "available_replicas": 10, "readiness_plasticity": 0.95,
          "active_rollback_watches": 0, "seconds_since_last_action": 600.0,
          "dependency_healthy": True, "freeze_active": False, "observation_time_s": 600.0}
    d = dict(cluster="fixture", namespace="protected", deployment="web", from_replicas=10,
             to_replicas=12, principal="agent:web-ops", permissions=("deploy",),
             delegator_id="sre", resource_version="1001", state_hash="sha-256:" + "ab" * 32,
             as_of="2026-01-01T00:09:30.000Z", operational=op, policy_version="1.0.0+abc",
             policy_digest="pd", correlation_id="protected/web")
    d.update(over)
    return ActuationRequest(**d)


def test_producer_emits_valid_cer():
    cer = UgenceCERProducer().propose(_req())
    spec.validate_cer(cer)  # does not raise
    assert cer["cer_version"] == "0.1"
    assert cer["profile"] == "cer.k8s.scale/0.1"
    assert cer["provenance"]["runtime"] == "ugence-agent-runtime"


def test_producer_stamps_provenance_not_identity():
    cer = UgenceCERProducer().propose(_req())
    # provenance present for audit
    assert cer["provenance"]["objective"]
    assert cer["provenance"]["model"] == "mistral-cg"
    # provenance not in the identity block
    for k in ("runtime", "model", "objective", "planner"):
        assert k not in cer["identity"]


def test_producer_deterministic():
    a = spec.action_digest(UgenceCERProducer().propose(_req()))
    b = spec.action_digest(UgenceCERProducer().propose(_req()))
    assert a == b


def test_producer_owns_no_authorization():
    # The producer proposes; it does not evaluate/authorize/execute.
    p = UgenceCERProducer()
    assert not hasattr(p, "authorize")
    assert not hasattr(p, "execute")
    assert not hasattr(p, "mint_token")


def test_identity_bearing_change_changes_digest():
    base = spec.action_digest(UgenceCERProducer().propose(_req()))
    assert spec.action_digest(UgenceCERProducer().propose(_req(to_replicas=13))) != base
    assert spec.action_digest(UgenceCERProducer().propose(_req(deployment="api"))) != base
