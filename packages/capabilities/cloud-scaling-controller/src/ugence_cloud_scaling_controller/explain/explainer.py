"""Explainer — unified decision explanation engine.

Consolidates explainability from across the stack into a single module
that produces structured, multi-audience explanations:

  1. Operator summary  — one-line tl;dr for dashboards and alerts
  2. Technical detail   — component breakdown for SREs debugging decisions
  3. Audit record       — full state snapshot for compliance and post-mortems

Each explanation is built from the controller's ActionResult plus optional
context from the recommend engine, safety bounds, and execution pipeline.

Design doc reference: L6 Observability — "every decision must be explainable
at three levels: what happened, why, and what would change the outcome."
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ugence_cloud_scaling_controller.controller import ActionResult


class Audience(Enum):
    """Target audience for the explanation."""
    OPERATOR = "operator"       # Dashboard / Slack — one-line summary
    SRE = "sre"                 # Technical detail — component breakdown
    AUDIT = "audit"             # Full state — compliance / post-mortem


class DecisionCategory(Enum):
    """High-level classification of the decision."""
    HOLD = "hold"               # No action — system stable
    SCALE_OUT = "scale_out"     # Adding capacity
    SCALE_IN = "scale_in"       # Reducing capacity
    OBSERVE = "observe"         # Watching — score below action threshold
    SUPPRESSED = "suppressed"   # Would act, but blocked by safety/cooldown/policy


@dataclass
class Factor:
    """A single factor contributing to the decision."""
    name: str
    value: float
    label: str                  # Human-readable interpretation
    influence: str              # "supporting", "opposing", "neutral"
    detail: str = ""            # Optional deeper explanation


@dataclass
class Explanation:
    """Structured decision explanation."""
    # Classification
    category: DecisionCategory
    timestamp: float

    # Operator level — short summary
    summary: str                # e.g. "HOLD — signals stable, coherence 0.82"

    # SRE level — factor breakdown
    factors: List[Factor] = field(default_factory=list)
    dominant_factor: str = ""   # Which factor had the most influence
    counterfactual: str = ""    # "Would scale out if pressure exceeded 0.50"

    # Audit level — full state
    action_score: float = 0.0
    recommendation: str = ""
    replica_delta: int = 0
    metrics_snapshot: Dict[str, float] = field(default_factory=dict)
    component_values: Dict[str, float] = field(default_factory=dict)

    # Optional context from downstream pipeline
    confidence_level: str = ""
    safety_clamped: bool = False
    safety_reason: str = ""
    suppress_reason: str = ""

    def for_audience(self, audience: Audience) -> Dict[str, Any]:
        """Return explanation filtered to audience level.

        Args:
            audience: Target audience.

        Returns:
            Dict suitable for JSON serialization at the requested detail level.
        """
        if audience == Audience.OPERATOR:
            return {
                "summary": self.summary,
                "category": self.category.value,
                "action_score": round(self.action_score, 3),
                "recommendation": self.recommendation,
                "replica_delta": self.replica_delta,
            }

        if audience == Audience.SRE:
            return {
                "summary": self.summary,
                "category": self.category.value,
                "action_score": round(self.action_score, 3),
                "recommendation": self.recommendation,
                "replica_delta": self.replica_delta,
                "dominant_factor": self.dominant_factor,
                "counterfactual": self.counterfactual,
                "factors": [
                    {
                        "name": f.name,
                        "value": round(f.value, 4),
                        "label": f.label,
                        "influence": f.influence,
                    }
                    for f in self.factors
                ],
                "component_values": {
                    k: round(v, 4) for k, v in self.component_values.items()
                },
            }

        # Audience.AUDIT — everything
        return {
            "summary": self.summary,
            "category": self.category.value,
            "timestamp": self.timestamp,
            "action_score": round(self.action_score, 4),
            "recommendation": self.recommendation,
            "replica_delta": self.replica_delta,
            "dominant_factor": self.dominant_factor,
            "counterfactual": self.counterfactual,
            "factors": [
                {
                    "name": f.name,
                    "value": round(f.value, 4),
                    "label": f.label,
                    "influence": f.influence,
                    "detail": f.detail,
                }
                for f in self.factors
            ],
            "component_values": {
                k: round(v, 4) for k, v in self.component_values.items()
            },
            "metrics_snapshot": {
                k: round(v, 4) for k, v in self.metrics_snapshot.items()
            },
            "confidence_level": self.confidence_level,
            "safety_clamped": self.safety_clamped,
            "safety_reason": self.safety_reason,
            "suppress_reason": self.suppress_reason,
        }

    def format_text(self, audience: Audience = Audience.SRE) -> str:
        """Render as human-readable text.

        Args:
            audience: Controls verbosity level.

        Returns:
            Multi-line string suitable for logging or terminal output.
        """
        if audience == Audience.OPERATOR:
            return self.summary

        lines = [self.summary, ""]

        # Factor breakdown
        for f in self.factors:
            marker = {"supporting": "+", "opposing": "-", "neutral": "~"}
            icon = marker.get(f.influence, " ")
            lines.append(f"  [{icon}] {f.name}: {f.value:.3f} — {f.label}")

        if self.dominant_factor:
            lines.append(f"  Dominant: {self.dominant_factor}")
        if self.counterfactual:
            lines.append(f"  Counterfactual: {self.counterfactual}")

        if audience == Audience.AUDIT:
            lines.append("")
            lines.append(f"  Metrics: {self.metrics_snapshot}")
            if self.confidence_level:
                lines.append(f"  Confidence: {self.confidence_level}")
            if self.safety_clamped:
                lines.append(f"  Safety: {self.safety_reason}")
            if self.suppress_reason:
                lines.append(f"  Suppressed: {self.suppress_reason}")

        return "\n".join(lines)


class Explainer:
    """Produces structured explanations from controller decisions.

    Usage:
        explainer = Explainer()
        explanation = explainer.explain(action_result)
        print(explanation.format_text())
        json_payload = explanation.for_audience(Audience.OPERATOR)

    With recommend context:
        explanation = explainer.explain(
            action_result,
            confidence_level="high",
            safety_clamped=True,
            safety_reason="Scale-out clamped from +3 to +2",
        )
    """

    # Action thresholds — used for counterfactual generation
    DEFAULT_THRESHOLDS = {
        "no_action": 0.05,
        "recommend": 0.2,
        "scale_1": 0.5,
        "scale_2": 1.0,
    }

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self.thresholds = thresholds or dict(self.DEFAULT_THRESHOLDS)

    def explain(
        self,
        action: ActionResult,
        confidence_level: str = "",
        safety_clamped: bool = False,
        safety_reason: str = "",
        suppress_reason: str = "",
    ) -> Explanation:
        """Generate a structured explanation from a controller decision.

        Args:
            action: Controller's ActionResult.
            confidence_level: From ConfidenceScorer (optional).
            safety_clamped: Whether safety bounds modified the delta.
            safety_reason: Why safety clamped (optional).
            suppress_reason: Why recommendation was suppressed (optional).

        Returns:
            Explanation with multi-audience rendering.
        """
        category = self._categorize(action, suppress_reason)
        factors = self._extract_factors(action)
        dominant = self._find_dominant(factors)
        counterfactual = self._generate_counterfactual(action, dominant)

        # Component values for audit
        components = {
            "pressure": action.pressure,
            "coherence": action.coherence.coherence,
            "plasticity": action.plasticity.plasticity,
            "resistance": action.plasticity.resistance,
            "misalignment": action.plasticity.misalignment,
            "gain": action.gain.gain,
            "damping": action.damping.damping,
            "identity_deviation": action.identity_deviation,
            "action_score": action.action_score,
        }

        summary = self._build_summary(action, category)

        return Explanation(
            category=category,
            timestamp=time.time(),
            summary=summary,
            factors=factors,
            dominant_factor=dominant,
            counterfactual=counterfactual,
            action_score=action.action_score,
            recommendation=action.recommendation,
            replica_delta=action.replica_delta,
            metrics_snapshot=dict(action.metrics_snapshot),
            component_values=components,
            confidence_level=confidence_level,
            safety_clamped=safety_clamped,
            safety_reason=safety_reason,
            suppress_reason=suppress_reason,
        )

    def _categorize(
        self, action: ActionResult, suppress_reason: str,
    ) -> DecisionCategory:
        """Classify the decision into a high-level category."""
        if suppress_reason:
            return DecisionCategory.SUPPRESSED
        if action.replica_delta > 0:
            return DecisionCategory.SCALE_OUT
        if action.replica_delta < 0:
            return DecisionCategory.SCALE_IN
        if action.recommendation.startswith("observe"):
            return DecisionCategory.OBSERVE
        return DecisionCategory.HOLD

    def _extract_factors(self, action: ActionResult) -> List[Factor]:
        """Extract contributing factors from the action result."""
        factors = []

        # Pressure
        pressure = action.pressure
        if pressure > 0.1:
            p_label = "high demand"
            p_influence = "supporting"
        elif pressure < -0.1:
            p_label = "over-provisioned"
            p_influence = "supporting"
        else:
            p_label = "balanced"
            p_influence = "neutral"
        factors.append(Factor(
            name="Pressure (S_t)",
            value=pressure,
            label=p_label,
            influence=p_influence,
            detail="Weighted demand signal from normalized metrics",
        ))

        # Coherence
        coherence = action.coherence.coherence
        elevated = action.coherence.elevated_count
        if coherence > 0.7:
            c_label = f"coherent ({elevated} signals elevated)"
            c_influence = "supporting"
        elif coherence < 0.4:
            c_label = f"incoherent ({elevated} signals elevated)"
            c_influence = "opposing"
        else:
            c_label = f"moderate ({elevated} signals elevated)"
            c_influence = "neutral"
        factors.append(Factor(
            name="Coherence (C_t)",
            value=coherence,
            label=c_label,
            influence=c_influence,
            detail="Signal agreement across infra/app/business groups",
        ))

        # Plasticity
        plasticity = action.plasticity.plasticity
        if plasticity > 0.6:
            pl_label = "open to change"
            pl_influence = "supporting"
        elif plasticity < 0.3:
            pl_label = "gate closed — system fragile"
            pl_influence = "opposing"
        else:
            pl_label = "partially open"
            pl_influence = "neutral"
        factors.append(Factor(
            name="Plasticity (P_t)",
            value=plasticity,
            label=pl_label,
            influence=pl_influence,
            detail=f"R_t={action.plasticity.resistance:.2f}, M_t={action.plasticity.misalignment:.2f}",
        ))

        # Gain
        gain = action.gain.gain
        g_label = f"{'rate-limited' if action.gain.rate_limited else 'normal'}"
        if gain > 1.5:
            g_label = f"amplified{' (rate-limited)' if action.gain.rate_limited else ''}"
        elif gain < 0.5:
            g_label = f"suppressed{' (rate-limited)' if action.gain.rate_limited else ''}"
        factors.append(Factor(
            name="Gain (G_t)",
            value=gain,
            label=g_label,
            influence="supporting" if gain > 0.8 else "opposing",
            detail=f"G_base * phase_factor * coherence_factor",
        ))

        # Damping
        damping = action.damping.damping
        if damping > 0.9:
            d_label = "minimal damping"
            d_influence = "supporting"
        elif damping < 0.5:
            d_label = "heavy damping — high variance"
            d_influence = "opposing"
        else:
            d_label = "moderate damping"
            d_influence = "neutral"
        factors.append(Factor(
            name="Damping (d_t)",
            value=damping,
            label=d_label,
            influence=d_influence,
            detail=f"{'rate-limited' if action.damping.rate_limited else 'free'}",
        ))

        # Identity deviation
        deviation = action.identity_deviation
        if deviation > 0.6:
            id_label = "anomalous — far from baseline"
            id_influence = "supporting"
        elif deviation > 0.3:
            id_label = "drifting from baseline"
            id_influence = "neutral"
        else:
            id_label = "normal range"
            id_influence = "neutral"
        factors.append(Factor(
            name="Identity Drift",
            value=deviation,
            label=id_label,
            influence=id_influence,
            detail="Distance from learned baseline state",
        ))

        return factors

    def _find_dominant(self, factors: List[Factor]) -> str:
        """Identify which factor most constrained or drove the decision.

        The dominant factor is the one with the lowest value among
        multiplicative components (pressure, plasticity, gain, damping),
        since the action score is their product.
        """
        # Only consider the multiplicative components
        multiplicative = {
            "Pressure (S_t)", "Plasticity (P_t)", "Gain (G_t)", "Damping (d_t)",
        }
        candidates = [f for f in factors if f.name in multiplicative]
        if not candidates:
            return ""

        # The bottleneck is the smallest absolute value
        bottleneck = min(candidates, key=lambda f: abs(f.value))
        return f"{bottleneck.name} = {bottleneck.value:.3f} ({bottleneck.label})"

    def _generate_counterfactual(
        self, action: ActionResult, dominant: str,
    ) -> str:
        """Generate a "what would change the outcome" statement."""
        score = abs(action.action_score)

        # Find the next threshold above current score
        sorted_thresholds = sorted(self.thresholds.items(), key=lambda x: x[1])
        next_threshold = None
        for name, value in sorted_thresholds:
            if value > score:
                next_threshold = (name, value)
                break

        if next_threshold is None:
            return "Action score already at maximum threshold"

        gap = next_threshold[1] - score
        label = next_threshold[0].replace("_", " ")
        return (
            f"Score {score:.3f} is {gap:.3f} below '{label}' threshold "
            f"({next_threshold[1]:.2f})"
        )

    def _build_summary(
        self, action: ActionResult, category: DecisionCategory,
    ) -> str:
        """Build the one-line operator summary."""
        cat_labels = {
            DecisionCategory.HOLD: "HOLD",
            DecisionCategory.SCALE_OUT: "SCALE OUT",
            DecisionCategory.SCALE_IN: "SCALE IN",
            DecisionCategory.OBSERVE: "OBSERVE",
            DecisionCategory.SUPPRESSED: "SUPPRESSED",
        }
        label = cat_labels.get(category, category.value.upper())

        coherence = action.coherence.coherence
        pressure = action.pressure

        if category in (DecisionCategory.SCALE_OUT, DecisionCategory.SCALE_IN):
            return (
                f"{label} {action.replica_delta:+d} — "
                f"score={action.action_score:.3f}, "
                f"coherence={coherence:.2f}, "
                f"pressure={pressure:.2f}"
            )
        return (
            f"{label} — score={action.action_score:.3f}, "
            f"coherence={coherence:.2f}, "
            f"pressure={pressure:.2f}"
        )
