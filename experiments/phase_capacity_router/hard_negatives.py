"""
hard_negatives.py — frequency-matched hard-negative configuration (§4E, §6 nuisance controls).

Hard negatives share event type, format, and (via a single repeated distractor entity)
frequency/recency statistics with relevant events; only focus identity distinguishes them.
This module provides the hard-negative-heavy DataCfg used to train R-bilinear-hard and to
stress-test admission.
"""
from __future__ import annotations

from dataclasses import replace

from .config import DataCfg


def hard_cfg(base: DataCfg = DataCfg()) -> DataCfg:
    return replace(base, family="hardneg", n_hard=max(base.n_hard, 8))
