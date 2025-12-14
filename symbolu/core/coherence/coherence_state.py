"""
CoherenceState - Conversation-level coherence state vector (CSV).

Tracks multi-turn coherence across conversation history with sliding window.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple


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

    # Phase 13: Enhanced SMI (observation only - not used in scoring)
    enhanced_smi_history: List[Optional[float]] = field(default_factory=list)  # Enhanced SMI per turn
    current_enhanced_smi: Optional[float] = None  # Current Enhanced SMI value
    avg_enhanced_smi: Optional[float] = None  # Average Enhanced SMI
    max_enhanced_smi: Optional[float] = None  # Maximum Enhanced SMI
    min_enhanced_smi: Optional[float] = None  # Minimum Enhanced SMI

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

    # Phase 16: Formula Fusion Stabilizer (observation only - not used in scoring)
    coherence_fused: Optional[float] = None  # [0.0, 1.0] - fused coherence score (stability-weighted blend)
    coherence_fused_history: List[Optional[float]] = field(default_factory=list)  # Fused coherence history
    fusion_stability_weight: Optional[float] = None  # [0.0, 1.0] - stability weight from variance
    fusion_inertia_factor: Optional[float] = None  # [0.5, 1.0] - temporal inertia factor
    fusion_quality_factor: Optional[float] = None  # [0.0, 1.0] - quality gating factor

    # Phase 17: Semantic Integrity & Cognitive Drift v3 (observation only - not used in scoring)
    semantic_integrity_score: Optional[float] = None  # [0.0, 1.0] - semantic coherence/self-consistency
    cognitive_drift_v3: Optional[float] = None  # [0.0, 1.0] - semantic center-of-gravity drift
    semantic_integrity_history: List[Optional[float]] = field(default_factory=list)  # Integrity history
    cognitive_drift_v3_history: List[Optional[float]] = field(default_factory=list)  # Drift history

    # Phase 17: Semantic skeleton tracking for integrity computation
    semantic_skeleton_history: List[Dict] = field(default_factory=list)  # Semantic skeleton per turn

    # Phase 17: Intent/identity tracking for drift computation
    intent_arc_history: List[Optional[str]] = field(default_factory=list)  # Intent arc per turn
    identity_signature_history: List[Optional[str]] = field(default_factory=list)  # Identity signature per turn

    # Phase 17: Detailed snapshot storage (optional, for observability)
    last_semantic_integrity_snapshot: Optional[Any] = None  # SemanticIntegritySnapshot
    last_cognitive_drift_snapshot: Optional[Any] = None  # CognitiveDriftSnapshotV3

    # Phase 18: Temporal Entropy Differential (observation only - not used in scoring)
    temporal_entropy_snapshot: Optional[Any] = None  # TemporalEntropySnapshot
    temporal_entropy_diff: Optional[float] = None  # Alias for normalized_entropy_diff [0.0, 1.0]
    temporal_entropy_volatility: Optional[float] = None  # Entropy volatility [0.0, 1.0]
    temporal_entropy_diff_history: List[Optional[float]] = field(default_factory=list)  # Diff history
    temporal_entropy_volatility_history: List[Optional[float]] = field(default_factory=list)  # Volatility history

    # Phase 19: Semantic-Temporal Drift Fusion (observation only - not used in scoring)
    drift_fusion_index: Optional[float] = None  # Current drift fusion index [0.0, 1.0]
    drift_risk_band: Optional[str] = None  # Current drift risk band: "low", "moderate", "high"
    drift_pattern_tags: List[str] = field(default_factory=list)  # Current drift pattern tags
    drift_fusion_index_history: List[Optional[float]] = field(default_factory=list)  # Drift fusion index per turn
    drift_risk_band_history: List[str] = field(default_factory=list)  # Drift risk band per turn
    drift_pattern_tags_history: List[List[str]] = field(default_factory=list)  # Drift pattern tags per turn

    # Phase 21: Mirror-Time Loop (observation only - not used in scoring)
    mirror_time_loop_snapshot: Optional[Any] = None  # MirrorTimeLoopSnapshot
    avg_loop_alignment: Optional[float] = None  # Average loop alignment [0.0, 1.0]
    avg_loop_tension: Optional[float] = None  # Average loop tension [0.0, 1.0]
    avg_reversal_probability: Optional[float] = None  # Average reversal probability [0.0, 1.0]
    loop_alignment_history: List[Optional[float]] = field(default_factory=list)  # Loop alignment history
    loop_tension_history: List[Optional[float]] = field(default_factory=list)  # Loop tension history
    reversal_probability_history: List[Optional[float]] = field(default_factory=list)  # Reversal probability history
    stability_band_history: List[Optional[str]] = field(default_factory=list)  # Stability band history

    # Phase 22: Mirror-Time Cycles (observation only - not used in scoring)
    mirror_cycle_history: List[Any] = field(default_factory=list)  # List of MirrorTimeCycleSnapshot
    dominant_cycle_type: Optional[str] = None  # Most common cycle type
    dominant_cycle_stability_band: Optional[str] = None  # Most common stability band
    avg_cycle_alignment: Optional[float] = None  # Average alignment across cycles [0.0, 1.0]
    avg_cycle_tension: Optional[float] = None  # Average tension across cycles [0.0, 1.0]
    avg_cycle_reversal_probability: Optional[float] = None  # Average reversal probability across cycles [0.0, 1.0]

    # Phase 23: Cause-Effect Inversion Analytics (observation only - not used in scoring)
    cause_effect_inversion_history: List[Optional[Any]] = field(default_factory=list)  # List of CauseEffectInversionSnapshot
    current_inversion_score: Optional[float] = None  # Current inversion score [0.0, 1.0]
    current_inversion_band: Optional[str] = None  # Current inversion band classification
    avg_inversion_score: Optional[float] = None  # Average inversion score across session [0.0, 1.0]
    cause_chain_stability_avg: Optional[float] = None  # Average cause-chain stability [0.0, 1.0]

    # Phase 24: Resonance Weighting Function (observation only - not used in scoring)
    resonance_weighting_history: List[Optional[Any]] = field(default_factory=list)  # List of ResonanceWeightingSnapshot
    resonance_weighting_entropy_history: List[Optional[float]] = field(default_factory=list)  # Entropy history
    current_resonance_weights: Optional[Dict[str, float]] = None  # Current raw weights
    current_normalized_resonance_weights: Optional[Dict[str, float]] = None  # Current normalized weights
    current_resonance_entropy: Optional[float] = None  # Current entropy [0.0, 1.0]
    dominant_resonance_metrics: List[str] = field(default_factory=list)  # Top metrics by weight

    # Phase 26: Unified Consciousness Formula (observation only - not used in scoring)
    unified_consciousness_snapshot: Optional[Any] = None  # UnifiedConsciousnessSnapshot (latest)
    ucf_history: List[Optional[Any]] = field(default_factory=list)  # List of UnifiedConsciousnessSnapshot
    current_coi: Optional[float] = None  # Consciousness Order Index [0.0, 1.0]
    current_csi: Optional[float] = None  # Consciousness Stability Index [0.0, 1.0]
    current_cip: Optional[float] = None  # Consciousness Integration Potential [0.0, 1.0]
    ucf_entropy: Optional[float] = None  # UCF weight distribution entropy [0.0, 1.0]
    ucf_notes: List[str] = field(default_factory=list)  # Current UCF diagnostic notes

    # Phase 27: Symbolic Harmonization Formula (observation only - not used in scoring)
    symbolic_harmonization_snapshot: Optional[Any] = None  # SymbolicHarmonizationSnapshot (latest)
    symbolic_harmonization_history: List[Optional[Any]] = field(default_factory=list)  # List of SymbolicHarmonizationSnapshot
    current_symbolic_harmonization_index: Optional[float] = None  # Symbolic Harmonization Index [0.0, 1.0]
    harmonization_entropy_history: List[Optional[float]] = field(default_factory=list)  # Entropy history

    # Phase 34: Identity Harmonics Layer (observation only - not used in scoring)
    identity_harmonics_snapshot: Optional[Any] = None  # IdentityHarmonicsSnapshot (latest)
    identity_harmonics_history: List[Optional[Any]] = field(default_factory=list)  # List of IdentityHarmonicsSnapshot
    current_cih: Optional[float] = None  # Core Identity Harmonic [0.0, 1.0]
    current_aih: Optional[float] = None  # Adaptive Identity Harmonic [0.0, 1.0]
    current_rih: Optional[float] = None  # Relational Identity Harmonic [0.0, 1.0]
    current_identity_harmonics_index: Optional[float] = None  # Identity Harmonics Index [0.0, 1.0]
    identity_entropy_history: List[Optional[float]] = field(default_factory=list)  # Identity entropy history
    identity_stability_history: List[Optional[float]] = field(default_factory=list)  # Identity stability history
    identity_flexibility_history: List[Optional[float]] = field(default_factory=list)  # Identity flexibility history

    # Phase 35: Predictive Persona Drift Model (observation only - not used in scoring)
    predictive_drift_snapshot: Optional[Any] = None  # PredictivePersonaDriftSnapshot (latest)
    predictive_drift_history: List[Optional[Any]] = field(default_factory=list)  # List of PredictivePersonaDriftSnapshot
    current_drift_magnitude_prediction: Optional[float] = None  # Drift Magnitude Prediction [0.0, 1.0]
    current_drift_stability_score: Optional[float] = None  # Drift Stability Score [0.0, 1.0]
    current_drift_likelihood_band: Optional[str] = None  # Drift Likelihood Band: "LOW", "MEDIUM", "HIGH"
    current_drift_direction_scores: Optional[Dict[str, float]] = None  # Drift direction scores
    drift_magnitude_history: List[Optional[float]] = field(default_factory=list)  # Drift magnitude history
    drift_stability_history: List[Optional[float]] = field(default_factory=list)  # Drift stability history
    drift_likelihood_band_history: List[Optional[str]] = field(default_factory=list)  # Drift band history

    # Phase 36: Identity Resonance Memory (observation only - not used in scoring)
    identity_resonance_memory_snapshot: Optional[Any] = None  # IdentityResonanceMemorySnapshot (latest)
    identity_resonance_memory_history: List[Optional[Any]] = field(default_factory=list)  # List of IdentityResonanceMemorySnapshot
    current_ims: Optional[float] = None  # Identity Memory Strength [0.0, 1.0]
    current_iep: Optional[float] = None  # Identity Echo Persistence [0.0, 1.0]
    current_ida: Optional[float] = None  # Identity Drift Anchoring [0.0, 1.0]
    current_irm_memory_band: Optional[str] = None  # IRM Memory Band: "LOW", "MEDIUM", "HIGH"
    current_irm_tags: List[str] = field(default_factory=list)  # Current IRM diagnostic tags
    ims_history: List[Optional[float]] = field(default_factory=list)  # Identity Memory Strength history
    iep_history: List[Optional[float]] = field(default_factory=list)  # Identity Echo Persistence history
    ida_history: List[Optional[float]] = field(default_factory=list)  # Identity Drift Anchoring history
    irm_memory_band_history: List[Optional[str]] = field(default_factory=list)  # IRM Memory Band history

    # Phase 37: Adaptive Continuity Engine (observation only - not used in scoring)
    adaptive_continuity_snapshot: Optional[Any] = None  # AdaptiveContinuitySnapshot (latest)
    adaptive_continuity_history: List[Optional[Any]] = field(default_factory=list)  # List of AdaptiveContinuitySnapshot
    current_ncc: Optional[float] = None  # Narrative Continuity Coefficient [0.0, 1.0]
    current_icc: Optional[float] = None  # Identity Continuity Coefficient [0.0, 1.0]
    current_css: Optional[float] = None  # Continuity Stability Score [0.0, 1.0]
    current_continuity_band: Optional[str] = None  # Continuity Band: "LOW", "MEDIUM", "HIGH"
    current_continuity_tags: List[str] = field(default_factory=list)  # Current continuity diagnostic tags
    ncc_history: List[Optional[float]] = field(default_factory=list)  # Narrative Continuity Coefficient history
    icc_history: List[Optional[float]] = field(default_factory=list)  # Identity Continuity Coefficient history
    css_history: List[Optional[float]] = field(default_factory=list)  # Continuity Stability Score history
    continuity_band_history: List[Optional[str]] = field(default_factory=list)  # Continuity Band history

    # Phase 38: Temporal Coherence Forecasting Model (observation only - not used in scoring)
    temporal_forecast_snapshot: Optional[Any] = None  # TemporalCoherenceForecastSnapshot (latest)
    forecast_history: List[Optional[Any]] = field(default_factory=list)  # List of TemporalCoherenceForecastSnapshot
    current_forecast_coherence_slope: Optional[float] = None  # Coherence trajectory slope [-1.0, 1.0]
    current_forecast_continuity_slope: Optional[float] = None  # Continuity trajectory slope [-1.0, 1.0]
    current_forecast_drift_influence: Optional[float] = None  # Drift influence on forecast [0.0, 1.0]
    current_forecast_entropy_forward_risk: Optional[float] = None  # Forward entropy risk [0.0, 1.0]
    current_forecast_strength: Optional[float] = None  # Forecast confidence [0.0, 1.0]
    current_forecast_band: Optional[str] = None  # Forecast Band: STRONG_UPTREND, MILD_UPTREND, NEUTRAL, etc.
    current_forecast_tags: List[str] = field(default_factory=list)  # Current forecast diagnostic tags
    forecast_band_history: List[Optional[str]] = field(default_factory=list)  # Forecast band history
    forecast_strength_history: List[Optional[float]] = field(default_factory=list)  # Forecast strength history
    drift_influence_history: List[Optional[float]] = field(default_factory=list)  # Drift influence history

    # Phase 39: Multi-Horizon Temporal Forecasting Engine (observation only - not used in scoring)
    multi_horizon_forecast_snapshot: Optional[Any] = None  # MultiHorizonForecastSnapshot (latest)
    multi_horizon_forecast_history: List[Optional[Any]] = field(default_factory=list)  # List of MultiHorizonForecastSnapshot
    # H1 (Short-Term: 1-3 turns)
    horizon_slope_H1: Optional[float] = None  # H1 coherence slope [-1.0, 1.0]
    horizon_continuity_slope_H1: Optional[float] = None  # H1 continuity slope [-1.0, 1.0]
    horizon_drift_H1: Optional[float] = None  # H1 drift risk [0.0, 1.0]
    horizon_entropy_H1: Optional[float] = None  # H1 entropy risk [0.0, 1.0]
    horizon_strength_H1: Optional[float] = None  # H1 forecast strength [0.0, 1.0]
    horizon_band_H1: Optional[str] = None  # H1 forecast band
    # H2 (Mid-Term: 4-8 turns)
    horizon_slope_H2: Optional[float] = None  # H2 coherence slope [-1.0, 1.0]
    horizon_continuity_slope_H2: Optional[float] = None  # H2 continuity slope [-1.0, 1.0]
    horizon_drift_H2: Optional[float] = None  # H2 drift risk [0.0, 1.0]
    horizon_entropy_H2: Optional[float] = None  # H2 entropy risk [0.0, 1.0]
    horizon_strength_H2: Optional[float] = None  # H2 forecast strength [0.0, 1.0]
    horizon_band_H2: Optional[str] = None  # H2 forecast band
    # H3 (Long-Term: 9-20 turns)
    horizon_slope_H3: Optional[float] = None  # H3 coherence slope [-1.0, 1.0]
    horizon_continuity_slope_H3: Optional[float] = None  # H3 continuity slope [-1.0, 1.0]
    horizon_drift_H3: Optional[float] = None  # H3 drift risk [0.0, 1.0]
    horizon_entropy_H3: Optional[float] = None  # H3 entropy risk [0.0, 1.0]
    horizon_strength_H3: Optional[float] = None  # H3 forecast strength [0.0, 1.0]
    horizon_band_H3: Optional[str] = None  # H3 forecast band
    # Cross-Horizon Analytics
    forecast_consensus_index: Optional[float] = None  # Forecast Consensus Index [0.0, 1.0]
    future_stability_envelope: Optional[float] = None  # Future Stability Envelope [0.0, 1.0]
    current_mh_forecast_tags: List[str] = field(default_factory=list)  # Current multi-horizon diagnostic tags
    # Histories
    forecast_consensus_history: List[Optional[float]] = field(default_factory=list)  # FCI history
    future_stability_envelope_history: List[Optional[float]] = field(default_factory=list)  # FSE history
    horizon_band_H1_history: List[Optional[str]] = field(default_factory=list)  # H1 band history
    horizon_band_H2_history: List[Optional[str]] = field(default_factory=list)  # H2 band history
    horizon_band_H3_history: List[Optional[str]] = field(default_factory=list)  # H3 band history

    # Phase 40: Cross-Horizon Resonance Alignment Engine (observation only - not used in scoring)
    cross_horizon_resonance_snapshot: Optional[Any] = None  # CrossHorizonResonanceSnapshot (latest)
    cross_horizon_resonance_history: List[Optional[Any]] = field(default_factory=list)  # List of CrossHorizonResonanceSnapshot
    current_has_H1: Optional[float] = None  # H1 Horizon Alignment Score [0.0, 1.0]
    current_has_H2: Optional[float] = None  # H2 Horizon Alignment Score [0.0, 1.0]
    current_has_H3: Optional[float] = None  # H3 Horizon Alignment Score [0.0, 1.0]
    current_rai: Optional[float] = None  # Resonance Alignment Index [0.0, 1.0]
    current_ifa: Optional[float] = None  # Identity–Forecast Agreement [0.0, 1.0]
    current_dft: Optional[float] = None  # Drift–Forecast Tension [0.0, 1.0]
    current_alignment_band: Optional[str] = None  # Alignment Band: "HIGH_ALIGNMENT", "MIXED_ALIGNMENT", "LOW_ALIGNMENT"
    current_chra_alignment_tags: List[str] = field(default_factory=list)  # Current CHRA diagnostic tags
    # Histories
    has_H1_history: List[Optional[float]] = field(default_factory=list)  # H1 alignment score history
    has_H2_history: List[Optional[float]] = field(default_factory=list)  # H2 alignment score history
    has_H3_history: List[Optional[float]] = field(default_factory=list)  # H3 alignment score history
    rai_history: List[Optional[float]] = field(default_factory=list)  # RAI history
    ifa_history: List[Optional[float]] = field(default_factory=list)  # IFA history
    dft_history: List[Optional[float]] = field(default_factory=list)  # DFT history
    chra_alignment_band_history: List[Optional[str]] = field(default_factory=list)  # Alignment band history

    # Phase 41: Coherence-Regime Scenario Mapper (observation only - not used in scoring)
    coherence_regime_snapshot: Optional[Any] = None  # CoherenceRegimeSnapshot (latest)
    coherence_regime_history: List[Optional[Any]] = field(default_factory=list)  # List of CoherenceRegimeSnapshot
    current_dominant_regime: Optional[str] = None  # Dominant coherence regime
    current_regime_band: Optional[str] = None  # Regime band: "stable" | "mixed" | "volatile"
    current_regime_scores: Dict[str, float] = field(default_factory=dict)  # Regime scores {regime_name: score}

    # Phase 42: Scenario Fusion Engine (observation only - not used in scoring)
    scenario_fusion_snapshot: Optional[Any] = None  # ScenarioFusionSnapshot (latest)
    scenario_alignment_history: List[Optional[float]] = field(default_factory=list)  # Scenario alignment score history
    scenario_divergence_history: List[Optional[float]] = field(default_factory=list)  # Scenario divergence index history
    scenario_uncertainty_band_history: List[Optional[str]] = field(default_factory=list)  # Future uncertainty band history
    dominant_future_path_history: List[Optional[str]] = field(default_factory=list)  # Dominant future path history

    # Phase 44: Coherence–Scenario Alignment Engine (observation only - not used in scoring)
    scenario_alignment_snapshot: Optional[Any] = None  # CoherenceScenarioAlignmentSnapshot (latest)
    scenario_alignment_score_history: List[Optional[float]] = field(default_factory=list)  # Alignment score history
    scenario_conflict_history: List[Optional[float]] = field(default_factory=list)  # Conflict index history
    scenario_stability_history: List[Optional[float]] = field(default_factory=list)  # Stability agreement history
    scenario_alignment_band_history: List[Optional[str]] = field(default_factory=list)  # Alignment band history
    scenario_tags_history: List[List[str]] = field(default_factory=list)  # Diagnostic tags history

    # Phase 45: Multi-Trajectory Stability Field (observation only - not used in scoring)
    mtsf_snapshot: Optional[Any] = None  # MultiTrajectoryStabilityFieldSnapshot (latest)
    mtsf_tsi_history: List[float] = field(default_factory=list)  # Trajectory Stability Index history
    mtsf_tvi_history: List[float] = field(default_factory=list)  # Trajectory Volatility Index history
    mtsf_chf_history: List[float] = field(default_factory=list)  # Cross-Horizon Flux history
    mtsf_scc_history: List[float] = field(default_factory=list)  # Scenario-Coherence Coupling history
    mtsf_band_history: List[str] = field(default_factory=list)  # Stability band history
    mtsf_tags_history: List[List[str]] = field(default_factory=list)  # Diagnostic tags history

    # Phase 46: Trajectory Field Convergence Engine (observation only - not used in scoring)
    trajectory_convergence_snapshot: Optional[Any] = None  # TrajectoryFieldConvergenceSnapshot (latest)
    tfce_convergence_index_history: List[float] = field(default_factory=list)  # Convergence index history
    tfce_divergence_index_history: List[float] = field(default_factory=list)  # Divergence index history
    tfce_stability_index_history: List[float] = field(default_factory=list)  # Stability index history
    tfce_convergence_band_history: List[str] = field(default_factory=list)  # Convergence band history
    tfce_dominant_signal_history: List[str] = field(default_factory=list)  # Dominant convergence signal history
    tfce_tags_history: List[List[str]] = field(default_factory=list)  # Diagnostic tags history

    # Phase 47: Unified Trajectory–Scenario Synthesis Engine (observation only - not used in scoring)
    trajectory_scenario_synthesis_snapshot: Optional[Any] = None  # UnifiedTrajectoryScenarioSnapshot (latest)
    synthesis_integrity_history: List[float] = field(default_factory=list)  # Synthesis integrity score history
    synthesis_alignment_history: List[float] = field(default_factory=list)  # Future state alignment history
    synthesis_divergence_history: List[float] = field(default_factory=list)  # Future divergence risk history
    synthesis_band_history: List[str] = field(default_factory=list)  # Synthesis band history
    synthesis_tags_history: List[List[str]] = field(default_factory=list)  # Diagnostic tags history

    # Phase 48: Macro-Stability Regulator (observation only - not used in scoring)
    macro_stability_snapshot: Optional[Any] = None  # MacroStabilitySnapshot (latest)
    macro_stability_index_history: List[float] = field(default_factory=list)  # Macro-stability index history
    macro_divergence_history: List[float] = field(default_factory=list)  # Macro-divergence index history
    macro_predictive_confidence_history: List[float] = field(default_factory=list)  # Macro-predictive confidence history
    macro_identity_resilience_history: List[float] = field(default_factory=list)  # Macro-identity resilience history
    macro_stability_band_history: List[str] = field(default_factory=list)  # Macro-stability band history
    macro_stability_tags_history: List[List[str]] = field(default_factory=list)  # Macro-stability diagnostic tags history

    # Phase 49: Unified Cross-Phase Temporal Stability Engine (observation only - not used in scoring)
    temporal_stability_snapshot: Optional[Any] = None  # UnifiedTemporalStabilitySnapshot (latest)
    temporal_stability_history: List[Optional[Any]] = field(default_factory=list)  # List of UnifiedTemporalStabilitySnapshot
    temporal_stability_band_history: List[str] = field(default_factory=list)  # Stability band history
    temporal_stability_index_history: List[float] = field(default_factory=list)  # Temporal stability index history
    temporal_stability_entropy_history: List[float] = field(default_factory=list)  # Predictive entropy history
    temporal_stability_consistency_history: List[float] = field(default_factory=list)  # Future consistency history

    # Phase 50: Cognitive Consistency Regression Engine (observation only - not used in scoring)
    cognitive_consistency_regression_snapshot: Optional[Any] = None  # CognitiveConsistencyRegressionSnapshot (latest)
    regression_stability_history: List[float] = field(default_factory=list)  # Regression Stability Index (RSI) history
    regression_alignment_history: List[float] = field(default_factory=list)  # Regression Alignment Score (CLRA) history
    regression_drift_history: List[float] = field(default_factory=list)  # Regression Drift Score (CDR) history
    regression_prr_history: List[float] = field(default_factory=list)  # Prediction Reversal Risk (PRR) history
    regression_ics_history: List[float] = field(default_factory=list)  # Internal Consistency Strength (ICS) history
    regression_band_history: List[str] = field(default_factory=list)  # Cognitive consistency band history
    regression_tags_history: List[List[str]] = field(default_factory=list)  # Cognitive consistency tags history

    # Phase 51: RAG Coherence Validation Engine (observation only - not used in scoring)
    rag_validation_snapshot: Optional[Any] = None  # RAGCoherenceValidationSnapshot (latest)
    rag_alignment_history: List[float] = field(default_factory=list)  # Evidence alignment history
    rag_conflict_history: List[float] = field(default_factory=list)  # Evidence conflict index history
    rag_stability_history: List[float] = field(default_factory=list)  # Evidence stability history
    rag_relevance_history: List[float] = field(default_factory=list)  # Context relevance history
    rag_support_history: List[float] = field(default_factory=list)  # External support density history
    rag_band_history: List[str] = field(default_factory=list)  # RAG alignment band history
    rag_tag_history: List[List[str]] = field(default_factory=list)  # RAG diagnostic tags history

    # Phase 52: Internal–External Reality Cross-Verification Engine (observation only - not used in scoring)
    internal_external_reality_snapshot: Optional[Any] = None  # InternalExternalRealityCVESnapshot (latest)
    ier_cve_alignment_history: List[float] = field(default_factory=list)  # Internal-external alignment history
    ier_cve_conflict_history: List[float] = field(default_factory=list)  # Internal-external conflict history
    ier_cve_stability_history: List[float] = field(default_factory=list)  # Stability projection history
    ier_cve_band_history: List[str] = field(default_factory=list)  # IER-CVE band history
    ier_cve_tag_history: List[List[str]] = field(default_factory=list)  # IER-CVE diagnostic tags history

    # Phase 53: External Reality Trust Calibration Engine (observation only - not used in scoring)
    external_reality_trust_snapshot: Optional[Any] = None  # ExternalRealityTrustSnapshot (latest)
    ertce_trust_score_history: List[float] = field(default_factory=list)  # External trust score history
    ertce_override_pressure_history: List[float] = field(default_factory=list)  # Internal override pressure history
    ertce_fragility_history: List[float] = field(default_factory=list)  # External signal fragility history
    ertce_resilience_history: List[float] = field(default_factory=list)  # Alignment resilience history
    ertce_decay_risk_history: List[float] = field(default_factory=list)  # Trust decay risk history
    ertce_band_history: List[str] = field(default_factory=list)  # ERTCE trust band history
    ertce_tag_history: List[List[str]] = field(default_factory=list)  # ERTCE diagnostic tags history

    # Phase 54: Action Eligibility & Commitment Boundary Engine (observation only - not used in scoring)
    action_eligibility_snapshot: Optional[Any] = None  # ActionEligibilitySnapshot (latest)
    action_eligibility_score_history: List[float] = field(default_factory=list)  # Action eligibility score history
    action_eligibility_band_history: List[str] = field(default_factory=list)  # Eligibility band history
    action_eligibility_tags_history: List[List[str]] = field(default_factory=list)  # Eligibility tags history
    internal_stability_index_history: List[float] = field(default_factory=list)  # Internal stability index history
    external_alignment_index_history: List[float] = field(default_factory=list)  # External alignment index history
    trust_confidence_index_history: List[float] = field(default_factory=list)  # Trust confidence index history
    conflict_suppression_index_history: List[float] = field(default_factory=list)  # Conflict suppression index history
    temporal_persistence_index_history: List[float] = field(default_factory=list)  # Temporal persistence index history

    # Phase 10 Extension: Acoustic Alignment Diagnostics (observer-only - NEVER influences authoritative decisions)
    # These fields store diagnostic observations from P22/P23/P24 for observability purposes only.
    # CRITICAL: These fields MUST NOT influence regime, discourse, semantics, lexical, DHA, Persona, or Renderer.
    acoustic_misalignment: bool = False  # True if acoustic-semantic misalignment detected
    acoustic_alignment_score: Optional[float] = None  # Alignment score [0.0, 1.0] from P23 (observation only)
    acoustic_pressure_band: Optional[str] = None  # Pressure band: "low" | "moderate" | "high" (observation only)
    acoustic_mismatch_tags: Tuple[str, ...] = field(default_factory=tuple)  # Mismatch tags (observation only)
    acoustic_quality_penalty_applied: bool = False  # True if quality penalty was applied (diagnostic tracking)
    acoustic_quality_penalty_amount: float = 0.0  # Amount of penalty applied [0.0, 0.05] (max 5%)

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

        # Phase 13 formula histories
        self.enhanced_smi_history = self.enhanced_smi_history[-window:]

        # Phase 16 formula histories
        self.coherence_fused_history = self.coherence_fused_history[-window:]

        # Phase 17 formula histories
        self.semantic_integrity_history = self.semantic_integrity_history[-window:]
        self.cognitive_drift_v3_history = self.cognitive_drift_v3_history[-window:]
        self.semantic_skeleton_history = self.semantic_skeleton_history[-window:]
        self.intent_arc_history = self.intent_arc_history[-window:]
        self.identity_signature_history = self.identity_signature_history[-window:]

        # Phase 18 formula histories
        self.temporal_entropy_diff_history = self.temporal_entropy_diff_history[-window:]
        self.temporal_entropy_volatility_history = self.temporal_entropy_volatility_history[-window:]

        # Phase 19 drift fusion histories
        self.drift_fusion_index_history = self.drift_fusion_index_history[-window:]
        self.drift_risk_band_history = self.drift_risk_band_history[-window:]
        self.drift_pattern_tags_history = self.drift_pattern_tags_history[-window:]

        # Phase 21 formula histories
        self.loop_alignment_history = self.loop_alignment_history[-window:]
        self.loop_tension_history = self.loop_tension_history[-window:]
        self.reversal_probability_history = self.reversal_probability_history[-window:]
        self.stability_band_history = self.stability_band_history[-window:]

        # Phase 22 cycle history
        self.mirror_cycle_history = self.mirror_cycle_history[-window:]

        # Phase 23 cause-effect inversion history
        self.cause_effect_inversion_history = self.cause_effect_inversion_history[-window:]

        # Phase 24 resonance weighting history
        self.resonance_weighting_history = self.resonance_weighting_history[-window:]
        self.resonance_weighting_entropy_history = self.resonance_weighting_entropy_history[-window:]

        # Phase 26 unified consciousness formula history
        self.ucf_history = self.ucf_history[-window:]

        # Phase 27 symbolic harmonization formula history
        self.symbolic_harmonization_history = self.symbolic_harmonization_history[-window:]
        self.harmonization_entropy_history = self.harmonization_entropy_history[-window:]

        # Phase 34 identity harmonics formula history
        self.identity_harmonics_history = self.identity_harmonics_history[-window:]
        self.identity_entropy_history = self.identity_entropy_history[-window:]
        self.identity_stability_history = self.identity_stability_history[-window:]
        self.identity_flexibility_history = self.identity_flexibility_history[-window:]

        # Phase 35 predictive persona drift formula history
        self.predictive_drift_history = self.predictive_drift_history[-window:]
        self.drift_magnitude_history = self.drift_magnitude_history[-window:]
        self.drift_stability_history = self.drift_stability_history[-window:]
        self.drift_likelihood_band_history = self.drift_likelihood_band_history[-window:]

        # Phase 36 identity resonance memory formula history
        self.identity_resonance_memory_history = self.identity_resonance_memory_history[-window:]
        self.ims_history = self.ims_history[-window:]
        self.iep_history = self.iep_history[-window:]
        self.ida_history = self.ida_history[-window:]
        self.irm_memory_band_history = self.irm_memory_band_history[-window:]

        # Phase 37 adaptive continuity engine formula history
        self.adaptive_continuity_history = self.adaptive_continuity_history[-window:]
        self.ncc_history = self.ncc_history[-window:]
        self.icc_history = self.icc_history[-window:]
        self.css_history = self.css_history[-window:]
        self.continuity_band_history = self.continuity_band_history[-window:]

        # Phase 38 temporal coherence forecasting model formula history
        self.forecast_history = self.forecast_history[-window:]
        self.forecast_band_history = self.forecast_band_history[-window:]
        self.forecast_strength_history = self.forecast_strength_history[-window:]
        self.drift_influence_history = self.drift_influence_history[-window:]

        # Phase 39 multi-horizon temporal forecasting engine formula history
        self.multi_horizon_forecast_history = self.multi_horizon_forecast_history[-window:]
        self.forecast_consensus_history = self.forecast_consensus_history[-window:]
        self.future_stability_envelope_history = self.future_stability_envelope_history[-window:]
        self.horizon_band_H1_history = self.horizon_band_H1_history[-window:]
        self.horizon_band_H2_history = self.horizon_band_H2_history[-window:]
        self.horizon_band_H3_history = self.horizon_band_H3_history[-window:]

        # Phase 40 cross-horizon resonance alignment engine formula history
        self.cross_horizon_resonance_history = self.cross_horizon_resonance_history[-window:]
        self.has_H1_history = self.has_H1_history[-window:]
        self.has_H2_history = self.has_H2_history[-window:]
        self.has_H3_history = self.has_H3_history[-window:]
        self.rai_history = self.rai_history[-window:]
        self.ifa_history = self.ifa_history[-window:]
        self.dft_history = self.dft_history[-window:]
        self.chra_alignment_band_history = self.chra_alignment_band_history[-window:]

        # Phase 41 coherence regime scenario mapper formula history
        self.coherence_regime_history = self.coherence_regime_history[-window:]

        # Phase 42 scenario fusion engine formula history
        self.scenario_alignment_history = self.scenario_alignment_history[-window:]
        self.scenario_divergence_history = self.scenario_divergence_history[-window:]
        self.scenario_uncertainty_band_history = self.scenario_uncertainty_band_history[-window:]
        self.dominant_future_path_history = self.dominant_future_path_history[-window:]

        # Phase 44 coherence scenario alignment engine formula history
        self.scenario_alignment_score_history = self.scenario_alignment_score_history[-window:]
        self.scenario_conflict_history = self.scenario_conflict_history[-window:]
        self.scenario_stability_history = self.scenario_stability_history[-window:]
        self.scenario_alignment_band_history = self.scenario_alignment_band_history[-window:]
        self.scenario_tags_history = self.scenario_tags_history[-window:]

        # Phase 45 multi-trajectory stability field formula history
        self.mtsf_tsi_history = self.mtsf_tsi_history[-window:]
        self.mtsf_tvi_history = self.mtsf_tvi_history[-window:]
        self.mtsf_chf_history = self.mtsf_chf_history[-window:]
        self.mtsf_scc_history = self.mtsf_scc_history[-window:]
        self.mtsf_band_history = self.mtsf_band_history[-window:]
        self.mtsf_tags_history = self.mtsf_tags_history[-window:]

        # Phase 46 trajectory field convergence engine formula history
        self.tfce_convergence_index_history = self.tfce_convergence_index_history[-window:]
        self.tfce_divergence_index_history = self.tfce_divergence_index_history[-window:]
        self.tfce_stability_index_history = self.tfce_stability_index_history[-window:]
        self.tfce_convergence_band_history = self.tfce_convergence_band_history[-window:]
        self.tfce_dominant_signal_history = self.tfce_dominant_signal_history[-window:]
        self.tfce_tags_history = self.tfce_tags_history[-window:]

        # Phase 47 unified trajectory scenario synthesis engine formula history
        self.synthesis_integrity_history = self.synthesis_integrity_history[-window:]
        self.synthesis_alignment_history = self.synthesis_alignment_history[-window:]
        self.synthesis_divergence_history = self.synthesis_divergence_history[-window:]
        self.synthesis_band_history = self.synthesis_band_history[-window:]
        self.synthesis_tags_history = self.synthesis_tags_history[-window:]

        # Phase 48 macro-stability regulator formula history
        self.macro_stability_index_history = self.macro_stability_index_history[-window:]
        self.macro_divergence_history = self.macro_divergence_history[-window:]
        self.macro_predictive_confidence_history = self.macro_predictive_confidence_history[-window:]
        self.macro_identity_resilience_history = self.macro_identity_resilience_history[-window:]
        self.macro_stability_band_history = self.macro_stability_band_history[-window:]
        self.macro_stability_tags_history = self.macro_stability_tags_history[-window:]

        # Phase 49 unified cross-phase temporal stability engine formula history
        self.temporal_stability_history = self.temporal_stability_history[-window:]
        self.temporal_stability_band_history = self.temporal_stability_band_history[-window:]
        self.temporal_stability_index_history = self.temporal_stability_index_history[-window:]
        self.temporal_stability_entropy_history = self.temporal_stability_entropy_history[-window:]
        self.temporal_stability_consistency_history = self.temporal_stability_consistency_history[-window:]

        # Phase 50 cognitive consistency regression engine formula history
        self.regression_stability_history = self.regression_stability_history[-window:]
        self.regression_alignment_history = self.regression_alignment_history[-window:]
        self.regression_drift_history = self.regression_drift_history[-window:]
        self.regression_prr_history = self.regression_prr_history[-window:]
        self.regression_ics_history = self.regression_ics_history[-window:]
        self.regression_band_history = self.regression_band_history[-window:]
        self.regression_tags_history = self.regression_tags_history[-window:]

        # Phase 51 RAG coherence validation engine formula history
        self.rag_alignment_history = self.rag_alignment_history[-window:]
        self.rag_conflict_history = self.rag_conflict_history[-window:]
        self.rag_stability_history = self.rag_stability_history[-window:]
        self.rag_relevance_history = self.rag_relevance_history[-window:]
        self.rag_support_history = self.rag_support_history[-window:]
        self.rag_band_history = self.rag_band_history[-window:]
        self.rag_tag_history = self.rag_tag_history[-window:]

        # Phase 52 internal-external reality cross-verification engine formula history
        self.ier_cve_alignment_history = self.ier_cve_alignment_history[-window:]
        self.ier_cve_conflict_history = self.ier_cve_conflict_history[-window:]
        self.ier_cve_stability_history = self.ier_cve_stability_history[-window:]
        self.ier_cve_band_history = self.ier_cve_band_history[-window:]
        self.ier_cve_tag_history = self.ier_cve_tag_history[-window:]

        # Phase 53 external reality trust calibration engine formula history
        self.ertce_trust_score_history = self.ertce_trust_score_history[-window:]
        self.ertce_override_pressure_history = self.ertce_override_pressure_history[-window:]
        self.ertce_fragility_history = self.ertce_fragility_history[-window:]
        self.ertce_resilience_history = self.ertce_resilience_history[-window:]
        self.ertce_decay_risk_history = self.ertce_decay_risk_history[-window:]
        self.ertce_band_history = self.ertce_band_history[-window:]
        self.ertce_tag_history = self.ertce_tag_history[-window:]

        # Phase 54 action eligibility boundary engine formula history
        self.action_eligibility_score_history = self.action_eligibility_score_history[-window:]
        self.action_eligibility_band_history = self.action_eligibility_band_history[-window:]
        self.action_eligibility_tags_history = self.action_eligibility_tags_history[-window:]
        self.internal_stability_index_history = self.internal_stability_index_history[-window:]
        self.external_alignment_index_history = self.external_alignment_index_history[-window:]
        self.trust_confidence_index_history = self.trust_confidence_index_history[-window:]
        self.conflict_suppression_index_history = self.conflict_suppression_index_history[-window:]
        self.temporal_persistence_index_history = self.temporal_persistence_index_history[-window:]

    def get_history_length(self) -> int:
        """
        Get the current history length (based on domain_history as reference).

        Returns:
            Current number of turns in history
        """
        return len(self.domain_history)
