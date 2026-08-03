"""Evidence-discipline tests (§24 — Evidence discipline; invariants I7, I8, I9)."""
from __future__ import annotations

from ugence_agent_workforce_composer.contracts import EligibilityState, EvidenceClass
from ugence_agent_workforce_composer.eligibility import evaluate_agent_eligibility
from ugence_agent_workforce_composer.reasons import EliminationReason
from ._helpers import (
    NOW,
    eligibility,
    enterprise,
    make_evidence,
    make_profile,
    make_role,
    make_snapshot,
)


def _eval(profile, evidence, role, ent=None, elig=None):
    snap = make_snapshot([profile], evidence)
    return evaluate_agent_eligibility(role, profile, snap, ent or enterprise(),
                                      elig or eligibility(), NOW)


def test_declared_only_rejected_when_measured_required():
    p = make_profile("a", "1.0.0")
    ev = [make_evidence("a", "1.0.0", "evidence_extraction", "DECLARED")]
    r = _eval(p, ev, make_role(required_evidence_classes=("MEASURED",)))
    assert r.state is EligibilityState.INELIGIBLE
    assert EliminationReason.DECLARED_ONLY_WHEN_MEASURED_REQUIRED.value in r.elimination_reasons


def test_measured_accepted_when_policy_permits():
    p = make_profile("a", "1.0.0")
    ev = [make_evidence("a", "1.0.0", "evidence_extraction", "MEASURED")]
    r = _eval(p, ev, make_role(required_evidence_classes=("MEASURED",)))
    assert r.state is EligibilityState.ELIGIBLE


def test_observed_precedence_satisfies_measured_requirement():
    p = make_profile("a", "1.0.0")
    ev = [make_evidence("a", "1.0.0", "evidence_extraction", "OBSERVED")]
    r = _eval(p, ev, make_role(required_evidence_classes=("MEASURED",)))
    assert r.state is EligibilityState.ELIGIBLE


def test_measured_insufficient_when_observed_required():
    p = make_profile("a", "1.0.0")
    ev = [make_evidence("a", "1.0.0", "evidence_extraction", "MEASURED")]
    r = _eval(p, ev, make_role(required_evidence_classes=("OBSERVED",)))
    assert r.state is EligibilityState.INELIGIBLE
    assert EliminationReason.CAPABILITY_EVIDENCE_INSUFFICIENT.value in r.elimination_reasons


def test_expired_evidence_fails_closed():
    p = make_profile("a", "1.0.0")
    ev = [make_evidence("a", "1.0.0", "evidence_extraction", "MEASURED", valid_until=500_000.0)]
    r = _eval(p, ev, make_role(required_evidence_classes=("MEASURED",)))
    assert r.state is EligibilityState.INELIGIBLE
    assert EliminationReason.CAPABILITY_EVIDENCE_EXPIRED.value in r.elimination_reasons


def test_wrong_agent_version_evidence_does_not_satisfy():
    # I8: evidence for one agent version never satisfies another version.
    p_old = make_profile("a", "1.0.0")   # the version the evidence belongs to
    p_new = make_profile("a", "2.0.0")   # the version under evaluation
    ev = [make_evidence("a", "1.0.0", "evidence_extraction", "MEASURED")]
    snap = make_snapshot([p_old, p_new], ev)
    r = evaluate_agent_eligibility(make_role(required_evidence_classes=("MEASURED",)),
                                   p_new, snap, enterprise(), eligibility(), NOW)
    assert r.state is EligibilityState.INELIGIBLE
    assert EliminationReason.CAPABILITY_EVIDENCE_VERSION_MISMATCH.value in r.elimination_reasons


def test_unknown_evidence_fails_closed():
    p = make_profile("a", "1.0.0")  # claims capability, but NO evidence at all
    r = _eval(p, [], make_role(required_evidence_classes=("MEASURED",)))
    assert r.state is EligibilityState.INELIGIBLE
    assert (EliminationReason.DECLARED_ONLY_WHEN_MEASURED_REQUIRED.value in r.elimination_reasons
            or EliminationReason.UNKNOWN_REQUIRED_EVIDENCE.value in r.elimination_reasons)


def test_injected_time_controls_expiry_deterministically():
    from ugence_agent_workforce_composer.agents import CapabilityEvidenceSet
    e = make_evidence("a", "1.0.0", "evidence_extraction", "MEASURED", valid_until=1_500_000.0)
    assert e.is_expired(2_000_000.0) is True
    assert e.is_expired(1_000_000.0) is False
    s = CapabilityEvidenceSet(items=(e,))
    assert s.best_class("a", "1.0.0", "evidence_extraction", 1_000_000.0) is EvidenceClass.MEASURED
    assert s.best_class("a", "1.0.0", "evidence_extraction", 2_000_000.0) is None
