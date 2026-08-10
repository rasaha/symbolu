#!/usr/bin/env python3
"""
Adaptive Diagnostic Controller — Appendix F Stage 7B
=====================================================

Converts embedding diagnostics from passive logging to active adaptive
feedback. Monitors projector drift, adapter gate magnitude, primitive
cache shift, and component norm ratio — then triggers corrective actions
when thresholds are crossed.

Diagnostic signals and their adaptive responses::

    ┌──────────────────────┬───────────────┬──────────────────────────────┐
    │ Diagnostic Signal    │ Threshold     │ Adaptive Response            │
    ├──────────────────────┼───────────────┼──────────────────────────────┤
    │ Projector drift      │ > 0.05/step   │ Reduce projector LR by 50%   │
    │ Adapter gate mag     │ > 2.0         │ Clip gate to [-1.5, 1.5]     │
    │ Primitive cache Δ    │ > 0.1/epoch   │ Trigger cache recomputation  │
    │ Component norm ratio │ > 3.0         │ Apply per-component norm     │
    └──────────────────────┴───────────────┴──────────────────────────────┘

Reference: Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.10.6.2

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 7B — Embedding Diagnostics → Adaptive Feedback
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class DiagnosticSignals:
    """Structured diagnostic signals replacing print-based logging.

    Attributes:
        projector_drift: Cosine distance of state projector outputs between
            snapshots. High values indicate rapid change.
        adapter_gate_magnitude: Absolute magnitude of the phase adapter gate.
            High values indicate aggressive steering.
        primitive_cache_shift: Maximum cosine drift across primitive caches
            (P_tok, R_tok, V_tok, G_tok) per epoch.
        component_norm_ratio: Ratio of max to min component norms across
            the 12 ontological dimensions. High = dominance.
        step: Training step at which signals were captured.
    """
    projector_drift: float = 0.0
    adapter_gate_magnitude: float = 0.0
    primitive_cache_shift: float = 0.0
    component_norm_ratio: float = 1.0
    step: int = 0


@dataclass
class AdaptiveResponse:
    """A corrective action triggered by a diagnostic threshold crossing.

    Attributes:
        signal_name: Which diagnostic signal triggered this response.
        action: Description of the corrective action to take.
        severity: 'info', 'warning', or 'critical'.
        value: The diagnostic signal value that triggered the response.
        threshold: The threshold that was exceeded.
    """
    signal_name: str = ""
    action: str = ""
    severity: str = "info"
    value: float = 0.0
    threshold: float = 0.0


@dataclass
class AdaptiveDiagnosticConfig:
    """Configuration for the adaptive diagnostic controller.

    Attributes:
        enable: Master switch for Stage 7B adaptive responses.
        projector_drift_threshold: Max acceptable drift per step.
        adapter_gate_max: Max acceptable gate magnitude.
        adapter_gate_clip: Clip range for gate when threshold exceeded.
        cache_shift_threshold: Max acceptable cache drift per epoch.
        norm_ratio_threshold: Max acceptable component norm ratio.
        lr_reduction_factor: Factor to reduce LR by when drift is high.
        history_window: Number of recent signals to retain for trend analysis.
    """
    enable: bool = True
    projector_drift_threshold: float = 0.05
    adapter_gate_max: float = 2.0
    adapter_gate_clip: float = 1.5
    cache_shift_threshold: float = 0.1
    norm_ratio_threshold: float = 3.0
    lr_reduction_factor: float = 0.5
    history_window: int = 50


class AdaptiveDiagnosticController:
    """Monitors diagnostics and triggers adaptive corrections.

    Replaces passive print-based logging from EmbeddingDiagnostics with
    structured DiagnosticSignals and actionable AdaptiveResponses.

    Usage::

        controller = AdaptiveDiagnosticController()

        # During training, after each diagnostic snapshot:
        signals = DiagnosticSignals(
            projector_drift=0.08,
            adapter_gate_magnitude=2.5,
            primitive_cache_shift=0.03,
            component_norm_ratio=1.8,
            step=1000,
        )
        responses = controller.check(signals)

        # Apply adaptive responses
        for r in responses:
            if r.action == "reduce_projector_lr":
                optimizer.param_groups[proj_group]["lr"] *= controller.config.lr_reduction_factor
            elif r.action == "clip_adapter_gate":
                gate.data.clamp_(-controller.config.adapter_gate_clip,
                                  controller.config.adapter_gate_clip)
            elif r.action == "recompute_cache":
                model.recompute_primitive_caches()
            elif r.action == "normalize_components":
                model.apply_component_normalization()

    Attributes:
        config: AdaptiveDiagnosticConfig with thresholds and responses.
        history: Rolling window of recent DiagnosticSignals for trends.
    """

    def __init__(self, config: AdaptiveDiagnosticConfig = None):
        self.config = config or AdaptiveDiagnosticConfig()
        self.history: List[DiagnosticSignals] = []
        self._response_counts: Dict[str, int] = {
            "reduce_projector_lr": 0,
            "clip_adapter_gate": 0,
            "recompute_cache": 0,
            "normalize_components": 0,
        }

    def check(self, signals: DiagnosticSignals) -> List[AdaptiveResponse]:
        """Check diagnostic signals against thresholds and return responses.

        Args:
            signals: Current diagnostic signals.

        Returns:
            List of AdaptiveResponse actions to take. Empty if all healthy.
        """
        # Record history
        self.history.append(signals)
        if len(self.history) > self.config.history_window:
            self.history = self.history[-self.config.history_window:]

        if not self.config.enable:
            return []

        responses = []

        # Check projector drift
        if signals.projector_drift > self.config.projector_drift_threshold:
            responses.append(AdaptiveResponse(
                signal_name="projector_drift",
                action="reduce_projector_lr",
                severity="warning",
                value=signals.projector_drift,
                threshold=self.config.projector_drift_threshold,
            ))
            self._response_counts["reduce_projector_lr"] += 1

        # Check adapter gate magnitude
        if signals.adapter_gate_magnitude > self.config.adapter_gate_max:
            responses.append(AdaptiveResponse(
                signal_name="adapter_gate_magnitude",
                action="clip_adapter_gate",
                severity="warning",
                value=signals.adapter_gate_magnitude,
                threshold=self.config.adapter_gate_max,
            ))
            self._response_counts["clip_adapter_gate"] += 1

        # Check primitive cache shift
        if signals.primitive_cache_shift > self.config.cache_shift_threshold:
            responses.append(AdaptiveResponse(
                signal_name="primitive_cache_shift",
                action="recompute_cache",
                severity="warning",
                value=signals.primitive_cache_shift,
                threshold=self.config.cache_shift_threshold,
            ))
            self._response_counts["recompute_cache"] += 1

        # Check component norm ratio
        if signals.component_norm_ratio > self.config.norm_ratio_threshold:
            responses.append(AdaptiveResponse(
                signal_name="component_norm_ratio",
                action="normalize_components",
                severity="critical" if signals.component_norm_ratio > 10.0 else "warning",
                value=signals.component_norm_ratio,
                threshold=self.config.norm_ratio_threshold,
            ))
            self._response_counts["normalize_components"] += 1

        return responses

    def get_trend(self) -> Dict[str, Any]:
        """Analyze trends in recent diagnostic history.

        Returns:
            Dict with trend indicators:
                - projector_drift_trend: 'stable', 'increasing', or 'decreasing'
                - mean_gate_magnitude: Average gate magnitude over window.
                - response_counts: Total corrective actions triggered.
                - healthy: True if no responses triggered in recent history.
        """
        if len(self.history) < 2:
            return {
                "projector_drift_trend": "stable",
                "mean_gate_magnitude": 0.0,
                "response_counts": dict(self._response_counts),
                "healthy": True,
            }

        # Drift trend (compare first half vs second half)
        mid = len(self.history) // 2
        first_half = [s.projector_drift for s in self.history[:mid]]
        second_half = [s.projector_drift for s in self.history[mid:]]
        mean_first = sum(first_half) / len(first_half) if first_half else 0
        mean_second = sum(second_half) / len(second_half) if second_half else 0

        if mean_second > mean_first * 1.2:
            drift_trend = "increasing"
        elif mean_second < mean_first * 0.8:
            drift_trend = "decreasing"
        else:
            drift_trend = "stable"

        # Mean gate magnitude
        gate_mags = [s.adapter_gate_magnitude for s in self.history]
        mean_gate = sum(gate_mags) / len(gate_mags)

        # Recent health: no responses in last 10 signals
        recent = self.history[-10:]
        healthy = all(
            s.projector_drift <= self.config.projector_drift_threshold
            and s.adapter_gate_magnitude <= self.config.adapter_gate_max
            and s.primitive_cache_shift <= self.config.cache_shift_threshold
            and s.component_norm_ratio <= self.config.norm_ratio_threshold
            for s in recent
        )

        return {
            "projector_drift_trend": drift_trend,
            "mean_gate_magnitude": mean_gate,
            "response_counts": dict(self._response_counts),
            "healthy": healthy,
        }

    def reset(self) -> None:
        """Reset all state."""
        self.history.clear()
        self._response_counts = {k: 0 for k in self._response_counts}
