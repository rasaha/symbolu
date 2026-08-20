"""Trust anchors: exact-coordinate resolution, key lifecycle, and revocation.

ADR E-5 (composition root), E-8 (deny by default), §7.1 row 9 (key trust and
key revocation), §11 row 5 (the key-lifecycle refusal family), §13.3 (revocation
checked at verification time), §17.9 (half-open intervals) and §26.9 (guessing
is prohibited).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from _authority_builders import (
    KEY_FROM,
    KEY_TO,
    TRUST_ANCHOR_SET_ID,
    TRUST_ANCHOR_SET_VERSION,
    VERIFIER_AUTHORITY_ID,
    VERIFIER_KEY_ID,
    attacker_signing_key,
    authority_anchor,
    authority_signing_key,
    directory,
    producer_anchor,
)
from ugence_trusted_evidence_authority.api import (
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    DenyAllTrustAnchorDirectory,
    KeyRevocation,
    StaticTrustAnchorDirectory,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorRecord,
    TrustAnchorResolution,
    TrustedEvidenceContractError,
    TrustedEvidenceRefusalReason,
    encode_public_key,
)

R = TrustedEvidenceRefusalReason
UTC = timezone.utc
MID = datetime(2026, 6, 1, tzinfo=UTC)


def coordinate(**kw) -> TrustAnchorCoordinate:
    return TrustAnchorCoordinate(
        **{
            "authority_id": VERIFIER_AUTHORITY_ID,
            "key_id": VERIFIER_KEY_ID,
            "capability": TrustAnchorCapability.RECEIPT_ISSUANCE,
            **kw,
        }
    )


# --------------------------------------------------------------------------- #
# Exact-coordinate resolution
# --------------------------------------------------------------------------- #

def test_an_exact_coordinate_resolves():
    resolution = directory().resolve(coordinate())
    assert resolution.anchor is not None
    assert resolution.refusal_reason is None
    assert resolution.anchor.key_id == VERIFIER_KEY_ID


@pytest.mark.parametrize(
    "override",
    [
        {"authority_id": "not-the-authority"},
        {"key_id": "not-the-key"},
        {"capability": TrustAnchorCapability.EVIDENCE_PRODUCTION},
        {"authority_id": VERIFIER_AUTHORITY_ID.upper()},
        {"key_id": VERIFIER_KEY_ID + "-2"},
        {"key_id": VERIFIER_KEY_ID[:-1]},
    ],
    ids=["wrong-authority", "wrong-key", "wrong-capability", "case-differs",
         "suffixed", "prefix-of"],
)
def test_a_near_miss_coordinate_is_a_miss(override):
    """No partial match, no prefix match, no case folding, no fuzzy lookup."""

    resolution = directory().resolve(coordinate(**override))
    assert resolution.anchor is None
    assert resolution.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING


def test_the_directory_offers_no_latest_default_or_first_key_wins_lookup():
    """§26.9 — guessing which key is an unsigned authority decision."""

    store = directory()
    for absent in ("latest", "current", "default", "any", "first", "find",
                   "search", "get", "resolve_by_authority", "resolve_latest",
                   "newest", "__getitem__"):
        assert not hasattr(store, absent), absent


def test_duplicate_coordinates_are_refused_at_construction():
    anchor = authority_anchor()
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        StaticTrustAnchorDirectory((anchor, anchor))
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_AMBIGUOUS


def test_a_second_anchor_at_one_coordinate_cannot_be_added_later():
    """Replacing a trust anchor is a composition-root act, not a mutation."""

    with pytest.raises(TrustedEvidenceContractError):
        directory().with_anchor(authority_anchor())
    # A *different* coordinate is fine, and returns a new directory.
    extended = StaticTrustAnchorDirectory((authority_anchor(),)).with_anchor(
        producer_anchor()
    )
    assert len(extended.anchors) == 2
    assert len(StaticTrustAnchorDirectory((authority_anchor(),)).anchors) == 1


def test_two_anchors_may_share_a_key_id_only_across_different_authorities():
    store = StaticTrustAnchorDirectory(
        (
            authority_anchor(),
            authority_anchor(authority_id="a-second-authority"),
        )
    )
    assert len(store.anchors) == 2
    assert store.resolve(coordinate()).anchor is not None
    assert (
        store.resolve(coordinate(authority_id="a-second-authority")).anchor is not None
    )


def test_an_empty_directory_denies_rather_than_reporting_absence():
    """E-8 — no trust anchor configured means deny, not "nothing to check"."""

    resolution = StaticTrustAnchorDirectory(()).resolve(coordinate())
    assert resolution.anchor is None
    assert resolution.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED


def test_the_deny_all_directory_refuses_every_coordinate():
    store = DenyAllTrustAnchorDirectory()
    for override in ({}, {"key_id": "anything"}, {"authority_id": "anyone"}):
        resolution = store.resolve(coordinate(**override))
        assert resolution.anchor is None
        assert resolution.refusal_reason is (
            R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED
        )


def test_no_permissive_or_allow_all_resolver_ships():
    """E-8 — "no production allow-all verifier may ship"."""

    import ugence_trusted_evidence_authority.api as api

    for name in api.__all__:
        lowered = name.lower()
        for banned in ("allowall", "permissive", "insecure", "trustall",
                       "fake", "stub", "null", "noop"):
            assert banned not in lowered.replace("_", ""), name


def test_a_resolution_carries_exactly_one_of_an_anchor_or_a_reason():
    with pytest.raises(TrustedEvidenceContractError):
        TrustAnchorResolution(coordinate=coordinate())
    with pytest.raises(TrustedEvidenceContractError):
        TrustAnchorResolution(
            coordinate=coordinate(),
            anchor=authority_anchor(),
            refusal_reason=R.TRUSTED_EVIDENCE_KEY_REVOKED,
        )


def test_a_resolver_may_not_answer_a_question_it_was_not_asked():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        TrustAnchorResolution.resolved(
            coordinate(key_id="a-different-key"), authority_anchor()
        )
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_KEY_ID_MISMATCH


# --------------------------------------------------------------------------- #
# Capability separation (E-3, §8.1.1)
# --------------------------------------------------------------------------- #

def test_an_anchor_holds_exactly_one_capability():
    """One key, one role — unrepresentable to violate.

    The role vocabulary now carries a third member,
    ``CLOUD_SCALING_RECOMMENDATION_ATTESTATION``, lent to the Cloud Scaling
    producer-attestation consumer. It changes nothing here: an anchor still holds
    exactly one capability, the two evidence roles keep their spelling and order, and
    no path in this package resolves the lent member (see
    ``test_lent_capability_disjointness.py``).
    """

    assert [m.name for m in TrustAnchorCapability] == [
        "EVIDENCE_PRODUCTION",
        "RECEIPT_ISSUANCE",
        "CLOUD_SCALING_RECOMMENDATION_ATTESTATION",
    ]
    anchor = authority_anchor()
    assert isinstance(anchor.capability, TrustAnchorCapability)
    with pytest.raises(TrustedEvidenceContractError):
        authority_anchor(capability={TrustAnchorCapability.RECEIPT_ISSUANCE})
    with pytest.raises(TrustedEvidenceContractError):
        authority_anchor(capability="RECEIPT_ISSUANCE")


def test_a_producing_key_never_satisfies_a_receipt_issuance_coordinate():
    same_key_both_roles = TrustAnchorRecord(
        authority_id=VERIFIER_AUTHORITY_ID,
        key_id=VERIFIER_KEY_ID,
        capability=TrustAnchorCapability.EVIDENCE_PRODUCTION,
        public_key=encode_public_key(
            authority_signing_key().verification_key.public_key_bytes
        ),
        trust_anchor_set_id=TRUST_ANCHOR_SET_ID,
        trust_anchor_set_version=TRUST_ANCHOR_SET_VERSION,
    )
    store = StaticTrustAnchorDirectory((same_key_both_roles,))
    assert store.resolve(coordinate()).anchor is None
    assert (
        store.resolve(
            coordinate(capability=TrustAnchorCapability.EVIDENCE_PRODUCTION)
        ).anchor
        is not None
    )


# --------------------------------------------------------------------------- #
# Key lifecycle at an explicit instant (§11 row 5, §17.9)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "instant,expected",
    [
        (KEY_FROM - timedelta(microseconds=1), R.TRUSTED_EVIDENCE_KEY_NOT_YET_VALID),
        (KEY_FROM, None),
        (KEY_FROM + timedelta(microseconds=1), None),
        (KEY_TO - timedelta(microseconds=1), None),
        (KEY_TO, R.TRUSTED_EVIDENCE_KEY_EXPIRED),
        (KEY_TO + timedelta(days=1), R.TRUSTED_EVIDENCE_KEY_EXPIRED),
    ],
    ids=["just-before", "at-from", "just-after-from", "just-before-to",
         "at-to-exclusive", "well-after"],
)
def test_key_validity_is_half_open_from_inclusive_to_exclusive(instant, expected):
    assert authority_anchor().lifecycle_refusal_at(instant) is expected


def test_an_open_ended_key_is_usable_on_the_open_side():
    assert authority_anchor(effective_from=None).lifecycle_refusal_at(
        datetime(1999, 1, 1, tzinfo=UTC)
    ) is None
    assert authority_anchor(effective_to=None).lifecycle_refusal_at(
        datetime(2999, 1, 1, tzinfo=UTC)
    ) is None


def test_an_inverted_or_empty_key_interval_is_refused():
    with pytest.raises(TrustedEvidenceContractError):
        authority_anchor(effective_from=KEY_TO, effective_to=KEY_FROM)
    with pytest.raises(TrustedEvidenceContractError):
        authority_anchor(effective_from=KEY_FROM, effective_to=KEY_FROM)


def test_a_disabled_key_is_refused_at_every_instant():
    anchor = authority_anchor(disabled=True)
    for instant in (KEY_FROM, MID, KEY_TO - timedelta(days=1)):
        assert anchor.lifecycle_refusal_at(instant) is R.TRUSTED_EVIDENCE_KEY_DISABLED


@pytest.mark.parametrize("truthy", [1, "true", "yes", [1], {"a": 1}, object()])
def test_disabled_refuses_a_truthy_substitute(truthy):
    """A trust decision may not rest on coercion."""

    with pytest.raises(TrustedEvidenceContractError):
        authority_anchor(disabled=truthy)


# --------------------------------------------------------------------------- #
# Revocation (§13.3, §26.8, §17.9)
# --------------------------------------------------------------------------- #

REVOKE_AT = datetime(2026, 6, 15, tzinfo=UTC)


@pytest.mark.parametrize(
    "instant,revoked",
    [
        (REVOKE_AT - timedelta(microseconds=1), False),
        (REVOKE_AT, True),
        (REVOKE_AT + timedelta(microseconds=1), True),
    ],
    ids=["just-before", "at-the-instant", "just-after"],
)
def test_revocation_takes_effect_from_its_instant_inclusive(instant, revoked):
    revocation = KeyRevocation(effective_at=REVOKE_AT)
    assert revocation.is_revoked_at(instant) is revoked
    anchor = authority_anchor(revocation=revocation)
    expected = R.TRUSTED_EVIDENCE_KEY_REVOKED if revoked else None
    assert anchor.lifecycle_refusal_at(instant) is expected


def test_revocation_outranks_every_other_lifecycle_state():
    """§13.3 — a revoked key is never silently honoured, whatever else holds."""

    anchor = authority_anchor(
        disabled=True,
        effective_from=datetime(2030, 1, 1, tzinfo=UTC),
        effective_to=datetime(2031, 1, 1, tzinfo=UTC),
        revocation=KeyRevocation(effective_at=KEY_FROM),
    )
    assert anchor.lifecycle_refusal_at(MID) is R.TRUSTED_EVIDENCE_KEY_REVOKED


def test_revocation_wins_even_inside_the_key_validity_window():
    anchor = authority_anchor(revocation=KeyRevocation(effective_at=KEY_FROM))
    assert anchor.lifecycle_refusal_at(MID) is R.TRUSTED_EVIDENCE_KEY_REVOKED
    assert KEY_FROM <= MID < KEY_TO


def test_key_revocation_is_distinct_from_evidence_revocation():
    """§26.8 — three revocations, never conflated."""

    assert R.TRUSTED_EVIDENCE_KEY_REVOKED is not R.TRUSTED_EVIDENCE_REVOKED
    assert (
        R.TRUSTED_EVIDENCE_KEY_REVOKED.value != R.TRUSTED_EVIDENCE_REVOKED.value
    )


def test_a_revocation_carries_an_instant_not_a_bare_flag():
    with pytest.raises(TrustedEvidenceContractError):
        KeyRevocation(effective_at=True)
    with pytest.raises(TrustedEvidenceContractError):
        KeyRevocation(effective_at="2026-06-15")
    with pytest.raises(TrustedEvidenceContractError):
        KeyRevocation(effective_at=datetime(2026, 6, 15))


def test_the_lifecycle_check_reads_no_clock():
    with pytest.raises(TrustedEvidenceContractError):
        authority_anchor().lifecycle_refusal_at(datetime(2026, 6, 1))
    with pytest.raises(TypeError):
        authority_anchor().lifecycle_refusal_at()


# --------------------------------------------------------------------------- #
# The record itself
# --------------------------------------------------------------------------- #

def test_a_trust_anchor_carries_no_private_material_and_no_field_could():
    import dataclasses

    fields = {f.name for f in dataclasses.fields(TrustAnchorRecord)}
    for banned in ("seed", "private_key", "secret", "signing_key", "key_material"):
        assert banned not in fields, banned
    # And the public key is a hex *string*; the encoder rejects bytes outright.
    assert isinstance(authority_anchor().public_key, str)


def test_the_public_key_must_decode_to_a_real_ed25519_key():
    for bad in ("00" * 31, "00" * 33, "zz" * 32, "AB" * 32, "", " " + "00" * 32):
        with pytest.raises(TrustedEvidenceContractError):
            authority_anchor(public_key=bad)


def test_the_profile_and_encoding_are_pinned_and_not_negotiable():
    anchor = authority_anchor()
    assert anchor.signature_profile == TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1
    assert anchor.signature_encoding == TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1
    for bad in ("none", "ed25519", "rsa", TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1 + "x"):
        with pytest.raises(TrustedEvidenceContractError):
            authority_anchor(signature_profile=bad)


def test_the_anchor_digest_is_deterministic_and_domain_separated():
    from ugence_trusted_evidence_authority.api import (
        TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
        canonical_bytes,
    )
    import json

    a, b = authority_anchor(), authority_anchor()
    assert a.canonical_digest() == b.canonical_digest()
    framed = json.loads(canonical_bytes(a))
    assert framed["domain"] == TRUST_ANCHOR_RECORD_DIGEST_DOMAIN
    assert framed["type"] == "TrustAnchorRecord"
    # Every coordinate moves the digest.
    for override in (
        {"authority_id": "other"},
        {"key_id": "other"},
        {"capability": TrustAnchorCapability.EVIDENCE_PRODUCTION},
        {"trust_anchor_set_version": "2"},
        {"disabled": True},
        {"effective_from": KEY_FROM + timedelta(microseconds=1)},
        {"revocation": KeyRevocation(effective_at=REVOKE_AT)},
        {
            "public_key": encode_public_key(
                attacker_signing_key().verification_key.public_key_bytes
            )
        },
    ):
        assert authority_anchor(**override).canonical_digest() != a.canonical_digest()


def test_resolution_itself_authorizes_nothing():
    anchor = directory().resolve(coordinate()).anchor
    for forbidden in ("authorize", "admit", "verify", "sign", "approve", "allow"):
        assert not hasattr(anchor, forbidden), forbidden
