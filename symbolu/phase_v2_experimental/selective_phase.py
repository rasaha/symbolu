"""
selective_phase.py — EXPERIMENTAL Phase v2 core: selective-write, bounded,
multi-timescale complex-phasor recurrence. O(N), streaming, causal, no N×N tensor.

Per head, per bank b:
    S_t^{(b)} = γ_b · S_{t-1}^{(b)} + w_t · (k_phasor_t ⊙ v_t)
    A_t^{(b)} = γ_b · A_{t-1}^{(b)} + w_t · a_{k,t}
    o_t^{(b)} = Re(q_phasor_t ⊙ S_t^{(b)}) / stopgrad(max(a_q ⊙ A_t^{(b)}, ε))
readout = W_fuse( concat_b o_t^{(b)} ) · aux_scale  (+ residual).

w_t = σ(W_w h_t) ∈ [0,1] is a learned, CAUSAL write gate (frozen v1 ≡ one bank,
γ=1, w_t≡1). The gate is what lets a rare focus token dominate a persistent (γ≈1)
bank instead of being diluted 1/N by dense accumulation.

This module does NOT import or modify the frozen symbolu.lightweight_phase.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

import torch
import torch.nn as nn
from torch import Tensor

from .config import PhaseV2Config


@dataclass
class PhaseV2State:
    complex_memory: Tensor   # [B, banks, H, Dh] complex64
    amplitude_sum: Tensor    # [B, banks, H, Dh] float32
    position: int

    def numel(self) -> int:
        return self.complex_memory.numel() + self.amplitude_sum.numel()

    def detach(self) -> "PhaseV2State":
        return PhaseV2State(self.complex_memory.detach(), self.amplitude_sum.detach(),
                            self.position)


@dataclass
class PhaseV2Output:
    output: Tensor
    state: Optional[PhaseV2State] = None
    diagnostics: Optional[Dict[str, Tensor]] = None


def _scan(g: Tensor, gamma: Optional[Tensor], prev: Optional[Tensor]) -> Tensor:
    """S_t = gamma * S_{t-1} + g_t over dim=1. g:[B,N,H,Dh]. gamma: scalar float or
    None (=1). prev:[B,H,Dh] or None."""
    B, N, H, Dh = g.shape
    if gamma is None:
        S = torch.cumsum(g, dim=1)
        if prev is not None:
            S = S + prev.unsqueeze(1)
        return S
    out = torch.empty_like(g)
    s = prev if prev is not None else torch.zeros(B, H, Dh, dtype=g.dtype, device=g.device)
    for t in range(N):
        s = gamma * s + g[:, t]
        out[:, t] = s
    return out


class SelectivePhaseV2(nn.Module):
    def __init__(self, config: PhaseV2Config):
        super().__init__()
        self.config = config
        D, H = config.embed_dim, config.num_heads
        self.embed_dim, self.num_heads, self.head_dim = D, H, config.head_dim
        self.num_banks = config.num_banks
        self.norm = nn.LayerNorm(D, eps=config.layernorm_eps)
        self.W_phi_k = nn.Linear(D, D, bias=False)
        self.W_a_k = nn.Linear(D, D, bias=False)
        self.W_v = nn.Linear(D, D, bias=False)
        self.W_phi_q = nn.Linear(D, D, bias=False)
        self.W_a_q = nn.Linear(D, D, bias=False)
        self.W_w = nn.Linear(D, H)                     # write gate (scalar per head)
        self.W_fuse = nn.Linear(self.num_banks * D, D, bias=False)
        # learned decay (V2-SD): one theta per (bank,head) mapped into [gmin,gmax]
        if config.learned_decay:
            target = (config.initial_gamma - config.gamma_min) / (config.gamma_max - config.gamma_min)
            target = min(max(target, 1e-4), 1 - 1e-4)
            theta0 = math.log(target / (1 - target))
            self.decay_theta = nn.Parameter(torch.full((self.num_banks, H), theta0))
        else:
            self.register_parameter("decay_theta", None)
        self.reset_parameters()

    def reset_parameters(self):
        for lin in (self.W_phi_q, self.W_phi_k):
            nn.init.uniform_(lin.weight, -1.0, 1.0)
        for lin in (self.W_a_q, self.W_a_k, self.W_v, self.W_fuse):
            nn.init.normal_(lin.weight, mean=0.0, std=0.02)
        nn.init.normal_(self.W_w.weight, std=0.02)
        nn.init.constant_(self.W_w.bias, self.config.gate_bias_init)

    # ---- decay per bank ----
    def bank_gamma(self, bank: int, device, dtype=torch.float32):
        cfg = self.config
        g = cfg.bank_gammas[bank]
        if cfg.learned_decay or g is None:
            gh = cfg.gamma_min + (cfg.gamma_max - cfg.gamma_min) * torch.sigmoid(self.decay_theta[bank])
            return gh.to(device=device, dtype=dtype)  # [H]
        return float(g)

    def _zero_state(self, B, device):
        H, Dh = self.num_heads, self.head_dim
        return PhaseV2State(
            complex_memory=torch.zeros(B, self.num_banks, H, Dh, dtype=torch.complex64, device=device),
            amplitude_sum=torch.zeros(B, self.num_banks, H, Dh, dtype=torch.float32, device=device),
            position=0)

    def _project(self, x_norm):
        B, N, _ = x_norm.shape
        H, Dh = self.num_heads, self.head_dim
        cfg = self.config

        def split(lin):
            return lin(x_norm).view(B, N, H, Dh)
        phi_q_raw, phi_k_raw = split(self.W_phi_q), split(self.W_phi_k)
        a_q = cfg.amp_floor + cfg.amp_scale * torch.sigmoid(split(self.W_a_q))
        a_k = cfg.amp_floor + cfg.amp_scale * torch.sigmoid(split(self.W_a_k))
        v = split(self.W_v)
        if cfg.bounded_phase:
            phi_q, phi_k = math.pi * torch.sin(phi_q_raw), math.pi * torch.sin(phi_k_raw)
        else:
            phi_q, phi_k = phi_q_raw, phi_k_raw
        return (phi_q.float(), a_q.float(), phi_k.float(), a_k.float(), v.float())

    def _gate(self, x_norm) -> Tensor:
        """Return w_t in [0,1], shape [B,N,H]. Causal (token-only)."""
        cfg = self.config
        logit = self.W_w(x_norm)                      # [B,N,H]
        if cfg.gate_mode == "forced_one":
            return torch.ones_like(logit)
        if cfg.gate_mode == "forced_zero":
            return torch.zeros_like(logit)
        if cfg.gate_mode == "random":
            return torch.rand_like(logit)
        w = torch.sigmoid(logit)
        if cfg.gate_mode == "detached":
            w = w.detach()
        return w

    def forward(self, x: Tensor, *, initial_state: Optional[PhaseV2State] = None,
                return_state: bool = False, return_diagnostics: bool = False,
                gate_override: Optional[Tensor] = None):
        B, N, D = x.shape
        assert D == self.embed_dim
        orig_dtype = x.dtype
        residual = x
        x_norm = self.norm(x)
        phi_q, a_q, phi_k, a_k, v = self._project(x_norm)
        w = self._gate(x_norm) if gate_override is None else gate_override   # [B,N,H]
        w_e = w.unsqueeze(-1)                                                # [B,N,H,1]

        k_phasor = torch.polar(a_k, -phi_k)
        v_complex = torch.complex(v, torch.zeros_like(v))
        kv = k_phasor * v_complex                       # [B,N,H,Dh] complex
        gated_kv = kv * w_e                             # selective write
        a_k_c = torch.complex(a_k, torch.zeros_like(a_k))
        gated_ak = a_k_c * w_e

        q_phasor = torch.polar(a_q, phi_q)
        o_banks = []
        S_last, A_last = [], []
        for b in range(self.num_banks):
            gamma = self.bank_gamma(b, x.device)
            gamma_t = gamma.view(1, 1, self.num_heads, 1) if torch.is_tensor(gamma) else gamma
            prevS = None if initial_state is None else initial_state.complex_memory[:, b]
            prevA = None if initial_state is None else torch.complex(
                initial_state.amplitude_sum[:, b], torch.zeros_like(initial_state.amplitude_sum[:, b]))
            S = _scan(gated_kv, gamma_t, prevS)
            A = _scan(gated_ak, gamma_t, prevA).real
            n_t = (q_phasor * S).real
            Z = (a_q * A).clamp(min=self.config.denom_eps)
            if self.config.detach_denominator:
                Z = Z.detach()
            o_banks.append((n_t / Z).reshape(B, N, D))
            S_last.append(S[:, -1]); A_last.append(A[:, -1])
        o = torch.cat(o_banks, dim=-1)                  # [B,N,banks*D]
        out = (self.W_fuse(o) * self.config.aux_scale)
        if orig_dtype != torch.float32:
            out = out.to(orig_dtype)
        y = out + residual

        if not (return_state or return_diagnostics):
            return y
        state = None
        if return_state:
            state = PhaseV2State(
                complex_memory=torch.stack(S_last, dim=1),
                amplitude_sum=torch.stack(A_last, dim=1),
                position=(0 if initial_state is None else initial_state.position) + N)
        diagnostics = None
        if return_diagnostics:
            with torch.no_grad():
                diagnostics = {
                    "write_rate_mean": w.mean().reshape(()),
                    "write_rate_per_pos": w.mean(dim=(0, 2)),      # [N]
                    "state_norm_per_bank": torch.stack(
                        [S_last[b].abs().pow(2).sum(dim=(-1, -2)).sqrt().mean() for b in range(self.num_banks)]),
                }
        return PhaseV2Output(output=y, state=state, diagnostics=diagnostics)

    def step(self, token_t: Tensor, previous_state: Optional[PhaseV2State] = None):
        if token_t.dim() == 2:
            token_t = token_t.unsqueeze(1)
        assert token_t.shape[1] == 1
        out = self.forward(token_t, initial_state=previous_state, return_state=True)
        return out.output[:, 0], out.state

    def state_bytes(self, B: int = 1) -> int:
        H, Dh = self.num_heads, self.head_dim
        return B * self.num_banks * H * Dh * (8 + 4)   # complex64 + float32
