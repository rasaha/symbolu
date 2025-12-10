"""
Coherence Observer - Non-invasive observability layer for Symbol-U coherence tracking.

This module provides deterministic, zero-LLM observation and reporting of coherence metrics.
It does not modify any core engine behavior (TTOR, MLCR, mappers, Fusion, DHA, or Renderer).

Usage:
    observer = CoherenceObserver()
    report = observer.observe(text, pipeline_context, coherence_state)
    serialized = observer.serialize()
    snapshot = observer.snapshot()
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field
import json


@dataclass
class CoherenceObservation:
    """Immutable observation snapshot of coherence metrics."""

    coherence_score: float
    persona_drift_score: float
    semantic_stability_score: float
    temporal_arc_score: float
    mapper_volatility_score: float
    turn_number: int
    tier: str
    domain: str
    active_mappers: List[str]

    # Additional context
    flow_mode: Optional[str] = None
    normalized_entropy: Optional[float] = None
    long_arc_tension: Optional[float] = None
    bhava_state: Optional[int] = None
    bhava_direction: Optional[str] = None
    smi_value: Optional[float] = None

    # Trend indicators
    is_stabilizing: bool = False
    is_recovering: bool = False
    is_volatile: bool = False

    # Phase 2 formula aggregates (observation only)
    avg_smi: Optional[float] = None
    max_smi: Optional[float] = None
    min_smi: Optional[float] = None
    avg_tension_corridor: Optional[float] = None
    max_tension_corridor: Optional[float] = None
    delta_smi: Optional[float] = None
    bhava_gap: Optional[float] = None
    tension_corridor: Optional[float] = None

    # Phase 3 derived formula metrics (observation only)
    resonance_index: Optional[float] = None
    tension_index: Optional[float] = None
    arc_alignment_index: Optional[float] = None

    # Phase 4: Formula-aware coherence v2 (observation only)
    coherence_score_v2: Optional[float] = None

    # Phase 10: Coherence v3 megafusion (experimental, observation only)
    coherence_score_v3: Optional[float] = None

    # Phase 12: Coherence v3 quality metric (soft stability windows)
    coherence_v3_quality: Optional[float] = None

    # Phase 8: Guna/Kosha resonance (observation only)
    guna_resonance_index: Optional[float] = None
    kosha_resonance_index: Optional[float] = None

    # Phase 14: Vritti Momentum & Arc-Tension Harmonizer (observation only)
    vritti_momentum: Optional[float] = None
    arc_tension_harmonizer: Optional[float] = None
    avg_vritti_momentum: Optional[float] = None
    max_vritti_momentum: Optional[float] = None
    min_vritti_momentum: Optional[float] = None
    avg_arc_tension_harmonizer: Optional[float] = None
    max_arc_tension_harmonizer: Optional[float] = None
    min_arc_tension_harmonizer: Optional[float] = None

    # Phase 16: Formula Fusion Stabilizer (observation only)
    coherence_fused: Optional[float] = None
    fusion_stability_weight: Optional[float] = None
    fusion_inertia_factor: Optional[float] = None
    fusion_quality_factor: Optional[float] = None

    # Phase 17: Semantic Integrity & Cognitive Drift v3 (observation only)
    semantic_integrity_score: Optional[float] = None
    cognitive_drift_v3: Optional[float] = None
    semantic_integrity_details: Optional[Dict[str, Any]] = None
    cognitive_drift_details: Optional[Dict[str, Any]] = None

    # Phase 18: Temporal Entropy Differential (observation only)
    temporal_entropy_diff: Optional[float] = None
    temporal_entropy_volatility: Optional[float] = None
    temporal_entropy_details: Optional[Dict[str, Any]] = None

    # Phase 21: Mirror-Time Loop (observation only)
    loop_alignment: Optional[float] = None
    loop_tension: Optional[float] = None
    reversal_probability: Optional[float] = None
    stability_band: Optional[str] = None
    forward_vector: Optional[float] = None
    mirror_vector: Optional[float] = None
    loop_delta: Optional[float] = None
    avg_loop_alignment: Optional[float] = None
    avg_loop_tension: Optional[float] = None
    avg_reversal_probability: Optional[float] = None

    # Phase 22: Mirror-Time Cycles (observation only)
    mirror_cycle_dominant_type: Optional[str] = None
    mirror_cycle_dominant_stability_band: Optional[str] = None
    mirror_cycle_count: Optional[int] = None
    mirror_cycle_avg_alignment: Optional[float] = None
    mirror_cycle_avg_tension: Optional[float] = None
    mirror_cycle_avg_reversal_probability: Optional[float] = None

    # Phase 23: Cause-Effect Inversion Analytics (observation only)
    cause_effect_inversion: Optional[Any] = None  # CauseEffectInversionSnapshot
    inversion_score: Optional[float] = None
    inversion_band: Optional[str] = None
    cause_chain_stability: Optional[float] = None
    forward_alignment: Optional[float] = None
    mirror_alignment: Optional[float] = None
    inversion_notes: Optional[List[str]] = None

    # Phase 24: Resonance Weighting Function (observation only)
    resonance_weighting: Optional[Any] = None  # ResonanceWeightingSnapshot
    resonance_entropy: Optional[float] = None
    dominant_resonance_metrics: List[str] = field(default_factory=list)

    # Phase 26: Unified Consciousness Formula (observation only)
    unified_consciousness: Optional[Any] = None  # UnifiedConsciousnessSnapshot
    consciousness_order_index: Optional[float] = None  # COI [0.0, 1.0]
    consciousness_stability_index: Optional[float] = None  # CSI [0.0, 1.0]
    consciousness_integration_potential: Optional[float] = None  # CIP [0.0, 1.0]
    ucf_entropy: Optional[float] = None  # UCF weight distribution entropy [0.0, 1.0]
    ucf_notes: List[str] = field(default_factory=list)  # UCF diagnostic notes

    # Phase 27: Symbolic Harmonization Formula (observation only)
    symbolic_harmonization: Optional[Any] = None  # SymbolicHarmonizationSnapshot
    symbolic_harmonization_index: Optional[float] = None  # SHI [0.0, 1.0]
    symbolic_alignment: Optional[float] = None  # Symbolic-Practical alignment [0.0, 1.0]
    mirror_alignment_shf: Optional[float] = None  # Symbolic-Mirror alignment [0.0, 1.0]
    harmonization_entropy: Optional[float] = None  # Component entropy [0.0, 1.0]
    symbolic_harmonization_notes: List[str] = field(default_factory=list)  # SHF diagnostic notes

    # Phase 29: Persona Resonance (observation only)
    persona_resonance_bias: Optional[float] = None  # Symbolic harmony bias applied to persona tone [-0.05, +0.05]
    persona_resonance_tags: List[str] = field(default_factory=list)  # Persona resonance tags

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


class CoherenceObserver:
    """
    Deterministic observer for coherence state metrics.

    Zero-LLM, rule-based observation only.
    Does not modify any pipeline behavior.
    """

    def __init__(self):
        """Initialize the observer."""
        self._last_observation: Optional[CoherenceObservation] = None
        self._observation_history: List[CoherenceObservation] = []

    def observe(
        self,
        text: str,
        pipeline_context: Any,  # PipelineContext
        coherence_state: Optional[Any] = None,  # CoherenceState
    ) -> CoherenceObservation:
        """
        Observe and extract coherence metrics from pipeline context.

        Args:
            text: Input text (for reference)
            pipeline_context: PipelineContext with MLCR, mappers, coherence state
            coherence_state: Optional explicit CoherenceState (uses ctx.coherence_state if None)

        Returns:
            CoherenceObservation with all metrics
        """
        # Use provided state or extract from context
        if coherence_state is None:
            coherence_state = getattr(pipeline_context, 'coherence_state', None)

        # Extract base coherence metrics
        if coherence_state is not None:
            coherence_score = getattr(coherence_state, 'coherence_score', 0.0)
            persona_drift = getattr(coherence_state, 'persona_drift_score', 0.0)
            semantic_stability = getattr(coherence_state, 'semantic_stability_score', 0.0)
            temporal_arc = getattr(coherence_state, 'temporal_arc_score', 0.0)
            mapper_volatility = getattr(coherence_state, 'mapper_volatility_score', 0.0)
            turn_number = getattr(coherence_state, 'turn_index', 0)
        else:
            # No coherence state available (first turn or missing)
            coherence_score = 1.0
            persona_drift = 0.0
            semantic_stability = 1.0
            temporal_arc = 1.0
            mapper_volatility = 0.0
            turn_number = 0

        # Extract TTOR/MLCR metadata
        tier = "unknown"
        domain = "unknown"
        flow_mode = None
        normalized_entropy = None
        long_arc_tension = None

        mlcr = getattr(pipeline_context, 'mlcr', None)
        if mlcr is not None:
            routing_plan = getattr(mlcr, 'routing_plan', None)
            if routing_plan is not None:
                tier = str(getattr(routing_plan, 'tier', 'unknown'))
                domain = getattr(routing_plan, 'domain', 'unknown')
                flow_mode = str(getattr(routing_plan, 'flow_mode', None))
                normalized_entropy = getattr(routing_plan, 'normalized_entropy', None)
                long_arc_tension = getattr(routing_plan, 'long_arc_tension', None)

        # Detect active mappers
        active_mappers = self._detect_active_mappers(pipeline_context)

        # Extract temporal/bhava metadata
        bhava_state = None
        bhava_direction = None
        smi_value = None

        if coherence_state is not None:
            bhava_history = getattr(coherence_state, 'bhava_id_history', [])
            if bhava_history:
                bhava_state = bhava_history[-1]

            bhava_dir_history = getattr(coherence_state, 'bhava_direction_history', [])
            if bhava_dir_history:
                bhava_direction = bhava_dir_history[-1]

            smi_history = getattr(coherence_state, 'smi_history', [])
            if smi_history:
                smi_value = smi_history[-1]

        # Compute trend indicators (rule-based)
        is_stabilizing = self._check_stabilizing(coherence_state)
        is_recovering = self._check_recovering(coherence_state)
        is_volatile = mapper_volatility > 0.5

        # Phase 2: Extract formula aggregates from coherence_state
        avg_smi = None
        max_smi = None
        min_smi = None
        avg_tension_corridor = None
        max_tension_corridor = None
        delta_smi = None
        bhava_gap = None
        tension_corridor = None

        if coherence_state is not None:
            avg_smi = getattr(coherence_state, 'avg_smi', None)
            max_smi = getattr(coherence_state, 'max_smi', None)
            min_smi = getattr(coherence_state, 'min_smi', None)
            avg_tension_corridor = getattr(coherence_state, 'avg_tension_corridor', None)
            max_tension_corridor = getattr(coherence_state, 'max_tension_corridor', None)

            # Extract most recent delta_smi, bhava_gap, tension_corridor from histories
            delta_smi_hist = getattr(coherence_state, 'delta_smi_history', [])
            if delta_smi_hist and delta_smi_hist[-1] is not None:
                delta_smi = delta_smi_hist[-1]

            bhava_gap_hist = getattr(coherence_state, 'bhava_gap_history', [])
            if bhava_gap_hist and bhava_gap_hist[-1] is not None:
                bhava_gap = bhava_gap_hist[-1]

            tension_corridor_hist = getattr(coherence_state, 'tension_corridor_history', [])
            if tension_corridor_hist and tension_corridor_hist[-1] is not None:
                tension_corridor = tension_corridor_hist[-1]

        # Phase 3: Extract derived formula metrics from coherence_state
        resonance_index = None
        tension_index = None
        arc_alignment_index = None

        if coherence_state is not None:
            resonance_index = getattr(coherence_state, 'resonance_index', None)
            tension_index = getattr(coherence_state, 'tension_index', None)
            arc_alignment_index = getattr(coherence_state, 'arc_alignment_index', None)
        # Phase 4: Extract coherence v2 from coherence_state
        coherence_score_v2 = None

        if coherence_state is not None:
            coherence_score_v2 = getattr(coherence_state, 'coherence_score_v2', None)

        # Phase 10: Extract coherence v3 from coherence_state
        coherence_score_v3 = None

        if coherence_state is not None:
            coherence_score_v3 = getattr(coherence_state, 'coherence_score_v3', None)

        # Phase 12: Extract coherence v3 quality from coherence_state
        coherence_v3_quality = None

        if coherence_state is not None:
            coherence_v3_quality = getattr(coherence_state, 'coherence_v3_quality', None)

        # Phase 8: Extract Guna/Kosha resonance from coherence_state
        guna_resonance_index = None
        kosha_resonance_index = None

        if coherence_state is not None:
            guna_resonance_index = getattr(coherence_state, 'guna_resonance_index', None)
            kosha_resonance_index = getattr(coherence_state, 'kosha_resonance_index', None)

        # Phase 14: Extract Vritti Momentum & Arc-Tension Harmonizer from coherence_state
        vritti_momentum = None
        arc_tension_harmonizer = None
        avg_vritti_momentum = None
        max_vritti_momentum = None
        min_vritti_momentum = None
        avg_arc_tension_harmonizer = None
        max_arc_tension_harmonizer = None
        min_arc_tension_harmonizer = None

        if coherence_state is not None:
            # Extract current values from histories
            vmf_hist = getattr(coherence_state, 'vritti_momentum_history', [])
            if vmf_hist and vmf_hist[-1] is not None:
                vritti_momentum = vmf_hist[-1]

            ath_hist = getattr(coherence_state, 'arc_tension_harmonizer_history', [])
            if ath_hist and ath_hist[-1] is not None:
                arc_tension_harmonizer = ath_hist[-1]

            # Extract aggregates
            avg_vritti_momentum = getattr(coherence_state, 'avg_vritti_momentum', None)
            max_vritti_momentum = getattr(coherence_state, 'max_vritti_momentum', None)
            min_vritti_momentum = getattr(coherence_state, 'min_vritti_momentum', None)
            avg_arc_tension_harmonizer = getattr(coherence_state, 'avg_arc_tension_harmonizer', None)
            max_arc_tension_harmonizer = getattr(coherence_state, 'max_arc_tension_harmonizer', None)
            min_arc_tension_harmonizer = getattr(coherence_state, 'min_arc_tension_harmonizer', None)

        # Phase 16: Extract Formula Fusion Stabilizer from coherence_state
        coherence_fused = None
        fusion_stability_weight = None
        fusion_inertia_factor = None
        fusion_quality_factor = None

        if coherence_state is not None:
            coherence_fused = getattr(coherence_state, 'coherence_fused', None)
            fusion_stability_weight = getattr(coherence_state, 'fusion_stability_weight', None)
            fusion_inertia_factor = getattr(coherence_state, 'fusion_inertia_factor', None)
            fusion_quality_factor = getattr(coherence_state, 'fusion_quality_factor', None)

        # Phase 17: Extract Semantic Integrity & Cognitive Drift v3 from coherence_state
        semantic_integrity_score = None
        cognitive_drift_v3 = None
        semantic_integrity_details = None
        cognitive_drift_details = None

        if coherence_state is not None:
            semantic_integrity_score = getattr(coherence_state, 'semantic_integrity_score', None)
            cognitive_drift_v3 = getattr(coherence_state, 'cognitive_drift_v3', None)

            # Extract detailed component breakdowns from snapshots
            integrity_snapshot = getattr(coherence_state, 'last_semantic_integrity_snapshot', None)
            if integrity_snapshot is not None:
                semantic_integrity_details = {
                    'structural_consistency': getattr(integrity_snapshot, 'structural_consistency', None),
                    'layer_agreement_score': getattr(integrity_snapshot, 'layer_agreement_score', None),
                    'cross_turn_consistency': getattr(integrity_snapshot, 'cross_turn_consistency', None),
                    'mapper_alignment_score': getattr(integrity_snapshot, 'mapper_alignment_score', None),
                    'intent_identity_alignment': getattr(integrity_snapshot, 'intent_identity_alignment', None),
                }

            drift_snapshot = getattr(coherence_state, 'last_cognitive_drift_snapshot', None)
            if drift_snapshot is not None:
                cognitive_drift_details = {
                    'structure_drift': getattr(drift_snapshot, 'structure_drift', None),
                    'topic_drift': getattr(drift_snapshot, 'topic_drift', None),
                    'mapper_drift': getattr(drift_snapshot, 'mapper_drift', None),
                    'intent_identity_drift': getattr(drift_snapshot, 'intent_identity_drift', None),
                }

        # Phase 18: Extract Temporal Entropy Differential from coherence_state
        temporal_entropy_diff = None
        temporal_entropy_volatility = None
        temporal_entropy_details = None

        if coherence_state is not None:
            temporal_entropy_diff = getattr(coherence_state, 'temporal_entropy_diff', None)
            temporal_entropy_volatility = getattr(coherence_state, 'temporal_entropy_volatility', None)

            # Extract detailed component breakdowns from snapshot
            entropy_snapshot = getattr(coherence_state, 'temporal_entropy_snapshot', None)
            if entropy_snapshot is not None:
                temporal_entropy_details = {
                    'instantaneous_entropy': getattr(entropy_snapshot, 'instantaneous_entropy', None),
                    'short_window_entropy': getattr(entropy_snapshot, 'short_window_entropy', None),
                    'long_window_entropy': getattr(entropy_snapshot, 'long_window_entropy', None),
                    'entropy_diff': getattr(entropy_snapshot, 'entropy_diff', None),
                    'normalized_entropy_diff': getattr(entropy_snapshot, 'normalized_entropy_diff', None),
                    'entropy_volatility': getattr(entropy_snapshot, 'entropy_volatility', None),
                }

        # Phase 21: Extract Mirror-Time Loop from coherence_state
        loop_alignment = None
        loop_tension = None
        reversal_probability = None
        stability_band = None
        forward_vector = None
        mirror_vector = None
        loop_delta = None
        avg_loop_alignment = None
        avg_loop_tension = None
        avg_reversal_probability = None

        if coherence_state is not None:
            # Extract aggregates
            avg_loop_alignment = getattr(coherence_state, 'avg_loop_alignment', None)
            avg_loop_tension = getattr(coherence_state, 'avg_loop_tension', None)
            avg_reversal_probability = getattr(coherence_state, 'avg_reversal_probability', None)

            # Extract current values from snapshot
            loop_snapshot = getattr(coherence_state, 'mirror_time_loop_snapshot', None)
            if loop_snapshot is not None:
                loop_alignment = getattr(loop_snapshot, 'loop_alignment', None)
                loop_tension = getattr(loop_snapshot, 'loop_tension', None)
                reversal_probability = getattr(loop_snapshot, 'reversal_probability', None)
                stability_band = getattr(loop_snapshot, 'stability_band', None)
                forward_vector = getattr(loop_snapshot, 'forward_vector', None)
                mirror_vector = getattr(loop_snapshot, 'mirror_vector', None)
                loop_delta = getattr(loop_snapshot, 'loop_delta', None)

        # Phase 22: Extract Mirror-Time Cycles from coherence_state
        mirror_cycle_dominant_type = None
        mirror_cycle_dominant_stability_band = None
        mirror_cycle_count = None
        mirror_cycle_avg_alignment = None
        mirror_cycle_avg_tension = None
        mirror_cycle_avg_reversal_probability = None

        if coherence_state is not None:
            # Extract cycle aggregates
            mirror_cycle_dominant_type = getattr(coherence_state, 'dominant_cycle_type', None)
            mirror_cycle_dominant_stability_band = getattr(coherence_state, 'dominant_cycle_stability_band', None)
            mirror_cycle_avg_alignment = getattr(coherence_state, 'avg_cycle_alignment', None)
            mirror_cycle_avg_tension = getattr(coherence_state, 'avg_cycle_tension', None)
            mirror_cycle_avg_reversal_probability = getattr(coherence_state, 'avg_cycle_reversal_probability', None)

            # Count cycles from mirror_cycle_history
            mirror_cycle_history = getattr(coherence_state, 'mirror_cycle_history', None)
            if mirror_cycle_history is not None:
                mirror_cycle_count = len(mirror_cycle_history)

        # Phase 23: Extract Cause-Effect Inversion Analytics from coherence_state
        cause_effect_inversion = None
        inversion_score = None
        inversion_band = None
        cause_chain_stability = None
        forward_alignment = None
        mirror_alignment = None
        inversion_notes = None

        if coherence_state is not None:
            # Extract current inversion metrics
            inversion_score = getattr(coherence_state, 'current_inversion_score', None)
            inversion_band = getattr(coherence_state, 'current_inversion_band', None)

            # Extract averages
            avg_inversion_score = getattr(coherence_state, 'avg_inversion_score', None)
            cause_chain_stability_avg = getattr(coherence_state, 'cause_chain_stability_avg', None)

            # Extract current snapshot
            inversion_history = getattr(coherence_state, 'cause_effect_inversion_history', None)
            if inversion_history and len(inversion_history) > 0:
                latest_snapshot = inversion_history[-1]
                if latest_snapshot is not None:
                    cause_effect_inversion = latest_snapshot
                    inversion_score = getattr(latest_snapshot, 'inversion_score', inversion_score)
                    inversion_band = getattr(latest_snapshot, 'inversion_band', inversion_band)
                    cause_chain_stability = getattr(latest_snapshot, 'cause_chain_stability', None)
                    forward_alignment = getattr(latest_snapshot, 'forward_alignment', None)
                    mirror_alignment = getattr(latest_snapshot, 'mirror_alignment', None)
                    inversion_notes = getattr(latest_snapshot, 'notes', None)

        # Phase 24: Extract Resonance Weighting from coherence_state
        resonance_weighting = None
        resonance_entropy = None
        dominant_resonance_metrics = []

        if coherence_state is not None:
            # Extract current resonance entropy
            resonance_entropy = getattr(coherence_state, 'current_resonance_entropy', None)

            # Extract dominant resonance metrics
            dominant_metrics = getattr(coherence_state, 'dominant_resonance_metrics', None)
            if dominant_metrics:
                dominant_resonance_metrics = list(dominant_metrics) if isinstance(dominant_metrics, list) else []

            # Extract current snapshot
            weighting_history = getattr(coherence_state, 'resonance_weighting_history', None)
            if weighting_history and len(weighting_history) > 0:
                latest_snapshot = weighting_history[-1]
                if latest_snapshot is not None:
                    resonance_weighting = latest_snapshot

        # Phase 26: Extract Unified Consciousness Formula from coherence_state
        unified_consciousness = None
        consciousness_order_index = None
        consciousness_stability_index = None
        consciousness_integration_potential = None
        ucf_entropy = None
        ucf_notes = []

        if coherence_state is not None:
            # Extract current COI, CSI, CIP
            consciousness_order_index = getattr(coherence_state, 'current_coi', None)
            consciousness_stability_index = getattr(coherence_state, 'current_csi', None)
            consciousness_integration_potential = getattr(coherence_state, 'current_cip', None)

            # Extract UCF entropy
            ucf_entropy = getattr(coherence_state, 'ucf_entropy', None)

            # Extract UCF notes
            notes = getattr(coherence_state, 'ucf_notes', None)
            if notes:
                ucf_notes = list(notes)

            # Extract current snapshot
            ucf_history = getattr(coherence_state, 'ucf_history', None)
            if ucf_history and len(ucf_history) > 0:
                latest_snapshot = ucf_history[-1]
                if latest_snapshot is not None:
                    unified_consciousness = latest_snapshot

        # Phase 27: Extract Symbolic Harmonization Formula from coherence_state
        symbolic_harmonization = None
        symbolic_harmonization_index = None
        symbolic_alignment = None
        mirror_alignment_shf = None
        harmonization_entropy = None
        symbolic_harmonization_notes = []

        if coherence_state is not None:
            # Extract current SHI
            symbolic_harmonization_index = getattr(coherence_state, 'current_symbolic_harmonization_index', None)

            # Extract harmonization entropy from snapshot
            shf_snapshot = getattr(coherence_state, 'symbolic_harmonization_snapshot', None)
            if shf_snapshot is not None:
                symbolic_alignment = getattr(shf_snapshot, 'symbolic_alignment', None)
                mirror_alignment_shf = getattr(shf_snapshot, 'mirror_alignment', None)
                harmonization_entropy = getattr(shf_snapshot, 'harmonization_entropy', None)
                notes = getattr(shf_snapshot, 'notes', None)
                if notes:
                    symbolic_harmonization_notes = list(notes)
                symbolic_harmonization = shf_snapshot

        # Phase 29: Extract Persona Resonance from pipeline context
        persona_resonance_bias = None
        persona_resonance_tags = []

        # Try to extract persona resonance from persona_response in context
        if hasattr(pipeline_context, 'persona_response') and pipeline_context.persona_response is not None:
            persona_response = pipeline_context.persona_response
            persona_resonance = getattr(persona_response, 'persona_resonance', None)
            if persona_resonance is not None:
                persona_resonance_bias = getattr(persona_resonance, 'symbolic_harmony_bias', None)
                persona_resonance_tags = getattr(persona_resonance, 'symbolic_resonance_tags', [])

        # Create observation
        observation = CoherenceObservation(
            coherence_score=coherence_score,
            persona_drift_score=persona_drift,
            semantic_stability_score=semantic_stability,
            temporal_arc_score=temporal_arc,
            mapper_volatility_score=mapper_volatility,
            turn_number=turn_number,
            tier=tier,
            domain=domain,
            active_mappers=active_mappers,
            flow_mode=flow_mode,
            normalized_entropy=normalized_entropy,
            long_arc_tension=long_arc_tension,
            bhava_state=bhava_state,
            bhava_direction=bhava_direction,
            smi_value=smi_value,
            is_stabilizing=is_stabilizing,
            is_recovering=is_recovering,
            is_volatile=is_volatile,
            avg_smi=avg_smi,
            max_smi=max_smi,
            min_smi=min_smi,
            avg_tension_corridor=avg_tension_corridor,
            max_tension_corridor=max_tension_corridor,
            delta_smi=delta_smi,
            bhava_gap=bhava_gap,
            tension_corridor=tension_corridor,
            resonance_index=resonance_index,
            tension_index=tension_index,
            arc_alignment_index=arc_alignment_index,
            coherence_score_v2=coherence_score_v2,
            coherence_score_v3=coherence_score_v3,
            coherence_v3_quality=coherence_v3_quality,
            guna_resonance_index=guna_resonance_index,
            kosha_resonance_index=kosha_resonance_index,
            vritti_momentum=vritti_momentum,
            arc_tension_harmonizer=arc_tension_harmonizer,
            avg_vritti_momentum=avg_vritti_momentum,
            max_vritti_momentum=max_vritti_momentum,
            min_vritti_momentum=min_vritti_momentum,
            avg_arc_tension_harmonizer=avg_arc_tension_harmonizer,
            max_arc_tension_harmonizer=max_arc_tension_harmonizer,
            min_arc_tension_harmonizer=min_arc_tension_harmonizer,
            coherence_fused=coherence_fused,
            fusion_stability_weight=fusion_stability_weight,
            fusion_inertia_factor=fusion_inertia_factor,
            fusion_quality_factor=fusion_quality_factor,
            semantic_integrity_score=semantic_integrity_score,
            cognitive_drift_v3=cognitive_drift_v3,
            semantic_integrity_details=semantic_integrity_details,
            cognitive_drift_details=cognitive_drift_details,
            temporal_entropy_diff=temporal_entropy_diff,
            temporal_entropy_volatility=temporal_entropy_volatility,
            temporal_entropy_details=temporal_entropy_details,
            loop_alignment=loop_alignment,
            loop_tension=loop_tension,
            reversal_probability=reversal_probability,
            stability_band=stability_band,
            forward_vector=forward_vector,
            mirror_vector=mirror_vector,
            loop_delta=loop_delta,
            avg_loop_alignment=avg_loop_alignment,
            avg_loop_tension=avg_loop_tension,
            avg_reversal_probability=avg_reversal_probability,
            mirror_cycle_dominant_type=mirror_cycle_dominant_type,
            mirror_cycle_dominant_stability_band=mirror_cycle_dominant_stability_band,
            mirror_cycle_count=mirror_cycle_count,
            mirror_cycle_avg_alignment=mirror_cycle_avg_alignment,
            mirror_cycle_avg_tension=mirror_cycle_avg_tension,
            mirror_cycle_avg_reversal_probability=mirror_cycle_avg_reversal_probability,
            cause_effect_inversion=cause_effect_inversion,
            inversion_score=inversion_score,
            inversion_band=inversion_band,
            cause_chain_stability=cause_chain_stability,
            forward_alignment=forward_alignment,
            mirror_alignment=mirror_alignment,
            inversion_notes=inversion_notes,
            resonance_weighting=resonance_weighting,
            resonance_entropy=resonance_entropy,
            dominant_resonance_metrics=dominant_resonance_metrics,
            unified_consciousness=unified_consciousness,
            consciousness_order_index=consciousness_order_index,
            consciousness_stability_index=consciousness_stability_index,
            consciousness_integration_potential=consciousness_integration_potential,
            ucf_entropy=ucf_entropy,
            ucf_notes=ucf_notes,
            symbolic_harmonization=symbolic_harmonization,
            symbolic_harmonization_index=symbolic_harmonization_index,
            symbolic_alignment=symbolic_alignment,
            mirror_alignment_shf=mirror_alignment_shf,
            harmonization_entropy=harmonization_entropy,
            symbolic_harmonization_notes=symbolic_harmonization_notes,
            persona_resonance_bias=persona_resonance_bias,  # Phase 29
            persona_resonance_tags=persona_resonance_tags,  # Phase 29
        )

        # Store observation
        self._last_observation = observation
        self._observation_history.append(observation)

        return observation

    def _detect_active_mappers(self, ctx: Any) -> List[str]:
        """Detect which mappers are active in this context."""
        active = []

        if getattr(ctx, 'hrm_map', None) is not None:
            active.append("HRM")
        if getattr(ctx, 'lcm_map', None) is not None:
            active.append("LCM")
        if getattr(ctx, 'lam_map', None) is not None:
            active.append("LAM")

        return active

    def _check_stabilizing(self, coherence_state: Optional[Any]) -> bool:
        """Check if coherence is stabilizing (improving over recent turns)."""
        if coherence_state is None:
            return False

        # Look at persona drift trend
        drift_history = getattr(coherence_state, 'persona_drift_score', 0.0)

        # Simple heuristic: low drift = stabilizing
        return drift_history < 0.3

    def _check_recovering(self, coherence_state: Optional[Any]) -> bool:
        """Check if coherence is recovering from instability."""
        if coherence_state is None:
            return False

        # Look at temporal arc score
        temporal_arc = getattr(coherence_state, 'temporal_arc_score', 0.0)

        # Check bhava direction
        bhava_dir_history = getattr(coherence_state, 'bhava_direction_history', [])
        if bhava_dir_history:
            recent_direction = bhava_dir_history[-1]
            if recent_direction == "upward" and temporal_arc > 0.6:
                return True

        return False

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the last observation to a JSON-safe dict.

        Returns:
            Complete observation dict with all metrics
        """
        if self._last_observation is None:
            return {
                "coherence_score": 0.0,
                "persona_drift_score": 0.0,
                "semantic_stability_score": 0.0,
                "temporal_arc_score": 0.0,
                "mapper_volatility_score": 0.0,
                "turn_number": 0,
                "tier": "unknown",
                "domain": "unknown",
                "active_mappers": [],
            }

        return self._last_observation.to_dict()

    def snapshot(self) -> Dict[str, Any]:
        """
        Generate a trimmed snapshot for dashboards.

        Returns:
            Minimal dict with key metrics only
        """
        if self._last_observation is None:
            return {
                "coherence": 0.0,
                "drift": 0.0,
                "stability": 0.0,
                "tier": "unknown",
                "mappers": [],
            }

        obs = self._last_observation
        snapshot = {
            "coherence": round(obs.coherence_score, 3),
            "drift": round(obs.persona_drift_score, 3),
            "stability": round(obs.semantic_stability_score, 3),
            "temporal_arc": round(obs.temporal_arc_score, 3),
            "volatility": round(obs.mapper_volatility_score, 3),
            "tier": obs.tier,
            "domain": obs.domain,
            "mappers": obs.active_mappers,
            "turn": obs.turn_number,
            "status": self._get_status_label(obs),
        }

        # Phase 2: Add formulas section from coherence_state if available
        formulas = self._extract_formulas_from_observation(obs)
        if formulas:
            snapshot["formulas"] = formulas

        # Phase 16: Add formula fusion stabilizer section if available
        stabilizer = self._extract_stabilizer_from_observation(obs)
        if stabilizer:
            snapshot["stabilizer"] = stabilizer

        # Phase 17: Add semantic integrity & cognitive drift section if available
        semantic = self._extract_semantic_from_observation(obs)
        if semantic:
            snapshot["semantic"] = semantic

        # Phase 18: Add temporal entropy section if available
        temporal_entropy = self._extract_temporal_entropy_from_observation(obs)
        if temporal_entropy:
            snapshot["temporal_entropy"] = temporal_entropy

        # Phase 24: Add resonance weighting section if available
        resonance_weighting = self._extract_resonance_weighting_from_observation(obs)
        if resonance_weighting:
            snapshot["resonance_weighting"] = resonance_weighting

        # Phase 26: Add unified consciousness section if available
        unified_consciousness = self._extract_unified_consciousness_from_observation(obs)
        if unified_consciousness:
            snapshot["unified_consciousness"] = unified_consciousness

        # Phase 27: Add symbolic harmonization section if available
        symbolic_harmonization = self._extract_symbolic_harmonization_from_observation(obs)
        if symbolic_harmonization:
            snapshot["symbolic_harmonization"] = symbolic_harmonization

        return snapshot

    def _extract_formulas_from_observation(self, obs: CoherenceObservation) -> Optional[Dict[str, Optional[float]]]:
        """
        Extract Phase 2 formulas and Phase 3 derived metrics from observation.

        Returns formula dict if formulas are available, None otherwise.
        """
        # Build formulas dict from observation
        formulas = {}

        # Current turn formulas
        if obs.smi_value is not None:
            formulas["smi"] = obs.smi_value
        if obs.delta_smi is not None:
            formulas["delta_smi"] = obs.delta_smi
        if obs.bhava_gap is not None:
            formulas["bhava_gap"] = obs.bhava_gap
        if obs.tension_corridor is not None:
            formulas["tension_corridor"] = obs.tension_corridor

        # Aggregates
        if obs.avg_smi is not None:
            formulas["avg_smi"] = obs.avg_smi
        if obs.max_smi is not None:
            formulas["max_smi"] = obs.max_smi
        if obs.min_smi is not None:
            formulas["min_smi"] = obs.min_smi
        if obs.avg_tension_corridor is not None:
            formulas["avg_tension_corridor"] = obs.avg_tension_corridor
        if obs.max_tension_corridor is not None:
            formulas["max_tension_corridor"] = obs.max_tension_corridor

        # Phase 3 derived metrics
        if obs.resonance_index is not None:
            formulas["resonance_index"] = obs.resonance_index
        if obs.tension_index is not None:
            formulas["tension_index"] = obs.tension_index
        if obs.arc_alignment_index is not None:
            formulas["arc_alignment_index"] = obs.arc_alignment_index

        # Phase 8 Guna/Kosha resonance metrics
        if obs.guna_resonance_index is not None:
            formulas["guna_resonance_index"] = obs.guna_resonance_index
        if obs.kosha_resonance_index is not None:
            formulas["kosha_resonance_index"] = obs.kosha_resonance_index

        return formulas if formulas else None

    def _extract_stabilizer_from_observation(self, obs: CoherenceObservation) -> Optional[Dict[str, Optional[float]]]:
        """
        Extract Phase 16 Formula Fusion Stabilizer metrics from observation.

        Returns stabilizer dict if metrics are available, None otherwise.
        """
        # Build stabilizer dict from observation
        stabilizer = {}

        if obs.coherence_fused is not None:
            stabilizer["coherence_fused"] = obs.coherence_fused
        if obs.fusion_stability_weight is not None:
            stabilizer["stability_weight"] = obs.fusion_stability_weight
        if obs.fusion_inertia_factor is not None:
            stabilizer["inertia_factor"] = obs.fusion_inertia_factor
        if obs.fusion_quality_factor is not None:
            stabilizer["quality_factor"] = obs.fusion_quality_factor

        return stabilizer if stabilizer else None

    def _extract_semantic_from_observation(self, obs: CoherenceObservation) -> Optional[Dict[str, Any]]:
        """
        Extract Phase 17 Semantic Integrity & Cognitive Drift metrics from observation.

        Returns semantic dict if metrics are available, None otherwise.
        """
        # Build semantic dict from observation
        semantic = {}

        # Integrity score and details
        if obs.semantic_integrity_score is not None:
            semantic["integrity_score"] = obs.semantic_integrity_score

        if obs.semantic_integrity_details is not None:
            semantic["integrity_components"] = obs.semantic_integrity_details

        # Drift score and details
        if obs.cognitive_drift_v3 is not None:
            semantic["cognitive_drift_v3"] = obs.cognitive_drift_v3

        if obs.cognitive_drift_details is not None:
            semantic["drift_components"] = obs.cognitive_drift_details

        return semantic if semantic else None

    def _extract_temporal_entropy_from_observation(self, obs: CoherenceObservation) -> Optional[Dict[str, Any]]:
        """
        Extract Phase 18 Temporal Entropy Differential metrics from observation.

        Returns temporal_entropy dict if metrics are available, None otherwise.
        """
        # Build temporal_entropy dict from observation
        temporal_entropy = {}

        # Core metrics
        if obs.temporal_entropy_diff is not None:
            temporal_entropy["diff"] = obs.temporal_entropy_diff

        if obs.temporal_entropy_volatility is not None:
            temporal_entropy["volatility"] = obs.temporal_entropy_volatility

        # Detailed components
        if obs.temporal_entropy_details is not None:
            temporal_entropy["details"] = obs.temporal_entropy_details

        return temporal_entropy if temporal_entropy else None

    def _extract_resonance_weighting_from_observation(self, obs: CoherenceObservation) -> Optional[Dict[str, Any]]:
        """
        Extract Phase 24 Resonance Weighting metrics from observation.

        Returns resonance_weighting dict if metrics are available, None otherwise.
        """
        # Build resonance_weighting dict from observation
        resonance_weighting = {}

        # Core metrics
        if obs.resonance_entropy is not None:
            resonance_weighting["entropy"] = obs.resonance_entropy

        if obs.dominant_resonance_metrics:
            resonance_weighting["dominant_metrics"] = obs.dominant_resonance_metrics

        # Full snapshot if available
        if obs.resonance_weighting is not None:
            # Try to serialize the snapshot
            if hasattr(obs.resonance_weighting, '__dict__'):
                # Convert snapshot object to dict
                snapshot_dict = {
                    "weights": getattr(obs.resonance_weighting, 'weights', {}),
                    "normalized_weights": getattr(obs.resonance_weighting, 'normalized_weights', {}),
                    "entropy": getattr(obs.resonance_weighting, 'entropy_of_weights', None),
                    "dominant_metrics": getattr(obs.resonance_weighting, 'dominant_metrics', {}),
                    "notes": getattr(obs.resonance_weighting, 'notes', []),
                }
                resonance_weighting["snapshot"] = snapshot_dict
            elif isinstance(obs.resonance_weighting, dict):
                resonance_weighting["snapshot"] = obs.resonance_weighting

        return resonance_weighting if resonance_weighting else None

    def _extract_unified_consciousness_from_observation(self, obs: CoherenceObservation) -> Optional[Dict[str, Any]]:
        """
        Extract Phase 26 Unified Consciousness Formula metrics from observation.

        Returns unified_consciousness dict if metrics are available, None otherwise.
        """
        # Build unified_consciousness dict from observation
        unified_consciousness = {}

        # Core indices (COI, CSI, CIP)
        if obs.consciousness_order_index is not None:
            unified_consciousness["consciousness_order_index"] = obs.consciousness_order_index
            unified_consciousness["coi"] = obs.consciousness_order_index  # Alias

        if obs.consciousness_stability_index is not None:
            unified_consciousness["consciousness_stability_index"] = obs.consciousness_stability_index
            unified_consciousness["csi"] = obs.consciousness_stability_index  # Alias

        if obs.consciousness_integration_potential is not None:
            unified_consciousness["consciousness_integration_potential"] = obs.consciousness_integration_potential
            unified_consciousness["cip"] = obs.consciousness_integration_potential  # Alias

        # UCF entropy
        if obs.ucf_entropy is not None:
            unified_consciousness["entropy"] = obs.ucf_entropy

        # UCF notes
        if obs.ucf_notes:
            unified_consciousness["notes"] = obs.ucf_notes

        # Full snapshot if available
        if obs.unified_consciousness is not None:
            # Try to serialize the snapshot
            if hasattr(obs.unified_consciousness, '__dict__'):
                # Convert snapshot object to dict
                snapshot_dict = {
                    "consciousness_order_index": getattr(obs.unified_consciousness, 'consciousness_order_index', None),
                    "consciousness_stability_index": getattr(obs.unified_consciousness, 'consciousness_stability_index', None),
                    "consciousness_integration_potential": getattr(obs.unified_consciousness, 'consciousness_integration_potential', None),
                    "weighted_component_breakdown": getattr(obs.unified_consciousness, 'weighted_component_breakdown', {}),
                    "normalized_weights": getattr(obs.unified_consciousness, 'normalized_weights', {}),
                    "entropy_of_weights": getattr(obs.unified_consciousness, 'entropy_of_weights', None),
                    "diagnostic_notes": getattr(obs.unified_consciousness, 'diagnostic_notes', []),
                }
                unified_consciousness["snapshot"] = snapshot_dict
            elif isinstance(obs.unified_consciousness, dict):
                unified_consciousness["snapshot"] = obs.unified_consciousness

        return unified_consciousness if unified_consciousness else None

    def _extract_symbolic_harmonization_from_observation(self, obs: CoherenceObservation) -> Optional[Dict[str, Any]]:
        """
        Extract Phase 27 Symbolic Harmonization Formula metrics from observation.

        Returns symbolic_harmonization dict if metrics are available, None otherwise.
        """
        # Build symbolic_harmonization dict from observation
        symbolic_harmonization = {}

        # Symbolic Harmonization Index (SHI)
        if obs.symbolic_harmonization_index is not None:
            symbolic_harmonization["index"] = obs.symbolic_harmonization_index
            symbolic_harmonization["symbolic_harmonization_index"] = obs.symbolic_harmonization_index  # Explicit

        # Component alignments
        if obs.symbolic_alignment is not None:
            symbolic_harmonization["symbolic_alignment"] = obs.symbolic_alignment

        if obs.mirror_alignment_shf is not None:
            symbolic_harmonization["mirror_alignment"] = obs.mirror_alignment_shf

        # Harmonization entropy
        if obs.harmonization_entropy is not None:
            symbolic_harmonization["entropy"] = obs.harmonization_entropy

        # SHF notes
        if obs.symbolic_harmonization_notes:
            symbolic_harmonization["notes"] = obs.symbolic_harmonization_notes

        # Full snapshot if available
        if obs.symbolic_harmonization is not None:
            # Try to serialize the snapshot
            if hasattr(obs.symbolic_harmonization, '__dict__'):
                # Convert snapshot object to dict
                snapshot_dict = {
                    "symbolic_alignment": getattr(obs.symbolic_harmonization, 'symbolic_alignment', None),
                    "mirror_alignment": getattr(obs.symbolic_harmonization, 'mirror_alignment', None),
                    "guna_symbolic_resonance": getattr(obs.symbolic_harmonization, 'guna_symbolic_resonance', None),
                    "kosha_symbolic_resonance": getattr(obs.symbolic_harmonization, 'kosha_symbolic_resonance', None),
                    "semantic_integrity_weight": getattr(obs.symbolic_harmonization, 'semantic_integrity_weight', None),
                    "symbolic_harmonization_index": getattr(obs.symbolic_harmonization, 'symbolic_harmonization_index', None),
                    "harmonization_entropy": getattr(obs.symbolic_harmonization, 'harmonization_entropy', None),
                    "notes": getattr(obs.symbolic_harmonization, 'notes', []),
                }
                symbolic_harmonization["snapshot"] = snapshot_dict
            elif isinstance(obs.symbolic_harmonization, dict):
                symbolic_harmonization["snapshot"] = obs.symbolic_harmonization

        return symbolic_harmonization if symbolic_harmonization else None

    def _get_status_label(self, obs: CoherenceObservation) -> str:
        """Get human-readable status label."""
        if obs.is_recovering:
            return "Recovering"
        elif obs.is_stabilizing:
            return "Stable"
        elif obs.is_volatile:
            return "Volatile"
        elif obs.coherence_score > 0.7:
            return "Good"
        elif obs.coherence_score > 0.4:
            return "Fair"
        else:
            return "Poor"

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get observation history.

        Args:
            limit: Optional max number of recent observations

        Returns:
            List of observation dicts
        """
        history = [obs.to_dict() for obs in self._observation_history]
        if limit is not None:
            return history[-limit:]
        return history

    def clear_history(self):
        """Clear observation history (for testing)."""
        self._observation_history.clear()
        self._last_observation = None
