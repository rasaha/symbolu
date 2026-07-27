"""
config.py — Autonomous Selective-Write Learning study.

Question (§0): can the validated V2-S selective-write gate B_t be learned WITHOUT
permanent gate supervision? Retained recurrence (frozen v2-S, unmodified):

    S_t = S_{t-1} + B_t(k_t ⊙ v_t)     (γ=1, ω=0, no C_t, single persistent bank)

The gate is driven through SelectivePhaseV2's existing `gate_override` hook, so the frozen
source is never modified. Per-head selective-write gates; bounded O(N) streaming.

Do NOT add: dynamic recurrent rotation, selective read C_t, multi-bank memory, slots,
hard eviction, quadratic attention.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

# reuse the validated task dims (parity with the v3 study)
from experiments.phase_v3_selective_ssm.config import (
    EMBED_DIM, NUM_HEADS, NUM_ENTITIES, NUM_FILLER, DataCfg)

# training arms (§ Required training arms)
ARMS = ("A_supervised_teacher", "B_annealed", "C_distillation",
        "D_future_relevance", "E_contrastive", "F_e2e_scratch")

# supervision-annealing schedules (arm B)
SCHEDULES = ("staged", "linear", "cosine")
MAIN_SCHEDULE = "staged"

# sparse-gate controls (§ Sparse-gate controls)
GATE_TYPES = ("sigmoid", "sparse_budget", "hard_st", "topk")
MAIN_GATE = "sigmoid"

SEEDS = (0, 1, 2)

# distances (§ Primary task) and distractor counts
DISTANCES = (64, 128, 256, 512, 1024, 2048, 4096)
DISTANCES_SMOKE = (128, 256, 512)
DISTRACTOR_COUNTS = (8, 16, 32, 64, 128, 256)   # controlled via event density / entity pool

# causal controls (§ Required causal controls) — applied at eval via gate/data overrides
CONTROLS = ("gate_force_one", "gate_force_zero", "gate_shuffle_examples",
            "gate_shuffle_positions", "gate_random_matched", "remove_focus_header",
            "shuffle_focus_identity", "randomize_teacher_labels", "shuffle_future_labels")


@dataclass
class TrainCfg:
    lr: float = 2e-3
    batch_size: int = 32
    # curriculum (train_distance, steps); short→long
    stages: List[Tuple[int, int]] = field(default_factory=lambda: [
        (32, 150), (64, 150), (128, 200), (256, 250)])
    # after supervision reaches zero, keep training end-to-end for this many extra steps
    post_anneal_steps: int = 250
    # loss weights
    lambda_gate: float = 0.5       # write-gate supervision (arms A, D)
    lambda_distill: float = 1.0    # KL/BCE to teacher gate (arm C)
    lambda_contrastive: float = 0.5
    lambda_budget: float = 0.05    # write-budget (sparse gate control)
    lambda_stability: float = 0.02
    contrastive_margin: float = 0.3
    seed: int = 0


# probe (§13-style; reuse the v3 probe machinery, but NO new selective readout)
PROBE_FEATURES = ("state", "readout")     # recurrent state + EXISTING phase readout only

# acceptance thresholds (§ Acceptance criteria)
ACCEPT_RETAIN_FRAC = 0.80      # zero-supervision student ≥ 80% of supervised teacher
ACCEPT_TOP1_2048 = 0.70        # Phase-state Top-1 ≥ 0.70 through 2048
PREFERRED_TOP1_2048 = 0.80
PREFERRED_TOP1_4096 = 0.60
ACCEPT_MARGIN = 0.0            # relevant write score − distractor > 0 (stable positive)
