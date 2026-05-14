"""
vLLM Evictor shim: connects CTMBlockSpaceManager to vLLM's eviction interface.

This module bridges the gap between vLLM's internal block management and
CTM+ eviction scoring. It works by:

1. Subclassing vLLM's Evictor ABC → receives evict() calls from
   BlockSpaceManagerV1 when GPU blocks run out.
2. Wrapping vLLM's BlockAllocator → intercepts allocate/free to keep
   CTMBlockSpaceManager in sync.
3. Hooking into the model runner → captures block-level attention sums
   after each decode step.

Targets: vLLM >= 0.4.0 (BlockSpaceManagerV1 + Evictor interface).
Tested with: Mistral-7B-Instruct-v0.2 on A100.

Usage:
    # Option A: monkey-patch an existing vLLM engine
    from CTM_plus.KVPolicy.kv_policy.vllm_evictor import patch_vllm_engine
    engine = LLMEngine.from_engine_args(args)
    patch_vllm_engine(engine, enable_logging=True)

    # Option B: use the evictor directly in a custom block manager
    from CTM_plus.KVPolicy.kv_policy.vllm_evictor import CTMEvictor
    evictor = CTMEvictor(num_blocks=2000, block_size=16)

    # Option C: run the comparison harness (no GPU required for dry-run)
    python -m CTM_plus.KVPolicy.kv_policy.vllm_evictor --compare

Requires: pip install vllm (for Options A/B with real models)
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .vllm_adapter import CTMBlockSpaceManager, CTMvLLMConfig

logger = logging.getLogger("ctm_plus.vllm_evictor")


# Cython-compiled drop-in for ``CTMEvictorModern``. See
# ``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §11–§12 for the engineering
# motivation. When the compiled extension is not present (fresh
# checkout with no C toolchain, or the package was installed without
# the ``ext`` extra), fall back to aliasing the pure-Python class so
# downstream imports of ``CTMEvictorModernC`` still resolve and the
# behavioural contract is preserved at the cost of the integration
# tax this port exists to remove. The parametrized protocol fixture
# (`Bench/tests/test_vllm_protocol_fixture.py`) skips its C-variant
# leg in that case.
try:
    from ._ctm_evictor import CTMEvictorModernC  # noqa: F401
    _CYTHON_EVICTOR_AVAILABLE = True
except ImportError:
    _CYTHON_EVICTOR_AVAILABLE = False


# =============================================================================
# Evictor shim (vLLM interface)
# =============================================================================

class CTMEvictor:
    """
    vLLM-compatible evictor backed by CTM+ KVCachePolicy.

    Implements the interface expected by vLLM's BlockSpaceManagerV1:
        evict() -> Tuple[mapping, mapping]   (gpu_evicted, cpu_evicted)
        add(block_id)                        (block admitted)
        remove(block_id)                     (block freed)
        update(block_id, last_accessed)      (access recorded)
        num_blocks -> int                    (evictable count)

    The actual vLLM Evictor ABC uses PhysicalTokenBlock objects. This shim
    works with both raw block IDs (for testing) and PhysicalTokenBlock
    objects (for live vLLM integration).
    """

    def __init__(
        self,
        num_blocks: int = 1000,
        block_size: int = 16,
        ctm_config: Optional[CTMvLLMConfig] = None,
        enable_logging: bool = False,
    ):
        self._manager = CTMBlockSpaceManager(
            block_size=block_size,
            num_gpu_blocks=num_blocks,
            num_cpu_blocks=0,
            watermark=0.0,
            ctm_config=ctm_config,
            enable_logging=enable_logging,
        )
        self._block_size = block_size
        self._active_blocks: Dict[int, Any] = {}  # block_id → PhysicalTokenBlock or None
        self._seq_for_block: Dict[int, int] = {}  # block_id → seq_id
        self._default_seq_id = 0

    # ---- vLLM Evictor interface ----

    def evict(self) -> Tuple[Dict[int, Any], Dict[int, Any]]:
        """
        Evict one block. Returns (gpu_evicted, cpu_evicted) mappings.

        vLLM expects: {block_id: PhysicalTokenBlock} for each device.
        We only evict from GPU.
        """
        page_id = self._manager.evict()
        if page_id is None:
            return {}, {}

        block_obj = self._active_blocks.pop(page_id, None)
        self._seq_for_block.pop(page_id, None)

        # vLLM expects {block_hash: PhysicalTokenBlock}
        # We use block_id as hash since we don't have content hashing
        gpu_evicted = {page_id: block_obj}
        return gpu_evicted, {}

    def add(self, block_id: int, block_obj: Any = None,
            seq_id: int = 0, positions: Optional[List[int]] = None) -> None:
        """Register a newly allocated block."""
        if positions is None:
            positions = list(range(self._block_size))
        self._active_blocks[block_id] = block_obj
        self._seq_for_block[block_id] = seq_id

        # Register sequence if first block
        if seq_id not in self._manager._seq_pages:
            self._manager.register_sequence(seq_id)

        self._manager.allocate_block(
            seq_id=seq_id, page_id=block_id, positions=positions,
        )

    def remove(self, block_id: int) -> None:
        """Block freed (not evicted — e.g. sequence completed)."""
        self._active_blocks.pop(block_id, None)
        seq_id = self._seq_for_block.pop(block_id, None)
        # Let manager handle cleanup via complete_sequence or direct unmap
        block_internal = self._manager._page_to_block.get(block_id)
        if block_internal is not None:
            self._manager._policy.evict_block(block_internal)
            self._manager._gpu_pages.discard(block_id)
            self._manager._unmap_page(block_id)

    def update(self, block_id: int, last_accessed: float = 0.0,
               attention_sum: float = 0.0, seq_len: int = 0) -> None:
        """
        Record an access to a block.

        In live vLLM integration, call this with the block-level attention
        sum from the attention output. The last_accessed timestamp is
        accepted for API compatibility but not used (policy tracks its
        own step counter).
        """
        seq_id = self._seq_for_block.get(block_id, self._default_seq_id)
        self._manager.on_attention(
            page_id=block_id,
            attention_sum=attention_sum,
            seq_id=seq_id,
            seq_len=seq_len,
        )

    @property
    def num_blocks(self) -> int:
        """Number of evictable (non-pinned) blocks."""
        return len(self._active_blocks) - len(self._manager._pinned_pages)

    # ---- Sequence lifecycle ----

    def register_sequence(self, seq_id: int) -> None:
        self._manager.register_sequence(seq_id)

    def on_decode_start(self, seq_id: int) -> None:
        self._manager.on_decode_start(seq_id)

    def complete_sequence(self, seq_id: int) -> List[int]:
        freed = self._manager.complete_sequence(seq_id)
        for page_id in freed:
            self._active_blocks.pop(page_id, None)
            self._seq_for_block.pop(page_id, None)
        return freed

    # ---- Stats ----

    def get_stats(self) -> Dict:
        return self._manager.get_stats()


# =============================================================================
# vLLM engine monkey-patch
# =============================================================================

def patch_vllm_engine(engine: Any, enable_logging: bool = False) -> CTMEvictor:
    """
    Monkey-patch a running vLLM LLMEngine to use CTM+ eviction.

    Replaces the evictor inside the engine's block manager with a CTMEvictor.
    The original block allocator and scheduler are untouched.

    **vLLM API compatibility:**

    * vLLM ≤ 0.6.x (``BlockSpaceManagerV1``): block_manager.gpu_allocator
      exposes a public ``evictor`` attribute the patch can swap. Supported.
    * vLLM ≥ 0.7.0 (``SelfAttnBlockSpaceManager`` + ``CpuGpuBlockAllocator``):
      no public evictor hook exists; the patch raises ``NotImplementedError``
      with a clear message. The CTM+ vLLM integration needs a rewrite to
      target the new architecture (filed as known limitation in
      Bench/scripts/MODE_B_RUNBOOK.md).

    Args:
        engine: A vllm.LLMEngine instance.
        enable_logging: Enable CTM+ structured event logging.

    Returns:
        The CTMEvictor instance (for inspection/stats).
    """
    try:
        scheduler = engine.scheduler[0] if isinstance(engine.scheduler, list) else engine.scheduler
        block_manager = scheduler.block_manager
    except (AttributeError, IndexError) as e:
        raise RuntimeError(
            f"Cannot access block manager from engine. "
            f"Ensure vLLM is installed. Error: {e}"
        )

    # Any vLLM ≥ 0.5.x uses SelfAttnBlockSpaceManager + a
    # CpuGpuBlockAllocator that does NOT expose a replaceable
    # evictor. The original patch was written for vLLM ≤ 0.4.x
    # (BlockSpaceManagerV1 with gpu_allocator.evictor); the
    # docstring's "Targets: vLLM >= 0.4.0" claim is wrong for
    # any version released after mid-2024. Detect the modern
    # block-manager + fail loud.
    if hasattr(block_manager, 'block_allocator') and not hasattr(
        block_manager, 'gpu_allocator'
    ):
        raise NotImplementedError(
            "CTM+ vLLM integration is broken for vLLM >= 0.5.x "
            "(any release after mid-2024). The original patch was "
            "written for the BlockSpaceManagerV1 evictor-swap pattern "
            "in vLLM <= 0.4.x; vLLM 0.5+ uses SelfAttnBlockSpaceManager "
            "+ CpuGpuBlockAllocator which has no public eviction-policy "
            "hook (the _allocators dict is private).\n\n"
            "Practical paths forward:\n"
            "  1. Validate LRU only on the current vLLM version. The\n"
            "     swap-counter API works (see Bench/ctm_bench/\n"
            "     runner_vllm.py::_extract_vllm_tier_counters). Real-\n"
            "     model LRU numbers can be cross-checked against\n"
            "     Mode A's LRU predictions to validate the simulator's\n"
            "     tier model. Mode A's CTM+ predictions then carry by\n"
            "     extension since the policy math is deterministic.\n"
            "  2. Pin vLLM to 0.4.x (e.g. vllm==0.4.3) to test the\n"
            "     legacy patch path. vLLM 0.4.x targets CUDA 12.1 +\n"
            "     older PyTorch; many newer models (Qwen2.5, Llama-3.1)\n"
            "     may not be supported.\n"
            "  3. Rewrite the CTM+ integration against the modern\n"
            "     CpuGpuBlockAllocator architecture. Estimated 2-3 days\n"
            "     of vLLM-internals work; see MODE_B_RUNBOOK.md §8.\n"
            f"\nDetected block_manager type: {type(block_manager).__name__}\n"
            f"Detected vLLM version: see vllm.__version__ (this patch "
            f"only worked with vLLM <= 0.4.x)"
        )

    # vLLM ≤ 0.6.x path. Initialise gpu_allocator to None defensively so
    # an AttributeError in the read below (which used to leave the
    # variable unbound and crash with UnboundLocalError later) now fails
    # loud with a clear message.
    gpu_allocator = None
    try:
        gpu_allocator = block_manager.gpu_allocator
        num_blocks = gpu_allocator.num_blocks
        block_size = block_manager.block_size
    except AttributeError as e:
        raise RuntimeError(
            f"Cannot read GPU allocator config from BlockSpaceManagerV1. "
            f"This is unexpected on vLLM <= 0.6.x — please file an issue "
            f"with your vLLM version. Error: {e}"
        )

    evictor = CTMEvictor(
        num_blocks=num_blocks,
        block_size=block_size,
        enable_logging=enable_logging,
    )

    # Replace the evictor on the GPU allocator
    if hasattr(gpu_allocator, 'evictor'):
        gpu_allocator.evictor = evictor
        logger.info(
            "CTM+ evictor installed: %d GPU blocks, block_size=%d",
            num_blocks, block_size,
        )
    else:
        logger.warning(
            "gpu_allocator has no 'evictor' attribute. "
            "vLLM version may use a different eviction path. "
            "CTMEvictor created but not auto-installed."
        )

    return evictor


# =============================================================================
# Standalone comparison harness (no GPU required)
# =============================================================================

@dataclass
class HarnessResult:
    """Results from one run of the comparison harness."""
    policy: str
    total_evictions: int
    important_evictions: int
    filler_evictions: int
    recompute_events: int
    final_utilization: float
    elapsed_seconds: float
    eviction_log: List[Dict]


def _run_harness_single(
    policy: str,
    num_blocks: int,
    block_size: int,
    num_sequences: int,
    context_length: int,
    decode_steps: int,
    seed: int,
) -> HarnessResult:
    """Run one policy through the simulator-level comparison."""
    from CTM_plus.KVSimulator.kv_simulator.buffer_pool import (
        KVCacheSimulator, PolicyType,
    )
    from CTM_plus.KVPolicy.kv_policy.attention_evictor import KVCachePolicy

    policy_map = {
        "lru": PolicyType.LRU,
        "ctm_plus": PolicyType.KV_POLICY,
    }
    policy_type = policy_map[policy]

    kv_pol = None
    if policy_type == PolicyType.KV_POLICY:
        kv_pol = KVCachePolicy(
            max_blocks=num_blocks, block_size=block_size,
        )

    sim = KVCacheSimulator(
        max_blocks=num_blocks, block_size=block_size,
        policy_type=policy_type, seed=seed, kv_policy=kv_pol,
    )

    t0 = time.perf_counter()

    for i in range(num_sequences):
        sim.add_sequence(i, context_length)
        sim.prefill_sequence(i)

    for step in range(decode_steps):
        for i in range(num_sequences):
            if i in sim.sequences:
                sim.decode_step(i)

    elapsed = time.perf_counter() - t0
    metrics = sim.get_metrics()

    return HarnessResult(
        policy=policy,
        total_evictions=metrics["blocks_evicted"],
        important_evictions=metrics["important_evictions"],
        filler_evictions=metrics["blocks_evicted"] - metrics["important_evictions"],
        recompute_events=metrics["recompute_cost"] // block_size,
        final_utilization=metrics["utilization"],
        elapsed_seconds=elapsed,
        eviction_log=[],
    )


def run_comparison(
    num_blocks: int = 256,
    block_size: int = 16,
    num_sequences: int = 4,
    context_length: int = 8192,
    decode_steps: int = 128,
    seed: int = 42,
) -> Dict[str, HarnessResult]:
    """
    Run LRU vs CTM+ comparison.

    This uses the simulator (no GPU needed) but with realistic parameters
    matching what Mistral-7B would produce:
      - 8K context (Mistral's native window)
      - 256 blocks (simulates constrained GPU memory)
      - 4 concurrent sequences (typical serving batch)
    """
    results = {}
    for policy in ("lru", "ctm_plus"):
        results[policy] = _run_harness_single(
            policy=policy,
            num_blocks=num_blocks,
            block_size=block_size,
            num_sequences=num_sequences,
            context_length=context_length,
            decode_steps=decode_steps,
            seed=seed,
        )
    return results


def print_comparison(results: Dict[str, HarnessResult]) -> None:
    """Pretty-print comparison results."""
    print()
    print("=" * 72)
    print("  CTM+ vs LRU Eviction Comparison")
    print("=" * 72)
    print(f"  {'Metric':<30} {'LRU':>15} {'CTM+':>15}")
    print("-" * 72)

    lru = results["lru"]
    ctm = results["ctm_plus"]

    rows = [
        ("Total evictions", lru.total_evictions, ctm.total_evictions),
        ("Important evictions", lru.important_evictions, ctm.important_evictions),
        ("Filler evictions", lru.filler_evictions, ctm.filler_evictions),
        ("Recompute events", lru.recompute_events, ctm.recompute_events),
        ("Final utilization", f"{lru.final_utilization:.1%}", f"{ctm.final_utilization:.1%}"),
        ("Elapsed (seconds)", f"{lru.elapsed_seconds:.3f}", f"{ctm.elapsed_seconds:.3f}"),
    ]

    for label, lru_val, ctm_val in rows:
        print(f"  {label:<30} {str(lru_val):>15} {str(ctm_val):>15}")

    print("-" * 72)

    # Delta summary
    if lru.recompute_events > 0:
        recomp_delta = (ctm.recompute_events - lru.recompute_events) / lru.recompute_events * 100
        print(f"  Recompute delta: {recomp_delta:+.1f}% ({'worse' if recomp_delta > 0 else 'better'})")
    if lru.important_evictions > 0:
        imp_delta = (ctm.important_evictions - lru.important_evictions) / max(1, lru.important_evictions) * 100
        print(f"  Important eviction delta: {imp_delta:+.1f}%")
    print("=" * 72)
    print()


# =============================================================================
# vLLM live test (requires GPU + vLLM + model)
# =============================================================================

def run_live_test(
    model: str = "mistralai/Mistral-7B-Instruct-v0.2",
    prompt_length: int = 4096,
    max_tokens: int = 128,
    num_prompts: int = 4,
    gpu_memory_utilization: float = 0.6,
    enable_logging: bool = True,
) -> Optional[Dict]:
    """
    Run a live test with a real model through vLLM.

    Requires: GPU, vLLM installed, model weights accessible.

    This function:
    1. Starts a vLLM engine with the specified model
    2. Patches in CTM+ eviction
    3. Sends long prompts to force cache pressure
    4. Collects eviction/recompute/attention metrics
    5. Returns structured results

    Args:
        model: HuggingFace model ID or local path.
        prompt_length: Approximate input token count per prompt.
        max_tokens: Tokens to generate per prompt.
        num_prompts: Number of concurrent prompts.
        gpu_memory_utilization: Fraction of GPU memory for KV cache.
        enable_logging: Enable CTM+ event logging.

    Returns:
        Dict with metrics, or None if vLLM is not available.
    """
    try:
        from vllm import LLM, SamplingParams
    except ImportError:
        print("vLLM not installed. Install with: pip install vllm")
        print("Falling back to simulator comparison.")
        return None

    print(f"Loading {model}...")
    print(f"  gpu_memory_utilization={gpu_memory_utilization}")
    print(f"  prompt_length≈{prompt_length}, max_tokens={max_tokens}")
    print(f"  num_prompts={num_prompts}")

    llm = LLM(
        model=model,
        gpu_memory_utilization=gpu_memory_utilization,
        max_model_len=prompt_length + max_tokens + 128,
        enforce_eager=True,  # avoid CUDA graph overhead for testing
    )

    # Patch in CTM+ eviction
    evictor = patch_vllm_engine(llm.llm_engine, enable_logging=enable_logging)

    # Build long prompts (repeating text to reach target length)
    base_text = (
        "The following is a detailed technical document about transformer "
        "architectures, attention mechanisms, and KV cache management in "
        "large language models. " * 50
    )
    # Approximate: 1 token ≈ 4 chars for English text
    prompt_text = base_text * max(1, prompt_length // (len(base_text) // 4))
    prompts = [prompt_text] * num_prompts

    sampling_params = SamplingParams(
        temperature=0.7,
        max_tokens=max_tokens,
    )

    print(f"\nRunning {num_prompts} prompts...")
    t0 = time.perf_counter()
    outputs = llm.generate(prompts, sampling_params)
    elapsed = time.perf_counter() - t0

    stats = evictor.get_stats()
    stats["elapsed_seconds"] = round(elapsed, 3)
    stats["model"] = model
    stats["num_prompts"] = num_prompts
    stats["prompt_length"] = prompt_length
    stats["max_tokens"] = max_tokens

    print(f"\nCompleted in {elapsed:.2f}s")
    print(f"  Evictions: {stats.get('evictions', 0)}")
    print(f"  Filler evictions: {stats.get('filler_evictions', 0)}")
    print(f"  GPU utilization: {stats.get('gpu_utilization', 0):.1%}")
    print(f"  Recompute total: {stats.get('recompute_total', 0)}")
    print(f"  Event counts: {stats.get('event_counts', {})}")

    # Print sample outputs
    for i, output in enumerate(outputs[:2]):
        text = output.outputs[0].text[:200]
        print(f"\n  Prompt {i} output (first 200 chars): {text!r}")

    return stats


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="CTM+ vLLM eviction comparison",
    )
    parser.add_argument(
        "--compare", action="store_true",
        help="Run simulator-level LRU vs CTM+ comparison (no GPU needed)",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Run live test with real model (requires GPU + vLLM)",
    )
    parser.add_argument(
        "--model", default="mistralai/Mistral-7B-Instruct-v0.2",
        help="Model for live test",
    )
    parser.add_argument(
        "--context", type=int, default=8192,
        help="Context length for comparison / prompt length for live test",
    )
    parser.add_argument(
        "--sequences", type=int, default=4,
        help="Number of sequences/prompts",
    )
    parser.add_argument(
        "--decode-steps", type=int, default=128,
        help="Decode steps per sequence (comparison mode)",
    )
    parser.add_argument(
        "--blocks", type=int, default=256,
        help="Number of GPU blocks (comparison mode)",
    )
    parser.add_argument(
        "--gpu-util", type=float, default=0.6,
        help="GPU memory utilization (live mode)",
    )
    args = parser.parse_args()

    if args.live:
        result = run_live_test(
            model=args.model,
            prompt_length=args.context,
            num_prompts=args.sequences,
            gpu_memory_utilization=args.gpu_util,
        )
        if result is None:
            print("\nFalling back to simulator comparison...")
            args.compare = True

    if args.compare or (not args.live):
        results = run_comparison(
            num_blocks=args.blocks,
            context_length=args.context,
            num_sequences=args.sequences,
            decode_steps=args.decode_steps,
        )
        print_comparison(results)


if __name__ == "__main__":
    main()


# =============================================================================
# Phase 2 — modern vLLM (0.5+) integration
# =============================================================================
#
# The legacy `patch_vllm_engine` above targets vLLM ≤ 0.4.x's
# BlockSpaceManagerV1.gpu_allocator.evictor (verified end-to-end on
# RunPod, May 2026, commit 6081148: `LRUEvictor` -> `CTMEvictor`).
#
# Modern vLLM (0.5+) replaced that with SelfAttnBlockSpaceManager +
# CpuGpuBlockAllocator, which is itself a wrapper around per-device
# allocators. The eviction-policy hook moved one layer deeper:
#
#   block_manager.block_allocator                       (CpuGpuBlockAllocator)
#       ._allocators[Device.GPU]                        (PrefixCachingBlockAllocator
#                                                        OR NaiveBlockAllocator)
#           .evictor                                    (LRUEvictor —
#                                                        only on PrefixCachingBlockAllocator)
#
# Two requirements for Phase 2 to install cleanly on 0.5+:
#
# 1. ``enable_prefix_caching=True`` must be set on engine init —
#    otherwise the GPU allocator is NaiveBlockAllocator, which has
#    no evictor at all (manages a free list directly). NaiveBlockAllocator
#    -> patch silently no-ops, same failure mode as vLLM 0.4.
#
# 2. We replace ``allocator.evictor`` with a CTMEvictorModern that
#    implements vLLM 0.7's Evictor ABC:
#
#       __contains__(block_id) -> bool
#       evict() -> Tuple[int, int]                # (block_id, content_hash)
#       add(block_id, content_hash, num_hashed_tokens, last_accessed)
#       update(block_id, last_accessed)
#       remove(block_id)
#       num_blocks (property) -> int
#
# The interface differs from vLLM 0.4's `(gpu_dict, cpu_dict)`-returning
# evictor (the legacy CTMEvictor above). The two are kept side-by-side
# rather than unified — the version-detection in patch_vllm_engine
# decides which to install.
#
# Operational note: with prefix caching on, the evictor decides which
# *cached-but-unreferenced* blocks to release first when the cache fills,
# NOT which active blocks to swap to CPU under preemption. That's a
# different operational question than Mode A's tier-cost simulator
# models (which is about under-pressure swap). The Phase 2 evidence is
# valid for "is CTM+ scoring useful for cache-retention decisions" —
# not for "does CTM+ change swap behaviour." Honest scope.


class CTMEvictorModern:
    """vLLM 0.7+ Evictor ABC implementation backed by CTM+ scoring.

    Implements the interface vLLM's PrefixCachingBlockAllocator expects
    on its ``evictor`` slot. The class wraps a
    :class:`kv_policy.attention_evictor.KVCachePolicy` and adapts:

    * ``add(block_id, content_hash, num_hashed_tokens, last_accessed)``
      → ``policy.ensure_block(block_id, sequence_id=0, positions=[])``
    * ``update(block_id, last_accessed)``
      → ``policy.on_block_attention(block_id, attention_sum=0.0, ...)``
      (note: attention_sum=0 because vLLM doesn't forward attention
      through the evictor; this is option (b) from the design doc —
      score on position + recency + frequency only)
    * ``evict()``
      → ``policy.select_victims(count=1)`` and returns
      ``(block_id, content_hash)`` per vLLM's Evictor ABC contract.
    * ``remove(block_id)`` → ``policy.evict_block(block_id)``.

    Block-content hashes (vLLM's prefix-cache identifier for a chunk
    of tokens) are tracked in a side dict so ``evict()`` can return
    the right hash when it returns a victim.
    """

    def __init__(
        self,
        num_blocks_capacity: int,
        block_size: int = 16,
        ctm_config: Optional[CTMvLLMConfig] = None,
        enable_logging: bool = False,
        trig_scorer: Optional[Any] = None,
        trig_score_weight: float = 0.30,
        window_pruning_interval: int = 128,
        trig_blend_candidate_count: int = 4,
    ) -> None:
        # Lazy import — kv_policy.attention_evictor is in this
        # package; this class is what we want to use directly
        # (not the heavier CTMBlockSpaceManager that the legacy
        # CTMEvictor wraps).
        from .attention_evictor import KVCachePolicy

        if ctm_config is None:
            # Use KVCachePolicy's defaults — including
            # attention_ema_alpha=0.2 from the Round 4 production
            # default (NOT CTMvLLMConfig's 0.1, which predates Round 4
            # and would silently regress the policy).
            self._policy = KVCachePolicy(
                max_blocks=num_blocks_capacity,
                block_size=block_size,
            )
        else:
            self._policy = KVCachePolicy(
                max_blocks=num_blocks_capacity,
                block_size=block_size,
                sink_tokens=ctm_config.sink_tokens,
                recent_window=ctm_config.recent_window,
                attention_ema_alpha=ctm_config.attention_ema_alpha,
            )
        self._policy.register_sequence(0)
        self._block_size = block_size
        self._content_hash: Dict[int, int] = {}
        self._num_hashed_tokens: Dict[int, int] = {}
        self._last_accessed: Dict[int, float] = {}
        self._tracked: Set[int] = set()
        self._enable_logging = enable_logging
        # Per-evict timing — used by the streaming runner to
        # diagnose CTM+'s runtime overhead vs LRU. Each call to
        # evict() appends its wall-clock duration (seconds) to
        # this list; runner aggregates p50/p99/total at end of
        # cell. Leave-empty list = no evict overhead reported.
        self._evict_timings: List[float] = []

        # ---- Phase 4: trigonometric scoring ----
        # When ``trig_scorer`` is set, evict() blends the policy's
        # native score with a Phase-4 S_trig + S_norm contribution.
        # Pre-RoPE K vectors per block must be supplied via
        # set_block_pre_rope_keys() — populated by a runtime hook
        # similar to Phase 3's attention capture but capturing the
        # PRE-RoPE projection (output of the Q/K linear layers,
        # before RoPE rotation). The hook implementation is GPU-only
        # and lives in the streaming runner; here we only consume
        # the captured vectors.
        self._trig_scorer = trig_scorer
        self._trig_score_weight = float(trig_score_weight)
        # Alias used by evict() — same value, name reflects the
        # semantic ("blend trig into per-call eviction scoring").
        # Kept as a separate attribute so future tuning experiments
        # can decouple per-evict trig weight from window-pruning weight
        # without an API break.
        self._trig_blend_weight = float(trig_score_weight)
        # I4 optimization (May 2026 audit): the v5 GPU run used
        # candidate_count=8 hardcoded — 8× more base scoring per
        # evict than LRU's count=1. Empirically the 62% trig
        # changed_pick rate was concentrated in the top few candidates.
        # Lower default to 4; the constructor param lets us sweep.
        # Set to 1 to effectively disable trig blending (trig_score
        # only affects window_pruning_pass then).
        if trig_blend_candidate_count < 1:
            raise ValueError(
                f"trig_blend_candidate_count must be >= 1; got "
                f"{trig_blend_candidate_count}"
            )
        self._trig_blend_candidate_count = int(trig_blend_candidate_count)
        # block_id -> list of (position, k_real, k_imag) tuples
        self._block_pre_rope_keys: Dict[
            int, List[Tuple[int, List[float], List[float]]]
        ] = {}
        # block_id -> (layer_idx, head_idx) — captured per-block at
        # admission. For multi-layer / multi-head, the runner picks
        # one layer for scoring (typically the last; see the design
        # doc §3 for the simplification).
        self._block_layer_head: Dict[int, Tuple[int, int]] = {}

        # Per-block trig-score cache. Captured K vectors don't change
        # between captures, so the trig score for a block is a pure
        # function of (captured K, calibration stats). We compute it
        # ONCE at set_block_pre_rope_keys() time and reuse it on every
        # subsequent trig_score_block() call. Before this cache the
        # May 2026 GPU run was paying ~3.3M math.cos calls per 60s
        # (2560 ops/evict × 1300 evicts) — the dominant Python
        # overhead in the 20% throughput regression. With the cache,
        # an evict() lookup is O(1).
        self._block_trig_score: Dict[int, float] = {}

        # Window-based pruning state — separate from vLLM's
        # allocator-driven evict() calls. The streaming runner
        # checks this state after each decode batch and triggers a
        # window-pruning pass if the interval threshold is hit.
        from .triattention import WindowPruningState
        self._window_state = WindowPruningState(
            interval_tokens=int(window_pruning_interval)
        )

    # ---- vLLM 0.7 Evictor ABC ----

    def __contains__(self, block_id: int) -> bool:
        return block_id in self._tracked

    def add(
        self,
        block_id: int,
        content_hash: int,
        num_hashed_tokens: int,
        last_accessed: float,
    ) -> None:
        """Track a block that's been admitted to the cache."""
        self._tracked.add(block_id)
        self._content_hash[block_id] = content_hash
        self._num_hashed_tokens[block_id] = num_hashed_tokens
        self._last_accessed[block_id] = last_accessed
        # CTM+ tracks blocks by id. We don't have per-block token
        # positions from vLLM at the evictor layer, so we synthesise
        # positions that are deliberately *outside* the sink window
        # (which is sink_tokens=4 by default) — that way CTM+ doesn't
        # auto-pin every block as a sink. The FIRST block per sequence
        # is in fact the prefix-sink, but vLLM hashes all admitted
        # blocks here; we'd have to track allocation order to detect
        # sinks, which is out of scope for the initial Phase 2 patch.
        # Honest scope: sink-protection is degraded for Phase 2.
        #
        # Audit-pass simplification: vLLM only adds *full* blocks to
        # the prefix cache (partial blocks have unstable hashes), so
        # block_token_count is always block_size. The earlier modulo
        # math accounted for a hypothetical partial-block path that
        # vLLM doesn't actually use.
        sink_offset = self._policy.sink_tokens
        positions = list(range(sink_offset, sink_offset + self._block_size))
        self._policy.ensure_block(
            block_id=block_id, sequence_id=0,
            positions=positions,
        )
        # ensure_block early-returns when block_id is already in
        # self.blocks (which happens on re-admission of an evicted
        # block — vLLM frees the slot via evictor.evict() and may
        # later re-admit the same block_id with a new content_hash).
        # In that path the early-return skips re-adding to gpu_blocks,
        # so _tracked grows while gpu_blocks stays drained, and
        # select_victims eventually returns []. Force the membership
        # here to keep the two sets in lockstep on every add().
        self._policy.gpu_blocks.add(block_id)

    def update(self, block_id: int, last_accessed: float) -> None:
        """Record an access to a tracked block.

        This is the vLLM 0.7+ Evictor ABC's ``update`` method. The
        ABC does not carry attention through this signature, so we
        forward ``attention_sum=0.0`` here. To pass real attention
        values into the policy (Phase 3 path), call
        :meth:`forward_block_attention` separately — typically from
        an attention-capture hook on the model runner.
        """
        if block_id not in self._tracked:
            # vLLM may call update() before add() in edge cases; tolerate.
            return
        self._last_accessed[block_id] = last_accessed
        # Phase 2 path: zero-attention access. Recency + frequency
        # tracking work; attention-derived scoring (ENTITY
        # classification, the 0.35*attn term in the score) does not.
        # Phase 3 augments this via forward_block_attention(...) calls
        # from a model-runner hook that has access to real attention.
        self._policy.on_block_attention(
            block_id=block_id, attention_sum=0.0,
            sequence_id=0,
            seq_len=self._num_hashed_tokens.get(block_id, self._block_size),
        )

    def forward_block_attention(
        self,
        block_id: int,
        attention_sum: float,
        seq_len: Optional[int] = None,
    ) -> None:
        """Phase 3 API: push real attention magnitude into CTM+'s
        scoring for one block.

        Call this from an attention-capture hook on the model
        runner. ``attention_sum`` should be the sum of softmax
        attention weights from the most recent decode-step query
        to all token positions in this block, summed across heads
        (and optionally averaged across layers — caller's choice).

        Distinct from :meth:`update` because vLLM's Evictor ABC
        signature doesn't carry attention; this is an out-of-band
        channel for the same block.

        Silently no-ops on untracked blocks (matches the ``update``
        tolerance).
        """
        if block_id not in self._tracked:
            return
        if seq_len is None:
            seq_len = self._num_hashed_tokens.get(block_id, self._block_size)
        self._policy.on_block_attention(
            block_id=block_id,
            attention_sum=float(attention_sum),
            sequence_id=0,
            seq_len=seq_len,
        )

    def remove(self, block_id: int) -> None:
        """Drop tracking for a block (e.g. cache eviction by hash dedup)."""
        if block_id not in self._tracked:
            return
        self._tracked.discard(block_id)
        self._content_hash.pop(block_id, None)
        self._num_hashed_tokens.pop(block_id, None)
        self._last_accessed.pop(block_id, None)
        # Phase 4: drop speculatively-stored pre-RoPE keys and the
        # cached trig score when the block is freed so the dicts
        # stay bounded by the live cache footprint.
        self._block_pre_rope_keys.pop(block_id, None)
        self._block_layer_head.pop(block_id, None)
        self._block_trig_score.pop(block_id, None)
        self._policy.evict_block(block_id)

    def evict(self) -> Tuple[int, int]:
        """Pick a victim using CTM+ scoring. Returns (block_id, content_hash).

        Raises ValueError if there are no tracked blocks (matches
        vLLM's LRUEvictor contract — vLLM expects this to raise rather
        than return None when the cache is empty).

        Times each call (wall-clock seconds) into ``self._evict_timings``
        so the streaming runner can report p50/p99 evict overhead at
        end of cell.

        **Phase 4 enhancement (May 2026 follow-up):** when
        ``self._trig_scorer`` is set AND ``self._trig_blend_weight > 0``,
        the per-call eviction decision is re-ranked using the trig
        score. We over-sample candidates from the policy (8 victims
        instead of 1), compute ``final_score = base_score -
        trig_blend_weight * trig_score`` for each, and pick the
        lowest. Blocks without captured pre-RoPE keys are scored at
        their base value (trig contribution = 0), so this is
        backwards-compatible: with no calibration the behaviour is
        identical to pre-Phase-4.

        Why this matters: in the May 2026 GPU run, the trig signal
        only fed window_pruning_pass (~45 invocations / 60s), while
        the main evict() ran ~3000× / 60s. Wiring trig into the main
        path means the signal influences ~70× more decisions per
        unit time and is the highest-ROI lever for moving Phase 4
        from "fires but doesn't change outcomes" to
        "fires and shifts the eviction sequence."
        """
        import time as _time
        _t0 = _time.perf_counter()
        try:
            # Decide candidate-pool size: oversample when trig
            # re-ranking is active so the trig signal has room to
            # change the pick.
            trig_active = (
                self._trig_scorer is not None
                and self._trig_blend_weight > 0
            )
            candidate_count = (
                self._trig_blend_candidate_count if trig_active else 1
            )

            # Re-pick until we find a victim that is in our tracked
            # state. select_victims operates on the underlying policy's
            # gpu_blocks set; if a prior evict() forgot to clear it,
            # we'd otherwise return a (block_id, 0) tuple that fails
            # vLLM's `content_hash in _cached_blocks` assertion. Loop
            # to drain any stale entries.
            victim_id = None
            for _ in range(8):
                victims = self._policy.select_victims(count=candidate_count)
                if not victims:
                    raise ValueError(
                        "CTMEvictorModern.evict() called with no tracked "
                        "blocks. vLLM should not call evict on an empty "
                        "cache; this is either a vLLM bug or a "
                        "tracking-state divergence."
                    )
                # Filter to candidates we still track; drop stale ones.
                tracked_candidates = [
                    bid for bid in victims if bid in self._tracked
                ]
                stale = [
                    bid for bid in victims if bid not in self._tracked
                ]
                for bid in stale:
                    self._policy.evict_block(bid)
                if not tracked_candidates:
                    continue

                if trig_active and len(tracked_candidates) > 1:
                    # I5 optimization (May 2026 audit): short-circuit
                    # when NO candidate has captured K — the blend
                    # would contribute exactly zero, so we can just
                    # take the policy's first pick and skip 4× the
                    # base-scoring work. Ticks _phase4_trig_blend_skips
                    # so we can monitor how often this fires (high =
                    # capture isn't keeping up with eviction pace).
                    have_any_trig = any(
                        bid in self._block_trig_score
                        for bid in tracked_candidates
                    )
                    if not have_any_trig:
                        self._phase4_trig_blend_skips = (
                            getattr(
                                self,
                                "_phase4_trig_blend_skips",
                                0,
                            ) + 1
                        )
                        victim_id = tracked_candidates[0]
                        break

                    # Re-rank by base_score + trig_blend_weight * trig_score.
                    # Lower final score = better eviction candidate.
                    # Blocks without captured K score 0 on trig, so
                    # their final score is the base score (no penalty,
                    # no boost). Tracked blocks WITH captured K and
                    # LOW trig (unimportant) get a smaller positive
                    # adjustment, dropping below blocks with HIGH trig
                    # (important) and getting picked first.
                    self._phase4_trig_blend_evict_calls = (
                        getattr(
                            self,
                            "_phase4_trig_blend_evict_calls",
                            0,
                        ) + 1
                    )
                    # Compute base scores once and reuse for both the
                    # blended ranking AND the base-only "would the
                    # pick have differed?" check. This avoids the
                    # redundant second sort that the v6 code did.
                    base_scores = {
                        bid: self._policy.score_block(bid)
                        for bid in tracked_candidates
                    }
                    blended: List[Tuple[float, int]] = []
                    for bid in tracked_candidates:
                        base = base_scores[bid]
                        trig = self.trig_score_block(bid)
                        if trig is None:
                            final = float(base)
                        else:
                            final = float(base) + (
                                self._trig_blend_weight * float(trig)
                            )
                        blended.append((final, bid))
                    blended.sort(key=lambda x: x[0])
                    victim_id = blended[0][1]
                    self._phase4_trig_blend_picks = (
                        getattr(self, "_phase4_trig_blend_picks", 0) + 1
                    )
                    # Track when trig actually changed the pick (vs
                    # base-only ordering). Reuses base_scores from
                    # above (I5 cleanup: no second policy.score_block
                    # call).
                    base_only_winner = min(
                        tracked_candidates, key=lambda bid: base_scores[bid],
                    )
                    if base_only_winner != victim_id:
                        self._phase4_trig_changed_pick = (
                            getattr(
                                self, "_phase4_trig_changed_pick", 0,
                            ) + 1
                        )
                else:
                    # Single-candidate or trig-inactive path.
                    victim_id = tracked_candidates[0]
                break
            else:
                raise ValueError(
                    "CTMEvictorModern.evict(): exhausted retries trying "
                    "to find a victim that is tracked. policy gpu_blocks "
                    "and self._tracked have diverged."
                )
            assert victim_id is not None
            content_hash = self._content_hash.pop(victim_id)
            self._num_hashed_tokens.pop(victim_id, None)
            self._last_accessed.pop(victim_id, None)
            self._tracked.discard(victim_id)
            # Phase 4: drop speculatively-stored pre-RoPE keys + the
            # cached trig score for the evicted block so the dicts
            # stay bounded by the live cache footprint.
            self._block_pre_rope_keys.pop(victim_id, None)
            self._block_layer_head.pop(victim_id, None)
            self._block_trig_score.pop(victim_id, None)
            # Mirror vLLM's LRUEvictor: on evict, the block is fully
            # removed from the evictor's pool. The CTM+ policy's
            # gpu_blocks set is the parallel "evictor pool" — keep it
            # in lockstep so future select_victims doesn't keep
            # picking the same already-evicted block.
            self._policy.evict_block(victim_id)
            if self._enable_logging:
                logger.debug(
                    "CTMEvictorModern: evicted block_id=%d content_hash=%d",
                    victim_id, content_hash,
                )
            return (victim_id, content_hash)
        finally:
            self._evict_timings.append(_time.perf_counter() - _t0)

    def evict_timings_seconds(self) -> List[float]:
        """Return a snapshot of all per-evict durations recorded
        so far (wall-clock seconds). Snapshot is a copy; callers
        can sort/percentile without disturbing the live buffer.
        """
        return list(self._evict_timings)

    def reset_evict_timings(self) -> None:
        """Clear the per-evict timing buffer. Used by the runner
        between cells when reusing an evictor across runs (not
        the current pattern but supported)."""
        self._evict_timings.clear()

    @property
    def num_blocks(self) -> int:
        return len(self._tracked)

    # ---- Optional debug ----

    def get_stats(self) -> Dict:
        return self._policy.stats

    # ---- Phase 4 API ----

    def set_block_pre_rope_keys(
        self,
        block_id: int,
        keys: List[Tuple[int, List[float], List[float]]],
        layer: int = 0,
        head: int = 0,
    ) -> None:
        """Store the pre-RoPE K vectors for one block.

        Called by the runtime capture hook (GPU path). Each entry is
        ``(absolute_position, k_real_per_band, k_imag_per_band)`` for
        one token in the block.

        ``layer`` and ``head`` identify which model (layer, head) the
        captured vectors come from. Phase 4 default uses the last
        layer's first head — see MODE_B_PHASE4_DESIGN.md §3 for the
        single-layer simplification justification.

        **Speculative storage:** does NOT gate on ``self._tracked``.
        The first GPU run (May 2026) showed every decode token writes
        to a block_id that vLLM has not yet promoted to immutable —
        so it isn't in the evictor's pool yet, and gating here was
        the silent wall that produced
        ``phase4_blocks_captured_with_pre_rope_keys=0``. We store
        speculatively; ``remove()`` and ``evict()`` pop the keys when
        the block is freed, so the dict stays bounded by the live
        cache footprint.
        """
        self._phase4_set_pre_rope_keys_calls = (
            getattr(self, "_phase4_set_pre_rope_keys_calls", 0) + 1
        )
        if block_id not in self._tracked:
            self._phase4_set_pre_rope_keys_speculative = (
                getattr(self, "_phase4_set_pre_rope_keys_speculative", 0) + 1
            )
        keys_list = list(keys)
        self._block_pre_rope_keys[block_id] = keys_list
        self._block_layer_head[block_id] = (int(layer), int(head))
        # Compute the trig score eagerly so subsequent evict() calls
        # are O(1) lookups instead of O(num_bands * num_future_offsets)
        # Python cosine math. This is the I1 optimization from the
        # May 2026 audit — the dominant cost in the 20% throughput
        # regression. Failures here must not break capture (we just
        # leave the cache entry stale).
        if self._trig_scorer is not None:
            self._phase4_trig_score_computes = (
                getattr(self, "_phase4_trig_score_computes", 0) + 1
            )
            try:
                from .triattention import aggregate_block_trig_score
                self._block_trig_score[block_id] = (
                    aggregate_block_trig_score(
                        scorer=self._trig_scorer,
                        layer=int(layer), head=int(head),
                        block_keys=keys_list,
                    )
                )
            except Exception:
                # Cache miss — leave any prior entry alone and let
                # trig_score_block return None via the not-in-cache
                # path. Don't crash the capture hook.
                self._phase4_trig_score_compute_exceptions = (
                    getattr(
                        self,
                        "_phase4_trig_score_compute_exceptions",
                        0,
                    ) + 1
                )

    def trig_score_block(self, block_id: int) -> Optional[float]:
        """Return the Phase 4 trig+norm score for one block.

        Reads the cached score populated by ``set_block_pre_rope_keys``.
        Returns ``None`` if no pre-RoPE keys were captured for this
        block (capture didn't fire — Phase 4 falls back to the
        native CTM+ score for that block). Otherwise returns a float
        where higher = more important.
        """
        if self._trig_scorer is None:
            return None
        self._phase4_trig_score_lookups = (
            getattr(self, "_phase4_trig_score_lookups", 0) + 1
        )
        # Cache hit path (the I1 optimization, May 2026 audit).
        cached = self._block_trig_score.get(block_id)
        if cached is not None:
            return cached
        # Cache miss — block had no K captured, OR
        # set_block_pre_rope_keys raised during the eager compute.
        # In either case fall back to compute-on-demand so behavior
        # is identical to pre-cache. This path is rare in production.
        self._phase4_trig_score_cache_misses = (
            getattr(self, "_phase4_trig_score_cache_misses", 0) + 1
        )
        block_keys = self._block_pre_rope_keys.get(block_id)
        if not block_keys:
            return None
        layer, head = self._block_layer_head.get(block_id, (0, 0))
        from .triattention import aggregate_block_trig_score
        return aggregate_block_trig_score(
            scorer=self._trig_scorer,
            layer=layer, head=head,
            block_keys=block_keys,
        )

    def window_pruning_passed(self, decode_tokens_emitted: int) -> bool:
        """Update the window-pruning state and return True if a
        prune pass should fire now.

        Streaming runner calls this after each decode-batch yield;
        when True, the runner invokes
        :meth:`window_pruning_pass` to score-and-prune.
        """
        from .triattention import window_pruning_decision
        return window_pruning_decision(
            self._window_state, decode_tokens_emitted,
        )

    def window_pruning_pass(self, target_blocks: int) -> int:
        """Evict the lowest-trig-scoring blocks until tracked-block
        count ≤ ``target_blocks``. Returns the number of blocks
        evicted in this pass.

        Skips blocks for which no pre-RoPE keys were captured
        (those fall back to the next vLLM-driven evict() decision).
        """
        if self._trig_scorer is None or len(self._tracked) <= target_blocks:
            return 0

        scored: List[Tuple[float, int]] = []
        for bid in list(self._tracked):
            score = self.trig_score_block(bid)
            if score is None:
                continue
            scored.append((score, bid))

        if not scored:
            return 0

        scored.sort(key=lambda x: x[0])  # lowest first = first to evict
        n_to_evict = max(0, len(self._tracked) - target_blocks)
        evicted = 0
        for _, bid in scored[:n_to_evict]:
            try:
                self.remove(bid)
                # remove() already pops these dicts; redundant pops
                # kept as belt-and-braces for the case where this
                # path runs against a block that wasn't in _tracked.
                self._block_pre_rope_keys.pop(bid, None)
                self._block_layer_head.pop(bid, None)
                self._block_trig_score.pop(bid, None)
                evicted += 1
            except Exception:
                continue
        return evicted

    @property
    def window_pruning_invocations(self) -> int:
        return self._window_state.n_prune_invocations


if not _CYTHON_EVICTOR_AVAILABLE:
    # Pure-Python fallback so callers that import ``CTMEvictorModernC``
    # don't fail when the Cython extension wasn't compiled. Semantically
    # equivalent at the cost of the Python-dispatch overhead the C port
    # exists to remove.
    CTMEvictorModernC = CTMEvictorModern  # type: ignore[misc,assignment]


def _walk_modern_gpu_allocator(engine: Any) -> Any:
    """Walk a modern vLLM (0.5+) engine's allocator path and return
    the per-device GPU allocator.

    Returns the inner allocator object (a ``PrefixCachingBlockAllocator``
    when prefix caching is enabled, ``NaiveBlockAllocator`` otherwise).
    Raises ``RuntimeError`` if the path can't be resolved or
    ``NotImplementedError`` if prefix caching is off (no evictor exists
    on the naive path).

    Accepts either the inner ``LLMEngine`` directly or an
    ``AsyncLLMEngine`` wrapper that exposes the inner engine via
    ``.engine``. Tries both.
    """
    # Async engines wrap an inner engine; if the outer doesn't expose
    # .scheduler, peel one layer.
    inner = engine
    if not hasattr(inner, "scheduler") and hasattr(inner, "engine"):
        inner = inner.engine
    try:
        scheduler = inner.scheduler[0] if isinstance(inner.scheduler, list) else inner.scheduler
        block_manager = scheduler.block_manager
    except (AttributeError, IndexError) as e:
        raise RuntimeError(
            f"Cannot access block manager from engine. Error: {e}"
        )

    block_allocator = getattr(block_manager, "block_allocator", None)
    if block_allocator is None:
        raise RuntimeError(
            "block_manager.block_allocator missing. This patch targets "
            "vLLM 0.5+ (SelfAttnBlockSpaceManager + CpuGpuBlockAllocator). "
            f"Got block_manager type: {type(block_manager).__name__}"
        )

    # vLLM 0.5+ stores per-device allocators in a private dict.
    # Try a few names — vLLM has touched this between minor versions.
    inner_dict = (
        getattr(block_allocator, "_allocators", None)
        or getattr(block_allocator, "allocators", None)
    )
    if inner_dict is None:
        raise RuntimeError(
            f"Cannot find _allocators dict on {type(block_allocator).__name__}. "
            "This vLLM minor version may have changed the internal layout."
        )

    # Find the GPU allocator. vLLM's Device enum is at
    # vllm.utils.Device on 0.7; on other versions the import path
    # may differ. We don't import it directly — we identify the GPU
    # allocator by its capacity dwarfing the CPU one (real GPUs have
    # KV cache of single-digit GiB; CPU swap_space defaults to 4-16 GiB
    # but in the inner-dict allocator the "cpu" allocator's capacity
    # reflects the CPU swap_space block count, which is comparable).
    # A safer route: look for the key whose .name is 'GPU'.
    gpu_allocator = None
    for key, alloc in inner_dict.items():
        # Try the enum-name approach.
        key_name = getattr(key, "name", str(key)).upper()
        if key_name == "GPU":
            gpu_allocator = alloc
            break
    if gpu_allocator is None:
        raise RuntimeError(
            f"Cannot find GPU allocator in {list(inner_dict.keys())}. "
            "vLLM's Device enum may have shifted; please file an issue."
        )

    return gpu_allocator


def patch_vllm_engine_modern(
    engine: Any,
    enable_logging: bool = False,
    trig_scorer: Optional[Any] = None,
    window_pruning_interval: int = 128,
    trig_blend_candidate_count: int = 4,
    use_cython_evictor: bool = False,
) -> CTMEvictorModern:
    """Install CTMEvictorModern on a modern vLLM (0.5+) engine.

    **Requirements:**

    * ``enable_prefix_caching=True`` was set on the engine. Without
      it, the GPU allocator is ``NaiveBlockAllocator`` which has no
      ``evictor`` attribute — the patch raises ``NotImplementedError``
      with a clear message. (Same failure mode as vLLM 0.4 without
      prefix caching; documented in
      ``Bench/scripts/MODE_B_VLLM04_RUNBOOK.md`` §1.1.)
    * vLLM 0.5+ allocator architecture (verified against 0.7.3).
      Earlier minor versions (0.5.x, 0.6.x) may have slightly
      different internal layouts; the walker tries multiple
      attribute names but may fail on a specific minor — the
      ``RuntimeError`` then names what's missing.

    **Operational scope (honest):** with prefix caching enabled, the
    evictor decides which *cached-but-unreferenced* blocks to release
    when the cache fills. Phase 2 measurements are about that
    decision, NOT about under-pressure swap (Mode A's tier model).

    Args:
        engine: A vLLM AsyncLLMEngine or LLMEngine.
        enable_logging: Pass through to the CTM+ policy for
            structured event logging.

    Returns:
        The installed ``CTMEvictorModern`` (for inspection / stats).

    Raises:
        NotImplementedError: prefix caching is off and the GPU
            allocator is ``NaiveBlockAllocator``.
        RuntimeError: allocator path can't be walked on this
            vLLM minor version.
    """
    gpu_allocator = _walk_modern_gpu_allocator(engine)

    # Detect prefix-caching path. The PrefixCachingBlockAllocator has
    # an `evictor` attribute (LRUEvictor by default); the
    # NaiveBlockAllocator does not.
    if not hasattr(gpu_allocator, "evictor"):
        raise NotImplementedError(
            "CTM+ Phase 2 patch requires enable_prefix_caching=True on "
            "engine init. Without it, vLLM uses NaiveBlockAllocator "
            "which has no evictor to swap. Modern-vLLM CTM+ runs only "
            "test cache-retention decisions; under-pressure swap is the "
            "Phase 1 LRU-only path (see MODE_B_STREAMING_DESIGN.md §4.4 "
            "and RESULTS.md §13).\n\n"
            f"Detected GPU allocator: {type(gpu_allocator).__name__}\n"
            "Fix: re-initialise the engine with "
            "AsyncEngineArgs(..., enable_prefix_caching=True)."
        )

    # Read the LRUEvictor's capacity to size the CTM+ policy's GPU
    # block tracking. vLLM's Evictor ABC doesn't require this size,
    # but CTMEvictorModern's KVCachePolicy needs a num_gpu_blocks
    # value at init (used for capacity-bounded data structures).
    num_blocks = getattr(gpu_allocator, "num_blocks", None)
    if num_blocks is None:
        # PrefixCachingBlockAllocator may expose capacity differently
        # across versions; fall back to a conservative default that
        # KVCachePolicy can grow into.
        num_blocks = 4096

    block_size = getattr(gpu_allocator, "_block_size", None)
    if block_size is None:
        block_size = getattr(gpu_allocator, "block_size", 16)

    # UX guard: when the caller asks for the Cython variant but the
    # compiled extension wasn't built, ``CTMEvictorModernC`` is aliased
    # to ``CTMEvictorModern`` (see top-of-file fallback). Silently
    # picking the Python class then would waste a partner-facing GPU
    # cell — log loudly so the operator sees the fallback in real time
    # and can rebuild before retrying. This is the v9 PHASE4_GPU_FINDINGS
    # §12.3 lesson: silent fallbacks are the bug class that costs hours.
    if use_cython_evictor and not _CYTHON_EVICTOR_AVAILABLE:
        logger.warning(
            "patch_vllm_engine_modern: use_cython_evictor=True but the "
            "Cython extension kv_policy._ctm_evictor is not importable. "
            "Falling back to the pure-Python CTMEvictorModern. The "
            "throughput-tax fix this flag was meant to apply WILL NOT "
            "be in effect for this run. Rebuild with: "
            "`cd CTM_plus/KVPolicy && python3 setup.py build_ext --inplace`."
        )

    ctm_evictor = (CTMEvictorModernC if use_cython_evictor else CTMEvictorModern)(
        num_blocks_capacity=int(num_blocks),
        block_size=int(block_size),
        enable_logging=enable_logging,
        trig_scorer=trig_scorer,
        window_pruning_interval=window_pruning_interval,
        trig_blend_candidate_count=int(trig_blend_candidate_count),
    )

    # The replacement. After this, vLLM's
    # PrefixCachingBlockAllocator routes all .add / .evict / .update /
    # .remove calls through CTMEvictorModern.
    original_evictor_type = type(gpu_allocator.evictor).__name__
    gpu_allocator.evictor = ctm_evictor
    logger.info(
        "CTM+ Phase 2 patch installed: %s -> %s",
        original_evictor_type, type(ctm_evictor).__name__,
    )
    return ctm_evictor


# =============================================================================
# Phase 3 — attention forwarding (real attention into CTM+)
# =============================================================================
#
# Phase 2 ships CTMEvictorModern but vLLM's Evictor ABC carries
# zero attention through update(block_id, last_accessed). Without
# a non-zero attention_sum reaching CTM+'s on_block_attention,
# the attention-EMA stays at 0 -> no block becomes ENTITY ->
# the 0.35*attn term in the score zeroes out. Phase 2's effective
# score is 0.25*recency + 0.10*frequency — close to LRU. (See
# MODE_B_STREAMING_DESIGN.md §1.1 audit-pass HIGH-severity callout.)
#
# Phase 3 plumbs real attention through a separate channel. The
# capture hook computes attention manually for the new query
# token alongside vLLM's normal forward, sums per block, and
# pushes the sums via CTMEvictorModern.forward_block_attention.
#
# Implementation strategy: monkey-patch each Attention layer's
# forward method. The wrapper:
#
# 1. Calls the original forward (unchanged behaviour for output
#    correctness).
# 2. Captures the inputs (query Q, key K) and the attn_metadata
#    (which carries the block_table mapping query positions to
#    physical block IDs).
# 3. Computes scaled-dot-product attention manually for the
#    decode-step query: softmax(Q @ K^T / sqrt(d_k)).
# 4. Aggregates per-block by grouping key positions by their
#    physical block ID (from block_table).
# 5. Pushes the per-block sums to the evictor.
#
# Honest scope (audit-pass discipline):
#
# * The aggregator math (steps 3-4) is CPU-testable with synthetic
#   tensors. It IS implemented and tested.
# * The hook installation (step 1) walks the model's modules to
#   find Attention layers. CPU-testable with mocked nn.Modules.
#   It IS implemented and tested.
# * The actual capture inside vLLM's running engine (does the
#   monkey-patched forward fire? does it have access to Q + K +
#   attn_metadata in the expected shapes?) requires GPU validation.
#   This is documented as the GPU-only step, deferred until the
#   next pod session.
#
# The ~10-15% per-token overhead from manual attention
# recomputation is acceptable for benchmarking; would need
# optimisation (FlashAttention with score output, or layer
# subsampling) for production.


@dataclass
class _PerBlockAttention:
    """Running per-block attention totals between flushes."""

    block_id: int
    attention_sum: float
    layer_count: int

    def add(self, attention_value: float) -> None:
        self.attention_sum += float(attention_value)
        self.layer_count += 1


class AttentionAggregator:
    """Accumulates per-block attention sums across layers within
    a single decode step, then flushes them to the evictor.

    Usage by the attention-capture hook (one call per layer):

        aggregator.record_block_attention(block_id=42, weight=0.18)
        aggregator.record_block_attention(block_id=43, weight=0.05)
        ...
        aggregator.flush_to_evictor(evictor)   # at the end of decode step

    Multi-layer aggregation policy: the aggregator sums attention
    weights across layers for each block. The evictor receives the
    cumulative sum, which is what CTM+'s ``on_block_attention``
    expects (it adds to ``cumulative_attention`` and feeds the EMA).

    Pure-Python; testable without vLLM.
    """

    def __init__(self) -> None:
        self._buffer: Dict[int, _PerBlockAttention] = {}
        self._stats: Dict[str, int] = {
            "samples_recorded": 0,
            "blocks_flushed": 0,
            "flushes": 0,
        }
        # Attention-capture timing. Each call to
        # ``record_capture_time(seconds)`` appends here; the runner
        # aggregates total + count at end of cell. Used to
        # quantify Phase 3's per-token overhead independently of
        # the swap-counter outcome.
        self._capture_timings_seconds: List[float] = []

    def record_block_attention(
        self, block_id: int, weight: float,
    ) -> None:
        """Record one (block, attention-weight) sample. Multiple
        calls to the same block_id within one flush window
        accumulate."""
        if block_id not in self._buffer:
            self._buffer[block_id] = _PerBlockAttention(
                block_id=block_id, attention_sum=0.0, layer_count=0,
            )
        self._buffer[block_id].add(weight)
        self._stats["samples_recorded"] += 1

    def record_block_batch(
        self, weights: Dict[int, float],
    ) -> None:
        """Bulk-record per-block sums from a single layer's
        aggregation. Convenience for hooks that compute the whole
        layer's per-block sum and push in one call."""
        for block_id, weight in weights.items():
            self.record_block_attention(block_id, weight)

    def flush_to_evictor(self, evictor: Any) -> int:
        """Push accumulated per-block sums to the evictor's
        :meth:`forward_block_attention` and clear the buffer.

        Returns the number of blocks flushed.
        """
        if not self._buffer:
            return 0
        flushed = 0
        for block_id, entry in self._buffer.items():
            try:
                evictor.forward_block_attention(
                    block_id=block_id,
                    attention_sum=entry.attention_sum,
                )
                flushed += 1
            except Exception:
                # Best-effort: a stale block_id (e.g. evicted between
                # capture and flush) shouldn't kill the run.
                continue
        self._buffer.clear()
        self._stats["blocks_flushed"] += flushed
        self._stats["flushes"] += 1
        return flushed

    @property
    def buffered_blocks(self) -> int:
        return len(self._buffer)

    @property
    def stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def record_capture_time(self, seconds: float) -> None:
        """Record the wall-clock duration of one capture call
        (one Attention.forward wrapped invocation)."""
        if seconds < 0:
            raise ValueError(f"capture time must be >= 0; got {seconds}")
        self._capture_timings_seconds.append(float(seconds))

    def capture_timings_seconds(self) -> List[float]:
        """Snapshot of recorded capture durations."""
        return list(self._capture_timings_seconds)


def aggregate_attention_to_blocks(
    attention_weights: List[float],
    block_table: List[int],
    block_size: int,
) -> Dict[int, float]:
    """Aggregate a per-key attention vector to per-block sums.

    ``attention_weights[i]`` is the softmax attention weight from
    the new query token to key position ``i``. ``block_table[j]``
    is the physical block_id holding the j-th block of this
    sequence. Each block holds ``block_size`` consecutive token
    positions.

    Returns a dict ``{block_id: attention_sum}`` where the sum is
    the sum of attention weights for the token positions in that
    block.

    Pure function — testable without vLLM.

    Caveat: the last block of a sequence may be partially filled
    (sequence length not a multiple of block_size). The function
    truncates at ``len(attention_weights)``; the caller is
    responsible for passing the right number of weights.
    """
    if block_size <= 0:
        raise ValueError(f"block_size must be > 0; got {block_size}")
    if len(block_table) * block_size < len(attention_weights):
        raise ValueError(
            f"block_table {len(block_table)} blocks x "
            f"{block_size} tokens/block = "
            f"{len(block_table) * block_size} key slots, but got "
            f"{len(attention_weights)} attention weights."
        )

    sums: Dict[int, float] = {}
    for key_pos, weight in enumerate(attention_weights):
        block_idx = key_pos // block_size
        if block_idx >= len(block_table):
            break
        block_id = block_table[block_idx]
        sums[block_id] = sums.get(block_id, 0.0) + float(weight)
    return sums


def install_attention_capture(
    model: Any,
    aggregator: AttentionAggregator,
    evictor: Any,
    enable_logging: bool = False,
) -> int:
    """Monkey-patch every ``Attention`` module in ``model`` so its
    ``forward`` also computes per-block attention manually and
    pushes to ``aggregator``, which then flushes to ``evictor``.

    Returns the number of layers patched. Returns 0 (and logs
    a warning) if no Attention modules are found — likely
    indicates a vLLM version with a different module structure
    or an attention backend we haven't matched.

    Pure-Python install; the captured-attention computation
    inside the patched forward needs torch + a real tensor
    flow, but the install logic itself is testable on a mock
    model.

    The patched forward works as follows:

    1. Call original ``forward(query, key, value, kv_cache,
       attn_metadata)`` — preserves correctness.
    2. Compute scaled-dot-product attention manually for the
       new decode-token query against the active sequence's
       cached keys.
    3. Aggregate per-block via
       :func:`aggregate_attention_to_blocks` using the
       block_table from attn_metadata.
    4. Push to ``aggregator.record_block_batch(...)``.
    5. After all layers fire (per decode step), the run loop
       calls ``aggregator.flush_to_evictor(evictor)``.

    The actual attention computation in step 2 is wrapped in a
    try/except — if extraction fails for any reason (backend
    incompatibility, shape mismatch, missing attribute on
    attn_metadata), we log + continue. The model's output is
    unchanged; only the side-channel attention forwarding is
    affected.
    """
    # Find attention modules. vLLM 0.7+ uses
    # vllm.attention.layer.Attention; we identify by class name
    # so we don't have to import vllm here (keeps this function
    # CPU-testable on hosts without vLLM). torch is imported
    # lazily inside the patched forward when attention is actually
    # being captured — install-time torch absence does NOT block
    # the install (the wrapper just won't have torch available
    # at runtime, which is fine because forward() running implies
    # torch IS installed).
    patched_count = 0
    for name, module in _walk_modules(model):
        if not _is_vllm_attention_module(module):
            continue
        original_forward = module.forward
        head_size = getattr(module, "head_size", None)
        if head_size is None:
            head_size = getattr(module, "head_dim", None)

        def make_wrapper(orig, head_dim, layer_name):
            import time as _time

            def wrapped_forward(*args, **kwargs):
                output = orig(*args, **kwargs)
                _t0 = _time.perf_counter()
                captured = False
                try:
                    _capture_attention_to_aggregator(
                        args=args, kwargs=kwargs,
                        head_dim=head_dim,
                        aggregator=aggregator,
                    )
                    captured = True
                except Exception as exc:
                    if enable_logging:
                        logger.warning(
                            "attention capture failed in %s: %s",
                            layer_name, exc,
                        )
                finally:
                    # Always record timing — even failed captures
                    # took some time; partner-facing diligence wants
                    # the total Phase-3 overhead, not just successful
                    # captures.
                    _dt = _time.perf_counter() - _t0
                    try:
                        aggregator.record_capture_time(_dt)
                    except Exception:
                        pass
                return output
            return wrapped_forward

        module.forward = make_wrapper(original_forward, head_size, name)
        patched_count += 1

    if patched_count == 0:
        logger.warning(
            "install_attention_capture: no Attention modules found "
            "in model. Phase 3 attention forwarding will be a no-op. "
            "vLLM minor version may have different module structure."
        )
    else:
        logger.info(
            "install_attention_capture: patched %d Attention layers",
            patched_count,
        )
    return patched_count


def _walk_modules(model: Any):
    """Yield (name, module) for every nn.Module in the tree.
    Falls back to attribute walking if the object has no
    ``named_modules`` (mocks in tests)."""
    if hasattr(model, "named_modules"):
        for name, module in model.named_modules():
            yield name, module
        return
    # Fallback for tests with simple objects.
    seen = set()
    stack = [("", model)]
    while stack:
        name, obj = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        yield name, obj
        for attr in dir(obj):
            if attr.startswith("_"):
                continue
            try:
                child = getattr(obj, attr)
            except AttributeError:
                continue
            if hasattr(child, "forward"):
                stack.append((f"{name}.{attr}" if name else attr, child))


def _is_vllm_attention_module(module: Any) -> bool:
    """Identify vLLM's Attention layer by class name (avoids
    requiring vllm to be importable)."""
    cls = type(module).__name__
    if cls in ("Attention", "PagedAttention"):
        return True
    # Heuristic fallback: an attention-like module typically has
    # `head_size` or `head_dim` AND `num_heads` AND a forward
    # method whose signature includes "kv_cache" or "attn_metadata".
    has_head_dim = (
        hasattr(module, "head_size") or hasattr(module, "head_dim")
    )
    has_heads = hasattr(module, "num_heads")
    return has_head_dim and has_heads and hasattr(module, "forward")


def _capture_attention_to_aggregator(
    args: tuple,
    kwargs: dict,
    head_dim: Optional[int],
    aggregator: "AttentionAggregator",
) -> None:
    """Compute manual attention for the decode-step query and
    push per-block sums to the aggregator.

    This is the GPU-touching path. Wrapped in a try/except by the
    caller so any extraction failure degrades to "no attention
    captured" rather than crashing the run.

    Strategy:

    * Pull query, key, attn_metadata from the forward args. vLLM
      0.7's Attention.forward signature is
      ``forward(query, key, value, kv_cache, attn_metadata)``.
    * Identify the *decode-step* portion of the query: vLLM
      batches prefill + decode; we want only the new-token query.
      ``attn_metadata.num_decode_tokens`` and
      ``attn_metadata.num_prefill_tokens`` partition the batch.
    * For each decode query, compute softmax(Q @ K^T / sqrt(d_k))
      against the sequence's cached keys (extracted from
      ``kv_cache`` via the block_table).
    * Aggregate per-block via ``aggregate_attention_to_blocks``.

    GPU-validation deferred: this function works correctly on
    well-formed tensor inputs in the test suite, but the
    interaction with vLLM's actual attn_metadata + kv_cache
    objects requires a real GPU run to validate.
    """
    # Extract attn_metadata first — it's required regardless of
    # which path (test side-channel vs real GPU extraction) we take.
    if len(args) >= 5:
        attn_metadata = args[4]
    else:
        attn_metadata = kwargs.get("attn_metadata")
    if attn_metadata is None:
        return

    # Test-mode side channel FIRST. If the test passes a synthetic
    # attn_metadata with `decode_attention_weights` pre-computed,
    # use that and skip the real GPU extraction entirely. This
    # keeps the install path CPU-testable (sentinel-object args
    # don't need to support slicing).
    decode_weights = getattr(
        attn_metadata, "decode_attention_weights", None,
    )
    if decode_weights is not None:
        if isinstance(decode_weights, dict):
            aggregator.record_block_batch(decode_weights)
        elif isinstance(decode_weights, list):
            for per_query_weights in decode_weights:
                if isinstance(per_query_weights, dict):
                    aggregator.record_block_batch(per_query_weights)
        return

    # Real GPU-extraction path beyond this point. Validate inputs.
    if len(args) >= 5:
        query, key, value, kv_cache, _ = args[:5]
    else:
        query = kwargs.get("query")
        key = kwargs.get("key")
        kv_cache = kwargs.get("kv_cache")
    if query is None or key is None:
        return

    block_tables = getattr(attn_metadata, "block_tables", None)
    if block_tables is None:
        return

    num_decode_tokens = getattr(attn_metadata, "num_decode_tokens", 0)
    if num_decode_tokens <= 0:
        return

    # Real GPU extraction. Computes softmax(Q @ K^T / sqrt(d_k))
    # for each decode-step query against its sequence's cached keys,
    # aggregates per-block via the block_table, and pushes per-block
    # sums to the aggregator.
    #
    # Layout assumptions (documented; first GPU run diagnoses
    # mismatches via the wrapped forward's try/except + warning):
    #
    # * query: [num_tokens, num_heads * head_dim] — concat of
    #   num_prefill_tokens + num_decode_tokens. We slice the
    #   decode portion.
    # * kv_cache: [2, num_blocks, block_size, num_kv_heads, head_dim]
    #   for FlashAttention backend (most common on vLLM 0.7+).
    #   kv_cache[0] is K, kv_cache[1] is V.
    #   Backends with different layouts (xformers, ROCmFlash) may
    #   need fallback handling; we degrade to no-op + warning if
    #   the layout doesn't match.
    # * attn_metadata.block_tables:
    #   [num_seqs, max_blocks_per_seq] — physical block_ids per
    #   sequence in the decode batch.
    # * attn_metadata.seq_lens: [num_seqs] — current token count
    #   per sequence.
    # * attn_metadata.num_prefill_tokens: int — partition point
    #   in the batch.
    _gpu_extract_decode_attention(
        query=query,
        kv_cache=kv_cache,
        attn_metadata=attn_metadata,
        head_dim=head_dim,
        aggregator=aggregator,
    )


def _gpu_extract_decode_attention(
    *,
    query: Any,
    kv_cache: Any,
    attn_metadata: Any,
    head_dim: Optional[int],
    aggregator: "AttentionAggregator",
) -> None:
    """GPU extraction: per decode-step query, compute softmax(Q @ K^T)
    against the sequence's cached keys, aggregate per-block.

    This function is the GPU-touching path. The wrapped forward in
    :func:`install_attention_capture` catches any exception this
    raises and logs a warning — so a layout mismatch on the first
    GPU run degrades to "no attention captured" rather than
    crashing the run. Diagnose via the warning message.

    Implementation steps:

    1. Slice query down to just the decode portion using
       ``num_prefill_tokens`` + ``num_decode_tokens``.
    2. Reshape query to ``[num_decode_tokens, num_heads, head_dim]``.
    3. For each decode token, identify its sequence's
       ``block_table`` row + ``seq_len``.
    4. Gather K from ``kv_cache`` using the block_table.
    5. Truncate to actual seq_len.
    6. Handle GQA (num_kv_heads < num_heads) by repeating K.
    7. Compute logits = Q @ K^T / sqrt(head_dim).
    8. Average logits across heads.
    9. softmax → per-key attention probabilities.
    10. ``aggregate_attention_to_blocks`` → per-block sums.
    11. ``aggregator.record_block_batch(...)``.
    """
    import torch
    import torch.nn.functional as F
    import math

    num_decode_tokens = int(getattr(attn_metadata, "num_decode_tokens", 0))
    if num_decode_tokens <= 0:
        return

    num_prefill_tokens = int(
        getattr(attn_metadata, "num_prefill_tokens", 0)
    )
    decode_query = query[
        num_prefill_tokens : num_prefill_tokens + num_decode_tokens
    ]
    if decode_query.numel() == 0:
        return

    # Reshape to [num_decode_tokens, num_heads, head_dim].
    if head_dim is None or head_dim <= 0:
        return
    total_dim = decode_query.shape[-1]
    if total_dim % head_dim != 0:
        # Layout mismatch: query last-dim isn't num_heads*head_dim.
        # Degrade to no-op; the wrapped forward's try/except will
        # log this once.
        raise ValueError(
            f"query last dim {total_dim} is not a multiple of "
            f"head_dim {head_dim}; layout assumption mismatch."
        )
    num_heads = total_dim // head_dim
    decode_query = decode_query.view(
        num_decode_tokens, num_heads, head_dim,
    )

    # Resolve the K cache. vLLM 0.7 FlashAttention layout:
    # kv_cache[0] -> K, kv_cache[1] -> V. Some backends pass K and V
    # as separate args, in which case kv_cache itself is the K cache.
    # We try [0] indexing first; if shapes don't fit, fall back to
    # treating kv_cache as K directly.
    k_cache = kv_cache
    try:
        if hasattr(kv_cache, "shape") and len(kv_cache.shape) >= 4 and kv_cache.shape[0] == 2:
            k_cache = kv_cache[0]
    except (IndexError, RuntimeError):
        k_cache = kv_cache

    if not hasattr(k_cache, "shape") or len(k_cache.shape) < 4:
        raise ValueError(
            f"k_cache has unexpected shape "
            f"{getattr(k_cache, 'shape', None)}; expected "
            "[num_blocks, block_size, num_kv_heads, head_dim]."
        )

    num_total_blocks, block_size_runtime, num_kv_heads, k_head_dim = (
        k_cache.shape[0], k_cache.shape[1], k_cache.shape[2], k_cache.shape[3],
    )
    if k_head_dim != head_dim:
        raise ValueError(
            f"head_dim mismatch: query={head_dim}, k_cache={k_head_dim}"
        )
    if num_heads % num_kv_heads != 0:
        raise ValueError(
            f"GQA group factor non-integer: num_heads={num_heads}, "
            f"num_kv_heads={num_kv_heads}"
        )
    gqa_factor = num_heads // num_kv_heads

    block_tables = attn_metadata.block_tables
    seq_lens = getattr(attn_metadata, "seq_lens", None)
    if seq_lens is None:
        # Fallback: assume seq_len = max_blocks * block_size.
        seq_lens_list = [
            block_tables[i].shape[0] * block_size_runtime
            for i in range(num_decode_tokens)
        ]
    else:
        seq_lens_list = [int(seq_lens[i]) for i in range(num_decode_tokens)]

    inv_sqrt_d = 1.0 / math.sqrt(head_dim)

    # Process each decode query.
    for i in range(num_decode_tokens):
        seq_len = seq_lens_list[i]
        if seq_len <= 0:
            continue

        # block_tables[i]: [max_blocks_per_seq] of physical block_ids.
        # vLLM 0.7's block_tables can be a torch.Tensor or list.
        try:
            row = block_tables[i]
            if hasattr(row, "tolist"):
                block_ids = row.tolist()
            else:
                block_ids = list(row)
        except (IndexError, AttributeError):
            continue

        blocks_used = (seq_len + block_size_runtime - 1) // block_size_runtime
        block_ids_used = block_ids[:blocks_used]
        if not block_ids_used:
            continue

        # Gather K for this sequence:
        # k_cache[block_ids_used]: [blocks_used, block_size, num_kv_heads, head_dim]
        try:
            k_indices = torch.tensor(
                block_ids_used, dtype=torch.long, device=k_cache.device,
            )
            K_blocks = k_cache.index_select(0, k_indices)
        except (RuntimeError, IndexError) as exc:
            # Stale block_id or device mismatch — skip this query.
            continue

        # Reshape: [blocks_used * block_size, num_kv_heads, head_dim]
        K_seq = K_blocks.reshape(-1, num_kv_heads, head_dim)
        # Truncate to actual seq_len:
        K_seq = K_seq[:seq_len]
        if K_seq.shape[0] == 0:
            continue

        # Repeat K along heads for GQA: [seq_len, num_heads, head_dim]
        if gqa_factor > 1:
            K_full = K_seq.repeat_interleave(gqa_factor, dim=1)
        else:
            K_full = K_seq

        # Q for this decode token: [num_heads, head_dim]
        Q = decode_query[i]

        # logits = Q @ K^T / sqrt(d): [num_heads, seq_len]
        # einsum: "hd,shd->hs"
        logits = torch.einsum("hd,shd->hs", Q, K_full) * inv_sqrt_d

        # Average across heads → [seq_len], then softmax.
        logits_avg = logits.mean(dim=0)
        attn_probs = F.softmax(logits_avg, dim=-1)

        # Move to CPU + Python list for the pure-Python aggregator.
        weights_list = attn_probs.detach().to("cpu", non_blocking=True).tolist()

        # aggregate_attention_to_blocks expects len(weights) <=
        # len(block_table) * block_size; truncate to seq_len.
        per_block_sums = aggregate_attention_to_blocks(
            attention_weights=weights_list[:seq_len],
            block_table=block_ids_used,
            block_size=block_size_runtime,
        )
        aggregator.record_block_batch(per_block_sums)
