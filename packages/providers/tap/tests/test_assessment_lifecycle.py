"""TAP assessment/recommendation lifecycle fixtures (migrated, kernel-guarded).

Four assertion fixtures (supported / constrained / unsupported / indeterminate)
prove TAP feeds the assessment→recommendation→decision-trace workflow and never
execution: uncertainty and infrastructure failure are never promoted to support.

Requires the Decision Authority kernel (optional ``decision-authority`` extra); the
ActionGate peer-composition proof lives in the monorepo suite, not here — ActionGate
is a peer, not a TAP dependency.
"""
from __future__ import annotations

import pytest

pytest.importorskip("decision_governance",
                    reason="assessment lifecycle needs the decision-authority extra")

from ugence_governance_provider_framework.api import AssertionGovernanceRequest  # noqa: E402
from ugence_tap_provider.configuration import build_tap_provider  # noqa: E402
from ugence_tap_provider.core import (  # noqa: E402
    TapConstraint, TapEngine, TapObligation, TapOutcome, TapRule)

from lifecycle_harness import run_tap_assessment_lifecycle  # noqa: E402

_SUPPLIER = "Supplier X reduced costs by 20% and has no compliance incidents"


def _provider(rules=None):
    p = build_tap_provider(TapEngine(rules=rules or {})); p.initialize()
    return p


def test_supported_assertion_recommendation_cites_supported_assessment():
    from decision_governance.api.audit import AuditEventType
    r = run_tap_assessment_lifecycle(
        _provider(), AssertionGovernanceRequest("Revenue increased",
                                                assertion_type="claim", evidence_refs=("e1",)))
    assert r.coverage == "SUPPORTED"
    assert r.finalized and not r.blocked
    assert r.proposed_outcome == "ADVANCE"
    assert r.cites_assessment
    assert AuditEventType.DECISION_CASE_RECOMMENDATION_ADDED in r.events
    assert AuditEventType.DECISION_CASE_ASSESSMENT_LINKED in r.events


def test_constrained_assertion_retains_qualifier_and_carries_constraint():
    rule = TapRule(
        outcome=TapOutcome.CONSTRAINED, evidence_coverage=0.5,
        supported_components=("revenue_increase",),
        omitted_qualifiers=("north_america_segment",),
        constraints=(TapConstraint("required_qualifier", "segment_scope"),),
        obligations=(TapObligation("include_uncertainty_disclosure"),),
        reason_codes=("scope_expansion",))
    r = run_tap_assessment_lifecycle(
        _provider({"Revenue increased": rule}),
        AssertionGovernanceRequest("Revenue increased", evidence_refs=("e1", "e2")))
    assert r.coverage == "CONSTRAINED"
    assert r.blocked
    assert "north_america_segment" in r.omitted_qualifiers
    assert "required_qualifier=segment_scope" in r.constraints
    assert r.proposed_outcome == "HOLD"
    assert r.cites_assessment


def test_unsupported_assertion_cannot_be_represented_as_supported():
    rule = TapRule(outcome=TapOutcome.UNSUPPORTED, evidence_coverage=0.0,
                   unsupported_components=("no_compliance_incidents",),
                   reason_codes=("contradicting_evidence",))
    r = run_tap_assessment_lifecycle(
        _provider({_SUPPLIER: rule}),
        AssertionGovernanceRequest(_SUPPLIER, evidence_refs=("e1",)))
    assert r.coverage == "UNSUPPORTED"
    assert not r.finalized
    assert r.proposed_outcome == "REJECT"
    assert r.proposed_outcome != "ADVANCE"
    assert "no_compliance_incidents" in r.unsupported_elements


def test_indeterminate_assertion_no_silent_promotion_to_supported():
    r = run_tap_assessment_lifecycle(
        _provider(), AssertionGovernanceRequest("Ambiguous claim", evidence_refs=()))
    assert r.coverage == "INDETERMINATE"
    assert not r.finalized
    assert r.proposed_outcome == "REQUEST_ADDITIONAL_EVIDENCE"
    assert r.proposed_outcome != "ADVANCE"
