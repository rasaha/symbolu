"""Ablation study: which internal representations and which USE signals carry predictive signal.

Operates on a pooled per-query dataset. Reports:
  * channel-set ablation  (head-wise / layer-wise / Quad-only / value-space / residual / full)
  * phase-mapping ablation (complex_pair / reference_projection / temporal_change)
  * per-signal ablation    (single-signal AUROC and leave-one-out) for the U1-U5 signal set
These realise the conceptual USE components (multi-head agreement -> quad_heads; cross-layer
conservation -> layers; residual coherence -> residual; relational preservation -> value/quad;
representation stability / internal consistency -> the correction-demand & convergence signals).
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from .channels import CHANNEL_SETS
from .phases import MAPPINGS
from .use_signals import SIGNAL_NAMES
from . import predict, metrics


def _names_for(pool, cs=None, mp=None, signal=None) -> List[str]:
    out = []
    for k in pool:
        if not k.startswith("USE::"):
            continue
        _, c, m, s = k.split("::")
        if cs is not None and c != cs:
            continue
        if mp is not None and m != mp:
            continue
        if signal is not None and s != signal:
            continue
        out.append(k)
    return out


def channel_set_ablation(pool, y, seed=0) -> Dict[str, float]:
    out = {}
    for cs in CHANNEL_SETS:
        names = _names_for(pool, cs=cs)
        if not names:
            continue
        probs = predict.oof_probabilities(pool, names, y, seed=seed)
        out[cs] = metrics.auroc(y, probs)
    return out


def mapping_ablation(pool, y, seed=0) -> Dict[str, float]:
    out = {}
    for mp in MAPPINGS:
        names = _names_for(pool, mp=mp)
        if not names:
            continue
        probs = predict.oof_probabilities(pool, names, y, seed=seed)
        out[mp] = metrics.auroc(y, probs)
    return out


def signal_ablation(pool, y, cs="quad_heads", mp="reference_projection", seed=0) -> Dict:
    """Single-signal AUROC and leave-one-out AUROC for one (channel set, mapping)."""
    group = [f"USE::{cs}::{mp}::{s}" for s in SIGNAL_NAMES if f"USE::{cs}::{mp}::{s}" in pool]
    single = {}
    for s in SIGNAL_NAMES:
        key = f"USE::{cs}::{mp}::{s}"
        if key not in pool:
            continue
        auc = metrics.auroc(y, pool[key])
        single[s] = {"auroc_oriented": float(max(auc, 1 - auc)), "raw": float(auc)}
    full = metrics.auroc(y, predict.oof_probabilities(pool, group, y, seed=seed))
    loo = {}
    for s in SIGNAL_NAMES:
        key = f"USE::{cs}::{mp}::{s}"
        if key not in group:
            continue
        sub = [k for k in group if k != key]
        loo[s] = metrics.auroc(y, predict.oof_probabilities(pool, sub, y, seed=seed))
    return {"channel_set": cs, "mapping": mp, "single_signal": single,
            "full_group_auroc": float(full),
            "leave_one_out_auroc": {k: float(v) for k, v in loo.items()}}


def full_ablation(pool, y, seed=0) -> Dict:
    return {
        "channel_set": channel_set_ablation(pool, y, seed),
        "mapping": mapping_ablation(pool, y, seed),
        "signal_quad_ref": signal_ablation(pool, y, "quad_heads", "reference_projection", seed),
        "signal_full_ref": signal_ablation(pool, y, "full", "reference_projection", seed),
    }
