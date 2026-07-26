"""
train.py — train a Phase variant so its recurrent state PRESERVES the distant focus
identity, then expose (frozen) states for the probe/evals.

FocusModel = token embedding → (optional small local window) → Phase variant →
focus-identity decoder. Training decodes focus_vendor from the Phase readout g at
fact-anchor positions (all of which are past the local window), forcing the
recurrence to carry the focus. Training modes (redesign §12):
  A  e2e         : focus-decode CE + write-budget regularizer only.
  B  gate_sup    : + auxiliary write-gate supervision (write the header, skip
                   distractors) — a research scaffold, NOT an inference oracle.
Write-budget reg: L_budget = (mean_write_rate - rho)^2 (§6).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from experiments.phase_guided_slots_v2.task_schema import VENDORS
from symbolu.phase_v2_experimental.multiscale_phase import build_variant
from symbolu.lightweight_phase.local_window import LocalWindowAttention
from .focus_data import FocusExample

N_VENDOR = len(VENDORS)


@dataclass
class TrainCfg:
    steps: int = 500
    batch_size: int = 16
    lr: float = 1e-3
    rho: float = 0.10          # write-budget target
    lambda_budget: float = 0.3
    mode: str = "e2e"          # e2e | gate_sup
    lambda_gate: float = 0.5
    local_window: int = 8      # small local encoder
    seed: int = 0


class FocusModel(nn.Module):
    def __init__(self, variant_name, vocab_size, embed_dim=96, num_heads=4,
                 local_window=8, **variant_kw):
        super().__init__()
        self.variant_name = variant_name
        self.embed = nn.Embedding(vocab_size, embed_dim)
        self.pos = nn.Embedding(8192, embed_dim)
        self.local = LocalWindowAttention(embed_dim, num_heads, local_window)
        self.phase = build_variant(variant_name, embed_dim, num_heads, **variant_kw)
        self.decoder = nn.Linear(embed_dim, N_VENDOR)   # focus-identity decoder
        nn.init.normal_(self.embed.weight, std=0.02)
        nn.init.normal_(self.pos.weight, std=0.02)

    def encode(self, ids, gate_override=None):
        N = ids.shape[1]
        pos = torch.arange(N, device=ids.device).clamp(max=8191)
        x = self.embed(ids) + self.pos(pos).unsqueeze(0)
        h = self.local(x, return_residual_add=True)
        if gate_override is not None and self.variant_name != "V1":
            g = self.phase.readout(h, gate_override=gate_override)
        else:
            g = self.phase.readout(h)          # global Phase readout [B,N,D]
        return h, g

    def write_rates(self, ids):
        if self.variant_name == "V1":
            return None
        N = ids.shape[1]
        pos = torch.arange(N, device=ids.device).clamp(max=8191)
        x = self.embed(ids) + self.pos(pos).unsqueeze(0)
        h = self.local(x, return_residual_add=True)
        d = self.phase(h, return_diagnostics=True).diagnostics
        return d


def collate(batch: List[FocusExample], pad_id, device):
    maxlen = max(len(e.tokens) for e in batch)
    B = len(batch)
    ids = torch.full((B, maxlen), pad_id, dtype=torch.long)
    focus = torch.zeros(B, dtype=torch.long)
    for i, e in enumerate(batch):
        ids[i, :len(e.tokens)] = torch.tensor(e.tokens)
        focus[i] = e.focus_vendor_id
    return ids.to(device), focus.to(device), batch


def _gate_target(model, ids, batch, device):
    """Header positions → write 1; distractor anchors → write 0; others ignored."""
    B, N = ids.shape
    H = model.phase.num_heads
    tgt = torch.full((B, N), -1.0, device=device)   # -1 = ignore
    for i, e in enumerate(batch):
        tgt[i, :e.header_end + 1] = 1.0              # focus header → write
        for p, rel in zip(e.anchor_pos, e.anchor_relevant):
            if p < N:
                tgt[i, p] = 1.0 if rel else 0.0      # relevant→write, distractor→skip
    return tgt


def train_focus(variant_name, gen_fn, pad_id, cfg: TrainCfg, vocab_size,
                embed_dim=96, num_heads=4, device="cpu", **variant_kw):
    torch.manual_seed(cfg.seed)
    model = FocusModel(variant_name, vocab_size, embed_dim, num_heads,
                       local_window=cfg.local_window, **variant_kw)
    rng = torch.Generator().manual_seed(cfg.seed + 1)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    model.train()
    data = gen_fn()
    n = len(data)
    log = []
    for step in range(cfg.steps):
        idx = torch.randint(0, n, (cfg.batch_size,), generator=rng).tolist()
        b = [data[i] for i in idx]
        ids, focus, batch = collate(b, pad_id, device)
        h, g = model.encode(ids)
        # decode focus from g at each anchor (all past the local window); batched CE
        bi, pi, yi = [], [], []
        for i, e in enumerate(batch):
            for p in e.anchor_pos:
                if p < ids.shape[1]:
                    bi.append(i); pi.append(p); yi.append(focus[i].item())
        if bi:
            gp = g[torch.tensor(bi, device=device), torch.tensor(pi, device=device)]  # [K,D]
            lg = model.decoder(gp)                                                     # [K,N_VENDOR]
            loss = F.cross_entropy(lg, torch.tensor(yi, device=device))
        else:
            loss = torch.zeros((), device=device)
        # write-budget regularizer + optional gate supervision — single cheap gate pass
        if variant_name != "V1":
            w_hn = model.phase.gate_values(h)          # [B,N,H] (reuses local rep h)
            w = w_hn.mean(-1)                            # [B,N]
            loss = loss + cfg.lambda_budget * (w.mean() - cfg.rho) ** 2
            if cfg.mode == "gate_sup":
                tgt = _gate_target(model, ids, batch, device)
                m = tgt >= 0
                if m.any():
                    loss = loss + cfg.lambda_gate * F.binary_cross_entropy(
                        w[m].clamp(1e-4, 1 - 1e-4), tgt[m])
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if (step + 1) % 100 == 0:
            log.append({"step": step + 1, "loss": loss.item()})
    model.eval()
    return model, log
