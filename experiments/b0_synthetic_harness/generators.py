"""Synthetic data generators for B.0 harness calibration (NO semantics, NO data).

A single parametric generator covers all five required regimes through three
weights on standardized components:

    y = confound * z(bag_part) + effect * z(order_part) + noise * z(gaussian)

where ``bag_part`` depends only on unordered unit COUNTS (order-blind) and
``order_part`` depends on the ORDERED non-commutative operator product
``u . M_{w_L} ... M_{w_1} s0``. Ground-truth "order signal present" == (effect != 0).

Regimes:
  null/bag        : confound=1, effect=0          (order must NOT help)
  order           : confound=0, effect=1          (order MUST help)
  weak-signal     : confound=0, effect=alpha small (tunable)
  confounded      : confound>0, effect=alpha       (counts partially mask order)
  pure-noise      : confound=0, effect=0           (probe must return null)

This is instrument calibration only — synthetic structure, no semantic Y, no
real-world data, no Symbol-U claim.
"""
from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import stats  # noqa: E402


@dataclass
class GenParams:
    n_units: int = 5
    op_dim: int = 3
    len_min: int = 3
    len_max: int = 6
    confound: float = 0.0   # weight on the bag/count component
    effect: float = 1.0     # weight on the ordered component
    noise: float = 1.0      # weight on gaussian noise
    # "bigram"  : local-order effect, linearly representable by the order-aware
    #             (bigram) probe -> the matched signal used for power calibration.
    # "product" : full non-commutative operator product u.M_{w_L}..M_{w_1} s0 -> a
    #             HARD/mismatched order signal that a linear bigram probe under-
    #             detects (used to expose the probe's power limit).
    order_kind: str = "bigram"


def _assets(p: GenParams, rng: np.random.Generator):
    w = rng.standard_normal(p.n_units)                       # per-unit bag weights
    B = rng.standard_normal((p.n_units, p.n_units))
    B = B - B.T                                              # ANTISYMMETRIC bigram weights:
    #   E[sum_adj B[a,b] | counts] = 0  -> pure order signal, invisible to the bag
    #   baseline, yet still linear in bigram counts (order-aware probe can capture it).
    ops = stats.random_orthogonal_matrices(p.n_units, p.op_dim, rng)  # per-unit operators
    s0 = rng.standard_normal(p.op_dim); s0 /= np.linalg.norm(s0)
    u = rng.standard_normal(p.op_dim)
    return w, B, ops, s0, u


def _z(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return (x - x.mean()) / sd if sd > 0 else x * 0.0


def _generate_core(n_samples: int, p: GenParams, rng: np.random.Generator):
    w, B, ops, s0, u = _assets(p, rng)
    seqs, bag, order = [], [], []
    for _ in range(n_samples):
        L = int(rng.integers(p.len_min, p.len_max + 1))
        seq = [int(i) for i in rng.integers(0, p.n_units, size=L)]
        seqs.append(seq)
        bag.append(sum(w[i] for i in seq))
        if p.order_kind == "bigram":
            order.append(sum(B[a, b] for a, b in zip(seq[:-1], seq[1:])))
        else:  # "product": full non-commutative ordered product
            s = s0.copy()
            for i in seq:
                s = ops[i] @ s
            order.append(float(u @ s))
    bag = np.array(bag); order = np.array(order)
    noise = rng.standard_normal(n_samples)
    y = p.confound * _z(bag) + p.effect * _z(order) + p.noise * _z(noise)
    meta = {"order_present": bool(p.effect != 0.0), "params": p,
            "var_bag": float(_z(bag).var()), "var_order": float(_z(order).var())}
    assets = {"ops": ops, "s0": s0, "u": u, "w": w, "B": B,
              "n_units": p.n_units, "op_dim": p.op_dim}
    return seqs, y, meta, assets


def generate(n_samples: int, p: GenParams, seed: int):
    """Return (sequences, y, meta). Deterministic under ``seed``."""
    seqs, y, meta, _ = _generate_core(n_samples, p, np.random.default_rng(seed))
    return seqs, y, meta


def generate_with_assets(n_samples: int, p: GenParams, seed: int):
    """Return (sequences, y, meta, assets) — assets expose the generative
    operator family {M_i}, s0, u, bag weights w, bigram weights B. Used by the
    operator-aware probe (B.0.1) to build matched product-state features, exactly
    as the real probe would be handed a candidate operator family."""
    return _generate_core(n_samples, p, np.random.default_rng(seed))


# Named regime presets (effect, confound, noise) at a reference scale.
REGIMES = {
    "null_bag":   GenParams(confound=1.0, effect=0.0, noise=1.0),
    "order":      GenParams(confound=0.0, effect=1.0, noise=1.0),
    "weak":       GenParams(confound=0.0, effect=0.2, noise=1.0),
    "confounded": GenParams(confound=1.5, effect=0.4, noise=1.0),
    "pure_noise": GenParams(confound=0.0, effect=0.0, noise=1.0),
}
