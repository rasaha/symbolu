"""The Procurement family's policy-pack builder (ruling CR-2).

A Policy Authority resolution returns a family artifact; only the family knows what
its artifact says. This distribution is that mapping for Procurement — deterministic,
declaring nothing the artifact does not state, and knowing nothing about Policy
Authority or about authoritative-source references.
"""

from __future__ import annotations

from .artifact import (
    ApprovalRole,
    EvidenceRequirement,
    ProcurementArtifactError,
    ProcurementPolicyArtifact,
    ProhibitedFact,
    artifact_from_projection,
)
from .builder import build_procurement_pack, procurement_pack_builder
from .version import __version__
from .version_info import version_info

__all__ = [
    "__version__",
    "ProcurementPolicyArtifact",
    "ApprovalRole",
    "EvidenceRequirement",
    "ProhibitedFact",
    "ProcurementArtifactError",
    "artifact_from_projection",
    "build_procurement_pack",
    "procurement_pack_builder",
    "version_info",
]
