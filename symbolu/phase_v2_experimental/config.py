"""
config.py — configuration for the EXPERIMENTAL Phase v2 (selective-write, bounded
multi-timescale). This is NOT canonical: the frozen v1 in symbolu/lightweight_phase
is untouched and remains the negative baseline.

Phase v2 recurrence (per head, per bank b):
    S_t^{(b)} = γ_b · S_{t-1}^{(b)} + w_t^{(b)} · (k_t ⊙ v_t)
with a learned write gate w_t ∈ [0,1] computed from the current token only (causal).
The frozen v1 is the special case: one bank, γ = 1, w_t ≡ 1 (dense, no decay).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import List, Literal, Tuple

GateMode = Literal["scalar_per_head", "scalar", "forced_one", "forced_zero",
                   "random", "detached"]


@dataclass(frozen=True)
class PhaseV2Config:
    # core dims
    embed_dim: int = 96
    num_heads: int = 4

    # phase / amplitude (same parameterization family as v1)
    bounded_phase: bool = True
    amp_floor: float = 0.05
    amp_scale: float = 0.95
    denom_eps: float = 0.1
    detach_denominator: bool = True
    aux_scale: float = 1.0
    layernorm_eps: float = 1e-5

    # selective write
    gate_mode: GateMode = "scalar_per_head"
    gate_bias_init: float = 0.0
    gate_local_context: bool = False   # if True, gate also sees a small causal average

    # decay / banks. `bank_gammas` lists the fixed decay per bank (len = #banks).
    #   V2-S  : [1.0]                       (selective write, no decay, single bank)
    #   V2-SD : [None]  (learned γ in [gamma_min,gamma_max])
    #   V2-M  : [0.5, 0.9, 0.99, 1.0]       (short/medium/long/persistent)
    bank_gammas: Tuple = (1.0,)
    learned_decay: bool = False
    gamma_min: float = 0.5
    gamma_max: float = 0.999999
    initial_gamma: float = 0.99

    version: str = "v2-experimental"

    def __post_init__(self):
        if self.embed_dim % self.num_heads != 0:
            raise ValueError("embed_dim must be divisible by num_heads")
        if not self.bank_gammas:
            raise ValueError("need at least one bank")

    @property
    def head_dim(self) -> int:
        return self.embed_dim // self.num_heads

    @property
    def num_banks(self) -> int:
        return len(self.bank_gammas)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["bank_gammas"] = list(self.bank_gammas)
        return d

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


# Named variant configs (embed_dim/num_heads set by caller for parity with the task).
def cfg_v2s(embed_dim=96, num_heads=4, **kw) -> PhaseV2Config:
    return PhaseV2Config(embed_dim=embed_dim, num_heads=num_heads,
                         bank_gammas=(1.0,), learned_decay=False, **kw)


def cfg_v2sd(embed_dim=96, num_heads=4, **kw) -> PhaseV2Config:
    return PhaseV2Config(embed_dim=embed_dim, num_heads=num_heads,
                         bank_gammas=(None,), learned_decay=True, **kw)


def cfg_v2m(embed_dim=96, num_heads=4, **kw) -> PhaseV2Config:
    return PhaseV2Config(embed_dim=embed_dim, num_heads=num_heads,
                         bank_gammas=(0.5, 0.9, 0.99, 1.0), learned_decay=False, **kw)
