"""
Sovereign Health Signal Adapter — Governance-time health resolution (Phase S2).

Wraps the runtime-safe sovereign alert/health monitoring logic for
governance consumption. Accepts optional health metrics and returns
structured governance-ready outputs.

Fail-safe: if health signals are unavailable, governance proceeds
unchanged. A lockdown state adds escalation bias but does NOT
hard-block (stricter-only enrichment).

Bounded effects:
- LOCKDOWN_ACTIVE → adds escalation bias reason code
- ALERT → adds caution reason code
- Degraded entropy status → informational metadata
- All effects are additive; absence of health data = no change
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# =========================================================================
# Resolution result
# =========================================================================

@dataclass(frozen=True)
class SovereignHealthResolution:
    """Resolved sovereign health signal for governance use.

    Attributes:
        alert_state: Current alert state (STABLE/ALERT/LOCKDOWN_ACTIVE/RECOVERING).
        lockdown_count: Number of lockdowns observed.
        entropy_status: Entropy classification (SATTVIC/FOCUSED/BALANCED/RAJASIC/NIDRA).
        inertial_brake_active: Whether S8 entropy brake is active.
        escalation_bias: True if alert state warrants increased escalation.
        caution_bias: True if alert state warrants additional caution codes.
        reason_codes: Machine-readable reason codes for governance.
        available: Whether health signals were successfully resolved.
        source_detail: Human-readable description.
    """
    alert_state: str
    lockdown_count: int
    entropy_status: str
    inertial_brake_active: bool
    escalation_bias: bool
    caution_bias: bool
    reason_codes: Tuple[str, ...]
    available: bool
    source_detail: str


# =========================================================================
# Resolution logic
# =========================================================================

def resolve_sovereign_health(
    *,
    alert_state: Optional[str] = None,
    lockdown_count: int = 0,
    entropy: Optional[float] = None,
    brake_active: bool = False,
    sa_ratio: Optional[float] = None,
    guna_coherence: Optional[float] = None,
    l_consistency: Optional[float] = None,
) -> SovereignHealthResolution:
    """Resolve sovereign health as a governance signal.

    Can be called with pre-computed alert state (from external monitoring)
    or with raw metrics that get classified here.

    Args:
        alert_state: Pre-computed alert state string, or None to infer.
        lockdown_count: Number of lockdowns observed.
        entropy: Normalized semantic entropy [0, 1], or None.
        brake_active: Whether S8 inertial brake is active.
        sa_ratio: Sensory/authority ratio, or None.
        guna_coherence: Guna coherence [0, 1], or None.
        l_consistency: Consistency Lagrangian value, or None.

    Returns:
        SovereignHealthResolution with governance-ready signals.

    Fail-safe:
        If no health data is available, returns a safe resolution
        with available=False, no biases, no reason codes.
    """
    # If we have no signal at all, return unavailable
    if alert_state is None and entropy is None and sa_ratio is None:
        return SovereignHealthResolution(
            alert_state="UNKNOWN",
            lockdown_count=0,
            entropy_status="UNKNOWN",
            inertial_brake_active=False,
            escalation_bias=False,
            caution_bias=False,
            reason_codes=(),
            available=False,
            source_detail="no sovereign health data available",
        )

    try:
        from agentic.sovereign_metrics_runtime import get_entropy_status
    except ImportError:
        # Inline fallback
        def get_entropy_status(e: float) -> Tuple[str, str]:
            if e < 0.30:
                return "SATTVIC_CLARITY", "SATTVIC"
            elif e < 0.50:
                return "HIGH_PRECISION", "FOCUSED"
            elif e < 0.70:
                return "CREATIVE_EXPLORATION", "BALANCED"
            elif e < 0.85:
                return "CONFUSION_RISK", "RAJASIC"
            else:
                return "COLLAPSE_RISK", "NIDRA"

    # Classify entropy
    if entropy is not None:
        _, entropy_status = get_entropy_status(entropy)
    else:
        entropy_status = "UNKNOWN"

    # Use provided alert state or infer from metrics
    effective_state = alert_state or "STABLE"
    if alert_state is None and entropy is not None:
        # Simple inference from available signals
        if entropy >= 0.85:
            effective_state = "ALERT"
        elif guna_coherence is not None and guna_coherence < 0.25:
            effective_state = "ALERT"

    # Build reason codes and biases
    reason_codes: List[str] = []
    escalation_bias = False
    caution_bias = False

    if effective_state == "LOCKDOWN_ACTIVE":
        escalation_bias = True
        caution_bias = True
        reason_codes.append("SOVEREIGN_LOCKDOWN")
    elif effective_state == "ALERT":
        caution_bias = True
        reason_codes.append("SOVEREIGN_ALERT")
    elif effective_state == "RECOVERING":
        caution_bias = True
        reason_codes.append("SOVEREIGN_RECOVERING")

    if brake_active:
        reason_codes.append("S8_BRAKE_ACTIVE")
        caution_bias = True

    if entropy_status in ("RAJASIC", "NIDRA"):
        reason_codes.append(f"ENTROPY_{entropy_status}")
        caution_bias = True

    source_parts = [f"alert={effective_state}"]
    if entropy is not None:
        source_parts.append(f"entropy={entropy:.3f}({entropy_status})")
    if brake_active:
        source_parts.append("brake=active")

    return SovereignHealthResolution(
        alert_state=effective_state,
        lockdown_count=lockdown_count,
        entropy_status=entropy_status,
        inertial_brake_active=brake_active,
        escalation_bias=escalation_bias,
        caution_bias=caution_bias,
        reason_codes=tuple(reason_codes),
        available=True,
        source_detail=f"sovereign health ({', '.join(source_parts)})",
    )
