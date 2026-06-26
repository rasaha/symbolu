"""Symbol-U augmentations, made CAUSAL so they can sit on the LM-loss path
without leaking future tokens. Reuses only the generic pointwise typed heads
and the Shannon-entropy helper from symbolu_neural.modules (no phase/JEPA/CSR).

Causality notes (the central correctness requirement of this experiment):
- Typed heads are pointwise on h_t  -> causal-safe.
- Entropy is per-position from per-position distributions -> causal-safe.
- Refinement uses CAUSAL self-attention (is_causal) -> causal-safe. (The
  generic EntropyGatedRefinementCore in symbolu_neural.modules uses a
  *bidirectional* TransformerEncoderLayer and is therefore deliberately NOT
  reused here — it would leak the future on a next-token task.)
"""
from __future__ import annotations

from typing import Dict

import torch
import torch.nn as nn
import torch.nn.functional as F

from .backbone import CausalBlock
from ..modules.typed_heads import VrittiHead, AspectHead, GunaHead, KoshaHead
from ..modules.entropy import shannon_entropy


class TypedHeadBank(nn.Module):
    """Per-position Vritti/aspect/Guna/Kosha heads on hidden states (probes)."""

    def __init__(self, d: int):
        super().__init__()
        self.vritti = VrittiHead(d)
        self.aspect = AspectHead(d)
        self.guna = GunaHead(d)
        self.kosha = KoshaHead(d)

    def forward(self, h: torch.Tensor) -> Dict[str, torch.Tensor]:
        return {"log_p_v": self.vritti(h), "log_p_w": self.aspect(h),
                "log_p_g": self.guna(h), "log_p_k": self.kosha(h)}

    @staticmethod
    def entropies(out: Dict[str, torch.Tensor]) -> torch.Tensor:
        """Per-position [B,L,3] entropy vector (H_D over aspect, H_G, H_K)."""
        H_D = shannon_entropy(out["log_p_w"])
        H_G = shannon_entropy(out["log_p_g"])
        H_K = shannon_entropy(out["log_p_k"])
        return torch.stack([H_D, H_G, H_K], dim=-1)        # [B,L,3]


class CausalEntropyRefinement(nn.Module):
    """Entropy-gated, ACT-style causal refinement of the hidden state.

    At each of up to `max_steps`, a shared CAUSAL block updates the state; a
    per-position halting unit (conditioned on the symbolic entropy vector)
    decides how much of each step to keep (adaptive compute). Output is a
    residual added to the input hidden state, so the LM head sees a refined h.
    The original Symbol-U EQ-F3 tau/H barrier energy is intentionally omitted
    (it diverges as H->0); a ponder cost regularizes compute instead.
    """

    def __init__(self, d: int, n_heads: int, d_ff: int, max_steps: int = 3):
        super().__init__()
        self.max_steps = max_steps
        self.block = CausalBlock(d, n_heads, d_ff)
        self.halt = nn.Linear(d + 3, 1)                    # entropy-conditioned

    def forward(self, h: torch.Tensor, entropy_vec: torch.Tensor):
        B, L, d = h.shape
        acc = h.new_zeros(B, L)
        out = h.new_zeros(B, L, d)
        n_upd = h.new_zeros(B, L)
        state = h
        for _ in range(self.max_steps):
            state = self.block(state)
            p = torch.sigmoid(self.halt(torch.cat([state, entropy_vec], -1))).squeeze(-1)
            still = (acc < 0.99).float()
            contrib = p * still
            out = out + contrib.unsqueeze(-1) * state
            acc = acc + contrib
            n_upd = n_upd + still
        refined = h + out                                  # residual
        return refined, {"ponder_cost": n_upd.mean()}


class CausalPrefixMemory(nn.Module):
    """Causal 'deferred insight' surrogate: a readiness-gated prefix summary.

    At position t it reads ONLY a causal cumulative (decayed) mean of past value
    projections (strictly <= t), so it never leaks the future. A readiness gate
    (sigmoid over the entropy vector) scales how much memory is injected. This is
    a causal stand-in for the Deferred Insight Engine on the LM path; the full
    episodic store is generation-time only.
    """

    def __init__(self, d: int, decay: float = 0.95):
        super().__init__()
        self.decay = decay
        self.val = nn.Linear(d, d)
        self.readiness = nn.Linear(3, 1)

    def forward(self, h: torch.Tensor, entropy_vec: torch.Tensor):
        B, L, d = h.shape
        v = self.val(h)
        # causal decayed prefix mean (exclusive of current pos to be safe)
        mem = torch.zeros_like(v)
        run = h.new_zeros(B, d)
        for t in range(L):
            mem[:, t] = run
            run = self.decay * run + (1 - self.decay) * v[:, t]
        R = torch.sigmoid(self.readiness(entropy_vec))     # [B,L,1]
        return h + R * mem, {"readiness": R.mean()}
