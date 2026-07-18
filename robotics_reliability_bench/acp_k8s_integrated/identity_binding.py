"""Kubernetes operation identity binding (V2.1 §4).

Proves that the ActionGate authorization and the ACP operational-safety
evaluation refer to the **same exact Kubernetes action** — same target,
operation, manifest/patch digest, resourceVersion, cluster, namespace, and
proposed state transition — WITHOUT merging the two decision schemas.

`KubernetesOperation` is the single source of truth. From it we build both the
ActionGate envelope (via `actiongate_runner`) and the ACP `CloudWorldState` +
`CloudActionCandidate`. `bind()` then independently re-derives the shared facts
from each layer's own artifacts and fails closed (`COMPOSITION_IDENTITY_MISMATCH`)
on any disagreement.

The binding anchor between the layers is the pair
``(manifest_digest, current_state_hash)``: both are computed with the **real**
ActionGate hashing conventions, so ACP recomputing them from its candidate/world
must reproduce ActionGate's values byte-for-byte, or the two are not the same
operation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, Tuple

from symbolu_robotics.autonomous_control_plane.cloud import (
    CloudActionCandidate,
    CloudOperation,
    CloudWorldState,
)
from robotics_reliability_bench.acp_k8s_integrated.actiongate_runner import (
    ActionGateResult,
    build_manifest,
    current_state_hash,
    manifest_digest,
)

# Kubernetes verb -> ACP CloudOperation.
_CLOUD_OP = {
    "SCALE": CloudOperation.SCALE,
    "ROLLOUT": CloudOperation.ROLLOUT,
    "DELETE": CloudOperation.DELETE,
}


@dataclass(frozen=True)
class KubernetesOperation:
    """One proposed Kubernetes Deployment operation — the single source of truth.

    Authorization-relevant fields feed ActionGate; operational fields feed ACP;
    the target/operation/manifest/resourceVersion are shared by both.
    """
    cluster: str
    namespace: str
    deployment: str
    k8s_verb: str                       # SCALE / ROLLOUT / DELETE
    current_replicas: int
    desired_replicas: int
    resource_version: str
    generation: int
    # ACP operational state (from fixture / authored):
    available_replicas: int
    readiness_plasticity: float
    seconds_since_last_action: float
    dependency_healthy: bool
    freeze_active: bool
    active_rollback_watches: int
    rollback_ref: str = ""
    compliant_manifest: bool = True
    provenance: str = ""

    @property
    def manifest(self) -> dict:
        replicas = 0 if self.k8s_verb == "DELETE" else self.desired_replicas
        return build_manifest(self.namespace, self.deployment, replicas,
                              compliant=self.compliant_manifest)

    @property
    def manifest_digest(self) -> str:
        return manifest_digest(self.manifest)


def _digest(tag: str, obj) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return tag + ":" + hashlib.sha256(payload).hexdigest()


def shared_operation_digest(op: KubernetesOperation, *,
                            manifest_digest_override: Optional[str] = None) -> str:
    """Domain-separated digest over the operation facts both layers share."""
    return _digest("k8sop", {
        "cluster": op.cluster, "namespace": op.namespace,
        "deployment": op.deployment, "kind": "Deployment",
        "verb": op.k8s_verb,
        "manifest_digest": manifest_digest_override or op.manifest_digest,
        "current_replicas": op.current_replicas,
        "desired_replicas": op.desired_replicas,
    })


def shared_state_version(op: KubernetesOperation) -> str:
    """Domain-separated digest over the shared observation/state version."""
    return _digest("k8sstate", {
        "cluster": op.cluster, "namespace": op.namespace,
        "deployment": op.deployment, "resource_version": op.resource_version,
        "generation": op.generation,
    })


def build_cloud_world(op: KubernetesOperation) -> CloudWorldState:
    return CloudWorldState(
        cluster=op.cluster, namespace=op.namespace, deployment=op.deployment,
        resource_version=op.resource_version, generation=op.generation,
        desired_replicas=op.desired_replicas, current_replicas=op.current_replicas,
        available_replicas=op.available_replicas,
        readiness_plasticity=op.readiness_plasticity,
        active_rollback_watches=op.active_rollback_watches,
        seconds_since_last_action=op.seconds_since_last_action,
        dependency_healthy=op.dependency_healthy, freeze_active=op.freeze_active,
        observation_time_s=0.0, provenance=op.provenance)


def build_cloud_candidate(op: KubernetesOperation, world: CloudWorldState, *,
                          manifest_digest_override: Optional[str] = None
                          ) -> CloudActionCandidate:
    """Build the ACP candidate for the SAME operation.

    ``manifest_digest_override`` injects a divergent patch digest, used ONLY by
    the identity-mismatch corpus scenario to prove `bind()` fails closed.
    """
    md = manifest_digest_override if manifest_digest_override is not None \
        else op.manifest_digest
    return CloudActionCandidate(
        candidate_id=f"{op.namespace}/{op.deployment}/{op.k8s_verb.lower()}",
        operation=_CLOUD_OP[op.k8s_verb], namespace=op.namespace,
        deployment=op.deployment, current_replicas=op.current_replicas,
        desired_replicas=(0 if op.k8s_verb == "DELETE" else op.desired_replicas),
        manifest_digest=md, rollback_ref=op.rollback_ref,
        rollout_strategy="RollingUpdate", max_unavailable=0, max_surge=1,
        timeout_s=60.0, origin_state_version=world.version, provenance=op.provenance)


@dataclass(frozen=True)
class CompositionIdentity:
    """Links the two layers to one Kubernetes operation (schemas NOT merged)."""
    actiongate_action_hash: str
    acp_candidate_identity: str
    shared_operation_digest: str
    shared_state_version: str
    actiongate_current_state_hash: str
    acp_state_version: str

    @property
    def identity(self) -> str:
        return _digest("composition", {
            "ag_action_hash": self.actiongate_action_hash,
            "acp_candidate_identity": self.acp_candidate_identity,
            "operation_digest": self.shared_operation_digest,
            "state_version": self.shared_state_version,
        })


def bind(op: KubernetesOperation, ag: ActionGateResult,
         candidate: CloudActionCandidate, world: CloudWorldState
         ) -> Tuple[Optional[CompositionIdentity], str]:
    """Verify both layers bind the same operation. Return (identity|None, reason).

    Independently re-derives the shared facts from ActionGate's artifacts and
    from ACP's candidate/world and compares. Any disagreement fails closed.
    """
    # 1. namespace
    if not (op.namespace == ag.namespace == candidate.namespace == world.namespace):
        return None, "NAMESPACE_MISMATCH"
    # 2. target name / deployment
    if not (op.deployment == ag.name == candidate.deployment == world.deployment):
        return None, "TARGET_MISMATCH"
    # 3. operation kind
    if ag.ag_operation != _expected_ag_op(op.k8s_verb):
        return None, "OPERATION_MISMATCH"
    if candidate.operation is not _CLOUD_OP[op.k8s_verb]:
        return None, "OPERATION_MISMATCH"
    # 4. manifest / patch digest — the cross-layer anchor
    if ag.manifest_digest != candidate.manifest_digest:
        return None, "MANIFEST_DIGEST_MISMATCH"
    # 5. resourceVersion: ACP recomputes ActionGate's current_state_hash from
    #    its own world.resource_version; must reproduce it byte-for-byte.
    acp_recomputed_csh = current_state_hash(
        world.namespace, world.deployment, world.resource_version)
    if acp_recomputed_csh != ag.current_state_hash:
        return None, "RESOURCE_VERSION_MISMATCH"
    if world.resource_version != op.resource_version:
        return None, "RESOURCE_VERSION_MISMATCH"
    # 6. proposed state transition
    exp_desired = 0 if op.k8s_verb == "DELETE" else op.desired_replicas
    if not (candidate.current_replicas == op.current_replicas
            and candidate.desired_replicas == exp_desired):
        return None, "TRANSITION_MISMATCH"

    ident = CompositionIdentity(
        actiongate_action_hash=ag.action_hash,
        acp_candidate_identity=candidate.identity,
        shared_operation_digest=shared_operation_digest(op),
        shared_state_version=shared_state_version(op),
        actiongate_current_state_hash=ag.current_state_hash,
        acp_state_version=world.version)
    return ident, "BOUND"


def _expected_ag_op(k8s_verb: str) -> str:
    return {"SCALE": "DEPLOY", "ROLLOUT": "DEPLOY", "DELETE": "DB_DELETE"}[k8s_verb]
