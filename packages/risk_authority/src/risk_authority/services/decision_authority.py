"""Decision Authority — converts an evaluation into a binding ruling (spec §11).

This is the *ruler*, distinct from the Risk Engine evaluator. It proves the
issuing principal holds authority covering the requested decision
(``IssuedAuthority ⊆ DelegatedAuthority``) before issuing, and denies
otherwise (user brief §6–7). The Risk Engine's recommendation is advisory: a
DENY/ESCALATE recommendation is honored as the binding outcome; an ALLOW
recommendation still requires a principal with sufficient authority.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..domain.authority import AuthorityGrant, authority_violations
from ..domain.decision import RiskDecision
from ..domain.enums import RiskClass, RiskOutcome, RiskRecommendation
from ..domain.errors import AuthorityDeniedError
from ..domain.risk_case import RiskDecisionCase
from ..domain.scope import Scope
from .risk_engine import RiskEvaluation

__all__ = ["DecisionAuthority", "DEFAULT_DECISION_TTL"]

DEFAULT_DECISION_TTL = timedelta(hours=1)

_RECOMMENDATION_TO_OUTCOME = {
    RiskRecommendation.ALLOW: RiskOutcome.ALLOW,
    RiskRecommendation.ALLOW_WITH_CONDITIONS: RiskOutcome.ALLOW_WITH_CONDITIONS,
    RiskRecommendation.ESCALATE: RiskOutcome.ESCALATE,
    RiskRecommendation.DENY: RiskOutcome.DENY,
}


class DecisionAuthority:
    """Issue binding risk decisions within Authority Registry scope."""

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
        ttl: timedelta = DEFAULT_DECISION_TTL,
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
        else:
            # A refusal grants nothing.
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
            expires_at=now + ttl,
            applicable_rules=evaluation.applicable_rules,
            reason=("; ".join(evaluation.trace))[:512],
        )
