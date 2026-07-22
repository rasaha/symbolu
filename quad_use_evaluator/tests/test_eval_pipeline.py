"""Evaluation-pipeline correctness: metrics, DeLong, dataset build, no-leakage OOF."""
import numpy as np

import use  # noqa: F401
from use import metrics, stats, predict
from use.dataset import bounded_fc, train_model, build_condition, conditions
from use.phases import PhaseExtractor
from use.experiment import evaluate_condition, _pool


def test_auroc_and_delong_sanity():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 400)
    good = y + rng.normal(0, 0.5, 400)        # informative
    noise = rng.normal(0, 1, 400)             # uninformative
    assert metrics.auroc(y, good) > 0.8
    assert 0.4 < metrics.auroc(y, noise) < 0.6
    d = stats.delong_roc_test(y, good, noise)
    assert d["auc1"] > d["auc2"]
    assert d["p_one_sided_1_gt_2"] < 0.05


def test_calibration_metrics():
    y = np.array([0, 0, 1, 1, 1, 0, 1, 0])
    prob = np.array([0.1, 0.2, 0.9, 0.8, 0.7, 0.3, 0.6, 0.4])
    cal = metrics.full_calibration(y, prob)
    assert 0 <= cal["ece"] <= 1 and 0 <= cal["brier"] <= 1
    assert isinstance(cal["reliability"], list)


def test_oof_no_leakage_on_noise():
    """OOF logistic on pure noise features must give AUROC near 0.5 (no leakage/overfit)."""
    rng = np.random.default_rng(1)
    n = 600
    y = rng.integers(0, 2, n)
    feats = {f"f{i}": rng.normal(0, 1, n) for i in range(9)}
    probs = predict.oof_probabilities(feats, list(feats), y, seed=0)
    assert 0.42 < metrics.auroc(y, probs) < 0.58


def test_build_condition_and_evaluate_smoke():
    fc = bounded_fc()
    m, acc = train_model(fc, 0)
    ex = PhaseExtractor()
    mq = conditions(fc)["long_and_hard"]
    d = build_condition(m, mq, 0, n_batches=6, batch_size=32, extractor=ex, W=6)
    y = d["label_failure"]
    assert y.mean() > 0.05  # this hard condition produces failures
    # confidence baseline should be a strong predictor here (sanity of labels/features)
    auc_tp = metrics.auroc(y, -d["BASE::token_prob"])
    assert auc_tp > 0.6
    res = evaluate_condition(d, seed_cv=0)
    assert "predictors" in res and "tests" in res
