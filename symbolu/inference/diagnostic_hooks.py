"""
Diagnostic Hooks — Advanced Observability Modules for Inference Runtime.

Integrates MirrorBalance and CausalLayer from guna_modulation/ into
the inference path in diagnostic/audit mode ONLY.  These hooks:

- Never modify generation behavior
- Produce trace metadata for observability
- Are gated behind explicit enable flags
- Fail silently on error (diagnostics should never crash generation)

Phase 4: Advanced observability integration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =========================================================================
# Configuration
# =========================================================================

@dataclass
class DiagnosticHooksConfig:
    """Configuration for inference diagnostic hooks.

    All hooks are disabled by default and must be explicitly enabled.
    """
    enable_mirror_balance: bool = False
    enable_causal_attribution: bool = False
    # Maximum trace entries to retain (prevents unbounded memory)
    max_trace_entries: int = 200


# =========================================================================
# Diagnostic result
# =========================================================================

@dataclass
class DiagnosticSnapshot:
    """Single-step diagnostic output from all enabled hooks.

    Attributes:
        step: Generation step number.
        mirror_balance: MirrorBalance diagnostics, or None if disabled.
        causal_attribution: CausalLayer diagnostics, or None if disabled.
        errors: Any errors encountered (diagnostics should never crash).
    """
    step: int = 0
    mirror_balance: Optional[Dict[str, Any]] = None
    causal_attribution: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"step": self.step}
        if self.mirror_balance is not None:
            result["mirror_balance"] = self.mirror_balance
        if self.causal_attribution is not None:
            result["causal_attribution"] = self.causal_attribution
        if self.errors:
            result["errors"] = self.errors
        return result


# =========================================================================
# MirrorBalance diagnostic hook
# =========================================================================

def _compute_mirror_balance_diagnostic(
    sattva: float,
    rajas: float,
    tamas: float,
    entropy: float = 0.5,
    motion: float = 0.5,
) -> Dict[str, Any]:
    """Compute MirrorBalance diagnostics without importing the full engine.

    Uses the core mirror theory directly:
    - Guna Mirror: S ↔ T swap (Rajas neutral)
    - Balance = 1 - |original - mirror|
    - Asymmetry = |S - T|

    This avoids importing guna_modulation's full MirrorBalanceEngine
    which has deep dependencies.  Instead, we compute the key diagnostic
    metrics inline.
    """
    # Guna mirror: swap S and T
    mirror_s = tamas
    mirror_t = sattva
    mirror_r = rajas

    # Guna asymmetry: |S - T| (0 = balanced, 1 = extreme)
    guna_asymmetry = abs(sattva - tamas)

    # Entropy mirror: H' = 1 - H
    entropy_mirror = 1.0 - entropy
    entropy_asymmetry = abs(entropy - 0.5) * 2.0  # 0 at H=0.5, 1 at H=0 or H=1

    # Motion mirror: M' = 1 - M
    motion_mirror = 1.0 - motion
    motion_asymmetry = abs(motion - 0.5) * 2.0

    # Overall balance score: 1 = perfectly balanced, 0 = maximally imbalanced
    balance_score = 1.0 - (guna_asymmetry * 0.5 + entropy_asymmetry * 0.3 + motion_asymmetry * 0.2)
    balance_score = max(0.0, min(1.0, balance_score))

    # Mirror correction direction
    correction_direction = "none"
    if guna_asymmetry > 0.2:
        correction_direction = "toward_tamas" if sattva > tamas else "toward_sattva"

    return {
        "guna_asymmetry": round(guna_asymmetry, 4),
        "entropy_asymmetry": round(entropy_asymmetry, 4),
        "motion_asymmetry": round(motion_asymmetry, 4),
        "balance_score": round(balance_score, 4),
        "correction_direction": correction_direction,
        "mirror_guna": {
            "sattva": round(mirror_s, 4),
            "rajas": round(mirror_r, 4),
            "tamas": round(mirror_t, 4),
        },
    }


# =========================================================================
# CausalLayer diagnostic hook
# =========================================================================

def _compute_causal_attribution_diagnostic(
    guna_sattva: float,
    guna_rajas: float,
    guna_tamas: float,
    coherence_score: float = 0.5,
    vritti_fact: float = 0.5,
) -> Dict[str, Any]:
    """Compute CausalLayer attribution diagnostics.

    Uses the causal theory: SIGNAL → GUNA → STATE → OUTPUT.
    Approximates the Average Treatment Effect of each guna component
    on the output quality (coherence + vritti reliability).

    This is a lightweight diagnostic approximation, not the full
    do-calculus engine from causal_layer.py.
    """
    # Output quality proxy: blend of coherence and reliability
    output_quality = coherence_score * 0.6 + vritti_fact * 0.4

    # Approximate causal contributions (linear attribution)
    # Sattva → positive effect on quality
    sattva_effect = guna_sattva * 0.6
    # Rajas → mixed effect (some dynamism helps, too much hurts)
    rajas_effect = guna_rajas * 0.2 - (guna_rajas ** 2) * 0.3
    # Tamas → negative effect (inertia hurts quality)
    tamas_effect = -guna_tamas * 0.4

    # Total attribution
    total_effect = sattva_effect + rajas_effect + tamas_effect

    # Dominant causal factor
    effects = {
        "sattva": sattva_effect,
        "rajas": rajas_effect,
        "tamas": tamas_effect,
    }
    dominant_factor = max(effects, key=lambda k: abs(effects[k]))

    return {
        "output_quality_proxy": round(output_quality, 4),
        "causal_effects": {k: round(v, 4) for k, v in effects.items()},
        "total_causal_effect": round(total_effect, 4),
        "dominant_causal_factor": dominant_factor,
        "attribution_method": "linear_approximation",
    }


# =========================================================================
# Main hook class
# =========================================================================

class InferenceDiagnosticHooks:
    """Manages diagnostic hooks for inference runtime.

    All hooks are observation-only and never influence generation.
    Failed hooks are caught and logged, never propagated.

    Usage::

        hooks = InferenceDiagnosticHooks(DiagnosticHooksConfig(
            enable_mirror_balance=True,
            enable_causal_attribution=True,
        ))

        # Per generation step:
        snapshot = hooks.record_step(
            step=42,
            sattva=0.5, rajas=0.3, tamas=0.2,
            coherence_score=0.7,
            vritti_fact=0.6,
        )

        # After generation:
        trace = hooks.get_trace()
        summary = hooks.get_summary()
    """

    def __init__(self, config: Optional[DiagnosticHooksConfig] = None):
        self.config = config or DiagnosticHooksConfig()
        self._trace: List[DiagnosticSnapshot] = []

    @property
    def enabled(self) -> bool:
        """Whether any diagnostic hook is enabled."""
        return (
            self.config.enable_mirror_balance or
            self.config.enable_causal_attribution
        )

    def record_step(
        self,
        step: int,
        sattva: float = 0.33,
        rajas: float = 0.33,
        tamas: float = 0.34,
        entropy: float = 0.5,
        motion: float = 0.5,
        coherence_score: float = 0.5,
        vritti_fact: float = 0.5,
    ) -> DiagnosticSnapshot:
        """Record diagnostics for a single generation step.

        Args:
            step: Generation step number.
            sattva: Current Sattva value.
            rajas: Current Rajas value.
            tamas: Current Tamas value.
            entropy: Current entropy estimate.
            motion: Current motion/transformation estimate.
            coherence_score: Current coherence score.
            vritti_fact: Current FACT vritti activation.

        Returns:
            DiagnosticSnapshot for this step.
        """
        snapshot = DiagnosticSnapshot(step=step)

        if self.config.enable_mirror_balance:
            try:
                snapshot.mirror_balance = _compute_mirror_balance_diagnostic(
                    sattva, rajas, tamas, entropy, motion,
                )
            except Exception as e:
                snapshot.errors.append(f"mirror_balance: {e}")
                logger.debug("MirrorBalance diagnostic failed: %s", e)

        if self.config.enable_causal_attribution:
            try:
                snapshot.causal_attribution = _compute_causal_attribution_diagnostic(
                    sattva, rajas, tamas, coherence_score, vritti_fact,
                )
            except Exception as e:
                snapshot.errors.append(f"causal_attribution: {e}")
                logger.debug("CausalAttribution diagnostic failed: %s", e)

        # Store trace (bounded)
        self._trace.append(snapshot)
        if len(self._trace) > self.config.max_trace_entries:
            self._trace = self._trace[-self.config.max_trace_entries:]

        return snapshot

    def get_trace(self) -> List[Dict[str, Any]]:
        """Get full diagnostic trace as serializable dicts."""
        return [s.to_dict() for s in self._trace]

    def get_summary(self) -> Dict[str, Any]:
        """Get aggregate summary of diagnostic trace."""
        if not self._trace:
            return {"steps": 0, "hooks_enabled": self.enabled}

        summary: Dict[str, Any] = {
            "steps": len(self._trace),
            "hooks_enabled": self.enabled,
            "errors_total": sum(len(s.errors) for s in self._trace),
        }

        if self.config.enable_mirror_balance:
            balances = [
                s.mirror_balance["balance_score"]
                for s in self._trace
                if s.mirror_balance is not None
            ]
            if balances:
                summary["mirror_balance"] = {
                    "avg_balance": round(sum(balances) / len(balances), 4),
                    "min_balance": round(min(balances), 4),
                    "max_balance": round(max(balances), 4),
                }

        if self.config.enable_causal_attribution:
            qualities = [
                s.causal_attribution["output_quality_proxy"]
                for s in self._trace
                if s.causal_attribution is not None
            ]
            if qualities:
                summary["causal_attribution"] = {
                    "avg_quality_proxy": round(sum(qualities) / len(qualities), 4),
                    "min_quality_proxy": round(min(qualities), 4),
                    "max_quality_proxy": round(max(qualities), 4),
                }

        return summary

    def clear(self) -> None:
        """Clear diagnostic trace."""
        self._trace = []
