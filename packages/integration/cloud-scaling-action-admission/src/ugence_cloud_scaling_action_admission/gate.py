"""``CapacityActionGate``: Risk Authority's ``ActionGatePort`` for capacity actions (D-2, D-4).

Built per act with the artifacts the caller presents — the ``ExecutionTargetScope`` and the
candidate digest — and asked by the ``ActionAdmissionSeam`` to rule on one
``CanonicalAction`` against one envelope the kernel has already verified. It therefore
never checks a signature, a window, revocation or an epoch: D-4 keeps those in the kernel
and a port that repeated them would only pretend to. What it checks is that the presented
action is the action the envelope was issued for:

1. the envelope binds a target scope, and that binding equals ``target_scope.digest()``
   re-derived here **and** the action's ``target_id``;
2. the envelope binds a candidate, and that binding equals the presented candidate digest;
3. the action type is one of the four canonical types and equals the target scope's;
4. the action names the envelope's subject and model, and the runtime identity agrees;
5. the action's purpose is the capacity purpose and inside the envelope's scope;
6. the action carries no data classes, destination or money — the D-2 mapping wrote none;
7. the target scope's magnitude and delta ceilings hold;
8. every condition the envelope requires is satisfied.

It answers ``AUTHORIZED`` or ``DENIED`` and nothing else. **No clock.**
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from risk_authority.crypto.keys import KeyRing
from risk_authority.domain.actions import ActionAuthorization, CanonicalAction
from risk_authority.domain.enums import ActionGateDecision
from risk_authority.domain.envelope import RiskAuthorizationEnvelope
from risk_authority.integrations.actiongate import RuntimeIdentity
from risk_authority.services.revocation import RevocationState
from ugence_cloud_scaling_authorization_contracts import ExecutionTargetScope, is_canonical_digest
from ugence_cloud_scaling_envelope_issuance import bare_digest

from .errors import ActionAdmissionExactTypeError
from .identifiers import (
    ADMISSION_PROFILE,
    ADMISSION_PROFILE_VERSION,
    BINDING_KIND_AUTHORIZATION_CANDIDATE,
    BINDING_KIND_TARGET_SCOPE,
    CANONICAL_ACTION_TYPES,
    PURPOSE_CAPACITY_ACTION,
)
from .mapping import capacity_bounds_violations

__all__ = ["CapacityActionGate"]


class CapacityActionGate:
    """One act's gate over the artifacts the caller presented. Production-authoritative."""

    is_production_authoritative = True

    def __init__(self, *, target_scope: ExecutionTargetScope, candidate_digest: str) -> None:
        if type(target_scope) is not ExecutionTargetScope:
            raise ActionAdmissionExactTypeError("target_scope must be exactly an ExecutionTargetScope")
        if not is_canonical_digest(candidate_digest):
            raise ActionAdmissionExactTypeError("candidate_digest must be a sha256:-prefixed digest")
        self._target_scope = target_scope
        self._candidate_digest = candidate_digest

    @property
    def target_scope(self) -> ExecutionTargetScope:
        return self._target_scope

    @property
    def candidate_digest(self) -> str:
        return self._candidate_digest

    def authorize(
        self,
        *,
        authorization_id: str,
        envelope: RiskAuthorizationEnvelope,
        action: CanonicalAction,
        identity: RuntimeIdentity,
        key_ring: KeyRing,
        revocation_state: RevocationState,
        now: datetime,
        satisfied_conditions: frozenset[str] = frozenset(),
        trajectory_version: Optional[int] = None,
    ) -> ActionAuthorization:
        reasons: list[str] = []
        scope = self._target_scope

        # 1. Target scope binding, re-derived here, and the action's own target id.
        bound_scope = envelope.bindings.binding_for(BINDING_KIND_TARGET_SCOPE)
        presented = bare_digest(scope.digest())
        if bound_scope is None:
            reasons.append("envelope binds no execution target scope")
        elif bound_scope.digest != presented:
            reasons.append("presented target scope is not the one the envelope binds")
        if not is_canonical_digest(action.target_id) or bare_digest(action.target_id) != presented:
            reasons.append("action target_id is not the presented target scope digest")
        # 2. Candidate binding.
        bound_candidate = envelope.bindings.binding_for(BINDING_KIND_AUTHORIZATION_CANDIDATE)
        if bound_candidate is None:
            reasons.append("envelope binds no authorization candidate")
        elif bound_candidate.digest != bare_digest(self._candidate_digest):
            reasons.append("presented candidate digest is not the one the envelope binds")
        # 3. Action type.
        if action.action_type not in CANONICAL_ACTION_TYPES:
            reasons.append(f"action_type {action.action_type!r} is not a canonical capacity action")
        if action.action_type != scope.action_type:
            reasons.append("action_type does not equal the target scope's action_type")
        # 4. Identity.
        if action.tenant_id != envelope.tenant_id or scope.tenant_id != envelope.tenant_id:
            reasons.append("tenant does not match the envelope")
        if action.tenant_id != identity.tenant_id:
            reasons.append("action tenant does not match runtime identity")
        if action.actor_id != envelope.subject:
            reasons.append("actor does not match envelope subject")
        if action.actor_id != identity.actor_id:
            reasons.append("actor does not match runtime identity")
        if action.model_id != envelope.model_id:
            reasons.append("model does not match envelope binding")
        if action.model_id != identity.model_id:
            reasons.append("model does not match runtime identity")
        # 5. Purpose.
        if action.purpose != PURPOSE_CAPACITY_ACTION:
            reasons.append(f"purpose {action.purpose!r} is not the capacity purpose")
        if action.purpose not in envelope.scope.purposes:
            reasons.append(f"purpose {action.purpose!r} outside envelope scope")
        # 6. The D-2 mapping writes no data, destination or money.
        if action.data_classes or action.destination or action.amount_minor_units is not None \
                or action.currency:
            reasons.append("a capacity action carries no data classes, destination or money")
        # 7. Magnitude ceilings.
        reasons.extend(capacity_bounds_violations(scope))
        # 8. Conditions.
        missing = set(envelope.conditions.required_conditions) - set(satisfied_conditions)
        if missing:
            reasons.append(f"unsatisfied conditions {sorted(missing)}")

        decision = ActionGateDecision.AUTHORIZED if not reasons else ActionGateDecision.DENIED
        if reasons:
            reasons.append(f"profile={ADMISSION_PROFILE}/{ADMISSION_PROFILE_VERSION}")
        return ActionAuthorization(
            authorization_id=authorization_id,
            envelope_id=envelope.envelope_id,
            action_digest=action.digest,
            decision=decision,
            tenant_id=action.tenant_id,
            reason_codes=tuple(reasons),
            trajectory_version=trajectory_version,
            expires_at=envelope.expires_at,
        )
