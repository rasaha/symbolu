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
                bb.d_model, bb.n_heads, bb.d_ff, cfg.refine_steps,
                min_strength=cfg.refine_min_strength,
                residual_scale=cfg.refine_residual_scale,
                fixed_steps=cfg.refine_fixed_steps)
        if cfg.memory:
            self.memory = CausalPrefixMemory(bb.d_model)
        if cfg.freeze_aug:                                  # random-aug control
            for name in ("heads", "refine", "memory"):
                mod = getattr(self, name, None)
                if mod is not None:
                    for p in mod.parameters():
                        p.requires_grad_(False)

    def forward(self, ids: torch.Tensor, disabled=frozenset()) -> Dict[str, torch.Tensor]:
        """`disabled` ablates modules at inference for contribution measurement:
        {'typed_heads'} or {'entropy'} zero the entropy signal; {'refine'} /
        {'memory'} skip that actuator (h passes through unchanged)."""
        cfg = self.cfg
        h = self.lm.hidden(ids)                             # [B,L,d] causal
        aux: Dict[str, torch.Tensor] = {}
        if cfg.extra_plain_block:
            h = self.extra_block(h)
        aux["act_norm"] = h.norm().detach()                 # backbone activation norm
        aux["act_norm_grad"] = h.norm()                     # (for residual-ratio reg)
        ent = None
        if cfg.typed_heads:
            tout = self.heads(h)
            aux.update(tout)
            ent = TypedHeadBank.entropies(tout)             # [B,L,3]
            if "typed_heads" in disabled or "entropy" in disabled:
                ent = torch.zeros_like(ent)
            aux["entropy_vec"] = ent
            aux["entropy_mean"] = ent.mean().detach()
            aux["entropy_std"] = ent.std().detach()         # ~0 => heads collapsed
        if cfg.entropy_refine and ent is not None and "refine" not in disabled:
            h, info = self.refine(h, ent)
            aux["ponder_cost"] = info["ponder_cost"]
            aux["refine_residual_norm"] = info["residual_post_gate_norm"]
            aux["refine_gate_mean"] = info["gate_mean"]
            aux["refine_halt_p"] = info["halt_p_mean"]
            aux["refine_halt_p_grad"] = info["halt_p_grad"]
            aux["refine_resid_grad"] = info["resid_grad"]
        if cfg.memory and ent is not None and "memory" not in disabled:
            h, minfo = self.memory(h, ent)
            aux["mem_readiness"] = minfo["readiness"]
            aux["mem_residual_norm"] = minfo["residual_norm"]
            aux["mem_readiness_grad"] = minfo["readiness_grad"]
            aux["mem_resid_grad"] = minfo["resid_grad"]
        aux["logits"] = self.lm.logits(h)
        return aux

    def num_params(self, trainable_only: bool = False) -> int:
        ps = (p for p in self.parameters() if p.requires_grad or not trainable_only)
        return sum(p.numel() for p in ps)
