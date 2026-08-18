"""Enumerations for the trusted-evidence contracts.

Every enum is a ``str``-valued ``Enum`` with UPPERCASE values, matching the
repository convention, so canonical serialization is stable and readable.

None of these enums is a trust grant. Constructing a member is a naming act, not
an authority act — ADR §10.2 is explicit that "a lifecycle label carried on the
artifact itself" is **never** proof of verification, and §10.1 says the same for
any caller-settable boolean.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "ApplicabilityDeclaration",
    "DeclaredVerificationOutcome",
    "EvidenceLifecycleState",
    "EvidenceStructuralStatus",
    "EvidenceTrustStage",
    "EVIDENCE_TRUST_STAGE_ORDER",
    "RECEIPT_REPORTABLE_TRUST_STAGES",
]


class EvidenceTrustStage(str, Enum):
    """The six distinct trust stages of ADR §12 — E-10.

    A **vocabulary**, not a claim. Naming a stage does not establish it. The
    stages exist as separate members precisely because ADR E-10 forbids a single
    boolean from collapsing them, and §25.7 records why: one flag cannot
    distinguish "the signature verified" from "the provenance chain is intact"
    from "this is bound to the right tenant" from "this is sufficient for *this*
    policy requirement".

    Stage 6 is requirement-relative
    -------------------------------
    ``POLICY_SUFFICIENT`` is **not a property of the evidence** (§12): the same
    verified evidence may be sufficient for one policy requirement and
    insufficient for another. It is owned by the consuming evaluation engine
    under a Policy Authority requirement — never by TAP, and never by a contract
    in this package. It is enumerated here only so that a request may be
    structurally refused for asking TAP to establish it (see
    :class:`~..requests.EvidenceVerificationRequest`).

    What TEV-1 can establish
    ------------------------
    Exactly ``STRUCTURALLY_CONSTRUCTIBLE``, and only for an object that actually
    constructed. Stages 2-6 are unreachable without a verifier, trust anchors
    and keys — all of which are TEV-2.
    """

    #: §12 stage 1 — parses into a well-formed, schema-known shape. Establishes
    #: nothing about authenticity.
    STRUCTURALLY_CONSTRUCTIBLE = "STRUCTURALLY_CONSTRUCTIBLE"
    #: §12 stage 2 — a trusted key's signature verifies over the exact content
    #: digest. Establishes nothing about where the content came from.
    CRYPTOGRAPHICALLY_AUTHENTIC = "CRYPTOGRAPHICALLY_AUTHENTIC"
    #: §12 stage 3 — the chain of custody from an authorized producer is intact.
    #: Establishes nothing about which system or tenant it describes.
    PROVENANCE_VERIFIED = "PROVENANCE_VERIFIED"
    #: §12 stage 4 — binds this tenant, context, subject and assessed-system
    #: binding. Establishes nothing about whether it is current.
    CONTEXT_SYSTEM_BOUND = "CONTEXT_SYSTEM_BOUND"
    #: §12 stage 5 — within its effective period, fresh and unrevoked at the
    #: caller-supplied instant. Establishes nothing about sufficiency.
    CURRENTLY_VALID = "CURRENTLY_VALID"
    #: §12 stage 6 — satisfies *one particular* policy requirement. Never
    #: transferable to a different requirement, and never TAP's to assert.
    POLICY_SUFFICIENT = "POLICY_SUFFICIENT"


#: The six stages in their ratified ADR §12 order.
#:
#: This is the canonical ordering for any stage sequence in this package: a
#: caller-supplied stage set is normalized into this order before it reaches a
#: digest, so a set expressed in two different orders produces one canonical
#: byte sequence (ADR §22.2, §22.13).
EVIDENCE_TRUST_STAGE_ORDER: tuple = (
    EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
    EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
    EvidenceTrustStage.PROVENANCE_VERIFIED,
    EvidenceTrustStage.CONTEXT_SYSTEM_BOUND,
    EvidenceTrustStage.CURRENTLY_VALID,
    EvidenceTrustStage.POLICY_SUFFICIENT,
)


#: The stages a receipt may report on — ADR §12 stages 1-5.
#:
#: Stage 6 is excluded by ratified rule, not by convenience: §12 states that "a
#: receipt therefore records stages 1-5 and **never asserts stage 6 globally**",
#: because policy sufficiency is requirement-relative and belongs to the
#: consuming evaluation engine under a Policy Authority requirement. A receipt
#: payload naming ``POLICY_SUFFICIENT`` in either its cleared or its
#: not-attempted list is refused.
RECEIPT_REPORTABLE_TRUST_STAGES: tuple = tuple(
    s for s in EVIDENCE_TRUST_STAGE_ORDER if s is not EvidenceTrustStage.POLICY_SUFFICIENT
)


class DeclaredVerificationOutcome(str, Enum):
    """The outcome a receipt payload **declares** — payload content, not proof.

    Every member carries the ``DECLARED_`` prefix deliberately. ADR §10 lists
    "a lifecycle label" and "an unsigned or untrusted verification object" among
    the enumerated non-proofs, and §10.5 extends that to "a structurally valid
    receipt whose signature, key, or trust anchor did not verify". A TEV-1
    payload is exactly such an object: any caller can construct one and write any
    outcome into it. The prefix keeps the reader's eye on the difference between
    *what the payload says* and *what has been established*, which is the whole
    substance of E-3 and E-7.

    Reading a ``DECLARED_ADMITTED`` payload therefore establishes nothing. The
    payload's :attr:`~..receipts.EvidenceVerificationReceiptPayload.structural_status`
    stays ``STRUCTURAL_UNVERIFIED`` and its ``unestablished_trust_stages`` still
    contains ``CRYPTOGRAPHICALLY_AUTHENTIC``, whatever the declared outcome says.

    There is no member meaning "verified by an authority". Reaching that state
    requires TEV-2's signed envelope, its trust anchors and its signature
    verification, none of which exists here.
    """

    #: The declaring verifier states the requested stages cleared. Not a pass:
    #: nothing has checked that the declaration came from a real verifier.
    DECLARED_ADMITTED = "DECLARED_ADMITTED"
    #: The declaring verifier states it refused, with reason codes.
    DECLARED_REFUSED = "DECLARED_REFUSED"
    #: The declaring verifier states it could not decide. ADR §11 — "a verifier
    #: that cannot decide has not verified"; this is a refusal, never a pass.
    DECLARED_INDETERMINATE = "DECLARED_INDETERMINATE"


class EvidenceStructuralStatus(str, Enum):
    """How much a TEV-1 contract actually proves.

    The enum has exactly **one** member because exactly one thing is provable by
    construction. This mirrors, deliberately and verbatim in spirit, the merged
    :class:`ugence_governance_contracts...SystemBindingAuthenticityStatus`,
    whose single ``STRUCTURAL_UNVERIFIED`` member ADR §14.5 cites as the correct
    way to be honest about an unverifiable artifact.

    A second member — an authority-verified status — is deliberately **absent**.
    Admitting one would require a ratified verifier, trust anchors and signature
    verification, which are TEV-2 (ADR §30). Adding it later is additive; adding
    it now would create exactly the caller-constructible "VERIFIED" that ADR
    §10.2 forbids consumers from trusting.
    """

    #: The contract is internally consistent and digest-bound; external
    #: authenticity was never established and is not claimed.
    STRUCTURAL_UNVERIFIED = "STRUCTURAL_UNVERIFIED"


class EvidenceLifecycleState(str, Enum):
    """The lifecycle state an evidence artifact **asserts about itself**.

    Carried for audit and for fail-closed admission — this package never
    *verifies* the state, and a state carried on the artifact is explicitly a
    **non-proof** (ADR §10.2). The members are the ratified nodes of the
    evidence lifecycle drawn in ADR §28, plus the two terminal states §11 names
    as refusal conditions.

    ``VERIFIED`` is deliberately not a member
    ----------------------------------------
    ADR §10.2 lists a ``VERIFIED`` lifecycle label carried on the artifact among
    the enumerated non-proofs, and §28 places verification *outside* the
    artifact's own state — it is an act TAP performs, recorded in a signed
    receipt (E-11), not a word an artifact may apply to itself. A ``VERIFIED``
    member here would be directly constructible by any caller and would be the
    forgery surface E-3 exists to close.

    ``SUPERSEDED`` is deliberately not a member
    -------------------------------------------
    The ratified evidence lifecycle (§28) contains no supersession arrow.
    Supersession appears only in the *benchmark* lifecycle (§29) and is itself
    deferred to DD-4. Inventing an evidence-supersession state would ratify a
    lifecycle model the ADR does not have.

    Every state is constructible for audit — including ``REVOKED`` — because a
    revoked artifact must still be representable in order to be refused. Being
    representable is not being admissible.
    """

    #: §28 — produced or observed by a producer/source.
    PRODUCED = "PRODUCED"
    #: §28 — collected/submitted by a collector. Transport confers no trust
    #: (E-4); this state means only that a collector handled it.
    SUBMITTED = "SUBMITTED"
    #: §28 — registered/retained, immutably and append-only.
    RETAINED = "RETAINED"
    #: §11 row 10 — past its validity; a refusal condition, never a warning.
    EXPIRED = "EXPIRED"
    #: §11 row 15 — revoked; a refusal condition. Terminal.
    REVOKED = "REVOKED"


class ApplicabilityDeclaration(str, Enum):
    """Whether an applicability-scoped coordinate applies, stated explicitly.

    ADR §15 rules, for geography and domain, that a coordinate is "required
    where applicability depends on it; explicitly ``NOT_APPLICABLE`` otherwise —
    **never omitted**", and adds: "*An explicit ``NOT_APPLICABLE`` is a decision
    on the record; an omitted field is not.*" This enum is that decision, made
    unrepresentable-by-omission.

    It distinguishes ``None`` from an empty value structurally: there is no
    ``None`` — a coordinate must declare one of these two members, and the
    declaration is cross-checked against the value it carries.
    """

    #: Applicability depends on this coordinate; a non-blank value is required.
    APPLICABLE = "APPLICABLE"
    #: Applicability does not depend on this coordinate; the value must be
    #: empty. This is a recorded decision, not an omission.
    NOT_APPLICABLE = "NOT_APPLICABLE"
