"""
Session Enrichment Adapter — Identity, Motivation, and Temporal signal resolution.

Resolves session-level enrichment signals for governance consumption:
1. Identity classification and stability
2. Motivation classification and instability flags
3. Temporal state and tension indicators

These signals enter governance as:
- Bounded confidence adjustments (additive, max penalty -0.15 total)
- Reason codes for audit/escalation
- Approval context enrichment
- Policy context metadata

CANONICAL AUTHORITIES:
    Identity: agentic/identity/ (IdentitySignature)
    Motivation: agentic/motivation/ (MotivationProfile)
    Temporal: agentic/temporal/ (TemporalBhavaTracker)

Phase 3: Session enrichment → governance integration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =========================================================================
# Constants: bounded penalties
# =========================================================================

# Maximum confidence penalty from each signal category.
# These are additive, so total max is -0.15.
_MAX_IDENTITY_PENALTY = 0.05
_MAX_MOTIVATION_PENALTY = 0.05
_MAX_TEMPORAL_PENALTY = 0.05

# Identity types considered unstable for governance purposes.
_IDENTITY_INSTABILITY_TYPES = frozenset({
    "self_fragmentation",
    "self_dissonance",
})

# Motivation types considered risk-relevant for governance purposes.
_MOTIVATION_RISK_TYPES = frozenset({
    "fear_driven",
    "overcorrection",
    "avoidance_driven",
})

# Temporal states considered high-tension for governance purposes.
_TEMPORAL_TENSION_STATES = frozenset({
    "TENSE",
    "VOLATILE",
})


# =========================================================================
# Resolution result
# =========================================================================

@dataclass(frozen=True)
class SessionEnrichmentResolution:
    """Resolved session enrichment signals for governance.

    Attributes:
        identity_type: Identity signature classification, or None.
        identity_confidence: Confidence in identity classification [0, 1].
        identity_stability_band: Stability band (stable/soft/fragile), or None.
        identity_unstable: Whether identity pattern is governance-relevant unstable.
        motivation_type: Motivation classification, or None.
        motivation_confidence: Confidence in motivation classification [0, 1].
        motivation_risk_relevant: Whether motivation is governance-relevant risky.
        temporal_state: Temporal state classification (STABLE/TENSE/etc.), or None.
        temporal_tension_index: Tension index [0, 1], or None.
        temporal_trend: Trend direction (rising/falling/stable), or None.
        temporal_tense: Whether temporal state is governance-relevant tense.
        confidence_adjustment: Total bounded confidence penalty (negative or zero).
        reason_codes: Reason codes explaining the adjustment.
        source_detail: Human-readable provenance.
    """
    # Identity
    identity_type: Optional[str]
    identity_confidence: Optional[float]
    identity_stability_band: Optional[str]
    identity_unstable: bool

    # Motivation
    motivation_type: Optional[str]
    motivation_confidence: Optional[float]
    motivation_risk_relevant: bool

    # Temporal
    temporal_state: Optional[str]
    temporal_tension_index: Optional[float]
    temporal_trend: Optional[str]
    temporal_tense: bool

    # Governance effect
    confidence_adjustment: float  # always <= 0
    reason_codes: tuple  # immutable tuple of reason strings

    # Provenance
    source_detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity_type": self.identity_type,
            "identity_confidence": self.identity_confidence,
            "identity_stability_band": self.identity_stability_band,
            "identity_unstable": self.identity_unstable,
            "motivation_type": self.motivation_type,
            "motivation_confidence": self.motivation_confidence,
            "motivation_risk_relevant": self.motivation_risk_relevant,
            "temporal_state": self.temporal_state,
            "temporal_tension_index": self.temporal_tension_index,
            "temporal_trend": self.temporal_trend,
            "temporal_tense": self.temporal_tense,
            "confidence_adjustment": self.confidence_adjustment,
            "reason_codes": list(self.reason_codes),
            "source_detail": self.source_detail,
        }


# =========================================================================
# Resolution logic
# =========================================================================

def resolve_session_enrichment(
    *,
    identity_signature: Any = None,
    identity_resonance_state: Any = None,
    motivation_profile: Any = None,
    temporal_summary: Optional[Dict[str, Any]] = None,
    coherence_state: Any = None,
) -> SessionEnrichmentResolution:
    """Resolve session enrichment signals for governance consumption.

    Args:
        identity_signature: IdentitySignature from ctx.identity_signature.
            Duck-typed on .signature_type, .confidence.
        identity_resonance_state: IdentityResonanceMemoryState from
            ctx.identity_resonance_memory_snapshot. Duck-typed on
            .identity_stability_band, .volatility_index.
        motivation_profile: MotivationProfile from ctx.motivation_profile.
            Duck-typed on .motivation_type, .confidence.
        temporal_summary: Dict from tracker.get_pattern_summary().
            Expected keys: state, trajectory, tension.
        coherence_state: CoherenceState from ctx.coherence_state.
            Duck-typed on .tension_index.

    Returns:
        SessionEnrichmentResolution with all resolved signals and bounded
        confidence adjustment.

    Fail-closed semantics:
        - Missing signals contribute zero penalty
        - Only recognized instability patterns increase scrutiny
        - Maximum total penalty is -0.15
    """
    reason_codes: List[str] = []
    parts: List[str] = []
    total_penalty = 0.0

    # ---- Identity ----
    id_fields = _resolve_identity(identity_signature, identity_resonance_state)
    if id_fields["identity_type"]:
        parts.append("identity")
    if id_fields["identity_unstable"]:
        penalty = _compute_identity_penalty(id_fields)
        total_penalty += penalty
        reason_codes.append(f"SESSION_IDENTITY:{id_fields['identity_type']}")
        if id_fields["identity_stability_band"] == "fragile":
            reason_codes.append("SESSION_IDENTITY:stability_band_fragile")

    # ---- Motivation ----
    mot_fields = _resolve_motivation(motivation_profile)
    if mot_fields["motivation_type"]:
        parts.append("motivation")
    if mot_fields["motivation_risk_relevant"]:
        penalty = _compute_motivation_penalty(mot_fields)
        total_penalty += penalty
        reason_codes.append(f"SESSION_MOTIVATION:{mot_fields['motivation_type']}")

    # ---- Temporal ----
    tmp_fields = _resolve_temporal(temporal_summary, coherence_state)
    if tmp_fields["temporal_state"]:
        parts.append("temporal")
    if tmp_fields["temporal_tense"]:
        penalty = _compute_temporal_penalty(tmp_fields)
        total_penalty += penalty
        reason_codes.append(f"SESSION_TEMPORAL:{tmp_fields['temporal_state']}")

    # Ensure total penalty is bounded (round to avoid IEEE 754 float accumulation)
    total_penalty = round(total_penalty, 10)
    total_penalty = max(-(_MAX_IDENTITY_PENALTY + _MAX_MOTIVATION_PENALTY + _MAX_TEMPORAL_PENALTY), total_penalty)

    source = ", ".join(parts) if parts else "no session data"
    source_detail = f"session enrichment resolved from: {source}"

    return SessionEnrichmentResolution(
        identity_type=id_fields["identity_type"],
        identity_confidence=id_fields["identity_confidence"],
        identity_stability_band=id_fields["identity_stability_band"],
        identity_unstable=id_fields["identity_unstable"],
        motivation_type=mot_fields["motivation_type"],
        motivation_confidence=mot_fields["motivation_confidence"],
        motivation_risk_relevant=mot_fields["motivation_risk_relevant"],
        temporal_state=tmp_fields["temporal_state"],
        temporal_tension_index=tmp_fields["temporal_tension_index"],
        temporal_trend=tmp_fields["temporal_trend"],
        temporal_tense=tmp_fields["temporal_tense"],
        confidence_adjustment=total_penalty,
        reason_codes=tuple(reason_codes),
        source_detail=source_detail,
    )


# =========================================================================
# Identity resolution
# =========================================================================

def _resolve_identity(signature: Any, resonance_state: Any) -> Dict:
    """Extract identity signals from IdentitySignature and resonance state."""
    result = {
        "identity_type": None,
        "identity_confidence": None,
        "identity_stability_band": None,
        "identity_unstable": False,
    }

    # Extract from IdentitySignature
    if signature is not None:
        try:
            sig_type = str(signature.signature_type)
            confidence = float(signature.confidence)
            result["identity_type"] = sig_type
            result["identity_confidence"] = confidence
            result["identity_unstable"] = (
                sig_type in _IDENTITY_INSTABILITY_TYPES and confidence >= 0.5
            )
        except (AttributeError, TypeError, ValueError):
            logger.debug("Malformed identity_signature, skipping")

    # Extract stability band from resonance state
    if resonance_state is not None:
        try:
            band = str(resonance_state.identity_stability_band)
            result["identity_stability_band"] = band
            # Fragile band reinforces instability even if signature type is benign
            if band == "fragile" and not result["identity_unstable"]:
                result["identity_unstable"] = True
        except (AttributeError, TypeError, ValueError):
            logger.debug("Malformed identity_resonance_state, skipping")

    return result


def _compute_identity_penalty(fields: Dict) -> float:
    """Compute bounded confidence penalty from identity instability.

    Penalty scales with identity confidence (higher confidence in
    instability = more penalty) but is capped at _MAX_IDENTITY_PENALTY.
    """
    conf = fields.get("identity_confidence") or 0.5
    # Scale: penalty = max_penalty * confidence_in_instability
    penalty = -_MAX_IDENTITY_PENALTY * min(1.0, conf)
    return max(-_MAX_IDENTITY_PENALTY, penalty)


# =========================================================================
# Motivation resolution
# =========================================================================

def _resolve_motivation(profile: Any) -> Dict:
    """Extract motivation signals from MotivationProfile."""
    result = {
        "motivation_type": None,
        "motivation_confidence": None,
        "motivation_risk_relevant": False,
    }

    if profile is not None:
        try:
            mot_type = str(profile.motivation_type)
            confidence = float(profile.confidence)
            result["motivation_type"] = mot_type
            result["motivation_confidence"] = confidence
            result["motivation_risk_relevant"] = (
                mot_type in _MOTIVATION_RISK_TYPES and confidence >= 0.5
            )
        except (AttributeError, TypeError, ValueError):
            logger.debug("Malformed motivation_profile, skipping")

    return result


def _compute_motivation_penalty(fields: Dict) -> float:
    """Compute bounded confidence penalty from risky motivation patterns."""
    conf = fields.get("motivation_confidence") or 0.5
    penalty = -_MAX_MOTIVATION_PENALTY * min(1.0, conf)
    return max(-_MAX_MOTIVATION_PENALTY, penalty)


# =========================================================================
# Temporal resolution
# =========================================================================

def _resolve_temporal(
    summary: Optional[Dict[str, Any]],
    coherence_state: Any,
) -> Dict:
    """Extract temporal signals from tracker summary and coherence state."""
    result = {
        "temporal_state": None,
        "temporal_tension_index": None,
        "temporal_trend": None,
        "temporal_tense": False,
    }

    # Extract from temporal summary (from tracker.get_pattern_summary())
    if summary is not None:
        try:
            state = summary.get("state")
            if state:
                result["temporal_state"] = str(state)
                result["temporal_tense"] = str(state) in _TEMPORAL_TENSION_STATES

            trajectory = summary.get("trajectory")
            if trajectory and isinstance(trajectory, dict):
                result["temporal_trend"] = trajectory.get("trend")
        except (AttributeError, TypeError):
            logger.debug("Malformed temporal_summary, skipping")

    # Extract tension_index from coherence state
    if coherence_state is not None:
        try:
            ti = getattr(coherence_state, "tension_index", None)
            if ti is not None:
                result["temporal_tension_index"] = float(ti)
                # If tension_index > 0.6 and we don't already have a tense state,
                # mark as tense (this catches cases where tracker summary is absent)
                if float(ti) > 0.6 and not result["temporal_tense"]:
                    result["temporal_tense"] = True
                    if not result["temporal_state"]:
                        result["temporal_state"] = "HIGH_TENSION_INDEX"
        except (TypeError, ValueError):
            logger.debug("Malformed coherence_state.tension_index, skipping")

    return result


def _compute_temporal_penalty(fields: Dict) -> float:
    """Compute bounded confidence penalty from temporal tension.

    Penalty scales with tension_index if available, otherwise uses
    a flat conservative penalty for recognized tense states.
    """
    ti = fields.get("temporal_tension_index")
    if ti is not None and ti > 0.0:
        # Scale: penalty proportional to tension, capped
        penalty = -_MAX_TEMPORAL_PENALTY * min(1.0, ti)
    else:
        # Flat penalty for recognized tense state without numeric index
        penalty = -_MAX_TEMPORAL_PENALTY * 0.5
    return max(-_MAX_TEMPORAL_PENALTY, penalty)
