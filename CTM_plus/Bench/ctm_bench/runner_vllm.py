"""Mode B — real-model runner via vLLM.

Drives a real LLM through the same workload generators as Mode A,
with vLLM's KV-cache constrained low enough to force CPU-pinned
+ NVMe swap. Reports the same :class:`RunResult` shape as Mode A
so the existing summary / markdown_table machinery works
unchanged.

**Status: GPU-required scaffold.** This module is runnable on a
machine with vLLM + CUDA + the target model installed, but it
has not been validated on the development sandbox (CPU-only).
The interfaces are pinned by tests; the lazy-import contract
ensures Mode B does not break Mode A or the rest of the harness
on a CPU-only host.

Usage:

    # On a GPU box with vLLM installed:
    pip install vllm
    pip install -e CTM_plus/KVPolicy

    python -m ctm_bench.runner_vllm \\
        --model meta-llama/Llama-3.1-8B-Instruct \\
        --workload rag_128k \\
        --policy ctm_plus \\
        --gpu-memory-utilization 0.30 \\
        --swap-space 8 \\
        --output-dir vllm_out/

The 0.30 gpu-memory-utilization + 8 GB swap_space combination
intentionally pushes KV-cache pressure past HBM into CPU pinned
memory + NVMe-mmap'd swap. Without that pressure the eviction
policy is irrelevant.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ctm_bench.metrics import RunResult
from ctm_bench.workload import (
    AGENTIC_64K,
    AGENTIC_CLUSTERED_64K,
    CHAT_32K,
    RAG_128K,
    AccessPattern,
    WorkloadSpec,
)


logger = logging.getLogger("ctm_bench.runner_vllm")


# ---------------------------------------------------------------- #
# Lazy vLLM import
# ---------------------------------------------------------------- #


def _import_vllm() -> Tuple[Any, Any]:
    """Import vLLM lazily so the module loads on CPU-only hosts.

    Returns ``(LLM, SamplingParams)`` from vLLM. Raises a clear
    ImportError if vLLM is not installed."""
    try:
        from vllm import LLM, SamplingParams  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Mode B requires vLLM. Install with `pip install vllm`. "
            "vLLM also requires CUDA + a supported GPU; this runner "
            "will not work on a CPU-only host even with the package "
            "installed."
        ) from exc
    return LLM, SamplingParams


def _import_ctm_evictor() -> Any:
    """Import the existing CTM+ vLLM evictor shim from the
    sibling KVPolicy package."""
    try:
        from kv_policy.vllm_evictor import patch_vllm_engine  # type: ignore
    except ImportError:
        # Try the path-injected import that policies.py uses.
        from ctm_bench.policies import _add_kv_policy_to_path
        _add_kv_policy_to_path()
        from kv_policy.vllm_evictor import patch_vllm_engine  # type: ignore
    return patch_vllm_engine


# ---------------------------------------------------------------- #
# Workload → vLLM prompt translation
# ---------------------------------------------------------------- #


@dataclass(frozen=True)
class VLLMRequest:
    """One concrete request the vLLM engine will execute. The
    benchmark constructs N of these from a WorkloadSpec and feeds
    them through engine.generate()."""

    seq_id: int
    prompt: str
    max_decode_tokens: int


def workload_to_vllm_requests(
    spec: WorkloadSpec,
    *,
    tokenizer: Any,
    filler_token_id: int = 100,
) -> List[VLLMRequest]:
    """Translate a WorkloadSpec into a list of vLLM requests.

    For the synthetic workloads used in Mode A, real prompt
    *content* doesn't matter — only the prompt *length* does, so
    we synthesise prompts of the right token count using a
    repeating filler token. The decode horizon is set per the
    spec's ``duration_decode_tokens``.

    A real-data run (the eventual successor to this scaffold)
    would replace this function with one that loads recorded
    prompts from a trace file.
    """
    requests: List[VLLMRequest] = []
    # vLLM's tokenizer round-trips token IDs through ``decode``.
    filler_tokens = [filler_token_id] * spec.context_length_tokens
    prompt = tokenizer.decode(filler_tokens, skip_special_tokens=True)
    for seq_id in range(spec.n_concurrent_seqs):
        requests.append(
            VLLMRequest(
                seq_id=seq_id,
                prompt=prompt,
                max_decode_tokens=spec.duration_decode_tokens,
            )
        )
    return requests


# ---------------------------------------------------------------- #
# Mode B runner
# ---------------------------------------------------------------- #


def run_vllm(
    spec: WorkloadSpec,
    policy_name: str,
    *,
    model: str,
    tier_config_name: str = "vllm_real",
    gpu_memory_utilization: float = 0.30,
    swap_space_gb: int = 8,
    enforce_eager: bool = True,
    seed: int = 42,
    dry_run: bool = False,
) -> RunResult:
    """Run a WorkloadSpec through a real model via vLLM.

    The cache pressure is created by clamping
    ``gpu_memory_utilization`` low enough that the working set
    spills past HBM into ``swap_space`` (CPU pinned memory backed
    by NVMe-mmap when the OS chooses to swap).

    For ``policy_name = "ctm_plus"``, we patch vLLM's engine via
    the existing :func:`kv_policy.vllm_evictor.patch_vllm_engine`
    so KV-cache eviction goes through the production CTM+
    scoring math. For ``"lru"`` and ``"fifo"``, we leave vLLM's
    default block manager alone (vLLM's default is roughly LRU);
    a true FIFO baseline would require a separate patch (TODO).
    """
    LLM, SamplingParams = _import_vllm()

    if policy_name not in {"lru", "ctm_plus"}:
        raise NotImplementedError(
            f"Mode B currently supports policy_name in {{'lru', 'ctm_plus'}}; "
            f"got {policy_name!r}. FIFO baseline requires a separate "
            f"vLLM block-manager patch (not yet implemented)."
        )

    logger.info("instantiating vLLM with model=%s", model)
    engine = LLM(
        model=model,
        gpu_memory_utilization=gpu_memory_utilization,
        swap_space=swap_space_gb,
        enforce_eager=enforce_eager,
        enable_prefix_caching=False,  # isolate eviction effect
        seed=seed,
    )

    if policy_name == "ctm_plus":
        patch_vllm_engine = _import_ctm_evictor()
        # Either succeeds (vLLM <= 0.6) or raises NotImplementedError
        # with a clear message (vLLM >= 0.7). Either way the user
        # gets unambiguous signal — no silent "patch installed but
        # actually doing nothing" behaviour.
        patch_vllm_engine(engine.llm_engine, enable_logging=False)
        logger.info("patched vLLM engine with CTM+ evictor")

    # Compute the bytes-per-block constant for counter conversion.
    # vLLM exposes block_size (tokens/block) and the model config
    # gives us the per-token KV size; we estimate the per-block KV
    # bytes from these. The estimate is rough — bf16 + GQA assumed.
    block_size_bytes = _estimate_block_bytes(engine, model)

    if dry_run:
        logger.info(
            "dry-run: skipping generation; reporting only the "
            "patch-installation result + counter-source detection"
        )
        counters = _extract_vllm_tier_counters(
            engine.llm_engine, block_size_bytes=block_size_bytes
        )
        return RunResult(
            workload_name=f"{spec.name}_dryrun",
            policy_name=policy_name,
            tier_config_name=tier_config_name,
            n_decode_tokens=0,
            bytes_read=counters["bytes_read"],
            bytes_written=counters["bytes_written"],
            accesses_served=counters["accesses_served"],
            cumulative_latency_ns=counters["cumulative_latency_ns"],
            evictions_to_tier=counters["evictions_to_tier"],
            hbm_hit_rate=0.0,
            slow_tier_bytes_per_decode_token=0.0,
            avg_access_latency_ns=0.0,
            wall_clock_seconds=0.0,
            seed=seed,
            counter_source=counters.get("counter_source", ""),
        )

    tokenizer = engine.get_tokenizer()
    requests = workload_to_vllm_requests(spec, tokenizer=tokenizer)
    sampling = SamplingParams(
        temperature=0.0,             # deterministic
        max_tokens=requests[0].max_decode_tokens,
        seed=seed,
    )

    wall_start = time.perf_counter()
    outputs = engine.generate(
        prompts=[r.prompt for r in requests],
        sampling_params=sampling,
    )
    wall_end = time.perf_counter()

    # Pull per-tier counters from vLLM's actual public API
    # (CpuGpuBlockAllocator.get_and_reset_swaps for vLLM 0.7+).
    # See _extract_vllm_tier_counters for the version-detection
    # logic + the counter_source field that documents what was
    # actually measured vs. left at zero.
    counters = _extract_vllm_tier_counters(
        engine.llm_engine, block_size_bytes=block_size_bytes
    )

    n_decode_tokens = sum(
        len(out.outputs[0].token_ids) for out in outputs
    )
    total_accesses = sum(counters.get("accesses_served", {}).values())
    hbm_hits = counters.get("accesses_served", {}).get("HBM", 0)
    hbm_hit_rate = hbm_hits / total_accesses if total_accesses else 0.0
    slow_tier_total_bytes = sum(
        counters.get("bytes_read", {}).get(name, 0)
        for name in ("DDR", "NVMe", "HBF")
    )
    slow_tier_per_token = (
        slow_tier_total_bytes / n_decode_tokens if n_decode_tokens else 0.0
    )
    cumulative_latency = sum(
        counters.get("cumulative_latency_ns", {}).values()
    )
    avg_latency = (
        cumulative_latency / total_accesses if total_accesses else 0.0
    )

    return RunResult(
        workload_name=spec.name,
        policy_name=policy_name,
        tier_config_name=tier_config_name,
        n_decode_tokens=n_decode_tokens,
        bytes_read=counters.get("bytes_read", {}),
        bytes_written=counters.get("bytes_written", {}),
        accesses_served=counters.get("accesses_served", {}),
        cumulative_latency_ns=counters.get("cumulative_latency_ns", {}),
        evictions_to_tier=counters.get("evictions_to_tier", {}),
        hbm_hit_rate=hbm_hit_rate,
        slow_tier_bytes_per_decode_token=slow_tier_per_token,
        avg_access_latency_ns=avg_latency,
        wall_clock_seconds=wall_end - wall_start,
        seed=seed,
        counter_source=counters.get("counter_source", ""),
    )


def _extract_vllm_tier_counters(
    llm_engine: Any,
    *,
    block_size_bytes: int = 0,
) -> Dict[str, Any]:
    """Best-effort extraction of per-tier counters from vLLM.

    vLLM 0.7+ exposes block-swap operations via the
    ``CpuGpuBlockAllocator.get_and_reset_swaps()`` method on the
    block manager's ``block_allocator``. We snapshot the count of
    swaps that occurred during the run and convert to bytes using
    the engine's configured block size + dtype.

    For vLLM ≤ 0.6.x (older ``BlockSpaceManagerV1``), there is no
    public swap-counter API and we fall back to zero counters
    with a documented limitation.

    The downstream :class:`RunResult` honestly reports any gaps
    via zero-valued counters rather than fabricating numbers, and
    sets ``mode_b_counter_source`` to a string explaining what
    was actually measured.
    """
    bytes_read: Dict[str, int] = {"HBM": 0, "DDR": 0, "NVMe": 0}
    bytes_written: Dict[str, int] = {"HBM": 0, "DDR": 0, "NVMe": 0}
    accesses_served: Dict[str, int] = {"HBM": 0, "DDR": 0, "NVMe": 0}
    cumulative_latency_ns: Dict[str, float] = {
        "HBM": 0.0, "DDR": 0.0, "NVMe": 0.0,
    }
    evictions_to_tier: Dict[str, int] = {"HBM": 0, "DDR": 0, "NVMe": 0}
    counter_source = "unavailable"

    scheduler = getattr(llm_engine, "scheduler", None) or getattr(
        llm_engine, "_scheduler", None
    )
    if scheduler is None:
        return _wrap_counters(
            bytes_read, bytes_written, accesses_served,
            cumulative_latency_ns, evictions_to_tier, counter_source,
        )
    if isinstance(scheduler, list) and scheduler:
        scheduler = scheduler[0]
    block_manager = getattr(scheduler, "block_manager", None)
    if block_manager is None:
        return _wrap_counters(
            bytes_read, bytes_written, accesses_served,
            cumulative_latency_ns, evictions_to_tier, counter_source,
        )

    # vLLM 0.7+: CpuGpuBlockAllocator on block_allocator.
    block_allocator = getattr(block_manager, "block_allocator", None)
    if block_allocator is not None and hasattr(
        block_allocator, "get_and_reset_swaps"
    ):
        try:
            swaps = block_allocator.get_and_reset_swaps()
        except Exception:
            swaps = None
        # swaps is an iterable of (src_block_id, dst_block_id) pairs
        # where the direction of swap depends on the call context. We
        # treat each swap as one "block touched at the slow tier" and
        # use the engine's block_size + dtype to convert to bytes.
        if swaps is not None:
            try:
                n_swaps = len(swaps) if hasattr(swaps, "__len__") else sum(
                    1 for _ in swaps
                )
            except TypeError:
                n_swaps = 0
            if block_size_bytes > 0 and n_swaps > 0:
                # vLLM's swap moves blocks from GPU → CPU on
                # eviction and CPU → GPU on re-access. We can't tell
                # the direction from the (src, dst) pair alone
                # without device-side context, so we attribute all
                # swaps to "DDR" (CPU pinned memory) for the purpose
                # of slow-tier traffic accounting. This matches the
                # Mode A "spill goes to tier 1" convention.
                slow_bytes = n_swaps * block_size_bytes
                bytes_read["DDR"] = slow_bytes
                evictions_to_tier["DDR"] = n_swaps
                accesses_served["DDR"] = n_swaps
                counter_source = "vllm_0_7_block_allocator_swaps"
            elif n_swaps == 0:
                counter_source = "vllm_0_7_no_swaps_observed"

    # vLLM ≤ 0.6.x fallback: gpu_allocator path. No reliable swap
    # counter; just record the source as "legacy_no_data".
    elif hasattr(block_manager, "gpu_allocator"):
        counter_source = "vllm_0_6_gpu_allocator_no_counter"

    return _wrap_counters(
        bytes_read, bytes_written, accesses_served,
        cumulative_latency_ns, evictions_to_tier, counter_source,
    )


def _estimate_block_bytes(engine: Any, model_name: str) -> int:
    """Estimate KV bytes per block from the engine + model config.

    The estimate is per_token = layers * kv_heads * head_dim * 2
    (bf16) for one layer's K + one layer's V, then * block_size
    tokens. Uses vLLM's loaded config when available; falls back
    to a 256 KiB-per-block default if attributes aren't found
    (better than 0, won't be far off for 7-13B GQA models).
    """
    fallback = 256 * 1024
    try:
        cfg = engine.llm_engine.model_config.hf_config
        layers = getattr(cfg, "num_hidden_layers", 0)
        kv_heads = getattr(cfg, "num_key_value_heads", None) or getattr(
            cfg, "num_attention_heads", 0
        )
        head_dim = getattr(cfg, "head_dim", 0) or (
            getattr(cfg, "hidden_size", 0) // max(
                getattr(cfg, "num_attention_heads", 1), 1
            )
        )
        block_size = (
            engine.llm_engine.cache_config.block_size
            if hasattr(engine, "llm_engine")
            else 16
        )
        if layers and kv_heads and head_dim and block_size:
            # K + V × bf16 × layers × kv_heads × head_dim × block_size
            return 2 * 2 * layers * kv_heads * head_dim * block_size
    except (AttributeError, TypeError):
        pass
    return fallback


def _wrap_counters(
    bytes_read, bytes_written, accesses_served,
    cumulative_latency_ns, evictions_to_tier, counter_source,
) -> Dict[str, Any]:
    return {
        "bytes_read": bytes_read,
        "bytes_written": bytes_written,
        "accesses_served": accesses_served,
        "cumulative_latency_ns": cumulative_latency_ns,
        "evictions_to_tier": evictions_to_tier,
        "counter_source": counter_source,
    }


# ---------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------- #


_WORKLOADS = {
    "agentic_64k": AGENTIC_64K,
    "agentic_clustered_64k": AGENTIC_CLUSTERED_64K,
    "rag_128k": RAG_128K,
    "chat_32k": CHAT_32K,
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ctm_bench.runner_vllm",
        description=(
            "Mode B — real-model benchmark via vLLM. Requires GPU + "
            "vLLM installed. See module docstring for usage."
        ),
    )
    p.add_argument("--model", required=True, type=str)
    p.add_argument(
        "--workload",
        required=True,
        type=str,
        choices=sorted(_WORKLOADS.keys()),
    )
    p.add_argument(
        "--policy",
        required=True,
        type=str,
        choices=["lru", "ctm_plus"],
    )
    p.add_argument("--gpu-memory-utilization", type=float, default=0.30)
    p.add_argument("--swap-space", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output-dir", type=str, default="")
    p.add_argument(
        "--enforce-eager",
        action="store_true",
        default=True,
        help="Disable CUDA graphs so per-step latency is observable.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Skip generation; only exercise the model load + CTM+ "
            "patch-install path. Useful for catching vLLM API drift "
            "(e.g. UnboundLocalError, missing attributes) cheaply "
            "before a full GPU sweep. Reports the counter_source "
            "string so you know what would be measured in a real run."
        ),
    )
    return p


def main(argv: List[str]) -> int:
    args = _build_parser().parse_args(argv)
    spec = _WORKLOADS[args.workload]
    result = run_vllm(
        spec,
        args.policy,
        model=args.model,
        gpu_memory_utilization=args.gpu_memory_utilization,
        swap_space_gb=args.swap_space,
        enforce_eager=args.enforce_eager,
        seed=args.seed,
        dry_run=args.dry_run,
    )
    print(
        f"workload={spec.name} policy={args.policy} "
        f"hbm_hit={result.hbm_hit_rate*100:.1f}% "
        f"slow_tier_B/tok={result.slow_tier_bytes_per_decode_token:,.0f} "
        f"wall={result.wall_clock_seconds:.2f}s"
    )

    if args.output_dir:
        from pathlib import Path

        from ctm_bench.metrics import to_json

        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "vllm_summary.json").write_text(
            to_json({"cells": [result.to_dict()], "pairs": []}) + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
