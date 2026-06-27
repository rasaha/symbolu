"""Configuration for the Symbol-U trainable neural architecture skeleton.

This is an *interface design*, not a finished model. Cardinalities are fixed by
the patent (|A|=10 aspects, |V|=5 Vritti, |G|=3 Guna, |K|=5 Kosha, 10 anchors,
3 delivery modes). Everything else (d_model, depths, temperatures, thresholds)
is a research hyperparameter and is collected here so ablations toggle cleanly.

See ``symbolu_neural/README.md`` for the full design review, tensor table,
loss table, ablation ladder, and kill criteria.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---- Patent-fixed cardinalities (do not change) ----------------------------
N_VRITTI = 5     # valid cognition, imagination, misperception, inertness, memory
N_ASPECT = 10    # Acting, Tagging, Forming, Thinking, Directing, Reasoning,
                 # Purposing, Observing, Unifying, Absolute
N_GUNA = 3       # clarity-balance, activity-desire, inertia-stillness
N_KOSHA = 5      # Physical, Vital, Emotional, Intellectual, Spiritual
N_ANCHOR = 10    # Needs, Exchange, Belonging, Expression, Challenge, Relation,
                 # Change, Meaning, Role, Collective
N_MODE = 3       # Sweet Resonance, Inverse Jolt, Symbolic Metaphor


@dataclass
class SymbolUConfig:
    # ---- backbone ----
    backbone_name: str = "sshleifer/tiny-gpt2"   # any HF causal LM; tiny for MVP
    d_model: int = 768                            # MUST match backbone hidden size
    vocab_size: int = 50257

    # ---- segmentation (EQ-A1) ----
    seg_stride: int = 2          # MVP: learned strided attention pooling window
    enable_segmentation: bool = True

    # ---- typed heads (EQ-A2/A3/B2 + Guna/Kosha) ----
    enable_typed_heads: bool = True

    # ---- entropy engine (EQ-C1..C5) ----
    enable_entropy: bool = True
    entropy_eps: float = 1e-8    # clamp for log(0)
    sigmoid_sharpness_init: float = 4.0   # kappa in EQ-C5

    # ---- entropy-gated recurrent refinement core (EQ-F1..F4/F6) ----
    enable_refinement: bool = True
    refine_max_steps: int = 4    # ACT cap == K_max
    refine_halt_eps: float = 0.01
    refine_ponder_cost: float = 1e-2
    n_router_modes: int = 2      # symbolic vs anchor (EQ-F6)

    # ---- soft stitching / differentiable selection (EQ-D1..D4) ----
    enable_stitching: bool = False   # off by default in MVP (needs candidate source)
    stitch_topk: int = 4
    stitch_temp: float = 1.0

    # ---- differentiable episodic memory (EQ-G1..G4) ----
    enable_memory: bool = False
    mem_slots: int = 64
    mem_readiness_dim: int = 4   # [H_D, H_G, H_K, dt]

    # ---- experience anchor router (EQ-H1..H4) ----
    enable_anchors: bool = False
    anchor_hysteresis_ema: float = 0.9

    # ---- delivery harmonization head (EQ-J1/J2) ----
    enable_dha: bool = False
    dha_gumbel_temp: float = 1.0

    # ---- hard safety / provenance boundary (EQ-I1..I8) ----
    enable_safety: bool = True
    n_safety_scorers: int = 3    # risk, compliance, (learned) resonance

    # ---- training-stage gating (MVP staging) ----
    freeze_backbone: bool = True             # stage 1: heads only
    unfreeze_last_n_backbone_layers: int = 0 # stage 2: > 0

    def assert_consistent(self) -> None:
        assert self.d_model > 0
        assert self.refine_max_steps >= 1
        assert 0.0 < self.anchor_hysteresis_ema < 1.0
