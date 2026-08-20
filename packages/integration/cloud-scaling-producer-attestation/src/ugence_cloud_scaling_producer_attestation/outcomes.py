"""The closed producer-authenticity outcome vocabulary. Every non-``VERIFIED`` member is a refusal.

Two properties make this vocabulary load-bearing rather than decorative.

**Security outcomes are distinguished by type, never by message string.** A caller branches
on a :class:`ProducerAuthenticityOutcome` member. Two different failures never share a
member merely because they read alike, and no member is reachable only by parsing prose:
``ProducerAttestationRefusal`` carries the member, and the message exists for humans.

**Unknown is a refusal.** :attr:`ProducerAuthenticityOutcome.INDETERMINATE` is the default
arm of every exhaustive match in this package, and
:attr:`ProducerAuthenticityOutcome.VERIFICATION_UNAVAILABLE` and
:attr:`ProducerAuthenticityOutcome.INVARIANT_VIOLATION` cover the two ways verification can
fail to reach a conclusion at all. None of the three is a success, none of them produces a
:class:`~.verified.VerifiedProducerAttestation`, and there is deliberately no member
meaning "probably fine", "unchecked" or "trusted transport".

There is exactly one success member, and holding it establishes **producer authenticity
only**. It is not authorization. See :mod:`.verified`.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

__all__ = [
    "ProducerAuthenticityOutcome",
    "REFUSAL_OUTCOMES",
    "ANCHOR_LIFECYCLE_OUTCOMES",
]


class ProducerAuthenticityOutcome(str, Enum):
    """The one closed vocabulary for the result of producer-attestation verification."""

    # --- the single success ------------------------------------------------------------
    #: The attestation reconciled with the candidate, the payload was recomputed and
    #: matched byte for byte, a trust anchor resolved at the exact coordinate, it was
    #: usable at the injected instant, and the signature verified under its public key.
    #: Nothing more. It is not an authorization.
    VERIFIED = "VERIFIED"

    # --- admission ---------------------------------------------------------------------
    #: No attestation was supplied. Absence is a refusal, never an unchecked pass.
    ATTESTATION_ABSENT = "ATTESTATION_ABSENT"
    #: An input was not the exact required type. Subclasses and look-alikes land here.
    UNSUPPORTED_EXACT_TYPE = "UNSUPPORTED_EXACT_TYPE"
    #: The attestation is structurally unusable — malformed field, non-NFC identifier,
    #: naive timestamp, or a self-inconsistent signing-payload digest.
    ATTESTATION_MALFORMED = "ATTESTATION_MALFORMED"
    #: The attestation names a schema tag this verifier does not implement. In particular
    #: the frozen Phase 5A v1 tag is refused here: v1 is a different contract.
    UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
    #: The attestation names a signing purpose outside the closed producer-signing set —
    #: a policy-signing purpose presented for producer verification lands here.
    UNSUPPORTED_SIGNING_PURPOSE = "UNSUPPORTED_SIGNING_PURPOSE"
    #: The signature profile is not the one ratified profile, or disagrees with the anchor.
    UNSUPPORTED_PROFILE = "UNSUPPORTED_PROFILE"
    #: The signature encoding is not the one ratified encoding, or disagrees with the anchor.
    UNSUPPORTED_ENCODING = "UNSUPPORTED_ENCODING"
    #: The signature algorithm identifier is outside the closed admitted set.
    UNSUPPORTED_ALGORITHM = "UNSUPPORTED_ALGORITHM"

    # --- reconciliation against the Phase 5A candidate ---------------------------------
    #: The attestation names a different recommendation identifier than the candidate.
    RECOMMENDATION_ID_MISMATCH = "RECOMMENDATION_ID_MISMATCH"
    #: The attestation binds a different recommendation digest than the candidate.
    RECOMMENDATION_DIGEST_MISMATCH = "RECOMMENDATION_DIGEST_MISMATCH"
    #: The attestation names a different tenant than the candidate reconciled.
    WRONG_TENANT = "WRONG_TENANT"
    #: The attestation names a different subject (or subject type) than the candidate.
    WRONG_SUBJECT = "WRONG_SUBJECT"

    # --- trust anchor -------------------------------------------------------------------
    #: No anchor is configured at the exact ``(issuer, key_id, capability)`` coordinate.
    ANCHOR_UNKNOWN = "ANCHOR_UNKNOWN"
    #: A resolver answered with an anchor belonging to a different authority.
    WRONG_AUTHORITY = "WRONG_AUTHORITY"
    #: The resolved anchor is not entitled to the producer-attestation capability.
    WRONG_CAPABILITY = "WRONG_CAPABILITY"
    #: The anchor is administratively disabled.
    ANCHOR_DISABLED = "ANCHOR_DISABLED"
    #: The anchor's key was revoked at or before the injected instant.
    ANCHOR_REVOKED = "ANCHOR_REVOKED"
    #: The injected instant precedes the anchor's ``effective_from``.
    ANCHOR_NOT_YET_VALID = "ANCHOR_NOT_YET_VALID"
    #: The injected instant is at or after the anchor's ``effective_to``.
    ANCHOR_EXPIRED = "ANCHOR_EXPIRED"
    #: The anchor is outside its validity window in a way this package cannot attribute to
    #: either side of it. The default arm of the lifecycle mapping: an unrecognised
    #: lifecycle refusal is a refusal, never a pass.
    ANCHOR_NOT_IN_WINDOW = "ANCHOR_NOT_IN_WINDOW"

    # --- payload and signature -----------------------------------------------------------
    #: The independently recomputed canonical signing payload is not byte-identical to the
    #: representation the attestation claims was signed.
    PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"
    #: The signature is not canonical lowercase base16 of exactly the Ed25519 length.
    MALFORMED_SIGNATURE = "MALFORMED_SIGNATURE"
    #: The signature did not verify under the resolved anchor's public key.
    SIGNATURE_INVALID = "SIGNATURE_INVALID"

    # --- fail-closed terminals ----------------------------------------------------------
    #: A collaborator required to reach a determination could not be used — for example a
    #: resolver or signature verifier that raised. Unavailable is a refusal.
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"
    #: An internal invariant of this package did not hold. A programming failure is a
    #: refusal too: a verifier that cannot trust its own reasoning must not conclude.
    INVARIANT_VIOLATION = "INVARIANT_VIOLATION"
    #: The default arm of every exhaustive match. Unknown fails closed.
    INDETERMINATE = "INDETERMINATE"


#: Every member that is **not** a success. Used to assert, structurally, that the only
#: outcome which can mint a verified artifact is ``VERIFIED``.
REFUSAL_OUTCOMES: Final[frozenset[ProducerAuthenticityOutcome]] = frozenset(
    member for member in ProducerAuthenticityOutcome
    if member is not ProducerAuthenticityOutcome.VERIFIED
)

#: The anchor-lifecycle refusals, as a set, for tests and for documentation.
ANCHOR_LIFECYCLE_OUTCOMES: Final[frozenset[ProducerAuthenticityOutcome]] = frozenset(
    {
        ProducerAuthenticityOutcome.ANCHOR_DISABLED,
        ProducerAuthenticityOutcome.ANCHOR_REVOKED,
        ProducerAuthenticityOutcome.ANCHOR_NOT_YET_VALID,
        ProducerAuthenticityOutcome.ANCHOR_EXPIRED,
        ProducerAuthenticityOutcome.ANCHOR_NOT_IN_WINDOW,
    }
)
