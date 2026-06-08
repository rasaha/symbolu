"""Protected-K INT4 KV cache for the fused decode kernel.

Per-(layer, sequence) preallocated INT4-packed K/V buffers driven by
the model-level fused-decode bypass in route-A (see
``Bench/scripts/KERNEL_6C3A_DESIGN.md``).

What this is
------------

A small class that owns the buffers the fused decode kernel
(``int4_fused_attention_kernel.fused_protected_k_decode_attention``)
needs as input:

* ``k_packed``, ``k_scale``, ``k_offset``, ``k_fp16``, ``v_packed``,
  ``v_scale``, ``v_offset``, ``protect_mask`` — all sized for the
  current sequence's accumulated KV.

On each prefill or decode forward, the route-A wrapper calls
``append(key, value)`` with this step's K/V (T tokens at a time);
on decode it then calls ``kernel_inputs()`` and runs the kernel.

What this is NOT
----------------

* Not a paged cache. v1 pre-allocates ``max_seq_len`` per buffer;
  paging is 6c.3C.
* Not multi-sequence. One cache per (layer, sequence); the manager
  reuses one cache per layer with ``reset()`` between requests.
* Not a memory-compression vehicle. The buffers live ON TOP of
  vLLM's existing FP16 KV pool — see the design note's "memory
  footprint" honesty notice.

v1 scope (locked in ``Bench/scripts/KERNEL_6C3A_DESIGN.md`` §2):

* batch=1, single-sequence
* ``k_group_size=1`` (per-token K — clean incremental append)
* ``v_group_size=32`` (within-token, no incremental issue)
* preallocated contiguous buffers up to ``max_seq_len``
* per-sequence-static top-fraction protect_mask, frozen on first
  ``kernel_inputs()`` call
* CPU-importable (pure PyTorch quantize; the kernel itself is GPU-only)

Numerical contract: after a sequence of ``append`` calls, the tensors
returned by ``kernel_inputs()`` match what the test
``Bench/scripts/kernel_6c_gpu_test.py`` constructs for the
fused kernel — i.e. the kernel's GPU-validated input shapes.
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover - guarded at caller
    torch = None  # type: ignore

logger = logging.getLogger("int4_protected_k_cache")


class ProtectedKINT4Cache:
    """Per-layer INT4-packed K/V cache + protected-K FP16 side-tensor.

    Lazy-allocates buffers on the first ``append()`` (uses the input
    tensor's ``H_kv``, ``D``, ``device``). Caller appends T tokens at
    a time (T = prefill length, then T = 1 per decode step), then
    calls ``kernel_inputs()`` on decode to get the kernel's inputs.

    Lifecycle (per design note §3.2):

      reset()           → ``s_curr = 0``, mask cleared, buffers kept
      append(k, v)      → quantize + pack + write at s_curr; s_curr += T
      freeze_protect_mask() → top-fraction over k_fp16_buf[:s_curr]
      kernel_inputs()   → slice, permute, contiguous, unsqueeze(B=1)

    ``kernel_inputs`` auto-calls ``freeze_protect_mask`` on first
    invocation so the prefill→decode transition needs no explicit
    freeze call from the caller.
    """

    def __init__(
        self,
        *,
        max_seq_len: int,
        protect_fraction: float = 0.04,
        k_group_size: int = 1,
        v_group_size: int = 32,
        asymmetric: bool = True,
        bits: int = 4,
    ) -> None:
        if torch is None:
            raise ImportError("ProtectedKINT4Cache requires PyTorch.")
        if max_seq_len < 1:
            raise ValueError(f"max_seq_len must be >= 1; got {max_seq_len}")
        if not (0.0 <= protect_fraction <= 1.0):
            raise ValueError(
                f"protect_fraction must be in [0, 1]; got {protect_fraction}"
            )
        if k_group_size != 1:
            # v1 only handles the per-token K case. group_size>1 along
            # the seq axis works at the kernel level but the cache's
            # incremental append must handle partial-group accounting
            # — that's a v2 follow-on (KERNEL_6C3A_DESIGN.md §2).
            raise ValueError(
                f"v1 only supports k_group_size=1 (per-token K); got "
                f"{k_group_size}. Group-along-seq with partial-group "
                "incremental appends is a v2 follow-on."
            )
        if v_group_size < 1:
            raise ValueError(f"v_group_size must be >= 1; got {v_group_size}")
        if not (2 <= bits <= 8):
            raise ValueError(f"bits must be in [2, 8]; got {bits}")

        self._max_seq_len = int(max_seq_len)
        self._protect_fraction = float(protect_fraction)
        self._k_group_size = int(k_group_size)
        self._v_group_size = int(v_group_size)
        self._asymmetric = bool(asymmetric)
        self._bits = int(bits)

        # Lazy-allocated on first append.
        self._allocated = False
        self._num_kv_heads: Optional[int] = None
        self._head_dim: Optional[int] = None
        self._device = None
        self._n_grp_v: Optional[int] = None

        # Buffers (set on _allocate).
        self.k_packed_buf: Optional["torch.Tensor"] = None
        self.k_scale_buf: Optional["torch.Tensor"] = None
        self.k_offset_buf: Optional["torch.Tensor"] = None
        self.k_fp16_buf: Optional["torch.Tensor"] = None
        self.v_packed_buf: Optional["torch.Tensor"] = None
        self.v_scale_buf: Optional["torch.Tensor"] = None
        self.v_offset_buf: Optional["torch.Tensor"] = None

        # Per-sequence state.
        self._s_curr = 0
        self._protect_mask: Optional["torch.Tensor"] = None
        self._protect_frozen = False
        # Set True by route-A if a sidecar append fails mid-sequence —
        # decode bypass must then refuse to fire on a possibly-stale
        # cache, even though the kernel inputs would still "look right".
        self._poisoned = False

        # Stats.
        self._appends = 0
        self._tokens_appended = 0
        self._kernel_inputs_calls = 0
        self._freeze_calls = 0

    # ------------------------------------------------------------------ #
    # Properties                                                         #
    # ------------------------------------------------------------------ #

    @property
    def seq_len(self) -> int:
        return self._s_curr

    @property
    def max_seq_len(self) -> int:
        return self._max_seq_len

    @property
    def num_kv_heads(self) -> Optional[int]:
        return self._num_kv_heads

    @property
    def head_dim(self) -> Optional[int]:
        return self._head_dim

    @property
    def device(self):
        return self._device

    @property
    def is_allocated(self) -> bool:
        return self._allocated

    @property
    def is_frozen(self) -> bool:
        return self._protect_frozen

    @property
    def is_poisoned(self) -> bool:
        return self._poisoned

    @property
    def asymmetric(self) -> bool:
        return self._asymmetric

    @property
    def k_group_size(self) -> int:
        return self._k_group_size

    @property
    def v_group_size(self) -> int:
        return self._v_group_size

    @property
    def protect_fraction(self) -> float:
        return self._protect_fraction

    @property
    def bits(self) -> int:
        return self._bits

    @property
    def stats(self) -> dict:
        return {
            "appends": self._appends,
            "tokens_appended": self._tokens_appended,
            "kernel_inputs_calls": self._kernel_inputs_calls,
            "freeze_calls": self._freeze_calls,
            "seq_len": self._s_curr,
            "is_frozen": self._protect_frozen,
            "is_poisoned": self._poisoned,
            "allocated": self._allocated,
            "n_protected_channels": (
                int(self._protect_mask.sum().item())
                if self._protect_mask is not None else 0
            ),
        }

    # ------------------------------------------------------------------ #
    # Lifecycle                                                          #
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """Clear per-sequence state. Keeps buffers + alloc shapes.

        Called by the manager between requests. ``_poisoned`` clears
        here too — a fresh sequence gets a fresh chance.
        """
        self._s_curr = 0
        self._protect_mask = None
        self._protect_frozen = False
        self._poisoned = False

    def mark_poisoned(self, reason: str = "") -> None:
        """Disable the decode bypass for the remainder of this sequence.

        Called by the route-A wrapper when a prefill sidecar append
        raises — the cache may be out of sync with vLLM's view of K/V
        for later positions, so the kernel's output would be wrong.
        """
        self._poisoned = True

    def _allocate(
        self, *, num_kv_heads: int, head_dim: int, device, dtype,
    ) -> None:
        if self._allocated:
            return
        # Buffers are always FP16 internally regardless of the input
        # dtype. ``append`` casts BF16 / FP32 / FP16 inputs to FP16
        # before calling ``_allocate`` (see ``append``). This keeps the
        # kernel's input contract pure FP16 — the kernel was validated
        # against FP16 inputs by ``kernel_6c_gpu_test.py``.
        if dtype != torch.float16:
            raise ValueError(
                f"ProtectedKINT4Cache buffer dtype must be FP16; got "
                f"{dtype}. (append() should have cast before calling "
                "_allocate — this is a bug in append.)"
            )
        if head_dim % 2 != 0:
            raise ValueError(
                f"head_dim must be even (INT4 packs 2 nibbles/byte); "
                f"got {head_dim}"
            )
        if head_dim % self._v_group_size != 0:
            raise ValueError(
                f"head_dim {head_dim} not divisible by v_group_size "
                f"{self._v_group_size}"
            )
        self._num_kv_heads = int(num_kv_heads)
        self._head_dim = int(head_dim)
        self._device = device
        self._n_grp_v = head_dim // self._v_group_size

        MS = self._max_seq_len
        H = num_kv_heads
        D = head_dim
        DH = D // 2
        nv = self._n_grp_v

        self.k_packed_buf = torch.empty(
            (MS, H, DH), dtype=torch.uint8, device=device,
        )
        self.k_scale_buf = torch.empty(
            (MS, H, D), dtype=torch.float16, device=device,
        )
        self.k_fp16_buf = torch.empty(
            (MS, H, D), dtype=torch.float16, device=device,
        )
        self.v_packed_buf = torch.empty(
            (MS, H, DH), dtype=torch.uint8, device=device,
        )
        self.v_scale_buf = torch.empty(
            (MS, H, nv), dtype=torch.float16, device=device,
        )
        if self._asymmetric:
            self.k_offset_buf = torch.empty(
                (MS, H, D), dtype=torch.float16, device=device,
            )
            self.v_offset_buf = torch.empty(
                (MS, H, nv), dtype=torch.float16, device=device,
            )
        self._allocated = True

    # ------------------------------------------------------------------ #
    # Append                                                             #
    # ------------------------------------------------------------------ #

    def append(self, key: "torch.Tensor", value: "torch.Tensor") -> None:
        """Append ``T`` tokens of K/V to the cache.

        ``key``, ``value``: shape ``(T, H_kv, D)``, FP16, on a single
        device. ``T >= 1``. Quantizes via
        ``quantize_per_channel_int4`` (K, group=1) and
        ``quantize_per_token_int4`` (V, group=v_group_size), then
        ``pack_int4`` along ``head_dim``. Writes contiguously at
        ``[s_curr : s_curr + T]`` of every buffer.
        """
        if torch is None:
            raise ImportError("ProtectedKINT4Cache.append requires PyTorch.")
        from kv_policy.int4_per_channel_kv import (
            quantize_per_channel_int4, quantize_per_token_int4, pack_int4,
        )

        if key.ndim != 3 or value.ndim != 3:
            raise ValueError(
                f"append expects 3-D (T, H_kv, D) tensors; got K "
                f"{tuple(key.shape)}, V {tuple(value.shape)}"
            )
        if key.shape != value.shape:
            raise ValueError(
                f"K and V shapes must match; got K {tuple(key.shape)} vs "
                f"V {tuple(value.shape)}"
            )

        T, H, D = key.shape
        if T < 1:
            return

        # Accept FP16 / BF16 / FP32 inputs — cast to FP16 BEFORE alloc
        # so the buffer dtype contract (FP16, kernel-compatible) holds
        # regardless of how the model loaded. Most vLLM models load in
        # BF16 by default (Qwen2.5, Llama-3); FP16 is rarer.
        if key.dtype not in (torch.float16, torch.bfloat16, torch.float32):
            raise ValueError(
                f"append expects FP16 / BF16 / FP32 K/V; got K dtype "
                f"{key.dtype}. (Quantize ops handle any float dtype "
                "internally; we restrict to these three for safety.)"
            )
        if key.dtype != value.dtype:
            raise ValueError(
                f"K and V dtypes must match; got K {key.dtype}, "
                f"V {value.dtype}"
            )
        if key.dtype != torch.float16:
            key = key.to(torch.float16)
            value = value.to(torch.float16)
        key = key.contiguous()
        value = value.contiguous()

        if not self._allocated:
            self._allocate(
                num_kv_heads=H, head_dim=D,
                device=key.device, dtype=key.dtype,  # always FP16 now
            )
        else:
            if (H, D) != (self._num_kv_heads, self._head_dim):
                raise ValueError(
                    f"append got shape (T={T}, H={H}, D={D}) but cache "
                    f"was allocated for (H={self._num_kv_heads}, "
                    f"D={self._head_dim})"
                )
            if key.device != self._device:
                raise ValueError(
                    f"append got tensor on {key.device} but cache is on "
                    f"{self._device}"
                )

        end = self._s_curr + T
        if end > self._max_seq_len:
            raise ValueError(
                f"append would exceed max_seq_len: s_curr={self._s_curr}"
                f" + T={T} = {end} > max_seq_len={self._max_seq_len}. "
                "Pre-allocate a larger cache or use a paged 6c.3.2 / "
                "6c.3C variant."
            )

        # K: per-channel along seq with group=1.
        kq, ks, ko = quantize_per_channel_int4(
            key,
            group_size=self._k_group_size,
            asymmetric=self._asymmetric,
            bits=self._bits,
        )
        k_packed = pack_int4(kq)
        self.k_packed_buf[self._s_curr:end] = k_packed
        self.k_scale_buf[self._s_curr:end] = ks.to(torch.float16)
        self.k_fp16_buf[self._s_curr:end] = key
        if self._asymmetric:
            self.k_offset_buf[self._s_curr:end] = ko.to(torch.float16)

        # V: per-token along head_dim with group=v_group_size.
        vq, vs, vo = quantize_per_token_int4(
            value,
            group_size=self._v_group_size,
            asymmetric=self._asymmetric,
            bits=self._bits,
        )
        v_packed = pack_int4(vq)
        self.v_packed_buf[self._s_curr:end] = v_packed
        self.v_scale_buf[self._s_curr:end] = vs.to(torch.float16)
        if self._asymmetric:
            self.v_offset_buf[self._s_curr:end] = vo.to(torch.float16)

        self._s_curr = end
        self._appends += 1
        self._tokens_appended += T
        # Appending does NOT auto-invalidate a frozen mask — the mask
        # is per-sequence-static and chosen from prefill. Reset clears
        # it. See KERNEL_6C3A_DESIGN.md §3.2.

    # ------------------------------------------------------------------ #
    # Protect mask                                                       #
    # ------------------------------------------------------------------ #

    def freeze_protect_mask(self) -> None:
        """Compute the static protect_mask from ``k_fp16_buf[:s_curr]``.

        Top-``round(protect_fraction * H_kv * D)`` channels by
        max-abs over the seq buffer, expressed as ``(H_kv, D) int8``
        with 1 at protected channels and 0 elsewhere — the exact
        layout the fused kernel's ``protect_mask`` argument expects.

        Per design note §3.2 this happens at end-of-prefill;
        ``kernel_inputs`` calls it lazily on first invocation.
        """
        if not self._allocated:
            raise ValueError("freeze_protect_mask called before any append.")
        if self._s_curr < 1:
            raise ValueError("freeze_protect_mask called with empty cache.")

        H = self._num_kv_heads
        D = self._head_dim
        # (s_curr, H, D) -> (H, D) max-abs.
        mag = self.k_fp16_buf[: self._s_curr].abs().amax(dim=0).float()
        if self._protect_fraction <= 0.0:
            mask = torch.zeros(H, D, dtype=torch.int8, device=self._device)
        elif self._protect_fraction >= 1.0:
            mask = torch.ones(H, D, dtype=torch.int8, device=self._device)
        else:
            n_protect = max(1, round(self._protect_fraction * H * D))
            idx = torch.topk(mag.reshape(-1), n_protect).indices
            flat = torch.zeros(H * D, dtype=torch.int8, device=self._device)
            flat[idx] = 1
            mask = flat.reshape(H, D)
        self._protect_mask = mask
        self._protect_frozen = True
        self._freeze_calls += 1

    # ------------------------------------------------------------------ #
    # Kernel inputs                                                      #
    # ------------------------------------------------------------------ #

    def kernel_inputs(self, active_positions=None) -> dict:
        """Return the tensors the fused kernel expects.

        ``active_positions`` (READ-SKIP): an optional sorted 1-D index of the KV
        positions to actually read this step (sink + recent + decode-attention
        selected blocks — see kv_policy/readskip_select.py). When given, the
        per-position buffers are COMPACTED to those positions so the fused kernel
        iterates only ``len(active_positions)`` tiles (physical read-skip); the
        unread (cold) positions remain STORED in int4 (density preserved).
        ``None`` reads the full ``[:s]`` sequence (identity — byte-eq baseline).

        Why the gather is byte-safe: every buffer is ``(MS, H, *)`` per-position;
        K scale is per-position (``k_group_size=1``) and V scale groups over
        head_dim (not sequence), so a position-gather stays aligned with the
        kernel's per-position scale indexing. Rotary is baked into the stored K,
        so gathering preserves positional encoding.

        Auto-freezes the protect mask on first call. Returns a dict
        ready to be ``**``-unpacked into
        ``fused_protected_k_decode_attention(q=..., **inputs,
        group_size_k=..., group_size_v=..., asymmetric=...)``.

        Layouts (B=1 in v1):

          k_packed   (1, H_kv, S_kv, D//2)  uint8     — copy
          k_scale    (1, S_kv, H_kv, D)     fp16      — view
          k_offset   (1, S_kv, H_kv, D)     fp16/None — view
          k_fp16     (1, H_kv, S_kv, D)     fp16      — copy
          protect_mask (H_kv, D)            int8      — view
          v_packed   (1, H_kv, S_kv, D//2)  uint8     — copy
          v_scale    (1, S_kv, H_kv, n_grp_v) fp16    — view
          v_offset   (1, S_kv, H_kv, n_grp_v) fp16/None — view

        Three ``.contiguous()`` copies — accepted v1 overhead per
        the design note §3.3.
        """
        if torch is None:
            raise ImportError("kernel_inputs requires PyTorch.")
        if not self._allocated:
            raise ValueError("kernel_inputs called before any append.")
        if self._s_curr < 1:
            raise ValueError("kernel_inputs called with empty cache.")
        if not self._protect_frozen:
            self.freeze_protect_mask()

        self._kernel_inputs_calls += 1
        s = self._s_curr

        # Read every stored position ([:s], identity) unless a read-skip index is
        # given, in which case gather only the retained positions (compacted).
        if active_positions is None:
            rows = slice(0, s)
        else:
            # Step 3: the controller passes an in-range GPU tensor (active_index);
            # index_select needs int64. Cast (cheap on-device) but SKIP the
            # int(min)/int(max) bounds-check sync for tensor inputs (it's a
            # per-layer-per-step GPU->CPU stall and the controller guarantees the
            # range). Python-list inputs (tests/other callers) keep the check.
            already_tensor = torch.is_tensor(active_positions)
            rows = torch.as_tensor(active_positions, dtype=torch.long,
                                   device=self.k_packed_buf.device)
            if rows.ndim != 1 or rows.numel() < 1:
                raise ValueError("active_positions must be a non-empty 1-D index")
            if not already_tensor and (int(rows.min()) < 0 or int(rows.max()) >= s):
                raise ValueError(
                    f"active_positions out of range [0,{s}): "
                    f"[{int(rows.min())},{int(rows.max())}]")
            self._kernel_inputs_skip_calls = (
                getattr(self, "_kernel_inputs_skip_calls", 0) + 1)

        # Permute (n, H, *) -> (H, n, *), contiguous-copy, unsqueeze(B=1).
        k_packed = (
            self.k_packed_buf[rows].permute(1, 0, 2).contiguous().unsqueeze(0)
        )
        k_fp16 = (
            self.k_fp16_buf[rows].permute(1, 0, 2).contiguous().unsqueeze(0)
        )
        v_packed = (
            self.v_packed_buf[rows].permute(1, 0, 2).contiguous().unsqueeze(0)
        )
        # Scales/offsets already in (n, H, *); just unsqueeze.
        k_scale = self.k_scale_buf[rows].unsqueeze(0)
        v_scale = self.v_scale_buf[rows].unsqueeze(0)
        if self._asymmetric:
            k_offset = self.k_offset_buf[rows].unsqueeze(0)
            v_offset = self.v_offset_buf[rows].unsqueeze(0)
        else:
            k_offset = None
            v_offset = None

        return {
            "k_packed": k_packed,
            "k_scale": k_scale,
            "k_offset": k_offset,
            "k_fp16": k_fp16,
            "protect_mask": self._protect_mask,
            "v_packed": v_packed,
            "v_scale": v_scale,
            "v_offset": v_offset,
        }

    def kernel_inputs_gather(self, active_positions) -> dict:
        """READ-SKIP Step 2: return the FULL, NATIVE, per-position buffers (no
        permute, no index_select) plus ``gather_idx`` — the retained positions as
        an int32 index. For ``fused_protected_k_decode_attention_gather``, which
        reads K/V in place at ``gather_idx[logical]`` instead of compacting first.
        Removes the 3 permute-contiguous copies AND the gather of
        ``kernel_inputs(active_positions=…)``. ``k_group_size == 1`` only.

        Returns ``[:s]`` views of the cache buffers (zero-copy) and the index."""
        if torch is None:
            raise ImportError("kernel_inputs_gather requires PyTorch.")
        if not self._allocated or self._s_curr < 1:
            raise ValueError("kernel_inputs_gather called on empty cache.")
        if self._k_group_size != 1:
            raise ValueError("kernel_inputs_gather assumes k_group_size == 1.")
        if not self._protect_frozen:
            self.freeze_protect_mask()
        s = self._s_curr
        # Step 3: the controller passes an in-range GPU int32 tensor; skip the
        # per-step bounds-check sync for tensor inputs (controller guarantees it).
        already_tensor = torch.is_tensor(active_positions)
        gather_idx = torch.as_tensor(
            active_positions, dtype=torch.int32, device=self.k_packed_buf.device)
        if gather_idx.ndim != 1 or gather_idx.numel() < 1:
            raise ValueError("active_positions must be a non-empty 1-D index")
        if not already_tensor and (int(gather_idx.min()) < 0 or int(gather_idx.max()) >= s):
            raise ValueError(
                f"active_positions out of range [0,{s}): "
                f"[{int(gather_idx.min())},{int(gather_idx.max())}]")
        self._kernel_inputs_calls += 1
        self._kernel_inputs_skip_calls = (
            getattr(self, "_kernel_inputs_skip_calls", 0) + 1)
        return {
            "k_packed": self.k_packed_buf[:s],          # (s, H_kv, D//2) native view
            "k_scale": self.k_scale_buf[:s],            # (s, H_kv, D)
            "k_offset": self.k_offset_buf[:s] if self._asymmetric else None,
            "k_fp16": self.k_fp16_buf[:s],              # (s, H_kv, D)
            "protect_mask": self._protect_mask,
            "v_packed": self.v_packed_buf[:s],          # (s, H_kv, D//2)
            "v_scale": self.v_scale_buf[:s],            # (s, H_kv, n_grp_v)
            "v_offset": self.v_offset_buf[:s] if self._asymmetric else None,
            "gather_idx": gather_idx,
        }

    def block_attention_scores(self, query, block_size: int,
                               use_kernel: bool = False) -> list:
        """READ-SKIP scoring: per-block decode-attention mass from `query` to the
        stored K, reconstructed EXACTLY as the fused kernel does
        (kiv*scale(+offset), then protect-overlay where the mask is set). Returns
        a python list of length n_blocks. Called only on observe/refresh steps.

        GQA: query heads are mean-pooled within each KV-head group. GPU path.

        ``use_kernel`` (Step 1): emit the per-block scores from a fused Triton pass
        (``fused_protected_k_block_scores``) instead of reconstructing the WHOLE K
        in eager torch — the Phase-10 measured bottleneck. Same result (proven by
        the numpy decomposition==softmax proof); fail-open to the torch path if the
        kernel is unavailable or raises.
        """
        import math
        from kv_policy.int4_per_channel_kv import unpack_int4
        s = self._s_curr
        D = self._head_dim
        H_kv = self._num_kv_heads
        nb = (s + block_size - 1) // block_size
        if s < 1 or D is None or H_kv is None:
            return [0.0] * max(nb, 0)
        # The protect mask is frozen lazily by kernel_inputs(); scoring runs
        # BEFORE that on the first decode step, so freeze here if needed.
        if not self._protect_frozen:
            self.freeze_protect_mask()

        # ---- Step 1: kernel-emitted block scores (no torch K reconstruction) ----
        if use_kernel and torch is not None and getattr(query, "is_cuda", False) \
                and self._k_group_size == 1:
            try:
                from kv_policy.int4_fused_attention_kernel import (
                    fused_protected_k_block_scores, combine_block_scores)
                blk_sum, blk_max = fused_protected_k_block_scores(
                    query, self.k_packed_buf, self.k_scale_buf,
                    (self.k_offset_buf if self._asymmetric else None),
                    self.k_fp16_buf, self._protect_mask,
                    num_kv_heads=H_kv, head_dim=D, asymmetric=self._asymmetric,
                    block_size=block_size, seq_len=s)
                return combine_block_scores(blk_sum, blk_max)
            except Exception:  # noqa: BLE001 — fail-open to the torch path
                logger.exception(
                    "kernel block-scores failed; falling back to torch scoring")

        # ---- Torch path (reference): reconstruct K_eff (s, H_kv, D) exactly. ----
        kiv = unpack_int4(self.k_packed_buf[:s], D).float()          # [-8,7]
        k_dq = kiv * self.k_scale_buf[:s].float()
        if self._asymmetric and self.k_offset_buf is not None:
            k_dq = k_dq + self.k_offset_buf[:s].float()
        if self._protect_mask is not None:
            pm = self._protect_mask.bool().unsqueeze(0)              # (1,H,D)
            k_eff = torch.where(pm, self.k_fp16_buf[:s].float(), k_dq)
        else:
            k_eff = k_dq                                            # no protection
        # Query -> per-KV-head via GQA mean-pool.
        q = query.reshape(-1, D).float()                            # (H_q, D)
        H_q = q.shape[0]
        if H_q < 1 or H_q % H_kv != 0:
            return [0.0] * nb
        q_kv = q.view(H_kv, H_q // H_kv, D).mean(dim=1)             # (H_kv, D)
        logits = torch.einsum("hd,shd->hs", q_kv, k_eff) / math.sqrt(D)
        probs = torch.softmax(logits, dim=-1)                       # (H_kv, s)
        pos_mass = probs.sum(dim=0)                                 # (s,)
        blk = torch.zeros(nb, device=pos_mass.device, dtype=pos_mass.dtype)
        idx = (torch.arange(s, device=pos_mass.device) // block_size)
        blk.scatter_add_(0, idx, pos_mass)
        return blk.tolist()

    # ------------------------------------------------------------------ #
    # Repr                                                               #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"ProtectedKINT4Cache(max_seq_len={self._max_seq_len}, "
            f"protect_fraction={self._protect_fraction}, "
            f"k_group_size={self._k_group_size}, "
            f"v_group_size={self._v_group_size}, "
            f"asymmetric={self._asymmetric}, bits={self._bits}, "
            f"H_kv={self._num_kv_heads}, D={self._head_dim}, "
            f"s_curr={self._s_curr}, frozen={self._protect_frozen}, "
            f"poisoned={self._poisoned})"
        )
