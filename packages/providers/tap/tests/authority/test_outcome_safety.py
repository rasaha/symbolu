"""Outcome-safety invariants: uncertainty/failure is never promoted to SUPPORTED.

This is the release gate. Every non-determination and every infrastructure failure
maps to INDETERMINATE (or a classified error under fail-safe-off) — never SUPPORTED.
"""
from __future__ import annotations

import pytest

from ugence_governance_provider_framework.api import (
    AssertionCoverage, AssertionGovernanceRequest)
from ugence_tap_provider.configuration import TapSettings, build_tap_provider
from ugence_tap_provider.core import TapEngine, TapEvaluationResult, TapOutcome
from ugence_tap_provider.mapping import map_result


def _p(**kw):
    p = build_tap_provider(TapEngine(**kw)); p.initialize()
    return p


def test_unknown_native_outcome_maps_to_indeterminate():
    assert map_result(TapEvaluationResult(outcome=TapOutcome.UNKNOWN)).coverage \
        is AssertionCoverage.INDETERMINATE


def test_every_outcome_maps_exactly():
    expected = {
        TapOutcome.SUPPORTED: AssertionCoverage.SUPPORTED,
        TapOutcome.UNSUPPORTED: AssertionCoverage.UNSUPPORTED,
        TapOutcome.CONSTRAINED: AssertionCoverage.CONSTRAINED,
        TapOutcome.INDETERMINATE: AssertionCoverage.INDETERMINATE,
        TapOutcome.UNKNOWN: AssertionCoverage.INDETERMINATE,
    }
    for native, coverage in expected.items():
        assert map_result(TapEvaluationResult(outcome=native)).coverage is coverage


@pytest.mark.parametrize("fail", ["timeout", "unavailable", "malformed", "protocol", "config"])
def test_infrastructure_failure_never_supported(fail):
    r = _p(fail=fail).evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    assert r.coverage is AssertionCoverage.INDETERMINATE
    assert r.coverage is not AssertionCoverage.SUPPORTED


def test_missing_evidence_never_supported():
    r = _p().evaluate(AssertionGovernanceRequest("A", evidence_refs=()))
    assert r.coverage is AssertionCoverage.INDETERMINATE


def test_constrained_and_indeterminate_stay_distinct_from_supported():
    from ugence_tap_provider.core import TapRule
    constrained = _p(rules={"C": TapRule(outcome=TapOutcome.CONSTRAINED,
                                         evidence_coverage=0.5)}).evaluate(
        AssertionGovernanceRequest("C", evidence_refs=("e1", "e2")))
    assert constrained.coverage is AssertionCoverage.CONSTRAINED
    assert constrained.coverage is not AssertionCoverage.SUPPORTED
    indeterminate = _p(emit_unknown=True).evaluate(
        AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    assert indeterminate.coverage is AssertionCoverage.INDETERMINATE
    assert indeterminate.coverage is not AssertionCoverage.SUPPORTED


def test_evidence_coverage_is_clamped_to_unit_interval():
    over = map_result(TapEvaluationResult(outcome=TapOutcome.SUPPORTED,
                                          evidence_coverage=5.0))
    under = map_result(TapEvaluationResult(outcome=TapOutcome.INDETERMINATE,
                                           evidence_coverage=-3.0))
    assert 0.0 <= over.evidence_coverage <= 1.0
    assert 0.0 <= under.evidence_coverage <= 1.0


def test_failsafe_off_raises_classified_never_returns_supported():
    from ugence_governance_provider_framework.api import ProviderTimeoutError
    p = build_tap_provider(TapEngine(fail="timeout"), settings=TapSettings(fail_safe=False))
    p.initialize()
    with pytest.raises(ProviderTimeoutError):
        p.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
