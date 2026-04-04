"""
Sovereign Shared Constants — Single source of truth for sovereign ontology.

This module consolidates constants that were previously duplicated across:
  - sovereign/vritti.py, sovereign/telemetry.py, sovereign/heartbeat.py
  - sovereign/pid_governor.py, sovereign/router.py
  - sovereign/reasoning_kernel.py, sovereign/inference_bridge.py
  - agentic_framework/sovereign_bridge.py
  - agentic_framework/jepa_governance.py
  - chitta_vritti/coupling.py
  - inference/sovereign_state_monitor.py

Design rules:
  - No PyTorch dependency — safe for both sovereign (tensor) and agentic (pure Python) use
  - No circular imports — this module imports nothing from sovereign/ or agentic_framework/
  - All naming variants are provided (short codes, full names, canonical lowercase)
  - Backward-compatible: consumers can import the variant they need

Phase S1 of sovereign → agentic framework integration.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Dict, FrozenSet, Tuple

# =============================================================================
# State Dimensions
# =============================================================================

SOVEREIGN_STATE_DIM = 32       # Inference control-plane width
SOVEREIGN_HEADER_DIM = 128     # Full training-time biological header width

# =============================================================================
# 32D State Slice Boundaries
# =============================================================================
# Layout: Bhava[0:12] | Kosha[12:17] | Vritti[17:22] | Guna[22:28] | Reserved[28:32]

BHAVA_START, BHAVA_END = 0, 12
KOSHA_START, KOSHA_END = 12, 17
VRITTI_START, VRITTI_END = 17, 22
GUNA_START, GUNA_END = 22, 28
RESERVED_START, RESERVED_END = 28, 32

# Slice objects (convenience for tensor indexing)
BHAVA_SLICE = slice(BHAVA_START, BHAVA_END)
KOSHA_SLICE = slice(KOSHA_START, KOSHA_END)
VRITTI_SLICE = slice(VRITTI_START, VRITTI_END)
GUNA_SLICE = slice(GUNA_START, GUNA_END)
RESERVED_SLICE = slice(RESERVED_START, RESERVED_END)

# =============================================================================
# Bhava — 12 Ontological Aspects
# =============================================================================

BHAVA_COUNT = 12

# Short 3-letter codes (used by reasoning_kernel, inference_bridge, state_monitor)
BHAVA_NAMES_SHORT: Tuple[str, ...] = (
    "POT", "IDN", "EXE", "STR", "COG", "AGY",
    "RSN", "PRP", "WIT", "UNI", "INT", "ABS",
)

# Full prefixed names (used by telemetry, jepa_governance, domain_policy)
BHAVA_NAMES_FULL: Tuple[str, ...] = (
    "O1_POTENTIAL", "O2_IDENTITY", "O3_EXECUTION", "O4_STRUCTURE",
    "O5_COGNITION", "O6_AGENCY", "O7_REASONING", "O8_PURPOSE",
    "O9_WITNESSES", "O10_UNIFYING", "O11_INTEGRATION", "O12_ABSOLVING",
)

# Human-readable names
BHAVA_NAMES_READABLE: Tuple[str, ...] = (
    "Potential", "Identity", "Execution", "Structure",
    "Cognition", "Agency", "Reason", "Purpose",
    "Witness", "Unity", "Intent", "Absolute",
)

# Short → Full lookup
BHAVA_SHORT_TO_FULL: Dict[str, str] = dict(zip(BHAVA_NAMES_SHORT, BHAVA_NAMES_FULL))
BHAVA_FULL_TO_SHORT: Dict[str, str] = dict(zip(BHAVA_NAMES_FULL, BHAVA_NAMES_SHORT))

# =============================================================================
# Kosha — 5 Processing Sheaths
# =============================================================================

KOSHA_COUNT = 5

KOSHA_NAMES: Tuple[str, ...] = (
    "MATERIAL",       # Annamaya — surface/syntax
    "VITAL",          # Pranamaya — flow/energy
    "MENTAL",         # Manomaya — semantics
    "INTELLECTUAL",   # Vijnanamaya — wisdom/patterns
    "BLISSFUL",       # Anandamaya — unity/integration
)

# Index constants (within the 5D Kosha slice)
KOSHA_MATERIAL = 0
KOSHA_VITAL = 1
KOSHA_MENTAL = 2
KOSHA_INTELLECTUAL = 3
KOSHA_BLISSFUL = 4

# =============================================================================
# Vritti — 5 Cognitive Modes
# =============================================================================

VRITTI_COUNT = 5


class VrittiIndex(IntEnum):
    """Canonical 32D-state ordering of the 5 Vritti states.

    NB: The training-side VrittiState enum in vritti.py uses
    SMRITI=3, NIDRA=4. The 32D inference state (reasoning_kernel,
    inference_bridge, sovereign_bridge) uses NIDRA=3, SMRITI=4.
    This enum follows the 32D state layout.
    """
    PRAMANA = 0      # Valid cognition / Truth
    VIPARYAYA = 1    # Misconception / Error
    VIKALPA = 2      # Imagination / Conceptualization
    NIDRA = 3        # Dormancy / Void
    SMRITI = 4       # Memory / Recall


# Canonical lowercase Sanskrit names (used by jepa_governance, coupling, telemetry)
VRITTI_NAMES: Tuple[str, ...] = (
    "pramana", "viparyaya", "vikalpa", "smrti", "nidra",
)

# English labels (used by reasoning_kernel, sovereign_bridge, state_monitor)
# Follows 32D state ordering: index 3 = VOID (Nidra), index 4 = MEMORY (Smriti)
VRITTI_LABELS: Tuple[str, ...] = (
    "FACT", "ERROR", "IMAGINATION", "VOID", "MEMORY",
)

# Uppercase Sanskrit (used by heartbeat)
VRITTI_NAMES_UPPER: Tuple[str, ...] = (
    "PRAMANA", "VIPARYAYA", "VIKALPA", "SMRTI", "NIDRA",
)

# Index constants (within the 5D Vritti slice)
# NB: The 32D state layout (reasoning_kernel, inference_bridge) puts Void at 3
# and Memory at 4. This matches sovereign_bridge.py. The training-side VrittiState
# enum in vritti.py uses the reverse (SMRITI=3, NIDRA=4). The constants here
# follow the 32D state layout since that's what the agentic framework consumes.
VRITTI_FACT = 0         # Pramana — valid cognition
VRITTI_ERROR = 1        # Viparyaya — misconception / hallucination
VRITTI_IMAGINATION = 2  # Vikalpa — conceptualization
VRITTI_VOID = 3         # Nidra — null state / absence
VRITTI_MEMORY = 4       # Smriti — recall from weights

# Governance-relevant Vritti sets
OBSERVATION_VRITTIS: FrozenSet[str] = frozenset({"viparyaya", "nidra"})
EXECUTION_VRITTIS: FrozenSet[str] = frozenset({"pramana", "smrti"})

# =============================================================================
# Guna — Energy Dynamics
# =============================================================================

GUNA_COUNT = 6  # Full 6D in 32D state

# Full 6-element names (32D control plane)
GUNA_NAMES: Tuple[str, ...] = (
    "LUCIDITY", "ACTIVITY", "STABILITY",
    "VELOCITY", "ACCEL", "STABLE",
)

# Traditional 3-element Guna names (used by entropy module, heartbeat)
GUNA_3D_NAMES: Tuple[str, ...] = ("sattva", "rajas", "tamas")

# Index constants (within the 6D Guna slice)
GUNA_LUCIDITY = 0      # Sattva — clarity
GUNA_ACTIVITY = 1      # Rajas — dynamism / turbulence
GUNA_STABILITY = 2     # Tamas — inertia / fixedness
GUNA_VELOCITY = 3      # Rate of state change
GUNA_ACCEL = 4         # Acceleration of change
GUNA_STABLE = 5        # Stability measure

# =============================================================================
# Ontology-to-Nexus Routing
# =============================================================================
# Maps each of the 12 ontological layers to a Virtual Nexus position.
# Nexus 4 = Logic-Heavy (4/8 split), Nexus 6 = Balanced, Nexus 8 = Memory-Heavy

ONTOLOGY_TO_NEXUS: Dict[str, int] = {
    "O1_POTENTIAL":    6,   # Balanced
    "O2_IDENTITY":     6,   # Balanced
    "O3_EXECUTION":    8,   # Memory-Heavy (action recall)
    "O4_STRUCTURE":    8,   # Memory-Heavy (form/patterns)
    "O5_COGNITION":    6,   # Balanced (perception)
    "O6_AGENCY":       6,   # Balanced (will/control)
    "O7_REASONING":    4,   # Logic-Heavy (analysis)
    "O8_PURPOSE":      6,   # Balanced (intent/goals)
    "O9_WITNESSES":    4,   # Logic-Heavy (observation/awareness)
    "O10_UNIFYING":    4,   # Logic-Heavy (integration)
    "O11_INTEGRATION": 4,   # Logic-Heavy (consolidation)
    "O12_ABSOLVING":   6,   # Balanced (transcendence)
}

NEXUS_MODE_DESCRIPTIONS: Dict[int, str] = {
    4: "4/8 (Logic-Heavy)",
    6: "6/6 (Balanced)",
    8: "8/4 (Memory-Heavy)",
}

# =============================================================================
# Ontology Governance Sets
# =============================================================================
# Higher ontological layers are governance-relevant (reasoning, purpose, witness)
# Lower layers are execution-relevant (potential, identity, action, structure)

GOVERNANCE_ONTOLOGY: FrozenSet[str] = frozenset({
    "O7_REASONING", "O8_PURPOSE", "O9_WITNESSES",
    "O10_UNIFYING", "O11_INTEGRATION", "O12_ABSOLVING",
})

EXECUTION_ONTOLOGY: FrozenSet[str] = frozenset({
    "O1_POTENTIAL", "O2_IDENTITY", "O3_EXECUTION",
    "O4_STRUCTURE", "O5_COGNITION", "O6_AGENCY",
})
