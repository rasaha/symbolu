"""Config + ablation presets for the clean-softmax Symbol-U experiment."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Dict

from .backbone import BackboneConfig


@dataclass
class ExpConfig:
    backbone: BackboneConfig = field(default_factory=BackboneConfig)
    # augmentation toggles
    typed_heads: bool = False
    entropy_refine: bool = False        # entropy-gated causal refinement on LM path
    memory: bool = False                # causal prefix memory on LM path
    extra_plain_block: bool = False     # FAIR-COMPUTE control: +1 plain causal block
    freeze_aug: bool = False            # random (untrained) augmentation control
    # capacity-/FLOP-matched controls (controls.py)
    recur_plain: bool = False           # shared plain block applied recur_plain_steps times
    recur_plain_steps: int = 3
    mem_control: bool = False           # pointwise FFN control (params ~ memory)
    refine_steps: int = 3
    refine_min_strength: float = 0.1    # gate floor: refinement cannot collapse to 0
    refine_residual_scale: float = 1.0  # fixed scale on the refinement delta
    refine_fixed_steps: bool = False    # smoke mode: bypass ACT halting entirely
    # --- layer-aware staged control (additive; defaults = current behavior) ---
    control_layer: int = -1             # which layer feeds the typed heads/entropy;
                                        # -1 = final-normed (current). >=0 taps that
                                        # block output (0..n_layers).
    stopgrad_heads: bool = False        # True = typed heads are diagnostic/validation
                                        # only (no gradient into the backbone)
    # head-role policy: which typed heads may drive the CONTROL entropy that gates
    # refinement/memory. None = original behavior (aspect,guna,kosha). The adopted
    # staged policy is ("vritti","aspect"); Guna/Kosha stay supervised/diagnostic.
    control_heads: tuple = None
    # aux-loss weights
    ponder_weight: float = 1e-3
    entropy_cal_weight: float = 0.0     # off by default (it shapes calibration)
    # contribution-aware training: reward a module's gate only when it lowers LM
    # loss on the batch (measured enabled-vs-disabled). 0 = off.
    contribution_weight: float = 0.0
    contrib_eval_every: int = 1         # do the extra disabled forwards every N steps
    # residual regularization: penalize residual norm above target_ratio * act_norm.
    residual_reg_weight: float = 0.0
    residual_target_ratio: float = 0.5
    # synthetic head-supervision (ONLY for the shuffled-label control; OFF for LM)
    synthetic_head_labels: bool = False
    shuffle_head_labels: bool = False
    typed_sup_weight: float = 0.0


def _base(**kw) -> ExpConfig:
    return replace(ExpConfig(), **kw)


ABLATIONS: Dict[str, Callable[[], ExpConfig]] = {
    # A0 — pure softmax baseline
    "baseline": lambda: _base(),
    # A0b — FAIR-COMPUTE control: same added depth as refinement, but plain
    "baseline_plus_block": lambda: _base(extra_plain_block=True),
    # A1 — random (frozen) Symbol-U augmentation: path present but untrained
    "random_aug": lambda: _base(typed_heads=True, entropy_refine=True, freeze_aug=True),
    # A2 — trained typed heads as PROBES (do not feed the LM path)
    "typed_heads_probe": lambda: _base(typed_heads=True),
    # A3 — entropy-gated causal refinement (heads -> entropy -> refine -> head)
    "entropy_refine": lambda: _base(typed_heads=True, entropy_refine=True),
    # A4 — + causal deferred-insight memory on the LM path
    "memory": lambda: _base(typed_heads=True, entropy_refine=True, memory=True),
    # A5 — full Symbol-U-on-softmax (everything on the LM path)
    "full": lambda: _base(typed_heads=True, entropy_refine=True, memory=True),
    # --- isolated Symbol-U mechanisms (for capacity-matched comparison) ---
    "mem_only": lambda: _base(typed_heads=True, memory=True),
    # --- capacity-/FLOP-matched CONTROLS (controls.py) ---
    "recur_plain": lambda: _base(recur_plain=True),                 # refine control
    "mem_control": lambda: _base(mem_control=True),                 # memory control
    "full_control": lambda: _base(recur_plain=True, mem_control=True),
}


def approx_flops_per_token(cfg: ExpConfig, L: int) -> float:
    """Rough forward FLOPs/token (approximate is fine — for matched comparison)."""
    d, dff = cfg.backbone.d_model, cfg.backbone.d_ff
    V = cfg.backbone.vocab_size
    def block(L):
        return 4 * d * d + 3 * d * dff + 2 * L * d        # qkv+proj, swiglu, attn
    f = cfg.backbone.n_layers * block(L)
    if cfg.extra_plain_block:
        f += block(L)
    if cfg.typed_heads:
        f += d * (5 + 10 + 3 + 5)                         # tiny typed heads
    if cfg.entropy_refine:
        f += cfg.refine_steps * block(L)                  # refinement = steps × block
    if cfg.memory:
        f += d * d                                        # value projection
    if cfg.recur_plain:
        f += cfg.recur_plain_steps * block(L)             # control = steps × block
    if cfg.mem_control:
        f += d * d                                        # pointwise FFN ≈ d^2
    f += d * V                                            # lm head
    return f


def get_ablation(name: str) -> ExpConfig:
    if name not in ABLATIONS:
        raise KeyError(f"unknown ablation '{name}'; choices={list(ABLATIONS)}")
    return ABLATIONS[name]()


# Adopted head-role policy (validation-first / control-later). Vritti & Aspect are
# the first control candidates; Guna/Kosha & DHA stay supervised/diagnostic until
# they prove they improve generation or controllability.
HEAD_ROLES = {
    "vritti":     "control-later (first control candidate)",
    "aspect":     "control-later (first control candidate)",
    "guna":       "supervised-only / diagnostic first",
    "kosha":      "supervised-only / diagnostic first",
    "entropy":    "control signal — calibrated carefully (only over validated heads)",
    "refinement": "control module",
    "memory":     "control module",
    "dha":        "supervised / preference-only first",
}


def with_staged_roles(cfg: ExpConfig) -> ExpConfig:
    """Enforce the adopted policy at the control boundary: only Vritti & Aspect feed
    the control entropy that gates refinement/memory. Guna/Kosha heads are still
    computed (for supervision/diagnostics) but excluded from control."""
    cfg.control_heads = ("vritti", "aspect")
    return cfg


# Training modes apply auxiliary-loss weights on top of an ablation config.
TRAIN_MODES = ("normal", "contribution", "entropy_cal", "residual_reg", "combined")


def with_mode(cfg: ExpConfig, mode: str) -> ExpConfig:
    if mode not in TRAIN_MODES:
        raise KeyError(f"unknown mode '{mode}'; choices={TRAIN_MODES}")
    if mode in ("contribution", "combined"):
        cfg.contribution_weight = 0.5
    if mode in ("entropy_cal", "combined"):
        cfg.entropy_cal_weight = 0.1
    if mode in ("residual_reg", "combined"):
        cfg.residual_reg_weight = 0.1
    return cfg
