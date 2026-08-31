"""Frozen digests — the artifact digest has a merged definition now, so it stops moving quietly.

Before this package merged, moving a fact between the verified and recorded halves was free:
nothing downstream pinned an artifact digest, so three rounds of remediation reshaped the
payload at ``0.1.0`` without consequence. That window is closed. A verified artifact's digest
is now something a consumer can pin, and 5B-1 and 5B-2 will each want to move one — promoting
``candidate_digest_fact`` when R-4 closes, ``resolved_as_of_fact`` when R-2 does.

**The rule this file enforces.** A change that moves a pinned digest is a change to what this
package's verification profile produces. When one of these constants must be updated, update
:data:`~ugence_cloud_scaling_policy_authenticity.VERIFICATION_PROFILE_VERSION` in the same
commit, and say in the changelog which digest moved and why.

**What this file cannot enforce, corrected (5B-1 D-5B1-3).** These constants are pins. An
earlier version of this docstring claimed the partition fingerprint below made the profile
bump "mechanical rather than remembered"; the 5B-1 audit measured otherwise — promoting
``candidate_digest_fact``, updating the two constants and leaving the profile version at
``"v1"`` passes this file at 5 passed. A pin catches an *accidental* move, because a change
that did not intend to move a digest does not carry an updated pin. It cannot catch a
deliberate one, because the pin and the change land in the same commit. The rule is enforced
by ``tests/test_partition_ratchet.py``, which takes its "before" from repository history.

**What is deliberately not frozen.** Nothing that depends on wall-clock time, machine state or
key generation. Every value below is reproducible from the repository alone: the fixtures sign
with fixed seeds at fixed instants, so a digest that moves here moved because the *contract*
moved. Verified across processes before pinning.
"""

from __future__ import annotations

import pytest

from _policy_fixtures import T_MID, issued, issued_bounds, verifier_for
from ugence_cloud_scaling_policy_authenticity import (
    POLICY_AUTHENTICITY_DIGEST_DOMAIN,
    POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN,
    POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN,
    VERIFICATION_PROFILE,
    VERIFICATION_PROFILE_VERSION,
    framed_digest,
)
from ugence_cloud_scaling_policy_authenticity.verified import (
    RECORDED_FACT_NAMES,
    VERIFIED_FACT_NAMES,
)

#: The digest of the reference determination: the authority's default fixture policy, resolved
#: at ``T_MID`` with no candidate supplied, under the fixture key ring.
FROZEN_ARTIFACT_DIGEST = (
    "15696691cf9bbab56a2cf331509bcb8c2b8d4c19c004e8d31add34311b791c7e"
)
#: The ``v3`` value, before R-8's reconciliation took the profile to ``v4``. No fact moved
#: and no fact was added; the digest moved because the profile version is *inside* the
#: artifact. Pinned from the other side: never produced again.
SUPERSEDED_V3_ARTIFACT_DIGEST = (
    "8ced1a5f7ef2ea2f7c5969d852d2f180f7942909c2745ff907f58c798822a392"
)
#: What the reference determination hashed to under profile ``v1``, before 5B-1 promoted
#: ``candidate_digest_fact`` into the verified half. Pinned as a negative anchor: reproducing
#: it would mean the promotion had been reverted without the profile version following.
SUPERSEDED_V1_ARTIFACT_DIGEST = (
    "8b0ea25f368287715657f1ff2293e137de1f810de7946e4fc27e52d8af473c7f"
)
#: What it hashed to under ``v2``, before 5B-3 promoted ``policy_type`` and added
#: ``capacity_bounds_fact``. A second negative anchor, for the same reason as the first.
SUPERSEDED_V2_ARTIFACT_DIGEST = (
    "f245511d4efeaee342ae6fac65fe323cc187f7f39d0c09a0034bc7d05899335c"
)

#: The identity of the fixture trust configuration. Moves when an anchor's authority, tenant,
#: entitlements, window, revocation state or the adapter set changes — which is the point.
#:
#: **Deliberately unmoved by 5B-3**, and worth stating because the subphase's own ruling
#: predicted otherwise. The promotion changes the *partition*, not the trust configuration:
#: the reference determination still resolves the same UVI fixture policy under the same key
#: ring and the same one registered adapter. The capacity-bounds family is exercised by
#: ``FROZEN_BOUNDS_TRUST_CONFIGURATION_DIGEST`` below, under its own registry. Re-pinning
#: this constant to a value nothing produced would have anchored a fiction.
FROZEN_TRUST_CONFIGURATION_DIGEST = (
    "87e8a90e26944f27b7f87b189332de4a45ea8db78ae2c35f245ace38da46f429"
)

#: The reference **capacity-bounds** determination (5B-3, R-8): the bounds fixture policy,
#: resolved at ``T_MID`` under a registry whose only adapter is the bounds family's.
FROZEN_BOUNDS_ARTIFACT_DIGEST = (
    "496c290c85c20468a4b0ac3a720d9b5fcb44d15c943299a06fadb82a472f8eef"
)
#: The same determination under profile ``v3`` with the selectable bounds already in place.
#: Distinguishes the two moves R-8 made — the fixture body, then the profile version — so
#: neither can be mistaken for the other.
SUPERSEDED_V3_BOUNDS_ARTIFACT_DIGEST = (
    "c145bb7e3e76d8944b24ea64b9f1360942c6375a230429d7360841abb0eeaebd"
)
#: The value this anchor held while the reference bounds body carried one unselectable bound
#: (``action_type="cloud_scaling.scale_out"``, ``resource_class=""``). R-8's gate 16 selects
#: exactly and fail-closed, so that bound could never match a genuine candidate and the
#: fixture could never exercise the gate it existed for. Replacing it moved the body, and so
#: the artifact digest. Pinned from the other side: this determination must never be produced
#: again.
SUPERSEDED_UNSELECTABLE_BOUNDS_ARTIFACT_DIGEST = (
    "218dfd93670b31fa6b56baacfd113ad8b9ac86727675ea75e6b575dd0eb51407"
)
#: That determination's trust configuration — a different adapter set, so a different digest.
#: This is where the adapter-set sensitivity of the digest is actually anchored.
FROZEN_BOUNDS_TRUST_CONFIGURATION_DIGEST = (
    "8bea54d17d9caaaa465917e963a8e579f5c43523a9567c8fd52ec2d84e376c05"
)

#: Covers the profile version together with both halves' exact membership and their domain
#: tags. This is the constant that ties a partition change to a profile bump.
FROZEN_PARTITION_FINGERPRINT = (
    "8f8071298cbc94755865ac9c5baaa367438f6900b6c77a7a87d6b4ebfb26d6a5"
)
#: The ``v3`` fingerprint. **Membership is identical** across this move — R-8 promotes,
#: demotes and adds nothing — so this pair is the measurement showing the fingerprint tracks
#: the profile version as well as the two halves.
SUPERSEDED_V3_PARTITION_FINGERPRINT = (
    "98c66c7ede134d37ff148fb619de5b3bbd8de316977b856d47ef95014addd3aa"
)
#: The ``v1`` fingerprint: four recorded facts, nineteen verified ones.
SUPERSEDED_V1_PARTITION_FINGERPRINT = (
    "86d39d254d0702ccc90df894ee44a8c5b51b4ebfedeaa7ef396e81ef33edda07"
)
#: The ``v2`` fingerprint: three recorded facts, twenty verified ones.
SUPERSEDED_V2_PARTITION_FINGERPRINT = (
    "242ac003c259a63b60f8f55fa26b8b002b7498267e1f8151ae78bca8db7afccc"
)


def _partition_fingerprint() -> str:
    return framed_digest(
        domain=POLICY_AUTHENTICITY_DIGEST_DOMAIN,
        body={
            "profile": VERIFICATION_PROFILE,
            "profile_version": VERIFICATION_PROFILE_VERSION,
            "verified": sorted(VERIFIED_FACT_NAMES),
            "recorded": sorted(RECORDED_FACT_NAMES),
            "verified_domain": POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN,
            "recorded_domain": POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN,
        },
    )


def _bounds_determination():
    """The reference capacity-bounds determination, under its own adapter registry."""

    authority, record = issued_bounds()
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id="",
        as_of=T_MID,
    ).verified_policy


def _reference_determination():
    authority, record = issued()
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy


@pytest.mark.invariant
def test_the_reference_artifact_digest_has_not_moved():
    """If this fails, the artifact's payload or partition changed. Bump the profile version."""

    assert _reference_determination().artifact_digest == FROZEN_ARTIFACT_DIGEST


@pytest.mark.invariant
def test_the_reference_trust_configuration_digest_has_not_moved():
    assert (
        _reference_determination().trust_configuration_digest
        == FROZEN_TRUST_CONFIGURATION_DIGEST
    )


@pytest.mark.invariant
def test_the_partition_fingerprint_ties_membership_to_the_profile_version():
    """The fingerprint still covers the profile version and both halves' exact membership.

    What it establishes is that an *unintended* move surfaces here rather than silently. What
    it does not establish is the discipline itself: a deliberate promotion can update this
    constant in the same commit. ``tests/test_partition_ratchet.py`` is what refuses that.
    """

    assert _partition_fingerprint() == FROZEN_PARTITION_FINGERPRINT


@pytest.mark.invariant
def test_the_profile_version_is_the_one_these_digests_were_recorded_under():
    """``v4`` since R-8: gate 16 reconciles a candidate against the authenticated bound.

    ``v3`` was 5B-3, which added gates 14-15 and promoted ``policy_type``. ``v4`` moves
    nothing between the halves — what changed is what a determination *establishes*, which
    is the thing a profile version names.
    """

    assert VERIFICATION_PROFILE_VERSION == "v4"


@pytest.mark.invariant
def test_the_v1_artifact_digest_and_fingerprint_are_never_produced_again():
    """The promotion, pinned from the other side: reverting it must fail rather than pass."""

    assert _reference_determination().artifact_digest != SUPERSEDED_V1_ARTIFACT_DIGEST
    assert _partition_fingerprint() != SUPERSEDED_V1_PARTITION_FINGERPRINT
    assert "candidate_digest_fact" in VERIFIED_FACT_NAMES
    assert "candidate_digest_fact" not in RECORDED_FACT_NAMES


@pytest.mark.invariant
def test_the_v2_artifact_digest_and_fingerprint_are_never_produced_again():
    """5B-3's promotion, pinned from the other side, exactly as 5B-1's is."""

    assert _reference_determination().artifact_digest != SUPERSEDED_V2_ARTIFACT_DIGEST
    assert _partition_fingerprint() != SUPERSEDED_V2_PARTITION_FINGERPRINT
    assert "policy_type" in VERIFIED_FACT_NAMES
    assert "policy_type" not in RECORDED_FACT_NAMES
    assert "capacity_bounds_fact" in VERIFIED_FACT_NAMES


@pytest.mark.invariant
def test_the_reference_bounds_artifact_digest_has_not_moved():
    """The capacity-bounds determination, anchored the same way the UVI one is."""

    assert _bounds_determination().artifact_digest == FROZEN_BOUNDS_ARTIFACT_DIGEST


@pytest.mark.invariant
def test_the_bounds_trust_configuration_digest_reflects_its_own_adapter_set():
    """A different registered adapter set is a different trust configuration.

    This is what the reference determination's own trust-configuration digest *cannot*
    establish, because that fixture's adapter set did not change in 5B-3.
    """

    bounds = _bounds_determination()
    assert bounds.trust_configuration_digest == FROZEN_BOUNDS_TRUST_CONFIGURATION_DIGEST
    assert bounds.trust_configuration_digest != FROZEN_TRUST_CONFIGURATION_DIGEST


@pytest.mark.invariant
def test_the_reference_bounds_artifact_carries_its_authenticated_bounds():
    """The facts 5B-3 promoted are actually on the artifact, not merely declared."""

    bounds = _bounds_determination()
    assert bounds.policy_type == "CapacityBoundsPolicy"
    # Two since R-8: one for the genuine candidate's exact selector, one for a different
    # selector so a selector *miss* has something real to miss against.
    assert len(bounds.capacity_bounds_fact) == 2
    selected = [b for b in bounds.capacity_bounds_fact if b.action_type == "scale_up"]
    assert len(selected) == 1
    assert selected[0].resource_class == "deploy/checkout-api"
    assert selected[0].max_permitted_magnitude == 100
    assert selected[0].max_permitted_delta == 25
    # And the superseded body is never produced again.
    assert bounds.artifact_digest != SUPERSEDED_UNSELECTABLE_BOUNDS_ARTIFACT_DIGEST


@pytest.mark.invariant
def test_the_frozen_digests_are_reproducible_within_a_process():
    """A digest that varies run to run pins nothing. Cross-process was verified before pinning."""

    first = _reference_determination()
    second = _reference_determination()
    assert first.artifact_digest == second.artifact_digest == FROZEN_ARTIFACT_DIGEST


@pytest.mark.invariant
def test_the_v3_digests_are_never_produced_again():
    """R-8's bump, pinned from the other side — and the membership half held constant.

    The other supersession tests in this file pair a moved digest with a moved partition.
    This one cannot: R-8 promotes, demotes and adds nothing, so the two halves are
    byte-identical across the move. That is the point of pinning it — it measures that the
    fingerprint tracks the profile version and not only the membership, which no earlier
    supersession in this file could distinguish.
    """

    assert _reference_determination().artifact_digest != SUPERSEDED_V3_ARTIFACT_DIGEST
    assert _bounds_determination().artifact_digest != SUPERSEDED_V3_BOUNDS_ARTIFACT_DIGEST
    assert _partition_fingerprint() != SUPERSEDED_V3_PARTITION_FINGERPRINT
    assert set(VERIFIED_FACT_NAMES) and set(RECORDED_FACT_NAMES)
