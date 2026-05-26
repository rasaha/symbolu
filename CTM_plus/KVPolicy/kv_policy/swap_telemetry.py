"""Phase TIER5A — Swap telemetry probes (read-only / observation-only).

Surfaces two new metrics the TIER5A acceptance gates require:

* **CPU swap pool occupancy** — how many CPU blocks vLLM currently
  holds for swapped-out KV. Read from
  ``block_manager.block_allocator._allocators[Device.CPU]`` (V2 dict
  form), ``block_allocator.cpu_allocator`` (V2 property form), or
  ``block_manager.cpu_allocator`` (V1 direct). All three paths are
  documented in vLLM 0.7.x; the prefix-hit probe + extended pinning
  install do the analogous walk for the GPU side.
* **Swap-in latency** — wall-time of the engine's swap-in operation
  per event. Installed via a monkey-patch on the CPU allocator's
  ``swap_in`` (or fallback) callable. RAII-style teardown.

## Orthogonality contract (durable, mirrors Phase 3 + Phase 4)

This module does NOT touch and MUST NOT import:

* ``Int4ProtectedAttentionImpl`` (orthogonal)
* The forked ``vllm-flash-attn`` kernel (orthogonal)
* The protected-channel splice, sink mechanism, or paged writer
  (all orthogonal)

The Phase TIER5A acceptance gates G5 + G6 enforce this contract
both via the static AST gate (test_swap_telemetry.py) and the
git/SHA pin (``tier5a_orthogonality_gate.py``).

## Composition contract

Composes additively with:

* ``cache_aware_install.install_cache_aware_scheduler`` (Phase 0-3)
* ``cache_aware_install.install_cache_aware_measurement_only``
  (Phase 3C measurement bridge)
* ``extended_pinning.install_extended_pinning`` (Phase 4A-C)
* ``prefix_hit_probe.install_prefix_hit_probe`` (Phase 3A)

Install order is free; teardown is LIFO per install handle.

## Why "observation-only"

Per the TIER5A briefing: Phase 5A verifies that the int4_protected
shipped backend's packed KV layout survives vLLM's built-in CPU
swap path. The verification is observation-only because the
orthogonality contract forbids any modification of the int4_protected
write/read path. This module's monkey-patch on ``swap_in`` is a
**timing hook**, not a behaviour change — the wrapped callable
delegates to the original after recording one ``perf_counter``
delta.

CPU-only design: all logic is unit-testable against mock
block_manager objects with V1/V2 fallback paths covered.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- #
# CpuSwapPoolSnapshot — read-only data class.
# ---------------------------------------------------------------- #


@dataclass(frozen=True)
class CpuSwapPoolSnapshot:
    """One point-in-time read of the CPU swap pool.

    Fields:
      * ``num_used_blocks`` — CPU blocks currently holding swapped
        KV. ``-1`` if the allocator doesn't expose used-block info.
      * ``num_total_blocks`` — total CPU blocks allocated by vLLM
        at engine start (controlled by ``swap_space`` GB).
      * ``block_size_tokens`` — vLLM ``cache_config.block_size``
        (typically 16 stock; ``int4_protected`` forces 32).
      * ``bytes_per_block_estimate`` — optional caller-supplied
        per-block byte cost. ``0`` if not available; the streaming
        runner derives this from the cache_config + model dtype
        when present.
      * ``hint_path`` — which allocator-walk path resolved.
        Useful for telemetry: distinguishes "no swap activity"
        from "could not find the allocator at all".
    """

    num_used_blocks: int
    num_total_blocks: int
    block_size_tokens: int
    bytes_per_block_estimate: int
    hint_path: str

    @property
    def num_used_bytes_estimate(self) -> int:
        """Approximate bytes in use. Returns 0 when
        ``bytes_per_block_estimate`` is unknown."""
        if self.bytes_per_block_estimate <= 0:
            return 0
        if self.num_used_blocks <= 0:
            return 0
        return int(self.num_used_blocks) * int(self.bytes_per_block_estimate)

    @property
    def utilization(self) -> float:
        """Fraction of the CPU swap pool in use, in [0.0, 1.0].
        Returns 0.0 if total is 0 or used is unknown."""
        if self.num_total_blocks <= 0:
            return 0.0
        if self.num_used_blocks < 0:
            return 0.0
        return min(1.0, float(self.num_used_blocks) / float(self.num_total_blocks))


# ---------------------------------------------------------------- #
# CPU allocator resolution — mirrors the V1/V2 fallback shape of
# cache_aware_install._resolve_gpu_allocator and prefix_hit_probe's
# allocator walk.
# ---------------------------------------------------------------- #


def _resolve_cpu_allocator(block_manager: Any) -> Tuple[Any, str]:
    """Walk the block manager to find the CPU-side allocator.

    Three documented paths (analogous to the GPU walk in
    cache_aware_install.py and extended_pinning.py):

    * V2 property: ``block_manager.block_allocator.cpu_allocator``
    * V2 dict:     ``block_manager.block_allocator._allocators[Device.CPU]``
    * V1 direct:   ``block_manager.cpu_allocator``

    Returns ``(allocator_or_none, hint_string)``. Returns
    ``(None, "no_known_path")`` if no path matched — the install
    or probe can still complete in a degraded mode (snapshot
    returns -1 for ``num_used_blocks``).
    """
    ba = getattr(block_manager, "block_allocator", None)
    if ba is not None:
        cpu = getattr(ba, "cpu_allocator", None)
        if cpu is not None:
            return cpu, "v2_block_allocator.cpu_allocator"
        allocators = getattr(ba, "_allocators", None)
        if isinstance(allocators, dict):
            for key in allocators:
                key_str = str(key).split(".")[-1].lower()
                if "cpu" in key_str:
                    return allocators[key], "v2_block_allocator._allocators[CPU]"
    v1_cpu = getattr(block_manager, "cpu_allocator", None)
    if v1_cpu is not None:
        return v1_cpu, "v1_block_manager.cpu_allocator"
    return None, "no_known_path"


def _read_allocator_block_counts(
    allocator: Any,
) -> Tuple[int, int]:
    """Read ``(num_used_blocks, num_total_blocks)`` from a vLLM
    allocator-like object.

    Tries several attribute / method names because vLLM's exact
    allocator surface differs by minor version + by allocator
    class (``NaiveBlockAllocator`` vs ``PrefixCachingBlockAllocator``
    vs ``CpuGpuBlockAllocator``'s per-device member).

    Returns ``(-1, 0)`` if neither used nor total can be read; the
    snapshot's ``num_used_blocks=-1`` is the signal to upstream that
    "we found an allocator but couldn't get a count".
    """
    # num_total_blocks: try the obvious attribute, then a few
    # method/property variants.
    total = -1
    for attr in (
        "num_total_blocks",
        "_num_total_blocks",
        "num_blocks",
        "total_blocks",
    ):
        v = getattr(allocator, attr, None)
        if v is None:
            continue
        if callable(v):
            try:
                v = v()
            except Exception:
                continue
        try:
            total = int(v)
            break
        except (TypeError, ValueError):
            continue

    # num_free_blocks: free-block count is widely exposed; we
    # derive used = total - free.
    free = -1
    for attr in (
        "get_num_free_blocks",
        "num_free_blocks",
        "_num_free_blocks",
        "free_blocks",
    ):
        v = getattr(allocator, attr, None)
        if v is None:
            continue
        if callable(v):
            try:
                v = v()
            except Exception:
                continue
        try:
            free = int(v)
            break
        except (TypeError, ValueError):
            continue

    # Direct used-block APIs (rare but cheap to try).
    used_direct = -1
    for attr in (
        "get_num_used_blocks",
        "num_used_blocks",
        "_num_used_blocks",
    ):
        v = getattr(allocator, attr, None)
        if v is None:
            continue
        if callable(v):
            try:
                v = v()
            except Exception:
                continue
        try:
            used_direct = int(v)
            break
        except (TypeError, ValueError):
            continue

    if used_direct >= 0:
        used = used_direct
    elif total > 0 and free >= 0:
        used = max(0, total - free)
    else:
        used = -1

    if total < 0:
        total = 0
    return used, total


def _resolve_block_size_tokens(
    block_manager: Any,
    *,
    fallback: int = 0,
) -> int:
    """Read vLLM's ``cache_config.block_size``. Mirrors
    runner_vllm_streaming._resolve_block_size_from_engine but
    operates on a block_manager (which doesn't carry the full
    engine handle). Returns ``fallback`` if no path resolves.
    """
    bs = getattr(block_manager, "block_size", None)
    if bs is not None:
        try:
            return int(bs)
        except (TypeError, ValueError):
            pass
    cfg = getattr(block_manager, "_cache_config", None) or getattr(
        block_manager, "cache_config", None,
    )
    if cfg is not None:
        bs = getattr(cfg, "block_size", None)
        if bs is not None:
            try:
                return int(bs)
            except (TypeError, ValueError):
                pass
    return int(fallback)


def read_cpu_swap_pool(
    block_manager: Any,
    *,
    bytes_per_block_estimate: int = 0,
    block_size_fallback: int = 0,
) -> CpuSwapPoolSnapshot:
    """Take a point-in-time snapshot of the CPU swap pool.

    Returns a fully-populated ``CpuSwapPoolSnapshot``. When the
    allocator path can't be resolved (e.g. running against an
    early vLLM minor version that doesn't expose ``block_allocator``
    at all), the snapshot reports ``num_used_blocks=-1`` and
    ``hint_path="no_known_path"`` so the caller can distinguish
    "no swap activity" from "could not read at all".

    ``bytes_per_block_estimate`` is plumbed through unchanged.
    Compute it from the engine's cache_config in the caller (see
    ``runner_vllm_streaming.py``); this function does not import
    vLLM and treats the value as opaque.
    """
    allocator, hint = _resolve_cpu_allocator(block_manager)
    block_size_tokens = _resolve_block_size_tokens(
        block_manager, fallback=block_size_fallback,
    )
    if allocator is None:
        return CpuSwapPoolSnapshot(
            num_used_blocks=-1,
            num_total_blocks=0,
            block_size_tokens=block_size_tokens,
            bytes_per_block_estimate=int(bytes_per_block_estimate),
            hint_path=hint,
        )
    used, total = _read_allocator_block_counts(allocator)
    return CpuSwapPoolSnapshot(
        num_used_blocks=used,
        num_total_blocks=total,
        block_size_tokens=block_size_tokens,
        bytes_per_block_estimate=int(bytes_per_block_estimate),
        hint_path=hint,
    )


# ---------------------------------------------------------------- #
# SwapInLatencyProbe — wraps swap-in operations to record per-event
# wall-time. Read-only behaviour: wraps delegate to the original
# callable verbatim.
# ---------------------------------------------------------------- #


@dataclass
class SwapInLatencyProbe:
    """Handle returned by ``install_swap_in_latency_probe``.

    With ``enabled=False`` (no-op path, e.g. when the allocator
    doesn't expose a swap-in entry point), ``latencies_ms`` stays
    empty and ``teardown()`` is a no-op.

    With ``enabled=True`` the install owns one or more LIFO
    teardown closures that revert the monkey-patches.

    Per-event latency is recorded in milliseconds. The probe is
    threadsafe with respect to a single AsyncEngineDriver — the
    streaming runner's run loop is single-event-loop async, so
    serial access is guaranteed. For parallel callers, wrap the
    list access in a lock at the call site.
    """

    enabled: bool
    hint_path: str
    wrap_target_name: str
    latencies_ms: List[float] = field(default_factory=list)
    _teardowns: List[Callable[[], None]] = field(default_factory=list)
    _torn_down: bool = False

    def record_ms(self, ms: float) -> None:
        """Test/manual entry point — records one synthetic
        latency. Production wraps call this from inside the
        monkey-patched ``swap_in`` callable."""
        if ms < 0.0:
            raise ValueError(
                f"swap-in latency must be >= 0; got {ms} ms"
            )
        if not self.enabled:
            # Even when not installed, recording is harmless and
            # makes unit tests cleaner. Treat as no-op.
            return
        self.latencies_ms.append(float(ms))

    def teardown(self) -> None:
        """Revert all monkey-patches in LIFO order. Idempotent."""
        if self._torn_down:
            return
        # LIFO revert — matches the cache_aware_install + extended
        # pinning teardown convention.
        while self._teardowns:
            fn = self._teardowns.pop()
            try:
                fn()
            except Exception as exc:
                logger.warning(
                    "swap_in_latency_probe teardown closure failed: %s",
                    exc,
                )
        self._torn_down = True

    # --------- aggregate helpers ---------

    def p50_ms(self) -> float:
        return _percentile_ms(self.latencies_ms, 0.50)

    def p99_ms(self) -> float:
        return _percentile_ms(self.latencies_ms, 0.99)

    def mean_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return sum(self.latencies_ms) / float(len(self.latencies_ms))

    def total_ms(self) -> float:
        return float(sum(self.latencies_ms))

    def stats(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "hint_path": self.hint_path,
            "wrap_target_name": self.wrap_target_name,
            "call_count": len(self.latencies_ms),
            "p50_ms": self.p50_ms(),
            "p99_ms": self.p99_ms(),
            "mean_ms": self.mean_ms(),
            "total_ms": self.total_ms(),
            "torn_down": self._torn_down,
        }


def _percentile_ms(samples: List[float], p: float) -> float:
    """Type-7 linear interpolation between sorted samples. Matches
    runner_vllm_streaming._compute_p50_p99_ms semantics so the
    streaming summary numbers stay consistent across modules.
    """
    if not samples:
        return 0.0
    s = sorted(samples)
    n = len(s)
    if n == 1:
        return s[0]
    rank = p * (n - 1)
    lo = int(rank)
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return s[lo] * (1 - frac) + s[hi] * frac


# Wrap target candidates, per vLLM API level. In vLLM 0.7.x the
# swap entry point lives at one of three layers depending on the
# block-manager version + scheduler config:
#
#  * V1 BlockSpaceManagerV1 has ``swap_in(seq_group)`` /
#    ``swap_out(seq_group)`` methods directly on the block_manager.
#  * V2 BlockSpaceManagerV2 delegates to the parent
#    ``CpuGpuBlockAllocator.swap(blocks, src_device, dst_device)``;
#    no per-device allocator has swap_in.
#  * Some legacy / patched builds expose swap_in on the per-device
#    CPU allocator directly — kept as the innermost fallback.
#
# The resolver walks in V1 → V2 → legacy-CPU order and returns the
# first level that exposes a callable. The probe wraps that
# callable with a ``time.perf_counter()`` delta. For the V2
# ``CpuGpuBlockAllocator.swap(blocks, src, dst)`` shape the timing
# is bi-directional (swap-out and swap-in share the same call); for
# the V1 shape it's strictly the named direction. The ``hint_path``
# string surfaces which level matched so operators can interpret
# the latency semantics correctly.
_SWAP_TARGET_LEVELS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    # Level 1: block_manager itself (V1 BlockSpaceManagerV1).
    ("block_manager", ("swap_in", "swap_in_blocks")),
    # Level 2: block_allocator (V2 CpuGpuBlockAllocator).
    ("block_allocator", ("swap", "swap_in")),
    # Level 3: cpu_allocator (per-device, legacy fallback).
    ("cpu_allocator", (
        "swap_in", "swap_in_blocks", "_swap_in", "swap_blocks_in",
    )),
)


# Legacy alias — preserved so external callers + the test suite
# that imports the constant by name keep working. Reflects the
# legacy cpu_allocator-level candidate list only.
_SWAP_IN_WRAP_CANDIDATES: Tuple[str, ...] = _SWAP_TARGET_LEVELS[2][1]


def _resolve_swap_target(
    block_manager: Any,
) -> Tuple[Any, Optional[str], str]:
    """Resolve the (target_object, attribute_name, hint_path) the
    swap-in latency probe should wrap.

    Walks block_manager → block_allocator → cpu_allocator. Returns
    the first level whose object exposes a callable matching one of
    the level's candidate attribute names. Returns
    ``(None, None, 'no_known_path')`` if no level matches — the
    caller surfaces this as an inert probe.

    The third element is a human-readable hint path that names both
    the level matched and the attribute selected.
    """
    for level_attr, candidates in _SWAP_TARGET_LEVELS:
        if level_attr == "block_manager":
            obj: Any = block_manager
        elif level_attr == "block_allocator":
            obj = getattr(block_manager, "block_allocator", None)
        elif level_attr == "cpu_allocator":
            obj, _ = _resolve_cpu_allocator(block_manager)
        else:
            obj = None
        if obj is None:
            continue
        for name in candidates:
            fn = getattr(obj, name, None)
            if callable(fn):
                return obj, name, f"{level_attr}.{name}"
    return None, None, "no_known_path"


def install_swap_in_latency_probe(
    block_manager: Any,
    *,
    enable: bool = True,
) -> SwapInLatencyProbe:
    """Install a timing wrap on the engine's swap-in callable.
    Returns a handle that records per-event latency in
    ``latencies_ms`` and supports LIFO teardown.

    Wrap target resolution (broadened in TIER5A.3 fixup): walks
    block_manager → block_allocator → cpu_allocator and selects the
    first callable that matches the per-level candidate set (see
    ``_SWAP_TARGET_LEVELS``). Matches vLLM 0.7.x's actual swap entry
    points across V1 (block_manager.swap_in) and V2
    (block_allocator.swap) shapes. The legacy cpu_allocator-level
    candidates remain as the innermost fallback.

    Behaviour:

    * ``enable=False`` returns an inert handle. Zero patching.
    * ``enable=True`` AND no level matches → inert handle with
      ``hint_path='no_known_path'``. The streaming runner surfaces
      this so an operator can see "we tried but vLLM didn't expose
      a swap entry point".
    * ``enable=True`` AND a callable found → wraps it with a
      ``time.perf_counter()`` delta; appends to ``latencies_ms``;
      restores on ``teardown()``.

    The wrap is **delegate-only**: it calls the original verbatim
    and returns its result. The orthogonality contract is preserved
    because we observe but never modify the swap operation.

    NB: for the V2 ``block_allocator.swap(blocks, src, dst)`` shape
    the latency captures the **bidirectional** swap op (both
    swap-in and swap-out fire the same callable). The ``hint_path``
    on the returned handle starts with ``block_allocator.`` for
    this case so callers can interpret the latency semantics.
    """
    if not enable:
        return SwapInLatencyProbe(
            enabled=False, hint_path="disabled",
            wrap_target_name="",
        )

    target_obj, target_name, hint = _resolve_swap_target(block_manager)
    if target_obj is None or target_name is None:
        return SwapInLatencyProbe(
            enabled=False, hint_path=hint,
            wrap_target_name="",
        )

    original_fn = getattr(target_obj, target_name)
    # The resolver already filtered for callable; re-checking is
    # defensive against a race that never realistically fires.
    if not callable(original_fn):
        return SwapInLatencyProbe(
            enabled=False, hint_path=hint + "/not_callable",
            wrap_target_name="",
        )

    # Local alias to keep the wrap/revert closures readable; matches
    # the prior layout that the test suite indexes against.
    allocator = target_obj

    handle = SwapInLatencyProbe(
        enabled=True, hint_path=hint,
        wrap_target_name=target_name,
    )

    # Bound-method wraps cleanly because we capture the original
    # callable directly. setattr on the instance shadows the
    # class-bound method without touching the class.
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        try:
            return original_fn(*args, **kwargs)
        finally:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            handle.latencies_ms.append(dt_ms)

    # Preserve a few metadata attrs so introspection still works.
    try:
        wrapped.__name__ = getattr(original_fn, "__name__", target_name)
    except (AttributeError, TypeError):
        pass

    try:
        setattr(allocator, target_name, wrapped)
    except (AttributeError, TypeError) as exc:
        # Allocator forbids attribute assignment (slot-based class
        # or read-only descriptor). Surface as disabled handle.
        logger.warning(
            "swap_in_latency_probe: cannot setattr %s on %s: %s",
            target_name, type(allocator).__name__, exc,
        )
        return SwapInLatencyProbe(
            enabled=False,
            hint_path=hint + "/setattr_failed",
            wrap_target_name="",
        )

    def revert() -> None:
        try:
            current = getattr(allocator, target_name, None)
            if current is wrapped:
                # Restore by deleting the instance-level override
                # so the class-bound method is visible again. If
                # that fails (e.g. the original wasn't a bound
                # method), explicitly setattr the captured callable.
                try:
                    delattr(allocator, target_name)
                    if getattr(allocator, target_name, None) is None:
                        setattr(allocator, target_name, original_fn)
                except (AttributeError, TypeError):
                    setattr(allocator, target_name, original_fn)
        except Exception as exc:
            logger.warning(
                "swap_in_latency_probe revert failed: %s", exc,
            )

    handle._teardowns.append(revert)
    return handle


# ---------------------------------------------------------------- #
# Cell-level peak tracker — composes with the periodic sampling
# pattern in runner_vllm_streaming.SwapCounterSampler.
# ---------------------------------------------------------------- #


@dataclass
class CpuSwapPoolPeakTracker:
    """Tracks the max-observed ``num_used_blocks`` across a cell's
    periodic samples. Mirrors the structural shape of
    SwapCounterSampler but for the CPU pool occupancy gauge
    (not a counter — gauge values don't accumulate, they peak).

    The streaming runner polls ``read_cpu_swap_pool`` on the same
    cadence as ``get_and_reset_swaps`` and feeds the snapshot here
    via :meth:`observe`.
    """

    peak_used_blocks: int = 0
    final_used_blocks: int = 0
    total_blocks: int = 0
    block_size_tokens: int = 0
    bytes_per_block_estimate: int = 0
    hint_path: str = ""
    n_samples: int = 0
    n_unreadable_samples: int = 0

    def observe(self, snapshot: CpuSwapPoolSnapshot) -> None:
        """Record one snapshot's gauge value. ``num_used_blocks=-1``
        (unreadable) increments ``n_unreadable_samples`` but does
        NOT affect the peak (a "?" reading is not evidence of
        zero use)."""
        self.n_samples += 1
        # Cache total / block_size / hint from the most recent
        # readable sample. Don't overwrite with stale info from
        # unreadable samples.
        if snapshot.num_total_blocks > 0:
            self.total_blocks = snapshot.num_total_blocks
        if snapshot.block_size_tokens > 0:
            self.block_size_tokens = snapshot.block_size_tokens
        if snapshot.bytes_per_block_estimate > 0:
            self.bytes_per_block_estimate = snapshot.bytes_per_block_estimate
        if snapshot.hint_path:
            self.hint_path = snapshot.hint_path

        if snapshot.num_used_blocks < 0:
            self.n_unreadable_samples += 1
            return
        self.final_used_blocks = int(snapshot.num_used_blocks)
        if self.final_used_blocks > self.peak_used_blocks:
            self.peak_used_blocks = self.final_used_blocks

    @property
    def peak_used_bytes_estimate(self) -> int:
        if self.bytes_per_block_estimate <= 0:
            return 0
        return int(self.peak_used_blocks) * int(self.bytes_per_block_estimate)

    @property
    def final_used_bytes_estimate(self) -> int:
        if self.bytes_per_block_estimate <= 0:
            return 0
        return int(self.final_used_blocks) * int(self.bytes_per_block_estimate)

    def stats(self) -> Dict[str, Any]:
        return {
            "peak_used_blocks": self.peak_used_blocks,
            "final_used_blocks": self.final_used_blocks,
            "total_blocks": self.total_blocks,
            "block_size_tokens": self.block_size_tokens,
            "bytes_per_block_estimate": self.bytes_per_block_estimate,
            "peak_used_bytes_estimate": self.peak_used_bytes_estimate,
            "final_used_bytes_estimate": self.final_used_bytes_estimate,
            "hint_path": self.hint_path,
            "n_samples": self.n_samples,
            "n_unreadable_samples": self.n_unreadable_samples,
        }
