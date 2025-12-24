"""
Phase-13: K1 Schema - Knowledge Layer 1 (Revised)
=================================================

K1 is the first canonical knowledge layer that binds ontological artifacts
to retrievable, composable "meaning scaffolds".

K1 does NOT store free-form meaning. It stores typed relational frames
that generation can condition on.

CRITICAL RULES:
    - K1 NEVER stores raw text
    - K1 stores structure about text
    - Interpretation/rendering happens outside K1
    - Discourse acts are routing/control signals only (not intent/emotion/truth)

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                     K1 KNOWLEDGE LAYER                          │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  K1Atom (minimal) ─────────────────────────────────────────────  │
    │    ├── atom_id: str                                             │
    │    ├── layer: OntologicalLayer (O1-O10)                         │
    │    ├── slot: K1Slot (17 typed slots)                            │
    │    ├── discourse_act: DiscourseAct (14 structural acts)         │
    │    ├── payload_ref: str (opaque pointer, NOT text)              │
    │    └── provenance: str                                          │
    │                                                                  │
    │  K1Query ────────────────────────────────────────────────────── │
    │    Index: (layer, slot, discourse_act)                          │
    │                                                                  │
    │  K1ResultSet ────────────────────────────────────────────────── │
    │    Deterministic, ledger-recorded, replay-provable              │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘

INVARIANTS:
    - Same query over same store → same ordered results (deterministic)
    - Fail-closed on invariant violations
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, Optional, Tuple


# =============================================================================
# K1 Slot Taxonomy (17 Slots, 4 Tiers)
# =============================================================================

class K1SlotTier(Enum):
    """Tier classification for K1 slots."""
    TIER_1_CORE = "TIER_1_CORE"           # Mandatory
    TIER_2_CONTROL = "TIER_2_CONTROL"     # Recommended
    TIER_3_FRAMING = "TIER_3_FRAMING"     # Optional
    TIER_4_GOVERNANCE = "TIER_4_GOVERNANCE"  # Advanced/GOVERNED


class K1Slot(Enum):
    """
    K1 Relational Slot Taxonomy v1.0

    17 slots across 4 tiers for structured knowledge representation.
    """
    # Tier-1: Core Structural Slots (Mandatory)
    TARGET = "TARGET"           # What the expression is oriented toward
    CAUSE = "CAUSE"             # Upstream condition or trigger
    EFFECT = "EFFECT"           # Downstream outcome (must pair with CAUSE)
    CONSTRAINT = "CONSTRAINT"   # Restrictive boundary
    EVIDENCE = "EVIDENCE"       # Supportive structural justification

    # Tier-2: Control & Flow Slots (Recommended)
    CONDITION = "CONDITION"     # Gate that must be satisfied
    ALTERNATIVE = "ALTERNATIVE" # Parallel possible path (mutually exclusive)
    SEQUENCE = "SEQUENCE"       # Ordered relationship
    DEPENDENCY = "DEPENDENCY"   # Non-causal reliance

    # Tier-3: Perspective & Framing Slots (Optional)
    ASSUMPTION = "ASSUMPTION"   # Declared premise
    SCOPE = "SCOPE"             # Applicability boundary
    REFERENCE = "REFERENCE"     # Pointer to external/prior atom
    EXCEPTION = "EXCEPTION"     # Explicit carve-out (must attach to CONSTRAINT/RULE)

    # Tier-4: Meta & Governance Slots (Advanced)
    RULE = "RULE"               # Structural rule
    JUSTIFICATION = "JUSTIFICATION"  # Why a rule/constraint exists
    RISK = "RISK"               # Declared potential negative outcome
    MITIGATION = "MITIGATION"   # Counter-measure to RISK


# Slot tier mapping
SLOT_TIER: Dict[K1Slot, K1SlotTier] = {
    # Tier 1 - Core
    K1Slot.TARGET: K1SlotTier.TIER_1_CORE,
    K1Slot.CAUSE: K1SlotTier.TIER_1_CORE,
    K1Slot.EFFECT: K1SlotTier.TIER_1_CORE,
    K1Slot.CONSTRAINT: K1SlotTier.TIER_1_CORE,
    K1Slot.EVIDENCE: K1SlotTier.TIER_1_CORE,
    # Tier 2 - Control
    K1Slot.CONDITION: K1SlotTier.TIER_2_CONTROL,
    K1Slot.ALTERNATIVE: K1SlotTier.TIER_2_CONTROL,
    K1Slot.SEQUENCE: K1SlotTier.TIER_2_CONTROL,
    K1Slot.DEPENDENCY: K1SlotTier.TIER_2_CONTROL,
    # Tier 3 - Framing
    K1Slot.ASSUMPTION: K1SlotTier.TIER_3_FRAMING,
    K1Slot.SCOPE: K1SlotTier.TIER_3_FRAMING,
    K1Slot.REFERENCE: K1SlotTier.TIER_3_FRAMING,
    K1Slot.EXCEPTION: K1SlotTier.TIER_3_FRAMING,
    # Tier 4 - Governance
    K1Slot.RULE: K1SlotTier.TIER_4_GOVERNANCE,
    K1Slot.JUSTIFICATION: K1SlotTier.TIER_4_GOVERNANCE,
    K1Slot.RISK: K1SlotTier.TIER_4_GOVERNANCE,
    K1Slot.MITIGATION: K1SlotTier.TIER_4_GOVERNANCE,
}


def get_slot_tier(slot: K1Slot) -> K1SlotTier:
    """Get the tier for a given slot."""
    return SLOT_TIER[slot]


def get_tier_slots(tier: K1SlotTier) -> Tuple[K1Slot, ...]:
    """Get all slots in a given tier."""
    return tuple(s for s, t in SLOT_TIER.items() if t == tier)


# =============================================================================
# Ontological Layer (O1-O10)
# =============================================================================

class OntologicalLayer(Enum):
    """Ontological layers from the 10-family structure."""
    O5_COGNITION = "O5_COGNITION"
    O4_STRUCTURE = "O4_STRUCTURE"
    O3_EXECUTION = "O3_EXECUTION"
    O4_TAGGING = "O4_TAGGING"
    O6_AGENCY = "O6_AGENCY"
    O7_REASONING = "O7_REASONING"
    O8_PURPOSE = "O8_PURPOSE"
    O9_WITNESSES = "O9_WITNESSES"
    O10_UNIFYING = "O10_UNIFYING"
    O12_ABSOLVING = "O12_ABSOLVING"


# =============================================================================
# Discourse Acts (Structural, NOT Semantic)
# =============================================================================

class DiscourseActTier(Enum):
    """Tier classification for discourse acts."""
    TIER_A_FLOW = "TIER_A_FLOW"           # Structural flow acts
    TIER_B_DIRECTIONAL = "TIER_B_DIRECTIONAL"  # Directional acts
    TIER_C_REFLECTIVE = "TIER_C_REFLECTIVE"    # Reflective/meta acts
    TIER_D_TERMINAL = "TIER_D_TERMINAL"        # Terminal/governance


class DiscourseAct(Enum):
    """
    Symbol-U Discourse Act Set (Structural, Not Semantic)

    These acts describe structural posture, NOT intent or meaning.

    HARD RULES:
        - Discourse acts do not imply intent
        - They do not imply emotion
        - They do not imply truth
        - They are routing and control signals only
    """
    # Tier A — Structural Flow Acts (used by most layers)
    DECLARE = "DECLARE"         # Introduce a structural atom (neutral, non-assertive)
    QUERY = "QUERY"             # Request traversal or retrieval (no expectation of truth)
    LINK = "LINK"               # Connect two atoms (used heavily in FORMING/THINKING)
    COMPARE = "COMPARE"         # Structural juxtaposition (no evaluation/ranking)
    NEGATE = "NEGATE"           # Explicit structural exclusion (NOT logical negation)

    # Tier B — Directional Acts (used by DIRECTING/REASONING)
    CONDITION = "CONDITION"     # Gate activation (must pair with CONDITION slot)
    TRIGGER = "TRIGGER"         # Cause activation (structural, not causal reasoning)
    RESOLVE = "RESOLVE"         # Select one path among alternatives (deterministic only)

    # Tier C — Reflective / Meta Acts (used by META_OBSERVING/UNIFYING)
    OBSERVE = "OBSERVE"         # Read-only structural witnessing
    SUMMARIZE = "SUMMARIZE"     # Structural compression (no interpretation)
    CANONICALIZE = "CANONICALIZE"  # Equivalence normalization

    # Tier D — Terminal / Governance (used sparingly)
    BOUND = "BOUND"             # Impose constraint
    RELEASE = "RELEASE"         # Remove constraint
    ABORT = "ABORT"             # Fail-closed termination


# Discourse act tier mapping
DISCOURSE_ACT_TIER: Dict[DiscourseAct, DiscourseActTier] = {
    # Tier A - Flow
    DiscourseAct.DECLARE: DiscourseActTier.TIER_A_FLOW,
    DiscourseAct.QUERY: DiscourseActTier.TIER_A_FLOW,
    DiscourseAct.LINK: DiscourseActTier.TIER_A_FLOW,
    DiscourseAct.COMPARE: DiscourseActTier.TIER_A_FLOW,
    DiscourseAct.NEGATE: DiscourseActTier.TIER_A_FLOW,
    # Tier B - Directional
    DiscourseAct.CONDITION: DiscourseActTier.TIER_B_DIRECTIONAL,
    DiscourseAct.TRIGGER: DiscourseActTier.TIER_B_DIRECTIONAL,
    DiscourseAct.RESOLVE: DiscourseActTier.TIER_B_DIRECTIONAL,
    # Tier C - Reflective
    DiscourseAct.OBSERVE: DiscourseActTier.TIER_C_REFLECTIVE,
    DiscourseAct.SUMMARIZE: DiscourseActTier.TIER_C_REFLECTIVE,
    DiscourseAct.CANONICALIZE: DiscourseActTier.TIER_C_REFLECTIVE,
    # Tier D - Terminal
    DiscourseAct.BOUND: DiscourseActTier.TIER_D_TERMINAL,
    DiscourseAct.RELEASE: DiscourseActTier.TIER_D_TERMINAL,
    DiscourseAct.ABORT: DiscourseActTier.TIER_D_TERMINAL,
}


def get_discourse_act_tier(act: DiscourseAct) -> DiscourseActTier:
    """Get the tier for a given discourse act."""
    return DISCOURSE_ACT_TIER[act]


# =============================================================================
# Entity Reference (Minimal Stub)
# =============================================================================

@dataclass(frozen=True)
class K1EntityRef:
    """
    Minimal entity reference stub.

    Rules:
        - No attributes
        - No hierarchy
        - No inference
        - No typing system
    """
    entity_id: str          # Opaque identifier
    entity_type: str = ""   # Optional label, no ontology


# =============================================================================
# Selection Rule (Deterministic Ordering)
# =============================================================================

class SelectionRule(Enum):
    """Deterministic ordering rules for query results."""
    LEXICOGRAPHIC_ID = "LEXICOGRAPHIC_ID"     # Sort by atom_id
    TIER_PRIORITY = "TIER_PRIORITY"           # Lower tier first
    LAYER_ORDER = "LAYER_ORDER"               # O1 before O2, etc.


# =============================================================================
# K1 Atom (Minimal, Finalized)
# =============================================================================

@dataclass(frozen=True)
class K1Atom:
    """
    Smallest retrievable unit in K1.

    INVARIANT: K1Atom contains no free text.
    payload_ref is an opaque pointer (hash:xxx, uri:xxx, rag:xxx)
    """
    atom_id: str                    # Hash-stable identifier
    layer: OntologicalLayer         # O1-O10
    slot: K1Slot                    # One of 17 slot types
    discourse_act: DiscourseAct     # One of 14 structural acts
    payload_ref: str                # Opaque pointer (NOT text)
    provenance: str                 # Source identifier

    def atom_hash(self) -> str:
        """Compute deterministic hash of atom (excluding atom_id)."""
        content = (
            f"{self.layer.value}|{self.slot.value}|{self.discourse_act.value}|"
            f"{self.payload_ref}|{self.provenance}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_slot_tier(self) -> K1SlotTier:
        """Get the tier of this atom's slot."""
        return get_slot_tier(self.slot)

    def get_discourse_act_tier(self) -> DiscourseActTier:
        """Get the tier of this atom's discourse act."""
        return get_discourse_act_tier(self.discourse_act)


def create_atom_id(
    layer: OntologicalLayer,
    slot: K1Slot,
    discourse_act: DiscourseAct,
    payload_ref: str,
    provenance: str,
) -> str:
    """Create deterministic atom ID from core fields."""
    content = f"{layer.value}|{slot.value}|{discourse_act.value}|{payload_ref}|{provenance}"
    return f"k1_{hashlib.sha256(content.encode()).hexdigest()[:12]}"


def create_atom(
    layer: OntologicalLayer,
    slot: K1Slot,
    discourse_act: DiscourseAct,
    payload_ref: str,
    provenance: str,
) -> K1Atom:
    """Create K1Atom with auto-generated atom_id."""
    atom_id = create_atom_id(layer, slot, discourse_act, payload_ref, provenance)
    return K1Atom(
        atom_id=atom_id,
        layer=layer,
        slot=slot,
        discourse_act=discourse_act,
        payload_ref=payload_ref,
        provenance=provenance,
    )


# =============================================================================
# K1 Query
# =============================================================================

@dataclass(frozen=True)
class K1Query:
    """
    Deterministic retrieval request.

    Primary index: (layer, slot, discourse_act)

    INVARIANT: Same query over same store state returns same ordered results.
    """
    # Focus (all optional for flexible querying)
    layer: Optional[OntologicalLayer] = None
    slot: Optional[K1Slot] = None
    discourse_act: Optional[DiscourseAct] = None

    # Additional constraints
    slot_tiers: Optional[FrozenSet[K1SlotTier]] = None
    discourse_act_tiers: Optional[FrozenSet[DiscourseActTier]] = None
    provenance_pattern: Optional[str] = None  # Exact match

    # Limit
    limit: int = 100

    # Ordering
    selection_rule: SelectionRule = SelectionRule.LEXICOGRAPHIC_ID

    def query_hash(self) -> str:
        """Compute deterministic hash of query."""
        slot_tiers_str = (
            "_".join(sorted(t.value for t in self.slot_tiers))
            if self.slot_tiers else "none"
        )
        act_tiers_str = (
            "_".join(sorted(t.value for t in self.discourse_act_tiers))
            if self.discourse_act_tiers else "none"
        )

        content = (
            f"layer:{self.layer.value if self.layer else 'any'}|"
            f"slot:{self.slot.value if self.slot else 'any'}|"
            f"act:{self.discourse_act.value if self.discourse_act else 'any'}|"
            f"slot_tiers:{slot_tiers_str}|"
            f"act_tiers:{act_tiers_str}|"
            f"prov:{self.provenance_pattern or 'any'}|"
            f"limit:{self.limit}|"
            f"rule:{self.selection_rule.value}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def matches(self, atom: K1Atom) -> bool:
        """Check if an atom matches this query's constraints."""
        # Check layer
        if self.layer is not None and atom.layer != self.layer:
            return False

        # Check slot
        if self.slot is not None and atom.slot != self.slot:
            return False

        # Check discourse act
        if self.discourse_act is not None and atom.discourse_act != self.discourse_act:
            return False

        # Check slot tiers
        if self.slot_tiers is not None and atom.get_slot_tier() not in self.slot_tiers:
            return False

        # Check discourse act tiers
        if self.discourse_act_tiers is not None and atom.get_discourse_act_tier() not in self.discourse_act_tiers:
            return False

        # Check provenance pattern (exact match)
        if self.provenance_pattern is not None and atom.provenance != self.provenance_pattern:
            return False

        return True


# =============================================================================
# Retrieval Step (for replay proof)
# =============================================================================

@dataclass(frozen=True)
class RetrievalStep:
    """Single step in retrieval process (for audit trail)."""
    step_type: str          # "index_lookup", "filter", "sort", "limit"
    input_count: int        # Atoms before this step
    output_count: int       # Atoms after this step
    step_hash: str          # Hash of step parameters


# =============================================================================
# K1 Result Set
# =============================================================================

@dataclass(frozen=True)
class K1ResultSet:
    """
    Returned atoms + proof metadata.

    INVARIANT: result_hash is deterministic from query + atoms.
    """
    # Results
    atoms: Tuple[K1Atom, ...]

    # Proof
    query_hash: str
    result_hash: str

    # Ledger
    ledger_span_id: str
    store_version_id: str

    # Replay proof
    replay_proof: Tuple[RetrievalStep, ...] = ()

    def is_empty(self) -> bool:
        """Check if result set is empty."""
        return len(self.atoms) == 0

    def count(self) -> int:
        """Get number of atoms in result set."""
        return len(self.atoms)

    def get_atom_ids(self) -> Tuple[str, ...]:
        """Get ordered list of atom IDs."""
        return tuple(a.atom_id for a in self.atoms)


def compute_result_hash(query_hash: str, atom_ids: Tuple[str, ...]) -> str:
    """Compute deterministic result hash."""
    content = f"{query_hash}|{'_'.join(atom_ids)}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# Constants
# =============================================================================

# All slots
ALL_SLOTS: Tuple[K1Slot, ...] = tuple(K1Slot)

# Core slots (Tier 1)
CORE_SLOTS: Tuple[K1Slot, ...] = get_tier_slots(K1SlotTier.TIER_1_CORE)

# All layers
ALL_LAYERS: Tuple[OntologicalLayer, ...] = tuple(OntologicalLayer)

# All discourse acts
ALL_DISCOURSE_ACTS: Tuple[DiscourseAct, ...] = tuple(DiscourseAct)


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Slot Enums
    "K1SlotTier",
    "K1Slot",
    # Layer Enum
    "OntologicalLayer",
    # Discourse Act Enums
    "DiscourseActTier",
    "DiscourseAct",
    # Selection Rule
    "SelectionRule",
    # Data classes
    "K1EntityRef",
    "K1Atom",
    "K1Query",
    "RetrievalStep",
    "K1ResultSet",
    # Functions
    "get_slot_tier",
    "get_tier_slots",
    "get_discourse_act_tier",
    "create_atom_id",
    "create_atom",
    "compute_result_hash",
    # Constants
    "SLOT_TIER",
    "DISCOURSE_ACT_TIER",
    "ALL_SLOTS",
    "CORE_SLOTS",
    "ALL_LAYERS",
    "ALL_DISCOURSE_ACTS",
]
