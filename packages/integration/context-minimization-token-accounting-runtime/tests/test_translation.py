"""Attempt -> ApiCallTokenRecord translation (unit-level; deny/unknown heavy)."""

from __future__ import annotations

import math

import pytest

from ugence_agent_runtime.observability.attempts import ProviderAttempt, ProviderAttemptStatus

from ugence_context_minimization.api import (
    AttemptStatus,
    InMemoryTokenAccountingSink,
    UsageAvailability,
    prepare_api_call_measurement,
)
from ugence_context_minimization.errors import InvalidUnitError, InvalidRequestError

from ugence_cm_token_accounting_runtime import (
    MappingUsageNormalizer,
    derive_attempt_id,
    translate_attempt,
)

from support_itg import VENDOR_FIELD_MAP, sample_minimization_result


def _prep():
    res = sample_minimization_result()
    return prepare_api_call_measurement(
        minimization_result=res, logical_request_id="lr", provider_id="vendor", model_id="m1"
    )


def _attempt(**kw):
    base = dict(
        provider_id="vendor", operation="op", attempt_number=1,
        status=ProviderAttemptStatus.SUCCEEDED, ok=True, provider_invoked=True,
        instance_id="wf-1", task_id="t", correlation_id="corr-itg",
    )
    base.update(kw)
    return ProviderAttempt(**base)


def _norm():
    return MappingUsageNormalizer(
        VENDOR_FIELD_MAP, schema_name="vendor.v1", adapter_id="ad", adapter_version="1",
    )


def test_success_with_usage_translates_to_available_record():
    prep = _prep()
    att = _attempt(neutral_usage={"prompt_tokens": 2337, "cache_read_tokens": 1500, "completion_tokens": 428})
    rec = translate_attempt(prep, att, normalizer=_norm())
    assert rec.status is AttemptStatus.SUCCEEDED
    assert rec.usage_availability is UsageAvailability.AVAILABLE
    assert rec.provider_usage.input_tokens == 2337
    assert rec.provider_usage.cached_input_tokens == 1500
    assert rec.provider_usage.output_tokens == 428
    assert rec.provider_usage.usage_schema == "vendor.v1"
    assert rec.attempt_id == "wf-1:t:1"


def test_exception_attempt_has_unknown_usage():
    prep = _prep()
    att = _attempt(status=ProviderAttemptStatus.EXCEPTION, ok=False, neutral_usage=None)
    rec = translate_attempt(prep, att, normalizer=_norm())
    assert rec.status is AttemptStatus.EXCEPTION
    assert rec.usage_availability is UsageAvailability.UNAVAILABLE_PROVIDER_ERROR
    assert rec.provider_usage is None  # unknown, never fabricated as zero


def test_no_normalizer_means_usage_unavailable():
    prep = _prep()
    att = _attempt(neutral_usage={"prompt_tokens": 10})
    rec = translate_attempt(prep, att, normalizer=None)
    assert rec.provider_usage is None
    assert rec.usage_availability is not UsageAvailability.AVAILABLE


def test_normalizer_returning_no_usable_fields_is_unavailable():
    prep = _prep()
    # Vendor blob has none of the mapped source keys -> normalizer yields None.
    att = _attempt(neutral_usage={"unrelated": 5})
    rec = translate_attempt(prep, att, normalizer=_norm())
    assert rec.provider_usage is None
    assert rec.usage_availability is not UsageAvailability.AVAILABLE


def test_failed_attempt_with_usage_keeps_usage():
    prep = _prep()
    att = _attempt(status=ProviderAttemptStatus.FAILED, ok=False,
                   neutral_usage={"prompt_tokens": 1200})
    rec = translate_attempt(prep, att, normalizer=_norm())
    assert rec.status is AttemptStatus.FAILED
    assert rec.usage_availability is UsageAvailability.AVAILABLE
    assert rec.provider_usage.input_tokens == 1200


def test_retry_links_to_predecessor_deterministically():
    prep = _prep()
    att = _attempt(attempt_number=3, neutral_usage={"prompt_tokens": 5, "completion_tokens": 1})
    rec = translate_attempt(prep, att, normalizer=_norm())
    assert rec.attempt_number == 3
    assert rec.attempt_id == "wf-1:t:3"
    assert rec.retry_of_attempt_id == "wf-1:t:2"
    assert rec.is_retry is True


def test_derive_attempt_id_is_deterministic():
    att = _attempt(attempt_number=2)
    assert derive_attempt_id(att) == "wf-1:t:2"
    assert derive_attempt_id(att) == derive_attempt_id(att)


@pytest.mark.parametrize("bad", [-1, True, 1.5, math.nan, math.inf, "5"])
def test_malformed_vendor_counts_rejected_via_normalizer(bad):
    prep = _prep()
    att = _attempt(neutral_usage={"prompt_tokens": bad})
    with pytest.raises((InvalidUnitError, InvalidRequestError)):
        translate_attempt(prep, att, normalizer=_norm())


def test_mapping_normalizer_rejects_unknown_target_field():
    with pytest.raises(ValueError):
        MappingUsageNormalizer({"not_a_field": "x"})


def test_sink_records_and_rejects_conflicting_duplicate():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    att = _attempt(neutral_usage={"prompt_tokens": 10, "completion_tokens": 2})
    translate_attempt(prep, att, normalizer=_norm(), sink=sink)
    # identical replay is idempotent
    translate_attempt(prep, att, normalizer=_norm(), sink=sink)
    assert len(sink.records) == 1
    # a conflicting record under the same derived attempt_id is rejected
    conflicting = _attempt(status=ProviderAttemptStatus.FAILED, ok=False, neutral_usage=None)
    with pytest.raises(InvalidRequestError):
        translate_attempt(prep, conflicting, normalizer=_norm(), sink=sink)
