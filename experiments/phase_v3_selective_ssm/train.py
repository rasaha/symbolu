"""
train.py — trainable focus model (token embed + Phase variant + focus-decode head) and
curriculum training with the §12 objectives and the three §11 supervision modes.

The model is deliberately minimal so the Phase state dynamics are the only long-range
mechanism: x_t = token_embed(t) + sinusoidal_pos(t), then the variant maps x → features;
focus identity is decoded from the (selective) Phase readout at the PROBE position. There
is no cross-token mixing outside the Phase recurrence, so any long-range focus retention
must come from the Phase state itself.

Supervision modes (§11):
    A_supervised : full auxiliary gate/retention/read supervision throughout.
    B_annealed   : auxiliary weight annealed 1→0 across curriculum stages (MAIN target).
    C_scratch    : no auxiliary supervision (end-to-end from scratch).
"""
from __future__ import annotations

import math
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu.phase_v3_experimental.variants import build_variant
from .config import EMBED_DIM, NUM_HEADS, NUM_ENTITIES, TrainCfg, DataCfg
from . import dataset as D


def sinusoidal(N, Dm, device):
    pos = torch.arange(N, device=device).float().unsqueeze(1)
    i = torch.arange(0, Dm, 2, device=device).float()
    div = torch.exp(-math.log(10000.0) * i / Dm)
    pe = torch.zeros(N, Dm, device=device)
    pe[:, 0::2] = torch.sin(pos * div)
    pe[:, 1::2] = torch.cos(pos * div)
    return pe


class FocusModel(nn.Module):
    def __init__(self, variant_name, vocab_size, embed_dim=EMBED_DIM, num_heads=NUM_HEADS,
                 num_entities=NUM_ENTITIES):
        super().__init__()
        self.variant_name = variant_name
        self.embed_dim = embed_dim
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.variant = build_variant(variant_name, embed_dim, num_heads)
        self.focus_head = nn.Linear(embed_dim, num_entities)
        nn.init.normal_(self.token_embed.weight, std=0.02)
        self.is_v3 = variant_name.startswith("V3")
        self.is_v2 = variant_name == "V2-S"

    def embed(self, ids):
        return self.token_embed(ids) + sinusoidal(ids.shape[1], self.embed_dim, ids.device).unsqueeze(0)

    def features(self, ids, overrides=None):
        x = self.embed(ids)
        return self.variant.features(x, overrides=overrides)

    def forward(self, ids, probe_pos, overrides=None):
        feats = self.features(ids, overrides=overrides)
        ar = torch.arange(ids.shape[0], device=ids.device)
        readout = feats["selective_readout"][ar, probe_pos]     # [B, D]
        logits = self.focus_head(readout)
        return logits, feats

    # ---- control signals for aux losses (v3 only) ----
    def v3_controls(self, ids):
        x = self.embed(ids)
        core = self.variant.core
        xn = core.norm(x)
        A, gamma, Bt, Ct = core._controls(xn)
        return gamma, Bt, Ct                                    # each [B,N,H]

    def v2_gate(self, ids):
        x = self.embed(ids)
        core = self.variant.core
        return core._gate(core.norm(x))                          # [B,N,H]


def _aux_losses(model, ids, wtgt, probe_pos, feats, cfg: TrainCfg):
    """§12 auxiliary losses. Returns dict of scalar tensors (0 for variants lacking a control)."""
    dev = ids.device
    zero = torch.zeros((), device=dev)
    out = {"write": zero, "retention": zero, "read": zero, "budget": zero, "stability": zero}
    sup = wtgt >= 0                                              # supervised (non-probe, non-pad) positions
    is_cue = torch.zeros_like(wtgt, dtype=torch.bool); is_cue[:, 0] = True
    is_filler = (wtgt == 0)

    if model.is_v3:
        gamma, Bt, Ct = model.v3_controls(ids)                  # [B,N,H]
        Bm = Bt.mean(-1)                                        # [B,N]
        # L_write: cue/relevant events (target 1) get higher B than filler/distractor (0)
        if sup.any():
            out["write"] = F.binary_cross_entropy(Bm[sup].clamp(1e-4, 1 - 1e-4), wtgt[sup])
        # L_budget: discourage dense writes
        out["budget"] = Bm.mean()
        # L_retention: cue retained long (γ→1), filler forgotten (γ↓) — §12 "important
        # state dimensions retain longer than filler".
        gm = gamma.mean(-1)
        ret = (1.0 - gm[:, 0]).mean()                       # push cue retention up
        if is_filler.any():
            ret = ret + gm[is_filler].mean()                # push filler retention down
        out["retention"] = ret
        # L_read: C_t high at probe (expose focus); modest elsewhere
        Cm = Ct.mean(-1)
        ar = torch.arange(ids.shape[0], device=dev)
        out["read"] = F.binary_cross_entropy(Cm[ar, probe_pos].clamp(1e-4, 1 - 1e-4),
                                             torch.ones(ids.shape[0], device=dev))
    elif model.is_v2:
        w = model.v2_gate(ids).mean(-1)
        if sup.any():
            out["write"] = F.binary_cross_entropy(w[sup].clamp(1e-4, 1 - 1e-4), wtgt[sup])
        out["budget"] = w.mean()

    # L_stability: keep phase state norm near unit (applies to any variant with a state)
    st = feats.get("state")
    if st is not None:
        norm = st.pow(2).mean(-1).sqrt().mean()
        out["stability"] = (norm - 1.0).pow(2)
    return out


def train_focus(model, vocab, cfg: TrainCfg, mode="B_annealed", dcfg: DataCfg = DataCfg(),
                device="cpu", log=None):
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    model.train()
    rng = torch.Generator().manual_seed(cfg.seed + 1)
    history = []
    for si, (dist, steps) in enumerate(cfg.stages):
        data = D.generate(vocab, dcfg, dist, 400, cfg.seed * 100 + si)
        n = len(data)
        if mode == "A_supervised":
            aw = 1.0
        elif mode == "B_annealed":
            aw = cfg.anneal_schedule[min(si, len(cfg.anneal_schedule) - 1)]
        else:                        # C_scratch
            aw = 0.0
        for step in range(steps):
            idx = torch.randint(0, n, (cfg.batch_size,), generator=rng).tolist()
            batch = [data[i] for i in idx]
            ids, wtgt, probe_pos, focus = D.collate(batch, vocab.PAD, device)
            logits, feats = model(ids, probe_pos)
            loss = F.cross_entropy(logits, focus)
            aux = _aux_losses(model, ids, wtgt, probe_pos, feats, cfg)
            loss = (loss + aw * (cfg.lambda_write * aux["write"]
                                 + cfg.lambda_retention * aux["retention"]
                                 + cfg.lambda_read * aux["read"])
                    + cfg.lambda_budget * aux["budget"]
                    + cfg.lambda_stability * aux["stability"])
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        history.append({"stage": si, "dist": dist, "aux_weight": aw, "loss": float(loss.item())})
        if log:
            log(f"  stage{si} d={dist} aw={aw:.2f} loss={loss.item():.3f}")
    model.eval()
    return history
