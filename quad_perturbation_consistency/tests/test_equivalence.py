"""BD-Sync is a pure add-on: at lambda=0 it is bit-identical to the prior BD-A baseline.

This guarantees the ONLY difference between BD-Sync and BD-A is the consistency term.
"""
import torch

import qpc  # noqa: F401
from qgr.experiment import FrozenConfig
from qgr.train import train_arm
from qpc.train_sync import SyncTrainConfig, train_sync


def _fc():
    fc = FrozenConfig(); fc.bounded = True; fc.bound_alpha = 4.0
    return fc


def _short(tc, steps):
    tc.steps = steps; tc.eval_every = 10 ** 9; tc.log_curves = False
    return tc


def test_lambda0_bit_identical_to_qgr_bd_a():
    fc = _fc(); STEPS = 50
    tcA = fc.train_cfg("A", 0); tcA.steps = STEPS
    tcA.eval_every = 10 ** 9; tcA.grad_diag_every = 0; tcA.log_curves = False
    rA = train_arm(fc.model_cfg(), fc.base_mqar(), tcA)

    stc = SyncTrainConfig(mode="sync", lambda_consistency=0.0, steps=STEPS,
                          eval_every=10 ** 9, log_curves=False, seed=0, lr=fc.lr,
                          warmup=fc.warmup, batch_size=fc.batch_size)
    rS = train_sync(fc.model_cfg(), fc.base_mqar(), stc)

    pA = dict(rA["model"].named_parameters())
    pS = dict(rS["model"].named_parameters())
    max_diff = max(float((pA[n] - pS[n]).abs().max()) for n in pA)
    assert max_diff == 0.0, f"lambda=0 sync diverged from BD-A by {max_diff}"


def test_sync_is_deterministic():
    fc = _fc(); STEPS = 40
    def run():
        stc = SyncTrainConfig(mode="sync", lambda_consistency=0.1, steps=STEPS,
                              eval_every=10 ** 9, log_curves=False, seed=1, lr=fc.lr,
                              warmup=fc.warmup, batch_size=fc.batch_size)
        return train_sync(fc.model_cfg(), fc.base_mqar(), stc)["model"]
    m1, m2 = run(), run()
    p1 = dict(m1.named_parameters()); p2 = dict(m2.named_parameters())
    assert max(float((p1[n] - p2[n]).abs().max()) for n in p1) == 0.0


def test_early_cutoff_stops_consistency():
    """After the early cutoff the run is task-only; a 0.0-fraction early arm == lambda=0 arm."""
    fc = _fc(); STEPS = 40
    stc0 = SyncTrainConfig(mode="sync", lambda_consistency=0.1, consistency_cutoff_frac=0.0,
                           steps=STEPS, eval_every=10 ** 9, log_curves=False, seed=2, lr=fc.lr,
                           warmup=fc.warmup, batch_size=fc.batch_size)
    r0 = train_sync(fc.model_cfg(), fc.base_mqar(), stc0)
    stcL0 = SyncTrainConfig(mode="sync", lambda_consistency=0.0, steps=STEPS,
                            eval_every=10 ** 9, log_curves=False, seed=2, lr=fc.lr,
                            warmup=fc.warmup, batch_size=fc.batch_size)
    rL0 = train_sync(fc.model_cfg(), fc.base_mqar(), stcL0)
    p0 = dict(r0["model"].named_parameters()); pL0 = dict(rL0["model"].named_parameters())
    assert max(float((p0[n] - pL0[n]).abs().max()) for n in p0) == 0.0
