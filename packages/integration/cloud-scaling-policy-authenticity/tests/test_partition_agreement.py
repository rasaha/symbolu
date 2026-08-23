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
