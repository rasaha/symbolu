"""Execution correlation — the runtime↔DA↔envelope binding (spec §5, §18).

RA-8 owns a neutral :class:`~.contracts.ExecutionCorrelation`, minted at
authorize-time from the governed authority context (envelope id, authorized action
digest, correlation id, tenant, workflow instance) and joined to the Agent Runtime
execution attempt by ``correlation_id`` + ``proposal_fingerprint``. No package
imports across the AR↔DA boundary: RA-8 mints the correlation from facts it already
holds and reads AR's neutral, duck-typed event contract (spec §5 "boundaries
preserved").

The correlator also enforces the **intrinsic binding tuple** (spec §18): an effect
observation must match ``(tenant, workflow-instance, envelope, authorized action
digest, attempt)`` — storage partitioning is *not* enough. A receipt for the wrong
tenant / workflow / envelope / action digest / attempt is rejected, never applied
to another execution (invariant I9).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from .contracts import EffectObservation, ExecutionCorrelation

__all__ = [
    "GovernedAuthorityContext",
    "ExecutionCorrelator",
]


@dataclass(frozen=True)
class GovernedAuthorityContext:
    """The authorize-time authority facts RA-8 mints a correlation from (spec §5).

    Every field is available on the ``GovernedExecutionDecision`` /
    ``RiskAuthorityMachineResult`` at authorize-time (spec §5 table): the signed
    envelope id, the authorized action digest (== the Agent Runtime
    ``proposal_fingerprint``), the join-key ``correlation_id``, the tenant, and the
    workflow instance. It carries **no authority** — it is a bundle of already-issued
    references, never a grant.
    """

    tenant_id: str
    workflow_instance_id: str
    envelope_id: str
    authorized_action_digest: str
    correlation_id: str
    provider: str = ""
    idempotency_key: str = ""

    def binding_errors(self) -> Tuple[str, ...]:
        reasons: list[str] = []
        for name in (
            "tenant_id",
            "workflow_instance_id",
            "envelope_id",
            "authorized_action_digest",
            "correlation_id",
        ):
            if not str(getattr(self, name)).strip():
                reasons.append(f"missing {name}")
        return tuple(reasons)


class ExecutionCorrelator:
    """Mint execution correlations and enforce the intrinsic binding tuple (§5/§18)."""

    def mint(
        self,
        context: GovernedAuthorityContext,
        *,
        attempt_id: str,
        external_request_id: str = "",
        execution_intent_id: str = "",
        provider: str = "",
        idempotency_key: str = "",
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> ExecutionCorrelation:
        """Mint a deterministic, replay-safe correlation from the governed context.

        Fails closed (``ValueError``) if the governed context or the attempt id is
        incomplete — a correlation can never be minted from a partial binding, so a
        wrong/blank tenant/envelope/action/attempt can never masquerade as a valid
        join key (spec §5, §7).
        """

        errors = context.binding_errors()
        if errors:
            raise ValueError(f"cannot mint correlation from incomplete context: {errors}")
        if not str(attempt_id).strip():
            raise ValueError("cannot mint correlation without an attempt_id")
        return ExecutionCorrelation(
            tenant_id=context.tenant_id,
            workflow_instance_id=context.workflow_instance_id,
            envelope_id=context.envelope_id,
            authorized_action_digest=context.authorized_action_digest,
            correlation_id=context.correlation_id,
            attempt_id=attempt_id,
            idempotency_key=idempotency_key or context.idempotency_key,
            provider=provider or context.provider,
            external_request_id=external_request_id,
            execution_intent_id=execution_intent_id,
            started_at=started_at,
            completed_at=completed_at,
        )

    def binding_mismatches(
        self, correlation: ExecutionCorrelation, observation: EffectObservation
    ) -> Tuple[str, ...]:
        """Return the intrinsic-tuple mismatches between a correlation and an effect (§18).

        Empty tuple == the observation intrinsically binds to this governed
        execution. Any mismatch is a hard rejection: wrong tenant / workflow /
        envelope / action digest / attempt, or an external-request/provider that
        contradicts a bound correlation. Evidence that does not match is discarded,
        never applied to another execution (invariants I9, §18).
        """

        if not isinstance(observation, EffectObservation):
            return ("observation is not an EffectObservation",)
        reasons: list[str] = []
        if observation.tenant_id != correlation.tenant_id:
            reasons.append("wrong tenant")
        if observation.workflow_instance_id != correlation.workflow_instance_id:
            reasons.append("wrong workflow")
        if observation.envelope_id != correlation.envelope_id:
            reasons.append("wrong envelope")
        if observation.authorized_action_digest != correlation.authorized_action_digest:
            reasons.append("wrong action digest")
        if observation.attempt_id != correlation.attempt_id:
            reasons.append("wrong attempt")
        # If the correlation is already bound to an external request, a contradicting
        # external_request_id on the observation is a rejection (old-receipt-on-new-
        # attempt / cross-request replay, spec §18/§24).
        if (
            correlation.external_request_id
            and observation.external_request_id
            and observation.external_request_id != correlation.external_request_id
        ):
            reasons.append("wrong external_request_id")
        if (
            correlation.provider
            and observation.provider
            and observation.provider != correlation.provider
        ):
            reasons.append("wrong provider")
        return tuple(reasons)
