"""The Phase 5B-0A identifiers, and the import-time separations that keep them apart.

Phase 5A froze a producer-attestation contract at the schema tag
``cloud-scaling-producer-attestation-evidence-1`` and never verified it. Phase 5B-0A does
**not** widen, reinterpret or re-verify that contract. It defines a **new**, separately
tagged contract whose signing payload binds facts v1 does not carry — issuer, tenant,
subject and subject type — because those are exactly the facts a verifier must reconcile
before a signature means anything about *this* recommendation for *this* workload.

Domain separation, and where it lives
-------------------------------------
Separation is carried **inside the signed bytes**, as two ordinary canonical fields:

* :data:`PRODUCER_ATTESTATION_V2_SCHEMA_VERSION` — the contract the bytes belong to;
* :data:`PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE` — what the key was used *for*.

Both are bound in :meth:`~.attestation.ProducerAttestationV2.signing_payload`, so a v1
signature can never verify as a v2 signature (the payloads differ in the schema field
before any other difference), and a signature made for one purpose can never be
reinterpreted as a signature made for another.

Three inequalities are asserted **at import time**, failing closed, following Phase 5A's
``identifiers.py``:

#. the v2 schema tag is not the frozen Phase 5A v1 tag;
#. the v2 signing purpose is not the **D-4 routing purpose**
   ``cloud_scaling.capacity_action`` — they are different kinds of identifier, and a
   collision would let one stand in for the other in an audit record;
#. the v2 signing purpose is not any **policy-signing** purpose — a key entitled to sign a
   controller recommendation must not thereby be entitled to sign policy, and vice versa.

The Policy Authority is a **forbidden import** for this package (it is 5B-0B's dependency,
not 5B-0A's), so the policy-signing purposes are named here as a conservative closed set of
the spellings this repository actually uses. That is deliberately a *widening* of what is
refused, not a narrowing: adding a spelling can only reject more.

Trust-anchor capability, and the ruling behind it
-------------------------------------------------
:data:`PRODUCER_ATTESTATION_CAPABILITY` is TEV's
``TrustAnchorCapability.EVIDENCE_PRODUCTION``. TEV ratifies exactly two capabilities and
exactly one per anchor: ``EVIDENCE_PRODUCTION`` ("the anchor's key signs on behalf of a
**producer**") and ``RECEIPT_ISSUANCE`` ("the anchor's key signs on behalf of the
**verifying authority**"). A Cloud Scaling producer attestation is a producer signing a
claim about its own output, so it is the producer role, and choosing it inherits ADR E-3's
producer/verifier separation for free: a receipt-issuance key physically cannot verify a
producer attestation here, and a producer key physically cannot issue a receipt there.

This reuses TEV's **capability vocabulary**, which is payload-neutral. It does not reuse,
and does not imply, TEV's evidence *verifier* — this package verifies a different payload
under its own routine (:mod:`.verification`).
"""

from __future__ import annotations

from typing import Final

from ugence_cloud_scaling_authorization_contracts import (
    PRODUCER_ATTESTATION_SCHEMA_VERSION as _PHASE_5A_V1_SCHEMA_VERSION,
)
from ugence_cloud_scaling_authorization_contracts import (
    PRODUCER_SIGNING_PURPOSE as _PHASE_5A_V1_SIGNING_PURPOSE,
)
from ugence_cloud_scaling_authorization_contracts import (
    PURPOSE_CAPACITY_ACTION as _D4_ROUTING_PURPOSE,
)
from ugence_cloud_scaling_authorization_contracts import (
    SUBJECT_TYPE_CAPACITY_SUBJECT as _D4_SUBJECT_TYPE,
)
from ugence_trusted_evidence_authority import (
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1 as _TEV_ENCODING_V1,
)
from ugence_trusted_evidence_authority import (
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1 as _TEV_PROFILE_V1,
)
from ugence_trusted_evidence_authority import TrustAnchorCapability

__all__ = [
    "PRODUCER_ATTESTATION_V2_SCHEMA_VERSION",
    "PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE",
    "SUPPORTED_V2_SIGNING_PURPOSES",
    "PRODUCER_ATTESTATION_SIGNATURE_ALGORITHM",
    "SUPPORTED_V2_SIGNATURE_ALGORITHMS",
    "PRODUCER_ATTESTATION_SIGNATURE_PROFILE",
    "PRODUCER_ATTESTATION_SIGNATURE_ENCODING",
    "PRODUCER_ATTESTATION_CAPABILITY",
    "PHASE_5A_V1_SCHEMA_VERSION",
    "KNOWN_POLICY_SIGNING_PURPOSES",
    "SUBJECT_TYPE_CAPACITY_SUBJECT",
    "VERIFICATION_PROFILE",
    "VERIFICATION_PROFILE_VERSION",
]

#: The **new** schema tag. Distinct from Phase 5A's frozen v1 tag, and bound as the first
#: canonical field of every signing payload this package produces or recomputes.
PRODUCER_ATTESTATION_V2_SCHEMA_VERSION: Final[str] = (
    "ugence.cloud-scaling/producer-attestation/v2"
)

#: The frozen Phase 5A v1 tag, re-exported so a caller can name what is *not* verified here.
PHASE_5A_V1_SCHEMA_VERSION: Final[str] = _PHASE_5A_V1_SCHEMA_VERSION

#: The dedicated v2 producer-signing purpose. Versioned alongside the schema so a v1
#: purpose string presented against the v2 contract is a typed refusal rather than a
#: near-miss that happens to work.
PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE: Final[str] = (
    "cloud_scaling.recommendation_producer_attestation.v2"
)

#: The closed set of signing purposes this package will admit. Anything else — including
#: Phase 5A's v1 purpose and every policy-signing purpose — is refused.
SUPPORTED_V2_SIGNING_PURPOSES: Final[frozenset[str]] = frozenset(
    {PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE}
)

#: The signature algorithm identifier, spelled as Phase 5A spells it.
PRODUCER_ATTESTATION_SIGNATURE_ALGORITHM: Final[str] = "ed25519"

#: The closed admitted algorithm set. There is no negotiation and no second member: a menu
#: of algorithms is a menu of downgrade attacks.
SUPPORTED_V2_SIGNATURE_ALGORITHMS: Final[frozenset[str]] = frozenset(
    {PRODUCER_ATTESTATION_SIGNATURE_ALGORITHM}
)

#: The one ratified Ed25519 signature profile in this repository, re-anchored — never
#: re-minted — from TEV, because it is the profile a :class:`TrustAnchorRecord` carries and
#: a verifier must compare against.
PRODUCER_ATTESTATION_SIGNATURE_PROFILE: Final[str] = _TEV_PROFILE_V1

#: The one ratified signature encoding — canonical lowercase base16.
PRODUCER_ATTESTATION_SIGNATURE_ENCODING: Final[str] = _TEV_ENCODING_V1

#: The capability an anchor must hold to verify a Cloud Scaling producer attestation.
PRODUCER_ATTESTATION_CAPABILITY: Final[TrustAnchorCapability] = (
    TrustAnchorCapability.EVIDENCE_PRODUCTION
)

#: The D-4 ratified subject type, re-anchored from Phase 5A. A v2 attestation must name it.
SUBJECT_TYPE_CAPACITY_SUBJECT: Final[str] = _D4_SUBJECT_TYPE

#: The named verification procedure a verified artifact records having been reached under.
VERIFICATION_PROFILE: Final[str] = "ugence.cloud-scaling/producer-authenticity/v1"

#: Its version. Bound into the verified artifact so a determination names the exact routine.
VERIFICATION_PROFILE_VERSION: Final[str] = "1"

#: Conservative closed set of policy-signing purpose spellings used in this repository.
#: Named locally because Policy Authority is a forbidden import for Phase 5B-0A.
KNOWN_POLICY_SIGNING_PURPOSES: Final[frozenset[str]] = frozenset(
    {
        "ugence.policy_authority.policy_signing",
        "ugence.policy-authority.policy-signing",
        "policy_authority.policy_signing",
        "cloud_scaling.policy_target_binding",
        "cloud_scaling.policy_signing",
    }
)


def _assert_domain_separation() -> None:
    """Fail closed at import if any separation this contract depends on has collapsed.

    Kept as a function so the identical assertions can be re-run as a test at test time,
    following Phase 5A's ``identifiers.py`` and ADR Phase 5 §9.
    """

    if PRODUCER_ATTESTATION_V2_SCHEMA_VERSION == PHASE_5A_V1_SCHEMA_VERSION:
        raise ImportError(
            "the Phase 5B-0A schema tag must not equal Phase 5A's frozen v1 tag "
            f"{PHASE_5A_V1_SCHEMA_VERSION!r}; a shared tag would let a v1 attestation be "
            "presented as a verified v2 attestation, which is the exact widening "
            "Phase 5B-0A must not perform"
        )
    if PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE == _D4_ROUTING_PURPOSE:
        raise ImportError(
            "the producer-signing purpose must not equal the D-4 routing purpose "
            f"{_D4_ROUTING_PURPOSE!r}; they are different kinds of identifier and a "
            "collision would let one stand in for the other in an audit record"
        )
    if PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE in KNOWN_POLICY_SIGNING_PURPOSES:
        raise ImportError(
            "the producer-signing purpose must not be a policy-signing purpose; a key "
            "entitled to sign a controller recommendation must not thereby be entitled "
            "to sign policy"
        )
    if SUPPORTED_V2_SIGNING_PURPOSES & KNOWN_POLICY_SIGNING_PURPOSES:
        raise ImportError(
            "no admitted producer-signing purpose may also be a policy-signing purpose"
        )
    if _PHASE_5A_V1_SIGNING_PURPOSE in SUPPORTED_V2_SIGNING_PURPOSES:
        raise ImportError(
            "Phase 5A's v1 signing purpose must not be admitted against the v2 contract; "
            "v1 is a different payload and was never verified"
        )
    if PRODUCER_ATTESTATION_CAPABILITY is TrustAnchorCapability.RECEIPT_ISSUANCE:
        raise ImportError(
            "a producer attestation must never be verified under the receipt-issuance "
            "capability; that would collapse ADR E-3's producer/verifier separation"
        )
    if PRODUCER_ATTESTATION_SIGNATURE_PROFILE != _TEV_PROFILE_V1:
        raise ImportError(
            "the signature profile drifted from the one ratified TEV profile; Phase "
            "5B-0A fails closed rather than verifying under an unratified profile"
        )
    if PRODUCER_ATTESTATION_SIGNATURE_ENCODING != _TEV_ENCODING_V1:
        raise ImportError("the signature encoding drifted from the one ratified encoding")
    if SUBJECT_TYPE_CAPACITY_SUBJECT != _D4_SUBJECT_TYPE:
        raise ImportError(
            "the subject type drifted from the D-4 ratified Phase 4C value; Phase 5B-0A "
            "fails closed rather than binding an unratified identifier into signed bytes"
        )


_assert_domain_separation()
