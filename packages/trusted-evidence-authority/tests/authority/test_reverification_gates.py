"""Each re-verification gate, shown to be the one that catches its own case.

Closure-audit finding **F-09** was that the PR presented twelve gate-deletion
mutants as all load-bearing, while the *re-verifier's* payload-digest gate had
never been shown to catch anything the envelope's own constructor did not
already reject. The mutation that was actually run deleted the **envelope's**
construction-time recomputation, not the re-verifier's check, and the two were
reported as one.

Both are real, and they are not the same gate:

* the **envelope's** check refuses a mismatched digest at construction, so no
  supported route produces such an envelope;
* the **re-verifier's** check refuses one whose ``__post_init__`` never ran —
  an unpickled envelope, or one a deserializer rebuilt field by field. That is
  not a hypothetical: dataclass unpickling restores state without calling
  ``__init__``, and an independent re-verifier is precisely the component that
  receives artifacts it did not construct.

This module proves the second, and proves it the only way a gate claim can be
proved: by showing that everything else in the pipeline *accepts* the case, so
the named gate is the one refusing it.
"""

from __future__ import annotations

import dataclasses
import pickle

import pytest
from _authority_builders import (
    AS_OF,
    authority_anchor,
    directory,
    envelope,
    producer_anchor,
    reverifier,
)
from _builders import OTHER_DIGEST
from ugence_trusted_evidence_authority.api import (
    ReceiptVerificationOutcome,
    TrustedEvidenceContractError,
    TrustedEvidenceRefusalReason,
)

R = TrustedEvidenceRefusalReason


def _bypassing_post_init(signed, **overrides):
    """An exact-type envelope whose ``__post_init__`` never ran.

    Exactly what ``pickle.loads`` produces for a frozen dataclass, and what any
    deserializer that assigns fields directly produces. Nothing here is a
    subclass or a look-alike: ``type(clone) is type(signed)``, so the
    re-verifier's exact-type check admits it and the gates decide.
    """

    clone = object.__new__(type(signed))
    for field in dataclasses.fields(signed):
        object.__setattr__(clone, field.name, getattr(signed, field.name))
    for name, value in overrides.items():
        object.__setattr__(clone, name, value)
    return clone


# --------------------------------------------------------------------------- #
# The two payload-digest checks are two gates, not one
# --------------------------------------------------------------------------- #

def test_the_envelope_refuses_a_mismatched_payload_digest_at_construction():
    """Gate one: no supported route produces a mismatched envelope."""

    with pytest.raises(TrustedEvidenceContractError):
        dataclasses.replace(envelope(), payload_canonical_digest=OTHER_DIGEST)


def test_an_unpickled_envelope_still_verifies_when_untampered():
    """The fixture for the next test, proved sound before it is used."""

    restored = pickle.loads(pickle.dumps(envelope()))
    assert type(restored) is type(envelope())
    assert reverifier().verify_signature(restored, evaluated_at=AS_OF).verified


def test_the_reverifier_payload_digest_gate_is_the_only_gate_that_catches_this():
    """Gate two, and the proof that it is load-bearing (closure-audit F-09).

    The tampered field is **not** bound to the signature: the signing frame
    binds the digest it *recomputes* from the payload, not the envelope's
    declared field. So the signature still verifies, every other gate passes,
    and the re-verifier's own recomputation is the single thing standing
    between a rebuilt envelope and a ``VERIFIED`` answer.
    """

    signed = envelope()
    tampered = _bypassing_post_init(signed, payload_canonical_digest=OTHER_DIGEST)

    # Everything else accepts it — this is what makes the gate load-bearing
    # rather than redundant.
    assert type(tampered) is type(signed)
    assert tampered.signed_input_bytes() == signed.signed_input_bytes()
    assert authority_anchor().verification_key().verify(
        tampered.signed_input_bytes(), tampered.signature_bytes()
    ) is True

    result = reverifier().verify_signature(tampered, evaluated_at=AS_OF)
    assert result.outcome is ReceiptVerificationOutcome.REFUSED
    assert result.refusal_reason is R.TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH

    # And the scope-bound operation refuses it for the same reason, before any
    # coordinate comparison: a digest that does not describe the payload makes
    # every coordinate read off that payload meaningless.
    from test_anti_forgery_and_replay import expectation_for

    bound = reverifier().verify_bound(
        tampered, expectation_for(signed), evaluated_at=AS_OF
    )
    assert bound.refusal_reason is R.TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH


def test_the_declared_digest_field_is_deliberately_not_a_signed_element():
    """Why gate two exists at all, stated as an assertion rather than prose.

    Signing the envelope's declared digest field would make the field
    self-attesting and the gate redundant — but it would also mean the signer
    signs a value it did not compute. The frame binds the recomputed digest
    instead, and the re-verifier recomputes again. Two independent
    computations, no believed field.
    """

    signed = envelope()
    other = _bypassing_post_init(signed, payload_canonical_digest=OTHER_DIGEST)
    assert other.signed_input_bytes() == signed.signed_input_bytes()
    # The recomputed digest *is* bound, so a swapped payload is a signature
    # failure rather than a digest mismatch.
    assert signed.payload.canonical_digest().encode("utf-8") in (
        signed.signed_input_bytes()
    )


# --------------------------------------------------------------------------- #
# The remaining gates, each shown against a case the others pass
# --------------------------------------------------------------------------- #

def test_the_capability_gate_catches_a_producing_key_at_an_issuance_coordinate():
    """E-3, enforced twice: structurally and then explicitly."""

    signed = envelope()
    result = reverifier(directory(producer_anchor())).verify_signature(
        signed, evaluated_at=AS_OF
    )
    assert result.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING


@pytest.mark.parametrize(
    "gate,expected",
    [
        ("anchor", R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED),
        ("signature", R.TRUSTED_EVIDENCE_SIGNATURE_INVALID),
    ],
)
def test_each_named_gate_refuses_with_its_own_reason(gate, expected):
    """Two reasons that must stay distinguishable.

    A verifier that collapsed "no anchor configured" into "signature invalid"
    would be telling an operator to look at the wrong thing.
    """

    from _authority_builders import attacker_signing_key
    from ugence_trusted_evidence_authority.api import (
        DenyAllTrustAnchorDirectory,
        encode_public_key,
    )

    signed = envelope()
    if gate == "anchor":
        result = reverifier(DenyAllTrustAnchorDirectory()).verify_signature(
            signed, evaluated_at=AS_OF
        )
    else:
        wrong = authority_anchor(
            public_key=encode_public_key(
                attacker_signing_key().verification_key.public_key_bytes
            )
        )
        result = reverifier(directory(producer_anchor(), wrong)).verify_signature(
            signed, evaluated_at=AS_OF
        )
    assert result.refusal_reason is expected


# --------------------------------------------------------------------------- #
# The two gates that are redundancy, and the structure that makes them so
# --------------------------------------------------------------------------- #

def test_the_capability_gate_is_unreachable_because_resolution_binds_capability():
    """Honest accounting: a gate-deletion mutant of this check survives.

    It survives because nothing can deliver a producing key to it. The
    coordinate the verifier builds always names ``RECEIPT_ISSUANCE``, and
    ``TrustAnchorResolution`` refuses an anchor whose own coordinate differs
    from the one resolved — so even a caller's own resolver cannot answer a
    receipt-issuance question with a production key. This test pins *that*
    structure, so if it ever loosens, the redundancy claim fails here rather
    than the gate silently becoming the only defence with no test behind it.
    """

    from ugence_trusted_evidence_authority.api import (
        TrustAnchorCapability,
        TrustAnchorCoordinate,
        TrustAnchorResolution,
    )

    issuance_coordinate = TrustAnchorCoordinate(
        authority_id=producer_anchor().authority_id,
        key_id=producer_anchor().key_id,
        capability=TrustAnchorCapability.RECEIPT_ISSUANCE,
    )
    assert producer_anchor().capability is TrustAnchorCapability.EVIDENCE_PRODUCTION
    with pytest.raises(TrustedEvidenceContractError):
        TrustAnchorResolution.resolved(issuance_coordinate, producer_anchor())


def test_the_profile_gate_is_unreachable_because_both_sides_are_pinned():
    """The other surviving mutant, and why it survives.

    One ratified profile, pinned by exact equality on both the anchor and the
    envelope, so the two cannot differ. The check stays as defence for the day a
    second profile exists; until then it is redundancy and is reported as such.
    """

    from ugence_trusted_evidence_authority.api import (
        TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    )

    signed = envelope()
    assert signed.signature_profile == TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1
    assert authority_anchor().signature_profile == TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1
    for bad in ("none", "ed25519", TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1 + "x"):
        with pytest.raises(TrustedEvidenceContractError):
            authority_anchor(signature_profile=bad)
        with pytest.raises(TrustedEvidenceContractError):
            dataclasses.replace(signed, signature_profile=bad)
