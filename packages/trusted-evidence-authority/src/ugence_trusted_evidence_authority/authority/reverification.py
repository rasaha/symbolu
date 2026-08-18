"""Independent re-verification of a signed receipt envelope (ADR §13.3).

ADR §13.3 requires that "independent verification must be possible: a third
party holding the receipt and the public verification functions can recompute
the digest and check the signature **without authority internals**". This module
is that third party's tool, and it lives up to the word *independent*:

* it holds **no signing key** and has no method that produces a signature;
* it holds **no** verification authority, no protocol and no determination;
* it never consults the issuer, and never trusts anything the envelope asserts
  about itself;
* it reconstructs the signed bytes from the envelope's own fields and the
  payload it carries, resolves the named anchor at an exact coordinate, and
  checks the signature with a maintained backend (:mod:`.backend`).

Two operations, two result types — never one ambiguous call
------------------------------------------------------------
The previous design was a single ``verify(..., expected_*=None)`` whose optional
coordinates defaulted to *unchecked*. The independent closure audit found two
defects in that shape, and both are structural rather than cosmetic:

* **F-04** — a signature-only result was **indistinguishable** from a fully
  scope-bound one. Same type, same fields, same ``repr``, and the two compared
  ``==`` equal. A consumer could not tell which question had been answered, and
  both claimed the same established stages.
* **F-05** — ``None``, ``""`` and other falsy values **silently skipped** their
  check, because the comparison was guarded by
  ``if expected and expected != actual``. Passing ``expected_tenant_id=None``
  looked like asking for a tenant check and produced a pass without one.

Neither is fixable with another optional flag, so the ambiguous entry point is
**removed** — TEV-2 is unmerged, so it is deleted rather than kept as a
compatibility alias. In its place:

===============================================  =========================================
:meth:`SignedReceiptVerifier.verify_signature`   :class:`SignatureOnlyVerificationResult`
:meth:`SignedReceiptVerifier.verify_bound`       :class:`ScopeBoundVerificationResult`
===============================================  =========================================

The two results are **different exact types**, carry an explicit
:class:`ReceiptVerificationKind`, record which ADR §12 stage set they
established, and can never compare equal to one another. Scope-bound
verification additionally records a digest of the exact expectation it was
checked against, so "what was actually required" is evidence rather than
recollection.

``verify_bound`` takes **one mandatory, exactly-typed**
:class:`ReceiptScopeExpectation`. There is no default, no per-coordinate
keyword, and no optional field inside it: every ratified coordinate must be
present and non-blank at construction, so "omitted" is unrepresentable and
there is nothing for a truthiness gate to skip.

Current trust, and the retroactive-revocation rule
--------------------------------------------------
The delegated question — whether re-verification asks "was this trusted when
signed?" or "is this trusted now?" — is settled by ADR §13.3 itself: "key
revocation is checked **at verification time**; a receipt signed by a key that
was later revoked is **not silently honoured**."

Both operations therefore evaluate the key's validity window, its revocation,
its disabled state and the receipt's own validity at the caller-supplied
``evaluated_at``, never at the payload's ``verified_at``. A key revoked as of
``evaluated_at`` cannot establish current trust, whatever instant the signature
was produced at, so a previously-valid receipt stops verifying once its key is
revoked — a signature is not grandfathered.

**Historical re-verification is deliberately not offered.** Asking "was this
trusted at some past instant T" needs a ratified as-of-T trust semantics — which
anchor set was configured then, which revocations were known then — and no
merged clause defines one for evidence. ADR §17.1's historical resolution is a
*Benchmark Registry* concept and is BR-2's, not TEV-2's.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from typing import Optional

from ..contracts._validation import (
    require_aware_datetime,
    require_canonical_str,
    require_digest,
    require_exact_type,
    require_identifier,
)
from ..contracts.enums import DeclaredVerificationOutcome, EvidenceTrustStage
from ..contracts.errors import TrustedEvidenceContractError
from ..contracts.identity import EvidenceScopeBinding
from ..contracts.reasons import TrustedEvidenceRefusalReason
from .envelope import SignedEvidenceVerificationReceipt
from .trust import (
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorResolution,
    TrustAnchorResolverPort,
)

__all__ = [
    "RECEIPT_SCOPE_EXPECTATION_DIGEST_DOMAIN",
    "ReceiptVerificationKind",
    "ReceiptVerificationOutcome",
    "ReceiptScopeExpectation",
    "SignatureOnlyVerificationResult",
    "ScopeBoundVerificationResult",
    "SignedReceiptVerifier",
]

_R = TrustedEvidenceRefusalReason

#: Domain tag for the scope-expectation digest recorded on a bound result.
RECEIPT_SCOPE_EXPECTATION_DIGEST_DOMAIN = (
    "ugence.trusted-evidence-authority/receipt-scope-expectation/v1"
)


def _fail(message: str, reason: TrustedEvidenceRefusalReason):
    error = TrustedEvidenceContractError(message)
    error.reason = reason
    return error


class ReceiptVerificationKind(str, Enum):
    """Which question a verification result answers. Never inferred.

    Recorded explicitly on every result so a consumer reading one cannot mistake
    the weaker answer for the stronger one — closure-audit **F-04**.
    """

    #: The signature verified under a currently-trusted anchor. **No consumer
    #: scope expectation was supplied or checked**, so this establishes nothing
    #: about which tenant, context, subject or system the receipt belongs to.
    SIGNATURE_ONLY = "SIGNATURE_ONLY"
    #: Everything ``SIGNATURE_ONLY`` establishes, **plus** every ratified scope
    #: coordinate matched an exact caller-supplied expectation.
    SCOPE_BOUND = "SCOPE_BOUND"


class ReceiptVerificationOutcome(str, Enum):
    """The result of independently re-verifying a signed receipt envelope.

    Two members, because E-9 admits no third state, §11 makes indeterminacy a
    refusal, and a success-shaped ``UNKNOWN``/``PARTIAL``/``PENDING``/
    ``BEST_EFFORT`` member would be read optimistically by exactly the consumer
    §10 is written to protect.
    """

    #: The checks for **this kind** of verification all passed.
    #: **This is not an authorization** (§13.2, E-12).
    VERIFIED = "VERIFIED"
    #: Fail-closed, with exactly one stable typed reason (E-9).
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class ReceiptScopeExpectation:
    """The exact coordinates a consumer requires a receipt to be bound to.

    One closed, mandatory, fully-populated contract — not a bag of optional
    keywords. Closure-audit **F-05** was that optional per-coordinate arguments
    let ``None`` and ``""`` silently disable their own check; here every field
    is required and validated non-blank at construction, so an omitted or empty
    coordinate is **unrepresentable** rather than silently skipped.

    Every ratified §13.1.3 / §9 scope coordinate is present:

    ==================================  ====================
    ``tenant_id``                       §9 row 7
    ``assessment_context_ref``          §9 row 8
    ``subject_ref``                     §9 row 9
    ``assessed_system_binding_digest``  §9 row 10
    ``assessment_purpose_ref``          §7.1 row 5
    ``usage_scope_ref``                 §7.1 row 5
    ``evidence_content_digest``         §9 row 3
    ``verification_protocol_id``        §9 row 15
    ``verification_protocol_version``   §9 row 15
    ==================================  ====================

    ``assessed_system_binding_digest`` may be the empty string **only** through
    :meth:`for_system_independent_evidence`. §9 row 10 makes the binding absent
    for system-independent evidence but requires that "its absence is explicit,
    never defaulted" — a named constructor is that explicit decision, whereas an
    optional argument defaulting to ``""`` would reintroduce exactly the silent
    skip F-05 closed.
    """

    tenant_id: str
    assessment_context_ref: str
    subject_ref: str
    assessed_system_binding_digest: str
    assessment_purpose_ref: str
    usage_scope_ref: str
    evidence_content_digest: str
    verification_protocol_id: str
    verification_protocol_version: str

    #: Every field, in declaration order. The matcher and the digest both walk
    #: this, so a coordinate added later cannot be forgotten by one of them.
    REQUIRED_COORDINATES = (
        "tenant_id",
        "assessment_context_ref",
        "subject_ref",
        "assessed_system_binding_digest",
        "assessment_purpose_ref",
        "usage_scope_ref",
        "evidence_content_digest",
        "verification_protocol_id",
        "verification_protocol_version",
    )

    def __post_init__(self) -> None:
        for name in (
            "tenant_id",
            "assessment_context_ref",
            "subject_ref",
            "assessment_purpose_ref",
            "usage_scope_ref",
            "verification_protocol_id",
            "verification_protocol_version",
        ):
            require_identifier(getattr(self, name), f"ReceiptScopeExpectation.{name}")
        require_digest(
            self.evidence_content_digest,
            "ReceiptScopeExpectation.evidence_content_digest",
        )
        binding = require_canonical_str(
            self.assessed_system_binding_digest,
            "ReceiptScopeExpectation.assessed_system_binding_digest",
            allow_empty=True,
        )
        if binding != "":
            require_digest(
                binding, "ReceiptScopeExpectation.assessed_system_binding_digest"
            )

    @classmethod
    def for_system_independent_evidence(cls, **kw) -> "ReceiptScopeExpectation":
        """Build an expectation for evidence that binds no assessed system.

        The absence is explicit and on the record, never defaulted — the
        discipline ADR §9 row 10 requires.
        """

        if "assessed_system_binding_digest" in kw:
            raise _fail(
                "for_system_independent_evidence() sets "
                "assessed_system_binding_digest itself; passing one would make "
                "the absence ambiguous",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        return cls(assessed_system_binding_digest="", **kw)

    @classmethod
    def from_scope(
        cls,
        scope: EvidenceScopeBinding,
        *,
        evidence_content_digest: str,
        verification_protocol_id: str,
        verification_protocol_version: str,
    ) -> "ReceiptScopeExpectation":
        """Build an expectation from a scope binding the **consumer** holds.

        A convenience for the common case where the consumer already has the
        authoritative scope. It is not a shortcut around checking: building one
        from the *envelope's* own scope would be circular, which is why this
        takes a scope the caller supplies.
        """

        require_exact_type(
            scope, EvidenceScopeBinding, "ReceiptScopeExpectation.from_scope.scope"
        )
        return cls(
            tenant_id=scope.tenant_id,
            assessment_context_ref=scope.assessment_context_ref,
            subject_ref=scope.subject_ref,
            assessed_system_binding_digest=scope.assessed_system_binding_digest,
            assessment_purpose_ref=scope.assessment_purpose_ref,
            usage_scope_ref=scope.usage_scope_ref,
            evidence_content_digest=evidence_content_digest,
            verification_protocol_id=verification_protocol_id,
            verification_protocol_version=verification_protocol_version,
        )

    def expectation_digest(self) -> str:
        """A closed, deterministic digest of exactly what was required.

        Recorded on :class:`ScopeBoundVerificationResult` so the result carries
        evidence of *which* expectation it was checked against, rather than only
        that some expectation was. Length-prefixed per field, so no pair of
        coordinate values can be re-partitioned into a different expectation
        with the same digest.
        """

        parts = [RECEIPT_SCOPE_EXPECTATION_DIGEST_DOMAIN]
        for name in self.REQUIRED_COORDINATES:
            value = getattr(self, name)
            parts.append(f"{len(name)}:{name}={len(value)}:{value}")
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


#: The private construction token for verification results. Not exported.
_VERIFICATION_TOKEN = object()


@dataclass(frozen=True, eq=False)
class _BaseVerificationResult:
    """Fields common to both result types. Never instantiated directly."""

    outcome: ReceiptVerificationOutcome
    evaluated_at: datetime
    coordinate: TrustAnchorCoordinate
    envelope_digest: str
    payload_canonical_digest: str
    refusal_reason: Optional[TrustedEvidenceRefusalReason] = None
    trust_anchor_digest: str = ""
    verification_token: object = None

    def __post_init__(self) -> None:
        if self.verification_token is not _VERIFICATION_TOKEN:
            raise _fail(
                f"{type(self).__name__} cannot be constructed directly. A "
                "verification outcome is produced only by "
                "SignedReceiptVerifier; a caller-built VERIFIED result would be "
                "exactly the manufactured verification ADR §8.1.5 prohibits and "
                "§10.5 enumerates as a non-proof",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        require_exact_type(self.outcome, ReceiptVerificationOutcome, "outcome")
        require_aware_datetime(self.evaluated_at, "evaluated_at")
        require_exact_type(self.coordinate, TrustAnchorCoordinate, "coordinate")
        require_identifier(self.envelope_digest, "envelope_digest")
        require_identifier(self.payload_canonical_digest, "payload_canonical_digest")
        require_canonical_str(
            self.trust_anchor_digest, "trust_anchor_digest", allow_empty=True
        )
        verified = self.outcome is ReceiptVerificationOutcome.VERIFIED
        if verified is True and self.refusal_reason is not None:
            raise _fail(
                "a VERIFIED result carries a refusal reason",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        if verified is False and self.refusal_reason is None:
            raise _fail(
                "a REFUSED result must carry a stable typed reason (ADR E-9)",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        if self.refusal_reason is not None:
            require_exact_type(
                self.refusal_reason, TrustedEvidenceRefusalReason, "refusal_reason"
            )

    @property
    def verified(self) -> bool:
        """Whether the checks **for this kind** of verification passed.

        Derived from :attr:`outcome`, never stored and never caller-settable.
        Read it together with ``verification_kind``: on a
        :class:`SignatureOnlyVerificationResult` it means *only* that the
        signature is authentic under a currently-trusted key, and says nothing
        about which tenant, context, subject or system the receipt belongs to.
        """

        return self.outcome is ReceiptVerificationOutcome.VERIFIED

    def __eq__(self, other: object) -> bool:
        """Results of different kinds are never equal, even field-for-field.

        Closure-audit **F-04**: previously a signature-only result compared
        ``==`` to a fully scope-bound one. Equality is now type-exact first.
        """

        if type(other) is not type(self):
            return NotImplemented
        return all(
            getattr(self, f.name) == getattr(other, f.name)
            for f in fields(self)
            if f.name != "verification_token"
        )

    def __hash__(self) -> int:
        return hash(
            (
                type(self).__name__,
                self.outcome,
                self.envelope_digest,
                self.payload_canonical_digest,
            )
        )


@dataclass(frozen=True, eq=False)
class SignatureOnlyVerificationResult(_BaseVerificationResult):
    """The signature is authentic under a currently-trusted key — and *only* that.

    **This result establishes no scope binding.** No consumer expectation was
    supplied, so nothing here says the receipt belongs to your tenant, your
    context, your subject or your assessed system. ADR §12 stage 4
    (``CONTEXT_SYSTEM_BOUND``) is deliberately **absent** from
    :attr:`established_trust_stages`, and no field of this type reports a scope
    coordinate as checked.

    It exists for §13.3's third party — someone holding only the envelope and
    the public verification functions, who genuinely cannot supply expectations.
    A consumer that *has* expectations must call
    :meth:`SignedReceiptVerifier.verify_bound` instead; §26.5's replay detection
    is only mechanical for coordinates someone actually asserts.
    """

    @property
    def verification_kind(self) -> ReceiptVerificationKind:
        return ReceiptVerificationKind.SIGNATURE_ONLY

    @property
    def scope_bound(self) -> bool:
        """Always ``False``. No scope expectation was supplied or checked."""

        return False

    @property
    def established_trust_stages(self) -> tuple:
        """Stages 1-2 of the **receipt** on success; empty on refusal.

        A verified envelope establishes that the receipt is structurally sound
        and cryptographically authentic under a currently-trusted authority key.
        It does **not** establish ``CONTEXT_SYSTEM_BOUND`` — that requires an
        expectation to bind against — and never establishes stage 6.
        """

        if self.verified is False:
            return ()
        return (
            EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
        )

    def __repr__(self) -> str:
        reason = (
            None if self.refusal_reason is None else self.refusal_reason.value
        )
        return (
            "SignatureOnlyVerificationResult(kind=SIGNATURE_ONLY, "
            f"outcome={self.outcome.value}, scope_bound=False, "
            f"reason={reason}, envelope={self.envelope_digest[:16]}...)"
        )


@dataclass(frozen=True, eq=False)
class ScopeBoundVerificationResult(_BaseVerificationResult):
    """The signature is authentic **and** every required coordinate matched.

    Carries :attr:`scope_expectation_digest`, a closed digest of the exact
    :class:`ReceiptScopeExpectation` it was checked against, so the result is
    evidence of *what* was required rather than merely that something was.
    """

    scope_expectation_digest: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        require_digest(
            self.scope_expectation_digest,
            "ScopeBoundVerificationResult.scope_expectation_digest",
        )

    @property
    def verification_kind(self) -> ReceiptVerificationKind:
        return ReceiptVerificationKind.SCOPE_BOUND

    @property
    def scope_bound(self) -> bool:
        """``True`` only when verified; a refusal bound nothing."""

        return self.verified

    @property
    def established_trust_stages(self) -> tuple:
        """Stages 1, 2 **and 4** on success; empty on refusal.

        ``CONTEXT_SYSTEM_BOUND`` is established here and only here, and only
        after every required coordinate matched exactly. Stage 6 is never
        established, by anything (§12).
        """

        if self.verified is False:
            return ()
        return (
            EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
            EvidenceTrustStage.CONTEXT_SYSTEM_BOUND,
        )

    def __repr__(self) -> str:
        reason = (
            None if self.refusal_reason is None else self.refusal_reason.value
        )
        return (
            "ScopeBoundVerificationResult(kind=SCOPE_BOUND, "
            f"outcome={self.outcome.value}, scope_bound={self.scope_bound}, "
            f"reason={reason}, "
            f"expectation={self.scope_expectation_digest[:16]}..., "
            f"envelope={self.envelope_digest[:16]}...)"
        )


class SignedReceiptVerifier:
    """Independently re-verify a signed receipt envelope. Holds no key.

    Wired with a :class:`~.trust.TrustAnchorResolverPort` and nothing else. Pass
    :class:`~.trust.DenyAllTrustAnchorDirectory` where no trust is configured
    and every re-verification denies, which is ADR E-8's production default made
    explicit rather than implicit.

    There is deliberately **no** ``verify()``. The two operations answer
    different questions and return different types; a single call whose meaning
    depended on which keyword arguments a caller remembered was closure-audit
    findings F-04 and F-05.
    """

    __slots__ = ("_trust_anchors",)

    def __init__(self, *, trust_anchors: TrustAnchorResolverPort) -> None:
        if not hasattr(trust_anchors, "resolve"):
            raise _fail(
                "SignedReceiptVerifier.trust_anchors must implement "
                "TrustAnchorResolverPort.resolve; ADR E-8 makes an unconfigured "
                "verifier a denial, not an absent check — pass "
                "DenyAllTrustAnchorDirectory() to deny explicitly",
                _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED,
            )
        object.__setattr__(self, "_trust_anchors", trust_anchors)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"SignedReceiptVerifier is immutable; cannot set {name!r}. "
            "Re-pointing a configured verifier's trust anchors would bypass "
            "the composition root (ADR E-5)."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"SignedReceiptVerifier is immutable; cannot delete {name!r}"
        )

    # ------------------------------------------------------------------ #
    # Operation 1 — signature only
    # ------------------------------------------------------------------ #

    def verify_signature(
        self,
        envelope: SignedEvidenceVerificationReceipt,
        *,
        evaluated_at: datetime,
    ) -> SignatureOnlyVerificationResult:
        """Verify authenticity under a currently-trusted key. **No scope check.**

        For ADR §13.3's third party, who holds the envelope and nothing else.
        The result type says so in its name, its ``verification_kind``, its
        ``repr`` and its stage set: ``CONTEXT_SYSTEM_BOUND`` is not established.

        A consumer that knows which tenant, context, subject or system it
        expects must call :meth:`verify_bound` instead.
        """

        outcome = self._run_common_checks(envelope, evaluated_at=evaluated_at)
        if outcome.refusal is not None:
            return self._signature_only(outcome, outcome.refusal)
        return SignatureOnlyVerificationResult(
            outcome=ReceiptVerificationOutcome.VERIFIED,
            evaluated_at=outcome.evaluated_at,
            coordinate=outcome.coordinate,
            envelope_digest=outcome.envelope_digest,
            payload_canonical_digest=outcome.payload_digest,
            trust_anchor_digest=outcome.anchor_digest,
            verification_token=_VERIFICATION_TOKEN,
        )

    # ------------------------------------------------------------------ #
    # Operation 2 — signature plus exact scope binding
    # ------------------------------------------------------------------ #

    def verify_bound(
        self,
        envelope: SignedEvidenceVerificationReceipt,
        expectation: ReceiptScopeExpectation,
        *,
        evaluated_at: datetime,
    ) -> ScopeBoundVerificationResult:
        """Verify authenticity **and** exact binding to ``expectation``.

        ``expectation`` is mandatory, positional, and must be exactly a
        :class:`ReceiptScopeExpectation` — not ``None``, not a mapping, not a
        duck-typed object, not a subclass. Every one of its coordinates is
        compared **unconditionally**; there is no truthiness gate and nothing a
        caller can leave out to skip a check.

        ``CONTEXT_SYSTEM_BOUND`` is established only when the signature verifies
        *and* every required coordinate matches.
        """

        if type(expectation) is not ReceiptScopeExpectation:
            raise _fail(
                "verify_bound() requires exactly a ReceiptScopeExpectation "
                f"(got {type(expectation).__name__}). It is mandatory and has "
                "no default: an optional or duck-typed expectation is how "
                "closure-audit F-05 let None and empty strings silently skip "
                "their own checks. For the third-party case with no "
                "expectations, call verify_signature() — which returns a result "
                "that says so.",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        expectation_digest = expectation.expectation_digest()

        outcome = self._run_common_checks(envelope, evaluated_at=evaluated_at)
        if outcome.refusal is not None:
            return self._scope_bound(outcome, outcome.refusal, expectation_digest)

        payload = envelope.payload
        scope = payload.scope
        actual = {
            "tenant_id": scope.tenant_id,
            "assessment_context_ref": scope.assessment_context_ref,
            "subject_ref": scope.subject_ref,
            "assessed_system_binding_digest": scope.assessed_system_binding_digest,
            "assessment_purpose_ref": scope.assessment_purpose_ref,
            "usage_scope_ref": scope.usage_scope_ref,
            "evidence_content_digest": payload.evidence_content_digest,
            "verification_protocol_id": payload.verification_protocol_id,
            "verification_protocol_version": payload.verification_protocol_version,
        }
        reasons = {
            "tenant_id": _R.TRUSTED_EVIDENCE_TENANT_MISMATCH,
            "assessment_context_ref": _R.TRUSTED_EVIDENCE_CONTEXT_MISMATCH,
            "subject_ref": _R.TRUSTED_EVIDENCE_SUBJECT_MISMATCH,
            "assessed_system_binding_digest": (
                _R.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH
            ),
            "assessment_purpose_ref": _R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH,
            "usage_scope_ref": _R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH,
            "evidence_content_digest": _R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH,
            "verification_protocol_id": _R.TRUSTED_EVIDENCE_PROTOCOL_UNSUPPORTED,
            "verification_protocol_version": (
                _R.TRUSTED_EVIDENCE_PROTOCOL_VERSION_MISMATCH
            ),
        }
        # Unconditional comparison, fixed order, every declared coordinate.
        # No `if expected and ...` anywhere: there is nothing optional to skip.
        for name in ReceiptScopeExpectation.REQUIRED_COORDINATES:
            if getattr(expectation, name) != actual[name]:
                return self._scope_bound(outcome, reasons[name], expectation_digest)

        return ScopeBoundVerificationResult(
            outcome=ReceiptVerificationOutcome.VERIFIED,
            evaluated_at=outcome.evaluated_at,
            coordinate=outcome.coordinate,
            envelope_digest=outcome.envelope_digest,
            payload_canonical_digest=outcome.payload_digest,
            trust_anchor_digest=outcome.anchor_digest,
            scope_expectation_digest=expectation_digest,
            verification_token=_VERIFICATION_TOKEN,
        )

    # ------------------------------------------------------------------ #
    # Shared: everything that does not depend on consumer expectations
    # ------------------------------------------------------------------ #

    def _run_common_checks(
        self,
        envelope: SignedEvidenceVerificationReceipt,
        *,
        evaluated_at: datetime,
    ) -> "_CommonChecks":
        """Run the kind-independent checks, ordered and fail-closed.

         1. **envelope structure** — enforced at construction, so an envelope
            cannot exist malformed;
         2. **payload digest** — recomputed from the payload and compared
            against the envelope's declared field. Load-bearing and *not*
            redundant with the envelope's own construction-time check: the
            signing frame binds the digest it recomputes, never the declared
            field, so an envelope whose ``__post_init__`` never ran — unpickled,
            or rebuilt field by field by a deserializer — reaches here with a
            valid signature and a lying digest, and this is the only gate that
            refuses it. Conflating the two checks was closure-audit **F-09**;
         3. **trust-anchor resolution** — exact
            ``(signer_authority_id, signing_key_id, RECEIPT_ISSUANCE)``;
         4. **capability** — a producing key can never satisfy this (E-3).
            **Currently unreachable, and counted as redundancy rather than as a
            load-bearing gate:** the coordinate this verifier builds always
            names ``RECEIPT_ISSUANCE``, and
            :class:`~.trust.TrustAnchorResolution` refuses an anchor whose own
            coordinate differs from the one resolved, so no resolver — including
            a caller's own — can deliver a producing key here. A gate-deletion
            mutant of this check survives the whole battery, and saying so is
            more useful than pretending otherwise (closure-audit **F-09**);
         5. **profile agreement** — anchor profile versus envelope profile.
            **Also currently unreachable, also counted as redundancy:** both
            fields are pinned by exact equality to
            :data:`~.profile.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1` at
            construction, so they cannot differ while exactly one profile
            exists. Both checks stay because they become load-bearing the day a
            second profile or a third capability is ratified, and a check added
            *after* the vocabulary widens is a check added too late;
         6. **key lifecycle at** ``evaluated_at`` — revoked, disabled, not yet
            valid, expired;
         7. **signature** — the one load-bearing cryptographic gate, checked by
            the maintained backend against a key that was strictly
            point-validated when its anchor was constructed;
         8. **payload/envelope coherence** — the payload's own authority, key
            and outcome agree with the envelope carrying it;
         9. **receipt validity at** ``evaluated_at`` — half-open, §13.1.6.
        """

        require_exact_type(
            envelope,
            SignedEvidenceVerificationReceipt,
            "SignedReceiptVerifier envelope",
        )
        require_aware_datetime(evaluated_at, "SignedReceiptVerifier evaluated_at")
        payload = envelope.payload
        coordinate = TrustAnchorCoordinate(
            authority_id=envelope.signer_authority_id,
            key_id=envelope.signing_key_id,
            capability=TrustAnchorCapability.RECEIPT_ISSUANCE,
        )
        state = _CommonChecks(
            evaluated_at=evaluated_at,
            coordinate=coordinate,
            envelope_digest=envelope.envelope_digest(),
            payload_digest=payload.canonical_digest(),
        )

        # 2. payload digest — recomputed, never believed. The signature does
        #    not cover the declared field (the frame binds the recomputed
        #    digest), so nothing downstream would catch a tampered one. F-09.
        if envelope.payload_canonical_digest != state.payload_digest:
            return state.refused(_R.TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH)

        # 3. trust-anchor resolution at the exact coordinate.
        resolution = self._trust_anchors.resolve(coordinate)
        if type(resolution) is not TrustAnchorResolution:
            return state.refused(_R.TRUSTED_EVIDENCE_VERIFIER_UNAVAILABLE)
        if resolution.anchor is None:
            return state.refused(resolution.refusal_reason)
        anchor = resolution.anchor
        state.anchor_digest = anchor.canonical_digest()

        # 4. capability — E-3 enforced structurally, re-checked explicitly.
        if anchor.capability is not TrustAnchorCapability.RECEIPT_ISSUANCE:
            return state.refused(_R.TRUSTED_EVIDENCE_KEY_CAPABILITY_MISMATCH)

        # 5. profile agreement — no negotiation, no downgrade.
        if anchor.signature_profile != envelope.signature_profile:
            return state.refused(_R.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED)

        # 6. key lifecycle at the caller's instant — revocation checked first.
        lifecycle_refusal = anchor.lifecycle_refusal_at(evaluated_at)
        if lifecycle_refusal is not None:
            return state.refused(lifecycle_refusal)

        # 7. the signature — the one load-bearing cryptographic gate.
        if not anchor.verification_key().verify(
            envelope.signed_input_bytes(), envelope.signature_bytes()
        ):
            return state.refused(_R.TRUSTED_EVIDENCE_SIGNATURE_INVALID)

        # 8. payload/envelope coherence.
        if payload.verifier_authority_id != envelope.signer_authority_id:
            return state.refused(_R.TRUSTED_EVIDENCE_AUTHORITY_MISMATCH)
        if payload.verifier_key_id != envelope.signing_key_id:
            return state.refused(_R.TRUSTED_EVIDENCE_KEY_ID_MISMATCH)
        if payload.declared_outcome is not DeclaredVerificationOutcome.DECLARED_ADMITTED:
            return state.refused(_R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED)

        # 9. the receipt's own half-open validity at evaluated_at (§13.1.6).
        if (
            payload.receipt_valid_from is not None
            and evaluated_at < payload.receipt_valid_from
        ):
            return state.refused(_R.TRUSTED_EVIDENCE_RECEIPT_NOT_YET_VALID)
        if (
            payload.receipt_valid_to is not None
            and evaluated_at >= payload.receipt_valid_to
        ):
            return state.refused(_R.TRUSTED_EVIDENCE_RECEIPT_EXPIRED)

        return state

    @staticmethod
    def _signature_only(state, reason) -> SignatureOnlyVerificationResult:
        return SignatureOnlyVerificationResult(
            outcome=ReceiptVerificationOutcome.REFUSED,
            evaluated_at=state.evaluated_at,
            coordinate=state.coordinate,
            envelope_digest=state.envelope_digest,
            payload_canonical_digest=state.payload_digest,
            refusal_reason=reason,
            trust_anchor_digest=state.anchor_digest,
            verification_token=_VERIFICATION_TOKEN,
        )

    @staticmethod
    def _scope_bound(state, reason, expectation_digest) -> ScopeBoundVerificationResult:
        return ScopeBoundVerificationResult(
            outcome=ReceiptVerificationOutcome.REFUSED,
            evaluated_at=state.evaluated_at,
            coordinate=state.coordinate,
            envelope_digest=state.envelope_digest,
            payload_canonical_digest=state.payload_digest,
            refusal_reason=reason,
            trust_anchor_digest=state.anchor_digest,
            scope_expectation_digest=expectation_digest,
            verification_token=_VERIFICATION_TOKEN,
        )

    def __repr__(self) -> str:
        return "SignedReceiptVerifier(trust_anchors=<configured>)"


class _CommonChecks:
    """Private carrier for the kind-independent check state. Never exported."""

    __slots__ = (
        "evaluated_at",
        "coordinate",
        "envelope_digest",
        "payload_digest",
        "anchor_digest",
        "refusal",
    )

    def __init__(self, *, evaluated_at, coordinate, envelope_digest, payload_digest):
        self.evaluated_at = evaluated_at
        self.coordinate = coordinate
        self.envelope_digest = envelope_digest
        self.payload_digest = payload_digest
        self.anchor_digest = ""
        self.refusal = None

    def refused(self, reason) -> "_CommonChecks":
        self.refusal = reason
        return self
