"""BCVF cost functional — LLM logit-space adaptation.

Parallels ``symbolu_robotics/bcvf_autonomous/core.py``. Implements
the same 2nd-order BCVF cost chain, re-targeted from SE(2) body-
frame trajectories to probability-simplex sequences along the
forward-lookahead axis:

    disagreement -> velocity -> acceleration -> gate -> huber -> sum

All functions are pure. Probability inputs are NumPy float32 or
float64 arrays of shape (M, T, L, V) where:
    M = number of sources (V1: M >= 3, see §1.3 / §2.2.4)
    T = number of outer decoding steps (streaming; may be 1)
    L = forward-lookahead horizon (V1: L = 5, see §2.3.4)
    V = vocabulary size (shared across sources for V1, see §2.7.5)

Design anchor: ``Project_documentation/repository/docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md``
§2.4-§2.7. Mathematical specification: V3.1 Lemma 1 (autonomy)
restated in §2.6 with the vector-path proof in §2.6.4.

No imports from other ``symbolu_bcvf_llm`` modules; no imports from
``symbolu_robotics``; no ML-framework imports (torch/transformers/
datasets). The caller in §4 handles fp16/bf16 -> fp32 conversion
(see §2.7.2) before invoking this kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple, Union

import numpy as np


class CostOrder(IntEnum):
    """Which derivative order of disagreement the gate-Huber chain scores.

    Carried verbatim from the autonomy kernel. V1 locks ``SECOND`` (see
    §2.4.1 vector-path choice and §2.6.4 linear-drift invariance proof).
    ZEROTH and FIRST are retained so the §3 signal-characterization
    sweep can ablate without code changes.

    * ``ZEROTH`` — penalize ``||e_ij(l*)||`` at each lookahead position.
    * ``FIRST``  — penalize ``||v_ij(l*)||``, the 1st-order forward
      difference along the lookahead axis. **Does not preserve
      Lemma 1 case 2** (non-zero under linear drift); diagnostic only.
    * ``SECOND`` — penalize ``||a_ij(l*)||``, the 2nd-order stencil
      from §2.4.2. **This is what V1 uses.**
    """

    ZEROTH = 0
    FIRST = 1
    SECOND = 2


@dataclass
class BCVFLLMConfig:
    """All tunable parameters for the LLM-domain BCVF cost functional.

    Parallels ``BCVFConfig`` in ``bcvf_autonomous/core.py:39``. Every
    field that has a meaningful LLM analogue is carried over with the
    same name and default; SE(2)-specific fields are dropped; LLM-
    specific fields are added with explicit reference to the design
    sub-section that motivated them.
    """

    gate_threshold: float = 0.1
    gate_beta: float = 200.0
    huber_delta: float = 0.5

    weight_vector: Optional[np.ndarray] = None

    use_anchor_pairing: bool = False
    anchor_index: int = 0

    step_l: float = 1.0

    cost_order: CostOrder = CostOrder.SECOND


@dataclass
class BCVFLLMResult:
    """Detailed output from LLM-domain BCVF cost computation at a
    single outer decoding step.

    Parallels ``BCVFResult`` (bcvf_autonomous/core.py:58). Adds
    ``per_source_costs`` — the §2.4.5 per-source attribution that
    §5's Rahu trust-weighting consumes.
    """

    total_cost: float
    per_pair_costs: Dict[Tuple[int, int], float]
    per_source_costs: Dict[int, float]
    max_acceleration_norm: float
    gate_activation_count: int


def compute_disagreement(p_i: np.ndarray, p_j: np.ndarray) -> np.ndarray:
    """§2.2 disagreement metric. Probability-simplex difference.

    Inputs: (..., V) arrays from softmax-normalized logits. Output:
    same leading shape, same V. The ellipsis supports both unbatched
    (L, V) sequences and batched (T, L, V) or (M, T, L, V) tensors.

    No normalization, no projection, no clamping. By §2.7.3 the BCVF
    operator is translation-invariant over the per-vocab mean, so
    simplex-sum rounding drift does not affect downstream 2nd-
    differences or norms.
    """
    return p_i - p_j


def compute_disagreement_velocity(
    e: np.ndarray, step_l: float = 1.0
) -> np.ndarray:
    """§2.4 forward-difference along the lookahead axis.

    v(..., l*, :) = [e(..., l*+1, :) - e(..., l*, :)] / step_l

    for l* ∈ [0, L-2].

    Input:  (..., L, V)    (lookahead axis is second-to-last)
    Output: (..., L-1, V)

    Note: under linear drift e(l) = α + γ·l, v(l) = γ — constant but
    non-zero. This breaks Lemma 1 case 2 (§2.6.4). V1 uses SECOND
    (§2.8.3, §2.8.4); velocity is exposed for §3 ablation only.
    """
    return (e[..., 1:, :] - e[..., :-1, :]) / step_l


def compute_disagreement_acceleration(
    e: np.ndarray, step_l: float = 1.0
) -> np.ndarray:
    """§2.4.2 stencil. Second finite difference along the lookahead axis.

    a(..., l*, :) = [e(..., l*+1, :) - 2·e(..., l*, :) + e(..., l*-1, :)] / step_l²

    for l* ∈ [1, L-2].

    Input:  (..., L, V)    (lookahead axis is second-to-last)
    Output: (..., L-2, V)

    Core BCVF innovation (§2.4). Lemma-1 invariance proved in §2.6.3 / §2.6.4.
    """
    return (
        e[..., 2:, :] - 2.0 * e[..., 1:-1, :] + e[..., :-2, :]
    ) / (step_l * step_l)


def smooth_gate(
    e: np.ndarray,
    threshold: float,
    beta: float,
    weight_vector: Optional[np.ndarray] = None,
) -> np.ndarray:
    """§2.5.1 smooth gate in [0, 1].

    g(..., l*) = sigmoid(beta * (||W^{1/2} e(..., l*, :)||_2 - T))

    Input e:  (..., V)
    Output:   (...)

    V1 defaults: threshold T = 0.1, beta = 200.0 (β·T = 20 ratio).
    weight_vector = None means W = I_V (§2.4.3); a non-None weight is
    element-wise multiplied by the disagreement before the ℓ² norm.

    Clipping: exp argument is clipped to [-50, 50] for numerical
    stability (§2.5.1 / §2.7.7).
    """
    if weight_vector is None:
        weighted = e
    else:
        weighted = e * np.sqrt(
            np.asarray(weight_vector, dtype=np.float64)
        )
    norm = np.linalg.norm(weighted, axis=-1)
    arg = beta * (norm - threshold)
    arg_clipped = np.clip(arg, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-arg_clipped))


def pseudo_huber(r: np.ndarray, delta: float) -> np.ndarray:
    """§2.5.2 pseudo-Huber penalty.

    rho(r; delta) = delta^2 * (sqrt(1 + (r/delta)^2) - 1)

    Quadratic near zero, linear for large |r|. Elementwise; no
    axis reduction.
    """
    r_arr = np.asarray(r, dtype=np.float64)
    return (delta * delta) * (np.sqrt(1.0 + (r_arr / delta) ** 2) - 1.0)


def _enumerate_pairs(
    num_sources: int, use_anchor_pairing: bool, anchor_index: int
) -> List[Tuple[int, int]]:
    """Enumerate (i, j) source pairs. j is the reference source.

    Anchor mode: j = anchor_index, i ranges over the other sources.
    All-pairs mode enumerates every unordered pair once with the
    lower-indexed source as the reference j.

    For V1 LLM domain with M=3 and use_anchor_pairing=False
    (§2.8.4 default), this returns [(1, 0), (2, 0), (2, 1)] — all
    three pairs needed for §2.4.5 per-source attribution to
    discriminate an outlier source 2:1 against non-outliers.
    """
    if use_anchor_pairing:
        return [
            (i, anchor_index) for i in range(num_sources) if i != anchor_index
        ]
    return [(i, j) for i in range(num_sources) for j in range(i)]


def _pair_cost(
    p_i: np.ndarray,
    p_j: np.ndarray,
    config: BCVFLLMConfig,
    valid_mask: Optional[np.ndarray] = None,
) -> Tuple[float, float, int]:
    """Compute the per-pair BCVF cost plus diagnostic stats (§2.5.3).

    Inputs:
        p_i, p_j    shape (L, V) — probability sequences for one pair
                    at one outer step, along the lookahead axis
        config      BCVFLLMConfig (§2.8.4)
        valid_mask  optional shape matching the signal domain — boolean;
                    True at stencil centers where both sources have
                    defined logits per §2.7.4. None ⇒ all valid.

    Returns: (pair_cost, max_signal_norm, gate_activation_count)

    SECOND-order path is V1 default. ZEROTH/FIRST retained for §3
    ablation only; FIRST breaks Lemma 1 case 2 (§2.6.4 / §2.8.3).
    """
    e = compute_disagreement(p_i, p_j)

    if config.cost_order == CostOrder.SECOND:
        signal = compute_disagreement_acceleration(e, config.step_l)
        gate_input = e[1:-1]
    elif config.cost_order == CostOrder.FIRST:
        signal = compute_disagreement_velocity(e, config.step_l)
        gate_input = 0.5 * (e[:-1] + e[1:])
    else:
        signal = e
        gate_input = e

    gate = smooth_gate(
        gate_input,
        config.gate_threshold,
        config.gate_beta,
        config.weight_vector,
    )

    if config.weight_vector is None:
        signal_weighted = signal
    else:
        w_sqrt = np.sqrt(
            np.asarray(config.weight_vector, dtype=np.float64)
        )
        signal_weighted = signal * w_sqrt
    signal_norms = np.linalg.norm(signal_weighted, axis=-1)

    penalty = pseudo_huber(signal_norms, config.huber_delta)

    contrib = gate * penalty
    if valid_mask is not None:
        mask_f = np.asarray(valid_mask).astype(contrib.dtype)
        contrib = contrib * mask_f

    pair_cost = float(np.sum(contrib) * config.step_l)
    max_signal = float(signal_norms.max()) if signal_norms.size > 0 else 0.0

    if valid_mask is None:
        activations = int(np.count_nonzero(gate > 0.5))
    else:
        activations = int(
            np.count_nonzero((gate > 0.5) & np.asarray(valid_mask).astype(bool))
        )
    return pair_cost, max_signal, activations


def _intersect_valid_masks(
    mask_i: Optional[np.ndarray],
    mask_j: Optional[np.ndarray],
    cost_order: CostOrder,
) -> Optional[np.ndarray]:
    """Combine two per-source (L,) masks into a per-stencil mask (§2.4.4).

    For SECOND-order, stencil centers are l* ∈ [1, L-2] and the stencil
    references l*-1, l*, l*+1. So valid(l*) requires mask_i[l*-1],
    mask_i[l*], mask_i[l*+1] all True, likewise for j.

    For FIRST-order, stencil references l*, l*+1.
    For ZEROTH-order, only l* itself.

    Returns None if both inputs are None.
    """
    if mask_i is None and mask_j is None:
        return None
    base = mask_i if mask_i is not None else mask_j
    L = base.shape[0]
    mi = np.ones(L, dtype=bool) if mask_i is None else np.asarray(mask_i).astype(bool)
    mj = np.ones(L, dtype=bool) if mask_j is None else np.asarray(mask_j).astype(bool)
    if cost_order == CostOrder.SECOND:
        return mi[:-2] & mi[1:-1] & mi[2:] & mj[:-2] & mj[1:-1] & mj[2:]
    if cost_order == CostOrder.FIRST:
        return mi[:-1] & mi[1:] & mj[:-1] & mj[1:]
    return mi & mj


def compute_bcvf_cost(
    sources: List[np.ndarray],
    config: BCVFLLMConfig,
    valid_masks: Optional[List[np.ndarray]] = None,
) -> BCVFLLMResult:
    """§2.5.3 / §2.8.11 full J_BCVF at a single outer decoding step.

    Inputs:
        sources       list of M arrays, each shape (L, V)
        config        BCVFLLMConfig (§2.8.4)
        valid_masks   optional list of M arrays, each shape (L,), boolean

    Returns: BCVFLLMResult with per-pair AND per-source attribution.

    Raises:
        ValueError — on shape mismatch, M<2, L<3, or non-finite input
                     (NaN/Inf guard per §2.7.6).
    """
    num_sources = len(sources)
    if num_sources < 2:
        raise ValueError(
            f"BCVF requires at least 2 sources; got {num_sources}"
        )
    lookahead_sizes = {s.shape[0] for s in sources}
    if len(lookahead_sizes) != 1:
        raise ValueError(
            f"Sources must share the same lookahead length L; "
            f"got {lookahead_sizes}"
        )
    vocab_sizes = {s.shape[-1] for s in sources}
    if len(vocab_sizes) != 1:
        raise ValueError(
            f"Sources must share the same vocab size V; got {vocab_sizes}"
        )
    if any(s.ndim != 2 for s in sources):
        raise ValueError(
            "Each source must have shape (L, V) for scalar entry"
        )
    if next(iter(lookahead_sizes)) < 3:
        raise ValueError(
            "BCVF requires L >= 3 for the second-difference stencil"
        )
    if any(not np.isfinite(s).all() for s in sources):
        raise ValueError(
            "BCVF received non-finite source probabilities; "
            "upstream softmax failed (§2.7.6)"
        )
    if valid_masks is not None and len(valid_masks) != num_sources:
        raise ValueError(
            f"valid_masks length {len(valid_masks)} != sources {num_sources}"
        )

    pairs = _enumerate_pairs(
        num_sources, config.use_anchor_pairing, config.anchor_index
    )

    per_pair: Dict[Tuple[int, int], float] = {}
    per_source: Dict[int, float] = {s: 0.0 for s in range(num_sources)}
    max_accel = 0.0
    activations = 0
    total = 0.0

    for (i, j) in pairs:
        pair_mask = _intersect_valid_masks(
            valid_masks[i] if valid_masks is not None else None,
            valid_masks[j] if valid_masks is not None else None,
            config.cost_order,
        )
        cost, pair_max_accel, pair_activations = _pair_cost(
            sources[i], sources[j], config, valid_mask=pair_mask
        )
        per_pair[(i, j)] = cost
        per_source[i] += cost
        per_source[j] += cost
        total += cost
        if pair_max_accel > max_accel:
            max_accel = pair_max_accel
        activations += pair_activations

    return BCVFLLMResult(
        total_cost=total,
        per_pair_costs=per_pair,
        per_source_costs=per_source,
        max_acceleration_norm=max_accel,
        gate_activation_count=activations,
    )


def compute_bcvf_cost_batch(
    sources_batch: np.ndarray,
    config: BCVFLLMConfig,
    valid_masks_batch: Optional[np.ndarray] = None,
    return_per_source: bool = True,
) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
    """§2.8.12 vectorized entry across outer decoding steps.

    Inputs:
        sources_batch       shape (T, M, L, V) — probabilities for T
                            outer steps, M sources each
        config              BCVFLLMConfig (§2.8.4)
        valid_masks_batch   optional shape (T, M, L) boolean mask
        return_per_source   if True, returns (total_cost[T,], per_source[T,M])

    Returns:
        total_cost: shape (T,)
        per_source: shape (T, M), only if return_per_source=True
    """
    stacked = np.asarray(sources_batch)
    if stacked.ndim != 4:
        raise ValueError(
            f"sources_batch must be (T, M, L, V); got {stacked.shape}"
        )
    T, M, L, V = stacked.shape
    if M < 2:
        raise ValueError(f"BCVF requires M >= 2; got M={M}")
    if L < 3:
        raise ValueError(f"BCVF requires L >= 3; got L={L}")
    if not np.isfinite(stacked).all():
        raise ValueError(
            "BCVF received non-finite source probabilities; "
            "upstream softmax failed (§2.7.6)"
        )
    if valid_masks_batch is not None:
        vm = np.asarray(valid_masks_batch).astype(bool)
        if vm.shape != (T, M, L):
            raise ValueError(
                f"valid_masks_batch must be (T, M, L)={(T, M, L)}; got {vm.shape}"
            )
    else:
        vm = None

    pairs = _enumerate_pairs(
        M, config.use_anchor_pairing, config.anchor_index
    )

    stacked_f64 = stacked.astype(np.float64, copy=False)

    total = np.zeros(T, dtype=np.float64)
    per_source = (
        np.zeros((T, M), dtype=np.float64) if return_per_source else None
    )

    if config.weight_vector is None:
        w_sqrt = None
    else:
        w_sqrt = np.sqrt(
            np.asarray(config.weight_vector, dtype=np.float64)
        )

    for (i, j) in pairs:
        p_i = stacked_f64[:, i, :, :]
        p_j = stacked_f64[:, j, :, :]
        e = p_i - p_j

        if config.cost_order == CostOrder.SECOND:
            signal = (
                e[:, 2:, :] - 2.0 * e[:, 1:-1, :] + e[:, :-2, :]
            ) / (config.step_l * config.step_l)
            gate_input = e[:, 1:-1, :]
        elif config.cost_order == CostOrder.FIRST:
            signal = (e[:, 1:, :] - e[:, :-1, :]) / config.step_l
            gate_input = 0.5 * (e[:, :-1, :] + e[:, 1:, :])
        else:
            signal = e
            gate_input = e

        if w_sqrt is None:
            gate_weighted = gate_input
            signal_weighted = signal
        else:
            gate_weighted = gate_input * w_sqrt
            signal_weighted = signal * w_sqrt

        gate_norm = np.linalg.norm(gate_weighted, axis=-1)
        gate_arg = config.gate_beta * (gate_norm - config.gate_threshold)
        gate_arg = np.clip(gate_arg, -50.0, 50.0)
        gate = 1.0 / (1.0 + np.exp(-gate_arg))

        signal_norms = np.linalg.norm(signal_weighted, axis=-1)
        penalty = (config.huber_delta ** 2) * (
            np.sqrt(1.0 + (signal_norms / config.huber_delta) ** 2) - 1.0
        )

        contrib = gate * penalty

        if vm is not None:
            mi = vm[:, i, :]
            mj = vm[:, j, :]
            if config.cost_order == CostOrder.SECOND:
                stencil_mask = (
                    mi[:, :-2] & mi[:, 1:-1] & mi[:, 2:]
                    & mj[:, :-2] & mj[:, 1:-1] & mj[:, 2:]
                )
            elif config.cost_order == CostOrder.FIRST:
                stencil_mask = mi[:, :-1] & mi[:, 1:] & mj[:, :-1] & mj[:, 1:]
            else:
                stencil_mask = mi & mj
            contrib = contrib * stencil_mask.astype(contrib.dtype)

        pair_cost = np.sum(contrib, axis=-1) * config.step_l
        total += pair_cost
        if per_source is not None:
            per_source[:, i] += pair_cost
            per_source[:, j] += pair_cost

    if return_per_source:
        return total, per_source
    return total
