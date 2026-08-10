#!/usr/bin/env python3
"""
Perspective Synthesizer — Appendix F Stage 8
=============================================

Synthesizes orthogonal interpretive signals (CSR, Vritti, Kosha, Bhava) into a
unified conditioning state that modifies the hidden representation BEFORE
vocabulary projection via lm_head.

This is the capstone of Stage 2's InterpretiveConditioner pattern. Instead of
post-hoc logit modulation, the transformer's own vocabulary projection operates
on an interpretively-enriched representation.

Architecture::

    hidden_state x [B, T, D]
        ↓
    InterpretiveStateBuilder
        → InterpretiveState {csr, vritti, kosha, bhava, [phase, exp]}
        ↓
    PerspectiveSynthesizer
        → conditioned_hidden = x + sigmoid(gate) · synthesis(interp_state)
        ↓
    lm_head(conditioned_hidden)  → logits

Invariants:
  - Gate initializes at 0 with zero-init final layer → output = hidden exactly.
  - Auxiliary modules interpret meaning on orthogonal semantic axes.
  - Conditioning is additive, never multiplicative.

Pattern precedent: mistral_wrapper.py:318-324 (phase adapter via gated residual).

Reference: Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md §F.12.5
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

import torch
import torch.nn as nn

from symbolu.inference.interpretive_state import InterpretiveState
from symbolu.inference.interpretive_conditioner import (
    InterpretiveConditionerConfig,
    InterpretiveStateBuilder,
    InterpretiveConditioner,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class PerspectiveSynthesizerConfig:
    """Configuration for the Stage 8 Perspective Synthesizer.

    Extends the Stage 2 InterpretiveConditionerConfig with synthesis-specific
    settings and diagnostic controls.

    Attributes:
        enable: Master switch. False → forward() returns hidden unchanged.
        d_synthesis: Hidden dimension of synthesis MLP.
        gate_init: Initial gating parameter (0.0 for safe cold start).
        csr_dim: CSR resonance signal dimension.
        vritti_classes: Number of Vritti cognitive mode classes.
        kosha_primitives: Number of Kosha experiential routing slots.
        bhava_output_dim: Compressed Bhava vector dimension.
        bhava_input_dim: Flattened Bhava matrix dimension (12×12=144).
        onto_dim: Ontological state dimension (12 for SymbolU12).
        enable_polarity: Stage 7D polarity encoding for CSR.
        phase_out_dim: Stage 7F phase coherence projection dim (0=disabled).
        d_exp: Stage 7C experiential state dim (0=disabled).
        log_interpretive_state: Log full InterpretiveState to tracer.
    """

    enable: bool = True
    d_synthesis: int = 64
    gate_init: float = 0.0
    csr_dim: int = 16
    vritti_classes: int = 5
    kosha_primitives: int = 6
    bhava_output_dim: int = 16
    bhava_input_dim: int = 144
    onto_dim: int = 12
    enable_polarity: bool = False
    phase_out_dim: int = 0
    d_exp: int = 0
    log_interpretive_state: bool = True

    def to_conditioner_config(self) -> InterpretiveConditionerConfig:
        """Convert to underlying InterpretiveConditionerConfig."""
        return InterpretiveConditionerConfig(
            d_synthesis=self.d_synthesis,
            gate_init=self.gate_init,
            enable=self.enable,
            csr_dim=self.csr_dim,
            vritti_classes=self.vritti_classes,
            kosha_primitives=self.kosha_primitives,
            bhava_output_dim=self.bhava_output_dim,
            bhava_input_dim=self.bhava_input_dim,
            onto_dim=self.onto_dim,
            enable_polarity=self.enable_polarity,
            phase_out_dim=self.phase_out_dim,
            d_exp=self.d_exp,
        )


# =============================================================================
# PERSPECTIVE SYNTHESIZER
# =============================================================================

class PerspectiveSynthesizer(nn.Module):
    """Synthesizes orthogonal interpretive signals into unified representation
    conditioning for the decoder.

    Composes InterpretiveStateBuilder (builds the multi-axis interpretive state)
    with InterpretiveConditioner (applies gated residual conditioning).

    Placement: Between final layer norm output and lm_head input.

    Args:
        config: PerspectiveSynthesizerConfig.
        hidden_dim: Transformer hidden state dimension.
    """

    def __init__(self, config: PerspectiveSynthesizerConfig, hidden_dim: int):
        super().__init__()
        self.config = config
        self.hidden_dim = hidden_dim

        conditioner_config = config.to_conditioner_config()

        self.state_builder = InterpretiveStateBuilder(
            hidden_dim=hidden_dim,
            config=conditioner_config,
        )

        self.conditioner = InterpretiveConditioner(
            config=conditioner_config,
            hidden_dim=hidden_dim,
            interp_dim=self.state_builder.interp_dim,
        )

    @property
    def gate_value(self) -> float:
        """Current gate value (sigmoid-activated)."""
        return self.conditioner.gate_value

    @property
    def interp_dim(self) -> int:
        """Total dimension of the interpretive state vector."""
        return self.state_builder.interp_dim

    def forward(
        self,
        hidden: torch.Tensor,
        onto_state: torch.Tensor,
        bhava_matrix: torch.Tensor,
        phase_coherence_vector: Optional[torch.Tensor] = None,
        experiential_vector: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """Build interpretive state and condition hidden representation.

        Args:
            hidden: Transformer hidden states [B, T, D].
            onto_state: Ontological projection [B, T, onto_dim].
            bhava_matrix: Bhava relationship matrix [B, 12, 12] or [B, 144].
            phase_coherence_vector: Optional [B, H] from Stage 7F.
            experiential_vector: Optional [B, d_exp] from Stage 7C.

        Returns:
            Dict with:
                - conditioned_hidden: [B, T, D] — the enriched representation
                - interpretive_state: InterpretiveState dataclass
                - gate_value: float — current synthesis gate magnitude
                - conditioning_norm: float — norm of the conditioning delta
                - log_dict: Dict — flat loggable summary (if logging enabled)
        """
        if not self.config.enable:
            return {
                "conditioned_hidden": hidden,
                "interpretive_state": None,
                "gate_value": 0.0,
                "conditioning_norm": 0.0,
                "log_dict": {},
            }

        # Build interpretive state from all axes
        builder_out = self.state_builder(
            hidden=hidden,
            onto_state=onto_state,
            bhava_matrix=bhava_matrix,
            phase_coherence_vector=phase_coherence_vector,
            experiential_vector=experiential_vector,
        )

        interp_tensor = builder_out["interpretive_state"]
        components = builder_out["components"]

        # Construct formal InterpretiveState dataclass
        interp_state = InterpretiveState(
            csr_signal=components["r_ctx"],
            vritti_distribution=components["v_ctx"],
            kosha_routing=components["alpha_t"],
            bhava_relation=components["b_t"],
            phase_coherence=components.get("phase_signal"),
            experiential_state=components.get("experiential"),
            bhava_coherence=components.get("bhava_coherence"),
            polarity_phi=components.get("phi"),
        )

        # Apply gated residual conditioning
        conditioned = self.conditioner(
            hidden=hidden,
            interpretive_state=interp_tensor,
        )

        # Compute conditioning delta norm for diagnostics
        delta = conditioned - hidden
        conditioning_norm = delta.norm(dim=-1).mean().item()

        result = {
            "conditioned_hidden": conditioned,
            "interpretive_state": interp_state,
            "gate_value": self.gate_value,
            "conditioning_norm": conditioning_norm,
        }

        # Build log dict if enabled
        if self.config.log_interpretive_state:
            log_dict = interp_state.to_log_dict()
            log_dict["synthesis_gate"] = self.gate_value
            log_dict["conditioning_norm"] = conditioning_norm
            result["log_dict"] = log_dict
        else:
            result["log_dict"] = {}

        return result
