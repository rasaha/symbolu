"""F2 — attempt-observation failure is surfaced, never silent, and never breaks execution.

The runtime stays fail-open: a raising observer does not re-execute the provider, erase a
successful result, or change retry behavior. But with an injected error reporter, exactly
one structured, payload-free AttemptObservationFailure is emitted per observer failure.
"""
from __future__ import annotations

import pytest

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    ProviderAttemptStatus,
    RecordingObservationErrorReporter,
    TaskDefinition,
    WorkflowDefinition,
    create_runtime,
    register_provider,
)
from ugence_agent_runtime.governance.hooks import AllowAllGovernanceHook
from ugence_agent_runtime.governance.interfaces import GovernanceDisposition
from ugence_agent_runtime.models.workflow import WorkflowStatus

from art_fakes import DispositionHook, FailingProvider, RecordingProvider


class RaisingObserver:
    def __init__(self):
        self.seen = 0

    def on_attempt(self, attempt):
        self.seen += 1
        raise RuntimeError("secret provider detail 0xDEADBEEF")  # message must NOT leak


class RaisingReporter:
    def on_observation_failure(self, failure):
        raise ValueError("reporter blew up")


def _wf(*tasks):
    return WorkflowDefinition(workflow_id="wf", tasks=tuple(tasks))


def _runtime(provider, observer, reporter=None, hook=None, **cfg):
    cfg.setdefault("governance_hook", hook or AllowAllGovernanceHook())
    rt = create_runtime(AgentRuntimeConfig(
        attempt_observer=observer, attempt_observer_error_reporter=reporter, **cfg))
    if provider is not None:
        register_provider(rt, provider)
    return rt


def test_raising_observer_does_not_re_execute_provider():
    prov = RecordingProvider("p")
    obs = RaisingObserver()
    rep = RecordingObservationErrorReporter()
    rt = _runtime(prov, obs, rep)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.COMPLETED  # provider success preserved
    assert len(prov.calls) == 1  # provider invoked exactly once — no re-execution
    assert obs.seen == 1
    assert len(rep.failures) == 1  # exactly one structured signal


def test_observation_failure_carries_no_sensitive_payload():
    rep = RecordingObservationErrorReporter()
    rt = _runtime(RecordingProvider("p"), RaisingObserver(), rep)
    rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    f = rep.failures[0]
    # Only the exception TYPE NAME is exposed — never the message/args/payload.
    assert f.error_type == "RuntimeError"
    d = f.to_dict()
    blob = repr(d)
    assert "DEADBEEF" not in blob and "secret" not in blob
    # No message/args/exception field exists on the structured record.
    assert not hasattr(f, "message")
    assert not hasattr(f, "exception")
    # Safe identity is present.
    assert f.task_id == "t"
    assert f.status is ProviderAttemptStatus.SUCCEEDED


def test_retry_behavior_unchanged_under_raising_observer():
    # Fails once (raises), succeeds on the 2nd; max_attempts=2. Observer raises every time.
    prov = FailingProvider("p", retriable=True, fail_times=1)
    rep = RecordingObservationErrorReporter()
    rt = _runtime(prov, RaisingObserver(), rep, )
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p", max_attempts=2)))
    assert inst.status is WorkflowStatus.COMPLETED
    assert prov.calls == 2  # retry still happened
    # One observation-failure per actual attempt (2), not collapsed.
    assert len(rep.failures) == 2
    assert [f.attempt_number for f in rep.failures] == [1, 2]


def test_failing_reporter_is_contained():
    prov = RecordingProvider("p")
    rt = _runtime(prov, RaisingObserver(), RaisingReporter())
    # A reporter that itself raises must not mask the provider result or break execution.
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.COMPLETED
    assert len(prov.calls) == 1


def test_no_signal_when_no_provider_invoked():
    rep = RecordingObservationErrorReporter()
    rt = _runtime(RecordingProvider("p"), RaisingObserver(), rep,
                  hook=DispositionHook(GovernanceDisposition.BLOCK))
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.FAILED
    assert rep.failures == []  # provider never invoked → no observation attempt → no signal


def test_default_no_reporter_preserves_silent_fail_open():
    # No reporter configured: a raising observer is swallowed silently (prior behavior).
    prov = RecordingProvider("p")
    rt = _runtime(prov, RaisingObserver(), reporter=None)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.COMPLETED
    assert len(prov.calls) == 1
