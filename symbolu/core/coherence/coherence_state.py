"""
CoherenceState - Conversation-level coherence state vector (CSV).

Tracks multi-turn coherence across conversation history with sliding window.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class CoherenceState:
    """
    Multi-turn coherence state vector tracking conversation-level coherence.

    Maintains sliding-window histories of:
    - Routing tiers and domains
    - Mapper profiles
    - SMI (authenticity/tension) indices
    - Bhava states and directions
    - Temporal flags and tension levels

    Derives coherence metrics:
    - persona_drift_score: 0.0-1.0 (higher = more drift)
    - semantic_stability_score: 0.0-1.0 (higher = more stable)
    - mapper_volatility_score: 0.0-1.0 (higher = more volatile)
    - temporal_arc_score: 0.0-1.0 (higher = better arc)
    - coherence_score: 0.0-1.0 (overall, higher = better)
    """

    convo_id: str
    turn_index: int

    # Histories (most recent last) - sliding window
    tier_history: List[str] = field(default_factory=list)  # "lower" | "hybrid" | "upper"
    domain_history: List[str] = field(default_factory=list)  # "task" | "finance" | "therapy" | ...
    mapper_profile_history: List[Dict] = field(default_factory=list)  # MapperProfile snapshots
    smi_history: List[float] = field(default_factory=list)  # authenticity/tension per turn
    bhava_id_history: List[int] = field(default_factory=list)  # bhava per turn
    bhava_direction_history: List[str] = field(default_factory=list)  # "upward" | "downward" | "stable"
    tension_history: List[float] = field(default_factory=list)  # long_arc_tension per turn
    temporal_flags_history: List[Dict[str, bool]] = field(default_factory=list)  # temporal flags per turn

    # Phase 1 formula histories (passive observation - not used in scoring yet)
    delta_smi_history: List[Optional[float]] = field(default_factory=list)  # ΔSMI per turn
    bhava_gap_history: List[Optional[float]] = field(default_factory=list)  # Bhava gap per turn
    tension_corridor_history: List[Optional[float]] = field(default_factory=list)  # Tension corridor per turn

    # Phase 14 formula histories (observation only - not used in scoring)
    vritti_momentum_history: List[Optional[float]] = field(default_factory=list)  # Vritti Momentum per turn
    arc_tension_harmonizer_history: List[Optional[float]] = field(default_factory=list)  # Arc-Tension Harmonizer per turn

    # Phase 2 formula aggregates (observation only - not used in scoring)
    avg_smi: Optional[float] = None  # Average SMI across session
    max_smi: Optional[float] = None  # Maximum SMI observed
    min_smi: Optional[float] = None  # Minimum SMI observed
    avg_tension_corridor: Optional[float] = None  # Average tension corridor
    max_tension_corridor: Optional[float] = None  # Maximum tension corridor

    # Phase 14 formula aggregates (observation only - not used in scoring)
    avg_vritti_momentum: Optional[float] = None  # Average Vritti Momentum
    max_vritti_momentum: Optional[float] = None  # Maximum Vritti Momentum
    min_vritti_momentum: Optional[float] = None  # Minimum Vritti Momentum
    avg_arc_tension_harmonizer: Optional[float] = None  # Average Arc-Tension Harmonizer
    max_arc_tension_harmonizer: Optional[float] = None  # Maximum Arc-Tension Harmonizer
    min_arc_tension_harmonizer: Optional[float] = None  # Minimum Arc-Tension Harmonizer

    # Phase 3 derived formula metrics (observation only - not used in scoring)
    resonance_index: Optional[float] = None  # [0.0, 1.0] - formula-weighted stabilizing signal
    tension_index: Optional[float] = None  # [0.0, 1.0] - session tension from Tension Corridor
    arc_alignment_index: Optional[float] = None  # [0.0, 1.0] - temporal pattern alignment

    # Derived metrics (0.0-1.0)
    persona_drift_score: float = 0.0  # Higher = more drift (worse)
    semantic_stability_score: float = 0.0  # Higher = more stable (better)
    mapper_volatility_score: float = 0.0  # Higher = more volatile (worse)
    temporal_arc_score: float = 0.0  # Higher = better arc (better)

    # Overall coherence score (0.0-1.0, higher = better)
    coherence_score: float = 0.0  # v1 canonical (always used)

    # Phase 4: Formula-aware coherence v2 (optional, feature-flag gated)
    coherence_score_v2: Optional[float] = None  # v2 formula-aware (optional)

    # Phase 10: Coherence v3 megafusion (experimental, disabled by default)
    coherence_score_v3: Optional[float] = None  # v3 formula megafusion (optional)

    # Phase 12: Coherence v3 quality metric (soft stability windows)
    coherence_v3_quality: Optional[float] = None  # [0.0, 1.0] - soft quality metric for v3 gating

    # Phase 8: Guna/Kosha resonance metrics (observation only - not used in scoring)
    guna_resonance_index: Optional[float] = None  # [0.0, 1.0] - Guna balance/distortion measure
    kosha_resonance_index: Optional[float] = None  # [0.0, 1.0] - Kosha coherence measure
    kosha_activation_vector: Optional[List[float]] = None  # Ordered kosha activation values

    def window_trim(self, window: int) -> None:
        """
        Trim all histories to sliding window size.

        Args:
            window: Maximum history length to retain (most recent entries)
        """
        if window <= 0:
            return

        self.tier_history = self.tier_history[-window:]
        self.domain_history = self.domain_history[-window:]
        self.mapper_profile_history = self.mapper_profile_history[-window:]
        self.smi_history = self.smi_history[-window:]
        self.bhava_id_history = self.bhava_id_history[-window:]
        self.bhava_direction_history = self.bhava_direction_history[-window:]
        self.tension_history = self.tension_history[-window:]
        self.temporal_flags_history = self.temporal_flags_history[-window:]

        # Phase 1 formula histories
        self.delta_smi_history = self.delta_smi_history[-window:]
        self.bhava_gap_history = self.bhava_gap_history[-window:]
        self.tension_corridor_history = self.tension_corridor_history[-window:]

        # Phase 14 formula histories
        self.vritti_momentum_history = self.vritti_momentum_history[-window:]
        self.arc_tension_harmonizer_history = self.arc_tension_harmonizer_history[-window:]

    def get_history_length(self) -> int:
        """
        Get the current history length (based on domain_history as reference).

        Returns:
            Current number of turns in history
        """
        return len(self.domain_history)
