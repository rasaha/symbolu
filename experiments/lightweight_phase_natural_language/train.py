"""
train.py — shared training loop for all arms.

Objective (identical across A/B/C/C-no-Phase — fairness):
    L = L_LM  +  lambda_ans * L_answer
where L_LM is next-token cross-entropy over the whole sequence (pad-masked) and
L_answer is cross-entropy at the <A> position predicting the answer token. Answer-
position supervision is used because full-sequence LM loss alone drowns the sparse
task signal; it is applied consistently to every arm and disclosed here.

C and C-no-Phase receive the SAME supervision as B — no privileged answer info.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Optional, Tuple

import torch
import torch.nn.functional as F

from .datasets import Example, Tokenizer


@dataclass
class TrainConfig:
    steps: int = 500
    batch_size: int = 12
    lr: float = 1e-3
    lambda_ans: float = 1.0
    grad_clip: float = 1.0
    seed: int = 0
    eval_every: int = 75          # validation cadence for early stopping (0 = off)


def _collate(batch: List[Example], pad_id: int, device) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    maxlen = max(len(e.tokens) for e in batch)
    B = len(batch)
    ids = torch.full((B, maxlen), pad_id, dtype=torch.long)
    labels = torch.full((B, maxlen), -100, dtype=torch.long)
    ans_pos = torch.zeros(B, dtype=torch.long)
    ans_id = torch.zeros(B, dtype=torch.long)
    for i, e in enumerate(batch):
        n = len(e.tokens)
        ids[i, :n] = torch.tensor(e.tokens)
        labels[i, :n] = torch.tensor(e.tokens)
        ans_pos[i] = e.answer_pos
        ans_id[i] = e.answer_id
    return ids.to(device), labels.to(device), ans_pos.to(device), ans_id.to(device)


@torch.no_grad()
def _val_answer_accuracy(model, val: List[Example], tok: Tokenizer, device) -> float:
    """Mean answer-position accuracy over the validation set (cheap early-stop signal)."""
    model.eval()
    correct = total = 0
    for i in range(0, len(val), 64):
        batch = val[i:i + 64]
        ids, labels, ans_pos, ans_id = _collate(batch, tok.pad_id, device)
        logits, _ = model(ids)
        ar = torch.arange(ids.size(0), device=device)
        pred = logits[ar, ans_pos].argmax(-1)
        correct += (pred == ans_id).sum().item(); total += len(batch)
    model.train()
    return correct / max(1, total)


def train_model(model, examples: List[Example], tok: Tokenizer, cfg: TrainConfig,
                device="cpu", log_every: int = 0,
                val: Optional[List[Example]] = None) -> dict:
    """Train with optional validation-based early stopping (best-checkpoint select).

    Because the tiny models overshoot and then degrade with more steps, we keep the
    checkpoint with the best validation answer-accuracy rather than the last one.
    This removes the step-count sensitivity confound and gives each arm its best
    achievable performance under an identical protocol.
    """
    torch.manual_seed(cfg.seed)
    rng = torch.Generator().manual_seed(cfg.seed + 7)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    model.train()
    n = len(examples)
    history = []
    best_val = -1.0
    best_state = None
    best_step = -1
    for step in range(cfg.steps):
        idx = torch.randint(0, n, (cfg.batch_size,), generator=rng).tolist()
        batch = [examples[i] for i in idx]
        ids, labels, ans_pos, ans_id = _collate(batch, tok.pad_id, device)
        logits, lm_loss = model(ids, labels=labels)
        ar = torch.arange(ids.size(0), device=device)
        ans_loss = F.cross_entropy(logits[ar, ans_pos], ans_id)
        loss = lm_loss + cfg.lambda_ans * ans_loss
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
        opt.step()
        if log_every and step % log_every == 0:
            history.append({"step": step, "lm": lm_loss.item(), "ans": ans_loss.item()})
        if val is not None and cfg.eval_every and (step + 1) % cfg.eval_every == 0:
            v = _val_answer_accuracy(model, val, tok, device)
            if v > best_val:
                best_val = v; best_step = step + 1
                best_state = copy.deepcopy(model.state_dict())
    if best_state is not None:
        model.load_state_dict(best_state)
    return {"final_lm": lm_loss.item(), "final_ans": ans_loss.item(),
            "best_val_acc": best_val, "best_step": best_step, "history": history}
