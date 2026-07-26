"""
config.py — single source of truth for the Phase-v2 oracle-retention study.

The experiment tests one hypothesis chain (§2):
    distant focus cue → Phase v2-S preserves its relevance in bounded state
    → the focus-target record receives higher retention priority
    → it survives eviction more often → answer accuracy improves.

Only retention/eviction priority may differ across arms. Identity allocation,
query lookup, value encoding, slot value, and the answer decoder are the oracle
components and are IDENTICAL across every arm. Frozen Phase v1 is never modified;
Phase v2-S lives in symbolu/phase_v2_experimental and is the experimental module.

Retention interface (§7):  r_final = r_local(h) + λ · normalize(r_phase([h; g_v2])),
λ ∈ [0, λ_max], initialised at 0 (learned) or pinned (lambda_fixed).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

# ---- study design (§15-16) -------------------------------------------------
ARMS: Tuple[str, ...] = ("C-oracle", "D-v2", "D-zero", "D-random", "D-shuffled")
# D-v1 (frozen Phase v1 as retention signal) is an OPTIONAL negative baseline.
ARMS_OPTIONAL: Tuple[str, ...] = ("D-v1",)
SEEDS: Tuple[int, ...] = (0, 1, 2)
PRESSURES: Tuple[int, ...] = (12, 16)   # n_live records competing for M=8 slots
NUM_SLOTS: int = 8

# ---- retention interface (§7) ----------------------------------------------
LAMBDA_MAX: float = 0.25
LAMBDA_STUDY: float = 0.25    # fixed λ used in the main study (bounded, non-dominant)
LAMBDA_SWEEP: Tuple[float, ...] = (0.0, 0.01, 0.05, 0.10, 0.25)

# ---- curriculum (§11) ------------------------------------------------------
# Warm up capacity gradually, then train at the evaluation pressure. The final
# (n_live, steps) stage is appended per pressure in run_study.train_arm.
CURRICULUM_BASE: List[Tuple[int, int]] = [(2, 100), (4, 120), (8, 150)]
FINAL_STAGE_STEPS: int = 180

# ---- data (§10) ------------------------------------------------------------
TRAIN_EXAMPLES: int = 300
TEST_EXAMPLES: int = 200
RECORD_LEN: int = 8            # tokens per record (fact) in the pressure task
TRAIN_SEED_BASE: int = 0
TEST_SEED_BASE: int = 1000     # test seeds are disjoint from train seeds


@dataclass
class StudyCfg:
    arms: Tuple[str, ...] = ARMS
    seeds: Tuple[int, ...] = SEEDS
    pressures: Tuple[int, ...] = PRESSURES
    num_slots: int = NUM_SLOTS
    lambda_study: float = LAMBDA_STUDY
    curriculum_base: List[Tuple[int, int]] = field(
        default_factory=lambda: list(CURRICULUM_BASE))
    final_stage_steps: int = FINAL_STAGE_STEPS
    train_examples: int = TRAIN_EXAMPLES
    test_examples: int = TEST_EXAMPLES


# ---- acceptance thresholds (§16) -------------------------------------------
# Primary endpoint: Δsurvival = P_{D-v2}(target survives) − P_{C-oracle}(...).
ACCEPT_SURVIVAL_GAIN: float = 0.10   # D-v2 − C must clear this at n_live 12 or 16
# Controls: D-zero ≈ C; D-random, D-shuffled ≤ C; the gain must hold across seeds
# and appear in early/middle target positions (not only late).
