"""The fixed D-2 mapping from a capacity action to a ``CanonicalAction``, and the bounds.

Nothing here is a judgement. :func:`capacity_action_to_canonical` writes exactly the
fields the ADR fixed, off the envelope and the presented target scope, and refuses to
write anything else; :func:`capacity_bounds_violations` restates the target scope's own
two ceilings so the gate can assert them without trusting the scope's constructor ran.
"""

from __future__ import annotations

from risk_authority.domain.actions import CanonicalAction
from risk_authority.domain.envelope import RiskAuthorizationEnvelope
from ugence_cloud_scaling_authorization_contracts import ExecutionTargetScope

from .errors import ActionAdmissionContractError, ActionAdmissionExactTypeError
from .identifiers import CANONICAL_ACTION_TYPES, PURPOSE_CAPACITY_ACTION

__all__ = ["capacity_action_to_canonical", "capacity_bounds_violations"]


def capacity_action_to_canonical(
    envelope: RiskAuthorizationEnvelope, target_scope: ExecutionTargetScope
) -> CanonicalAction:
    """D-2: ``actor = envelope.subject``, ``model = envelope.model_id``,
    ``action_type = target_scope.action_type``, ``target_id = target_scope.digest()``,
    ``purpose = cloud_scaling.capacity_action``; data, destination and money fields empty."""

    if type(envelope) is not RiskAuthorizationEnvelope:
        raise ActionAdmissionExactTypeError("envelope must be exactly a RiskAuthorizationEnvelope")
    if type(target_scope) is not ExecutionTargetScope:
        raise ActionAdmissionExactTypeError("target_scope must be exactly an ExecutionTargetScope")
    if target_scope.tenant_id != envelope.tenant_id:
        raise ActionAdmissionContractError(
            "the presented target scope belongs to another tenant than the envelope")
    if target_scope.action_type not in CANONICAL_ACTION_TYPES:
        raise ActionAdmissionContractError(
            f"action_type {target_scope.action_type!r} is not a canonical capacity action")
    return CanonicalAction(
        tenant_id=envelope.tenant_id,
        actor_id=envelope.subject,
        model_id=envelope.model_id,
        action_type=target_scope.action_type,
        target_id=target_scope.digest(),
        purpose=PURPOSE_CAPACITY_ACTION,
        data_classes=(),
        destination="",
        amount_minor_units=None,
        currency="",
    )


def capacity_bounds_violations(target_scope: object) -> tuple[str, ...]:
    """The target scope's own ceilings, restated: requested magnitude and delta."""

    reasons: list[str] = []
    requested = getattr(target_scope, "requested_magnitude", None)
    before = getattr(target_scope, "magnitude_before", None)
    max_mag = getattr(target_scope, "max_permitted_magnitude", None)
    max_delta = getattr(target_scope, "max_permitted_delta", None)
    for name, value in (("requested_magnitude", requested), ("magnitude_before", before),
                        ("max_permitted_magnitude", max_mag), ("max_permitted_delta", max_delta)):
        if type(value) is not int or value < 0:
            reasons.append(f"{name} is not a non-negative int")
    if reasons:
        return tuple(reasons)
    if requested > max_mag:
        reasons.append(f"requested magnitude {requested} exceeds permitted maximum {max_mag}")
    if abs(requested - before) > max_delta:
        reasons.append(f"requested delta {abs(requested - before)} exceeds permitted delta {max_delta}")
    return tuple(reasons)
