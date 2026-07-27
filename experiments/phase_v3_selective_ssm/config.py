"""
config.py — study configuration for the Phase v3 selective-SSM focus-retention study.

Central hypothesis (§0): Phase becomes a usable long-range state-memory mechanism when
retention (A_t), writing (B_t) and reading (C_t) are all input-dependent, while
preserving causal streaming, bounded state, complex phase dynamics, and O(N).

Primary comparison: V3-ABC vs V2-S and V1 (§7). Primary endpoint: Phase-state focus
decoding exceeds shuffled/random controls by ≥0.20 and beats V1 through long distance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

# model / task dims
EMBED_DIM = 64
NUM_HEADS = 4
NUM_ENTITIES = 16          # focus-identity classes (Top-1 over these)
NUM_FILLER = 48            # filler token types (the distractor/noise flood)

# variants (§7). V3-ABC-M (multi-bank) only after ABC succeeds — excluded by default.
VARIANTS = ("V1", "V2-S", "V3-B", "V3-AB", "V3-ABC")
PRIMARY = "V3-ABC"

# distances between the focus cue and the probe (§10). Early smoke uses the short subset.
DISTANCES_SMOKE = (64, 128, 256)
DISTANCES_STUDY = (64, 128, 256, 512, 1024)
DISTANCES_EXTENDED = (2048, 4096)     # only if V3 succeeds through 512–1024

SEEDS = (0, 1, 2)

# training-supervision modes (§11): A fully supervised, B annealed to zero (main target),
# C end-to-end from scratch.
TRAIN_MODES = ("A_supervised", "B_annealed", "C_scratch")
MAIN_MODE = "B_annealed"


@dataclass
class TrainCfg:
    lr: float = 2e-3
    batch_size: int = 32
    # curriculum stages (§11): (train_distance, steps). Short→long; distractors scale with distance.
    stages: List[Tuple[int, int]] = field(default_factory=lambda: [
        (32, 150), (64, 150), (128, 200), (256, 250)])
    # auxiliary loss weights (§12)
    lambda_write: float = 0.5       # L_write : cue/relevant get higher B_t
    lambda_retention: float = 0.2   # L_retention : cue retained longer than filler
    lambda_read: float = 0.3        # L_read : C_t exposes focus at probe
    lambda_budget: float = 0.05     # L_budget : discourage dense writes
    lambda_stability: float = 0.02  # L_stability : bound state norm
    # supervision annealing (mode B): fraction of aux weight remaining, per stage
    anneal_schedule: Tuple[float, ...] = (1.0, 0.6, 0.3, 0.0)
    seed: int = 0


@dataclass
class DataCfg:
    num_entities: int = NUM_ENTITIES
    num_filler: int = NUM_FILLER
    relevant_event_rate: float = 0.35   # fraction of events that mention the focus entity
    event_rate: float = 0.25            # fraction of non-cue/non-probe positions that are events
    distractor_entities: int = NUM_ENTITIES - 1


# probe (§13): lightweight, regularized, with shuffled + random controls.
PROBE_L2 = 1e-3
PROBE_EPOCHS = 60
PROBE_FEATURES = ("local", "state", "raw_readout", "selective_readout",
                  "local+state", "shuffled_state", "random_state")

# acceptance thresholds (§16)
ACCEPT_STATE_MINUS_CONTROL = 0.20     # Phase-state focus decode − shuffled/random ≥ 0.20
ACCEPT_F1_OVER_V2S = 0.10             # relevance F1 exceeds V2-S by ≥0.10 …
ACCEPT_F1_ABS = 0.70                  # … or reaches ≥0.70
ACCEPT_ANNEAL_RETENTION = 0.80        # annealed keeps ≥80% of supervised
