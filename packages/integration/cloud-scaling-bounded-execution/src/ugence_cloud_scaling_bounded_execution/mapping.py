"""Pure projections between the ladder's artifacts and the operations executor's shapes.

Nothing here is a judgement. The target scope names a place; the operations executor
addresses a place as cluster, namespace and resource; a capacity action type names an
operation the executor either has or does not. Instants are aware ``datetime`` on the
ladder and epoch floats in the executor, converted here in one direction only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ugence_cloud_scaling_authorization_contracts import ExecutionTargetScope
from ugence_cloud_scaling_operations.contracts import ExecutionAction, ExecutionOutcome
from ugence_decision_authority.execution.status import BusinessOutcome, Finality
from ugence_governance_contracts.api import ExecutionBusinessOutcome

from .errors import BoundedExecutionContractError, BoundedExecutionExactTypeError
from .identifiers import DISPATCHABLE_ACTION_TYPES

__all__ = ["OpsTarget", "ops_target_for", "ops_action_for", "to_epoch", "business_outcome_for",
           "ledger_outcome_for", "finality_for"]


@dataclass(frozen=True)
class OpsTarget:
    """The executor's address for a target scope: cluster, namespace, resource."""

    cluster: str
    namespace: str
    resource: str


def ops_target_for(target_scope: ExecutionTargetScope) -> OpsTarget:
    """Cluster is the compute group, namespace the scope's namespace or, for targets that have
    no namespace concept, the account partition; resource is the resource class. A scope that
    names no compute group or resource class is not addressable and is refused."""

    if type(target_scope) is not ExecutionTargetScope:
        raise BoundedExecutionExactTypeError("target_scope must be exactly an ExecutionTargetScope")
    cluster = target_scope.compute_group
    resource = target_scope.resource_class
    if not cluster or not resource:
        raise BoundedExecutionContractError(
            "target scope names no compute group or resource class; the executor cannot address it")
    namespace = target_scope.namespace or target_scope.account_id
    return OpsTarget(cluster=cluster, namespace=namespace, resource=resource)


def ops_action_for(action_type: str) -> str:
    if action_type not in DISPATCHABLE_ACTION_TYPES:
        raise BoundedExecutionContractError(
            f"action_type {action_type!r} has no bounded single-target operation in the executor")
    return ExecutionAction.SCALE.value


def to_epoch(instant: datetime) -> float:
    if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise BoundedExecutionContractError("instants must be timezone-aware")
    return instant.astimezone(timezone.utc).timestamp()


_BUSINESS = {
    ExecutionOutcome.APPLIED.value: BusinessOutcome.SUCCEEDED,
    ExecutionOutcome.SIMULATED.value: BusinessOutcome.SUCCEEDED,
    ExecutionOutcome.DUPLICATE.value: BusinessOutcome.DUPLICATE,
    ExecutionOutcome.DENIED.value: BusinessOutcome.REJECTED,
    ExecutionOutcome.FAILED.value: BusinessOutcome.FAILED,
    ExecutionOutcome.PROPOSED.value: BusinessOutcome.UNKNOWN,
    ExecutionOutcome.SHADOWED.value: BusinessOutcome.UNKNOWN,
}
_LEDGER = {
    BusinessOutcome.SUCCEEDED: ExecutionBusinessOutcome.SUCCEEDED,
    BusinessOutcome.DUPLICATE: ExecutionBusinessOutcome.DUPLICATE,
    BusinessOutcome.REJECTED: ExecutionBusinessOutcome.REJECTED,
    BusinessOutcome.FAILED: ExecutionBusinessOutcome.FAILED,
    BusinessOutcome.UNKNOWN: ExecutionBusinessOutcome.UNKNOWN,
}


def business_outcome_for(ops_outcome: str) -> BusinessOutcome:
    """The executor's outcome as the effect vocabulary RA-8 reads. Unknown words are UNKNOWN."""

    return _BUSINESS.get(ops_outcome, BusinessOutcome.UNKNOWN)


def ledger_outcome_for(outcome: BusinessOutcome) -> ExecutionBusinessOutcome:
    return _LEDGER.get(outcome, ExecutionBusinessOutcome.UNKNOWN)


def finality_for(ops_outcome: str, applied_mode: bool) -> Finality:
    """An applied, simulated, failed, denied or duplicate outcome is final for its mode; a
    proposal or a shadow read decided nothing."""

    if ops_outcome in (ExecutionOutcome.PROPOSED.value, ExecutionOutcome.SHADOWED.value):
        return Finality.UNKNOWN
    return Finality.FINAL if applied_mode or ops_outcome != ExecutionOutcome.APPLIED.value else Finality.UNKNOWN


def optional_int(value: Optional[int]) -> Optional[int]:
    return None if value is None else int(value)
