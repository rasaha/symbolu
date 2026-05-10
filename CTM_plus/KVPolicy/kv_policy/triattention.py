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


# --------------------------------------------------------------------- #
# GPU-side calibration + runtime pre-RoPE K capture
# --------------------------------------------------------------------- #


def _walk_rotary_emb_modules(model: Any):
    """Yield (layer_index, rotary_emb_module) pairs for every
    rotary positional-embedding module in the model.

    Identification heuristics (avoids importing vllm here so the
    function is CPU-importable):

    * Class name contains "Rotary" / "RoPE" / "RotaryEmbedding".
    * Has a callable ``forward`` taking at least 3 args
      (positions, query, key).

    Layer indexing is by document-order traversal of the model's
    ``named_modules()`` — the n-th rotary module found maps to
    layer index n. This works for transformer stacks where each
    layer has one rotary_emb. Models with nested or multi-rotary
    structures (rare) may need a model-specific override.
    """
    layer_idx = 0
    if hasattr(model, "named_modules"):
        modules_iter = model.named_modules()
    else:
        # Fallback for tests with simple objects (no nn.Module).
        # Walk attributes shallowly — no recursion.
        modules_iter = (
            (name, getattr(model, name))
            for name in dir(model)
            if not name.startswith("_")
        )
    for name, module in modules_iter:
        cls = type(module).__name__
        if any(k in cls for k in ("Rotary", "RoPE")):
            yield layer_idx, name, module
            layer_idx += 1


@dataclass
class _RunningQStats:
    """Per-(head, band) running statistics. Internal helper."""

    sum_real: List[List[float]]   # [head][band]
    sum_imag: List[List[float]]
    sum_norm: List[List[float]]
    count: List[List[int]]

    @classmethod
    def empty(cls, num_heads: int, num_bands: int) -> "_RunningQStats":
        return cls(
            sum_real=[[0.0] * num_bands for _ in range(num_heads)],
            sum_imag=[[0.0] * num_bands for _ in range(num_heads)],
            sum_norm=[[0.0] * num_bands for _ in range(num_heads)],
            count=[[0] * num_bands for _ in range(num_heads)],
        )

    def add_batch(
        self,
        q_real: Any,
        q_imag: Any,
        q_norm: Any,
    ) -> None:
        """Accumulate a [num_tokens, num_heads, num_bands] batch.
        ``q_*`` are torch.Tensor or numpy arrays on CPU."""
        # Sum across the token dimension into per-(head, band) totals.
        # Tolerates either torch tensors or python lists.
        try:
            sums_real = q_real.sum(dim=0).tolist()
            sums_imag = q_imag.sum(dim=0).tolist()
            sums_norm = q_norm.sum(dim=0).tolist()
            n_tokens = q_real.shape[0]
        except AttributeError:
            # numpy fallback
            sums_real = q_real.sum(axis=0).tolist()
            sums_imag = q_imag.sum(axis=0).tolist()
            sums_norm = q_norm.sum(axis=0).tolist()
            n_tokens = q_real.shape[0]

        num_heads = len(self.sum_real)
        num_bands = len(self.sum_real[0]) if num_heads else 0
        for h in range(num_heads):
            for f in range(num_bands):
                self.sum_real[h][f] += float(sums_real[h][f])
                self.sum_imag[h][f] += float(sums_imag[h][f])
                self.sum_norm[h][f] += float(sums_norm[h][f])
                self.count[h][f] += int(n_tokens)

    def finalise(self) -> Tuple[
        List[List[float]], List[List[float]], List[List[float]],
    ]:
        """Return (e_q_real, e_q_imag, e_q_norm) means."""
        num_heads = len(self.sum_real)
        num_bands = len(self.sum_real[0]) if num_heads else 0
        e_real: List[List[float]] = []
        e_imag: List[List[float]] = []
        e_norm: List[List[float]] = []
        for h in range(num_heads):
            row_re: List[float] = []
            row_im: List[float] = []
            row_no: List[float] = []
            for f in range(num_bands):
                n = max(1, self.count[h][f])
                row_re.append(self.sum_real[h][f] / n)
                row_im.append(self.sum_imag[h][f] / n)
                row_no.append(self.sum_norm[h][f] / n)
            e_real.append(row_re)
            e_imag.append(row_im)
            e_norm.append(row_no)
        return e_real, e_imag, e_norm


def _split_q_into_complex_pairs(
    q_tensor: Any,
    num_heads: int,
    head_dim: int,
) -> Tuple[Any, Any, Any]:
    """Convert a Q tensor [num_tokens, num_heads * head_dim] to
    (q_real, q_imag, q_norm) shaped [num_tokens, num_heads, num_bands]
    where num_bands = head_dim // 2.

    RoPE pairs adjacent dimensions: dim 2f is the real part, dim
    2f+1 is the imaginary part of frequency band f. Returns
    detached CPU tensors (caller may convert to numpy / lists for
    the running aggregator).
    """
    import torch  # type: ignore

    if not isinstance(q_tensor, torch.Tensor):
        raise TypeError(
            f"_split_q_into_complex_pairs expects torch.Tensor; "
            f"got {type(q_tensor).__name__}"
        )
    if q_tensor.dim() != 2:
        raise ValueError(
            f"q_tensor must be 2D [num_tokens, num_heads*head_dim]; "
            f"got shape {tuple(q_tensor.shape)}"
        )
    total_dim = q_tensor.shape[-1]
    if total_dim != num_heads * head_dim:
        raise ValueError(
            f"q_tensor last dim {total_dim} != num_heads*head_dim "
            f"({num_heads}*{head_dim} = {num_heads * head_dim})"
        )
    if head_dim % 2 != 0:
        raise ValueError(
            f"head_dim must be even (RoPE pairs adjacent dims); "
            f"got {head_dim}"
        )
    num_tokens = q_tensor.shape[0]
    num_bands = head_dim // 2
    # Reshape: [tokens, heads, head_dim] -> [tokens, heads, bands, 2]
    reshaped = q_tensor.detach().to("cpu").float().view(
        num_tokens, num_heads, num_bands, 2,
    )
    q_real = reshaped[..., 0]   # [tokens, heads, bands]
    q_imag = reshaped[..., 1]
    q_norm = (q_real * q_real + q_imag * q_imag).sqrt()
    return q_real, q_imag, q_norm


def calibrate_q_centers(
    *,
    model: Any,
    forward_callable: Any,
    model_name: str,
    num_heads: int,
    head_dim: int,
    rope_theta: float = 10000.0,
    corpus_label: str = "unspecified",
    max_tokens: int = 100_000,
    num_kv_heads: Optional[int] = None,
) -> QCenterStats:
    """Offline calibration: collect per-(layer, head, band) Q
    statistics from the model.

    **GPU + torch + a real model required.** On hosts without
    torch, this function will fail at the ``import torch`` line
    inside its helpers.

    Algorithm (per the design doc §4):

    1. Walk ``model.named_modules()`` for rotary-positional-
       embedding modules (identified by class name containing
       "Rotary" or "RoPE"). The n-th such module is layer n.
    2. Register a ``forward_pre_hook`` on each rotary_emb. The
       pre-hook receives ``(positions, q, k)`` BEFORE rotation
       — exactly the pre-RoPE Q vectors we need.
    3. Run forward passes via ``forward_callable(model)`` —
       caller supplies a closure that drives the model with
       calibration data. Every hook firing accumulates
       per-(layer, head, band) running sums of (real, imag, norm).
    4. Stop when total observed tokens ≥ ``max_tokens``. Per
       paper Table F, 50K-200K tokens is plenty for stable
       statistics.
    5. Finalise to mean E[q_f] (complex) and E[‖q_f‖] (scalar)
       per (layer, head, band). Pack into QCenterStats.

    Args:
        model: ``torch.nn.Module`` — the model to hook. Must
            expose RotaryEmbedding-like modules.
        forward_callable: a function ``f(model)`` that drives
            the model on calibration data. Caller's
            responsibility (e.g., iterate over a calibration
            corpus, calling ``model.forward(input_ids)`` for
            each batch).
        model_name: identifier saved in the stats; verified at
            engine init.
        num_heads, head_dim: model architecture parameters
            (used to reshape Q correctly). num_bands = head_dim/2.
        rope_theta: RoPE θ; usually 10000.
        corpus_label: free-form label saved with the stats.
        max_tokens: stop after this many tokens accumulated.
        num_kv_heads: GQA / MLA — KV heads per layer. Defaults
            to num_heads (vanilla MHA).

    Returns:
        QCenterStats ready to pass to a TrigScorer.

    First-GPU-run diagnostic notes:

    * If 0 rotary modules are found, the model's class names may
      not contain "Rotary" / "RoPE". Inspect with
      ``[type(m).__name__ for _, m in model.named_modules()]``
      and either rename or extend ``_walk_rotary_emb_modules``.
    * If hook firings yield Q tensors with unexpected shapes,
      the rotary_emb's forward signature differs from
      ``(positions, q, k)`` — check the wrapping layer's source.
    * If statistics look uniform (R near 0 across all bands),
      the calibration data may be too small or biased. Per
      paper Table F, even Google homepage HTML works as
      calibration data; if HTML doesn't produce stable stats,
      the hook isn't seeing real Q vectors.
    """
    import torch  # type: ignore  # noqa

    if num_kv_heads is None:
        num_kv_heads = num_heads
    num_bands = head_dim // 2
    if num_bands * 2 != head_dim:
        raise ValueError(
            f"head_dim must be even; got {head_dim}"
        )

    rotary_modules: List[Tuple[int, str, Any]] = list(
        _walk_rotary_emb_modules(model)
    )
    if not rotary_modules:
        raise RuntimeError(
            "calibrate_q_centers found 0 rotary_emb modules in "
            "the model. The walker matches class names containing "
            "'Rotary' or 'RoPE'; if your model uses a different "
            "naming convention, extend _walk_rotary_emb_modules. "
            "See MODE_B_PHASE4_DESIGN.md §4 for diagnostics."
        )

    num_layers = len(rotary_modules)
    logger.info(
        "calibrate_q_centers: found %d rotary_emb modules", num_layers,
    )

    per_layer_stats: List[_RunningQStats] = [
        _RunningQStats.empty(num_heads, num_bands)
        for _ in range(num_layers)
    ]
    tokens_seen = 0
    handles = []

    def make_hook(layer_idx: int):
        def pre_hook(module, inputs):
            nonlocal tokens_seen
            if tokens_seen >= max_tokens:
                return  # stop accumulating
            # Standard rotary_emb forward signature:
            #   forward(positions, query, key) -> (rotated_q, rotated_k)
            # The pre-hook receives (positions, query, key) as inputs.
            if len(inputs) < 3:
                return
            _positions, query, _key = inputs[:3]
            try:
                q_real, q_imag, q_norm = _split_q_into_complex_pairs(
                    query, num_heads=num_heads, head_dim=head_dim,
                )
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "layer %d Q reshape failed: %s", layer_idx, exc,
                )
                return
            per_layer_stats[layer_idx].add_batch(q_real, q_imag, q_norm)
            tokens_seen += int(query.shape[0])
        return pre_hook

    for layer_idx, _name, module in rotary_modules:
        h = module.register_forward_pre_hook(make_hook(layer_idx))
        handles.append(h)

    try:
        forward_callable(model)
    finally:
        for h in handles:
            h.remove()

    # Finalise: per-layer means.
    e_q_real: List[List[List[float]]] = []
    e_q_imag: List[List[List[float]]] = []
    e_q_norm: List[List[List[float]]] = []
    for stats in per_layer_stats:
        re_layer, im_layer, no_layer = stats.finalise()
        e_q_real.append(re_layer)
        e_q_imag.append(im_layer)
        e_q_norm.append(no_layer)

    return QCenterStats.from_lists(
        model_name=model_name,
        num_layers=num_layers,
        num_heads=num_heads,
        num_kv_heads=num_kv_heads,
        head_dim=head_dim,
        e_q_real=e_q_real,
        e_q_imag=e_q_imag,
        e_q_norm=e_q_norm,
        rope_theta=rope_theta,
        calibration_token_count=tokens_seen,
        calibration_corpus=corpus_label,
    )


def install_pre_rope_capture(
    *,
    model: Any,
    evictor: Any,
    layer_for_scoring: Optional[int] = None,
    head_for_scoring: int = 0,
    enable_logging: bool = False,
) -> int:
    """Install runtime hooks that capture pre-RoPE K vectors per
    block and push them to the evictor.

    Hooks every rotary_emb's ``forward_pre_hook``. The pre-hook
    receives ``(positions, query, key)`` BEFORE rotation; we read
    K (untouched), reshape to per-band complex pairs, identify
    which decode tokens belong to which blocks via
    ``attn_metadata.slot_mapping`` (carried alongside the
    forward), and call
    ``evictor.set_block_pre_rope_keys(block_id, keys, layer, head)``.

    Returns the number of layers patched. 0 + a warning if no
    rotary modules found.

    Args:
        model: torch.nn.Module — the model whose layers are
            hooked.
        evictor: a CTMEvictorModern instance with
            ``set_block_pre_rope_keys`` available.
        layer_for_scoring: which layer's K vectors to push to
            the evictor. Phase 4's design uses one layer
            (typically last) for scoring; default ``None``
            captures from EVERY layer (the evictor will overwrite
            per-block as later layers fire). For deterministic
            behaviour, pass an explicit layer index — typically
            ``num_layers - 1``.
        head_for_scoring: which (KV-head-aligned) head to use.
            Default 0.
        enable_logging: log per-firing diagnostics on warnings.

    The runtime hook is intentionally lightweight: per call,
    O(num_decode_tokens × num_bands) Python work. The slot_mapping
    walk is the only allocation hot-path; we use plain Python for
    portability. If profiling shows it as a bottleneck, switch to
    numpy-vectorised aggregation here.

    Layout assumptions (defensive — first GPU run validates):

    * ``key`` argument is shape
      ``[num_tokens, num_kv_heads * head_dim]``.
    * ``attn_metadata`` is reachable from the same forward call
      OR via a captured closure variable. If we can't find
      ``slot_mapping``, we degrade to "no per-block capture"
      and Phase 4 falls back to Phase 2 scoring on a per-block
      basis (untracked blocks score None, get skipped by
      ``window_pruning_pass``).

    See MODE_B_PHASE4_DESIGN.md §5 for the GPU validation
    procedure.
    """
    import torch  # type: ignore  # noqa: F401

    rotary_modules: List[Tuple[int, str, Any]] = list(
        _walk_rotary_emb_modules(model)
    )
    if not rotary_modules:
        logger.warning(
            "install_pre_rope_capture: no rotary_emb modules "
            "found. Phase 4 K capture will be a no-op; Phase 4 "
            "scoring will fall back to per-block None (skipped "
            "by window_pruning_pass). Inspect model module "
            "names; see MODE_B_PHASE4_DESIGN.md §5."
        )
        return 0

    num_layers = len(rotary_modules)
    target_layer = (
        num_layers - 1 if layer_for_scoring is None
        else int(layer_for_scoring)
    )

    # Attempt to locate the model's KV head dim from one of the
    # attention layers. Best-effort; if we can't find it, the
    # hook will derive it from the K tensor's shape.
    inferred_kv_head_dim: Optional[int] = None
    if hasattr(model, "named_modules"):
        for name, module in model.named_modules():
            cls = type(module).__name__
            if "Attention" in cls or "Attn" in cls:
                hd = (
                    getattr(module, "head_size", None)
                    or getattr(module, "head_dim", None)
                )
                if hd:
                    inferred_kv_head_dim = int(hd)
                    break

    def make_hook(layer_idx: int):
        def pre_hook(module, inputs):
            if layer_idx != target_layer:
                return
            try:
                _capture_pre_rope_k_to_evictor(
                    inputs=inputs,
                    evictor=evictor,
                    layer=layer_idx,
                    head=head_for_scoring,
                    inferred_head_dim=inferred_kv_head_dim,
                )
            except Exception as exc:
                if enable_logging:
                    logger.warning(
                        "pre-RoPE K capture failed at layer %d: %s",
                        layer_idx, exc,
                    )
        return pre_hook

    n_patched = 0
    for layer_idx, _name, module in rotary_modules:
        module.register_forward_pre_hook(make_hook(layer_idx))
        n_patched += 1

    logger.info(
        "install_pre_rope_capture: hooked %d layers (scoring layer=%d, "
        "head=%d)",
        n_patched, target_layer, head_for_scoring,
    )
    return n_patched


def install_attn_metadata_side_channel(
    *,
    model: Any,
    evictor: Any,
    enable_logging: bool = False,
) -> int:
    """Install hooks that stash ``attn_metadata.slot_mapping`` +
    ``num_decode_tokens`` on the evictor BEFORE any rotary_emb
    pre-hook fires.

    The pre-RoPE K capture hook (:func:`install_pre_rope_capture`)
    needs to know which decode token writes to which block. That
    information lives on ``attn_metadata`` which the rotary_emb
    pre-hook does not directly see.

    **Design (revised after the May 2026 GPU run):** the original
    design hooked each ``Attention`` layer's ``forward_pre_hook``,
    on the assumption that ``Attention.forward`` fires before
    ``rotary_emb``. In vLLM 0.7.3's Qwen2.5 implementation the
    actual order inside a decoder layer is:

    1. ``qkv_proj.forward(hidden_states)`` -> Q, K, V (pre-RoPE)
    2. ``rotary_emb(positions, Q, K)`` -> Q, K (post-RoPE)
       <-- our pre-RoPE capture pre-hook fires HERE
    3. ``Attention.forward(Q, K, V, kv_cache, attn_metadata)``
       <-- the OLD side-channel hook fired HERE (too late)

    So the side-channel was never set when capture ran, and
    ``phase4_blocks_captured_with_pre_rope_keys`` stayed at 0
    for the entire run.

    The fix: hook the **top-level model.forward**, which receives
    ``attn_metadata`` as a forward kwarg and fires before any
    submodule. The pre-hook stashes the side-channel for the
    duration of one forward pass; the post-hook clears it at the
    end. By construction the side-channel is set before any
    rotary_emb fires anywhere in the model.

    Returns the number of hooks installed (1 if ``model.forward``
    was hooked successfully; 0 with a warning otherwise).
    """
    try:
        import torch  # type: ignore  # noqa: F401
    except ImportError:
        logger.warning(
            "install_attn_metadata_side_channel needs torch; not "
            "installed."
        )
        return 0

    if not hasattr(model, "register_forward_pre_hook") or not hasattr(
        model, "register_forward_hook"
    ):
        logger.warning(
            "install_attn_metadata_side_channel: model is not a "
            "torch.nn.Module (no register_forward_*_hook). Phase 4 "
            "capture cannot be wired up."
        )
        return 0

    h_pre = model.register_forward_pre_hook(
        _make_attn_metadata_pre_hook(
            evictor, name="model_forward",
            enable_logging=enable_logging,
        ),
        with_kwargs=True,
    )
    h_post = model.register_forward_hook(
        _make_attn_metadata_post_hook(evictor)
    )
    existing = getattr(evictor, "_phase4_handles", None)
    if existing is None:
        existing = []
        evictor._phase4_handles = existing
    existing.append(h_pre)
    existing.append(h_post)
    return 1


def _walk_attention_modules(model: Any):
    """Yield (name, module) for every vLLM Attention layer.
    Same identification heuristic as
    install_attention_capture (Phase 3) — class name 'Attention'
    or 'PagedAttention'."""
    if hasattr(model, "named_modules"):
        for name, module in model.named_modules():
            cls = type(module).__name__
            if cls in ("Attention", "PagedAttention"):
                yield name, module
            elif (
                hasattr(module, "head_size") or hasattr(module, "head_dim")
            ) and hasattr(module, "num_heads") and hasattr(module, "forward"):
                yield name, module


def _make_attn_metadata_pre_hook(evictor, name, enable_logging):
    def pre_hook(module, args, kwargs=None):
        # Attention.forward signatures vary across vLLM versions:
        #   forward(query, key, value, kv_cache, attn_metadata)
        #   forward(query, key, value, attn_metadata, ...)
        # We try positional first, then kwargs. attn_metadata is
        # identified by having a ``slot_mapping`` attribute.
        attn_metadata = None
        for candidate in args:
            if hasattr(candidate, "slot_mapping"):
                attn_metadata = candidate
                break
        if attn_metadata is None and kwargs:
            for candidate in kwargs.values():
                if hasattr(candidate, "slot_mapping"):
                    attn_metadata = candidate
                    break
        if attn_metadata is None:
            if enable_logging:
                logger.warning(
                    "phase4 side-channel: no attn_metadata in %s "
                    "forward args", name,
                )
            return
        try:
            evictor._phase4_pending_slot_mapping = (
                attn_metadata.slot_mapping
            )
            evictor._phase4_pending_num_decode_tokens = int(
                getattr(attn_metadata, "num_decode_tokens", 0)
            )
        except Exception as exc:
            if enable_logging:
                logger.warning(
                    "phase4 side-channel stash failed: %s", exc,
                )
    return pre_hook


def _make_attn_metadata_post_hook(evictor):
    def post_hook(module, inputs, output):
        # Clear side-channel after the layer so stale state from
        # one layer doesn't leak to the next.
        try:
            evictor._phase4_pending_slot_mapping = None
            evictor._phase4_pending_num_decode_tokens = 0
        except Exception:
            pass
    return post_hook


def _capture_pre_rope_k_to_evictor(
    *,
    inputs: tuple,
    evictor: Any,
    layer: int,
    head: int,
    inferred_head_dim: Optional[int],
) -> None:
    """Per-call work for the runtime pre-RoPE K capture hook.

    Inputs are the rotary_emb forward_pre_hook's args:
    ``(positions, query, key, ...)``. We ignore query (only K
    matters for the evictor's score-block API).

    Block identification: vLLM threads ``attn_metadata`` through
    via module-attached state OR via the hook's closure (we don't
    have direct access to attn_metadata from the rotary_emb hook).
    Best-effort: read ``module.attn_metadata`` if vLLM stashes
    it there; otherwise look for a side-channel attribute on the
    evictor itself (set by a separate hook that DOES see
    attn_metadata).

    Production GPU run will likely need to combine this hook
    with a second hook on the Attention layer that stashes
    attn_metadata for the rotary_emb hook to read. The first
    GPU validation will surface this; the design accommodates
    a follow-up that wires the connection.

    For the initial implementation we accept that without
    attn_metadata access, K capture is a no-op (no block_id
    mapping). The defensive try/except in install_pre_rope_capture
    surfaces this as a "no per-block capture" warning.
    """
    import torch  # type: ignore

    if len(inputs) < 3:
        raise ValueError(
            f"rotary_emb forward expects (positions, q, k); got "
            f"{len(inputs)} args"
        )
    positions, _query, key = inputs[:3]
    if not isinstance(key, torch.Tensor):
        raise TypeError(
            f"key must be torch.Tensor; got {type(key).__name__}"
        )
    if key.dim() != 2:
        raise ValueError(
            f"key must be 2D [num_tokens, num_kv_heads*head_dim]; "
            f"got shape {tuple(key.shape)}"
        )

    # Look for slot_mapping side-channel. The streaming runner
    # patches Attention.forward to stash attn_metadata where this
    # hook can find it (see runner_vllm_streaming.py).
    slot_mapping = getattr(evictor, "_phase4_pending_slot_mapping", None)
    block_size = getattr(evictor, "_block_size", 16)
    if slot_mapping is None:
        # No attn_metadata side-channel. Skip silently — the
        # outer hook's try/except logs once if enable_logging.
        return

    # Number of decode tokens to capture. The runner's outer hook
    # also stashes the count.
    num_decode_tokens = getattr(
        evictor, "_phase4_pending_num_decode_tokens", 0,
    )
    if num_decode_tokens <= 0:
        return

    # Determine head_dim from the K tensor.
    total_dim = key.shape[-1]
    if inferred_head_dim is not None:
        head_dim = inferred_head_dim
    else:
        # Best-effort: assume a single KV head for derivation.
        head_dim = total_dim
    if head_dim % 2 != 0:
        raise ValueError(
            f"head_dim must be even (RoPE pairs adjacent dims); "
            f"got {head_dim}"
        )
    num_kv_heads = max(1, total_dim // head_dim)
    num_bands = head_dim // 2

    # Slice the decode portion of K.
    num_tokens = key.shape[0]
    decode_start = num_tokens - num_decode_tokens
    if decode_start < 0:
        return
    decode_key = key[decode_start:].detach().to("cpu").float()
    # Reshape: [decode_tokens, num_kv_heads, num_bands, 2]
    decode_key = decode_key.view(
        num_decode_tokens, num_kv_heads, num_bands, 2,
    )
    # Slice to head 0 (TriAttention's KV-head-aligned simplification).
    head_k = decode_key[:, 0, :, :]   # [decode_tokens, num_bands, 2]
    k_real_per_token = head_k[..., 0].tolist()
    k_imag_per_token = head_k[..., 1].tolist()

    # slot_mapping is shape [num_tokens] of slot indices (block_id *
    # block_size + offset). Slice the decode portion.
    if hasattr(slot_mapping, "tolist"):
        slot_list = slot_mapping[decode_start:].tolist()
    else:
        slot_list = list(slot_mapping)[decode_start:]

    if hasattr(positions, "tolist"):
        pos_list = positions[decode_start:].tolist()
    else:
        pos_list = list(positions)[decode_start:]

    # Group per block.
    per_block: Dict[int, List[Tuple[int, List[float], List[float]]]] = {}
    for tok_idx in range(num_decode_tokens):
        slot = int(slot_list[tok_idx])
        if slot < 0:
            continue
        block_id = slot // block_size
        position = int(pos_list[tok_idx])
        per_block.setdefault(block_id, []).append(
            (position, list(k_real_per_token[tok_idx]),
             list(k_imag_per_token[tok_idx])),
        )

    for block_id, keys in per_block.items():
        try:
            evictor.set_block_pre_rope_keys(
                block_id=block_id, keys=keys,
                layer=layer, head=head,
            )
        except Exception:
            # Block may already have been evicted; skip silently.
            continue
