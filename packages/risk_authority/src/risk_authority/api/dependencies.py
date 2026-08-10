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
from typing import Callable, Mapping, Optional

from ..crypto.keys import KeyRing, SigningKeyRecord
from ..domain.actions import ActionAuthorization, CanonicalAction
from ..domain.binding import AdmittedContext, CaseBindingContext, usable_control_results
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
from ..domain.evidence import ControlEvidenceRecord
from ..domain.risk_case import RequestedCapabilities, RiskDecisionCase
from ..integrations.actiongate import ReferenceActionGate, RuntimeIdentity
from ..integrations.control_assurance import (
    ControlAssurancePort,
    ControlAssuranceRequest,
    bind_control_result,
)
from ..integrations.ingress import TrustedEvidenceIngressPort
from ..integrations.pwc import WorkflowIRSource
from ..integrations.tap import EvidenceAdmissionPort
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
from ..services.decision_authority import ReferenceDecisionAuthority
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
        evidence_admission: Optional[EvidenceAdmissionPort] = None,
        control_assurance: Optional[ControlAssurancePort] = None,
        evidence_ingress: Optional[TrustedEvidenceIngressPort] = None,
        production_mode: bool = False,
    ) -> None:
        # RA-5 mode selection (RISK_AUTHORITY_RA5_SPEC.md §12; audit H-1/H-2).
        # Mode is EXPLICIT: production mode is only entered when the caller sets
        # ``production_mode=True`` and injects the trusted-evidence ports. It never
        # silently falls back to the reference (caller-asserted) path; an
        # incomplete or fail-open production configuration fails closed here.
        if production_mode:
            if evidence_admission is None or control_assurance is None:
                raise RiskAuthorityError(
                    "production_mode requires both an EvidenceAdmissionPort and a "
                    "ControlAssurancePort (RA-5 §12: fail closed on incomplete "
                    "production configuration)"
                )
            # H-2: evidence must arrive over an authenticated producer channel; a
            # self-computable integrity digest is not producer authenticity (§13).
            # Production fails closed without an explicit trusted-ingress seam.
            if evidence_ingress is None:
                raise RiskAuthorityError(
                    "production_mode requires a TrustedEvidenceIngressPort: a valid "
                    "integrity digest proves content tamper-detection, not producer "
                    "authenticity (RA-5 §13; audit H-2). Inject an authenticated "
                    "producer-channel verifier."
                )
            # H-1: a permissive/reference/default evaluator must not silently
            # satisfy control assurance in production. A production-authoritative
            # port must explicitly opt in; anything else fails closed.
            if getattr(control_assurance, "is_production_authoritative", False) is not True:
                raise RiskAuthorityError(
                    "production ControlAssurancePort must be production-authoritative "
                    "(is_production_authoritative=True): a permissive/reference "
                    "evaluator whose support is presumptive cannot mint PASS in "
                    "production (RA-5 audit H-1)."
                )
        self._production_mode = bool(production_mode)
        self._evidence_admission = evidence_admission
        self._control_assurance = control_assurance
        self._evidence_ingress = evidence_ingress
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
        # Reference ruler behind DecisionAuthorityPort; production adapts the
        # shipped ugence-decision-authority kernel onto the same port.
        self._authority_service = ReferenceDecisionAuthority()
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
        # RA-5 §12: in production mode a caller-supplied control status is inert.
        # This reference path constructs a ControlResult straight from
        # ``req.control_results`` (the RA-1→RA-4 conformance behavior); it is the
        # exact trust gap RA-5 closes, so it fails closed rather than silently
        # trusting caller input when production mode is active. Production callers
        # must use ``evaluate_with_evidence`` (admit → assure → bind).
        if self._production_mode:
            raise RiskAuthorityError(
                "reference evaluate() is disabled in production mode: a "
                "caller-supplied control status cannot mint authority (RA-5 §12). "
                "Use evaluate_with_evidence() with raw evidence."
            )
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
    # RA-5 production trusted-evidence path (RISK_AUTHORITY_RA5_SPEC.md §5, §10,
    # §12). Raw evidence → admitted evidence → assured controls → bound, RA-re-
    # checked trusted ControlResults → the *existing* non-compensatory gate. A
    # caller-supplied control status is never consulted here.
    # ------------------------------------------------------------------
    def evaluate_with_evidence(
        self,
        tenant_id: str,
        case_id: str,
        raw_evidence: tuple[ControlEvidenceRecord, ...],
        *,
        control_evidence: Optional[Mapping[str, tuple[str, ...]]] = None,
        conditions: tuple[str, ...] = (),
    ) -> RiskEvaluation:
        """Evaluate a case from admitted evidence and trusted control assurance.

        ``raw_evidence`` MUST be presented over an authenticated producer channel
        (RA-5 §13; audit H-2): a valid integrity digest proves only content
        tamper-detection, never producer authenticity, so each record is first
        gated through the injected ``TrustedEvidenceIngressPort`` — a record the
        deployment's channel verifier does not trust never reaches admission.

        Fail-closed at every step (RA-5 §11): untrusted-channel / admission
        unavailable / evidence rejected / stale / wrong-context ⇒ the backed
        control is ``MISSING``; assurance unavailable / evaluator error ⇒
        ``UNKNOWN``; neither can mint a ``PASS``. The RA state machine only
        advances on the *real* artifacts produced here — never on an actor label
        (§10; audit L-1): a case with missing/stale/untrusted required evidence is
        never represented as evidence-complete and cannot reach AUTHORITY_REVIEW.
        """

        if not (
            self._production_mode
            and self._evidence_admission is not None
            and self._control_assurance is not None
            and self._evidence_ingress is not None
        ):
            raise RiskAuthorityError(
                "evaluate_with_evidence() requires production mode with an "
                "EvidenceAdmissionPort, a ControlAssurancePort, and a "
                "TrustedEvidenceIngressPort (RA-5 §12, §13; audit H-2)"
            )

        now = self._clock()
        case = self._require_case(tenant_id, case_id)
        workflow = self._workflow_for(case)
        required = case.required_controls
        # Today policy_digest == WorkflowIR digest (RA-5 §6); kept distinct for
        # future divergence but bound to the same value now.
        policy_digest = case.workflow_ir_digest

        # --- 1. Admission (provenance/integrity/freshness/schema; §4, §6). ----
        # Only evidence that is admissible AND bound to THIS case's tenant /
        # workflow / policy context enters the admitted-in-context set. A
        # cross-tenant/-workflow/-policy record is filtered out here even if
        # storage returned it (§16), so no control can rest on it.
        admitted_by_id: dict[str, ControlEvidenceRecord] = {}
        for record in raw_evidence:
            if record.tenant_id != tenant_id:
                continue
            if record.workflow_ir_digest != case.workflow_ir_digest:
                continue
            if record.policy_digest != policy_digest:
                continue
            # H-2: authenticated-producer-channel gate BEFORE admission. A
            # self-computable integrity digest is not producer authenticity (§13);
            # a record the deployment's channel verifier does not trust never
            # enters the admitted set, so it can back no control (fail closed).
            try:
                channel_trusted = self._evidence_ingress.is_trusted(record, now=now)
            except Exception:  # noqa: BLE001 - ingress failure ⇒ untrusted
                channel_trusted = False
            if not channel_trusted:
                continue
            try:
                admissible = self._evidence_admission.is_admissible(record, now=now)
            except Exception:  # noqa: BLE001 - admission failure ⇒ inadmissible
                admissible = False
            if admissible and record.is_admitted() and record.is_current(now):
                admitted_by_id[record.evidence_id] = record

        admitted_ctx = AdmittedContext(
            valid_until_by_id={
                eid: rec.valid_until for eid, rec in admitted_by_id.items()
            }
        )
        binding_ctx = CaseBindingContext(
            tenant_id=tenant_id,
            case_id=case_id,
            workflow_ir_digest=case.workflow_ir_digest,
            policy_digest=policy_digest,
            required_controls=frozenset(required),
        )

        # --- 2. Control assurance per required control (§4, §5). --------------
        trusted: list[ControlResult] = []
        for control_id in required:
            backing = self._evidence_for_control(
                control_id, control_evidence, admitted_by_id
            )
            request = ControlAssuranceRequest(
                tenant_id=tenant_id,
                risk_case_id=case_id,
                workflow_ir_digest=case.workflow_ir_digest,
                policy_digest=policy_digest,
                control_id=control_id,
                subject_id=case.subject_id,
                admitted_evidence=backing,
                now=now,
            )
            try:
                assurance = self._control_assurance.evaluate(request)
                result = assurance.control_result
                if not assurance.available:
                    # Evaluator ran but reported itself unavailable ⇒ UNKNOWN.
                    result = bind_control_result(
                        request,
                        status=ControlStatus.UNKNOWN,
                        engine_id=assurance.engine_id,
                        engine_version=assurance.engine_version,
                        reason="control assurance unavailable",
                    )
            except Exception as exc:  # noqa: BLE001 - evaluator error ⇒ UNKNOWN
                result = bind_control_result(
                    request,
                    status=ControlStatus.UNKNOWN,
                    engine_id="control-assurance",
                    engine_version="",
                    reason=f"control assurance error: {type(exc).__name__}",
                )
            trusted.append(result)

        # --- 3. RA authoritative binding re-check (§8). ----------------------
        # A trusted result must belong to the exact current decision context and
        # rest only on admitted-in-context, current evidence. Results that fail
        # any clause are dropped, so the non-compensatory gate then sees the
        # control as MISSING (fail closed). A retained in-context FAIL still
        # governs (F-E preserved).
        trusted_tuple = tuple(trusted)
        results = usable_control_results(
            trusted_tuple, binding_ctx, admitted_ctx, now
        )
        self.controls.put(tenant_id, case_id, results)

        # --- 4. State machine, GATED on the real artifacts above (§10; L-1). --
        # A transition may only be taken when it corresponds to a real artifact,
        # not an actor label. A case with missing/stale/untrusted required
        # evidence must never be represented as evidence-complete, and must not
        # reach AUTHORITY_REVIEW — so no authority can be minted from it. The
        # recommendation below is still computed (and will DENY) for observability.
        result_control_ids = {r.control_id for r in results}
        evidence_complete = all(
            self._evidence_for_control(c, control_evidence, admitted_by_id)
            for c in required
        )
        controls_evaluated = evidence_complete and all(
            c in result_control_ids for c in required
        )

        case.transition(
            target=RiskCaseState.EVIDENCE_PENDING,
            actor="risk-authority",
            reason="evidence intake",
            now=now,
        )
        if evidence_complete:
            # EVIDENCE_PENDING → EVIDENCE_COMPLETE only when every required control
            # actually has admitted-in-context backing evidence (a real artifact).
            case.transition(
                target=RiskCaseState.EVIDENCE_COMPLETE,
                actor="evidence-admission",
                reason=(
                    f"admitted {len(admitted_by_id)} evidence record(s); every "
                    f"required control has in-context backing"
                ),
                now=now,
            )
            if controls_evaluated:
                # EVIDENCE_COMPLETE → CONTROL_EVALUATED only when a real, RA-re-
                # checked trusted result exists for every required control.
                case.transition(
                    target=RiskCaseState.CONTROL_EVALUATED,
                    actor="control-assurance",
                    reason=f"assured {len(required)} control(s); {len(results)} trusted",
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
            conditions=conditions,
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
                attributes={
                    "recommendation": evaluation.recommendation.value,
                    "mode": "production",
                },
            )
        )
        self._emit_case_events(case)
        self.cases.save(case)
        return evaluation

    @staticmethod
    def _evidence_for_control(
        control_id: str,
        control_evidence: Optional[Mapping[str, tuple[str, ...]]],
        admitted_by_id: Mapping[str, ControlEvidenceRecord],
    ) -> tuple[ControlEvidenceRecord, ...]:
        """The admitted-in-context evidence assigned to one control.

        When an explicit ``control_evidence`` map is supplied, only the listed
        ids that are actually admitted-in-context back the control (an id not in
        the admitted set is silently ignored ⇒ the control loses that backing and
        fails closed). Absent a map, every admitted-in-context record is a
        candidate (still bounded by admission + context filtering).
        """

        if control_evidence is not None:
            wanted = control_evidence.get(control_id, ())
            return tuple(
                admitted_by_id[eid] for eid in wanted if eid in admitted_by_id
            )
        return tuple(admitted_by_id.values())

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
        # A binding decision may only be issued once the case has actually reached
        # authority review. This gate runs *before* anything is persisted, so a
        # caller cannot skip evaluation (or replay the call out of order) and have
        # a decision survive a later illegal-transition error (spec AC-02).
        if case.state is not RiskCaseState.AUTHORITY_REVIEW:
            raise RiskAuthorityError(
                f"case {case_id!r} is in state {case.state.value}; a binding "
                "decision may only be issued from AUTHORITY_REVIEW (evaluate first)"
            )
        grant = self.authority.get_grant(tenant_id, req.principal_id)
        if grant is None:
            raise RiskAuthorityError(
                f"no authority grant for principal {req.principal_id!r}"
            )
        # The recommendation that gates authority is re-derived here from the
        # case's *persisted* control state, never taken from the caller-supplied
        # evaluation. The passed evaluation is advisory: a caller cannot substitute
        # an ALLOW for a case whose required controls failed. Only its
        # caller-requested conditions (which can merely tighten authority) are
        # carried forward.
        workflow = self._workflow_for(case)
        controls = self.controls.get(tenant_id, case_id)
        authoritative = self._engine.evaluate(
            workflow_ir=workflow,
            case=case,
            controls=controls,
            now=now,
            conditions=evaluation.conditions,
        )
        decision = self._authority_service.issue_decision(
            decision_id=self._ids.next("risk_dec"),
            case=case,
            evaluation=authoritative,
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
