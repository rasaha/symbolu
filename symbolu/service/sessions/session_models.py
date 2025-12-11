"""
Symbol-U Session Models (Deterministic)

This module defines data models for multi-turn session management.
It enables DILchat and enterprise clients to run conversations with preserved:
- Coherence state
- Temporal tracker state
- Mapper history (HRM, LCM, LAM)
- Domain continuity
- Routing / tier transitions
- Unified output accumulation

Design Principles:
    1. Zero-LLM (fully deterministic)
    2. Non-invasive (does not modify pipeline behavior)
    3. In-memory storage (no external dependencies)
    4. Preserves complete turn-by-turn state
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from datetime import datetime


@dataclass
class SessionState:
    """
    Container for all state accumulated across multiple conversation turns.

    This is the primary storage model for a single session. Each turn appends
    new data to the history lists, enabling trend analysis and coherence tracking.

    Attributes:
        session_id: Unique session identifier (UUID4)
        created_at: UTC timestamp when session was created
        domain: Domain context for the session (e.g., "generic", "trading", "therapy")
        coherence_history: List of coherence states from each turn
        temporal_history: List of temporal arc states from each turn
        routing_history: List of routing/tier decisions from each turn
        mapper_history: List of mapper outputs (HRM/LCM/LAM) from each turn
        turns: Complete list of unified outputs from each turn
    """
    session_id: str
    created_at: datetime
    domain: str = "generic"

    # Rolling state accumulators
    coherence_history: List[Dict[str, Any]] = field(default_factory=list)
    temporal_history: List[Dict[str, Any]] = field(default_factory=list)
    routing_history: List[Dict[str, Any]] = field(default_factory=list)
    mapper_history: List[Dict[str, Any]] = field(default_factory=list)
    turns: List[Dict[str, Any]] = field(default_factory=list)

    # Session memory (episodic memory v2.0)
    session_memory: Optional["SessionMemory"] = None


@dataclass
class SessionSummary:
    """
    Aggregated statistics and trends for a session.

    This is computed on-demand from SessionState to provide:
    - Turn count
    - Average coherence trends
    - Persona drift detection
    - Temporal arc patterns
    - Semantic stability metrics
    - Mapper volatility tracking
    - Last routing state

    Attributes:
        session_id: Session identifier
        total_turns: Number of turns completed
        coherence_trend: Average coherence score across all turns
        persona_drift_avg: Average persona drift/change across turns
        temporal_arc_avg: Average temporal arc score across turns
        semantic_stability_score: Average semantic stability (lower = more drift)
        mapper_volatility_score: Volatility in mapper outputs (HRM/LCM/LAM changes)
        last_tier: Last MLCR tier selected (UPPER/LOWER/HYBRID)
        last_domain: Last detected domain
        created_at: Session creation timestamp
    """
    session_id: str
    total_turns: int
    coherence_trend: float
    persona_drift_avg: float
    temporal_arc_avg: float
    semantic_stability_score: float = 0.5
    mapper_volatility_score: float = 0.5
    last_tier: str = "HYBRID"
    last_domain: str = "generic"
    created_at: Optional[datetime] = None

    # Phase 19: Drift Fusion aggregates (observation only)
    avg_drift_fusion_index: Optional[float] = None
    dominant_drift_risk_band: Optional[str] = None
    drift_pattern_frequency: Dict[str, int] = field(default_factory=dict)

    # Convenience properties for policy layer compatibility
    @property
    def coherence_score(self) -> float:
        """Alias for coherence_trend for policy layer compatibility."""
        return self.coherence_trend

    @property
    def persona_drift_score(self) -> float:
        """Alias for persona_drift_avg for policy layer compatibility."""
        return self.persona_drift_avg

    @property
    def temporal_arc_score(self) -> float:
        """Alias for temporal_arc_avg for policy layer compatibility."""
        return self.temporal_arc_avg

    @property
    def turn_count(self) -> int:
        """Alias for total_turns for policy layer compatibility."""
        return self.total_turns

    # Memory v2.0 fields (timelines for event detection)
    coherence_timeline: List[float] = field(default_factory=list)
    temporal_arc_timeline: List[float] = field(default_factory=list)
    mapper_sets: List[Set[str]] = field(default_factory=list)

    @property
    def last_mapper_set(self) -> Set[str]:
        """Get the most recent mapper set."""
        return self.mapper_sets[-1] if self.mapper_sets else set()

    # Phase 2 formula aggregates (observation only)
    avg_smi: Optional[float] = None  # Average SMI across session
    net_delta_smi: Optional[float] = None  # Net ΔSMI (cumulative change)
    avg_bhava_gap: Optional[float] = None  # Average bhava gap
    avg_tension_corridor: Optional[float] = None  # Average tension corridor

    # Phase 3 derived formula metrics (observation only)
    avg_resonance_index: Optional[float] = None  # Average resonance index across session
    avg_tension_index: Optional[float] = None  # Average tension index across session
    avg_arc_alignment_index: Optional[float] = None  # Average arc alignment index across session

    # Phase 8 Guna/Kosha resonance metrics (observation only)
    avg_guna_resonance: Optional[float] = None  # Average Guna resonance index across session
    avg_kosha_resonance: Optional[float] = None  # Average Kosha resonance index across session

    # Phase 14 Vritti Momentum & Arc-Tension Harmonizer (observation only)
    avg_vritti_momentum: Optional[float] = None  # Average Vritti Momentum across session
    max_vritti_momentum: Optional[float] = None  # Maximum Vritti Momentum observed
    min_vritti_momentum: Optional[float] = None  # Minimum Vritti Momentum observed
    avg_arc_tension_harmonizer: Optional[float] = None  # Average Arc-Tension Harmonizer across session
    max_arc_tension_harmonizer: Optional[float] = None  # Maximum Arc-Tension Harmonizer observed
    min_arc_tension_harmonizer: Optional[float] = None  # Minimum Arc-Tension Harmonizer observed

    # Phase 18 Temporal Entropy Differential (observation only)
    avg_temporal_entropy_diff: Optional[float] = None  # Average normalized entropy diff [0.0, 1.0]
    avg_temporal_entropy_volatility: Optional[float] = None  # Average entropy volatility [0.0, 1.0]
    temporal_entropy_regime: Optional[str] = None  # "stable" | "transition" | "volatile"

    # Phase 21 Mirror-Time Loop (observation only)
    avg_loop_alignment: Optional[float] = None  # Average loop alignment [0.0, 1.0]
    avg_loop_tension: Optional[float] = None  # Average loop tension [0.0, 1.0]
    avg_reversal_probability: Optional[float] = None  # Average reversal probability [0.0, 1.0]
    dominant_loop_stability_band: Optional[str] = None  # "stable" | "transitional" | "unstable"
    reversal_probability_trend: Optional[str] = None  # "increasing" | "decreasing" | "stable"

    # Phase 22 Mirror-Time Cycles (observation only)
    dominant_cycle_type: Optional[str] = None  # Most common cycle type: "converging" | "diverging" | "oscillating" | "stalled"
    dominant_cycle_stability_band: Optional[str] = None  # Most common stability band: "stable" | "transitional" | "unstable"
    avg_cycle_alignment: Optional[float] = None  # Average alignment across cycles [0.0, 1.0]
    avg_cycle_tension: Optional[float] = None  # Average tension across cycles [0.0, 1.0]
    avg_cycle_reversal_probability: Optional[float] = None  # Average reversal probability across cycles [0.0, 1.0]
    cycle_count: int = 0  # Total number of cycles detected in session

    # Phase 23 Cause-Effect Inversion Analytics (observation only)
    avg_inversion_score: Optional[float] = None  # Average inversion score [0.0, 1.0]
    dominant_inversion_band: Optional[str] = None  # Most common inversion band: "forward_dominant" | "ambiguous" | "inversion_plausible" | "inversion_dominant"
    cause_chain_stability_avg: Optional[float] = None  # Average cause-chain stability [0.0, 1.0]
    inversion_pattern_tags: List[str] = field(default_factory=list)  # Collected diagnostic tags

    # Phase 24 Resonance Weighting Function (observation only)
    avg_resonance_entropy: Optional[float] = None  # Average resonance entropy [0.0, 1.0]
    dominant_resonance_metrics: List[str] = field(default_factory=list)  # Top metrics by normalized weight
    resonance_weighting_notes: List[str] = field(default_factory=list)  # Collected diagnostic notes

    # Phase 26 Unified Consciousness Formula (observation only)
    avg_coi: Optional[float] = None  # Average Consciousness Order Index [0.0, 1.0]
    avg_csi: Optional[float] = None  # Average Consciousness Stability Index [0.0, 1.0]
    avg_cip: Optional[float] = None  # Average Consciousness Integration Potential [0.0, 1.0]
    ucf_entropy_band: Optional[str] = None  # "focused" | "balanced" | "diffuse"
    dominant_ucf_signals: List[str] = field(default_factory=list)  # Top 3 weighted metric keys
    ucf_notes: List[str] = field(default_factory=list)  # Collected UCF diagnostic summaries

    # Phase 27 Symbolic Harmonization Formula (observation only)
    avg_symbolic_harmonization: Optional[float] = None  # Average Symbolic Harmonization Index [0.0, 1.0]
    dominant_symbolic_harmonization_pattern: Optional[str] = None  # "high_harmony" | "medium_harmony" | "low_harmony"
    symbolic_harmonization_notes: List[str] = field(default_factory=list)  # Collected SHF diagnostic notes

    # Phase 34 Identity Harmonics Layer (observation only)
    avg_core_identity_harmonic: Optional[float] = None  # Average CIH [0.0, 1.0]
    avg_adaptive_identity_harmonic: Optional[float] = None  # Average AIH [0.0, 1.0]
    avg_relational_identity_harmonic: Optional[float] = None  # Average RIH [0.0, 1.0]
    avg_identity_harmonics_index: Optional[float] = None  # Average IHI [0.0, 1.0]
    identity_harmonics_pattern: Optional[str] = None  # "converging" | "balanced" | "diverging"
    identity_harmonics_notes: List[str] = field(default_factory=list)  # Collected IHL diagnostic notes

    # Phase 35 Predictive Persona Drift Model (observation only)
    avg_predicted_drift_magnitude: Optional[float] = None  # Average predicted drift magnitude [0.0, 1.0]
    avg_predicted_drift_stability: Optional[float] = None  # Average drift stability score [0.0, 1.0]
    dominant_drift_band: Optional[str] = None  # Most common drift band: "LOW" | "MEDIUM" | "HIGH"
    drift_prediction_notes: List[str] = field(default_factory=list)  # Collected PPDM diagnostic notes

    # Phase 36 Identity Resonance Memory (observation only)
    avg_ims: Optional[float] = None  # Average Identity Memory Strength [0.0, 1.0]
    avg_iep: Optional[float] = None  # Average Identity Echo Persistence [0.0, 1.0]
    avg_ida: Optional[float] = None  # Average Identity Drift Anchoring [0.0, 1.0]
    dominant_memory_band: Optional[str] = None  # Most common memory band: "LOW" | "MEDIUM" | "HIGH"
    aggregated_memory_tags: List[str] = field(default_factory=list)  # Collected IRM diagnostic tags

    # Phase 41 Coherence-Regime Scenario Mapper (observation only)
    dominant_coherence_regime: Optional[str] = None  # Most frequent coherence regime
    regime_band: Optional[str] = None  # Most frequent regime band: "stable" | "mixed" | "volatile"
    regime_frequency: Dict[str, int] = field(default_factory=dict)  # Regime name → occurrence count
    regime_notes: List[str] = field(default_factory=list)  # Collected regime notes (deduped)

    # Phase 42 Scenario Fusion Engine (observation only)
    avg_scenario_alignment: Optional[float] = None  # Average scenario alignment score [0.0, 1.0]
    avg_scenario_divergence: Optional[float] = None  # Average scenario divergence index [0.0, 1.0]
    scenario_uncertainty_band: Optional[str] = None  # Most frequent uncertainty band: "low" | "medium" | "high"
    dominant_fused_future_path: Optional[str] = None  # Most frequent dominant future path (regime)
    scenario_pattern_tags: List[str] = field(default_factory=list)  # Collected scenario pattern tags (deduped, sorted)

    # Phase 44 Coherence–Scenario Alignment Engine (observation only)
    avg_csae_alignment: Optional[float] = None  # Average alignment score [0.0, 1.0]
    avg_csae_conflict: Optional[float] = None  # Average conflict index [0.0, 1.0]
    avg_csae_stability: Optional[float] = None  # Average stability agreement [0.0, 1.0]
    csae_alignment_band: Optional[str] = None  # Most frequent alignment band: "high" | "medium" | "low" | "conflict"
    csae_alignment_tags: List[str] = field(default_factory=list)  # Collected CSAE diagnostic tags (deduped, sorted)

    # Phase 45 Multi-Trajectory Stability Field (observation only)
    avg_tsi: float = 0.0  # Average Trajectory Stability Index [0.0, 1.0]
    avg_tvi: float = 0.0  # Average Trajectory Volatility Index [0.0, 1.0]
    avg_chf: float = 0.0  # Average Cross-Horizon Flux [0.0, 1.0]
    avg_scc: float = 0.0  # Average Scenario-Coherence Coupling [0.0, 1.0]
    mtsf_band: Optional[str] = None  # Most frequent stability band: "HIGH" | "MEDIUM" | "LOW" | "CHAOTIC"
    mtsf_tags: List[str] = field(default_factory=list)  # Collected MTSF diagnostic tags (deduped, sorted)

    # Phase 46 Trajectory Field Convergence Engine (observation only)
    avg_trajectory_convergence: Optional[float] = None  # Average convergence index [0.0, 1.0]
    avg_trajectory_divergence: Optional[float] = None  # Average divergence index [0.0, 1.0]
    avg_trajectory_stability: Optional[float] = None  # Average stability index [0.0, 1.0]
    dominant_convergence_band: Optional[str] = None  # Most frequent convergence band: "high" | "medium" | "low" | "fragmented"
    dominant_convergence_tags: List[str] = field(default_factory=list)  # Collected TFCE diagnostic tags (deduped, sorted)

    # Phase 47 Unified Trajectory–Scenario Synthesis Engine (observation only)
    avg_synthesis_integrity: Optional[float] = None  # Average synthesis integrity score [0.0, 1.0]
    avg_future_alignment: Optional[float] = None  # Average future state alignment score [0.0, 1.0]
    avg_future_divergence_risk: Optional[float] = None  # Average future divergence risk [0.0, 1.0]
    dominant_synthesis_band: Optional[str] = None  # Most frequent synthesis band: "HIGH" | "MEDIUM" | "LOW" | "FRAGMENTED"
    synthesis_tags: List[str] = field(default_factory=list)  # Collected UTSSE diagnostic tags (deduped, sorted)

    # Phase 48 Macro-Stability Regulator (observation only)
    avg_macro_stability: Optional[float] = None  # Average macro-stability index [0.0, 1.0]
    avg_macro_divergence: Optional[float] = None  # Average macro-divergence index [0.0, 1.0]
    avg_macro_predictive_confidence: Optional[float] = None  # Average macro-predictive confidence [0.0, 1.0]
    avg_macro_identity_resilience: Optional[float] = None  # Average macro-identity resilience [0.0, 1.0]
    dominant_macro_stability_band: Optional[str] = None  # Most frequent stability band: "high" | "medium" | "low" | "fragmented"
    macro_stability_tags: List[str] = field(default_factory=list)  # Collected MSR diagnostic tags (deduped, sorted)
