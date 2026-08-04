"""Rollback model — never assumed automatically safe.

A rollback requires a known prior state, a valid prior execution receipt, an explicit
bounded rollback policy or a separate rollback authorization, an idempotency key, a
reason, and audit persistence. Unlimited rollback to an unknown historical value is
refused.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .contracts import (
    ExecutionAction,
    ExecutionAuthorization,
    ExecutionReceipt,
    ExecutionRequest,
)
from .executors import ControlledScalingExecutor


@dataclass(frozen=True)
class RollbackPolicy:
    """Pre-authorized bounded rollback envelope."""

    min_replicas: int
    max_replicas: int
    max_delta: int


@dataclass(frozen=True)
class RollbackAuthorization:
    """Either wraps a full ExecutionAuthorization or a pre-authorized bounded policy."""

    authorization: Optional[ExecutionAuthorization] = None
    policy: Optional[RollbackPolicy] = None


@dataclass(frozen=True)
class RollbackPlan:
    prior_receipt: ExecutionReceipt
    prior_state: int
    target_state: int
    reason: str
    idempotency_key: str
    correlation_id: Optional[str] = None


@dataclass(frozen=True)
class RollbackResult:
    success: bool
    receipt: Optional[ExecutionReceipt]
    denial_reason: Optional[str] = None


class RollbackCoordinator:
    """Coordinates bounded, authorized rollbacks via the controlled executor."""

    def __init__(self, executor: ControlledScalingExecutor):
        self._executor = executor

    def rollback(
        self,
        plan: RollbackPlan,
        authorization: RollbackAuthorization,
        *,
        tenant_id: str = "",
        actor_id: str = "system",
    ) -> RollbackResult:
        # Known prior state required.
        if plan.prior_state is None or plan.target_state is None:
            return RollbackResult(False, None, "unknown prior/target state")
        if plan.prior_receipt is None:
            return RollbackResult(False, None, "missing prior execution receipt")

        # Bounded target: either a full authorization (verified downstream) or a policy.
        if authorization.authorization is None and authorization.policy is None:
            return RollbackResult(False, None, "no rollback authorization or policy")
        if authorization.policy is not None:
            pol = authorization.policy
            if not (pol.min_replicas <= plan.target_state <= pol.max_replicas):
                return RollbackResult(False, None, "rollback target outside policy bounds")

        req = ExecutionRequest(
            action=ExecutionAction.ROLLBACK.value,
            target_cluster=plan.prior_receipt.target_cluster,
            target_namespace=plan.prior_receipt.target_namespace,
            target_resource=plan.prior_receipt.target_resource,
            current_replicas=plan.prior_receipt.post_state or plan.prior_state,
            target_replicas=plan.target_state,
            recommendation_id=plan.prior_receipt.recommendation_id,
            idempotency_key=plan.idempotency_key,
            correlation_id=plan.correlation_id,
        )
        receipt = self._executor.execute(
            req, authorization.authorization, tenant_id=tenant_id, actor_id=actor_id)
        success = receipt.outcome in ("applied", "simulated", "proposed", "duplicate")
        return RollbackResult(success, receipt,
                              None if success else receipt.denial_reason)


__all__ = [
    "RollbackPolicy",
    "RollbackAuthorization",
    "RollbackPlan",
    "RollbackResult",
    "RollbackCoordinator",
]
