"""Training loop: task-only baseline + optional same-head consistency add-on.

This loop is a strict SUPERSET of the frozen task-only bounded baseline (BD-A).  With
``lambda_consistency == 0`` it performs exactly the BD-A optimisation — same init, same data
order, same optimizer, same task loss on the same tokens — so BD-Sync is BD-A *plus* the
consistency term and nothing else (verified bit-identical in tests).  The consistency term is
read from the model's own forward-path Quad score; it adds no inference-time operation.

Arms produced here (all bounded, base = task-only):
    BD-Sync         : task + lambda * same-head JS consistency (full duration).
    BD-Sync-Early   : consistency active only for the first ``consistency_cutoff_frac`` steps.
    BD-Shuffled     : same machinery, but the key-identity alignment is randomly permuted
                      (semantic pairing destroyed) -- the generic-regularisation control.

BD-A (task-only) and BD-D (Quad auxiliary) are produced by the *unmodified* prior package
(``qgr.train.train_arm``); this module never reproduces or replaces them.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import torch

from . import _qgr_path  # noqa: F401
from qgr.quad_model import QuadConfig, build_model
from qgr.mqar import MQARConfig, generate_batch, split_seed
from qgr.losses import task_loss
from qgr.metrics import evaluate, quad_mechanism

from .perturbations import AugConfig, make_aligned_pair
from .consistency import consistency_loss, EMATarget


@dataclass
class SyncTrainConfig:
    mode: str = "sync"                 # "sync" | "sync_early" | "shuffled"
    lambda_consistency: float = 0.1    # small fixed coefficient
    tau: float = 1.0
    stop_grad_target: bool = True      # stop-grad on the target side (else EMA self-target)
    ema_decay: float = 0.99
    consistency_cutoff_frac: float = 1.0   # sync_early sets this < 1 (hard cutoff to 0)
    steps: int = 2500
    batch_size: int = 32
    lr: float = 4e-3
    weight_decay: float = 0.0
    warmup: int = 50
    grad_clip: float = 1.0
    eval_every: int = 250
    eval_batches: int = 8
    seed: int = 0
    device: str = "cpu"
    log_curves: bool = True
    aug: AugConfig = field(default_factory=AugConfig)

    def cutoff_step(self) -> int:
        return int(self.consistency_cutoff_frac * self.steps)


def _shuffled(mode: str) -> bool:
    return mode == "shuffled"


def train_sync(cfg: QuadConfig, mqar_cfg: MQARConfig, tc: SyncTrainConfig) -> Dict:
    """Train one consistency arm (or, at lambda=0, exactly the task-only baseline)."""
    device = tc.device
    torch.manual_seed(tc.seed)
    model = build_model(cfg, tc.seed).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=tc.lr, weight_decay=tc.weight_decay)

    ema = None
    if not tc.stop_grad_target and tc.lambda_consistency > 0:
        ema = EMATarget(model, decay=tc.ema_decay)

    def lr_at(step):
        if step < tc.warmup:
            return tc.lr * (step + 1) / tc.warmup
        return tc.lr

    cutoff = tc.cutoff_step()
    history: List[Dict] = []
    cons_history: List[Dict] = []
    step_times: List[float] = []

    for step in range(tc.steps):
        model.train()
        for grp in opt.param_groups:
            grp["lr"] = lr_at(step)
        cons_active = tc.lambda_consistency > 0 and step < cutoff
        base = generate_batch(mqar_cfg, split_seed(tc.seed, "train", step),
                              tc.batch_size, device)
        t0 = time.perf_counter()

        if cons_active:
            pair = make_aligned_pair(base, mqar_cfg, tc.aug,
                                     seed=split_seed(tc.seed, "train", step) + 3,
                                     shuffled_control=_shuffled(tc.mode), device=device)
            out_o = model(pair.tokens_o, expose_quad=True)
            tl = task_loss(out_o["logits"], pair.targets_o)
            if ema is not None:
                quad_p = ema.score(pair.tokens_p)
            else:
                quad_p = model(pair.tokens_p, expose_quad=True)["quad_score"]
            cl, cdiag = consistency_loss(out_o["quad_score"], quad_p, pair, tau=tc.tau,
                                         stop_grad_target=tc.stop_grad_target)
            loss = tl + tc.lambda_consistency * cl
        else:
            # task-only path (identical to BD-A): forward on the base batch, task loss only.
            out = model(base.tokens)
            tl = task_loss(out["logits"], base.targets)
            cl = torch.zeros((), device=device)
            cdiag = {"consistency_jsd": 0.0, "consistency_jsd_max": 0.0}
            loss = tl

        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), tc.grad_clip)
        opt.step()
        if ema is not None and cons_active:
            ema.update(model)
        step_times.append(time.perf_counter() - t0)

        if tc.log_curves and (step % tc.eval_every == 0 or step == tc.steps - 1):
            ev = evaluate(model, mqar_cfg, tc.seed, "val", tc.eval_batches,
                          tc.batch_size, device)
            mech = quad_mechanism(model, mqar_cfg, tc.seed, "val", 4, tc.batch_size, device)
            history.append({
                "step": step, "task_loss": float(tl), "consistency_loss": float(cl),
                "cons_active": bool(cons_active), "val_acc": ev["acc"],
                "val_seq_acc": ev["seq_acc"],
                **{f"mech_{k}": v for k, v in mech.items()},
            })
        if step % 100 == 0:
            cons_history.append({"step": step, "cons_active": bool(cons_active), **cdiag})

    final_val = evaluate(model, mqar_cfg, tc.seed, "val", tc.eval_batches * 2,
                         tc.batch_size, device)
    return {
        "mode": tc.mode, "seed": tc.seed,
        "lambda_consistency": tc.lambda_consistency,
        "consistency_cutoff_frac": tc.consistency_cutoff_frac,
        "history": history, "cons_history": cons_history,
        "final_val": final_val, "model": model,
        "mean_step_time": sum(step_times) / max(len(step_times), 1),
        "total_train_time": sum(step_times),
        "num_params": model.num_params(),
    }
