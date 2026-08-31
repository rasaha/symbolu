"""Shared RA-6 scenario builder.

Builds a **real** Ed25519-signed ``RiskAuthorizationEnvelope`` through the Risk
Authority public API (a finance refund-review slice), plus the RA-6 status
runtime wiring (store + bounded-stale cache + authenticated writer + reassessor +
status-aware gate). Nothing is mocked: the conformance suite exercises genuine
signature / expiry / revocation / epoch / scope failures produced by RA itself,
now gated by RA-6's freshness + lifecycle machinery.

Uniquely named (``ra6_scenario``) so running this package's tests alongside other
packages in one pytest process never collides on a shared ``conftest`` name.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

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
from risk_authority.domain.authority_signal import (
    AUTHORITY_SIGNAL_SCHEMA_VERSION,
    AuthorityReassessmentSignal,
    SignalChangeType,
    SignalTarget,
    SignalTargetType,
)
from risk_authority.domain.events import GovernanceEvent
from risk_authority.integrations import InMemoryWorkflowIRSource, RuntimeIdentity
from risk_authority.services.authority_status import StalenessPolicy

from ugence_risk_authority_status_runtime import (
    AuthorityLifecycleService,
    AuthorityReassessor,
    AuthorityStatusCache,
    ReferenceAuthorityStore,
    ReferenceWriterAuthorizer,
    StatusAwareActionGate,
)
from ugence_risk_authority_status_runtime.writer import (
    EMERGENCY_STOP_CAPABILITY,
    LIFECYCLE_WRITE_CAPABILITY,
)
from risk_authority.integrations.authority_lifecycle import WriterPrincipal

FIXED_NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
TENANT = "tenant_123"
ACTOR = "agent_finance_07"
MODEL = "model_xyz"
PRINCIPAL = "risk-office-prod"
KEY_ID = "risk-key-2026-08"
SESSION = "sess_1"
MAX_REFUND_MINOR = 500000

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


class Clock:
    """A mutable logical clock shared by the RA-6 cache + writer.

    The RA envelope is minted once at build time; the cache/writer clock can be
    advanced afterward so a test can control *cache freshness* and *check time*
    independently (isolating the staleness dimension from the envelope-expiry
    dimension).
    """

    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


@dataclass
class RA6Harness:
    """A live RA envelope + RA-6 status runtime wiring."""

    app: RiskAuthorityApplication
    key_ring: KeyRing
    envelope: RiskAuthorizationEnvelope
    now: datetime
    residual_risk: RiskClass
    store: ReferenceAuthorityStore
    cache: AuthorityStatusCache
    writer: AuthorityLifecycleService
    events: List[GovernanceEvent]
    clock: "Clock"
    _seq: list

    def refresh_at(self, when: datetime) -> None:
        """Advance the clock to ``when`` and re-sync the cache (snapshot fresh)."""

        self.clock.value = when
        self.cache.sync()

    # -- principals ----------------------------------------------------- #
    def admin(self, capabilities=(LIFECYCLE_WRITE_CAPABILITY,)) -> WriterPrincipal:
        return WriterPrincipal(
            principal_id="gov-admin",
            tenant_id=TENANT,
            capabilities=frozenset(capabilities),
        )

    def emergency_admin(self) -> WriterPrincipal:
        return WriterPrincipal(
            principal_id="gov-emergency",
            tenant_id=TENANT,
            capabilities=frozenset(
                {LIFECYCLE_WRITE_CAPABILITY, EMERGENCY_STOP_CAPABILITY}
            ),
        )

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
        base = dict(tenant_id=TENANT, actor_id=ACTOR, model_id=MODEL, session_id=SESSION)
        base.update(overrides)
        return RuntimeIdentity(**base)

    def gate(self, *, policy: Optional[StalenessPolicy] = None) -> StatusAwareActionGate:
        return StatusAwareActionGate(
            self.cache, policy=policy or StalenessPolicy.fail_closed_defaults()
        )

    def authorize(
        self,
        *,
        gate: Optional[StatusAwareActionGate] = None,
        action: Optional[CanonicalAction] = None,
        identity: Optional[RuntimeIdentity] = None,
        tier: Optional[RiskClass] = None,
        now: Optional[datetime] = None,
        satisfied_conditions: frozenset = frozenset(),
    ):
        self._seq.append(1)
        g = gate or self.gate()
        return g.authorize(
            authorization_id=f"auth_{len(self._seq):06d}",
            envelope=self.envelope,
            action=action if action is not None else self.action(),
            identity=identity if identity is not None else self.identity(),
            key_ring=self.key_ring,
            tier=self.residual_risk if tier is None else tier,
            now=self.now if now is None else now,
            satisfied_conditions=satisfied_conditions,
        )


def build(
    *,
    now: datetime = FIXED_NOW,
    residual_risk: RiskClass = RiskClass.LOW,
    controls: tuple[tuple[str, str], ...] = (
        ("MODEL_PROVENANCE_VALID", "PASS"),
        ("HUMAN_OVERSIGHT_VALID", "PASS"),
        ("BIAS_EVALUATION_CURRENT", "PASS"),
    ),
    synced: bool = True,
    production_mode: bool = False,
) -> RA6Harness:
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
            residual_risk=residual_risk,
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
    envelope = None
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

    store = ReferenceAuthorityStore()
    store.seed_tenant(TENANT)
    events: List[GovernanceEvent] = []
    clock = Clock(now)
    writer = AuthorityLifecycleService(
        store,
        ReferenceWriterAuthorizer(),
        event_sink=events.append,
        clock=clock,
        production_mode=production_mode,
    )
    cache = AuthorityStatusCache(store, clock=clock)
    if synced:
        cache.sync()

    return RA6Harness(
        app=app,
        key_ring=key_ring,
        envelope=envelope,
        now=now,
        residual_risk=residual_risk,
        store=store,
        cache=cache,
        writer=writer,
        events=events,
        clock=clock,
        _seq=[],
    )


def system_reassessor(h: RA6Harness) -> AuthorityReassessor:
    """A reassessor whose system principal holds lifecycle-write for TENANT."""

    return AuthorityReassessor(
        h.writer,
        system_principal=WriterPrincipal(
            principal_id="ra-reassessor",
            tenant_id=TENANT,
            capabilities=frozenset({LIFECYCLE_WRITE_CAPABILITY}),
        ),
    )
