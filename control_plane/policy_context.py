"""PolicyContext (Phase 5/8). Resolves and PINS policy + registry + contract versions
once at layer 1, immutable for the whole trace (invariant 10). Owns the authority
envelope and the data-flow approval decision. Holds no model/eligibility authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from control_plane.contracts import CONTRACTS_VERSION
from control_plane.envelope import ENVELOPE_VERSION, RequestEnvelope
from control_plane.failure_codes import Failure


@dataclass
class PolicyContext:
    """Immutable-per-trace resolved policy state. Constructed once from the envelope."""
    trace_id: str
    policy_versions: Dict[str, str]
    registry_version: str
    contracts_version: str
    envelope_version: str
    mode: str
    residency: Optional[str]
    provider_allowlist: Optional[Set[str]]
    provider_denylist: Set[str]
    permitted_actions: Set[str]
    approval_required_actions: Set[str]
    data_flow_approved: bool
    risk_class: str
    _pinned: bool = field(default=True, repr=False)

    @classmethod
    def resolve(cls, env: RequestEnvelope) -> "PolicyContext":
        # Data-flow approval: a decision-bearing/irreversible request touching non-internal
        # data must have an explicit approved flow; unknown => NOT approved (invariant 9,16).
        data_flow_approved = _resolve_data_flow(env)
        return cls(
            trace_id=env.trace_id,
            policy_versions=dict(env.policy_versions),
            registry_version=env.registry_version,
            contracts_version=CONTRACTS_VERSION,
            envelope_version=env.envelope_version,
            mode=env.mode,
            residency=env.residency_requirements,
            provider_allowlist=set(env.provider_allowlist) if env.provider_allowlist else None,
            provider_denylist=set(env.provider_denylist),
            permitted_actions=set(env.action_policy.get("permitted", [])),
            approval_required_actions=set(env.action_policy.get("require_approval", [])),
            data_flow_approved=data_flow_approved,
            risk_class=env.task_risk_class,
        )

    def check_compatibility(self, env: RequestEnvelope) -> Optional[Failure]:
        """Version pins cannot change mid-trace (invariant 10). Returns a Failure or None."""
        if env.envelope_version != self.envelope_version:
            return Failure.CONTRACT_VERSION_UNSUPPORTED
        if dict(env.policy_versions) != self.policy_versions:
            return Failure.POLICY_VERSION_MISMATCH
        if env.registry_version != self.registry_version:
            return Failure.REGISTRY_VERSION_MISMATCH
        return None

    def authority_envelope(self) -> Dict[str, Any]:
        return {"permitted_actions": set(self.permitted_actions),
                "approval_required": set(self.approval_required_actions),
                "risk_class": self.risk_class}

    def data_flow_gate(self) -> Optional[Failure]:
        return None if self.data_flow_approved else Failure.DATA_FLOW_NOT_APPROVED


def _resolve_data_flow(env: RequestEnvelope) -> bool:
    # Internal/public data on non-irreversible tasks: approved by default.
    # Confidential/regulated data, or irreversible tasks: require an explicit approved
    # provider allowlist (no implicit new external flow, invariant 16).
    sensitive = env.data_sensitivity in ("confidential", "regulated")
    irreversible = env.task_risk_class == "irreversible"
    if sensitive or irreversible:
        return bool(env.provider_allowlist)   # explicit approved providers required
    return True
