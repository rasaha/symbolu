"""F1 — total provenance is never blended.

`provider_reported_total_tokens` holds ONLY provider-reported totals; `derived_total_tokens`
holds ONLY input+output derivations; `settlement_token_units` is the documented per-attempt
selection. Cached/reasoning are never re-added. Incomplete summaries stay conservative.
"""

from __future__ import annotations

import pytest

from ugence_context_minimization.api import (
    AttemptStatus,
    InMemoryTokenAccountingSink,
    ProviderTokenUsage,
    aggregate_logical_request_usage,
    prepare_api_call_measurement,
    reconcile_api_call_measurement,
)

from support_accounting import sample_minimization_result


def _prep(lr="lr"):
    return prepare_api_call_measurement(
        minimization_result=sample_minimization_result(), logical_request_id=lr, provider_id="prov"
    )


def _rec(prep, sink, aid, n, usage, status=AttemptStatus.SUCCEEDED):
    return reconcile_api_call_measurement(
        prep, attempt_id=aid, attempt_number=n, status=status, provider_usage=usage, sink=sink
    )


def test_one_explicit_provider_total():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    _rec(prep, sink, "a1", 1, ProviderTokenUsage(input_tokens=100, output_tokens=40, total_tokens=145))
    s = aggregate_logical_request_usage(sink.records)
    assert s.provider_reported_total_tokens == 145
    assert s.attempts_reporting_total == 1
    assert s.derived_total_tokens == 140  # 100 + 40
    assert s.settlement_token_units == 145  # reported preferred


def test_derived_total_with_no_provider_total():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    _rec(prep, sink, "a1", 1, ProviderTokenUsage(input_tokens=100, output_tokens=40))  # no total
    s = aggregate_logical_request_usage(sink.records)
    assert s.provider_reported_total_tokens == 0  # NONE reported → zero reported, not derived
    assert s.attempts_reporting_total == 0
    assert s.derived_total_tokens == 140
    assert s.settlement_token_units == 140  # falls back to derived


def test_mixed_reported_and_derived_across_retries():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    _rec(prep, sink, "a1", 1, ProviderTokenUsage(input_tokens=10, output_tokens=5, total_tokens=999), status=AttemptStatus.FAILED)
    _rec(prep, sink, "a2", 2, ProviderTokenUsage(input_tokens=20, output_tokens=10))  # derived 30
    s = aggregate_logical_request_usage(sink.records)
    assert s.provider_reported_total_tokens == 999  # only a1's explicit total
    assert s.attempts_reporting_total == 1
    assert s.derived_total_tokens == 15 + 30
    assert s.settlement_token_units == 999 + 30  # per-attempt: reported for a1, derived for a2


def test_known_plus_unknown_attempt_stays_incomplete():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    _rec(prep, sink, "a1", 1, ProviderTokenUsage(input_tokens=500, output_tokens=50, total_tokens=550))
    reconcile_api_call_measurement(prep, attempt_id="a2", attempt_number=2, status=AttemptStatus.FAILED, sink=sink)
    s = aggregate_logical_request_usage(sink.records)
    assert s.attempts_usage_unknown == 1
    assert s.complete is False  # gap present
    assert s.provider_reported_total_tokens == 550  # known contribution preserved
    assert s.settlement_token_units == 550


def test_inconsistent_provider_total_vs_derived_are_both_preserved_distinctly():
    """A provider total that disagrees with input+output is preserved AS-IS, not reconciled."""
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    # Reported total 500 but input+output = 60 (provider's own accounting differs).
    _rec(prep, sink, "a1", 1, ProviderTokenUsage(input_tokens=40, output_tokens=20, total_tokens=500))
    s = aggregate_logical_request_usage(sink.records)
    assert s.provider_reported_total_tokens == 500  # verbatim provider value
    assert s.derived_total_tokens == 60  # honest derivation, not forced to match
    assert s.settlement_token_units == 500  # settlement uses the reported total


def test_cached_and_reasoning_not_re_added_to_totals():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    _rec(prep, sink, "a1", 1, ProviderTokenUsage(
        input_tokens=2337, cached_input_tokens=1500, cache_write_input_tokens=200,
        output_tokens=428, reasoning_tokens=128,
    ))
    s = aggregate_logical_request_usage(sink.records)
    # derived = input + output ONLY (cached/cache-write/reasoning excluded).
    assert s.derived_total_tokens == 2337 + 428
    assert s.settlement_token_units == 2337 + 428
    assert s.provider_input_tokens == 2337  # cached is NOT removed from input either


def test_conservative_when_summary_incomplete_settlement_units_still_partial_but_flagged():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    _rec(prep, sink, "a1", 1, ProviderTokenUsage(input_tokens=100, output_tokens=20, total_tokens=120))
    reconcile_api_call_measurement(prep, attempt_id="a2", attempt_number=2, status=AttemptStatus.EXCEPTION, sink=sink)
    s = aggregate_logical_request_usage(sink.records)
    # settlement_token_units reflects only known attempts, but `complete=False` is the
    # signal a settler must honor (see integration settle_budget_from_summary → conservative).
    assert s.complete is False
    assert s.settlement_token_units == 120


def test_summary_fingerprint_deterministic_after_split():
    prep = _prep()
    recs = [
        _rec(_prep(), InMemoryTokenAccountingSink(), "a1", 1,
             ProviderTokenUsage(input_tokens=10, output_tokens=2, total_tokens=12)),
    ]
    s1 = aggregate_logical_request_usage(recs)
    s2 = aggregate_logical_request_usage(list(recs))
    assert s1.summary_fingerprint == s2.summary_fingerprint
    # the fingerprint binds the new provenance fields
    assert "provider_reported_total_tokens" in s1.to_dict()
    assert "derived_total_tokens" in s1.to_dict()
    assert "settlement_token_units" in s1.to_dict()
    assert "provider_total_tokens" not in s1.to_dict()
