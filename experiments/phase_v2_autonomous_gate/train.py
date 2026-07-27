"""
train.py — curriculum training for the six autonomous-gate arms (§ Required training arms).

All arms share architecture (AutoGateModel = embed + frozen-arch V2-S + focus head), data,
seeds, optimizer, and budget. They differ only in how the write gate B_t is trained:

    A_supervised_teacher : permanent BCE(gate, oracle write mask)      (upper bound)
    B_annealed           : same BCE, coefficient annealed → 0, then E2E (main target)
    C_distillation       : BCE(student gate, frozen teacher gate), then E2E
    D_future_relevance   : BCE(gate, future-relevance label)           (delayed credit)
    E_contrastive        : hinge(relevant > distractor write score)
    F_e2e_scratch        : focus CE only                               (negative baseline)

At INFERENCE every arm uses the gate σ(W_w h) with no labels. Focus identity is decoded
from the existing Phase readout at PROBE (no new selective readout).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from experiments.phase_v3_selective_ssm import dataset as D
from experiments.phase_v3_selective_ssm.config import DataCfg
from .config import TrainCfg
from .teacher import AutoGateModel
from .annealing import anneal_coeff
from .contrastive_gate import contrastive_loss
from .future_relevance import future_relevance_loss
from .distillation import teacher_gate_prob, distill_loss


def build_masks(batch, maxlen, device):
    """Per-position masks/labels: write_target (cue/rel=1, filler/distr=0), relevant, distractor,
    future-relevance label (cue+rel=1, distr=0) and its supervised mask (cue+events)."""
    B = len(batch)
    wtgt = torch.full((B, maxlen), -1.0, device=device)
    relevant = torch.zeros(B, maxlen, dtype=torch.bool, device=device)
    distractor = torch.zeros(B, maxlen, dtype=torch.bool, device=device)
    future = torch.full((B, maxlen), -1.0, device=device)
    for i, e in enumerate(batch):
        wtgt[i, 0] = 1.0                       # cue is a write target
        future[i, 0] = 1.0                     # cue is future-relevant
        for k, pos in enumerate(e["event_pos"]):
            rel = e["event_relevant"][k]
            wtgt[i, pos] = 1.0 if rel else 0.0
            future[i, pos] = 1.0 if rel else 0.0
            (relevant if rel else distractor)[i, pos] = True
        # filler positions default wtgt stays where set; set remaining event-free non-probe to 0
    # filler → 0 for write target: any position that is not cue/event/probe/pad
    return wtgt, relevant, distractor, future


def train_arm(model, arm, vocab, cfg: TrainCfg, mode_schedule="staged", dcfg=DataCfg(),
              teacher=None, device="cpu", label_noise=None):
    """label_noise: optional dict for controls (e.g. randomize teacher / shuffle future labels)."""
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    model.train()
    rng = torch.Generator().manual_seed(cfg.seed + 1)
    total_main = sum(s for _, s in cfg.stages)
    total = total_main + cfg.post_anneal_steps
    step_global = 0
    stages = cfg.stages + [(cfg.stages[-1][0], cfg.post_anneal_steps)]
    for si, (dist, steps) in enumerate(stages):
        data = D.generate(vocab, dcfg, dist, 400, cfg.seed * 100 + si)
        n = len(data)
        for _ in range(steps):
            idx = torch.randint(0, n, (cfg.batch_size,), generator=rng).tolist()
            batch = [data[i] for i in idx]
            ids, wtgt0, probe_pos, focus = D.collate(batch, vocab.PAD, device)
            maxlen = ids.shape[1]
            wtgt, relevant, distractor, future = build_masks(batch, maxlen, device)
            # filler = non-pad, non-probe, wtgt still -1  → set to 0 (skip target)
            nonpad = ids != vocab.PAD
            is_probe = torch.zeros_like(nonpad); is_probe[torch.arange(ids.shape[0]), probe_pos] = True
            filler = nonpad & ~is_probe & (wtgt < 0)
            wtgt = torch.where(filler, torch.zeros_like(wtgt), wtgt)

            gate = model.gate(ids)                          # [B,N,H]
            logits, feats = model(ids, probe_pos, gate=gate)
            loss = F.cross_entropy(logits, focus)
            gm = gate.mean(-1)                              # [B,N]
            sup = wtgt >= 0
            frac = step_global / max(1, total_main)         # progress through the annealed portion

            if arm == "A_supervised_teacher":
                loss = loss + cfg.lambda_gate * F.binary_cross_entropy(gm[sup].clamp(1e-4, 1 - 1e-4), wtgt[sup])
            elif arm == "B_annealed":
                c = anneal_coeff(mode_schedule, frac)
                if c > 0 and sup.any():
                    loss = loss + c * cfg.lambda_gate * F.binary_cross_entropy(gm[sup].clamp(1e-4, 1 - 1e-4), wtgt[sup])
            elif arm == "C_distillation":
                if teacher is not None and frac < 1.0:       # distill during annealed portion, then E2E
                    tp = teacher_gate_prob(teacher, ids)
                    if label_noise == "randomize_teacher":
                        tp = tp[torch.randperm(tp.shape[0], generator=rng)]
                    loss = loss + cfg.lambda_distill * distill_loss(model.gate_logit(ids), tp)
            elif arm == "D_future_relevance":
                fmask = future >= 0
                flab = future.clone()
                if label_noise == "shuffle_future":
                    perm = torch.randperm(fmask.numel(), generator=rng).reshape(fmask.shape)
                    flab = torch.gather(flab.reshape(-1), 0, perm.reshape(-1)).reshape(fmask.shape)
                loss = loss + cfg.lambda_gate * future_relevance_loss(gm, flab.clamp(0, 1), fmask)
            elif arm == "E_contrastive":
                loss = loss + cfg.lambda_contrastive * contrastive_loss(gm, relevant, distractor, cfg.contrastive_margin)
            # F_e2e_scratch: focus CE only

            if model.gate_type == "sparse_budget":
                loss = loss + cfg.lambda_budget * gm.mean()
            st = feats["state"]
            loss = loss + cfg.lambda_stability * (st.pow(2).mean(-1).sqrt().mean() - 1.0).pow(2)

            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
            step_global += 1
    model.eval()
    return {"final_loss": float(loss.item())}


def build_model(vocab, gate_type="sigmoid", seed=0):
    torch.manual_seed(seed)
    return AutoGateModel(vocab.size, gate_type=gate_type)
