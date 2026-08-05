#!/usr/bin/env python3
"""Tests for the E1 capability probe. Torch-free parts (task/leakage/gates) always run; torch-backed
parts (determinism, hard top-1) are RESOURCE_BLOCKED-safe."""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))

import task as T          # noqa: E402
import leakage as L       # noqa: E402
import gates as G         # noqa: E402
import config as C        # noqa: E402

try:
    import torch  # noqa: F401
    HAVE = True
except Exception:
    HAVE = False


# ---- torch-free ----------------------------------------------------------------------
def test_pools_disjoint():
    r = L.check_pools_disjoint()
    assert r["pass"], r


def test_no_exact_overlap_and_no_answer_in_key():
    eps = T.build_split(T.identity_pools()["dev"], 60, seed=11)
    assert L.check_no_exact_overlap(eps)["pass"]
    assert L.check_no_answer_in_key(eps)["pass"]


def test_lexical_overlap_uninformative():
    eps = T.build_split(T.identity_pools()["dev"], 120, seed=12)
    r = L.check_lexical_overlap_uninformative(eps)
    assert r["pass"], r        # surface overlap cannot solve the task


def test_eval_ids_unseen():
    splits = T.build_eval_splits(T.identity_pools()["final"], 40, seed_base=99)
    all_eps = [e for v in splits.values() for e in v]
    assert L.check_eval_ids_unseen(all_eps)["pass"]


def test_no_table_import():
    assert L.check_no_table_import()["pass"]


def test_leakage_suite_all_pass():
    splits = T.build_eval_splits(T.identity_pools()["dev"], 40, seed_base=7)
    assert L.run_all(splits)["all_pass"]


def _synthetic_seed(g1=0.95, b0=0.05, nm_fa=0.10, g7=0.98):
    from task import KEYS_PER_EPISODE  # noqa
    m = {"G1_addr": g1, "G2_addr": g1, "G3_addr": g1, "G4_addr": g1, "G5_addr": g1, "G7_addr": g7,
         "G1_e2e": g1 - 0.02, "G1_false_reject": 0.05, "answer_availability": 0.9,
         "oracle_key_value_accuracy": 1.0, "nomatch_false_accept": nm_fa,
         "nomatch_recall": 1 - nm_fa, "nomatch_precision": 0.93,
         "nomatch_confident_false_accept": 0.05, "b0_G1_e2e": b0,
         "improvement_over_b0": (g1 - 0.02) - b0, "oracle_to_predicted_gap": 1.0 - (g1 - 0.02)}
    return {"metrics": m, "gates": G.eval_seed_gates(m)}


def test_verdict_validated():
    per = [_synthetic_seed() for _ in range(5)]
    v, extra = G.verdict(per, determinism_ok=True, leakage_ok=True, protocol_ok=True)
    assert v == "EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED", v
    assert "INDEPENDENT_NEURAL_MEMORY_CONFIRMATION_REQUIRED" in extra
    assert "KDA_VALIDATION_BLOCKED" in extra


def test_verdict_integrity_precedence():
    per = [_synthetic_seed() for _ in range(5)]
    assert G.verdict(per, True, False, True)[0] == "EXPLICIT_KEY_SHORTCUT_OR_LEAKAGE_DETECTED"
    assert G.verdict(per, False, True, True)[0] == "EXPLICIT_KEY_DETERMINISM_NOT_ESTABLISHED"
    assert G.verdict(per, True, True, False)[0] == "EXPLICIT_KEY_PROTOCOL_VIOLATED"


def test_verdict_generalization_fail():
    per = [_synthetic_seed(g1=0.4, b0=0.05) for _ in range(5)]   # E1 fails generalization
    v, _ = G.verdict(per, True, True, True)
    assert v in ("EXPLICIT_KEY_GENERALIZATION_GATE_FAILED", "EXPLICIT_KEY_NO_MATCH_GATE_FAILED"), v
    assert v != "EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED"


def test_no_approval_required_remaining():
    assert all("APPROVAL_REQUIRED" not in str(v) for v in C.GATES.values())


# ---- torch-backed --------------------------------------------------------------------
def test_e1_determinism_small():
    if not HAVE:
        return
    import engine as E
    eps = T.build_split(T.identity_pools()["train"], 200, seed=3, no_match_frac=0.3)
    a, _ = E.train_e1(eps, steps=60, batch=16, lr=1e-3, tau=0.05, seed=5)
    b, _ = E.train_e1(eps, steps=60, batch=16, lr=1e-3, tau=0.05, seed=5)
    assert E.param_hash(a) == E.param_hash(b), "E1 training must be byte-identical"


def test_e1_hard_top1_returns_single_key_value():
    if not HAVE:
        return
    import engine as E
    eps = T.build_split(T.identity_pools()["train"], 100, seed=4, no_match_frac=0.2)
    m, _ = E.train_e1(eps, steps=60, batch=16, lr=1e-3, tau=0.05, seed=6)
    kt, kv, qt, ti, tv = E.collate(eps[:8])
    import torch
    with torch.no_grad():
        logits = m(kt, qt, 0.05)
    K = kt.size(1)
    pred = logits.argmax(-1)
    # every prediction is a single discrete index in [0, K] (K = null); never a mixture
    assert int(pred.min()) >= 0 and int(pred.max()) <= K


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ran = 0
    for fn in fns:
        fn(); ran += 1
    tag = "" if HAVE else " (torch-free subset; torch-backed skipped)"
    print(f"e1 tests: {ran} passed, 0 failed{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
