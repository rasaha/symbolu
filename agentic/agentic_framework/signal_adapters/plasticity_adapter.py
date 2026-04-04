"""
Plasticity Gate Adapter — Governance-Safe Plasticity Signal
============================================================

Phase S2: Bridges the ``PlasticityGate`` from
``agentic.safety.governance_patterns.plasticity_gate`` into the governance
authorization path as a bounded, deterministic signal.

The plasticity gate computes a smooth sigmoid permission-to-act value
[~0.27, 1.0] from two inputs:
    - **resistance** (stability): how stable the system is [0, 1]
    - **misalignment** (drift): how far the system has drifted [0, 1]

High stability and low drift open the gate; low stability and/or high
drift close it.

Input sourcing:
    This adapter sources its inputs from already-resolved governance
    signals (core coherence state), requiring NO new upstream dependencies:
    - resistance ← coherence_score or semantic_stability (whichever available)
    - misalignment ← persona_drift

    Both are already computed by the time this adapter runs in the
    authorize() pipeline.

Design:
    Follows the signal adapter pattern (see coherence_state_adapter, ontology_adapter):
    - Frozen Resolution dataclass (immutable, serializable)
    - ``resolve_plasticity_signal()`` pure function (deterministic, fail-closed)
    - Bounded confidence penalty (max 0.04)
    - ``available`` / ``source_detail`` / ``reason_codes`` provenance

Statelessness note:
    The PlasticityGate supports session-level double-EMA smoothing via
    persistent internal state. In this governance adapter, we create a
    fresh gate per call (no cross-request state). This means we get
    the sigmoid gating behavior but not the temporal smoothing.
    Session-level EMA integration is a future enhancement requiring
    pipeline↔governance state bridging.

Dependency:
    Imports PlasticityGate from agentic.safety.governance_patterns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from agentic.safety.governance_patterns.plasticity_gate import (
    PlasticityGate,
    PlasticityResult,
)


# =========================================================================
# Constants
# =========================================================================

# Max confidence penalty this adapter can impose.
# Modest contribution to the sovereign aggregate cap (0.20).
_MAX_PENALTY: float = 0.04

# Plasticity below this threshold triggers a confidence penalty.
# At default parameters, plasticity ~0.50 corresponds to neutral logit=0.
_LOW_PLASTICITY_THRESHOLD: float = 0.50

# Plasticity below this triggers escalation bias (gate nearly closed).
_CRITICAL_PLASTICITY_THRESHOLD: float = 0.35

# Default resistance when no stability signal is available.
# 0.5 is neutral — neither opens nor closes the gate.
_DEFAULT_RESISTANCE: float = 0.5

# Default misalignment when no drift signal is available.
# 0.0 is safe default — no drift closes nothing.
_DEFAULT_MISALIGNMENT: float = 0.0


# =========================================================================
# Governance-facing contract
# =========================================================================

@dataclass(frozen=True)
class PlasticityResolution:
    """Governance-safe view of the plasticity gate computation.

    Field categories
    ----------------

    BEHAVIOR-AFFECTING:
        plasticity          Gate value [~0.27, 1.0]. Higher = more open.
        resistance          Stability input fed to the gate [0, 1].
        misalignment        Drift input fed to the gate [0, 1].
        logit               Pre-sigmoid logit value.

    ADAPTER METADATA:
        confidence_penalty  Bounded [0, MAX_PENALTY] penalty applied.
        escalation_bias     Whether escalation should be bumped.
        reason_codes        Machine-readable governance codes.
        available           Whether signal was successfully resolved.
        source_detail       Human-readable provenance description.
    """

    # --- Behavior-affecting ---
    plasticity: Optional[float]
    resistance: Optional[float]
    misalignment: Optional[float]
    logit: Optional[float]

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
            "plasticity", "resistance", "misalignment", "logit",
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

_EMPTY_RESOLUTION = PlasticityResolution(
    plasticity=None,
    resistance=None,
    misalignment=None,
    logit=None,
    confidence_penalty=0.0,
    escalation_bias=False,
    reason_codes=(),
    available=False,
    source_detail="plasticity signal unavailable",
)


def _empty_resolution(
    detail: str = "plasticity signal unavailable",
) -> PlasticityResolution:
    """Return a safe empty resolution (fail-closed: zero penalty)."""
    if detail == _EMPTY_RESOLUTION.source_detail:
        return _EMPTY_RESOLUTION
    return PlasticityResolution(
        plasticity=None,
        resistance=None,
        misalignment=None,
        logit=None,
        confidence_penalty=0.0,
        escalation_bias=False,
        reason_codes=(),
        available=False,
        source_detail=detail,
    )


# =========================================================================
# Confidence penalty computation
# =========================================================================

def _compute_penalty(plasticity: float) -> float:
    """Compute bounded confidence penalty from plasticity gate value.

    Penalty budget (max _MAX_PENALTY = 0.04):
    - plasticity >= 0.50 → 0.0 penalty (gate open enough)
    - plasticity < 0.50  → linear penalty up to 0.04 (gate closing)

    The floor of the sigmoid (~0.27) produces max penalty.
    """
    if plasticity >= _LOW_PLASTICITY_THRESHOLD:
        return 0.0

    # Linear from threshold (0.0 penalty) to sigmoid floor (full penalty)
    ratio = 1.0 - (plasticity / _LOW_PLASTICITY_THRESHOLD)
    return min(_MAX_PENALTY, _MAX_PENALTY * ratio)


def _should_escalate(plasticity: float) -> bool:
    """Determine if escalation should be bumped.

    Triggers only when gate is nearly closed (< 0.35).
    """
    return plasticity < _CRITICAL_PLASTICITY_THRESHOLD


# =========================================================================
# Main resolution function
# =========================================================================

def resolve_plasticity_signal(
    *,
    coherence_score: Optional[float] = None,
    semantic_stability: Optional[float] = None,
    persona_drift: Optional[float] = None,
) -> PlasticityResolution:
    """Resolve plasticity gate signal for governance use.

    Args:
        coherence_score: Overall pipeline coherence [0, 1].
            Used as resistance input when semantic_stability unavailable.
        semantic_stability: Semantic consistency [0, 1].
            Preferred resistance input (more specific than coherence_score).
        persona_drift: Persona drift magnitude [0, 1].
            Used as misalignment input. Higher = more drift.

    Returns:
        PlasticityResolution with gate value and bounded penalty.

    Input priority:
        resistance = semantic_stability ?? coherence_score ?? 0.5
        misalignment = persona_drift ?? 0.0

    Fail-closed semantics:
        If ALL inputs are None, returns available=False with zero penalty.
        Absence of signals never weakens governance.
        If at least one input is available, the gate computes with
        safe defaults for the missing ones.
    """
    # Determine if we have any usable input at all
    has_any_input = (
        coherence_score is not None
        or semantic_stability is not None
        or persona_drift is not None
    )

    if not has_any_input:
        return _empty_resolution()

    try:
        return _compute_from_inputs(
            coherence_score=coherence_score,
            semantic_stability=semantic_stability,
            persona_drift=persona_drift,
        )
    except Exception:
        return _empty_resolution("plasticity computation failed")


def _compute_from_inputs(
    *,
    coherence_score: Optional[float],
    semantic_stability: Optional[float],
    persona_drift: Optional[float],
) -> PlasticityResolution:
    """Compute plasticity gate from available inputs.

    Creates a fresh PlasticityGate per call (stateless — no session EMA).
    """
    # Determine resistance: prefer semantic_stability, fall back to coherence
    if semantic_stability is not None:
        resistance = max(0.0, min(1.0, float(semantic_stability)))
        resistance_source = "semantic_stability"
    elif coherence_score is not None:
        resistance = max(0.0, min(1.0, float(coherence_score)))
        resistance_source = "coherence_score"
    else:
        resistance = _DEFAULT_RESISTANCE
        resistance_source = "default"

    # Determine misalignment
    if persona_drift is not None:
        misalignment = max(0.0, min(1.0, float(persona_drift)))
        misalignment_source = "persona_drift"
    else:
        misalignment = _DEFAULT_MISALIGNMENT
        misalignment_source = "default"

    # Compute gate (fresh instance — no session EMA in governance path)
    gate = PlasticityGate()
    result: PlasticityResult = gate.compute(
        resistance=resistance,
        misalignment=misalignment,
    )

    # Compute penalty and escalation
    penalty = _compute_penalty(result.plasticity)
    escalation = _should_escalate(result.plasticity)

    # Build reason codes
    codes = []
    if penalty > 0:
        codes.append("PLASTICITY_PENALTY")
    if escalation:
        codes.append("PLASTICITY_ESCALATION")

    # Build source detail
    detail_parts = [
        f"plasticity={result.plasticity:.3f}",
        f"resistance={resistance:.3f}({resistance_source})",
        f"misalignment={misalignment:.3f}({misalignment_source})",
    ]
    source_detail = f"PlasticityGate ({', '.join(detail_parts)})"

    return PlasticityResolution(
        plasticity=result.plasticity,
        resistance=result.resistance,
        misalignment=result.misalignment,
        logit=result.logit,
        confidence_penalty=penalty,
        escalation_bias=escalation,
        reason_codes=tuple(codes),
        available=True,
        source_detail=source_detail,
    )
