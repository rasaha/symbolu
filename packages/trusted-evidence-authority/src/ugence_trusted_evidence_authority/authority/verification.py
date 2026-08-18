"""Evidence verification: the protocol boundary, and the fail-closed authority.

ADR §30 assigns "the verification authority" to TEV-2, and §7.1 lists what it
owns: admission, authenticity, integrity, attributability, scope, temporal
validity, provenance, key trust and key revocation. §12 fixes what it may
conclude — stages 1-5 — and rules stage 6 out entirely: policy sufficiency "is
**not a property of the evidence**" and belongs to the consuming evaluation
engine under a Policy Authority requirement.

Three roles, three objects
--------------------------
ADR §8's matrix says "no row may absorb another", so the three TEV-2
responsibilities are three separate types even though a deployment wires them in
sequence:

1. :class:`EvidenceVerificationAuthority` — verifies, and produces a typed
   :class:`EvidenceVerificationDetermination`. It holds **no signing key** and
   cannot issue a receipt.
2. :class:`~.issuance.ReceiptIssuer` — turns an *admitted* determination into a
   signed envelope. It performs no verification and cannot admit anything.
3. :class:`~.reverification.SignedReceiptVerifier` — independently re-verifies a
   signed envelope. It holds no signing key and issues nothing.

The verification protocol is a port, not a hardcoded procedure
--------------------------------------------------------------
ADR §9 row 15 requires a verification result to bind a "verification protocol /
version", which only means something if the protocol is a real, nameable,
substitutable thing. :class:`EvidenceVerificationProtocolPort` is that boundary.
A protocol reports which ADR §12 stages **it** established and which refusals it
found; the authority then re-checks the structural, scope and temporal
coordinates *itself* and combines the two fail-closed.

That re-check is ADR §8.1's closing rule, applied literally: "a lax or
compromised verifier must still be unable to get a **mismatched** artifact
admitted: the authority independently re-checks that the verification binds the
exact identity, version, tenant/scope, content digest, producing authority, and
verification artifact." A protocol that returns "all stages cleared" for
mismatched evidence gets a refusal, not an admission.

The clock is never read
-----------------------
Two instants are explicit parameters and neither has a default: ``request.as_of``
(the evaluation instant, TEV-1's own field) and ``verified_at`` (ADR §9 row 6,
"explicit verification time, distinct from #5"). §22.9 and §22.10 forbid the
alternative.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from ..contracts._validation import (
    require_aware_datetime,
    require_exact_type,
    require_identifier,
)
from ..contracts.canonical import canonical_bytes, canonical_digest
from ..contracts.enums import (
    EVIDENCE_TRUST_STAGE_ORDER,
    RECEIPT_REPORTABLE_TRUST_STAGES,
    DeclaredVerificationOutcome,
    EvidenceLifecycleState,
    EvidenceTrustStage,
)
from ..contracts.errors import TrustedEvidenceContractError
from ..contracts.identity import EvidenceSchemaRef
from ..contracts.reasons import TrustedEvidenceRefusalReason
from ..contracts.receipts import EvidenceVerificationReceiptPayload
from ..contracts.requests import EvidenceVerificationRequest
from .envelope import SignedEvidenceSubmission, signed_evidence_input_bytes
from .trust import (
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorResolverPort,
)

__all__ = [
    "TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN",
    "TRUSTED_EVIDENCE_PROTOCOL_V1_ID",
    "TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION",
    "EvidenceAdmissionOutcome",
    "ProtocolExecutionResult",
    "EvidenceVerificationProtocolPort",
    "Ed25519EvidenceAuthenticityProtocol",
    "EvidenceVerificationDetermination",
    "EvidenceVerificationAuthority",
    "derive_receipt_id",
]

_R = TrustedEvidenceRefusalReason
_REPORTABLE = frozenset(RECEIPT_REPORTABLE_TRUST_STAGES)
_REASON_ORDER = tuple(TrustedEvidenceRefusalReason)

#: Domain tag for deterministic receipt-identifier derivation (§22.1, DD-9).
TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN = (
    "ugence.trusted-evidence-authority/receipt-id/v1"
)

#: Identity of the reference verification protocol (ADR §9 row 15).
TRUSTED_EVIDENCE_PROTOCOL_V1_ID = (
    "ugence.trusted-evidence-authority/verification-protocol/"
    "ed25519-evidence-authenticity/v1"
)

#: Version of the reference verification protocol, bound separately from its id
#: so a version skew is distinguishable from an unknown protocol (§9 row 15).
TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION = "1"

#: The private determination token. Not exported and not reachable from the
#: curated API: it is what separates a determination this authority reached from
#: one a caller assembled.
_DETERMINATION_TOKEN = object()


def _fail(message: str, reason: TrustedEvidenceRefusalReason):
    error = TrustedEvidenceContractError(message)
    error.reason = reason
    return error


def _ordered_reasons(reasons) -> tuple:
    """De-duplicate and sort into the ratified declaration order (ADR §22.13)."""

    unique = set()
    for index, reason in enumerate(reasons):
        if type(reason) is not TrustedEvidenceRefusalReason:
            raise _fail(
                f"refusal reason [{index}] must be exactly a "
                f"TrustedEvidenceRefusalReason (got {type(reason).__name__}); "
                "the vocabulary is closed and a lookalike is refused",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        unique.add(reason)
    return tuple(r for r in _REASON_ORDER if r in unique)


def _ordered_stages(stages, name: str) -> tuple:
    unique = set()
    for index, stage in enumerate(stages):
        if type(stage) is not EvidenceTrustStage:
            raise _fail(
                f"{name}[{index}] must be exactly an EvidenceTrustStage "
                f"(got {type(stage).__name__})",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        if stage not in _REPORTABLE:
            raise _fail(
                f"{name} may not name {stage.value}: ADR §12 rules policy "
                "sufficiency requirement-relative and assigns it to the "
                "consuming evaluation engine under a Policy Authority "
                "requirement, never to TAP",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        unique.add(stage)
    return tuple(s for s in EVIDENCE_TRUST_STAGE_ORDER if s in unique)


class EvidenceAdmissionOutcome(str, Enum):
    """What the authority **established**, as distinct from what was declared.

    Exactly **two** members, and that is the point. ADR §11 rules that
    "indeterminate is a refusal, not a pass", §26.4 that verifier timeout and
    verifier error are "refusals, not passes", and E-9 that nothing "degrades to
    a warning, an advisory, a default-allow". A third member — ``UNKNOWN``,
    ``PARTIAL``, ``PENDING``, ``BEST_EFFORT``, ``DEGRADED`` — would be a
    success-shaped state a consumer could read optimistically, so the vocabulary
    offers none. Indeterminacy is expressed as :attr:`REFUSED` carrying
    ``TRUSTED_EVIDENCE_INDETERMINATE``.

    Distinct from TEV-1's
    :class:`~..contracts.enums.DeclaredVerificationOutcome`, whose members carry
    a ``DECLARED_`` prefix because they are caller-written payload content. These
    members are neither caller-written nor caller-settable: an
    :class:`EvidenceVerificationDetermination` can only be built by this module.
    """

    #: The authority verified the requested stages and admits the evidence.
    #: Admission is not authorization: §13.2 and E-12 hold that nothing here
    #: authorizes deployment, runtime action, policy sufficiency or value.
    ADMITTED = "ADMITTED"
    #: The authority refused, carrying at least one stable typed reason (E-9).
    REFUSED = "REFUSED"


def derive_receipt_id(
    *,
    verification_request_digest: str,
    verifier_authority_id: str,
    verifier_key_id: str,
    verification_protocol_id: str,
    verification_protocol_version: str,
    verified_at: datetime,
) -> str:
    """Derive the deterministic identifier of one verification act.

    A receipt identifier must be unique per verification act and reproducible by
    anyone re-deriving it — and it cannot come from a random source or a clock,
    because ``random``, ``secrets``, ``uuid``, ``os`` and every clock call are
    banned package-wide so that every output is a pure function of its inputs.
    It is therefore derived: a domain-separated sha-256 over the exact
    coordinates that individuate the act.

    Two verifications of the same evidence by the same authority and key at the
    same instant under the same protocol are the same act and get the same id.
    Change any coordinate — including re-verifying later, which changes
    ``verified_at`` — and the id differs, which is precisely ADR §13.1.7's
    "re-verification issues a **new** receipt".

    The result is prefixed and human-legible rather than a bare digest, so a
    receipt id can never be mistaken for a content digest in a log or a field.
    """

    for name, value in (
        ("verifier_authority_id", verifier_authority_id),
        ("verifier_key_id", verifier_key_id),
        ("verification_protocol_id", verification_protocol_id),
        ("verification_protocol_version", verification_protocol_version),
        ("verification_request_digest", verification_request_digest),
    ):
        require_identifier(value, f"derive_receipt_id.{name}")
    require_aware_datetime(verified_at, "derive_receipt_id.verified_at")
    frame = "".join(
        (
            TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN,
            verification_request_digest,
            verifier_authority_id,
            verifier_key_id,
            verification_protocol_id,
            verification_protocol_version,
            _utc_text(verified_at),
        )
    )
    return "receipt-" + hashlib.sha256(frame.encode("utf-8")).hexdigest()


def _utc_text(value: datetime) -> str:
    """The same UTC rendering the canonical encoder uses (§22.3)."""

    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# --------------------------------------------------------------------------- #
# The verification protocol boundary
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProtocolExecutionResult:
    """What one verification protocol run established, and what it refused.

    A **report from a protocol to the authority**, never a verdict a consumer
    reads. The authority re-checks everything a protocol claims about scope,
    integrity and time before any of it becomes an admission, so a protocol that
    over-claims is caught rather than believed (ADR §8.1).

    ``cleared_stages`` may not name ``POLICY_SUFFICIENT``: §12 places stage 6
    outside TAP entirely.
    """

    protocol_id: str
    protocol_version: str
    cleared_stages: tuple = ()
    refusal_reasons: tuple = ()

    def __post_init__(self) -> None:
        require_identifier(self.protocol_id, "ProtocolExecutionResult.protocol_id")
        require_identifier(
            self.protocol_version, "ProtocolExecutionResult.protocol_version"
        )
        for name in ("cleared_stages", "refusal_reasons"):
            value = getattr(self, name)
            if not isinstance(value, (list, tuple, set, frozenset)):
                raise _fail(
                    f"ProtocolExecutionResult.{name} must be a list, tuple or "
                    f"set (got {type(value).__name__})",
                    _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
                )
        object.__setattr__(
            self,
            "cleared_stages",
            _ordered_stages(
                self.cleared_stages, "ProtocolExecutionResult.cleared_stages"
            ),
        )
        object.__setattr__(
            self, "refusal_reasons", _ordered_reasons(self.refusal_reasons)
        )
        if self.cleared_stages and self.refusal_reasons:
            raise _fail(
                "ProtocolExecutionResult reports both cleared stages and "
                "refusals; a protocol run either established stages or failed "
                "closed, and E-9 admits no partial pass",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        if not self.cleared_stages and not self.refusal_reasons:
            raise _fail(
                "ProtocolExecutionResult reports neither a cleared stage nor a "
                "refusal; an untyped silence is not an outcome (E-9)",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )

    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self)

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@runtime_checkable
class EvidenceVerificationProtocolPort(Protocol):
    """A named, versioned evidence-verification protocol (ADR §9 row 15).

    Substitutable: a deployment may run a different protocol — a different
    producer-attestation scheme, a different chain-of-custody check — and bind
    its own id and version into the receipt. What it may **not** do is escape
    the authority's independent re-check, or return a stage the ADR does not let
    TAP establish.
    """

    @property
    def protocol_id(self) -> str:
        """Stable protocol identity, bound into the receipt and its signature."""
        ...

    @property
    def protocol_version(self) -> str:
        """Protocol version, bound separately so a skew is distinguishable."""
        ...

    def run_protocol(
        self,
        *,
        submission: SignedEvidenceSubmission,
        request: EvidenceVerificationRequest,
        trust_anchors: TrustAnchorResolverPort,
        as_of: datetime,
    ) -> ProtocolExecutionResult:
        """Run the protocol. Must not read a clock; ``as_of`` is the instant.

        Named ``run_protocol`` rather than ``execute``: ADR §6.4 records that
        "execution" already names a different thing in Agent Runtime and
        ``risk-authority-execution-assurance``, and a verification protocol run
        is not a runtime execution. E-14 keeps TAP off the runtime path
        entirely, so the vocabulary should not suggest otherwise.
        """
        ...


class Ed25519EvidenceAuthenticityProtocol:
    """The reference protocol: producer-signature verification (§12 stage 2).

    Resolves the producer's trust anchor at the exact
    ``(producer_authority_id, producer_key_id, EVIDENCE_PRODUCTION)`` coordinate,
    checks its lifecycle at ``as_of``, reconstructs the signed evidence frame,
    and verifies the signature. On success it reports
    ``CRYPTOGRAPHICALLY_AUTHENTIC`` and ``PROVENANCE_VERIFIED``; on any failure
    it reports the typed refusal and clears nothing.

    Why ``PROVENANCE_VERIFIED`` is included, and what it does not mean
    ------------------------------------------------------------------
    ADR §12 stage 3 asks whether "the chain of custody from an **authorized
    producer** is intact". A verified producer signature over the evidence — an
    evidence identity whose canonical bytes include its own
    :class:`~..contracts.identity.EvidenceProvenanceChain` — establishes exactly
    that: the named authorized producer committed to that chain, and the chain
    has not been altered since. It does **not** establish that each custody hop
    independently attested its own link, which would need per-hop signatures the
    ADR does not define and DD-7 keeps open. A protocol needing that stronger
    property is a different protocol with a different id.

    It never reports ``CONTEXT_SYSTEM_BOUND`` or ``CURRENTLY_VALID``. Those are
    the authority's own re-checks (§8.1), and a protocol claiming them would be
    claiming the very thing the re-check exists to establish independently.
    """

    __slots__ = ()

    @property
    def protocol_id(self) -> str:
        return TRUSTED_EVIDENCE_PROTOCOL_V1_ID

    @property
    def protocol_version(self) -> str:
        return TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION

    def run_protocol(
        self,
        *,
        submission: SignedEvidenceSubmission,
        request: EvidenceVerificationRequest,
        trust_anchors: TrustAnchorResolverPort,
        as_of: datetime,
    ) -> ProtocolExecutionResult:
        require_exact_type(
            submission,
            SignedEvidenceSubmission,
            "Ed25519EvidenceAuthenticityProtocol.submission",
        )
        require_exact_type(
            request,
            EvidenceVerificationRequest,
            "Ed25519EvidenceAuthenticityProtocol.request",
        )
        require_aware_datetime(
            as_of, "Ed25519EvidenceAuthenticityProtocol.as_of"
        )
        refused = self._refuse
        if submission.evidence != request.evidence:
            return refused(_R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH)
        coordinate = TrustAnchorCoordinate(
            authority_id=submission.producer_authority_id,
            key_id=submission.producer_key_id,
            capability=TrustAnchorCapability.EVIDENCE_PRODUCTION,
        )
        resolution = trust_anchors.resolve(coordinate)
        if resolution.anchor is None:
            return refused(resolution.refusal_reason)
        anchor = resolution.anchor
        if anchor.signature_profile != submission.signature_profile:
            return refused(_R.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED)
        lifecycle_refusal = anchor.lifecycle_refusal_at(as_of)
        if lifecycle_refusal is not None:
            return refused(lifecycle_refusal)
        expected = signed_evidence_input_bytes(
            evidence=submission.evidence,
            producer_authority_id=submission.producer_authority_id,
            producer_key_id=submission.producer_key_id,
            signature_profile=submission.signature_profile,
        )
        if not anchor.verification_key().verify(expected, submission.signature_bytes()):
            return refused(_R.TRUSTED_EVIDENCE_SIGNATURE_INVALID)
        return ProtocolExecutionResult(
            protocol_id=self.protocol_id,
            protocol_version=self.protocol_version,
            cleared_stages=(
                EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
                EvidenceTrustStage.PROVENANCE_VERIFIED,
            ),
        )

    def _refuse(self, reason: TrustedEvidenceRefusalReason) -> ProtocolExecutionResult:
        return ProtocolExecutionResult(
            protocol_id=self.protocol_id,
            protocol_version=self.protocol_version,
            refusal_reasons=(reason,),
        )

    def __repr__(self) -> str:
        return "Ed25519EvidenceAuthenticityProtocol()"


# --------------------------------------------------------------------------- #
# The determination
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EvidenceVerificationDetermination:
    """What the authority established. Constructible only by the authority.

    ``issuance_token`` must be the package's private determination token, which
    the curated API does not export. A caller therefore cannot build a
    determination at all — admitted or refused — so
    :class:`~.issuance.ReceiptIssuer` never has to decide whether to *believe* a
    determination handed to it. ADR §8.1.5: "no consumer may manufacture
    verification."

    :attr:`receipt_payload` is present **exactly when** the outcome is
    ``ADMITTED``, and is built by the authority from what it actually verified —
    never from caller-supplied verification coordinates. ADR §13.3's "no
    unsigned 'trusted' receipts" cuts both ways: TEV-2 also mints no receipt
    payload for a refusal, so there is no refused-but-issued artifact to
    misread.

    Refused determinations carry at least one typed reason (E-9), ordered
    deterministically (§22.13).
    """

    outcome: EvidenceAdmissionOutcome
    verification_request_digest: str
    verifier_authority_id: str
    verifier_key_id: str
    verification_protocol_id: str
    verification_protocol_version: str
    verified_at: datetime
    evaluated_at: datetime
    cleared_stages: tuple = ()
    refusal_reasons: tuple = ()
    receipt_payload: Optional[EvidenceVerificationReceiptPayload] = None
    issuance_token: object = None

    def __post_init__(self) -> None:
        if self.issuance_token is not _DETERMINATION_TOKEN:
            raise _fail(
                "EvidenceVerificationDetermination cannot be constructed "
                "directly. A determination is produced only by "
                "EvidenceVerificationAuthority.verify(); a caller-built one "
                "would be exactly the manufactured verification ADR §8.1.5 "
                "prohibits and §10 enumerates as a non-proof",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        require_exact_type(
            self.outcome,
            EvidenceAdmissionOutcome,
            "EvidenceVerificationDetermination.outcome",
        )
        for name in (
            "verification_request_digest",
            "verifier_authority_id",
            "verifier_key_id",
            "verification_protocol_id",
            "verification_protocol_version",
        ):
            require_identifier(
                getattr(self, name), f"EvidenceVerificationDetermination.{name}"
            )
        require_aware_datetime(
            self.verified_at, "EvidenceVerificationDetermination.verified_at"
        )
        require_aware_datetime(
            self.evaluated_at, "EvidenceVerificationDetermination.evaluated_at"
        )
        object.__setattr__(
            self,
            "cleared_stages",
            _ordered_stages(
                self.cleared_stages, "EvidenceVerificationDetermination.cleared_stages"
            ),
        )
        object.__setattr__(
            self, "refusal_reasons", _ordered_reasons(self.refusal_reasons)
        )
        admitted = self.outcome is EvidenceAdmissionOutcome.ADMITTED
        if admitted:
            if self.refusal_reasons:
                raise _fail(
                    "an ADMITTED determination carries refusal reasons; every "
                    "member of the vocabulary is a refusal, so an admission "
                    "carries none",
                    _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
                )
            if self.receipt_payload is None:
                raise _fail(
                    "an ADMITTED determination must carry the receipt payload "
                    "the authority built from what it verified",
                    _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
                )
            require_exact_type(
                self.receipt_payload,
                EvidenceVerificationReceiptPayload,
                "EvidenceVerificationDetermination.receipt_payload",
            )
        else:
            if not self.refusal_reasons:
                raise _fail(
                    "a REFUSED determination must carry at least one stable "
                    "typed reason code (ADR E-9, §11)",
                    _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
                )
            if self.receipt_payload is not None:
                raise _fail(
                    "a REFUSED determination carries a receipt payload; TEV-2 "
                    "issues no artifact for a refusal, so there is no "
                    "refused-but-issued receipt to misread",
                    _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
                )

    @property
    def admitted(self) -> bool:
        """Whether the authority admitted. Derived, never a stored flag.

        Read-only and computed from :attr:`outcome`, which itself cannot be set
        by a caller because the determination cannot be built by one. This is
        deliberately **not** the ``verified=True`` of ADR §10.1: that clause
        forbids treating a *caller-settable* boolean as proof, and there is no
        route by which a caller sets this one.
        """

        return self.outcome is EvidenceAdmissionOutcome.ADMITTED

    @property
    def unestablished_trust_stages(self) -> tuple:
        """The ADR §12 stages this determination did **not** establish.

        Always includes ``POLICY_SUFFICIENT``: stage 6 is requirement-relative
        and never TAP's to establish (§12), so it is unestablished by every
        determination this package can produce, admitted ones included.
        """

        cleared = set(self.cleared_stages)
        return tuple(s for s in EVIDENCE_TRUST_STAGE_ORDER if s not in cleared)

    # No ``canonical_bytes`` / ``canonical_digest``, deliberately.
    #
    # A determination is an **in-process finding**, not an artifact anyone
    # signs, stores or transmits. It also carries the private issuance token,
    # and the canonical encoder's total-field-inclusion rule — every dataclass
    # field, always, no conditional omission — means canonicalizing one would
    # have to either serialize that token or make an exception to a ratified
    # invariant (ADR §22.2). Neither is acceptable, so the type simply is not
    # digestible.
    #
    # The auditable artifact is
    # :class:`~.audit.EvidenceVerificationAuditRecord`, which carries the same
    # act by digest and *is* canonicalizable; the signable artifact is the
    # receipt payload the determination carries.


# --------------------------------------------------------------------------- #
# The authority
# --------------------------------------------------------------------------- #


class EvidenceVerificationAuthority:
    """The platform evidence verification authority (ADR E-1, §7.1).

    Wired at the composition root with a trust-anchor resolver and a
    verification protocol (E-5: "trust anchors and verifier entitlements are
    configured at the composition root, never supplied by the caller of
    verification"). It holds **no signing key** and has no method that produces
    a signature: issuing a receipt is :class:`~.issuance.ReceiptIssuer`'s, under
    §8's separation of roles 3 and 4.

    The ordered checks
    ------------------
    ``verify`` runs a fixed sequence and stops at the first failing group, so
    identical inputs always produce the identical refusal set (§22.13):

    1. **structural** — the submission and request are the ratified types and
       name the same evidence;
    2. **lifecycle** — evidence that is ``REVOKED`` or ``EXPIRED`` is refused
       before anything else is checked (§11 rows 10 and 15);
    3. **integrity and scope** — the request's own
       ``structural_scope_mismatches()`` re-checked here rather than trusted;
    4. **temporal** — the evidence's half-open validity at ``as_of`` (§17.9);
    5. **protocol** — the configured protocol runs and reports;
    6. **coverage** — every stage the caller requested must actually have been
       established, by the protocol or by this authority.

    A missing stage is a refusal, not a partial admission. ADR §12's whole point
    is that stages do not collapse into one another, so "we cleared three of the
    four you asked for" is a refusal with
    ``TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED``.
    """

    __slots__ = ("_authority_id", "_trust_anchors", "_protocol", "_receipt_schema")

    def __init__(
        self,
        *,
        authority_id: str,
        trust_anchors: TrustAnchorResolverPort,
        protocol: EvidenceVerificationProtocolPort,
        receipt_schema: EvidenceSchemaRef,
    ) -> None:
        require_identifier(authority_id, "EvidenceVerificationAuthority.authority_id")
        if not hasattr(trust_anchors, "resolve"):
            raise _fail(
                "EvidenceVerificationAuthority.trust_anchors must implement "
                "TrustAnchorResolverPort.resolve; ADR E-8 makes an unconfigured "
                "verifier a denial, not an absent check — pass "
                "DenyAllTrustAnchorDirectory() to deny explicitly",
                _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED,
            )
        for name in ("protocol_id", "protocol_version", "run_protocol"):
            if not hasattr(protocol, name):
                raise _fail(
                    "EvidenceVerificationAuthority.protocol must implement "
                    f"EvidenceVerificationProtocolPort (missing {name!r})",
                    _R.TRUSTED_EVIDENCE_PROTOCOL_UNSUPPORTED,
                )
        require_exact_type(
            receipt_schema,
            EvidenceSchemaRef,
            "EvidenceVerificationAuthority.receipt_schema",
        )
        object.__setattr__(self, "_authority_id", authority_id)
        object.__setattr__(self, "_trust_anchors", trust_anchors)
        object.__setattr__(self, "_protocol", protocol)
        object.__setattr__(self, "_receipt_schema", receipt_schema)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"EvidenceVerificationAuthority is immutable; cannot set {name!r}. "
            "Re-pointing a configured authority's trust anchors or protocol "
            "after construction would bypass the composition root (ADR E-5)."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"EvidenceVerificationAuthority is immutable; cannot delete {name!r}"
        )

    @property
    def authority_id(self) -> str:
        return self._authority_id

    @property
    def protocol_id(self) -> str:
        return self._protocol.protocol_id

    @property
    def protocol_version(self) -> str:
        return self._protocol.protocol_version

    def verify(
        self,
        submission: SignedEvidenceSubmission,
        request: EvidenceVerificationRequest,
        *,
        verified_at: datetime,
        verifier_key_id: str,
        receipt_valid_from: Optional[datetime] = None,
        receipt_valid_to: Optional[datetime] = None,
    ) -> EvidenceVerificationDetermination:
        """Verify one evidence submission against one request. Fail-closed.

        ``verified_at`` is ADR §9 row 6, mandatory and explicit; the evaluation
        instant is ``request.as_of``, TEV-1's own mandatory field. Neither has a
        default and no clock is read (§22.9, §22.10).

        ``verifier_key_id`` names the key the resulting receipt will be signed
        under. It is bound into the payload *before* signing so that the payload
        the signature covers already commits to its own key coordinate — a
        receipt cannot later be re-labelled with a different key without
        invalidating the signature.

        Returns a determination. It never raises for a verification failure —
        a refusal is a typed value, not an exception — and never returns
        ``None``.
        """

        require_exact_type(
            submission,
            SignedEvidenceSubmission,
            "EvidenceVerificationAuthority.verify.submission",
        )
        require_exact_type(
            request,
            EvidenceVerificationRequest,
            "EvidenceVerificationAuthority.verify.request",
        )
        require_aware_datetime(
            verified_at, "EvidenceVerificationAuthority.verify.verified_at"
        )
        require_identifier(
            verifier_key_id, "EvidenceVerificationAuthority.verify.verifier_key_id"
        )
        as_of = request.as_of
        request_digest = request.canonical_digest()
        refuse = self._refusal_factory(
            request_digest=request_digest,
            verifier_key_id=verifier_key_id,
            verified_at=verified_at,
            as_of=as_of,
        )

        # 1. structural — the submission must be about the requested evidence.
        if submission.evidence != request.evidence:
            return refuse((_R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH,))

        evidence = request.evidence

        # 2. lifecycle — a revoked or expired artifact is refused up front.
        if evidence.lifecycle_state is EvidenceLifecycleState.REVOKED:
            return refuse((_R.TRUSTED_EVIDENCE_REVOKED,))
        if evidence.lifecycle_state is EvidenceLifecycleState.EXPIRED:
            return refuse((_R.TRUSTED_EVIDENCE_STALE,))

        # 3. integrity and scope — re-checked here, never taken from a caller
        #    or from the protocol (ADR §8.1's independent re-check).
        mismatches = request.structural_scope_mismatches()
        if mismatches:
            return refuse(mismatches)

        # 4. temporal — the evidence's own half-open interval at as_of (§17.9).
        temporal = evidence.temporal_refusal_at(as_of)
        if temporal is not None:
            return refuse((temporal,))

        # 5. protocol — the configured protocol runs and reports.
        result = self._protocol.run_protocol(
            submission=submission,
            request=request,
            trust_anchors=self._trust_anchors,
            as_of=as_of,
        )
        if type(result) is not ProtocolExecutionResult:
            return refuse((_R.TRUSTED_EVIDENCE_VERIFIER_UNAVAILABLE,))
        if result.protocol_id != self._protocol.protocol_id:
            return refuse((_R.TRUSTED_EVIDENCE_PROTOCOL_UNSUPPORTED,))
        if result.protocol_version != self._protocol.protocol_version:
            return refuse((_R.TRUSTED_EVIDENCE_PROTOCOL_VERSION_MISMATCH,))
        if result.refusal_reasons:
            return refuse(result.refusal_reasons)

        # The authority's own stages, established by the checks above and not
        # taken from the protocol's report.
        cleared = set(result.cleared_stages)
        cleared.add(EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE)
        cleared.add(EvidenceTrustStage.CONTEXT_SYSTEM_BOUND)
        cleared.add(EvidenceTrustStage.CURRENTLY_VALID)

        # 6. coverage — every requested stage must actually be established.
        missing = [s for s in request.requested_trust_stages if s not in cleared]
        if missing:
            return refuse((_R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED,))

        cleared_stages = _ordered_stages(
            tuple(cleared), "EvidenceVerificationAuthority.cleared_stages"
        )
        unattempted = tuple(
            s for s in RECEIPT_REPORTABLE_TRUST_STAGES if s not in cleared
        )
        payload = EvidenceVerificationReceiptPayload(
            receipt_id=derive_receipt_id(
                verification_request_digest=request_digest,
                verifier_authority_id=self._authority_id,
                verifier_key_id=verifier_key_id,
                verification_protocol_id=self._protocol.protocol_id,
                verification_protocol_version=self._protocol.protocol_version,
                verified_at=verified_at,
            ),
            schema=self._receipt_schema,
            source_evidence_identity_digest=evidence.canonical_digest(),
            evidence_content_digest=evidence.content_digest,
            verification_request_digest=request_digest,
            scope=evidence.scope,
            verified_at=verified_at,
            verifier_authority_id=self._authority_id,
            verifier_key_id=verifier_key_id,
            verification_protocol_id=self._protocol.protocol_id,
            verification_protocol_version=self._protocol.protocol_version,
            declared_outcome=DeclaredVerificationOutcome.DECLARED_ADMITTED,
            declared_cleared_stages=cleared_stages,
            declared_unattempted_stages=unattempted,
            declared_refusal_reasons=(),
            evidence_valid_from=evidence.valid_from,
            evidence_valid_to=evidence.valid_to,
            receipt_valid_from=receipt_valid_from,
            receipt_valid_to=receipt_valid_to,
        )
        return EvidenceVerificationDetermination(
            outcome=EvidenceAdmissionOutcome.ADMITTED,
            verification_request_digest=request_digest,
            verifier_authority_id=self._authority_id,
            verifier_key_id=verifier_key_id,
            verification_protocol_id=self._protocol.protocol_id,
            verification_protocol_version=self._protocol.protocol_version,
            verified_at=verified_at,
            evaluated_at=as_of,
            cleared_stages=cleared_stages,
            receipt_payload=payload,
            issuance_token=_DETERMINATION_TOKEN,
        )

    def _refusal_factory(
        self,
        *,
        request_digest: str,
        verifier_key_id: str,
        verified_at: datetime,
        as_of: datetime,
    ):
        def refuse(reasons) -> EvidenceVerificationDetermination:
            return EvidenceVerificationDetermination(
                outcome=EvidenceAdmissionOutcome.REFUSED,
                verification_request_digest=request_digest,
                verifier_authority_id=self._authority_id,
                verifier_key_id=verifier_key_id,
                verification_protocol_id=self._protocol.protocol_id,
                verification_protocol_version=self._protocol.protocol_version,
                verified_at=verified_at,
                evaluated_at=as_of,
                refusal_reasons=tuple(reasons),
                issuance_token=_DETERMINATION_TOKEN,
            )

        return refuse

    def __repr__(self) -> str:
        return (
            "EvidenceVerificationAuthority(authority="
            f"{self._authority_id!r}, protocol={self._protocol.protocol_id!r}"
            f"@{self._protocol.protocol_version!r})"
        )
