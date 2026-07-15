"""Shared actuation model for CER V0.2. One request -> identical identity across
all runtimes; each runtime stamps its own (non-identity) provenance.

Both profiles share an EnvelopeContext (authority + state binding + policy). The
per-profile Actuation carries the identity-bearing payload and the flat tool-call
args a runtime tool would receive. Adapters reconstruct the actuation block from
the intercepted tool-call args; the native producer uses it directly. All paths
converge on the same CER identity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class EnvelopeContext:
    principal: str
    permissions: tuple
    delegator_id: str
    resource_version: str
    state_hash: str
    as_of: str
    operational: Dict[str, object]
    policy_version: str
    policy_digest: str
    correlation_id: str
    sequence_id: str = "1"
    delegation_grant: str = "*"
    live_resource_version: str = ""
    risk_tier: str = "GOVERNED"

    def envelope_sections(self) -> dict:
        sb = {
            "resource_version": self.resource_version, "state_hash": self.state_hash,
            "as_of": self.as_of, "source": "kubernetes",
            "correlation_id": self.correlation_id, "sequence_id": self.sequence_id,
            "operational": dict(self.operational),
        }
        if self.live_resource_version:
            sb["live_resource_version"] = self.live_resource_version
        return {
            "authority": {
                "principal": self.principal, "permissions": list(self.permissions),
                "delegator": {"id": self.delegator_id, "type": "HUMAN"},
                "delegation_chain": [{"grant": self.delegation_grant}],
            },
            "state_binding": sb,
            "policy_ref": {"version": self.policy_version, "digest": self.policy_digest},
        }


@dataclass(frozen=True)
class ScaleActuation:
    cluster: str
    namespace: str
    deployment: str
    from_replicas: int
    to_replicas: int
    reversibility: str = "REVERSIBLE"
    PROFILE = "kubernetes.scale.v1"

    def tool_args(self) -> dict:
        return {"cluster": self.cluster, "namespace": self.namespace,
                "deployment": self.deployment, "from_replicas": self.from_replicas,
                "replicas": self.to_replicas, "reversibility": self.reversibility}

    def actuation_block(self) -> dict:
        return {
            "operation": "DEPLOY",
            "target": {"cluster": self.cluster, "namespace": self.namespace,
                       "deployment": self.deployment},
            "arguments": {"replicas": str(self.to_replicas)},
            "requested_state_transition": {
                "replicas": {"from": str(self.from_replicas), "to": str(self.to_replicas)}},
            "reversibility": self.reversibility,
        }


@dataclass(frozen=True)
class RolloutActuation:
    cluster: str
    namespace: str
    deployment: str
    image_digest: str
    current_manifest_digest: str
    rollout_strategy: str = "RollingUpdate"
    max_surge: int = 1
    max_unavailable: int = 0
    timeout_s: int = 600
    rollback_ref: str = ""
    reversibility: str = "REVERSIBLE_WITH_COST"
    PROFILE = "kubernetes.rollout.v1"

    def tool_args(self) -> dict:
        return {"cluster": self.cluster, "namespace": self.namespace,
                "deployment": self.deployment, "image_digest": self.image_digest,
                "current_manifest_digest": self.current_manifest_digest,
                "rollout_strategy": self.rollout_strategy, "max_surge": self.max_surge,
                "max_unavailable": self.max_unavailable, "timeout_s": self.timeout_s,
                "rollback_ref": self.rollback_ref, "reversibility": self.reversibility}

    def actuation_block(self) -> dict:
        b = {
            "operation": "DEPLOY",
            "target": {"cluster": self.cluster, "namespace": self.namespace,
                       "deployment": self.deployment},
            "image_digest": self.image_digest,
            "current_manifest_digest": self.current_manifest_digest,
            "rollout_strategy": self.rollout_strategy,
            "max_surge": str(self.max_surge), "max_unavailable": str(self.max_unavailable),
            "timeout_s": str(self.timeout_s),
            "reversibility": self.reversibility,
        }
        if self.rollback_ref:
            b["rollback_ref"] = self.rollback_ref
        return b


def actuation_block_from_tool_args(profile: str, args: dict) -> dict:
    """Rebuild the CER actuation block from intercepted tool-call args (adapters)."""
    if profile == "kubernetes.scale.v1":
        return ScaleActuation(
            cluster=args["cluster"], namespace=args["namespace"],
            deployment=args["deployment"], from_replicas=int(args["from_replicas"]),
            to_replicas=int(args["replicas"]),
            reversibility=args.get("reversibility", "REVERSIBLE")).actuation_block()
    if profile == "kubernetes.rollout.v1":
        return RolloutActuation(
            cluster=args["cluster"], namespace=args["namespace"],
            deployment=args["deployment"], image_digest=args["image_digest"],
            current_manifest_digest=args["current_manifest_digest"],
            rollout_strategy=args["rollout_strategy"], max_surge=int(args["max_surge"]),
            max_unavailable=int(args["max_unavailable"]), timeout_s=int(args["timeout_s"]),
            rollback_ref=args.get("rollback_ref", ""),
            reversibility=args.get("reversibility", "REVERSIBLE_WITH_COST")).actuation_block()
    raise ValueError(f"unknown profile {profile!r}")


def assemble_cer(profile: str, ctx: EnvelopeContext, actuation_block: dict,
                 provenance: dict) -> dict:
    cer = {
        "cer_version": "0.2", "profile": profile, "risk_tier": ctx.risk_tier,
        "actuation": actuation_block, "provenance": provenance,
    }
    cer.update(ctx.envelope_sections())
    return cer
