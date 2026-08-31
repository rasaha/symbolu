"""Three frozen Phase 5B-0A fixtures, with independently recomputed pinned digests.

Frozen exactly three, as ratified: one **verified** attestation, one **resolved** trust
anchor, and one **refused** attestation with its pinned refusal. Nothing that already
existed is re-pinned — the Phase 5A values below are asserted, never redefined, and this
module changes none of them.

Independence is the point of the recomputation helper. The package's own
``canonical_digest`` is what produced these values, so comparing a value to itself would
prove nothing. :func:`_independent_digest` recomputes ``sha256`` over the canonical bytes
directly, through ``hashlib``, which the package itself may not use. If Risk Authority's
canonicalization ever moved, these values would move with it and this module would fail —
which is the intended alarm, not an inconvenience.
"""

from __future__ import annotations

import pytest

import hashlib

import phase5a_fixtures as P5A
from _producer_fixtures import (
    AS_OF,
    ISSUER_ID,
    PRODUCER_ID,
    PRODUCER_KEY_ID,
    TRUSTED_PRODUCER_SEED,
    UNTRUSTED_PRODUCER_SEED,
    build_anchor,
    build_attestation,
    build_candidate,
    build_directory,
    build_verifier,
)

from ugence_trusted_evidence_authority import TrustAnchorCapability

from ugence_cloud_scaling_producer_attestation import (
    ProducerAuthenticityOutcome,
    anchor_coordinate_digest,
    anchor_record_digest,
    canonical_bytes,
    canonical_digest,
    producer_anchor_coordinate,
)

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.

O = ProducerAuthenticityOutcome

# ======================================================================================= #
# The three NEW frozen fixtures. Independently pinned; nothing existing is re-pinned.
# ======================================================================================= #

#: Fixture 1 — a verified producer attestation.
FROZEN_V2_SIGNING_PAYLOAD_DIGEST = (
    "sha256:dc2846759f8ee180c2f895079b17a8bc2f0f7fc1b86d25a453faaefcdda10d9d"
)
FROZEN_V2_ATTESTATION_DIGEST = (
    "sha256:9004557e13363eb7aa1469322e6392481444b7ca11c3be80ba8d538850bd1ae6"
)
FROZEN_V2_SIGNATURE = (
    "2d8ef3dd0cd9c81491159beedb0bf55ef65b3d3892366b06fb4ac85a3335b6a6"
    "dea1287ba58bc12b4e0a3cadd097f545f6baea671ad8bd0352a1386dfd4d4707"
)
#: **Moved by 5B-1**, and not by anything this package did: ``digest_payload()`` binds
#: ``candidate_digest``, and the Phase 5A candidate gained the policy coordinate that closes
#: R-4. This package's source did not change and its version does not move; the fixture it
#: verifies did. The superseded value is pinned below.
#: **Moved again by R-12b**, and again by nothing this package did: ``digest_payload()`` binds
#: ``candidate_digest``, and the Phase 5A candidate digest moved when the Risk Authority
#: decision snapshot gained ``evaluated_at``. Source untouched; fixture pins only.
FROZEN_VERIFIED_ARTIFACT_DIGEST = (
    "sha256:fefe4884af18907fc4e304e3142c4001f4f6280edd91d5259d78fe297058de29"
)
#: The verified artifact this package produced while the decision snapshot carried no
#: ``evaluated_at`` — i.e. while the instant Phase 5B's occurrence gate depends on was
#: unbound. Pinned as a negative anchor on this side too, so a revert surfaces on both.
SUPERSEDED_PRE_R12B_VERIFIED_ARTIFACT_DIGEST = (
    "sha256:5a2a66489c00a5fef94c8fc5be231ee564786286315d6d60e75ecbc55f60d30e"
)

#: Fixture 2 — the resolved trust anchor the verification above ran under.
FROZEN_ANCHOR_COORDINATE_DIGEST = (
    "sha256:2f2e303dbb951971369ad7a98ad5f4140c5aa01977640a55aefed79e22c88054"
)
FROZEN_ANCHOR_RECORD_DIGEST = (
    "sha256:0617ebc49db218fc0f0be405b39cf4da2df456dadbf5cf2ae13970af0d1e2fa9"
)

#: Fixture 3 — a refused attestation, and the exact refusal it pins.
FROZEN_REFUSED_ATTESTATION_DIGEST = (
    "sha256:5167ca7a2e6f02c4848099ea069e4bd5257c883483626b19f2f5b1f0dc7620ed"
)
FROZEN_REFUSAL_OUTCOME = O.SIGNATURE_INVALID

# ======================================================================================= #
# Values that already existed. Asserted here, defined elsewhere, never re-pinned.
# ======================================================================================= #

PHASE_5A_CANDIDATE_DIGEST = (
    "sha256:357bb3d4d660034c9abe50000986808a1e9c15fce05b4a22b6cb82836cc50e79"
)
#: What the Phase 5A candidate hashed to between 5B-1 and R-12b — correct until the decision
#: snapshot gained ``evaluated_at`` and moved ``decision_digest`` beneath the candidate.
SUPERSEDED_PRE_R12B_PHASE_5A_CANDIDATE_DIGEST = (
    "sha256:be06c65385d73f66c52dd51024c30ed7939a836369db654f381d52270f2aa906"
)
#: What the Phase 5A candidate hashed to before 5B-1 bound the policy coordinate inside it.
#: Pinned here, in the package that consumes it, so a revert surfaces on both sides.
SUPERSEDED_PRE_5B1_PHASE_5A_CANDIDATE_DIGEST = (
    "sha256:db72ffffc5bf4ecfe8a5f9fe187efb5e8439355e559fcc34b391cc4c9282a313"
)
#: The verified artifact this package produced while the candidate carried no coordinate.
SUPERSEDED_PRE_5B1_VERIFIED_ARTIFACT_DIGEST = (
    "sha256:519983d832ac08e9914b69cbe8894f241e0e118fd5596d37e903325f171a385d"
)
PHASE_5A_FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST = (
    "sha256:1035d2fc2ab8f4b443f815562f9f6ad8e4ce0032633f03a12e04e691c24cf2d0"
)

# ======================================================================================= #
# Superseded Phase 5B-0A digests, kept as NEGATIVE anchors.
#
# Three of this package's own fixtures moved during remediation, and only these three.
# Every cause is a deliberate correction to an unmerged package, not drift.
#
# The two **trust-anchor** digests moved for one reason: the capability inside the
# coordinate changed from the borrowed ``EVIDENCE_PRODUCTION`` to the dedicated
# ``CLOUD_SCALING_RECOMMENDATION_ATTESTATION``. That the coordinate digest moves is the
# point — it is the machine-checkable proof that the two signing domains are not the same
# coordinate, and therefore not the same entitlement. The record digest moves with it
# because a record carries its coordinate's capability.
#
# The **verified-artifact** digest moved for **four** canonical reasons, not one. Its
# ``digest_payload()`` covers all four of these fields, so each is independently part of
# the hashed bytes:
#
#   1. ``verified_producer_id`` was renamed to ``attested_producer_id``, so the bytes now
#      name what the signature actually establishes;
#   2. ``trust_anchor_capability`` changed value, from ``EVIDENCE_PRODUCTION`` to
#      ``CLOUD_SCALING_RECOMMENDATION_ATTESTATION``;
#   3. ``trust_anchor_coordinate_digest`` changed, because the coordinate it digests now
#      carries the dedicated capability;
#   4. ``trust_anchor_record_digest`` changed, for the same reason.
#
# Causes 2-4 all follow from the dedicated capability replacing the borrowed one; cause 1
# is independent of them. The field rename **alone** does not account for the movement,
# and :func:`test_the_verified_artifact_digest_moved_for_all_four_reasons` proves it by
# reconstructing the superseded bytes: all four reversions together reproduce
# ``39f1b3dd...`` exactly, and reverting any three of the four does not.
#
# They are pinned as values that must **never** be produced again. A recurrence would
# mean the borrowed capability or the overstated field name had come back.
#
# Nothing upstream moved: the v2 signing payload, the v2 attestation, every Phase 5A
# digest and the platform freeze are asserted unchanged elsewhere in this module.
# ======================================================================================= #

SUPERSEDED_VERIFIED_ARTIFACT_DIGEST = (
    "sha256:39f1b3dd2ebe8b313aa7c2c59037ead226308a14a42580f3d2e44363ade7081d"
)
SUPERSEDED_ANCHOR_COORDINATE_DIGEST = (
    "sha256:a122f5323fb05c73b961ddd463b54959e5b2ee8ddde6ee4897d2775dca0a31b8"
)
SUPERSEDED_ANCHOR_RECORD_DIGEST = (
    "sha256:5af3bf6d088c2bd2660e41e85ccd6f7942190177c42facb90c99635931d1e523"
)



#: Every test in this module is a **invariant** property unless it carries an
#: explicit override below. ``tests/test_property_ledger.py`` counts these markers and
#: asserts the ratio the ratified design requires, so the ratio is machine-checked
#: rather than claimed.

def _independent_digest(value) -> str:
    """Recompute ``sha256:`` over the canonical bytes, without the package's digest helper.

    ``hashlib`` is banned inside the distribution precisely so there is exactly one digest
    path there. Using it *here* is what makes this an independent check rather than a
    tautology.
    """

    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


# --------------------------------------------------------------------------------------- #
# Fixture 1 — the verified attestation
# --------------------------------------------------------------------------------------- #


def test_the_verified_attestation_fixture_reproduces_byte_for_byte():
    """F-1: the signing payload, the signature and the attestation digest are all pinned."""

    candidate = build_candidate()
    attestation = build_attestation(candidate)

    assert attestation.signature == FROZEN_V2_SIGNATURE
    assert attestation.signing_payload_digest == FROZEN_V2_SIGNING_PAYLOAD_DIGEST
    assert attestation.digest() == FROZEN_V2_ATTESTATION_DIGEST


def test_the_verified_attestation_digests_are_independently_recomputable():
    """F-2: recomputed from raw canonical bytes, not read back from the package."""

    candidate = build_candidate()
    attestation = build_attestation(candidate)

    assert _independent_digest(attestation.signing_payload()) == (
        FROZEN_V2_SIGNING_PAYLOAD_DIGEST
    )
    assert _independent_digest(attestation.to_canonical_dict()) == (
        FROZEN_V2_ATTESTATION_DIGEST
    )


def test_the_verified_artifact_digest_is_pinned_and_independently_recomputable():
    """F-3: the verification artifact itself is frozen, under the injected instant."""

    candidate = build_candidate()
    verifier = build_verifier(directory=build_directory(build_anchor()))
    artifact = verifier.verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=AS_OF
    ).verified_attestation

    assert artifact.artifact_digest == FROZEN_VERIFIED_ARTIFACT_DIGEST
    assert _independent_digest(artifact.digest_payload()) == (
        FROZEN_VERIFIED_ARTIFACT_DIGEST
    )


# --------------------------------------------------------------------------------------- #
# Fixture 2 — the resolved trust anchor
# --------------------------------------------------------------------------------------- #


def test_the_resolved_trust_anchor_fixture_is_pinned():
    """F-4: the coordinate and the complete anchor record are both frozen."""

    anchor = build_anchor()
    coordinate = producer_anchor_coordinate(
        issuer=ISSUER_ID, producer_key_id=PRODUCER_KEY_ID
    )

    assert anchor_coordinate_digest(coordinate) == FROZEN_ANCHOR_COORDINATE_DIGEST
    assert anchor_record_digest(anchor) == FROZEN_ANCHOR_RECORD_DIGEST


def test_the_trust_anchor_digests_are_independently_recomputable():
    """F-5: recomputed from raw canonical bytes."""

    anchor = build_anchor()
    coordinate = producer_anchor_coordinate(
        issuer=ISSUER_ID, producer_key_id=PRODUCER_KEY_ID
    )

    assert _independent_digest(coordinate) == FROZEN_ANCHOR_COORDINATE_DIGEST
    assert _independent_digest(anchor) == FROZEN_ANCHOR_RECORD_DIGEST


def test_the_anchor_record_digest_covers_the_public_key_and_the_capability():
    """F-6: changing either moves the frozen value, so neither rides along unbound."""

    from ugence_cloud_scaling_producer_attestation import TrustAnchorCapability

    other_key = build_anchor(seed=UNTRUSTED_PRODUCER_SEED)
    other_capability = build_anchor(capability=TrustAnchorCapability.RECEIPT_ISSUANCE)

    assert anchor_record_digest(other_key) != FROZEN_ANCHOR_RECORD_DIGEST
    assert anchor_record_digest(other_capability) != FROZEN_ANCHOR_RECORD_DIGEST


# --------------------------------------------------------------------------------------- #
# Fixture 3 — the refused attestation and its pinned refusal
# --------------------------------------------------------------------------------------- #


def test_the_refused_attestation_fixture_is_pinned():
    """F-7: the forged attestation's own digest is frozen, so the fixture cannot drift."""

    candidate = build_candidate()
    forged = build_attestation(
        candidate, seed=UNTRUSTED_PRODUCER_SEED, producer_key_id=PRODUCER_KEY_ID
    )
    assert forged.digest() == FROZEN_REFUSED_ATTESTATION_DIGEST
    assert _independent_digest(forged.to_canonical_dict()) == (
        FROZEN_REFUSED_ATTESTATION_DIGEST
    )


def test_the_refused_attestation_pins_its_exact_refusal():
    """F-8: the refusal set is pinned by member, and mints nothing."""

    candidate = build_candidate()
    forged = build_attestation(
        candidate, seed=UNTRUSTED_PRODUCER_SEED, producer_key_id=PRODUCER_KEY_ID
    )
    result = build_verifier(directory=build_directory(build_anchor())).verify(
        candidate=candidate, attestation=forged, as_of=AS_OF
    )

    assert result.verified_attestation is None
    assert result.refusal.outcome is FROZEN_REFUSAL_OUTCOME


def test_the_refused_and_verified_fixtures_differ_only_in_the_signature():
    """F-9: the two fixtures are byte-identical apart from the signature bytes."""

    candidate = build_candidate()
    verified = build_attestation(candidate, seed=TRUSTED_PRODUCER_SEED)
    refused = build_attestation(
        candidate, seed=UNTRUSTED_PRODUCER_SEED, producer_key_id=PRODUCER_KEY_ID
    )

    assert verified.signed_bytes() == refused.signed_bytes()
    assert verified.signing_payload_digest == refused.signing_payload_digest
    assert verified.signature != refused.signature
    assert verified.digest() != refused.digest()


# --------------------------------------------------------------------------------------- #
# Pre-existing values: asserted, never re-pinned
# --------------------------------------------------------------------------------------- #


def test_the_phase_5a_candidate_digest_is_unchanged():
    """F-10: Phase 5A's own frozen candidate digest still reproduces exactly."""

    assert build_candidate().candidate_digest == PHASE_5A_CANDIDATE_DIGEST


def test_the_phase_5a_frozen_producer_signing_payload_digest_is_unchanged():
    """F-11: the v1 payload digest the ratified brief names is untouched by v2."""

    projection = P5A.build_projection()
    v1 = P5A.build_attestation(recommendation_digest=projection.recommendation_digest)
    assert v1.signing_payload_digest == (
        PHASE_5A_FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST
    )
    assert _independent_digest(v1.signing_payload()) == (
        PHASE_5A_FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST
    )


def test_no_v2_digest_collides_with_any_v1_digest():
    """F-12: domain separation, checked as an actual inequality over every frozen value."""

    v2_values = {
        FROZEN_V2_SIGNING_PAYLOAD_DIGEST,
        FROZEN_V2_ATTESTATION_DIGEST,
        FROZEN_VERIFIED_ARTIFACT_DIGEST,
        FROZEN_ANCHOR_COORDINATE_DIGEST,
        FROZEN_ANCHOR_RECORD_DIGEST,
        FROZEN_REFUSED_ATTESTATION_DIGEST,
    }
    v1_values = {
        PHASE_5A_CANDIDATE_DIGEST,
        PHASE_5A_FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST,
    }
    assert v2_values & v1_values == set()
    assert len(v2_values) == 6, "two frozen v2 fixtures collided"


def test_every_frozen_digest_is_in_the_one_canonical_format():
    """F-13: one digest spelling in this distribution — ``sha256:`` plus 64 lowercase hex."""

    from ugence_cloud_scaling_producer_attestation import is_canonical_digest

    for value in (
        FROZEN_V2_SIGNING_PAYLOAD_DIGEST,
        FROZEN_V2_ATTESTATION_DIGEST,
        FROZEN_VERIFIED_ARTIFACT_DIGEST,
        FROZEN_ANCHOR_COORDINATE_DIGEST,
        FROZEN_ANCHOR_RECORD_DIGEST,
        FROZEN_REFUSED_ATTESTATION_DIGEST,
        PHASE_5A_CANDIDATE_DIGEST,
        PHASE_5A_FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST,
    ):
        assert is_canonical_digest(value), value


# ======================================================================================= #
# The superseded Phase 5B-0A digests are NEGATIVE anchors.
# ======================================================================================= #


def test_the_superseded_verified_artifact_digest_is_never_produced_again():
    """F-N1: the artifact no longer names a producer as independently verified.

    The superseded digest covered a canonical field called ``verified_producer_id``.
    Producing it again would mean that name — and the claim it makes — had come back.

    This property pins the *outcome*. It deliberately does not attribute the movement to
    the rename, which is only one of its four canonical causes;
    :func:`test_the_verified_artifact_digest_moved_for_all_four_reasons` attributes it.
    """

    candidate = build_candidate()
    result = build_verifier().verify(
        candidate=candidate,
        attestation=build_attestation(candidate),
        as_of=AS_OF,
    )
    artifact = result.verified_attestation
    assert artifact is not None
    assert artifact.artifact_digest != SUPERSEDED_VERIFIED_ARTIFACT_DIGEST
    assert artifact.artifact_digest != SUPERSEDED_PRE_R12B_VERIFIED_ARTIFACT_DIGEST
    assert artifact.artifact_digest == FROZEN_VERIFIED_ARTIFACT_DIGEST
    assert "attested_producer_id" in artifact.digest_payload()
    assert "verified_producer_id" not in artifact.digest_payload()


#: The four canonical fields of ``VerifiedProducerAttestation.digest_payload()`` that the
#: remediation changed, each mapped to the value it carried before. Reverting all four
#: reconstructs the superseded bytes exactly; that is the attribution claim, in data.
_SUPERSEDED_ARTIFACT_FIELDS = {
    # (1) the rename. Independent of the capability correction.
    "attested_producer_id": ("verified_producer_id", None),
    # (2)-(4) all three follow from the dedicated capability replacing EVIDENCE_PRODUCTION.
    "trust_anchor_capability": (None, "EVIDENCE_PRODUCTION"),
    "trust_anchor_coordinate_digest": (None, SUPERSEDED_ANCHOR_COORDINATE_DIGEST),
    "trust_anchor_record_digest": (None, SUPERSEDED_ANCHOR_RECORD_DIGEST),
}

#: A fifth difference, from a different cause and a different phase: 5B-1 moved the Phase 5A
#: candidate digest, and this artifact binds it. Kept out of the map above so the four-way
#: attribution keeps saying what it said — those four are the 5B-0A remediation's — and
#: reverted alongside them wherever the superseded *bytes* must be reconstructed.
_PRE_5B1_CANDIDATE_FIELD = {
    "candidate_digest": SUPERSEDED_PRE_5B1_PHASE_5A_CANDIDATE_DIGEST
}


def _revert(payload: dict, fields) -> dict:
    """Rebuild the superseded canonical payload by undoing exactly ``fields``."""

    reverted = dict(payload)
    for field in fields:
        old_name, old_value = _SUPERSEDED_ARTIFACT_FIELDS[field]
        if old_name is not None:
            reverted[old_name] = reverted.pop(field)
        else:
            reverted[field] = old_value
    # Always undone: the pre-5B-1 candidate digest. Reconstructing the superseded bytes means
    # reconstructing the fixture chain they were computed over, and 5B-1 moved that chain.
    reverted.update(_PRE_5B1_CANDIDATE_FIELD)
    return reverted


def test_the_verified_artifact_digest_moved_for_all_four_reasons():
    """F-N1b: attribution, not just detection — the rename alone did not move the digest.

    It is tempting to describe the verified-artifact movement as "the field rename", because
    the rename is the visible edit. That is wrong, and wrong in the direction that matters:
    it would let someone conclude the dedicated capability never reached the artifact's
    canonical bytes, when in fact three of the four changed fields are exactly that.

    The proof is a reconstruction rather than an assertion. Undoing all four changes to the
    live payload reproduces the superseded digest ``39f1b3dd...`` **exactly** — which is only
    possible if those four fields are the complete set of differences — and undoing any three
    of the four does not. Both halves are necessary: the first shows the attribution is
    complete, the second shows every one of the four is required.

    Since 5B-1 the reversion also undoes ``candidate_digest``, which that phase moved when it
    bound the policy coordinate inside the Phase 5A candidate. That is a fifth difference from
    a different phase, not a fifth cause of *this* movement, so it is applied by ``_revert``
    unconditionally and the four-way attribution below still ranges over exactly four.

    Recomputed through ``canonical_digest`` on a plain dict, so nothing here can be satisfied
    by an artifact object carrying a stale digest.
    """

    candidate = build_candidate()
    result = build_verifier().verify(
        candidate=candidate,
        attestation=build_attestation(candidate),
        as_of=AS_OF,
    )
    artifact = result.verified_attestation
    assert artifact is not None
    payload = artifact.digest_payload()

    all_four = tuple(_SUPERSEDED_ARTIFACT_FIELDS)
    assert len(all_four) == 4
    # Sanity: the live payload really does carry all four fields, under their new names
    # and values, so the reversion below is undoing something real.
    for field in all_four:
        assert field in payload
    assert payload["trust_anchor_capability"] == (
        TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION.value
    )

    # Complete: all four together reproduce the superseded bytes.
    assert canonical_digest(_revert(payload, all_four)) == (
        SUPERSEDED_VERIFIED_ARTIFACT_DIGEST
    )
    # Necessary: each one is load-bearing. Reverting the other three is not enough.
    for omitted in all_four:
        partial = tuple(f for f in all_four if f != omitted)
        assert canonical_digest(_revert(payload, partial)) != (
            SUPERSEDED_VERIFIED_ARTIFACT_DIGEST
        ), f"reverting everything except {omitted} still reproduced the superseded digest"

    # And in particular, the claim the audit corrected: the rename on its own does not.
    assert canonical_digest(_revert(payload, ("attested_producer_id",))) != (
        SUPERSEDED_VERIFIED_ARTIFACT_DIGEST
    )


def test_the_superseded_anchor_digests_are_never_produced_again():
    """F-N2: the coordinate no longer names the borrowed evidence capability.

    These two digests are the machine-checkable form of the cross-domain finding: they
    are what the coordinate and record hashed to while this package resolved anchors
    under ``EVIDENCE_PRODUCTION``. Reproducing either would mean the borrowed capability
    had returned.
    """

    coordinate = producer_anchor_coordinate(
        issuer=ISSUER_ID, producer_key_id=PRODUCER_KEY_ID
    )
    assert anchor_coordinate_digest(coordinate) != SUPERSEDED_ANCHOR_COORDINATE_DIGEST
    assert anchor_coordinate_digest(coordinate) == FROZEN_ANCHOR_COORDINATE_DIGEST
    assert anchor_record_digest(build_anchor()) != SUPERSEDED_ANCHOR_RECORD_DIGEST
    assert anchor_record_digest(build_anchor()) == FROZEN_ANCHOR_RECORD_DIGEST
    assert coordinate.capability is (
        TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION
    )


def test_only_these_three_phase_5b_0a_digests_moved():
    """F-N3: the remediation moved exactly what it had to, and nothing upstream.

    The v2 signing payload and the v2 attestation are unchanged, because neither the
    capability nor the artifact field name is inside the signed bytes. If either had
    moved, the signing contract itself would have changed and every issued attestation
    would have been invalidated.
    """

    candidate = build_candidate()
    attestation = build_attestation(candidate)
    assert _independent_digest(attestation.signing_payload()) == (
        FROZEN_V2_SIGNING_PAYLOAD_DIGEST
    )
    assert _independent_digest(attestation.to_canonical_dict()) == (
        FROZEN_V2_ATTESTATION_DIGEST
    )
    assert candidate.candidate_digest == PHASE_5A_CANDIDATE_DIGEST
    assert candidate.candidate_digest != SUPERSEDED_PRE_5B1_PHASE_5A_CANDIDATE_DIGEST
    assert candidate.candidate_digest != SUPERSEDED_PRE_R12B_PHASE_5A_CANDIDATE_DIGEST


def test_the_frozen_candidate_payload_reproduces_the_genuine_chain_exactly():
    """F-N4: the sdist's fallback candidate is the chain's candidate, not a lookalike.

    An extracted sdist has no monorepo test trees, so the shipped suite rebuilds the Phase
    5A candidate from this package's frozen payload. That reconstruction is only worth
    anything if it is the *same artifact* the genuine chain produces, and only a checkout —
    where both are reachable at once — can prove it. So this property lives here, and it
    compares the whole dataclass rather than only the digest: a digest match over a subset
    of fields would leave the unhashed remainder free to drift.

    ``REC_TIME`` is compared explicitly because it is the one fixture constant the shipped
    suite reads from the payload instead of from Phase 5A, as the default ``issued_at`` for
    every v2 attestation it mints.
    """

    import _producer_fixtures as F

    assert F.PHASE_5A_CHAIN_AVAILABLE, "this property requires the monorepo test trees"
    genuine = P5A.build_candidate()
    reconstructed = F._candidate_from_frozen_payload()
    assert reconstructed == genuine
    assert reconstructed.candidate_digest == genuine.candidate_digest
    assert reconstructed.candidate_digest == PHASE_5A_CANDIDATE_DIGEST
    assert F.REC_TIME == P5A.REC_TIME
    assert F._canonical_ts(
        F.frozen_payload()["producer_attestation"]["issued_at"]
    ) == P5A.REC_TIME
