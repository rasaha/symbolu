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
    refine_steps: int = 3
    refine_min_strength: float = 0.1    # gate floor: refinement cannot collapse to 0
    refine_residual_scale: float = 1.0  # fixed scale on the refinement delta
    refine_fixed_steps: bool = False    # smoke mode: bypass ACT halting entirely
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
}


def get_ablation(name: str) -> ExpConfig:
    if name not in ABLATIONS:
        raise KeyError(f"unknown ablation '{name}'; choices={list(ABLATIONS)}")
    return ABLATIONS[name]()


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
