"""Frozen digests — the artifact digest has a merged definition now, so it stops moving quietly.

Before this package merged, moving a fact between the verified and recorded halves was free:
nothing downstream pinned an artifact digest, so three rounds of remediation reshaped the
payload at ``0.1.0`` without consequence. That window is closed. A verified artifact's digest
is now something a consumer can pin, and 5B-1 and 5B-2 will each want to move one — promoting
``candidate_digest_fact`` when R-4 closes, ``resolved_as_of_fact`` when R-2 does.

**The rule this file enforces.** A change that moves a pinned digest is a change to what this
package's verification profile produces. When one of these constants must be updated, update
:data:`~ugence_cloud_scaling_policy_authenticity.VERIFICATION_PROFILE_VERSION` in the same
commit, and say in the changelog which digest moved and why. The partition fingerprint below
makes that mechanical rather than remembered: it covers the profile version *and* the exact
membership of both halves, so moving a fact without bumping fails here, and bumping without
recording the new fingerprint fails here too. Both edits land together or neither does.

**What is deliberately not frozen.** Nothing that depends on wall-clock time, machine state or
key generation. Every value below is reproducible from the repository alone: the fixtures sign
with fixed seeds at fixed instants, so a digest that moves here moved because the *contract*
moved. Verified across processes before pinning.
"""

from __future__ import annotations

import pytest

from _policy_fixtures import T_MID, issued, verifier_for
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
    "8b0ea25f368287715657f1ff2293e137de1f810de7946e4fc27e52d8af473c7f"
)

#: The identity of the fixture trust configuration. Moves when an anchor's authority, tenant,
#: entitlements, window, revocation state or the adapter set changes — which is the point.
FROZEN_TRUST_CONFIGURATION_DIGEST = (
    "87e8a90e26944f27b7f87b189332de4a45ea8db78ae2c35f245ace38da46f429"
)

#: Covers the profile version together with both halves' exact membership and their domain
#: tags. This is the constant that ties a partition change to a profile bump.
FROZEN_PARTITION_FINGERPRINT = (
    "86d39d254d0702ccc90df894ee44a8c5b51b4ebfedeaa7ef396e81ef33edda07"
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
    """Moving a fact between halves without bumping the profile version fails here.

    So does bumping without re-recording the fingerprint. The two edits are forced into one
    commit, which is what makes "promotion requires a bump" a rule rather than a note.
    """

    assert _partition_fingerprint() == FROZEN_PARTITION_FINGERPRINT


@pytest.mark.invariant
def test_the_profile_version_is_the_one_these_digests_were_recorded_under():
    assert VERIFICATION_PROFILE_VERSION == "v1"


@pytest.mark.invariant
def test_the_frozen_digests_are_reproducible_within_a_process():
    """A digest that varies run to run pins nothing. Cross-process was verified before pinning."""

    first = _reference_determination()
    second = _reference_determination()
    assert first.artifact_digest == second.artifact_digest == FROZEN_ARTIFACT_DIGEST
