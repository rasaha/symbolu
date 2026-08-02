"""Acceptance tests 16-20: TAP assertion-governance integration."""
from __future__ import annotations

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
)
from ugence_code_governance.governance.tap_adapter import TapClaimAdapter


def _prep(service):
    change = service.ingest_change_event(make_payload(), tenant_id="acme",
                                         captured_at=T0, delivery_id="d")
    rid = revision_of(change)
    for ct in LOW_CLAIMS:
        service.record_evidence("acme", rid, make_evidence(change, ct))
    service.build_claim_manifest("acme", rid, risk_tier=RiskTier.LOW,
                                 claim_inputs=claim_inputs_for(change, LOW_CLAIMS), captured_at=T0)
    service.evaluate_claim_requirements("acme", rid, at=T0)
    return change, rid


# 16. claim maps to assertion request by evidence reference
def test_claim_maps_by_evidence_reference(service: CodeGovernanceService):
    change, rid = _prep(service)
    tap = service.evaluate_assertions("acme", rid, at=T0)
    assert len(tap.results) == len(LOW_CLAIMS)
    # every result carries covered evidence refs (by reference, not content)
    for r in tap.results:
        assert r.request_fingerprint
        assert isinstance(r.covered_evidence_refs, tuple)


# 17. TAP result remains per claim
def test_tap_result_per_claim(service: CodeGovernanceService):
    change, rid = _prep(service)
    tap = service.evaluate_assertions("acme", rid, at=T0)
    claim_ids = {r.claim_id for r in tap.results}
    assert len(claim_ids) == len(LOW_CLAIMS)  # one distinct result per claim


# 18. unsupported claim remains unsupported (TAP layer; not promoted to supported)
def test_unsupported_claim_remains_unsupported(service: CodeGovernanceService):
    change = service.ingest_change_event(make_payload(), tenant_id="acme",
                                         captured_at=T0, delivery_id="d")
    rid = revision_of(change)
    for ct in LOW_CLAIMS:
        service.record_evidence("acme", rid, make_evidence(change, ct))
    # All mandatory claims satisfied so the gate proceeds; add an OPTIONAL claim
    # with NO evidence refs -> TAP cannot support it and must NOT promote it.
    inputs = claim_inputs_for(change, LOW_CLAIMS) + (
        ClaimInput(ClaimType.ARTIFACT_SIZE_DELTA, ClaimStatus.INCOMPLETE, ()),
    )
    service.build_claim_manifest("acme", rid, risk_tier=RiskTier.LOW,
                                 claim_inputs=inputs, captured_at=T0)
    service.evaluate_claim_requirements("acme", rid, at=T0)
    tap = service.evaluate_assertions("acme", rid, at=T0)
    optional_result = next(
        r for r in tap.results if r.claim_type == ClaimType.ARTIFACT_SIZE_DELTA.value)
    assert optional_result.coverage in ("UNSUPPORTED", "INDETERMINATE")
    assert not optional_result.is_supported


# 19. evidence coverage is not treated as aggregate authorization
def test_evidence_coverage_is_descriptive_not_authorization(service: CodeGovernanceService):
    change, rid = _prep(service)
    tap = service.evaluate_assertions("acme", rid, at=T0)
    # coverage is a per-claim float in [0,1]; there is no aggregate authorization
    for r in tap.results:
        assert 0.0 <= r.evidence_coverage <= 1.0
    # the workflow never authorizes from coverage — it advances to ASSERTIONS_EVALUATED
    assert service.get_workflow("acme", rid).state.value == "ASSERTIONS_EVALUATED"


# 20. missing TAP result prevents chain completion
def test_missing_tap_result_prevents_chain_completion(service: CodeGovernanceService):
    # If the TAP stage never runs, the chain must fail closed at finalization.
    change, rid = _prep(service)
    # skip evaluate_assertions; force the run's tap fingerprints empty
    run = service._runs[("acme", rid)]
    run.tap_result_fingerprints = ()
    # attempt to finalize a chain directly -> CHAIN_INCOMPLETE (fail closed)
    run.transition(run.state.__class__.ASSERTIONS_EVALUATED, at=T0)
    from ugence_code_governance import AuthorizedActor, DecisionInput, MergeMethod
    service.record_authorized_decision(
        "acme", rid, actor=AuthorizedActor(actor_id="u", authority_id="r",
                                           decision_scope="merge_pull_request"),
        decision=DecisionInput(outcome="APPROVE"), at=T0)
    service.prepare_exact_action("acme", rid, merge_method=MergeMethod.SQUASH, at=T0)
    service.evaluate_action_shadow("acme", rid, at=T0)
    assert service.get_workflow("acme", rid).state.value == "CHAIN_INCOMPLETE"
