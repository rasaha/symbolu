"""Decision Authority — converts an evaluation into a binding ruling (spec §11).

This is the *ruler*, distinct from the Risk Engine evaluator. It proves the
issuing principal holds authority covering the requested decision
(``IssuedAuthority ⊆ DelegatedAuthority``) before issuing, and denies
otherwise (user brief §6–7). The Risk Engine's recommendation is advisory: a
DENY/ESCALATE recommendation is honored as the binding outcome; an ALLOW
recommendation still requires a principal with sufficient authority.

Boundary note (spec §D1/§D2). :class:`DecisionAuthorityPort` is the contract;
:class:`ReferenceDecisionAuthority` is the in-package **reference** ruler that
keeps ``risk_authority`` a stdlib-only leaf and lets the RA-1..RA-4 spine be
proven in isolation. The **canonical production binding-decision authority is
the separately shipped ``ugence-decision-authority`` kernel** (package
``packages/capabilities/decision-authority``); a production deployment adapts
that kernel onto :class:`DecisionAuthorityPort` — through the contract, without
``risk_authority`` importing it, exactly as ``ActionGatePort`` /
``ReferenceActionGate`` relate to ``ugence-actiongate-provider``. The reference
ruler here must not be mistaken for that canonical kernel.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Optional, Protocol, runtime_checkable

from ..domain.authority import AuthorityGrant, authority_violations
from ..domain.decision import RiskDecision
from ..domain.enums import RiskClass, RiskOutcome, RiskRecommendation
from ..domain.errors import AuthorityDeniedError, NoRemainingValidityError
from ..domain.risk_case import RiskDecisionCase
from ..domain.scope import Scope
from .risk_engine import RiskEvaluation

__all__ = [
    "DecisionAuthorityPort",
    "ReferenceDecisionAuthority",
    "DEFAULT_DECISION_TTL",
]

DEFAULT_DECISION_TTL = timedelta(hours=1)

_RECOMMENDATION_TO_OUTCOME = {
    RiskRecommendation.ALLOW: RiskOutcome.ALLOW,
    RiskRecommendation.ALLOW_WITH_CONDITIONS: RiskOutcome.ALLOW_WITH_CONDITIONS,
    RiskRecommendation.ESCALATE: RiskOutcome.ESCALATE,
    RiskRecommendation.DENY: RiskOutcome.DENY,
}


@runtime_checkable
class DecisionAuthorityPort(Protocol):
    """The contract for the binding-decision authority (spec §11).

    A production deployment satisfies this port with an adapter over the shipped
    ``ugence-decision-authority`` kernel; the RA-1..RA-4 slice satisfies it with
    :class:`ReferenceDecisionAuthority`. Callers depend on this port, never on a
    concrete ruler.
    """

    def issue_decision(
        self,
        *,
        decision_id: str,
        case: RiskDecisionCase,
        evaluation: RiskEvaluation,
        grant: AuthorityGrant,
        requested_scope: Scope,
        evidence_snapshot_digest: str,
        model_digest: str,
        now: datetime,
        evaluated_at: Optional[datetime] = None,
        ttl: timedelta = DEFAULT_DECISION_TTL,
        prerequisite_horizons: "Mapping[str, Optional[datetime]] | None" = None,
    ) -> RiskDecision: ...


class ReferenceDecisionAuthority:
    """In-package reference ruler that issues binding decisions within Authority
    Registry scope.

    Reference implementation only — see this module's boundary note. The
    canonical production binding-decision authority is the shipped
    ``ugence-decision-authority`` kernel, adapted onto
    :class:`DecisionAuthorityPort`.
    """

    def issue_decision(
        self,
        *,
        decision_id: str,
        case: RiskDecisionCase,
        evaluation: RiskEvaluation,
        grant: AuthorityGrant,
        requested_scope: Scope,
        evidence_snapshot_digest: str,
        model_digest: str,
        now: datetime,
        evaluated_at: Optional[datetime] = None,
        ttl: timedelta = DEFAULT_DECISION_TTL,
        prerequisite_horizons: "Mapping[str, Optional[datetime]] | None" = None,
    ) -> RiskDecision:
        """Issue a binding :class:`RiskDecision`.

        For an allow-family recommendation the principal's authority is checked
        and :class:`AuthorityDeniedError` is raised if the principal is not
        entitled to the requested risk class, domain, autonomy or scope. A
        deny/escalate recommendation is issued as-is without granting scope.
        """

        risk_class = case.inherent_risk or RiskClass.HIGH
        outcome = _RECOMMENDATION_TO_OUTCOME[evaluation.recommendation]

        grants_authority = outcome in (
            RiskOutcome.ALLOW,
            RiskOutcome.ALLOW_WITH_CONDITIONS,
        )

        bound_scope = requested_scope.normalized()

        expires_at = now + ttl

        if grants_authority:
            reasons = authority_violations(
                grant,
                tenant_id=case.tenant_id,
                domain=case.domain,
                risk_class=risk_class,
                autonomy_level=case.requested.autonomy_level,
                requested_scope=bound_scope,
                now=now,
            )
            if reasons:
                raise AuthorityDeniedError(reasons)

            # Derived authority is capped by the earliest prerequisite that actually
            # authorized it. Previously ``now + ttl`` was applied unconditionally, so a
            # grant expiring moments after the decision was minted still yielded a full
            # hour of decision validity — and a further envelope TTL on top of that. The
            # half-open operator on ``AuthorityGrant.is_active`` only closes the boundary
            # instant; this is what closes the reach.
            #
            # Each bound is named so the refusal below can say which one bound, and so a
            # reader can tell which prerequisites participate. Only prerequisites that
            # contributed to *this* authorization appear here: the caller passes the
            # control-freshness horizon computed over the required set that was actually
            # satisfied, never over every result that happened to be in the request.
            #
            # Evidence bounds are covered transitively and by construction, not by
            # omission: ``binding._freshness_is_monotonic`` refuses any trusted control
            # result whose ``valid_until`` outlives the earliest ``valid_until`` of its
            # admitted backing evidence, so the control horizon is already no later than
            # the evidence floor beneath it.
            horizons: "dict[str, Optional[datetime]]" = {
                "authority_grant": grant.expires_at,
            }
            if prerequisite_horizons:
                horizons.update(prerequisite_horizons)

            binding_prerequisite: Optional[str] = None
            for name, bound in horizons.items():
                # An absent bound imposes no cap, never a cap of zero.
                if bound is not None and bound < expires_at:
                    expires_at, binding_prerequisite = bound, name

            # Windows are half-open, so ``expires_at == now`` authorizes nothing at any
            # instant. Refuse rather than mint a decision that is already expired: a
            # point-in-time fact may remain valid at its final instant, but it cannot
            # create authority that survives beyond that instant, and returning a
            # zero-width decision would push the failure to a later, less obvious refusal.
            if expires_at <= now:
                bound_by = binding_prerequisite or "decision_ttl"
                raise NoRemainingValidityError(
                    [
                        f"no validity remains for a decision at this instant "
                        f"(bound by {bound_by}): "
                        + ", ".join(
                            f"{name}={bound.isoformat() if bound else None}"
                            for name, bound in horizons.items()
                        )
                    ],
                    prerequisite=bound_by,
                )
        else:
            # A refusal grants nothing, so neither cap applies: the decision conveys no
            # authority whose lifetime could exceed the grant's or the evidence's.
            bound_scope = Scope()

        return RiskDecision(
            decision_id=decision_id,
            tenant_id=case.tenant_id,
            case_id=case.case_id,
            outcome=outcome,
            authority_principal_id=grant.principal_id,
            risk_class=risk_class,
            domain=case.domain,
            scope=bound_scope,
            conditions=evaluation.conditions,
            workflow_ir_digest=case.workflow_ir_digest,
            evidence_snapshot_digest=evidence_snapshot_digest,
            model_digest=model_digest,
            issued_at=now,
            # Recorded, never invented: with no evaluator stamp supplied the decision says so
            # rather than substituting ``now``, which would make the authority's own clock
            # masquerade as the evaluator's (R-12b).
            evaluated_at=evaluated_at,
            expires_at=expires_at,
            applicable_rules=evaluation.applicable_rules,
            reason=("; ".join(evaluation.trace))[:512],
        )
