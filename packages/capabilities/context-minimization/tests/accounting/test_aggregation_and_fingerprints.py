"""Logical-request aggregation + deterministic fingerprints.

Three attempts stay three records; retry/failed token sums are separate; unknown usage
keeps ``complete=False`` and is never zeroed; context savings are counted ONCE; record
and summary fingerprints are deterministic and sensitive to the right fields.
"""

from __future__ import annotations

import dataclasses

import pytest

from ugence_context_minimization.api import (
    AttemptStatus,
    InMemoryTokenAccountingSink,
    ProviderTokenUsage,
    RequestComponents,
    TokenCountBasis,
    UsageAvailability,
    aggregate_logical_request_usage,
    prepare_api_call_measurement,
    reconcile_api_call_measurement,
)
from ugence_context_minimization.errors import InvalidRequestError

from support_accounting import ExactRequestCounter, sample_minimization_result


def _prep(logical_request_id="lr", counter=None):
    res = sample_minimization_result()
    return prepare_api_call_measurement(
        minimization_result=res,
        logical_request_id=logical_request_id,
        provider_id="prov",
        request_counter=counter,
        request_components=None if counter else RequestComponents(minimized_context_tokens=res.resulting_tokens),
        model_id="m1",
    )


def test_three_attempts_remain_three_records():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    for i in range(1, 4):
        reconcile_api_call_measurement(
            prep, attempt_id=f"a{i}", attempt_number=i, status=AttemptStatus.FAILED if i < 3 else AttemptStatus.SUCCEEDED,
            retry_of_attempt_id=(f"a{i-1}" if i > 1 else None),
            provider_usage=ProviderTokenUsage(input_tokens=100 * i, output_tokens=i),
            sink=sink,
        )
    summ = aggregate_logical_request_usage(sink.records)
    assert summ.attempt_count == 3
    assert summ.succeeded_count == 1
    assert summ.failed_count == 2


def test_retry_and_failed_token_aggregation():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    # Attempt 1 FAILED (input 100), attempt 2 (retry) FAILED (input 200), attempt 3 SUCCEEDED (input 300).
    reconcile_api_call_measurement(prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.FAILED,
                                   provider_usage=ProviderTokenUsage(input_tokens=100, output_tokens=1), sink=sink)
    reconcile_api_call_measurement(prep, attempt_id="a2", attempt_number=2, status=AttemptStatus.FAILED,
                                   retry_of_attempt_id="a1",
                                   provider_usage=ProviderTokenUsage(input_tokens=200, output_tokens=2), sink=sink)
    reconcile_api_call_measurement(prep, attempt_id="a3", attempt_number=3, status=AttemptStatus.SUCCEEDED,
                                   retry_of_attempt_id="a2",
                                   provider_usage=ProviderTokenUsage(input_tokens=300, output_tokens=3), sink=sink)
    summ = aggregate_logical_request_usage(sink.records)
    assert summ.provider_input_tokens == 600
    assert summ.provider_output_tokens == 6
    # Retry attempts (2 and 3 — attempt_number>1) consumed 200+300 input.
    assert summ.retry_input_tokens == 500
    # Failed attempts (1 and 2) consumed 100+200 input — NOT zeroed just because they failed.
    assert summ.failed_attempt_input_tokens == 300
    assert summ.complete is True


def test_unknown_usage_marks_summary_incomplete_not_zero():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    reconcile_api_call_measurement(prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
                                   provider_usage=ProviderTokenUsage(input_tokens=500, output_tokens=50), sink=sink)
    # A second attempt failed with NO usage reported.
    reconcile_api_call_measurement(prep, attempt_id="a2", attempt_number=2, status=AttemptStatus.FAILED, sink=sink)
    summ = aggregate_logical_request_usage(sink.records)
    assert summ.attempt_count == 2
    assert summ.attempts_usage_unknown == 1
    assert summ.complete is False  # a gap exists → not claimed zero
    # Known usage still summed correctly.
    assert summ.provider_input_tokens == 500


def test_context_savings_counted_once_across_attempts():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    for i in range(1, 4):
        reconcile_api_call_measurement(prep, attempt_id=f"a{i}", attempt_number=i,
                                       status=AttemptStatus.SUCCEEDED,
                                       provider_usage=ProviderTokenUsage(input_tokens=10, output_tokens=1), sink=sink)
    summ = aggregate_logical_request_usage(sink.records)
    # NOT multiplied by 3 — the shared minimization run's savings appear once.
    assert summ.context_tokens_eliminated == prep.context_tokens_eliminated
    assert summ.context_tokens_before == prep.context_tokens_before


def test_total_provenance_is_not_blended(F1=True):
    """F1: a field named provider ... total contains ONLY provider-reported totals.

    a1 reports an explicit total (999); a2 reports none (derived 30). The reported-total
    field must be 999 alone; the derived field must be the sum of per-attempt input+output;
    and the settlement selection (reported-else-derived per attempt) must be 999 + 30.
    """
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    reconcile_api_call_measurement(prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
                                   provider_usage=ProviderTokenUsage(input_tokens=10, output_tokens=5, total_tokens=999), sink=sink)
    reconcile_api_call_measurement(prep, attempt_id="a2", attempt_number=2, status=AttemptStatus.SUCCEEDED,
                                   provider_usage=ProviderTokenUsage(input_tokens=20, output_tokens=10), sink=sink)
    summ = aggregate_logical_request_usage(sink.records)
    # ONLY the explicit provider total contributes here (a2 reported none).
    assert summ.provider_reported_total_tokens == 999
    assert summ.attempts_reporting_total == 1
    # Derived = per-attempt input+output over both known attempts (15 + 30).
    assert summ.derived_total_tokens == 15 + 30
    # Settlement selection: reported-else-derived per attempt (999 for a1, 30 for a2).
    assert summ.settlement_token_units == 999 + 30
    # No field named "provider ... total" carries the blended derived value.
    assert not hasattr(summ, "provider_total_tokens")


def test_divergent_run_fingerprint_across_attempts_fails_closed():
    prep_a = _prep()
    # Second prepared measurement from a DIFFERENT minimization run.
    prep_b = _prep()
    # Force a different run fingerprint by replacing it.
    prep_b = dataclasses.replace(prep_b, minimization_run_fingerprint="sha256:different")
    r1 = reconcile_api_call_measurement(prep_a, attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
                                        provider_usage=ProviderTokenUsage(input_tokens=1, output_tokens=1))
    r2 = reconcile_api_call_measurement(prep_b, attempt_id="a2", attempt_number=2, status=AttemptStatus.SUCCEEDED,
                                        provider_usage=ProviderTokenUsage(input_tokens=1, output_tokens=1))
    with pytest.raises(InvalidRequestError):
        aggregate_logical_request_usage([r1, r2])


def test_aggregate_selects_by_logical_request_id():
    prep_a = _prep(logical_request_id="lr-a")
    prep_b = _prep(logical_request_id="lr-b")
    r1 = reconcile_api_call_measurement(prep_a, attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
                                        provider_usage=ProviderTokenUsage(input_tokens=1, output_tokens=1))
    r2 = reconcile_api_call_measurement(prep_b, attempt_id="b1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
                                        provider_usage=ProviderTokenUsage(input_tokens=2, output_tokens=2))
    with pytest.raises(InvalidRequestError):
        aggregate_logical_request_usage([r1, r2])  # ambiguous — spans two logical requests
    summ = aggregate_logical_request_usage([r1, r2], logical_request_id="lr-b")
    assert summ.provider_input_tokens == 2


def test_empty_aggregation_rejected():
    with pytest.raises(InvalidRequestError):
        aggregate_logical_request_usage([])


# --------------------------------------------------------------------------- #
# Fingerprints.
# --------------------------------------------------------------------------- #
def test_record_fingerprint_is_deterministic():
    prep = _prep()
    kw = dict(attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
              provider_usage=ProviderTokenUsage(input_tokens=10, output_tokens=2))
    r1 = reconcile_api_call_measurement(prep, **kw)
    r2 = reconcile_api_call_measurement(prep, **kw)
    assert r1.record_fingerprint == r2.record_fingerprint
    assert r1.record_fingerprint.startswith("sha256:")


def test_summary_fingerprint_is_deterministic():
    prep = _prep()
    recs = [
        reconcile_api_call_measurement(prep, attempt_id=f"a{i}", attempt_number=i,
                                       status=AttemptStatus.SUCCEEDED,
                                       provider_usage=ProviderTokenUsage(input_tokens=i, output_tokens=1))
        for i in range(1, 4)
    ]
    s1 = aggregate_logical_request_usage(recs)
    s2 = aggregate_logical_request_usage(list(reversed(recs)))  # order-independent
    assert s1.summary_fingerprint == s2.summary_fingerprint


def test_different_counter_version_changes_record_fingerprint():
    """A different counter id/version changes the estimate → changes the record fp (§8)."""
    prep_v9 = _prep(counter=ExactRequestCounter(100))  # counter_version "9"

    class OtherCounter(ExactRequestCounter):
        counter_version = "10"

    prep_v10 = _prep(counter=OtherCounter(100))
    common = dict(attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
                  provider_usage=ProviderTokenUsage(input_tokens=10, output_tokens=2))
    r_v9 = reconcile_api_call_measurement(prep_v9, **common)
    r_v10 = reconcile_api_call_measurement(prep_v10, **common)
    assert r_v9.record_fingerprint != r_v10.record_fingerprint


def test_usage_change_changes_record_fingerprint():
    prep = _prep()
    r1 = reconcile_api_call_measurement(prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
                                        provider_usage=ProviderTokenUsage(input_tokens=10, output_tokens=2))
    r2 = reconcile_api_call_measurement(prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
                                        provider_usage=ProviderTokenUsage(input_tokens=11, output_tokens=2))
    assert r1.record_fingerprint != r2.record_fingerprint
