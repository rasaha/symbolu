"""
Active-mode vLLM integration for PCAM (Phase 5).

Upgrades the shadow-mode helper at ``benchmarks/vllm_bridge.py`` with
an active-mode path that installs PCAM as the *live* eviction policy
inside a running vLLM engine. When installed, every call vLLM makes
to its free-block queue's ``popleft_n`` routes through
``KVCachePolicy.select_victims``, so PCAM decisions actually determine
which blocks get reused.

Shape (narrow, surgical)
------------------------
Feature-detects vLLM's v1 core architecture by attempting to import
``vllm.v1.core.block_pool.BlockPool`` and
``vllm.v1.core.kv_cache_utils.FreeKVCacheBlockQueue``. If either is
missing, fails clean via ``VLLMVersionSupportError`` with a clear
message about which module was not importable.

The install hook patches three methods on the live
``FreeKVCacheBlockQueue`` instance:

1. ``popleft_n(n)`` — instead of the default "pop n LRU-front blocks",
   this version walks all currently-free blocks, asks PCAM for its
   preferred victim order via ``select_victims(n)``, falls back to
   LRU order for any gap PCAM couldn't fill, and uses the existing
   ``FreeKVCacheBlockQueue.remove(block)`` to physically unlink each
   chosen block from the free list.

2. ``append(block)`` — notifies PCAM that a block has been freed
   (is now tracked / evictable) via ``KVCachePolicy.ensure_block``.

3. ``append_n(blocks)`` — batched version of the append hook.

The install also admits every currently-free block to PCAM at
install time so the policy can make informed decisions immediately,
not just once blocks start cycling through append/pop.

What this integration proves
----------------------------
When the harness runs against a real vLLM model on a real GPU, the
eviction order that reaches vLLM's block reuse path is PCAM's order,
not LRU's. This is "active-mode" in the strict sense: PCAM decisions
affect live serving behavior, not just shadow reporting.

What this integration does NOT solve
------------------------------------
- PCAM's scoring in active mode currently uses only the recency,
  frequency-sketch, and position signals — NOT real per-block
  attention mass. vLLM's v1 core block pool does not expose
  attention mass at the block level because the attention tensors
  are consumed inside the paged-attention kernel. For attention-rich
  scoring, the shadow-mode + ``pcam_trace_extract.py`` HuggingFace
  path remains the authoritative source of trained-attention data.

- The ``FreeKVCacheBlockQueue`` hook is O(num_free) per call (walks
  the full free list to ask PCAM). vLLM's default ``popleft_n`` is
  O(n). This is a known performance tradeoff for active mode, to be
  measured directly by ``benchmarks/pcam_vllm_perf.py``.

- Active-mode integration is fragile across vLLM releases. This
  bridge is tested against vLLM's current v1 core layout; older or
  newer architectures will fail at ``check_vllm_active_mode_supported``
  with a clean error. The supported window is deliberately narrow.

Not a bridge class
------------------
The task rules forbid a "CTM+ ↔ PCAM bridge class." This module is a
vLLM integration adapter, not a CTM+-to-PCAM bridge. PCAM's runtime
policy is still ``KVCachePolicy``, the vendored reference is still
the spec, and the parity harness is still the sync mechanism. The
rule about bridge classes is about keeping a single source of truth
between CTM+ and PCAM; it does not forbid vLLM-specific glue code.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional

# ---------------------------------------------------------------------------
# Repo root on sys.path for PCAM imports.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulator.pcam import PCAMConfig  # noqa: E402
from simulator.pcam.integrations.vllm import PCAMEvictor  # noqa: E402
from simulator.pcam.kv_policy import InferencePhase  # noqa: E402


__all__ = [
    "VLLMVersionSupportError",
    "check_vllm_active_mode_supported",
    "ActiveModeInstallation",
    "install_pcam_active_evictor",
    "uninstall_pcam_active_evictor",
]


# ---------------------------------------------------------------------------
# Error surface
# ---------------------------------------------------------------------------


class VLLMVersionSupportError(RuntimeError):
    """
    Raised when active-mode installation cannot proceed because the
    installed vLLM version does not expose the expected v1 core
    modules. The message always names the specific import that
    failed so the user knows which upstream component to look for.
    """


# ---------------------------------------------------------------------------
# Supported-version feature detection
# ---------------------------------------------------------------------------


def check_vllm_active_mode_supported() -> None:
    """
    Feature-detect whether the installed vLLM exposes the surface this
    bridge needs. Raises ``VLLMVersionSupportError`` with a specific
    missing-module hint on failure. Does not load any model or
    construct any engine — it's an import probe only.

    Supported window: vLLM versions that ship the "v1 core" block
    pool architecture. This was introduced around vLLM 0.7.x and is
    the default in 0.8.0+. Older releases that only have
    ``vllm.core.evictor`` or ``vllm.core.evictor_v2`` are NOT
    supported by this bridge.
    """
    try:
        import vllm  # noqa: F401
    except ImportError as exc:
        raise VLLMVersionSupportError(
            "vllm is not installed. Install with `pip install vllm` "
            "(requires a CUDA-capable GPU and a supported CUDA runtime)."
        ) from exc
    except Exception as exc:
        raise VLLMVersionSupportError(
            f"vllm is installed but failed to import: "
            f"{type(exc).__name__}: {exc}. This is usually a CUDA/library "
            "mismatch; run `python -c 'import vllm'` interactively to get "
            "the full traceback."
        ) from exc

    try:
        from vllm.v1.core.block_pool import BlockPool  # noqa: F401
    except ImportError as exc:
        raise VLLMVersionSupportError(
            "This vLLM release does not expose vllm.v1.core.block_pool. "
            "Active-mode integration requires the v1 core architecture "
            "(vLLM 0.7.0+ / the default in 0.8.0+). For older releases "
            "with vllm.core.evictor[_v2], use the Phase 4 shadow-mode "
            f"path instead. Root cause: {exc}"
        ) from exc

    try:
        from vllm.v1.core.kv_cache_utils import (  # noqa: F401
            FreeKVCacheBlockQueue,
            KVCacheBlock,
        )
    except ImportError as exc:
        raise VLLMVersionSupportError(
            "vllm.v1.core.kv_cache_utils does not expose "
            "FreeKVCacheBlockQueue / KVCacheBlock. The v1 core "
            "architecture has changed since this bridge was written. "
            f"Root cause: {exc}"
        ) from exc

    # Method-surface probe: verify every method we patch exists, so a
    # silent refactor upstream turns into a clean failure at install
    # time rather than a confusing AttributeError later.
    _required_queue_methods = ("popleft_n", "append", "append_n", "remove",
                               "get_all_free_blocks")
    missing = [
        m for m in _required_queue_methods
        if not hasattr(FreeKVCacheBlockQueue, m)
    ]
    if missing:
        raise VLLMVersionSupportError(
            f"FreeKVCacheBlockQueue is missing methods required by the "
            f"PCAM active-mode bridge: {missing}. The v1 core API has "
            "evolved; the bridge needs to be updated."
        )


# ---------------------------------------------------------------------------
# Installation record (for clean uninstall)
# ---------------------------------------------------------------------------


@dataclass
class ActiveModeInstallation:
    """
    Handle returned by ``install_pcam_active_evictor``. Holds enough
    state to undo the monkey-patch in ``uninstall_pcam_active_evictor``.

    ``had_*_before`` flags record whether each method was an instance
    attribute on the queue before install. Uninstall uses them to
    decide between ``del`` (restoring class-method lookup) and
    ``setattr`` (restoring a pre-existing instance override).
    """

    policy: Any
    evictor: PCAMEvictor
    free_block_queue: Any
    prior_popleft_n: Any  # the instance attribute if one existed, else None
    prior_append: Any
    prior_append_n: Any
    had_popleft_n_before: bool
    had_append_before: bool
    had_append_n_before: bool
    sequence_id: int = 0
    installed: bool = True
    stats: dict = field(default_factory=lambda: {
        "popleft_n_calls": 0,
        "blocks_evicted": 0,
        "pcam_chosen_blocks": 0,
        "lru_fallback_blocks": 0,
        "append_events": 0,
    })


# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------


def install_pcam_active_evictor(
    block_pool: Any,
    config: Optional[PCAMConfig] = None,
    *,
    policy: Optional[Any] = None,
    sequence_id: int = 0,
) -> ActiveModeInstallation:
    """
    Install PCAM as the live eviction policy inside ``block_pool``.

    Arguments
    ---------
    block_pool : vllm.v1.core.block_pool.BlockPool
        A BlockPool instance reached via e.g.
        ``llm.llm_engine.kv_cache_manager.block_pool`` (the exact
        attribute chain depends on the vLLM entry point; the caller
        is responsible for locating the BlockPool and passing it in).
    config : PCAMConfig, optional
        Config used to build a fresh ``KVCachePolicy`` if ``policy``
        is not provided. Defaults to ``PCAMConfig(max_blocks=4096)``.
    policy : KVCachePolicy, optional
        An existing policy to use. Mutually exclusive with ``config``.
    sequence_id : int
        Synthetic sequence id used when admitting blocks to PCAM.
        Active mode operates at the physical-block level and does
        not carry per-sequence metadata; all blocks are admitted
        under a single synthetic sequence.

    Returns
    -------
    ActiveModeInstallation
        Handle that the caller should pass to
        ``uninstall_pcam_active_evictor`` at the end of the run.

    Raises
    ------
    VLLMVersionSupportError
        If vLLM is not installed or does not expose the v1 core API.
    """
    check_vllm_active_mode_supported()

    if policy is None:
        if config is None:
            config = PCAMConfig(max_blocks=4096)
        policy = config.build_policy()
    evictor = PCAMEvictor(policy)
    policy.register_sequence(sequence_id)
    policy.set_phase(sequence_id, InferencePhase.DECODE)

    queue = block_pool.free_block_queue

    # Snapshot any pre-existing instance overrides so uninstall can
    # restore the exact prior state. For the common case where the
    # methods were only defined on the class, these flags are False
    # and uninstall will ``del`` the instance attributes the bridge
    # set, which restores the class-method lookup cleanly.
    queue_dict = queue.__dict__
    had_popleft_n_before = "popleft_n" in queue_dict
    had_append_before = "append" in queue_dict
    had_append_n_before = "append_n" in queue_dict
    prior_popleft_n = queue_dict.get("popleft_n")
    prior_append = queue_dict.get("append")
    prior_append_n = queue_dict.get("append_n")

    # Initial admission: every block currently in the free queue is
    # fair game for PCAM scoring. Walk the list once and admit each.
    for block in queue.get_all_free_blocks():
        policy.ensure_block(
            block_id=int(block.block_id),
            sequence_id=sequence_id,
            positions=[int(block.block_id)],
        )

    installation = ActiveModeInstallation(
        policy=policy,
        evictor=evictor,
        free_block_queue=queue,
        prior_popleft_n=prior_popleft_n,
        prior_append=prior_append,
        prior_append_n=prior_append_n,
        had_popleft_n_before=had_popleft_n_before,
        had_append_before=had_append_before,
        had_append_n_before=had_append_n_before,
        sequence_id=sequence_id,
    )

    # Build the replacement closures. They capture `installation` for
    # stats bookkeeping and `policy` for direct calls.

    def _pcam_popleft_n(n: int) -> list:
        """
        Active-mode replacement for FreeKVCacheBlockQueue.popleft_n.

        Walks every currently-free block, asks PCAM for up to n
        preferred victims, falls back to LRU order for any gap, and
        physically removes each chosen block from the linked list
        via the queue's own remove() method.
        """
        if n == 0:
            return []
        if queue.num_free_blocks < n:
            # Not enough free blocks — defer to whatever the original
            # popleft_n would do (usually raise ValueError). Retrieve
            # the original from the class if we didn't shadow a prior
            # instance override.
            if had_popleft_n_before:
                return prior_popleft_n(n)
            return type(queue).popleft_n(queue, n)

        installation.stats["popleft_n_calls"] += 1

        # get_all_free_blocks returns LRU order (head = least recent).
        free_blocks = queue.get_all_free_blocks()
        if not free_blocks:
            return []
        free_by_id = {int(b.block_id): b for b in free_blocks}

        # Ask PCAM for victims. select_victims may return fewer than n
        # if not enough blocks are tracked yet.
        try:
            pcam_chosen_ids = policy.select_victims(n)
        except Exception:
            # Any PCAM failure triggers clean LRU fallback; active
            # mode must never break vLLM.
            pcam_chosen_ids = []

        chosen: list = []
        for bid in pcam_chosen_ids:
            bid_int = int(bid)
            if bid_int in free_by_id and len(chosen) < n:
                chosen.append(free_by_id.pop(bid_int))
                installation.stats["pcam_chosen_blocks"] += 1

        # Fill any remaining slots in LRU order.
        for block in free_blocks:
            if len(chosen) >= n:
                break
            bid_int = int(block.block_id)
            if bid_int in free_by_id:
                chosen.append(block)
                del free_by_id[bid_int]
                installation.stats["lru_fallback_blocks"] += 1

        # Physically unlink each chosen block. remove() is the safe
        # queue-level operation; it updates num_free_blocks.
        for block in chosen:
            queue.remove(block)
            # Reset linked-list pointers the way the original popleft_n
            # does, so downstream vLLM code doesn't trip on stale refs.
            block.prev_free_block = None
            block.next_free_block = None

        installation.stats["blocks_evicted"] += len(chosen)
        return chosen

    def _call_original_append(block) -> None:
        if had_append_before:
            prior_append(block)
        else:
            type(queue).append(queue, block)

    def _call_original_append_n(blocks) -> None:
        if had_append_n_before:
            prior_append_n(blocks)
        else:
            type(queue).append_n(queue, blocks)

    def _pcam_append(block) -> None:
        """Track newly-freed blocks in PCAM before handing off to the real append."""
        _call_original_append(block)
        installation.stats["append_events"] += 1
        try:
            policy.ensure_block(
                block_id=int(block.block_id),
                sequence_id=sequence_id,
                positions=[int(block.block_id)],
            )
        except Exception:
            # Tracking failures must not break vLLM. Active mode is
            # a best-effort overlay on the LRU queue.
            pass

    def _pcam_append_n(blocks) -> None:
        _call_original_append_n(blocks)
        for block in blocks:
            installation.stats["append_events"] += 1
            try:
                policy.ensure_block(
                    block_id=int(block.block_id),
                    sequence_id=sequence_id,
                    positions=[int(block.block_id)],
                )
            except Exception:
                pass

    # Attribute swap. We assign to the instance, not the class, so
    # uninstall is a clean restore and other BlockPool instances in
    # the same process are unaffected.
    queue.popleft_n = _pcam_popleft_n  # type: ignore[assignment]
    queue.append = _pcam_append  # type: ignore[assignment]
    queue.append_n = _pcam_append_n  # type: ignore[assignment]

    return installation


def uninstall_pcam_active_evictor(installation: ActiveModeInstallation) -> None:
    """
    Restore the original FreeKVCacheBlockQueue methods. Safe to call
    more than once; subsequent calls are no-ops.

    For each of the three patched methods:
      - If the queue had an instance-level override BEFORE install,
        restore that exact override.
      - Otherwise, ``del`` the instance attribute the bridge set so
        the class-method lookup resolves normally again.
    """
    if not installation.installed:
        return
    queue = installation.free_block_queue

    def _restore(name: str, had_before: bool, prior: Any) -> None:
        if had_before:
            setattr(queue, name, prior)
        else:
            # Remove the instance attribute the bridge set; fall back
            # to the class method.
            try:
                delattr(queue, name)
            except AttributeError:
                pass

    _restore("popleft_n", installation.had_popleft_n_before,
             installation.prior_popleft_n)
    _restore("append", installation.had_append_before,
             installation.prior_append)
    _restore("append_n", installation.had_append_n_before,
             installation.prior_append_n)
    installation.installed = False
