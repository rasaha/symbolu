"""Phase 4 — Trigonometric Position Scoring for CTM+.

Implements the TriAttention-inspired scoring component from
Mao et al., arXiv:2604.04921 (April 2026), adapted for CTM+'s
block-level integration with vLLM's PagedAttention.

This module contains the pure-Python pieces:

* :class:`QCenterStats` — dataclass holding per-(layer, head,
  frequency-band) Q statistics from offline calibration. Saved as
  ``.npz`` for fast load at engine init.
* :class:`TrigScorer` — combines ``S_trig`` (distance preference
  via the trigonometric series) and ``S_norm`` (norm-based
  complement weighted by ``(1 - R_f)``). Pure-Python given
  pre-computed stats and a key's pre-RoPE vector.
* :func:`aggregate_block_trig_score` — sums S_trig over a block's
  positions and averages over future-offsets ``D``.
* :func:`gqa_normalize_then_max` — for GQA / MLA, z-score
  normalises per query-head and max-aggregates across the group.
* :func:`window_pruning_decision` — pure helper for the
  window-based trigger (every β decoded tokens, score-and-prune
  if cache exceeds budget).
* :func:`calibrate_q_centers` — calibration entry-point.
  Implementation is GPU-only (needs torch + a real model); a
  stub raises NotImplementedError on CPU-only hosts with a
  pointer to the GPU runbook.

Mathematical reference (paper Appendix B):

  RoPE attention logit, in pre-RoPE complex form:
    logit(q,k) = Σ_f ‖q_f‖·‖k_f‖·cos(ω_f·Δ + φ_f)
  where Δ = p_q - p_k, q_f and k_f are pre-RoPE Q/K in
  frequency band f, ω_f = θ^(-2f/d) (θ=10000), and
  φ_f = arg(q_f) - arg(k_f).

  When Q is concentrated near its centre E[q_f]:
    S_trig(k, Δ) = Σ_f ‖E[q_f]‖·‖k_f‖·cos(ω_f·Δ + φ_f^*)
  with φ_f^* = arg(E[q_f]) - arg(k_f).

  Norm complement:
    S_norm(k) = Σ_f (1 - R_f)·E[‖q_f‖]·‖k_f‖
  where R_f = ‖E[q_f]‖ / E[‖q_f‖] is Mean Resultant Length.

  Combined: S(k, Δ) = S_trig(k, Δ) + S_norm(k).

Honest scope: the math is implementable + testable in pure
Python. The actual collection of pre-RoPE Q/K stats during a
forward pass and the runtime capture of pre-RoPE K vectors per
block require GPU + vLLM internals work; both are documented as
GPU-only follow-ups.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


logger = logging.getLogger("ctm_plus.triattention")


# --------------------------------------------------------------------- #
# Q-centre statistics
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class QCenterStats:
    """Per-(layer, head, band) statistics from offline calibration.

    All arrays are stored as nested Python lists for JSON-serializability
    in the CPU-testable path. The GPU calibration pipeline produces
    numpy arrays internally; ``QCenterStats.from_numpy`` packages them
    into this dataclass for save/load.

    Attributes:
        model_name: identifier — saved alongside the stats so the
            engine init can verify the cached calibration matches the
            running model.
        num_layers: layer count
        num_heads: query heads per layer
        num_kv_heads: KV heads per layer (for GQA; equals num_heads
            for vanilla MHA)
        head_dim: per-head dimension; determines ω_f frequencies
        num_bands: head_dim // 2 (RoPE pairs adjacent dims as
            complex frequency bands)
        e_q_real, e_q_imag: complex centre E[q_f], shape
            ``[num_layers, num_heads, num_bands]``
        e_q_norm: scalar mean magnitude E[‖q_f‖], shape
            ``[num_layers, num_heads, num_bands]``
        rope_theta: typically 10000; required to reconstruct ω_f
        calibration_token_count: how many tokens were used (for
            audit-trail; affects no math)
        calibration_corpus: short label naming the calibration
            data source (for audit-trail)
    """

    model_name: str
    num_layers: int
    num_heads: int
    num_kv_heads: int
    head_dim: int
    num_bands: int
    e_q_real: List[List[List[float]]]
    e_q_imag: List[List[List[float]]]
    e_q_norm: List[List[List[float]]]
    rope_theta: float = 10000.0
    calibration_token_count: int = 0
    calibration_corpus: str = "unspecified"

    def __post_init__(self) -> None:
        # Shape validation. All three arrays must be
        # [num_layers][num_heads][num_bands].
        for name, arr in (
            ("e_q_real", self.e_q_real),
            ("e_q_imag", self.e_q_imag),
            ("e_q_norm", self.e_q_norm),
        ):
            if len(arr) != self.num_layers:
                raise ValueError(
                    f"{name}: expected num_layers={self.num_layers} "
                    f"layers, got {len(arr)}"
                )
            for layer_idx, layer_arr in enumerate(arr):
                if len(layer_arr) != self.num_heads:
                    raise ValueError(
                        f"{name} layer {layer_idx}: expected "
                        f"num_heads={self.num_heads} heads, got "
                        f"{len(layer_arr)}"
                    )
                for head_idx, head_arr in enumerate(layer_arr):
                    if len(head_arr) != self.num_bands:
                        raise ValueError(
                            f"{name} layer {layer_idx} head "
                            f"{head_idx}: expected "
                            f"num_bands={self.num_bands} bands, "
                            f"got {len(head_arr)}"
                        )
        if self.num_bands * 2 != self.head_dim:
            raise ValueError(
                f"num_bands ({self.num_bands}) must be head_dim/2 "
                f"({self.head_dim // 2}); RoPE pairs adjacent dims."
            )

    def mean_resultant_length(
        self, layer: int, head: int, band: int,
    ) -> float:
        """R_f = ‖E[q_f]‖ / E[‖q_f‖] — concentration metric."""
        denom = self.e_q_norm[layer][head][band]
        if denom <= 0:
            return 0.0
        re = self.e_q_real[layer][head][band]
        im = self.e_q_imag[layer][head][band]
        e_q_mag = math.sqrt(re * re + im * im)
        return e_q_mag / denom

    def omega_f(self, band: int) -> float:
        """Frequency for RoPE band f: ω_f = θ^(-2f/d)."""
        return self.rope_theta ** (-2.0 * band / self.head_dim)

    def save(self, path: Path) -> None:
        """Save as JSON for portability + audit-readability.

        Production-scale calibration would prefer ``.npz`` for size,
        but JSON keeps the file human-readable for diligence audits
        on partner-shipped calibration files.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model_name": self.model_name,
            "num_layers": self.num_layers,
            "num_heads": self.num_heads,
            "num_kv_heads": self.num_kv_heads,
            "head_dim": self.head_dim,
            "num_bands": self.num_bands,
            "rope_theta": self.rope_theta,
            "calibration_token_count": self.calibration_token_count,
            "calibration_corpus": self.calibration_corpus,
            "e_q_real": self.e_q_real,
            "e_q_imag": self.e_q_imag,
            "e_q_norm": self.e_q_norm,
        }
        path.write_text(json.dumps(payload, indent=2))

    @classmethod
    def load(cls, path: Path) -> "QCenterStats":
        """Load from JSON. Validates schema via __post_init__."""
        data = json.loads(path.read_text())
        return cls(
            model_name=data["model_name"],
            num_layers=int(data["num_layers"]),
            num_heads=int(data["num_heads"]),
            num_kv_heads=int(data["num_kv_heads"]),
            head_dim=int(data["head_dim"]),
            num_bands=int(data["num_bands"]),
            e_q_real=data["e_q_real"],
            e_q_imag=data["e_q_imag"],
            e_q_norm=data["e_q_norm"],
            rope_theta=float(data.get("rope_theta", 10000.0)),
            calibration_token_count=int(
                data.get("calibration_token_count", 0)
            ),
            calibration_corpus=data.get("calibration_corpus", "unspecified"),
        )

    @classmethod
    def from_lists(
        cls,
        *,
        model_name: str,
        num_layers: int,
        num_heads: int,
        num_kv_heads: int,
        head_dim: int,
        e_q_real: Sequence[Sequence[Sequence[float]]],
        e_q_imag: Sequence[Sequence[Sequence[float]]],
        e_q_norm: Sequence[Sequence[Sequence[float]]],
        rope_theta: float = 10000.0,
        calibration_token_count: int = 0,
        calibration_corpus: str = "unspecified",
    ) -> "QCenterStats":
        """Convenience constructor accepting any sequence-of-sequences."""
        return cls(
            model_name=model_name,
            num_layers=num_layers,
            num_heads=num_heads,
            num_kv_heads=num_kv_heads,
            head_dim=head_dim,
            num_bands=head_dim // 2,
            e_q_real=[[list(b) for b in h] for h in e_q_real],
            e_q_imag=[[list(b) for b in h] for h in e_q_imag],
            e_q_norm=[[list(b) for b in h] for h in e_q_norm],
            rope_theta=rope_theta,
            calibration_token_count=calibration_token_count,
            calibration_corpus=calibration_corpus,
        )


# --------------------------------------------------------------------- #
# TrigScorer — per-(layer, head) scoring math
# --------------------------------------------------------------------- #


class TrigScorer:
    """Phase 4 scorer combining S_trig + S_norm with R-weighting.

    Pure-Python given pre-computed :class:`QCenterStats` and the
    actual key's pre-RoPE complex vector. Tested with synthetic
    statistics + synthetic keys; the runtime capture of pre-RoPE
    K vectors inside vLLM is the GPU-only piece.

    Usage:

        scorer = TrigScorer(stats=qcenter_stats,
                            future_offsets=[1, 2, 4, 8, 16])
        score = scorer.score_token(
            layer=0, head=3,
            k_real=[0.1, 0.2, ...], k_imag=[-0.1, 0.0, ...],
            position=42,
        )

    The score is a single scalar suitable as one component of
    CTM+'s combined eviction score. Higher = more important
    (less likely to evict).
    """

    DEFAULT_FUTURE_OFFSETS: Tuple[int, ...] = (1, 2, 4, 8, 16)

    def __init__(
        self,
        stats: QCenterStats,
        future_offsets: Optional[Sequence[int]] = None,
    ) -> None:
        self._stats = stats
        if future_offsets is None:
            self._future_offsets = list(self.DEFAULT_FUTURE_OFFSETS)
        else:
            self._future_offsets = [int(o) for o in future_offsets]
            if not self._future_offsets:
                raise ValueError("future_offsets must be non-empty")
            if any(o <= 0 for o in self._future_offsets):
                raise ValueError(
                    "future_offsets must all be > 0; got "
                    f"{self._future_offsets}"
                )

    @property
    def future_offsets(self) -> List[int]:
        return list(self._future_offsets)

    @property
    def stats(self) -> QCenterStats:
        return self._stats

    def s_trig_at_distance(
        self,
        *,
        layer: int,
        head: int,
        k_real: Sequence[float],
        k_imag: Sequence[float],
        delta: int,
    ) -> float:
        """S_trig(k, Δ) at a specific Q-K distance Δ.

        Computes Σ_f ‖E[q_f]‖·‖k_f‖·cos(ω_f·Δ + φ_f^*)
        where φ_f^* = arg(E[q_f]) - arg(k_f).
        """
        stats = self._stats
        if len(k_real) != stats.num_bands or len(k_imag) != stats.num_bands:
            raise ValueError(
                f"k_real / k_imag must have num_bands={stats.num_bands} "
                f"entries; got {len(k_real)}, {len(k_imag)}"
            )
        total = 0.0
        for f in range(stats.num_bands):
            eq_re = stats.e_q_real[layer][head][f]
            eq_im = stats.e_q_imag[layer][head][f]
            eq_mag = math.sqrt(eq_re * eq_re + eq_im * eq_im)
            kf_re = float(k_real[f])
            kf_im = float(k_imag[f])
            kf_mag = math.sqrt(kf_re * kf_re + kf_im * kf_im)
            if eq_mag == 0.0 or kf_mag == 0.0:
                continue
            phi_eq = math.atan2(eq_im, eq_re)
            phi_kf = math.atan2(kf_im, kf_re)
            phi_star = phi_eq - phi_kf
            omega = stats.omega_f(f)
            total += eq_mag * kf_mag * math.cos(omega * delta + phi_star)
        return total

    def s_norm(
        self,
        *,
        layer: int,
        head: int,
        k_real: Sequence[float],
        k_imag: Sequence[float],
    ) -> float:
        """S_norm(k) = Σ_f (1 - R_f)·E[‖q_f‖]·‖k_f‖.

        Equivalent form (paper Eq. 9):
            Σ_f (E[‖q_f‖] - ‖E[q_f]‖)·‖k_f‖.

        Contributes only to bands with low concentration (R_f < 1).
        """
        stats = self._stats
        if len(k_real) != stats.num_bands or len(k_imag) != stats.num_bands:
            raise ValueError(
                f"k_real / k_imag must have num_bands={stats.num_bands} "
                f"entries; got {len(k_real)}, {len(k_imag)}"
            )
        total = 0.0
        for f in range(stats.num_bands):
            r_f = stats.mean_resultant_length(layer, head, f)
            e_q_norm = stats.e_q_norm[layer][head][f]
            kf_re = float(k_real[f])
            kf_im = float(k_imag[f])
            kf_mag = math.sqrt(kf_re * kf_re + kf_im * kf_im)
            total += (1.0 - r_f) * e_q_norm * kf_mag
        return total

    def score_token(
        self,
        *,
        layer: int,
        head: int,
        k_real: Sequence[float],
        k_imag: Sequence[float],
        position: int,
        future_query_position: Optional[int] = None,
    ) -> float:
        """Final per-token score. Averages S_trig over future_offsets
        (or uses an explicit future_query_position if given) and
        adds S_norm.

        ``future_query_position``: if set, S_trig is evaluated only at
        Δ = future_query_position - position. If None, S_trig is
        averaged over self.future_offsets relative to ``position``.
        """
        if future_query_position is not None:
            delta = future_query_position - position
            s_trig = self.s_trig_at_distance(
                layer=layer, head=head,
                k_real=k_real, k_imag=k_imag, delta=delta,
            )
        else:
            # Mean over future offsets, each interpreted as a future
            # query Δ relative to *this* token's position. The model
            # sees keys at distance Δ_future; we score the key against
            # several future Δ values to anticipate any future query.
            s_trig_sum = 0.0
            for delta in self._future_offsets:
                s_trig_sum += self.s_trig_at_distance(
                    layer=layer, head=head,
                    k_real=k_real, k_imag=k_imag, delta=delta,
                )
            s_trig = s_trig_sum / len(self._future_offsets)

        s_norm_val = self.s_norm(
            layer=layer, head=head,
            k_real=k_real, k_imag=k_imag,
        )
        return s_trig + s_norm_val


# --------------------------------------------------------------------- #
# Block-level + GQA aggregation helpers
# --------------------------------------------------------------------- #


def aggregate_block_trig_score(
    *,
    scorer: TrigScorer,
    layer: int,
    head: int,
    block_keys: Sequence[Tuple[int, Sequence[float], Sequence[float]]],
) -> float:
    """Sum the per-token scores over all positions in a block.

    Args:
        scorer: TrigScorer with calibrated stats + future offsets.
        layer, head: which model layer/head we're scoring.
        block_keys: list of ``(position, k_real, k_imag)`` tuples,
            one per token in the block. Position is the absolute
            sequence position (NOT block-local).

    Returns:
        float — block-level score. Higher = more important.
    """
    if not block_keys:
        return 0.0
    total = 0.0
    for position, k_real, k_imag in block_keys:
        total += scorer.score_token(
            layer=layer, head=head,
            k_real=k_real, k_imag=k_imag,
            position=position,
        )
    return total


def gqa_normalize_then_max(
    per_head_scores: Mapping[int, Mapping[int, float]],
) -> Dict[int, float]:
    """For GQA / MLA: per-query-head, z-score normalise within each
    head, then aggregate per block by max across heads.

    Args:
        per_head_scores: mapping ``query_head -> {block_id: score}``.
            All query heads should cover the same set of block_ids.

    Returns:
        ``{block_id: aggregated_score}``.

    Z-score normalisation per head ensures different heads' scores
    are on comparable scales before max-aggregation. From paper
    Equations 12-13.
    """
    if not per_head_scores:
        return {}

    # Compute per-head mean + std.
    normalised: Dict[int, Dict[int, float]] = {}
    for head, scores in per_head_scores.items():
        if not scores:
            normalised[head] = {}
            continue
        values = list(scores.values())
        n = len(values)
        mean = sum(values) / n
        if n > 1:
            variance = sum((v - mean) ** 2 for v in values) / n
            std = math.sqrt(variance) if variance > 0 else 1.0
        else:
            std = 1.0
        if std == 0.0:
            std = 1.0
        normalised[head] = {
            bid: (val - mean) / std for bid, val in scores.items()
        }

    # Max across heads per block_id.
    all_block_ids = set()
    for scores in normalised.values():
        all_block_ids.update(scores.keys())

    out: Dict[int, float] = {}
    for bid in all_block_ids:
        best = float("-inf")
        for head_scores in normalised.values():
            if bid in head_scores:
                if head_scores[bid] > best:
                    best = head_scores[bid]
        out[bid] = best
    return out


# --------------------------------------------------------------------- #
# Window-based pruning trigger
# --------------------------------------------------------------------- #


@dataclass
class WindowPruningState:
    """State machine for the every-β-tokens pruning trigger.

    Phase 4 (and TriAttention) score-and-prune lazily:
    rather than scoring on every potential eviction event, we
    accumulate decode tokens and trigger a single pruning pass
    every β tokens. The evictor's ``evict()`` method's normal
    behaviour (called when vLLM needs a free block immediately)
    is unaffected; window-based pruning is a SEPARATE pass that
    can evict opportunistically before the cache is full.
    """

    interval_tokens: int = 128
    decode_tokens_since_last_prune: int = 0
    n_prune_invocations: int = 0


def window_pruning_decision(
    state: WindowPruningState,
    decode_tokens_emitted: int,
) -> bool:
    """Return True iff a window-based pruning pass should fire now.

    Increments the per-state counter and resets it on trigger.
    Called by the streaming runner after each decode step (or
    after each engine.generate yield).
    """
    state.decode_tokens_since_last_prune += int(decode_tokens_emitted)
    if state.decode_tokens_since_last_prune >= state.interval_tokens:
        state.decode_tokens_since_last_prune = 0
        state.n_prune_invocations += 1
        return True
    return False


# --------------------------------------------------------------------- #
# Calibration entry-point (GPU-only; stub on CPU-only hosts)
# --------------------------------------------------------------------- #


def calibrate_q_centers(
    *,
    model: Any,
    calibration_token_ids: Any,
    model_name: str,
    rope_theta: float = 10000.0,
    corpus_label: str = "unspecified",
    max_tokens: int = 100_000,
) -> QCenterStats:
    """Offline calibration: collect per-(layer, head, band) Q
    statistics from the model.

    **GPU + torch + a real model required.** On a CPU-only sandbox
    this raises NotImplementedError pointing at the GPU runbook.
    The algorithm:

    1. Hook every Attention layer's pre-RoPE Q projection. Capture
       Q tensors after the linear projection but BEFORE RoPE
       rotation.
    2. Run forward passes on ``calibration_token_ids`` until
       ``max_tokens`` accumulated. Per (layer, head, band), maintain
       running E[q_f] (complex mean) and E[‖q_f‖] (scalar mean).
    3. Pack into a :class:`QCenterStats` and return.

    Args:
        model: a torch.nn.Module — the model whose layers will be
            hooked. Must expose ``Attention`` modules with the
            standard Q linear projection.
        calibration_token_ids: a tensor or iterable of token id
            sequences to feed through the model.
        model_name: identifier saved in the stats; used at engine
            init to verify the cache matches the model.
        rope_theta: RoPE θ; usually 10000.
        corpus_label: free-form label saved with the stats for
            audit-trail.
        max_tokens: stop after seeing this many tokens. Per the
            paper (Table F), 50K is plenty for stable statistics.

    Returns:
        QCenterStats ready to pass to a TrigScorer.
    """
    raise NotImplementedError(
        "calibrate_q_centers requires torch + a real model + a real "
        "GPU. The pure-Python pieces of Phase 4 (TrigScorer, "
        "QCenterStats, aggregate_block_trig_score, "
        "gqa_normalize_then_max, window_pruning_decision) are "
        "implemented and CPU-tested; this function is the GPU-only "
        "offline calibration step. See "
        "MODE_B_PHASE4_DESIGN.md §4 for the full pipeline spec and "
        "the GPU runbook for the calibration command."
    )
