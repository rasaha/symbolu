#!/usr/bin/env python3
"""
Interpretive Conditioner — Appendix F Stage 2
===============================================

Conditions the hidden state with interpretive signals from auxiliary modules
(CSR, Vritti, Kosha, Bhava) BEFORE vocabulary projection. Auxiliary modules
interpret meaning on orthogonal semantic axes — they do not compete for tokens
or modify logits directly.

Architecture::

    hidden_state x [B, T, D]
        ↓
    ┌─── Parallel Interpretation ─────────────────────────┐
    │ CSR context:   r_ctx = csr_proj(x, onto_state)      │
    │ Vritti dist:   v_ctx = vritti_proj(x, onto_state)    │
    │ Kosha routing: α_t   = kosha_proj(x, onto_state)     │
    │ Bhava vector:  b_t   = bhava_compressor(bhava_144d)  │
    └─────────────────────────────────────────────────────┘
        ↓
    interpretive_state = concat(r_ctx, v_ctx, α_t, b_t)
        ↓
    conditioned_hidden = x + sigmoid(gate) · synthesis_mlp(interpretive_state)
        ↓
    lm_head(conditioned_hidden)  → logits

Invariants:
  - At gate=0 (initialization), output equals unconditioned hidden state.
  - Final synthesis layer is zero-initialized for safe cold start.
  - Auxiliary interpretation is additive, never multiplicative on logits.

Pattern precedent: mistral_wrapper.py:318-324 (phase adapter via gated residual).

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.4

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 2 — Auxiliary Interpretation Informs Generation
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

import torch
import torch.nn as nn


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class InterpretiveConditionerConfig:
    """Configuration for the interpretive conditioner.

    Attributes:
        d_synthesis: Hidden dimension of the synthesis MLP.
        gate_init: Initial value for the gating parameter. 0.0 means
            sigmoid(0)=0.5, but with zero-init on the final linear layer,
            the conditioning starts at zero regardless.
        enable: Master switch. When False, forward() returns hidden unchanged.
        csr_dim: Output dimension of CSR context projection.
        vritti_classes: Number of Vritti cognitive mode classes.
        kosha_primitives: Number of Kosha primitive routing weights.
        bhava_output_dim: Compressed Bhava vector dimension.
        bhava_input_dim: Flattened Bhava matrix dimension (12×12=144).
        onto_dim: Ontological state dimension (12 for SymbolU12).
    """
    d_synthesis: int = 64
    gate_init: float = 0.0
    enable: bool = True
    csr_dim: int = 16
    vritti_classes: int = 5
    kosha_primitives: int = 6
    bhava_output_dim: int = 16
    bhava_input_dim: int = 144
    onto_dim: int = 12
    # Stage 7D: Polarity encoding (replaces standard CSR projection)
    enable_polarity: bool = False
    # Stage 7F: Phase coherence signal dimension (added to interpretive state)
    phase_out_dim: int = 0
    # Stage 7C: Experiential state dimension (added to interpretive state)
    d_exp: int = 0


# =============================================================================
# BHAVA VECTOR COMPRESSOR (F.5 — Stage 3 dependency)
# =============================================================================

class BhavaVectorCompressor(nn.Module):
    """Compresses 12x12 Bhava relationship matrix to a compact vector.

    Preserves relational structure lost by scalar collapse.

    Architecture: 144D → 64D (ReLU) → output_dim (16D)
    Also outputs scalar coherence for backward compatibility.

    Args:
        bhava_dim: Dimension of each ontological axis (12).
        output_dim: Compressed vector dimension (16).
    """

    def __init__(self, bhava_dim: int = 12, output_dim: int = 16):
        super().__init__()
        input_dim = bhava_dim * bhava_dim  # 144
        self.compressor = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim),
        )
        # Backward-compatible scalar coherence
        self.coherence_head = nn.Linear(output_dim, 1)

    def forward(self, bhava_matrix: torch.Tensor) -> Dict[str, torch.Tensor]:
        """Compress Bhava matrix to vector + coherence scalar.

        Args:
            bhava_matrix: Bhava relationship matrix (..., 12, 12) or
                flattened (..., 144).

        Returns:
            Dict with:
                - bhava_vector: Compressed vector (..., output_dim)
                - coherence: Scalar coherence (...,)
        """
        if bhava_matrix.dim() >= 2 and bhava_matrix.shape[-1] != bhava_matrix.shape[-2]:
            # Already flattened
            flat = bhava_matrix
        else:
            flat = bhava_matrix.flatten(start_dim=-2)  # (..., 144)
        bhava_vector = self.compressor(flat)  # (..., output_dim)
        coherence = torch.sigmoid(self.coherence_head(bhava_vector))  # (..., 1)
        return {
            "bhava_vector": bhava_vector,
            "coherence": coherence.squeeze(-1),
        }


# =============================================================================
# INTERPRETIVE STATE BUILDER
# =============================================================================

class InterpretiveStateBuilder(nn.Module):
    """Builds the concatenated interpretive state from hidden + auxiliary signals.

    Contains lightweight context projections that mirror the training-time
    modules (CSRTokenScorer, VrittiTokenScorer, KoshaPrimitiveRouter) for
    context-side interpretation, plus a BhavaVectorCompressor.

    These projections can be loaded from a CG checkpoint or trained from
    scratch with the InterpretiveConditioner.

    Args:
        hidden_dim: Transformer hidden state dimension.
        config: InterpretiveConditionerConfig with dimension parameters.
    """

    def __init__(self, hidden_dim: int, config: InterpretiveConditionerConfig):
        super().__init__()
        self.config = config
        self.hidden_dim = hidden_dim
        input_dim = hidden_dim + config.onto_dim

        # Stage 7D: Use PolarityGate if enabled, otherwise standard CSR projection
        self._polarity_gate = None
        if config.enable_polarity:
            try:
                from symbolu.inference.polarity_encoding import PolarityGate, PolarityEncodingConfig
                self._polarity_gate = PolarityGate(PolarityEncodingConfig(
                    hidden_dim=hidden_dim,
                    onto_dim=config.onto_dim,
                    csr_dim=config.csr_dim,
                ))
            except ImportError:
                pass

        # CSR context projection (fallback if polarity not enabled/available)
        self.csr_proj = nn.Sequential(
            nn.Linear(input_dim, hidden_dim // 4),
            nn.GELU(),
            nn.Linear(hidden_dim // 4, config.csr_dim),
        )

        # Vritti context projection: [h_t; o_t] → vritti_classes (softmax)
        self.vritti_proj = nn.Linear(input_dim, config.vritti_classes)

        # Kosha routing projection: [h_t; o_t] → kosha_primitives (softmax)
        self.kosha_proj = nn.Sequential(
            nn.Linear(input_dim, hidden_dim // 4),
            nn.GELU(),
            nn.Linear(hidden_dim // 4, config.kosha_primitives),
        )

        # Bhava compressor: 144 → bhava_output_dim
        self.bhava_compressor = BhavaVectorCompressor(
            bhava_dim=int(config.bhava_input_dim ** 0.5),  # 12
            output_dim=config.bhava_output_dim,
        )

        # Stage 7F: Phase coherence projection (zero-init for bounded intro)
        self._phase_projection = None
        if config.phase_out_dim > 0:
            try:
                from symbolu.inference.phase_coherence_signal import PhaseCoherenceProjection
                self._phase_projection = PhaseCoherenceProjection(
                    num_heads=8,  # Default; overridden by caller if needed
                    phase_out_dim=config.phase_out_dim,
                )
            except ImportError:
                pass

        # Stage 7C: Experiential state projection (zero-init for bounded intro)
        self._exp_projection = None
        if config.d_exp > 0:
            self._exp_projection = nn.Linear(config.d_exp, config.d_exp)
            nn.init.zeros_(self._exp_projection.weight)
            nn.init.zeros_(self._exp_projection.bias)

        self._init_weights()

    def _init_weights(self):
        """Initialize for near-uniform initial distributions."""
        for module in [self.csr_proj, self.vritti_proj, self.kosha_proj]:
            for m in (module.modules() if hasattr(module, 'modules') else [module]):
                if isinstance(m, nn.Linear):
                    nn.init.xavier_normal_(m.weight, gain=0.3)
                    if m.bias is not None:
                        m.bias.data.fill_(0.0)

    @property
    def interp_dim(self) -> int:
        """Total dimension of the concatenated interpretive state."""
        base = (
            self.config.csr_dim
            + self.config.vritti_classes
            + self.config.kosha_primitives
            + self.config.bhava_output_dim
        )
        # Stage 7F: Phase coherence adds phase_out_dim
        if self._phase_projection is not None:
            base += self.config.phase_out_dim
        # Stage 7C: Experiential state adds d_exp
        if self._exp_projection is not None:
            base += self.config.d_exp
        return base

    def forward(
        self,
        hidden: torch.Tensor,
        onto_state: torch.Tensor,
        bhava_matrix: torch.Tensor,
        phase_coherence_vector: Optional[torch.Tensor] = None,
        experiential_vector: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """Build interpretive state from hidden + auxiliary signals.

        Args:
            hidden: Transformer hidden states (..., hidden_dim).
            onto_state: Ontological projection (..., onto_dim).
            bhava_matrix: Bhava relationship matrix (..., 12, 12) or (..., 144).
            phase_coherence_vector: Optional [B, H] from Stage 7F aggregator.
            experiential_vector: Optional [B, d_exp] from Stage 7C module.

        Returns:
            Dict with:
                - interpretive_state: Concatenated vector (..., interp_dim)
                - components: Dict of individual components for logging
        """
        combined = torch.cat([hidden, onto_state], dim=-1)

        # Stage 7D: Use PolarityGate for CSR if available, else standard projection
        polarity_result = None
        if self._polarity_gate is not None:
            polarity_result = self._polarity_gate(hidden, onto_state)
            r_ctx = polarity_result["c_polar"]
        else:
            r_ctx = self.csr_proj(combined)

        # Vritti cognitive mode distribution
        v_ctx = torch.softmax(self.vritti_proj(combined), dim=-1)

        # Kosha experiential depth routing
        alpha_t = torch.softmax(self.kosha_proj(combined), dim=-1)

        # Bhava relational structure
        bhava_out = self.bhava_compressor(bhava_matrix)
        b_t = bhava_out["bhava_vector"]

        # Broadcast b_t to match hidden sequence dimensions if needed
        if b_t.dim() < r_ctx.dim():
            expand_shape = list(r_ctx.shape[:-1]) + [b_t.shape[-1]]
            b_t = b_t.unsqueeze(-2).expand(expand_shape)

        parts = [r_ctx, v_ctx, alpha_t, b_t]
        components = {
            "r_ctx": r_ctx,
            "v_ctx": v_ctx,
            "alpha_t": alpha_t,
            "b_t": b_t,
            "bhava_coherence": bhava_out["coherence"],
        }

        # Stage 7F: Append phase coherence projection
        if self._phase_projection is not None and phase_coherence_vector is not None:
            seq_len = hidden.shape[-2] if hidden.dim() >= 2 else 1
            phase_signal = self._phase_projection(phase_coherence_vector, seq_len=seq_len)
            parts.append(phase_signal)
            components["phase_signal"] = phase_signal

        # Stage 7C: Append experiential state projection
        if self._exp_projection is not None and experiential_vector is not None:
            exp_proj = self._exp_projection(experiential_vector)
            # Broadcast to sequence length if needed
            if exp_proj.dim() < r_ctx.dim():
                expand_shape = list(r_ctx.shape[:-1]) + [exp_proj.shape[-1]]
                exp_proj = exp_proj.unsqueeze(-2).expand(expand_shape)
            parts.append(exp_proj)
            components["experiential"] = exp_proj

        # Stage 7D: Record polarity metrics
        if polarity_result is not None:
            components["phi"] = polarity_result["phi"]

        interpretive_state = torch.cat(parts, dim=-1)

        return {
            "interpretive_state": interpretive_state,
            "components": components,
        }


# =============================================================================
# INTERPRETIVE CONDITIONER (F.4.4)
# =============================================================================

class InterpretiveConditioner(nn.Module):
    """Conditions hidden state with interpretive signals via gated residual.

    Synthesizes auxiliary interpretations (CSR, Vritti, Kosha, Bhava) into a
    conditioning signal that modifies the hidden state BEFORE lm_head
    vocabulary projection.

    Invariant: At gate=0 with zero-init on the final linear layer, the
    output equals the unconditioned hidden state exactly.

    Args:
        config: InterpretiveConditionerConfig.
        hidden_dim: Transformer hidden state dimension.
        interp_dim: Dimension of the concatenated interpretive state.
    """

    def __init__(
        self,
        config: InterpretiveConditionerConfig,
        hidden_dim: int,
        interp_dim: int,
    ):
        super().__init__()
        self.config = config
        self.hidden_dim = hidden_dim
        self.interp_dim = interp_dim

        # Synthesis MLP: interpretive signals → hidden-compatible conditioning
        self.synthesis = nn.Sequential(
            nn.Linear(interp_dim, config.d_synthesis),
            nn.GELU(),
            nn.Linear(config.d_synthesis, hidden_dim),
        )

        # Gated residual — zero-init for safe cold start
        self.gate = nn.Parameter(torch.tensor(float(config.gate_init)))
        nn.init.zeros_(self.synthesis[-1].weight)
        nn.init.zeros_(self.synthesis[-1].bias)

    @property
    def gate_value(self) -> float:
        """Current gate value after sigmoid."""
        return torch.sigmoid(self.gate).item()

    def forward(
        self,
        hidden: torch.Tensor,
        interpretive_state: torch.Tensor,
    ) -> torch.Tensor:
        """Apply interpretive conditioning to hidden state.

        Args:
            hidden: Transformer hidden states (..., hidden_dim).
            interpretive_state: Concatenated interpretive vector (..., interp_dim).

        Returns:
            conditioned_hidden: hidden + sigmoid(gate) * synthesis(interpretive_state)
        """
        if not self.config.enable:
            return hidden

        conditioning = self.synthesis(interpretive_state)
        g = torch.sigmoid(self.gate)
        return hidden + g * conditioning
