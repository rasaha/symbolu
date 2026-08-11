"""Authority-status freshness + snapshot semantics (RA-6 §3, §4, §12).

The hot path already verifies a signed envelope **offline** against a local
:class:`~risk_authority.services.revocation.RevocationState`
(:mod:`risk_authority.services.envelope_verifier`). RA-6 wraps that pure
predicate in a *status snapshot* that also records **whether the local view is
trustworthy**:

* ``as_of`` — the instant of the last successful sync from the authoritative
  store. ``None`` ⇒ **UNINITIALIZED** (cold start / cache wipe / never synced).
* ``tenant_ids`` — which tenants this snapshot has actually synced. A tenant
  absent from the set is UNINITIALIZED *for that tenant* — never silently
  "nothing revoked" (closes R-1, invariant I13).

The freshness policy (RA-6 §3, Policy C) is risk-tiered bounded staleness:

    age = now − as_of
    UNINITIALIZED (as_of is None, or tenant not covered)  → DENY, every tier
    age > max_staleness(tier)                             → DENY
    0 < age ≤ max_staleness(tier)                         → ALLOW_WITH_BOUNDED_STALE_STATUS
    age ≈ 0                                               → ALLOW

The leaf keeps the ``RevocationState`` predicate pure; the init/``as_of``
metadata lives here in the status wrapper (RA-6 §3.3, §12). This module is
stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional

from ..crypto.keys import KeyRing
from ..domain.enums import RiskClass
from ..domain.envelope import RiskAuthorizationEnvelope
from .envelope_verifier import EnvelopeVerifier
from .revocation import RevocationState

__all__ = [
    "AUTHORITY_STATUS_SCHEMA_VERSION",
    "ALLOW",
    "ALLOW_WITH_BOUNDED_STALE_STATUS",
    "DENY",
    "StalenessPolicy",
    "AuthorityStatusSnapshot",
    "AuthorityStatus",
    "evaluate_status_freshness",
    "check_authority_status",
]

AUTHORITY_STATUS_SCHEMA_VERSION = "1"

# Status-check outcome vocabulary (RA-6 §14). Canonical RA-6 strings.
ALLOW = "ALLOW"
ALLOW_WITH_BOUNDED_STALE_STATUS = "ALLOW_WITH_BOUNDED_STALE_STATUS"
DENY = "DENY"


@dataclass(frozen=True)
class StalenessPolicy:
    """Risk-tiered bounded-staleness policy (RA-6 §3, Policy C).

    ``max_staleness_seconds`` is per-tier tenant-governance configuration;
    ``platform_ceiling_seconds`` is the hard platform cap the tenant/runtime can
    only tighten below, never widen past (RA-6 §3.4). No numeric business policy
    is canonized by the architecture — these are **fail-closed defaults** a
    deployment overrides. The coherence constraint ``max_staleness(T) ≤
    envelope_TTL(T)`` (RA-6 §10.2) is the deployment's responsibility; this
    object only enforces the platform ceiling and non-negativity.
    """

    max_staleness_seconds: Mapping[RiskClass, float]
    platform_ceiling_seconds: float

    @classmethod
    def fail_closed_defaults(cls) -> "StalenessPolicy":
        """Conservative defaults: higher risk ⇒ tighter freshness requirement.

        These are intentionally small and are NOT a canonized business policy —
        a deployment sets its own values under governance. HIGH/CRITICAL default
        to requiring an essentially-fresh snapshot.
        """

        return cls(
            max_staleness_seconds={
                RiskClass.LOW: 300.0,
                RiskClass.MEDIUM: 120.0,
                RiskClass.HIGH: 30.0,
                RiskClass.CRITICAL: 0.0,
            },
            platform_ceiling_seconds=600.0,
        )

    def bound_for(self, tier: Optional[RiskClass]) -> float:
        """Effective staleness bound for ``tier``, clamped to the ceiling.

        An unknown/None tier fails closed: it is treated as CRITICAL (the
        tightest configured bound), so a missing tier can never buy a wider
        staleness allowance.
        """

        effective_tier = tier if isinstance(tier, RiskClass) else RiskClass.CRITICAL
        configured = self.max_staleness_seconds.get(
            effective_tier,
            self.max_staleness_seconds.get(RiskClass.CRITICAL, 0.0),
        )
        return max(0.0, min(float(configured), float(self.platform_ceiling_seconds)))


@dataclass(frozen=True)
class AuthorityStatusSnapshot:
    """A local, bounded-stale view of authoritative authority state (RA-6 §4).

    Carries the pure :class:`RevocationState` predicate plus the freshness
    metadata the hot path needs to decide whether the view is trustworthy. The
    snapshot is read offline — never a synchronous central lookup.
    """

    revocation_state: RevocationState
    as_of: Optional[datetime]
    tenant_ids: frozenset[str] = frozenset()
    schema_version: str = AUTHORITY_STATUS_SCHEMA_VERSION

    @property
    def initialized(self) -> bool:
        """True iff the snapshot has synced at least once (``as_of`` is set)."""

        return self.as_of is not None

    def covers_tenant(self, tenant_id: str) -> bool:
        """True iff this snapshot has synced state for ``tenant_id``.

        An initialized snapshot that has never synced a given tenant is
        UNINITIALIZED *for that tenant* — the R-1 trap, per-tenant.
        """

        return self.initialized and tenant_id in self.tenant_ids

    def age_seconds(self, now: datetime) -> Optional[float]:
        if self.as_of is None:
            return None
        return (now - self.as_of).total_seconds()

    @classmethod
    def uninitialized(cls) -> "AuthorityStatusSnapshot":
        """A cold-start snapshot: initialized=False ⇒ DENY every tier (R-1)."""

        return cls(revocation_state=RevocationState(), as_of=None, tenant_ids=frozenset())


@dataclass(frozen=True)
class AuthorityStatus:
    """The result of an authority-status check (RA-6 §12.1)."""

    outcome: str
    reasons: tuple[str, ...] = ()
    initialized: bool = False
    as_of: Optional[datetime] = None
    age_seconds: Optional[float] = None
    tier: Optional[RiskClass] = None

    @property
    def allowed(self) -> bool:
        return self.outcome in (ALLOW, ALLOW_WITH_BOUNDED_STALE_STATUS)


def evaluate_status_freshness(
    *,
    snapshot: AuthorityStatusSnapshot,
    tenant_id: str,
    tier: Optional[RiskClass],
    now: datetime,
    policy: StalenessPolicy,
) -> AuthorityStatus:
    """Apply Policy C (RA-6 §3) to a snapshot's freshness — no envelope check.

    This is the freshness half only: it decides whether the local view is fresh
    enough to be *trusted* for the given tier. UNINITIALIZED (globally or for the
    tenant) ⇒ DENY for every tier; stale-beyond-bound ⇒ DENY.
    """

    if not snapshot.initialized:
        return AuthorityStatus(
            outcome=DENY,
            reasons=("authority status uninitialized (never synced)",),
            initialized=False,
            as_of=None,
            age_seconds=None,
            tier=tier,
        )
    if not snapshot.covers_tenant(tenant_id):
        return AuthorityStatus(
            outcome=DENY,
            reasons=(f"authority status uninitialized for tenant {tenant_id!r}",),
            initialized=True,
            as_of=snapshot.as_of,
            age_seconds=snapshot.age_seconds(now),
            tier=tier,
        )

    age = snapshot.age_seconds(now)
    bound = policy.bound_for(tier)
    # A snapshot from the future (clock skew) is treated as age 0, not negative.
    effective_age = max(0.0, age if age is not None else 0.0)
    if effective_age > bound:
        return AuthorityStatus(
            outcome=DENY,
            reasons=(
                f"authority status stale: age {effective_age:.3f}s > "
                f"max_staleness {bound:.3f}s for tier "
                f"{(tier.value if isinstance(tier, RiskClass) else 'UNKNOWN')}",
            ),
            initialized=True,
            as_of=snapshot.as_of,
            age_seconds=age,
            tier=tier,
        )

    outcome = ALLOW if effective_age == 0.0 else ALLOW_WITH_BOUNDED_STALE_STATUS
    return AuthorityStatus(
        outcome=outcome,
        reasons=(),
        initialized=True,
        as_of=snapshot.as_of,
        age_seconds=age,
        tier=tier,
    )


def check_authority_status(
    *,
    envelope: RiskAuthorizationEnvelope,
    key_ring: KeyRing,
    snapshot: AuthorityStatusSnapshot,
    tier: Optional[RiskClass],
    now: datetime,
    policy: StalenessPolicy,
    expected_tenant: Optional[str] = None,
    expected_session: Optional[str] = None,
    expected_audience: Optional[str] = None,
) -> AuthorityStatus:
    """Full offline authority-status check for the hot path / last-mile (§8).

    Composes, fail-closed and in order:

      1. **Freshness gate** (Policy C, §3): uninitialized/stale ⇒ DENY before any
         envelope trust is extended.
      2. **Offline envelope verification** (§8): the existing
         :class:`EnvelopeVerifier` re-run against the snapshot's
         ``RevocationState`` at the current ``now`` — signature, time window,
         tenant/session binding, targeted revocation, and authority epoch.

    This is *validity re-verification, not reauthorization*: it re-runs the
    existing offline verifier and adds no lease/nonce/polling primitive. It is
    the same routine used pre-effect for consequential actions (RA-6 §8).
    """

    freshness = evaluate_status_freshness(
        snapshot=snapshot,
        tenant_id=envelope.tenant_id,
        tier=tier,
        now=now,
        policy=policy,
    )
    if freshness.outcome == DENY:
        return freshness

    verification = EnvelopeVerifier().verify(
        envelope=envelope,
        key_ring=key_ring,
        revocation_state=snapshot.revocation_state,
        now=now,
        expected_tenant=expected_tenant,
        expected_audience=expected_audience,
        expected_session=expected_session,
    )
    if not verification.valid:
        return AuthorityStatus(
            outcome=DENY,
            reasons=verification.reasons,
            initialized=True,
            as_of=snapshot.as_of,
            age_seconds=snapshot.age_seconds(now),
            tier=tier,
        )

    # Envelope is valid AND status is fresh-enough for the tier. Preserve the
    # bounded-stale annotation so the caller can record it.
    return freshness
