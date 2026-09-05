"""Least-privilege role derivation: a pure function of the target scope (ADR 5X, D-3).

One operation from ``action_type``; one resource from account, compute group, resource
class, namespace and region; the magnitude ceilings as the only parameters. ``no_change``
derives nothing: an action that changes nothing needs no credential. A broker may narrow a
derived role and never widen it; :func:`role_widening` says where a granted role does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ugence_cloud_scaling_authorization_contracts import CANONICAL_ACTION_TYPES, ExecutionTargetScope

from .errors import CredentialBrokerContractError, CredentialBrokerExactTypeError

__all__ = ["RoleStatement", "derive_least_privilege_role", "role_widening", "NO_CREDENTIAL_ACTION_TYPES"]

#: Action types that derive no credential at all (D-3).
NO_CREDENTIAL_ACTION_TYPES: frozenset = frozenset({"no_change"})


@dataclass(frozen=True)
class RoleStatement:
    """Exactly what a credential may do, and nowhere else. Canonicalizable and digestible."""

    tenant_id: str
    operation: str
    account_id: str
    compute_group: Optional[str]
    resource_class: Optional[str]
    namespace: Optional[str]
    region: Optional[str]
    max_magnitude: int
    max_delta: int

    def __post_init__(self) -> None:
        for name in ("tenant_id", "operation", "account_id"):
            value = getattr(self, name)
            if type(value) is not str or not value.strip():
                raise CredentialBrokerContractError(f"RoleStatement.{name} must be a non-blank str")
        for name in ("compute_group", "resource_class", "namespace", "region"):
            value = getattr(self, name)
            if value is not None and (type(value) is not str or not value.strip()):
                raise CredentialBrokerContractError(f"RoleStatement.{name} must be None or a non-blank str")
        for name in ("max_magnitude", "max_delta"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise CredentialBrokerContractError(f"RoleStatement.{name} must be a non-negative int")


def derive_least_privilege_role(target_scope: ExecutionTargetScope) -> Optional[RoleStatement]:
    """The one role the target scope permits, or ``None`` for an action that changes nothing."""

    if type(target_scope) is not ExecutionTargetScope:
        raise CredentialBrokerExactTypeError("target_scope must be exactly an ExecutionTargetScope")
    if target_scope.action_type not in CANONICAL_ACTION_TYPES:
        raise CredentialBrokerContractError(
            f"action_type {target_scope.action_type!r} is not a canonical capacity action")
    if target_scope.action_type in NO_CREDENTIAL_ACTION_TYPES:
        return None
    return RoleStatement(
        tenant_id=target_scope.tenant_id,
        operation=target_scope.action_type,
        account_id=target_scope.account_id,
        compute_group=target_scope.compute_group,
        resource_class=target_scope.resource_class,
        namespace=target_scope.namespace,
        region=target_scope.region,
        max_magnitude=target_scope.max_permitted_magnitude,
        max_delta=target_scope.max_permitted_delta,
    )


def role_widening(granted: object, derived: RoleStatement) -> tuple[str, ...]:
    """Every way ``granted`` reaches beyond ``derived``. Empty means it narrows or equals."""

    if type(granted) is not RoleStatement:
        return ("granted role is not a RoleStatement",)
    reasons: list[str] = []
    for name in ("tenant_id", "operation", "account_id"):
        if getattr(granted, name) != getattr(derived, name):
            reasons.append(f"granted role changes {name}")
    for name in ("compute_group", "resource_class", "namespace", "region"):
        d, g = getattr(derived, name), getattr(granted, name)
        # A derived None is "any"; a granted value narrows it. A derived value must be kept.
        if d is not None and g != d:
            reasons.append(f"granted role widens {name}")
    if granted.max_magnitude > derived.max_magnitude:
        reasons.append("granted role widens max_magnitude")
    if granted.max_delta > derived.max_delta:
        reasons.append("granted role widens max_delta")
    return tuple(reasons)
