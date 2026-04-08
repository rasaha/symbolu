"""
Core CoherenceState Adapter — Pipeline → Governance Bridge
============================================================

Phase C2: Bridges the rich ``agentic.core.coherence.CoherenceState``
(241+ field pipeline state) into a bounded, governance-safe signal view.

This adapter is **complementary** to
``agentic.agentic_framework.coherence_tracker.CoherenceEngine``:

- ``coherence_tracker.py`` is the **governance-native** turn-level tracker.
  It computes governance metrics (internal_consistency, goal_alignment,
  volatility, etc.) from generation output at each turn. It runs entirely
  within the agentic framework, with no pipeline dependency.

- **This adapter** bridges the **pipeline-level** CoherenceState — which
  accumulates 241+ fields across coherence, drift, entropy, UCF,
  continuity, identity, and predictive phases — into a small, typed,
  governance-safe signal view. It extracts the governance-relevant subset
  and makes it available for audit, confidence adjustment, and
  enrichment without pulling the pipeline engine into governance.

Relationship:
    coherence_tracker  = governance computes its own coherence signals
    this adapter       = governance reads pipeline coherence signals
    Both feed into governance decisions; neither replaces the other.

Design:
    Follows the signal adapter pattern (see vritti_adapter, entropy_adapter):
    - Frozen Resolution dataclass (immutable, serializable)
    - ``resolve_core_coherence()`` pure function (duck-typed, fail-closed)
    - Bounded confidence penalty (max 0.10)
    - ``available`` / ``source_detail`` / ``reason_codes`` provenance

Dependency:
    This adapter does NOT import ``coherence_engine.py``.
    It only depends on the CoherenceState dataclass shape (duck-typed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


# =========================================================================
# Constants
# =========================================================================

# Max confidence penalty this adapter can impose.
# Adds to the sovereign aggregate cap (0.20) alongside entropy/insight/guna.
_MAX_PENALTY: float = 0.10

# Coherence below this triggers a penalty contribution.
_LOW_COHERENCE_THRESHOLD: float = 0.40

# Drift risk bands that trigger a penalty contribution.
_HIGH_DRIFT_BANDS: frozenset = frozenset({
    "high", "critical", "severe", "elevated",
})

# Persona drift above this triggers a penalty contribution.
_PERSONA_DRIFT_PENALTY_THRESHOLD: float = 0.60

# Escalation-triggering drift bands (stricter than penalty-only).
_ESCALATION_DRIFT_BANDS: frozenset = frozenset({
    "critical", "severe",
})


# =========================================================================
# Governance-facing contract
# =========================================================================

@dataclass(frozen=True)
class CoreCoherenceResolution:
    """Governance-safe view of the pipeline's CoherenceState.

    This is the **bounded signal contract** between the pipeline's rich
    coherence tracking (241+ fields) and the governance framework.

    Field categories
    ----------------

    BEHAVIOR-AFFECTING — may influence governance confidence or escalation:
        coherence_score         Overall pipeline coherence [0, 1].
        coherence_v3_quality    Latest coherence quality version [0, 1].
        semantic_stability      Semantic consistency [0, 1].
        persona_drift           Persona drift magnitude [0, 1]. Higher = more drift.
        drift_fusion_index      Unified semantic-temporal drift [0, 1].
        drift_risk_band         Categorical drift risk (low/moderate/high/critical).
        drift_likelihood_band   Predicted drift risk band.
        temporal_entropy_diff   Entropy change between turns.
        temporal_entropy_vol    Entropy volatility (stability of entropy).
        ucf_coi                 UCF Consciousness-of-Intent index [0, 1].
        ucf_csi                 UCF Consciousness Stability Index [0, 1].
        continuity_score        Adaptive continuity stability [0, 1].
        continuity_band         Continuity classification band.
        identity_memory_score   Identity memory stability [0, 1].
        drift_magnitude_pred    Predicted drift magnitude [0, 1].

    AUDIT-ONLY — for debugging, replay, and provenance (not decision-affecting):
        convo_id                Conversation identifier.
        turn_index              Turn number within conversation.
        resonance_index         Resonance quality metric.
        mapper_volatility       Mapper stability detail.

    ADAPTER METADATA — standard adapter provenance:
        confidence_penalty      Bounded [0, MAX_PENALTY] penalty applied.
        escalation_bias         Whether escalation should be bumped.
        reason_codes            Machine-readable governance codes.
        available               Whether signal was successfully resolved.
        source_detail           Human-readable provenance description.
    """

    # --- Behavior-affecting: coherence ---
    coherence_score: Optional[float]
    coherence_v3_quality: Optional[float]
    semantic_stability: Optional[float]

    # --- Behavior-affecting: drift ---
    persona_drift: Optional[float]
    drift_fusion_index: Optional[float]
    drift_risk_band: Optional[str]
    drift_likelihood_band: Optional[str]

    # --- Behavior-affecting: entropy dynamics ---
    temporal_entropy_diff: Optional[float]
    temporal_entropy_vol: Optional[float]

    # --- Behavior-affecting: UCF ---
    ucf_coi: Optional[float]
    ucf_csi: Optional[float]

    # --- Behavior-affecting: continuity ---
    continuity_score: Optional[float]
    continuity_band: Optional[str]

    # --- Behavior-affecting: identity & predictive ---
    identity_memory_score: Optional[float]
    drift_magnitude_pred: Optional[float]

    # --- Audit-only ---
    convo_id: Optional[str]
    turn_index: Optional[int]
    resonance_index: Optional[float]
    mapper_volatility: Optional[float]

    # --- Adapter metadata ---
    confidence_penalty: float
    escalation_bias: bool
    reason_codes: Tuple[str, ...]
    available: bool
    source_detail: str

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to audit-safe dictionary."""
        d: Dict[str, Any] = {}
        for field_name in (
            "coherence_score", "coherence_v3_quality", "semantic_stability",
            "persona_drift", "drift_fusion_index", "drift_risk_band",
            "drift_likelihood_band", "temporal_entropy_diff",
            "temporal_entropy_vol", "ucf_coi", "ucf_csi",
            "continuity_score", "continuity_band",
            "identity_memory_score", "drift_magnitude_pred",
            "convo_id", "turn_index", "resonance_index", "mapper_volatility",
            "confidence_penalty", "escalation_bias",
            "available", "source_detail",
        ):
            val = getattr(self, field_name)
            if isinstance(val, float):
                val = round(val, 6)
            d[field_name] = val
        d["reason_codes"] = list(self.reason_codes)
        return d


# =========================================================================
# Empty/fallback resolution
# =========================================================================

def _empty_resolution(detail: str = "no core coherence state available") -> CoreCoherenceResolution:
    """Return a safe empty resolution (fail-closed: zero penalty)."""
    return CoreCoherenceResolution(
        coherence_score=None,
        coherence_v3_quality=None,
        semantic_stability=None,
        persona_drift=None,
        drift_fusion_index=None,
        drift_risk_band=None,
        drift_likelihood_band=None,
        temporal_entropy_diff=None,
        temporal_entropy_vol=None,
        ucf_coi=None,
        ucf_csi=None,
        continuity_score=None,
        continuity_band=None,
        identity_memory_score=None,
        drift_magnitude_pred=None,
        convo_id=None,
        turn_index=None,
        resonance_index=None,
        mapper_volatility=None,
        confidence_penalty=0.0,
        escalation_bias=False,
        reason_codes=(),
        available=False,
        source_detail=detail,
    )


# =========================================================================
# Confidence penalty computation
# =========================================================================

def _compute_penalty(
    coherence: Optional[float],
    coherence_v3: Optional[float],
    persona_drift: Optional[float],
    drift_risk_band: Optional[str],
) -> float:
    """Compute bounded confidence penalty from coherence/drift signals.

    Penalty budget (max _MAX_PENALTY = 0.10):
    - Low coherence contributes up to 0.05
    - High drift contributes up to 0.05

    Both use linear interpolation within their respective bands.
    """
    penalty = 0.0

    # --- Coherence penalty (up to 0.05) ---
    # Use v3 quality if available, else base coherence_score.
    c = coherence_v3 if coherence_v3 is not None else coherence
    if c is not None and c < _LOW_COHERENCE_THRESHOLD:
        # Linear from threshold (0.0 penalty) to 0.0 (full 0.05 penalty)
        ratio = 1.0 - (c / _LOW_COHERENCE_THRESHOLD)
        penalty += ratio * 0.05

    # --- Drift penalty (up to 0.05) ---
    # Categorical: high drift band adds flat 0.03
    drift_band_penalty = 0.0
    if drift_risk_band is not None and drift_risk_band.lower() in _HIGH_DRIFT_BANDS:
        drift_band_penalty = 0.03

    # Continuous: high persona drift adds up to 0.02
    persona_penalty = 0.0
    if persona_drift is not None and persona_drift > _PERSONA_DRIFT_PENALTY_THRESHOLD:
        ratio = min(
            1.0,
            (persona_drift - _PERSONA_DRIFT_PENALTY_THRESHOLD)
            / (1.0 - _PERSONA_DRIFT_PENALTY_THRESHOLD),
        )
        persona_penalty = ratio * 0.02

    penalty += min(0.05, drift_band_penalty + persona_penalty)

    return min(_MAX_PENALTY, penalty)


def _should_escalate(
    drift_risk_band: Optional[str],
    drift_likelihood_band: Optional[str],
) -> bool:
    """Determine if escalation should be bumped (stricter-only).

    Triggers only on critical/severe drift bands.
    """
    for band in (drift_risk_band, drift_likelihood_band):
        if band is not None and band.lower() in _ESCALATION_DRIFT_BANDS:
            return True
    return False


# =========================================================================
# Main resolution function
# =========================================================================

def resolve_core_coherence(
    *,
    core_coherence_state: Any = None,
) -> CoreCoherenceResolution:
    """Resolve pipeline CoherenceState into a governance-safe signal view.

    Args:
        core_coherence_state: A ``agentic.core.coherence.CoherenceState``
            instance (duck-typed — any object with the expected attributes).
            Typically passed via ``request.metadata["core_coherence_state"]``.

    Returns:
        CoreCoherenceResolution with extracted signals and bounded penalty.

    Fail-closed semantics:
        If ``core_coherence_state`` is None, malformed, or missing expected
        attributes, returns ``available=False`` with zero penalty and no
        escalation bias. Absence of pipeline signals never weakens governance.
    """
    if core_coherence_state is None:
        return _empty_resolution()

    try:
        return _extract_from_state(core_coherence_state)
    except Exception:
        return _empty_resolution("core coherence state extraction failed")


def _extract_from_state(state: Any) -> CoreCoherenceResolution:
    """Extract governance-relevant subset from a CoherenceState object.

    Uses getattr with None defaults for every field — partial states are
    handled gracefully.
    """

    # --- Safe extraction helper ---
    def _f(name: str) -> Optional[float]:
        """Extract optional float, clamped to [0, 1] if present."""
        val = getattr(state, name, None)
        if val is None:
            return None
        val = float(val)
        return max(0.0, min(1.0, val))

    def _f_unbounded(name: str) -> Optional[float]:
        """Extract optional float without clamping (for diffs/volatility)."""
        val = getattr(state, name, None)
        if val is None:
            return None
        return float(val)

    def _s(name: str) -> Optional[str]:
        """Extract optional string."""
        val = getattr(state, name, None)
        return str(val) if val is not None else None

    def _i(name: str) -> Optional[int]:
        """Extract optional int."""
        val = getattr(state, name, None)
        return int(val) if val is not None else None

    # --- Extract fields ---
    coherence_score = _f("coherence_score")
    coherence_v3_quality = _f("coherence_v3_quality")
    semantic_stability = _f("semantic_stability_score")

    persona_drift = _f("persona_drift_score")
    drift_fusion_index = _f("drift_fusion_index")
    drift_risk_band = _s("drift_risk_band")
    drift_likelihood_band = _s("current_drift_likelihood_band")

    temporal_entropy_diff = _f_unbounded("temporal_entropy_diff")
    temporal_entropy_vol = _f_unbounded("temporal_entropy_volatility")

    ucf_coi = _f("current_coi")
    ucf_csi = _f("current_csi")

    continuity_score = _f("current_css")
    continuity_band = _s("current_continuity_band")

    identity_memory_score = _f("current_ims")
    drift_magnitude_pred = _f("current_drift_magnitude_prediction")

    convo_id = _s("convo_id")
    turn_index = _i("turn_index")
    resonance_index = _f_unbounded("resonance_index")
    mapper_volatility = _f("mapper_volatility_score")

    # --- Compute penalty and escalation ---
    penalty = _compute_penalty(
        coherence_score, coherence_v3_quality,
        persona_drift, drift_risk_band,
    )
    escalation = _should_escalate(drift_risk_band, drift_likelihood_band)

    # --- Build reason codes ---
    codes = []
    if penalty > 0:
        codes.append("CORE_COHERENCE_PENALTY")
    if escalation:
        codes.append("CORE_COHERENCE_ESCALATION")
    if drift_risk_band is not None:
        codes.append(f"DRIFT_BAND_{drift_risk_band.upper()}")

    detail_parts = []
    if coherence_score is not None:
        detail_parts.append(f"coherence={coherence_score:.3f}")
    if persona_drift is not None:
        detail_parts.append(f"drift={persona_drift:.3f}")
    if drift_risk_band is not None:
        detail_parts.append(f"risk_band={drift_risk_band}")
    if turn_index is not None:
        detail_parts.append(f"turn={turn_index}")
    source_detail = (
        f"core CoherenceState ({', '.join(detail_parts)})"
        if detail_parts
        else "core CoherenceState (partial)"
    )

    return CoreCoherenceResolution(
        coherence_score=coherence_score,
        coherence_v3_quality=coherence_v3_quality,
        semantic_stability=semantic_stability,
        persona_drift=persona_drift,
        drift_fusion_index=drift_fusion_index,
        drift_risk_band=drift_risk_band,
        drift_likelihood_band=drift_likelihood_band,
        temporal_entropy_diff=temporal_entropy_diff,
        temporal_entropy_vol=temporal_entropy_vol,
        ucf_coi=ucf_coi,
        ucf_csi=ucf_csi,
        continuity_score=continuity_score,
        continuity_band=continuity_band,
        identity_memory_score=identity_memory_score,
        drift_magnitude_pred=drift_magnitude_pred,
        convo_id=convo_id,
        turn_index=turn_index,
        resonance_index=resonance_index,
        mapper_volatility=mapper_volatility,
        confidence_penalty=penalty,
        escalation_bias=escalation,
        reason_codes=tuple(codes),
        available=True,
        source_detail=source_detail,
    )
