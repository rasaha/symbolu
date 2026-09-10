"""Authority principals and delegation grants (spec §11.2, user brief §6).

A grant constrains *who* may issue *which* class of decision, and bounds the
scope they may grant. Delegation is monotone: ``IssuedAuthority ⊆
DelegatedAuthority`` (spec §29 delegation monotonicity, AC-03).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .enums import AuthorityType, RiskClass
from .scope import Scope, subset_violations

__all__ = ["AuthorityPrincipal", "AuthorityGrant", "authority_violations"]


@dataclass(frozen=True)
class AuthorityPrincipal:
    """An identified principal that may hold authority grants."""

    principal_id: str
    tenant_id: str
    display_name: str = ""


@dataclass(frozen=True)
class AuthorityGrant:
    """A scoped, time-bound, delegated authority to issue risk decisions."""

    principal_id: str
    tenant_id: str
    authority_type: AuthorityType
    domains: tuple[str, ...]
    allowed_risk_classes: tuple[RiskClass, ...]
    max_autonomy: int
    delegated_by: str
    expires_at: Optional[datetime] = None
    # The maximum scope this principal may bind into a decision. A decision's
    # scope must be contained within this grant scope.
    grantable_scope: Scope = field(default_factory=Scope)

    def is_active(self, now: datetime) -> bool:
        """Half-open ``[.., expires_at)`` — expired at exactly ``expires_at``.

        This is an *authorization* gate, not a freshness report: ``authority_violations``
        calls it at the moment a ``RiskDecision`` is minted, and a violation raises
        ``AuthorityDeniedError``. It decides who may issue decisions at all.

        It was previously inclusive, and the boundary instant did not cost a microsecond —
        it cost ninety minutes. A grant expiring at exactly ``now`` was still "active", so
        it minted a decision carrying a full ``DEFAULT_DECISION_TTL``, from which an
        envelope carrying a further ``DEFAULT_ENVELOPE_TTL`` could be issued as late as
        that decision allowed. Machine authority reached 1:29:59.999999 past a delegation
        that had already expired when it was exercised. The operator closes the instant;
        the expiry caps in ``ReferenceDecisionAuthority.issue_decision`` close the reach.
        """

        return self.expires_at is None or now < self.expires_at


def authority_violations(
    grant: AuthorityGrant,
    *,
    tenant_id: str,
    domain: str,
    risk_class: RiskClass,
    autonomy_level: int,
    requested_scope: Scope,
    now: datetime,
) -> list[str]:
    """Return reasons ``grant`` does not cover the requested decision.

    Empty list == the principal is authorized. Any non-empty result means
    Decision Authority must DENY (fail closed).
    """

    reasons: list[str] = []

    if grant.tenant_id != tenant_id:
        reasons.append(
            f"tenant mismatch: grant {grant.tenant_id!r} != request {tenant_id!r}"
        )
    if not grant.is_active(now):
        reasons.append("grant expired")
    if domain not in grant.domains:
        reasons.append(f"domain {domain!r} not in grant domains {list(grant.domains)}")
    if risk_class not in grant.allowed_risk_classes:
        reasons.append(
            f"risk_class {risk_class.value!r} not in "
            f"{[c.value for c in grant.allowed_risk_classes]}"
        )
    if autonomy_level > grant.max_autonomy:
        reasons.append(
            f"autonomy_level {autonomy_level} exceeds grant max_autonomy "
            f"{grant.max_autonomy}"
        )

    reasons.extend(
        f"scope: {v}" for v in subset_violations(requested_scope, grant.grantable_scope)
    )
    return reasons
