#!/usr/bin/env python3
"""
InterpretiveState — Appendix F Stage 8
========================================

Formal dataclass capturing the unified interpretive state from all auxiliary
modules. Each field represents a different semantic axis of interpretation:

  - CSR:    Resonance / acoustic-emotional signal  [B, T, D_csr]
  - Vritti: Cognitive mode simplex                  [B, T, 5]
  - Kosha:  Experiential layer routing              [B, T, 6]
  - Bhava:  Compressed ontological relation          [B, T, 16]

Optionally extended with Stage 7 signals:
  - Phase coherence:  [B, T, phase_out_dim]  (Stage 7F)
  - Experiential P_t: [B, T, d_exp]          (Stage 7C)

Reference: Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md §F.12.4
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

import torch


@dataclass
class InterpretiveState:
    """Unified interpretive state from all auxiliary modules.

    Each field captures a different semantic axis of the input.
    Combined into a single conditioning vector for the PerspectiveSynthesizer.
    """

    csr_signal: torch.Tensor              # [B, T, D_csr] resonance pattern
    vritti_distribution: torch.Tensor      # [B, T, 5] cognitive mode simplex
    kosha_routing: torch.Tensor            # [B, T, 6] experiential layer weights
    bhava_relation: torch.Tensor           # [B, T, 16] compressed ontological state

    # Stage 7 optional extensions
    phase_coherence: Optional[torch.Tensor] = None   # [B, T, phase_out_dim]
    experiential_state: Optional[torch.Tensor] = None  # [B, T, d_exp]

    # Diagnostic metadata
    bhava_coherence: Optional[torch.Tensor] = None  # [B,] scalar
    polarity_phi: Optional[torch.Tensor] = None      # [B, T, csr_dim] if polarity enabled

    def to_conditioning_vector(self) -> torch.Tensor:
        """Concatenate all interpretive signals into a single vector.

        Returns:
            [B, T, D_total] where D_total = D_csr + 5 + 6 + 16 + optional extensions
        """
        parts = [
            self.csr_signal,
            self.vritti_distribution,
            self.kosha_routing,
            self.bhava_relation,
        ]
        if self.phase_coherence is not None:
            parts.append(self.phase_coherence)
        if self.experiential_state is not None:
            parts.append(self.experiential_state)
        return torch.cat(parts, dim=-1)

    @property
    def conditioning_dim(self) -> int:
        """Total dimension of the conditioning vector."""
        d = (
            self.csr_signal.shape[-1]
            + self.vritti_distribution.shape[-1]
            + self.kosha_routing.shape[-1]
            + self.bhava_relation.shape[-1]
        )
        if self.phase_coherence is not None:
            d += self.phase_coherence.shape[-1]
        if self.experiential_state is not None:
            d += self.experiential_state.shape[-1]
        return d

    def to_log_dict(self) -> Dict[str, Any]:
        """Extract loggable summary statistics for per-token tracing.

        Returns a flat dict suitable for GenerationTracer.record_token().
        """
        log = {}

        # Vritti: dominant mode + distribution
        v = self.vritti_distribution
        if v.dim() >= 2:
            v_last = v[:, -1] if v.dim() == 3 else v[-1]
        else:
            v_last = v
        vritti_names = ["pramana", "viparyaya", "vikalpa", "nidra", "smrti"]
        dominant_idx = v_last.argmax(dim=-1).item() if v_last.dim() <= 1 else v_last[0].argmax().item()
        log["vritti_dominant"] = vritti_names[dominant_idx] if dominant_idx < len(vritti_names) else str(dominant_idx)
        log["vritti_distribution"] = v_last[0].tolist() if v_last.dim() > 1 else v_last.tolist()

        # Kosha: primary layer + distribution
        k = self.kosha_routing
        if k.dim() >= 2:
            k_last = k[:, -1] if k.dim() == 3 else k[-1]
        else:
            k_last = k
        kosha_names = ["base", "ontology", "jepa", "csr", "vritti", "guna"]
        primary_idx = k_last.argmax(dim=-1).item() if k_last.dim() <= 1 else k_last[0].argmax().item()
        log["kosha_primary"] = kosha_names[primary_idx] if primary_idx < len(kosha_names) else str(primary_idx)
        log["kosha_distribution"] = k_last[0].tolist() if k_last.dim() > 1 else k_last.tolist()

        # CSR: norm of resonance signal
        log["csr_signal_norm"] = self.csr_signal[:, -1].norm(dim=-1).mean().item() if self.csr_signal.dim() >= 2 else self.csr_signal.norm().item()

        # Bhava: coherence + relation norm
        log["bhava_relation_norm"] = self.bhava_relation[:, -1].norm(dim=-1).mean().item() if self.bhava_relation.dim() >= 2 else self.bhava_relation.norm().item()
        if self.bhava_coherence is not None:
            log["bhava_coherence"] = self.bhava_coherence.mean().item()

        # Stage 7 extensions
        if self.phase_coherence is not None:
            log["phase_coherence_interp_norm"] = self.phase_coherence[:, -1].norm(dim=-1).mean().item() if self.phase_coherence.dim() >= 2 else self.phase_coherence.norm().item()
        if self.experiential_state is not None:
            log["experiential_interp_norm"] = self.experiential_state[:, -1].norm(dim=-1).mean().item() if self.experiential_state.dim() >= 2 else self.experiential_state.norm().item()
        if self.polarity_phi is not None:
            log["polarity_phi_norm"] = self.polarity_phi[:, -1].norm(dim=-1).mean().item() if self.polarity_phi.dim() >= 2 else self.polarity_phi.norm().item()

        # Total conditioning norm
        vec = self.to_conditioning_vector()
        log["conditioning_norm"] = vec[:, -1].norm(dim=-1).mean().item() if vec.dim() >= 2 else vec.norm().item()

        return log
