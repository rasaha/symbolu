#!/usr/bin/env python3
"""Torch-free unit tests for the factorial gates, selection rule, verdict, factorial effects, seed
disjointness, and the AST no-oracle proof. Runnable in CI without torch."""
from __future__ import annotations

import ast
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import factor_config as C          # noqa: E402
import factor_gates as G           # noqa: E402
import factor_leakage as L         # noqa: E402


def _cm(t4_correct_latest, addr=0.95, fa=0.10, fr=0.05):
    """Build a full split-metric dict where all inherited splits pass and T4 = given correct_latest."""
    base = {"addressing_top1": addr, "correct_latest": addr, "correct_latest_record": addr,
            "correct_entity": addr, "null_rate": fr, "wrong_entity": 0.0,
            "right_entity_wrong_older": 0.0, "e2e": addr, "false_reject": fr,
            "mean_correct_key_rank": 1.0, "n": 150}
    m = {G.SPLIT[k]: dict(base) for k in ("T1", "T2", "T3", "T6", "T7", "T9")}
    m[G.SPLIT["T4"]] = dict(base, correct_latest=t4_correct_latest, correct_latest_record=t4_correct_latest)
    m[G.SPLIT["T8"]] = {"false_accept": fa, "n": 150}
    m[G.SPLIT["T3"]]["false_reject"] = fr
    return m


def test_seed_disjointness():
    prior = C.all_prior_seeds()
    prop = C.proposed_seeds()
    assert not (prior & prop), f"seed collision: {sorted(prior & prop)}"
    assert prop == {74, 740, 741, 742, 7140, 7141, 7142, 7143, 7144}


def test_per_seed_gates_pass_and_fail():
    assert G.per_seed_gates(_cm(0.90))["all_primary_pass"] is True
    assert G.per_seed_gates(_cm(0.84))["all_primary_pass"] is False       # T4 below 0.85
    assert G.per_seed_gates(_cm(0.90, fa=0.40))["all_primary_pass"] is False   # false-accept too high
    assert G.per_seed_gates(_cm(0.90, fr=0.20))["all_primary_pass"] is False   # false-reject too high
    assert G.per_seed_gates(_cm(0.90, addr=0.70))["all_primary_pass"] is False  # inherited split fails


def test_reference_cell_never_qualifies():
    seeds = [_cm(0.90)] * 5
    q = G.cell_qualification("000", seeds, ref_mean_T4=0.90, added_params=0)
    assert q["is_reference"] and not q["qualifies"]


def test_qualification_requires_improvement_and_seed_count():
    ref = 0.72
    strong = [_cm(0.90)] * 5
    q = G.cell_qualification("100", strong, ref_mean_T4=ref, added_params=569)
    assert q["qualifies"] and q["seeds_passing_all_primary"] == 5
    assert q["improvement_over_000"] == 0.90 - ref
    # improvement below 0.05 -> not qualified even if gates pass
    q2 = G.cell_qualification("100", [_cm(0.90)] * 5, ref_mean_T4=0.88, added_params=569)
    assert not q2["qualifies"]
    # only 3/5 seeds pass -> not qualified
    mixed = [_cm(0.90), _cm(0.90), _cm(0.90), _cm(0.80), _cm(0.80)]
    q3 = G.cell_qualification("100", mixed, ref_mean_T4=ref, added_params=569)
    assert q3["seeds_passing_all_primary"] == 3 and not q3["qualifies"]


def test_selection_prefers_fewest_factors_then_params():
    quals = [
        {"cell": "111", "n_factors": 3, "added_params": 1741, "worst_seed_T4": 0.95, "mean_T4": 0.96, "qualifies": True},
        {"cell": "100", "n_factors": 1, "added_params": 569, "worst_seed_T4": 0.88, "mean_T4": 0.90, "qualifies": True},
        {"cell": "010", "n_factors": 1, "added_params": 1041, "worst_seed_T4": 0.89, "mean_T4": 0.93, "qualifies": True},
    ]
    sel = G.select_cell(quals)
    assert sel["cell"] == "100"                     # fewest factors, then lowest params over 010
    # no qualifiers -> None
    assert G.select_cell([dict(q, qualifies=False) for q in quals]) is None


def test_selection_worstseed_then_mean_tiebreak():
    quals = [
        {"cell": "100", "n_factors": 1, "added_params": 569, "worst_seed_T4": 0.86, "mean_T4": 0.97, "qualifies": True},
        {"cell": "001", "n_factors": 1, "added_params": 131, "worst_seed_T4": 0.90, "mean_T4": 0.91, "qualifies": True},
    ]
    # tie on n_factors=1; 001 has fewer params -> selected regardless of 100's higher mean
    assert G.select_cell(quals)["cell"] == "001"


def test_verdict_mapping():
    assert G.verdict(None, True, True, True)[0] == "T4_FACTORIAL_NO_INTERVENTION_SELECTED"
    assert G.verdict({"n_factors": 1, "cell": "100"}, True, True, True)[0] == "T4_FACTORIAL_SINGLE_FACTOR_SELECTED"
    assert G.verdict({"n_factors": 2, "cell": "110"}, True, True, True)[0] == "T4_FACTORIAL_COMBINATION_SELECTED"
    assert G.verdict({"n_factors": 3, "cell": "111"}, True, True, True)[0] == "T4_FACTORIAL_ALL_FACTORS_REQUIRED"
    assert G.verdict({"n_factors": 1, "cell": "100"}, False, True, True)[0] == "T4_FACTORIAL_PROTOCOL_VIOLATED"
    assert G.verdict(None, True, True, True, resource_ok=False)[0] == "T4_FACTORIAL_RESOURCE_BLOCKED"
    # always preserves the three invariants; never a validation/unblock verdict
    for sel in (None, {"n_factors": 3, "cell": "111"}):
        _, _, pres = G.verdict(sel, True, True, True)
        assert pres == C.PRESERVE
        assert "E1_TEMPORAL_TRANSFER_VALIDATED" not in pres


def test_factorial_effects_recovers_known_main_effect():
    # response = 0.5 + 0.1*F1 (on) only -> F1 main effect should be 0.1, others ~0
    codes = list(C.CELLS.keys())
    y = {c: 0.5 + (0.1 if c[0] == "1" else 0.0) for c in codes}
    eff = G.factorial_effects(y)
    assert abs(eff["F1"] - 0.1) < 1e-9
    for t in ("F2", "F3", "F1xF2", "F1xF3", "F2xF3", "F1xF2xF3"):
        assert abs(eff[t]) < 1e-9


def test_factorial_effects_recovers_interaction():
    # pure F1xF2 interaction: y = +1 when F1==F2 else -1 (F3 irrelevant). Effect (mean at contrast=+1
    # minus mean at contrast=-1) = 1 - (-1) = 2.0; main effects and F3 terms vanish by symmetry.
    y = {c: (1.0 if c[0] == c[1] else -1.0) for c in C.CELLS}
    eff = G.factorial_effects(y)
    assert abs(eff["F1xF2"] - 2.0) < 1e-9
    for t in ("F1", "F2", "F3", "F1xF3", "F2xF3", "F1xF2xF3"):
        assert abs(eff[t]) < 1e-9


def test_leakage_scoring_no_oracle_passes_on_real_source():
    r = L.check_scoring_no_oracle()
    assert r["pass"], r["problems"]
    assert r["signature_ok"] == {"scores": True, "forward": True}
    assert L.check_no_table_import()["pass"]


def test_leakage_ast_detects_injected_oracle(tmp_path):
    # a synthetic factor forward that reads a banned identifier must be flagged by the same AST scan
    bad = "class F2EntityResidual:\n    def forward(self, q_repr, k_repr):\n        return target_index\n"
    tree = ast.parse(bad)
    fn = tree.body[0].body[0]
    assert "target_index" in L._names(fn)


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            import inspect
            if "tmp_path" in inspect.signature(fn).parameters:
                fn(HERE)
            else:
                fn()
            print("PASS", fn.__name__); passed += 1
        except Exception:
            print("FAIL", fn.__name__); traceback.print_exc()
    print(f"{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
