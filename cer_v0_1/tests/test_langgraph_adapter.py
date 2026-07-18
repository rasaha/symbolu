"""LangGraph adapter tests (deliverable 13). Exercises REAL langgraph."""
from __future__ import annotations

import pytest

from cer_v0_1 import spec
from cer_v0_1.actuation import ActuationRequest
from cer_v0_1.producers.langgraph_adapter import LangGraphCERAdapter
from cer_v0_1.producers.ugence import UgenceCERProducer

langgraph = pytest.importorskip("langgraph")  # skip if the runtime is absent


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


def test_adapter_runs_real_graph_and_intercepts():
    adapter = LangGraphCERAdapter()
    state = adapter.run(_req())
    # a real graph ran and produced a CER at the intercepted tool-call boundary
    assert state["cer"] is not None
    assert state["cer"]["provenance"]["runtime"] == "langgraph"
    spec.validate_cer(state["cer"])


def test_adapter_never_executes_tool_in_governed_shadow():
    # the real k8s_scale tool body must not run (routed to END, not ToolNode)
    state = LangGraphCERAdapter().run(_req())
    msgs = state["messages"]
    # no ToolMessage (tool result) present -> the tool did not execute
    assert not any(getattr(m, "type", "") == "tool" for m in msgs)


def test_adapter_and_ugence_same_digest():
    req = _req()
    d_lg = spec.action_digest(LangGraphCERAdapter().propose(req))
    d_ug = spec.action_digest(UgenceCERProducer().propose(req))
    assert d_lg == d_ug


def test_adapter_different_provenance_and_objective():
    req = _req()
    lg = LangGraphCERAdapter().propose(req)
    ug = UgenceCERProducer().propose(req)
    assert lg["provenance"]["runtime"] != ug["provenance"]["runtime"]
    assert lg["provenance"]["objective"] != ug["provenance"]["objective"]
    # yet identical identity block
    assert lg["identity"] == ug["identity"]


def test_adapter_deterministic():
    req = _req()
    assert spec.action_digest(LangGraphCERAdapter().propose(req)) == \
        spec.action_digest(LangGraphCERAdapter().propose(req))
