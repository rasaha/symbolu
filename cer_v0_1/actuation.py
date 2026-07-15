"""The shared ActuationRequest — the *same exact* actuation, on the *same* tool
surface, handed independently to both runtimes.

The experiment tests "same actuation, not same intent" (milestone §5). So the
identity-bearing facts (target, replicas, authority, observed state, policy) come
from ONE shared request object; each runtime independently *normalizes* it into a
CER through its own code path and stamps its own (differing) provenance. The
independence being tested is in the derivation path, not in inventing different
target values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class ActuationRequest:
    # target (shared tool surface: kubernetes.scale)
    cluster: str
    namespace: str
    deployment: str
    from_replicas: int
    to_replicas: int
    # authority
    principal: str
    permissions: tuple
    delegator_id: str
    # external-state binding (observed, shared)
    resource_version: str
    state_hash: str
    as_of: str
    operational: Dict[str, object]
    # policy
    policy_version: str
    policy_digest: str
    # correlation of the one logical action across runtimes
    correlation_id: str
    sequence_id: str = "1"
    # consequence class — POLICY/TOOL-PROFILE controlled, never model-asserted
    risk_tier: str = "GOVERNED"
    operation: str = "DEPLOY"
    reversibility: str = "REVERSIBLE"
    # optional: evidence the enterprise/runtime attaches (scrutiny-only)
    attach_evidence: bool = False
    rollback_ref: str = ""
    extras: Dict[str, object] = field(default_factory=dict)

    def identity_block(self) -> dict:
        """The identity-bearing CER fields — identical for any runtime."""
        return {
            "operation": self.operation,
            "actuation_interface": "kubernetes.scale",
            "target": {"cluster": self.cluster, "namespace": self.namespace,
                       "deployment": self.deployment},
            "arguments": {"replicas": str(self.to_replicas)},
            "requested_state_transition": {
                "replicas": {"from": str(self.from_replicas), "to": str(self.to_replicas)}},
            "authority": {
                "principal": self.principal,
                "permissions": list(self.permissions),
                "delegator": {"id": self.delegator_id, "type": "HUMAN"},
                "delegation_chain": [{"grant": "*"}],
            },
            "external_state_binding": {
                "resource_version": self.resource_version,
                "state_hash": self.state_hash,
                "as_of": self.as_of,
                "source": "kubernetes",
                "correlation_id": self.correlation_id,
                "sequence_id": self.sequence_id,
                "rollback_ref": self.rollback_ref,
                "operational": dict(self.operational),
            },
            "policy_ref": {"version": self.policy_version, "digest": self.policy_digest},
            "reversibility": self.reversibility,
        }
