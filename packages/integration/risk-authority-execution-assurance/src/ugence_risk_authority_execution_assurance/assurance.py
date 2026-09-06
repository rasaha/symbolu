"""RA-8 composition — correlate → ingest → reconcile → aggregate → assess → hand off.

``EffectAssuranceService`` is the single composition owner (spec §8). It ties the
ratified flow together and never mutates authority:

    governed authority context + AR attempt
        → ExecutionCorrelation                    (bind; spec §5/§18)
        → TrustedEffectIngress                     (trust boundary; §4/D-A, §19)
        → DecisionAuthorityReconciler              (reuse DA kernel; §9/§14)
        → safe_aggregate (non-compensatory)        (close M-1; §6/D-C)
        → EffectAssuranceAssessment                (neutral verdict; §14)
        → EffectAssuranceSignalEmitter             (material only; §7/§22)
        → RA-6 reassessor → sole writer → revoke / epoch / no-op

RA-8 OBSERVES, CORRELATES, AGGREGATES, AND ASSESSES POST-EFFECT. RA-6 OWNS
AUTHORITY CONSEQUENCES. No failure resolves to ``MATCHED`` (spec §27); a false
mismatch can cost availability but can never widen authority (spec §18).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple

from .aggregation import safe_aggregate
from .contracts import (
    EffectAssuranceAssessment,
    EffectFinality,
    EffectObservation,
    EffectReasonCode,
    EffectReconciliationOutcome,
    ExecutionCorrelation,
)
from .correlation import ExecutionCorrelator, GovernedAuthorityContext
from .handoff import EffectAssuranceSignalEmitter, HandoffResult
from .ingress import (
    AttestedEffectInput,
    IngressDecision,
    IngressDisposition,
    ReferenceEffectSourceAuthenticator,
    TrustedEffectIngress,
)
from .provenance import production_matched_gate
from .reconciler import (
    DecisionAuthorityReconciler,
    ExpectedEffect,
    ReconciliationEvidence,
    ReferenceDecisionAuthorityReconciler,
    ReferenceReconcilerRejectedError,
)

__all__ = [
    "EffectAssuranceOutcome",
    "EffectAssuranceService",
    "CompositionRejectedError",
]

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class CompositionRejectedError(RuntimeError):
    """Raised when a reference adapter is composed in production (F-1 aggregation)."""


@dataclass(frozen=True)
class EffectAssuranceOutcome:
    """The full audited result of one RA-8 assessment (evidence, never authority)."""

    assessment: EffectAssuranceAssessment
    correlation: ExecutionCorrelation
    evidence: ReconciliationEvidence
    ingress_decisions: Tuple[IngressDecision, ...] = ()
    handoff: Optional[HandoffResult] = None

    @property
    def outcome(self) -> EffectReconciliationOutcome:
        return self.assessment.outcome


class EffectAssuranceService:
    """Compose the RA-8 flow. Holds only neutral seams; never a lifecycle writer."""

    def __init__(
        self,
        *,
        ingress: TrustedEffectIngress,
        reconciler: DecisionAuthorityReconciler,
        emitter: Optional[EffectAssuranceSignalEmitter] = None,
        correlator: Optional[ExecutionCorrelator] = None,
        production_mode: bool = False,
    ) -> None:
        if ingress is None or reconciler is None:
            raise ValueError("EffectAssuranceService requires an ingress and a reconciler")
        if production_mode:
            if getattr(reconciler, "is_reference_reconciler", False):
                raise ReferenceReconcilerRejectedError(
                    "reference DA reconciler refused in production mode (F-1): inject a "
                    "DA reconciler backed by durable persistence + authenticated ingestion"
                )
            # The outer composition boundary must not rely on the caller having
            # remembered to construct a production-posture ingress. A production
            # service requires a production-safe ingress — and because a
            # ``TrustedEffectIngress`` built with ``production_mode=True`` already
            # refuses a reference effect authenticator at construction (D-A/F-1),
            # this single exact-bool check transitively guarantees no reference
            # authenticator can reach a production reconciliation. Fail closed on any
            # non-``True`` posture (malformed/None/1/"yes" never satisfy it).
            if getattr(ingress, "production_mode", False) is not True:
                raise CompositionRejectedError(
                    "production EffectAssuranceService requires a production-posture "
                    "TrustedEffectIngress (constructed with production_mode=True); a "
                    "reference/default ingress is refused so a reference effect "
                    "authenticator can never become production reconciliation evidence "
                    "(spec §4/D-A, §19, RA-5/6/7 F-1)"
                )
        self._ingress = ingress
        self._reconciler = reconciler
        self._emitter = emitter
        self._correlator = correlator or ExecutionCorrelator()
        self._production_mode = production_mode

    # ------------------------------------------------------------------ #
    @classmethod
    def reference(
        cls,
        *,
        emitter: Optional[EffectAssuranceSignalEmitter] = None,
    ) -> "EffectAssuranceService":
        """A reference (non-production) composition over the in-memory adapters."""

        return cls(
            ingress=TrustedEffectIngress(ReferenceEffectSourceAuthenticator()),
            reconciler=ReferenceDecisionAuthorityReconciler(),
            emitter=emitter,
        )

    # ------------------------------------------------------------------ #
    def assess(
        self,
        context: GovernedAuthorityContext,
        *,
        attempt_id: str,
        expected: ExpectedEffect,
        observations: Sequence[EffectObservation] = (),
        external_request_id: str = "",
        idempotency_key: str = "",
        provider: str = "",
        effect_source_available: bool = True,
        produced_at: Optional[datetime] = None,
        emit: bool = True,
        attested: Sequence[AttestedEffectInput] = (),
        verification_instant: Optional[datetime] = None,
    ) -> EffectAssuranceOutcome:
        """Run one full RA-8 assessment over a governed execution.

        ``observations`` are pre-normalized :class:`EffectObservation`s (build them
        from a governance-contracts ``ExecutionObservation`` via
        :func:`~.ingress.normalize_execution_observation`). Every one passes the
        trusted ingress before it can influence the verdict; a rejected observation
        can never become a reconciliation record (spec §18, §19, §27).

        ``attested`` are signed observations admitted through
        :meth:`TrustedEffectIngress.admit_attested` at the explicitly injected
        ``verification_instant`` (RI-5). ``produced_at`` is never used as that
        instant: it is the assessment timestamp, and an attestation's own
        ``attested_at`` is the attester's claim. In production the unsigned path
        rejects every observation (RI-2) and a ``MATCHED`` verdict requires verified
        independent-observer provenance (RI-3).
        """

        now = produced_at if isinstance(produced_at, datetime) else datetime.now(timezone.utc)
        correlation = self._correlator.mint(
            context,
            attempt_id=attempt_id,
            external_request_id=external_request_id,
            provider=provider,
            idempotency_key=idempotency_key,
            completed_at=now,
        )

        # 1. Trust boundary: admit each observation; a rejection never reconciles.
        admitted: List[EffectObservation] = []
        decisions: List[IngressDecision] = []
        for obs in observations:
            decision = self._ingress.admit(obs, correlation=correlation)
            decisions.append(decision)
            if decision.admitted and decision.observation is not None:
                admitted.append(decision.observation)
        for item in attested:
            if type(item) is not AttestedEffectInput:
                decisions.append(IngressDecision(
                    IngressDisposition.REJECTED, reasons=("not an AttestedEffectInput",)
                ))
                continue
            decision = self._ingress.admit_attested(
                item.attestation,
                correlation=correlation,
                as_of=verification_instant,  # type: ignore[arg-type] - the ingress rejects a bad instant
                observation_id=item.observation_id,
                external_effect_id=item.external_effect_id,
                source=item.source,
                source_version=item.source_version,
            )
            decisions.append(decision)
            if decision.admitted and decision.observation is not None:
                admitted.append(decision.observation)
        supplied = bool(observations) or bool(attested)

        # 2. Effect-source availability / trusted-evidence gates (never MATCHED).
        if effect_source_available is not True:
            return self._finish(
                correlation,
                ReconciliationEvidence(error="effect source unavailable"),
                decisions,
                now,
                outcome=EffectReconciliationOutcome.UNVERIFIABLE,
                reason_code=EffectReasonCode.EFFECT_SOURCE_UNAVAILABLE,
                reason="effect source unavailable; authority unchanged",
                finality=EffectFinality.PENDING,
                emit=emit,
            )
        if supplied and not admitted:
            return self._finish(
                correlation,
                ReconciliationEvidence(error="no trusted effect observation admitted"),
                decisions,
                now,
                outcome=EffectReconciliationOutcome.UNVERIFIABLE,
                reason_code=EffectReasonCode.EFFECT_SOURCE_UNAVAILABLE,
                reason="every effect observation was rejected at the trust boundary",
                finality=EffectFinality.PENDING,
                emit=emit,
            )
        if not supplied:
            return self._finish(
                correlation,
                ReconciliationEvidence(),
                decisions,
                now,
                outcome=EffectReconciliationOutcome.UNKNOWN,
                reason_code=EffectReasonCode.NO_OBSERVATION,
                reason="no effect observation yet; reconciliation pending",
                finality=EffectFinality.PENDING,
                emit=emit,
            )

        # 3. Reuse DA reconciliation (verdict + duplicate detection). A raising
        #    reconciler is caught here so a reconciliation exception fails closed to
        #    UNKNOWN, never MATCHED (spec §27, §28).
        try:
            evidence = self._reconciler.reconcile(correlation, admitted, expected)
        except Exception as exc:  # noqa: BLE001 - reconciliation fault ⇒ fail closed
            evidence = ReconciliationEvidence(error=repr(exc))
        if not evidence.available:
            # DA unavailable / reconciliation error → fail-closed, never MATCHED.
            return self._finish(
                correlation,
                evidence,
                decisions,
                now,
                outcome=EffectReconciliationOutcome.UNKNOWN,
                reason_code=EffectReasonCode.RECONCILIATION_ERROR,
                reason=f"reconciliation unavailable: {evidence.error}",
                finality=EffectFinality.PENDING,
                emit=emit,
            )

        # 4. Safe non-compensatory aggregation over the FULL record set (closes M-1).
        aggregate = safe_aggregate(
            evidence.records, expected_parameters=expected.authorized_parameters
        )
        # 4b. RI-3: in production, MATCHED requires verified independent-observer
        #     provenance on an admitted, favorable, final observation. Every other
        #     verdict passes through untouched, so adverse evidence is never masked.
        gate = production_matched_gate(
            aggregate.outcome, admitted, production_mode=self._production_mode
        )
        if gate is not None:
            withheld_outcome, withheld_code, withheld_reason = gate
            return self._finish(
                correlation,
                evidence,
                decisions,
                now,
                outcome=withheld_outcome,
                reason_code=withheld_code,
                reason=withheld_reason,
                finality=aggregate.finality,
                emit=emit,
            )
        assessment = EffectAssuranceAssessment(
            assessment_id=self._assessment_id(correlation, aggregate.outcome, now),
            tenant_id=correlation.tenant_id,
            workflow_instance_id=correlation.workflow_instance_id,
            envelope_id=correlation.envelope_id,
            authorized_action_digest=correlation.authorized_action_digest,
            attempt_id=correlation.attempt_id,
            outcome=aggregate.outcome,
            finality=aggregate.finality,
            produced_at=now,
            correlation_digest=correlation.correlation_digest,
            execution_intent_id=evidence.execution_intent_id,
            reconciliation_id=(
                evidence.da_result.reconciliation_id if evidence.da_result else ""
            ),
            da_status=evidence.da_result.status if evidence.da_result else None,
            reason_codes=aggregate.reason_codes,
            reasons=aggregate.reasons,
            evidence_refs=aggregate.dominant_record_ids,
            compensation_recommended=aggregate.compensation_recommended,
        )
        handoff = self._maybe_emit(assessment, correlation, emit)
        return EffectAssuranceOutcome(
            assessment=assessment,
            correlation=correlation,
            evidence=evidence,
            ingress_decisions=tuple(decisions),
            handoff=handoff,
        )

    # ------------------------------------------------------------------ #
    def _finish(
        self,
        correlation: ExecutionCorrelation,
        evidence: ReconciliationEvidence,
        decisions: Sequence[IngressDecision],
        now: datetime,
        *,
        outcome: EffectReconciliationOutcome,
        reason_code: EffectReasonCode,
        reason: str,
        finality: EffectFinality,
        emit: bool,
    ) -> EffectAssuranceOutcome:
        assessment = EffectAssuranceAssessment(
            assessment_id=self._assessment_id(correlation, outcome, now),
            tenant_id=correlation.tenant_id,
            workflow_instance_id=correlation.workflow_instance_id,
            envelope_id=correlation.envelope_id,
            authorized_action_digest=correlation.authorized_action_digest,
            attempt_id=correlation.attempt_id,
            outcome=outcome,
            finality=finality,
            produced_at=now,
            correlation_digest=correlation.correlation_digest,
            execution_intent_id=evidence.execution_intent_id,
            reason_codes=(reason_code,),
            reasons=(reason,),
        )
        handoff = self._maybe_emit(assessment, correlation, emit)
        return EffectAssuranceOutcome(
            assessment=assessment,
            correlation=correlation,
            evidence=evidence,
            ingress_decisions=tuple(decisions),
            handoff=handoff,
        )

    def _maybe_emit(
        self,
        assessment: EffectAssuranceAssessment,
        correlation: ExecutionCorrelation,
        emit: bool,
    ) -> Optional[HandoffResult]:
        if not emit or self._emitter is None or not assessment.is_material:
            return None
        return self._emitter.emit(assessment, correlation_id=correlation.correlation_id)

    @staticmethod
    def _assessment_id(
        correlation: ExecutionCorrelation, outcome: EffectReconciliationOutcome, now: datetime
    ) -> str:
        # Deterministic within a governed execution + verdict + observation instant,
        # so a replayed identical assessment dedupes at the RA-6 intake (spec §22/§27).
        ts = int((now - _EPOCH).total_seconds()) if isinstance(now, datetime) else 0
        return f"ra8:{correlation.correlation_digest[:24]}:{outcome.value}:{ts}"
