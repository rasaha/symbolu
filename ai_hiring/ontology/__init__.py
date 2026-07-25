"""Capability ontology (Phase 3A) — the controlled vocabulary of capabilities.

Immutable capability definitions, their hierarchy, the evidence-type and
reason-code vocabularies, and versioning helpers. Contracts only — no scoring or
evaluation.
"""

from __future__ import annotations

from .capability import Capability, CapabilityStatus
from .registry import CapabilityGraph, build_graph
from .taxonomy import (
    REASON_CODE_CATALOG,
    EvidenceType,
    ReasonCode,
    ReasonCodeSpec,
    get_reason_code_spec,
    is_known_evidence_type,
    is_known_reason_code,
)
from .versioning import VersionRef, VersionWindow, is_monotonic, next_version

__all__ = [
    "Capability",
    "CapabilityStatus",
    "CapabilityGraph",
    "build_graph",
    "EvidenceType",
    "ReasonCode",
    "ReasonCodeSpec",
    "REASON_CODE_CATALOG",
    "get_reason_code_spec",
    "is_known_evidence_type",
    "is_known_reason_code",
    "VersionRef",
    "VersionWindow",
    "next_version",
    "is_monotonic",
]
