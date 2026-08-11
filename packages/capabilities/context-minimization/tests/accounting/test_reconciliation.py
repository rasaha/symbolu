"""Reconciliation (measurement C) — deny/failure/unknown paths dominate.

The provider-reported usage is authoritative for the response being reconciled but is
NOT an invoice; it never overwrites the estimate; unknown usage is None, never zero;
failed and retried attempts are preserved as distinct records; malformed counts and
conflicting duplicate identities fail closed.
"""

from __future__ import annotations

import math

import pytest

from ugence_context_minimization.api import (
    ApiCallTokenRecord,
    AttemptStatus,
    InMemoryTokenAccountingSink,
    ProviderTokenUsage,
    RequestComponents,
    UsageAvailability,
    prepare_api_call_measurement,
    reconcile_api_call_measurement,
)
from ugence_context_minimization.errors import InvalidRequestError, InvalidUnitError

from support_accounting import sample_minimization_result


def _prep(logical_request_id="lr"):
    res = sample_minimization_result()
    return prepare_api_call_measurement(
        minimization_result=res,
        logical_request_id=logical_request_id,
        provider_id="prov",
        request_components=RequestComponents(system_text="hi", minimized_context_tokens=res.resulting_tokens),
        model_id="m1",
    )


# --------------------------------------------------------------------------- #
# Worked example (§8).
# --------------------------------------------------------------------------- #
def test_worked_example_reconciliation():
    prep = _prep()
    # Overwrite context counts with the spec's exact worked numbers via a crafted record,
    # proving the arithmetic contract holds independent of the sampled minimization.
    usage = ProviderTokenUsage(input_tokens=2337, cached_input_tokens=1500, output_tokens=428)
    rec = ApiCallTokenRecord(
        logical_request_id="lr",
        attempt_id="a1",
        attempt_number=1,
        context_id=prep.context_id,
        minimization_run_fingerprint=prep.minimization_run_fingerprint,
        provider_id="prov",
        status=AttemptStatus.SUCCEEDED,
        provider_invoked=True,
        context_tokens_before=8214,
        context_tokens_after=2310,
        context_tokens_eliminated=5904,
        request_estimate=prep.request_estimate,
        usage_availability=UsageAvailability.AVAILABLE,
        provider_usage=usage,
    )
    assert rec.context_tokens_eliminated == 5904
    assert rec.provider_usage.input_tokens == 2337
    assert rec.provider_usage.cached_input_tokens == 1500
    assert rec.provider_usage.output_tokens == 428
    # The full-request estimate is a DIFFERENT number than provider-reported input.
    assert rec.request_estimate.estimated_input_tokens != rec.provider_usage.input_tokens


def test_estimate_is_never_overwritten_by_actual_usage():
    prep = _prep()
    before = prep.request_estimate.estimated_input_tokens
    usage = ProviderTokenUsage(input_tokens=before + 5000, output_tokens=10)
    rec = reconcile_api_call_measurement(
        prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED, provider_usage=usage
    )
    # Estimate untouched; usage carried separately.
    assert rec.request_estimate.estimated_input_tokens == before
    assert rec.provider_usage.input_tokens == before + 5000


# --------------------------------------------------------------------------- #
# Unknown / failure paths (the majority).
# --------------------------------------------------------------------------- #
def test_failed_attempt_with_unavailable_usage_is_unknown_not_zero():
    prep = _prep()
    rec = reconcile_api_call_measurement(
        prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.FAILED,
        usage_unavailable_reason="provider 500",
    )
    assert rec.status is AttemptStatus.FAILED
    assert rec.usage_availability is UsageAvailability.UNAVAILABLE_PROVIDER_ERROR
    assert rec.provider_usage is None  # unknown, never fabricated as zero


def test_provider_exception_produces_record_with_unknown_usage():
    prep = _prep()
    rec = reconcile_api_call_measurement(
        prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.EXCEPTION,
    )
    assert rec.status is AttemptStatus.EXCEPTION
    assert rec.provider_invoked is True
    assert rec.usage_availability is UsageAvailability.UNAVAILABLE_PROVIDER_ERROR
    assert rec.provider_usage is None


def test_failed_attempt_with_known_usage_keeps_usage():
    """A failed attempt can still have consumed tokens (§7.4)."""
    prep = _prep()
    usage = ProviderTokenUsage(input_tokens=1200, output_tokens=0)
    rec = reconcile_api_call_measurement(
        prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.FAILED, provider_usage=usage
    )
    assert rec.status is AttemptStatus.FAILED
    assert rec.usage_availability is UsageAvailability.AVAILABLE
    assert rec.provider_usage.input_tokens == 1200


def test_success_without_reported_usage_is_not_reported():
    prep = _prep()
    rec = reconcile_api_call_measurement(
        prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED
    )
    assert rec.usage_availability is UsageAvailability.UNAVAILABLE_NOT_REPORTED
    assert rec.provider_usage is None


def test_available_usage_requires_a_known_field():
    prep = _prep()
    with pytest.raises(InvalidRequestError):
        reconcile_api_call_measurement(
            prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
            usage_availability=UsageAvailability.AVAILABLE,
            provider_usage=ProviderTokenUsage(),  # all-None → nothing known
        )


def test_available_usage_requires_provider_invoked():
    prep = _prep()
    with pytest.raises(InvalidRequestError):
        ApiCallTokenRecord(
            logical_request_id="lr", attempt_id="a1", attempt_number=1,
            context_id=prep.context_id, minimization_run_fingerprint=prep.minimization_run_fingerprint,
            provider_id="prov", status=AttemptStatus.SUCCEEDED, provider_invoked=False,
            context_tokens_before=10, context_tokens_after=4, context_tokens_eliminated=6,
            request_estimate=prep.request_estimate,
            usage_availability=UsageAvailability.AVAILABLE,
            provider_usage=ProviderTokenUsage(input_tokens=1),
        )


def test_unavailable_usage_rejects_a_usage_object():
    prep = _prep()
    with pytest.raises(InvalidRequestError):
        ApiCallTokenRecord(
            logical_request_id="lr", attempt_id="a1", attempt_number=1,
            context_id=prep.context_id, minimization_run_fingerprint=prep.minimization_run_fingerprint,
            provider_id="prov", status=AttemptStatus.FAILED, provider_invoked=True,
            context_tokens_before=10, context_tokens_after=4, context_tokens_eliminated=6,
            request_estimate=prep.request_estimate,
            usage_availability=UsageAvailability.UNAVAILABLE_NOT_REPORTED,
            provider_usage=ProviderTokenUsage(input_tokens=1),
        )


# --------------------------------------------------------------------------- #
# Malformed token counts fail closed (§4).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [-1, True, 1.5, float("nan"), math.inf, "5", -0.0001])
def test_malformed_provider_token_counts_rejected(bad):
    with pytest.raises((InvalidUnitError, InvalidRequestError)):
        ProviderTokenUsage(input_tokens=bad)


@pytest.mark.parametrize("bad", [-1, True, 1.5, float("nan"), math.inf, "5"])
def test_malformed_estimate_rejected(bad):
    prep = _prep()
    from ugence_context_minimization.api import RequestTokenEstimate, TokenCountBasis

    with pytest.raises((InvalidUnitError, InvalidRequestError)):
        RequestTokenEstimate(
            estimated_input_tokens=bad, counter_id="c", counter_version="1",
            basis=TokenCountBasis.CALLER_SUPPLIED,
        )


def test_context_count_inconsistency_rejected():
    prep = _prep()
    with pytest.raises(InvalidRequestError):
        ApiCallTokenRecord(
            logical_request_id="lr", attempt_id="a1", attempt_number=1,
            context_id=prep.context_id, minimization_run_fingerprint=prep.minimization_run_fingerprint,
            provider_id="prov", status=AttemptStatus.SUCCEEDED, provider_invoked=True,
            context_tokens_before=100, context_tokens_after=40, context_tokens_eliminated=999,  # != 60
            request_estimate=prep.request_estimate,
            usage_availability=UsageAvailability.UNAVAILABLE_NOT_REPORTED,
        )


def test_after_greater_than_before_rejected():
    prep = _prep()
    with pytest.raises(InvalidRequestError):
        ApiCallTokenRecord(
            logical_request_id="lr", attempt_id="a1", attempt_number=1,
            context_id=prep.context_id, minimization_run_fingerprint=prep.minimization_run_fingerprint,
            provider_id="prov", status=AttemptStatus.SUCCEEDED, provider_invoked=True,
            context_tokens_before=40, context_tokens_after=100, context_tokens_eliminated=-60,
            request_estimate=prep.request_estimate,
            usage_availability=UsageAvailability.UNAVAILABLE_NOT_REPORTED,
        )


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, "1"])
def test_bad_attempt_number_rejected(bad):
    prep = _prep()
    with pytest.raises(InvalidRequestError):
        ApiCallTokenRecord(
            logical_request_id="lr", attempt_id="a1", attempt_number=bad,
            context_id=prep.context_id, minimization_run_fingerprint=prep.minimization_run_fingerprint,
            provider_id="prov", status=AttemptStatus.SUCCEEDED, provider_invoked=True,
            context_tokens_before=10, context_tokens_after=4, context_tokens_eliminated=6,
            request_estimate=prep.request_estimate,
            usage_availability=UsageAvailability.UNAVAILABLE_NOT_REPORTED,
        )


# --------------------------------------------------------------------------- #
# Cached / reasoning details are not double-counted (§7.6, §7.7).
# --------------------------------------------------------------------------- #
def test_cached_and_reasoning_not_folded_into_totals():
    usage = ProviderTokenUsage(
        input_tokens=2337, cached_input_tokens=1500, cache_write_input_tokens=200,
        output_tokens=428, reasoning_tokens=128,
    )
    # derived_total is input+output ONLY — cached/cache-write/reasoning excluded.
    assert usage.derived_total() == 2337 + 428
    # cached remains VISIBLE (not silently removed from input accounting).
    assert usage.cached_input_tokens == 1500


def test_reported_total_preserved_separately_from_derived():
    usage = ProviderTokenUsage(input_tokens=100, output_tokens=50, total_tokens=200)
    assert usage.total_tokens == 200  # provider-reported, preserved verbatim
    assert usage.derived_total() == 150  # derived, explicitly different


# --------------------------------------------------------------------------- #
# Unknown fields serialize as null, not zero (§8).
# --------------------------------------------------------------------------- #
def test_unknown_usage_fields_serialize_as_null():
    usage = ProviderTokenUsage(input_tokens=10)  # everything else unknown
    d = usage.to_dict()
    assert d["input_tokens"] == 10
    assert d["output_tokens"] is None
    assert d["cached_input_tokens"] is None
    assert d["total_tokens"] is None
    assert d["derived_total"] is None  # can't derive without output


# --------------------------------------------------------------------------- #
# Duplicate attempt identity (§4).
# --------------------------------------------------------------------------- #
def test_idempotent_replay_of_identical_record_is_accepted():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    usage = ProviderTokenUsage(input_tokens=100, output_tokens=20)
    for _ in range(3):
        reconcile_api_call_measurement(
            prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
            provider_usage=usage, sink=sink,
        )
    assert len(sink.records) == 1  # identical replay not double-stored


def test_duplicate_attempt_id_with_conflicting_content_rejected():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    reconcile_api_call_measurement(
        prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.SUCCEEDED,
        provider_usage=ProviderTokenUsage(input_tokens=100, output_tokens=20), sink=sink,
    )
    with pytest.raises(InvalidRequestError):
        reconcile_api_call_measurement(
            prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.FAILED, sink=sink,
        )
