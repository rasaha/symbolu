"""Early-only auxiliary schedule: hard cutoff correctness (schedule-ablation experiment).

Deliverables 2-3: verify the auxiliary coefficient becomes EXACTLY zero at each cutoff,
and that post-cutoff gradients come only from the task loss.
"""
import torch
from qgr import QuadConfig
from qgr.mqar import MQARConfig
from qgr.train import TrainConfig, train_arm


def _cfg():
    return QuadConfig(vocab_size=32, hidden_size=48, num_layers=2, num_heads=4,
                      ff_size=192, context_length=64)


def _mq():
    return MQARConfig(num_kv=4, num_queries=2, vocab_size=32)


def test_cutoff_step_arithmetic():
    for frac, expect in [(0.0, 0), (0.10, 250), (0.25, 625), (0.50, 1250), (1.0, 2500)]:
        tc = TrainConfig(arm="D", steps=2500, aux_cutoff_frac=frac)
        assert tc.cutoff_step() == expect


def test_aux_coefficient_exactly_zero_after_cutoff():
    """D-50 on 40 steps: aux active & coeff==lambda for step<20, exactly 0 for step>=20."""
    steps = 40
    tc = TrainConfig(arm="D", lambda_aux=1.0, steps=steps, aux_cutoff_frac=0.5,
                     batch_size=8, lr=3e-3, seed=0, eval_every=1, grad_diag_every=1)
    r = train_arm(_cfg(), _mq(), tc)
    cutoff = tc.cutoff_step()
    assert cutoff == 20
    for h in r["history"]:
        if h["step"] < cutoff:
            assert h["aux_active"] is True and h["aux_coeff"] == 1.0
        else:
            assert h["aux_active"] is False
            assert h["aux_coeff"] == 0.0
            assert h["aux_loss"] == 0.0            # auxiliary loss not added
    # gradient diagnostics: aux gradient measured only while active, exactly zero after.
    for g in r["grad_history"]:
        if g["step"] < cutoff:
            assert g["aux_grad_norm"] > 0.0
        else:
            assert g["aux_grad_norm"] == 0.0       # post-cutoff: no auxiliary gradient


def test_frac_zero_is_bit_identical_to_arm_A():
    """aux_cutoff_frac=0.0 (auxiliary never active) must equal Arm A bit-for-bit, proving
    that when the coefficient is zero the gradients come ONLY from the task loss."""
    steps = 30
    common = dict(steps=steps, batch_size=8, lr=3e-3, seed=1, eval_every=10**9,
                  grad_diag_every=0, log_curves=False)
    rA = train_arm(_cfg(), _mq(), TrainConfig(arm="A", **common))
    rD0 = train_arm(_cfg(), _mq(), TrainConfig(arm="D", lambda_aux=1.0,
                                               aux_cutoff_frac=0.0, **common))
    pA = dict(rA["model"].named_parameters())
    pD = dict(rD0["model"].named_parameters())
    for name in pA:
        assert torch.equal(pA[name], pD[name]), f"{name} differs (aux-off D != A)"


def test_full_duration_matches_default_D():
    """aux_cutoff_frac=1.0 reproduces the un-scheduled Arm D exactly."""
    steps = 25
    common = dict(arm="D", lambda_aux=1.0, steps=steps, batch_size=8, lr=3e-3, seed=2,
                  eval_every=10**9, grad_diag_every=0, log_curves=False)
    r_default = train_arm(_cfg(), _mq(), TrainConfig(**common))
    r_full = train_arm(_cfg(), _mq(), TrainConfig(aux_cutoff_frac=1.0, **common))
    p0 = dict(r_default["model"].named_parameters())
    p1 = dict(r_full["model"].named_parameters())
    for name in p0:
        assert torch.equal(p0[name], p1[name])
