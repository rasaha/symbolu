"""Last-mile authority-recheck hook: fail-closed on errors / malformed results.

Regression coverage for audit finding F-1. The optional ``authority_recheck``
hook (RA-6 §8) is a neutral callable the runtime runs immediately before a
consequential provider invocation. Its contract is ``(bool, reasons)``. This
suite pins the fail-closed normalization: a hook that raises, or returns anything
other than that exact shape, becomes a deterministic governance rejection
(:data:`CLEAR_REJECTED_AUTHORITY_STALE` + :data:`AUTHORITY_RECHECK_ERROR`) and the
provider is NEVER invoked — while the legitimate ``(True, ())`` /
``(False, reasons)`` / no-hook behaviors are unchanged.
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
from ugence_agent_runtime.governance.decisions import (
    AUTHORITY_RECHECK_ERROR,
    CLEAR_REJECTED_AUTHORITY_STALE,
    validate_clearance,
)
from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
    GovernanceHook,
)
from ugence_agent_runtime.models.proposal import TransitionProposal
from ugence_agent_runtime.models.workflow import WorkflowStatus

from art_fakes import RecordingProvider


# --------------------------------------------------------------------------- #
# Unit level: a fully-bound CLEAR so the recheck hook is actually reached.     #
# --------------------------------------------------------------------------- #
def _proposal() -> TransitionProposal:
    return TransitionProposal.build(
        workflow_id="wf",
        instance_id="inst",
        task_id="task",
        provider_id="prov",
        operation="refund.prepare",
        arguments={"amount": 100},
        correlation_id="corr-1",
    )


def _clear(proposal: TransitionProposal) -> GovernanceEvaluation:
    return GovernanceEvaluation(
        disposition=GovernanceDisposition.CLEAR,
        proposal_fingerprint=proposal.fingerprint,
        authorization_reference="rae_1",
        valid_until=None,
        correlation_reference=proposal.correlation_id,
    )


def _validate(hook):
    proposal = _proposal()
    evaluation = _clear(proposal)
    return validate_clearance(evaluation, proposal, now=0.0, authority_recheck=hook)


def _raises(_ev, _pr, _now):
    raise RuntimeError("boom")


# Every shape that is NOT the exact ``(bool, reasons)`` contract.
_MALFORMED_HOOKS = {
    "raises": _raises,
    "returns_none": lambda ev, pr, n: None,
    "returns_true": lambda ev, pr, n: True,
    "returns_str": lambda ev, pr, n: "allow",
    "one_tuple": lambda ev, pr, n: (True,),
    "three_tuple": lambda ev, pr, n: (True, (), 1),
    "non_bool_first_str": lambda ev, pr, n: ("allow", ()),   # F-1 fail-open
    "non_bool_first_int": lambda ev, pr, n: (1, ()),          # F-1 fail-open
    "reasons_bare_str_deny": lambda ev, pr, n: (False, "REVOKED"),
    "reasons_bare_str_pass": lambda ev, pr, n: (True, "xyz"),  # F-1 fail-open
    "reasons_non_str": lambda ev, pr, n: (False, (1, 2)),
    "reasons_not_iterable": lambda ev, pr, n: (False, 5),
}


@pytest.mark.parametrize("name", sorted(_MALFORMED_HOOKS))
def test_malformed_or_raising_recheck_is_deterministic_fail_closed(name):
    permitted, reasons = _validate(_MALFORMED_HOOKS[name])
    assert permitted is False
    # Deterministic, stable reason codes — no fragmented/garbled reasons.
    assert reasons == (CLEAR_REJECTED_AUTHORITY_STALE, AUTHORITY_RECHECK_ERROR)


def test_valid_denial_preserves_hook_reasons():
    permitted, reasons = _validate(lambda ev, pr, n: (False, ("REVOKED", "EPOCH_STALE")))
    assert permitted is False
    assert reasons == (CLEAR_REJECTED_AUTHORITY_STALE, "REVOKED", "EPOCH_STALE")


def test_valid_pass_permits_unchanged():
    permitted, reasons = _validate(lambda ev, pr, n: (True, ()))
    assert permitted is True
    assert reasons == ()


def test_valid_pass_as_list_is_accepted():
    # The contract is a 2-sequence; a list is tolerated as much as a tuple.
    permitted, reasons = _validate(lambda ev, pr, n: [True, []])
    assert permitted is True
    assert reasons == ()


def test_no_hook_is_backward_compatible():
    proposal = _proposal()
    evaluation = _clear(proposal)
    # No authority_recheck argument at all — historical behavior.
    assert validate_clearance(evaluation, proposal, now=0.0) == (True, ())
    # Explicit None is identical.
    assert _validate(None) == (True, ())


# --------------------------------------------------------------------------- #
# Engine level: the provider must NOT be invoked on an invalid recheck.        #
# --------------------------------------------------------------------------- #
class _Hook(GovernanceHook):
    def __init__(self, fn):
        self._fn = fn

    def evaluate(self, proposal, evaluation_time):
        return self._fn(proposal, evaluation_time)


def _clear_fn(proposal, _t):
    return GovernanceEvaluation(
        disposition=GovernanceDisposition.CLEAR,
        proposal_fingerprint=proposal.fingerprint,
        authorization_reference="rae_1",
        correlation_reference=proposal.correlation_id,
    )


def _run_consequential(recheck):
    rt = create_runtime(
        AgentRuntimeConfig(governance_hook=_Hook(_clear_fn), authority_recheck=recheck)
    )
    provider = RecordingProvider("p")
    register_provider(rt, provider)
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p", arguments={"a": 1}),),
    )
    inst = rt.start_workflow(wf)
    return inst, provider


def test_engine_raising_recheck_blocks_provider():
    inst, provider = _run_consequential(_raises)
    assert inst.status is WorkflowStatus.FAILED
    assert provider.calls == []  # no side effect occurred


def test_engine_malformed_recheck_blocks_provider():
    inst, provider = _run_consequential(lambda ev, pr, n: None)
    assert inst.status is WorkflowStatus.FAILED
    assert provider.calls == []


def test_engine_non_bool_truthy_recheck_blocks_provider():
    # The former F-1 fail-open: ("allow", ()) must NOT execute the provider.
    inst, provider = _run_consequential(lambda ev, pr, n: ("allow", ()))
    assert inst.status is WorkflowStatus.FAILED
    assert provider.calls == []


def test_engine_denial_recheck_blocks_provider():
    inst, provider = _run_consequential(lambda ev, pr, n: (False, ("REVOKED",)))
    assert inst.status is WorkflowStatus.FAILED
    assert provider.calls == []


def test_engine_valid_pass_executes_provider():
    inst, provider = _run_consequential(lambda ev, pr, n: (True, ()))
    assert inst.status is WorkflowStatus.COMPLETED
    assert len(provider.calls) == 1  # legitimate consequential action still runs
