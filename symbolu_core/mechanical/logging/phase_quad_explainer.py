"""
Phase Quad Explainer
====================

Bridge between Phase Quad model internals and the Explanation Telemetry schema.

This module reads from the model's existing diagnostic surfaces:
    - compute_phase_health_diagnostics()  →  R_k, R_q, drift, redundancy
    - get_instrumentation()               →  cache health metrics
    - get_proposal_metrics()              →  confidence, skip rates
    - get_phase_health()                  →  per-layer R_k

...and assembles a unified ExplanationTelemetry record that enterprises can
audit, display, and act on.

Design principles:
    - READ-ONLY: never modifies model state or gradients
    - ZERO-COPY where possible: reads captured tensors, computes scalars
    - OPTIONAL: can be enabled/disabled without affecting training or inference
    - SCHEMA-STABLE: output conforms to telemetry_schema.ExplanationTelemetry

Usage:
    explainer = PhaseQuadExplainer()
    telemetry = explainer.explain(model, response_id="req-123")
    print(telemetry.summary())
    audit_log.record(telemetry.to_dict())
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from symbolu_core.mechanical.logging.telemetry_schema import (
    AttentionProvenance,
    ConfidenceBand,
    EscalationLevel,
    ExplanationTelemetry,
    PathAttribution,
    PolicyDecision,
    PolicyOutcome,
    ProvenanceBlock,
    StabilityBadge,
    StabilityMetrics,
    confidence_to_band,
    stability_to_badge,
)

if TYPE_CHECKING:
    pass  # torch types only needed at runtime


class PhaseQuadExplainer:
    """
    Assembles ExplanationTelemetry from Phase Quad model internals.

    Collects from three aggregation surfaces already on the transformer:
        model.get_phase_health()      → R_k per layer
        model.get_instrumentation()   → cache hit rate, cosine similarity
        model.get_proposal_metrics()  → confidence, skip rate

    Plus the per-forward diagnostic capture (when enabled):
        compute_phase_health_diagnostics(model) → full health dict

    Architecture mapping:
        Local path   = LocalWindowAttention   (syntax, recency)
        Phase path   = BindingCachePhaseState  (semantic memory, always active)
        Quad path    = BindingCacheQuadQuery    (structured retrieval)
        Control path = Ontological State + SRK  (Koshas, Vrittis, Gunas)
    """

    def __init__(
        self,
        enable_deep_diagnostics: bool = False,
        confidence_threshold: float = 0.7,
    ):
        """
        Args:
            enable_deep_diagnostics: If True, call enable_health_diagnostics_capture
                on the model before forward and compute full health diagnostics
                after. More expensive but gives R_k, drift, head_redundancy.
            confidence_threshold: Phase confidence above which quad is skippable.
                Must match the model's own confidence_threshold.
        """
        self.enable_deep_diagnostics = enable_deep_diagnostics
        self.confidence_threshold = confidence_threshold

    def explain(
        self,
        model: Any,
        response_id: str = "",
        health_diagnostics: Optional[Dict[str, float]] = None,
        ontological_state: Optional[Dict[str, float]] = None,
        coherence_score: Optional[float] = None,
        sequence_length: int = 0,
    ) -> ExplanationTelemetry:
        """
        Produce an ExplanationTelemetry record from model internals.

        This is designed to be called AFTER a forward pass completes.
        It reads instrumentation metrics that the model already computes
        during inference — no extra forward passes required.

        Args:
            model: The PhaseQuadTransformer (or any module exposing
                   get_phase_health / get_instrumentation / get_proposal_metrics).
            response_id: Unique ID for this response (for audit correlation).
            health_diagnostics: Pre-computed result of
                compute_phase_health_diagnostics(model). If None and
                enable_deep_diagnostics is True, we will call it.
            ontological_state: Optional dict with control plane signals:
                {kosha_depth, vritti_reliability, guna_energy, ...}
            coherence_score: Optional aggregate coherence from CoherenceObserver.
            sequence_length: Token count for metadata.

        Returns:
            ExplanationTelemetry: Complete, JSON-serializable explanation record.
        """
        # --- Collect raw metrics from model ---
        phase_health = _safe_call(model, "get_phase_health", {})
        instrumentation = _safe_call(model, "get_instrumentation", {})
        proposal_metrics = _safe_call(model, "get_proposal_metrics", {})

        # Deep diagnostics (optional — requires prior capture)
        if health_diagnostics is None and self.enable_deep_diagnostics:
            health_diagnostics = _try_compute_health_diagnostics(model)
        if health_diagnostics is None:
            health_diagnostics = {}

        # --- A) Path Attribution ---
        routing = self._compute_path_attribution(
            proposal_metrics, phase_health, instrumentation
        )

        # --- B) Attention Provenance ---
        provenance = self._compute_provenance(instrumentation)

        # --- C) Stability & Drift ---
        stability = self._compute_stability(health_diagnostics, phase_health)

        # --- D) Policy & Confidence ---
        policy = self._compute_policy(
            proposal_metrics,
            stability,
            ontological_state or {},
            coherence_score,
        )

        # --- Infer layer count from per-layer data ---
        layer_count = len(phase_health.get("r_k_per_layer", []))

        return ExplanationTelemetry(
            routing=routing,
            provenance=provenance,
            stability=stability,
            policy=policy,
            response_id=response_id,
            timestamp_ms=int(time.time() * 1000),
            model_version="phase_quad_v11.0.0",
            layer_count=layer_count,
            sequence_length=sequence_length,
        )

    # ------------------------------------------------------------------
    # A) Path Attribution
    # ------------------------------------------------------------------

    def _compute_path_attribution(
        self,
        proposal_metrics: Dict[str, Any],
        phase_health: Dict[str, Any],
        instrumentation: Dict[str, Any],
    ) -> PathAttribution:
        """
        Estimate Local / Phase / Quad contribution ratios.

        The three-path architecture combines as:
            attn_out = local_out + mem_out   (additive, not competitive)

        Where mem_out comes from Phase (always active) + Quad (conditional).
        We estimate the split using:
            - Quad skip_rate → how often quad was bypassed
            - Confidence mean → how much phase trusted its own state
            - Cache hit rate → how useful quad retrieval was when invoked
        """
        skip_rate = proposal_metrics.get("skip_rate", 0.0)
        confidence_mean = proposal_metrics.get("confidence_mean", 0.5)
        cache_hit_rate = instrumentation.get("cache_hit_rate", 0.0)

        # Phase is always active.  Quad is conditional.
        # When quad is skipped, all memory contribution is Phase.
        # When quad runs, its contribution depends on cache_hit_rate.
        quad_effective = (1.0 - skip_rate) * cache_hit_rate
        phase_effective = 1.0 - quad_effective

        # Local vs Memory split: Local handles syntax, Memory handles semantics.
        # Heuristic: high confidence → phase/quad dominate; low → local matters more.
        # This is a first-order approximation; precise attribution requires
        # gradient-based methods or ablation studies.
        local_weight = max(0.3, 1.0 - confidence_mean)  # Floor at 30%
        memory_weight = 1.0 - local_weight

        total = local_weight + memory_weight
        local_ratio = local_weight / total
        memory_ratio = memory_weight / total

        return PathAttribution(
            local_ratio=round(local_ratio, 4),
            phase_ratio=round(memory_ratio * phase_effective, 4),
            quad_ratio=round(memory_ratio * quad_effective, 4),
            confidence_mean=round(confidence_mean, 4),
            quad_skip_rate=round(skip_rate, 4),
            per_layer_confidence=proposal_metrics.get("per_layer_confidence", []),
            per_layer_skip_rate=proposal_metrics.get("per_layer_skip_rate", []),
        )

    # ------------------------------------------------------------------
    # B) Attention Provenance
    # ------------------------------------------------------------------

    def _compute_provenance(
        self,
        instrumentation: Dict[str, Any],
    ) -> AttentionProvenance:
        """
        Build provenance from Quad's cache instrumentation.

        In Phase Quad, the "source blocks" are the Top-K cache entries
        retrieved by BindingCacheQuadQuery. Cache health metrics tell us
        how diverse and useful those retrievals were.
        """
        return AttentionProvenance(
            cache_hit_rate=round(instrumentation.get("cache_hit_rate", 0.0), 4),
            cache_key_cosine_mean=round(
                instrumentation.get("cache_key_cosine_mean", 0.0), 4
            ),
            cache_key_cosine_max=round(
                instrumentation.get("cache_key_cosine_max", 0.0), 4
            ),
            # Block entropy: inverse of cosine similarity (high sim = low diversity)
            block_entropy=round(
                max(0.0, 1.0 - instrumentation.get("cache_key_cosine_mean", 0.0)),
                4,
            ),
        )

    # ------------------------------------------------------------------
    # C) Stability & Drift
    # ------------------------------------------------------------------

    def _compute_stability(
        self,
        health: Dict[str, float],
        phase_health: Dict[str, Any],
    ) -> StabilityMetrics:
        """
        Compute stability signals from phase health diagnostics.

        Health diagnostics come from compute_phase_health_diagnostics():
            r_k_mean, r_q_mean, amp_phase_corr, head_redundancy,
            phase_drift_mean, phase_drift_std

        Phase health comes from get_phase_health():
            r_k_mean, r_k_per_layer
        """
        r_k = health.get("r_k_mean", phase_health.get("r_k_mean", 0.5))
        r_q = health.get("r_q_mean", 0.5)
        amp_corr = health.get("amp_phase_corr", 0.0)
        redundancy = health.get("head_redundancy", 0.0)
        drift_mean = health.get("phase_drift_mean", 0.0)
        drift_std = health.get("phase_drift_std", 0.0)

        # Reversal risk: composite of drift instability + head redundancy
        # High drift_std means inconsistent step-to-step behavior
        # High redundancy means heads can't disagree to self-correct
        reversal_risk = _clamp01(
            0.3 * min(drift_std / 0.3, 1.0)
            + 0.3 * max(0.0, (redundancy - 0.5) / 0.5)
            + 0.2 * abs(amp_corr)
            + 0.2 * _collapse_risk(r_k)
        )

        badge = stability_to_badge(drift_mean, r_k, redundancy, reversal_risk)

        return StabilityMetrics(
            r_k_mean=round(r_k, 4),
            r_k_std=round(health.get("r_k_std", 0.0), 4),
            r_q_mean=round(r_q, 4),
            amp_phase_correlation=round(amp_corr, 4),
            head_redundancy=round(redundancy, 4),
            phase_drift_mean=round(drift_mean, 4),
            phase_drift_std=round(drift_std, 4),
            reversal_risk=round(reversal_risk, 4),
            stability_badge=badge,
        )

    # ------------------------------------------------------------------
    # D) Policy & Confidence
    # ------------------------------------------------------------------

    def _compute_policy(
        self,
        proposal_metrics: Dict[str, Any],
        stability: StabilityMetrics,
        ontological_state: Dict[str, float],
        coherence_score: Optional[float],
    ) -> PolicyDecision:
        """
        Compute the policy decision (ConfidenceGate / Sentinel).

        Combines:
            - Phase confidence (from proposal_metrics)
            - Stability badge (GREEN/YELLOW/RED)
            - Ontological control plane (Koshas, Vrittis, Gunas)
            - Coherence score (from CoherenceObserver)
        """
        raw_confidence = proposal_metrics.get("confidence_mean", 0.5)

        # Penalise confidence if stability is poor
        stability_penalty = {
            StabilityBadge.GREEN: 0.0,
            StabilityBadge.YELLOW: 0.1,
            StabilityBadge.RED: 0.3,
        }[stability.stability_badge]

        effective_confidence = _clamp01(raw_confidence - stability_penalty)
        band = confidence_to_band(effective_confidence)

        # Coherence integration (if available from CoherenceObserver)
        coh = coherence_score if coherence_score is not None else effective_confidence

        # Escalation logic
        escalation = EscalationLevel.NONE
        outcome = PolicyOutcome.ALLOWED
        verification_needed = False
        verification_reason = ""

        if stability.stability_badge == StabilityBadge.RED:
            escalation = EscalationLevel.VERIFY
            verification_needed = True
            verification_reason = "Stability RED — high drift or phase collapse risk"

        if coh < 0.4:
            escalation = EscalationLevel.VERIFY
            verification_needed = True
            verification_reason = f"Low coherence ({coh:.2f}) — reasoning may be unreliable"

        if stability.reversal_risk > 0.7 and coh < 0.5:
            escalation = EscalationLevel.BLOCK
            outcome = PolicyOutcome.BLOCKED
            verification_reason = (
                f"Blocked: reversal_risk={stability.reversal_risk:.2f}, "
                f"coherence={coh:.2f}"
            )

        if outcome == PolicyOutcome.ALLOWED and verification_needed:
            outcome = PolicyOutcome.CONFIRM_REQUIRED

        # Adversarial drift detection: sudden gate volatility spike
        adversarial = stability.gate_volatility > 0.5

        return PolicyDecision(
            confidence_band=band,
            confidence_score=round(effective_confidence, 4),
            escalation_level=escalation,
            policy_outcome=outcome,
            kosha_depth=round(ontological_state.get("kosha_depth", 0.0), 4),
            vritti_reliability=round(ontological_state.get("vritti_reliability", 0.0), 4),
            guna_energy=round(ontological_state.get("guna_energy", 0.0), 4),
            tool_execution_allowed=(outcome != PolicyOutcome.BLOCKED),
            tool_block_reason=verification_reason if outcome == PolicyOutcome.BLOCKED else "",
            verification_needed=verification_needed,
            verification_reason=verification_reason,
            coherence_score=round(coh, 4),
            prompt_injection_detected=False,  # Reserved for Sentinel integration
            adversarial_drift_detected=adversarial,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_call(obj: Any, method: str, default: Any) -> Any:
    """Call obj.method() if it exists, otherwise return default."""
    fn = getattr(obj, method, None)
    if fn is not None and callable(fn):
        try:
            return fn()
        except Exception:
            return default
    return default


def _try_compute_health_diagnostics(model: Any) -> Optional[Dict[str, float]]:
    """
    Attempt to call compute_phase_health_diagnostics if available.

    This requires torch and the diagnostic functions from phase_transformer.
    Returns None if unavailable (e.g. in CI without torch).
    """
    try:
        from symbolu_core.phase_transformer import compute_phase_health_diagnostics
        return compute_phase_health_diagnostics(model)
    except (ImportError, Exception):
        return None


def _clamp01(x: float) -> float:
    """Clamp to [0, 1]."""
    return max(0.0, min(1.0, x))


def _collapse_risk(r_k: float) -> float:
    """
    Map R_k to collapse risk [0, 1].

    Healthy range: 0.05 < R_k < 5.0
    Collapsed: R_k < 0.01 or R_k > 10
    """
    if r_k < 0.01:
        return 1.0
    elif r_k < 0.05:
        return 0.5
    elif r_k > 10.0:
        return 1.0
    elif r_k > 5.0:
        return 0.5
    return 0.0


__all__ = ["PhaseQuadExplainer"]
