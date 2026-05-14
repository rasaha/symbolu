"""HuggingFace ``DynamicCache`` subclass that compresses K/V on update.

This is the **route B** integration path from
``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §16.2 — a HuggingFace-
transformers attention-hook bypass that exercises TurboQuant
compression in a real model forward pass *without* requiring vLLM's
``cache_kv`` monkey-patch (which is the route-A blocker that this
session deferred).

Used by ``Bench/scripts/track_e_quality_eval.py`` to drive perplexity
and MMLU-subset evaluation against Qwen2.5-7B with lossy KV cache.
The lossy K/V flows back into the parent cache and into subsequent
attention computation, exactly mirroring what a production
TurboQuant-on-vLLM deployment would experience.

Why this is OK for quality-only measurement (not for production
serving): we still pay the compression cost on every update, AND we
still hold the lossy KV in the parent cache (no actual memory savings
because we're storing the decompressed full-precision tensor). What
this measures is purely the *information-loss* impact of compression
on attention output and downstream generation — exactly the question
Track E exists to answer. Real memory savings need the
``cache_kv`` hook + bit-packed storage (Tier 3 work).

Scope note
----------

Each HF ``DynamicCache.update()`` call passes a tensor of shape
``(batch, num_kv_heads, seq_len_new, head_dim)`` where ``seq_len_new``
is the entire prefill on the first call (typically 50-250 tokens for
MMLU prompts) and 1 on each subsequent decode step. This cache wrapper
compresses the *whole chunk* as one TurboQuant block per call. The
§14.2 / §15.2 partner-shareable cosine numbers were measured on a
single vLLM-style 16-token block. PolarQuant is segment-local at 128
elements, so the per-segment math is identical — but the *scope* of
what gets compressed in one ``write_block`` call differs. See
``Bench/scripts/RUNPOD_TRACK_D_E_RUNBOOK.md`` § "Scope note" for the
partner-conversation framing.

Track E result (Qwen2.5-7B-Instruct)
------------------------------------

See ``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §17 for the full
writeup. Headline:

| angle_bits | compression vs FP16 | PPL ratio | verdict |
|---:|---:|---:|---|
| 3 (arch-doc default) | 3.58× | 3052× | catastrophic |
| 4 | 2.69× | 301× | catastrophic |
| 8 (no QJL, ~lossless) | 1.96× | 0.94× | within noise |

The 8-bit lossless result validates this cache wrapper's plumbing.
The 3-bit and 4-bit failures reflect the PolarQuant algorithm at low
bit depths on Qwen2.5-7B, not the integration. Softmax-attention's
exponential amplification of K errors means cosine 0.965 (block-
level) does not imply preserved generation quality. Do not deploy
TurboQuant-compressed KV at the current algorithm config without
revisiting §17.7's recommended algorithm modifications.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

try:
    from transformers.cache_utils import DynamicCache  # type: ignore
except ImportError:  # pragma: no cover
    DynamicCache = None  # type: ignore


def _compress_decompress_kv(
    k: "torch.Tensor",
    v: "torch.Tensor",
    *,
    store: Any,
) -> "tuple[torch.Tensor, torch.Tensor]":
    """Round-trip a (B, H, S, D) K/V pair through ``TurboQuantKVStore``.

    The kvstore expects per-block tensors of shape
    ``(block_size, num_kv_heads, head_dim)`` (vLLM's slot layout). HF
    transformers gives us ``(batch, num_kv_heads, seq_len, head_dim)``.
    We transpose to put the seq axis first, run one write/read per
    batch element, and transpose back. block_id is reused per call
    (the kvstore is throwaway-per-call in this Cache wrapper — its
    persistence is intentionally not used; we only want the lossy
    round-trip).

    Returns the lossy K, V with the input shape and dtype preserved.
    """
    if k.ndim != 4 or v.ndim != 4:
        raise ValueError(
            f"_compress_decompress_kv expected 4-D (B, H, S, D) tensors, "
            f"got K.shape={tuple(k.shape)}, V.shape={tuple(v.shape)}"
        )
    b = k.shape[0]
    if v.shape[0] != b:
        raise ValueError(f"K batch {b} != V batch {v.shape[0]}")

    k_out = torch.empty_like(k)
    v_out = torch.empty_like(v)
    for batch_idx in range(b):
        # (H, S, D) → (S, H, D) — vLLM block layout
        k_block = k[batch_idx].transpose(0, 1).contiguous()
        v_block = v[batch_idx].transpose(0, 1).contiguous()
        store.write_block(0, k_block, v_block)
        k_back, v_back = store.read_block(0)
        store.remove_block(0)
        k_out[batch_idx] = k_back.transpose(0, 1)
        v_out[batch_idx] = v_back.transpose(0, 1)
    return k_out, v_out


class TurboQuantCache(DynamicCache if DynamicCache is not None else object):
    """``DynamicCache`` that compresses K/V on every update.

    Drop-in replacement for ``DynamicCache`` in HF generation calls.
    Construct one per generation call (compressed state is stale across
    generations because each generation builds its own KV cache).

    Args:
        angle_bits: Polar quantisation bit width (3 / 4). Default 3 to
            match the architecture-doc target.
        segment_dim: PolarQuant segment size. Default 128 to match the
            existing benchmark + Track B Tier 1/2 measurements.
        enable_qjl: Whether to apply the QJL residual sign projection
            during compression. Default True. Note that QJL doesn't
            affect reconstruction (see numpy reference lines 862-865)
            so the cosine number is the same with QJL on or off; the
            difference is only in the theoretical compression-ratio
            number reported by ``compression_ratio``.
        backend: ``"numpy"`` (default) or ``"torch"``. The torch backend
            keeps tensors on whatever device they arrived on, which is
            the only sensible choice on a GPU pod. The numpy backend
            forces a host transit per update — fine for debugging on
            CPU, catastrophic on GPU.
        torch_device: optional device override for the torch backend's
            internal compressor state.
    """

    def __init__(
        self,
        *,
        angle_bits: int = 3,
        segment_dim: int = 128,
        enable_qjl: bool = True,
        backend: str = "torch",
        torch_device: Optional[Any] = None,
    ) -> None:
        if DynamicCache is None:
            raise ImportError(
                "TurboQuantCache requires HuggingFace transformers. Install "
                "with `pip install transformers`."
            )
        if torch is None:
            raise ImportError(
                "TurboQuantCache requires PyTorch."
            )
        super().__init__()
        # Lazy import — kv_policy is on a sibling sys.path that the
        # caller is responsible for setting up (see
        # ``Bench/scripts/track_e_quality_eval.py``).
        from kv_policy.turboquant_kvstore import TurboQuantKVStore
        self._tq_store = TurboQuantKVStore(
            angle_bits=angle_bits,
            enable_qjl=enable_qjl,
            segment_dim=segment_dim,
            backend=backend,
            torch_device=torch_device,
        )
        self._tq_cfg = dict(
            angle_bits=angle_bits,
            segment_dim=segment_dim,
            enable_qjl=enable_qjl,
            backend=backend,
        )
        # Counters for the eval JSON.
        self._tq_updates = 0
        self._tq_total_kv_elements = 0

    def update(
        self,
        key_states: "torch.Tensor",
        value_states: "torch.Tensor",
        layer_idx: int,
        *args,
        **kwargs,
    ) -> "tuple[torch.Tensor, torch.Tensor]":
        """Compress + decompress K/V then delegate to parent."""
        k_lossy, v_lossy = _compress_decompress_kv(
            key_states, value_states, store=self._tq_store,
        )
        self._tq_updates += 1
        self._tq_total_kv_elements += int(key_states.numel() + value_states.numel())
        return super().update(k_lossy, v_lossy, layer_idx, *args, **kwargs)

    @property
    def turboquant_config(self) -> dict:
        return dict(self._tq_cfg)

    @property
    def turboquant_stats(self) -> dict:
        """Stats for the eval JSON. Compression ratio comes from the
        kvstore's theoretical formula (matches the §14.2 partner
        number)."""
        s = self._tq_store.get_stats()
        s["updates"] = self._tq_updates
        s["total_kv_elements_seen"] = self._tq_total_kv_elements
        return s
