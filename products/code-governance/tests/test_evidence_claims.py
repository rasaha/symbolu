"""Acceptance tests 7-15: evidence records and Claim Manifest semantics."""
from __future__ import annotations

import dataclasses

import pytest

from cg_helpers import (
    LOW_CLAIMS,
    T0,
    claim_inputs_for,
    make_evidence,
    make_payload,
    revision_of,
)
from ugence_code_governance import (
    ClaimInput,
    ClaimStatus,
    ClaimType,
    CodeGovernanceService,
    RiskTier,
    ValidatorTrustLevel,
    build_claim_manifest,
    evaluate_claim_requirements,
)
from ugence_code_governance.errors import ContentDigestMismatchError
from ugence_code_governance.policies import DEFAULT_POLICY


def _change(service):
    return service.ingest_change_event(make_payload(), tenant_id="acme",
                                       captured_at=T0, delivery_id="d")


# 7. evidence bound to current head is admitted
def test_current_head_evidence_admitted(service: CodeGovernanceService):
    change = _change(service)
    rid = revision_of(change)
    ev = make_evidence(change, ClaimType.BUILD)
    service.record_evidence("acme", rid, ev)
    assert ev.evidence_id in service.get_workflow("acme", rid).evidence_ids
    assert ev.is_current_for(change.head_sha)


# 8. evidence bound to old head is stale
def test_old_head_evidence_is_stale(service: CodeGovernanceService):
    change = _change(service)
    stale = make_evidence(change, ClaimType.BUILD, head_sha="old-head")
    assert stale.is_stale_for(change.head_sha)
    rid = revision_of(change)
    service.record_evidence("acme", rid, stale)
    # stored but NOT admitted to the current-head run
    assert stale.evidence_id not in service.get_workflow("acme", rid).evidence_ids


# 9. validator identity/version preserved
def test_validator_identity_preserved(service: CodeGovernanceService):
    change = _change(service)
    ev = make_evidence(change, ClaimType.SECURITY, validator_id="semgrep", validator_version="9.9")
    assert ev.validator_id == "semgrep"
    assert ev.validator_version == "9.9"
    manifest = build_claim_manifest(
        change=change, policy=DEFAULT_POLICY, risk_tier=RiskTier.HIGH,
        claim_inputs=(ClaimInput(claim_type=ClaimType.SECURITY,
                                 status=ClaimStatus.SATISFIED, evidence=(ev,)),),
        captured_at=T0)
    entry = manifest.entry_for(ClaimType.SECURITY)
    assert entry.validator_id == "semgrep" and entry.validator_version == "9.9"


# 10. content digest mismatch rejected
def test_content_digest_mismatch_rejected(service: CodeGovernanceService):
    change = _change(service)
    ev = make_evidence(change, ClaimType.BUILD)
    tampered = dataclasses.replace(ev, normalized_payload={"result": "TAMPERED"})
    with pytest.raises(ContentDigestMismatchError):
        tampered.verify_integrity()
    # untampered verifies cleanly
    ev.verify_integrity()


# 11. missing required claim makes manifest incomplete
def test_missing_required_claim_incomplete(service: CodeGovernanceService):
    change = _change(service)
    # LOW requires BUILD, UNIT_TEST, STATIC_ANALYSIS; omit STATIC_ANALYSIS
    inputs = claim_inputs_for(change, (ClaimType.BUILD, ClaimType.UNIT_TEST))
    manifest = build_claim_manifest(change=change, policy=DEFAULT_POLICY,
                                    risk_tier=RiskTier.LOW, claim_inputs=inputs, captured_at=T0)
    ev = evaluate_claim_requirements(manifest, DEFAULT_POLICY.requirements_for(RiskTier.LOW))
    assert not ev.proceed
    assert ClaimType.STATIC_ANALYSIS in ev.missing_required_claims


# 12. failed required claim cannot be compensated for
def test_failed_required_claim_not_compensated(service: CodeGovernanceService):
    change = _change(service)
    inputs = (
        ClaimInput(ClaimType.BUILD, ClaimStatus.FAILED, (make_evidence(change, ClaimType.BUILD),)),
        ClaimInput(ClaimType.UNIT_TEST, ClaimStatus.SATISFIED, (make_evidence(change, ClaimType.UNIT_TEST),)),
        ClaimInput(ClaimType.STATIC_ANALYSIS, ClaimStatus.SATISFIED, (make_evidence(change, ClaimType.STATIC_ANALYSIS),)),
        # pile on optional successes — must not compensate
        ClaimInput(ClaimType.ARTIFACT_SIZE_DELTA, ClaimStatus.SATISFIED, ()),
        ClaimInput(ClaimType.COMPLEXITY_DELTA, ClaimStatus.SATISFIED, ()),
    )
    manifest = build_claim_manifest(change=change, policy=DEFAULT_POLICY,
                                    risk_tier=RiskTier.LOW, claim_inputs=inputs, captured_at=T0)
    ev = evaluate_claim_requirements(manifest, DEFAULT_POLICY.requirements_for(RiskTier.LOW))
    assert not ev.proceed
    assert ClaimType.BUILD in ev.failed_required_claims


# 13. optional failed claim does not automatically become a mandatory block
def test_optional_failed_does_not_block(service: CodeGovernanceService):
    change = _change(service)
    inputs = claim_inputs_for(change, LOW_CLAIMS) + (
        ClaimInput(ClaimType.ARTIFACT_SIZE_DELTA, ClaimStatus.FAILED, ()),
    )
    manifest = build_claim_manifest(change=change, policy=DEFAULT_POLICY,
                                    risk_tier=RiskTier.LOW, claim_inputs=inputs, captured_at=T0)
    ev = evaluate_claim_requirements(manifest, DEFAULT_POLICY.requirements_for(RiskTier.LOW))
    assert ev.proceed  # mandatory all satisfied; optional failure is advisory
    assert ev.optional_claim_summary.get("FAILED") == 1


# 14. claim order does not change fingerprint
def test_claim_order_stable_fingerprint(service: CodeGovernanceService):
    change = _change(service)
    a = claim_inputs_for(change, LOW_CLAIMS)
    b = tuple(reversed(a))
    m1 = build_claim_manifest(change=change, policy=DEFAULT_POLICY, risk_tier=RiskTier.LOW,
                              claim_inputs=a, captured_at=T0)
    m2 = build_claim_manifest(change=change, policy=DEFAULT_POLICY, risk_tier=RiskTier.LOW,
                              claim_inputs=b, captured_at=T0)
    assert m1.fingerprint == m2.fingerprint


# 15. same normalized manifest gives same fingerprint
def test_same_manifest_same_fingerprint(service: CodeGovernanceService):
    change = _change(service)
    inputs = claim_inputs_for(change, LOW_CLAIMS)
    m1 = build_claim_manifest(change=change, policy=DEFAULT_POLICY, risk_tier=RiskTier.LOW,
                              claim_inputs=inputs, captured_at=T0)
    m2 = build_claim_manifest(change=change, policy=DEFAULT_POLICY, risk_tier=RiskTier.LOW,
                              claim_inputs=inputs, captured_at=T0)
    assert m1.fingerprint == m2.fingerprint


def test_untrusted_validator_makes_mandatory_inadmissible(service: CodeGovernanceService):
    change = _change(service)
    inputs = (
        ClaimInput(ClaimType.BUILD, ClaimStatus.SATISFIED,
                   (make_evidence(change, ClaimType.BUILD, trust=ValidatorTrustLevel.UNTRUSTED),),
                   ),
        ClaimInput(ClaimType.UNIT_TEST, ClaimStatus.SATISFIED, (make_evidence(change, ClaimType.UNIT_TEST),)),
        ClaimInput(ClaimType.STATIC_ANALYSIS, ClaimStatus.SATISFIED, (make_evidence(change, ClaimType.STATIC_ANALYSIS),)),
    )
    manifest = build_claim_manifest(change=change, policy=DEFAULT_POLICY,
                                    risk_tier=RiskTier.LOW, claim_inputs=inputs, captured_at=T0)
    ev = evaluate_claim_requirements(manifest, DEFAULT_POLICY.requirements_for(RiskTier.LOW))
    assert not ev.proceed
    assert ClaimType.BUILD in ev.inadmissible_required_claims


def test_high_tier_requires_more_claims(service: CodeGovernanceService):
    change = _change(service)
    # only LOW claims present, HIGH tier -> incomplete
    inputs = claim_inputs_for(change, LOW_CLAIMS)
    manifest = build_claim_manifest(change=change, policy=DEFAULT_POLICY,
                                    risk_tier=RiskTier.HIGH, claim_inputs=inputs, captured_at=T0)
    ev = evaluate_claim_requirements(manifest, DEFAULT_POLICY.requirements_for(RiskTier.HIGH))
    assert not ev.proceed
    assert ClaimType.SECURITY in ev.missing_required_claims
    assert ClaimType.INDEPENDENT_REVIEW in ev.missing_required_claims
