#!/usr/bin/env python3
"""
Experiential State (Dual-Space Architecture) — Appendix F Stage 7C
====================================================================

Implements a parallel experiential state P_t that accumulates trajectory
information via latent recurrence alongside the standard hidden state x.

Central recurrence equation::

    g_t = sigmoid(W_g @ x_t)                    # gating vector
    u_t = W_u @ x_t                              # input projection
    c_t = coherence_embedding(C_total)            # coherence context
    P_t = g_t * (rho * P_{t-1}) + u_t + lam * W_c @ c_t

Stability constraints:
    - ρ < 1.0 (init 0.95, enforced by sigmoid parameterization)
    - λ ≤ 0.1 (init 0.0 for bounded introduction)
    - spectral_norm(W_c) ≤ 1.0

Architecture::

    hidden_state x
          │
          ├──→ experiential_gate(x) ──→ g_t
          ├──→ experiential_input(x) ──→ u_t
          │
          └──→ P_t = g_t ⊙ (ρ P_{t-1}) + u_t + λ W_c c_t
                      │
                      └──→ InterpretiveConditioner (extends interpretive state)

Bounded introduction: λ = 0.0 initially so P_t accumulates but does
not influence generation. Ramp λ during fine-tuning.

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.10.6.3

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 7C — Dual-Space Architecture
"""

from dataclasses import dataclass
from typing import Dict, Optional

import torch
import torch.nn as nn
import torch.nn.utils.parametrize as parametrize


@dataclass
class ExperientialStateConfig:
    """Configuration for the experiential state module.

    Attributes:
        enable: Master switch for Stage 7C.
        d_exp: Dimension of the experiential state P_t.
        d_coherence: Dimension of the coherence embedding.
        rho_init: Initial decay rate (before sigmoid).
            sigmoid(3.0) ≈ 0.95. Must produce ρ < 1.0.
        lambda_init: Initial coherence coupling strength.
            0.0 for bounded introduction.
        lambda_max: Maximum λ value (enforced by clamping).
        hidden_dim: Transformer hidden state dimension.
    """
    enable: bool = True
    d_exp: int = 64
    d_coherence: int = 16
    rho_init: float = 3.0  # sigmoid(3.0) ≈ 0.95
    lambda_init: float = 0.0
    lambda_max: float = 0.1
    hidden_dim: int = 768


class ExperientialStateModule(nn.Module):
    """Parallel experiential state with latent recurrence.

    Maintains P_t alongside the standard hidden state, capturing
    trajectory information that the snapshot hidden state cannot.

    Usage::

        module = ExperientialStateModule(config)

        # Per-token step during generation
        for t in range(seq_len):
            x_t = hidden_states[:, t, :]  # [B, D]
            P_t = module.step(x_t, c_total=0.75)

        # Get P_t for interpretive conditioner
        p_vector = module.get_experiential_vector()  # [B, d_exp]

        # Reset for new sequence
        module.reset()

    Attributes:
        config: ExperientialStateConfig.
        P: Current experiential state tensor.
    """

    def __init__(self, config: ExperientialStateConfig = None):
        super().__init__()
        self.config = config or ExperientialStateConfig()
        d = self.config.d_exp
        h = self.config.hidden_dim

        # Gating: g_t = sigmoid(W_g @ x_t)
        self.W_g = nn.Linear(h, d)

        # Input projection: u_t = W_u @ x_t
        self.W_u = nn.Linear(h, d)

        # Coherence embedding: maps scalar C_total → d_coherence vector
        self.coherence_embedding = nn.Sequential(
            nn.Linear(1, self.config.d_coherence),
            nn.GELU(),
            nn.Linear(self.config.d_coherence, self.config.d_coherence),
        )

        # Coherence projection: W_c @ c_t → d_exp
        # Spectral norm enforced: ||W_c|| ≤ 1.0
        self.W_c = nn.Linear(self.config.d_coherence, d, bias=False)
        nn.utils.parametrizations.spectral_norm(self.W_c)

        # Decay rate ρ: sigmoid(rho_raw) ensures ρ ∈ (0, 1)
        self.rho_raw = nn.Parameter(torch.tensor(float(self.config.rho_init)))

        # Coupling strength λ: clamped to [0, lambda_max]
        self.lambda_raw = nn.Parameter(torch.tensor(float(self.config.lambda_init)))

        # Experiential state buffer (not a parameter, reset per sequence)
        self.register_buffer("P", torch.zeros(1, d))

        self._batch_size = 1

    @property
    def rho(self) -> torch.Tensor:
        """Decay rate ρ ∈ (0, 1), enforced by sigmoid."""
        return torch.sigmoid(self.rho_raw)

    @property
    def lam(self) -> torch.Tensor:
        """Coupling strength λ ∈ [0, lambda_max], enforced by clamp."""
        return self.lambda_raw.clamp(0.0, self.config.lambda_max)

    def step(
        self,
        x_t: torch.Tensor,
        c_total: float = 0.5,
    ) -> torch.Tensor:
        """Advance experiential state by one token.

        Implements: P_t = g_t ⊙ (ρ P_{t-1}) + u_t + λ W_c c_t

        Args:
            x_t: Hidden state for current token [B, hidden_dim].
            c_total: Unified coherence signal (scalar).

        Returns:
            P_t: Updated experiential state [B, d_exp].
        """
        if not self.config.enable:
            return self.P

        B = x_t.shape[0]

        # Resize P if batch size changed
        if self.P.shape[0] != B:
            self.P = torch.zeros(B, self.config.d_exp, device=x_t.device)
            self._batch_size = B

        # Gating
        g_t = torch.sigmoid(self.W_g(x_t))  # [B, d_exp]

        # Input projection
        u_t = self.W_u(x_t)  # [B, d_exp]

        # Coherence context
        c_scalar = torch.tensor([[c_total]], device=x_t.device, dtype=x_t.dtype)
        c_scalar = c_scalar.expand(B, 1)
        c_t = self.coherence_embedding(c_scalar)  # [B, d_coherence]
        wc_ct = self.W_c(c_t)  # [B, d_exp]

        # Recurrence
        rho = self.rho
        lam = self.lam
        self.P = g_t * (rho * self.P.detach()) + u_t + lam * wc_ct

        return self.P

    def get_experiential_vector(self) -> torch.Tensor:
        """Return current experiential state for use in interpretive conditioner.

        Returns:
            P: Current P_t [B, d_exp].
        """
        return self.P

    def reset(self, batch_size: int = 1) -> None:
        """Reset experiential state for a new sequence.

        Args:
            batch_size: Batch size for the new sequence.
        """
        self.P = torch.zeros(
            batch_size, self.config.d_exp,
            device=self.P.device, dtype=self.P.dtype,
        )
        self._batch_size = batch_size
