"""
config.py — configuration for the EXPERIMENTAL Phase v3 (selective complex
state-space memory). NOT canonical: frozen v1 (symbolu.lightweight_phase) and the
completed v2 (symbolu.phase_v2_experimental) are untouched.

Phase v3 recurrence (per head; controls are input-dependent functions of h_t only):
    A_t = γ_t · e^{i·ω_t}            (input-dependent retention + complex rotation)
    S_t = A_t ⊙ S_{t-1} + B_t ⊙ (k_t ⊙ v_t)     (input-dependent selective write B_t)
    o_t = C_t ⊙ Re(q_t ⊙ S_t) / Z_t             (input-dependent selective read C_t)

with
    γ_t = γ_min + (γ_max-γ_min)·σ(W_γ h_t + b_γ)      ∈ [γ_min, γ_max]
    ω_t = ω_max·tanh(W_ω h_t + b_ω)                   ∈ [-ω_max, ω_max]
    B_t = σ(W_B h_t + b_B) ∈ [0,1]   C_t = σ(W_C h_t + b_C) ∈ [0,1]
    Z_t = clamp(a_q ⊙ R_t, denom_eps),  R_t = γ_t·R_{t-1} + B_t·a_k   (amplitude accumulator)

The phase encoding (bounded phase map, complex k/v construction, amplitude, normalizer
clamp + detachment, causal layout) is preserved from v1/v2 (§8). Only the state
dynamics — retention A_t, write B_t, read C_t — become input-dependent.

Each control can independently be `input_dependent` (learned) or fixed, which yields
the required variants and ablations:
    V3-B   : write only     (retention fixed γ=const ω=0, read C=1)
    V3-AB  : retention+write (read C=1)
    V3-ABC : retention+write+read
Ablation `*_mode` overrides force / shuffle / detach a control at eval time.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

# per-control eval-time modes (§14). "learned" = normal; the rest are ablations.
CtrlMode = Literal["learned", "fixed", "forced_one", "forced_zero", "shuffled", "detached"]


@dataclass(frozen=True)
class PhaseV3Config:
    # core dims
    embed_dim: int = 96
    num_heads: int = 4

    # preserved phase / amplitude / normalizer parameterization (§8)
    bounded_phase: bool = True
    amp_floor: float = 0.05
    amp_scale: float = 0.95
    denom_eps: float = 0.1
    detach_denominator: bool = True
    aux_scale: float = 1.0
    layernorm_eps: float = 1e-5

    # input-dependent retention transition A_t = γ_t e^{iω_t} (§4)
    input_dependent_retention: bool = True
    gamma_min: float = 0.90
    gamma_max: float = 0.9999
    omega_max: float = 3.141592653589793      # π
    initial_gamma: float = 0.99               # bias γ toward long memory (not exact 1)
    fixed_gamma: float = 0.99                  # γ when retention is not input-dependent
    use_omega: bool = True                     # complex rotation on/off

    # input-dependent selective write B_t (§5)
    input_dependent_write: bool = True
    write_bias_init: float = 0.0               # neutral (NOT strongly negative) — §5
    fixed_write: float = 1.0                    # B_t when write is not input-dependent

    # input-dependent selective read C_t (§6)
    input_dependent_read: bool = True
    read_bias_init: float = 0.0
    fixed_read: float = 1.0                     # C_t when read is not input-dependent

    # eval-time ablation overrides (§14); "learned"/"fixed" = no override
    a_mode: CtrlMode = "learned"               # affects γ_t and ω_t together
    gamma_mode: CtrlMode = "learned"           # γ_t specifically (fixed / shuffled / detached)
    omega_mode: CtrlMode = "learned"           # ω_t specifically (forced_zero = no rotation)
    b_mode: CtrlMode = "learned"
    c_mode: CtrlMode = "learned"

    # scan
    chunk: int = 64
    num_banks: int = 1                         # multi-bank (V3-ABC-M) only after ABC succeeds

    version: str = "v3-experimental"

    def __post_init__(self):
        if self.embed_dim % self.num_heads != 0:
            raise ValueError("embed_dim must be divisible by num_heads")

    @property
    def head_dim(self) -> int:
        return self.embed_dim // self.num_heads

    def to_dict(self) -> dict:
        return asdict(self)

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


# ---- named variant configs (§7) --------------------------------------------
def cfg_v3b(embed_dim=96, num_heads=4, **kw) -> PhaseV3Config:
    """V3-B: input-dependent write only (retention fixed, read = 1)."""
    return PhaseV3Config(embed_dim=embed_dim, num_heads=num_heads,
                         input_dependent_retention=False, use_omega=False,
                         input_dependent_write=True,
                         input_dependent_read=False, **kw)


def cfg_v3ab(embed_dim=96, num_heads=4, **kw) -> PhaseV3Config:
    """V3-AB: input-dependent retention + write (read = 1)."""
    return PhaseV3Config(embed_dim=embed_dim, num_heads=num_heads,
                         input_dependent_retention=True, use_omega=True,
                         input_dependent_write=True,
                         input_dependent_read=False, **kw)


def cfg_v3abc(embed_dim=96, num_heads=4, **kw) -> PhaseV3Config:
    """V3-ABC: input-dependent retention + write + read (the primary variant)."""
    return PhaseV3Config(embed_dim=embed_dim, num_heads=num_heads,
                         input_dependent_retention=True, use_omega=True,
                         input_dependent_write=True,
                         input_dependent_read=True, **kw)
