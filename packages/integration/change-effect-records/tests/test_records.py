"""The thirteen record shapes: what each one requires, and what each one refuses."""

from __future__ import annotations

import dataclasses

import pytest
from _fixtures import CHAIN, OBLIGATION, bundle, classification, d, obligation

from ugence_change_effect_records import (
    RECORD_TYPES,
    AdmissionClaimRecord,
    AdmissionCompletionRecord,
    AdmissionReservationRecord,
    AdmissionResolutionRecord,
    AdmissionState,
    AuthorizationBinding,
    ClaimKind,
    ClosureOutcome,
    CompletionAbsence,
    ConfirmationAmendment,
    ContractViolation,
    EffectClass,
    EvaluationStatus,
    FinalResolutionRecord,
    InvestigationClosureRecord,
    InvestigationExtensionRecord,
    InvestigationRecord,
    JurisdictionalRoute,
    RegistryEffectResult,
    RemediationRequirement,
    ResolutionRevocationRecord,
    RevocationImpactRecord,
    RevocationOrdering,
)


def test_there_are_thirteen_record_types_and_every_one_is_frozen():
    assert len(RECORD_TYPES) == 13
    for cls in RECORD_TYPES:
        assert dataclasses.is_dataclass(cls) and cls.__dataclass_params__.frozen, cls.__name__


def test_a_record_cannot_be_mutated_after_construction():
    record = classification()
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.signer = "someone-else"  # type: ignore[misc]


# ------------------------------------------------------------------ classification
def test_an_effect_class_is_set_only_when_measured():
    with pytest.raises(ContractViolation):
        RegistryEffectResult(registry="r", evaluation_status=EvaluationStatus.MEASURED)
    with pytest.raises(ContractViolation):
        RegistryEffectResult(registry="r", evaluation_status=EvaluationStatus.NO_EFFECT,
                             effect_class=EffectClass.AUTHORITY)


def test_an_unevaluated_registry_must_name_the_obligation_recording_why():
    with pytest.raises(ContractViolation):
        RegistryEffectResult(registry="r", evaluation_status=EvaluationStatus.UNEVALUATED)
    assert RegistryEffectResult(
        registry="r", evaluation_status=EvaluationStatus.UNEVALUATED,
        blocking_obligation_id=OBLIGATION).blocking_obligation_id == OBLIGATION


def test_a_classification_carries_no_confirmation_field():
    """The confirmation is produced after the freeze and lives in the amendment."""

    fields = {f.name for f in dataclasses.fields(classification())}
    assert not [f for f in fields if "confirmation" in f]


def test_provisional_is_an_enumerated_string_not_a_boolean():
    with pytest.raises(ContractViolation):
        classification(provisional="yes")
    assert classification(provisional="true").provisional == "true"


def test_an_obligation_identifier_appears_at_most_once():
    with pytest.raises(ContractViolation):
        classification(blocking_obligations=(obligation(), obligation()))


# -------------------------------------------------------------------- investigation
def _opening(**kw) -> InvestigationRecord:
    args = dict(chain_id=CHAIN, obligation_id=OBLIGATION,
                introducing_role="CLASSIFICATION", introducing_digest=d("cls"),
                candidate_digest=d("cand"), anomaly_family="family-7",
                named_evaluation="larger sample", owner_identity="owner-1",
                deadline="2026-10-01T00:00:00.000000+00:00")
    args.update(kw)
    return InvestigationRecord(**args)


def test_an_opening_pins_exactly_one_introducing_role():
    assert _opening().introducing_role == "CLASSIFICATION"
    assert _opening(introducing_role="CONFIRMATION_AMENDMENT")
    with pytest.raises(ContractViolation):
        _opening(introducing_role="BOTH")


def test_an_opening_carries_no_state_and_no_closing_disposition():
    fields = {f.name for f in dataclasses.fields(_opening())}
    assert "state" not in fields and "outcome" not in fields


def test_a_completed_closure_carries_a_bundle_and_a_terminating_one_does_not():
    closure = InvestigationClosureRecord(
        chain_id=CHAIN, obligation_id=OBLIGATION, opening_digest=d("open"),
        outcome=ClosureOutcome.COMPLETED, bundle=bundle(), signer="owner-1")
    assert closure.bundle is not None
    with pytest.raises(ContractViolation):
        InvestigationClosureRecord(
            chain_id=CHAIN, obligation_id=OBLIGATION, opening_digest=d("open"),
            outcome=ClosureOutcome.COMPLETED, signer="owner-1")
    with pytest.raises(ContractViolation):
        InvestigationClosureRecord(
            chain_id=CHAIN, obligation_id=OBLIGATION, opening_digest=d("open"),
            outcome=ClosureOutcome.EXPIRED, bundle=bundle(), signer="owner-1")


def test_a_closure_s_bundle_must_answer_the_closure_s_own_obligation():
    other = bundle(obligation_id=d("other-obligation"))
    with pytest.raises(ContractViolation):
        InvestigationClosureRecord(
            chain_id=CHAIN, obligation_id=OBLIGATION, opening_digest=d("open"),
            outcome=ClosureOutcome.COMPLETED, bundle=other, signer="owner-1")


def test_a_bundle_carries_at_least_one_primitive_and_no_repeated_target():
    with pytest.raises(ContractViolation):
        bundle(effects=())
    with pytest.raises(ContractViolation):
        bundle(declared_write_set=("t", "t"))


def test_an_extension_pins_its_opening():
    ext = InvestigationExtensionRecord(
        chain_id=CHAIN, opening_digest=d("open"),
        extended_deadline="2026-11-01T00:00:00.000000+00:00", owner_identity="owner-1")
    assert ext.opening_digest == d("open")


# ----------------------------------------------------------------- final resolution
def _resolution(**kw) -> FinalResolutionRecord:
    args = dict(chain_id=CHAIN, classification_digest=d("cls"), amendment_digest=d("amd"),
                closure_digests=(d("clo"),), jurisdictional_route=JurisdictionalRoute.GERL_BASE,
                routing_rule="R6", signer="classifier")
    args.update(kw)
    return FinalResolutionRecord(**args)


def test_a_final_resolution_exists_only_with_an_empty_effective_set():
    assert _resolution().effective_set_empty == "true"
    with pytest.raises(ContractViolation):
        _resolution(effective_set_empty="false")


def test_an_authorization_pins_the_final_resolution_not_the_classification():
    binding = AuthorizationBinding(
        chain_id=CHAIN, final_resolution_digest=d("res"), authorization_digest=d("auth"),
        issuing_authority="m6", validity_window="2026-09-13/2026-09-20")
    fields = {f.name for f in dataclasses.fields(binding)}
    assert "final_resolution_digest" in fields and "classification_digest" not in fields


# ---------------------------------------------------------- revocation and impact
def _revocation(**kw) -> ResolutionRevocationRecord:
    args = dict(chain_id=CHAIN, final_resolution_digest=d("res"), basis="later evidence",
                ordering=RevocationOrdering.APPLY_THEN_REVOKE, control_version_at_revocation=2,
                signer="route-issuing-authority", signer_authority="m6")
    args.update(kw)
    return ResolutionRevocationRecord(**args)


def test_a_revocation_carries_no_exposure_window():
    """At the instant it is sealed the window may not exist yet (rule section 8a)."""

    fields = {f.name for f in dataclasses.fields(_revocation())}
    assert not [f for f in fields if "exposure" in f or "receipt" in f]


def _impact(**kw) -> RevocationImpactRecord:
    args = dict(chain_id=CHAIN, revocation_digest=d("rev"), applied="true",
                ordering=RevocationOrdering.APPLY_THEN_REVOKE,
                remediation=RemediationRequirement.STATE_REPAIR_REQUIRED,
                exposure_presumed="false", completion_digest=d("comp"), signer="gov")
    args.update(kw)
    return RevocationImpactRecord(**args)


def test_an_impact_pins_a_completion_or_states_its_structural_absence_never_both():
    assert _impact().completion_digest == d("comp")
    assert _impact(completion_digest=None, applied="false",
                   remediation=RemediationRequirement.NONE,
                   completion_absence=CompletionAbsence.NO_APPLY_CLAIM)
    with pytest.raises(ContractViolation):
        _impact(completion_absence=CompletionAbsence.NO_APPLY_CLAIM)
    with pytest.raises(ContractViolation):
        _impact(completion_digest=None)


def test_absence_is_admissible_only_where_nothing_could_have_been_applied():
    with pytest.raises(ContractViolation):
        _impact(completion_digest=None, completion_absence=CompletionAbsence.NO_APPLY_CLAIM,
                applied="true")


def test_owner_decision_6b_a_revoked_applied_delta_always_requires_state_repair():
    with pytest.raises(ContractViolation):
        _impact(applied="true", remediation=RemediationRequirement.NONE)
    assert _impact(remediation=RemediationRequirement.STATE_REPAIR_REQUIRED)
    assert _impact(
        exposure_presumed="true",
        remediation=RemediationRequirement.STATE_REPAIR_AND_EXPOSURE_REMEDIATION_REQUIRED)


def test_no_remediation_arises_where_nothing_was_applied():
    with pytest.raises(ContractViolation):
        _impact(applied="false", completion_digest=d("c"),
                remediation=RemediationRequirement.STATE_REPAIR_REQUIRED)


# ----------------------------------------------------------------------- admission
def _reservation(**kw) -> AdmissionReservationRecord:
    args = dict(chain_id=CHAIN, final_resolution_digest=d("res"),
                authorization_digest=d("auth"), classification_digest=d("cls"),
                amendment_digest=d("amd"), pre_state_digest=d("pre"), delta_digest=d("delta"),
                idempotency_key="k-1", head_version=3, control_version=0, tenant="tenant-1",
                expected_target_versions=(("mem.x", 0),), signer="admission-boundary")
    args.update(kw)
    return AdmissionReservationRecord(**args)


def test_a_reservation_binds_the_target_set_and_its_expected_versions():
    assert _reservation().expected_target_versions == (("mem.x", 0),)
    with pytest.raises(ContractViolation):
        _reservation(expected_target_versions=())
    with pytest.raises(ContractViolation):
        _reservation(expected_target_versions=(("mem.x", 0), ("mem.x", 1)))


def test_a_reservation_is_reserved_and_nothing_else():
    with pytest.raises(ContractViolation):
        _reservation(state=AdmissionState.APPLIED)


def test_an_apply_claim_restates_the_reserved_target_versions():
    apply = AdmissionClaimRecord(
        chain_id=CHAIN, reservation_digest=d("resv"), claim_kind=ClaimKind.APPLY,
        expected_control_version=0, expected_target_versions=(("mem.x", 0),), signer="executor")
    assert apply.expected_target_versions
    with pytest.raises(ContractViolation):
        AdmissionClaimRecord(chain_id=CHAIN, reservation_digest=d("resv"),
                             claim_kind=ClaimKind.APPLY, expected_control_version=0,
                             signer="executor")


def test_a_cancel_claim_needs_no_target_versions_because_it_writes_nothing():
    cancel = AdmissionClaimRecord(
        chain_id=CHAIN, reservation_digest=d("resv"), claim_kind=ClaimKind.CANCEL,
        expected_control_version=0, signer="route-issuing-authority")
    assert cancel.expected_target_versions == ()


def test_a_completion_says_whether_the_mutation_happened():
    applied = AdmissionCompletionRecord(
        chain_id=CHAIN, claim_digest=d("claim"), state=AdmissionState.APPLIED,
        post_state_digest=d("post"), signer="executor")
    assert applied.post_state_digest == d("post")
    with pytest.raises(ContractViolation):
        AdmissionCompletionRecord(chain_id=CHAIN, claim_digest=d("claim"),
                                  state=AdmissionState.APPLIED, signer="executor")
    with pytest.raises(ContractViolation):
        AdmissionCompletionRecord(chain_id=CHAIN, claim_digest=d("claim"),
                                  state=AdmissionState.FAILED, signer="executor")
    with pytest.raises(ContractViolation):
        AdmissionCompletionRecord(chain_id=CHAIN, claim_digest=d("claim"),
                                  state=AdmissionState.RESERVED, signer="executor")


def test_a_human_resolution_resolves_to_applied_or_failed_and_overwrites_nothing():
    resolution = AdmissionResolutionRecord(
        chain_id=CHAIN, completion_digest=d("unknown"), resolved_state=AdmissionState.APPLIED,
        evidence="memory inspected", resolving_authority="human-authority")
    assert resolution.completion_digest == d("unknown")
    with pytest.raises(ContractViolation):
        AdmissionResolutionRecord(
            chain_id=CHAIN, completion_digest=d("unknown"),
            resolved_state=AdmissionState.OUTCOME_UNKNOWN, evidence="e",
            resolving_authority="h")


def test_an_amendment_closes_confirmation_and_pins_the_frozen_record():
    amendment = ConfirmationAmendment(
        chain_id=CHAIN, classification_digest=d("cls"), confirmation_seed_digest=d("cseed"),
        confirmation_sample_digest=d("csample"), confirmation_result_digest=d("cresult"),
        closes_obligation_ids=(OBLIGATION,), signer="classifier")
    assert amendment.classification_digest == d("cls")
