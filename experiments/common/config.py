"""Versioned experiment configuration (dataclass + JSON).

Experiments read parameters from a config object loaded from a JSON file, so
constants are not scattered across runners. ``CONFIG_VERSION`` is recorded in
every config and in reports.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

CONFIG_VERSION = 1


def _from_dict(cls, d: dict):
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class D0Config:
    version: int = CONFIG_VERSION
    tol_commute: float = 1e-8
    tol_abelian: float = 1e-6
    rank_tol: float = 1e-9
    generic_seed: int = 20260629
    max_word_len: int = 4
    trace_samples: int = 2000


@dataclass
class HarnessConfig:
    version: int = CONFIG_VERSION
    repeats: int = 20
    k_shuffle: int = 40
    n_ref: int = 300
    base_seed: int = 1000
    min_delta_r2: float = 0.01
    shuffle_pctl: float = 95.0
    n_units: int = 5
    op_dim: int = 3
    len_min: int = 3
    len_max: int = 6
    effect_grid: list = field(default_factory=lambda: [0.0, 0.1, 0.2, 0.3, 0.5, 0.8])
    sample_grid: list = field(default_factory=lambda: [100, 200, 400, 800])
    noise_grid: list = field(default_factory=lambda: [0.5, 1.0, 2.0, 4.0])
    confound_grid: list = field(default_factory=lambda: [0.0, 1.0, 2.0, 4.0])


def save_config(cfg, path) -> None:
    Path(path).write_text(json.dumps(asdict(cfg), indent=2))


def load_config(cls, path):
    """Load ``cls`` from JSON if present, else return defaults."""
    p = Path(path)
    if not p.exists():
        return cls()
    return _from_dict(cls, json.loads(p.read_text()))
