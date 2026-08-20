"""D-5B0B-7: the digest payload partitions into a verified half and a recorded half.

Two of a verification artifact's facts were never attested. ``resolved_as_of_fact`` is
injected by the caller and unvalidated (**R-2**); ``candidate_digest_fact`` is recorded and
never reconciled (**R-4**). Before the partition, the only thing separating them from
"signed by an entitled key under configured trust" was a ``_fact`` suffix and a docstring — a
reader who trusts the artifact's shape rather than its prose got no signal at all.

Both halves stay inside the artifact digest, so neither can be rewritten after the fact. What
the partition adds is that the **frame a fact sits in** is part of what the digest commits to,
which makes promotion visible: when 5B-1 closes R-4 and 5B-2 closes R-2, moving those facts
into the verified half moves the artifact digest.
"""

from __future__ import annotations

import pytest

from _policy_fixtures import T_MID, issued, verifier_for
from ugence_cloud_scaling_policy_authenticity import (
    POLICY_AUTHENTICITY_DIGEST_DOMAIN,
    POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN,
    POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN,
    VerifiedPolicyArtifactIntegrityError,
    VerifiedPolicyAuthenticity,
    require_verified_policy_authenticity,
)
from ugence_cloud_scaling_policy_authenticity.verified import (
    RECORDED_FACT_NAMES,
    VERIFIED_FACT_NAMES,
    _partitioned_digest,
)


def _genuine():
    authority, record = issued()
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy


# --------------------------------------------------------------------------- #
# The partition itself
# --------------------------------------------------------------------------- #
@pytest.mark.invariant
def test_the_partition_is_total_and_disjoint_over_the_artifact_s_own_fields():
    """Adding a field means deciding whether a gate checked it. An import guard enforces it."""

    from dataclasses import fields

    declared = {f.name for f in fields(VerifiedPolicyAuthenticity)} - {
        "artifact_digest",
        "construction_token",
    }
    assert VERIFIED_FACT_NAMES.isdisjoint(RECORDED_FACT_NAMES)
    assert VERIFIED_FACT_NAMES | RECORDED_FACT_NAMES == declared


@pytest.mark.invariant
def test_the_recorded_half_holds_exactly_the_two_facts_the_open_residuals_name():
    assert RECORDED_FACT_NAMES == {"resolved_as_of_fact", "candidate_digest_fact"}


@pytest.mark.invariant
def test_the_two_halves_are_separately_framed_under_distinct_domains():
    payload = _genuine().digest_payload()
    assert set(payload) == {"verified", "recorded"}
    assert payload["verified"]["domain"] == POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN
    assert payload["recorded"]["domain"] == POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN
    assert set(payload["verified"]) == set(payload["recorded"]) == {"domain", "facts"}
    assert POLICY_AUTHENTICITY_DIGEST_DOMAIN not in (
        payload["verified"]["domain"],
        payload["recorded"]["domain"],
    )


@pytest.mark.invariant
def test_no_fact_appears_in_both_halves_of_a_real_artifact():
    artifact = _genuine()
    assert set(artifact.verified_facts()).isdisjoint(artifact.recorded_facts())
    assert set(artifact.recorded_facts()) == RECORDED_FACT_NAMES


# --------------------------------------------------------------------------- #
# Both halves are covered by the artifact digest
# --------------------------------------------------------------------------- #
@pytest.mark.adversarial
def test_rewriting_a_verified_fact_breaks_the_artifact_digest():
    artifact = _genuine()
    object.__setattr__(artifact, "policy_id", "some-other-policy")
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        require_verified_policy_authenticity(artifact)


@pytest.mark.adversarial
def test_rewriting_a_recorded_fact_breaks_the_artifact_digest_too():
    """Unverified is not unprotected: nobody checked it, and nobody can rewrite it either."""

    artifact = _genuine()
    assert artifact.candidate_digest_fact is None
    object.__setattr__(artifact, "candidate_digest_fact", "sha256:" + "a" * 64)
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        require_verified_policy_authenticity(artifact)


@pytest.mark.adversarial
def test_rewriting_the_injected_instant_breaks_the_artifact_digest():
    from datetime import timedelta

    artifact = _genuine()
    object.__setattr__(artifact, "resolved_as_of_fact", T_MID + timedelta(days=1))
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        require_verified_policy_authenticity(artifact)


# --------------------------------------------------------------------------- #
# Moving a fact between the halves moves the digest
# --------------------------------------------------------------------------- #
@pytest.mark.adversarial
@pytest.mark.parametrize("promoted", sorted(RECORDED_FACT_NAMES))
def test_promoting_a_recorded_fact_into_the_verified_half_moves_the_artifact_digest(promoted):
    """What 5B-1 and 5B-2 will do when they close R-4 and R-2, and it must be visible."""

    artifact = _genuine()
    verified_map = dict(artifact.verified_facts())
    recorded_map = dict(artifact.recorded_facts())
    as_is = _partitioned_digest(verified_map=verified_map, recorded_map=recorded_map)
    assert as_is == artifact.artifact_digest

    verified_map[promoted] = recorded_map.pop(promoted)
    promoted_digest = _partitioned_digest(
        verified_map=verified_map, recorded_map=recorded_map
    )
    assert promoted_digest != as_is


@pytest.mark.adversarial
def test_demoting_a_verified_fact_into_the_recorded_half_moves_the_artifact_digest():
    """The direction that matters for an attacker: a checked fact quietly reclassified."""

    artifact = _genuine()
    verified_map = dict(artifact.verified_facts())
    recorded_map = dict(artifact.recorded_facts())
    recorded_map["policy_body_digest"] = verified_map.pop("policy_body_digest")
    assert (
        _partitioned_digest(verified_map=verified_map, recorded_map=recorded_map)
        != artifact.artifact_digest
    )


@pytest.mark.adversarial
def test_the_same_facts_in_one_flat_map_do_not_reproduce_the_artifact_digest():
    """The partition is load-bearing, not cosmetic: the pre-D-5B0B-7 shape no longer verifies."""

    from ugence_cloud_scaling_policy_authenticity import framed_digest

    artifact = _genuine()
    flat = {**artifact.verified_facts(), **artifact.recorded_facts()}
    assert (
        framed_digest(domain=POLICY_AUTHENTICITY_DIGEST_DOMAIN, body=flat)
        != artifact.artifact_digest
    )


# --------------------------------------------------------------------------- #
# A recorded fact cannot be read through an accessor that reads as attested
# --------------------------------------------------------------------------- #
@pytest.mark.adversarial
@pytest.mark.parametrize("name", sorted(RECORDED_FACT_NAMES))
def test_a_recorded_fact_is_refused_by_the_verified_accessor(name):
    artifact = _genuine()
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        artifact.verified_fact(name)


@pytest.mark.adversarial
def test_a_verified_fact_is_refused_by_the_recorded_accessor():
    """Symmetric on purpose: understating what is known is its own misreading."""

    artifact = _genuine()
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        artifact.recorded_fact("policy_body_digest")


@pytest.mark.adversarial
def test_an_unknown_name_is_refused_by_both_accessors():
    artifact = _genuine()
    for accessor in (artifact.verified_fact, artifact.recorded_fact):
        with pytest.raises(VerifiedPolicyArtifactIntegrityError):
            accessor("grants_authority_somehow")


@pytest.mark.happy
def test_each_accessor_answers_for_its_own_half():
    artifact = _genuine()
    assert artifact.verified_fact("policy_body_digest") == artifact.policy_body_digest
    assert artifact.recorded_fact("resolved_as_of_fact") == artifact.resolved_as_of_fact
    for name in VERIFIED_FACT_NAMES:
        assert artifact.verified_fact(name) == getattr(artifact, name)
