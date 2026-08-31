"""Authority Registry delegation containment (spec §11.2, §29, AC-03)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from risk_authority.domain import (
    AuthorityDeniedError,
    AuthorityGrant,
    AuthorityType,
    RiskClass,
    Scope,
    authority_violations,
)
from risk_authority.services import ReferenceDecisionAuthority, RiskEngine
from risk_authority.services.risk_engine import RiskEvaluation
from risk_authority.domain import RiskRecommendation

from tests.scenario import (
    FINANCE_SCOPE,
    FIXED_NOW,
    build_application,
    build_grant,
)
from tests.scenario import TENANT, PRINCIPAL

NOW = FIXED_NOW


def test_grant_covers_in_scope_request():
    grant = build_grant()
    reasons = authority_violations(
        grant,
        tenant_id=TENANT,
        domain="FINANCE",
        risk_class=RiskClass.HIGH,
        autonomy_level=2,
        requested_scope=FINANCE_SCOPE,
        now=NOW,
    )
    assert reasons == []


def test_wrong_domain_denied():
    grant = build_grant()
    reasons = authority_violations(
        grant,
        tenant_id=TENANT,
        domain="HR",
        risk_class=RiskClass.HIGH,
        autonomy_level=2,
        requested_scope=FINANCE_SCOPE,
        now=NOW,
    )
    assert any("domain" in r for r in reasons)


def test_risk_class_above_delegation_denied():
    grant = build_grant()  # up to HIGH only
    reasons = authority_violations(
        grant,
        tenant_id=TENANT,
        domain="FINANCE",
        risk_class=RiskClass.CRITICAL,
        autonomy_level=2,
        requested_scope=FINANCE_SCOPE,
        now=NOW,
    )
    assert any("risk_class" in r for r in reasons)


def test_hr_officer_cannot_authorize_finance_scope():
    # An HR compliance officer with generic approver status must not authorize a
    # finance-domain scope (user brief §6 example).
    hr_grant = AuthorityGrant(
        principal_id="hr-compliance",
        tenant_id=TENANT,
        authority_type=AuthorityType.RISK_APPROVAL,
        domains=("HR",),
        allowed_risk_classes=(RiskClass.LOW, RiskClass.MEDIUM, RiskClass.HIGH),
        max_autonomy=3,
        delegated_by="enterprise-risk-office",
        grantable_scope=Scope(purposes=("EMPLOYEE_REVIEW",), max_autonomy_level=3),
    )
    reasons = authority_violations(
        hr_grant,
        tenant_id=TENANT,
        domain="FINANCE",
        risk_class=RiskClass.HIGH,
        autonomy_level=2,
        requested_scope=FINANCE_SCOPE,
        now=NOW,
    )
    assert reasons  # denied on domain and scope


def test_expired_grant_denied():
    grant = AuthorityGrant(
        principal_id=PRINCIPAL,
        tenant_id=TENANT,
        authority_type=AuthorityType.RISK_APPROVAL,
        domains=("FINANCE",),
        allowed_risk_classes=(RiskClass.HIGH,),
        max_autonomy=2,
        delegated_by="x",
        expires_at=NOW - timedelta(hours=1),
        grantable_scope=FINANCE_SCOPE,
    )
    reasons = authority_violations(
        grant,
        tenant_id=TENANT,
        domain="FINANCE",
        risk_class=RiskClass.HIGH,
        autonomy_level=2,
        requested_scope=FINANCE_SCOPE,
        now=NOW,
    )
    assert any("expired" in r for r in reasons)


def test_decision_authority_raises_on_over_delegation():
    # Requesting a scope broader than the grant must raise, not silently issue.
    app = build_application()
    grant = build_grant()
    authority = ReferenceDecisionAuthority()
    case = _minimal_case()
    evaluation = RiskEvaluation(
        recommendation=RiskRecommendation.ALLOW,
        applicable_rules=("FIN-12",),
        required_controls=(),
        failed_controls=(),
        conditions=(),
        trace=(),
    )
    broader = Scope(
        purposes=("CUSTOMER_REFUND_REVIEW", "PAYROLL"),
        tools_allow=("crm.read", "refund.prepare", "wire.transfer"),
        max_autonomy_level=4,
    )
    with pytest.raises(AuthorityDeniedError):
        authority.issue_decision(
            decision_id="d",
            case=case,
            evaluation=evaluation,
            grant=grant,
            requested_scope=broader,
            evidence_snapshot_digest="",
            model_digest="",
            now=NOW,
        )


def _minimal_case():
    from risk_authority.domain import RequestedCapabilities, RiskDecisionCase

    return RiskDecisionCase(
        case_id="rdc_1",
        tenant_id=TENANT,
        subject_id="agent_finance_07",
        model_id="model_xyz",
        purpose="CUSTOMER_REFUND_REVIEW",
        domain="FINANCE",
        jurisdictions=("US",),
        requested=RequestedCapabilities(tools=("crm.read",), autonomy_level=2),
        workflow_ir_id="finance-ai-risk",
        workflow_ir_version="4.1.0",
        workflow_ir_digest="sha256:x",
        created_at=NOW,
        inherent_risk=RiskClass.HIGH,
    )
