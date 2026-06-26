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

    _HEAD_KEY = {"vritti": "log_p_v", "aspect": "log_p_w",
                 "guna": "log_p_g", "kosha": "log_p_k"}

    @staticmethod
    def entropies(out: Dict[str, torch.Tensor], control_heads=None) -> torch.Tensor:
        """Per-position [B,L,3] CONTROL entropy vector that gates refine/memory.

        control_heads selects which typed heads are allowed to drive control
        (head-role policy). None reproduces the original behavior exactly:
        [H_aspect, H_guna, H_kosha]. A staged policy of ("vritti","aspect") yields
        [H_vritti, H_aspect, 0] — Guna/Kosha are still computed (for supervision /
        diagnostics) but excluded from the control signal. Width is fixed at 3 so the
        gate layers are unchanged."""
        if control_heads is None:
            order = ["aspect", "guna", "kosha"]            # backward-compatible default
        else:
            order = [h for h in ("vritti", "aspect", "guna", "kosha")
                     if h in control_heads]
        zero = shannon_entropy(out["log_p_w"]) * 0.0
        slots = [shannon_entropy(out[TypedHeadBank._HEAD_KEY[h]]) for h in order[:3]]
        while len(slots) < 3:
            slots.append(zero)
        return torch.stack(slots, dim=-1)                  # [B,L,3]

    @staticmethod
    def per_head_entropy(out: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        return {f"H_{h}": shannon_entropy(out[k]).mean().detach()
                for h, k in TypedHeadBank._HEAD_KEY.items()}


class CausalEntropyRefinement(nn.Module):
    """Entropy-gated, ACT-style causal refinement of the hidden state.

    At each of up to `max_steps`, a shared CAUSAL block updates the state; a
    per-position halting unit (conditioned on the symbolic entropy vector)
    decides how much of each step to keep (adaptive compute). Output is a
    residual added to the input hidden state, so the LM head sees a refined h.
    The original Symbol-U EQ-F3 tau/H barrier energy is intentionally omitted
    (it diverges as H->0); a ponder cost regularizes compute instead.
    """

    def __init__(self, d: int, n_heads: int, d_ff: int, max_steps: int = 3,
                 min_strength: float = 0.1, residual_scale: float = 1.0,
                 fixed_steps: bool = False):
        super().__init__()
        self.max_steps = max_steps
        self.min_strength = float(min_strength)       # gate floor (cannot collapse to 0)
        self.residual_scale = float(residual_scale)   # fixed scale on the refinement delta
        self.fixed_steps = bool(fixed_steps)          # smoke mode: bypass ACT halting
        self.block = CausalBlock(d, n_heads, d_ff)
        self.halt = nn.Linear(d + 3, 1)               # entropy-conditioned
        nn.init.zeros_(self.halt.weight)              # start engaged: sigmoid(2)≈0.88
        nn.init.constant_(self.halt.bias, 2.0)

    def forward(self, h: torch.Tensor, entropy_vec: torch.Tensor):
        """Why the old version was a no-op: it accumulated the ABSOLUTE refined
        state gated by a halting prob, and `refined = h + out`. Training drove the
        gate -> 0 to suppress that ill-scaled perturbation, so Δh collapsed to ~0.

        Fix: accumulate gated *deltas* (block(state) - state) with a minimum-
        strength floor on the gate and a fixed residual scale, so the contribution
        cannot be optimized away to zero."""
        B, L, d = h.shape
        state = h
        gated = h.new_zeros(B, L, d)                  # accumulated gated delta
        raw = h.new_zeros(B, L, d)                     # ungated delta (diagnostic)
        halt_ps, gates = [], []
        for _ in range(self.max_steps):
            new = self.block(state)
            delta = new - state                        # refinement DELTA (residual)
            raw = raw + delta
            if self.fixed_steps:
                g = h.new_ones(B, L)
            else:
                p = torch.sigmoid(
                    self.halt(torch.cat([new, entropy_vec], -1))).squeeze(-1)
                g = self.min_strength + (1.0 - self.min_strength) * p   # floor
                halt_ps.append(p)
            gates.append(g)
            gated = gated + g.unsqueeze(-1) * delta
            state = new
        injected = self.residual_scale * gated
        refined = h + injected
        gate_mean = torch.stack(gates).mean()
        halt_p_mean = (torch.stack(halt_ps).mean() if halt_ps
                       else h.new_tensor(1.0))
        diag = {
            "ponder_cost": gate_mean,                  # mild compute penalty (keeps grad)
            "steps_used": float(self.max_steps),
            "halt_p_mean": halt_p_mean.detach(),
            "gate_mean": gate_mean.detach(),
            "residual_pre_gate_norm": raw.norm().detach(),
            "residual_post_gate_norm": injected.norm().detach(),
            "entropy_gate_mean": entropy_vec.mean().detach(),
            # differentiable handles for contribution / residual-reg losses:
            "halt_p_grad": halt_p_mean,                # mean halting prob (keeps grad)
            "resid_grad": injected.norm(),             # residual norm (keeps grad)
        }
        return refined, diag


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
        """Vectorized causal decayed prefix mean (same computation as the old
        O(L) python loop, no semantic change). mem[t] = sum_{s<t} (1-decay)
        decay^{t-1-s} v[s], strictly causal (excludes current position). Stable
        for L up to a few hundred (decay^{-t} stays bounded)."""
        B, L, d = h.shape
        v = self.val(h)
        t = torch.arange(L, device=h.device, dtype=h.dtype)
        dp = self.decay ** t                               # decay^t        [L]
        inv = self.decay ** (-t)                           # decay^{-t}     [L]
        run = (1.0 - self.decay) * dp.view(1, L, 1) * (v * inv.view(1, L, 1)).cumsum(1)
        mem = torch.zeros_like(run)
        mem[:, 1:] = run[:, :-1]                            # exclusive (strictly < t)
        R = torch.sigmoid(self.readiness(entropy_vec))     # [B,L,1]
        injected = R * mem
        return h + injected, {"readiness": R.mean().detach(),
                              "residual_norm": injected.norm().detach(),
                              # differentiable handles for contribution / residual-reg:
                              "readiness_grad": R.mean(),
                              "resid_grad": injected.norm()}
