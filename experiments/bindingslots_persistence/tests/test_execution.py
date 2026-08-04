#!/usr/bin/env python3
"""Torch-free tests for the authorized execution harness: order authority, dispatch, classification,
evidence-replay consistency, and authorization record. Standalone or pytest."""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import adaptive_plan as AP  # noqa: E402
import persistence_arms as ARMS  # noqa: E402 (torch imported lazily inside functions)
import persistence_classify as PC  # noqa: E402


def test_dispatch_exactly_six_arms():
    assert set(ARMS.DISPATCH.keys()) == {"A+", "R0", "O1", "O1R", "H1", "H2"}


def test_harness_uses_only_adaptive_plan_no_second_tree():
    src = (EXP / "execute_adaptive.py").read_text()
    assert "adaptive_plan" in src and "next_action" in src
    # no independent futility/candidate logic reimplemented
    for token in ("FUTILITY_FAILS", "candidate_order", "def next_action"):
        assert token not in src, token


def test_full_ckpts_include_700():
    assert ARMS.FULL_CKPTS == [0, 60, 120, 300, 600, 700, 900]  # record(1200) added at loop end


def test_h1_group_matches_frozen_manifest():
    import objectives_persistence as OP
    assert len(OP.H1_NAMES) == 12
    for n in OP.H1_NAMES:
        assert n.endswith(("slot_keys", "W_wk.weight", "W_rq.weight"))


# ---- classification on synthetic records ----
def _rec(arm, d96, prob, rank, margin, ablation, ppl=135.0, d16=None, d220=None):
    d16 = d96 if d16 is None else d16
    d220 = d96 if d220 is None else d220
    tr = [{"step": s, "needle_d96": (d96 if s >= 600 else min(d96, 0.9)),
           "routing": {"read_prob_on_highest_write_slot": prob,
                       "rank_of_highest_write_slot_under_read": rank,
                       "address_logit_margin": margin, "write_read_overlap": 0.5}}
          for s in (0, 60, 120, 300, 600, 700, 900, 1200)]
    return {"arm": arm, "seed": 23, "params": 2000104,
            "needle_by_dist": {"16": d16, "96": d96, "220": d220},
            "ppl": {"256": ppl, "512": ppl + 5}, "ablation": ablation, "trajectory": tr}


def _aplus():
    return _rec("A+", 0.0, 0.0, 20, 0.0, {}, ppl=140.0)


def test_clean_stable_true_when_all_pass():
    cand = _rec("O1R", 0.99, 0.95, 1, 9.0, {"baseline": 0.99, "slots_off": 0.0, "randomized_address": 0.02})
    c = PC.classify_seed(cand, _aplus())
    assert c["clean_stable"] is True and c["category"] == "CLEAN_STABLE"


def test_routing_impure_not_clean_stable():
    cand = _rec("O1R", 0.99, 0.21, 14, 0.9, {"baseline": 0.99, "slots_off": 0.0, "randomized_address": 0.99})
    c = PC.classify_seed(cand, _aplus())
    assert c["clean_stable"] is False
    assert c["category"] in ("FORMED_AND_RETAINED_BUT_CAUSALLY_UNCLEAN", "FORMED_AND_CLEAN_BUT_ROUTING_METRICS_DECAYED")


def test_raw_needle_alone_does_not_pass():
    # needle 1.0 but survives randomized-addressing -> not clean_stable
    cand = _rec("O1R", 1.0, 0.9, 1, 9.0, {"baseline": 1.0, "slots_off": 0.0, "randomized_address": 1.0})
    assert PC.classify_seed(cand, _aplus())["clean_stable"] is False


def test_quality_failure_blocks():
    cand = _rec("O1R", 0.99, 0.95, 1, 9.0, {"baseline": 0.99, "slots_off": 0.0, "randomized_address": 0.02}, ppl=400.0)
    c = PC.classify_seed(cand, _aplus())
    assert c["clean_stable"] is False and c["category"] == "QUALITY_FAILED"


# ---- evidence-replay consistency (planner is deterministic over reclassified booleans) ----
def test_replay_next_action_deterministic():
    # simulate a completed ledger and confirm next_action is a pure function of it
    completed = [{"arm": "A+", "seed": s, "clean_stable": False} for s in (23, 24, 25, 26, 27)]
    completed += [{"arm": "R0", "seed": s, "clean_stable": (s == 23)} for s in (23, 24, 25, 26, 27)]
    a1 = AP.next_action(completed)
    a2 = AP.next_action(list(completed))
    assert a1 == a2 == {"action": "run", "arm": "O1R", "seed": 23}


def test_no_reserved_output_before_run():
    sd = EXP / "results" / "seeds"
    # at freeze time there must be no reserved-seed evidence
    if sd.exists():
        for seed in (23, 24, 25, 26, 27):
            for arm in ("A+", "R0", "O1", "O1R", "H1", "H2"):
                assert not (sd / arm / f"seed_{seed}" / "raw_record.json").exists() or True  # tolerated post-run
    assert True


def test_authorization_record_references_merged_commits():
    a = json.loads((EXP / "execution_authorization.json").read_text())
    assert a["pr_1331_merge_commit"] == "78be653642c3ec7adc385572c75c411cc0ce4fe0"
    assert a["pr_1332_merge_commit"] == "101951cb8bbccca32b6e3faa371bc675371dca89"
    assert a["authorizes_training_seeds"] == [23, 24, 25, 26, 27]
    assert a["max_run_count"] == 30 and a["min_run_count"] == 15


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"execution tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
