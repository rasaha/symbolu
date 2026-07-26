"""
config.py — Typed, frozen configuration for the Lightweight Phase Transformer.

This module is dependency-light: it imports only the Python standard library.
Every knob that affects the *mathematics* of the Phase core lives here so that a
config hash uniquely determines forward behavior (see ``PhaseConfig.hash``).

Design contract (Stage 1, frozen v1.0):
  * The canonical amplitude parameterization is ``a = amp_floor + amp_scale * sigmoid(.)``.
    Canonical defaults are ``amp_floor=0.0, amp_scale=1.0`` → a = sigmoid(.), matching
    the frozen reference equations in ``reference_equations.md``.
  * The production ``PhaseAttentionLayer`` uses ``amp_floor=0.05, amp_scale=0.95``.
    The equivalence harness (Stage 4) sets those values explicitly; it never silently
    changes the canonical default.
  * ``bounded_phase=True`` (φ = π·sin(raw)) is mandatory for stability and is the
    canonical default, matching the production ``bounded_phase`` fix.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Literal

DecayMode = Literal["none", "fixed_scalar", "fixed_per_head", "learned_per_head"]


@dataclass(frozen=True)
class PhaseConfig:
    """Configuration for :class:`~symbolu.lightweight_phase.phase_core.LightweightPhaseAttention`.

    Attributes are grouped by stage so the freeze history is legible.

    Stage 1 (Phase Core v1.0) — the fields below fully determine the non-decay forward:
        embed_dim, num_heads, bounded_phase, amp_floor, amp_scale,
        denom_eps, aux_scale, dropout, layernorm_eps

    Stage 3 (Decay Phase v1.2) — decay fields; ``decay_mode="none"`` reproduces Stage 1:
        decay_mode, gamma_min, gamma_max, initial_gamma
    """

    # -- core dimensions ---------------------------------------------------
    embed_dim: int = 64
    num_heads: int = 4

    # -- phase / amplitude parameterization (Stage 1) ----------------------
    bounded_phase: bool = True
    amp_floor: float = 0.0
    amp_scale: float = 1.0

    # -- normalizer (Stage 1) ---------------------------------------------
    # Z_t = stopgrad(max(a_q * A_t, denom_eps)). Detachment is a FROZEN contract,
    # never an incidental detail (see reference_equations.md §5).
    denom_eps: float = 0.1
    detach_denominator: bool = True

    # -- output scaling / regularization (Stage 1) ------------------------
    aux_scale: float = 1.0  # canonical = 1.0; production PhaseAttentionLayer default = 0.1
    dropout: float = 0.0
    layernorm_eps: float = 1e-5

    # -- decay (Stage 3) ---------------------------------------------------
    decay_mode: DecayMode = "none"
    gamma_min: float = 0.90
    gamma_max: float = 0.99999
    initial_gamma: float = 0.99  # used by fixed_scalar / fixed_per_head init

    # -- provenance --------------------------------------------------------
    version: str = "1.2"  # frozen stage version this config schema belongs to

    def __post_init__(self) -> None:
        if self.embed_dim % self.num_heads != 0:
            raise ValueError(
                f"embed_dim ({self.embed_dim}) must be divisible by num_heads ({self.num_heads})"
            )
        if not (0.0 < self.gamma_min <= self.gamma_max <= 1.0):
            raise ValueError(
                f"require 0 < gamma_min <= gamma_max <= 1, got {self.gamma_min}, {self.gamma_max}"
            )
        if not (self.gamma_min <= self.initial_gamma <= self.gamma_max):
            raise ValueError(
                f"initial_gamma ({self.initial_gamma}) must lie in [gamma_min, gamma_max]"
            )
        if self.decay_mode not in ("none", "fixed_scalar", "fixed_per_head", "learned_per_head"):
            raise ValueError(f"unknown decay_mode: {self.decay_mode!r}")
        if self.amp_scale <= 0.0:
            raise ValueError("amp_scale must be positive")
        if self.denom_eps <= 0.0:
            raise ValueError("denom_eps must be positive")

    @property
    def head_dim(self) -> int:
        return self.embed_dim // self.num_heads

    @property
    def uses_decay(self) -> bool:
        return self.decay_mode != "none"

    def to_dict(self) -> dict:
        return asdict(self)

    def canonical_json(self) -> str:
        """Deterministic JSON encoding used for hashing (sorted keys)."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def hash(self) -> str:
        """SHA-256 of the canonical JSON — the config hash recorded in frozen manifests."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TransformerConfig:
    """Configuration for the Lightweight Phase Transformer LM (Stage 5)."""

    vocab_size: int = 256
    phase: PhaseConfig = field(default_factory=PhaseConfig)
    num_layers: int = 2
    ffn_ratio: int = 4
    max_seq_len: int = 512
    tie_embeddings: bool = True
    dropout: float = 0.0

    # Stage 6 — sliding-window local path (disabled by default so Stage 5 is Phase-only)
    use_local_window: bool = False
    local_window_size: int = 32
    # protected additive fusion initial mixing coefficients (Stage 6)
    local_alpha_init: float = 1.0
    phase_alpha_init: float = 1.0

    @property
    def embed_dim(self) -> int:
        return self.phase.embed_dim

    @property
    def ffn_dim(self) -> int:
        return self.embed_dim * self.ffn_ratio

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
