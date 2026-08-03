"""Request/result/control mapping + error translation + fail-safe policy."""
from __future__ import annotations

import pytest

from ugence_governance_provider_framework.api import (
    AssertionCoverage, AssertionGovernanceRequest,
    ProviderError, ProviderResultValidationError, ProviderTimeoutError,
    ProviderUnavailableError)
from ugence_tap_provider.configuration import build_tap_provider
from ugence_tap_provider.core import (
    TapConstraint, TapEngine, TapEvaluationResult, TapObligation, TapOutcome, TapRule)
from ugence_tap_provider.mapping import map_request, map_result


def test_request_mapping_preserves_fields_and_provenance():
    n = map_request(AssertionGovernanceRequest(
        assertion="A", assertion_type="claim", evidence_refs=("e1", "e2"),
        source_identity="src", policy_refs=("p:1",), context={"k": "v"},
        correlation_id="c"))
    assert n.assertion == "A" and n.assertion_type == "claim"
    assert n.policy_references == ("p:1",) and n.correlation_id == "c"
    assert n.source_identity == "src" and len(n.evidence) == 2
    assert n.evidence[0].source_reference == "e1"
    assert n.evidence[0].provenance == "caller_supplied"
    assert n.evidence[0].fingerprint  # provenance preserved distinctly from support


def test_unknown_native_outcome_never_supported():
    d = TapEvaluationResult(outcome=TapOutcome.UNKNOWN)
    assert map_result(d).coverage is AssertionCoverage.INDETERMINATE


def test_constrained_result_mapping_preserves_components_and_controls():
    rule = TapRule(
        outcome=TapOutcome.CONSTRAINED, evidence_coverage=0.6,
        supported_components=("cost_reduction",),
        unsupported_components=("magnitude_20pct",),
        omitted_qualifiers=("segment_scope",),
        constraints=(TapConstraint("required_qualifier", "segment"),
                     TapConstraint("weird_ext", "x")),
        obligations=(TapObligation("include_uncertainty_disclosure"),),
        reason_codes=("scope_expansion",))
    p = build_tap_provider(TapEngine(rules={"C": rule})); p.initialize()
    r = p.evaluate(AssertionGovernanceRequest("C", evidence_refs=("e1", "e2")))
    assert r.coverage is AssertionCoverage.CONSTRAINED
    assert "magnitude_20pct" in r.unsupported_elements
    assert "segment_scope" in r.omitted_qualifiers
    assert "required_qualifier=segment" in r.constraints
    assert "ext:weird_ext=x" in r.constraints                 # unknown kept, not dropped
    assert "include_uncertainty_disclosure" in r.obligations
    # supported component + reason code retained in provider-owned explanation refs
    assert "supported:cost_reduction" in r.explanation_refs
    assert "reason:scope_expansion" in r.explanation_refs


def test_missing_evidence_is_indeterminate_not_supported():
    p = build_tap_provider(); p.initialize()
    r = p.evaluate(AssertionGovernanceRequest("Unbacked", evidence_refs=()))
    assert r.coverage is AssertionCoverage.INDETERMINATE
    assert r.coverage is not AssertionCoverage.SUPPORTED


@pytest.mark.parametrize("fail", ["timeout", "unavailable", "malformed", "protocol"])
def test_failsafe_maps_infrastructure_failure_to_indeterminate(fail):
    p = build_tap_provider(TapEngine(fail=fail)); p.initialize()
    r = p.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    assert r.coverage is AssertionCoverage.INDETERMINATE  # never SUPPORTED


@pytest.mark.parametrize("fail,exc", [
    ("timeout", ProviderTimeoutError),
    ("unavailable", ProviderUnavailableError),
    ("malformed", ProviderResultValidationError),
])
def test_non_failsafe_raises_classified_error(fail, exc):
    from ugence_tap_provider.configuration import TapSettings
    p = build_tap_provider(TapEngine(fail=fail),
                           settings=TapSettings(fail_safe=False)); p.initialize()
    with pytest.raises(exc):
        p.evaluate(AssertionGovernanceRequest("X", evidence_refs=("e1",)))


def test_no_native_exception_leaks():
    from ugence_tap_provider.core import TapError
    from ugence_tap_provider.configuration import TapSettings
    p = build_tap_provider(TapEngine(fail="config"),
                           settings=TapSettings(fail_safe=False)); p.initialize()
    with pytest.raises(ProviderError) as ei:
        p.evaluate(AssertionGovernanceRequest("X", evidence_refs=("e1",)))
    assert not isinstance(ei.value, TapError)
