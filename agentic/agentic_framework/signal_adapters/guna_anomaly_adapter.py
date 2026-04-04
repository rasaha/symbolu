"""
Guna Anomaly Adapter — Governance-side consumption of Guna anomaly signals.

Wraps the pure-Python Guna anomaly detection into a governance-compatible
resolution with bounded effects:

  - Confidence penalty: max 0.05 for collapse or oscillation (stricter-only)
  - Escalation bias: True when collapse detected (bump escalation by 1)
  - Caution reason codes: GUNA_COLLAPSE, GUNA_OSCILLATION, GUNA_STAGNATION
  - Audit metadata: full anomaly snapshot

Stagnation is informational only — it does not penalize confidence or
trigger escalation, because stagnation means the model is stable
(just not changing), which is not inherently dangerous.

Phase S4: sovereign integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class GunaAnomalyResolution:
    """Governance-compatible Guna anomaly resolution."""

    # Anomaly flags
    collapse: bool = False
    oscillation: bool = False
    stagnation: bool = False
    dominant_guna: str = "unknown"

    # Bounded governance effects
    confidence_penalty: float = 0.0    # max 0.05 (stricter-only)
    escalation_bias: bool = False      # True → bump escalation by 1
    reason_codes: Tuple[str, ...] = ()

    # Metadata
    available: bool = False
    source_detail: str = "guna_anomaly_adapter"

    def to_audit_dict(self) -> Dict[str, object]:
        """Serialize for audit trail."""
        return {
            "collapse": self.collapse,
            "oscillation": self.oscillation,
            "stagnation": self.stagnation,
            "dominant_guna": self.dominant_guna,
            "confidence_penalty": self.confidence_penalty,
            "escalation_bias": self.escalation_bias,
            "reason_codes": list(self.reason_codes),
            "available": self.available,
            "source_detail": self.source_detail,
        }


# Maximum confidence penalty from Guna anomalies (intentionally conservative)
_MAX_GUNA_PENALTY = 0.05


def resolve_guna_anomaly(
    anomaly_data: Optional[Dict[str, Any]] = None,
) -> GunaAnomalyResolution:
    """Resolve Guna anomaly signals into governance-compatible form.

    Args:
        anomaly_data: Dict with keys from GunaAnomalySnapshot.to_audit_dict()
            or from GunaMonitor output. Expected keys:
            - collapse (bool)
            - oscillation (bool)
            - stagnation (bool)
            - dominant_guna (str)
            - statistics (optional dict)

    Returns:
        GunaAnomalyResolution with bounded effects.
        If anomaly_data is None or resolution fails, returns safe defaults.
    """
    if anomaly_data is None:
        return GunaAnomalyResolution()

    try:
        collapse = bool(anomaly_data.get("collapse", False))
        oscillation = bool(anomaly_data.get("oscillation", False))
        stagnation = bool(anomaly_data.get("stagnation", False))
        dominant_guna = str(anomaly_data.get("dominant_guna", "unknown"))

        # Build reason codes
        codes: List[str] = []
        if collapse:
            codes.append("GUNA_COLLAPSE")
        if oscillation:
            codes.append("GUNA_OSCILLATION")
        if stagnation:
            codes.append("GUNA_STAGNATION")

        # Bounded confidence penalty (stricter-only)
        # Collapse and oscillation each contribute; stagnation does not
        penalty = 0.0
        if collapse:
            penalty += 0.03
        if oscillation:
            penalty += 0.02
        penalty = min(penalty, _MAX_GUNA_PENALTY)

        # Escalation bias: only for collapse (most severe anomaly)
        escalation_bias = collapse

        return GunaAnomalyResolution(
            collapse=collapse,
            oscillation=oscillation,
            stagnation=stagnation,
            dominant_guna=dominant_guna,
            confidence_penalty=penalty,
            escalation_bias=escalation_bias,
            reason_codes=tuple(codes),
            available=True,
            source_detail="guna_anomaly_adapter",
        )
    except Exception:
        return GunaAnomalyResolution()
