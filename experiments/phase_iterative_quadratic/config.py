"""
config.py — Iterative Phase-Routed bounded-softmax hybrid (9P:3Q).

Hypothesis: static routing fails multi-hop because hop-2 relevance is unknown before hop-1 is
read. A bounded quadratic softmax block composes first-hop evidence into an UPDATED query, after
which the router discovers the next hop. Phase stays frozen (V2-S, γ=1, ω=0); it only chooses
which global events enter the bounded attention set — never Q/K/V, logits, or identities.
"""
from __future__ import annotations

from dataclasses import dataclass

from experiments.phase_capacity_router.config import DataCfg  # reuse the (entity,relation) task

EMBED_DIM = 64
NUM_HEADS = 4

# bounded attention (§5)
W_WINDOW = 32
K_ROUTED = 8

# pilot arms (§8)
PILOT_ARMS = ("P0-static-cond", "P1-static-phase", "I0-iter-cond", "I1-iter-cosine",
              "I2-iter-bilinear", "I3-iter-phase", "I4-phase-zero", "I5-phase-shuffled",
              "I6-random", "I7-oracle", "Q-local")

SEEDS = (0, 1, 2)


@dataclass
class TrainCfg:
    lr: float = 2e-3
    batch_size: int = 32
    steps: int = 2500              # oracle needs ~1600+ to converge; static/iterative comparably
    seed: int = 0
    margin: float = 0.5
    lambda_route: float = 1.0     # per-hop routing ranking loss
    lambda_align: float = 0.3     # updated query ↔ next-hop event alignment


# pilot validity gate (§7)
GATE_STATIC_MAX = 0.25
GATE_ORACLE_MIN = 0.85
GATE_ITER_LO, GATE_ITER_HI = 0.35, 0.75

# acceptance (§15)
ACCEPT_ITER_OVER_STATIC = 0.15
ACCEPT_PHASE_OVER_ITERCOND = 0.05
