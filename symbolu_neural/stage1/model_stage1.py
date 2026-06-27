"""Stage1GroundingModel — frozen backbone + Symbol-U typed heads ONLY.

No new architecture: it reuses VrittiHead/AspectHead/GunaHead/KoshaHead from
symbolu_neural.modules.typed_heads, applied to unit-pooled frozen backbone
representations. The backbone is asserted frozen; only head parameters train.
"""
from __future__ import annotations

from typing import Dict, List

import torch
import torch.nn as nn

from ..modules.typed_heads import VrittiHead, AspectHead, GunaHead, KoshaHead
from ..modules.entropy import shannon_entropy

_HEAD_CLS = {"vritti": VrittiHead, "aspect": AspectHead,
             "guna": GunaHead, "kosha": KoshaHead}


class Stage1GroundingModel(nn.Module):
    def __init__(self, backbone: nn.Module, d_model: int,
                 heads: List[str] = ("vritti", "aspect")):
        super().__init__()
        self.backbone = backbone
        for p in self.backbone.parameters():
            p.requires_grad_(False)                       # enforce frozen
        self.heads = nn.ModuleDict({h: _HEAD_CLS[h](d_model) for h in heads})

    def head_parameters(self):
        return self.heads.parameters()

    def assert_backbone_frozen(self) -> None:
        assert all(not p.requires_grad for p in self.backbone.parameters()), \
            "backbone must be frozen in Stage-1"

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor,
                pool: torch.Tensor) -> Dict[str, torch.Tensor]:
        """input_ids:[B,L], pool:[B,U,L] -> {head: log_p[B,U,C]}."""
        with torch.no_grad():
            h = self.backbone.encode(input_ids, attention_mask)   # [B,L,d]
        unit_reps = torch.bmm(pool, h)                            # [B,U,d]
        return {h_name: head(unit_reps) for h_name, head in self.heads.items()}

    @staticmethod
    def entropy(log_p: torch.Tensor) -> torch.Tensor:
        """Per-unit predictive entropy from log-probs [B,U,C] -> [B,U]."""
        return shannon_entropy(log_p)
