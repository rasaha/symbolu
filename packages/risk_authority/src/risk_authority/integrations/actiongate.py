"""ActionGate — canonical-action matching against a signed envelope (spec §15).

This is the RA-4 enforcement seam and the product thesis in code: an agent can
physically perform *only* what the signed envelope authorizes. The matching is
bounded and deterministic — no LLM call, no regulatory-text interpretation, no
fuzzy scoring (user brief §12). It composes the offline envelope verifier
(signature/time/revocation) with exact scope matching over the canonical action.

``ActionGatePort`` is the contract; ``ReferenceActionGate`` is the in-package
reference. The existing ``ugence_actiongate_provider`` can be adapted onto this
port later without ``risk_authority`` importing it — integration through a
contract, not a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from ..crypto.keys import KeyRing
from ..domain.actions import ActionAuthorization, CanonicalAction
from ..domain.enums import ActionGateDecision
from ..domain.envelope import RiskAuthorizationEnvelope
from ..services.envelope_verifier import EnvelopeVerifier
from ..services.revocation import RevocationState

__all__ = ["RuntimeIdentity", "ActionGatePort", "ReferenceActionGate"]


@dataclass(frozen=True)
class RuntimeIdentity:
    """The authenticated runtime identity presenting an action (spec §15)."""

    tenant_id: str
    actor_id: str
    model_id: str
    session_id: str


@runtime_checkable
class ActionGatePort(Protocol):
    """The contract runtimes call to authorize an exact action."""

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
    ) -> ActionAuthorization: ...


class ReferenceActionGate:
    """Deterministic reference ActionGate. Never production (Phase 5C, D-4)."""

    is_production_authoritative = False

    def __init__(self, verifier: Optional[EnvelopeVerifier] = None) -> None:
        self._verifier = verifier or EnvelopeVerifier()

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
        scope = envelope.scope

        # 1. Envelope-level verification (signature, time window, tenant/session
        #    binding, revocation, authority epoch). Bind expectations to the
        #    presenting runtime identity so a replayed envelope in another
        #    tenant/session fails here.
        verification = self._verifier.verify(
            envelope=envelope,
            key_ring=key_ring,
            revocation_state=revocation_state,
            now=now,
            expected_tenant=identity.tenant_id,
            expected_session=identity.session_id,
        )
        if not verification.valid:
            reasons.extend(verification.reasons)

        # 2. Identity binding: the canonical action, the runtime identity and the
        #    envelope subject/model/tenant must all agree.
        if action.tenant_id != envelope.tenant_id:
            reasons.append("action tenant does not match envelope")
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

        # NOTE (documented follow-up, F-D): the scope also carries `jurisdictions`,
        # `max_autonomy_level` and per-resource constraints, but the canonical
        # action has no field to match them against, so they bound *issuance*
        # (monotonicity) without being enforced here. Closing this requires
        # extending CanonicalAction and is tracked separately — not done in the
        # authority-spine slice.

        # 3. Purpose.
        if action.purpose not in scope.purposes:
            reasons.append(f"purpose {action.purpose!r} outside envelope scope")

        # 4. Tool / action type (allow set and deny set).
        if action.action_type in scope.tools_deny:
            reasons.append(f"tool {action.action_type!r} explicitly denied")
        elif action.action_type not in scope.tools_allow:
            reasons.append(f"tool {action.action_type!r} not in allow set")

        # 5. Data classes.
        denied_data = set(action.data_classes) & set(scope.data_deny)
        if denied_data:
            reasons.append(f"prohibited data classes {sorted(denied_data)}")
        extra_data = set(action.data_classes) - set(scope.data_allow)
        if extra_data:
            reasons.append(f"data classes {sorted(extra_data)} not authorized")

        # 6. Destination.
        if action.destination and action.destination not in scope.destinations:
            reasons.append(f"destination {action.destination!r} outside scope")

        # 7. Numeric bound (amount).
        if action.amount_minor_units is not None:
            limit = scope.max_transaction_minor_units
            if limit is not None and action.amount_minor_units > limit:
                reasons.append(
                    f"amount {action.amount_minor_units} exceeds limit {limit}"
                )

        # 8. Conditions.
        missing_conditions = set(envelope.conditions.required_conditions) - set(
            satisfied_conditions
        )
        if missing_conditions:
            reasons.append(f"unsatisfied conditions {sorted(missing_conditions)}")
        threshold = envelope.conditions.human_approval_required_above_minor_units
        if (
            threshold is not None
            and action.amount_minor_units is not None
            and action.amount_minor_units > threshold
            and "HUMAN_APPROVAL" not in satisfied_conditions
        ):
            reasons.append(
                f"human approval required above {threshold} minor units"
            )

        decision = (
            ActionGateDecision.AUTHORIZED
            if not reasons
            else ActionGateDecision.DENIED
        )
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
