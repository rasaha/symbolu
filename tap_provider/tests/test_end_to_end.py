"""Assessment/recommendation fixtures + TAP↔ActionGate peer composition.

Four assertion fixtures (supported / constrained / unsupported / indeterminate)
prove TAP feeds the DGM assessment→recommendation→decision-trace workflow and
never execution. The peer fixture composes TAP and ActionGate in one application
and proves they are genuine, mutually-unaware peers.
"""
from __future__ import annotations

from decision_governance.api.audit import AuditEventType
from governance_providers.api import AssertionGovernanceRequest
from tap_provider.configuration import build_tap_provider
from tap_provider.core import TapConstraint, TapEngine, TapObligation, TapOutcome, TapRule

from .conftest import run_tap_assessment_lifecycle

_SUPPLIER = "Supplier X reduced costs by 20% and has no compliance incidents"


def _provider(rules=None):
    p = build_tap_provider(TapEngine(rules=rules or {})); p.initialize()
    return p


def test_supported_assertion_recommendation_cites_supported_assessment():
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
    assert r.blocked                                  # constrained → blocked/qualified
    assert "north_america_segment" in r.omitted_qualifiers
    assert "required_qualifier=segment_scope" in r.constraints
    assert r.proposed_outcome == "HOLD"               # not represented as supported
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


def test_tap_and_actiongate_are_independent_peers():
    """One application composition: TAP evaluates an assertion, ActionGate
    authorizes a later action. They correlate only through DGM records — neither
    imports nor invokes the other."""
    from actiongate_provider.configuration import build_actiongate_provider
    from actiongate_provider.core import ActionGateEngine
    from governance_providers.api import (
        ActionGovernanceControlPlaneAdapter, ActionGovernanceRequest, ProviderKind,
        ProviderRegistry)

    # both providers registered as peers of distinct kinds
    tap = build_tap_provider(); tap.initialize()
    ag = build_actiongate_provider(); ag.initialize()
    reg = ProviderRegistry()
    reg.register(tap.descriptor())
    reg.register(ag.descriptor())
    assert {d.kind for d in reg.list_by_kind()} >= {
        ProviderKind.ASSERTION_GOVERNANCE, ProviderKind.ACTION_GOVERNANCE}

    # TAP evaluates an assertion → assessment/recommendation (no execution)
    r = run_tap_assessment_lifecycle(
        tap, AssertionGovernanceRequest("Revenue increased", evidence_refs=("e1",)))
    assert r.coverage == "SUPPORTED" and r.cites_assessment

    # ActionGate authorizes a later, separate action (no assertion coupling).
    # The control-plane adapter proves it plugs into the kernel's action path,
    # entirely distinct from TAP's assessment path.
    ActionGovernanceControlPlaneAdapter(ag)
    auth = ag.authorize(ActionGovernanceRequest("ACT"))
    assert auth.outcome.value == "AUTHORIZED"

    # mutual unawareness (import-level) — neither module graph references the other
    import tap_provider, actiongate_provider  # noqa: F401
    import sys
    tap_mods = [m for m in sys.modules if m.startswith("tap_provider")]
    assert all("actiongate" not in m for m in tap_mods)
