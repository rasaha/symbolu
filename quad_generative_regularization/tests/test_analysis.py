"""Analysis-only diagnostics: hook must not change training; measurement sanity."""
import torch
from qgr import QuadConfig, build_model
from qgr.mqar import MQARConfig, generate_batch
from qgr.train import TrainConfig, train_arm
from qgr import analysis


def _cfg():
    return QuadConfig(vocab_size=32, hidden_size=48, num_layers=2, num_heads=4,
                      ff_size=192, context_length=64)


def _mq():
    return MQARConfig(num_kv=4, num_queries=2, vocab_size=32)


def test_analysis_hook_does_not_change_training():
    """Read-only instrumentation must leave training bit-identical (same seed -> same params)."""
    mq = _mq()
    ab = generate_batch(mq, seed=555, batch_size=8)
    common = dict(arm="D", steps=40, batch_size=16, lr=3e-3, seed=0,
                  eval_every=10**9, grad_diag_every=0, log_curves=False)
    def hook(step, model, rh, active):
        analysis.full_snapshot(model, ab)
    r_hook = train_arm(_cfg(), mq, TrainConfig(**common), analysis_hook=hook, analysis_every=10)
    r_plain = train_arm(_cfg(), mq, TrainConfig(**common))
    ph, pp = dict(r_hook["model"].named_parameters()), dict(r_plain["model"].named_parameters())
    for n in ph:
        assert torch.equal(ph[n], pp[n]), f"{n} differs — hook perturbed training"


def test_temperature_monotonic_and_ranking_preserved():
    m = build_model(_cfg(), 0)
    b = generate_batch(_mq(), seed=1, batch_size=8)
    res = analysis.temperature_counterfactual(m, b, temps=(1.0, 5.0, 20.0, 100.0))
    bt = res["by_temp"]
    ents = [bt[str(T)]["entropy_mean"] for T in (1.0, 5.0, 20.0, 100.0)]
    # entropy is non-decreasing in temperature
    assert all(ents[i] <= ents[i + 1] + 1e-6 for i in range(len(ents) - 1))
    # ranking is temperature-invariant
    assert all(bt[T]["ranking_preserved"] for T in bt)


def test_gradient_norms_nonzero_and_shapes():
    m = build_model(_cfg(), 0)
    b = generate_batch(_mq(), seed=2, batch_size=8)
    g = analysis.gradient_norms(m, b)
    assert g["grad_wrt_score"] > 0 and g["grad_wrt_Wq"] > 0 and g["grad_wrt_hidden"] > 0
    dyn = analysis.quad_score_dynamics(m, b)
    assert dyn["entropy_mean"] > 0 and len(dyn["hist_counts"]) == dyn["hist_bins"]
