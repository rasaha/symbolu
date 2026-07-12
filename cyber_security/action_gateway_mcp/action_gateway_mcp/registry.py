"""Explicit MCP-tool -> canonical-action mapping registry (fail-closed).

One registry maps every exposed MCP tool name to: the frozen operation, the
runtime-gateway (tool, verb), a target-resource builder, credential scope,
reversibility class, required state/evidence/simulation/rollback, and the
argument schema. Unknown tools, verbs, targets, or argument shapes fail closed —
nothing is silently coerced into a generic "safe" operation.

Read-only tools (discovery/inspection) carry no execution authority and map to no
mutating operation; they are served by the read-only handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .errors import ArgumentError, UnknownToolError


@dataclass(frozen=True)
class ToolSpec:
    name: str
    read_only: bool
    operation: str | None            # frozen operation (None for read-only)
    gateway_tool: str | None         # runtime-gateway adapter (None for read-only)
    gateway_verb: str | None
    reversibility: str | None
    target_builder: Callable         # (args) -> list[str]
    required_args: dict = field(default_factory=dict)   # name -> type token
    optional_args: dict = field(default_factory=dict)   # name -> type token
    default_facts: dict = field(default_factory=dict)   # gate facts injected into arguments
    scope_permissions: list | None = None               # credential scope (default: needed perm)
    auto_evidence: tuple = ()        # evidence kinds the MCP layer produces at submit (e.g. build provenance)
    simulation_required: bool = False
    simulation_kind: str | None = None
    rollback_required: bool = False
    required_evidence: tuple = ()    # evidence kinds the gate will demand
    approver_policy: str | None = None
    consequence: str = ""
    description: str = ""


# ---- target builders (fail closed on missing pieces) ---------------------------

def _fs_target(a):
    return [f"file://{a['path']}"]


def _tf_target(a):
    return [f"tf://{a['workspace']}"]


def _k8s_target(a):
    return [f"k8s://{a['namespace']}/{a['kind']}/{a['name']}"]


def _iam_target(a):
    return [a["role"]]


def _mon_target(a):
    return [f"mon://{a['monitor']}"]


REGISTRY: dict[str, ToolSpec] = {
    # ---- read-only (discovery / inspection / preview) ----
    "kubernetes.get": ToolSpec(
        name="kubernetes.get", read_only=True, operation=None,
        gateway_tool=None, gateway_verb=None, reversibility=None,
        target_builder=_k8s_target,
        required_args={"namespace": "str", "kind": "str", "name": "str"},
        consequence="read-only cluster query; no side effects",
        description="Read a Kubernetes resource (metadata only, mocked)."),
    "iam.inspect": ToolSpec(
        name="iam.inspect", read_only=True, operation=None,
        gateway_tool=None, gateway_verb=None, reversibility=None,
        target_builder=_iam_target, required_args={"role": "str"},
        consequence="read-only IAM inspection; no side effects",
        description="Inspect an IAM role's current permissions (mocked)."),
    "terraform.plan": ToolSpec(
        name="terraform.plan", read_only=True, operation=None,
        gateway_tool=None, gateway_verb=None, reversibility=None,
        target_builder=_tf_target, required_args={"workspace": "str"},
        simulation_kind="terraform_plan",
        consequence="read-only plan/preview; produces simulation evidence, no apply",
        description="Produce a Terraform plan (preview, mocked); no infrastructure change."),

    # ---- mutating (require token + scoped capability) ----
    "filesystem.write": ToolSpec(
        name="filesystem.write", read_only=False, operation="DB_MUTATION",
        gateway_tool="filesystem", gateway_verb="write",
        reversibility="REVERSIBLE_WITH_COST", target_builder=_fs_target,
        required_args={"path": "str", "content": "str"},
        optional_args={"unbounded": "bool", "affected_count": "strnum"},
        default_facts={"unbounded": False, "affected_count": "1"},
        simulation_required=True, simulation_kind="fs_diff",
        consequence="bounded write to stored state; recoverable at cost",
        description="Write a file within the sandbox."),
    "filesystem.delete": ToolSpec(
        name="filesystem.delete", read_only=False, operation="DB_DELETE",
        gateway_tool="filesystem", gateway_verb="delete",
        reversibility="IRREVERSIBLE", target_builder=_fs_target,
        required_args={"path": "str"}, optional_args={"last_replica": "bool"},
        default_facts={"last_replica": False},
        required_evidence=("verified_restorable_backup",), rollback_required=True,
        approver_policy="dual_control",
        consequence="irreversible destructive delete",
        description="Delete a file (destructive)."),
    "terraform.apply": ToolSpec(
        name="terraform.apply", read_only=False, operation="DEPLOY",
        gateway_tool="terraform", gateway_verb="apply", reversibility="REVERSIBLE",
        target_builder=_tf_target,
        required_args={"workspace": "str"}, optional_args={"changes": "strnum"},
        auto_evidence=("signed_artifact",),  # build provenance supplied by CI/registry
        simulation_required=True, simulation_kind="terraform_plan",
        required_evidence=("signed_artifact", "simulation"),
        consequence="infrastructure change; reversible",
        description="Apply a Terraform configuration (mocked)."),
    "kubernetes.apply": ToolSpec(
        name="kubernetes.apply", read_only=False, operation="DEPLOY",
        gateway_tool="kubernetes", gateway_verb="apply", reversibility="REVERSIBLE",
        target_builder=_k8s_target,
        required_args={"namespace": "str", "kind": "str", "name": "str"},
        auto_evidence=("signed_artifact",),
        simulation_required=True, simulation_kind="kubernetes_dryrun",
        required_evidence=("signed_artifact", "simulation"),
        consequence="apply a Kubernetes manifest; reversible",
        description="Apply a Kubernetes resource (mocked)."),
    "kubernetes.delete": ToolSpec(
        name="kubernetes.delete", read_only=False, operation="DB_DELETE",
        gateway_tool="kubernetes", gateway_verb="delete",
        reversibility="REVERSIBLE_WITH_COST", target_builder=_k8s_target,
        required_args={"namespace": "str", "kind": "str", "name": "str"},
        optional_args={"last_replica": "bool"},
        default_facts={"last_replica": False},
        required_evidence=("verified_restorable_backup",), rollback_required=True,
        simulation_kind="kubernetes_dryrun", approver_policy="dual_control",
        consequence="destructive delete; recoverable at cost via backup/rollback",
        description="Delete a Kubernetes resource (destructive; escalates)."),
    "iam.grant": ToolSpec(
        name="iam.grant", read_only=False, operation="IAM_GRANT_ADMIN",
        gateway_tool="iam", gateway_verb="grant", reversibility="REVERSIBLE_WITH_COST",
        target_builder=_iam_target,
        required_args={"role": "str", "grantee": "str"},
        simulation_kind="iam_delta", approver_policy="dual_control",
        consequence="grants privileged IAM access; requires dual control + attestation",
        description="Grant an IAM admin policy (mocked)."),
    "monitoring.disable": ToolSpec(
        name="monitoring.disable", read_only=False, operation="MONITORING_DISABLE",
        gateway_tool="monitoring", gateway_verb="disable", reversibility="REVERSIBLE",
        target_builder=_mon_target,
        required_args={"monitor": "str"}, optional_args={"target": "str"},
        default_facts={"target": "monitor"}, approver_policy="dual_control",
        consequence="disables monitoring; requires dual control, auto re-enable",
        description="Disable a monitoring alarm (mocked)."),
}


_TYPE_CHECKS = {
    "str": lambda v: isinstance(v, str),
    "bool": lambda v: isinstance(v, bool),
    "strnum": lambda v: isinstance(v, str) and v.lstrip("-").isdigit(),
    "list": lambda v: isinstance(v, list),
}


def get_spec(tool_name: str) -> ToolSpec:
    spec = REGISTRY.get(tool_name)
    if spec is None:
        raise UnknownToolError(f"tool not in registry: {tool_name!r}")
    return spec


def validate_arguments(spec: ToolSpec, args: dict) -> None:
    """Strict, fail-closed argument validation: required present, no unknown keys."""
    if not isinstance(args, dict):
        raise ArgumentError("arguments must be an object")
    allowed = set(spec.required_args) | set(spec.optional_args) | set(spec.default_facts)
    for k in args:
        if k not in allowed:
            raise ArgumentError(f"unknown argument {k!r} for {spec.name}")
    for k, t in spec.required_args.items():
        if k not in args:
            raise ArgumentError(f"missing required argument {k!r} for {spec.name}")
    for k, t in list(spec.required_args.items()) + list(spec.optional_args.items()):
        if k in args and not _TYPE_CHECKS[t](args[k]):
            raise ArgumentError(f"argument {k!r} must be {t} for {spec.name}")
    # numeric facts must be typed strings (no bare JSON numbers survive canonicalization)
    for k, t in spec.optional_args.items():
        if t == "strnum" and k in args and not _TYPE_CHECKS["strnum"](args[k]):
            raise ArgumentError(f"argument {k!r} must be a numeric string")


def build_arguments(spec: ToolSpec, args: dict) -> dict:
    """Envelope arguments = declared facts (client may override) + tool payload."""
    merged = dict(spec.default_facts)
    merged.update(args)
    return merged


def metadata() -> dict:
    """Machine-readable registry metadata (for discovery + coverage tests)."""
    return {name: {
        "read_only": s.read_only, "operation": s.operation,
        "gateway_tool": s.gateway_tool, "gateway_verb": s.gateway_verb,
        "reversibility": s.reversibility,
        "required_args": s.required_args, "optional_args": s.optional_args,
        "simulation_required": s.simulation_required,
        "simulation_kind": s.simulation_kind, "rollback_required": s.rollback_required,
        "required_evidence": list(s.required_evidence),
        "auto_evidence": list(s.auto_evidence),
        "approver_policy": s.approver_policy, "consequence": s.consequence,
        "description": s.description,
    } for name, s in REGISTRY.items()}


EXPOSED_TOOLS = tuple(REGISTRY.keys())
