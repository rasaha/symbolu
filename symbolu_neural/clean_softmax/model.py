"""SymbolUSoftmaxModel — clean softmax backbone + optional causal Symbol-U path.

Returns LM logits and an `aux` dict (typed distributions, entropy, ponder).
Everything that touches the LM-loss path is causal. Memory/typed-supervision are
optional and clearly separated from the headline next-token objective.
"""
from __future__ import annotations

from typing import Dict

import torch
import torch.nn as nn

from .backbone import SoftmaxTransformerLM, CausalBlock
from .augment import TypedHeadBank, CausalEntropyRefinement, CausalPrefixMemory
from .config import ExpConfig


class SymbolUSoftmaxModel(nn.Module):
    def __init__(self, cfg: ExpConfig):
        super().__init__()
        self.cfg = cfg
        bb = cfg.backbone
        self.lm = SoftmaxTransformerLM(bb)
        if cfg.extra_plain_block:
            self.extra_block = CausalBlock(bb.d_model, bb.n_heads, bb.d_ff)
        if cfg.typed_heads:
            self.heads = TypedHeadBank(bb.d_model)
        if cfg.entropy_refine:
            self.refine = CausalEntropyRefinement(
                bb.d_model, bb.n_heads, bb.d_ff, cfg.refine_steps)
        if cfg.memory:
            self.memory = CausalPrefixMemory(bb.d_model)
        if cfg.freeze_aug:                                  # random-aug control
            for name in ("heads", "refine", "memory"):
                mod = getattr(self, name, None)
                if mod is not None:
                    for p in mod.parameters():
                        p.requires_grad_(False)

    def forward(self, ids: torch.Tensor) -> Dict[str, torch.Tensor]:
        cfg = self.cfg
        h = self.lm.hidden(ids)                             # [B,L,d] causal
        aux: Dict[str, torch.Tensor] = {}
        if cfg.extra_plain_block:
            h = self.extra_block(h)
        ent = None
        if cfg.typed_heads:
            tout = self.heads(h)
            aux.update(tout)
            ent = TypedHeadBank.entropies(tout)             # [B,L,3]
            aux["entropy_vec"] = ent
        if cfg.entropy_refine and ent is not None:
            h, info = self.refine(h, ent)
            aux["ponder_cost"] = info["ponder_cost"]
        if cfg.memory and ent is not None:
            h, minfo = self.memory(h, ent)
            aux["mem_readiness"] = minfo["readiness"]
        aux["logits"] = self.lm.logits(h)
        return aux

    def num_params(self, trainable_only: bool = False) -> int:
        ps = (p for p in self.parameters() if p.requires_grad or not trainable_only)
        return sum(p.numel() for p in ps)
