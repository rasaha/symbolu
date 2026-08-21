"""Gate 11: the candidate this determination accompanies is about **this** policy (5B-1).

This module replaces ``test_candidate_not_bound.py``, which measured the opposite and was
right to: until Phase 5A 0.2.0 a candidate could not name a policy version, so one genuine
policy proof verified alongside any candidate whatsoever — including one whose policy binding
named a different policy entirely. That was ADR residual **R-4**, and it is what closes here.

What closing it means, stated precisely
----------------------------------------
A supplied candidate's ``policy_coordinate_binding`` is compared against the resolved policy on
all six coordinate components, on the signed body digest, and on the issuing identity. Any
disagreement is ``CANDIDATE_COORDINATE_MISMATCH`` — a refusal, not a flag, because the two
artifacts are handed to a consumer together and a proof about policy A beside a candidate about
policy B is a misstatement however genuine each half is on its own.

``candidate_digest_fact`` therefore moved into the artifact's **verified** half, which moved
the artifact digest and the verification profile version with it.

What it still does not mean
----------------------------
Reconciled is not authorized, and it is not "the candidate is about the right recommendation":
5B-0A's A-59 residual is untouched here — a producer attestation binds the recommendation, not
the candidate. Nor does it establish that the bounds the candidate carries are the bounds the
policy states; extracting those from the verified body is 5B-2's work.

These tests skip outside a checkout, where the Phase 5A test tree that builds a genuine
candidate is unavailable.
"""

from __future__ import annotations

import pytest

from _policy_fixtures import (
    T_MID,
    genuine_candidate,
    issued,
    phase5a_builders,
    verifier_for,
)
from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome as O

pytestmark = pytest.mark.skipif(
    phase5a_builders() is None,
    reason="the Phase 5A test tree is unavailable outside a source checkout",
)


def _verify(candidate=None, authority=None, record=None):
    if authority is None or record is None:
        authority, record = issued()
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
        candidate=candidate,
    )


def _agreeing():
    """An authority, its issued record, and a candidate whose coordinate names that policy."""

    authority, record = issued()
    return authority, record, genuine_candidate(record)


# ======================================================================================
# The candidate stays optional — and absence is not a silent pass
# ======================================================================================


@pytest.mark.happy
def test_a_candidate_is_optional_and_its_absence_is_not_a_refusal():
    result = _verify(candidate=None)
    assert result.outcome is O.VERIFIED
    assert result.verified_policy.candidate_digest_fact is None


@pytest.mark.invariant
def test_an_absent_candidate_leaves_the_fact_none_rather_than_unverified():
    """The one nuance of the promotion: ``None`` means "no candidate", never "unchecked"."""

    verified = _verify(candidate=None).verified_policy
    assert verified.verified_fact("candidate_digest_fact") is None
    with pytest.raises(Exception):
        verified.recorded_fact("candidate_digest_fact")


# ======================================================================================
# The reconciliation itself
# ======================================================================================


@pytest.mark.happy
def test_a_candidate_naming_this_policy_reconciles_and_is_bound():
    authority, record, candidate = _agreeing()
    result = _verify(candidate=candidate, authority=authority, record=record)
    assert result.outcome is O.VERIFIED
    verified = result.verified_policy
    assert verified.candidate_digest_fact == candidate.candidate_digest

    binding = candidate.policy_coordinate_binding
    assert binding.policy_id == verified.policy_id
    assert binding.policy_family == verified.policy_family
    assert binding.policy_version == verified.policy_version
    assert binding.policy_body_digest == verified.policy_body_digest
    assert binding.policy_tenant_id == verified.policy_tenant_id
    assert binding.policy_scope == verified.policy_scope


@pytest.mark.adversarial
def test_a_candidate_naming_a_different_policy_is_refused():
    """The residual, inverted. This is the property that used to assert VERIFIED."""

    authority, record = issued()
    other = genuine_candidate(
        record, policy_id="something.else-entirely", policy_version="99.0.0"
    )
    result = _verify(candidate=other, authority=authority, record=record)
    assert result.outcome is O.CANDIDATE_COORDINATE_MISMATCH
    assert result.verified_policy is None
    assert "policy_id" in result.refusal.detail


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "override,reported",
    [
        ({"policy_family": "OTHER_FAMILY"}, "policy_family"),
        ({"policy_id": "other-policy"}, "policy_id"),
        ({"policy_version": "9.9.9"}, "policy_version"),
        ({"policy_scope": "TENANT"}, "policy_scope"),
        ({"policy_tenant_id": "tenant-elsewhere"}, "policy_tenant_id"),
        # A substituted body digest surfaces as ``policy_content_digest``: Phase 5A's V2 type
        # refuses a coordinate whose content and body digests differ (the R-3 equality), so a
        # candidate carrying one substituted body digest carries both, and the earlier field
        # in the compared order is the one reported.
        ({"policy_body_digest": "d" * 64}, "policy_content_digest"),
        ({"issuing_authority_id": "attacker.example"}, "issuing_authority_id"),
        ({"key_id": "attacker-key-1"}, "key_id"),
    ],
)
def test_every_reconciled_field_is_load_bearing(override, reported):
    """One field at a time: each disagreement on its own is enough to refuse.

    A reconciliation that compared a subset would read as a binding while establishing less
    than one, so each member of the compared set is measured rather than assumed.
    """

    authority, record = issued()
    candidate = genuine_candidate(record, **override)
    result = _verify(candidate=candidate, authority=authority, record=record)
    assert result.outcome is O.CANDIDATE_COORDINATE_MISMATCH
    assert result.verified_policy is None
    assert reported in result.refusal.detail


@pytest.mark.adversarial
def test_a_refused_pair_mints_no_artifact_at_all():
    """There is no third state: no artifact carrying an unreconciled candidate exists."""

    authority, record = issued()
    other = genuine_candidate(record, policy_id="something.else-entirely")
    result = _verify(candidate=other, authority=authority, record=record)
    assert result.verified_policy is None
    assert result.verified is False
    assert result.outcome is not O.VERIFIED


# ======================================================================================
# What reconciliation does not change
# ======================================================================================


@pytest.mark.adversarial
def test_the_candidate_digest_stays_in_its_own_namespace_and_is_never_converted():
    """D-5B0B-2 and D-5B1-4: reconciled, still not re-encoded."""

    from ugence_cloud_scaling_policy_authenticity import is_phase5a_digest, is_policy_digest

    _authority, _record, candidate = _agreeing()
    verified = _verify(
        candidate=candidate, authority=_authority, record=_record
    ).verified_policy
    assert is_phase5a_digest(verified.candidate_digest_fact)
    assert not is_policy_digest(verified.candidate_digest_fact)
    assert is_policy_digest(verified.policy_body_digest)
    assert not is_phase5a_digest(verified.policy_body_digest)
    # The candidate carries the authority's digest bare, and this package compares it bare.
    assert candidate.policy_coordinate_binding.policy_body_digest == (
        verified.policy_body_digest
    )


@pytest.mark.adversarial
def test_two_determinations_differing_only_in_candidate_are_two_determinations():
    """The candidate is not signature-covered, but it IS artifact-digest covered."""

    authority, record, candidate = _agreeing()
    with_candidate = _verify(
        candidate=candidate, authority=authority, record=record
    ).verified_policy
    without = _verify(candidate=None, authority=authority, record=record).verified_policy
    assert with_candidate.candidate_digest_fact != without.candidate_digest_fact
    assert with_candidate.artifact_digest != without.artifact_digest
    assert with_candidate.policy_body_digest == without.policy_body_digest


@pytest.mark.invariant
def test_a_reconciled_determination_still_grants_nothing():
    """Reconciled is not authorized. The whole phase adds a binding, not a permission."""

    authority, record, candidate = _agreeing()
    verified = _verify(
        candidate=candidate, authority=authority, record=record
    ).verified_policy
    assert verified.grants_authority is False
    assert verified.historical is False
    assert verified.outcome is O.VERIFIED
