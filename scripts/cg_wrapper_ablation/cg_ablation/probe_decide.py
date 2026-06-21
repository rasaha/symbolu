"""Decision logic for the Bhava/ontology probe (pure Python; see BHAVA_ONTOLOGY_PROBE_PLAN.md §6).

Maps per-feature-set probe results + the paired hidden_plus_bhava-vs-hidden_only comparison to one
of the pre-registered categories. The scientific rule: Bhava is "useful" ONLY if bhava_only beats
chance AND hidden_plus_bhava beats hidden_only.
"""

from __future__ import annotations

from typing import Any, Dict

DECISIONS = (
    "INSUFFICIENT_DATA",
    "NO_SIGNAL",
    "HIDDEN_ONLY_SIGNAL",
    "BHAVA_WEAK_SIGNAL",
    "BHAVA_COMPLEMENTARY_SIGNAL",
    "BHAVA_STRONG_SIGNAL",
)

# Minimum labeled examples + minimum per-class count to even attempt a verdict.
MIN_EXAMPLES = 40
MIN_PER_CLASS = 8


def decide(results: Dict[str, Dict[str, Any]],
           paired: Dict[str, Dict[str, Any]],
           *, n: int, min_per_class: int) -> Dict[str, Any]:
    """Return {decision, reasons, answers} for one label_type.

    results: feature_set -> evaluate_feature_set(...) output.
    paired:  {"hidden_plus_bhava_vs_hidden": paired_vs_reference(...),
              "bhava_vs_delta_bhava": ...}  (optional keys tolerated).
    """
    out: Dict[str, Any] = {"reasons": [], "answers": {}}

    bhava = results.get("bhava_only", {})
    hidden = results.get("hidden_only", {})
    delta = results.get("delta_bhava_only", {})
    hpb = paired.get("hidden_plus_bhava_vs_hidden", {})

    def _auroc(r):
        a = r.get("auroc", float("nan"))
        return a if a == a else 0.0  # NaN -> 0

    # --- Q1-Q5 answers (for the report; decodability is AUROC-based, imbalance-robust) ---
    out["answers"]["bhava_beats_chance"] = bool(bhava.get("beats_chance"))
    out["answers"]["hidden_beats_chance"] = bool(hidden.get("beats_chance"))
    out["answers"]["bhava_beats_delta_bhava"] = (
        _auroc(bhava) > _auroc(delta) if delta else None
    )
    out["answers"]["bhava_beats_hidden"] = (
        _auroc(bhava) >= _auroc(hidden) if hidden else None
    )
    out["answers"]["bhava_complements_hidden"] = bool(
        hpb.get("significant") and hpb.get("direction") == "cand_better"
    )

    # --- insufficient data gate (AUROC CI too wide to resolve, or too few examples) ---
    def _ci_w(r):
        ci = r.get("auroc_ci", [0.0, 1.0])
        lo, hi = ci[0], ci[1]
        if lo != lo or hi != hi:   # NaN -> uninformative
            return 1.0
        return hi - lo
    widest_ci = max((_ci_w(r) for r in results.values()), default=1.0)
    if n < MIN_EXAMPLES or widest_ci > 0.5:
        out["decision"] = "INSUFFICIENT_DATA"
        out["reasons"].append(
            f"n={n} (<{MIN_EXAMPLES}) or AUROC CI width {widest_ci:.2f} > 0.5 — cannot resolve.")
        return out

    bhava_sig = bool(bhava.get("beats_chance"))
    hidden_sig = bool(hidden.get("beats_chance"))
    complements = out["answers"]["bhava_complements_hidden"]
    bhava_ge_hidden = _auroc(bhava) >= _auroc(hidden)

    # --- decision tree (pre-registered) ---
    # CONTINUE rule (user-specified): bhava_only AUROC CI lower bound > 0.5 (bhava_sig)
    # AND hidden_plus_bhava beats hidden_only with a significant paired delta (complements).
    # Both are required; anything else parks Bhava for generation.
    if not bhava_sig and not hidden_sig:
        decision = "NO_SIGNAL"
        out["reasons"].append("Both bhava_only and hidden_only ~chance (AUROC CI spans 0.5): "
                              "task not decodable here.")
    elif bhava_sig and complements and bhava_ge_hidden:
        decision = "BHAVA_STRONG_SIGNAL"
        out["reasons"].append("bhava_only decodable AND ≥ hidden AUROC AND hidden+bhava beats hidden.")
    elif bhava_sig and complements:
        decision = "BHAVA_COMPLEMENTARY_SIGNAL"
        out["reasons"].append("bhava_only decodable (CI>0.5) AND hidden+bhava significantly beats hidden.")
    elif bhava_sig and not complements:
        decision = "BHAVA_WEAK_SIGNAL"
        out["reasons"].append("bhava_only decodable but adds nothing over hidden_only — park.")
    else:
        decision = "HIDDEN_ONLY_SIGNAL"
        out["reasons"].append("hidden_only predicts; bhava_only not decodable (CI spans 0.5) — "
                              "Bhava not load-bearing.")

    out["decision"] = decision
    return out


def parks_bhava(decision: str) -> bool:
    """True if this decision parks Bhava as a generation lever."""
    return decision in ("NO_SIGNAL", "HIDDEN_ONLY_SIGNAL", "BHAVA_WEAK_SIGNAL")


def continues_bhava(decision: str) -> bool:
    return decision in ("BHAVA_COMPLEMENTARY_SIGNAL", "BHAVA_STRONG_SIGNAL")
