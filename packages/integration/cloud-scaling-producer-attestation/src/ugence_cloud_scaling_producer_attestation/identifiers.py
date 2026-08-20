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
:data:`PRODUCER_ATTESTATION_CAPABILITY` is
``TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION`` — a **dedicated**
capability, added to TEV's trust-anchor contract for this domain and used by nothing else.

An earlier revision of this package borrowed ``EVIDENCE_PRODUCTION`` on the reasoning that
"a producer attestation is the producer role". An independent closure audit showed what
that reasoning missed. The repository deliberately keeps **one** trust-anchor store, so
the capability is not a label on a role — it is the part of the coordinate an anchor is
resolved by. Sharing it made a key provisioned purely to sign Trusted Evidence equally
entitled to attest a capacity recommendation, and the coordinate had no way to tell the
two apart. The audit demonstrated it end to end with a telemetry-agent key that held no
Cloud Scaling grant of any kind.

Domain separation inside the signed bytes does not close that. The schema tag and the
signing purpose stop a *signature* from being replayed across domains; they say nothing
about which *keys* a domain trusts. Neither does ``trust_anchor_set_id``, a naming
convention or deployment documentation: none of them is what the anchor is resolved by.

So the entitlement is now named in the coordinate. The three capabilities are mutually
disjoint and exactly compared, in both directions: a receipt-issuance key cannot verify a
producer attestation here, an evidence-production key cannot either, and the dedicated
capability grants nothing back inside TEV — it produces no evidence and issues no receipt.
One key may hold several of these grants, but each is a separate, explicitly configured
anchor record; nothing derives one from another.

This reuses TEV's **capability vocabulary**, which is payload-neutral, and now extends it
by one member. It does not reuse, and does not imply, TEV's evidence *verifier* — this
package verifies a different payload under its own routine (:mod:`.verification`). TEV
defines the coordinate and verifies nothing under it; it neither admits nor approves a
Cloud Scaling recommendation. Which keys receive the capability is the composition root's
decision, not this package's and not TEV's.
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
#:
#: A **dedicated** capability, not a reused evidence one. An earlier revision of this
#: package resolved anchors under ``EVIDENCE_PRODUCTION``, and an independent closure
#: audit proved the consequence: because the repository deliberately keeps **one**
#: trust-anchor store, a key provisioned purely to sign Trusted Evidence — a telemetry
#: agent, say — was thereby entitled to attest a capacity recommendation. The coordinate
#: could not tell the two signing domains apart, so the entitlement was shared.
#:
#: Domain separation inside the signed bytes does not fix that. The schema tag and the
#: signing purpose stop a *signature* from being replayed across domains; they say
#: nothing about which *keys* a domain trusts. Only the coordinate can carry that, and
#: the capability is the part of the coordinate that names the role.
#:
#: Deliberately **not** substituted for by ``trust_anchor_set_id``, by a naming
#: convention, by the signing purpose alone or by deployment documentation. Those may add
#: separation; none of them is the authority control, because none of them is what the
#: anchor is resolved by.
PRODUCER_ATTESTATION_CAPABILITY: Final[TrustAnchorCapability] = (
    TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION
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
    if PRODUCER_ATTESTATION_CAPABILITY is TrustAnchorCapability.EVIDENCE_PRODUCTION:
        raise ImportError(
            "a Cloud Scaling recommendation attestation must never be verified under the "
            "evidence-production capability. The repository keeps one trust-anchor store, "
            "so sharing that capability makes a key entitled to sign Trusted Evidence "
            "equally entitled to attest a capacity recommendation — the exact cross-domain "
            "privilege reuse the dedicated capability exists to refuse"
        )
    _DEDICATED = TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION
    if PRODUCER_ATTESTATION_CAPABILITY is not _DEDICATED:
        raise ImportError(
            "the producer-attestation capability drifted from the one dedicated Cloud "
            "Scaling capability; this package fails closed rather than resolving anchors "
            "under a capability that names another domain"
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
