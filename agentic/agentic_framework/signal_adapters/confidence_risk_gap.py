"""
Confidence-Risk Gap — escalate when the model is CONFIDENTLY UNCERTAIN.

This operationalizes the fastest-falsification finding: the dangerous signature is high
VERBALIZED safety confidence (the model says "this is safe to do") paired with high RAW
next-token entropy (the model is internally uncertain) on a non-trivial action. On the
fabrication probe, that combination flagged the confident-but-unsafe (fooled) cases where
verbalized confidence alone was useless. So: when the words say "safe" but the logits say
"unsure", escalate to a human.

Conservative + provider-agnostic by design:
  - Both inputs (a verbalized safety confidence AND a resolved raw entropy) must be present.
    If raw entropy is unavailable, the gap cannot be assessed and governance degrades to
    verbalized confidence + risk taxonomy (no escalation from this primitive).
  - Fires only above configured thresholds AND at/above a minimum tool risk level, so
    read-only and low-confidence cases never trigger it.

No proprietary claim — this is a simple, transparent rule over standard signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from agentic.agentic_framework.signal_adapters.raw_entropy_adapter import RawEntropyResolution
from agentic.agentic_framework.signal_config import DEFAULT_SIGNAL_CONFIG, SignalConfig


@dataclass(frozen=True)
class ConfidenceRiskGapResult:
    """Outcome of the confidence-risk gap assessment.

    Attributes:
        escalate: Whether to raise escalation (confident-but-uncertain on a risky tool).
        level: Escalation level to apply if escalate ("notify" | "confirm" | "halt"),
            else "none".
        gap: max(0, verbalized_safety + raw_entropy - 1) in [0, 1] — magnitude of the
            "confident yet uncertain" divergence (0 when the two are consistent).
        verbalized_safety: The verbalized safety confidence used, or None.
        raw_entropy: The resolved raw entropy used, or None.
        available: Whether the gap could be assessed (both inputs present + enabled).
        reason: Human-readable audit explanation of the decision.
    """
    escalate: bool
    level: str
    gap: float
    verbalized_safety: Optional[float]
    raw_entropy: Optional[float]
    available: bool
    reason: str

    def to_audit(self) -> Dict[str, Any]:
        return {
            "confidence_risk_gap_escalate": self.escalate,
            "confidence_risk_gap_level": self.level,
            "confidence_risk_gap_value": round(self.gap, 4),
            "confidence_risk_gap_verbalized_safety": self.verbalized_safety,
            "confidence_risk_gap_raw_entropy": self.raw_entropy,
            "confidence_risk_gap_available": self.available,
            "confidence_risk_gap_reason": self.reason,
        }


def _result(escalate, level, gap, vs, re, available, reason) -> ConfidenceRiskGapResult:
    return ConfidenceRiskGapResult(
        escalate=escalate, level=level, gap=gap, verbalized_safety=vs,
        raw_entropy=re, available=available, reason=reason)


def assess_confidence_risk_gap(
    *,
    verbalized_safety_confidence: Optional[float],
    raw_entropy_resolution: RawEntropyResolution,
    tool_risk_level: str,
    config: SignalConfig = DEFAULT_SIGNAL_CONFIG,
) -> ConfidenceRiskGapResult:
    """Assess the confidence-risk gap and decide whether to escalate.

    Escalates iff (gap enabled) AND verbalized safety >= verbalized_safety_high AND raw
    entropy >= raw_entropy_high AND tool risk >= min_risk_level_for_gap. Degrades to
    no-escalation (available=False) when raw entropy or the verbalized score is absent.
    """
    if not config.enable_confidence_risk_gap:
        return _result(False, "none", 0.0, verbalized_safety_confidence,
                       raw_entropy_resolution.raw_entropy, False,
                       "confidence-risk gap disabled")

    if not raw_entropy_resolution.available or raw_entropy_resolution.raw_entropy is None:
        return _result(False, "none", 0.0, verbalized_safety_confidence, None, False,
                       "raw entropy unavailable; degrading to verbalized confidence + "
                       "risk taxonomy (no gap escalation)")

    if verbalized_safety_confidence is None:
        return _result(False, "none", 0.0, None, raw_entropy_resolution.raw_entropy,
                       False, "no verbalized safety confidence provided; gap not assessed")

    try:
        vs = min(1.0, max(0.0, float(verbalized_safety_confidence)))
    except (TypeError, ValueError):
        return _result(False, "none", 0.0, None, raw_entropy_resolution.raw_entropy,
                       False, "verbalized safety confidence not numeric; gap not assessed")

    re = raw_entropy_resolution.raw_entropy
    gap = max(0.0, vs + re - 1.0)
    confident = vs >= config.verbalized_safety_high
    uncertain = re >= config.raw_entropy_high
    risk_ok = config.risk_meets_gap_minimum(tool_risk_level)

    if confident and uncertain and risk_ok:
        return _result(
            True, config.gap_escalation_level, gap, vs, re, True,
            f"confidence-risk gap: model reports safe (verbalized={vs:.2f} >= "
            f"{config.verbalized_safety_high:.2f}) but is internally uncertain "
            f"(raw_entropy={re:.2f} >= {config.raw_entropy_high:.2f}) on a "
            f"{tool_risk_level} tool -> escalate ({config.gap_escalation_level}).")

    # Assessed, but did not meet all gates — explain which gate held.
    held = []
    if not confident:
        held.append(f"verbalized={vs:.2f}<{config.verbalized_safety_high:.2f}")
    if not uncertain:
        held.append(f"raw_entropy={re:.2f}<{config.raw_entropy_high:.2f}")
    if not risk_ok:
        held.append(f"risk={tool_risk_level}<{config.min_risk_level_for_gap}")
    return _result(False, "none", gap, vs, re, True,
                   "confidence-risk gap below threshold (" + ", ".join(held) + ")")
