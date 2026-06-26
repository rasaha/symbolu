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
        if cfg.recur_plain:                                 # refine control
            from .controls import RecurrentPlainRefine
            self.recur = RecurrentPlainRefine(
                bb.d_model, bb.n_heads, bb.d_ff, cfg.recur_plain_steps)
        if cfg.mem_control:                                 # memory control
            from .controls import PointwiseMemoryControl
            self.memctrl = PointwiseMemoryControl(bb.d_model)
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
        # layer-aware tap (additive; control_layer == -1 -> current behavior)
        if getattr(cfg, "control_layer", -1) is not None and cfg.control_layer >= 0:
            layers = self.lm.hidden_all_layers(ids)
            h = layers[-1]                                  # LM path uses final
            h_tap = layers[cfg.control_layer]               # heads read this zone
        else:
            h = self.lm.hidden(ids)                         # [B,L,d] causal
            h_tap = h
        aux: Dict[str, torch.Tensor] = {}
        if cfg.extra_plain_block:
            h = self.extra_block(h)
            h_tap = h_tap if cfg.control_layer >= 0 else h
        aux["act_norm"] = h.norm().detach()                 # backbone activation norm
        aux["act_norm_grad"] = h.norm()                     # (for residual-ratio reg)
        ent = None
        if cfg.typed_heads:
            head_in = h_tap.detach() if getattr(cfg, "stopgrad_heads", False) else h_tap
            tout = self.heads(head_in)
            aux.update(tout)
            # CONTROL entropy honors the head-role policy (cfg.control_heads).
            ent = TypedHeadBank.entropies(tout, getattr(cfg, "control_heads", None))
            if "typed_heads" in disabled or "entropy" in disabled:
                ent = torch.zeros_like(ent)
            aux["entropy_vec"] = ent
            aux["entropy_mean"] = ent.mean().detach()
            aux["entropy_std"] = ent.std().detach()         # ~0 => heads collapsed
            aux.update(TypedHeadBank.per_head_entropy(tout))  # diagnostics for ALL heads
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
        if cfg.recur_plain and "recur" not in disabled:     # control path
            h = self.recur(h)
        if cfg.mem_control and "mem_control" not in disabled:
            h = self.memctrl(h)
        aux["logits"] = self.lm.logits(h)
        return aux

    def num_params(self, trainable_only: bool = False) -> int:
        ps = (p for p in self.parameters() if p.requires_grad or not trainable_only)
        return sum(p.numel() for p in ps)
