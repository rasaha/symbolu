"""
matcher_train.py — train the matcher gate with ranking-based objectives (§ study discipline).

L = L_decode + λ1·L_pairwise(s) + λ2·L_event(e) + λ3·L_write_budget (+ λ4·L_align)

Recurrence unchanged; only the gate is the matcher. Decode uses the existing Phase readout at
the probe. Data may be soft (v3 dataset) or hard-negative (frequency-matched repeated
distractor). Everything else (curriculum, seeds, budget, decoder) matches the other arms.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from experiments.phase_v3_selective_ssm import dataset as D
from experiments.phase_v3_selective_ssm.config import DataCfg
from .config import TrainCfg
from .train import build_masks
from .hard_dataset import generate_hard
from .matcher_losses import pairwise_rank, event_vs_filler, alignment


def train_matcher(model, vocab, cfg: TrainCfg, dcfg=DataCfg(), hard=False, use_align=True,
                  lambda_rank=1.0, lambda_event=0.5, lambda_budget=0.05, lambda_align=0.3,
                  device="cpu"):
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    model.train()
    rng = torch.Generator().manual_seed(cfg.seed + 1)
    stages = cfg.stages + [(cfg.stages[-1][0], cfg.post_anneal_steps)]
    gen = (lambda dist, n, s: generate_hard(vocab, dcfg, dist, n, s)) if hard else \
          (lambda dist, n, s: D.generate(vocab, dcfg, dist, n, s))
    for si, (dist, steps) in enumerate(stages):
        data = gen(dist, 400, cfg.seed * 100 + si); n = len(data)
        for _ in range(steps):
            idx = torch.randint(0, n, (cfg.batch_size,), generator=rng).tolist()
            batch = [data[i] for i in idx]
            ids, wt0, probe_pos, focus = D.collate(batch, vocab.PAD, device)
            maxlen = ids.shape[1]
            wtgt, relevant, distractor, future = build_masks(batch, maxlen, device)
            nonpad = ids != vocab.PAD
            is_probe = torch.zeros_like(nonpad); is_probe[torch.arange(ids.shape[0]), probe_pos] = True
            is_cue = torch.zeros_like(nonpad); is_cue[:, 0] = True
            event = relevant | distractor
            filler = nonpad & ~is_probe & ~is_cue & ~event

            logits, feats = model(ids, probe_pos)                    # decode via gate=matcher.logit
            loss = F.cross_entropy(logits, focus)
            s = model.match_score(ids)                                # [B,N]
            loss = loss + lambda_rank * pairwise_rank(s, relevant, distractor, margin=0.5)
            z_f, z_h, e_logit = model.matcher_projections(ids)
            loss = loss + lambda_event * event_vs_filler(e_logit, event, filler)
            loss = loss + lambda_budget * torch.sigmoid(model.gate_logit(ids)).mean()
            if use_align:
                loss = loss + lambda_align * alignment(z_f, z_h, relevant, distractor)
            st = feats["state"]
            loss = loss + cfg.lambda_stability * (st.pow(2).mean(-1).sqrt().mean() - 1.0).pow(2)
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    model.eval()
    return {"final_loss": float(loss.item())}
