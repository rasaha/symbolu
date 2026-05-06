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
