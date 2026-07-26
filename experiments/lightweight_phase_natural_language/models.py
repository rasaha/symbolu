"""
models.py — A/B/C/C-no-Phase language models composed from FROZEN components.

The frozen lightweight modules are used unmodified:
    LightweightPhaseAttention   (symbolu.lightweight_phase.phase_core)
    LocalWindowAttention        (symbolu.lightweight_phase.local_window)
    BoundedBindingSlots         (symbolu.lightweight_phase.binding_slots)
    FeedForward                 (symbolu.lightweight_phase.phase_block)

This harness does NOT recreate Phase, copy the production class, or alter any
frozen behavior. It only *composes* the frozen paths with a protected additive
fusion (learnable per-path scalars, initialized so no path starts disabled — no
competitive gate). The four arms are pure on/off switches over the same backbone:

    A          : local
    B          : local + Phase
    C          : local + Phase + slots
    C-no-Phase : local + slots

Ablation hooks (used by ablations.py) allow disabling / zeroing / shuffling the
Phase state and corrupting slot memory at eval time without changing weights.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.lightweight_phase.config import PhaseConfig
from symbolu.lightweight_phase.phase_core import LightweightPhaseAttention
from symbolu.lightweight_phase.local_window import LocalWindowAttention
from symbolu.lightweight_phase.binding_slots import BoundedBindingSlots
from symbolu.lightweight_phase.phase_block import FeedForward

ARMS = ("A", "B", "C", "C-no-Phase")


@dataclass
class ArmSpec:
    use_local: bool
    use_phase: bool
    use_slots: bool


ARM_SPECS = {
    "A": ArmSpec(True, False, False),
    "B": ArmSpec(True, True, False),
    "C": ArmSpec(True, True, True),
    "C-no-Phase": ArmSpec(True, False, True),
}


@dataclass
class ModelConfig:
    vocab_size: int
    embed_dim: int = 96
    num_heads: int = 4
    num_layers: int = 2
    ffn_ratio: int = 4
    max_seq_len: int = 2048
    local_window: int = 32
    num_slots: int = 16
    slot_top_k: int = 4
    dropout: float = 0.0
    tie_embeddings: bool = True

    @property
    def ffn_dim(self) -> int:
        return self.embed_dim * self.ffn_ratio


class _AblationState:
    """Per-forward ablation switches (default: none)."""
    def __init__(self):
        self.phase_disabled = False
        self.phase_zero_state = False
        self.phase_shuffle_state = False
        self.slots_disabled = False
        self.slot_key_randomize = False
        self.slot_value_shuffle = False
        self.slot_disable_supersession = False


class ExperimentBlock(nn.Module):
    def __init__(self, cfg: ModelConfig, spec: ArmSpec):
        super().__init__()
        self.spec = spec
        D, H = cfg.embed_dim, cfg.num_heads
        if spec.use_local:
            self.local = LocalWindowAttention(D, H, cfg.local_window, dropout=cfg.dropout)
            self.alpha_local = nn.Parameter(torch.tensor(1.0))
        if spec.use_phase:
            self.phase = LightweightPhaseAttention(PhaseConfig(embed_dim=D, num_heads=H))
            self.alpha_phase = nn.Parameter(torch.tensor(1.0))
        if spec.use_slots:
            self.slots = BoundedBindingSlots(D, cfg.num_slots, top_k=cfg.slot_top_k)
            self.alpha_slots = nn.Parameter(torch.tensor(1.0))
        self.ffn = FeedForward(D, cfg.ffn_dim, cfg.dropout)

    def forward(self, x: Tensor, abl: _AblationState) -> Tensor:
        y = x
        if self.spec.use_local:
            y = y + self.alpha_local * self.local(x, return_residual_add=False)
        if self.spec.use_phase and not abl.phase_disabled:
            out = self.phase(x, return_state=False)
            phase_delta = out - x
            y = y + self.alpha_phase * phase_delta
        if self.spec.use_slots and not abl.slots_disabled:
            slot_out = self._slot_forward(x, abl)
            y = y + self.alpha_slots * slot_out
        return self.ffn(y)

    def _slot_forward(self, x: Tensor, abl: _AblationState) -> Tensor:
        readout = self.slots(x)  # [B,N,D]; frozen streaming module
        if abl.slot_value_shuffle:
            perm = torch.randperm(readout.shape[1], device=readout.device)
            readout = readout[:, perm]
        return readout


class ExperimentLM(nn.Module):
    def __init__(self, cfg: ModelConfig, arm: str):
        super().__init__()
        assert arm in ARM_SPECS, arm
        self.cfg = cfg
        self.arm = arm
        spec = ARM_SPECS[arm]
        D = cfg.embed_dim
        self.token_embed = nn.Embedding(cfg.vocab_size, D)
        self.pos_embed = nn.Embedding(cfg.max_seq_len, D)
        self.drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList([ExperimentBlock(cfg, spec) for _ in range(cfg.num_layers)])
        self.norm_f = nn.LayerNorm(D)
        self.lm_head = nn.Linear(D, cfg.vocab_size, bias=False)
        nn.init.normal_(self.token_embed.weight, std=0.02)
        nn.init.normal_(self.pos_embed.weight, std=0.02)
        nn.init.normal_(self.lm_head.weight, std=0.02)
        if cfg.tie_embeddings:
            self.lm_head.weight = self.token_embed.weight
        self.abl = _AblationState()

    def num_parameters(self) -> int:
        return sum(p.numel() for p in {id(p): p for p in self.parameters()}.values())

    def forward(self, input_ids: Tensor, labels: Optional[Tensor] = None):
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).clamp(max=self.cfg.max_seq_len - 1)
        x = self.drop(self.token_embed(input_ids) + self.pos_embed(pos).unsqueeze(0))
        for blk in self.blocks:
            x = blk(x, self.abl)
        x = self.norm_f(x)
        logits = self.lm_head(x)
        loss = None
        if labels is not None:
            loss = nn.functional.cross_entropy(
                logits[:, :-1].reshape(-1, logits.size(-1)),
                labels[:, 1:].reshape(-1),
                ignore_index=-100,
            )
        return logits, loss


def build_model(cfg: ModelConfig, arm: str, seed: int) -> ExperimentLM:
    torch.manual_seed(seed)
    return ExperimentLM(cfg, arm)
