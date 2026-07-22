"""Unified training loop for the perturbation-consistency study (imports qgr as a library).

All five arms share the SAME bounded architecture, initialization, optimizer, LR schedule,
batch size, token budget, seeds, and base data (paired generator). The only difference is the
extra training-only term:

  BD-A            : task loss only.
  BD-D            : task + lam_aux * labelled Quad aux (qgr.quad_aux_loss)   [existing baseline]
  BD-Sync         : task + lam_sync * JS(A(x), sg(A(x_tilde)))              [proposed]
  BD-Sync-Early   : BD-Sync with the consistency term hard-disabled after `cutoff_frac`.
  Shuffled-Pair   : BD-Sync but x_tilde paired with an UNRELATED sample (partner_roll=1).

No inference-time component; no labels for the sync arms; no one-hot pressure; no scheduling of
the coefficient; no temperature/normalization/architecture change beyond the frozen bound.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                                "quad_generative_regularization"))
from qgr import QuadConfig, build_model, MQARConfig, split_seed, evaluate, quad_mechanism  # noqa
from qgr.losses import task_loss, quad_aux_loss                                            # noqa
from qgr.experiment import FrozenConfig                                                    # noqa

from .paired_mqar import gen_paired_batch
from .consistency import consistency_loss, distribution_drift, pair_distribution
from . import diagnostics as D

ARMS = ("BD-A", "BD-D", "BD-Sync", "BD-Sync-Early", "Shuffled-Pair")


@dataclass
class SyncConfig:
    alpha: float = 4.0
    steps: int = 2500
    batch_size: int = 32
    lr: float = 4e-3
    warmup: int = 50
    grad_clip: float = 1.0
    lam_aux: float = 1.0
    lam_sync: float = 1.0
    early_cutoff_frac: float = 0.25
    eval_every: int = 250
    eval_batches: int = 8

    def model_cfg(self) -> QuadConfig:
        return QuadConfig(vocab_size=32, hidden_size=96, num_layers=2, num_heads=4,
                          ff_size=384, context_length=64, dropout=0.0,
                          bounded=True, bound_alpha=self.alpha)

    def mqar(self) -> MQARConfig:
        return MQARConfig(num_kv=4, num_queries=2, vocab_size=32)


def _arm_flags(arm: str):
    return {
        "BD-A": dict(aux=False, sync=False, roll=0, cutoff=1.0),
        "BD-D": dict(aux=True, sync=False, roll=0, cutoff=1.0),
        "BD-Sync": dict(aux=False, sync=True, roll=0, cutoff=1.0),
        "BD-Sync-Early": dict(aux=False, sync=True, roll=0, cutoff=None),   # uses early_cutoff_frac
        "Shuffled-Pair": dict(aux=False, sync=True, roll=1, cutoff=1.0),
    }[arm]


def train_sync_arm(arm: str, seed: int, cfg: SyncConfig, log_curves: bool = True) -> Dict:
    assert arm in ARMS
    fl = _arm_flags(arm)
    cutoff_frac = cfg.early_cutoff_frac if fl["cutoff"] is None else fl["cutoff"]
    cutoff = int(cutoff_frac * cfg.steps)

    torch.manual_seed(seed)
    model = build_model(cfg.model_cfg(), seed)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr)
    mq = cfg.mqar()

    def lr_at(s):
        return cfg.lr * (s + 1) / cfg.warmup if s < cfg.warmup else cfg.lr

    history: List[Dict] = []
    step_times = []
    for step in range(cfg.steps):
        model.train()
        for g in opt.param_groups:
            g["lr"] = lr_at(step)
        paired = gen_paired_batch(mq, split_seed(seed, "train", step), cfg.batch_size)
        active = step < cutoff
        t0 = time.perf_counter()
        out_x = model(paired.x_tokens, expose_quad=True)
        tl = task_loss(out_x["logits"], paired.x_targets)
        loss = tl
        aux_val = 0.0
        if fl["aux"] and active:
            al = quad_aux_loss(out_x["quad_score"], paired.x_key_pos, paired.x_cand_mask)
            loss = loss + cfg.lam_aux * al
            aux_val = float(al)
        if fl["sync"] and active:
            out_xt = model(paired.xt_tokens, expose_quad=True)
            sl = consistency_loss(out_x["quad_score"], paired, out_xt["quad_score"],
                                  partner_roll=fl["roll"])
            loss = loss + cfg.lam_sync * sl
            aux_val = float(sl)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
        opt.step()
        step_times.append(time.perf_counter() - t0)

        if log_curves and (step % cfg.eval_every == 0 or step == cfg.steps - 1):
            ev = evaluate(model, mq, seed, "val", cfg.eval_batches, cfg.batch_size)
            mech = quad_mechanism(model, mq, seed, "val", 4, cfg.batch_size)
            history.append({"step": step, "task_loss": float(tl), "aux_loss": aux_val,
                            "aux_active": bool(active),
                            "val_acc": ev["acc"], "val_task_loss": ev["task_loss"],
                            "entropy": mech.get("cand_entropy", float("nan")),
                            "margin": mech.get("pos_neg_margin", float("nan")),
                            "select_acc": mech.get("internal_select_acc", float("nan"))})

    final = evaluate(model, mq, seed, "val", cfg.eval_batches * 2, cfg.batch_size)
    return {"arm": arm, "seed": seed, "cutoff_step": cutoff, "history": history,
            "final_val": final, "model": model,
            "mean_step_time": sum(step_times) / max(len(step_times), 1),
            "total_train_time": sum(step_times)}
