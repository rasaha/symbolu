"""
phase_core.py — Canonical Lightweight Phase Attention.

This is the small, auditable, dependency-light reference implementation of the
Phase write/read kernel specified in ``reference_equations.md``. It intentionally
does NOT contain: quadratic attention, Top-K retrieval, binding slots, auxiliary
losses, head-diversity losses, controllers, adaptive routing, or intent rotation.

Line-by-line correspondence to reference_equations.md is annotated in ``forward``.

Public surface:
    PhaseState              — typed recurrent state (complex_memory, amplitude_sum, position)
    PhaseOutput             — forward result bundle (output, state, diagnostics)
    LightweightPhaseAttention(nn.Module)
        .forward(x, *, initial_state=None, return_state=False, return_diagnostics=False)
        .step(token_t, previous_state)      — Stage 2 incremental API
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Union

from contextlib import nullcontext

import torch
import torch.nn as nn
from torch import Tensor

from .config import PhaseConfig
from .invariants import get_active_audit, register_shape, shape_audit


# ---------------------------------------------------------------------------
# Typed state and output containers
# ---------------------------------------------------------------------------
@dataclass
class PhaseState:
    """Recurrent Phase state carried across tokens/chunks.

    Shapes:
        complex_memory : [B, H, Dh]  complex64  — S_t (the phasor accumulator)
        amplitude_sum  : [B, H, Dh]  float32    — A_t (cumulative key amplitude)
        position       : int                    — number of tokens already consumed

    The state size is independent of sequence length N (INV-STATE-O).
    """

    complex_memory: Tensor
    amplitude_sum: Tensor
    position: int

    def numel(self) -> int:
        return self.complex_memory.numel() + self.amplitude_sum.numel()

    def detach(self) -> "PhaseState":
        return PhaseState(
            complex_memory=self.complex_memory.detach(),
            amplitude_sum=self.amplitude_sum.detach(),
            position=self.position,
        )

    def to(self, *args, **kwargs) -> "PhaseState":
        return PhaseState(
            complex_memory=self.complex_memory.to(*args, **kwargs),
            amplitude_sum=self.amplitude_sum.to(*args, **kwargs),
            position=self.position,
        )


@dataclass
class PhaseOutput:
    """Bundle returned when ``return_state`` or ``return_diagnostics`` is set."""

    output: Tensor
    state: Optional[PhaseState] = None
    diagnostics: Optional[Dict[str, Tensor]] = None


# ---------------------------------------------------------------------------
# The Phase core
# ---------------------------------------------------------------------------
class LightweightPhaseAttention(nn.Module):
    """O(N) complex phase attention — canonical reference (see reference_equations.md).

    Multi-head layout is explicit: internal tensors are [B, N, H, Dh] with D = H·Dh.
    The recurrent state (PhaseState) is [B, H, Dh] — one fixed-size complex vector
    per head, per batch element.
    """

    def __init__(self, config: PhaseConfig):
        super().__init__()
        self.config = config
        D, H = config.embed_dim, config.num_heads
        self.embed_dim = D
        self.num_heads = H
        self.head_dim = config.head_dim

        # Pre-norm (§1)
        self.norm = nn.LayerNorm(D, eps=config.layernorm_eps)

        # Key-side (§2): phase and amplitude projections + values
        self.W_phi_k = nn.Linear(D, D, bias=False)
        self.W_a_k = nn.Linear(D, D, bias=False)
        self.W_v = nn.Linear(D, D, bias=False)

        # Query-side (§4)
        self.W_phi_q = nn.Linear(D, D, bias=False)
        self.W_a_q = nn.Linear(D, D, bias=False)

        # Output projection (§6)
        self.W_out = nn.Linear(D, D, bias=False)
        self.dropout = nn.Dropout(config.dropout)

        # Decay parameters (§3 / Stage 3) --------------------------------
        self.decay_mode = config.decay_mode
        if config.decay_mode == "learned_per_head":
            # γ_h = γ_min + (γ_max − γ_min)·σ(θ_h). Initialize σ(θ)=target so that
            # γ starts at initial_gamma for every head.
            target = (config.initial_gamma - config.gamma_min) / (
                config.gamma_max - config.gamma_min
            )
            target = min(max(target, 1e-4), 1 - 1e-4)
            theta0 = math.log(target / (1.0 - target))
            self.decay_theta = nn.Parameter(torch.full((H,), theta0))
        else:
            self.register_parameter("decay_theta", None)

        self.reset_parameters()

    # ------------------------------------------------------------------
    def reset_parameters(self) -> None:
        # Deterministic, phase-diverse init for the phase projections; small
        # normal for amplitude/value/output. Uses the global RNG so callers can
        # make it reproducible with torch.manual_seed before construction.
        for lin in (self.W_phi_q, self.W_phi_k):
            nn.init.uniform_(lin.weight, -1.0, 1.0)
        for lin in (self.W_a_q, self.W_a_k, self.W_v, self.W_out):
            nn.init.normal_(lin.weight, mean=0.0, std=0.02)

    # ------------------------------------------------------------------
    def gamma_per_head(self, device, dtype=torch.float32) -> Optional[Tensor]:
        """Return per-head γ tensor [H] (float32) or None when decay is off."""
        cfg = self.config
        if cfg.decay_mode == "none":
            return None
        if cfg.decay_mode == "fixed_scalar":
            return torch.full((self.num_heads,), float(cfg.initial_gamma), device=device, dtype=dtype)
        if cfg.decay_mode == "fixed_per_head":
            # Log-space spread across [gamma_min, gamma_max] (short → long horizons).
            lin = torch.linspace(0.0, 1.0, self.num_heads, device=device, dtype=dtype)
            return cfg.gamma_min + (cfg.gamma_max - cfg.gamma_min) * lin
        if cfg.decay_mode == "learned_per_head":
            g = cfg.gamma_min + (cfg.gamma_max - cfg.gamma_min) * torch.sigmoid(self.decay_theta)
            return g.to(device=device, dtype=dtype)
        raise RuntimeError(f"unreachable decay_mode {cfg.decay_mode}")

    # ------------------------------------------------------------------
    def _project(self, x_norm: Tensor):
        """Compute (phi_q, a_q, phi_k, a_k, v) as [B, N, H, Dh] float32 tensors."""
        B, N, _ = x_norm.shape
        H, Dh = self.num_heads, self.head_dim
        cfg = self.config

        def split(lin):
            return lin(x_norm).view(B, N, H, Dh)

        phi_q_raw = split(self.W_phi_q)                 # §4
        phi_k_raw = split(self.W_phi_k)                 # §2
        a_q = cfg.amp_floor + cfg.amp_scale * torch.sigmoid(split(self.W_a_q))
        a_k = cfg.amp_floor + cfg.amp_scale * torch.sigmoid(split(self.W_a_k))
        v = split(self.W_v)                             # §2

        if cfg.bounded_phase:
            phi_q = math.pi * torch.sin(phi_q_raw)      # §4 / §2 bounded parameterization
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_q, phi_k = phi_q_raw, phi_k_raw

        # Always accumulate complex arithmetic in float32.
        return (
            phi_q.float(), a_q.float(), phi_k.float(), a_k.float(), v.float(),
        )

    # ------------------------------------------------------------------
    def _zero_state(self, B: int, device, dtype=torch.float32) -> PhaseState:
        H, Dh = self.num_heads, self.head_dim
        return PhaseState(
            complex_memory=torch.zeros(B, H, Dh, dtype=torch.complex64, device=device),
            amplitude_sum=torch.zeros(B, H, Dh, dtype=torch.float32, device=device),
            position=0,
        )

    # ------------------------------------------------------------------
    def forward(
        self,
        x: Tensor,
        *,
        initial_state: Optional[PhaseState] = None,
        return_state: bool = False,
        return_diagnostics: bool = False,
    ) -> Union[Tensor, PhaseOutput]:
        """Batched O(N) forward. See reference_equations.md for the line map."""
        B, N, D = x.shape
        assert D == self.embed_dim, f"expected embed_dim {self.embed_dim}, got {D}"
        orig_dtype = x.dtype
        residual = x

        # Reuse an already-active audit (e.g. from a test) instead of nesting,
        # so registered shapes are visible to the caller's audit.
        _audit_ctx = nullcontext(get_active_audit()) if get_active_audit() is not None else shape_audit(N)
        with _audit_ctx:
            x_norm = self.norm(x)                                   # §1
            phi_q, a_q, phi_k, a_k, v = self._project(x_norm)
            register_shape("phi_k", phi_k.shape)                    # [B,N,H,Dh] — never N×N
            register_shape("a_k", a_k.shape)

            # §2/§3 complex key phasor and KV
            k_phasor = torch.polar(a_k, -phi_k)                     # a_k·e^{-iφ_k}
            v_complex = torch.complex(v, torch.zeros_like(v))
            kv = k_phasor * v_complex                               # [B,N,H,Dh] complex

            gamma = self.gamma_per_head(x.device)                   # [H] or None

            # --- causal state accumulation S_t (§3) -----------------
            prev_S = None if initial_state is None else initial_state.complex_memory
            prev_A = None if initial_state is None else initial_state.amplitude_sum
            S = _causal_scan(kv, gamma, prev_S)                     # [B,N,H,Dh] complex
            register_shape("S", S.shape)

            # --- amplitude accumulation A_t (§5) --------------------
            a_k_c = torch.complex(a_k, torch.zeros_like(a_k))
            A = _causal_scan(a_k_c, gamma, None if prev_A is None
                             else torch.complex(prev_A, torch.zeros_like(prev_A))).real
            register_shape("A", A.shape)

            # --- readout (§5) ---------------------------------------
            q_phasor = torch.polar(a_q, phi_q)                      # a_q·e^{+iφ_q}
            n_t = (q_phasor * S).real                               # Re(q ⊙ S)
            Z = (a_q * A).clamp(min=self.config.denom_eps)          # max(a_q⊙A, ε)
            if self.config.detach_denominator:
                Z = Z.detach()                                      # stopgrad
            o_t = n_t / Z                                           # [B,N,H,Dh]

            # --- output projection + residual (§6) ------------------
            o = o_t.reshape(B, N, D)
            if orig_dtype != torch.float32:
                o = o.to(orig_dtype)
            out = self.dropout(self.W_out(o)) * self.config.aux_scale
            y = out + residual

        if not (return_state or return_diagnostics):
            return y

        state = None
        if return_state:
            state = PhaseState(
                complex_memory=S[:, -1],       # [B,H,Dh]
                amplitude_sum=A[:, -1],         # [B,H,Dh]
                position=(0 if initial_state is None else initial_state.position) + N,
            )
        diagnostics = None
        if return_diagnostics:
            diagnostics = self._diagnostics(phi_q, phi_k, a_q, a_k, S, o_t)
        return PhaseOutput(output=y, state=state, diagnostics=diagnostics)

    # ------------------------------------------------------------------
    def step(self, token_t: Tensor, previous_state: Optional[PhaseState] = None):
        """Stage-2 incremental API: consume one token, return (output_t, next_state).

        Args:
            token_t: [B, D] or [B, 1, D]
            previous_state: PhaseState or None (fresh start)
        Returns:
            (output_t [B, D], next_state PhaseState)
        """
        if token_t.dim() == 2:
            token_t = token_t.unsqueeze(1)                          # [B,1,D]
        assert token_t.shape[1] == 1, "step consumes exactly one token"
        out = self.forward(token_t, initial_state=previous_state, return_state=True)
        return out.output[:, 0], out.state

    # ------------------------------------------------------------------
    def _diagnostics(self, phi_q, phi_k, a_q, a_k, S, o_t) -> Dict[str, Tensor]:
        with torch.no_grad():
            # Mean resultant length R_k per head (phase concentration; 0=uniform).
            zk = torch.exp(1j * phi_k.to(torch.float32)).mean(dim=-1)   # [B,N,H]
            R_k = zk.abs().mean(dim=(0, 1))                              # [H]
            zq = torch.exp(1j * phi_q.to(torch.float32)).mean(dim=-1)
            R_q = zq.abs().mean(dim=(0, 1))
            return {
                "R_k": R_k,
                "R_q": R_q,
                "a_k_mean": a_k.mean().reshape(()),
                "a_q_mean": a_q.mean().reshape(()),
                "state_abs_mean": S.abs().mean().reshape(()),
                "output_abs_mean": o_t.abs().mean().reshape(()),
            }


# ---------------------------------------------------------------------------
# Causal scan helper (shared by state and amplitude accumulation)
# ---------------------------------------------------------------------------
def _causal_scan(
    kv: Tensor,
    gamma: Optional[Tensor],
    prev: Optional[Tensor],
) -> Tensor:
    """Compute S_t = γ·S_{t-1} + kv_t for t=1..N over dim=1.

    Args:
        kv:    [B, N, H, Dh] (complex or real)
        gamma: [H] float32 per-head decay, or None for γ=1 (pure cumsum).
        prev:  [B, H, Dh] carried state S_0, or None (zeros).
    Returns:
        S: [B, N, H, Dh] with S[:, t] = S_t.

    This is intentionally simple and exact (no chunked-EMA overflow tricks); the
    canonical reference favors auditability over the production parallel scan.
    """
    B, N, H, Dh = kv.shape
    if gamma is None:
        S = torch.cumsum(kv, dim=1)
        if prev is not None:
            S = S + prev.unsqueeze(1)
        return S

    # Decay path: γ^{t} weighting. Compute in float64-safe log space via powers.
    g = gamma.view(1, 1, H, 1).to(kv.real.dtype if kv.is_complex() else kv.dtype)
    # Exact recurrence with a Python loop over N (reference clarity; N is small in
    # tests and the production parallel_ema_scan is the fast path elsewhere).
    out = torch.empty_like(kv)
    s = (prev if prev is not None else torch.zeros(B, H, Dh, dtype=kv.dtype, device=kv.device))
    gflat = g.view(1, H, 1)
    for t in range(N):
        s = gflat * s + kv[:, t]
        out[:, t] = s
    return out
