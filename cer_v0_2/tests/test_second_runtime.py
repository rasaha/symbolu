"""Second-runtime integration tests (deliverable 12): REAL OpenAI Agents SDK."""
from __future__ import annotations

import pytest

agents = pytest.importorskip("agents")

from cer_v0_2 import envelope as e2
from cer_v0_2.actuation import EnvelopeContext, RolloutActuation, ScaleActuation
from cer_v0_2.producers.langgraph_adapter import LangGraphCERAdapter
from cer_v0_2.producers.openai_agents_adapter import OpenAIAgentsCERAdapter
from cer_v0_2.producers.ugence import UgenceCERProducer


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


def _scale():
    return ScaleActuation(cluster="fixture", namespace="protected", deployment="web",
                          from_replicas=10, to_replicas=12)


def _rollout():
    return RolloutActuation(cluster="fixture", namespace="protected", deployment="web",
                            image_digest="sha256:" + "cd" * 32,
                            current_manifest_digest="sha256:" + "ef" * 32,
                            rollback_ref="web-rev-41")


def test_openai_agents_real_runtime_emits_cer():
    cer = OpenAIAgentsCERAdapter().propose(_ctx(), _scale())
    e2.validate_cer(cer)
    assert cer["provenance"]["runtime"] == "openai-agents"


def test_three_runtimes_same_digest_scale():
    ctx, act = _ctx(), _scale()
    d = {name: e2.action_digest(p.propose(ctx, act)) for name, p in (
        ("ug", UgenceCERProducer()), ("lg", LangGraphCERAdapter()),
        ("oa", OpenAIAgentsCERAdapter()))}
    assert d["ug"] == d["lg"] == d["oa"]


def test_three_runtimes_same_digest_rollout():
    ctx, act = _ctx(), _rollout()
    d = {name: e2.action_digest(p.propose(ctx, act)) for name, p in (
        ("ug", UgenceCERProducer()), ("lg", LangGraphCERAdapter()),
        ("oa", OpenAIAgentsCERAdapter()))}
    assert d["ug"] == d["lg"] == d["oa"]


def test_openai_provenance_excluded_from_identity():
    ctx = _ctx()
    d_oa = e2.action_digest(OpenAIAgentsCERAdapter().propose(ctx, _scale()))
    d_ug = e2.action_digest(UgenceCERProducer().propose(ctx, _scale()))
    assert d_oa == d_ug  # provenance differs, identity equal


def test_openai_deterministic():
    ctx, act = _ctx(), _rollout()
    a = e2.action_digest(OpenAIAgentsCERAdapter().propose(ctx, act))
    b = e2.action_digest(OpenAIAgentsCERAdapter().propose(ctx, act))
    assert a == b
