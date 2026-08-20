"""Inbound assertion envelopes — declared signature material, never proof.

Three envelopes carry the three **non-registry** assertions BR-2's four-party
separation (D-02) depends on:

* :class:`BenchmarkPublisherSubmissionEnvelope` — the publisher submits and
  signs. **The sole source of publisher identity in the entire chain.**
* :class:`BenchmarkApprovalEnvelope` — an independent approver supplies an
  authenticated approval, nesting the exact publisher envelope it approves.
* :class:`BenchmarkRevocationEnvelope` — a revoker asserts a revocation, with a
  declared effective time.

The fourth party, the composition root, supplies trust anchors, the clock and
production adapters. It is **never represented as an issuer or a signer in any
payload**, here or in :mod:`.chain`: it configures the registry, it does not
speak in the registry's chain.

Declared signature material, not a valid signature
--------------------------------------------------
Every envelope validates the **encoding** of what it carries: a detached
signature is exactly 128 lowercase hex characters (64 bytes, Ed25519); a key
identifier is a canonical identifier; a signature profile is a member of a
**closed enum, never an unconstrained algorithm string**. An attacker-chosen
algorithm name is the classic downgrade vector — a verifier that reads the
algorithm out of the artifact it is about to verify has already lost — so the
admissible set is fixed at ratification rather than at call time.

None of that verifies anything. Every envelope permanently derives
``signature_verified is False`` and ``admission_established is False`` on top of
§09's five, and **BR-2A implements no signing, no verification and no key
parsing**, and ships no cryptographic dependency. D-03 makes a verified
publisher signature mandatory *before admission*; BR-2B's injected verifier
defaults to exact deny-all, and BR-2C supplies the audited one. Until then
nothing can be admitted, which is the intended state and not a limitation to be
worked around.

The signing frame, specified now so BR-2C need not reinterpret it
------------------------------------------------------------------
An envelope published today must still be verifiable by a verifier written
later, without that verifier having to guess what the signer signed. §11
therefore requires the frame to be specified **completely** at BR-2A. It is,
below and in :data:`BENCHMARK_SIGNING_FRAME_SPECIFICATION`.

The signing input for every profile is::

    SIGNING_INPUT :=  domain_tag_element
                   || version_element
                   || element_1 || element_2 || ... || element_n

where every element — the domain tag and the version included — is encoded as::

    element := uint32_be(len(utf8_bytes)) || utf8_bytes

Length-prefixing every element, including the framing elements, is what makes
the encoding **unambiguous**: without it, two different field tuples can
concatenate to one byte string (``"ab" + "c"`` and ``"a" + "bc"``), and a
signature over one would verify over the other. The prefix is a fixed-width
big-endian ``uint32``, so its own length never has to be parsed.

The element order per profile is pinned in
:data:`BENCHMARK_SIGNING_FRAME_SPECIFICATION` and is **declaration order of the
signed fields**, which is the order the dataclasses declare them.

The ``detached_signature`` field is **excluded** from its own signing input —
a signature cannot cover itself. So is every derived property, because a
derived property is a function of fields already covered.

The frame identifiers are carried **on the artifact**, as digest-participating
fields, so a later verifier reads which frame to verify under rather than
assuming one. They are simultaneously a **closed, pinned vocabulary**: the only
admissible value of each is the constant this package publishes, enforced by
:func:`~._validation.require_pinned_constant`. A caller-chosen frame identifier
would be an unconstrained algorithm string under a different name.

Actor separation is checked where both actors first become reachable
---------------------------------------------------------------------
D-02 rules that publisher approval of its own artifact is insufficient. The
publisher envelope alone cannot check that: it holds one identity. The
**approval envelope** is the first contract in which the approver and the
publisher are both mechanically reachable, so the check belongs there and is
enforced in its constructor — not documented for a later engine to remember.

A BR-1 artifact carrying ``lifecycle_state=APPROVED`` **never** substitutes for
this envelope. ADR B-5 rules that a lifecycle enum on the artifact is not
approval evidence; the artifact's author wrote that enum, and its only effect is
to participate in BR-1's identity digest. D-05 requires the embedded state to be
exactly ``APPROVED`` at admission precisely so the identity digest is a *stable
content address* — that is a digest-stability rule, not an approval one.
``tests/contract/test_envelopes.py`` asserts the non-substitution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from ugence_benchmark_registry import BenchmarkCoordinate

from ._authority import (
    permanently_unverified_authority,
    permanently_unverified_signature,
)
from ._validation import (
    require_aware_datetime,
    require_detached_signature,
    require_digest,
    require_distinct_actors,
    require_enum_member,
    require_exact_type,
    require_identifier,
    require_pinned_constant,
)
from .canonical import (
    BENCHMARK_APPROVAL_ENVELOPE_DIGEST_DOMAIN,
    BENCHMARK_PUBLISHER_SUBMISSION_ENVELOPE_DIGEST_DOMAIN,
    BENCHMARK_REVOCATION_ENVELOPE_DIGEST_DOMAIN,
    _register_contract_type,
    canonical_digest,
)
from .enums import BenchmarkAdmissionOutcome, BenchmarkSignatureProfile
from .errors import BenchmarkRegistryContractError

__all__ = [
    "BENCHMARK_SIGNING_FRAME_VERSION",
    "BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN",
    "BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN",
    "BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN",
    "BENCHMARK_SIGNING_FRAME_SPECIFICATION",
    "BenchmarkPublisherSubmissionEnvelope",
    "BenchmarkApprovalEnvelope",
    "BenchmarkRevocationEnvelope",
]

#: The signing-frame version every BR-2 envelope declares. One version, closed.
BENCHMARK_SIGNING_FRAME_VERSION = "v1"

#: Domain tag framed into a publisher submission signature.
BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN = (
    "ugence.benchmark-registry-authority/publisher-submission-signing-frame/v1"
)

#: Domain tag framed into an approval signature. A **different byte space** from
#: the publisher frame, so a publisher signature can never be replayed as an
#: approval signature or vice versa — which is exactly the four-party separation
#: of D-02 expressed at the cryptographic layer rather than only at the type
#: layer.
BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN = (
    "ugence.benchmark-registry-authority/approval-signing-frame/v1"
)

#: Domain tag framed into a revocation signature. Again a distinct byte space:
#: a revocation is the one assertion that can take a registered artifact away,
#: and it must never be satisfiable by replaying a submission or an approval.
BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN = (
    "ugence.benchmark-registry-authority/revocation-signing-frame/v1"
)

#: The complete, pinned signing-frame specification — framing order, length
#: prefixing, domain tag and version — published so BR-2C's verifier never has
#: to reinterpret an envelope this milestone already published.
#:
#: This is a **specification constant**, not an implementation. Nothing in this
#: package builds a signing input, signs one, or verifies one; the constant
#: exists so that the contract published today is the contract verified later.
BENCHMARK_SIGNING_FRAME_SPECIFICATION: dict = {
    "length_prefix": "uint32_be(len(utf8_bytes)) before every element, framing "
    "elements included, so no two distinct field tuples can concatenate to one "
    "byte string",
    "element_encoding": "UTF-8 bytes of the canonical NFC string form of the "
    "field; enum fields contribute their .value; datetimes contribute the "
    "canonicalization v1 rendering %Y-%m-%dT%H:%M:%S.%fZ after normalization "
    "to UTC",
    "version": BENCHMARK_SIGNING_FRAME_VERSION,
    "excluded": (
        "detached_signature (a signature cannot cover itself); every derived "
        "read-only property (each is a function of fields already covered)"
    ),
    "profiles": {
        BenchmarkSignatureProfile.ED25519_SHA512_V1.value: (
            "Ed25519 (RFC 8032); detached signature carried as exactly 128 "
            "lowercase hex characters"
        ),
    },
    "frames": {
        "BenchmarkPublisherSubmissionEnvelope": {
            "domain": BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
            "element_order": (
                "signing_frame_domain",
                "signing_frame_version",
                "coordinate.benchmark_id",
                "coordinate.benchmark_family",
                "coordinate.benchmark_version",
                "coordinate.scope.kind",
                "coordinate.scope.tenant_id",
                "coordinate.geography.declaration",
                "coordinate.geography.value",
                "coordinate.domain.declaration",
                "coordinate.domain.value",
                "benchmark_identity_digest",
                "benchmark_content_digest",
                "publisher_identity",
                "publisher_key_id",
                "signature_profile",
            ),
        },
        "BenchmarkApprovalEnvelope": {
            "domain": BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
            "element_order": (
                "signing_frame_domain",
                "signing_frame_version",
                "publisher_submission_envelope_digest",
                "approval_authority_identity",
                "approval_authority_key_id",
                "signature_profile",
                "declared_outcome",
                "applicable_policy_ref",
                "validity_from",
                "validity_to",
            ),
            "note": "publisher_submission_envelope_digest is the independently "
            "recomputed canonical digest of the exact nested envelope, never a "
            "caller-supplied field",
        },
        "BenchmarkRevocationEnvelope": {
            "domain": BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
            "element_order": (
                "signing_frame_domain",
                "signing_frame_version",
                "coordinate.benchmark_id",
                "coordinate.benchmark_family",
                "coordinate.benchmark_version",
                "coordinate.scope.kind",
                "coordinate.scope.tenant_id",
                "coordinate.geography.declaration",
                "coordinate.geography.value",
                "coordinate.domain.declaration",
                "coordinate.domain.value",
                "admitted_digest",
                "revoker_identity",
                "revoker_key_id",
                "signature_profile",
                "declared_revocation_reason",
                "effective_at",
            ),
        },
    },
}


@permanently_unverified_signature
@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkPublisherSubmissionEnvelope:
    """A publisher's signed-looking submission. **The sole source of publisher
    identity in the entire chain.**

    Every downstream contract that needs to know who the publisher is reaches
    *through* this envelope rather than accepting a second spelling — that is
    §09's one-source-of-truth rule, and it is why
    :class:`~.chain.BenchmarkSubmissionRecordPayload` has no ``publisher_identity``
    field of its own to disagree with this one.

    Carries **no** ``declared_recorded_at``. A publisher does not observe the
    registry's clock, and D-11 rules that publisher-supplied time is *evidence*,
    never registry time. Recorded time enters the chain at the submission
    record, where the registry is the declarant.

    What this proves: the structure is well formed, the digests are
    single-spelling lowercase sha-256 hex, the signature field is a well-formed
    128-character Ed25519 encoding, the profile is a ratified member, and the
    locator is an exact BR-1 coordinate that already refused every floating
    token, wildcard, range, partial version and build-metadata spelling at its
    own construction.

    What it proves about the publisher: **nothing**.
    """

    #: The exact BR-1 locator. One coordinate, and no second version field
    #: anywhere in this package — :attr:`BenchmarkCoordinate.benchmark_version`
    #: is the single source of truth for the version.
    coordinate: BenchmarkCoordinate

    #: The BR-1 identity digest of the submitted artifact, as the publisher
    #: declares it. Not recomputed here: this package never holds the BR-1
    #: identity object, only the locator and the declared digest of it.
    benchmark_identity_digest: str

    #: ADR §15 row 4's **content digest** — the digest of the benchmark content
    #: itself, which lives outside both packages and which the registry never
    #: authors. A different value with a different owner from the identity
    #: digest above.
    benchmark_content_digest: str

    #: The publisher's declared identity. Declared **here and nowhere else**.
    publisher_identity: str

    #: The declared key identifier. Naming a key is not possessing one, and no
    #: key material, public or otherwise, is carried, parsed or stored.
    publisher_key_id: str

    #: A member of the closed :class:`~.enums.BenchmarkSignatureProfile`.
    signature_profile: BenchmarkSignatureProfile

    #: The pinned publisher signing-frame domain tag. Digest-participating and
    #: closed to one admissible value.
    signing_frame_domain: str

    #: The pinned signing-frame version. Same discipline.
    signing_frame_version: str

    #: A detached signature, exactly 128 lowercase hex characters. Validated as
    #: an encoding; verified by nothing.
    detached_signature: str

    def __post_init__(self) -> None:
        require_exact_type(self.coordinate, BenchmarkCoordinate, "coordinate")
        require_digest(
            self.benchmark_identity_digest, "benchmark_identity_digest"
        )
        require_digest(self.benchmark_content_digest, "benchmark_content_digest")
        require_identifier(self.publisher_identity, "publisher_identity")
        require_identifier(self.publisher_key_id, "publisher_key_id")
        require_enum_member(
            self.signature_profile,
            BenchmarkSignatureProfile,
            "signature_profile",
        )
        require_pinned_constant(
            self.signing_frame_domain,
            BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
            "signing_frame_domain",
            "a publisher submission is signed under the publisher frame only, "
            "so an approval or revocation signature can never be replayed as a "
            "submission signature",
        )
        require_pinned_constant(
            self.signing_frame_version,
            BENCHMARK_SIGNING_FRAME_VERSION,
            "signing_frame_version",
            "one ratified signing-frame version exists",
        )
        require_detached_signature(self.detached_signature, "detached_signature")


@permanently_unverified_signature
@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkApprovalEnvelope:
    """An independent approver's assertion, nesting the **exact** publisher envelope.

    It nests the envelope object itself, not that envelope's digest. That is the
    difference between binding a submission and *claiming* to have bound one: a
    caller-supplied digest field would be an independent spelling an attacker
    could set to anything, and the approval would then attest to a submission
    nobody could reproduce. :attr:`publisher_submission_envelope_digest` is a
    **derived read-only property**, recomputed from the nested object every time
    it is read.

    Carries **no** ``declared_recorded_at``: an approver does not observe the
    registry's clock either. Its :attr:`validity_from`/:attr:`validity_to`
    interval is the approver's own declared validity, half-open and strictly
    ordered, and is not a registry observation.

    Permanently reports that approval authenticity is **not** established.
    """

    #: The **exact** publisher envelope this approval is about. Not its digest.
    publisher_submission_envelope: BenchmarkPublisherSubmissionEnvelope

    #: The approving authority's declared identity. Must differ from the
    #: publisher's — checked here, the first place both are reachable.
    approval_authority_identity: str

    #: The approving authority's declared key identifier.
    approval_authority_key_id: str

    #: A member of the closed :class:`~.enums.BenchmarkSignatureProfile`.
    signature_profile: BenchmarkSignatureProfile

    #: The pinned approval signing-frame domain tag.
    signing_frame_domain: str

    #: The pinned signing-frame version.
    signing_frame_version: str

    #: What the approver declares: ``ADMITTED`` or ``REJECTED``. A declaration,
    #: never a decision the registry made and never one it must honour.
    declared_outcome: BenchmarkAdmissionOutcome

    #: The applicable policy or approval reference the approver acted under.
    applicable_policy_ref: str

    #: Inclusive start of the approver's declared validity interval.
    validity_from: datetime

    #: **Exclusive** end of the declared validity interval — half-open
    #: ``[validity_from, validity_to)``, the same boundary rule BR-1's effective
    #: period uses, stated once and applied identically.
    validity_to: datetime

    #: A detached signature, exactly 128 lowercase hex characters.
    detached_signature: str

    def __post_init__(self) -> None:
        require_exact_type(
            self.publisher_submission_envelope,
            BenchmarkPublisherSubmissionEnvelope,
            "publisher_submission_envelope",
        )
        require_identifier(
            self.approval_authority_identity, "approval_authority_identity"
        )
        require_identifier(
            self.approval_authority_key_id, "approval_authority_key_id"
        )
        require_enum_member(
            self.signature_profile,
            BenchmarkSignatureProfile,
            "signature_profile",
        )
        require_pinned_constant(
            self.signing_frame_domain,
            BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
            "signing_frame_domain",
            "an approval is signed under the approval frame only",
        )
        require_pinned_constant(
            self.signing_frame_version,
            BENCHMARK_SIGNING_FRAME_VERSION,
            "signing_frame_version",
            "one ratified signing-frame version exists",
        )
        require_enum_member(
            self.declared_outcome,
            BenchmarkAdmissionOutcome,
            "declared_outcome",
        )
        require_identifier(self.applicable_policy_ref, "applicable_policy_ref")
        require_aware_datetime(self.validity_from, "validity_from")
        require_aware_datetime(self.validity_to, "validity_to")
        if not self.validity_from < self.validity_to:
            raise BenchmarkRegistryContractError(
                "validity_from must strictly precede validity_to; under the "
                "half-open [validity_from, validity_to) rule an equal or "
                "reversed pair names an interval containing no instant, which "
                "could never be valid — refused, never reordered"
            )
        require_detached_signature(self.detached_signature, "detached_signature")
        # Actor separation. This is the first contract in which the approver and
        # the publisher are both mechanically reachable, so the check lives
        # here: any later and an unseparated artifact would already exist.
        require_distinct_actors(
            self.approval_authority_identity,
            self.publisher_submission_envelope.publisher_identity,
            "approval_authority_identity",
            "publisher_submission_envelope.publisher_identity",
            "D-02's four-party separation: a publisher approving its own "
            "artifact is not an independent approval, and no compromised "
            "single party may move an artifact from submitted to resolvable",
        )

    @property
    def publisher_submission_envelope_digest(self) -> str:
        """The independently recomputed canonical digest of the nested envelope.

        A **derived** property, never a field. Reading it re-canonicalizes the
        exact nested object — which revalidates that object's entire graph
        first — so the value can never disagree with what is actually nested,
        and no caller-supplied spelling of it exists to disagree with.
        """

        return canonical_digest(self.publisher_submission_envelope)

    @property
    def publisher_identity(self) -> str:
        """The publisher identity, derived through the nested envelope.

        One source of truth: this envelope declares no publisher identity of its
        own, so there is no second spelling to reconcile and no conflict to
        detect.
        """

        return self.publisher_submission_envelope.publisher_identity


@permanently_unverified_signature
@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkRevocationEnvelope:
    """A revoker's declared revocation assertion. **Not a registry event.**

    Chain position belongs to :class:`~.chain.BenchmarkRevocationEventPayload`,
    which nests this envelope alongside the exact registration event it revokes.
    This envelope therefore carries **no** ``recorded_at``, **no**
    ``declared_recorded_at`` and **no** ``prev_event_digest``: no field exists
    here merely to be populated later, which §13 requires and §05 enforces
    generally.

    :attr:`effective_at` is the **revoker's own declared** effective time and
    nothing more. D-11 rules that a revocation's effective time is validated
    against registry-observed time and against its own signed record, and that
    it "can never be used to reopen or reverse a revocation". BR-2A performs
    none of that validation, because it reads no clock and holds no registry
    state.

    BR-2A must not — and structurally cannot — validate the signature, read a
    clock, apply the revocation, or make any artifact unresolvable. Nothing here
    is a receipt: "receipt" is the trusted-evidence layer's word under ADR §6.4,
    and no component issues the independent verification receipt validating its
    own action.
    """

    #: The exact BR-1 locator being revoked.
    coordinate: BenchmarkCoordinate

    #: The immutable admitted digest this revocation is against — the content
    #: address D-05 pins by requiring the embedded lifecycle state to be exactly
    #: ``APPROVED`` at admission.
    admitted_digest: str

    #: The revoker's declared identity.
    revoker_identity: str

    #: The revoker's declared key identifier.
    revoker_key_id: str

    #: A member of the closed :class:`~.enums.BenchmarkSignatureProfile`.
    signature_profile: BenchmarkSignatureProfile

    #: The pinned revocation signing-frame domain tag.
    signing_frame_domain: str

    #: The pinned signing-frame version.
    signing_frame_version: str

    #: The revoker's declared reason, as a canonical string. Deliberately not a
    #: member of the BR-2 refusal vocabulary: a revocation is not a refusal of
    #: the revocation, and minting a second closed vocabulary for it would be
    #: introducing a vocabulary this milestone was not authorized to introduce.
    declared_revocation_reason: str

    #: The revoker's **declared** effective time. Never the registry's observed
    #: time, and never interchangeable with a ``declared_recorded_at``.
    effective_at: datetime

    #: A detached signature, exactly 128 lowercase hex characters.
    detached_signature: str

    def __post_init__(self) -> None:
        require_exact_type(self.coordinate, BenchmarkCoordinate, "coordinate")
        require_digest(self.admitted_digest, "admitted_digest")
        require_identifier(self.revoker_identity, "revoker_identity")
        require_identifier(self.revoker_key_id, "revoker_key_id")
        require_enum_member(
            self.signature_profile,
            BenchmarkSignatureProfile,
            "signature_profile",
        )
        require_pinned_constant(
            self.signing_frame_domain,
            BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
            "signing_frame_domain",
            "a revocation is signed under the revocation frame only, so a "
            "submission or approval signature can never be replayed to take a "
            "registered artifact away",
        )
        require_pinned_constant(
            self.signing_frame_version,
            BENCHMARK_SIGNING_FRAME_VERSION,
            "signing_frame_version",
            "one ratified signing-frame version exists",
        )
        require_identifier(
            self.declared_revocation_reason, "declared_revocation_reason"
        )
        require_aware_datetime(self.effective_at, "effective_at")
        require_detached_signature(self.detached_signature, "detached_signature")


for _cls, _domain in (
    (
        BenchmarkPublisherSubmissionEnvelope,
        BENCHMARK_PUBLISHER_SUBMISSION_ENVELOPE_DIGEST_DOMAIN,
    ),
    (BenchmarkApprovalEnvelope, BENCHMARK_APPROVAL_ENVELOPE_DIGEST_DOMAIN),
    (BenchmarkRevocationEnvelope, BENCHMARK_REVOCATION_ENVELOPE_DIGEST_DOMAIN),
):
    _register_contract_type(_cls, _domain, root_canonicalizable=True)
del _cls, _domain
