"""Typed contract-validation errors for the Ugence Trusted Evidence Authority.

Every rejection this package raises is one of these types. **None of them is
ever the inverse of a verification result**: not raising is not a claim that
anything was verified. These are *structural* refusals at construction time —
the package performs no authenticity check, holds no trust anchor, and reaches
no admission decision (ADR §12, stages 2-6 remain unestablished for every object
this package can build).

The base type subclasses :class:`ValueError`, mirroring
:class:`ugence_governance_contracts...EvidenceContractError` and
:class:`...SystemIdentityContractError`, so existing ``ValueError`` handling in
consuming code still catches a structural rejection.
"""

from __future__ import annotations

from typing import Optional

from .reasons import TrustedEvidenceRefusalReason

__all__ = [
    "TrustedEvidenceContractError",
    "TrustedEvidenceCanonicalizationError",
    "TrustedEvidenceLifecycleError",
]


class TrustedEvidenceContractError(ValueError):
    """A structural trusted-evidence contract invariant was violated.

    Raised at construction time when a coordinate is missing, blank, padded,
    non-canonical, mistyped, temporally impossible, duplicated, or internally
    inconsistent. It signals only that the *shape* was refused.

    It is **never** an assertion that evidence was authentic, attributable,
    in-scope, current, or sufficient for any requirement. Conversely, a
    successfully constructed contract has cleared exactly one of the six ADR §12
    trust stages — ``STRUCTURALLY_CONSTRUCTIBLE`` — and nothing more.
    """

    #: The typed refusal code this structural rejection maps to, when one of the
    #: ratified codes applies. ``None`` when the rejection is a plain caller
    #: fault with no ratified admission-time analogue.
    reason: Optional[TrustedEvidenceRefusalReason] = None


class TrustedEvidenceCanonicalizationError(TrustedEvidenceContractError):
    """The value cannot be canonicalized under the declared, versioned rules.

    Raised for a naive datetime, a non-NFC string, a ``float``, a mapping, a
    ``bytes`` value, or any type the canonical encoder does not admit. These are
    refusals, never coercions: the encoder has no permissive fallback and never
    repairs a value into a serializable shape (ADR §22.8 — "unknown types fail
    closed ... never a best-effort serialization").
    """

    reason = TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT


class TrustedEvidenceLifecycleError(TrustedEvidenceContractError):
    """A proposed evidence lifecycle transition is not in the ratified relation.

    The transition relation is the closed set of arrows drawn in ADR §28. A
    transition outside it is refused; it is never downgraded to a warning and
    never silently applied (E-9).
    """

    reason = TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_INVALID_LIFECYCLE_TRANSITION
