"""Exact-action governance binding + fail-closed defaults (P0-1, P0-2).

Covers required checks 1-9: fail-closed default, non-consequential execution,
fingerprint/reference/expiry binding, exact-invocation match, and fingerprint identity.
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
from ugence_agent_runtime.models.proposal import TransitionProposal, compute_fingerprint
from ugence_agent_runtime.models.workflow import WorkflowStatus

from art_fakes import RecordingProvider


class _Hook(GovernanceHook):
    """A hook whose evaluation is fully controlled by an injected function."""

    def __init__(self, fn):
        self._fn = fn
        self.last_proposal = None

    def evaluate(self, proposal: TransitionProposal, evaluation_time: float) -> GovernanceEvaluation:
        self.last_proposal = proposal
        return self._fn(proposal, evaluation_time)


def _run(fn, *, provider=None, clock=None):
    hook = _Hook(fn)
    kw = {"governance_hook": hook}
    if clock is not None:
        kw["clock"] = clock
    rt = create_runtime(AgentRuntimeConfig(**kw))
    p = provider or RecordingProvider("p")
    register_provider(rt, p)
    wf = WorkflowDefinition(workflow_id="wf", tasks=(
        TaskDefinition(task_id="t", operation="op", provider_id="p", arguments={"a": 1}),))
    inst = rt.start_workflow(wf)
    return inst, p, hook, rt


def _clear(**over):
    def fn(proposal, t):
        base = dict(
            disposition=GovernanceDisposition.CLEAR,
            proposal_fingerprint=proposal.fingerprint,
            evaluation_reference="ref-1",
        )
        base.update(over)
        return GovernanceEvaluation(**base)
    return fn


# check 1
def test_default_config_consequential_does_not_call_provider():
    rt = create_runtime(AgentRuntimeConfig())
    p = RecordingProvider("p")
    register_provider(rt, p)
    wf = WorkflowDefinition(workflow_id="wf", tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),))
    inst = rt.start_workflow(wf)
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []


# check 2
def test_default_config_non_consequential_can_execute():
    rt = create_runtime(AgentRuntimeConfig())
    p = RecordingProvider("p")
    register_provider(rt, p)
    wf = WorkflowDefinition(workflow_id="wf", tasks=(
        TaskDefinition(task_id="t", operation="op", provider_id="p", consequential=False),))
    inst = rt.start_workflow(wf)
    assert inst.status is WorkflowStatus.COMPLETED
    assert len(p.calls) == 1


# check 3
def test_clear_without_fingerprint_fails_closed():
    inst, p, _, rt = _run(_clear(proposal_fingerprint=None))
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []
    assert "GOVERNANCE_CLEAR_MISSING_FINGERPRINT" in rt.result(inst.instance_id).failures[0].reason_codes


# check 4
def test_mismatched_fingerprint_fails_closed():
    inst, p, _, rt = _run(_clear(proposal_fingerprint="deadbeef"))
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []
    assert "GOVERNANCE_CLEAR_FINGERPRINT_MISMATCH" in rt.result(inst.instance_id).failures[0].reason_codes


# check 5
def test_missing_reference_fails_closed():
    inst, p, _, rt = _run(_clear(evaluation_reference=None))
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []
    assert "GOVERNANCE_CLEAR_MISSING_REFERENCE" in rt.result(inst.instance_id).failures[0].reason_codes


# check 6
def test_expired_clear_fails_closed():
    # valid_until in the past relative to the runtime clock (default monotonic > 0).
    inst, p, _, rt = _run(_clear(valid_until=-1.0))
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []
    assert "GOVERNANCE_CLEAR_EXPIRED" in rt.result(inst.instance_id).failures[0].reason_codes


# check 7 (positive control: a fully-bound CLEAR executes)
def test_fully_bound_clear_executes():
    inst, p, _, rt = _run(_clear())
    assert inst.status is WorkflowStatus.COMPLETED
    assert len(p.calls) == 1


# check 8
def test_exact_invocation_matches_evaluated_proposal():
    inst, p, hook, rt = _run(_clear())
    assert len(p.calls) == 1
    inv = p.calls[0]
    proposal = hook.last_proposal
    inv_fp = compute_fingerprint(
        proposal.workflow_id, proposal.instance_id, proposal.task_id,
        inv.provider_id, inv.operation, inv.arguments, inv.idempotency_key,
        proposal.proposal_version,
    )
    assert inv_fp == proposal.fingerprint


# check 9
def test_fingerprint_changes_with_identity():
    base = dict(workflow_id="w", instance_id="i", task_id="t", provider_id="p",
                operation="op", arguments={"a": 1}, idempotency_key="k")
    p0 = TransitionProposal.build(**base)
    assert TransitionProposal.build(**{**base, "provider_id": "other"}).fingerprint != p0.fingerprint
    assert TransitionProposal.build(**{**base, "operation": "other"}).fingerprint != p0.fingerprint
    assert TransitionProposal.build(**{**base, "arguments": {"a": 2}}).fingerprint != p0.fingerprint
    assert TransitionProposal.build(**{**base, "idempotency_key": "k2"}).fingerprint != p0.fingerprint
    # Stable for identical identity, and argument key order is canonicalized.
    assert TransitionProposal.build(**base).fingerprint == p0.fingerprint
    reordered = dict(base)
    reordered["arguments"] = {"a": 1, "b": 2}
    assert (
        TransitionProposal.build(**reordered).fingerprint
        == TransitionProposal.build(**{**base, "arguments": {"b": 2, "a": 1}}).fingerprint
    )


def test_unknown_disposition_fails_closed():
    # A hook that returns a non-CLEAR/HOLD/BLOCK/ESCALATE disposition must not execute.
    class Weird:
        value = "MAYBE"
    inst, p, _, rt = _run(lambda pr, t: GovernanceEvaluation(disposition=Weird()))
    assert p.calls == []
    assert inst.status is WorkflowStatus.FAILED
