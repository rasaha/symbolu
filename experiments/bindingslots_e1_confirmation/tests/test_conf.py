#!/usr/bin/env python3
"""Tests for the E1 independent confirmation. Torch-free (task/leakage/gates/verdict) always run;
torch-backed (determinism) is RESOURCE_BLOCKED-safe."""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))

import conf_task as T        # noqa: E402
import conf_leakage as LK    # noqa: E402
import conf_gates as G       # noqa: E402
import conf_config as C      # noqa: E402

try:
    import torch  # noqa: F401
    HAVE = True
except Exception:
    HAVE = False


def test_seed_disjointness():
    conf = set(C.DEV_SEEDS) | set(C.FINAL_SEEDS) | {C.TRAIN_SEED_FOR_EPISODES}
    assert not (conf & C.all_prior_seeds()), conf & C.all_prior_seeds()


def test_pools_disjoint_and_query_no_overlap():
    assert LK.check_pools_disjoint()["pass"]
    eps = T.build_split(T.identity_pools(C.POOL_SALT)["dev"], 60, seed=700)
    assert LK.check_no_exact_overlap(eps)["pass"]
    assert LK.check_no_answer_in_key(eps)["pass"]


def test_lexical_overlap_uninformative():
    eps = T.build_split(T.identity_pools(C.POOL_SALT)["dev"], 150, seed=701)
    assert LK.check_lexical_overlap_uninformative(eps)["pass"]


def test_eval_ids_unseen_final():
    splits = T.build_eval_splits(T.identity_pools(C.POOL_SALT)["final"], 40, seed_base=5140)
    all_eps = [e for v in splits.values() for e in v]
    assert LK.check_eval_ids_unseen(all_eps)["pass"]


def test_no_table_import_and_no_opaque_id():
    assert LK.check_no_table_import()["pass"]
    assert LK.check_no_opaque_identifier()["pass"]


def test_leakage_suite_all_pass():
    splits = T.build_eval_splits(T.identity_pools(C.POOL_SALT)["dev"], 40, seed_base=700)
    assert LK.run_all(splits)["all_pass"]


def test_gates_use_frozen_1351_numbers():
    import sys as _s, pathlib as _p
    _s.path.insert(0, str(_p.Path(__file__).resolve().parents[2] / "bindingslots_e1"))
    import config as FROZEN
    assert C.GATES == dict(FROZEN.GATES), "confirmation must use the frozen PR #1351 gate numbers"


def _seed(g1=0.98, b0=0.03, fa=0.15, g7=0.99):
    m = {"G1_addr": g1, "G2_addr": g1, "G3_addr": g1, "G4_addr": g1, "G5_addr": g1, "G7_addr": g7,
         "G1_e2e": g1 - 0.01, "G1_false_reject": 0.03, "answer_availability": 0.95,
         "oracle_key_value_accuracy": 1.0, "nomatch_false_accept": fa,
         "nomatch_recall": 1 - fa, "nomatch_precision": 0.95, "nomatch_confident_false_accept": 0.05,
         "b0_G1_e2e": b0, "improvement_over_b0": (g1 - 0.01) - b0, "oracle_to_predicted_gap": 1.0 - (g1 - 0.01)}
    return {"metrics": m, "gates": G.eval_gates(m)}


def test_verdict_confirmed():
    per = [_seed() for _ in range(5)]
    v, extra = G.verdict(per, True, True, True)
    assert v == "E1_INDEPENDENTLY_CONFIRMED", v
    assert "E1_FOLLOW_ON_RESEARCH_ELIGIBLE" in extra
    assert "KDA_VALIDATION_BLOCKED" in extra


def test_verdict_protocol_and_fail():
    per = [_seed() for _ in range(5)]
    assert G.verdict(per, False, True, True)[0] == "E1_CONFIRMATION_PROTOCOL_VIOLATED"
    assert G.verdict(per, True, False, True)[0] == "E1_CONFIRMATION_PROTOCOL_VIOLATED"
    bad = [_seed(g1=0.4) for _ in range(5)]
    assert G.verdict(bad, True, True, True)[0] in ("E1_CONFIRMATION_FAILED", "E1_CONFIRMATION_PARTIAL")


def test_determinism_small():
    if not HAVE:
        return
    import conf_train as TR
    eps = T.build_split(T.identity_pools(C.POOL_SALT)["train"], 200, seed=71, no_match_frac=0.3)
    a, _ = TR.train_e1(eps, 700)   # note: uses frozen STEPS; small train set keeps it quick
    b, _ = TR.train_e1(eps, 700)
    assert TR.param_hash(a) == TR.param_hash(b)


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    tag = "" if HAVE else " (torch-free subset)"
    print(f"conf tests: {len(fns)} passed, 0 failed{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
