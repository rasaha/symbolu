"""Ablation ladder as config presets.

Each preset returns a SymbolUConfig with a specific subset of modules enabled,
so the same model/loss code runs the full ladder by swapping the config. Order
matches the design review: each rung adds exactly one capability over the prior.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable, Dict

from .config import SymbolUConfig


def _base(**kw) -> SymbolUConfig:
    cfg = SymbolUConfig(
        enable_segmentation=False, enable_typed_heads=False, enable_entropy=False,
        enable_refinement=False, enable_stitching=False, enable_memory=False,
        enable_anchors=False, enable_dha=False, enable_safety=False,
    )
    return replace(cfg, **kw)


ABLATIONS: Dict[str, Callable[[], SymbolUConfig]] = {
    # A0 backbone only (sanity floor)
    "backbone_only": lambda: _base(),
    # A1 + typed latent heads (tests grounding / kill-criterion #1)
    "typed_heads": lambda: _base(
        enable_segmentation=True, enable_typed_heads=True),
    # A2 + entropy gating (tests entropy<->uncertainty, kill-criterion #2)
    "entropy_gating": lambda: _base(
        enable_segmentation=True, enable_typed_heads=True, enable_entropy=True),
    # A3 + recurrent refinement (tests loss/calibration gain, kill-criterion #3)
    "recurrent_refinement": lambda: _base(
        enable_segmentation=True, enable_typed_heads=True, enable_entropy=True,
        enable_refinement=True),
    # A4 + episodic memory (tests task-quality gain, not just style)
    "memory": lambda: _base(
        enable_segmentation=True, enable_typed_heads=True, enable_entropy=True,
        enable_refinement=True, enable_memory=True),
    # A5 + delivery harmonization (style head)
    "dha": lambda: _base(
        enable_segmentation=True, enable_typed_heads=True, enable_entropy=True,
        enable_refinement=True, enable_memory=True, enable_dha=True),
    # A6 full Symbol-U (all + anchors + safety)
    "full": lambda: replace(
        SymbolUConfig(),  # all defaults; flip on the optional ones
        enable_stitching=False, enable_memory=True, enable_anchors=True,
        enable_dha=True, enable_safety=True),
}


def get_ablation(name: str) -> SymbolUConfig:
    if name not in ABLATIONS:
        raise KeyError(f"unknown ablation '{name}'; choices={list(ABLATIONS)}")
    return ABLATIONS[name]()
