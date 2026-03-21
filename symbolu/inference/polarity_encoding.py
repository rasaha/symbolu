#!/usr/bin/env python3
"""
Polarity Encoding (Varna Polarity Gates) — Appendix F Stage 7D
================================================================

Extends CSR context projection with polarity gates that encode emotional
direction (positive/negative poles) based on ontological state.

Polarity encoding formula::

    φ = tanh(W_φ @ onto_state)               # polarity ∈ [-1, 1]
    v_neg = W_neg @ hidden_state              # negative pole embedding
    v_pos = W_pos @ hidden_state              # positive pole embedding
    c_polar = (1 - φ)/2 · v_neg + (1 + φ)/2 · v_pos

Backward compatibility: when φ = 0, the formula reduces to
(v_neg + v_pos) / 2, which approximates the original bilinear output.

The polarity-aware CSR signal replaces the standard CSR context projection
in the InterpretiveStateBuilder.

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.10.6.4

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 7D — Polarity Encoding (Varna Polarity Gates)
"""

from dataclasses import dataclass
from typing import Dict, Optional

import torch
import torch.nn as nn


@dataclass
class PolarityEncodingConfig:
    """Configuration for polarity encoding.

    Attributes:
        enable: Master switch for Stage 7D. When False, returns standard
            CSR projection (no polarity gates).
        onto_dim: Ontological state dimension (12 for SymbolU12).
        hidden_dim: Transformer hidden state dimension.
        csr_dim: Output dimension for polarity-aware CSR (matches Stage 2).
        phi_init_scale: Scale for initializing W_phi. Small values keep
            φ ≈ 0 at start for bounded introduction.
    """
    enable: bool = True
    onto_dim: int = 12
    hidden_dim: int = 768
    csr_dim: int = 16
    phi_init_scale: float = 0.01


class PolarityGate(nn.Module):
    """Varna Polarity Gate for CSR context projection.

    Computes polarity-aware CSR representation using positive and
    negative pole embeddings gated by ontological state polarity.

    When φ = 0:
        c_polar = (v_neg + v_pos) / 2  (neutral, backward-compatible)

    When φ = 1 (positive):
        c_polar = v_pos

    When φ = -1 (negative):
        c_polar = v_neg

    Args:
        config: PolarityEncodingConfig.
    """

    def __init__(self, config: PolarityEncodingConfig = None):
        super().__init__()
        self.config = config or PolarityEncodingConfig()
        h = self.config.hidden_dim
        o = self.config.onto_dim
        c = self.config.csr_dim

        # Polarity gate: φ = tanh(W_phi @ onto_state)
        self.W_phi = nn.Linear(o, c)

        # Negative pole projection: v_neg = W_neg @ hidden_state
        self.W_neg = nn.Linear(h, c)

        # Positive pole projection: v_pos = W_pos @ hidden_state
        self.W_pos = nn.Linear(h, c)

        # Fallback: standard CSR projection (for when disabled)
        self.standard_proj = nn.Sequential(
            nn.Linear(h + o, h // 4),
            nn.GELU(),
            nn.Linear(h // 4, c),
        )

        self._init_weights()

    def _init_weights(self):
        """Initialize W_phi with small values for bounded introduction."""
        nn.init.normal_(self.W_phi.weight, std=self.config.phi_init_scale)
        nn.init.zeros_(self.W_phi.bias)
        # Initialize pole projections with Xavier for stable start
        nn.init.xavier_normal_(self.W_neg.weight, gain=0.5)
        nn.init.xavier_normal_(self.W_pos.weight, gain=0.5)

    def forward(
        self,
        hidden: torch.Tensor,
        onto_state: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """Compute polarity-aware CSR representation.

        Args:
            hidden: Transformer hidden states (..., hidden_dim).
            onto_state: Ontological state (..., onto_dim).

        Returns:
            Dict with:
                - c_polar: Polarity-aware CSR (..., csr_dim).
                - phi: Polarity values (..., csr_dim) in [-1, 1].
                - v_neg: Negative pole embedding (..., csr_dim).
                - v_pos: Positive pole embedding (..., csr_dim).
        """
        if not self.config.enable:
            combined = torch.cat([hidden, onto_state], dim=-1)
            c_standard = self.standard_proj(combined)
            return {
                "c_polar": c_standard,
                "phi": torch.zeros_like(c_standard),
                "v_neg": c_standard,
                "v_pos": c_standard,
            }

        # Polarity gate
        phi = torch.tanh(self.W_phi(onto_state))  # (..., csr_dim)

        # Pole embeddings
        v_neg = self.W_neg(hidden)  # (..., csr_dim)
        v_pos = self.W_pos(hidden)  # (..., csr_dim)

        # Polarity encoding: c = (1-φ)/2 · v_neg + (1+φ)/2 · v_pos
        c_polar = (1 - phi) / 2 * v_neg + (1 + phi) / 2 * v_pos

        return {
            "c_polar": c_polar,
            "phi": phi,
            "v_neg": v_neg,
            "v_pos": v_pos,
        }
