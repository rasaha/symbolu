"""Governance-equivalence (deliverable 14) + compatibility (deliverable 15) tests."""
from __future__ import annotations

import inspect

import pytest

from cer_v0_2 import control_plane as cp
from cer_v0_2 import envelope as e2
from cer_v0_2.actuation import EnvelopeContext, RolloutActuation, ScaleActuation
from cer_v0_2.producers.langgraph_adapter import LangGraphCERAdapter
from cer_v0_2.producers.openai_agents_adapter import OpenAIAgentsCERAdapter
from cer_v0_2.producers.ugence import UgenceCERProducer

NOW = "2026-01-01T00:10:00.000Z"


def _ctx(**over):
    op = {"generation": 1, "desired_replicas": 10, "current_replicas": 10,
          "available_replicas": 10, "readiness_plasticity": 0.95,
          "active_rollback_watches": 0, "seconds_since_last_action": 600.0,
          "dependency_healthy": True, "freeze_active": False, "observation_time_s": 600.0}
    op.update(over.pop("operational", {}))
    from dataclasses import replace
    base = EnvelopeContext(principal="agent:web-ops", permissions=("deploy",), delegator_id="sre",
                           resource_version="1001", state_hash="sha-256:" + "ab" * 32,
                           as_of="2026-01-01T00:09:30.000Z", operational=op,
                           policy_version="1.0.0+abc", policy_digest="pd",
                           correlation_id="protected/web")
    return replace(base, **over) if over else base


def _rollout():
    return RolloutActuation(cluster="fixture", namespace="protected", deployment="web",
                            image_digest="sha256:" + "cd" * 32,
                            current_manifest_digest="sha256:" + "ef" * 32, rollback_ref="web-rev-41")


def _scale():
    return ScaleActuation(cluster="fixture", namespace="protected", deployment="web",
                          from_replicas=10, to_replicas=12)


def _cp_all(ctx, act, **kw):
    return {n: cp.run_control_plane(p.propose(ctx, act), now=NOW, auto_evidence=True, **kw)
            for n, p in (("ug", UgenceCERProducer()), ("lg", LangGraphCERAdapter()),
                         ("oa", OpenAIAgentsCERAdapter()))}


@pytest.mark.parametrize("act", [_scale(), _rollout()])
def test_governance_equivalence_across_runtimes(act):
    r = _cp_all(_ctx(), act)
    outs = list(r.values())
    assert len({o.actiongate_outcome for o in outs}) == 1
    assert len({o.acp_decision for o in outs}) == 1
    assert len({o.combined_outcome for o in outs}) == 1
    assert len({o.actiongate_action_hash for o in outs}) == 1


def test_rollout_authorized_and_safe_eligible():
    r = _cp_all(_ctx(), _rollout())["ug"]
    assert r.combined_outcome == "PROCEED" and r.eligible


def test_rollout_freeze_held():
    r = _cp_all(_ctx(operational={"freeze_active": True}), _rollout())["ug"]
    assert r.combined_outcome == "HELD_BY_ACP"


def test_no_runtime_switch_in_frozen_components():
    from action_gate_ref import gate, projection
    from symbolu_robotics.autonomous_control_plane.cloud import adapter, composition
    for mod in (gate, projection, composition, adapter):
        s = inspect.getsource(mod).lower()
        for tok in ("langgraph", "ugence", "openai", "runtime_type", "crewai"):
            assert tok not in s


# --- compatibility: V0.1 scale identity preserved under V0.2 ---
def test_v02_scale_matches_v01_identity():
    from cer_v0_1 import spec as v1spec
    from cer_v0_1.actuation import ActuationRequest
    from cer_v0_1.producers.ugence import UgenceCERProducer as V1Ug
    op = {"generation": 1, "desired_replicas": 10, "current_replicas": 10,
          "available_replicas": 10, "readiness_plasticity": 0.95, "active_rollback_watches": 0,
          "seconds_since_last_action": 600.0, "dependency_healthy": True,
          "freeze_active": False, "observation_time_s": 600.0}
    v1_req = ActuationRequest(cluster="fixture", namespace="protected", deployment="web",
                              from_replicas=10, to_replicas=12, principal="agent:web-ops",
                              permissions=("deploy",), delegator_id="sre", resource_version="1001",
                              state_hash="sha-256:" + "ab" * 32, as_of="2026-01-01T00:09:30.000Z",
                              operational=op, policy_version="1.0.0+abc", policy_digest="pd",
                              correlation_id="protected/web")
    d_v1 = v1spec.action_digest(V1Ug().propose(v1_req))
    d_v2 = e2.action_digest(UgenceCERProducer().propose(_ctx(), _scale()))
    assert d_v1 == d_v2  # same actuation -> same identity across CER versions


def test_v01_suite_and_vectors_unchanged():
    import hashlib
    h = hashlib.sha256(open("cer_v0_1/conformance/vectors.json", "rb").read()).hexdigest()[:16]
    assert h == "3ec7f36d741f6302"  # frozen V0.1 vectors fingerprint
