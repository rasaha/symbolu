"""Shared fixtures for the RA-4.5 composition suite.

Builds a **real** signed Risk Authority envelope through the RA public API (the
finance refund-review vertical slice), then drives the canonical RA enforcement
path via :class:`RiskAuthorityEnforcer`. Nothing here mocks Risk Authority: the
adversarial tests exercise genuine signature / expiry / revocation / epoch /
identity / scope failures produced by RA itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import pytest

from risk_authority.api import (
    ControlResultInput,
    CreateCaseRequest,
    DecisionRequest,
    EvaluateRequest,
    IssueEnvelopeRequest,
    RiskAuthorityApplication,
)
from risk_authority.crypto import KeyRing, SigningKey, SigningKeyRecord
from risk_authority.domain import (
    AuthorityGrant,
    AuthorityType,
    CanonicalAction,
    Predicate,
    PredicateOp,
    RiskAuthorizationEnvelope,
    RiskClass,
    RuleEffect,
    Scope,
    WorkflowIR,
    WorkflowRule,
    WorkflowStatus,
)
from risk_authority.integrations import InMemoryWorkflowIRSource, RuntimeIdentity
from risk_authority.services.revocation import RevocationState

from ugence_risk_authority_runtime import (
    RiskAuthorityEnforcer,
    RiskAuthorityMachineResult,
)

FIXED_NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
TENANT = "tenant_123"
ACTOR = "agent_finance_07"
MODEL = "model_xyz"
PRINCIPAL = "risk-office-prod"
KEY_ID = "risk-key-2026-08"
SESSION = "sess_1"
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


def _build_workflow() -> WorkflowIR:
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
        source_refs=("CORP-AI-04",),
        effective_at=FIXED_NOW,
    ).with_digest()


def _build_grant() -> AuthorityGrant:
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


@dataclass
class RAHarness:
    """A live RA slice exposing everything the enforcer needs."""

    app: RiskAuthorityApplication
    key_ring: KeyRing
    revocation: RevocationState
    envelope: RiskAuthorizationEnvelope
    now: datetime
    enforcer: RiskAuthorityEnforcer
    _seq: list

    def action(self, **overrides) -> CanonicalAction:
        base = dict(
            tenant_id=TENANT,
            actor_id=ACTOR,
            model_id=MODEL,
            action_type="crm.read",
            target_id="txn_123",
            purpose="CUSTOMER_REFUND_REVIEW",
            data_classes=(),
            destination="internal://finance",
            amount_minor_units=None,
            currency="USD",
        )
        base.update(overrides)
        return CanonicalAction(**base)

    def identity(self, **overrides) -> RuntimeIdentity:
        base = dict(
            tenant_id=TENANT, actor_id=ACTOR, model_id=MODEL, session_id=SESSION
        )
        base.update(overrides)
        return RuntimeIdentity(**base)

    def enforce(
        self,
        action: Optional[CanonicalAction] = None,
        *,
        identity: Optional[RuntimeIdentity] = None,
        envelope: Optional[RiskAuthorizationEnvelope] = None,
        now: Optional[datetime] = None,
        satisfied_conditions: frozenset = frozenset(),
        key_ring: Optional[KeyRing] = None,
        revocation: Optional[RevocationState] = None,
    ) -> RiskAuthorityMachineResult:
        self._seq.append(1)
        return self.enforcer.enforce(
            authorization_id=f"auth_{len(self._seq):06d}",
            envelope=self.envelope if envelope is None else envelope,
            action=action if action is not None else self.action(),
            identity=identity if identity is not None else self.identity(),
            key_ring=self.key_ring if key_ring is None else key_ring,
            revocation_state=self.revocation if revocation is None else revocation,
            now=self.now if now is None else now,
            satisfied_conditions=satisfied_conditions,
        )


def _make_harness(
    *,
    controls: tuple[tuple[str, str], ...] = (
        ("MODEL_PROVENANCE_VALID", "PASS"),
        ("HUMAN_OVERSIGHT_VALID", "PASS"),
        ("BIAS_EVALUATION_CURRENT", "PASS"),
    ),
    now: datetime = FIXED_NOW,
) -> RAHarness:
    source = InMemoryWorkflowIRSource()
    source.register(_build_workflow())
    key = SigningKeyRecord(KEY_ID, SigningKey.from_seed(bytes(range(32))))
    app = RiskAuthorityApplication(
        workflow_source=source, key_record=key, clock=lambda: now
    )
    app.authority.add_grant(_build_grant())
    key_ring = KeyRing.from_records([key])

    case_id = "rdc_1"
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
            control_results=tuple(
                ControlResultInput(cid, status) for cid, status in controls
            ),
        ),
    )
    decision = app.issue_decision(
        TENANT,
        case_id,
        evaluation,
        DecisionRequest(principal_id=PRINCIPAL, requested_scope=FINANCE_SCOPE),
    )
    # Risk Authority refuses to mint an envelope for a decision that does not
    # grant authority (e.g. a failed mandatory control). That refusal is itself
    # the F-A/F-E guarantee: no signed capability ever exists, so the enforcer
    # sees no envelope and denies.
    if decision.grants_authority:
        envelope = app.issue_envelope(
            TENANT,
            case_id,
            IssueEnvelopeRequest(
                decision_id=decision.decision_id,
                audience="finance-agent-runtime",
                session_id=SESSION,
                nonce="nonce_1",
            ),
        )
    else:
        envelope = None
    return RAHarness(
        app=app,
        key_ring=key_ring,
        revocation=app.revocation,
        envelope=envelope,
        now=now,
        enforcer=RiskAuthorityEnforcer(),
        _seq=[],
    )


@pytest.fixture
def ra() -> RAHarness:
    """A live, approved RA envelope for the finance refund-review slice."""

    return _make_harness()


@pytest.fixture
def make_harness() -> Callable[..., RAHarness]:
    return _make_harness
