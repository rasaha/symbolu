"""Deterministic release packaging (Stage 5 subset).

Assembles the content-addressed compiled package. The **logical** package digest
is computed over the deterministic artifacts only (policy pack, workflow IR,
capability manifest, assurance manifest, coverage matrix, audit schema) — never
over timestamps or filesystem metadata. The same approved input and compiler
version therefore produce the same logical digest. Release timestamps are recorded
separately as metadata, not embedded in policy logic.
"""

from __future__ import annotations

from typing import Optional, Tuple

from pydantic import Field

from ..models.approvals import HumanApprovalRecord
from ..models.assurance import AssuranceManifest, CoverageMatrix
from ..models.audit import AuditSchema
from ..models.common import CompilerModel
from ..models.policy_pack import PolicyPack
from ..serialization import hashing
from ..validation.errors import ValidationReport
from ..version import DISTRIBUTION_VERSION
from .capability_registry import CapabilityDefinition, CapabilityRegistry, DEFAULT_REGISTRY
from .workflow_ir import WorkflowIR

#: Canonical file names inside a compiled package.
PACKAGE_FILES: Tuple[str, ...] = (
    "manifest.json",
    "policy_pack.json",
    "workflow_ir.json",
    "capability_manifest.json",
    "assurance_manifest.json",
    "coverage_matrix.json",
    "audit_schema.json",
    "approval_record.json",
    "validation_report.json",
    "structural_digest.json",
)


class CapabilityManifest(CompilerModel):
    """The capability-requirement manifest for a compiled pack."""

    registry_version: str
    #: Capability ids referenced by the workflow IR, in deterministic order.
    referenced_capabilities: Tuple[str, ...] = ()
    #: Full metadata for each referenced capability.
    capabilities: Tuple[CapabilityDefinition, ...] = ()


class ReleaseManifest(CompilerModel):
    """Top-level manifest: identity + the structural digest (no timestamps)."""

    policy_pack_id: str
    policy_pack_version: int
    schema_version: str
    compiler_distribution_version: str
    structural_digest: str
    file_names: Tuple[str, ...] = PACKAGE_FILES


class CompiledReleasePackage(CompilerModel):
    """The content-addressed compiled package.

    ``structural_digest`` is the logical digest and is reproducible for identical
    approved input and compiler version. ``release_metadata`` holds volatile
    values (timestamps) and is excluded from the logical digest.
    """

    manifest: ReleaseManifest
    policy_pack: PolicyPack
    workflow_ir: WorkflowIR
    capability_manifest: CapabilityManifest
    assurance_manifest: AssuranceManifest
    coverage_matrix: CoverageMatrix
    audit_schema: AuditSchema
    approval_record: Optional[HumanApprovalRecord] = None
    validation_report: ValidationReport
    structural_digest: str
    release_metadata: dict = Field(default_factory=dict)

    def logical_payload(self) -> dict:
        """The deterministic subset the logical digest commits to."""
        return _logical_payload(
            self.policy_pack,
            self.workflow_ir,
            self.capability_manifest,
            self.assurance_manifest,
            self.coverage_matrix,
            self.audit_schema,
        )

    def recompute_digest(self) -> str:
        return hashing.digest(self.logical_payload())


def build_capability_manifest(
    ir: WorkflowIR, registry: CapabilityRegistry = DEFAULT_REGISTRY
) -> CapabilityManifest:
    from ..models.common import CapabilityId

    referenced = tuple(sorted(ir.referenced_capabilities))
    caps = tuple(
        registry.get(CapabilityId(cid))
        for cid in referenced
        if registry.has(CapabilityId(cid))
    )
    return CapabilityManifest(
        registry_version=registry.version,
        referenced_capabilities=referenced,
        capabilities=caps,
    )


def _pack_logical(pack: PolicyPack) -> dict:
    """A status-independent view of the pack for the logical digest.

    The lifecycle ``status`` is excluded so the digest is identical across the
    ``APPROVED -> COMPILED`` transition — reproducibility is about content, not
    lifecycle position.
    """
    data = pack.model_dump(mode="python")
    data.pop("status", None)
    return data


def _logical_payload(
    pack: PolicyPack,
    ir: WorkflowIR,
    capability_manifest: CapabilityManifest,
    assurance: AssuranceManifest,
    coverage: CoverageMatrix,
    audit_schema: AuditSchema,
) -> dict:
    return {
        "policy_pack": _pack_logical(pack),
        "workflow_ir": ir,
        "capability_manifest": capability_manifest,
        "assurance_manifest": assurance,
        "coverage_matrix": coverage,
        "audit_schema": audit_schema,
        "compiler_distribution_version": DISTRIBUTION_VERSION,
    }


def compute_logical_digest(
    pack: PolicyPack,
    ir: WorkflowIR,
    capability_manifest: CapabilityManifest,
    assurance: AssuranceManifest,
    coverage: CoverageMatrix,
    audit_schema: AuditSchema,
) -> str:
    """Compute the reproducible logical package digest."""
    return hashing.digest(
        _logical_payload(pack, ir, capability_manifest, assurance, coverage, audit_schema)
    )
