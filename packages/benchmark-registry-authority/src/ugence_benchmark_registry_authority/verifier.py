"""The BR-2C **candidate** verifier — the one module that performs cryptography.

Status
------
This is the ``0.3.0rc1`` candidate head, engineered under the owner's ruling
that BR-2C candidate engineering and testing may begin before the D-38
independent external cryptographic reviewer is individually named or the review
commissioned. It is a **candidate only**: it conveys no audit, no independent
review and no production-release claim, and ``0.3.0`` — BR-2C's closure — is
not taken until that review has been commissioned and completed (D-32(4),
D-38(i)). No artifact of this distribution may describe this module otherwise.

What is here, and under which rulings
--------------------------------------
* :class:`BenchmarkEd25519Verifier` implements the three seams of
  :class:`~.contracts.ports.BenchmarkApprovalVerifierPort` (D-24, D-26) over an
  injected :class:`~.contracts.ports.BenchmarkPublisherTrustDirectoryPort`
  (D-25, D-34). It reconstructs each envelope's signing input from the pinned
  :data:`~.contracts.envelopes.BENCHMARK_SIGNING_FRAME_SPECIFICATION`, evaluates
  the resolved anchor on :data:`~.contracts.trust.BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER`
  at the **explicit trusted instant** (D-27, D-28), admits the anchor's key
  material only after strict point validation, and verifies the detached
  signature under the single ratified profile (D-29).
* :class:`BenchmarkDenyAllVerifier` is the **exact deny-all default** §35.1's
  BR-2C row requires the injected verifier to default to: every seam refuses
  with ``NO_TRUST_ANCHOR_CONFIGURED``, consults no directory and admits no key.
* **D-41's division of labour**, exactly: ``cryptography`` verifies the Ed25519
  signature; ``PyNaCl`` (libsodium ``crypto_core_ed25519_is_valid_point``)
  validates the public-key point at the moment the anchor's key material enters
  verification. Measured on this pair, ``cryptography`` alone accepts a
  signature forged without any private key under the identity point, its
  non-canonical encoding, the order-2 point, one order-4 point and a ``y ≥ p``
  encoding; the libsodium check refuses every one of them and every other
  small-order or non-canonical encoding — that is why the second backend is
  load-bearing and not decorative.
* **D-40's release transition**, as ratified for the candidate rung: the two
  libraries are imported **only in this module** and only for those two roles.
  Every other dependency-boundary prohibition stands — no
  ``ugence_trusted_evidence_authority``, no Policy Authority or Risk Authority
  Ed25519 code, no reuse of any other Ugence Ed25519 implementation. The
  shape of the strict-corpus discipline is copied from the trusted-evidence
  layer's closure findings; its code is never imported (D-22(4)).
* **D-39 and D-42**: parsing is private — nothing here is exported beyond the
  two verifier classes, no parser API exists — and every malformation of an
  external artifact that reaches a seam is expressed as a typed ``REFUSED``
  result, never raised past it. A key identifier or public key that fails its
  encoding refuses ``INDETERMINATE``; a signature that fails its encoding or its
  verification refuses ``SIGNATURE_INVALID``; a contract error carrying no
  ratified reason refuses ``INDETERMINATE`` (D-42(d)).

What raises, and what refuses
------------------------------
D-42 separates contract construction from the verification seam. The seam's
**inputs are contracts**: an envelope that is not exactly the declared envelope
type, or a trusted instant that is not timezone-aware, is a caller's contract
violation and raises :class:`~.contracts.errors.BenchmarkRegistryContractError`
before any evaluation begins — there is no envelope digest to bind a refusal
to. Everything after that point — anchor resolution, the resolved record, its
lifecycle, its key material, the signature — is an evaluation of external trust
state and is **returned** as a verified result, never raised. A directory that
raises, returns the wrong type or answers a different triple than it was asked
refuses ``INDETERMINATE`` (D-28: never a fallback to a cached, default or
previously successful answer; Q-2C-5: a resolver unreachable in flight refuses
through ``INDETERMINATE``).

What this module does not do
-----------------------------
It holds no anchor, mints none, reads no clock, signs nothing, admits nothing,
registers nothing, revokes nothing and resolves no benchmark. A ``VERIFIED``
result establishes cryptographic verification against one anchor revision at
one instant and nothing else: every result still carries §09's five
permanently-``False`` authority derivations. No composition root exists yet
(BR-2D); nothing here is wired to one.

Tests: ``tests/contract/test_verifier.py`` (the seams, the strict corpus, the
frame reconstruction, the D-28 order and every refusal mapping) and
``tests/packaging/test_milestone_boundary.py`` (the import confinement).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Tuple, Type, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from nacl.bindings import crypto_core_ed25519_is_valid_point

from .contracts._validation import (
    require_aware_datetime,
    require_exact_type,
    require_key_identifier,
    require_public_key_material,
)
from .contracts.canonical import _format_datetime, canonical_digest
from .contracts.enums import (
    BenchmarkSignatureProfile,
    BenchmarkTrustAnchorStatus,
    BenchmarkTrustRole,
    BenchmarkVerificationOutcome,
)
from .contracts.envelopes import (
    BENCHMARK_SIGNING_FRAME_SPECIFICATION,
    BenchmarkApprovalEnvelope,
    BenchmarkPublisherSubmissionEnvelope,
    BenchmarkRevocationEnvelope,
)
from .contracts.errors import BenchmarkRegistryContractError
from .contracts.ports import BenchmarkPublisherTrustDirectoryPort
from .contracts.reasons import BenchmarkRegistryRefusalReason
from .contracts.trust import (
    BENCHMARK_VERIFICATION_REFUSAL_REASONS,
    BenchmarkApprovalVerifiedResult,
    BenchmarkPublisherVerifiedResult,
    BenchmarkRevocationVerifiedResult,
    BenchmarkTrustAnchorRecord,
    BenchmarkTrustAnchorResolution,
)

__all__ = [
    "BenchmarkDenyAllVerifier",
    "BenchmarkEd25519Verifier",
]

_Envelope = Union[
    BenchmarkPublisherSubmissionEnvelope,
    BenchmarkApprovalEnvelope,
    BenchmarkRevocationEnvelope,
]

#: The Ed25519 group order ``L`` (RFC 8032 §5.1). A signature's scalar ``S``
#: must satisfy ``0 <= S < L``; §5.1.7 rejects anything else, and enforcing it
#: here as well as in the backend removes the malleable ``S + L`` form before
#: the backend is asked, so the refusal does not depend on which backend a
#: later maintainer substitutes.
_ED25519_GROUP_ORDER = 2**252 + 27742317777372353535851937790883648493

#: Element-length prefix width and bound (uint32, big-endian) from the frame.
_LENGTH_PREFIX_BYTES = 4
_MAX_ELEMENT_LENGTH = 2**32 - 1


class _Refused(Exception):
    """Internal: carries a ratified refusal reason and, when an anchor was
    resolved before the refusal, the revision it was evaluated against. Never
    escapes the seam."""

    def __init__(
        self,
        reason: BenchmarkRegistryRefusalReason,
        anchor_record_digest: Optional[str] = None,
    ) -> None:
        super().__init__(reason.value)
        self.reason = reason
        self.anchor_record_digest = anchor_record_digest


def _reason_of(error: BaseException) -> BenchmarkRegistryRefusalReason:
    """D-42(d): a contract error's attached reason, if it is one a verified
    result may carry; otherwise ``INDETERMINATE``. Never success, never an
    escaping exception."""

    reason = getattr(error, "reason", None)
    if isinstance(reason, BenchmarkRegistryRefusalReason) and (
        reason in BENCHMARK_VERIFICATION_REFUSAL_REASONS
    ):
        return reason
    return BenchmarkRegistryRefusalReason.INDETERMINATE


def _element_bytes(value: object, path: str) -> bytes:
    """One frame element's UTF-8 bytes, per the pinned element encoding."""

    if isinstance(value, Enum):
        value = value.value
    elif isinstance(value, datetime):
        value = _format_datetime(value, path)
    if type(value) is not str:
        raise _Refused(BenchmarkRegistryRefusalReason.INDETERMINATE)
    encoded = value.encode("utf-8")
    if len(encoded) > _MAX_ELEMENT_LENGTH:
        raise _Refused(BenchmarkRegistryRefusalReason.INDETERMINATE)
    return len(encoded).to_bytes(_LENGTH_PREFIX_BYTES, "big") + encoded


def _signing_input(envelope: _Envelope) -> bytes:
    """Reconstruct ``SIGNING_INPUT`` exactly as the pinned frame specifies.

    Reads the element order from :data:`BENCHMARK_SIGNING_FRAME_SPECIFICATION`
    rather than restating it, so the verifier and the specification cannot
    disagree: an element added to the frame is an element this reads. Dotted
    names walk into the nested BR-1 coordinate; every derived property in the
    order (``publisher_submission_envelope_digest``) is read as the live
    recomputed property, never a stored field.
    """

    frame = BENCHMARK_SIGNING_FRAME_SPECIFICATION["frames"][type(envelope).__name__]
    parts = []
    for element in frame["element_order"]:
        value: object = envelope
        for step in element.split("."):
            value = getattr(value, step)
        parts.append(_element_bytes(value, element))
    return b"".join(parts)


def _admit_anchor_key(anchor: BenchmarkTrustAnchorRecord) -> Ed25519PublicKey:
    """Admit the anchor's key material into verification — the F-01/F-03 seam.

    The record validated the material as an **encoding** (D-04; 64 lowercase hex
    characters). Here, and nowhere earlier, the bytes are decoded and the point
    is checked with libsodium's ``crypto_core_ed25519_is_valid_point``, which
    refuses the identity, every small-order point, every non-canonical encoding
    and every ``y ≥ p`` encoding. Only a point that survives is handed to the
    signature backend. Any failure refuses ``INDETERMINATE``, the reason D-42
    pins for malformed public-key material; the anchor revision is carried so
    the refusal names which key was refused.
    """

    revision = anchor.anchor_record_digest
    try:
        material = require_public_key_material(
            anchor.public_key_material, "public_key_material"
        )
        raw = bytes.fromhex(material)
        if len(raw) != 32 or not crypto_core_ed25519_is_valid_point(raw):
            raise _Refused(BenchmarkRegistryRefusalReason.INDETERMINATE, revision)
        return Ed25519PublicKey.from_public_bytes(raw)
    except _Refused:
        raise
    except Exception:
        raise _Refused(BenchmarkRegistryRefusalReason.INDETERMINATE, revision)


def _signature_bytes(detached_signature: object, revision: str) -> bytes:
    """Decode the detached signature and apply RFC 8032 §5.1.7's ``S < L``.

    The envelope validated the encoding (128 lowercase hex characters). A
    scalar at or above the group order is the malleable form of a genuine
    signature and is refused ``SIGNATURE_INVALID`` before the backend is
    consulted.
    """

    try:
        if type(detached_signature) is not str:
            raise _Refused(BenchmarkRegistryRefusalReason.SIGNATURE_INVALID, revision)
        raw = bytes.fromhex(detached_signature)
    except _Refused:
        raise
    except Exception:
        raise _Refused(BenchmarkRegistryRefusalReason.SIGNATURE_INVALID, revision)
    if len(raw) != 64:
        raise _Refused(BenchmarkRegistryRefusalReason.SIGNATURE_INVALID, revision)
    if int.from_bytes(raw[32:], "little") >= _ED25519_GROUP_ORDER:
        raise _Refused(BenchmarkRegistryRefusalReason.SIGNATURE_INVALID, revision)
    return raw


def _evaluate_lifecycle(
    anchor: BenchmarkTrustAnchorRecord, trusted_instant: datetime, revision: str
) -> None:
    """D-28's four terms, in :data:`BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER`.

    Revoked before disabled before not-yet-valid before expired, so a revoked
    anchor whose interval has also elapsed refuses ``TRUST_ANCHOR_REVOKED`` —
    revocation is retroactive and expiry is not, and the weaker condition
    would understate what happened. The interval is half-open
    ``[validity_from, validity_to)``, and the instant is the caller's explicit
    trusted instant, never a clock read.
    """

    if anchor.status is BenchmarkTrustAnchorStatus.REVOKED:
        raise _Refused(BenchmarkRegistryRefusalReason.TRUST_ANCHOR_REVOKED, revision)
    if anchor.status is BenchmarkTrustAnchorStatus.DISABLED:
        raise _Refused(BenchmarkRegistryRefusalReason.TRUST_ANCHOR_DISABLED, revision)
    if anchor.status is not BenchmarkTrustAnchorStatus.ENABLED:
        raise _Refused(BenchmarkRegistryRefusalReason.INDETERMINATE, revision)
    if trusted_instant < anchor.validity_from:
        raise _Refused(
            BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_YET_VALID, revision
        )
    if trusted_instant >= anchor.validity_to:
        raise _Refused(BenchmarkRegistryRefusalReason.TRUST_ANCHOR_EXPIRED, revision)


def _admit_inputs(
    envelope: object,
    expected: Type[_Envelope],
    trusted_instant: object,
) -> Tuple[str, datetime]:
    """The seam's contract-side preconditions. These **raise** (D-42(a)).

    Exactly the declared envelope type — a subclass or a duck-typed lookalike is
    refused because contract identity is load-bearing — and a timezone-aware
    trusted instant. Then the envelope's canonical digest, which revalidates
    the whole graph, so an envelope corrupted after construction cannot be
    bound into any result.
    """

    require_exact_type(envelope, expected, "envelope")
    instant = require_aware_datetime(trusted_instant, "trusted_instant")
    return canonical_digest(envelope), instant


def _refusal(
    reason: BenchmarkRegistryRefusalReason, anchor_record_digest: Optional[str]
) -> Tuple[BenchmarkVerificationOutcome, BenchmarkRegistryRefusalReason, Optional[str]]:
    return BenchmarkVerificationOutcome.REFUSED, reason, anchor_record_digest


class BenchmarkEd25519Verifier:
    """The candidate Ed25519 verifier over an injected trust directory.

    Satisfies :class:`~.contracts.ports.BenchmarkApprovalVerifierPort`. Holds
    exactly one collaborator, the role-scoped directory the composition root
    owns (D-04), and consults it by the exact ``(role, identity, key_id)``
    triple the envelope declares — the publisher seam asks the ``PUBLISHER``
    namespace, the approval seam the ``APPROVER`` namespace and the revocation
    seam the ``REVOKER`` namespace, so an anchor authorized for one role never
    verifies another (D-26).

    Every verification is a fresh evaluation of one envelope against one anchor
    revision at one trusted instant, and nothing is memoized (D-21).
    """

    __slots__ = ("_trust_directory",)

    def __init__(self, trust_directory: BenchmarkPublisherTrustDirectoryPort) -> None:
        if not isinstance(trust_directory, BenchmarkPublisherTrustDirectoryPort):
            raise BenchmarkRegistryContractError(
                "trust_directory must satisfy BenchmarkPublisherTrustDirectoryPort "
                "(a resolve_anchor(role, identity, key_id) seam); the verifier "
                "holds no anchors of its own and refuses to be composed without "
                "a directory to ask"
            )
        if isinstance(trust_directory, type):
            raise BenchmarkRegistryContractError(
                "trust_directory must be a directory instance, not a class"
            )
        self._trust_directory = trust_directory

    # ------------------------------------------------------------------ seams
    def verify_publisher_submission(
        self,
        envelope: BenchmarkPublisherSubmissionEnvelope,
        trusted_instant: datetime,
    ) -> BenchmarkPublisherVerifiedResult:
        digest, instant = _admit_inputs(
            envelope, BenchmarkPublisherSubmissionEnvelope, trusted_instant
        )
        outcome, reason, revision = self._evaluate(
            envelope,
            BenchmarkTrustRole.PUBLISHER,
            envelope.publisher_identity,
            envelope.publisher_key_id,
            instant,
        )
        return BenchmarkPublisherVerifiedResult(
            verified_digest=digest,
            signer_role=BenchmarkTrustRole.PUBLISHER,
            signer_identity=envelope.publisher_identity,
            signer_key_id=envelope.publisher_key_id,
            signature_profile=envelope.signature_profile,
            anchor_record_digest=revision,
            evaluated_at=instant,
            outcome=outcome,
            refusal_reason=reason,
        )

    def verify_approval(
        self,
        envelope: BenchmarkApprovalEnvelope,
        trusted_instant: datetime,
    ) -> BenchmarkApprovalVerifiedResult:
        digest, instant = _admit_inputs(
            envelope, BenchmarkApprovalEnvelope, trusted_instant
        )
        outcome, reason, revision = self._evaluate(
            envelope,
            BenchmarkTrustRole.APPROVER,
            envelope.approval_authority_identity,
            envelope.approval_authority_key_id,
            instant,
        )
        return BenchmarkApprovalVerifiedResult(
            verified_digest=digest,
            signer_role=BenchmarkTrustRole.APPROVER,
            signer_identity=envelope.approval_authority_identity,
            signer_key_id=envelope.approval_authority_key_id,
            signature_profile=envelope.signature_profile,
            anchor_record_digest=revision,
            evaluated_at=instant,
            outcome=outcome,
            refusal_reason=reason,
        )

    def verify_revocation(
        self,
        envelope: BenchmarkRevocationEnvelope,
        trusted_instant: datetime,
    ) -> BenchmarkRevocationVerifiedResult:
        digest, instant = _admit_inputs(
            envelope, BenchmarkRevocationEnvelope, trusted_instant
        )
        outcome, reason, revision = self._evaluate(
            envelope,
            BenchmarkTrustRole.REVOKER,
            envelope.revoker_identity,
            envelope.revoker_key_id,
            instant,
        )
        return BenchmarkRevocationVerifiedResult(
            verified_digest=digest,
            signer_role=BenchmarkTrustRole.REVOKER,
            signer_identity=envelope.revoker_identity,
            signer_key_id=envelope.revoker_key_id,
            signature_profile=envelope.signature_profile,
            anchor_record_digest=revision,
            evaluated_at=instant,
            outcome=outcome,
            refusal_reason=reason,
        )

    # ------------------------------------------------------------- evaluation
    def _resolve(
        self, role: BenchmarkTrustRole, identity: str, key_id: str
    ) -> BenchmarkTrustAnchorRecord:
        """Ask the directory for the exact triple; refuse anything but a matching
        resolution. The directory's own two refusals pass through as themselves
        (D-34); every other failure is ``INDETERMINATE`` (D-28)."""

        try:
            key_id = require_key_identifier(key_id, "key_id")
        except BenchmarkRegistryContractError as error:
            raise _Refused(_reason_of(error))
        try:
            resolution = self._trust_directory.resolve_anchor(role, identity, key_id)
        except Exception:
            raise _Refused(BenchmarkRegistryRefusalReason.INDETERMINATE)
        if type(resolution) is not BenchmarkTrustAnchorResolution:
            raise _Refused(BenchmarkRegistryRefusalReason.INDETERMINATE)
        if (
            resolution.role is not role
            or resolution.identity != identity
            or resolution.key_id != key_id
        ):
            raise _Refused(BenchmarkRegistryRefusalReason.INDETERMINATE)
        if resolution.refusal_reason is not None:
            refused = resolution.refusal_reason
            if refused not in BENCHMARK_VERIFICATION_REFUSAL_REASONS:
                refused = BenchmarkRegistryRefusalReason.INDETERMINATE
            raise _Refused(refused)
        anchor = resolution.anchor
        if type(anchor) is not BenchmarkTrustAnchorRecord:
            raise _Refused(BenchmarkRegistryRefusalReason.INDETERMINATE)
        return anchor

    def _evaluate(
        self,
        envelope: _Envelope,
        role: BenchmarkTrustRole,
        identity: str,
        key_id: str,
        trusted_instant: datetime,
    ) -> Tuple[
        BenchmarkVerificationOutcome,
        Optional[BenchmarkRegistryRefusalReason],
        Optional[str],
    ]:
        """Resolve, evaluate, admit, verify — returning, never raising.

        The broad ``except Exception`` at the end is the fail-closed catch-all
        D-42(d) requires of the seam: an exception the mapping above did not
        classify is an undeterminable condition and refuses ``INDETERMINATE``.
        It is the opposite of a permissive fallback — nothing is retried,
        cached, defaulted or assumed fine.
        """

        try:
            anchor = self._resolve(role, identity, key_id)
            revision = anchor.anchor_record_digest
            if anchor.signature_profile is not envelope.signature_profile or (
                envelope.signature_profile
                is not BenchmarkSignatureProfile.ED25519_SHA512_V1
            ):
                raise _Refused(BenchmarkRegistryRefusalReason.INDETERMINATE, revision)
            _evaluate_lifecycle(anchor, trusted_instant, revision)
            public_key = _admit_anchor_key(anchor)
            signature = _signature_bytes(envelope.detached_signature, revision)
            message = _signing_input(envelope)
            try:
                public_key.verify(signature, message)
            except InvalidSignature:
                raise _Refused(BenchmarkRegistryRefusalReason.SIGNATURE_INVALID, revision)
            return BenchmarkVerificationOutcome.VERIFIED, None, revision
        except _Refused as refused:
            return _refusal(refused.reason, refused.anchor_record_digest)
        except BenchmarkRegistryContractError as error:
            return _refusal(_reason_of(error), None)
        except Exception:
            return _refusal(BenchmarkRegistryRefusalReason.INDETERMINATE, None)


class BenchmarkDenyAllVerifier:
    """The exact deny-all default: every seam refuses ``NO_TRUST_ANCHOR_CONFIGURED``.

    Satisfies :class:`~.contracts.ports.BenchmarkApprovalVerifierPort` and is
    what a composition root gets until it deliberately injects a configured
    verifier (§35.1 BR-2C row; D-04's first constraint). It holds no directory,
    consults nothing, decodes nothing and never returns ``VERIFIED`` — the
    refusal is unconditional on the envelope's content, and the only facts it
    binds are the envelope's digest, the declared signer, and the caller's
    trusted instant, so a deny-all answer is as evidence-bound and as
    non-reusable as any other (D-21, D-24).

    Not a placeholder and not a stub: it is the ratified default posture, it is
    total, and it cannot be flipped — there is no field on it to flip.
    """

    __slots__ = ()

    @staticmethod
    def _deny(
        envelope: object, expected: Type[_Envelope], trusted_instant: object
    ) -> Tuple[str, datetime]:
        return _admit_inputs(envelope, expected, trusted_instant)

    def verify_publisher_submission(
        self,
        envelope: BenchmarkPublisherSubmissionEnvelope,
        trusted_instant: datetime,
    ) -> BenchmarkPublisherVerifiedResult:
        digest, instant = self._deny(
            envelope, BenchmarkPublisherSubmissionEnvelope, trusted_instant
        )
        return BenchmarkPublisherVerifiedResult(
            verified_digest=digest,
            signer_role=BenchmarkTrustRole.PUBLISHER,
            signer_identity=envelope.publisher_identity,
            signer_key_id=envelope.publisher_key_id,
            signature_profile=envelope.signature_profile,
            anchor_record_digest=None,
            evaluated_at=instant,
            outcome=BenchmarkVerificationOutcome.REFUSED,
            refusal_reason=BenchmarkRegistryRefusalReason.NO_TRUST_ANCHOR_CONFIGURED,
        )

    def verify_approval(
        self,
        envelope: BenchmarkApprovalEnvelope,
        trusted_instant: datetime,
    ) -> BenchmarkApprovalVerifiedResult:
        digest, instant = self._deny(envelope, BenchmarkApprovalEnvelope, trusted_instant)
        return BenchmarkApprovalVerifiedResult(
            verified_digest=digest,
            signer_role=BenchmarkTrustRole.APPROVER,
            signer_identity=envelope.approval_authority_identity,
            signer_key_id=envelope.approval_authority_key_id,
            signature_profile=envelope.signature_profile,
            anchor_record_digest=None,
            evaluated_at=instant,
            outcome=BenchmarkVerificationOutcome.REFUSED,
            refusal_reason=BenchmarkRegistryRefusalReason.NO_TRUST_ANCHOR_CONFIGURED,
        )

    def verify_revocation(
        self,
        envelope: BenchmarkRevocationEnvelope,
        trusted_instant: datetime,
    ) -> BenchmarkRevocationVerifiedResult:
        digest, instant = self._deny(envelope, BenchmarkRevocationEnvelope, trusted_instant)
        return BenchmarkRevocationVerifiedResult(
            verified_digest=digest,
            signer_role=BenchmarkTrustRole.REVOKER,
            signer_identity=envelope.revoker_identity,
            signer_key_id=envelope.revoker_key_id,
            signature_profile=envelope.signature_profile,
            anchor_record_digest=None,
            evaluated_at=instant,
            outcome=BenchmarkVerificationOutcome.REFUSED,
            refusal_reason=BenchmarkRegistryRefusalReason.NO_TRUST_ANCHOR_CONFIGURED,
        )
