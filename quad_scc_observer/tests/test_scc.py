"""SCC correctness: read-only, feature sanity, evidence=oracle, no-leakage, verdict plumbing."""
import numpy as np
import torch

import scc  # noqa: F401
from use.dataset import bounded_fc, train_model, conditions
from use.capture import run_inference
from qgr.mqar import generate_batch, split_seed
from scc import claims, features_S, features_R, features_E, features_T, baselines, evaluate


def _setup(cond="long_and_hard", ci=4, nb_seed=0):
    fc = bounded_fc()
    model, acc = train_model(fc, 0)
    mq = conditions(fc)[cond]
    base = generate_batch(mq, split_seed(0, "test", 20_000 + ci * 1000), 32)
    rec = run_inference(model, base.tokens)
    records = claims.build_records(rec, base, model)
    return fc, model, mq, base, rec, records


def test_inference_read_only():
    fc, model, mq, base, rec, records = _setup()
    with torch.no_grad():
        plain = model(base.tokens)["logits"].clone()
    rec2 = run_inference(model, base.tokens)
    assert torch.equal(plain, rec2["logits"])


def test_claim_decoding_matches_labels():
    fc, model, mq, base, rec, records = _setup()
    for r in records:
        assert r["failure"] == int(r["v_pred"] != r["v_true"])
        assert r["k_q"] in r["key_token_set"]


def test_evidence_adjacency_is_oracle_single_system():
    """In a single-relation closed world, adjacency support == correctness (near-oracle)."""
    fc, model, mq, base, rec, records = _setup(cond="long_and_hard", ci=4)
    E = features_E.compute(records, rec, model)
    y_correct = np.array([r["correct"] for r in records])
    # adjacency_support should equal correctness for (near) all queries
    agree = (E["E_adjacency_support"] == y_correct).mean()
    assert agree > 0.98


def test_E_equals_grounding():
    fc, model, mq, base, rec, records = _setup()
    E = features_E.compute(records, rec, model)
    C = baselines.grounding(records, rec, model)
    assert np.allclose(E["E_adjacency_support"], C["C::adjacency_support"])


def test_T_coverage_on_distractor_condition():
    fc, model, mq, base, rec, records = _setup(cond="long_context", ci=1)
    T = features_T.compute(records, base, mq, model, 0, 1, M=3)
    cov = np.mean(~np.isnan(T["T_flip_rate"]))
    assert cov > 0.9  # token-identity alignment covers distractor conditions


def test_feature_finiteness():
    fc, model, mq, base, rec, records = _setup()
    for mod in (features_S, features_R, features_E):
        for k, v in mod.compute(records, rec, model).items():
            assert np.isfinite(v).all(), k


def test_confidence_predicts_failure():
    fc, model, mq, base, rec, records = _setup()
    from sklearn.metrics import roc_auc_score
    y = np.array([r["failure"] for r in records])
    conf = baselines.confidence(rec, records)["A::token_prob"]
    auc = roc_auc_score(y, -conf)  # low prob -> failure
    assert auc > 0.6


def test_evaluate_pool_runs_and_no_leakage_on_random():
    # random-only features must give AUROC ~0.5 through the OOF pipeline
    n = 800
    rng = np.random.default_rng(0)
    pool = {"A::token_prob": rng.normal(size=n), "C::adjacency_support": rng.normal(size=n),
            "S::x": rng.normal(size=n), "R::x": rng.normal(size=n),
            "E::x": rng.normal(size=n), "T::x": rng.normal(size=n),
            "B::x": rng.normal(size=n),
            "label_failure": rng.integers(0, 2, n), "correct": rng.integers(0, 2, n)}
    res = evaluate.evaluate_pool(pool)
    assert 0.4 < res["arms"]["1_confidence"]["auroc"] < 0.6
