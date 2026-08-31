"""Happy-path properties: what a well-formed candidate *is*, and what it still is not.

Twelve distinct properties. Every one runs against the genuine chain built in
``conftest.py`` — a real Phase-3 recommendation, a real Phase 4C projection, a real Risk
Authority decision and a real Ed25519 producer signature.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from conftest import build_candidate, build_projection
from ugence_cloud_scaling_authorization_contracts import (
    AUTHORIZATION_CANDIDATE_SCHEMA_VERSION,
    DOMAIN_CLOUD_SCALING,
    PHASE_5A_TRUST_STATE,
    PURPOSE_CAPACITY_ACTION,
    SUBJECT_TYPE_CAPACITY_SUBJECT,
    CapacityAuthorizationCandidate,
    EvidenceTrustState,
    ExecutionTargetScope,
    PolicyTargetBindingReference,
    ProducerAttestationEvidence,
    is_canonical_digest,
    reconcile_phase4,
)


def test_builds_an_exact_candidate_from_a_genuine_chain(candidate):
    """H-1: the production entry point returns an exact CapacityAuthorizationCandidate."""

    assert type(candidate) is CapacityAuthorizationCandidate
    assert candidate.schema_version == AUTHORIZATION_CANDIDATE_SCHEMA_VERSION


def test_candidate_digest_is_canonical_and_self_consistent(candidate):
    """H-2: the carried digest is canonical and equals a fresh recomputation."""

    assert is_canonical_digest(candidate.candidate_digest)
    assert candidate.digest() == candidate.candidate_digest


def test_candidate_is_deterministic(candidate):
    """H-3: the same inputs always produce the same candidate digest."""

    again = build_candidate()
    assert again.candidate_digest == candidate.candidate_digest


def test_phase4_digests_are_carried_unchanged(candidate, projection):
    """H-4: every Phase 4 digest survives into the candidate byte-identically."""

    assert candidate.recommendation_digest == projection.recommendation_digest
    assert candidate.context_digest == projection.context_digest
    assert candidate.subject_digest == projection.subject_digest
    assert candidate.request_digest == projection.request_digest
    assert candidate.idempotency_key == projection.idempotency_key


def test_d4_identifiers_are_the_ratified_values(candidate):
    """H-5: the D-4 identifiers are module-owned and exactly the Phase 4C values."""

    assert candidate.purpose == PURPOSE_CAPACITY_ACTION == "cloud_scaling.capacity_action"
    assert candidate.domain == DOMAIN_CLOUD_SCALING == "cloud_scaling"
    assert candidate.subject_type == SUBJECT_TYPE_CAPACITY_SUBJECT
    # Not caller-controlled: no constructor parameter of the builder names any of them.
    import inspect

    from ugence_cloud_scaling_authorization_contracts import (
        build_capacity_authorization_candidate,
    )

    params = set(inspect.signature(build_capacity_authorization_candidate).parameters)
    assert not params & {"purpose", "domain", "subject_type", "action_type"}


def test_action_parameters_are_exact(candidate, projection):
    """H-6: the action type and magnitudes are the projection's, not the caller's."""

    assert candidate.action_type == projection.context.action_type
    assert candidate.magnitude_before == projection.context.magnitude_before
    assert candidate.magnitude_after == projection.context.magnitude_after
    assert candidate.requested_delta == abs(
        projection.context.magnitude_after - projection.context.magnitude_before
    )


def test_decision_binding_is_carried_and_revalidated(candidate, decision):
    """H-7: the decision digest is recomputed from the snapshot and matches."""

    assert candidate.decision_digest == decision.decision_digest
    assert candidate.decision_snapshot_digest == decision.decision_digest
    assert candidate.decision_id == decision.decision_snapshot["decision_id"]
    assert candidate.disposition == decision.disposition.value


def test_evidence_references_are_bound(candidate, projection):
    """H-8: the evidence references and the evidence-snapshot digest are both bound."""

    assert candidate.evidence_references == projection.evidence_references
    assert candidate.evidence_references
    assert is_canonical_digest(candidate.evidence_snapshot_digest)


def test_target_and_policy_bindings_are_exact_types(candidate):
    """H-9: the Phase 5 bindings are carried as exact types with matching digests."""

    assert type(candidate.target_scope) is ExecutionTargetScope
    assert type(candidate.policy_binding) is PolicyTargetBindingReference
    assert type(candidate.producer_attestation) is ProducerAttestationEvidence
    assert candidate.target_scope_digest == candidate.target_scope.digest()
    assert candidate.policy_binding_digest == candidate.policy_binding.digest()
    assert candidate.policy_binding.target_scope_digest == candidate.target_scope_digest


def test_account_binding_is_present(candidate):
    """H-10: the candidate is account-bound — new Phase 5 vocabulary, not Phase 4's."""

    assert candidate.target_scope.account_id
    # The frozen Phase 4 subject has no account concept at all; this is the proof that
    # the account binding is genuinely new here rather than copied from upstream.
    from ugence_cloud_scaling_controller.canonical.identity import CapacitySubject

    assert "account_id" not in CapacitySubject.__dataclass_fields__


def test_both_evidence_states_are_the_single_unverified_state(candidate):
    """H-11: producer and policy evidence both report PRESENT_BUT_NOT_TRUST_VERIFIED."""

    assert candidate.producer_attestation.trust_state is PHASE_5A_TRUST_STATE
    assert candidate.policy_binding.trust_state is PHASE_5A_TRUST_STATE
    assert candidate.trust_state is PHASE_5A_TRUST_STATE
    assert PHASE_5A_TRUST_STATE.value == "PRESENT_BUT_NOT_TRUST_VERIFIED"
    # There is exactly one state in the vocabulary; there is no verified state to reach.
    assert len(list(EvidenceTrustState)) == 1


def test_validity_timestamps_are_carried_as_facts_only(candidate):
    """H-12: Phase 4 timestamps are carried, named as facts, and never evaluated."""

    for name in (
        "subject_valid_from_fact",
        "subject_valid_until_fact",
        "subject_asserted_at_fact",
        "decision_evaluated_at_fact",
        "decision_expires_at_fact",
        "attestation_issued_at_fact",
    ):
        value = getattr(candidate, name)
        assert isinstance(value, datetime) and value.tzinfo is not None
    # No field claims current validity, and none is named as though it did.
    fields = set(CapacityAuthorizationCandidate.__dataclass_fields__)
    assert not {"is_valid", "valid_now", "is_fresh", "expired", "current"} & fields


def test_reconciliation_returns_validated_values(projection, decision):
    """H-13: reconcile_phase4 returns a plain validated-facts record, not a live view."""

    facts = reconcile_phase4(projection, decision)
    assert facts.tenant_id == projection.tenant_id
    assert facts.request_digest == projection.request_digest
    assert facts.decision_digest == decision.decision_digest
    # The record holds primitives only — no reference back to a source object that a
    # second read could divert.
    for value in vars(facts).values():
        assert not isinstance(value, (type(projection), type(decision)))


def test_candidate_never_reports_authority(candidate):
    """H-14: the derived answer to "does this grant anything" is an unconditional no."""

    assert candidate.grants_authority is False
    canonical = candidate.to_canonical_dict()
    assert "grants_authority" not in canonical  # derived, never canonical
