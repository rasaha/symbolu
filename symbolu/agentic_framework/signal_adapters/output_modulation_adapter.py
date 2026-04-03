"""
Output Modulation Adapter — Delivery-time modulation signal resolution.

Resolves output modulation signals for the rendering/output path:
1. DHA formula delivery profile (tone weights, intensity, restraint, D factor)
2. Guna modulation canonical intensity (E = G × P × T)
3. Entropy gate information

Phase 2 approach:
- Enable DHA formula computation in diagnostic mode (observation-only)
- Compute guna modulation E factor for output intensity
- Surface entropy gate in output metadata
- Do NOT modify semantic content; modulation is delivery-only
- Full audit trail for all computations

CANONICAL AUTHORITIES:
    DHA formulas: agentic/dha/
    Guna modulation: agentic/guna_modulation/
    Entropy: agentic/entropy/

Phase 2: Output modulation path wiring.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# =========================================================================
# Resolution result
# =========================================================================

@dataclass(frozen=True)
class OutputModulationResolution:
    """Resolved output modulation signals for rendering/output.

    Attributes:
        dha_available: Whether DHA formula was successfully computed.
        dha_tone_weights: Tone weights {sweet, jolt, metaphor}, or None.
        dha_intensity: Intensity scalar I [0, 1], or None.
        dha_restraint: Restraint scalar R [0, 1], or None.
        dha_delivery_factor: Delivery modulation factor D, or None.
        dha_dominant_tone: Dominant tone name, or None.
        dha_suppressed: Whether D < 0.1 (effective suppression), or None.
        guna_modulation_available: Whether guna modulation was computed.
        guna_E: Entropy modulation factor E = G × P × T, or None.
        guna_G: Guna coefficient, or None.
        guna_P: Policy scalar, or None.
        guna_T_scalar: Tier scalar, or None.
        guna_output_intensity: BASE × E, or None.
        guna_vector: {sattva, rajas, tamas}, or None.
        entropy_gate: Gate classification string, or None.
        entropy_combined: Combined entropy [0, 1], or None.
        source_detail: Human-readable description of what was computed.
    """
    # DHA delivery profile
    dha_available: bool
    dha_tone_weights: Optional[Dict[str, float]]
    dha_intensity: Optional[float]
    dha_restraint: Optional[float]
    dha_delivery_factor: Optional[float]
    dha_dominant_tone: Optional[str]
    dha_suppressed: Optional[bool]

    # Guna modulation intensity
    guna_modulation_available: bool
    guna_E: Optional[float]
    guna_G: Optional[float]
    guna_P: Optional[float]
    guna_T_scalar: Optional[float]
    guna_output_intensity: Optional[float]
    guna_vector: Optional[Dict[str, float]]

    # Entropy gate
    entropy_gate: Optional[str]
    entropy_combined: Optional[float]

    # Provenance
    source_detail: str

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "dha_available": self.dha_available,
            "dha_tone_weights": self.dha_tone_weights,
            "dha_intensity": self.dha_intensity,
            "dha_restraint": self.dha_restraint,
            "dha_delivery_factor": self.dha_delivery_factor,
            "dha_dominant_tone": self.dha_dominant_tone,
            "dha_suppressed": self.dha_suppressed,
            "guna_modulation_available": self.guna_modulation_available,
            "guna_E": self.guna_E,
            "guna_G": self.guna_G,
            "guna_P": self.guna_P,
            "guna_T_scalar": self.guna_T_scalar,
            "guna_output_intensity": self.guna_output_intensity,
            "guna_vector": self.guna_vector,
            "entropy_gate": self.entropy_gate,
            "entropy_combined": self.entropy_combined,
            "source_detail": self.source_detail,
        }


# =========================================================================
# Resolution logic
# =========================================================================

def resolve_output_modulation(
    *,
    dha_result: object = None,
    C_s: float = 0.5,
    M: float = 0.0,
    H: float = 0.0,
    tier: str = "consumer",
    base_intensity: float = 1.0,
    entropy_gate: Optional[str] = None,
    entropy_combined: Optional[float] = None,
) -> OutputModulationResolution:
    """Resolve output modulation signals for rendering/output.

    This function combines three modulation signal sources:
    1. DHA formula delivery profile (from a pre-computed DHAResult)
    2. Guna modulation canonical intensity (E = G × P × T)
    3. Entropy gate information

    Args:
        dha_result: A DHAResult dict or object from formula DHA, if available.
            Duck-typed on tone_weights/I/R/D/suppressed keys (dict) or attrs.
        C_s: Structural coherence [0, 1] for guna derivation.
        M: Motion/transformation magnitude [0, 1] for guna derivation.
        H: Normalized entropy [0, 1] for guna derivation.
        tier: System tier name (enterprise_tier_1, enterprise_tier_2, consumer).
        base_intensity: Base intensity to modulate with E factor.
        entropy_gate: Entropy gate string (ALLOW/ALLOW_WITH_MODULATION/BLOCK).
        entropy_combined: Combined entropy value [0, 1].

    Returns:
        OutputModulationResolution with all resolved modulation signals.

    Fail-closed semantics:
        - If DHA unavailable → dha_available=False, no tone/intensity data
        - If guna modulation fails → guna_modulation_available=False
        - Failures do NOT weaken governance or alter output
    """
    parts = []

    # Path 1: Extract DHA delivery profile
    dha_fields = _extract_dha(dha_result)
    if dha_fields["dha_available"]:
        parts.append("dha_formula")

    # Path 2: Compute guna modulation E factor
    guna_fields = _compute_guna_modulation(
        C_s=C_s, M=M, H=H, tier=tier, base_intensity=base_intensity,
    )
    if guna_fields["guna_modulation_available"]:
        parts.append("guna_modulation")

    # Path 3: Entropy gate passthrough
    gate_str = None
    if entropy_gate is not None:
        gate_str = entropy_gate.value if hasattr(entropy_gate, "value") else str(entropy_gate)

    if gate_str:
        parts.append("entropy_gate")

    source = ", ".join(parts) if parts else "no modulation data"
    source_detail = f"output modulation resolved from: {source}"

    return OutputModulationResolution(
        # DHA
        dha_available=dha_fields["dha_available"],
        dha_tone_weights=dha_fields["dha_tone_weights"],
        dha_intensity=dha_fields["dha_intensity"],
        dha_restraint=dha_fields["dha_restraint"],
        dha_delivery_factor=dha_fields["dha_delivery_factor"],
        dha_dominant_tone=dha_fields["dha_dominant_tone"],
        dha_suppressed=dha_fields["dha_suppressed"],
        # Guna modulation
        guna_modulation_available=guna_fields["guna_modulation_available"],
        guna_E=guna_fields["guna_E"],
        guna_G=guna_fields["guna_G"],
        guna_P=guna_fields["guna_P"],
        guna_T_scalar=guna_fields["guna_T_scalar"],
        guna_output_intensity=guna_fields["guna_output_intensity"],
        guna_vector=guna_fields["guna_vector"],
        # Entropy gate
        entropy_gate=gate_str,
        entropy_combined=entropy_combined,
        # Provenance
        source_detail=source_detail,
    )


# =========================================================================
# DHA extraction
# =========================================================================

def _extract_dha(dha_result: object) -> Dict:
    """Extract DHA delivery profile from a DHAResult dict or object."""
    if dha_result is None:
        return _empty_dha()

    try:
        # Dict path (from maybe_run_dha / DHAResult.to_dict())
        if isinstance(dha_result, dict):
            tone_weights = dha_result.get("tone_weights")
            if tone_weights is None:
                return _empty_dha()
            # tone_weights may be a ToneWeights object with .to_dict()
            if hasattr(tone_weights, "to_dict"):
                tone_weights = tone_weights.to_dict()
            return {
                "dha_available": True,
                "dha_tone_weights": tone_weights,
                "dha_intensity": dha_result.get("I"),
                "dha_restraint": dha_result.get("R"),
                "dha_delivery_factor": dha_result.get("D"),
                "dha_dominant_tone": _dominant_from_weights(tone_weights),
                "dha_suppressed": dha_result.get("suppressed", False),
            }

        # Object path (DHAResult dataclass)
        tw = dha_result.tone_weights  # type: ignore[union-attr]
        tw_dict = tw.to_dict() if hasattr(tw, "to_dict") else {
            "sweet": tw.sweet, "jolt": tw.jolt, "metaphor": tw.metaphor,
        }
        return {
            "dha_available": True,
            "dha_tone_weights": tw_dict,
            "dha_intensity": dha_result.I,  # type: ignore[union-attr]
            "dha_restraint": dha_result.R,  # type: ignore[union-attr]
            "dha_delivery_factor": dha_result.D,  # type: ignore[union-attr]
            "dha_dominant_tone": dha_result.dominant_tone,  # type: ignore[union-attr]
            "dha_suppressed": dha_result.suppressed,  # type: ignore[union-attr]
        }

    except (AttributeError, TypeError, KeyError):
        logger.debug("Malformed DHA result, treating as unavailable")
        return _empty_dha()


def _empty_dha() -> Dict:
    """Return empty DHA fields."""
    return {
        "dha_available": False,
        "dha_tone_weights": None,
        "dha_intensity": None,
        "dha_restraint": None,
        "dha_delivery_factor": None,
        "dha_dominant_tone": None,
        "dha_suppressed": None,
    }


def _dominant_from_weights(tw: Dict[str, float]) -> Optional[str]:
    """Get dominant tone from weights dict."""
    if not tw:
        return None
    return max(tw, key=lambda k: tw.get(k, 0))


# =========================================================================
# Guna modulation computation
# =========================================================================

def _compute_guna_modulation(
    *,
    C_s: float,
    M: float,
    H: float,
    tier: str,
    base_intensity: float,
) -> Dict:
    """Compute guna modulation E = G × P × T.

    Uses the canonical EntropyModulationEngine from agentic.guna_modulation.
    """
    try:
        from agentic.guna_modulation.entropy_modulation_engine import (
            modulate_intensity,
        )
        from agentic.guna_modulation.types import ModulationTier

        tier_map = {
            "enterprise_tier_1": ModulationTier.ENTERPRISE_TIER_1,
            "enterprise_tier_2": ModulationTier.ENTERPRISE_TIER_2,
            "consumer": ModulationTier.CONSUMER,
        }
        tier_enum = tier_map.get(tier, ModulationTier.CONSUMER)

        result = modulate_intensity(
            base_intensity=base_intensity,
            C_s=max(0.0, min(1.0, C_s)),
            M=max(0.0, min(1.0, M)),
            H=max(0.0, min(1.0, H)),
            tier=tier_enum,
        )

        gv = result.guna_vector
        return {
            "guna_modulation_available": True,
            "guna_E": result.E,
            "guna_G": result.G,
            "guna_P": result.P,
            "guna_T_scalar": result.T,
            "guna_output_intensity": result.output_intensity,
            "guna_vector": {
                "sattva": gv.sattva,
                "rajas": gv.rajas,
                "tamas": gv.tamas,
            },
        }

    except Exception as exc:
        logger.debug("Guna modulation unavailable: %s", exc)
        return {
            "guna_modulation_available": False,
            "guna_E": None,
            "guna_G": None,
            "guna_P": None,
            "guna_T_scalar": None,
            "guna_output_intensity": None,
            "guna_vector": None,
        }


# =========================================================================
# Strategy 2: Bounded confidence adjustment from E
# =========================================================================

# Threshold constants for the E → confidence adjustment transform
_E_LOW_THRESHOLD = 0.4    # Below this, E causes a cautionary penalty
_E_HIGH_THRESHOLD = 0.7   # Above this, E provides modest uplift
_E_MAX_PENALTY = -0.10    # Maximum downside at E=0.0
_E_MAX_UPLIFT = 0.03      # Maximum upside at E=1.0


def compute_modulation_confidence_adjustment(
    guna_E: Optional[float],
) -> float:
    """Compute a bounded confidence adjustment derived from E = G × P × T.

    Design principles:
        - Low E (< 0.4) → cautionary penalty, up to -0.10
        - Neutral E (0.4 to 0.7) → no adjustment (dead zone)
        - High E (> 0.7) → modest uplift, up to +0.03
        - Asymmetric: downside penalty 3× larger than upside uplift
        - Missing/None E → 0.0 (neutral, no effect)

    The transform is:
        E < 0.4:  adjustment = -0.10 × (1 - E/0.4)     linear, ∈ [-0.10, 0]
        0.4 ≤ E ≤ 0.7:  adjustment = 0.0               dead zone
        E > 0.7:  adjustment = +0.03 × (E - 0.7)/0.3   linear, ∈ [0, +0.03]

    Bounds: [-0.10, +0.03]
    Deterministic and documented.

    Args:
        guna_E: The E = G × P × T modulation factor, or None if unavailable.

    Returns:
        Bounded confidence adjustment in [-0.10, +0.03].
    """
    if guna_E is None:
        return 0.0

    # Clamp E to [0, 1] defensively
    E = max(0.0, min(1.0, float(guna_E)))

    if E < _E_LOW_THRESHOLD:
        # Linear penalty: 0 at E=0.4, -0.10 at E=0.0
        return _E_MAX_PENALTY * (1.0 - E / _E_LOW_THRESHOLD)
    elif E > _E_HIGH_THRESHOLD:
        # Linear uplift: 0 at E=0.7, +0.03 at E=1.0
        return _E_MAX_UPLIFT * (E - _E_HIGH_THRESHOLD) / (1.0 - _E_HIGH_THRESHOLD)
    else:
        return 0.0
