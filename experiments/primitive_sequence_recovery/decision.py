"""Cross-realization decision helper.

Combines per-realization verdicts into one label. The confirmatory claim (see
PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md) is CROSS-REALIZATION INVARIANCE: the real
assignment must beat scrambled under EVERY realization. English is never privileged.
"""
from __future__ import annotations

LABELS = ("ONTOLOGICAL_SIGNAL", "REALIZATION_ARTIFACT", "NO_SIGNAL",
          "REALIZER_DEPENDENT", "INCONCLUSIVE")


def per_realization_verdict(delta_result, threshold: float = 0.02, pct_threshold: float = 0.95,
                            inconclusive: bool = False, encoder_disagreement: bool = False) -> dict:
    """Turn a scoring.delta_j result into a per-realization record.

    positive := beats the scramble null (Δ over threshold AND scramble percentile high).
    `inconclusive` / `encoder_disagreement` are supplied by the (out-of-scope) stats layer.
    """
    positive = (delta_result["delta"] > threshold) and (delta_result["scramble_pct"] >= pct_threshold)
    return {"realization": delta_result.get("realization"),
            "positive": bool(positive),
            "inconclusive": bool(inconclusive),
            "encoder_disagreement": bool(encoder_disagreement)}


def cross_realization_decision(records) -> str:
    """records: list of {positive, inconclusive, encoder_disagreement}. Returns one LABEL.

    Precedence:
      1. any encoder disagreement within a realization -> REALIZER_DEPENDENT (validity failure)
      2. any inconclusive realization -> INCONCLUSIVE (cross-realization test cannot complete)
      3. positive under EVERY realization -> ONTOLOGICAL_SIGNAL
      4. positive under NO realization -> NO_SIGNAL
      5. positive under some but not all -> REALIZATION_ARTIFACT
    """
    if not records:
        return "INCONCLUSIVE"
    if any(r.get("encoder_disagreement") for r in records):
        return "REALIZER_DEPENDENT"
    if any(r.get("inconclusive") for r in records):
        return "INCONCLUSIVE"
    pos = [bool(r.get("positive")) for r in records]
    if all(pos):
        return "ONTOLOGICAL_SIGNAL"
    if not any(pos):
        return "NO_SIGNAL"
    return "REALIZATION_ARTIFACT"
