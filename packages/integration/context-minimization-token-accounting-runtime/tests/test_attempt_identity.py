"""F3 — deterministic, collision-resistant attempt-ID derivation and retry linkage.

No "?" placeholder; missing/empty/whitespace identity is rejected; distinct logical
requests can never collide on attempt number alone; explicit ids never cross-derive retry
linkage from a different scheme.
"""

from __future__ import annotations

import pytest

from ugence_agent_runtime.observability.attempts import ProviderAttempt, ProviderAttemptStatus

from ugence_context_minimization.api import (
    AttemptStatus,
    InMemoryTokenAccountingSink,
    UsageAvailability,
    prepare_api_call_measurement,
)

from ugence_cm_token_accounting_runtime import (
    derive_attempt_id, translate_attempt, ExplicitAttemptReference,
)

from support_itg import sample_minimization_result


def _prep(lr="lr"):
    return prepare_api_call_measurement(
        minimization_result=sample_minimization_result(), logical_request_id=lr, provider_id="vendor"
    )


def _att(*, instance_id="wf-1", task_id="t", attempt_number=1, status=ProviderAttemptStatus.SUCCEEDED):
    return ProviderAttempt(
        provider_id="vendor", operation="op", attempt_number=attempt_number, status=status,
        ok=(status is ProviderAttemptStatus.SUCCEEDED), provider_invoked=True,
        instance_id=instance_id, task_id=task_id, correlation_id="corr",
    )


# --------------------------------------------------------------------------- #
# Missing / ambiguous identity is rejected (no "?" fallback).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [None, "", "   ", "\t\n"])
def test_missing_or_blank_instance_rejected(bad):
    prep = _prep()
    att = _att(instance_id=bad)
    with pytest.raises(ValueError):
        translate_attempt(prep, att, normalizer=None)


@pytest.mark.parametrize("bad", [None, "", "  "])
def test_missing_or_blank_task_rejected(bad):
    prep = _prep()
    att = _att(task_id=bad)
    with pytest.raises(ValueError):
        translate_attempt(prep, att, normalizer=None)


@pytest.mark.parametrize("bad", [None, "", "  "])
def test_derive_requires_logical_request_id(bad):
    att = _att()
    with pytest.raises(ValueError):
        derive_attempt_id(att, logical_request_id=bad)


# --------------------------------------------------------------------------- #
# Collision resistance.
# --------------------------------------------------------------------------- #
def test_two_logical_requests_same_attempt_number_do_not_collide():
    att = _att(attempt_number=1)
    id_a = derive_attempt_id(att, logical_request_id="lr-A")
    id_b = derive_attempt_id(att, logical_request_id="lr-B")
    assert id_a != id_b  # same instance/task/number, different logical request


def test_absent_instance_cannot_cause_cross_request_collision():
    # Both would have collapsed to "?:t:1" under the old scheme; now both are rejected.
    with pytest.raises(ValueError):
        derive_attempt_id(_att(instance_id=None), logical_request_id="lr-A")
    with pytest.raises(ValueError):
        derive_attempt_id(_att(instance_id=None), logical_request_id="lr-B")


def test_length_prefix_prevents_delimiter_collision():
    # ("a", "bc") vs ("ab", "c") must not collide despite a naive join.
    a = derive_attempt_id(_att(instance_id="a", task_id="bc"), logical_request_id="lr")
    b = derive_attempt_id(_att(instance_id="ab", task_id="c"), logical_request_id="lr")
    assert a != b


def test_stable_replay_same_request():
    att = _att(attempt_number=2)
    assert derive_attempt_id(att, logical_request_id="lr") == derive_attempt_id(att, logical_request_id="lr")


# --------------------------------------------------------------------------- #
# Explicit vs derived id + retry linkage rules.
# --------------------------------------------------------------------------- #
def test_explicit_id_with_explicit_retry_linkage_accepted():
    prep = _prep()
    att = _att(attempt_number=2)
    rec = translate_attempt(prep, att, attempt_id="custom-att-2", retry_of=ExplicitAttemptReference(attempt_id="custom-att-1"))
    assert rec.attempt_id == "custom-att-2"
    assert rec.retry_of_attempt_id == "custom-att-1"


def test_explicit_id_for_retry_without_retry_linkage_rejected():
    prep = _prep()
    att = _att(attempt_number=2)  # a retry
    with pytest.raises(ValueError):
        translate_attempt(prep, att, attempt_id="custom-att-2")  # no retry_of supplied


def test_explicit_id_non_retry_with_retry_linkage_rejected():
    prep = _prep()
    att = _att(attempt_number=1)  # not a retry
    with pytest.raises(ValueError):
        translate_attempt(prep, att, attempt_id="custom-att-1", retry_of=ExplicitAttemptReference(attempt_id="x"))


def test_derived_id_with_explicit_retry_of_rejected():
    prep = _prep()
    att = _att(attempt_number=2)
    with pytest.raises(ValueError):
        translate_attempt(prep, att, retry_of=ExplicitAttemptReference(attempt_id="x"))  # deriving id but supplying retry_of


def test_derived_retry_uses_same_scheme():
    prep = _prep()
    att3 = _att(attempt_number=3)
    att2 = _att(attempt_number=2)
    rec = translate_attempt(prep, att3, normalizer=None)
    assert rec.retry_of_attempt_id == derive_attempt_id(att2, logical_request_id=prep.logical_request_id)


def test_deterministic_fingerprint_and_sink_idempotency():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    att = _att(attempt_number=1)
    r1 = translate_attempt(prep, att, normalizer=None, sink=sink)
    r2 = translate_attempt(prep, att, normalizer=None, sink=sink)  # identical replay
    assert r1.record_fingerprint == r2.record_fingerprint
    assert len(sink.records) == 1
