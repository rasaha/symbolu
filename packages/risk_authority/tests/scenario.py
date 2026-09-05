"""Shared test scenario: the finance refund-review vertical slice (spec §26, §34).

Builds the exact policy from the user brief's first end-to-end test and Phase-1
exit test:

    Finance agent may:  crm.read, refund.prepare
    May not:            refund.execute, email.external
    Maximum refund:     $5,000  (500000 minor units)
    Destination:        internal only
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone

from risk_authority.api import (
    AuthorizeActionRequest,
    ControlResultInput,
    CreateCaseRequest,
    DecisionRequest,
    EvaluateRequest,
    IssueEnvelopeRequest,
    RiskAuthorityApplication,
)
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.domain import (
    AuthorityGrant,
    AuthorityType,
    Predicate,
    PredicateOp,
    RiskClass,
    RuleEffect,
    Scope,
    WorkflowIR,
    WorkflowRule,
    WorkflowStatus,
)
from risk_authority.integrations import InMemoryWorkflowIRSource
from risk_authority.persistence import SqliteRiskAuthorityStore

FIXED_NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


def durable_store(path=None) -> SqliteRiskAuthorityStore:
    """A fresh file-backed store: what a production application must stand on (D-5)."""

    import os
    import tempfile

    return SqliteRiskAuthorityStore(path or os.path.join(tempfile.mkdtemp(), "risk-authority.sqlite"))
TENANT = "tenant_123"
ACTOR = "agent_finance_07"
MODEL = "model_xyz"
PRINCIPAL = "risk-office-prod"
KEY_ID = "risk-key-2026-08"
MAX_REFUND_MINOR = 500000  # $5,000

FINANCE_SCOPE = Scope(
    purposes=("CUSTOMER_REFUND_REVIEW",),
    tools_allow=("crm.read", "refund.prepare"),
    tools_deny=("refund.execute", "email.external"),
    data_allow=("CUSTOMER_PII", "TRANSACTION_DATA"),
    data_deny=("HEALTH_DATA", "EMPLOYEE_HR"),
    destinations=("internal://finance",),
    models=(MODEL,),
    actors=(ACTOR,),
    max_autonomy_level=2,
    max_transaction_minor_units=MAX_REFUND_MINOR,
)


def build_workflow() -> WorkflowIR:
    return WorkflowIR(
        workflow_ir_id="finance-ai-risk",
        version="4.1.0",
        status=WorkflowStatus.ACTIVE,
        rules=(
            WorkflowRule(
                rule_id="FIN-12",
                conditions=(
                    Predicate("risk_class", PredicateOp.IN, ["HIGH", "CRITICAL"]),
                    Predicate("domain", PredicateOp.EQ, "FINANCE"),
                ),
                required_controls=(
                    "MODEL_PROVENANCE_VALID",
                    "HUMAN_OVERSIGHT_VALID",
                    "BIAS_EVALUATION_CURRENT",
                ),
                effect=RuleEffect.DENY_UNLESS_ALL,
            ),
        ),
        source_refs=("CORP-AI-04", "EUAI-HR-001"),
        effective_at=FIXED_NOW,
    ).with_digest()


def build_grant() -> AuthorityGrant:
    return AuthorityGrant(
        principal_id=PRINCIPAL,
        tenant_id=TENANT,
        authority_type=AuthorityType.RISK_APPROVAL,
        domains=("FINANCE",),
        allowed_risk_classes=(RiskClass.LOW, RiskClass.MEDIUM, RiskClass.HIGH),
        max_autonomy=2,
        delegated_by="enterprise-risk-office",
        grantable_scope=FINANCE_SCOPE,
    )


def build_application() -> RiskAuthorityApplication:
    source = InMemoryWorkflowIRSource()
    source.register(build_workflow())
    key = SigningKeyRecord(KEY_ID, SigningKey.from_seed(bytes(range(32))))
    app = RiskAuthorityApplication(
        workflow_source=source, key_record=key, clock=lambda: FIXED_NOW
    )
    app.authority.add_grant(build_grant())
    return app


def approved_envelope(app: RiskAuthorityApplication, *, case_id: str = "rdc_1"):
    """Run create -> evaluate -> decide -> issue and return the signed envelope."""

    app.create_case(
        CreateCaseRequest(
            tenant_id=TENANT,
            case_id=case_id,
            subject_id=ACTOR,
            model_id=MODEL,
            purpose="CUSTOMER_REFUND_REVIEW",
            domain="FINANCE",
            jurisdictions=("US",),
            tools=("crm.read", "refund.prepare"),
            autonomy_level=2,
            data_classes=("CUSTOMER_PII", "TRANSACTION_DATA"),
            workflow_ir_id="finance-ai-risk",
            inherent_risk=RiskClass.HIGH,
            residual_risk=RiskClass.MEDIUM,
        )
    )
    evaluation = app.evaluate(
        TENANT,
        case_id,
        EvaluateRequest(
            control_results=(
                ControlResultInput("MODEL_PROVENANCE_VALID", "PASS"),
                ControlResultInput("HUMAN_OVERSIGHT_VALID", "PASS"),
                ControlResultInput("BIAS_EVALUATION_CURRENT", "PASS"),
            ),
            conditions=("context_minimization",),
        ),
    )
    decision = app.issue_decision(
        TENANT,
        case_id,
        evaluation,
        DecisionRequest(principal_id=PRINCIPAL, requested_scope=FINANCE_SCOPE),
    )
    envelope = app.issue_envelope(
        TENANT,
        case_id,
        IssueEnvelopeRequest(
            decision_id=decision.decision_id,
            audience="finance-agent-runtime",
            session_id="sess_1",
            nonce="nonce_1",
        ),
    )
    return evaluation, decision, envelope


def action_request(app_envelope, **overrides) -> AuthorizeActionRequest:
    """Build an ActionGate request against ``app_envelope`` with overrides."""

    base = dict(
        envelope_id=app_envelope.envelope_id,
        tenant_id=TENANT,
        actor_id=ACTOR,
        model_id=MODEL,
        session_id="sess_1",
        action_type="crm.read",
        target_id="txn_123",
        purpose="CUSTOMER_REFUND_REVIEW",
        data_classes=(),
        destination="internal://finance",
        amount_minor_units=None,
        currency="USD",
        satisfied_conditions=(),
    )
    base.update(overrides)
    return AuthorizeActionRequest(**base)
