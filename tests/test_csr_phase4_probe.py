"""CPU tests for Phase 4 Stage-A plumbing — probe math (synthetic activations) + collector helpers.

No GPU, no torch, no model. Validates: the linear-probe / AUROC math, group-by-term CV (no term in
both splits), the dimension-matched random-feature control, Bhava-collapse detection, the leakage
check, bootstrap AUROC-delta CIs, decide_phase4 label logic, and the collector's metadata schema +
no-answer-token guarantee. This is Stage-A infrastructure only — NO Phase 4 claim is made.
"""

import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

np = pytest.importorskip("numpy", reason="numpy required")

from csr_match_filter import phase4_probe as PB              # noqa: E402
from csr_match_filter import phase4_collect_states as PC     # noqa: E402


def _groups(n, n_terms, seed=0):
    return np.array([f"t{i % n_terms}" for i in range(n)])


# ---- AUROC + linear probe -----------------------------------------------------------------------

def test_auroc_basic_and_ties():
    assert PB.auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert PB.auroc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0
    assert abs(PB.auroc([0, 1], [0.5, 0.5]) - 0.5) < 1e-9          # tie -> 0.5
    assert PB.auroc([1, 1], [0.3, 0.7]) == 0.5                     # one class -> 0.5


def test_probe_recovers_signal_under_group_cv():
    rng = np.random.default_rng(1)
    n, d = 240, 24
    X = rng.standard_normal((n, d))
    w = np.zeros(d); w[:4] = [3.0, -3.0, 3.0, -3.0]
    y = (X @ w + rng.standard_normal(n) * 0.5 > 0).astype(int)
    groups = _groups(n, 24)                                        # signal is feature-based, not term
    res = PB.evaluate_probe(X, y, groups, seed=0)
    assert res["auroc"] > 0.75


def test_probe_no_signal_is_chance():
    rng = np.random.default_rng(2)
    n, d = 200, 16
    X = rng.standard_normal((n, d))
    y = rng.integers(0, 2, n)
    auc = PB.evaluate_probe(X, y, _groups(n, 20), seed=0)["auroc"]
    assert 0.35 < auc < 0.65                                       # ~ chance


# ---- group-by-term CV -----------------------------------------------------------------------------

def test_group_kfold_has_no_term_leakage():
    groups = _groups(100, 10)
    for tr, te in PB.group_kfold_indices(groups, n_splits=5, seed=3):
        assert len(tr) and len(te)
        assert set(groups[tr].tolist()).isdisjoint(set(groups[te].tolist()))


# ---- collapse detection ---------------------------------------------------------------------------

def test_effective_rank_detects_collapse():
    rng = np.random.default_rng(4)
    n = 150
    collapsed = rng.standard_normal((n, 1)) @ rng.standard_normal((1, 12))   # rank 1
    full = rng.standard_normal((n, 12))
    assert PB.effective_rank(collapsed) < 1.5
    assert PB.effective_rank(full) > 8.0


# ---- dimension-matched control --------------------------------------------------------------------

def test_incremental_value_credits_real_extra_signal():
    rng = np.random.default_rng(5)
    n = 260
    X_hidden = rng.standard_normal((n, 16))                       # no signal in hidden
    X_extra = rng.standard_normal((n, 4))
    y = (X_extra @ np.array([3.0, -3.0, 3.0, -3.0]) + rng.standard_normal(n) * 0.5 > 0).astype(int)
    iv = PB.incremental_value(X_hidden, X_extra, y, _groups(n, 26), seed=0, n_boot=300)
    assert iv["auroc_hidden_extra"] > iv["auroc_hidden"] + 0.10
    assert iv["delta_vs_hidden"]["delta"] > 0 and iv["delta_vs_hidden"]["excludes_zero"]
    assert iv["delta_vs_random"]["delta"] > 0 and iv["delta_vs_random"]["excludes_zero"]


def test_incremental_value_noise_extra_adds_nothing_over_random():
    rng = np.random.default_rng(6)
    n = 260
    X_hidden = rng.standard_normal((n, 16))
    y = (X_hidden @ (np.r_[np.array([3.0, -3.0, 3.0]), np.zeros(13)])
         + rng.standard_normal(n) * 0.5 > 0).astype(int)          # signal is in hidden
    X_extra = rng.standard_normal((n, 4))                         # pure noise
    iv = PB.incremental_value(X_hidden, X_extra, y, _groups(n, 26), seed=0, n_boot=300)
    assert not iv["delta_vs_random"]["excludes_zero"]             # noise doesn't beat random


# ---- leakage check --------------------------------------------------------------------------------

def test_leakage_flag_on_near_perfect_extra():
    rng = np.random.default_rng(7)
    n = 200
    y = rng.integers(0, 2, n)
    leaky = np.c_[y + rng.standard_normal(n) * 0.01, rng.standard_normal(n)]   # col == label
    clean = rng.standard_normal((n, 4))
    assert PB.leakage_check(leaky, y, _groups(n, 20))["leakage_suspected"] is True
    assert PB.leakage_check(clean, y, _groups(n, 20))["leakage_suspected"] is False


def test_leakage_flag_on_supervision_confound():
    rng = np.random.default_rng(8)
    n = 200
    y = rng.integers(0, 2, n)
    out = PB.leakage_check(rng.standard_normal((n, 4)), y, _groups(n, 20), supervision=y)
    assert out["leakage_suspected"] is True                       # supervision == target


# ---- bootstrap CI ---------------------------------------------------------------------------------

def test_bootstrap_delta_ci():
    rng = np.random.default_rng(9)
    n = 200
    y = rng.integers(0, 2, n)
    good = y + rng.standard_normal(n) * 0.3
    bad = rng.standard_normal(n)
    d = PB.bootstrap_auroc_delta(y, good, bad, n_boot=400, seed=0)
    assert d["delta"] > 0 and d["excludes_zero"]
    same = PB.bootstrap_auroc_delta(y, bad, bad, n_boot=400, seed=0)
    assert not same["excludes_zero"]


# ---- decision labels ------------------------------------------------------------------------------

def _excl(delta):
    return {"delta": delta, "ci_low": delta - 0.01, "ci_high": delta + 0.01, "excludes_zero": delta > 0}


def test_decide_phase4_precedence_and_labels():
    d_pos, d_zero = _excl(0.08), {"delta": 0.0, "ci_low": -0.05, "ci_high": 0.05, "excludes_zero": False}
    # leakage dominates everything
    assert PB.decide_phase4(0.9, d_pos, d_pos, 10.0, leakage=True) == "PHASE4_BHAVA_LEAKAGE_SUSPECTED"
    # collapse next
    assert PB.decide_phase4(0.9, d_pos, d_pos, 1.2, leakage=False) == "PHASE4_BHAVA_COLLAPSE"
    # inconclusive
    assert PB.decide_phase4(0.9, d_pos, d_pos, 10.0, leakage=False, inconclusive=True) == \
        "PHASE4_PILOT_INCONCLUSIVE"
    # hidden not predictive
    assert PB.decide_phase4(0.52, d_pos, d_pos, 10.0, leakage=False) == "PHASE4_NOT_PREDICTIVE"
    # adds signal (beats hidden AND random, >= min_delta, CIs exclude 0)
    assert PB.decide_phase4(0.70, d_pos, d_pos, 10.0, leakage=False) == "PHASE4_BHAVA_ADDS_SIGNAL"
    # predictive but no added value
    assert PB.decide_phase4(0.70, d_zero, d_zero, 10.0, leakage=False) == \
        "PHASE4_HIDDEN_STATE_PREDICTIVE"


# ---- collector helpers (no GPU) -------------------------------------------------------------------

_FRAME = {"primary_domains": ["medicine"], "secondary_domains": ["care"],
          "rejected_domains": ["commerce"]}


class _Trace:
    primary_domains = ["medicine"]; secondary_domains = ["care"]; rejected_domains = ["commerce"]


def test_resolve_layers():
    assert PC.resolve_layers("all", 5) == [0, 1, 2, 3, 4]
    assert PC.resolve_layers("0,8,16", 33) == [0, 8, 16]


def test_build_prompts_uses_frozen_builders():
    ex = {"id": "x", "query": "What is a doctor?"}
    pr = PC.build_prompts(ex, _Trace())
    assert "medicine" in pr["framed"] and "commerce" in pr["framed"]      # frame injected
    assert "medicine" not in pr["base"] and "doctor" in pr["base"].lower()  # base is frame-free


def test_metadata_schema_and_no_answer_token_guarantee():
    ex = {"id": "ord_001", "query": "What is a doctor?", "category": "ordinary"}
    m = PC.build_metadata_row(0, ex, "framed", "PROMPT TEXT", "mistralai/Mistral-7B-Instruct-v0.3",
                              [0, 8, 16], {"audit_pass": True}, "phase2b_traces", feature_dim=4096)
    for k in ("row_index", "id", "arm", "model_id", "prompt_sha256", "token_position",
              "extraction_mode", "reads_answer_tokens", "features_from_answer_tokens", "layers",
              "label_source", "labels", "feature_dim"):
        assert k in m
    assert m["token_position"] == -1
    assert m["extraction_mode"] == "last_prompt_token_pre_generation"
    assert m["reads_answer_tokens"] is False and m["features_from_answer_tokens"] is False
    assert len(m["prompt_sha256"]) == 64


def test_labels_from_audit_maps_findings():
    compliant = "A doctor primarily involves medicine, clinical, and cure here."
    lab = PC.labels_from_audit("What is a doctor?", compliant, _FRAME, terms=["doctor"])
    assert lab["audit_pass"] and not lab["frame_violation"] and not lab["rejected_domain_leak"]
    leak = "A doctor is basically about business, market, and trade above all."
    lab2 = PC.labels_from_audit("What is a doctor?", leak, _FRAME, terms=["doctor"])
    assert lab2["audit_fail"] and lab2["rejected_domain_leak"] and lab2["frame_violation"]
