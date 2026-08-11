"""RA-7 composition root + assurance-required read seam (spec §7/D4, §16, §19).

:class:`RuntimeAssuranceService` wires the ratified pipeline:

    observation
      → TrustedTelemetryIngress.admit   (trust boundary; §10)
      → RuntimeAssuranceObserver.record (dedupe / re-sequence; §13)
      → SafeEvaluator.evaluate          (risk-type the trajectory; §12)
      → AuthorityReassessmentSignalEmitter.emit  (material ⇒ RA-6 intake; §18)

By default this is **event-driven and additive** — an observer/ingress/evaluator
being unavailable never blocks the runtime hot path (spec §7/D4). Existing RA-6
authority still governs.

For the **opt-in** ``assurance_required`` mode (spec §7/D4, §16), the service
exposes a **read-only** current-assurance seam a pre-effect recheck / ActionGate
consumer may query. Under ``assurance_required`` a missing / stale / ``UNKNOWN`` /
``ESCALATED`` assurance state fails closed (``ERROR_NON_EXECUTABLE`` /
``DENY_IF_ASSURANCE_REQUIRED``, spec §20). This is never a default global
dependency and the read seam grants no authority.

Production composition (``production_mode=True``) refuses reference ingress /
policy / evaluator stand-ins (RA-5/RA-6 F-1), so a permissive stand-in can never
silently produce unsafe assurance.
"""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple

from .contracts import (
    AssessmentOutcome,
    RuntimeRiskLevel,
    TrajectoryAssessment,
    TrajectoryObservation,
)
from .evaluator import (
    ReferenceTrajectoryEvaluator,
    RuntimeAssuranceEvaluator,
    SafeEvaluator,
)
from .handoff import AuthorityReassessmentSignalEmitter, HandoffResult
from .ingress import (
    ExpectedBinding,
    IngressDecision,
    ReferenceTelemetryAuthenticator,
    TrustedTelemetryIngress,
)
from .observer import DEFAULT_WINDOW_SIZE, RuntimeAssuranceObserver
from .policy import ReferenceTrajectoryPolicyReader

__all__ = [
    "AssuranceStateRecord",
    "PreEffectAssuranceDecision",
    "RuntimeAssuranceOutcome",
    "RuntimeAssuranceService",
    "ReferenceCompositionRejectedError",
]


class ReferenceCompositionRejectedError(RuntimeError):
    """Raised when a reference stand-in is composed into production (F-1)."""


@dataclass(frozen=True)
class AssuranceStateRecord:
    """The latest known assurance state for a trajectory — evidence, not authority."""

    tenant_id: str
    workflow_instance_id: str
    envelope_id: str
    risk_level: RuntimeRiskLevel
    assessment_id: str
    produced_at: datetime


@dataclass(frozen=True)
class PreEffectAssuranceDecision:
    """Result of the opt-in assurance-required pre-effect check (spec §7/§20).

    Carries no authority: it only tells the pre-effect recheck / ActionGate
    consumer whether the assurance precondition is satisfied. ``CONTINUE_UNDER_RA6``
    means "no RA-7 objection — existing RA-6 authority governs".
    """

    outcome: AssessmentOutcome
    reasons: Tuple[str, ...] = ()
    state: Optional[AssuranceStateRecord] = None

    @property
    def executable(self) -> bool:
        return self.outcome is AssessmentOutcome.CONTINUE_UNDER_RA6


@dataclass(frozen=True)
class RuntimeAssuranceOutcome:
    """The end-to-end result of processing one observation — all evidence, no authority."""

    outcome: AssessmentOutcome
    ingress: IngressDecision
    assessment: Optional[TrajectoryAssessment] = None
    handoff: Optional[HandoffResult] = None
    reasons: Tuple[str, ...] = ()


class RuntimeAssuranceService:
    """Compose the RA-7 observe→assess→signal pipeline (spec §22–§23)."""

    def __init__(
        self,
        *,
        ingress: TrustedTelemetryIngress,
        observer: RuntimeAssuranceObserver,
        evaluator: RuntimeAssuranceEvaluator,
        emitter: Optional[AuthorityReassessmentSignalEmitter] = None,
        clock: Optional["object"] = None,
        production_mode: bool = False,
    ) -> None:
        if ingress is None or observer is None or evaluator is None:
            raise ValueError("RuntimeAssuranceService requires ingress, observer, evaluator")
        # F-1: refuse reference stand-ins in production composition.
        if production_mode:
            self._refuse_reference(ingress, evaluator)
        self._ingress = ingress
        self._observer = observer
        # Always wrap the evaluator so a malformed plug-in return degrades to UNKNOWN.
        self._evaluator = evaluator if isinstance(evaluator, SafeEvaluator) else SafeEvaluator(evaluator)
        self._emitter = emitter
        self._production_mode = production_mode
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._state: dict[Tuple[str, str], AssuranceStateRecord] = {}

    @staticmethod
    def _refuse_reference(
        ingress: TrustedTelemetryIngress, evaluator: RuntimeAssuranceEvaluator
    ) -> None:
        if not ingress.production_mode:
            raise ReferenceCompositionRejectedError(
                "production RuntimeAssuranceService requires a production-mode ingress"
            )
        inner = evaluator._inner if isinstance(evaluator, SafeEvaluator) else evaluator  # type: ignore[attr-defined]
        reader = getattr(inner, "_reader", None)
        if reader is not None and getattr(reader, "is_reference_reader", False):
            raise ReferenceCompositionRejectedError(
                "reference TrajectoryPolicyReader refused in production mode (F-1)"
            )

    # -- reference factory --------------------------------------------------
    @classmethod
    def reference(
        cls,
        *,
        policy_reader: Optional[ReferenceTrajectoryPolicyReader] = None,
        emitter: Optional[AuthorityReassessmentSignalEmitter] = None,
        window_size: int = DEFAULT_WINDOW_SIZE,
    ) -> "RuntimeAssuranceService":
        """Build a fully-wired **reference** service for conformance/tests.

        Every component is a clearly-marked reference stand-in; this factory is
        NOT for production (``production_mode`` stays ``False``). Production must
        inject real ingress / policy / evaluator explicitly.
        """

        reader = policy_reader or ReferenceTrajectoryPolicyReader()
        return cls(
            ingress=TrustedTelemetryIngress(ReferenceTelemetryAuthenticator()),
            observer=RuntimeAssuranceObserver(window_size=window_size),
            evaluator=ReferenceTrajectoryEvaluator(reader),
            emitter=emitter,
            production_mode=False,
        )

    # -- pipeline -----------------------------------------------------------
    def observe(
        self,
        observation: TrajectoryObservation,
        *,
        produced_at: datetime,
        expected: Optional[ExpectedBinding] = None,
        correlation_id: str = "",
    ) -> RuntimeAssuranceOutcome:
        """Process one observation end-to-end. Returns evidence; never authority.

        ``produced_at`` is caller-supplied (no wall clock) so the pipeline is
        deterministic. A rejected ingress short-circuits to ``IGNORE_EVENT``; a
        duplicate observation short-circuits to ``IGNORE_EVENT`` (idempotent). A
        material assessment is handed to the RA-6 intake iff an emitter is wired.
        """

        decision = self._ingress.admit(observation, expected=expected)
        if not decision.admitted:
            return RuntimeAssuranceOutcome(
                outcome=AssessmentOutcome.IGNORE_EVENT,
                ingress=decision,
                reasons=decision.reasons,
            )

        is_new = self._observer.record(decision.observation)  # type: ignore[arg-type]
        if not is_new:
            return RuntimeAssuranceOutcome(
                outcome=AssessmentOutcome.IGNORE_EVENT,
                ingress=decision,
                reasons=("duplicate event_id (idempotent)",),
            )

        obs = decision.observation
        assert obs is not None
        trajectory = self._observer.trajectory(
            obs.tenant_id, obs.workflow_instance_id
        )
        if trajectory is None:  # defensive; a just-recorded key always resolves
            return RuntimeAssuranceOutcome(
                outcome=AssessmentOutcome.UNKNOWN_ASSESSMENT,
                ingress=decision,
                reasons=("no trajectory after record",),
            )

        with self._lock:
            assessment_id = f"assess-{obs.workflow_instance_id}-{next(self._ids)}"
        assessment = self._evaluator.evaluate(
            trajectory, assessment_id=assessment_id, produced_at=produced_at
        )
        self._remember(assessment)

        handoff: Optional[HandoffResult] = None
        if assessment.is_material and self._emitter is not None:
            handoff = self._emitter.emit(
                assessment, correlation_id=correlation_id, observed_at=produced_at
            )

        return RuntimeAssuranceOutcome(
            outcome=assessment.outcome,
            ingress=decision,
            assessment=assessment,
            handoff=handoff,
            reasons=assessment.reasons,
        )

    def _remember(self, assessment: TrajectoryAssessment) -> None:
        # Record only decisive verdicts as current assurance state; an UNKNOWN does
        # not overwrite a prior known state (it is a blind window, not a new fact).
        if assessment.risk_level is RuntimeRiskLevel.UNKNOWN:
            return
        record = AssuranceStateRecord(
            tenant_id=assessment.tenant_id,
            workflow_instance_id=assessment.workflow_instance_id,
            envelope_id=assessment.envelope_id,
            risk_level=assessment.risk_level,
            assessment_id=assessment.assessment_id,
            produced_at=assessment.produced_at,
        )
        with self._lock:
            self._state[(assessment.tenant_id, assessment.workflow_instance_id)] = record

    # -- assurance-required read seam (D4; read-only; grants no authority) ---
    def assurance_state(
        self, tenant_id: str, workflow_instance_id: str
    ) -> Optional[AssuranceStateRecord]:
        """Current known assurance state for a trajectory, or ``None`` if none.

        Read-only. A pre-effect recheck / ActionGate consumer may query this under
        an ``assurance_required`` condition — it returns evidence, never authority.
        """

        with self._lock:
            return self._state.get((tenant_id, workflow_instance_id))

    def pre_effect_assurance_decision(
        self,
        *,
        tenant_id: str,
        workflow_instance_id: str,
        assurance_required: bool,
        now: datetime,
        max_age: Optional[timedelta] = None,
        deny_verdict: bool = False,
    ) -> PreEffectAssuranceDecision:
        """The opt-in assurance-required gate (spec §7/D4, §20).

        When ``assurance_required`` is ``False`` this always returns
        ``CONTINUE_UNDER_RA6`` — RA-7 is additive and never blocks by default. When
        ``True``, current assurance must be **present, fresh, and ``NORMAL``**;
        otherwise it fails closed (``ERROR_NON_EXECUTABLE``, or
        ``DENY_IF_ASSURANCE_REQUIRED`` when ``deny_verdict`` is set). No outcome ever
        widens authority.
        """

        if not assurance_required:
            return PreEffectAssuranceDecision(AssessmentOutcome.CONTINUE_UNDER_RA6)

        fail = (
            AssessmentOutcome.DENY_IF_ASSURANCE_REQUIRED
            if deny_verdict
            else AssessmentOutcome.ERROR_NON_EXECUTABLE
        )
        state = self.assurance_state(tenant_id, workflow_instance_id)
        if state is None:
            return PreEffectAssuranceDecision(
                fail, reasons=("assurance-required: no current assurance state",)
            )
        if max_age is not None and (now - state.produced_at) > max_age:
            return PreEffectAssuranceDecision(
                fail,
                reasons=("assurance-required: assurance state is stale",),
                state=state,
            )
        if state.risk_level is not RuntimeRiskLevel.NORMAL:
            return PreEffectAssuranceDecision(
                fail,
                reasons=(
                    f"assurance-required: current assurance is "
                    f"{state.risk_level.value}, not NORMAL",
                ),
                state=state,
            )
        return PreEffectAssuranceDecision(
            AssessmentOutcome.CONTINUE_UNDER_RA6, state=state
        )
