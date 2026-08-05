#!/usr/bin/env python3
"""Tests for the temporal transfer experiment. Torch-free (task/leakage/gates/verdict) always run;
torch-backed (determinism) is RESOURCE_BLOCKED-safe."""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))

import temporal_task as T        # noqa: E402
import temporal_leakage as LK    # noqa: E402
import temporal_gates as G       # noqa: E402
import temporal_config as C      # noqa: E402

try:
    import torch  # noqa: F401
    HAVE = True
except Exception:
    HAVE = False


def test_seed_disjointness():
    conf = set(C.DEV_SEEDS) | set(C.FINAL_SEEDS) | {C.TRAIN_SEED}
    assert not (conf & C.all_prior_seeds()), conf & C.all_prior_seeds()


def test_no_answer_in_key_no_status_in_query():
    splits = T.build_eval_splits(T.identity_pools(C.POOL_SALT)["dev"], 30, 720)
    all_eps = [e for v in splits.values() for e in v]
    assert LK.check_no_answer_in_key(all_eps)["pass"]
    assert LK.check_no_status_in_query(all_eps)["pass"]


def test_no_exact_overlap_and_lexical_chance():
    splits = T.build_eval_splits(T.identity_pools(C.POOL_SALT)["dev"], 120, 721)
    valid = [e for v in splits.values() for e in v if e["target_index"] >= 0]
    assert LK.check_no_exact_overlap(valid)["pass"]
    assert LK.check_lexical_overlap_uninformative(valid)["pass"]


def test_latest_heuristic_uninformative():
    splits = T.build_eval_splits(T.identity_pools(C.POOL_SALT)["dev"], 150, 720)
    assert LK.check_latest_heuristic_uninformative(splits["T4_latest"])["pass"]


def test_pools_disjoint_eval_unseen_no_table():
    assert LK.check_pools_disjoint()["pass"]
    splits = T.build_eval_splits(T.identity_pools(C.POOL_SALT)["final"], 30, 6140)
    assert LK.check_eval_ids_unseen([e for v in splits.values() for e in v])["pass"]
    assert LK.check_no_table_import()["pass"]


def test_leakage_suite_all_pass():
    splits = T.build_eval_splits(T.identity_pools(C.POOL_SALT)["dev"], 40, 720)
    assert LK.run_all(splits)["all_pass"]


def test_gates_use_given_numbers():
    assert C.GATES["T4_min"] == 0.85 and C.GATES["T1_min"] == 0.80 and C.GATES["improvement_over_b0_min"] == 0.50
    assert C.GATES["T9_min_no_material_regression"] == 0.90


def _seed(t3=0.87, t4=0.87, t1=0.87, t9=0.98, fa=0.15, imp=0.75):
    m = {"T1": t1, "T2": t1, "T3": t3, "T4": t4, "T5_diagnostic": 0.4, "T6": t1, "T7": t1, "T9": t9,
         "primary_structural": (t3 + t4) / 2, "improvement_over_b0": imp, "min_T3T4": min(t3, t4),
         "nomatch_false_accept": fa, "nomatch_false_reject": 0.05, "nomatch_recall": 1 - fa,
         "nomatch_precision": 0.95}
    return {"metrics": m, "gates": G.eval_gates(m)}


def test_verdict_validated():
    per = [_seed() for _ in range(5)]
    v, extra = G.verdict(per, True, True, True)
    assert v == "E1_TEMPORAL_TRANSFER_VALIDATED", v
    assert "E1_STRUCTURAL_TRANSFER_CONFIRMED" in extra and "KDA_VALIDATION_BLOCKED" in extra


def test_verdict_partial_when_t4_short():
    per = [_seed(t4=0.81) for _ in range(5)]     # T4 below 0.85, everything else strong
    v, _ = G.verdict(per, True, True, True)
    assert v == "E1_TEMPORAL_TRANSFER_PARTIAL", v


def test_verdict_nomatch_failed():
    per = [_seed(fa=0.5) for _ in range(5)]
    assert G.verdict(per, True, True, True)[0] == "E1_TEMPORAL_TRANSFER_NO_MATCH_FAILED"


def test_verdict_protocol_violated():
    per = [_seed() for _ in range(5)]
    assert G.verdict(per, False, True, True)[0] == "E1_TEMPORAL_TRANSFER_PROTOCOL_VIOLATED"


def test_determinism_small():
    if not HAVE:
        return
    import temporal_train as TR
    eps = T.build_train_episodes(T.identity_pools(C.POOL_SALT)["train"], 200, 73, 0.30)
    a = TR.train_e1(eps, 720); b = TR.train_e1(eps, 720)
    assert TR.param_hash(a) == TR.param_hash(b)


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    tag = "" if HAVE else " (torch-free subset)"
    print(f"temporal tests: {len(fns)} passed, 0 failed{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
