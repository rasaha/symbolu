"""
selective_complex_phase.py — EXPERIMENTAL Phase v3 core: a fully selective complex
state-space memory. Retention (A_t), write (B_t) and read (C_t) are all input-dependent
functions of the current token h_t only (causal). O(N), streaming, bounded-state.

    A_t = γ_t · e^{i·ω_t}                         (input-dependent retention, §4)
    S_t = A_t ⊙ S_{t-1} + B_t ⊙ (k_t ⊙ v_t)       (input-dependent write, §5)
    R_t = γ_t · R_{t-1} + B_t · a_k               (amplitude accumulator, detached norm)
    o_t = C_t ⊙ Re(q_t ⊙ S_t) / Z_t               (input-dependent read, §6)

Controls are per-head ([B,N,H,1], broadcast over Dh). The phase encoding (bounded phase
map φ = π·sin(·), complex k/v, amplitude a_q/a_k, normalizer clamp + detach) is preserved
from v1/v2 (§8). This module does NOT import or modify the frozen v1 or the v2 package.
"""
from __future__ import annotations

import math
from typing import Optional

import torch
import torch.nn as nn
from torch import Tensor

from .config import PhaseV3Config
from .scan import selective_scan
from .state import PhaseV3State, PhaseV3Output


def _apply_mode_real(x: Tensor, mode: str, fixed: float, perm: Optional[Tensor]):
    if mode == "learned":
        return x
    if mode == "fixed":
        return torch.full_like(x, fixed)
    if mode == "forced_one":
        return torch.ones_like(x)
    if mode == "forced_zero":
        return torch.zeros_like(x)
    if mode == "shuffled":
        return x[perm]
    if mode == "detached":
        return x.detach()
    raise ValueError(mode)


class SelectiveComplexPhaseV3(nn.Module):
    def __init__(self, config: PhaseV3Config):
        super().__init__()
        self.config = config
        D, H = config.embed_dim, config.num_heads
        self.embed_dim, self.num_heads, self.head_dim = D, H, config.head_dim
        Dh = self.head_dim
        self.norm = nn.LayerNorm(D, eps=config.layernorm_eps)
        # preserved phase projections
        self.W_phi_k = nn.Linear(D, D, bias=False)
        self.W_a_k = nn.Linear(D, D, bias=False)
        self.W_v = nn.Linear(D, D, bias=False)
        self.W_phi_q = nn.Linear(D, D, bias=False)
        self.W_a_q = nn.Linear(D, D, bias=False)
        # input-dependent controls (per head)
        self.W_gamma = nn.Linear(D, H)
        self.W_omega = nn.Linear(D, H)
        self.W_B = nn.Linear(D, H)
        self.W_C = nn.Linear(D, H)
        self.W_fuse = nn.Linear(D, D, bias=False)
        self.reset_parameters()

    def reset_parameters(self):
        cfg = self.config
        for lin in (self.W_phi_q, self.W_phi_k):
            nn.init.uniform_(lin.weight, -1.0, 1.0)
        for lin in (self.W_a_q, self.W_a_k, self.W_v, self.W_fuse):
            nn.init.normal_(lin.weight, mean=0.0, std=0.02)
        for lin in (self.W_gamma, self.W_omega, self.W_B, self.W_C):
            nn.init.normal_(lin.weight, std=0.02)
            nn.init.zeros_(lin.bias)
        # bias γ toward long memory: solve σ(b_γ) = (γ0-γmin)/(γmax-γmin)
        t = (cfg.initial_gamma - cfg.gamma_min) / (cfg.gamma_max - cfg.gamma_min)
        t = min(max(t, 1e-4), 1 - 1e-4)
        with torch.no_grad():
            self.W_gamma.bias.fill_(math.log(t / (1 - t)))
            self.W_B.bias.fill_(cfg.write_bias_init)     # neutral, not strongly negative
            self.W_C.bias.fill_(cfg.read_bias_init)

    # ---- projections (preserved phase encoding) ----
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
            phi_q = math.pi * torch.sin(phi_q_raw)
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_q, phi_k = phi_q_raw, phi_k_raw
        return phi_q.float(), a_q.float(), phi_k.float(), a_k.float(), v.float()

    # ---- input-dependent controls A_t, B_t, C_t ----
    def _controls(self, x_norm, overrides: Optional[dict] = None):
        cfg = self.config
        B, N, _ = x_norm.shape
        H = self.num_heads
        ov = overrides or {}
        perm = torch.randperm(B, device=x_norm.device)

        # γ_t ∈ [γmin, γmax]
        if cfg.input_dependent_retention:
            gamma = cfg.gamma_min + (cfg.gamma_max - cfg.gamma_min) * torch.sigmoid(self.W_gamma(x_norm))
        else:
            gamma = torch.full((B, N, H), cfg.fixed_gamma, device=x_norm.device)
        gamma = _apply_mode_real(gamma, ov.get("gamma_mode", cfg.gamma_mode), cfg.fixed_gamma, perm)

        # ω_t ∈ [-ωmax, ωmax]
        if cfg.input_dependent_retention and cfg.use_omega:
            omega = cfg.omega_max * torch.tanh(self.W_omega(x_norm))
        else:
            omega = torch.zeros((B, N, H), device=x_norm.device)
        omega = _apply_mode_real(omega, ov.get("omega_mode", cfg.omega_mode), 0.0, perm)

        # B_t, C_t ∈ [0,1]
        if cfg.input_dependent_write:
            Bt = torch.sigmoid(self.W_B(x_norm))
        else:
            Bt = torch.full((B, N, H), cfg.fixed_write, device=x_norm.device)
        Bt = _apply_mode_real(Bt, ov.get("b_mode", cfg.b_mode), cfg.fixed_write, perm)

        if cfg.input_dependent_read:
            Ct = torch.sigmoid(self.W_C(x_norm))
        else:
            Ct = torch.full((B, N, H), cfg.fixed_read, device=x_norm.device)
        Ct = _apply_mode_real(Ct, ov.get("c_mode", cfg.c_mode), cfg.fixed_read, perm)

        # build complex A_t = γ e^{iω}; apply joint a_mode override
        A = torch.polar(gamma, omega)                      # [B,N,H] complex
        a_mode = ov.get("a_mode", cfg.a_mode)
        if a_mode == "fixed":
            A = torch.polar(torch.full_like(gamma, cfg.fixed_gamma), torch.zeros_like(omega))
            gamma = torch.full_like(gamma, cfg.fixed_gamma)
        elif a_mode == "shuffled":
            A = A[perm]; gamma = gamma[perm]
        elif a_mode == "detached":
            A = A.detach(); gamma = gamma.detach()
        return A, gamma, Bt, Ct

    def forward(self, x: Tensor, *, initial_state: Optional[PhaseV3State] = None,
                return_state: bool = False, return_features: bool = False,
                return_diagnostics: bool = False, overrides: Optional[dict] = None):
        B, N, D = x.shape
        assert D == self.embed_dim
        H, Dh = self.num_heads, self.head_dim
        orig_dtype = x.dtype
        residual = x
        x_norm = self.norm(x)
        phi_q, a_q, phi_k, a_k, v = self._project(x_norm)
        A, gamma, Bt, Ct = self._controls(x_norm, overrides)
        A_e = A.unsqueeze(-1)                # [B,N,H,1] complex
        g_e = gamma.unsqueeze(-1)            # [B,N,H,1] real
        B_e = Bt.unsqueeze(-1)              # [B,N,H,1]
        C_e = Ct.unsqueeze(-1)              # [B,N,H,1]

        k_phasor = torch.polar(a_k, -phi_k)
        v_complex = torch.complex(v, torch.zeros_like(v))
        u_S = (k_phasor * v_complex) * B_e            # selective write into complex state
        u_R = a_k * B_e                               # amplitude accumulator input

        prevS = None if initial_state is None else initial_state.complex_memory[:, 0]
        prevR = None if initial_state is None else initial_state.amplitude_sum[:, 0]
        S = selective_scan(A_e, u_S, prevS, chunk=self.config.chunk)          # [B,N,H,Dh] complex
        R = selective_scan(g_e.to(u_R.dtype), u_R, prevR, chunk=self.config.chunk)  # real

        q_phasor = torch.polar(a_q, phi_q)
        raw_o = (q_phasor * S).real                   # [B,N,H,Dh]
        Z = (a_q * R).clamp(min=self.config.denom_eps)
        if self.config.detach_denominator:
            Z = Z.detach()
        raw_o = raw_o / Z
        sel_o = C_e * raw_o                            # input-dependent selective read

        o_flat = sel_o.reshape(B, N, D)
        out = self.W_fuse(o_flat) * self.config.aux_scale
        if orig_dtype != torch.float32:
            out = out.to(orig_dtype)
        y = out + residual

        if not (return_state or return_features or return_diagnostics):
            return y
        state = feats = diag = None
        if return_state:
            state = PhaseV3State(
                complex_memory=S[:, -1].unsqueeze(1),
                amplitude_sum=R[:, -1].unsqueeze(1),
                position=(0 if initial_state is None else initial_state.position) + N)
        if return_features:
            feats = {
                "state": torch.cat([S.real, S.imag], dim=-1).reshape(B, N, 2 * D),
                "raw_readout": raw_o.reshape(B, N, D),
                "selective_readout": sel_o.reshape(B, N, D),
                "fused": y,
            }
        if return_diagnostics:
            with torch.no_grad():
                snorm = S.abs().pow(2).sum(dim=-1).sqrt()          # [B,N,H]
                diag = {
                    "write_rate_mean": Bt.mean().reshape(()),
                    "read_rate_mean": Ct.mean().reshape(()),
                    "write_rate_per_head": Bt.mean(dim=(0, 1)),     # [H]
                    "read_rate_per_head": Ct.mean(dim=(0, 1)),      # [H]
                    "write_rate_per_pos": Bt.mean(dim=(0, 2)),      # [N]
                    "gamma_mean": gamma.mean().reshape(()),
                    "gamma_per_head": gamma.mean(dim=(0, 1)),       # [H]
                    "omega_abs_mean": A.angle().abs().mean().reshape(()),
                    "state_norm_per_pos": snorm.mean(dim=(0, 2)),   # [N]
                    "state_norm_per_head": snorm.mean(dim=(0, 1)),  # [H]
                }
        return PhaseV3Output(output=y, state=state, features=feats, diagnostics=diag)

    def step(self, token_t: Tensor, previous_state: Optional[PhaseV3State] = None):
        if token_t.dim() == 2:
            token_t = token_t.unsqueeze(1)
        assert token_t.shape[1] == 1
        out = self.forward(token_t, initial_state=previous_state, return_state=True)
        return out.output[:, 0], out.state

    def effective_horizon(self, x: Tensor):
        """Per-head effective retention horizon 1/(1-mean γ_t) (§4)."""
        with torch.no_grad():
            _, gamma, _, _ = self._controls(self.norm(x))
            g = gamma.mean(dim=(0, 1)).clamp(max=1 - 1e-6)          # [H]
            return (1.0 / (1.0 - g))

    def state_bytes(self, B: int = 1) -> int:
        H, Dh = self.num_heads, self.head_dim
        return B * self.config.num_banks * H * Dh * (8 + 4)
