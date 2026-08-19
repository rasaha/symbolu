"""Trust resolution — the Trusted Evidence Authority's store, reused rather than rebuilt.

There is **no second trust-anchor store** in this repository, and Phase 5B-0A does not
create one. Every contract below is TEV's, re-exported here for a caller's convenience and
used unchanged:

``TrustAnchorCoordinate``, ``TrustAnchorRecord``, ``TrustAnchorCapability``,
``TrustAnchorResolution``, ``TrustAnchorResolverPort``, ``KeyRevocation``,
``StaticTrustAnchorDirectory``, ``DenyAllTrustAnchorDirectory``.

They are reusable here because they are **payload-neutral**: not one of them imports an
evidence contract, mentions an evidence type, or presumes anything about what the signed
bytes contain. They answer a single question — "is there a configured, currently-valid,
unrevoked anchor at this exact coordinate?" — and that question is the same whatever the
key signed.

What was *not* reused, and why
------------------------------
TEV's evidence and receipt **verifiers** are not reused, and no evidence-specific verifier
is treated as if it had verified this payload. A producer attestation is not an evidence
item: it has a different schema tag, a different signing purpose, a different field set and
a different framing. A verifier that accepted it would be verifying something it was never
specified against. Phase 5B-0A therefore defines its own verification protocol
(:mod:`.verification`) — and resolves every key through the store above.

Resolution authorizes nothing
-----------------------------
A resolved anchor is an *input* to verification, never a substitute for it. Resolution
performs no signature check, admits nothing and issues nothing.

Reference grade versus production grade
---------------------------------------
The repository classifies ``StaticTrustAnchorDirectory`` as **reference grade** in its own
words: "the deterministic *reference* ``TrustAnchorResolverPort`` … suitable for tests, for
local use, and as the shape a production resolver should present." :func:`require_production_resolver`
therefore refuses it under ``production_mode=True``, following the Risk Authority's
``is_production_authoritative`` convention.

``DenyAllTrustAnchorDirectory`` is admitted in production, because it is the ADR E-8
deny-by-default posture and can only ever refuse: admitting it cannot widen anything. That
is the only "no anchors" posture this package ships, and it is not permissive.
"""

from __future__ import annotations

from datetime import datetime

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

from .canonical import canonical_digest, require_aware_utc, require_exact_type
from .errors import ProducerAttestationConfigurationError as _ConfigError
from .identifiers import PRODUCER_ATTESTATION_CAPABILITY
from .outcomes import ProducerAuthenticityOutcome as _Outcome

__all__ = [
    "TrustAnchorCoordinate",
    "TrustAnchorRecord",
    "TrustAnchorCapability",
    "TrustAnchorResolution",
    "TrustAnchorResolverPort",
    "KeyRevocation",
    "StaticTrustAnchorDirectory",
    "DenyAllTrustAnchorDirectory",
    "producer_anchor_coordinate",
    "anchor_coordinate_digest",
    "anchor_record_digest",
    "anchor_lifecycle_outcome",
    "require_production_resolver",
    "anchor_verification_key",
    "REFERENCE_GRADE_RESOLVERS",
]

#: Resolver types this repository documents as reference grade. Refused in production.
#: ``DenyAllTrustAnchorDirectory`` is deliberately absent: it can only refuse.
REFERENCE_GRADE_RESOLVERS: tuple[type, ...] = (StaticTrustAnchorDirectory,)

#: TEV lifecycle refusal -> this package's typed outcome. Exhaustive over the reasons
#: ``TrustAnchorRecord.lifecycle_refusal_at`` can return; anything else is the default arm.
_LIFECYCLE_OUTCOMES = {
    TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_KEY_REVOKED: _Outcome.ANCHOR_REVOKED,
    TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_KEY_DISABLED: _Outcome.ANCHOR_DISABLED,
    TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_KEY_NOT_YET_VALID: (
        _Outcome.ANCHOR_NOT_YET_VALID
    ),
    TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_KEY_EXPIRED: _Outcome.ANCHOR_EXPIRED,
}


def producer_anchor_coordinate(
    *, issuer: str, producer_key_id: str
) -> TrustAnchorCoordinate:
    """The exact triple a producer attestation's key is looked up by.

    The capability is this package's constant and is **not** a parameter: a caller cannot
    ask for a producer attestation to be verified under the receipt-issuance capability,
    because there is nothing to pass.
    """

    return TrustAnchorCoordinate(
        authority_id=issuer,
        key_id=producer_key_id,
        capability=PRODUCER_ATTESTATION_CAPABILITY,
    )


def anchor_coordinate_digest(coordinate: TrustAnchorCoordinate) -> str:
    """The ``sha256:``-prefixed digest of a trust-anchor coordinate.

    Deliberately **not** TEV's own ``coordinate.canonical_digest()``. That method is
    correct, and it is TEV's identity scheme: it emits bare lowercase hex under TEV's
    canonicalization. Storing a bare-hex value in a Phase 5B-0A artifact would put a second
    digest spelling into a distribution that admits exactly one, and this package's own
    format check refuses a bare-hex digest by design. So the coordinate is re-digested here
    under Risk Authority's scheme — the same scheme every other digest in this package and
    in Phase 5A uses — and there is still no second *canonicalization* anywhere, only the
    one this package has always used.
    """

    require_exact_type(
        "anchor_coordinate_digest.coordinate", coordinate, TrustAnchorCoordinate
    )
    return canonical_digest(coordinate)


def anchor_record_digest(anchor: TrustAnchorRecord) -> str:
    """The ``sha256:``-prefixed digest of a complete trust-anchor record.

    An auditable identity for "which configured anchor was consulted", covering the public
    key, the capability, the lifecycle bounds and the anchor-set coordinates. It is not a
    signature, not an entitlement and not a trust decision. Re-digested under Risk
    Authority's scheme for the reason given in :func:`anchor_coordinate_digest`.
    """

    require_exact_type("anchor_record_digest.anchor", anchor, TrustAnchorRecord)
    return canonical_digest(anchor)


def anchor_lifecycle_outcome(anchor: TrustAnchorRecord, as_of: datetime):
    """The typed outcome of this anchor's lifecycle at ``as_of``, or ``None`` if usable.

    Delegates the decision to TEV's own ``lifecycle_refusal_at`` — revoked first and
    hardest, then disabled, then not-yet-valid, then expired — and maps its typed reason
    onto this package's vocabulary. An unrecognised reason maps to
    :attr:`~.outcomes.ProducerAuthenticityOutcome.ANCHOR_NOT_IN_WINDOW`, which is a
    refusal: a lifecycle answer this package cannot interpret is never a pass.
    """

    instant = require_aware_utc("anchor_lifecycle_outcome.as_of", as_of)
    refusal = anchor.lifecycle_refusal_at(instant)
    if refusal is None:
        return None
    return _LIFECYCLE_OUTCOMES.get(refusal, _Outcome.ANCHOR_NOT_IN_WINDOW)


def require_production_resolver(resolver: object) -> object:
    """Refuse a reference-grade or unattested resolver under production mode.

    Two independent conditions, both fail-closed:

    * a resolver whose exact type this repository classifies as reference grade is
      refused outright — its own docstring says it is for tests and local use;
    * every other resolver must **explicitly opt in** with
      ``is_production_authoritative = True``, following the Risk Authority convention.
      Silence is refusal, so a resolver that has never considered the question cannot
      drift into production by default.

    ``DenyAllTrustAnchorDirectory`` is exempt from the opt-in because it refuses every
    coordinate unconditionally: admitting it cannot widen anything, and refusing it would
    leave a composition root with no ratified deny-by-default posture at all.
    """

    if resolver is None:
        raise _ConfigError(
            "production_mode=True requires an explicit trust-anchor resolver; there is "
            "no default, no fallback and no ambient anchor store"
        )
    if type(resolver) is DenyAllTrustAnchorDirectory:
        return resolver
    for reference_type in REFERENCE_GRADE_RESOLVERS:
        if type(resolver) is reference_type:
            raise _ConfigError(
                f"production_mode=True refuses {reference_type.__name__}: this repository "
                "documents it as the deterministic REFERENCE resolver, 'suitable for "
                "tests, for local use, and as the shape a production resolver should "
                "present'. Inject a production-authoritative resolver "
                "(is_production_authoritative=True) over a managed key service, or use "
                "DenyAllTrustAnchorDirectory to deny by default."
            )
    if getattr(resolver, "is_production_authoritative", False) is not True:
        raise _ConfigError(
            "a production TrustAnchorResolverPort must be production-authoritative "
            "(is_production_authoritative=True); a resolver that has not declared itself "
            "production-grade cannot supply the key a producer attestation is trusted "
            f"under (got {type(resolver).__name__})"
        )
    return resolver


def anchor_verification_key(anchor: TrustAnchorRecord) -> TrustedEvidenceVerificationKey:
    """The anchor's strictly validated public half.

    Re-validates the curve point rather than caching it, so this cannot become a route
    around TEV's construction-time check: identity, small-order, torsion, non-canonical and
    off-curve keys are refused here as well as there.
    """

    require_exact_type("anchor_verification_key.anchor", anchor, TrustAnchorRecord)
    return anchor.verification_key()
