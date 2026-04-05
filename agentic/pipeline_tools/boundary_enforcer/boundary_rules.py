"""
Boundary Rules: Definitions of authoritative and observer module roots.

This module defines the boundary contract between:
- Authoritative modules: Make binding pipeline decisions (PO1-P9, policy)
- Observer modules: Compute diagnostics only (P22, P23, P24)

Rule: Authoritative modules must NOT import observer modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, List


class ModuleType(Enum):
    """Classification of module authority level."""
    AUTHORITATIVE = "authoritative"
    OBSERVER = "observer"
    ALLOWED_SINK = "allowed_sink"
    UNKNOWN = "unknown"


# ============================================================================
# AUTHORITATIVE MODULE ROOTS
# ============================================================================
# These modules make binding decisions and must NOT import observer modules.

AUTHORITATIVE_MODULE_ROOTS: FrozenSet[str] = frozenset({
    # Pre-Governance Phases (PO1-PO5)
    "symbolu.mechanical.pipeline.grounding",          # PO1 (P-1)
    "symbolu.mechanical.pipeline.phase_zero",         # PO2 (P0)
    "symbolu.mechanical.pipeline.phase_one",          # PO3 (P1)
    "symbolu.mechanical.pipeline.phase_po4",          # PO4
    "symbolu.mechanical.pipeline.phase_po5",          # PO5

    # Core Governance Phases (P6-P9)
    "symbolu.mechanical.pipeline.phase_p6",           # P6: Regime
    "symbolu.mechanical.pipeline.p7_discourse",       # P7: Discourse
    "symbolu.mechanical.pipeline.p8_semantics",       # P8: Semantic
    "symbolu.mechanical.pipeline.p9_lexical",         # P9: Lexical

    # Extended Governance (P10-P21)
    "symbolu.mechanical.pipeline.p10_acoustic",       # P10
    "symbolu.mechanical.pipeline.p11_prosodic",       # P11
    "symbolu.mechanical.pipeline.p12_consistency",    # P12
    "symbolu.mechanical.pipeline.p13_acoustic_safety",# P13
    "symbolu.mechanical.pipeline.p14_surface",        # P14
    "symbolu.mechanical.pipeline.p15_interaction",    # P15
    "symbolu.mechanical.pipeline.p16_regression_guard",  # P16
    "symbolu.mechanical.pipeline.p17_semantic_integrity",  # P17
    "symbolu.mechanical.pipeline.p18_temporal_entropy",    # P18
    "symbolu.mechanical.pipeline.p19_drift_fusion",   # P19
    "symbolu.mechanical.pipeline.p20_snapshot",       # P20
    "symbolu.mechanical.pipeline.p21_delivery",       # P21

    # Policy and Routing
    "symbolu.policy",                                 # Policy engines
    "symbolu.mechanical.router",                      # Routing logic

    # Core Coherence (authoritative aspects)
    "symbolu.core.coherence",                         # Coherence engine
})


# ============================================================================
# OBSERVER MODULE ROOTS
# ============================================================================
# These modules compute diagnostics only and must NEVER influence decisions.

OBSERVER_MODULE_ROOTS: FrozenSet[str] = frozenset({
    "symbolu.mechanical.pipeline.p22_acoustic_witness",  # P22
    "symbolu.mechanical.pipeline.p23_alignment",         # P23
    "symbolu.mechanical.pipeline.p24_projection",        # P24
})


# ============================================================================
# ALLOWED SINK PATTERNS
# ============================================================================
# Observer outputs may only flow to these destination patterns.

ALLOWED_SINK_PATTERNS: FrozenSet[str] = frozenset({
    # Logging
    "logging",
    "logger",
    "log_",

    # Snapshots
    "to_dict",
    "snapshot",
    "serialize",

    # API serialization
    "api",
    "response",
    "payload",

    # Dashboard/observability
    "dashboard",
    "observability",
    "metrics",
    "diagnostic",

    # Renderer hints (presentation only)
    "renderer",
    "hint",
    "display",
})


# ============================================================================
# OBSERVER DATACLASS NAMES
# ============================================================================
# These dataclass names are observer outputs and must not appear in decision logic.

OBSERVER_DATACLASS_NAMES: FrozenSet[str] = frozenset({
    # P22 outputs
    "P22AcousticVrittiWitness",
    "p22_acoustic_witness",
    "AcousticWitness",
    "pressure_band",
    "motion_balance",
    "vritti_vector",

    # P23 outputs
    "P23AlignmentReport",
    "p23_alignment_report",
    "AlignmentReport",
    "tension_score",
    "alignment_state",

    # P24 outputs
    "P24ProjectionReport",
    "p24_projection_report",
    "ProjectionReport",
    "projection_risk_band",
    "mismatch_type",
})


# ============================================================================
# DECISION SURFACE PHASES
# ============================================================================
# These phases produce the decision surface that must be invariant.

DECISION_SURFACE_PHASES: FrozenSet[str] = frozenset({
    "PO1",  # Grounding
    "PO2",  # Intent
    "PO3",  # Action
    "PO4",  # Ontology
    "PO5",  # Policy
    "P6",   # Regime
    "P7",   # Discourse
    "P8",   # Semantic
    "P9",   # Lexical
})


# ============================================================================
# BOUNDARY RULE DATACLASS
# ============================================================================

@dataclass(frozen=True)
class BoundaryRule:
    """A boundary enforcement rule."""
    rule_id: str
    description: str
    source_type: ModuleType
    target_type: ModuleType
    allowed: bool

    def __str__(self) -> str:
        direction = "allowed" if self.allowed else "FORBIDDEN"
        return f"{self.rule_id}: {self.source_type.value} -> {self.target_type.value} [{direction}]"


def get_boundary_rules() -> List[BoundaryRule]:
    """
    Return the complete set of boundary rules.

    Returns:
        List of BoundaryRule objects defining allowed/forbidden couplings.
    """
    return [
        # FORBIDDEN: Authoritative importing Observer
        BoundaryRule(
            rule_id="INV-B1",
            description="Authoritative modules must NOT import observer modules",
            source_type=ModuleType.AUTHORITATIVE,
            target_type=ModuleType.OBSERVER,
            allowed=False,
        ),

        # ALLOWED: Observer reading Authoritative (read-only)
        BoundaryRule(
            rule_id="FLOW-1",
            description="Observer modules may read authoritative outputs (read-only)",
            source_type=ModuleType.OBSERVER,
            target_type=ModuleType.AUTHORITATIVE,
            allowed=True,
        ),

        # ALLOWED: Observer to Allowed Sinks
        BoundaryRule(
            rule_id="FLOW-2",
            description="Observer outputs may flow to allowed sinks",
            source_type=ModuleType.OBSERVER,
            target_type=ModuleType.ALLOWED_SINK,
            allowed=True,
        ),

        # ALLOWED: Observer to Observer (chain)
        BoundaryRule(
            rule_id="FLOW-3",
            description="Observer modules may read other observer outputs",
            source_type=ModuleType.OBSERVER,
            target_type=ModuleType.OBSERVER,
            allowed=True,
        ),
    ]


def classify_module(module_path: str) -> ModuleType:
    """
    Classify a module path by its authority type.

    Args:
        module_path: Dotted module path (e.g., 'symbolu.mechanical.pipeline.phase_p6')

    Returns:
        ModuleType classification.
    """
    # Check observer first (more specific)
    for observer_root in OBSERVER_MODULE_ROOTS:
        if module_path == observer_root or module_path.startswith(f"{observer_root}."):
            return ModuleType.OBSERVER

    # Check authoritative
    for auth_root in AUTHORITATIVE_MODULE_ROOTS:
        if module_path == auth_root or module_path.startswith(f"{auth_root}."):
            return ModuleType.AUTHORITATIVE

    # Check for sink patterns
    for sink_pattern in ALLOWED_SINK_PATTERNS:
        if sink_pattern in module_path.lower():
            return ModuleType.ALLOWED_SINK

    return ModuleType.UNKNOWN


def is_observer_import_violation(source_module: str, imported_module: str) -> bool:
    """
    Check if an import constitutes a boundary violation.

    Args:
        source_module: The module doing the importing
        imported_module: The module being imported

    Returns:
        True if this is a forbidden authoritative -> observer import.
    """
    source_type = classify_module(source_module)
    target_type = classify_module(imported_module)

    # Violation: Authoritative module importing Observer module
    if source_type == ModuleType.AUTHORITATIVE and target_type == ModuleType.OBSERVER:
        return True

    return False
