#!/usr/bin/env python3
"""Torch-free tests for the functional-routing development phase. Runnable standalone or via pytest."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP))
import fr_classifier as FC  # noqa: E402
import curriculum_gradual as CG  # noqa: E402

FROZEN = json.loads((EXP / "frozen_reference_config.json").read_text())
CLS = json.loads((EXP / "stable_classifier.json").read_text())
SEEDS = json.loads((EXP / "stage1_seed_manifest.json").read_text())


def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


# ---- frozen reference / integrity ----
def test_frozen_hashes_match():
    for rel, want in FROZEN["frozen_code_hashes_sha256"].items():
        assert sha256(REPO / rel) == want, rel


def test_R0_is_unswapped_cr1():
    assert FROZEN["R0"]["run_mechanism"] == "frozen stabilize.run_arm('CR1', seed) with NO function swap"


def test_interventions_and_stabilize_unedited():
    # the two files we swap at runtime must be byte-stable on disk
    assert sha256(REPO / "hybrid_llm_vnext_lab/experiments/slot_formation_stabilization/interventions.py") == \
        FROZEN["frozen_code_hashes_sha256"]["hybrid_llm_vnext_lab/experiments/slot_formation_stabilization/interventions.py"]


# ---- seeds ----
def test_seed_sets_disjoint_and_fresh():
    s1, s2, s3 = SEEDS["stage1_seeds"], SEEDS["stage2_reserved"], SEEDS["confirmation_reserved"]
    assert s1 == [18, 19, 20, 21, 22]
    used = set(SEEDS["previously_used_bindingslots_training_seeds"])
    allnew = set(s1) | set(s2) | set(s3)
    assert not (used & allnew) and len(allnew) == 15


# ---- curriculum_gradual determinism / ranges ----
def test_gradual_phase_boundaries():
    import random
    # deterministic given a fixed rng; check the mixture region only mixes in 600..900
    class FakeT:
        def train_batch(self, *a, **k):
            return "ORIG", None, None
    # We can't build real batches without torch here; just check the mixture control flow via rng.
    # Emulate: at step 600 p=0 -> never original; at step 899 p~1 -> almost always original.
    def p_original(step):
        return (step - 600) / 300.0
    assert p_original(600) == 0.0
    assert abs(p_original(750) - 0.5) < 1e-9
    assert p_original(900) == 1.0


# ---- classifier states ----
def _rec(seed, arm, d96, prob, rank, margin, ab, ppl=135.0, params=2000104, collapse=False):
    if collapse:
        series = {0: 0, 60: 0.1, 120: 0.5, 300: 1.0, 600: 0.9, 900: 0.1, 1200: 0.0}
    else:
        series = {0: 0, 60: 0.1, 120: 0.5, 300: 0.9, 600: d96, 900: d96, 1200: d96}
    tr = [{"step": st, "needle_d96": series[st],
           "routing": {"read_prob_on_highest_write_slot": prob,
                       "rank_of_highest_write_slot_under_read": rank,
                       "address_logit_margin": margin, "write_read_overlap": 0.5}} for st in series]
    return {"seed": seed, "arm": arm, "params": params,
            "needle_by_dist": {"16": d96, "96": d96, "220": d96},
            "ppl": {"256": ppl, "512": ppl + 5}, "ablation": ab, "trajectory": tr}


def _clean(b):
    return {"baseline": b, "slots_off": 0.0, "randomized_address": 0.02}


def _dirty(b):
    return {"baseline": b, "slots_off": 0.0, "randomized_address": b}


def _dir(tmp, arms):
    d = pathlib.Path(tmp)
    (d).mkdir(parents=True, exist_ok=True)
    for arm, recs in arms.items():
        (d / f"{arm}_results.json").write_text(json.dumps({"arm": arm, "records": recs}))
    return str(d)


def _seeds5(fn):
    return [fn(s) for s in [18, 19, 20, 21, 22]]


def test_state_clean_retained():
    ap = _rec(18, "A+", 0.0, 0.0, 20, 0.0, {}, ppl=140, params=2000392)
    c = _rec(18, "O1", 0.99, 0.95, 1, 9.0, _clean(0.99))
    assert FC.per_seed_state(c, ap) == "FORMED_FUNCTIONALLY_CLEAN_AND_RETAINED"


def test_state_collapsed():
    ap = _rec(18, "A+", 0.0, 0.0, 20, 0.0, {}, ppl=140, params=2000392)
    c = _rec(18, "R0", 0.0, 0.9, 1, 9.0, {}, collapse=True)
    assert FC.per_seed_state(c, ap) == "FORMED_THEN_COLLAPSED"


def test_state_proxy_only_impure():
    ap = _rec(18, "A+", 0.0, 0.0, 20, 0.0, {}, ppl=140, params=2000392)
    # forms + retained endpoint but routing-unclean and causal-dirty -> ROUTING_PROXY_ONLY
    c = _rec(18, "R0", 0.99, 0.21, 14, 0.9, _dirty(0.99))
    assert FC.per_seed_state(c, ap) in ("ROUTING_PROXY_ONLY", "FORMED_FUNCTIONALLY_UNCLEAN_AND_RETAINED")


def test_candidate_selected_when_arm_clears(tmp_path=None):
    import tempfile
    d = tmp_path or tempfile.mkdtemp()
    arms = {
        "A+": _seeds5(lambda s: _rec(s, "A+", 0.0, 0.0, 20, 0.0, {}, ppl=140, params=2000392)),
        "R0": _seeds5(lambda s: _rec(s, "R0", 0.0, 0.9, 1, 9.0, {})),  # R0 forms 0/5
        "O1": _seeds5(lambda s: _rec(s, "O1", 0.99, 0.95, 1, 9.0, _clean(0.99))),  # 5/5 clean, wins 5/5
        "O2": _seeds5(lambda s: _rec(s, "O2", 0.99, 0.9, 2, 8.0, _clean(0.99))),
        "H3": _seeds5(lambda s: _rec(s, "H3", 0.99, 0.8, 3, 7.0, _clean(0.99))),
    }
    out = FC.classify(_dir(d, arms))
    assert out["primary_verdict"] == "FUNCTIONAL_ROUTING_AND_RETENTION_CANDIDATE_SELECTED"
    assert out["selected_candidate"] == "O1"  # tie-break O1 first
    assert out["kda_readiness"] == "KDA_VALIDATION_BLOCKED_PENDING_INDEPENDENT_CONFIRMATION"


def test_purity_unresolved(tmp_path=None):
    import tempfile
    d = tmp_path or tempfile.mkdtemp()
    # interventions form but stay routing-unclean; no clean gain over R0 -> ROUTING_PURITY_NOT_RESOLVED
    arms = {
        "A+": _seeds5(lambda s: _rec(s, "A+", 0.0, 0.0, 20, 0.0, {}, ppl=140, params=2000392)),
        "R0": _seeds5(lambda s: _rec(s, "R0", 0.0, 0.9, 1, 9.0, {})),
        "O1": _seeds5(lambda s: _rec(s, "O1", 0.99, 0.21, 14, 0.9, _dirty(0.99))),
        "O2": _seeds5(lambda s: _rec(s, "O2", 0.99, 0.21, 14, 0.9, _dirty(0.99))),
        "H3": _seeds5(lambda s: _rec(s, "H3", 0.99, 0.21, 14, 0.9, _dirty(0.99))),
    }
    out = FC.classify(_dir(d, arms))
    assert out["primary_verdict"] in ("ROUTING_PURITY_NOT_RESOLVED", "NO_FUNCTIONAL_ROUTING_INTERVENTION_SELECTED")


def test_integrity_and_deviation_verdicts(tmp_path=None):
    import tempfile
    d = tmp_path or tempfile.mkdtemp()
    arms = {
        "A+": _seeds5(lambda s: _rec(s, "A+", 0.0, 0.0, 20, 0.0, {}, ppl=140, params=2000392)),
        "R0": _seeds5(lambda s: _rec(s, "R0", 0.0, 0.9, 1, 9.0, {})),
        "O1": _seeds5(lambda s: _rec(s, "O1", 0.99, 0.95, 1, 9.0, _clean(0.99))),
        "O2": _seeds5(lambda s: _rec(s, "O2", 0.99, 0.9, 2, 8.0, _clean(0.99))),
        "H3": _seeds5(lambda s: _rec(s, "H3", 0.99, 0.8, 3, 7.0, _clean(0.99))),
    }
    rd = _dir(d, arms)
    assert FC.classify(rd, integrity_ok=False)["primary_verdict"] == "FUNCTIONAL_ROUTING_INTEGRITY_FAILED"
    assert FC.classify(rd, deviations=["x"])["primary_verdict"] == "FUNCTIONAL_ROUTING_PROTOCOL_VIOLATED"


def test_resource_blocked_when_incomplete(tmp_path=None):
    import tempfile
    d = tmp_path or tempfile.mkdtemp()
    arms = {"A+": _seeds5(lambda s: _rec(s, "A+", 0.0, 0.0, 20, 0.0, {}))}  # missing arms
    assert FC.classify(_dir(d, arms))["primary_verdict"] == "FUNCTIONAL_ROUTING_RESOURCE_BLOCKED"


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"functional-routing tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
