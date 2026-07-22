"""Training loop and experimental arms A / C / D / D0.

Arms (spec sections 12-13):
    A  : task loss only (baseline).
    C  : task + lambda * generic hidden-state relational loss (generic control).
    D  : task + lambda * Quad-native auxiliary loss (proposed method).
    D0 : Arm-D code path with lambda=0 (deterministic equivalence test vs A).

All arms share identical model dims, initialization, data order, optimizer, LR schedule,
batch size, causal mask, seeds, and candidate construction (spec section 14).  The only
difference between arms is which score field the auxiliary loss reads (and lambda).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import torch

from .quad_model import QuadConfig, QuadTransformer, GenericRelationHead, build_model
from .mqar import MQARConfig, generate_batch, split_seed
from .losses import (
    task_loss, quad_aux_loss, generic_relational_loss, quad_margin_loss,
    mechanism_diagnostics,
)
from .metrics import evaluate, quad_mechanism


@dataclass
class TrainConfig:
    arm: str = "A"                 # "A" | "C" | "D" | "D0"
    lambda_aux: float = 1.0
    tau: float = 1.0
    objective: str = "classification"   # "classification" (Option B) | "margin" (Option C)
    margin: float = 1.0
    steps: int = 800
    batch_size: int = 32
    lr: float = 3e-3
    weight_decay: float = 0.0
    warmup: int = 50
    grad_clip: float = 1.0
    eval_every: int = 100
    eval_batches: int = 8
    grad_diag_every: int = 100     # diagnostic gradient measurement cadence
    seed: int = 0
    device: str = "cpu"
    log_curves: bool = True
    # Shuffled-label control (spec 21.1): permute the correct-key AUX label to a random
    # candidate key per query, preserving candidate-set size / causal visibility / position
    # distribution. Task targets are UNCHANGED. Used only in the conditional follow-up.
    shuffle_aux_labels: bool = False


def _effective_lambda(tcfg: TrainConfig) -> float:
    if tcfg.arm == "A":
        return 0.0
    if tcfg.arm == "D0":
        return 0.0
    return tcfg.lambda_aux


def _uses_aux_code(arm: str) -> bool:
    """A: no aux code. C/D/D0: aux code path active (D0 exercises it with lambda=0)."""
    return arm in ("C", "D", "D0")


def _compute_aux(tcfg: TrainConfig, out: Dict[str, torch.Tensor], batch,
                 relation_head=None) -> torch.Tensor:
    if tcfg.arm == "C":
        return generic_relational_loss(relation_head, out["aux_hidden"], batch.key_pos,
                                       batch.cand_mask, tau=tcfg.tau)
    # Arm D / D0: Quad-native objective.
    if tcfg.objective == "margin":
        return quad_margin_loss(out["quad_score"], batch.key_pos,
                                batch.cand_mask, margin=tcfg.margin)
    return quad_aux_loss(out["quad_score"], batch.key_pos, batch.cand_mask, tau=tcfg.tau)


def _shuffle_labels(batch, gen: torch.Generator):
    """Return a copy of key_pos where each query's correct-key label is replaced by a
    uniformly-random candidate key from that query's own candidate set (spec 21.1).
    Preserves candidate-set size, causal visibility, and position distribution; only the
    identity of the 'correct' key for the AUX loss changes. Task targets are untouched."""
    key_pos = batch.key_pos.clone()
    q = batch.key_pos >= 0
    for bi, t in q.nonzero(as_tuple=False).tolist():
        cands = batch.cand_mask[bi, t].nonzero(as_tuple=False).flatten()
        pick = cands[torch.randint(len(cands), (1,), generator=gen)]
        key_pos[bi, t] = int(pick)
    from .mqar import MQARBatch
    return MQARBatch(batch.tokens, batch.targets, batch.query_pos, key_pos, batch.cand_mask)


def _forward(model: QuadTransformer, tokens, arm: str):
    if arm == "A":
        return model(tokens)
    if arm == "C":
        return model(tokens, expose_hidden=True)
    return model(tokens, expose_quad=True)  # D / D0


def _grad_diagnostics(model, tcfg, mqar_cfg, diag_batch, relation_head=None) -> Dict[str, float]:
    """Separate task vs aux gradient measurement on a fixed diagnostic minibatch.

    Excluded from per-step timing (spec section 15.2). Only meaningful for arms with aux.
    Gradients are measured w.r.t. the SHARED model parameters (embeddings + blocks + head),
    the parameters both task and aux gradients touch, to confirm the aux signal reaches the
    shared model (spec sections 15.2, 17.6).
    """
    params = [p for p in model.parameters() if p.requires_grad]
    out = _forward(model, diag_batch.tokens, tcfg.arm if tcfg.arm != "D0" else "D")
    tl = task_loss(out["logits"], diag_batch.targets)
    g_task = torch.autograd.grad(tl, params, retain_graph=True, allow_unused=True)

    if not _uses_aux_code(tcfg.arm):
        return {}
    al = _compute_aux(
        TrainConfig(arm="D" if tcfg.arm in ("D", "D0") else "C", tau=tcfg.tau,
                    objective=tcfg.objective, margin=tcfg.margin),
        out, diag_batch, relation_head,
    )
    # grad w.r.t. shared model params only (relation_head params, if any, are excluded).
    g_aux = torch.autograd.grad(al, params, retain_graph=False, allow_unused=True)

    def flat(gs):
        return torch.cat([g.reshape(-1) if g is not None else torch.zeros(p.numel())
                          for g, p in zip(gs, params)])
    ft, fa = flat(g_task), flat(g_aux)
    task_norm = float(ft.norm())
    aux_norm = float(fa.norm())
    cos = float(torch.nn.functional.cosine_similarity(ft, fa, dim=0)) if aux_norm > 0 else 0.0
    # fraction of parameters whose aux-grad is negligible relative to task-grad scale
    per_param_aux = torch.stack([
        (g.norm() if g is not None else torch.tensor(0.0)) for g in g_aux
    ])
    ref = max(task_norm, 1e-12)
    negligible = float((per_param_aux < 1e-3 * ref).float().mean())
    return {
        "task_grad_norm": task_norm,
        "aux_grad_norm": aux_norm,
        "aux_to_task_ratio": aux_norm / ref,
        "grad_cosine": cos,
        "aux_grad_negligible_frac": negligible,
    }


def train_arm(cfg: QuadConfig, mqar_cfg: MQARConfig, tcfg: TrainConfig,
              val_seed: Optional[int] = None) -> Dict:
    """Train one arm. Returns history + final model + summary."""
    device = tcfg.device
    torch.manual_seed(tcfg.seed)
    model = build_model(cfg, tcfg.seed).to(device)

    # Arm C gets an equal-capacity OFF-PATH learned relation head (training-only,
    # discarded at inference). Seeded deterministically AFTER the model so the base
    # model init is bit-identical across arms.
    relation_head = None
    trainable = list(model.parameters())
    if tcfg.arm == "C":
        torch.manual_seed(tcfg.seed + 10_007)
        relation_head = GenericRelationHead(cfg.hidden_size, cfg.num_heads).to(device)
        trainable = trainable + list(relation_head.parameters())
    opt = torch.optim.AdamW(trainable, lr=tcfg.lr, weight_decay=tcfg.weight_decay)

    def lr_at(step):
        if step < tcfg.warmup:
            return tcfg.lr * (step + 1) / tcfg.warmup
        return tcfg.lr
    val_seed = tcfg.seed if val_seed is None else val_seed

    lam = _effective_lambda(tcfg)
    history: List[Dict] = []
    grad_history: List[Dict] = []
    step_times: List[float] = []
    diag_batch = generate_batch(mqar_cfg, split_seed(tcfg.seed, "val", 999),
                                min(16, tcfg.batch_size), device)

    for step in range(tcfg.steps):
        model.train()
        for grp in opt.param_groups:
            grp["lr"] = lr_at(step)
        batch = generate_batch(mqar_cfg, split_seed(tcfg.seed, "train", step),
                               tcfg.batch_size, device)
        aux_batch = batch
        if tcfg.shuffle_aux_labels and _uses_aux_code(tcfg.arm):
            shuf_gen = torch.Generator().manual_seed(split_seed(tcfg.seed, "train", step) + 1)
            aux_batch = _shuffle_labels(batch, shuf_gen)
        t0 = time.perf_counter()
        out = _forward(model, batch.tokens, tcfg.arm)
        tl = task_loss(out["logits"], batch.targets)
        if _uses_aux_code(tcfg.arm):
            al = _compute_aux(tcfg, out, aux_batch, relation_head)
            loss = tl + lam * al
        else:
            al = torch.zeros((), device=device)
            loss = tl
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), tcfg.grad_clip)
        opt.step()
        step_times.append(time.perf_counter() - t0)

        if tcfg.log_curves and (step % tcfg.eval_every == 0 or step == tcfg.steps - 1):
            ev = evaluate(model, mqar_cfg, val_seed, "val", tcfg.eval_batches,
                          tcfg.batch_size, device)
            mech = quad_mechanism(model, mqar_cfg, val_seed, "val",
                                  min(tcfg.eval_batches, 4), tcfg.batch_size, device)
            history.append({
                "step": step, "task_loss": float(tl), "aux_loss": float(al),
                "val_acc": ev["acc"], "val_seq_acc": ev["seq_acc"],
                "val_task_loss": ev["task_loss"], **{f"mech_{k}": v for k, v in mech.items()},
            })

        if tcfg.grad_diag_every > 0 and step % tcfg.grad_diag_every == 0:
            gd = _grad_diagnostics(model, tcfg, mqar_cfg, diag_batch, relation_head)
            if gd:
                gd["step"] = step
                grad_history.append(gd)

    final_val = evaluate(model, mqar_cfg, val_seed, "val", tcfg.eval_batches * 2,
                         tcfg.batch_size, device)
    return {
        "arm": tcfg.arm,
        "seed": tcfg.seed,
        "history": history,
        "grad_history": grad_history,
        "final_val": final_val,
        "mean_step_time": sum(step_times) / max(len(step_times), 1),
        "total_train_time": sum(step_times),
        "model": model,
        "num_params": model.num_params(),
    }
