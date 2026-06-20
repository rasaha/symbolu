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

    # --- Q1-Q5 answers (for the report) ---
    out["answers"]["bhava_beats_chance"] = bool(bhava.get("beats_chance"))
    out["answers"]["hidden_beats_chance"] = bool(hidden.get("beats_chance"))
    out["answers"]["bhava_beats_delta_bhava"] = (
        bhava.get("accuracy", 0) > delta.get("accuracy", 0) if delta else None
    )
    out["answers"]["bhava_beats_hidden"] = (
        bhava.get("accuracy", 0) >= hidden.get("accuracy", 0) if hidden else None
    )
    out["answers"]["bhava_complements_hidden"] = bool(
        hpb.get("significant") and hpb.get("direction") == "cand_better"
    )

    # --- insufficient data gate ---
    classes_ok = True  # caller computes per-class; we gate on n + CI width here
    widest_ci = max((r.get("acc_ci", [0, 1])[1] - r.get("acc_ci", [0, 1])[0]
                     for r in results.values()), default=1.0)
    if n < MIN_EXAMPLES or widest_ci > 0.5 or not classes_ok:
        out["decision"] = "INSUFFICIENT_DATA"
        out["reasons"].append(
            f"n={n} (<{MIN_EXAMPLES}) or accuracy CI width {widest_ci:.2f} > 0.5 — cannot resolve.")
        return out

    bhava_sig = bool(bhava.get("beats_chance"))
    hidden_sig = bool(hidden.get("beats_chance"))
    complements = out["answers"]["bhava_complements_hidden"]
    bhava_ge_hidden = bhava.get("accuracy", 0) >= hidden.get("accuracy", 0)

    # --- decision tree (pre-registered) ---
    if not bhava_sig and not hidden_sig:
        decision = "NO_SIGNAL"
        out["reasons"].append("Both bhava_only and hidden_only ~chance: task not decodable here.")
    elif bhava_sig and bhava_ge_hidden and complements:
        decision = "BHAVA_STRONG_SIGNAL"
        out["reasons"].append("bhava_only ≥ hidden_only AND hidden+bhava improves further.")
    elif complements:
        decision = "BHAVA_COMPLEMENTARY_SIGNAL"
        out["reasons"].append("hidden+bhava significantly beats hidden_only — Bhava adds signal.")
    elif hidden_sig and not bhava_sig:
        decision = "HIDDEN_ONLY_SIGNAL"
        out["reasons"].append("hidden_only predicts; bhava_only ~chance — Bhava not load-bearing.")
    elif bhava_sig and not complements:
        decision = "BHAVA_WEAK_SIGNAL"
        out["reasons"].append("bhava_only beats chance but adds nothing over hidden_only.")
    else:
        decision = "HIDDEN_ONLY_SIGNAL"
        out["reasons"].append("Fallback: signal present but Bhava not complementary.")

    out["decision"] = decision
    return out


def parks_bhava(decision: str) -> bool:
    """True if this decision parks Bhava as a generation lever."""
    return decision in ("NO_SIGNAL", "HIDDEN_ONLY_SIGNAL", "BHAVA_WEAK_SIGNAL")


def continues_bhava(decision: str) -> bool:
    return decision in ("BHAVA_COMPLEMENTARY_SIGNAL", "BHAVA_STRONG_SIGNAL")
