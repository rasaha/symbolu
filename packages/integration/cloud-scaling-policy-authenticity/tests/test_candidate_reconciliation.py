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
    T_CANDIDATE,
    T_MID,
    PolicyScope,
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


def _verify(candidate=None, authority=None, record=None, as_of=None):
    """Verify at an instant the candidate is actually valid at, when one is supplied.

    ``T_CANDIDATE`` rather than ``T_MID`` whenever a candidate is present (5B-2, gate 13).
    The fixture candidate's recommendation expires 00:08:10 on 2026-01-01 and ``T_MID`` is
    five months later, so every candidate-bearing case here used to assert ``VERIFIED`` on a
    pair that was stale by more than the recommendation's entire lifetime. Nothing objected,
    which is the residual R-2 names, measured by this suite's own fixtures.
    """

    if authority is None or record is None:
        authority, record = issued()
    if as_of is None:
        as_of = T_CANDIDATE if candidate is not None else T_MID
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=as_of,
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
        # The tenant must ride along: the fixture policy is GLOBAL with the empty tenant, so
        # claiming TENANT scope while keeping that empty tenant is a pairing Phase 5A's
        # builder now refuses outright (R-9). Naming this candidate's own tenant keeps the
        # candidate constructible so that *this* gate is the one measured; policy_scope is
        # still the reported field, being earlier in the compared order.
        ({"policy_scope": "TENANT", "policy_tenant_id": "tenant-1"}, "policy_scope"),
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


# ======================================================================================
# R-9, closed: a TENANT-scoped policy bounds only its own tenant's action (gate 12, 5B-2)
#
# The rule is not invented here. ``uvi-policy-contracts`` already refuses cross-tenant policy
# binding at ``contracts/context.py:118`` and ``:223``, ratified, keyed on the scope. 5B-2
# carries it into the two places that held both tenants and did not compare them: Phase 5A's
# builder, and this boundary.
#
# The two enforce the same rule and neither is redundant. Phase 5A refuses to *build* such a
# candidate; this gate refuses one that arrived anyway. A candidate is shape- and
# digest-validated by its type but carries no cross-field policy guard there, so an internally
# consistent cross-tenant candidate can exist without the builder ever having produced one —
# which is exactly what ``_forged_cross_tenant_candidate`` below constructs.
# ======================================================================================


def _forged_cross_tenant_candidate(record):
    """A genuine-shaped candidate Phase 5A's builder would refuse to produce.

    Every field is internally consistent and ``candidate_digest`` genuinely covers the payload,
    so nothing earlier than gate 12 has grounds to refuse it. What makes it forged is only that
    its action belongs to one tenant while its coordinate faithfully describes another tenant's
    ``TENANT``-scoped policy — the pairing the builder now rejects at construction.
    """

    import dataclasses

    from ugence_cloud_scaling_authorization_contracts import (
        CapacityAuthorizationCandidate,
        canonical_digest,
    )

    honest = genuine_candidate()
    coordinate = _coordinate_matching(record, honest)

    forged = object.__new__(CapacityAuthorizationCandidate)
    for field in dataclasses.fields(honest):
        object.__setattr__(forged, field.name, getattr(honest, field.name))
    object.__setattr__(forged, "policy_coordinate_binding", coordinate)
    object.__setattr__(forged, "candidate_digest", canonical_digest(forged.digest_payload()))
    return forged


def _coordinate_matching(record, honest):
    """The coordinate that record was genuinely issued under, bound to the honest scope."""

    builders = phase5a_builders()
    return builders.build_policy_coordinate_binding(
        target_scope_digest=honest.policy_coordinate_binding.target_scope_digest,
        policy_family=record.coordinate.policy_family,
        policy_id=record.coordinate.policy_id,
        policy_version=record.coordinate.version,
        policy_scope=record.coordinate.scope,
        policy_tenant_id=record.coordinate.tenant_id,
        policy_body_digest=record.policy_body_digest,
        issuing_authority_id=record.issuing_authority_id,
        key_id=record.key_id,
        signature_alg=record.signature_alg,
    )


@pytest.mark.adversarial
def test_another_tenants_policy_no_longer_bounds_this_action():
    """**R-9, closed.** The property that measured the residual, inverted.

    Before 5B-2 this pair verified: gate 11 compares the candidate's coordinate against the
    *resolved* policy, and a tenant-B coordinate for a tenant-B policy matches exactly — even
    when the action described belongs to tenant A. Gate 12 is the comparison nothing made.
    """

    authority, record = issued(scope=PolicyScope.TENANT, tenant_id="tenant-elsewhere")
    candidate = _forged_cross_tenant_candidate(record)

    assert record.coordinate.scope == "TENANT"
    assert candidate.tenant_id != record.coordinate.tenant_id, (
        "the fixture must describe an action for a different tenant than the policy's, or "
        "this property measures nothing"
    )

    result = _verify(candidate=candidate, authority=authority, record=record)
    assert result.outcome is O.CANDIDATE_CROSS_TENANT_POLICY
    assert result.verified_policy is None
    assert "tenant-elsewhere" in result.refusal.detail


@pytest.mark.adversarial
def test_the_refusal_is_not_the_coordinate_mismatch_wearing_another_name():
    """Gate 11 and gate 12 answer different questions, and the outcomes must not blur.

    Here the two artifacts agree perfectly about *which* policy is in play. Reporting that as
    ``CANDIDATE_COORDINATE_MISMATCH`` would tell a reader to go looking for a disagreement
    that is not there.
    """

    authority, record = issued(scope=PolicyScope.TENANT, tenant_id="tenant-elsewhere")
    candidate = _forged_cross_tenant_candidate(record)
    binding = candidate.policy_coordinate_binding

    assert binding.policy_id == record.coordinate.policy_id
    assert binding.policy_version == record.coordinate.version
    assert binding.policy_tenant_id == record.coordinate.tenant_id

    result = _verify(candidate=candidate, authority=authority, record=record)
    assert result.outcome is not O.CANDIDATE_COORDINATE_MISMATCH
    assert result.outcome is O.CANDIDATE_CROSS_TENANT_POLICY


@pytest.mark.happy
def test_a_globally_scoped_policy_still_bounds_any_tenants_action():
    """The carve-out, and the reason the guard reads the scope rather than the tenant.

    A ``GLOBAL`` policy carries the empty tenant. A bare equality would refuse every global
    policy in the platform — which is the whole of what the original R-9 framing worried
    about, and why that framing read as an edge case rather than the hole it was.
    """

    authority, record = issued()
    assert record.coordinate.scope == "GLOBAL"
    assert record.coordinate.tenant_id == ""

    candidate = genuine_candidate(record)
    assert candidate.tenant_id not in ("", record.coordinate.tenant_id)

    result = _verify(candidate=candidate, authority=authority, record=record)
    assert result.outcome is O.VERIFIED
    assert result.verified_policy.candidate_digest_fact == candidate.candidate_digest


@pytest.mark.happy
def test_a_tenant_scoped_policy_bounds_its_own_tenants_action():
    """The guard refuses a mismatch, not the ``TENANT`` scope itself."""

    builders = phase5a_builders()
    own_tenant = builders.build_target_scope(builders.build_projection()).tenant_id
    authority, record = issued(scope=PolicyScope.TENANT, tenant_id=own_tenant)

    candidate = genuine_candidate(record)
    assert candidate.tenant_id == record.coordinate.tenant_id

    result = _verify(candidate=candidate, authority=authority, record=record)
    assert result.outcome is O.VERIFIED
