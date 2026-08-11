"""The three distinct measurements stay distinct, and the pre-call estimate is honest.

A = context reduction (owned by the minimizer), B = complete-request estimate,
C = provider-reported usage. This module covers A/B (estimate provenance + linkage);
reconciliation (C) and aggregation live in the sibling adversarial/aggregation modules.
"""

from __future__ import annotations

import dataclasses

import pytest

from ugence_context_minimization.api import (
    DefaultApproximateRequestCounter,
    RequestComponents,
    RequestTokenEstimate,
    TokenCountBasis,
    prepare_api_call_measurement,
)
from ugence_context_minimization.errors import InvalidRequestError

from support_accounting import ExactRequestCounter, sample_minimization_result


def test_prepare_copies_minimization_counts_verbatim():
    """Measurement A is copied, never re-derived or mutated (§2A)."""
    res = sample_minimization_result()
    prep = prepare_api_call_measurement(
        minimization_result=res, logical_request_id="lr", provider_id="prov"
    )
    assert prep.context_tokens_before == res.original_tokens
    assert prep.context_tokens_after == res.resulting_tokens
    assert prep.context_tokens_eliminated == res.original_tokens - res.resulting_tokens
    # The minimization result object itself is unchanged (frozen; identity preserved).
    assert prep.minimization_run_fingerprint == res.run_fingerprint


def test_default_counter_is_labelled_approximate():
    res = sample_minimization_result()
    prep = prepare_api_call_measurement(
        minimization_result=res,
        logical_request_id="lr",
        provider_id="prov",
        request_components=RequestComponents(system_text="a b c", minimized_context_tokens=res.resulting_tokens),
    )
    est = prep.request_estimate
    assert est.basis is TokenCountBasis.DEFAULT_APPROXIMATE
    assert est.is_approximate is True
    assert est.counter_id == DefaultApproximateRequestCounter.counter_id


def test_default_counter_with_images_marks_incomplete_coverage():
    res = sample_minimization_result()
    prep = prepare_api_call_measurement(
        minimization_result=res,
        logical_request_id="lr",
        provider_id="prov",
        request_components=RequestComponents(system_text="hi", image_count=2),
    )
    est = prep.request_estimate
    assert est.covers_images is False
    assert est.covers_non_text is False
    assert est.incomplete_reason is not None
    assert est.is_approximate is True


def test_exact_injected_counter_is_not_approximate():
    res = sample_minimization_result()
    prep = prepare_api_call_measurement(
        minimization_result=res,
        logical_request_id="lr",
        provider_id="prov",
        request_counter=ExactRequestCounter(4242),
        model_id="m1",
    )
    est = prep.request_estimate
    assert est.basis is TokenCountBasis.INJECTED_COUNTER
    assert est.estimated_input_tokens == 4242
    assert est.is_approximate is False


def test_mixed_basis_is_labelled_mixed():
    res = sample_minimization_result()
    prep = prepare_api_call_measurement(
        minimization_result=res,
        logical_request_id="lr",
        provider_id="prov",
        request_counter=ExactRequestCounter(100, basis=TokenCountBasis.MIXED),
    )
    assert prep.request_estimate.basis is TokenCountBasis.MIXED


def test_caller_supplied_estimate_preserved():
    res = sample_minimization_result()
    supplied = RequestTokenEstimate(
        estimated_input_tokens=999,
        counter_id="caller",
        counter_version="1",
        basis=TokenCountBasis.CALLER_SUPPLIED,
        covers_tools=True,
        covers_schemas=True,
        covers_non_text=True,
    )
    prep = prepare_api_call_measurement(
        minimization_result=res,
        logical_request_id="lr",
        provider_id="prov",
        request_estimate=supplied,
    )
    assert prep.request_estimate is supplied
    assert prep.request_estimate.basis is TokenCountBasis.CALLER_SUPPLIED


def test_full_request_estimate_distinct_from_minimized_context():
    """§2: the full-request estimate must be its own number, larger than context alone."""
    res = sample_minimization_result()
    prep = prepare_api_call_measurement(
        minimization_result=res,
        logical_request_id="lr",
        provider_id="prov",
        request_components=RequestComponents(
            system_text="you are a helpful assistant with many instructions here",
            message_texts=("hello there general", "another user turn with words"),
            minimized_context_tokens=res.resulting_tokens,
            tool_definition_texts=("tool one schema blob", "tool two schema blob"),
        ),
    )
    # Estimate includes system + messages + tools ON TOP of the minimized context.
    assert prep.request_estimate.estimated_input_tokens > prep.context_tokens_after


def test_reduction_pct_is_deterministic():
    res = sample_minimization_result()
    prep = prepare_api_call_measurement(
        minimization_result=res, logical_request_id="lr", provider_id="prov"
    )
    from ugence_context_minimization.api import ApiCallTokenRecord, AttemptStatus, UsageAvailability

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
        usage_availability=UsageAvailability.UNAVAILABLE_NOT_REPORTED,
    )
    assert rec.reduction_pct == pytest.approx(5904 / 8214)
    # Deterministic: same inputs → same float, every call.
    assert rec.reduction_pct == rec.reduction_pct


def test_supplying_both_estimate_and_counter_is_rejected():
    res = sample_minimization_result()
    with pytest.raises(InvalidRequestError):
        prepare_api_call_measurement(
            minimization_result=res,
            logical_request_id="lr",
            provider_id="prov",
            request_estimate=RequestTokenEstimate(
                estimated_input_tokens=1, counter_id="c", counter_version="1",
                basis=TokenCountBasis.CALLER_SUPPLIED,
            ),
            request_counter=ExactRequestCounter(2),
        )
