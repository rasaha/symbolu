"""Application facade wiring the RA-1..RA-4 vertical slice.

``RiskAuthorityApplication`` composes the domain, services, integrations and
persistence into the eight-endpoint flow:

    create case -> evaluate -> issue decision -> issue envelope
                -> verify envelope -> authorize action

It owns case-state orchestration (driving the state machine through its legal
sequence) and audit emission, but no policy logic — that lives in WorkflowIR
and the services. Clock and id generation are injected so the whole flow is
deterministic under test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from itertools import count
from typing import Callable, Optional

from ..crypto.keys import KeyRing, SigningKeyRecord
from ..domain.actions import ActionAuthorization, CanonicalAction
from ..domain.controls import ControlResult
from ..domain.decision import RiskDecision
from ..domain.enums import (
    ControlStatus,
    GovernanceEventType,
    RiskCaseState,
    RiskOutcome,
)
from ..domain.envelope import EnvelopeConditions, RiskAuthorizationEnvelope
from ..domain.errors import RiskAuthorityError
from ..domain.events import GovernanceEvent
from ..domain.risk_case import RequestedCapabilities, RiskDecisionCase
from ..integrations.actiongate import ReferenceActionGate, RuntimeIdentity
from ..integrations.pwc import WorkflowIRSource
from ..observability.events import EventBus
from ..observability.metrics import Metrics
from ..persistence.in_memory import (
    InMemoryAuthorityRegistry,
    InMemoryControlResultRepository,
    InMemoryDecisionRepository,
    InMemoryEnvelopeRepository,
    InMemoryGovernanceEventStore,
    InMemoryRiskCaseRepository,
)
from ..services.decision_authority import DecisionAuthority
from ..services.envelope_issuer import EnvelopeIssuer
from ..services.envelope_verifier import EnvelopeVerification, EnvelopeVerifier
from ..services.revocation import RevocationState
from ..services.risk_engine import RiskEngine, RiskEvaluation
from .schemas import (
    AuthorizeActionRequest,
    CreateCaseRequest,
    DecisionRequest,
    EvaluateRequest,
    IssueEnvelopeRequest,
)

__all__ = ["RiskAuthorityApplication"]


@dataclass
class _Ids:
    """Deterministic id generator keyed by prefix."""

    _counters: dict[str, "count[int]"]

    def __init__(self) -> None:
        self._counters = {}

    def next(self, prefix: str) -> str:
        counter = self._counters.setdefault(prefix, count(1))
        return f"{prefix}_{next(counter):06d}"


class RiskAuthorityApplication:
    def __init__(
        self,
        *,
        workflow_source: WorkflowIRSource,
        key_record: SigningKeyRecord,
        clock: Callable[[], datetime],
        issuer: str = "ugence-risk-authority",
        cases: Optional[InMemoryRiskCaseRepository] = None,
        decisions: Optional[InMemoryDecisionRepository] = None,
        envelopes: Optional[InMemoryEnvelopeRepository] = None,
        authority: Optional[InMemoryAuthorityRegistry] = None,
        controls: Optional[InMemoryControlResultRepository] = None,
        events: Optional[InMemoryGovernanceEventStore] = None,
        revocation: Optional[RevocationState] = None,
        event_bus: Optional[EventBus] = None,
        metrics: Optional[Metrics] = None,
        ids: Optional[_Ids] = None,
    ) -> None:
        self._workflow_source = workflow_source
        self._key_record = key_record
        self._key_ring = KeyRing.from_records([key_record])
        self._clock = clock
        self.cases = cases or InMemoryRiskCaseRepository()
        self.decisions = decisions or InMemoryDecisionRepository()
        self.envelopes = envelopes or InMemoryEnvelopeRepository()
        self.authority = authority or InMemoryAuthorityRegistry()
        self.controls = controls or InMemoryControlResultRepository()
        self.events = events or InMemoryGovernanceEventStore()
        self.revocation = revocation or RevocationState()
        self.event_bus = event_bus or EventBus()
        self.metrics = metrics or Metrics()
        self._ids = ids or _Ids()

        self._engine = RiskEngine()
        self._authority_service = DecisionAuthority()
        self._issuer_service = EnvelopeIssuer(issuer=issuer)
        self._verifier = EnvelopeVerifier()
        self._gate = ReferenceActionGate(self._verifier)

    # ------------------------------------------------------------------
    # Internal helpers.
    # ------------------------------------------------------------------
    def _emit_case_events(self, case: RiskDecisionCase) -> None:
        known = {e.event_id for e in self.events.for_aggregate(case.tenant_id, case.case_id)}
        for event in case.events:
            if event.event_id not in known:
                self.events.append(event)
                self.event_bus.publish(event)

    def _publish(self, event: GovernanceEvent) -> None:
        self.events.append(event)
        self.event_bus.publish(event)

    def _workflow_for(self, case: RiskDecisionCase):
        workflow = self._workflow_source.get(
            case.workflow_ir_id, version=case.workflow_ir_version or None
        )
        if workflow is None:
            raise RiskAuthorityError(
                f"no active WorkflowIR {case.workflow_ir_id!r} "
                f"version {case.workflow_ir_version!r}"
            )
        return workflow

    # ------------------------------------------------------------------
    # POST /risk-cases
    # ------------------------------------------------------------------
    def create_case(self, req: CreateCaseRequest) -> RiskDecisionCase:
        now = self._clock()
        workflow = self._workflow_source.get(
            req.workflow_ir_id, version=req.workflow_ir_version or None
        )
        if workflow is None:
            raise RiskAuthorityError(
                f"no active WorkflowIR {req.workflow_ir_id!r}"
            )
        case = RiskDecisionCase(
            case_id=req.case_id or self._ids.next("rdc"),
            tenant_id=req.tenant_id,
            subject_id=req.subject_id,
            model_id=req.model_id,
            purpose=req.purpose,
            domain=req.domain,
            jurisdictions=req.jurisdictions,
            requested=RequestedCapabilities(
                tools=req.tools,
                autonomy_level=req.autonomy_level,
                data_classes=req.data_classes,
            ),
            workflow_ir_id=workflow.workflow_ir_id,
            workflow_ir_version=workflow.version,
            workflow_ir_digest=workflow.digest,
            created_at=now,
            correlation_id=req.correlation_id,
        )
        # CREATED event.
        self._publish(
            GovernanceEvent(
                event_id=f"evt_{case.case_id}_0000",
                tenant_id=case.tenant_id,
                event_type=GovernanceEventType.CASE_CREATED,
                aggregate_id=case.case_id,
                actor="risk-authority",
                timestamp=now,
                correlation_id=case.correlation_id,
            )
        )
        # CREATED -> CLASSIFIED -> CONTROLS_RESOLVED.
        case.classify(
            inherent=req.inherent_risk,
            residual=req.residual_risk,
            actor="risk-engine",
            now=now,
        )
        from ..services.control_resolver import resolve_required_controls

        required = resolve_required_controls(workflow, case.evaluation_context())
        case.set_required_controls(required, actor="risk-engine", now=now)
        self._emit_case_events(case)
        self.cases.save(case)
        return case

    # ------------------------------------------------------------------
    # POST /risk-cases/{id}/evaluate
    # ------------------------------------------------------------------
    def evaluate(
        self, tenant_id: str, case_id: str, req: EvaluateRequest
    ) -> RiskEvaluation:
        now = self._clock()
        case = self._require_case(tenant_id, case_id)
        workflow = self._workflow_for(case)

        results = tuple(
            ControlResult(
                control_id=c.control_id,
                status=ControlStatus(c.status),
                evidence_ids=c.evidence_ids,
                evaluated_at=now,
            )
            for c in req.control_results
        )
        self.controls.put(tenant_id, case_id, results)

        # Walk the evidence/evaluation states to AUTHORITY_REVIEW.
        case.transition(
            target=RiskCaseState.EVIDENCE_PENDING,
            actor="risk-authority",
            reason="evidence intake",
            now=now,
        )
        case.transition(
            target=RiskCaseState.EVIDENCE_COMPLETE,
            actor="risk-authority",
            reason="evidence submitted",
            now=now,
        )
        case.transition(
            target=RiskCaseState.CONTROL_EVALUATED,
            actor="control-assurance",
            reason="controls evaluated",
            now=now,
            event_type=GovernanceEventType.CONTROL_EVALUATED,
        )
        case.transition(
            target=RiskCaseState.AUTHORITY_REVIEW,
            actor="risk-authority",
            reason="ready for authority review",
            now=now,
        )

        evaluation = self._engine.evaluate(
            workflow_ir=workflow,
            case=case,
            controls=results,
            now=now,
            conditions=req.conditions,
        )
        self._publish(
            GovernanceEvent(
                event_id=f"evt_{case_id}_eval_{self._ids.next('e')}",
                tenant_id=tenant_id,
                event_type=GovernanceEventType.RISK_EVALUATED,
                aggregate_id=case_id,
                actor="risk-engine",
                timestamp=now,
                correlation_id=case.correlation_id,
                payload_digest="",
                attributes={"recommendation": evaluation.recommendation.value},
            )
        )
        self._emit_case_events(case)
        self.cases.save(case)
        return evaluation

    # ------------------------------------------------------------------
    # POST /risk-cases/{id}/decision
    # ------------------------------------------------------------------
    def issue_decision(
        self,
        tenant_id: str,
        case_id: str,
        evaluation: RiskEvaluation,
        req: DecisionRequest,
    ) -> RiskDecision:
        now = self._clock()
        case = self._require_case(tenant_id, case_id)
        grant = self.authority.get_grant(tenant_id, req.principal_id)
        if grant is None:
            raise RiskAuthorityError(
                f"no authority grant for principal {req.principal_id!r}"
            )
        decision = self._authority_service.issue_decision(
            decision_id=self._ids.next("risk_dec"),
            case=case,
            evaluation=evaluation,
            grant=grant,
            requested_scope=req.requested_scope,
            evidence_snapshot_digest=req.evidence_snapshot_digest,
            model_digest=req.model_digest,
            now=now,
        )
        self.decisions.save(decision)

        target = {
            RiskOutcome.ALLOW: RiskCaseState.APPROVED,
            RiskOutcome.ALLOW_WITH_CONDITIONS: RiskCaseState.CONDITIONAL,
            RiskOutcome.ESCALATE: RiskCaseState.DENIED,
            RiskOutcome.DENY: RiskCaseState.DENIED,
        }[decision.outcome]
        case.transition(
            target=target,
            actor=req.principal_id,
            reason=f"decision {decision.outcome.value}",
            now=now,
            event_type=(
                GovernanceEventType.RISK_APPROVED
                if decision.grants_authority
                else GovernanceEventType.RISK_DENIED
            ),
        )
        self._publish(
            GovernanceEvent(
                event_id=f"evt_{decision.decision_id}",
                tenant_id=tenant_id,
                event_type=GovernanceEventType.DECISION_ISSUED,
                aggregate_id=case_id,
                actor=req.principal_id,
                timestamp=now,
                correlation_id=case.correlation_id,
                attributes={"outcome": decision.outcome.value},
            )
        )
        self._emit_case_events(case)
        self.cases.save(case)
        return decision

    # ------------------------------------------------------------------
    # POST /risk-cases/{id}/envelopes
    # ------------------------------------------------------------------
    def issue_envelope(
        self, tenant_id: str, case_id: str, req: IssueEnvelopeRequest
    ) -> RiskAuthorizationEnvelope:
        now = self._clock()
        case = self._require_case(tenant_id, case_id)
        decision = self.decisions.get(tenant_id, req.decision_id)
        if decision is None:
            raise RiskAuthorityError(f"no decision {req.decision_id!r}")

        conditions = EnvelopeConditions(
            context_minimization=req.context_minimization,
            human_approval_required_above_minor_units=(
                req.human_approval_required_above_minor_units
            ),
            required_conditions=req.required_conditions,
        )
        envelope = self._issuer_service.issue(
            envelope_id=self._ids.next("rae"),
            decision=decision,
            audience=req.audience,
            subject=case.subject_id,
            model_id=case.model_id,
            session_id=req.session_id,
            nonce=req.nonce,
            key_record=self._key_record,
            revocation_state=self.revocation,
            now=now,
            model_digest=decision.model_digest,
            envelope_scope=req.envelope_scope,
            conditions=conditions,
        )
        self.envelopes.save(envelope)

        case.transition(
            target=RiskCaseState.ENVELOPE_ISSUED,
            actor="risk-authority",
            reason=f"envelope {envelope.envelope_id}",
            now=now,
            event_type=GovernanceEventType.ENVELOPE_ISSUED,
        )
        case.transition(
            target=RiskCaseState.ACTIVE,
            actor="risk-authority",
            reason="authority active",
            now=now,
        )
        self._emit_case_events(case)
        self.cases.save(case)
        return envelope

    # ------------------------------------------------------------------
    # POST /envelopes/{id}/verify
    # ------------------------------------------------------------------
    def verify_envelope(
        self, tenant_id: str, envelope_id: str
    ) -> EnvelopeVerification:
        now = self._clock()
        envelope = self.envelopes.get(tenant_id, envelope_id)
        if envelope is None:
            return EnvelopeVerification.deny("unknown envelope")
        return self._verifier.verify(
            envelope=envelope,
            key_ring=self._key_ring,
            revocation_state=self.revocation,
            now=now,
            expected_tenant=tenant_id,
        )

    # ------------------------------------------------------------------
    # POST /actions/authorize
    # ------------------------------------------------------------------
    def authorize_action(self, req: AuthorizeActionRequest) -> ActionAuthorization:
        now = self._clock()
        envelope = self.envelopes.get(req.tenant_id, req.envelope_id)
        action = CanonicalAction(
            tenant_id=req.tenant_id,
            actor_id=req.actor_id,
            model_id=req.model_id,
            action_type=req.action_type,
            target_id=req.target_id,
            purpose=req.purpose,
            data_classes=req.data_classes,
            destination=req.destination,
            amount_minor_units=req.amount_minor_units,
            currency=req.currency,
        )
        self.metrics.incr("actiongate.requests")
        if envelope is None:
            self.metrics.incr("actiongate.denied")
            from ..domain.enums import ActionGateDecision

            return ActionAuthorization(
                authorization_id=self._ids.next("auth"),
                envelope_id=req.envelope_id,
                action_digest=action.digest,
                decision=ActionGateDecision.DENIED,
                tenant_id=req.tenant_id,
                reason_codes=("unknown envelope",),
            )
        identity = RuntimeIdentity(
            tenant_id=req.tenant_id,
            actor_id=req.actor_id,
            model_id=req.model_id,
            session_id=req.session_id,
        )
        authorization = self._gate.authorize(
            authorization_id=self._ids.next("auth"),
            envelope=envelope,
            action=action,
            identity=identity,
            key_ring=self._key_ring,
            revocation_state=self.revocation,
            now=now,
            satisfied_conditions=frozenset(req.satisfied_conditions),
        )
        if authorization.authorized:
            self.metrics.incr("actiongate.authorized")
        else:
            self.metrics.incr("actiongate.denied")
        self._publish(
            GovernanceEvent(
                event_id=f"evt_{authorization.authorization_id}",
                tenant_id=req.tenant_id,
                event_type=(
                    GovernanceEventType.ACTION_AUTHORIZED
                    if authorization.authorized
                    else GovernanceEventType.ACTION_DENIED
                ),
                aggregate_id=req.envelope_id,
                actor=req.actor_id,
                timestamp=now,
                payload_digest=action.digest,
            )
        )
        return authorization

    # ------------------------------------------------------------------
    def _require_case(self, tenant_id: str, case_id: str) -> RiskDecisionCase:
        case = self.cases.get(tenant_id, case_id)
        if case is None:
            raise RiskAuthorityError(f"no case {case_id!r} for tenant {tenant_id!r}")
        return case
