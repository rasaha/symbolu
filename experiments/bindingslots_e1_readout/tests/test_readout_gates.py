#!/usr/bin/env python3
"""Torch-free unit tests for the readout diagnostic: gate/conclusion logic, learned-arm selection,
structural-prior-only path, seed disjointness, and the AST no-oracle proof. Runs in CI without torch."""
from __future__ import annotations

import ast
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import readout_config as C          # noqa: E402
import readout_gates as G           # noqa: E402
import readout_leakage as L         # noqa: E402

ADDED = {"R0": 0, "R1": 4160, "R2": 16576, "R3": 16576}


def _cm(t4, addr=0.95, fa=0.10, fr=0.05):
    base = {"addressing_top1": addr, "correct_latest": t4, "correct_latest_record": t4,
            "correct_entity": addr, "null_rate": fr, "wrong_entity": 0.0,
            "right_entity_wrong_older": 0.0, "e2e": t4, "false_reject": fr,
            "mean_correct_key_rank": 1.0, "n": 150}
    m = {G.SPLIT[k]: dict(base) for k in ("T1", "T2", "T3", "T6", "T7", "T9")}
    m[G.SPLIT["T4"]] = dict(base, correct_latest=t4, correct_latest_record=t4)
    m[G.SPLIT["T8"]] = {"false_accept": fa, "n": 150}
    m[G.SPLIT["T3"]]["false_reject"] = fr
    return m


def _arm_results(t4_by_arm, r0=0.60):
    r0_seed = [r0] * 5
    res = {}
    for arm, t4 in t4_by_arm.items():
        res[arm] = G.eval_arm(arm, [_cm(t4)] * 5, r0_seed)
    return res


def test_seed_disjointness():
    assert not (C.all_prior_seeds() & C.proposed_seeds())
    assert C.proposed_seeds() == {75, 750, 751, 752, 7150, 7151, 7152, 7153, 7154}


def test_present_requires_learned_arm_and_bars():
    # R1 strong (0.80, +0.20 over R0=0.60) -> SIGNAL_PRESENT, R1 selected
    res = _arm_results({"R0": 0.60, "R1": 0.80, "R2": 0.62, "R3": 0.62})
    out = G.conclude(res, ADDED, integrity_ok=True)
    assert out["conclusion"] == "FROZEN_REPRESENTATION_READOUT_SIGNAL_PRESENT"
    assert out["selected_arm"] == "R1" and not out["structural_prior_only"]


def test_present_selection_fewer_params_when_tied():
    # both R1 and R2 reach present; R1 has fewer params -> R1 selected
    res = _arm_results({"R0": 0.60, "R1": 0.80, "R2": 0.82, "R3": 0.60})
    out = G.conclude(res, ADDED, integrity_ok=True)
    assert out["conclusion"] == "FROZEN_REPRESENTATION_READOUT_SIGNAL_PRESENT"
    assert out["selected_arm"] == "R1"


def test_partial_learned():
    # R2 at 0.70 (+0.10 impr, >=0.68, <0.75) -> PARTIAL learned, R2 selected
    res = _arm_results({"R0": 0.60, "R1": 0.60, "R2": 0.70, "R3": 0.60})
    out = G.conclude(res, ADDED, integrity_ok=True)
    assert out["conclusion"] == "FROZEN_REPRESENTATION_READOUT_SIGNAL_PARTIAL"
    assert out["selected_arm"] == "R2" and not out["structural_prior_only"]


def test_structural_prior_only():
    # learned flat; R3 reaches PRESENT bars (0.78, +0.18) -> PARTIAL + structural_prior_only, no selection
    res = _arm_results({"R0": 0.60, "R1": 0.61, "R2": 0.62, "R3": 0.78})
    out = G.conclude(res, ADDED, integrity_ok=True)
    assert out["conclusion"] == "FROZEN_REPRESENTATION_READOUT_SIGNAL_PARTIAL"
    assert out["structural_prior_only"] is True and out["selected_arm"] is None


def test_r3_below_present_floor_is_not_found():
    # R3 improves a lot (+0.11) but absolute 0.71 < 0.75 present floor, learned flat -> NOT_FOUND
    res = _arm_results({"R0": 0.60, "R1": 0.59, "R2": 0.61, "R3": 0.71})
    out = G.conclude(res, ADDED, integrity_ok=True)
    assert out["conclusion"] == "FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND"
    assert out["selected_arm"] is None and not out["structural_prior_only"]


def test_r3_cannot_be_present():
    # even if R3 hits both present bars, it can never be SIGNAL_PRESENT (only structural-only PARTIAL)
    res = _arm_results({"R0": 0.60, "R1": 0.60, "R2": 0.60, "R3": 0.85})
    out = G.conclude(res, ADDED, integrity_ok=True)
    assert out["conclusion"] != "FROZEN_REPRESENTATION_READOUT_SIGNAL_PRESENT"
    assert out["structural_prior_only"] is True


def test_integrity_and_resource_gates():
    res = _arm_results({"R0": 0.60, "R1": 0.80, "R2": 0.62, "R3": 0.62})
    assert G.conclude(res, ADDED, integrity_ok=False)["conclusion"] == "FROZEN_REPRESENTATION_READOUT_PROTOCOL_VIOLATED"
    assert G.conclude(res, ADDED, integrity_ok=True, resource_ok=False)["conclusion"] == "FROZEN_REPRESENTATION_READOUT_RESOURCE_BLOCKED"


def test_inherited_regression_blocks_pass():
    # strong T4 but a broken inherited split -> the seed does not pass -> no present
    bad = [_cm(0.80, addr=0.50)] * 5
    res = {"R0": G.eval_arm("R0", [_cm(0.60)] * 5, [0.60] * 5),
           "R1": G.eval_arm("R1", bad, [0.60] * 5),
           "R2": G.eval_arm("R2", [_cm(0.60)] * 5, [0.60] * 5),
           "R3": G.eval_arm("R3", [_cm(0.60)] * 5, [0.60] * 5)}
    out = G.conclude(res, ADDED, integrity_ok=True)
    assert out["conclusion"] == "FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND"


def test_preserve_and_never_emit():
    res = _arm_results({"R0": 0.60, "R1": 0.80, "R2": 0.62, "R3": 0.62})
    out = G.conclude(res, ADDED, integrity_ok=True)
    assert out["preserved"] == C.PRESERVE
    for t in C.NEVER_EMIT:
        assert t not in out["conclusion"]


def test_leakage_no_oracle_on_real_source():
    r = L.check_scoring_no_oracle()
    assert r["pass"], r["problems"]
    assert r["scores_signature_ok"]
    assert L.check_no_table_import()["pass"]


def test_leakage_ast_detects_injected_oracle():
    bad = "class _AttnHead:\n    def forward(self, tok, q, pad):\n        return target_index\n"
    fn = ast.parse(bad).body[0].body[0]
    assert "target_index" in L._names(fn)


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    p = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); p += 1
        except Exception:
            print("FAIL", fn.__name__); traceback.print_exc()
    print(f"{p}/{len(fns)} passed")
    sys.exit(0 if p == len(fns) else 1)
