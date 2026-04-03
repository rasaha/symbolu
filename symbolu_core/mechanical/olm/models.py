"""
OLM v1.0 Models Module

Defines data models for the Ontological Layer Mapper:
- OLMInput: Input context for OLM processing
- OntologicalLayerMap: Output ontological layer map

5+5 Ontological Layer Architecture (Patent-Aligned):

Lower 5 — Execution / Manifestation Layers:
    O1 — Action: Immediate execution pressure; raw acts and impulses
    O2 — Tagging: Classification and labeling; assigns type without meaning
    O3 — Forming: Structural shaping and pattern formation; core compositional layer
    O4 — Thinking: Rule-based internal transformation; mechanical manipulation only
    O5 — Directing: Trajectory steering and vector control; not purpose or intent

Upper 5 — Governance / Coherence Layers:
    O6 — Reasoning: Logical consistency and admissibility checks; no inference
    O7 — Purposing: Constraint alignment toward targets (Phase-7); not semantic "why"
    O8 — Meta-Observing: Witness layer; damping, stabilization, distortion exposure
    O9 — Unifying: Integration and coherence across structures; contradiction removal
    O10 — Absolving: Termination, dissolution, or release; final system boundary

Key Architectural Principles (Do Not Violate):
- There is no active/passive mode
- There is no controller deciding when layers engage
- All layers exist simultaneously
- Behavior emerges from ontological placement + constraints
- Upper layers never generate, only constrain or terminate
- The system is deterministic, non-semantic, and non-learning

All models are immutable dataclasses for deterministic processing.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Final, Tuple

# =============================================================================
# ONTOLOGICAL LAYER CONSTANTS (Patent-Aligned)
# =============================================================================

# Lower 5 — Execution / Manifestation Layers (O1-O5)
LOWER_ONTOLOGICAL_LAYERS: Final[Tuple[str, ...]] = (
    "O1_action",       # Immediate execution pressure; raw acts and impulses
    "O2_tagging",      # Classification and labeling; assigns type without meaning
    "O3_forming",      # Structural shaping and pattern formation
    "O4_thinking",     # Rule-based internal transformation; mechanical only
    "O5_directing",    # Trajectory steering and vector control
)

# Upper 5 — Governance / Coherence Layers (O6-O10)
UPPER_ONTOLOGICAL_LAYERS: Final[Tuple[str, ...]] = (
    "O6_reasoning",      # Logical consistency and admissibility checks
    "O7_purposing",      # Constraint alignment toward targets (Phase-7)
    "O8_meta_observing", # Witness layer; damping, stabilization
    "O9_unifying",       # Integration and coherence; contradiction removal
    "O10_absolving",     # Termination, dissolution, or release
)

# All ontological layers (O1-O10)
ALL_ONTOLOGICAL_LAYERS: Final[Tuple[str, ...]] = (
    LOWER_ONTOLOGICAL_LAYERS + UPPER_ONTOLOGICAL_LAYERS
)

# Layer descriptions for documentation
LAYER_DESCRIPTIONS: Final[Dict[str, str]] = {
    "O1_action": "Immediate execution pressure; raw acts and impulses",
    "O2_tagging": "Classification and labeling; assigns type without meaning",
    "O3_forming": "Structural shaping and pattern formation; core compositional layer",
    "O4_thinking": "Rule-based internal transformation; mechanical manipulation only",
    "O5_directing": "Trajectory steering and vector control; not purpose or intent",
    "O6_reasoning": "Logical consistency and admissibility checks; no inference",
    "O7_purposing": "Constraint alignment toward targets (Phase-7); not semantic 'why'",
    "O8_meta_observing": "Witness layer; damping, stabilization, distortion exposure",
    "O9_unifying": "Integration and coherence across structures; contradiction removal",
    "O10_absolving": "Termination, dissolution, or release; final system boundary",
}

# Mapping from legacy aspect names to ontological layers (for compatibility)
LEGACY_ASPECT_TO_LAYER: Final[Dict[str, str]] = {
    "Execution": "O1_action",
    "Identity": "O2_tagging",
    "Form": "O3_forming",
    "Cognition": "O4_thinking",
    "Agency": "O5_directing",
    "Reasoning": "O6_reasoning",
    "Purpose": "O7_purposing",
    "Observation": "O8_meta_observing",
    "Core": "O9_unifying",
    "Universal": "O10_absolving",
}

# Reverse mapping for output compatibility
LAYER_TO_LEGACY_ASPECT: Final[Dict[str, str]] = {
    v: k for k, v in LEGACY_ASPECT_TO_LAYER.items()
}


@dataclass(frozen=True)
class OLMInput:
    """
    Input context for OLM (Ontological Layer Mapper) processing.

    Contains all signals needed for building an ontological layer map:
    - Layer weights from symbolic engine (O1-O10 probabilities)
    - Experiential anchor scores
    - Entropy measures (dimensional, guna, kosha)
    - Domain and tier context
    - Flow mode specification

    Processing is constrained by ontological layer placement.
    Lower layers execute symbol dynamics; upper layers enforce
    coherence, alignment, and termination.

    Attributes:
        layer_weights: Dictionary mapping layer names to weights [0, 1].
                      Keys: O1_action through O10_absolving
                      Lower 5 (O1-O5): Execution/Manifestation
                      Upper 5 (O6-O10): Governance/Coherence
        anchor_scores: Dictionary mapping anchor names to scores [0, 1].
                      Keys: Needs, Exchange, Challenge (lower)
                            Belonging, Relation, Change, Meaning, Role, Collective (upper)
        H_D: Dimensional entropy [0, ln(10) ≈ 2.303]
        H_G: Guna entropy [0, ln(3) ≈ 1.099]
        H_K: Kosha entropy [0, ln(5) ≈ 1.609]
        domain: Domain classification (task, code, math, therapy, philosophy, etc.)
        tier: Routing tier from TTOR ("lower", "upper", "hybrid")
        flow_mode: Cognitive flow mode ("outer_only", "outer_plus_inner", "inner_priority")
    """

    layer_weights: Dict[str, float]
    anchor_scores: Dict[str, float]
    H_D: float
    H_G: float
    H_K: float
    domain: str
    tier: str
    flow_mode: str


@dataclass
class OntologicalLayerMap:
    """
    Output ontological layer map from OLM.

    Contains structured, symbolic data representing the ontological
    placement and constraint profile for downstream engines:
    - Dominant layers (high activation in the ontological hierarchy)
    - Suppressed layers (low activation)
    - Anchor profile (normalized)
    - Entropy profiling
    - Tension zone detection (between layer groups)
    - Resolution constraints

    This is a STRUCTURAL ONTOLOGY map, not a behavioral profile.
    All layers exist simultaneously; this map describes their
    relative activation states, not mode switches.

    Attributes:
        dominant_layers: Ontological layers sorted by weight (highest first).
                        Layers with weight >= threshold.
        suppressed_layers: Layers with very low weight (< threshold).
                          These receive minimal processing emphasis.
        execution_profile: Normalized Lower 5 (O1-O5) layer vector.
                          Shows relative strength of execution layers.
        governance_profile: Normalized Upper 5 (O6-O10) layer vector.
                           Shows relative strength of governance layers.
        anchor_profile: Normalized anchor vector (sums to 1.0).
                       Shows relative strength of each experiential anchor.
        entropy_profile: Entropy analysis dictionary containing:
                        - H_D_norm: Normalized dimensional entropy [0, 1]
                        - H_G_norm: Normalized guna entropy [0, 1]
                        - H_K_norm: Normalized kosha entropy [0, 1]
                        - entropy_mix: Combined weighted entropy signal [0, 1]
                        - regime: Classification ("low", "medium", "high")
        tension_zones: List of detected ontological tension labels.
                      Examples: "execution_governance_gap", "grounding_deficit"
        resolution_constraints: Deterministic constraint labels for downstream.
                               Examples: "O1_execution_pressure", "O10_termination_check"
        tier: Routing tier from input ("lower", "upper", "hybrid")
        domain: Domain classification from input
        layer_balance: Ratio of execution (O1-O5) to governance (O6-O10) activation
    """

    dominant_layers: List[str] = field(default_factory=list)
    suppressed_layers: List[str] = field(default_factory=list)
    execution_profile: Dict[str, float] = field(default_factory=dict)
    governance_profile: Dict[str, float] = field(default_factory=dict)
    anchor_profile: Dict[str, float] = field(default_factory=dict)
    entropy_profile: Dict[str, float] = field(default_factory=dict)
    tension_zones: List[str] = field(default_factory=list)
    resolution_constraints: List[str] = field(default_factory=list)
    tier: str = ""
    domain: str = ""
    layer_balance: float = 0.5

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "dominant_layers": self.dominant_layers,
            "suppressed_layers": self.suppressed_layers,
            "execution_profile": self.execution_profile,
            "governance_profile": self.governance_profile,
            "anchor_profile": self.anchor_profile,
            "entropy_profile": self.entropy_profile,
            "tension_zones": self.tension_zones,
            "resolution_constraints": self.resolution_constraints,
            "tier": self.tier,
            "domain": self.domain,
            "layer_balance": self.layer_balance,
        }

    def __repr__(self) -> str:
        """Concise representation for logging."""
        dominant = ", ".join(self.dominant_layers[:3]) if self.dominant_layers else "none"
        tensions = len(self.tension_zones)
        regime = self.entropy_profile.get("regime", "unknown")
        return (
            f"OntologicalLayerMap(tier={self.tier}, domain={self.domain}, "
            f"dominant=[{dominant}], tensions={tensions}, regime={regime}, "
            f"balance={self.layer_balance:.2f})"
        )
