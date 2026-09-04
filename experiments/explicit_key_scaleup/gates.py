"""E1-S gate evaluation and mechanical verdict (torch-free math over computed metrics).

Reuses experiments/bindingslots_e1/gates.py::nomatch_precision_recall and eval_seed_gates (with this
package's GATES) unchanged; adds G8 and the density-ladder verdict of draft §7.
"""
from __future__ import annotations

from . import config as C
from .e1_import import E1_DIR

ALWAYS = list(C.PRESERVED_VERDICTS)


def _e1_gates():
    import importlib, sys
    if str(E1_DIR) not in sys.path:
        sys.path.insert(0, str(E1_DIR))
    return importlib.import_module("gates")


def seed_density_metrics(e1_splits: dict, b0_g1_e2e: float) -> dict:
    """Collapse one (seed, density) eval into gate scalars; E1's mapping + G8."""
    g = e1_splits
    fa = g["G6_no_match"]["false_accept_rate"]
    fr = g["G1_unseen_identity"]["false_reject_rate"]
    prec, rec = _e1_gates().nomatch_precision_recall(fa, fr)
    g1 = g["G1_unseen_identity"]
    return {
        "G1_addr": g1["addressing_top1"], "G2_addr": g["G2_paraphrase"]["addressing_top1"],
        "G3_addr": g["G3_hard_names"]["addressing_top1"], "G4_addr": g["G4_same_entity_diff_attr"]["addressing_top1"],
        "G5_addr": g["G5_recombined"]["addressing_top1"], "G7_addr": g["G7_stable"]["addressing_top1"],
        "G8_addr": g["G8_unseen_composition"]["addressing_top1"],
        "G1_e2e": g1["e2e_retrieval_accuracy"], "G1_false_reject": fr,
        "answer_availability": g1["answer_availability"],
        "oracle_key_value_accuracy": g1["oracle_key_value_accuracy"],
        "nomatch_false_accept": fa, "nomatch_recall": rec, "nomatch_precision": prec,
        "nomatch_confident_false_accept": g["G6_no_match"]["nomatch_confident_falseaccept_rate"],
        "b0_G1_e2e": b0_g1_e2e, "improvement_over_b0": g1["e2e_retrieval_accuracy"] - b0_g1_e2e,
        "oracle_to_predicted_gap": g1["oracle_key_value_accuracy"] - g1["e2e_retrieval_accuracy"],
    }


def eval_gates(m: dict, G=C.GATES) -> dict:
    """E1's eval_seed_gates (unchanged) + the G8 generalization gate; all_primary_pass requires both."""
    r = _e1_gates().eval_seed_gates(m, G=G)
    r["generalization"]["G8_unseen_composition"] = m["G8_addr"] >= G["G8_unseen_composition_min_addr"]
    r["groups"]["generalization"] = all(r["generalization"].values())
    r["all_primary_pass"] = all(r["groups"].values())
    return r


def verdict(per_seed: list, *, leakage_ok: bool, determinism_ok: bool, shortcut_detected: bool,
            anchor_ok: bool, required: int = C.FINAL_SEEDS_REQUIRED_TO_PASS) -> tuple:
    """per_seed: [{"densities": {K: {"metrics":..., "gates":...}}}]. Precedence (draft §7, E1 order):
    leakage/shortcut -> determinism -> protocol (anchor) -> validated -> nomatch-only failure at the
    primary density -> density-limited -> not validated."""
    if not leakage_ok or shortcut_detected:
        return "SHORTCUT_OR_LEAKAGE_DETECTED", list(ALWAYS)
    if not determinism_ok:
        return "EXPLICIT_KEY_DETERMINISM_NOT_ESTABLISHED", list(ALWAYS)
    if not anchor_ok:
        return "EXPLICIT_KEY_PROTOCOL_VIOLATED", list(ALWAYS)
    worst_floor = C.GATES["worst_seed_min_G1_addr"]

    def passes(K):
        rows = [s["densities"][K] for s in per_seed if K in s["densities"]]
        n_pass = sum(1 for r in rows if r["gates"]["all_primary_pass"])
        worst = min((r["metrics"]["G1_addr"] for r in rows), default=0.0)
        return n_pass >= required and worst >= worst_floor and len(rows) > 0

    if passes(C.PRIMARY_DENSITY):
        return "EXPLICIT_KEY_SCALEUP_VALIDATED", list(ALWAYS)
    # H2 first: addressing transfers at the primary density but no-match does not. This must precede the
    # density-limited check, because the K=32 anchor always passes when we get here (otherwise PROTOCOL_VIOLATED),
    # so "a lower density passes" is always true and would mask the more informative no-match verdict.
    rows = [s["densities"][C.PRIMARY_DENSITY] for s in per_seed if C.PRIMARY_DENSITY in s["densities"]]
    others_ok = sum(1 for r in rows if r["gates"]["groups"]["generalization"] and r["gates"]["groups"]["e2e"]
                    and r["gates"]["groups"]["stable"])
    nomatch_fail = sum(1 for r in rows if not r["gates"]["groups"]["nomatch"])
    if rows and others_ok >= required and nomatch_fail >= 1:
        return "EXPLICIT_KEY_SCALEUP_NOMATCH_FAILED", list(ALWAYS)
    lower = [K for K in C.DENSITIES if K < C.PRIMARY_DENSITY and passes(K)]
    if lower:
        return "EXPLICIT_KEY_SCALEUP_DENSITY_LIMITED", list(ALWAYS) + [f"DENSITY_CEILING_{max(lower)}"]
    return "EXPLICIT_KEY_SCALEUP_NOT_VALIDATED", list(ALWAYS)


def assert_verdict_admissible(primary: str, preserved: list) -> None:
    assert primary in C.VERDICTS, primary
    assert primary not in C.FORBIDDEN_VERDICTS
    assert all(p not in C.FORBIDDEN_VERDICTS for p in preserved)
    assert all(a in preserved for a in ALWAYS)
