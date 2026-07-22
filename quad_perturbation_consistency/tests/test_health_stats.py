"""Health metrics, progressive curve, and statistics behave sensibly."""
import torch

import qpc  # noqa: F401
from qgr.experiment import FrozenConfig
from qgr.quad_model import build_model
from qpc.health import attention_health, stability, guardrail2_health
from qpc.progressive import progressive_curve, distinct_two_system_batch
from qpc.perturbations import AugConfig
from qpc import stats as qstats
from qgr.mqar import MQARConfig


def _fc():
    fc = FrozenConfig(); fc.bounded = True; fc.bound_alpha = 4.0
    return fc


def test_health_metrics_ranges():
    fc = _fc()
    model = build_model(fc.model_cfg(), 0)
    h = attention_health(model, fc.base_mqar(), 0, n_batches=3)
    assert 0.0 <= h["attn_entropy_norm"] <= 1.05
    assert h["head_diversity_js"] >= 0.0
    assert 0.0 <= h["headmean_select_acc"] <= 1.0
    s = stability(model, fc.base_mqar(), 0, AugConfig(), n_batches=3)
    assert -0.05 <= s["perturb_stability"] <= 1.05
    assert 0.0 <= s["retrieval_stability"] <= 1.0


def test_guardrail2_flags_uniform_and_collapse():
    # a synthetic collapsed-entropy health record is flagged
    bad = {"attn_entropy_norm": 0.0, "head_diversity_js": 0.0,
           "head_specialization_sel_std": 0.0, "head_specialization_ent_std": 0.0}
    g = guardrail2_health(bad)
    assert not g["healthy"]
    assert g["checks"]["entropy_collapse"] and g["checks"]["head_collapse"]
    good = {"attn_entropy_norm": 0.5, "head_diversity_js": 0.2,
            "head_specialization_sel_std": 0.1, "head_specialization_ent_std": 0.1}
    assert guardrail2_health(good)["healthy"]


def test_distinct_two_system_batch_has_distinct_keys():
    fc = _fc()
    mq2 = MQARConfig(fc.num_kv, fc.num_queries, 0, fc.vocab_size, 2)
    b = distinct_two_system_batch(mq2, 0, 8)
    for i in range(8):
        cand = b.cand_mask[i].any(0).nonzero().flatten()
        toks = b.tokens[i][cand].tolist()
        assert len(toks) == len(set(toks)), "keys must be globally distinct"


def test_progressive_curve_shape():
    fc = _fc()
    model = build_model(fc.model_cfg(), 0)
    curve = progressive_curve(model, fc, 0, n_batches=2)
    labels = [d["label"] for d in curve]
    assert labels == ["original", "small_shift", "distractor_permute",
                      "extra_distractors", "longer_context", "multi_system"]
    # level 0 (no perturbation) is (near) perfectly stable
    assert curve[0]["perturb_stability"] > 0.98


def test_paired_comparison_directional():
    # a method uniformly better than baseline -> positive mean delta, one-sided p small
    base = [0.50, 0.55, 0.48, 0.52, 0.51, 0.49, 0.53, 0.50]
    meth = [b + 0.06 for b in base]
    cmp = qstats.paired_comparison(meth, base)
    assert cmp["mean_delta"] > 0
    assert cmp["n_positive"] == len(base)
    assert cmp["bootstrap_ci95"]["lo"] > 0
    if cmp["wilcoxon"]["p_greater"] is not None:
        assert cmp["wilcoxon"]["p_greater"] < 0.05
    # identical arms -> not significant
    cmp0 = qstats.paired_comparison(base, base)
    assert not cmp0["significant_improvement_over_baseline"]
