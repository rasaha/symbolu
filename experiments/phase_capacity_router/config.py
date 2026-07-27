"""
config.py — Phase-as-admission-router study.

Decisive question: when memory capacity binds (admit K of N candidate events into a bounded
EXACT store), does the frozen V2-S Phase relevance matcher admit the right events often enough
to improve exact downstream answers, causally dependent on the focus summary?

Phase recurrence is FROZEN (S_t = S_{t-1}+B_t(k⊙v), γ=1, ω=0, one bank, existing readout,
validated matcher). Phase only SCORES candidates; a bounded exact store does identity binding
and retrieval. The store is fully exact (oracle identity→value) so answer accuracy is a direct
function of admission quality — no neural decoder confounds the test.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from experiments.phase_v3_selective_ssm.config import EMBED_DIM, NUM_HEADS

NUM_ENTITIES = 32          # event identities (larger pool → more distinct events)
NUM_VALUES = 32            # answer values

# task families (§4)
FAMILIES = ("single", "multihop", "update", "hardneg")

# router arms (§7)
ROUTERS = ("R-random", "R-recency", "R-frequency", "R-token", "R-COND",
           "R-cosine", "R-bilinear", "R-bilinear-hard", "R-shuffled", "R-removed",
           "R-oracle", "R-unlimited")
LEARNED = ("R-token", "R-COND", "R-cosine", "R-bilinear", "R-bilinear-hard")

# capacity ladder (§12): (N_events, [K...])
LADDER = [(16, [2, 4, 8]), (32, [2, 4, 8]), (64, [4, 8, 16]), (128, [4, 8, 16])]
SEEDS = (0, 1, 2)


@dataclass
class DataCfg:
    num_entities: int = NUM_ENTITIES
    num_values: int = NUM_VALUES
    n_relevant: int = 1            # one relevant event (entity=focus); avoids exact-store key collision
    n_hard: int = 6                # frequency-matched hard negatives
    family: str = "single"
    multihop_depth: int = 2


@dataclass
class TrainCfg:
    lr: float = 2e-3
    batch_size: int = 32
    steps: int = 700               # matcher training steps (single stage; task is fixed-form)
    margin: float = 0.5
    seed: int = 0


# saturation window (§11)
SAT_RANDOM_MAX = 0.35
SAT_COND_LO, SAT_COND_HI = 0.35, 0.75
SAT_ORACLE_MIN = 0.85

# acceptance (§16)
ACCEPT_ADMISSION_GAIN = 0.10       # matcher − COND relevant admission recall
ACCEPT_ACC_GAIN = 0.10             # matcher − COND exact answer accuracy
ACCEPT_ORACLE_GAP_CLOSURE = 0.40   # preferred: close ≥40% of COND→oracle gap at N/K≥8
