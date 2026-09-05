"""RiskDecisionCase — the aggregate root of the risk lifecycle (spec §8).

The case is the one place state changes. It is deliberately *not* a frozen
value object: state is guarded behind :meth:`transition`, which validates
legality against the state machine and emits a :class:`GovernanceEvent`. There
is no public setter for ``state`` — ``case.state = ...`` is not part of the API
(user brief §3). Illegal or skipped transitions raise, so authority can never
be issued before required states are reached (spec AC-02).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional

from .enums import GovernanceEventType, RiskCaseState, RiskClass
from .errors import IllegalTransitionError, SnapshotIntegrityError
from .events import GovernanceEvent, make_event

__all__ = ["RiskDecisionCase", "RiskCaseSnapshot", "ALLOWED_TRANSITIONS", "RequestedCapabilities"]


# The legal successor states for each state (spec §8.3). States absent as keys
# (DENIED, EXPIRED, REVOKED, SUPERSEDED) are terminal.
ALLOWED_TRANSITIONS: Mapping[RiskCaseState, frozenset[RiskCaseState]] = {
    RiskCaseState.CREATED: frozenset({RiskCaseState.CLASSIFIED}),
    RiskCaseState.CLASSIFIED: frozenset({RiskCaseState.CONTROLS_RESOLVED}),
    RiskCaseState.CONTROLS_RESOLVED: frozenset({RiskCaseState.EVIDENCE_PENDING}),
    RiskCaseState.EVIDENCE_PENDING: frozenset({RiskCaseState.EVIDENCE_COMPLETE}),
    RiskCaseState.EVIDENCE_COMPLETE: frozenset({RiskCaseState.CONTROL_EVALUATED}),
    RiskCaseState.CONTROL_EVALUATED: frozenset({RiskCaseState.AUTHORITY_REVIEW}),
    RiskCaseState.AUTHORITY_REVIEW: frozenset(
        {RiskCaseState.APPROVED, RiskCaseState.CONDITIONAL, RiskCaseState.DENIED}
    ),
    RiskCaseState.APPROVED: frozenset({RiskCaseState.ENVELOPE_ISSUED}),
    RiskCaseState.CONDITIONAL: frozenset({RiskCaseState.ENVELOPE_ISSUED}),
    RiskCaseState.ENVELOPE_ISSUED: frozenset({RiskCaseState.ACTIVE}),
    RiskCaseState.ACTIVE: frozenset(
        {RiskCaseState.EXPIRED, RiskCaseState.REVOKED, RiskCaseState.SUPERSEDED}
    ),
}


@dataclass(frozen=True)
class RequestedCapabilities:
    """The capabilities a subject is requesting (spec §8.2)."""

    tools: tuple[str, ...] = ()
    autonomy_level: int = 0
    data_classes: tuple[str, ...] = ()


class RiskDecisionCase:
    """Mutable aggregate governing one risk evaluation/approval lifecycle."""

    def __init__(
        self,
        *,
        case_id: str,
        tenant_id: str,
        subject_id: str,
        model_id: str,
        purpose: str,
        domain: str,
        jurisdictions: tuple[str, ...],
        requested: RequestedCapabilities,
        workflow_ir_id: str,
        workflow_ir_version: str,
        workflow_ir_digest: str,
        created_at: datetime,
        correlation_id: str = "",
        inherent_risk: Optional[RiskClass] = None,
        residual_risk: Optional[RiskClass] = None,
        state: RiskCaseState = RiskCaseState.CREATED,
    ) -> None:
        self.case_id = case_id
        self.tenant_id = tenant_id
        self.subject_id = subject_id
        self.model_id = model_id
        self.purpose = purpose
        self.domain = domain
        self.jurisdictions = jurisdictions
        self.requested = requested
        self.workflow_ir_id = workflow_ir_id
        self.workflow_ir_version = workflow_ir_version
        self.workflow_ir_digest = workflow_ir_digest
        self.created_at = created_at
        self.correlation_id = correlation_id
        self.inherent_risk = inherent_risk
        self.residual_risk = residual_risk
        self.required_controls: tuple[str, ...] = ()
        self._state = state
        self._events: list[GovernanceEvent] = []
        self._seq = 0

    # ------------------------------------------------------------------
    # State (read-only property; no setter — use transition()).
    # ------------------------------------------------------------------
    @property
    def state(self) -> RiskCaseState:
        return self._state

    # ------------------------------------------------------------------
    # Durable snapshot (ADR durable persistence, D-2).
    # ------------------------------------------------------------------
    def snapshot(self) -> "RiskCaseSnapshot":
        """The complete, canonicalizable state of this aggregate, events included."""

        return RiskCaseSnapshot(
            case_id=self.case_id,
            tenant_id=self.tenant_id,
            subject_id=self.subject_id,
            model_id=self.model_id,
            purpose=self.purpose,
            domain=self.domain,
            jurisdictions=tuple(self.jurisdictions),
            requested=self.requested,
            workflow_ir_id=self.workflow_ir_id,
            workflow_ir_version=self.workflow_ir_version,
            workflow_ir_digest=self.workflow_ir_digest,
            created_at=self.created_at,
            correlation_id=self.correlation_id,
            inherent_risk=self.inherent_risk,
            residual_risk=self.residual_risk,
            state=self._state,
            required_controls=tuple(self.required_controls),
            seq=self._seq,
            events=tuple(self._events),
        )

    @classmethod
    def from_snapshot(cls, snapshot: "RiskCaseSnapshot") -> "RiskDecisionCase":
        """Rebuild an aggregate from a snapshot, replaying and chain-checking its events.

        Refuses a snapshot whose events do not form one unbroken ``prev_digest`` chain
        rooted at ``None``, whose ids are not the sequential ids :meth:`transition`
        mints, whose events name another aggregate or tenant, or whose ``seq`` does
        not equal the number of events. A stored aggregate that fails here is not
        loaded partially; it is refused.
        """

        if not isinstance(snapshot, RiskCaseSnapshot):
            raise SnapshotIntegrityError("from_snapshot requires a RiskCaseSnapshot")
        events = tuple(snapshot.events)
        if snapshot.seq != len(events):
            raise SnapshotIntegrityError(
                f"case {snapshot.case_id}: seq {snapshot.seq} != {len(events)} events")
        prev_digest: Optional[str] = None
        for index, event in enumerate(events, start=1):
            if not isinstance(event, GovernanceEvent):
                raise SnapshotIntegrityError(f"case {snapshot.case_id}: event {index} is not a GovernanceEvent")
            if event.tenant_id != snapshot.tenant_id or event.aggregate_id != snapshot.case_id:
                raise SnapshotIntegrityError(
                    f"case {snapshot.case_id}: event {event.event_id} names another aggregate")
            if event.event_id != f"evt_{snapshot.case_id}_{index:04d}":
                raise SnapshotIntegrityError(
                    f"case {snapshot.case_id}: event {index} carries id {event.event_id!r}")
            if event.prev_digest != prev_digest:
                raise SnapshotIntegrityError(
                    f"case {snapshot.case_id}: event {event.event_id} breaks the prev_digest chain")
            prev_digest = event.payload_digest
        case = cls(
            case_id=snapshot.case_id,
            tenant_id=snapshot.tenant_id,
            subject_id=snapshot.subject_id,
            model_id=snapshot.model_id,
            purpose=snapshot.purpose,
            domain=snapshot.domain,
            jurisdictions=tuple(snapshot.jurisdictions),
            requested=snapshot.requested,
            workflow_ir_id=snapshot.workflow_ir_id,
            workflow_ir_version=snapshot.workflow_ir_version,
            workflow_ir_digest=snapshot.workflow_ir_digest,
            created_at=snapshot.created_at,
            correlation_id=snapshot.correlation_id,
            inherent_risk=snapshot.inherent_risk,
            residual_risk=snapshot.residual_risk,
            state=snapshot.state,
        )
        case.required_controls = tuple(snapshot.required_controls)
        case._events = list(events)
        case._seq = snapshot.seq
        return case

    @property
    def events(self) -> tuple[GovernanceEvent, ...]:
        return tuple(self._events)

    def evaluation_context(self) -> dict[str, object]:
        """The fact context WorkflowIR predicates evaluate against (spec §8)."""

        return {
            "purpose": self.purpose,
            "domain": self.domain,
            "business_process": self.domain,
            "jurisdiction": list(self.jurisdictions),
            "model_id": self.model_id,
            "actor_id": self.subject_id,
            "autonomy_level": self.requested.autonomy_level,
            "tools": list(self.requested.tools),
            "data_classes": list(self.requested.data_classes),
            "risk_class": self.inherent_risk.value if self.inherent_risk else None,
            "residual_risk": self.residual_risk.value if self.residual_risk else None,
        }

    # ------------------------------------------------------------------
    # Guarded mutation.
    # ------------------------------------------------------------------
    def classify(
        self, *, inherent: RiskClass, residual: RiskClass, actor: str, now: datetime
    ) -> GovernanceEvent:
        self.inherent_risk = inherent
        self.residual_risk = residual
        event = self.transition(
            target=RiskCaseState.CLASSIFIED,
            actor=actor,
            reason=f"classified inherent={inherent.value} residual={residual.value}",
            now=now,
            event_type=GovernanceEventType.RISK_CLASSIFIED,
        )
        return event

    def set_required_controls(
        self, controls: tuple[str, ...], *, actor: str, now: datetime
    ) -> GovernanceEvent:
        self.required_controls = controls
        return self.transition(
            target=RiskCaseState.CONTROLS_RESOLVED,
            actor=actor,
            reason=f"required controls: {list(controls)}",
            now=now,
            event_type=GovernanceEventType.CONTROL_REQUIRED,
        )

    def transition(
        self,
        *,
        target: RiskCaseState,
        actor: str,
        reason: str,
        now: datetime,
        event_type: GovernanceEventType = GovernanceEventType.CASE_STATE_CHANGED,
    ) -> GovernanceEvent:
        """Validate and apply a state transition, emitting a governance event."""

        legal = ALLOWED_TRANSITIONS.get(self._state, frozenset())
        if target not in legal:
            raise IllegalTransitionError(
                f"illegal transition {self._state.value} -> {target.value}; "
                f"legal targets: {sorted(s.value for s in legal)}"
            )
        prev = self._state
        self._state = target
        self._seq += 1
        prev_digest = self._events[-1].payload_digest if self._events else None
        event = make_event(
            event_id=f"evt_{self.case_id}_{self._seq:04d}",
            tenant_id=self.tenant_id,
            event_type=event_type,
            aggregate_id=self.case_id,
            actor=actor,
            timestamp=now,
            correlation_id=self.correlation_id,
            payload={"from": prev.value, "to": target.value, "reason": reason},
            prev_digest=prev_digest,
        )
        self._events.append(event)
        return event


@dataclass(frozen=True)
class RiskCaseSnapshot:
    """The durable form of a :class:`RiskDecisionCase`: every field, plus its event chain.

    A frozen dataclass so the persistence codec can encode and strictly decode it by
    annotation; :meth:`RiskDecisionCase.from_snapshot` is the only way back to an
    aggregate, and it replays the chain before it hands one over.
    """

    case_id: str
    tenant_id: str
    subject_id: str
    model_id: str
    purpose: str
    domain: str
    jurisdictions: tuple[str, ...]
    requested: RequestedCapabilities
    workflow_ir_id: str
    workflow_ir_version: str
    workflow_ir_digest: str
    created_at: datetime
    correlation_id: str
    inherent_risk: Optional[RiskClass]
    residual_risk: Optional[RiskClass]
    state: RiskCaseState
    required_controls: tuple[str, ...]
    seq: int
    events: tuple[GovernanceEvent, ...]
