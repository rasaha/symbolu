"""§3.2–§3.3 synthetic trace families for Phase 1.5 characterization.

Seven families, generated reproducibly from a seed. Each returns a
``TraceBundle(sources, valid_masks, truth_label, metadata)`` where
``sources`` has shape ``(M=3, L, V)`` in fp32 for signal-bearing
families and fp64 for Lemma-1 invariance families.

Construction notes (strategic scaffold — §3.2/§3.3 skeleton):

  - ``baseline`` / ``accelerating`` / ``outlier`` / ``noise_floor``
    apply perturbations in *logit space* and project through softmax
    as §3.3.3 prescribes.
  - ``constant_bias`` and ``linear_drift`` apply perturbations in
    *probability space* directly. The doc's logit-space recipe is
    descriptive, but softmax is nonlinear — a logit-space constant
    shift does NOT produce a probability-space constant difference
    across varying ``z_base(l)``, which would cause §3.5.3/§3.5.4's
    1e-10 Lemma-1 threshold to fail structurally. Applying the
    perturbation in probability space realizes the §2.6 C1/C2
    invariance claims exactly. This deviation is called out in
    ``metadata["perturbation_space"]``.
  - ``eos_truncation`` wraps any outer family and carries its
    ``truth_label`` forward.

RNG discipline per §3.3.5: one ``default_rng(seed)`` per call; draws
in fixed order (base → direction → noise).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np


_VALID_FAMILIES = (
    "baseline",
    "constant_bias",
    "linear_drift",
    "accelerating",
    "noise_floor",
    "outlier",
    "eos_truncation",
)


@dataclass
class TraceBundle:
    sources: np.ndarray                     # (M=3, L, V)
    valid_masks: Optional[np.ndarray]       # (M=3, L) bool, or None
    truth_label: Optional[int]              # source index of outlier, or None
    metadata: Dict[str, Any] = field(default_factory=dict)


def _softmax(z: np.ndarray, axis: int = -1) -> np.ndarray:
    z_shift = z - np.max(z, axis=axis, keepdims=True)
    e = np.exp(z_shift)
    return e / np.sum(e, axis=axis, keepdims=True)


def _unit_direction(rng: np.random.Generator, V: int, dtype) -> np.ndarray:
    v = rng.normal(size=V).astype(dtype)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def _zero_sum_direction(rng: np.random.Generator, V: int, dtype) -> np.ndarray:
    """Unit vector constrained to sum to zero (preserves approximate
    simplex invariants when added to a probability distribution)."""
    v = rng.normal(size=V).astype(dtype)
    v = v - v.mean()
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def generate_trace(
    family: str,
    L: int = 5,
    V: int = 1024,
    sigma_logit: float = 3.0,
    seed: int = 0,
    **family_params: Any,
) -> TraceBundle:
    """Generate a reproducible M=3 probability sequence for ``family``.

    See module docstring for construction details and the perturbation-
    space deviation for Lemma-1 families.
    """
    if family not in _VALID_FAMILIES:
        raise ValueError(
            f"unknown family {family!r}; expected one of {_VALID_FAMILIES}"
        )

    # Lemma-1 invariance families run in fp64 so the 1e-10 threshold is
    # attainable; the others run in fp32 per §2.7.2's V1 production rule.
    dtype = np.float64 if family in ("constant_bias", "linear_drift") else np.float32

    rng = np.random.default_rng(seed=seed)
    z_base = rng.normal(loc=0.0, scale=sigma_logit, size=(L, V)).astype(dtype)
    p_base = _softmax(z_base, axis=-1)

    metadata: Dict[str, Any] = {
        "family": family,
        "L": L,
        "V": V,
        "sigma_logit": sigma_logit,
        "seed": seed,
        "dtype": str(dtype().dtype),
    }
    metadata.update(family_params)

    valid_masks: Optional[np.ndarray] = None
    truth_label: Optional[int] = None

    if family == "baseline":
        sources = np.stack([p_base, p_base.copy(), p_base.copy()], axis=0)
        metadata["perturbation_space"] = "none"

    elif family == "constant_bias":
        alpha_mag = float(family_params.get("alpha_mag", 0.1))
        direction = _zero_sum_direction(rng, V, dtype)
        bias = alpha_mag * direction
        # Probability-space constant offset on source 1. Preserves
        # §2.6 C1 exactly (e_{0,1}(l) == -bias for every l).
        p_0 = p_base
        p_1 = p_base + bias
        p_2 = p_base.copy()
        sources = np.stack([p_0, p_1, p_2], axis=0)
        metadata["perturbation_space"] = "probability"

    elif family == "linear_drift":
        drift_rate = float(family_params.get("drift_rate", 0.02))
        direction = _zero_sum_direction(rng, V, dtype)
        ls = np.arange(L, dtype=dtype).reshape(L, 1)
        drift = ls * drift_rate * direction  # shape (L, V)
        p_0 = p_base
        p_1 = p_base + drift
        p_2 = p_base.copy()
        sources = np.stack([p_0, p_1, p_2], axis=0)
        metadata["perturbation_space"] = "probability"

    elif family == "accelerating":
        accel_mag = float(family_params.get("accel_mag", 0.2))
        direction = _zero_sum_direction(rng, V, dtype)
        ls = np.arange(L, dtype=dtype).reshape(L, 1)
        # Probability-space quadratic perturbation: e_{0,1}(l) is an
        # exact quadratic in l, so ‖a‖ = accel_mag and ‖e(l*)‖ scales
        # predictably with accel_mag and the gate threshold T=0.1 is
        # straddled across the sweep range (§3.3.3 intent).
        p_1 = p_base + 0.5 * (ls ** 2) * accel_mag * direction
        sources = np.stack([p_base, p_1, p_base.copy()], axis=0)
        truth_label = 1
        metadata["perturbation_space"] = "probability"

    elif family == "noise_floor":
        sigma_noise = float(family_params.get("sigma_noise", 0.005))
        # Logit-space IID noise per §3.3.3 original spec: softmax
        # suppresses tails, so probability-space disagreement stays
        # below the gate threshold for realistic sigma_noise. Keeping
        # this family in logit space is the right choice — signal
        # families (accelerating / outlier) use probability space to
        # make gate activations controllable; this family needs
        # softmax suppression to exercise the gate-below-floor path.
        noise = rng.normal(
            loc=0.0, scale=sigma_noise, size=(3, L, V)
        ).astype(dtype)
        z_all = z_base[None, :, :] + noise  # (3, L, V)
        sources = _softmax(z_all, axis=-1)
        metadata["perturbation_space"] = "logit"

    elif family == "outlier":
        accel_mag = float(family_params.get("accel_mag", 0.3))
        direction = _zero_sum_direction(rng, V, dtype)
        ls = np.arange(L, dtype=dtype).reshape(L, 1)
        p_0 = p_base + 0.5 * (ls ** 2) * accel_mag * direction
        sources = np.stack([p_0, p_base, p_base.copy()], axis=0)
        truth_label = 0
        metadata["perturbation_space"] = "probability"

    elif family == "eos_truncation":
        outer_family = str(family_params.get("outer_family", "outlier"))
        k_eos = int(family_params.get("k_eos", 2))
        outer_params = {
            k: v for k, v in family_params.items()
            if k not in ("outer_family", "k_eos")
        }
        outer = generate_trace(
            family=outer_family,
            L=L,
            V=V,
            sigma_logit=sigma_logit,
            seed=seed,
            **outer_params,
        )
        sources = outer.sources
        # valid_mask convention: valid[l] = True for l <= k_eos on source 0.
        # k_eos = L-1 ⇒ all valid (no truncation); k_eos = 0 ⇒ only l=0.
        vm = np.ones((3, L), dtype=bool)
        vm[0, k_eos + 1 :] = False
        valid_masks = vm
        truth_label = outer.truth_label
        metadata["outer_family"] = outer_family
        metadata["k_eos"] = k_eos
        metadata["perturbation_space"] = outer.metadata.get(
            "perturbation_space", "unknown"
        )

    else:  # unreachable; validation above
        raise ValueError(family)

    return TraceBundle(
        sources=sources,
        valid_masks=valid_masks,
        truth_label=truth_label,
        metadata=metadata,
    )
