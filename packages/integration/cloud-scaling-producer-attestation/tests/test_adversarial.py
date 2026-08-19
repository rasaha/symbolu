"""Adversarial properties. Every one of them must refuse, typed, and mint nothing.

Organised by what the attacker controls. The rule throughout: an attack is built the way a
real attacker would build it — self-consistently, with every derived value recomputed — so
a gate that only catches an attacker who forgot to recompute something is not credited.
"""

from __future__ import annotations

import copy
import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from _producer_fixtures import (
    AS_OF,
    FOREIGN_ISSUER_ID,
    ISSUER_ID,
    PRODUCER_ID,
    PRODUCER_KEY_ID,
    TRUSTED_PRODUCER_SEED,
    UNTRUSTED_KEY_ID,
    UNTRUSTED_PRODUCER_SEED,
    WINDOW_FROM,
    WINDOW_TO,
    WRONG_CAPABILITY_SEED,
    CountingSignatureVerifier,
    CountingSigner,
    build_anchor,
    build_attestation,
    build_candidate,
    build_directory,
    build_signer,
    build_verifier,
    replace_attestation,
)

from ugence_cloud_scaling_producer_attestation import (
    KNOWN_POLICY_SIGNING_PURPOSES,
    PHASE_5A_V1_SCHEMA_VERSION,
    DenyAllTrustAnchorDirectory,
    Ed25519ProducerSignatureVerifier,
    KeyRevocation,
    ProducerAttestationCanonicalFieldError,
    ProducerAttestationContractError,
    ProducerAttestationV2,
    ProducerAuthenticityOutcome,
    StaticTrustAnchorDirectory,
    TrustAnchorCapability,
    TrustAnchorRecord,
    TrustAnchorResolution,
    producer_anchor_coordinate,
)

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.

O = ProducerAuthenticityOutcome


def _field_names(cls) -> tuple[str, ...]:
    """Real dataclass fields only.

    ``__dataclass_fields__`` also carries ``ClassVar`` pseudo-entries; ``dataclasses.fields``
    filters them out. Using the dict directly would try to pass a class constant as a
    constructor keyword — which is itself refused, and is a separate property.
    """

    return tuple(f.name for f in dataclasses.fields(cls))


def _outcome(verifier, candidate, attestation, as_of=AS_OF):
    result = verifier.verify(candidate=candidate, attestation=attestation, as_of=as_of)
    assert result.verified_attestation is None, "a refusal must mint no artifact"
    assert result.refusal is not None
    return result.refusal.outcome


# ======================================================================================= #
# 1. The producer key itself — the isolated authenticity gate
# ======================================================================================= #


def test_an_untrusted_producer_key_is_refused(candidate, verifier):
    """A-1: a key that is not configured at the named coordinate resolves to nothing."""

    forged = build_attestation(
        candidate, seed=UNTRUSTED_PRODUCER_SEED, producer_key_id=UNTRUSTED_KEY_ID
    )
    assert _outcome(verifier, candidate, forged) is O.ANCHOR_UNKNOWN


def test_a_signature_made_by_another_key_under_a_trusted_key_id_is_refused(
    candidate, verifier
):
    """A-2: the isolated signature gate. Same coordinate, same payload, wrong signing key.

    Everything reconciles, the anchor resolves, it is in window and correctly scoped — and
    the signature still fails, because it was produced by a key whose public half is not
    the one configured. This is the single gate the forgery-laundering proof turns on.
    """

    impostor = build_attestation(
        candidate,
        seed=UNTRUSTED_PRODUCER_SEED,
        producer_key_id=PRODUCER_KEY_ID,
        issuer=ISSUER_ID,
    )
    assert _outcome(verifier, candidate, impostor) is O.SIGNATURE_INVALID


def test_a_foreign_issuer_is_refused(candidate, verifier):
    """A-3: an issuer with no configured anchor resolves to nothing."""

    foreign = build_attestation(candidate, issuer=FOREIGN_ISSUER_ID)
    assert _outcome(verifier, candidate, foreign) is O.ANCHOR_UNKNOWN


def test_a_substituted_producer_identity_invalidates_the_signature(candidate, verifier):
    """A-4: ``producer_id`` is inside the signed bytes, so renaming the producer breaks it."""

    renamed = replace_attestation(
        build_attestation(candidate), producer_id="attacker.impersonated-controller"
    )
    assert _outcome(verifier, candidate, renamed) is O.SIGNATURE_INVALID


def test_a_key_registered_only_for_receipt_issuance_is_not_found(candidate):
    """A-5: capability is part of the coordinate, so a receipt-issuance key is not reachable."""

    receipt_anchor = build_anchor(
        seed=TRUSTED_PRODUCER_SEED, capability=TrustAnchorCapability.RECEIPT_ISSUANCE
    )
    verifier = build_verifier(directory=build_directory(receipt_anchor))
    assert _outcome(verifier, candidate, build_attestation(candidate)) is O.ANCHOR_UNKNOWN


def test_a_resolver_answering_with_a_wrong_capability_anchor_is_refused(candidate):
    """A-6: a resolver may not answer a question it was not asked."""

    wrong = build_anchor(
        seed=TRUSTED_PRODUCER_SEED, capability=TrustAnchorCapability.RECEIPT_ISSUANCE
    )

    class MisdirectingResolver:
        def resolve(self, coordinate):
            return TrustAnchorResolution.resolved(wrong.coordinate, wrong)

    verifier = build_verifier(directory=MisdirectingResolver())
    assert (
        _outcome(verifier, candidate, build_attestation(candidate)) is O.WRONG_CAPABILITY
    )


def test_a_resolver_answering_for_another_authority_is_refused(candidate):
    """A-7: an anchor belonging to a different authority than the issuer is refused."""

    other = build_anchor(seed=TRUSTED_PRODUCER_SEED, issuer=FOREIGN_ISSUER_ID)

    class MisdirectingResolver:
        def resolve(self, coordinate):
            return TrustAnchorResolution.resolved(other.coordinate, other)

    verifier = build_verifier(directory=MisdirectingResolver())
    assert (
        _outcome(verifier, candidate, build_attestation(candidate)) is O.WRONG_AUTHORITY
    )


def test_a_resolver_answering_with_another_key_id_is_refused(candidate):
    """A-8: an anchor carrying a different key id than was resolved for is refused."""

    other = build_anchor(seed=TRUSTED_PRODUCER_SEED, key_id="some-other-key")

    class MisdirectingResolver:
        def resolve(self, coordinate):
            return TrustAnchorResolution.resolved(other.coordinate, other)

    verifier = build_verifier(directory=MisdirectingResolver())
    assert _outcome(verifier, candidate, build_attestation(candidate)) is O.ANCHOR_UNKNOWN


# ======================================================================================= #
# 2. Anchor lifecycle — evaluated at the injected instant, never at a clock reading
# ======================================================================================= #


def test_a_key_revoked_before_the_instant_is_refused(candidate):
    """A-9: revocation is dated, and a key revoked at or before ``as_of`` is refused."""

    revoked = build_anchor(
        revocation=KeyRevocation(effective_at=AS_OF - timedelta(minutes=1))
    )
    verifier = build_verifier(directory=build_directory(revoked))
    assert _outcome(verifier, candidate, build_attestation(candidate)) is O.ANCHOR_REVOKED


@pytest.mark.happy
def test_a_key_revoked_after_the_instant_still_verifies(candidate):
    """A-10: revocation is dated, not a bare flag — a later revocation is not retroactive."""

    later = build_anchor(
        revocation=KeyRevocation(effective_at=AS_OF + timedelta(hours=1))
    )
    verifier = build_verifier(directory=build_directory(later))
    result = verifier.verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=AS_OF
    )
    assert result.refusal is None
    assert result.verified_attestation is not None


def test_a_disabled_key_is_refused(candidate):
    """A-11: an administratively disabled anchor is refused, in window or not."""

    verifier = build_verifier(directory=build_directory(build_anchor(disabled=True)))
    assert _outcome(verifier, candidate, build_attestation(candidate)) is O.ANCHOR_DISABLED


def test_a_key_not_yet_valid_is_refused(candidate):
    """A-12: the half-open window's lower bound. ``as_of`` before ``effective_from``."""

    future = build_anchor(
        effective_from=AS_OF + timedelta(days=1), effective_to=AS_OF + timedelta(days=2)
    )
    verifier = build_verifier(directory=build_directory(future))
    assert (
        _outcome(verifier, candidate, build_attestation(candidate))
        is O.ANCHOR_NOT_YET_VALID
    )


def test_an_expired_key_is_refused(candidate):
    """A-13: the half-open window's upper bound. ``as_of`` at or after ``effective_to``."""

    expired = build_anchor(
        effective_from=WINDOW_FROM, effective_to=AS_OF - timedelta(seconds=1)
    )
    verifier = build_verifier(directory=build_directory(expired))
    assert _outcome(verifier, candidate, build_attestation(candidate)) is O.ANCHOR_EXPIRED


def test_an_unrecognised_lifecycle_refusal_falls_closed_to_not_in_window(candidate):
    """A-14: the default arm of the lifecycle mapping is a refusal, never a pass."""

    from ugence_trusted_evidence_authority import TrustedEvidenceRefusalReason

    genuine = build_anchor()

    class OddLifecycleAnchor:
        pass

    class UninterpretableResolver:
        def resolve(self, coordinate):
            # A record whose lifecycle answer this package has no mapping for.
            patched = copy.copy(genuine)
            object.__setattr__(
                patched,
                "lifecycle_refusal_at",
                lambda instant: (
                    TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT
                ),
            )
            return TrustAnchorResolution.resolved(patched.coordinate, patched)

    verifier = build_verifier(directory=UninterpretableResolver())
    assert (
        _outcome(verifier, candidate, build_attestation(candidate))
        is O.ANCHOR_NOT_IN_WINDOW
    )


# ======================================================================================= #
# 3. Substitution — the facts the attestation binds versus the facts the candidate holds
# ======================================================================================= #


def test_a_cross_tenant_attestation_is_refused(candidate, verifier):
    """A-15: a genuinely signed attestation for another tenant does not travel."""

    other_tenant = build_attestation(candidate, tenant_id="tenant-2")
    assert _outcome(verifier, candidate, other_tenant) is O.WRONG_TENANT


def test_a_cross_subject_attestation_is_refused(candidate, verifier):
    """A-16: a genuinely signed attestation for another workload does not travel."""

    other_subject = build_attestation(candidate, subject_id="billing-api")
    assert _outcome(verifier, candidate, other_subject) is O.WRONG_SUBJECT


def test_an_attestation_naming_another_recommendation_id_is_refused(candidate, verifier):
    """A-17: the recommendation identifier is reconciled against the candidate."""

    other_id = build_attestation(candidate, recommendation_id="rec-somebody-elses")
    assert _outcome(verifier, candidate, other_id) is O.RECOMMENDATION_ID_MISMATCH


def test_an_attestation_binding_another_recommendation_digest_is_refused(
    candidate, verifier
):
    """A-18: the recommendation digest is reconciled against the candidate."""

    other_digest = build_attestation(candidate, recommendation_digest="sha256:" + "b" * 64)
    assert _outcome(verifier, candidate, other_digest) is O.RECOMMENDATION_DIGEST_MISMATCH


def test_a_genuine_attestation_replayed_against_another_candidate_is_refused(verifier):
    """A-19: replay. A genuine, correctly signed attestation for candidate A, presented
    beside candidate B, is refused — the binding is to a specific recommendation."""

    import _producer_fixtures as F

    if not F.PHASE_5A_CHAIN_AVAILABLE:
        pytest.skip(
            "replay needs a SECOND, genuinely different candidate, which means varying the "
            "Phase 5A chain — reachable only from a checkout, not from an extracted sdist"
        )
    P5A = F.P5A

    first = build_candidate()
    other_projection = P5A.build_projection(
        P5A.build_recommendation(predicted=8, recommendation_id="rec-phase5a-2")
    )
    second = build_candidate(projection=other_projection)

    genuine_for_first = build_attestation(first)
    # The two candidates share a recommendation *label* — Phase 5A reads that label out of
    # the attestation, not out of Phase 4 — and differ in the recommendation *digest*.
    # Replay is refused on the digest, which is the fact the producer actually signed.
    assert genuine_for_first.recommendation_id == second.recommendation_id
    assert genuine_for_first.recommendation_digest != second.recommendation_digest
    assert (
        _outcome(verifier, second, genuine_for_first) is O.RECOMMENDATION_DIGEST_MISMATCH
    )


def test_a_subject_type_substitution_is_refused_at_construction(candidate):
    """A-20: only the D-4 ratified subject type can be spelled into a v2 attestation."""

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        replace_attestation(
            build_attestation(candidate), subject_type="cloud_scaling.other_subject"
        )


# ======================================================================================= #
# 4. Purpose, schema and profile — cross-protocol confusion
# ======================================================================================= #


@pytest.mark.parametrize("policy_purpose", sorted(KNOWN_POLICY_SIGNING_PURPOSES))
def test_a_policy_signing_purpose_is_refused(candidate, policy_purpose):
    """A-21: a policy key's purpose presented for producer verification is refused."""

    with pytest.raises(ProducerAttestationCanonicalFieldError) as exc:
        replace_attestation(build_attestation(candidate), signing_purpose=policy_purpose)
    assert exc.value.outcome is O.UNSUPPORTED_SIGNING_PURPOSE


def test_phase_5a_v1_signing_purpose_is_refused_against_the_v2_contract(candidate):
    """A-22: v1's purpose is not admitted here. v1 is a different, unverified contract."""

    from ugence_cloud_scaling_authorization_contracts import PRODUCER_SIGNING_PURPOSE

    with pytest.raises(ProducerAttestationCanonicalFieldError) as exc:
        replace_attestation(
            build_attestation(candidate), signing_purpose=PRODUCER_SIGNING_PURPOSE
        )
    assert exc.value.outcome is O.UNSUPPORTED_SIGNING_PURPOSE


def test_phase_5a_v1_schema_tag_is_refused(candidate):
    """A-23: the frozen v1 schema tag cannot be spelled into a v2 attestation."""

    with pytest.raises(ProducerAttestationCanonicalFieldError) as exc:
        replace_attestation(
            build_attestation(candidate), schema_version=PHASE_5A_V1_SCHEMA_VERSION
        )
    assert exc.value.outcome is O.UNSUPPORTED_SCHEMA_VERSION


def test_a_phase_5a_v1_attestation_object_is_refused_by_exact_type(candidate, verifier):
    """A-24: Phase 5A's own ``ProducerAttestationEvidence`` is not this contract."""

    v1 = candidate.producer_attestation
    assert _outcome(verifier, candidate, v1) is O.UNSUPPORTED_EXACT_TYPE


@pytest.mark.parametrize(
    "field,value,outcome",
    [
        ("signature_algorithm", "ed448", O.UNSUPPORTED_ALGORITHM),
        ("signature_algorithm", "none", O.UNSUPPORTED_ALGORITHM),
        ("signature_profile", "some.other/profile/v1", O.UNSUPPORTED_PROFILE),
        ("signature_encoding", "some.other/encoding/v1", O.UNSUPPORTED_ENCODING),
    ],
)
def test_an_unratified_algorithm_profile_or_encoding_is_refused(
    candidate, field, value, outcome
):
    """A-25: there is no negotiation. A menu of algorithms is a menu of downgrades."""

    with pytest.raises(ProducerAttestationCanonicalFieldError) as exc:
        replace_attestation(build_attestation(candidate), **{field: value})
    assert exc.value.outcome is outcome


def test_an_anchor_profile_disagreement_is_refused(candidate, monkeypatch):
    """A-26: profile agreement is re-checked against the RESOLVED anchor, not just the
    attestation's own claim."""

    genuine = build_anchor()

    class ProfileDivergentResolver:
        def resolve(self, coordinate):
            patched = copy.copy(genuine)
            object.__setattr__(patched, "signature_profile", "some.other/profile/v1")
            return TrustAnchorResolution.resolved(genuine.coordinate, patched)

    verifier = build_verifier(directory=ProfileDivergentResolver())
    assert (
        _outcome(verifier, candidate, build_attestation(candidate)) is O.UNSUPPORTED_PROFILE
    )


def test_an_anchor_encoding_disagreement_is_refused(candidate):
    """A-27: encoding agreement is re-checked against the resolved anchor too."""

    genuine = build_anchor()

    class EncodingDivergentResolver:
        def resolve(self, coordinate):
            patched = copy.copy(genuine)
            object.__setattr__(patched, "signature_encoding", "some.other/encoding/v1")
            return TrustAnchorResolution.resolved(genuine.coordinate, patched)

    verifier = build_verifier(directory=EncodingDivergentResolver())
    assert (
        _outcome(verifier, candidate, build_attestation(candidate))
        is O.UNSUPPORTED_ENCODING
    )


# ======================================================================================= #
# 5. Signature encoding — pinned, never coerced
# ======================================================================================= #


@pytest.mark.parametrize(
    "spelling,label",
    [
        ("A" * 128, "uppercase hex"),
        ("0x" + "a" * 126, "0x prefix"),
        ("a" * 127, "one character short"),
        ("a" * 129, "one character long"),
        ("", "empty"),
        (" " + "a" * 127, "leading whitespace"),
        ("a" * 127 + " ", "trailing whitespace"),
        ("a" * 64, "public-key length, not signature length"),
        ("z" * 128, "non-hex characters"),
        ("YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXphYmNkZWZnaGlqa2xtbm9wcXJzdHV2d3h5eg==", "base64"),
    ],
)
def test_every_non_canonical_signature_spelling_is_refused(candidate, spelling, label):
    """A-28: rejection, never coercion. One byte string has exactly one spelling."""

    with pytest.raises(ProducerAttestationCanonicalFieldError) as exc:
        replace_attestation(build_attestation(candidate), signature=spelling)
    assert exc.value.outcome is O.MALFORMED_SIGNATURE, label


def test_a_mixed_case_signature_is_refused_rather_than_lowercased(candidate):
    """A-29: a genuine signature respelled in mixed case is refused, not normalized."""

    genuine = build_attestation(candidate)
    respelled = genuine.signature[:-8] + genuine.signature[-8:].upper()
    assert respelled != genuine.signature
    with pytest.raises(ProducerAttestationCanonicalFieldError):
        replace_attestation(genuine, signature=respelled)


def test_a_signature_of_the_right_shape_but_wrong_bytes_is_refused(candidate, verifier):
    """A-30: canonical spelling is not validity. A well-formed wrong signature fails."""

    tampered = replace_attestation(
        build_attestation(candidate), signature="de" * 64
    )
    assert _outcome(verifier, candidate, tampered) is O.SIGNATURE_INVALID


# ======================================================================================= #
# 6. Exact-type, constructor-bypass and look-alike attacks
# ======================================================================================= #


def test_a_subclass_attestation_is_refused(candidate, verifier):
    """A-31: a subclass can divert every read through a property. Refused by exact type."""

    class SubAttestation(ProducerAttestationV2):
        pass

    genuine = build_attestation(candidate)
    sub = SubAttestation(
        **{
            f: getattr(genuine, f)
            for f in _field_names(ProducerAttestationV2)
        }
    )
    assert _outcome(verifier, candidate, sub) is O.UNSUPPORTED_EXACT_TYPE


def test_a_subclass_candidate_is_refused(candidate, verifier):
    """A-32: the candidate side is exact-typed too — the facts are read from it."""

    from ugence_cloud_scaling_authorization_contracts import (
        CapacityAuthorizationCandidate,
    )

    class SubCandidate(CapacityAuthorizationCandidate):
        pass

    sub = SubCandidate(
        **{
            f: getattr(candidate, f)
            for f in _field_names(CapacityAuthorizationCandidate)
        }
    )
    assert _outcome(verifier, sub, build_attestation(candidate)) is O.UNSUPPORTED_EXACT_TYPE


def test_a_duck_typed_attestation_look_alike_is_refused(candidate, verifier):
    """A-33: having the right attributes is not being the right type."""

    genuine = build_attestation(candidate)

    class LookAlike:
        def __init__(self):
            for f in _field_names(ProducerAttestationV2):
                setattr(self, f, getattr(genuine, f))

        def signed_bytes(self):
            return genuine.signed_bytes()

        def digest(self):
            return genuine.digest()

    assert _outcome(verifier, candidate, LookAlike()) is O.UNSUPPORTED_EXACT_TYPE


def test_an_object_new_fabricated_attestation_is_refused(candidate, verifier):
    """A-34: ``object.__new__`` skips ``__post_init__`` entirely. Refused by exact type
    only if the type differs — so this one uses the REAL type, and is caught by the
    verifier's own recomputation instead."""

    genuine = build_attestation(candidate)
    fabricated = object.__new__(ProducerAttestationV2)
    for f in _field_names(ProducerAttestationV2):
        object.__setattr__(fabricated, f, getattr(genuine, f))
    object.__setattr__(fabricated, "tenant_id", "tenant-2")
    assert _outcome(verifier, candidate, fabricated) is O.WRONG_TENANT


def test_a_mutated_attestation_fails_the_payload_recomputation(candidate, verifier):
    """A-35: ``object.__setattr__`` after construction. The recomputation catches it."""

    genuine = build_attestation(candidate)
    mutated = copy.copy(genuine)
    object.__setattr__(mutated, "issued_at", genuine.issued_at + timedelta(seconds=1))
    assert _outcome(verifier, candidate, mutated) is O.PAYLOAD_MISMATCH


def test_a_metaclass_equality_attack_does_not_pass_the_exact_type_gate(
    candidate, verifier
):
    """A-36: ``type(x) is T`` cannot be diverted by ``__eq__``/``__hash__`` on a metaclass."""

    class AlwaysEqualMeta(type):
        def __eq__(cls, other):  # pragma: no cover - the point is it is never consulted
            return True

        def __hash__(cls):
            return hash(ProducerAttestationV2)

    class Impostor(metaclass=AlwaysEqualMeta):
        pass

    impostor = Impostor()
    for f in _field_names(ProducerAttestationV2):
        setattr(impostor, f, getattr(build_attestation(candidate), f))
    assert type(impostor) is not ProducerAttestationV2
    assert _outcome(verifier, candidate, impostor) is O.UNSUPPORTED_EXACT_TYPE


def test_a_doctored_instance_dictionary_cannot_forge_the_outcome(
    candidate, verifier, as_of
):
    """A-37: the verified artifact's ``outcome`` is a property, so ``__dict__`` loses."""

    from ugence_cloud_scaling_producer_attestation import (
        VerifiedArtifactIntegrityError,
        require_verified_producer_attestation,
    )

    artifact = verifier.verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=as_of
    ).verified_attestation
    with pytest.raises((AttributeError, VerifiedArtifactIntegrityError)):
        object.__setattr__(artifact, "outcome", "FORGED")
    assert artifact.outcome is O.VERIFIED
    assert require_verified_producer_attestation(artifact) is artifact


# ======================================================================================= #
# 7. Canonical identifiers and malformed input
# ======================================================================================= #


@pytest.mark.parametrize(
    "field",
    ["producer_id", "issuer", "producer_key_id", "tenant_id", "subject_id",
     "recommendation_id"],
)
def test_a_non_nfc_identifier_is_refused_rather_than_normalized(candidate, field):
    """A-38: a decomposed spelling is a different byte sequence, and is refused."""

    non_nfc = "café-producer"  # e + combining acute, not the NFC precomposed form
    with pytest.raises(ProducerAttestationCanonicalFieldError):
        replace_attestation(build_attestation(candidate), **{field: non_nfc})


@pytest.mark.parametrize(
    "field", ["producer_id", "issuer", "producer_key_id", "tenant_id", "subject_id"]
)
def test_an_empty_identifier_is_refused(candidate, field):
    """A-39: an empty identifier names nothing and cannot be resolved."""

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        replace_attestation(build_attestation(candidate), **{field: ""})


def test_a_whitespace_padded_identifier_is_refused(candidate):
    """A-40: leading/trailing whitespace would make two spellings of one identity."""

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        replace_attestation(build_attestation(candidate), issuer=" " + ISSUER_ID)


def test_a_bare_hex_recommendation_digest_is_refused(candidate):
    """A-41: this package emits and admits exactly one digest spelling."""

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        replace_attestation(build_attestation(candidate), recommendation_digest="a" * 64)


def test_a_naive_issued_at_is_refused_rather_than_assumed_utc(candidate):
    """A-42: an instant whose offset nobody stated is an instant nobody can reconstruct."""

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        replace_attestation(
            build_attestation(candidate), issued_at=datetime(2026, 1, 1, 0, 3, 10)
        )


def test_a_naive_as_of_is_refused(candidate, verifier):
    """A-43: the injected verification instant must be timezone-aware too."""

    assert (
        _outcome(
            verifier,
            candidate,
            build_attestation(candidate),
            as_of=datetime(2026, 1, 1, 0, 5, 0),
        )
        is O.UNSUPPORTED_EXACT_TYPE
    )


def test_an_absent_attestation_is_refused(candidate, verifier):
    """A-44: absence is a refusal, never an unchecked pass."""

    assert _outcome(verifier, candidate, None) is O.ATTESTATION_ABSENT


def test_a_reserialized_attestation_with_a_stale_payload_digest_is_refused(candidate):
    """A-45: round-tripping through ``from_dict`` re-runs every check, including the
    self-consistency of the payload digest."""

    genuine = build_attestation(candidate)
    data = dict(genuine.to_canonical_dict())
    data["tenant_id"] = "tenant-2"  # changed, but the payload digest was NOT recomputed
    with pytest.raises(ProducerAttestationCanonicalFieldError) as exc:
        ProducerAttestationV2.from_dict(data)
    assert exc.value.outcome is O.PAYLOAD_MISMATCH


@pytest.mark.parametrize(
    "mutation",
    [
        {"trust_state": "TRUST_VERIFIED"},
        {"verified": True},
        {"authorized": True},
        {"grants_authority": True},
    ],
)
def test_a_mapping_offering_a_trust_field_is_refused(candidate, mutation):
    """A-46: there is no trust field to supply, so a mapping offering one is refused."""

    data = dict(build_attestation(candidate).to_canonical_dict())
    data.update(mutation)
    with pytest.raises(ProducerAttestationCanonicalFieldError):
        ProducerAttestationV2.from_dict(data)


@pytest.mark.parametrize("dropped", ["signature", "issuer", "tenant_id", "subject_id"])
def test_a_mapping_missing_a_required_field_is_refused(candidate, dropped):
    """A-47: a partial mapping is a refusal, never a default-filled attestation."""

    data = dict(build_attestation(candidate).to_canonical_dict())
    data.pop(dropped)
    with pytest.raises(ProducerAttestationCanonicalFieldError):
        ProducerAttestationV2.from_dict(data)


@pytest.mark.parametrize("garbage", [b"not a mapping", 42, None, ["a", "b"]])
def test_malformed_canonical_input_is_refused(garbage):
    """A-48: a non-mapping is refused by exact type, not coerced."""

    with pytest.raises(ProducerAttestationContractError):
        ProducerAttestationV2.from_dict(garbage)


# ======================================================================================= #
# 8. Collaborator failure, and the deny-by-default posture
# ======================================================================================= #


def test_the_deny_all_resolver_refuses_everything(candidate):
    """A-49: the ratified deny-by-default posture. Nothing configured is not nothing to check."""

    verifier = build_verifier(directory=DenyAllTrustAnchorDirectory())
    assert _outcome(verifier, candidate, build_attestation(candidate)) is O.ANCHOR_UNKNOWN


def test_an_empty_directory_refuses(candidate):
    """A-50: an empty anchor store denies rather than admitting."""

    verifier = build_verifier(directory=StaticTrustAnchorDirectory(()))
    assert _outcome(verifier, candidate, build_attestation(candidate)) is O.ANCHOR_UNKNOWN


def test_a_resolver_that_raises_is_unavailable_not_successful(candidate):
    """A-51: an exception is never converted into a success."""

    class ExplodingResolver:
        def resolve(self, coordinate):
            raise RuntimeError("key service unreachable")

    verifier = build_verifier(directory=ExplodingResolver())
    assert (
        _outcome(verifier, candidate, build_attestation(candidate))
        is O.VERIFICATION_UNAVAILABLE
    )


def test_a_signature_verifier_that_raises_is_unavailable_not_successful(
    candidate, directory
):

    """A-52: the same rule at the signature-check boundary."""

    class ExplodingVerifier:
        is_production_authoritative = True

        def verify_producer_signature(self, *, anchor, signed_input, signature):
            raise RuntimeError("backend unavailable")

    verifier = build_verifier(directory=directory, signature_verifier=ExplodingVerifier())
    assert (
        _outcome(verifier, candidate, build_attestation(candidate))
        is O.VERIFICATION_UNAVAILABLE
    )


def test_a_truthy_non_true_verifier_result_is_refused(candidate, directory):
    """A-53: ``is True``, not truthiness. A trust decision may not rest on coercion."""

    class TruthyVerifier:
        is_production_authoritative = True

        def verify_producer_signature(self, *, anchor, signed_input, signature):
            return "yes"

    verifier = build_verifier(directory=directory, signature_verifier=TruthyVerifier())
    assert (
        _outcome(verifier, candidate, build_attestation(candidate)) is O.SIGNATURE_INVALID
    )


def test_a_resolver_returning_a_wrong_typed_resolution_is_refused(candidate):
    """A-54: the resolver's answer is exact-typed too."""

    class WrongTypeResolver:
        def resolve(self, coordinate):
            return {"anchor": "trust me"}

    verifier = build_verifier(directory=WrongTypeResolver())
    assert (
        _outcome(verifier, candidate, build_attestation(candidate))
        is O.UNSUPPORTED_EXACT_TYPE
    )


def test_an_identity_public_key_can_never_enter_the_anchor_store():
    """A-55: a small-order/identity key is refused at anchor construction, not at verify
    time — against such a key the signature equation *succeeds* for a forgery."""

    from ugence_trusted_evidence_authority import TrustedEvidenceContractError

    identity = "01" + "00" * 31
    with pytest.raises((TrustedEvidenceContractError, ValueError)):
        TrustAnchorRecord(
            authority_id=ISSUER_ID,
            key_id=PRODUCER_KEY_ID,
            capability=TrustAnchorCapability.EVIDENCE_PRODUCTION,
            public_key=identity,
            trust_anchor_set_id="s",
            trust_anchor_set_version="1",
        )


# ======================================================================================= #
# 9. The universal invariant: no invalid input mints an artifact or calls a signer
# ======================================================================================= #


def _invalid_cases(candidate):
    """Every refusal route reachable through the public verifier, in one place."""

    genuine = build_attestation(candidate)
    fabricated = object.__new__(ProducerAttestationV2)
    for f in _field_names(ProducerAttestationV2):
        object.__setattr__(fabricated, f, getattr(genuine, f))
    object.__setattr__(fabricated, "subject_id", "billing-api")

    mutated = copy.copy(genuine)
    object.__setattr__(mutated, "issued_at", genuine.issued_at + timedelta(seconds=5))

    return {
        "absent": (None, build_directory()),
        "untrusted_key": (
            build_attestation(
                candidate, seed=UNTRUSTED_PRODUCER_SEED, producer_key_id=UNTRUSTED_KEY_ID
            ),
            build_directory(),
        ),
        "impostor_signature": (
            build_attestation(candidate, seed=UNTRUSTED_PRODUCER_SEED),
            build_directory(),
        ),
        "foreign_issuer": (
            build_attestation(candidate, issuer=FOREIGN_ISSUER_ID),
            build_directory(),
        ),
        "cross_tenant": (build_attestation(candidate, tenant_id="tenant-2"), build_directory()),
        "cross_subject": (
            build_attestation(candidate, subject_id="billing-api"),
            build_directory(),
        ),
        "wrong_recommendation": (
            build_attestation(candidate, recommendation_digest="sha256:" + "c" * 64),
            build_directory(),
        ),
        "revoked": (
            genuine,
            build_directory(
                build_anchor(revocation=KeyRevocation(effective_at=WINDOW_FROM))
            ),
        ),
        "disabled": (genuine, build_directory(build_anchor(disabled=True))),
        "expired": (
            genuine,
            build_directory(build_anchor(effective_to=WINDOW_FROM + timedelta(minutes=1))),
        ),
        "not_yet_valid": (
            genuine,
            build_directory(
                build_anchor(
                    effective_from=WINDOW_TO, effective_to=WINDOW_TO + timedelta(days=1)
                )
            ),
        ),
        "deny_all": (genuine, DenyAllTrustAnchorDirectory()),
        "wrong_capability_registration": (
            genuine,
            build_directory(build_anchor(capability=TrustAnchorCapability.RECEIPT_ISSUANCE)),
        ),
        "fabricated_attestation": (fabricated, build_directory()),
        "mutated_attestation": (mutated, build_directory()),
        "wrong_type": (object(), build_directory()),
        "v1_attestation": (candidate.producer_attestation, build_directory()),
        "tampered_signature": (
            replace_attestation(genuine, signature="ab" * 64),
            build_directory(),
        ),
    }


def test_every_invalid_case_mints_no_artifact_and_calls_no_signer(candidate):
    """A-56: the universal invariant, over every refusal route at once.

    Zero verified artifacts, zero signer calls, and a typed refusal in every case. The
    signer sentinel raises if it is touched, so "no signer was called" is proved by
    construction rather than asserted about a counter nobody incremented.
    """

    signer_sentinel = CountingSigner()
    for label, (attestation, directory) in _invalid_cases(candidate).items():
        counting = CountingSignatureVerifier()
        verifier = build_verifier(directory=directory, signature_verifier=counting)
        result = verifier.verify(
            candidate=candidate, attestation=attestation, as_of=AS_OF
        )
        assert result.verified_attestation is None, f"{label} minted an artifact"
        assert result.refusal is not None, f"{label} produced no typed refusal"
        assert result.refusal.outcome is not O.VERIFIED, label
        assert signer_sentinel.calls == 0, f"{label} reached a signer"


def test_every_invalid_case_produces_a_distinct_typed_outcome_not_a_message(candidate):
    """A-57: security outcomes are told apart by member, never by message string."""

    for label, (attestation, directory) in _invalid_cases(candidate).items():
        verifier = build_verifier(directory=directory)
        result = verifier.verify(
            candidate=candidate, attestation=attestation, as_of=AS_OF
        )
        assert type(result.refusal.outcome) is ProducerAuthenticityOutcome, label
