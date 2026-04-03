#!/usr/bin/env python3
"""
Coherence Monitor: Real-Time Coherence Tracking for Image Generation
======================================================================

Integrates BCVF, USE, and SCC engines for unified coherence monitoring
during Symbol-U image generation.

Key Features:
1. Real-time tracking across generation timesteps
2. Integration of all three patent formula systems
3. Completion weight (w_final) computation
4. Anomaly detection and correction triggers
5. Generation history for debugging

Completion Weight Formula:
    w_final = w_bcvf * w_use * w_scc * decay_factor

Where:
    w_bcvf = exp(-beta_1 * L_bcvf)
    w_use = sigmoid(coherence_use - threshold)
    w_scc = global_coherence_scc
    decay_factor = handles temporal consistency

Usage:
------
    from symbolu_extensions.image_gen.coherence_monitor import CoherenceMonitor

    monitor = CoherenceMonitor()

    # During generation:
    for timestep in range(num_steps):
        # Record state
        monitor.record_timestep(
            timestep=timestep,
            latents=latents,
            layer_states=layer_states,
            prompt=prompt,
        )

        # Check if correction needed
        if monitor.needs_correction():
            latents = monitor.apply_corrections(latents)

    # Final decision
    result = monitor.get_generation_result()
    if result.should_accept:
        return image
    else:
        retry_generation()
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union
import time
import math

try:
    import torch
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    torch = None
    F = None

import numpy as np

from symbolu_extensions.image_gen.config import (
    CoherenceConfig,
    BCVFImageConfig,
    USEImageConfig,
    SCCImageConfig,
    CoherenceMatrixConfig,
    GenerationMode,
)
from symbolu_extensions.image_gen.bcvf_image import BCVFImageEngine, BCVFImageScore
from symbolu_extensions.image_gen.use_image import USEImageEngine, PhaseSyncResult
from symbolu_extensions.image_gen.scc_image import (
    SCCImageEngine,
    GlobalCoherenceResult,
    CoherenceIssue,
)


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class TimestepMetrics:
    """Metrics captured at a single timestep."""
    timestep: int
    timestamp_ms: float

    # BCVF metrics
    bcvf_forward: float
    bcvf_backward: float
    bcvf_lagrangian: float
    bcvf_weight: float

    # USE metrics
    use_coherence: float
    use_improvement: Optional[float]

    # SCC metrics
    scc_global: float
    scc_weakest_layer: int
    scc_weakest_score: float

    # Combined
    combined_weight: float
    issues: List[str]


@dataclass
class CoherenceHistory:
    """History of coherence across all timesteps."""
    timesteps: List[TimestepMetrics]

    @property
    def num_timesteps(self) -> int:
        return len(self.timesteps)

    @property
    def latest(self) -> Optional[TimestepMetrics]:
        return self.timesteps[-1] if self.timesteps else None

    def get_trend(self, metric: str, window: int = 5) -> str:
        """Get trend direction for a metric over recent timesteps."""
        if len(self.timesteps) < 2:
            return "stable"

        recent = self.timesteps[-window:]
        values = [getattr(m, metric, 0) for m in recent]

        if len(values) < 2:
            return "stable"

        diff = values[-1] - values[0]
        if diff > 0.05:
            return "improving"
        elif diff < -0.05:
            return "declining"
        else:
            return "stable"

    def get_average(self, metric: str) -> float:
        """Get average of a metric across all timesteps."""
        if not self.timesteps:
            return 0.0
        values = [getattr(m, metric, 0) for m in self.timesteps]
        return float(np.mean(values))


@dataclass
class GenerationDecision:
    """Final decision about the generated image."""
    should_accept: bool
    confidence: float  # [0, 1]
    category: str  # "excellent", "good", "acceptable", "poor"

    # Final metrics
    final_bcvf: BCVFImageScore
    final_use_coherence: float
    final_scc: GlobalCoherenceResult

    # Combined completion weight
    completion_weight: float

    # Issues and recommendations
    issues: List[str]
    recommendations: List[str]

    # History summary
    num_corrections_applied: int
    trend_summary: Dict[str, str]


@dataclass
class CorrectionAction:
    """A correction action to apply."""
    action_type: str  # "semantic_restore", "phase_sync", "layer_boost"
    target_layer: Optional[int]
    strength: float
    reason: str


# =============================================================================
# COHERENCE MONITOR
# =============================================================================

class CoherenceMonitor:
    """
    Real-time coherence monitoring during image generation.

    Integrates BCVF, USE, and SCC for comprehensive tracking.
    """

    def __init__(
        self,
        coherence_config: Optional[CoherenceConfig] = None,
        bcvf_config: Optional[BCVFImageConfig] = None,
        use_config: Optional[USEImageConfig] = None,
        scc_config: Optional[SCCImageConfig] = None,
        matrix_config: Optional[CoherenceMatrixConfig] = None,
        mode: GenerationMode = GenerationMode.BALANCED,
    ):
        self.coherence_config = coherence_config or CoherenceConfig()
        self.mode = mode

        # Initialize engines
        self.bcvf_engine = BCVFImageEngine(bcvf_config)
        self.use_engine = USEImageEngine(use_config)
        self.scc_engine = SCCImageEngine(scc_config, matrix_config)

        # Get coupling matrix for USE
        self._matrix_config = matrix_config or CoherenceMatrixConfig()
        self._coupling_matrix = np.array(self._matrix_config.build_default_matrix())

        # State
        self._history = CoherenceHistory(timesteps=[])
        self._corrections_applied = 0
        self._start_time_ms = time.time() * 1000

        # Caches
        self._last_phases: Optional[Dict[int, Any]] = None
        self._last_layer_states: Optional[Dict[int, Any]] = None
        self._prompt: str = ""
        self._text_embeddings: Optional[Any] = None

    def reset(self) -> None:
        """Reset monitor for a new generation."""
        self._history = CoherenceHistory(timesteps=[])
        self._corrections_applied = 0
        self._start_time_ms = time.time() * 1000
        self._last_phases = None
        self._last_layer_states = None

    def set_prompt(
        self,
        prompt: str,
        text_embeddings: Optional[Any] = None,
    ) -> None:
        """Set prompt information for backward scoring."""
        self._prompt = prompt
        self._text_embeddings = text_embeddings

    # =========================================================================
    # TIMESTEP RECORDING
    # =========================================================================

    def record_timestep(
        self,
        timestep: int,
        latents: Optional[Any] = None,
        layer_states: Optional[Dict[int, Any]] = None,
        image: Optional[Any] = None,
        prompt: Optional[str] = None,
        text_embeddings: Optional[Any] = None,
    ) -> TimestepMetrics:
        """
        Record metrics at a generation timestep.

        Args:
            timestep: Current timestep number
            latents: Current image latents
            layer_states: Hidden states for each layer
            image: Decoded image (if available)
            prompt: Override prompt
            text_embeddings: Override text embeddings

        Returns:
            TimestepMetrics for this timestep
        """
        current_time_ms = time.time() * 1000

        # Use cached values if not provided
        prompt = prompt or self._prompt
        text_embeddings = text_embeddings or self._text_embeddings
        layer_states = layer_states or self._last_layer_states or {}

        # Cache for potential corrections
        self._last_layer_states = layer_states

        # === BCVF METRICS ===
        bcvf_score = self.bcvf_engine.score(
            image=image,
            latents=latents,
            prompt=prompt,
            text_embeddings=text_embeddings,
            hidden_states=layer_states,
        )

        # === USE METRICS ===
        phases = self.use_engine.extract_phases(layer_states)
        use_coherence = self.use_engine.compute_total_coherence(
            phases=phases,
            coupling_matrix=self._coupling_matrix,
        )

        # Check improvement from sync
        use_improvement = None
        if self.mode in [GenerationMode.QUALITY, GenerationMode.STRICT]:
            sync_result = self.use_engine.synchronize(
                phases=phases,
                num_steps=1,
                coupling_matrix=self._coupling_matrix,
            )
            use_improvement = sync_result.improvement

        self._last_phases = phases

        # === SCC METRICS ===
        scc_result = self.scc_engine.compute_global_coherence(layer_states)

        weakest_layer = scc_result.weakest_layers[0] if scc_result.weakest_layers else 1
        weakest_score = scc_result.layer_results.get(
            weakest_layer, scc_result.layer_results.get(1)
        )
        weakest_value = weakest_score.coherence if weakest_score else 0.5

        # === COMBINE METRICS ===
        combined_weight = self._compute_combined_weight(
            bcvf_score, use_coherence, scc_result.global_coherence
        )

        # === DETECT ISSUES ===
        issues = self._detect_issues(bcvf_score, use_coherence, scc_result)

        # Create metrics record
        metrics = TimestepMetrics(
            timestep=timestep,
            timestamp_ms=current_time_ms - self._start_time_ms,
            bcvf_forward=bcvf_score.forward_score,
            bcvf_backward=bcvf_score.backward_score,
            bcvf_lagrangian=bcvf_score.lagrangian,
            bcvf_weight=bcvf_score.consistency_weight,
            use_coherence=use_coherence,
            use_improvement=use_improvement,
            scc_global=scc_result.global_coherence,
            scc_weakest_layer=weakest_layer,
            scc_weakest_score=weakest_value,
            combined_weight=combined_weight,
            issues=[str(i) for i in issues],
        )

        self._history.timesteps.append(metrics)

        return metrics

    def _compute_combined_weight(
        self,
        bcvf_score: BCVFImageScore,
        use_coherence: float,
        scc_coherence: float,
    ) -> float:
        """
        Compute combined completion weight from all three systems.

        Formula: w_final = w_bcvf * sigmoid(use) * scc * decay
        """
        # BCVF weight (already computed as exp(-beta * L))
        w_bcvf = bcvf_score.consistency_weight

        # USE weight (sigmoid around threshold)
        threshold = self.coherence_config.coherence_threshold
        w_use = 1.0 / (1.0 + np.exp(-(use_coherence - threshold) * 10))

        # SCC weight (direct use)
        w_scc = scc_coherence

        # Temporal decay factor (penalize inconsistent trends)
        decay = self._compute_temporal_decay()

        # Combine multiplicatively
        combined = w_bcvf * w_use * w_scc * decay

        return float(np.clip(combined, 0.0, 1.0))

    def _compute_temporal_decay(self) -> float:
        """Compute decay factor based on coherence stability."""
        if len(self._history.timesteps) < 3:
            return 1.0

        # Check variance of recent combined weights
        recent = self._history.timesteps[-5:]
        weights = [m.combined_weight for m in recent]
        variance = np.var(weights)

        # High variance = unstable = lower decay
        decay = 1.0 / (1.0 + 2 * variance)

        return float(np.clip(decay, 0.5, 1.0))

    def _detect_issues(
        self,
        bcvf_score: BCVFImageScore,
        use_coherence: float,
        scc_result: GlobalCoherenceResult,
    ) -> List[str]:
        """Detect issues from current metrics."""
        issues = []
        config = self.coherence_config

        # BCVF issues
        if bcvf_score.forward_score < config.min_forward_score:
            issues.append(f"Low forward score: {bcvf_score.forward_score:.2f}")
        if bcvf_score.backward_score < config.min_backward_score:
            issues.append(f"Low backward score: {bcvf_score.backward_score:.2f}")
        if not bcvf_score.is_consistent:
            gap = abs(bcvf_score.forward_score - bcvf_score.backward_score)
            if gap > config.max_consistency_gap:
                issues.append(f"BCVF consistency gap: {gap:.2f}")

        # USE issues
        if use_coherence < config.coherence_threshold:
            issues.append(f"Low phase coherence: {use_coherence:.2f}")

        # SCC issues
        if scc_result.global_coherence < config.coherence_threshold:
            issues.append(f"Low global coherence: {scc_result.global_coherence:.2f}")

        for layer_idx, layer_result in scc_result.layer_results.items():
            if layer_result.entropy > config.cognition_entropy_threshold:
                issues.append(f"High entropy in L{layer_idx}: {layer_result.entropy:.2f}")

        return issues

    # =========================================================================
    # CORRECTION DECISIONS
    # =========================================================================

    def needs_correction(self) -> bool:
        """Check if correction is needed based on current state."""
        if not self._history.timesteps:
            return False

        latest = self._history.latest

        # Mode-specific thresholds
        if self.mode == GenerationMode.FAST:
            return False  # No corrections in fast mode
        elif self.mode == GenerationMode.BALANCED:
            threshold = 0.4
        elif self.mode == GenerationMode.QUALITY:
            threshold = 0.5
        else:  # STRICT
            threshold = 0.6

        return latest.combined_weight < threshold or len(latest.issues) > 2

    def get_correction_actions(self) -> List[CorrectionAction]:
        """Determine what corrections to apply."""
        if not self._history.timesteps:
            return []

        actions = []
        latest = self._history.latest

        # Low backward score -> semantic restoration
        if latest.bcvf_backward < 0.5:
            actions.append(CorrectionAction(
                action_type="semantic_restore",
                target_layer=None,
                strength=0.1,
                reason=f"Low prompt alignment ({latest.bcvf_backward:.2f})",
            ))

        # Low phase coherence -> phase sync
        if latest.use_coherence < self.coherence_config.coherence_threshold:
            actions.append(CorrectionAction(
                action_type="phase_sync",
                target_layer=None,
                strength=0.1,
                reason=f"Low phase coherence ({latest.use_coherence:.2f})",
            ))

        # Weak layer -> layer boost
        if latest.scc_weakest_score < 0.4:
            actions.append(CorrectionAction(
                action_type="layer_boost",
                target_layer=latest.scc_weakest_layer,
                strength=0.15,
                reason=f"Weak layer {latest.scc_weakest_layer} ({latest.scc_weakest_score:.2f})",
            ))

        return actions

    def apply_corrections(
        self,
        latents: Any,
        text_embeddings: Optional[Any] = None,
    ) -> Any:
        """
        Apply correction actions to latents.

        Args:
            latents: Current image latents
            text_embeddings: Text embeddings for semantic correction

        Returns:
            Corrected latents
        """
        if not PYTORCH_AVAILABLE or not isinstance(latents, torch.Tensor):
            return latents

        text_embeddings = text_embeddings or self._text_embeddings
        actions = self.get_correction_actions()

        corrected = latents

        for action in actions:
            if action.action_type == "semantic_restore":
                corrected = self.scc_engine.restore_coherence(
                    corrected, text_embeddings, strength=action.strength
                )
            elif action.action_type == "phase_sync" and self._last_layer_states:
                sync_result = self.use_engine.synchronize(
                    layer_states=self._last_layer_states,
                    coupling_matrix=self._coupling_matrix,
                )
                corrected = self.use_engine.apply_synchronization_to_latents(
                    corrected,
                    self._last_layer_states,
                    sync_result,
                    strength=action.strength,
                )
            # layer_boost would require layer-specific modifications

        self._corrections_applied += len(actions)

        return corrected

    # =========================================================================
    # FINAL DECISION
    # =========================================================================

    def get_generation_result(
        self,
        final_latents: Optional[Any] = None,
        final_image: Optional[Any] = None,
        final_layer_states: Optional[Dict[int, Any]] = None,
    ) -> GenerationDecision:
        """
        Get final generation decision after all timesteps.

        Args:
            final_latents: Final latents
            final_image: Decoded final image
            final_layer_states: Final layer states

        Returns:
            GenerationDecision with accept/reject and metrics
        """
        # Use last recorded state if not provided
        layer_states = final_layer_states or self._last_layer_states or {}

        # Compute final BCVF
        final_bcvf = self.bcvf_engine.score(
            image=final_image,
            latents=final_latents,
            prompt=self._prompt,
            text_embeddings=self._text_embeddings,
            hidden_states=layer_states,
        )

        # Compute final USE coherence
        final_use_coherence = self.use_engine.compute_total_coherence(
            layer_states=layer_states,
            coupling_matrix=self._coupling_matrix,
        )

        # Compute final SCC
        final_scc = self.scc_engine.compute_global_coherence(layer_states)

        # Final completion weight
        completion_weight = self._compute_combined_weight(
            final_bcvf, final_use_coherence, final_scc.global_coherence
        )

        # Decision based on mode and thresholds
        should_accept, confidence, category = self._make_decision(
            final_bcvf, final_use_coherence, final_scc, completion_weight
        )

        # Gather issues
        all_issues = self._detect_issues(final_bcvf, final_use_coherence, final_scc)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            final_bcvf, final_use_coherence, final_scc
        )

        # Trend summary
        trend_summary = {
            "bcvf_forward": self._history.get_trend("bcvf_forward"),
            "bcvf_backward": self._history.get_trend("bcvf_backward"),
            "use_coherence": self._history.get_trend("use_coherence"),
            "scc_global": self._history.get_trend("scc_global"),
            "combined_weight": self._history.get_trend("combined_weight"),
        }

        return GenerationDecision(
            should_accept=should_accept,
            confidence=confidence,
            category=category,
            final_bcvf=final_bcvf,
            final_use_coherence=final_use_coherence,
            final_scc=final_scc,
            completion_weight=completion_weight,
            issues=all_issues,
            recommendations=recommendations,
            num_corrections_applied=self._corrections_applied,
            trend_summary=trend_summary,
        )

    def _make_decision(
        self,
        bcvf: BCVFImageScore,
        use_coherence: float,
        scc: GlobalCoherenceResult,
        completion_weight: float,
    ) -> Tuple[bool, float, str]:
        """Make accept/reject decision with confidence."""
        config = self.coherence_config

        # Compute confidence from multiple factors
        factors = [
            bcvf.forward_score,
            bcvf.backward_score,
            use_coherence,
            scc.global_coherence,
        ]
        confidence = float(np.mean(factors))

        # Determine category
        if completion_weight >= 0.8:
            category = "excellent"
        elif completion_weight >= 0.6:
            category = "good"
        elif completion_weight >= 0.4:
            category = "acceptable"
        else:
            category = "poor"

        # Decision based on mode
        if self.mode == GenerationMode.FAST:
            should_accept = True  # Always accept in fast mode
        elif self.mode == GenerationMode.BALANCED:
            should_accept = completion_weight >= config.coherence_threshold
        elif self.mode == GenerationMode.QUALITY:
            should_accept = (
                completion_weight >= config.completion_threshold and
                bcvf.is_consistent
            )
        else:  # STRICT
            should_accept = (
                completion_weight >= config.completion_threshold and
                bcvf.forward_score >= config.min_forward_score and
                bcvf.backward_score >= config.min_backward_score and
                bcvf.is_consistent and
                len(scc.weakest_layers) == 0 or
                all(scc.layer_results[l].coherence >= 0.5 for l in scc.weakest_layers)
            )

        return should_accept, confidence, category

    def _generate_recommendations(
        self,
        bcvf: BCVFImageScore,
        use_coherence: float,
        scc: GlobalCoherenceResult,
    ) -> List[str]:
        """Generate recommendations for improvement."""
        recommendations = []

        if bcvf.forward_score < 0.7:
            recommendations.append(
                "Consider increasing inference steps for better quality"
            )

        if bcvf.backward_score < 0.7:
            recommendations.append(
                "Consider more specific prompt or stronger guidance scale"
            )

        if use_coherence < 0.7:
            recommendations.append(
                "Enable phase synchronization for better layer coherence"
            )

        if scc.global_coherence < 0.7:
            weak_layers = [
                scc.layer_results[l].layer_name
                for l in scc.weakest_layers
                if l in scc.layer_results
            ]
            if weak_layers:
                recommendations.append(
                    f"Strengthen weak layers: {', '.join(weak_layers)}"
                )

        if not bcvf.is_consistent:
            if bcvf.forward_score > bcvf.backward_score:
                recommendations.append(
                    "Image is high quality but drifted from prompt - "
                    "increase guidance scale"
                )
            else:
                recommendations.append(
                    "Image matches prompt but quality is low - "
                    "increase inference steps"
                )

        return recommendations

    # =========================================================================
    # PROPERTIES AND UTILITIES
    # =========================================================================

    @property
    def history(self) -> CoherenceHistory:
        """Get generation history."""
        return self._history

    @property
    def corrections_applied(self) -> int:
        """Get number of corrections applied."""
        return self._corrections_applied

    def get_summary_stats(self) -> Dict[str, float]:
        """Get summary statistics across all timesteps."""
        if not self._history.timesteps:
            return {}

        return {
            "avg_bcvf_forward": self._history.get_average("bcvf_forward"),
            "avg_bcvf_backward": self._history.get_average("bcvf_backward"),
            "avg_use_coherence": self._history.get_average("use_coherence"),
            "avg_scc_global": self._history.get_average("scc_global"),
            "avg_combined_weight": self._history.get_average("combined_weight"),
            "min_combined_weight": min(m.combined_weight for m in self._history.timesteps),
            "max_combined_weight": max(m.combined_weight for m in self._history.timesteps),
            "total_issues": sum(len(m.issues) for m in self._history.timesteps),
        }

    def get_layer_coherence_report(
        self,
        layer_states: Optional[Dict[int, Any]] = None,
    ) -> Dict[int, Dict[str, float]]:
        """Get detailed per-layer coherence report."""
        layer_states = layer_states or self._last_layer_states or {}

        layer_coherences = self.scc_engine.compute_layer_coherences(layer_states)

        report = {}
        for layer_idx, result in layer_coherences.items():
            report[layer_idx] = {
                "name": result.layer_name,
                "coherence": result.coherence,
                "semantic_consistency": result.semantic_consistency,
                "resonance": result.resonance,
                "entropy": result.entropy,
                "predictability": result.predictability,
                "quality": result.quality,
            }

        return report


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_monitor(
    mode: GenerationMode = GenerationMode.BALANCED,
    coherence_threshold: float = 0.7,
) -> CoherenceMonitor:
    """Create a coherence monitor with common settings."""
    config = CoherenceConfig(coherence_threshold=coherence_threshold)
    return CoherenceMonitor(coherence_config=config, mode=mode)


def quick_check(
    latents: Any,
    layer_states: Dict[int, Any],
    prompt: str = "",
    text_embeddings: Optional[Any] = None,
) -> Tuple[bool, float]:
    """
    Quick coherence check without full monitoring.

    Returns:
        (passes_threshold, completion_weight)
    """
    monitor = CoherenceMonitor()
    monitor.set_prompt(prompt, text_embeddings)
    metrics = monitor.record_timestep(
        timestep=0,
        latents=latents,
        layer_states=layer_states,
    )

    threshold = monitor.coherence_config.coherence_threshold
    return metrics.combined_weight >= threshold, metrics.combined_weight
