"""Contract-hardening tests (Corrections A, B, C).

A — deeply immutable proposal identity.
B — mandatory correlation binding (correlation is fingerprinted identity).
C — inclusive expiration (now >= valid_until fails closed).
"""
from __future__ import annotations

import pytest

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    TaskDefinition,
    WorkflowDefinition,
    create_runtime,
    register_provider,
)
from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
    GovernanceHook,
)
from ugence_agent_runtime.models.proposal import (
    ProposalError,
    TransitionProposal,
)
from ugence_agent_runtime.models.workflow import WorkflowStatus

from art_fakes import RecordingProvider


def _proposal(**over):
    base = dict(workflow_id="w", instance_id="i", task_id="t", provider_id="p",
                operation="op", arguments={"a": 1}, idempotency_key="k",
                correlation_id="corr-1")
    base.update(over)
    return TransitionProposal.build(**base)


# ---------------------------------------------------------------------------
# Correction A — deeply immutable proposal identity
# ---------------------------------------------------------------------------
def test_A1_mutating_original_dict_does_not_affect_proposal():
    args = {"a": 1}
    p = _proposal(arguments=args)
    fp = p.fingerprint
    args["a"] = 999
    args["b"] = "new"
    assert p.arguments["a"] == 1
    assert "b" not in p.arguments
    assert p.fingerprint == fp
    assert p.is_intact()


def test_A2_mutating_nested_original_does_not_affect_proposal():
    args = {"outer": {"inner": [1, 2]}}
    p = _proposal(arguments=args)
    fp = p.fingerprint
    args["outer"]["inner"].append(3)
    args["outer"]["new"] = "x"
    assert p.arguments["outer"]["inner"] == (1, 2)
    assert "new" not in p.arguments["outer"]
    assert p.fingerprint == fp
    # And the eventual materialized invocation args are unaffected too.
    assert p.materialize_arguments() == {"outer": {"inner": [1, 2]}}


def test_A3_proposal_arguments_cannot_be_mutated_directly():
    p = _proposal(arguments={"outer": {"inner": [1]}})
    with pytest.raises(TypeError):
        p.arguments["outer"] = 1            # top-level proxy is read-only
    with pytest.raises(TypeError):
        p.arguments["outer"]["inner"] = 2   # nested proxy is read-only
    with pytest.raises(AttributeError):
        p.arguments["outer"]["inner"].append(2)  # nested sequence is a tuple


def test_A4_provider_receives_same_semantic_arguments_as_evaluated():
    seen = {}

    class Capturing(RecordingProvider):
        def execute(self, invocation):
            seen["args"] = invocation.arguments
            return super().execute(invocation)

    hook = _binding_clear_hook()
    rt = create_runtime(AgentRuntimeConfig(governance_hook=hook))
    register_provider(rt, Capturing("p"))
    original = {"nested": {"k": [1, {"deep": True}]}, "z": 2}
    wf = WorkflowDefinition(workflow_id="wf", tasks=(
        TaskDefinition(task_id="t", operation="op", provider_id="p", arguments=original),))
    rt.start_workflow(wf)
    assert seen["args"] == original                 # same semantic content
    assert isinstance(seen["args"], dict)           # fresh mutable mapping
    assert isinstance(seen["args"]["nested"], dict)


def test_A5_unsupported_argument_type_fails_deterministically():
    with pytest.raises(ProposalError):
        _proposal(arguments={"bad": object()})
    with pytest.raises(ProposalError):
        _proposal(arguments={"bad": lambda: 1})


def test_A6_key_order_does_not_change_fingerprint():
    a = _proposal(arguments={"a": 1, "b": {"x": 1, "y": 2}})
    b = _proposal(arguments={"b": {"y": 2, "x": 1}, "a": 1})
    assert a.fingerprint == b.fingerprint


# ---------------------------------------------------------------------------
# Correction B — mandatory correlation binding
# ---------------------------------------------------------------------------
def test_B1_changed_correlation_changes_fingerprint():
    assert _proposal(correlation_id="corr-1").fingerprint != _proposal(correlation_id="corr-2").fingerprint


def _run_with_eval(fn, *, arguments=None):
    class Hook(GovernanceHook):
        def __init__(self):
            self.last = None
        def evaluate(self, proposal, evaluation_time):
            self.last = proposal
            return fn(proposal, evaluation_time)
    hook = Hook()
    rt = create_runtime(AgentRuntimeConfig(governance_hook=hook))
    p = RecordingProvider("p")
    register_provider(rt, p)
    wf = WorkflowDefinition(workflow_id="wf", tasks=(
        TaskDefinition(task_id="t", operation="op", provider_id="p",
                       arguments=arguments or {}),))
    inst = rt.start_workflow(wf)
    return inst, p, hook, rt


def _clear(proposal, *, correlation_reference="__use_proposal__", **over):
    corr = proposal.correlation_id if correlation_reference == "__use_proposal__" else correlation_reference
    base = dict(
        disposition=GovernanceDisposition.CLEAR,
        proposal_fingerprint=proposal.fingerprint,
        evaluation_reference="ref-1",
        correlation_reference=corr,
    )
    base.update(over)
    return GovernanceEvaluation(**base)


def test_B2_missing_correlation_reference_fails_closed():
    inst, p, _, rt = _run_with_eval(lambda pr, t: _clear(pr, correlation_reference=None))
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []
    assert "GOVERNANCE_CLEAR_MISSING_CORRELATION" in rt.result(inst.instance_id).failures[0].reason_codes


def test_B3_mismatched_correlation_fails_closed():
    inst, p, _, rt = _run_with_eval(lambda pr, t: _clear(pr, correlation_reference="WRONG"))
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []
    assert "GOVERNANCE_CLEAR_CORRELATION_MISMATCH" in rt.result(inst.instance_id).failures[0].reason_codes


def test_B4_matching_correlation_succeeds():
    inst, p, _, rt = _run_with_eval(lambda pr, t: _clear(pr))
    assert inst.status is WorkflowStatus.COMPLETED
    assert len(p.calls) == 1


def test_B5_provider_receives_evaluated_correlation_id():
    inst, p, hook, rt = _run_with_eval(lambda pr, t: _clear(pr))
    assert p.calls[0].correlation_id == hook.last.correlation_id


def test_B6_invocation_correlation_drift_fails_before_provider(monkeypatch):
    # Force the materialized invocation to drift from the evaluated proposal by
    # rewriting the arguments after evaluation; the engine's exact-action re-check
    # must fail closed before the provider is invoked.
    original = TransitionProposal.materialize_arguments

    def drifted(self):
        d = original(self)
        d["__injected__"] = "drift"
        return d

    monkeypatch.setattr(TransitionProposal, "materialize_arguments", drifted)
    inst, p, _, rt = _run_with_eval(lambda pr, t: _clear(pr))
    assert p.calls == []
    assert inst.status is WorkflowStatus.FAILED
    assert "PROPOSAL_INVOCATION_MISMATCH" in rt.result(inst.instance_id).failures[0].reason_codes


# ---------------------------------------------------------------------------
# Correction C — inclusive expiration
# ---------------------------------------------------------------------------
def _run_with_clock(clock_values, valid_until):
    idx = {"i": 0}

    def clock():
        v = clock_values[min(idx["i"], len(clock_values) - 1)]
        idx["i"] += 1
        return v

    def fn(proposal, t):
        return _clear(proposal, valid_until=valid_until)

    class Hook(GovernanceHook):
        def evaluate(self, proposal, evaluation_time):
            return fn(proposal, evaluation_time)

    rt = create_runtime(AgentRuntimeConfig(governance_hook=Hook(), clock=clock))
    p = RecordingProvider("p")
    register_provider(rt, p)
    wf = WorkflowDefinition(workflow_id="wf", tasks=(
        TaskDefinition(task_id="t", operation="op", provider_id="p"),))
    inst = rt.start_workflow(wf)
    return inst, p, rt


def test_C1_before_expiry_may_execute():
    # clock reads: [evaluation_time, clearance-check now, provider timing...]
    inst, p, rt = _run_with_clock([10.0, 10.0, 10.0], valid_until=20.0)
    assert inst.status is WorkflowStatus.COMPLETED
    assert len(p.calls) == 1


def test_C2_at_exact_expiry_fails_closed():
    inst, p, rt = _run_with_clock([10.0, 20.0], valid_until=20.0)  # now == valid_until
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []
    assert "GOVERNANCE_CLEAR_EXPIRED" in rt.result(inst.instance_id).failures[0].reason_codes


def test_C3_after_expiry_fails_closed():
    inst, p, rt = _run_with_clock([10.0, 21.0], valid_until=20.0)
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []
    assert "GOVERNANCE_CLEAR_EXPIRED" in rt.result(inst.instance_id).failures[0].reason_codes


def test_C4_expired_never_calls_provider():
    inst, p, rt = _run_with_clock([0.0, 100.0], valid_until=1.0)
    assert p.calls == []


def test_C5_expiry_reason_codes_are_deterministic():
    inst_a, _, rt_a = _run_with_clock([5.0, 20.0], valid_until=20.0)
    inst_b, _, rt_b = _run_with_clock([5.0, 20.0], valid_until=20.0)
    assert (rt_a.result(inst_a.instance_id).failures[0].reason_codes
            == rt_b.result(inst_b.instance_id).failures[0].reason_codes)
    assert rt_a.result(inst_a.instance_id).failures[0].reason_codes == ("GOVERNANCE_CLEAR_EXPIRED",)


def _binding_clear_hook():
    class Hook(GovernanceHook):
        def evaluate(self, proposal, evaluation_time):
            return GovernanceEvaluation(
                disposition=GovernanceDisposition.CLEAR,
                proposal_fingerprint=proposal.fingerprint,
                evaluation_reference="ref-1",
                correlation_reference=proposal.correlation_id,
            )
    return Hook()
