"""Neutral provider-attempt telemetry (CM-TA1).

Every actual provider.execute invocation emits exactly one attempt; retries and
failures are recorded distinctly (never collapsed into the final attempt); a
governance HOLD/BLOCK/ESCALATE, an exact-action rejection, and a provider-not-found
produce NO attempt because the provider was never invoked; the runtime forwards a
provider's opaque usage mapping without interpreting it.
"""
from __future__ import annotations

import pytest

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    ProviderAttemptStatus,
    RecordingAttemptObserver,
    TaskDefinition,
    WorkflowDefinition,
    create_runtime,
    register_provider,
)
from ugence_agent_runtime.governance.hooks import AllowAllGovernanceHook
from ugence_agent_runtime.governance.interfaces import GovernanceDisposition
from ugence_agent_runtime.models.task import TaskStatus
from ugence_agent_runtime.models.workflow import WorkflowStatus

from art_fakes import DispositionHook, FailingProvider, RecordingProvider, UsageProvider


def _wf(*tasks):
    return WorkflowDefinition(workflow_id="wf", tasks=tuple(tasks))


def _runtime(provider=None, observer=None, hook=None, **cfg):
    cfg.setdefault("governance_hook", hook or AllowAllGovernanceHook())
    rt = create_runtime(AgentRuntimeConfig(attempt_observer=observer, **cfg))
    if provider is not None:
        register_provider(rt, provider)
    return rt


# --------------------------------------------------------------------------- #
# Happy path — one attempt, authoritative number, forwarded usage.
# --------------------------------------------------------------------------- #
def test_success_emits_single_attempt():
    obs = RecordingAttemptObserver()
    rt = _runtime(RecordingProvider("p"), observer=obs)
    rt.start_workflow(_wf(TaskDefinition(task_id="t1", operation="op", provider_id="p")))
    assert len(obs.attempts) == 1
    a = obs.attempts[0]
    assert a.status is ProviderAttemptStatus.SUCCEEDED
    assert a.ok is True
    assert a.provider_invoked is True
    assert a.attempt_number == 1
    assert a.task_id == "t1"
    assert a.provider_id == "p"


def test_neutral_usage_is_forwarded_verbatim_and_uninterpreted():
    obs = RecordingAttemptObserver()
    rt = _runtime(UsageProvider("p", usage={"prompt_tokens": 2337, "cache_read": 1500}), observer=obs)
    rt.start_workflow(_wf(TaskDefinition(task_id="t1", operation="op", provider_id="p")))
    a = obs.attempts[0]
    # Forwarded verbatim — provider-specific field names untouched by the runtime.
    assert a.neutral_usage == {"prompt_tokens": 2337, "cache_read": 1500}


def test_no_usage_metadata_means_unknown_not_empty():
    obs = RecordingAttemptObserver()
    rt = _runtime(RecordingProvider("p"), observer=obs)
    rt.start_workflow(_wf(TaskDefinition(task_id="t1", operation="op", provider_id="p")))
    assert obs.attempts[0].neutral_usage is None  # unknown, never fabricated as {}


# --------------------------------------------------------------------------- #
# Retries + failures are never collapsed.
# --------------------------------------------------------------------------- #
def test_retries_recorded_as_distinct_attempts():
    obs = RecordingAttemptObserver()
    # Fails the first 2 attempts (raises), succeeds on the 3rd; max_attempts=3.
    prov = FailingProvider("p", retriable=True, fail_times=2)
    rt = _runtime(prov, observer=obs)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p", max_attempts=3)))
    assert inst.status is WorkflowStatus.COMPLETED
    # Three distinct attempts, authoritative numbering 1..3 — NOT collapsed into one.
    assert [a.attempt_number for a in obs.attempts] == [1, 2, 3]
    assert obs.attempts[0].status is ProviderAttemptStatus.EXCEPTION
    assert obs.attempts[1].status is ProviderAttemptStatus.EXCEPTION
    assert obs.attempts[2].status is ProviderAttemptStatus.SUCCEEDED


def test_exhausted_retries_record_every_attempt():
    obs = RecordingAttemptObserver()
    prov = FailingProvider("p", retriable=True, fail_times=None)  # always fails
    rt = _runtime(prov, observer=obs)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p", max_attempts=2)))
    assert inst.status is WorkflowStatus.FAILED
    assert [a.attempt_number for a in obs.attempts] == [1, 2]
    assert all(a.status is ProviderAttemptStatus.EXCEPTION for a in obs.attempts)
    assert all(a.ok is False for a in obs.attempts)


def test_provider_exception_produces_attempt_with_unknown_usage():
    obs = RecordingAttemptObserver()
    prov = FailingProvider("p", retriable=False, fail_times=None)
    rt = _runtime(prov, observer=obs)
    rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert len(obs.attempts) == 1
    a = obs.attempts[0]
    assert a.status is ProviderAttemptStatus.EXCEPTION
    assert a.provider_invoked is True
    assert a.neutral_usage is None  # unknown, never fabricated


def test_expected_failure_by_value_is_failed_status():
    obs = RecordingAttemptObserver()
    prov = UsageProvider("p", ok=False, error="declined")  # ToolResult.ok = False
    rt = _runtime(prov, observer=obs)
    rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    a = obs.attempts[0]
    assert a.status is ProviderAttemptStatus.FAILED
    # Usage on a failed attempt is still forwarded (failed calls can consume tokens).
    assert a.neutral_usage is not None


# --------------------------------------------------------------------------- #
# No provider call ⇒ no attempt (governance / not-found).
# --------------------------------------------------------------------------- #
def test_governance_block_produces_no_attempt():
    obs = RecordingAttemptObserver()
    hook = DispositionHook(GovernanceDisposition.BLOCK)
    rt = _runtime(RecordingProvider("p"), observer=obs, hook=hook)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.FAILED
    assert obs.attempts == []  # provider never invoked


def test_governance_hold_produces_no_attempt():
    obs = RecordingAttemptObserver()
    hook = DispositionHook(GovernanceDisposition.HOLD)
    rt = _runtime(RecordingProvider("p"), observer=obs, hook=hook)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.WAITING
    assert obs.attempts == []


def test_clear_without_binding_fails_closed_with_no_attempt():
    """A CLEAR not bound to the exact proposal fails the exact-action check BEFORE the
    provider is invoked — so no attempt is observed."""
    obs = RecordingAttemptObserver()
    hook = DispositionHook(GovernanceDisposition.CLEAR, bind=False)
    rt = _runtime(RecordingProvider("p"), observer=obs, hook=hook)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.FAILED
    assert obs.attempts == []


def test_provider_not_found_produces_no_attempt():
    obs = RecordingAttemptObserver()
    rt = _runtime(observer=obs)  # no provider registered
    rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="missing")))
    assert obs.attempts == []


# --------------------------------------------------------------------------- #
# Robustness — a raising observer never breaks execution; None observer is a no-op.
# --------------------------------------------------------------------------- #
def test_raising_observer_never_breaks_execution():
    class Boom:
        def on_attempt(self, attempt):
            raise RuntimeError("observer boom")

    rt = _runtime(RecordingProvider("p"), observer=Boom())
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.COMPLETED  # execution unaffected


def test_no_observer_is_a_silent_noop():
    rt = _runtime(RecordingProvider("p"))  # attempt_observer defaults to None
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.COMPLETED


def test_timeout_attempt_is_recorded_as_timeout():
    obs = RecordingAttemptObserver()
    # A monotonically advancing clock: each call returns +10, so any positive timeout
    # is exceeded deterministically (no wall clock, no sleep).
    ticks = iter(range(0, 1000, 10))
    rt = _runtime(RecordingProvider("p"), observer=obs, default_timeout=1.0,
                  clock=lambda: next(ticks))
    rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert len(obs.attempts) == 1
    assert obs.attempts[0].status is ProviderAttemptStatus.TIMEOUT
    assert obs.attempts[0].ok is False
