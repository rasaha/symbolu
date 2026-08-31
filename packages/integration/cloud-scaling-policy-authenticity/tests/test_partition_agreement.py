"""R-7 — the payload maps and the canonical membership are compared before minting (5B-2).

The membership used to live in three places: ``VERIFIED_FACT_NAMES`` and
``RECORDED_FACT_NAMES`` in ``verified.py``, the two literal maps in ``verification.py``, and an
unnamed ``derived`` tuple reconciling the difference. Nothing compared them. The 5B-1 promotion
had to edit two of the three by hand, and the only thing that would have caught a miss was the
artifact's own self-digest failing later — a correctness backstop that reports the symptom
rather than the edit.

``DERIVED_FACT_NAMES`` names the difference instead of hiding it in a tuple, and
:func:`require_partition_agreement` compares the maps against the declaration at mint time. The
residual was recorded as a maintenance hazard rather than a correctness one, and that reading
holds — what changes is that the hazard now fails loudly and says which side is short.
"""

from __future__ import annotations

import pytest

from _policy_fixtures import T_MID, issued, verifier_for
from ugence_cloud_scaling_policy_authenticity import VerifiedPolicyArtifactIntegrityError
from ugence_cloud_scaling_policy_authenticity.verified import (
    DERIVED_FACT_NAMES,
    RECORDED_FACT_NAMES,
    VERIFIED_DIGEST_KEYS,
    VERIFIED_FACT_NAMES,
    require_partition_agreement,
)


def _genuine():
    authority, record = issued()
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy


@pytest.mark.invariant
def test_the_derived_names_are_exactly_the_difference_between_the_two_views():
    """Why the sets differ at all: three digest-covered names that are not fields."""

    from dataclasses import fields

    declared = {f.name for f in fields(type(_genuine()))} - {
        "artifact_digest",
        "construction_token",
    }
    assert VERIFIED_DIGEST_KEYS == VERIFIED_FACT_NAMES | DERIVED_FACT_NAMES
    assert DERIVED_FACT_NAMES.isdisjoint(declared), (
        "a derived name is one the digest covers but the artifact does not carry as a field; "
        "one that IS a field belongs in VERIFIED_FACT_NAMES instead"
    )
    assert DERIVED_FACT_NAMES == {"outcome", "grants_authority", "historical"}


@pytest.mark.invariant
def test_a_real_determination_satisfies_the_agreement():
    """The gate is not vacuous in the passing direction either."""

    require_partition_agreement(
        verified_map={name: None for name in VERIFIED_DIGEST_KEYS},
        recorded_map={name: None for name in RECORDED_FACT_NAMES},
    )


@pytest.mark.adversarial
@pytest.mark.parametrize("half", ["verified", "recorded"])
def test_a_missing_name_is_refused_and_named(half):
    maps = {
        "verified": {n: None for n in VERIFIED_DIGEST_KEYS},
        "recorded": {n: None for n in RECORDED_FACT_NAMES},
    }
    dropped = sorted(maps[half])[0]
    del maps[half][dropped]
    with pytest.raises(VerifiedPolicyArtifactIntegrityError) as exc:
        require_partition_agreement(
            verified_map=maps["verified"], recorded_map=maps["recorded"]
        )
    assert half in str(exc.value) and dropped in str(exc.value)


@pytest.mark.adversarial
def test_an_extra_name_is_refused_too():
    """Symmetric: a payload key nobody declared is as much a drift as a missing one."""

    with pytest.raises(VerifiedPolicyArtifactIntegrityError) as exc:
        require_partition_agreement(
            verified_map={**{n: None for n in VERIFIED_DIGEST_KEYS}, "smuggled": None},
            recorded_map={n: None for n in RECORDED_FACT_NAMES},
        )
    assert "smuggled" in str(exc.value)


@pytest.mark.adversarial
def test_a_name_moved_between_the_halves_is_refused_by_both_sides():
    """The 5B-1 promotion's exact shape — done to one map and not the declaration."""

    verified = {n: None for n in VERIFIED_DIGEST_KEYS}
    recorded = {n: None for n in RECORDED_FACT_NAMES}
    moved = sorted(RECORDED_FACT_NAMES)[0]
    verified[moved] = recorded.pop(moved)
    with pytest.raises(VerifiedPolicyArtifactIntegrityError) as exc:
        require_partition_agreement(verified_map=verified, recorded_map=recorded)
    assert moved in str(exc.value)


@pytest.mark.adversarial
def test_derived_cannot_be_widened_to_swallow_a_real_field():
    """Found by independent review, and it defeated the first version of this guard.

    Adding a real constructor field to ``DERIVED_FACT_NAMES`` does not change
    ``VERIFIED_DIGEST_KEYS`` — the union already contained it — so the membership comparison
    saw nothing short. The field was then dropped from the constructor call and the artifact
    died on a missing keyword argument, which classifies as ``VERIFICATION_UNAVAILABLE``:
    *the verifier could not run*, when the truth was *the verifier's partition is wrong*.

    Measured before the repair: outcome ``VERIFICATION_UNAVAILABLE``, detail "TypeError".
    """

    import ugence_cloud_scaling_policy_authenticity.verified as V

    original = V.DERIVED_FACT_NAMES
    V.DERIVED_FACT_NAMES = original | {"policy_id"}
    try:
        assert (V.VERIFIED_FACT_NAMES | V.DERIVED_FACT_NAMES) == V.VERIFIED_DIGEST_KEYS, (
            "the union is unchanged by the widening, which is exactly why the membership "
            "comparison alone could not see it"
        )
        with pytest.raises(VerifiedPolicyArtifactIntegrityError) as exc:
            require_partition_agreement(
                verified_map={n: None for n in V.VERIFIED_DIGEST_KEYS},
                recorded_map={n: None for n in RECORDED_FACT_NAMES},
            )
        assert "policy_id" in str(exc.value)
    finally:
        V.DERIVED_FACT_NAMES = original


@pytest.mark.adversarial
def test_the_real_verifier_refuses_the_widening_as_an_invariant_violation():
    """End to end: the terminal classification is the honest one, not 'could not run'."""

    import ugence_cloud_scaling_policy_authenticity.verification as VF
    import ugence_cloud_scaling_policy_authenticity.verified as V
    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome as O

    original = V.DERIVED_FACT_NAMES
    V.DERIVED_FACT_NAMES = VF.DERIVED_FACT_NAMES = original | {"policy_id"}
    try:
        authority, record = issued()
        result = verifier_for(authority).verify(
            coordinate=record.coordinate,
            expected_reference_tenant_id=record.coordinate.tenant_id,
            as_of=T_MID,
        )
        assert result.outcome is O.INVARIANT_VIOLATION
        assert result.outcome is not O.VERIFICATION_UNAVAILABLE
    finally:
        V.DERIVED_FACT_NAMES = VF.DERIVED_FACT_NAMES = original


@pytest.mark.adversarial
def test_verified_cannot_be_widened_to_swallow_a_derived_name():
    """The mirror of ``test_derived_cannot_be_widened_to_swallow_a_real_field``.

    Moving ``historical`` out of ``DERIVED_FACT_NAMES`` and into ``VERIFIED_FACT_NAMES`` makes
    it pass straight through to the constructor. The ``smuggled`` check only ever inspects
    ``DERIVED_FACT_NAMES``, so it is blind to this direction, and the membership comparison
    below it only compares a payload against the declaration — never the declaration against
    the dataclass — so it cannot see it either. Before the mirrored check existed, the direct
    call did not raise at all: the union is unchanged by the move (the name is still counted
    once), so nothing here looked short.
    """

    import ugence_cloud_scaling_policy_authenticity.verified as V

    original_verified = V.VERIFIED_FACT_NAMES
    original_derived = V.DERIVED_FACT_NAMES
    V.VERIFIED_FACT_NAMES = original_verified | {"historical"}
    V.DERIVED_FACT_NAMES = original_derived - {"historical"}
    V.VERIFIED_DIGEST_KEYS = V.VERIFIED_FACT_NAMES | V.DERIVED_FACT_NAMES
    try:
        assert V.VERIFIED_DIGEST_KEYS == (original_verified | original_derived), (
            "the union is unchanged by the move, which is exactly why the membership "
            "comparison alone could not see it"
        )
        with pytest.raises(VerifiedPolicyArtifactIntegrityError) as exc:
            require_partition_agreement(
                verified_map={n: None for n in V.VERIFIED_DIGEST_KEYS},
                recorded_map={n: None for n in RECORDED_FACT_NAMES},
            )
        assert "historical" in str(exc.value)
    finally:
        V.VERIFIED_FACT_NAMES = original_verified
        V.DERIVED_FACT_NAMES = original_derived
        V.VERIFIED_DIGEST_KEYS = original_verified | original_derived


@pytest.mark.adversarial
def test_the_real_verifier_refuses_the_derived_promotion_as_an_invariant_violation():
    """End to end: promoting a derived name into VERIFIED_FACT_NAMES is also refused cleanly.

    Before the mirrored check existed: outcome ``VERIFICATION_UNAVAILABLE``, detail
    "TypeError" — the mint routine excludes only ``DERIVED_FACT_NAMES`` keys from the
    constructor call, so ``historical`` was passed through as an unexpected keyword argument.
    """

    import ugence_cloud_scaling_policy_authenticity.verification as VF
    import ugence_cloud_scaling_policy_authenticity.verified as V
    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome as O

    original_verified = V.VERIFIED_FACT_NAMES
    original_derived = V.DERIVED_FACT_NAMES
    V.VERIFIED_FACT_NAMES = original_verified | {"historical"}
    V.DERIVED_FACT_NAMES = VF.DERIVED_FACT_NAMES = original_derived - {"historical"}
    V.VERIFIED_DIGEST_KEYS = V.VERIFIED_FACT_NAMES | V.DERIVED_FACT_NAMES
    try:
        authority, record = issued()
        result = verifier_for(authority).verify(
            coordinate=record.coordinate,
            expected_reference_tenant_id=record.coordinate.tenant_id,
            as_of=T_MID,
        )
        assert result.outcome is O.INVARIANT_VIOLATION
        assert result.outcome is not O.VERIFICATION_UNAVAILABLE
    finally:
        V.VERIFIED_FACT_NAMES = original_verified
        V.DERIVED_FACT_NAMES = VF.DERIVED_FACT_NAMES = original_derived
        V.VERIFIED_DIGEST_KEYS = original_verified | original_derived
