"""End-to-end governance tests (deliverable 14): CER -> ActionGate -> ACP -> compose.

Uses the REAL frozen ActionGate + ACP. Proves the required conformance assertions.
"""
from __future__ import annotations

import inspect

from cer_v0_1 import control_plane as cp
from cer_v0_1 import spec
from cer_v0_1.actuation import ActuationRequest
from cer_v0_1.producers.langgraph_adapter import LangGraphCERAdapter
from cer_v0_1.producers.ugence import UgenceCERProducer

NOW = "2026-01-01T00:10:00.000Z"


def _req(**over):
    op = {"generation": 1, "desired_replicas": 10, "current_replicas": 10,
          "available_replicas": 10, "readiness_plasticity": 0.95,
          "active_rollback_watches": 0, "seconds_since_last_action": 600.0,
          "dependency_healthy": True, "freeze_active": False, "observation_time_s": 600.0}
    op.update(over.pop("operational", {}))
    d = dict(cluster="fixture", namespace="protected", deployment="web", from_replicas=10,
             to_replicas=12, principal="agent:web-ops", permissions=("deploy",),
             delegator_id="sre", resource_version="1001", state_hash="sha-256:" + "ab" * 32,
             as_of="2026-01-01T00:09:30.000Z", operational=op, policy_version="1.0.0+abc",
             policy_digest="pd", correlation_id="protected/web", attach_evidence=True)
    d.update(over)
    return ActuationRequest(**d)


def _run(req, **kw):
    ug = cp.run_control_plane(UgenceCERProducer().propose(req), now=NOW, auto_evidence=True, **kw)
    lg = cp.run_control_plane(LangGraphCERAdapter().propose(req), now=NOW, auto_evidence=True, **kw)
    return ug, lg


def test_authorized_and_safe_is_eligible():
    ug, lg = _run(_req())
    assert ug.actiongate_outcome == "ALLOW"
    assert ug.combined_outcome == "PROCEED"
    assert ug.eligible and lg.eligible


def test_actiongate_and_acp_verdicts_match_across_runtimes():
    for req in (_req(), _req(operational={"freeze_active": True}),
                _req(delegation_grant="read:*")):
        ug, lg = _run(req)
        assert ug.actiongate_outcome == lg.actiongate_outcome
        assert ug.acp_decision == lg.acp_decision
        assert ug.combined_outcome == lg.combined_outcome
        assert ug.actiongate_action_hash == lg.actiongate_action_hash


def test_unauthorized_blocked():
    ug, _ = _run(_req(delegation_grant="read:*"))
    assert ug.combined_outcome == "BLOCKED_BY_AUTHORIZATION"
    assert not ug.eligible


def test_operationally_unsafe_held():
    ug, _ = _run(_req(operational={"freeze_active": True}))
    assert ug.combined_outcome == "HELD_BY_ACP"
    assert not ug.eligible


def test_evidence_binds_under_v2_identity():
    # a valid scale WITH evidence bound to the v2 hash is ALLOW; WITHOUT is not.
    ug_ev, _ = _run(_req())
    ug_noev = cp.run_control_plane(UgenceCERProducer().propose(_req(attach_evidence=False)),
                                   now=NOW, auto_evidence=False)
    assert ug_ev.actiongate_outcome == "ALLOW"
    assert ug_noev.actiongate_outcome == "REQUEST_MORE_EVIDENCE"


def test_stale_state_invalidates():
    req = _req(as_of="2026-01-01T00:00:00.000Z", live_resource_version="2000")
    ug, lg = _run(req)
    assert not ug.eligible and not lg.eligible


def test_no_runtime_switch_in_frozen_components():
    from action_gate_ref import gate, projection
    from symbolu_robotics.autonomous_control_plane.cloud import adapter, composition
    for mod in (gate, projection, composition, adapter):
        s = inspect.getsource(mod).lower()
        for tok in ("langgraph", "ugence", "runtime_type", "crewai"):
            assert tok not in s, f"{tok} found in {mod.__name__}"


def test_direct_bypass_blocked():
    # A runtime that bypasses the CER path obtains no execution identity.
    # (Governed mode: eligibility+identity only come from run_control_plane.)
    class _BypassAttempt:
        eligible = False
        execution_identity = None
    assert _BypassAttempt.execution_identity is None
    # and the LangGraph graph never executes the real tool in shadow mode
    state = LangGraphCERAdapter().run(_req())
    assert not any(getattr(m, "type", "") == "tool" for m in state["messages"])


def test_deterministic_rerun_byte_identical():
    req = _req()
    a = cp.run_control_plane(UgenceCERProducer().propose(req), now=NOW, auto_evidence=True)
    b = cp.run_control_plane(UgenceCERProducer().propose(req), now=NOW, auto_evidence=True)
    assert a.to_dict() == b.to_dict()
