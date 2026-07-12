"""Kubernetes tool -> canonical action envelope mapping (fail-closed).

Binds every Kubernetes action to: cluster identity, namespace, API group/version,
kind, resource name, requested manifest digest, verb, credential scope, current-
state hash, rollback plan, and policy version. Unknown kinds, namespaces, verbs,
or argument shapes fail closed.

Manifests carry bare JSON numbers (replicas, ports), which the Action Profile
forbids in a hashed envelope, so the manifest is serialized to a deterministic
JSON *string* (``manifest_json``) and its digest recorded — both are string
values, both are covered by the action hash, so any manifest change is detected.
"""

from __future__ import annotations

import json

from . import cluster as cluster_mod
from ._core import ToolRequest, ref_hashing
from .errors import UnknownKindError, UnknownNamespaceError, BadK8sArgumentError
from .kubeclient import GVR

KNOWN_NAMESPACES = {"protected", "sandbox", "default", "kube-system"}
# only these namespaces may be *mutated* through the gateway; others -> admission deny
MUTABLE_NAMESPACES = {"protected", "sandbox"}
# kinds each tool may target
_APPLY_KINDS = {"ConfigMap", "Deployment", "Service", "Secret", "Role", "RoleBinding",
                "ClusterRole", "ClusterRoleBinding", "NetworkPolicy", "Pod"}
_DELETE_KINDS = {"ConfigMap", "Deployment", "Service", "Pod", "NetworkPolicy"}
_READ_KINDS = {"ConfigMap", "Deployment", "Service", "Pod", "Role", "RoleBinding"}


class K8sToolSpec:
    def __init__(self, name, read_only, operation, verb, reversibility, kinds,
                 *, approver_policy=None, rollback_required=False,
                 simulation_required=False, description=""):
        self.name = name
        self.read_only = read_only
        self.operation = operation
        self.verb = verb
        self.reversibility = reversibility
        self.kinds = kinds
        self.approver_policy = approver_policy
        self.rollback_required = rollback_required
        self.simulation_required = simulation_required
        self.description = description


REGISTRY = {
    "kubernetes.get": K8sToolSpec(
        "kubernetes.get", True, None, "get", None, _READ_KINDS,
        description="Read a namespaced resource (no execution authority)."),
    "kubernetes.inspect_rbac": K8sToolSpec(
        "kubernetes.inspect_rbac", True, None, "get", None, {"Role", "RoleBinding"},
        description="Inspect RBAC roles/bindings (read-only)."),
    "kubernetes.apply": K8sToolSpec(
        "kubernetes.apply", False, "DEPLOY", "apply", "REVERSIBLE", _APPLY_KINDS,
        simulation_required=True,
        description="Server-side apply a manifest (deployment/config map/service)."),
    "kubernetes.delete": K8sToolSpec(
        "kubernetes.delete", False, "DB_DELETE", "delete", "REVERSIBLE_WITH_COST",
        _DELETE_KINDS, approver_policy="dual_control", rollback_required=True,
        simulation_required=True,
        description="Delete a namespaced resource (destructive; escalates)."),
}

EXPOSED_TOOLS = tuple(REGISTRY.keys())


def get_spec(name):
    spec = REGISTRY.get(name)
    if spec is None:
        raise UnknownKindError(f"tool not in registry: {name!r}")
    return spec


def _manifest_json(manifest: dict) -> str:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"))


def validate_and_extract(spec, args):
    """Return (namespace, kind, name, manifest) or fail closed."""
    if not isinstance(args, dict):
        raise BadK8sArgumentError("arguments must be an object")
    ns = args.get("namespace")
    kind = args.get("kind")
    name = args.get("name")
    if not isinstance(ns, str) or ns not in KNOWN_NAMESPACES:
        raise UnknownNamespaceError(f"unknown or missing namespace: {ns!r}")
    if not isinstance(kind, str) or kind not in GVR:
        raise UnknownKindError(f"unknown or missing kind: {kind!r}")
    if kind not in spec.kinds:
        raise UnknownKindError(f"{kind!r} not permitted for {spec.name}")
    if not isinstance(name, str) or not name:
        raise BadK8sArgumentError("missing resource name")
    manifest = None
    if spec.verb == "apply":
        manifest = args.get("manifest")
        if not isinstance(manifest, dict):
            raise BadK8sArgumentError("apply requires a manifest object")
        # the manifest must self-describe the same coordinates (no smuggling)
        md = manifest.get("metadata", {})
        if md.get("name") not in (name, None):
            raise BadK8sArgumentError("manifest name does not match target name")
        if md.get("namespace") not in (ns, None):
            raise BadK8sArgumentError("manifest namespace does not match target namespace")
    return ns, kind, name, manifest


def to_tool_request(spec, args, ctx, *, current_state_hash):
    ns, kind, name, manifest = validate_and_extract(spec, args)
    gvr = GVR[kind]
    env_args = {
        "cluster": cluster_mod.CLUSTER_ID, "namespace": ns,
        "api_group": gvr.group, "api_version": gvr.version, "kind": kind,
        "resource": gvr.resource, "name": name, "verb": spec.verb,
    }
    if manifest is not None:
        mj = _manifest_json(manifest)
        env_args["manifest_json"] = mj
        env_args["manifest_digest"] = ref_hashing.domain_digest("SIMULATION", mj.encode("utf-8"))
    rollback = args.get("rollback_plan")
    return ToolRequest(
        tool="kubernetes", verb=spec.verb, target=[f"k8s://{ns}/{kind}/{name}"],
        args=env_args, principal=ctx.effective_agent_id(), agent_id=ctx.effective_agent_id(),
        key_id=ctx.agent_key_id, delegator=ctx.delegator, delegator_type=ctx.delegator_type,
        objective=f"k8s:{spec.name}", runtime=ctx.agent_runtime,
        model=ctx.model or "claude-opus-4-8", provider=ctx.provider or "anthropic",
        grant="*", reversibility=spec.reversibility, permissions=[f"k8s:{spec.verb}"],
        rollback_plan=rollback, correlation_id=ctx.correlation_id,
        sequence_id=ctx.sequence_id)


def metadata():
    return {n: {"read_only": s.read_only, "operation": s.operation, "verb": s.verb,
                "reversibility": s.reversibility, "kinds": sorted(s.kinds),
                "approver_policy": s.approver_policy,
                "rollback_required": s.rollback_required,
                "simulation_required": s.simulation_required,
                "description": s.description} for n, s in REGISTRY.items()}
