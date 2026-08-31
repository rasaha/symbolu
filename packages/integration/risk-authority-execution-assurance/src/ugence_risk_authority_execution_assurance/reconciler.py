"""Decision Authority reconciliation composition (spec §9, §14, §15, §25, §26).

RA-8 **reuses** the mature DA reconciliation kernel (``ExecutionIntent`` /
``ExecutionAttempt`` / ``ExecutionRecord`` / ``ReconciliationService`` /
``ReconciliationResult`` / ``CompensationRequirement``) and does **not**
re-implement reconciliation (spec §14). This module is the thin seam that:

  * builds a DA ``ExecutionIntent`` with ``authority_ref = envelope_id`` and
    ``execution_idempotency_key = AR idempotency key`` (spec §6/M-2, §15);
  * feeds the admitted effect observations into DA as ``ExecutionRecord``s via the
    authenticated ``record_external_outcome`` ingestion seam;
  * invokes DA ``reconcile_execution`` (the reused verdict + duplicate detection);
  * returns the DA verdict **and the full record set** so RA-8's safe aggregation
    (``aggregation.safe_aggregate``) can dominate the latest-wins verdict where they
    differ (spec §6 — M-1 closure).

Persistence/ownership (spec §25): DA owns the execution/reconciliation records;
RA-8 adds **no third canonical execution ledger**. The reference reconciler uses
DA's in-memory repository (reference-grade, allowed); a production deployment
injects a DA reconciler backed by real persistence + authenticated ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

from ugence_decision_authority.audit.repository import InMemoryAuditRepository
from ugence_decision_authority.audit.service import AuditService
from ugence_decision_authority.execution.execution_attempt import ExecutionAttempt
from ugence_decision_authority.execution.execution_intent import ExecutionIntent
from ugence_decision_authority.execution.execution_record import ExecutionRecord
from ugence_decision_authority.execution.reconciliation import ReconciliationResult
from ugence_decision_authority.execution.status import (
    ExecutionStatus,
    TransportStatus,
)
from ugence_decision_authority.identity.provider import StaticIdentityProvider
from ugence_decision_authority.policy.access import (
    AccessGrant,
    EvidenceAccessPolicy,
    GrantStore,
    Permission,
)
from ugence_decision_authority.repositories.execution_repository import (
    InMemoryExecutionRepository,
)
from ugence_decision_authority.services.reconciliation_service import ReconciliationService

from .contracts import EffectObservation, ExecutionCorrelation

__all__ = [
    "ExpectedEffect",
    "ReconciliationEvidence",
    "DecisionAuthorityReconciler",
    "ReferenceReconcilerRejectedError",
    "ReferenceDecisionAuthorityReconciler",
]

_RA8_ACTOR = "ra8-execution-assurance"

# Permissions the RA-8 composition needs on the DA ingestion + reconciliation seam.
_RA8_PERMISSIONS = frozenset(
    {
        Permission.RECORD_EXTERNAL_OUTCOME,
        Permission.RECONCILE_EXECUTION,
        Permission.QUERY_EXECUTION_STATUS,
    }
)


class ReferenceReconcilerRejectedError(RuntimeError):
    """Raised when the reference (in-memory) DA reconciler is used in production (F-1)."""


@dataclass(frozen=True)
class ExpectedEffect:
    """The authorized/expected effect carried per-intent from workflow/domain policy.

    Spec §15: workflow/domain policy owns the *expected effect*; DA owns the generic
    reconciliation semantics; RA-8 composes. These are **not** global hardcoded
    values — they are supplied per governed execution.
    """

    action_type: str
    target_system: str
    authorized_parameters: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "authorized_parameters", dict(self.authorized_parameters or {})
        )


@dataclass(frozen=True)
class ReconciliationEvidence:
    """The DA reconciliation output RA-8 aggregates over (evidence, never authority)."""

    records: Tuple[ExecutionRecord, ...] = ()
    da_result: Optional[ReconciliationResult] = None
    execution_intent_id: str = ""
    error: Optional[str] = None

    @property
    def available(self) -> bool:
        """False when DA was unavailable / raised — the assessment defers, never MATCHED."""

        return self.error is None


@runtime_checkable
class DecisionAuthorityReconciler(Protocol):
    """The seam RA-8 composes for DA reconciliation (production injects the real one)."""

    is_reference_reconciler: bool

    def reconcile(
        self,
        correlation: ExecutionCorrelation,
        observations: Sequence[EffectObservation],
        expected: ExpectedEffect,
    ) -> ReconciliationEvidence:
        ...


class ReferenceDecisionAuthorityReconciler:
    """Reference DA reconciler over DA's in-memory kernel (reference-grade; F-1).

    Composes a genuine DA ``ReconciliationService`` (real reconciliation semantics,
    real duplicate detection, real audit) over DA's in-memory repository. It is
    reference-grade persistence (allowed, spec §25) and **refused in production**
    (``is_reference_reconciler = True``): production injects a DA reconciler backed
    by durable persistence and authenticated ingestion.
    """

    is_reference_reconciler = True

    def __init__(self) -> None:
        identity = StaticIdentityProvider()
        identity.register_service(_RA8_ACTOR, authenticated=True)
        self._identity = identity

    def _fresh_service(self, tenant_id: str):
        repo = InMemoryExecutionRepository()
        grants = GrantStore()
        grants.add(
            AccessGrant(
                principal_id=_RA8_ACTOR, tenant_id=tenant_id, permissions=_RA8_PERMISSIONS
            )
        )
        policy = EvidenceAccessPolicy(grants)
        audit = AuditService(InMemoryAuditRepository())
        service = ReconciliationService(repo, _NullExternalPort(), audit, self._identity, policy)
        return repo, service

    def reconcile(
        self,
        correlation: ExecutionCorrelation,
        observations: Sequence[EffectObservation],
        expected: ExpectedEffect,
    ) -> ReconciliationEvidence:
        try:
            repo, service = self._fresh_service(correlation.tenant_id)
            intent = self._build_intent(correlation, expected)
            repo.create_execution_intent(intent)
            external_request_id = correlation.external_request_id or f"ext:{correlation.attempt_id}"
            attempt = ExecutionAttempt(
                execution_attempt_id=f"exa:{correlation.attempt_id}",
                execution_intent_id=intent.execution_intent_id,
                attempt_number=1,
                adapter_id="ra8-effect-bridge",
                adapter_version="1.0",
                request_payload_hash=correlation.correlation_digest,
                transport_status=TransportStatus.ACKNOWLEDGED,
                external_request_id=external_request_id,
                correlation_id=correlation.correlation_id,
            )
            repo.record_execution_attempt(attempt)

            for idx, obs in enumerate(observations):
                service.record_external_outcome(
                    intent_id=intent.execution_intent_id,
                    actor=_RA8_ACTOR,
                    business_outcome=obs.business_outcome,
                    observed_parameters=dict(obs.observed_parameters),
                    external_result_id=obs.external_effect_id or f"{external_request_id}:res{idx}",
                    finality=obs.finality,
                    external_request_id=external_request_id,
                )

            records = service.get_execution_records(intent.execution_intent_id)
            da_result: Optional[ReconciliationResult] = None
            if records:
                da_result = service.reconcile_execution(
                    intent_id=intent.execution_intent_id, actor=_RA8_ACTOR
                )
            return ReconciliationEvidence(
                records=records,
                da_result=da_result,
                execution_intent_id=intent.execution_intent_id,
            )
        except Exception as exc:  # noqa: BLE001 - a reconciliation fault fails closed
            return ReconciliationEvidence(error=repr(exc))

    def _build_intent(
        self, correlation: ExecutionCorrelation, expected: ExpectedEffect
    ) -> ExecutionIntent:
        # authority_ref = envelope_id (spec §6/M-2, §15). The action-request /
        # authorization / CER references are derived from the governed correlation;
        # RA-8 introduces no new authority artifact — these are references into the
        # already-governed decision chain.
        intent = ExecutionIntent(
            execution_intent_id=f"exi:{correlation.correlation_digest[:24]}",
            tenant_id=correlation.tenant_id,
            action_request_id=f"ar:{correlation.correlation_id}",
            action_request_version=1,
            authorization_id=f"authz:{correlation.envelope_id}",
            cer_id=f"cer:{correlation.envelope_id}",
            action_type=expected.action_type,
            target_system=expected.target_system,
            authorized_parameters=dict(expected.authorized_parameters),
            authority_ref=correlation.envelope_id,
            correlation_id=correlation.correlation_id,
            execution_idempotency_key=correlation.idempotency_key,
            created_by=_RA8_ACTOR,
            status=ExecutionStatus.DISPATCHED,
            intent_version_id=f"iv:{correlation.correlation_digest[:24]}",
        )
        return intent.model_copy(update={"content_hash": intent.compute_hash()})


class _NullExternalPort:
    """A DA external port that never dispatches or queries (RA-8 feeds records directly).

    RA-8 admits effect observations through its own trusted ingress and records them
    via ``record_external_outcome``; it never uses DA's ``dispatch`` / ``query_status``
    seam, so this port raises if either is called (fail-closed, never a fabricated
    outcome).
    """

    adapter_id = "ra8-null-external"
    adapter_version = "1.0"

    def dispatch(self, intent):  # noqa: D401 - see class docstring
        raise RuntimeError("RA-8 does not dispatch through DA; effect ingress is external")

    def query_status(self, external_request_id):
        raise RuntimeError("RA-8 does not query through DA; effect ingress is external")
