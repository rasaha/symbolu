"""
UCF Signal Adapter — Consciousness Stability → Governance Bridge
================================================================

Phase C3: Integrates the Unified Consciousness Formula (UCF) into the
governance framework as a bounded, auditable consciousness stability signal.

UCF is a deterministic weighted blend of 5 pipeline signals:
    coherence_v3_quality (0.30), drift_fusion_stability (0.25),
    entropy_stability (0.20), schema_stability (0.15),
    identity_harmonics (0.10)

It produces a composite score [0.0, 1.0] and a stability band
(stable / transitional / unstable).

This adapter provides two resolution paths:
    1. Pre-computed ``UnifiedConsciousnessState`` from pipeline metadata
    2. Direct ``compute_ucf()`` from governance-available signals

The adapter does NOT depend on ``ucf_resolver.py`` (pipeline-specific)
or ``coherence_engine.py``. It only depends on:
    - ``ucf_formula.compute_ucf()`` (pure deterministic function)
    - ``ucf_schema.UnifiedConsciousnessState`` (frozen dataclass)

Relationship to Phase C2:
    The C2 coherence_state_adapter passes ``ucf_coi`` and ``ucf_csi``
    as individual sub-indices from CoherenceState. This adapter provides
    the **composite** UCF score and stability band, which is a higher-level
    consciousness stability summary. They are complementary: C2 carries
    the raw sub-indices, this adapter carries the composite view.

Design:
    Follows the signal adapter pattern (frozen Resolution, pure function,
    fail-closed, bounded penalty, stricter-only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from agentic.core.consciousness.ucf_formula import compute_ucf
from agentic.core.consciousness.ucf_schema import (
    StabilityBand,
    UnifiedConsciousnessState,
    create_neutral_state,
)


# =========================================================================
# Constants
# =========================================================================

# Max confidence penalty from UCF instability.
_MAX_PENALTY: float = 0.05

# Penalty only applies when UCF is in the unstable band.
# No penalty for stable or transitional.
_UNSTABLE_PENALTY: float = 0.05
_TRANSITIONAL_PENALTY: float = 0.0  # informational only


# =========================================================================
# Governance-facing contract
# =========================================================================

@dataclass(frozen=True)
class UCFResolution:
    """Governance-safe view of the Unified Consciousness Formula.

    Field categories
    ----------------

    BEHAVIOR-AFFECTING — may influence governance confidence or escalation:
        ucf_score               Composite consciousness stability [0, 1].
                                Higher = more stable.
        stability_band          Categorical band: stable/transitional/unstable.

    AUDIT / EXPLAINABILITY — for audit, replay, and rationale:
        contributing_factors    Breakdown by factor name → value [0, 1].
                                Keys: coherence_v3_quality, drift_fusion_stability,
                                entropy_stability, schema_stability, identity_harmonics.
        ucf_confidence          Data availability confidence [0, 1].
                                1.0 = all 5 inputs present, 0.0 = none.
        computation_source      "precomputed" or "governance_computed".

    ADAPTER METADATA:
        confidence_penalty      Bounded [0, _MAX_PENALTY] stricter-only penalty.
        escalation_bias         Whether escalation should be bumped.
        reason_codes            Machine-readable governance reason codes.
        available               Whether signal was successfully resolved.
        source_detail           Human-readable provenance description.
    """

    # --- Behavior-affecting ---
    ucf_score: Optional[float]
    stability_band: Optional[str]

    # --- Audit / explainability ---
    contributing_factors: Optional[Dict[str, float]]
    ucf_confidence: Optional[float]
    computation_source: Optional[str]

    # --- Adapter metadata ---
    confidence_penalty: float
    escalation_bias: bool
    reason_codes: Tuple[str, ...]
    available: bool
    source_detail: str

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to audit-safe dictionary."""
        d: Dict[str, Any] = {
            "ucf_score": round(self.ucf_score, 6) if self.ucf_score is not None else None,
            "stability_band": self.stability_band,
            "contributing_factors": (
                {k: round(v, 6) for k, v in self.contributing_factors.items()}
                if self.contributing_factors else None
            ),
            "ucf_confidence": (
                round(self.ucf_confidence, 6) if self.ucf_confidence is not None else None
            ),
            "computation_source": self.computation_source,
            "confidence_penalty": round(self.confidence_penalty, 6),
            "escalation_bias": self.escalation_bias,
            "reason_codes": list(self.reason_codes),
            "available": self.available,
            "source_detail": self.source_detail,
        }
        return d


# =========================================================================
# Empty/fallback resolution
# =========================================================================

def _empty_resolution(detail: str = "no UCF data available") -> UCFResolution:
    """Fail-closed: zero penalty, no escalation. Absence never weakens."""
    return UCFResolution(
        ucf_score=None,
        stability_band=None,
        contributing_factors=None,
        ucf_confidence=None,
        computation_source=None,
        confidence_penalty=0.0,
        escalation_bias=False,
        reason_codes=(),
        available=False,
        source_detail=detail,
    )


# =========================================================================
# Penalty / escalation logic
# =========================================================================

def _compute_penalty(band: StabilityBand) -> float:
    """Bounded penalty from stability band. Only unstable penalizes."""
    if band == StabilityBand.UNSTABLE:
        return _UNSTABLE_PENALTY
    return 0.0


def _should_escalate(band: StabilityBand) -> bool:
    """Escalation bias on unstable consciousness only."""
    return band == StabilityBand.UNSTABLE


# =========================================================================
# Main resolution function
# =========================================================================

def resolve_ucf_signal(
    *,
    ucf_state: Any = None,
    coherence_v3_quality: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    entropy_volatility: Optional[float] = None,
    schema_stability: Optional[float] = None,
    identity_harmonics_stability: Optional[float] = None,
) -> UCFResolution:
    """Resolve UCF as a governance-consumable consciousness stability signal.

    Resolution paths (in priority order):

    Path 1 — Pre-computed state:
        If ``ucf_state`` is a ``UnifiedConsciousnessState`` (or duck-typed
        equivalent with ``.ucf_score``, ``.stability_band``,
        ``.contributing_factors``, ``.confidence``), use it directly.

    Path 2 — Governance-computed:
        If individual signals are available (from the C2 coherence adapter
        or request metadata), call ``compute_ucf()`` directly.

    Path 3 — Fail-closed:
        If no data available, return ``available=False`` with zero penalty.

    Args:
        ucf_state: Pre-computed ``UnifiedConsciousnessState`` or compatible.
        coherence_v3_quality: Coherence v3 quality [0, 1].
        drift_fusion_index: Drift fusion index [0, 1] (higher = more drift).
        entropy_volatility: Entropy volatility [0, 1] (higher = more volatile).
        schema_stability: Schema stability [0, 1].
        identity_harmonics_stability: Identity harmonics stability [0, 1].

    Returns:
        UCFResolution with bounded penalty and explainable breakdown.
    """
    # Path 1: Pre-computed state
    if ucf_state is not None:
        try:
            return _from_precomputed(ucf_state)
        except Exception:
            pass  # fall through to Path 2

    # Path 2: Compute from available signals
    has_any = any(v is not None for v in (
        coherence_v3_quality, drift_fusion_index, entropy_volatility,
        schema_stability, identity_harmonics_stability,
    ))
    if has_any:
        try:
            return _compute_from_signals(
                coherence_v3_quality=coherence_v3_quality,
                drift_fusion_index=drift_fusion_index,
                entropy_volatility=entropy_volatility,
                schema_stability=schema_stability,
                identity_harmonics_stability=identity_harmonics_stability,
            )
        except Exception:
            pass  # fall through to Path 3

    # Path 3: No data
    return _empty_resolution()


def _from_precomputed(state: Any) -> UCFResolution:
    """Extract from a pre-computed UnifiedConsciousnessState."""
    score = float(getattr(state, "ucf_score"))
    band_raw = getattr(state, "stability_band")
    # Handle both StabilityBand enum and plain string
    band_str = band_raw.value if hasattr(band_raw, "value") else str(band_raw)
    band_enum = StabilityBand(band_str)

    factors = getattr(state, "contributing_factors", None)
    if factors is not None:
        factors = dict(factors)  # ensure mutable copy for safety
    confidence = float(getattr(state, "confidence", 0.5))

    penalty = _compute_penalty(band_enum)
    escalation = _should_escalate(band_enum)

    codes = []
    if penalty > 0:
        codes.append("UCF_INSTABILITY_PENALTY")
    if escalation:
        codes.append("UCF_ESCALATION")
    codes.append(f"UCF_BAND_{band_str.upper()}")

    return UCFResolution(
        ucf_score=score,
        stability_band=band_str,
        contributing_factors=factors,
        ucf_confidence=confidence,
        computation_source="precomputed",
        confidence_penalty=penalty,
        escalation_bias=escalation,
        reason_codes=tuple(codes),
        available=True,
        source_detail=f"precomputed UCF (score={score:.3f}, band={band_str})",
    )


def _compute_from_signals(
    *,
    coherence_v3_quality: Optional[float],
    drift_fusion_index: Optional[float],
    entropy_volatility: Optional[float],
    schema_stability: Optional[float],
    identity_harmonics_stability: Optional[float],
) -> UCFResolution:
    """Compute UCF directly from governance-available signals."""
    result = compute_ucf(
        coherence_v3_quality=coherence_v3_quality,
        drift_fusion_index=drift_fusion_index,
        entropy_volatility=entropy_volatility,
        schema_stability=schema_stability,
        identity_harmonics_stability=identity_harmonics_stability,
    )

    score = result.ucf_score
    band_str = result.stability_band.value
    band_enum = result.stability_band
    factors = dict(result.contributing_factors)
    confidence = result.confidence

    penalty = _compute_penalty(band_enum)
    escalation = _should_escalate(band_enum)

    codes = []
    if penalty > 0:
        codes.append("UCF_INSTABILITY_PENALTY")
    if escalation:
        codes.append("UCF_ESCALATION")
    codes.append(f"UCF_BAND_{band_str.upper()}")

    input_count = sum(1 for v in (
        coherence_v3_quality, drift_fusion_index, entropy_volatility,
        schema_stability, identity_harmonics_stability,
    ) if v is not None)

    return UCFResolution(
        ucf_score=score,
        stability_band=band_str,
        contributing_factors=factors,
        ucf_confidence=confidence,
        computation_source="governance_computed",
        confidence_penalty=penalty,
        escalation_bias=escalation,
        reason_codes=tuple(codes),
        available=True,
        source_detail=(
            f"governance-computed UCF (score={score:.3f}, "
            f"band={band_str}, inputs={input_count}/5)"
        ),
    )
