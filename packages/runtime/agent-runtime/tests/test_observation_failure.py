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
    # N2: a FIXED classification code — never the exception class name/message/args.
    from ugence_agent_runtime.api import ObservationFailureKind
    assert f.error_kind is ObservationFailureKind.OBSERVER_EXCEPTION  # RuntimeError → catch-all
    d = f.to_dict()
    blob = repr(d)
    assert "DEADBEEF" not in blob and "secret" not in blob and "RuntimeError" not in blob
    # No exception class name / message / args field exists on the structured record.
    assert not hasattr(f, "error_type")
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


# --------------------------------------------------------------------------- #
# N2 — bounded classification: attacker-controlled strings never enter telemetry.
# --------------------------------------------------------------------------- #
def _one_failure(observer):
    prov = RecordingProvider("p")
    rep = RecordingObservationErrorReporter()
    rt = _runtime(prov, observer, rep)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    from ugence_agent_runtime.models.workflow import WorkflowStatus as _WS
    assert inst.status is _WS.COMPLETED and len(prov.calls) == 1  # fail-open preserved
    assert len(rep.failures) == 1
    return rep.failures[0]


def test_dynamically_named_exception_cannot_inject_content():
    class Evil:
        def on_attempt(self, a):
            # class NAME embeds a fake secret; message embeds another.
            Exc = type("sk_live_DEADBEEF_classname", (RuntimeError,), {})
            raise Exc("BEGIN PRIVATE KEY prompt-body api_key=sk_live_9999")
    from ugence_agent_runtime.api import ObservationFailureKind
    f = _one_failure(Evil())
    assert f.error_kind is ObservationFailureKind.OBSERVER_EXCEPTION  # not in allowlist → catch-all
    blob = repr(f.to_dict()) + repr(f)
    for secret in ("sk_live_DEADBEEF_classname", "PRIVATE KEY", "prompt-body", "sk_live_9999"):
        assert secret not in blob, secret
    # error_kind is a fixed enum value, not derived from the class name.
    assert f.error_kind.value in {k.value for k in ObservationFailureKind}


def test_message_and_args_with_secrets_are_absent():
    class Evil:
        def on_attempt(self, a):
            raise ValueError("secret=SUPERSECRET", {"authorization": "Bearer LEAK"})
    from ugence_agent_runtime.api import ObservationFailureKind
    f = _one_failure(Evil())
    assert f.error_kind is ObservationFailureKind.OBSERVER_VALUE_ERROR  # allowlisted category
    blob = repr(f.to_dict()) + repr(f)
    for secret in ("SUPERSECRET", "Bearer LEAK", "authorization"):
        assert secret not in blob, secret


def test_allowlist_categories_are_fixed_codes():
    from ugence_agent_runtime.api import ObservationFailureKind, classify_observation_failure
    assert classify_observation_failure(ValueError("x")) is ObservationFailureKind.OBSERVER_VALUE_ERROR
    assert classify_observation_failure(TypeError("x")) is ObservationFailureKind.OBSERVER_TYPE_ERROR
    assert classify_observation_failure(KeyError("x")) is ObservationFailureKind.OBSERVER_LOOKUP_ERROR
    assert classify_observation_failure(RuntimeError("x")) is ObservationFailureKind.OBSERVER_EXCEPTION
    # a dynamically-named subclass of an allowlisted type still maps to the FIXED code
    Sub = type("LEAK_secret", (ValueError,), {})
    assert classify_observation_failure(Sub()) is ObservationFailureKind.OBSERVER_VALUE_ERROR


def test_raising_reporter_with_dynamic_exception_still_contained():
    class Evil:
        def on_attempt(self, a):
            raise type("LEAK", (RuntimeError,), {})("x")
    class BadReporter:
        def on_observation_failure(self, f):
            raise type("REPORTER_LEAK", (RuntimeError,), {})("y")
    prov = RecordingProvider("p")
    rt = _runtime(prov, Evil(), BadReporter())
    from ugence_agent_runtime.models.workflow import WorkflowStatus as _WS
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is _WS.COMPLETED and len(prov.calls) == 1  # both contained
