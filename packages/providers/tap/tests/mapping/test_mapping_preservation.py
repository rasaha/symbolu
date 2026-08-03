"""Request/result mapping preservation + deterministic fingerprints (canonical)."""
from __future__ import annotations

from ugence_governance_provider_framework.api import (
    AssertionCoverage, AssertionGovernanceRequest)
from ugence_tap_provider.configuration import build_tap_provider
from ugence_tap_provider.core import (
    TapConstraint, TapEngine, TapObligation, TapOutcome, TapRule)
from ugence_tap_provider.mapping import map_request, map_result


def test_request_mapping_preserves_all_fields_and_provenance():
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
    assert n.trace_id == "c"


def test_constrained_result_preserves_components_and_extension_controls():
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
    # unknown extension control kept (prefixed), never silently discarded
    assert "ext:weird_ext=x" in r.constraints
    assert "include_uncertainty_disclosure" in r.obligations
    assert "supported:cost_reduction" in r.explanation_refs
    assert "reason:scope_expansion" in r.explanation_refs


def test_covered_and_trace_and_correlation_preserved():
    p = build_tap_provider(); p.initialize()
    r = p.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1", "e2"),
                                              correlation_id="corr-9"))
    assert set(r.covered_evidence_refs) == {"e1", "e2"}
    assert r.provider_trace_id == "corr-9"


def test_fingerprints_are_deterministic():
    def one():
        p = build_tap_provider(TapEngine(rules={"C": TapRule(
            outcome=TapOutcome.CONSTRAINED, evidence_coverage=0.6,
            supported_components=("a",))})); p.initialize()
        return p.evaluate(AssertionGovernanceRequest("C", evidence_refs=("e1", "e2")))
    assert one().fingerprint == one().fingerprint


def test_result_mapping_totality_over_all_native_outcomes():
    from ugence_tap_provider.core import TapEvaluationResult
    for outcome in TapOutcome:
        r = map_result(TapEvaluationResult(outcome=outcome))
        assert isinstance(r.coverage, AssertionCoverage)
