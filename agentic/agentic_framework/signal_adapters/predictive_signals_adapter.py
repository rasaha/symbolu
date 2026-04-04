"""
Predictive Signals Adapter — P35 Drift + P36 Identity + P37 Continuity → Governance
====================================================================================

Phase C4: Integrates the predictive persona drift (P35), identity resonance
memory (P36), and adaptive continuity (P37) modules into the governance
framework as bounded, auditable signals.

Signal classification:
    P35 (predictive drift)  — BEHAVIOR-AFFECTING: max 0.03 penalty + escalation on HIGH risk
    P37 (continuity)        — LIGHT BEHAVIOR: max 0.02 penalty on fragmenting mode
    P36 (identity resonance)— AUDIT-ONLY: no penalty, no escalation

Combined adapter rationale:
    P35/P36/P37 form a dependency chain (P37 depends on P35+P36 outputs).
    Grouping them in one adapter avoids redundant resolution and keeps
    governance wiring simple. The adapter resolves P35 first, then P36,
    then P37 (which consumes both).

Design:
    Follows the signal adapter pattern (frozen Resolution, pure function,
    fail-closed, bounded penalty, stricter-only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# =========================================================================
# Constants
# =========================================================================

# P35 predictive drift — behavior-affecting
_P35_MAX_PENALTY: float = 0.03
_P35_HIGH_RISK_PENALTY: float = 0.03
_P35_MODERATE_RISK_PENALTY: float = 0.01

# P37 continuity — light behavior
_P37_MAX_PENALTY: float = 0.02
_P37_FRAGMENTING_PENALTY: float = 0.02
_P37_STRAINED_PENALTY: float = 0.005

# P36 identity resonance — audit-only (no penalty)


# =========================================================================
# Governance-facing contract
# =========================================================================

@dataclass(frozen=True)
class PredictiveSignalsResolution:
    """Governance-safe view of P35 + P36 + P37 predictive signals.

    Field categories
    ----------------

    BEHAVIOR-AFFECTING (P35 drift — may influence confidence/escalation):
        predicted_drift_score       Predicted persona drift [0, 1]. Higher = more drift.
        drift_risk_band             "low", "moderate", "high".
        drift_trend                 "stable", "worsening", "improving".
        drift_contributing_factors  Factors driving drift prediction.

    LIGHT BEHAVIOR (P37 continuity — small penalty on fragmenting):
        continuity_score            Adaptive continuity score [0, 1].
        continuity_mode             "stable", "strained", "fragmenting".
        continuity_pressure         Inverse of continuity_score [0, 1].
        oscillation_detected        Whether identity oscillation detected.

    AUDIT-ONLY (P36 identity — no governance penalty):
        identity_resonance_index    Identity resonance [0, 1].
        identity_stability_band     "stable", "soft", "fragile".
        persistence_score           Identity persistence [0, 1].
        volatility_index            Identity volatility [0, 1].

    ADAPTER METADATA:
        confidence_penalty          Bounded aggregate penalty [0, 0.05].
        escalation_bias             Whether escalation should be bumped.
        reason_codes                Machine-readable governance reason codes.
        available                   Whether signal was successfully resolved.
        source_detail               Human-readable provenance description.
        p35_available               Whether P35 drift resolved.
        p36_available               Whether P36 identity resolved.
        p37_available               Whether P37 continuity resolved.
    """

    # --- P35 Behavior-affecting ---
    predicted_drift_score: Optional[float]
    drift_risk_band: Optional[str]
    drift_trend: Optional[str]
    drift_contributing_factors: Optional[Tuple[str, ...]]

    # --- P37 Light behavior ---
    continuity_score: Optional[float]
    continuity_mode: Optional[str]
    continuity_pressure: Optional[float]
    oscillation_detected: Optional[bool]

    # --- P36 Audit-only ---
    identity_resonance_index: Optional[float]
    identity_stability_band: Optional[str]
    persistence_score: Optional[float]
    volatility_index: Optional[float]

    # --- Adapter metadata ---
    confidence_penalty: float
    escalation_bias: bool
    reason_codes: Tuple[str, ...]
    available: bool
    source_detail: str
    p35_available: bool
    p36_available: bool
    p37_available: bool

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to audit-safe dictionary."""
        def _r(v: Optional[float]) -> Optional[float]:
            return round(v, 6) if v is not None else None

        return {
            # P35
            "predicted_drift_score": _r(self.predicted_drift_score),
            "drift_risk_band": self.drift_risk_band,
            "drift_trend": self.drift_trend,
            "drift_contributing_factors": (
                list(self.drift_contributing_factors)
                if self.drift_contributing_factors else None
            ),
            # P37
            "continuity_score": _r(self.continuity_score),
            "continuity_mode": self.continuity_mode,
            "continuity_pressure": _r(self.continuity_pressure),
            "oscillation_detected": self.oscillation_detected,
            # P36
            "identity_resonance_index": _r(self.identity_resonance_index),
            "identity_stability_band": self.identity_stability_band,
            "persistence_score": _r(self.persistence_score),
            "volatility_index": _r(self.volatility_index),
            # Metadata
            "confidence_penalty": round(self.confidence_penalty, 6),
            "escalation_bias": self.escalation_bias,
            "reason_codes": list(self.reason_codes),
            "available": self.available,
            "source_detail": self.source_detail,
            "p35_available": self.p35_available,
            "p36_available": self.p36_available,
            "p37_available": self.p37_available,
        }


# =========================================================================
# Empty/fallback resolution
# =========================================================================

def _empty_resolution(detail: str = "no predictive signal data available") -> PredictiveSignalsResolution:
    """Fail-closed: zero penalty, no escalation. Absence never weakens."""
    return PredictiveSignalsResolution(
        predicted_drift_score=None,
        drift_risk_band=None,
        drift_trend=None,
        drift_contributing_factors=None,
        continuity_score=None,
        continuity_mode=None,
        continuity_pressure=None,
        oscillation_detected=None,
        identity_resonance_index=None,
        identity_stability_band=None,
        persistence_score=None,
        volatility_index=None,
        confidence_penalty=0.0,
        escalation_bias=False,
        reason_codes=(),
        available=False,
        source_detail=detail,
        p35_available=False,
        p36_available=False,
        p37_available=False,
    )


# =========================================================================
# Penalty / escalation logic
# =========================================================================

def _p35_penalty(drift_risk_band: str) -> float:
    """Bounded penalty from P35 drift risk band."""
    if drift_risk_band == "high":
        return _P35_HIGH_RISK_PENALTY
    elif drift_risk_band == "moderate":
        return _P35_MODERATE_RISK_PENALTY
    return 0.0


def _p35_should_escalate(drift_risk_band: str) -> bool:
    """Escalation bias on HIGH drift risk only."""
    return drift_risk_band == "high"


def _p37_penalty(continuity_mode: str) -> float:
    """Bounded penalty from P37 continuity mode."""
    if continuity_mode == "fragmenting":
        return _P37_FRAGMENTING_PENALTY
    elif continuity_mode == "strained":
        return _P37_STRAINED_PENALTY
    return 0.0


# =========================================================================
# Main resolution function
# =========================================================================

def resolve_predictive_signals(
    *,
    drift_report: Any = None,
    identity_state: Any = None,
    continuity_report: Any = None,
) -> PredictiveSignalsResolution:
    """Resolve P35 + P36 + P37 as governance-consumable predictive signals.

    Resolution strategy:
        Accepts pre-computed report/state objects from the pipeline.
        Each signal resolves independently — partial availability is fine.
        Any signal that fails to resolve contributes zero penalty.

    Args:
        drift_report: Pre-computed PredictivePersonaDriftReport (P35) or
            duck-typed equivalent with predicted_drift_score, drift_risk_band,
            trend_direction, contributing_factors, confidence.
        identity_state: Pre-computed IdentityResonanceMemoryState (P36) or
            duck-typed equivalent with identity_resonance_index,
            identity_stability_band, persistence_score, volatility_index.
        continuity_report: Pre-computed AdaptiveContinuityReport (P37) or
            duck-typed equivalent with continuity_score, continuity_mode,
            continuity_pressure, oscillation_detected.

    Returns:
        PredictiveSignalsResolution with bounded penalties and audit data.
    """
    # Resolve each signal independently
    p35 = _resolve_p35(drift_report)
    p36 = _resolve_p36(identity_state)
    p37 = _resolve_p37(continuity_report)

    any_available = p35["available"] or p36["available"] or p37["available"]
    if not any_available:
        return _empty_resolution()

    # Aggregate penalties (P35 behavior + P37 light behavior; P36 = 0)
    total_penalty = p35["penalty"] + p37["penalty"]
    escalation = p35["escalation"]

    # Build reason codes
    codes: List[str] = []
    codes.extend(p35["codes"])
    codes.extend(p37["codes"])
    codes.extend(p36["codes"])

    # Build source detail
    parts: List[str] = []
    if p35["available"]:
        parts.append(
            f"P35(drift={p35['score']:.3f}, band={p35['band']})"
        )
    if p36["available"]:
        parts.append(
            f"P36(resonance={p36['resonance']:.3f}, band={p36['band']})"
        )
    if p37["available"]:
        parts.append(
            f"P37(continuity={p37['score']:.3f}, mode={p37['mode']})"
        )

    return PredictiveSignalsResolution(
        # P35
        predicted_drift_score=p35["score"] if p35["available"] else None,
        drift_risk_band=p35["band"] if p35["available"] else None,
        drift_trend=p35["trend"] if p35["available"] else None,
        drift_contributing_factors=p35["factors"] if p35["available"] else None,
        # P37
        continuity_score=p37["score"] if p37["available"] else None,
        continuity_mode=p37["mode"] if p37["available"] else None,
        continuity_pressure=p37["pressure"] if p37["available"] else None,
        oscillation_detected=p37["oscillation"] if p37["available"] else None,
        # P36
        identity_resonance_index=p36["resonance"] if p36["available"] else None,
        identity_stability_band=p36["band"] if p36["available"] else None,
        persistence_score=p36["persistence"] if p36["available"] else None,
        volatility_index=p36["volatility"] if p36["available"] else None,
        # Metadata
        confidence_penalty=total_penalty,
        escalation_bias=escalation,
        reason_codes=tuple(codes),
        available=True,
        source_detail="; ".join(parts),
        p35_available=p35["available"],
        p36_available=p36["available"],
        p37_available=p37["available"],
    )


# =========================================================================
# Per-signal resolvers (duck-typed, fail-safe)
# =========================================================================

def _resolve_p35(report: Any) -> Dict[str, Any]:
    """Resolve P35 predictive drift from duck-typed report."""
    if report is None:
        return {"available": False, "penalty": 0.0, "escalation": False, "codes": [],
                "score": 0.0, "band": "low", "trend": "stable", "factors": ()}
    try:
        score = float(getattr(report, "predicted_drift_score"))
        band_raw = getattr(report, "drift_risk_band")
        band = band_raw.value if hasattr(band_raw, "value") else str(band_raw)
        trend_raw = getattr(report, "trend_direction")
        trend = trend_raw.value if hasattr(trend_raw, "value") else str(trend_raw)
        factors_raw = getattr(report, "contributing_factors", ())
        factors = tuple(factors_raw) if factors_raw else ()

        penalty = _p35_penalty(band)
        escalation = _p35_should_escalate(band)

        codes: List[str] = []
        if penalty > 0:
            codes.append("P35_DRIFT_PENALTY")
        if escalation:
            codes.append("P35_DRIFT_ESCALATION")
        codes.append(f"P35_RISK_{band.upper()}")

        return {
            "available": True, "penalty": penalty, "escalation": escalation,
            "codes": codes, "score": score, "band": band, "trend": trend,
            "factors": factors,
        }
    except Exception:
        return {"available": False, "penalty": 0.0, "escalation": False, "codes": [],
                "score": 0.0, "band": "low", "trend": "stable", "factors": ()}


def _resolve_p36(state: Any) -> Dict[str, Any]:
    """Resolve P36 identity resonance from duck-typed state. Audit-only."""
    if state is None:
        return {"available": False, "codes": [], "resonance": 0.0,
                "band": "soft", "persistence": 0.0, "volatility": 0.0}
    try:
        resonance = float(getattr(state, "identity_resonance_index"))
        band_raw = getattr(state, "identity_stability_band")
        band = band_raw.value if hasattr(band_raw, "value") else str(band_raw)
        persistence = float(getattr(state, "persistence_score"))
        volatility = float(getattr(state, "volatility_index"))

        codes: List[str] = [f"P36_IDENTITY_{band.upper()}"]
        if band == "fragile":
            codes.append("P36_IDENTITY_FRAGILE_WARN")

        return {
            "available": True, "codes": codes, "resonance": resonance,
            "band": band, "persistence": persistence, "volatility": volatility,
        }
    except Exception:
        return {"available": False, "codes": [], "resonance": 0.0,
                "band": "soft", "persistence": 0.0, "volatility": 0.0}


def _resolve_p37(report: Any) -> Dict[str, Any]:
    """Resolve P37 continuity from duck-typed report. Light behavior."""
    if report is None:
        return {"available": False, "penalty": 0.0, "codes": [],
                "score": 0.0, "mode": "stable", "pressure": 0.0,
                "oscillation": False}
    try:
        score = float(getattr(report, "continuity_score"))
        mode_raw = getattr(report, "continuity_mode")
        mode = mode_raw.value if hasattr(mode_raw, "value") else str(mode_raw)
        pressure = float(getattr(report, "continuity_pressure"))
        oscillation = bool(getattr(report, "oscillation_detected"))

        penalty = _p37_penalty(mode)

        codes: List[str] = []
        if penalty > 0:
            codes.append("P37_CONTINUITY_PENALTY")
        codes.append(f"P37_MODE_{mode.upper()}")
        if oscillation:
            codes.append("P37_OSCILLATION_DETECTED")

        return {
            "available": True, "penalty": penalty, "codes": codes,
            "score": score, "mode": mode, "pressure": pressure,
            "oscillation": oscillation,
        }
    except Exception:
        return {"available": False, "penalty": 0.0, "codes": [],
                "score": 0.0, "mode": "stable", "pressure": 0.0,
                "oscillation": False}
