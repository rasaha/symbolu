"""Deterministic compiler: synthesis, assurance, audit schema, release."""

from __future__ import annotations

from .assurance_generation import AssuranceGenerator
from .audit_schema import AuditSchemaGenerator
from .capability_registry import (
    DEFAULT_REGISTRY,
    REGISTRY_VERSION,
    CapabilityDefinition,
    CapabilityRegistry,
    UnknownCapabilityError,
)
from .compiler import (
    CompilationError,
    CompilationResult,
    GovernedWorkflowCompiler,
    compile_policy_pack,
)
from .release import (
    PACKAGE_FILES,
    CapabilityManifest,
    CompiledReleasePackage,
    ReleaseManifest,
    build_capability_manifest,
    compute_logical_digest,
)
from .synthesis import WorkflowSynthesizer
from .workflow_ir import (
    EdgeKind,
    NodeKind,
    WorkflowEdge,
    WorkflowIR,
    WorkflowNode,
    make_edge_id,
    make_node_id,
)

__all__ = [
    "CapabilityRegistry",
    "CapabilityDefinition",
    "DEFAULT_REGISTRY",
    "REGISTRY_VERSION",
    "UnknownCapabilityError",
    "WorkflowIR",
    "WorkflowNode",
    "WorkflowEdge",
    "NodeKind",
    "EdgeKind",
    "make_node_id",
    "make_edge_id",
    "WorkflowSynthesizer",
    "AssuranceGenerator",
    "AuditSchemaGenerator",
    "GovernedWorkflowCompiler",
    "CompilationResult",
    "CompilationError",
    "compile_policy_pack",
    "CompiledReleasePackage",
    "CapabilityManifest",
    "ReleaseManifest",
    "PACKAGE_FILES",
    "build_capability_manifest",
    "compute_logical_digest",
]
