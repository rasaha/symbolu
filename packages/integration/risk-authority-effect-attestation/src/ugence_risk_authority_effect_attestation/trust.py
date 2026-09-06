"""The Trusted Evidence Authority's trust anchors, reused unchanged (SE-4).

There is **no second trust-anchor store** in this repository and this package
adds none: the coordinate, record, resolution, resolver port, revocation and the
two reference directories are the Trusted Evidence Authority's own objects,
re-exported so a composition root reaches one vocabulary. What this module adds
is the coordinate an effect attester is resolved at — its capability is chosen
by the attester's **role**, never by a caller — and the production posture a
resolver must declare before a verified result can be minted in production.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ugence_trusted_evidence_authority import (
    DenyAllTrustAnchorDirectory,
    KeyRevocation,
    StaticTrustAnchorDirectory,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorRecord,
    TrustAnchorResolution,
    TrustAnchorResolverPort,
    TrustedEvidenceRefusalReason,
    TrustedEvidenceVerificationKey,
)

from .canonical import DIGEST_PREFIX, canonical_digest, require_aware_utc, require_canonical_identifier
from .errors import EffectAttestationConfigurationError as _ConfigError
from .outcomes import EffectAttestationRefusalReason as _Reason
from .roles import EffectAttesterRole, capability_for_role

__all__ = [
    "TrustAnchorCoordinate",
    "TrustAnchorRecord",
    "TrustAnchorCapability",
    "TrustAnchorResolution",
    "TrustAnchorResolverPort",
    "KeyRevocation",
    "StaticTrustAnchorDirectory",
    "DenyAllTrustAnchorDirectory",
    "REFERENCE_GRADE_RESOLVERS",
    "effect_attester_coordinate",
    "anchor_coordinate_digest",
    "anchor_record_digest",
    "anchor_lifecycle_refusal",
    "anchor_verification_key",
    "require_production_resolver",
]

#: Resolver types this repository documents as reference grade. Refused in
#: production, **including every subclass**.
REFERENCE_GRADE_RESOLVERS: tuple = (StaticTrustAnchorDirectory,)

#: TEA lifecycle refusal -> this package's typed reason. Exhaustive over what
#: ``TrustAnchorRecord.lifecycle_refusal_at`` returns.
_LIFECYCLE_REASONS = {
    TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_KEY_REVOKED: _Reason.ANCHOR_REVOKED,
    TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_KEY_DISABLED: _Reason.ANCHOR_DISABLED,
    TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_KEY_NOT_YET_VALID: _Reason.ANCHOR_NOT_YET_VALID,
    TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_KEY_EXPIRED: _Reason.ANCHOR_EXPIRED,
}


def effect_attester_coordinate(
    *, role: EffectAttesterRole, attester_identity: str, attester_key_id: str
) -> TrustAnchorCoordinate:
    """The exact coordinate an attester under ``role`` is resolved at.

    The capability comes from the role and from nowhere else: a caller cannot
    ask for a provider signature to be checked under the observer capability,
    and an anchor filed under the wrong role is simply not at this coordinate.
    """

    return TrustAnchorCoordinate(
        authority_id=require_canonical_identifier("attester_identity", attester_identity),
        key_id=require_canonical_identifier("attester_key_id", attester_key_id),
        capability=capability_for_role(role),
    )


def anchor_coordinate_digest(coordinate: TrustAnchorCoordinate) -> str:
    """This package's digest of the exact coordinate that was resolved."""

    if type(coordinate) is not TrustAnchorCoordinate:
        raise _ConfigError("anchor_coordinate_digest expects exactly a TrustAnchorCoordinate")
    return canonical_digest(
        {
            "authority_id": coordinate.authority_id,
            "key_id": coordinate.key_id,
            "capability": coordinate.capability.value,
        }
    )


def anchor_record_digest(anchor: TrustAnchorRecord) -> str:
    """TEA's own canonical digest of the complete anchor record — the anchor
    revision a result binds. Read through TEA, never recomputed here."""

    if type(anchor) is not TrustAnchorRecord:
        raise _ConfigError("anchor_record_digest expects exactly a TrustAnchorRecord")
    tea_digest = anchor.canonical_digest()
    # TEA spells its digests as bare 64-hex; this package spells every digest
    # ``sha256:<hex>``. The value is TEA's, relabelled, never recomputed.
    if type(tea_digest) is not str or len(tea_digest) != 64 or not set(tea_digest) <= set("0123456789abcdef"):
        raise _ConfigError("TEA returned an anchor digest outside its documented 64-hex form")
    return DIGEST_PREFIX + tea_digest


def anchor_lifecycle_refusal(anchor: TrustAnchorRecord, as_of: datetime) -> Optional[_Reason]:
    """TEA's fixed-order lifecycle evaluation, mapped onto this vocabulary."""

    if type(anchor) is not TrustAnchorRecord:
        raise _ConfigError("anchor_lifecycle_refusal expects exactly a TrustAnchorRecord")
    reason = anchor.lifecycle_refusal_at(require_aware_utc("as_of", as_of))
    if reason is None:
        return None
    return _LIFECYCLE_REASONS.get(reason, _Reason.VERIFICATION_UNAVAILABLE)


def anchor_verification_key(anchor: TrustAnchorRecord) -> TrustedEvidenceVerificationKey:
    """The anchor's strictly validated public half — the D-41 pair with the
    libsodium point check (SE-5), through TEA and never re-implemented here.

    Re-validates the point on every call rather than caching it, so this cannot
    become a route around TEA's construction-time check: identity, small-order,
    torsion, non-canonical and off-curve keys are refused here as well as there.
    """

    if type(anchor) is not TrustAnchorRecord:
        raise _ConfigError("anchor_verification_key expects exactly a TrustAnchorRecord")
    return anchor.verification_key()


def require_production_resolver(resolver: object) -> object:
    """Refuse a reference-grade or unattested resolver under production mode.

    A reference-grade resolver — that type or **any subclass** — is refused
    outright. ``DenyAllTrustAnchorDirectory`` is admitted by exact type because
    it can only refuse. Every other resolver must opt in explicitly with
    ``is_production_authoritative = True``; silence is refusal.
    """

    if resolver is None:
        raise _ConfigError(
            "production_mode=True requires an explicit trust-anchor resolver; there is "
            "no default, no fallback and no ambient anchor store"
        )
    if type(resolver) is DenyAllTrustAnchorDirectory:
        return resolver
    if isinstance(resolver, REFERENCE_GRADE_RESOLVERS):
        raise _ConfigError(
            f"production_mode=True refuses {type(resolver).__name__}: it is, or inherits, "
            "the deterministic REFERENCE resolver, which this repository documents as "
            "suitable for tests and local use. Declaring is_production_authoritative on it "
            "does not lift this refusal."
        )
    if getattr(resolver, "is_production_authoritative", False) is not True:
        raise _ConfigError(
            "a production TrustAnchorResolverPort must be production-authoritative "
            "(is_production_authoritative=True); a resolver that has not declared itself "
            f"production-grade cannot supply an effect attester's key (got "
            f"{type(resolver).__name__})"
        )
    if not isinstance(resolver, TrustAnchorResolverPort):
        raise _ConfigError("the resolver must implement resolve(coordinate) -> TrustAnchorResolution")
    return resolver
