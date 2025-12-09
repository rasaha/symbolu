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
from dataclasses import dataclass, asdict
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

        return snapshot

    def _extract_formulas_from_observation(self, obs: CoherenceObservation) -> Optional[Dict[str, Optional[float]]]:
        """
        Extract Phase 2 formulas from observation.

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

        return formulas if formulas else None

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
