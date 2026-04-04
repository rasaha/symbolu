"""
Policy Engine Adapter — Governance-Safe Agent Policy Signal
=============================================================

Phase S4: Bridges the ``PolicyEngine`` from
``agentic.safety.governance_patterns.policy_engine`` into the
governance authorization path as a deterministic allow/deny signal.

The policy engine evaluates agent actions against configurable
constraints:
    1. Action-type allowlists/denylists per agent
    2. Blackout windows (time-based action blocking)
    3. Rate limits (max actions per sliding window)

Input sourcing:
    This adapter sources inputs directly from the AuthorizationRequest:
    - agent_id ← request.actor_id (always present)
    - action_type ← request.action_type (always present)

    No new upstream dependencies or signal resolution needed.

Design:
    Follows the signal adapter pattern but with a key difference:
    policy violations produce HARD DENY, not just confidence penalty.
    This is consistent with the existing forbidden-capability check
    which also produces hard denies.

    - Frozen Resolution dataclass (immutable, serializable)
    - ``resolve_policy_check()`` pure function (deterministic, fail-safe)
    - ``available`` / ``source_detail`` / ``reason_codes`` provenance

Fail-safe semantics:
    Unlike other adapters which are fail-closed (failure → penalty),
    the policy engine is fail-SAFE: if no PolicyEngine is configured
    or if computation fails, the result is ALLOWED with no violations.
    This is intentional — absence of explicit policy should not block
    actions. Explicit deny rules are opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from agentic.safety.governance_patterns.policy_engine import (
    PolicyCheckResult,
    PolicyConfig,
    PolicyEngine,
)


# =========================================================================
# Governance-facing contract
# =========================================================================

@dataclass(frozen=True)
class PolicyResolution:
    """Governance-safe view of the policy engine evaluation.

    Field categories
    ----------------

    BEHAVIOR-AFFECTING:
        allowed             Whether the action is permitted by policy.
        hard_deny           Whether governance should hard-deny this action.
        violations          Tuple of policy violation reason strings.

    AUDIT METADATA:
        agent_id            Agent that was evaluated.
        action_type         Action that was evaluated.
        reason_codes        Machine-readable governance codes.
        available           Whether policy check was performed.
        source_detail       Human-readable provenance description.

    Note: This is named PolicyResolution (not PolicyCheckResolution)
    to match the adapter naming convention. It is distinct from
    ``agentic.agentic_framework.policy_bundle.PolicyResolution``
    which represents resolved policy bundles, not check results.
    """

    # --- Behavior-affecting ---
    allowed: bool
    hard_deny: bool
    violations: Tuple[str, ...]

    # --- Audit metadata ---
    agent_id: str
    action_type: str
    reason_codes: Tuple[str, ...]
    available: bool
    source_detail: str

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to audit-safe dictionary."""
        return {
            "allowed": self.allowed,
            "hard_deny": self.hard_deny,
            "violations": list(self.violations),
            "agent_id": self.agent_id,
            "action_type": self.action_type,
            "reason_codes": list(self.reason_codes),
            "available": self.available,
            "source_detail": self.source_detail,
        }


# =========================================================================
# Empty/fallback resolution
# =========================================================================

def _no_policy_resolution(
    agent_id: str = "",
    action_type: str = "",
    detail: str = "no policy engine configured",
) -> "AgentPolicyResolution":
    """Return a safe no-policy resolution (fail-safe: allowed)."""
    return AgentPolicyResolution(
        allowed=True,
        hard_deny=False,
        violations=(),
        agent_id=agent_id,
        action_type=action_type,
        reason_codes=(),
        available=False,
        source_detail=detail,
    )


# Use a distinct name to avoid collision with policy_bundle.PolicyResolution
AgentPolicyResolution = PolicyResolution


# =========================================================================
# Main resolution function
# =========================================================================

def resolve_policy_check(
    *,
    engine: Optional[PolicyEngine] = None,
    agent_id: str,
    action_type: str,
    current_time: Optional[float] = None,
) -> AgentPolicyResolution:
    """Resolve agent policy check for governance use.

    Args:
        engine: PolicyEngine instance (None if no policy configured).
        agent_id: Agent/actor identifier from the request.
        action_type: Action type being proposed.
        current_time: Override for current time (testing).

    Returns:
        AgentPolicyResolution with allow/deny decision.

    Fail-safe semantics:
        If engine is None → allowed, available=False.
        If computation fails → allowed, available=False.
        Absence of policy never blocks actions.
    """
    if engine is None:
        return _no_policy_resolution(agent_id, action_type)

    try:
        result: PolicyCheckResult = engine.check(
            agent_id,
            action_type,
            current_time=current_time,
        )

        codes = []
        if not result.allowed:
            codes.append("AGENT_POLICY_DENY")
        if result.violations:
            codes.append("AGENT_POLICY_VIOLATION")

        detail_parts = [f"agent={agent_id}", f"action={action_type}"]
        if result.violations:
            detail_parts.append(f"violations={len(result.violations)}")
        source_detail = f"PolicyEngine ({', '.join(detail_parts)})"

        return AgentPolicyResolution(
            allowed=result.allowed,
            hard_deny=not result.allowed,
            violations=result.violations,
            agent_id=agent_id,
            action_type=action_type,
            reason_codes=tuple(codes),
            available=True,
            source_detail=source_detail,
        )

    except Exception:
        return _no_policy_resolution(
            agent_id, action_type,
            detail="policy engine check failed",
        )
