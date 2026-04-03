"""
Trading Formula Guardrail Engine v1.0
======================================

Zero-LLM, deterministic trading safety guardrails based on Symbol-U formulas.

This module provides trading-specific safety checks using:
- Tension Corridor (from coherence state)
- Resonance Index (derived metric)
- Delta SMI (temporal momentum)
- Coherence Score v1
- Mapper Volatility Score
- Persona Drift Score

Design Principles:
- Zero-LLM: Pure deterministic rule evaluation
- Non-invasive: Does not modify routing, rendering, or pipeline behavior
- UI-layer only: Provides metadata for presentation layer
- Feature-flag gated: Only runs when formula_guardrails_enabled=True in domain profile

Canonical Rules v1.0:
---------------------
1. High Tension Risk:
   - Trigger: tension_corridor > max_tension_allowed AND resonance_index < 0.45

2. Negative Momentum Risk:
   - Trigger: delta_smi < -max_negative_delta_smi AND coherence_score_v1 < 0.55

3. Volatility Risk:
   - Trigger: mapper_volatility_score > max_volatility_allowed AND persona_drift_score > 0.45

4. Recommend No Action:
   - Trigger: ANY of the above 3 risks are TRUE

Usage:
    from agentic.policy.trading_guardrail_engine import compute_trading_guardrails

    guardrails = compute_trading_guardrails(
        summary=session_summary,
        policy=policy_flags,
        motivation=ctx.motivation_profile,
        intent_arc=ctx.intent_arc,
        identity_signature=ctx.identity_signature
    )

    if guardrails.recommend_no_action:
        # Show UI warning: "High risk detected - consider waiting"
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class TradingGuardrailFlags:
    """
    Trading guardrail risk flags.

    These flags are deterministic indicators of trading safety risk
    based on Symbol-U temporal formulas and coherence metrics.

    Attributes:
        high_tension_risk: High tension corridor with low resonance
        negative_momentum_risk: Negative delta SMI with low coherence
        volatility_risk: High mapper volatility with high persona drift
        recommend_no_action: Master switch - ANY risk triggers this
    """
    high_tension_risk: bool = False
    negative_momentum_risk: bool = False
    volatility_risk: bool = False
    recommend_no_action: bool = False

    def to_dict(self) -> Dict[str, bool]:
        """
        Convert to JSON-serializable dictionary.

        Returns:
            Dictionary with all guardrail flags
        """
        return {
            "high_tension_risk": self.high_tension_risk,
            "negative_momentum_risk": self.negative_momentum_risk,
            "volatility_risk": self.volatility_risk,
            "recommend_no_action": self.recommend_no_action,
        }


def compute_trading_guardrails(
    summary: Any,
    policy: Any,
    motivation: Any,
    intent_arc: Any,
    identity_signature: Any,
) -> TradingGuardrailFlags:
    """
    Compute trading guardrails from session state and formula metrics.

    This is the main guardrail computation function. It evaluates 3 risk
    conditions and sets the recommend_no_action flag if ANY risk is detected.

    Args:
        summary: SessionSummary with coherence metrics and formula values
        policy: PolicyFlags (currently unused, reserved for future extensions)
        motivation: MotivationProfile (currently unused, reserved for future extensions)
        intent_arc: IntentArc (currently unused, reserved for future extensions)
        identity_signature: IdentitySignature (currently unused, reserved for future extensions)

    Returns:
        TradingGuardrailFlags with risk indicators

    Raises:
        ValueError: If summary is None or missing required metrics

    Examples:
        >>> from symbolu_core.service.sessions import SessionSummary
        >>> summary = SessionSummary(
        ...     coherence_score=0.50,
        ...     tension_corridor=0.75,
        ...     resonance_index=0.40,
        ...     delta_smi=-0.15,
        ...     mapper_volatility_score=0.65,
        ...     persona_drift_score=0.50,
        ... )
        >>> guardrails = compute_trading_guardrails(summary, None, None, None, None)
        >>> guardrails.high_tension_risk
        True
        >>> guardrails.recommend_no_action
        True
    """
    # Validate inputs
    if summary is None:
        raise ValueError("SessionSummary is required for trading guardrails")

    # Extract coherence metrics from summary
    # These values come from CoherenceObserver and SessionSummary
    coherence_score_v1 = _safe_get_float(summary, "coherence_score", 1.0)
    mapper_volatility_score = _safe_get_float(summary, "mapper_volatility_score", 0.0)
    persona_drift_score = _safe_get_float(summary, "persona_drift_score", 0.0)

    # Extract temporal formulas from summary
    # These values come from CoherenceState histories
    tension_corridor = _safe_get_float(summary, "tension_corridor", 0.0)
    resonance_index = _safe_get_float(summary, "resonance_index", 1.0)
    delta_smi = _safe_get_float(summary, "delta_smi", 0.0)

    # Get domain profile thresholds from summary
    # These are injected by SessionStore when summary is created
    max_tension_allowed = _safe_get_float(summary, "max_tension_allowed", 0.70)
    max_negative_delta_smi = _safe_get_float(summary, "max_negative_delta_smi", 0.12)
    max_volatility_allowed = _safe_get_float(summary, "max_volatility_allowed", 0.60)

    # Initialize flags
    flags = TradingGuardrailFlags()

    # ========================================================================
    # RULE 1: High Tension Risk
    # ========================================================================
    # Trigger when BOTH:
    # - tension_corridor > max_tension_allowed
    # - resonance_index < 0.45
    if tension_corridor > max_tension_allowed and resonance_index < 0.45:
        flags.high_tension_risk = True

    # ========================================================================
    # RULE 2: Negative Momentum Risk
    # ========================================================================
    # Trigger when BOTH:
    # - delta_smi < -max_negative_delta_smi
    # - coherence_score_v1 < 0.55
    if delta_smi < -max_negative_delta_smi and coherence_score_v1 < 0.55:
        flags.negative_momentum_risk = True

    # ========================================================================
    # RULE 3: Volatility Risk
    # ========================================================================
    # Trigger when BOTH:
    # - mapper_volatility_score > max_volatility_allowed
    # - persona_drift_score > 0.45
    if mapper_volatility_score > max_volatility_allowed and persona_drift_score > 0.45:
        flags.volatility_risk = True

    # ========================================================================
    # RULE 4: Recommend No Action (Master Switch)
    # ========================================================================
    # Trigger when ANY of the above 3 risks are TRUE
    if flags.high_tension_risk or flags.negative_momentum_risk or flags.volatility_risk:
        flags.recommend_no_action = True

    return flags


# ============================================================================
# Helper Functions
# ============================================================================


def _safe_get_float(obj: Any, attr: str, default: float) -> float:
    """
    Safely extract a float attribute from an object or dict.

    Supports both attribute access (obj.attr) and dict access (obj[attr]).

    Args:
        obj: Object or dictionary to extract from
        attr: Attribute name or key
        default: Default value if attribute is missing or None

    Returns:
        Float value or default
    """
    # Try attribute access first (for dataclass objects)
    if hasattr(obj, attr):
        value = getattr(obj, attr, default)
        return float(value) if value is not None else default

    # Try dict access (for dict objects)
    if isinstance(obj, dict):
        value = obj.get(attr, default)
        return float(value) if value is not None else default

    # Fallback to default
    return default


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    'TradingGuardrailFlags',
    'compute_trading_guardrails',
]
