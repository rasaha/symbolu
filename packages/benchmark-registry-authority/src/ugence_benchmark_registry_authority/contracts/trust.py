"""BR-2C's trust and verification **contracts**. No verifier ships here.

D-24 and D-25 replace the two ``bool``-returning seams BR-2A froze. This module
holds the exact types those rulings require, and **nothing that produces one**:
there is no verifier, no key parser, no trust store, no anchor resolution logic,
no clock read and no cryptographic dependency in this package. §35.1's
engineering blocker on BR-2C stands, and D-32 waives only the distinct-reviewer
requirement, not that.

**The verifier this contract describes does not exist and has not been audited.**
D-32 narrows "independently audited" for BR-2C to an *external cryptographic
audit of the verifier*, makes that audit a hard precondition to any production
use, and forbids any artifact of this package describing the verifier as
audited, independently reviewed or production-ready until it is obtained and
recorded. Nothing here may be read as such a description.

Why a Boolean could not carry this
-----------------------------------
§35.1's BR-2C row requires a verified result to bind *exact artifact digest,
role, key, profile and anchor revision*. A ``bool`` has nowhere to put any of
them, which is the governance half of the blocker D-23 classified and D-24
ruled. A Boolean has a second defect D-21 names directly: it is
**indistinguishable from a cached copy of itself**, so a caller cannot tell a
fresh answer from a reused one. An evidence-bound result is precisely what a
reusable Boolean is not — every field below is a fact about *one* evaluation of
*one* artifact against *one* anchor revision at *one* instant.

Three results, not one
-----------------------
:class:`BenchmarkPublisherVerifiedResult`,
:class:`BenchmarkApprovalVerifiedResult` and
:class:`BenchmarkRevocationVerifiedResult` are **distinct exact types** (D-24),
each pinning its own :class:`~.enums.BenchmarkTrustRole` and owning its own
digest domain. They are not one parameterized type, and they are not
interchangeable: D-26 rules that publisher, approver and revoker occupy
logically separate role-scoped anchor namespaces and that an anchor authorized
for one role never authorizes another automatically. Three separate types means
a function expecting proof about a *revoker* cannot be handed proof about a
publisher — a substitution §17's rule 10 forbids and which a shared type would
make a call-site mistake rather than a compile-time impossibility.

What a verified result is not
------------------------------
D-24: a verified result establishes **cryptographic verification only — never
admission, never registration, never trusted resolution**. Every type here
therefore carries §09's five permanently-``False`` authority derivations,
installed directly on the class with no field, no setter and no subclass hook,
exactly as every envelope and payload does. A result reading
``outcome=VERIFIED`` still reports ``registry_admission_established is False``
and ``trusted_resolution_established is False``, because verifying a signature
is not admitting an artifact and D-01 keeps BR-2D the first phase permitted to
assert that anything *occurred*.

These types are **caller-constructible**, which is why the derivations are not
optional. A caller can write ``outcome=VERIFIED`` into one of these all day; §09
is what keeps that declaration from reading as an authority fact, on exactly the
ground ADR B-5 rules a caller-created verification object is not evidence.

The anchor record, and where anchors live
------------------------------------------
:class:`BenchmarkTrustAnchorRecord` is what the resolution seam resolves (D-25)
— an immutable role-scoped record, never a Boolean entitlement answer. **The
anchor revision is this record's canonical digest**, and no parallel revision
counter is invented: two records differing in any bound field are two revisions
by construction, and there is no counter to increment out of step with content.

D-04 keeps anchor ownership with the composition root and forbids a second
hidden trust store inside the registry. Defining the *type* of a record is not
holding one: this package holds no anchors, mints none, resolves none and
parses no key material. :attr:`BenchmarkTrustAnchorRecord.public_key_material`
is validated as an **encoding** — 64 lowercase hex characters — and its bytes
are never decoded.

Trusted instant, never a clock
-------------------------------
D-28 evaluates against an **explicit trusted instant**, and records the
consequence for D-11 so it is not discovered late: **BR-2C ships no clock, so
the trusted instant is an input to verification, never a clock read.** The
authoritative clock arrives at BR-2D and D-11 is unamended. That is why every
verification seam on :class:`~.ports.BenchmarkApprovalVerifierPort` takes the
instant as a parameter, and why :attr:`evaluated_at` is a *declared* field here
like every other timestamp in this package.

The lifecycle order, and what is derived from what
---------------------------------------------------
D-28 fixes the evaluation order: **revoked, disabled, not yet valid, expired.**
The first two are read from :class:`~.enums.BenchmarkTrustAnchorStatus`; the
last two are derived by comparing the record's half-open
``[validity_from, validity_to)`` interval against the trusted instant. D-28 also
rules that **revocation invalidates prior signatures retroactively while
ordinary key rotation does not**, which is why a revoked anchor refuses at every
instant rather than only at instants after its revocation — and why that rule is
stated on the status member rather than left to an evaluator to remember.

Nothing in this module performs that evaluation. The order is documented and
:data:`BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER` publishes it, for the same
reason :data:`~.envelopes.BENCHMARK_SIGNING_FRAME_SPECIFICATION` publishes the
signing frame: the contract published today is the contract verified later, and
a verifier that had to reinterpret it could reinterpret it differently.

One signature profile
----------------------
D-29's first constraint: BR-2C supports only ``ED25519_SHA512_V1``, the single
ratified member of :class:`~.enums.BenchmarkSignatureProfile`. A second profile
requires its own later ratification and **none is reserved now** — §05 forbids
reserving byte space a future milestone would have to honour or break. Every
profile field here is therefore a member of that closed enum, which today admits
exactly one value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union

from ._authority import permanently_unverified_authority
from ._validation import (
    require_aware_datetime,
    require_canonical_str,
    require_digest,
    require_enum_member,
    require_exact_type,
    require_actor_identity,
    require_key_identifier,
    require_public_key_material,
)
from .canonical import (
    BENCHMARK_APPROVAL_VERIFIED_RESULT_DIGEST_DOMAIN,
    BENCHMARK_PUBLISHER_VERIFIED_RESULT_DIGEST_DOMAIN,
    BENCHMARK_REVOCATION_VERIFIED_RESULT_DIGEST_DOMAIN,
    BENCHMARK_TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    _register_contract_type,
    canonical_digest,
)
from .enums import (
    BenchmarkRegistryFaultClass,
    BenchmarkSignatureProfile,
    BenchmarkTrustAnchorStatus,
    BenchmarkTrustRole,
    BenchmarkVerificationOutcome,
)
from .errors import BenchmarkRegistryContractError
from .reasons import (
    BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES,
    BenchmarkRegistryRefusalReason,
)

__all__ = [
    "BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER",
    "BENCHMARK_VERIFICATION_REFUSAL_REASONS",
    "BENCHMARK_VERIFIED_RESULT_BOUND_FACTS",
    "BenchmarkTrustAnchorRecord",
    "BenchmarkTrustAnchorResolution",
    "BenchmarkPublisherVerifiedResult",
    "BenchmarkApprovalVerifiedResult",
    "BenchmarkRevocationVerifiedResult",
]

#: D-28's ratified trust-anchor evaluation order, published as a specification
#: constant rather than implemented. **Order is load-bearing**: a revoked anchor
#: whose interval has also elapsed refuses as ``TRUST_ANCHOR_REVOKED``, not as
#: ``TRUST_ANCHOR_EXPIRED``, because revocation is retroactive and expiry is not,
#: and reporting the weaker condition would understate what happened.
#:
#: Nothing in this package evaluates this order. It exists so BR-2C's verifier,
#: whenever it is written and audited, does not have to reinterpret a rule that
#: was already ratified.
BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER: tuple = (
    BenchmarkRegistryRefusalReason.TRUST_ANCHOR_REVOKED,
    BenchmarkRegistryRefusalReason.TRUST_ANCHOR_DISABLED,
    BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_YET_VALID,
    BenchmarkRegistryRefusalReason.TRUST_ANCHOR_EXPIRED,
)

#: The **only** two refusals an anchor-resolution outcome may carry (D-34).
#:
#: **Module-private deliberately.** D-34's *Surfaces moved* clause ratifies one
#: new exported type and no second symbol, and D-18 keeps the curated surface a
#: thing that moves by ratification rather than by an author's judgement that a
#: constant would be useful. The constructor enforces the membership and its
#: refusal names both members, so nothing a caller needs is unavailable; a later
#: row may export it, and until one does this stays inside the module.
#:
#: Both name conditions in which **no anchor record exists to return**: the
#: directory answered and held no anchor at the triple, or the directory could
#: not be consulted at all. D-28 rules the second fails closed with **never** a
#: fallback to a cached, default or previously successful answer, and an
#: unreachable directory reading as *no such anchor* is exactly such a
#: substituted default — which is why the two are separate members here rather
#: than one absent value.
#:
#: The four **lifecycle** refusals are deliberately absent. D-27 requires
#: revoked, disabled, not-yet-valid and expired to stay distinguishable, and
#: D-25's seam performs **no lifecycle evaluation**: it returns the record as it
#: stands, with its own status and interval intact, and the verification seam
#: decides those four against the trusted instant on
#: :data:`BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER`. A resolution that could
#: refuse ``TRUST_ANCHOR_EXPIRED`` would be a resolver that had already
#: evaluated, which is the collapse D-25's docstring refuses.
#:
#: Adding a third member is a ratification, not an implementation choice (D-34).
_TRUST_ANCHOR_RESOLUTION_REFUSAL_REASONS: tuple = (
    BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_FOUND,
    BenchmarkRegistryRefusalReason.TRUST_DIRECTORY_UNAVAILABLE,
)

#: The **only** refusal reasons a ``REFUSED`` verified result may carry (D-35):
#: the eleven members classified ``TRUST_AND_AUTHENTICITY``, plus
#: ``INDETERMINATE``. Twelve of the twenty-four; twelve excluded.
#:
#: **Derived from the fault-class map, never written out.** §35.6 makes the
#: vocabulary append-only, and a hand-copied list of twelve would have to be
#: re-edited by hand every time a member is appended — the drift D-35 closed the
#: subtractive option to avoid. Deriving it means the next appended member
#: classifies itself in or out, and D-27 and D-28 already require the
#: classification to be **total**, so there is no member the derivation can miss.
#:
#: Why ``INDETERMINATE`` joins a class it is not in. It is its own fault class
#: (:attr:`~.enums.BenchmarkRegistryFaultClass.INDETERMINATE`), so the trust
#: class alone would exclude it, and D-35 rules it in explicitly rather than
#: leaving it to be read off the map: §35.9's Q-2C-5 records that a resolver
#: becoming unreachable in flight refuses through ``INDETERMINATE`` and so fails
#: closed, which makes it a live verification-time answer. A subset with no
#: fail-closed catch-all would force an undeterminable condition into a specific
#: trust claim, or into no representable answer at all.
#:
#: What is excluded, and why it is not a judgement call. §35.1's BR-2C row
#: forbids the subphase to ship "any storage, and any registry state whatsoever",
#: and nine of the excluded twelve are registry-state facts a phase with no
#: registry state cannot know. ``UNSUPPORTED_SUPERSESSION`` is D-10's
#: out-of-scope refusal, and BR-2 infers no supersession at any phase.
#: ``NOT_FOUND`` and ``NOT_ADMITTED`` are ``READ_NON_DISCLOSURE``, and D-27
#: deliberately places the non-disclosure collapse at a later **external read
#: boundary** rather than in the verification result, so admitting the read
#: vocabulary here would invert D-27.
#:
#: Declaration order is preserved — the enum is iterated, not a set — so a
#: consumer sorting by index under §22.13 reads the same order this vocabulary
#: has everywhere else.
BENCHMARK_VERIFICATION_REFUSAL_REASONS: tuple = tuple(
    reason
    for reason in BenchmarkRegistryRefusalReason
    if BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES[reason]
    in (
        BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY,
        BenchmarkRegistryFaultClass.INDETERMINATE,
    )
)

#: The nine facts D-24 requires every verified result to bind, as the field
#: names carrying them. Published as one list so the three result types, the
#: tests and the contract inventory read a single source rather than three
#: copies that could drift — the defect D-30 and D-31 spent three rounds
#: cleaning out of this package's prose.
BENCHMARK_VERIFIED_RESULT_BOUND_FACTS: tuple = (
    "verified_digest",
    "signer_role",
    "signer_identity",
    "signer_key_id",
    "signature_profile",
    "anchor_record_digest",
    "evaluated_at",
    "outcome",
    "refusal_reason",
)


def _require_pinned_role(
    value: object, expected: BenchmarkTrustRole, name: str
) -> None:
    """Require the role field to be exactly the role this result type is for.

    What makes three types *distinct* rather than three aliases. A publisher
    result whose ``signer_role`` could be set to ``REVOKER`` would reintroduce
    the cross-role substitution D-26 forbids at the one place a type system can
    still catch it, and §17's rule 10 requires the revoking authority to be
    entitled for the exact scope with the publisher never substituted for it.

    Compared with ``is`` against the enum member, so a bare string spelling the
    member's value is refused rather than accepted as equal — ``str`` enum
    members compare equal to their values, and a text match is not membership.
    """

    require_enum_member(value, BenchmarkTrustRole, name)
    if value is not expected:
        raise BenchmarkRegistryContractError(
            f"{name} must be exactly {expected.value} for this result type; "
            "the three verified-result types are distinct exact types, one per "
            "role-scoped anchor namespace (D-24, D-26), and an anchor "
            "authorized for one role never authorizes another automatically"
        )


def _require_outcome_and_reason_agree(
    outcome: object, refusal_reason: object
) -> None:
    """Require the outcome and the refusal reason to be exactly biconditional.

    ``VERIFIED`` carries no reason; ``REFUSED`` carries exactly one. Both other
    combinations are **unconstructible**, not merely discouraged:

    * a ``REFUSED`` result with no reason is a refusal that cannot say why,
      which is the shapeless answer D-24 replaced the Boolean to avoid; and
    * a ``VERIFIED`` result carrying a reason is self-contradictory, and a
      consumer branching on whichever field it happened to read would get two
      different answers from one object.

    D-35 narrows *which* reason. A ``REFUSED`` result carries one of the twelve
    in :data:`BENCHMARK_VERIFICATION_REFUSAL_REASONS` and not merely any member
    of the BR-2 vocabulary. Before that ruling this accepted all twenty-four, so
    a verified result could refuse with ``COORDINATE_SLOT_CONFLICT`` or
    ``STORE_UNAVAILABLE`` — registry-state facts a subphase §35.1 forbids to ship
    "any registry state whatsoever" cannot know — or with ``NOT_FOUND``, whose
    non-disclosure collapse D-27 places at a later external read boundary rather
    than in this result.

    Enforced in the constructor rather than documented for a caller to honour,
    on the same ground the actor-separation check lives in the approval
    envelope's constructor: any later and the inconsistent artifact already
    exists.
    """

    require_enum_member(outcome, BenchmarkVerificationOutcome, "outcome")
    if outcome is BenchmarkVerificationOutcome.VERIFIED:
        if refusal_reason is not None:
            raise BenchmarkRegistryContractError(
                "a VERIFIED result carries no refusal_reason; a result that "
                "both verified and refused is self-contradictory, and a "
                "consumer branching on either field alone would get two "
                "different answers from one object"
            )
        return
    if refusal_reason is None:
        raise BenchmarkRegistryContractError(
            "a REFUSED result must carry exactly one typed refusal_reason from "
            "the BR-2 vocabulary; a refusal that cannot say why is the "
            "shapeless answer D-24 replaced the Boolean verifier result to "
            "eliminate"
        )
    require_enum_member(
        refusal_reason, BenchmarkRegistryRefusalReason, "refusal_reason"
    )
    if refusal_reason not in BENCHMARK_VERIFICATION_REFUSAL_REASONS:
        raise BenchmarkRegistryContractError(
            f"refusal_reason {refusal_reason.value} is not one a verified "
            "result may carry; D-35 admits the eleven members classified "
            "TRUST_AND_AUTHENTICITY and INDETERMINATE, and nothing else — "
            f"{refusal_reason.value} is classified "
            f"{BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES[refusal_reason].value},"
            " which is a fact about registry state, registry scope or a read "
            "boundary that a phase shipping no registry state cannot establish"
        )


def _require_anchor_digest_binding(
    outcome: object, anchor_record_digest: object
) -> None:
    """A ``VERIFIED`` result binds the exact anchor revision it verified against.

    D-24 requires the anchor-record digest among the nine bound facts and D-25
    makes that digest the **anchor revision**. A verification that could not name
    the revision it trusted would leave a consumer unable to tell whether the
    anchor has since been revoked, which is the whole point of binding it.

    :data:`None` is admissible only on a refusal, and only because a refusal can
    precede resolution: ``TRUST_ANCHOR_NOT_FOUND`` and
    ``TRUST_DIRECTORY_UNAVAILABLE`` name conditions in which **no anchor record
    exists to digest**, and inventing a placeholder digest for one would be a
    fabricated revision. A refusal that *did* resolve an anchor — revoked,
    disabled, not yet valid, expired — should carry it, and may.
    """

    if outcome is BenchmarkVerificationOutcome.VERIFIED:
        if anchor_record_digest is None:
            raise BenchmarkRegistryContractError(
                "a VERIFIED result must bind the anchor_record_digest it "
                "verified against; D-25 makes that digest the anchor revision, "
                "and a verification that cannot name the revision it trusted "
                "cannot be re-checked against a later revocation"
            )
        require_digest(anchor_record_digest, "anchor_record_digest")
        return
    if anchor_record_digest is not None:
        require_digest(anchor_record_digest, "anchor_record_digest")


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkTrustAnchorRecord:
    """One immutable role-scoped trust anchor, as the composition root holds it.

    D-25 replaces Boolean entitlement with exact anchor **resolution**: the seam
    resolves this record rather than answering true or false. A Boolean said
    only *entitled* or *not*, so a caller learned nothing about which key, under
    which role, valid over which interval, in which status — and could not
    re-check any of it.

    **The anchor revision is :attr:`anchor_record_digest`**, this record's own
    canonical digest, and no parallel revision counter exists to drift from it
    (D-25). D-05's dual immutable indexing is the repository's existing pattern
    for identity carried by digest rather than by a counter, and this follows it.

    Immutable in three independent ways: the dataclass is frozen, every field is
    an immutable value, and the record has no update path — a changed anchor is a
    **new record with a new revision**, never an edit to this one. That is what
    makes a bound revision meaningful in a verified result.

    Not held here. This package holds no anchors, mints none, resolves none and
    parses no key material (D-04). This is the shape of something the composition
    root owns.
    """

    #: Which role-scoped namespace this anchor lives in. Mandatory and bound,
    #: because D-26 rules the three namespaces logically separate: an anchor
    #: authorized for one role **never** authorizes another automatically, and
    #: a record without a role would make that separation a convention.
    role: BenchmarkTrustRole

    #: The anchor's declared identity within its role namespace.
    identity: str

    #: The declared key identifier. One anchor, one key: an identity holding two
    #: keys is two records with two revisions, which is what keeps a rotation
    #: visible as a revision change rather than an invisible in-place edit.
    key_id: str

    #: The profile this key signs under — a member of the closed
    #: :class:`~.enums.BenchmarkSignatureProfile`, which D-29 keeps at exactly
    #: one ratified member for BR-2C.
    signature_profile: BenchmarkSignatureProfile

    #: Ed25519 public-key material as exactly 64 lowercase hex characters.
    #: Validated as an **encoding** and never decoded: this package parses no key
    #: material and links no cryptographic library.
    public_key_material: str

    #: Inclusive start of the anchor's validity interval.
    validity_from: datetime

    #: **Exclusive** end — half-open ``[validity_from, validity_to)``, the same
    #: boundary rule the approval envelope and BR-1's effective period use,
    #: stated once and applied identically. D-28's third and fourth evaluation
    #: terms are derived from this interval against the trusted instant.
    validity_to: datetime

    #: The anchor's lifecycle status. D-28's first two evaluation terms are read
    #: from here.
    status: BenchmarkTrustAnchorStatus

    #: When the anchor was revoked, or :data:`None` when it was not. Present
    #: **exactly** when :attr:`status` is ``REVOKED``: a revocation time on an
    #: active anchor and a revoked anchor with no revocation time are both
    #: unconstructible, so the two spellings of "was this revoked" can never
    #: disagree. Note that revocation is **retroactive** (D-28), so this time
    #: records *when* it happened and never bounds *what* it invalidates.
    revoked_at: Optional[datetime]

    #: The revoking authority's declared reason, or :data:`None`. Admissible
    #: only alongside :attr:`revoked_at`. Free text by design — this is the
    #: revoker's own words, not a member of the BR-2 refusal vocabulary, which
    #: is the registry's own and is never put into a third party's mouth.
    revocation_reason: Optional[str]

    def __post_init__(self) -> None:
        require_enum_member(self.role, BenchmarkTrustRole, "role")
        require_actor_identity(self.identity, "identity")
        require_key_identifier(self.key_id, "key_id")
        require_enum_member(
            self.signature_profile,
            BenchmarkSignatureProfile,
            "signature_profile",
        )
        require_public_key_material(
            self.public_key_material, "public_key_material"
        )
        require_aware_datetime(self.validity_from, "validity_from")
        require_aware_datetime(self.validity_to, "validity_to")
        if not self.validity_from < self.validity_to:
            raise BenchmarkRegistryContractError(
                "validity_from must strictly precede validity_to; under the "
                "half-open [validity_from, validity_to) rule an equal or "
                "reversed pair names an interval containing no instant, so the "
                "anchor could never be valid at any trusted instant — refused, "
                "never reordered"
            )
        require_enum_member(
            self.status, BenchmarkTrustAnchorStatus, "status"
        )
        if self.status is BenchmarkTrustAnchorStatus.REVOKED:
            if self.revoked_at is None:
                raise BenchmarkRegistryContractError(
                    "a REVOKED anchor must carry revoked_at; a revocation with "
                    "no recorded time cannot be audited, and the two spellings "
                    "of whether this anchor was revoked must never disagree"
                )
            require_aware_datetime(self.revoked_at, "revoked_at")
            if self.revocation_reason is not None:
                require_canonical_str(
                    self.revocation_reason,
                    "revocation_reason",
                    allow_empty=False,
                )
            return
        if self.revoked_at is not None:
            raise BenchmarkRegistryContractError(
                f"status is {self.status.value} but revoked_at is set; a "
                "revocation time on an anchor that is not revoked is a "
                "revocation fact with no revocation, and D-28 gives revocation "
                "retroactive effect that DISABLED deliberately does not carry"
            )
        if self.revocation_reason is not None:
            raise BenchmarkRegistryContractError(
                f"status is {self.status.value} but revocation_reason is set; "
                "a revocation reason without a revocation is an unsupported "
                "claim about an anchor that was never revoked"
            )

    @property
    def anchor_record_digest(self) -> str:
        """The **anchor revision** — this record's canonical digest (D-25).

        A **derived** property, never a field, so no caller-supplied spelling of
        it exists to disagree with the record it claims to identify. Reading it
        re-canonicalizes this record, which revalidates the whole object first,
        so a record corrupted after construction via ``object.__setattr__``
        cannot produce a digest for the state it was forged into.

        This is the value a verified result binds as its
        ``anchor_record_digest``. There is deliberately no counter beside it:
        D-25 rules the revision *is* the digest, so two anchors differing in any
        bound field are two revisions by construction and no increment can fall
        out of step with content.
        """

        return canonical_digest(self)


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkTrustAnchorResolution:
    """The typed outcome of one exact-triple anchor lookup. **Resolves nothing.**

    D-25 replaced Boolean entitlement with anchor *resolution*, and the seam that
    landed with it returned ``Optional[BenchmarkTrustAnchorRecord]``. That
    followed D-25 and D-28 literally — D-25 enumerates exactly one new type and
    D-28 says no further type is minted there — but it left a one-bit answer
    wearing a type: a ``None`` could not say whether the directory **answered and
    held no anchor** or **could not be consulted at all**. D-34 rules the seam
    returns this instead.

    Exactly one of :attr:`anchor` and :attr:`refusal_reason` is set, enforced in
    :meth:`__post_init__`. There is no "resolved but also refused" state, no
    "neither" state to read optimistically, and **no Boolean success flag**: a
    caller must branch on which of the two is present. A flag would be a third
    spelling of the same fact, free to disagree with the other two, and D-24
    removed Booleans from these seams for that reason.

    Why the two conditions must stay separate
    ------------------------------------------
    D-28 rules fail-closed on unavailable trust state, with **never** a fallback
    to a cached, default or previously successful verification. An unreachable
    directory that reads as *no such anchor* is a default answer substituted for
    an unavailable one — the precise substitution D-28 forbids — and a verifier
    handed a bare ``None`` could not tell which it had. D-27 requires the anchor
    distinctions preserved in verification and audit results, and locates any
    deliberate collapse at a later **external read boundary**, not at this seam.

    What it does not evaluate
    --------------------------
    Nothing. This carries the record **as it stands**, with its own status and
    validity interval intact, exactly as
    :meth:`~.ports.BenchmarkPublisherTrustDirectoryPort.resolve_anchor`
    describes. It takes **no trusted instant** and performs no lifecycle
    evaluation: were it to filter on the instant, revoked, disabled, not-yet-valid
    and expired would collapse into one indistinguishable absence, which is what
    D-27 requires stay distinguishable. Those four belong to the verification
    seam, which binds its outcome and reason into the verified result.

    Shape copied, code never imported
    ----------------------------------
    ``TrustAnchorResolution`` in the trusted-evidence layer is the ratified
    precedent for a record-XOR-refusal outcome, and this is deliberately the same
    shape. It is **copied and not imported**: ``ugence_trusted_evidence_authority``
    is on this package's forbidden-import list, §23 restricts BR-2 to
    ``governance-contracts``, D-04's fourth constraint forbids importing the
    trusted-evidence layer's trust-anchor directory, and D-22(4) is the ratified
    precedent for copying a shape and not the code.

    Two things are deliberately *not* copied. The precedent's ``resolved()`` and
    ``refused()`` classmethod factories are omitted: §17 forbids a convenience
    resolver, and a classmethod named ``resolved`` on an exported type in a
    package whose exported-function ban lists ``resolve`` is a name no contract
    needs. And neither field carries a default, so the unset half of the XOR is
    written at every call site rather than defaulted into silence — the same rule
    :class:`BenchmarkTrustAnchorRecord`'s ``revoked_at`` follows.

    Not a resolution. Naming the shape of an answer is not answering: this
    package holds no anchors, mints none, resolves none and parses no key
    material (D-04), and no implementation of the seam exists to build one of
    these. It carries §09's five permanently-``False`` authority derivations like
    every other contract here, so a resolution carrying an anchor still reports
    ``trusted_resolution_established is False``.
    """

    #: The role namespace the lookup was made in. Bound because D-26 keeps the
    #: three namespaces logically separate: an anchor authorized for one role
    #: never authorizes another automatically.
    role: BenchmarkTrustRole

    #: The identity the lookup asked for.
    identity: str

    #: The key identifier the lookup asked for.
    key_id: str

    #: The resolved record, or :data:`None` on a refusal. Present **exactly**
    #: when :attr:`refusal_reason` is absent.
    anchor: Optional[BenchmarkTrustAnchorRecord]

    #: Why no usable record was returned, or :data:`None` when one was. Present
    #: **exactly** when :attr:`anchor` is absent, and drawn only from
    #: ``TRUST_ANCHOR_NOT_FOUND`` and ``TRUST_DIRECTORY_UNAVAILABLE``.
    refusal_reason: Optional[BenchmarkRegistryRefusalReason]

    def __post_init__(self) -> None:
        require_enum_member(self.role, BenchmarkTrustRole, "role")
        require_actor_identity(self.identity, "identity")
        require_key_identifier(self.key_id, "key_id")
        if (self.anchor is None) == (self.refusal_reason is None):
            raise BenchmarkRegistryContractError(
                "a trust-anchor resolution carries exactly one of an anchor "
                "record or a typed refusal reason; carrying both would be a "
                "resolved refusal, and carrying neither would be the untyped "
                "silence D-34 replaced Optional[BenchmarkTrustAnchorRecord] to "
                "eliminate"
            )
        if self.refusal_reason is not None:
            require_enum_member(
                self.refusal_reason,
                BenchmarkRegistryRefusalReason,
                "refusal_reason",
            )
            if (
                self.refusal_reason
                not in _TRUST_ANCHOR_RESOLUTION_REFUSAL_REASONS
            ):
                raise BenchmarkRegistryContractError(
                    f"refusal_reason {self.refusal_reason.value} is not one a "
                    "resolution may carry; D-34 admits exactly "
                    "TRUST_ANCHOR_NOT_FOUND and TRUST_DIRECTORY_UNAVAILABLE, "
                    "the two conditions in which no anchor record exists to "
                    "return, and the seam performs no lifecycle evaluation, so "
                    "revoked, disabled, not-yet-valid and expired belong to the "
                    "verification seam and never to this one"
                )
            return
        require_exact_type(self.anchor, BenchmarkTrustAnchorRecord, "anchor")
        mismatched = [
            name
            for name, asked, answered in (
                ("role", self.role, self.anchor.role),
                ("identity", self.identity, self.anchor.identity),
                ("key_id", self.key_id, self.anchor.key_id),
            )
            if asked != answered
        ]
        if mismatched:
            raise BenchmarkRegistryContractError(
                "the resolved anchor answers a different "
                f"{', '.join(mismatched)} than the lookup asked for; a resolver "
                "may not answer a question it was not asked, and D-26 makes the "
                "role part of the question rather than something a shared "
                "physical directory may infer"
            )


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkPublisherVerifiedResult:
    """The publisher seam's exact verified result. Replaces a ``bool`` (D-24).

    Binds the nine facts D-24 requires — listed once in
    :data:`BENCHMARK_VERIFIED_RESULT_BOUND_FACTS` — about **one** evaluation of
    **one** publisher submission envelope against **one** anchor revision at
    **one** trusted instant. That specificity is the point: D-21 records that
    the prohibition on memoizing a verification result holds *regardless of
    return width*, and this type makes a reused answer visibly wrong rather than
    merely disallowed, because a reuse would carry the wrong digest, the wrong
    revision or the wrong instant.

    :attr:`signer_role` is pinned to
    :attr:`~.enums.BenchmarkTrustRole.PUBLISHER` and cannot be set otherwise.

    **Establishes cryptographic verification only** — never admission, never
    registration, never trusted resolution (D-24). All five of §09's authority
    derivations remain permanently ``False`` on every instance, including one
    reading ``outcome=VERIFIED``.

    Produced by nothing in this package: no verifier ships here.
    """

    #: The canonical digest of the exact publisher submission envelope this
    #: result is about. The "exact artifact digest" §35.1's BR-2C row requires.
    verified_digest: str

    #: Pinned to ``PUBLISHER``. Bound rather than implied by the type's name so
    #: the role survives serialization and digesting.
    signer_role: BenchmarkTrustRole

    #: The signer's declared identity, as resolved against.
    signer_identity: str

    #: The key identifier evaluated.
    signer_key_id: str

    #: The profile the signature was evaluated under. D-29 keeps this a member
    #: of a closed enum with exactly one ratified value, because an
    #: attacker-chosen algorithm name is the classic downgrade vector.
    signature_profile: BenchmarkSignatureProfile

    #: The **anchor revision** verified against — the canonical digest of the
    #: resolved :class:`BenchmarkTrustAnchorRecord`. Mandatory on a ``VERIFIED``
    #: result; :data:`None` only on a refusal that never reached an anchor.
    anchor_record_digest: Optional[str]

    #: The **explicit trusted instant** the evaluation ran against (D-28).
    #: An input, never a clock read: BR-2C ships no clock, the authoritative
    #: clock arrives at BR-2D and D-11 is unamended.
    evaluated_at: datetime

    #: ``VERIFIED`` or ``REFUSED``. Never an admission outcome.
    outcome: BenchmarkVerificationOutcome

    #: Exactly one typed reason when refused, and :data:`None` when verified.
    #: The constructor enforces the biconditional in both directions.
    refusal_reason: Optional[BenchmarkRegistryRefusalReason]

    def __post_init__(self) -> None:
        _validate_verified_result(self, BenchmarkTrustRole.PUBLISHER)


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkApprovalVerifiedResult:
    """The approval seam's exact verified result. Replaces a ``bool`` (D-24).

    Identical bound facts to :class:`BenchmarkPublisherVerifiedResult`, and a
    **deliberately different type** with its own digest domain. D-02's
    four-party separation is why: an approval that could be represented by the
    same object as a publisher verification would let a publisher's own verified
    signature stand where an independent approver's is required, which is the
    substitution D-02 exists to prevent.

    :attr:`signer_role` is pinned to
    :attr:`~.enums.BenchmarkTrustRole.APPROVER`.

    Verifying an approval signature establishes that the approver signed. It
    does **not** establish that the approval is valid, that the artifact may be
    admitted, or that anything was registered — ``approval_authenticity_
    established`` stays permanently ``False`` here as everywhere else in this
    package, because no verifier exists to establish it.
    """

    #: The canonical digest of the exact approval envelope this result is about.
    verified_digest: str

    #: Pinned to ``APPROVER``.
    signer_role: BenchmarkTrustRole

    #: The approving authority's declared identity.
    signer_identity: str

    #: The key identifier evaluated.
    signer_key_id: str

    #: The profile the signature was evaluated under.
    signature_profile: BenchmarkSignatureProfile

    #: The anchor revision verified against, from the **approver** namespace.
    anchor_record_digest: Optional[str]

    #: The explicit trusted instant the evaluation ran against.
    evaluated_at: datetime

    #: ``VERIFIED`` or ``REFUSED``.
    outcome: BenchmarkVerificationOutcome

    #: Exactly one typed reason when refused; :data:`None` when verified.
    refusal_reason: Optional[BenchmarkRegistryRefusalReason]

    def __post_init__(self) -> None:
        _validate_verified_result(self, BenchmarkTrustRole.APPROVER)


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkRevocationVerifiedResult:
    """The revocation seam's exact verified result. **New at D-26.**

    D-26 rules that revokers are verified at BR-2C under role separation, adding
    a third verification seam that BR-2A's two-method port had no place for.
    §8's role-separation matrix names the benchmark-version revoker as a role
    distinct from the publisher, §17's rule 10 requires the revoking authority
    to be entitled for the exact benchmark scope with the publisher **never**
    substituted for it, and D-12 requires revocation assertions to carry revoker
    signatures. D-02's four-party separation names no revoker at all and
    ``is_entitled`` was publisher-scoped in its own signature, which is why D-26
    made the allocation rather than leaving it to an implementer.

    :attr:`signer_role` is pinned to
    :attr:`~.enums.BenchmarkTrustRole.REVOKER`.

    **Verifying a revoker's assertion is not appending a revocation.** D-26 says
    so explicitly, and it changes nothing about registry events: through BR-2C
    those remain unsigned and non-existent under D-12. Nothing here revokes
    anything.
    """

    #: The canonical digest of the exact revocation envelope this result is
    #: about.
    verified_digest: str

    #: Pinned to ``REVOKER``.
    signer_role: BenchmarkTrustRole

    #: The revoking authority's declared identity.
    signer_identity: str

    #: The key identifier evaluated.
    signer_key_id: str

    #: The profile the signature was evaluated under.
    signature_profile: BenchmarkSignatureProfile

    #: The anchor revision verified against, from the **revoker** namespace —
    #: never the publisher's, whatever that publisher is entitled to.
    anchor_record_digest: Optional[str]

    #: The explicit trusted instant the evaluation ran against.
    evaluated_at: datetime

    #: ``VERIFIED`` or ``REFUSED``.
    outcome: BenchmarkVerificationOutcome

    #: Exactly one typed reason when refused; :data:`None` when verified.
    refusal_reason: Optional[BenchmarkRegistryRefusalReason]

    def __post_init__(self) -> None:
        _validate_verified_result(self, BenchmarkTrustRole.REVOKER)


#: The three verified-result types, as one annotation for the shared validator.
#: Not a public alias and not exported: it exists so the validator's parameter
#: can be annotated exactly, and a fourth result type would have to be added
#: here to be validated at all.
_VerifiedResult = Union[
    "BenchmarkPublisherVerifiedResult",
    "BenchmarkApprovalVerifiedResult",
    "BenchmarkRevocationVerifiedResult",
]


def _validate_verified_result(
    result: _VerifiedResult, expected_role: BenchmarkTrustRole
) -> None:
    """The nine-fact validation every verified-result type runs.

    One function rather than three copies: the three types differ in their
    pinned role and their digest domain, and in nothing else, so three
    hand-copied constructors would be three chances for one of them to drift
    into accepting what the others refuse.

    It validates; it verifies nothing. Every check here is about the *shape* of
    a claim — a digest is 64 lowercase hex characters, an identity is canonical
    and unpadded, an instant is timezone-aware, an outcome and its reason agree.
    None of it consults an anchor, parses a key or performs a curve operation,
    because this package does none of those things.
    """

    require_digest(result.verified_digest, "verified_digest")
    _require_pinned_role(result.signer_role, expected_role, "signer_role")
    require_actor_identity(result.signer_identity, "signer_identity")
    require_key_identifier(result.signer_key_id, "signer_key_id")
    require_enum_member(
        result.signature_profile,
        BenchmarkSignatureProfile,
        "signature_profile",
    )
    _require_outcome_and_reason_agree(result.outcome, result.refusal_reason)
    _require_anchor_digest_binding(result.outcome, result.anchor_record_digest)
    require_aware_datetime(result.evaluated_at, "evaluated_at")


for _cls, _domain in (
    (BenchmarkTrustAnchorRecord, BENCHMARK_TRUST_ANCHOR_RECORD_DIGEST_DOMAIN),
    (
        BenchmarkPublisherVerifiedResult,
        BENCHMARK_PUBLISHER_VERIFIED_RESULT_DIGEST_DOMAIN,
    ),
    (
        BenchmarkApprovalVerifiedResult,
        BENCHMARK_APPROVAL_VERIFIED_RESULT_DIGEST_DOMAIN,
    ),
    (
        BenchmarkRevocationVerifiedResult,
        BENCHMARK_REVOCATION_VERIFIED_RESULT_DIGEST_DOMAIN,
    ),
):
    _register_contract_type(_cls, _domain, root_canonicalizable=True)
del _cls, _domain
