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


# ===========================================================================
# Static CSR = Context x Semantic x Resonance  (docs/STL_CSR_REFACTOR_PLAN.md)
# ===========================================================================

CSR_DECISIONS = (
    "INSUFFICIENT_DATA", "NO_SIGNAL", "STATE_BHAVA_ONLY_SIGNAL", "RESONANCE_ONLY_SIGNAL",
    "CONTEXT_ONLY_SIGNAL", "SEMANTIC_ONLY_SIGNAL", "CSR_REDUNDANT", "CSR_COMPLEMENTARY",
    "CSR_STRONG_SIGNAL", "HIDDEN_ONLY_SIGNAL",
)


def csr_continues(decision: str) -> bool:
    return decision in ("CSR_COMPLEMENTARY", "CSR_STRONG_SIGNAL")


def decide_csr(results: Dict[str, Dict[str, Any]], paired: Dict[str, Dict[str, Any]],
               *, n: int) -> Dict[str, Any]:
    """Static-CSR decision (Task 5). `results`: set->metrics; `paired`: cand_vs_ref dicts.

    CONTINUE only on CSR_COMPLEMENTARY (csr_static beats its best part) or CSR_STRONG_SIGNAL
    (hidden+state_bhava+csr beats hidden_only). Beating chance with one part is not enough.
    """
    out: Dict[str, Any] = {"reasons": [], "answers": {}}

    def dec(name):  # decodable (AUROC CI lower bound > 0.5)
        return bool(results.get(name, {}).get("beats_chance"))

    def sig(key):   # a paired comparison is significant & cand_better
        p = paired.get(key, {})
        return bool(p.get("significant") and p.get("direction") == "cand_better")

    sb = dec("state_bhava_only")
    res = dec("resonance_combined") or dec("phoneme_bhava_only") or dec("vritti_consonant_only")
    ctx = dec("context_r_ctx_only")
    sem = dec("semantic_only")
    hid = dec("hidden_only")

    csr_beats_parts = (sig("csr_vs_context") or sig("csr_vs_semantic") or sig("csr_vs_resonance"))
    full_beats_hidden = sig("hidden_plus_all_vs_hidden")
    csr_adds_to_sb = sig("state_bhava_plus_csr_vs_state_bhava")

    out["answers"] = {
        "state_bhava_decodable": sb, "resonance_decodable": res,
        "context_decodable": ctx, "semantic_decodable": sem, "hidden_decodable": hid,
        "csr_beats_parts": csr_beats_parts, "csr_adds_to_state_bhava": csr_adds_to_sb,
        "full_beats_hidden": full_beats_hidden,
    }

    # insufficient-data gate (wide AUROC CI or tiny n)
    def ci_w(nm):
        ci = results.get(nm, {}).get("auroc_ci", [0.0, 1.0])
        lo, hi = ci[0], ci[1]
        return 1.0 if (lo != lo or hi != hi) else (hi - lo)
    widest = max((ci_w(k) for k in results), default=1.0)
    if n < MIN_EXAMPLES or widest > 0.5:
        out["decision"] = "INSUFFICIENT_DATA"
        out["reasons"].append(f"n={n} (<{MIN_EXAMPLES}) or AUROC CI width {widest:.2f}>0.5.")
        return out

    parts_decodable = sum([res, ctx, sem])
    if not (sb or res or ctx or sem or hid):
        decision = "NO_SIGNAL"
    elif full_beats_hidden:
        decision = "CSR_STRONG_SIGNAL"
        out["reasons"].append("hidden+state_bhava+CSR beats hidden_only (significant).")
    elif csr_beats_parts:
        decision = "CSR_COMPLEMENTARY"
        out["reasons"].append("csr_static beats its best individual part (significant).")
    elif parts_decodable >= 2:
        decision = "CSR_REDUNDANT"
        out["reasons"].append("CSR parts decodable but the combination improves on none.")
    elif res and not ctx and not sem:
        decision = "RESONANCE_ONLY_SIGNAL"
    elif ctx and not res and not sem:
        decision = "CONTEXT_ONLY_SIGNAL"
    elif sem and not res and not ctx:
        decision = "SEMANTIC_ONLY_SIGNAL"
    elif sb and not (res or ctx or sem):
        decision = "STATE_BHAVA_ONLY_SIGNAL"
    elif hid:
        decision = "HIDDEN_ONLY_SIGNAL"
        out["reasons"].append("hidden decodes; state_bhava/CSR add nothing over hidden.")
    else:
        decision = "NO_SIGNAL"
    out["decision"] = decision
    return out
