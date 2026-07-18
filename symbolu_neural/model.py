"""SymbolUModel — assembles the EQ-group modules onto a backbone.

This is an *interface* assembly: it wires the modules, threads tensors with the
documented shapes, and returns LM logits plus an ``aux`` dict carrying every
intermediate distribution / scalar that the loss functions and ablations consume.
Full training is intentionally NOT implemented here (see README milestones).

Dataflow (see README block diagram):
  ids -> backbone h:[B,L,d] -> (seg) u:[B,n,d]
      -> Vritti/Aspect heads -> AspectAggregator p_w:[B,10]
      -> Guna/Kosha heads (on pooled h) -> EntropyEngine -> refinement core
      -> (memory / anchors / DHA conditioning) -> LM logits
      -> HardSafetyBoundary (admit mask, scorer supervision)
"""
from __future__ import annotations

from typing import Dict, Optional

import torch
import torch.nn as nn

from .config import SymbolUConfig
from .backbone import BackboneWrapper
from .modules import (
    SoftSyllableSegmenter, VrittiHead, AspectHead, AspectAggregator,
    GunaHead, KoshaHead, ContextVrittiCoupling, EntropyEngine,
    EntropyGatedRefinementCore, SoftStitchingSelector, DeferredInsightMemory,
    ExperienceAnchorRouter, DeliveryHarmonizationHead, HardSafetyBoundary,
)


class SymbolUModel(nn.Module):
    def __init__(self, cfg: SymbolUConfig, backbone: BackboneWrapper):
        super().__init__()
        cfg.assert_consistent()
        self.cfg = cfg
        self.backbone = backbone
        d = cfg.d_model

        if cfg.freeze_backbone:
            backbone.freeze()
            backbone.unfreeze_last_n_layers(cfg.unfreeze_last_n_backbone_layers)

        if cfg.enable_segmentation:
            self.segmenter = SoftSyllableSegmenter(d, cfg.seg_stride)
        if cfg.enable_typed_heads:
            self.vritti = VrittiHead(d)
            self.aspect = AspectHead(d)
            self.aspect_agg = AspectAggregator(d)
            self.guna = GunaHead(d)
            self.kosha = KoshaHead(d)
            self.coupling = ContextVrittiCoupling(d)
        if cfg.enable_entropy:
            self.entropy = EntropyEngine(cfg.sigmoid_sharpness_init, cfg.entropy_eps)
        if cfg.enable_refinement:
            self.refine = EntropyGatedRefinementCore(
                d, cfg.refine_max_steps, cfg.refine_halt_eps, cfg.n_router_modes)
        if cfg.enable_stitching:
            self.stitch = SoftStitchingSelector(d, cfg.stitch_topk, cfg.stitch_temp)
        if cfg.enable_memory:
            self.memory = DeferredInsightMemory(d, cfg.mem_slots, cfg.mem_readiness_dim)
        if cfg.enable_anchors:
            self.anchors = ExperienceAnchorRouter(d, cfg.anchor_hysteresis_ema)
        if cfg.enable_dha:
            self.dha = DeliveryHarmonizationHead(d, cfg.dha_gumbel_temp)
        if cfg.enable_safety:
            self.safety = HardSafetyBoundary(d, cfg.n_safety_scorers)
        # projection used when refinement runs on segmented units (n != L)
        self.unit_to_seq = nn.Linear(d, d)

    def forward(
        self, input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        dt: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        cfg = self.cfg
        aux: Dict[str, torch.Tensor] = {}
        h, base_logits = self.backbone(input_ids, attention_mask)   # [B,L,d],[B,L,V]
        B, L, d = h.shape
        pooled = h.mean(dim=1)                                       # [B,d] context C

        units = h
        if cfg.enable_segmentation:
            units, align = self.segmenter(h, attention_mask)        # [B,n,d]
            aux["seg_align"] = align

        if cfg.enable_typed_heads:
            log_p_v = self.vritti(units)                            # [B,n,5]
            log_p_w_syl = self.aspect(units)                        # [B,n,10]
            log_p_w = self.aspect_agg(log_p_w_syl, units)           # [B,10]
            log_p_g = self.guna(pooled)                             # [B,3]
            log_p_k = self.kosha(pooled)                            # [B,5]
            s_c = self.coupling(log_p_v, pooled)                   # [B,n]
            aux.update(log_p_v=log_p_v, log_p_w_syl=log_p_w_syl,
                       log_p_w=log_p_w, log_p_g=log_p_g,
                       log_p_k=log_p_k, s_c=s_c)

        ent = None
        if cfg.enable_entropy and cfg.enable_typed_heads:
            ent = self.entropy(log_p_w, log_p_g, log_p_k)
            aux.update({k: v for k, v in ent.items()})

        refined = h
        if cfg.enable_refinement and ent is not None:
            seq = self.unit_to_seq(units) if cfg.enable_segmentation else h
            refined_units, info = self.refine(seq, ent["entropy_vec"])
            aux["ponder_cost"] = info["ponder_cost"]
            aux["final_delta"] = info["final_delta"]
            # broadcast refined unit signal back to token resolution (residual)
            refined = h + refined_units.mean(dim=1, keepdim=True)

        cond = refined
        if cfg.enable_memory and ent is not None:
            feats = torch.stack(
                [ent["H_D"], ent["H_G"], ent["H_K"],
                 (dt if dt is not None else torch.zeros_like(ent["H_D"]))], dim=-1)
            recall, minfo = self.memory(refined.mean(1), feats)
            aux["mem_readiness"] = minfo["readiness"]
            cond = refined + recall.unsqueeze(1)

        if cfg.enable_anchors and ent is not None:
            anchor_mix, ainfo = self.anchors(cond.mean(1), ent["entropy_vec"])
            aux["anchor_w"] = ainfo["w"]
            cond = cond + anchor_mix.unsqueeze(1)

        if cfg.enable_dha and ent is not None:
            ready = aux.get("mem_readiness", torch.zeros(B, 1, device=h.device)).squeeze(-1)
            ctrl = torch.stack([ent["H_D"], ent["H_G"], ent["H_K"], ready], dim=-1)
            style, dinfo = self.dha(cond.mean(1), ctrl)
            aux["mode_logits"] = dinfo["mode_logits"]
            cond = cond + style.unsqueeze(1)

        logits = self.backbone.model.logits(cond) \
            if hasattr(self.backbone.model, "logits") else base_logits
        aux["logits"] = logits

        if cfg.enable_safety:
            admit, sinfo = self.safety(cond.mean(1))
            aux["admit_mask"] = admit
            aux["safety_scores"] = sinfo["soft_scores"]

        return aux
