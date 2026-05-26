"""Phase 4B — three-cell Extended Pinning bench driver.

Runs three streaming-mode cells against the same shared-prefix
chat workload and emits a comparison JSON for Phase 4D decision
analysis:

| Cell | ``enable_prefix_caching`` | ``extended_pinning`` | Role                  |
|------|---------------------------|----------------------|-----------------------|
| A    | OFF                       | OFF                  | sanity / throughput floor |
| B    | ON                        | OFF                  | stock vLLM (the realistic competitor) |
| C    | ON                        | ON                   | the proposal           |

The load-bearing comparison is **B vs C**: both have prefix caching
on; the only difference is whether the cache layer is augmented
with deterministic eviction-protection on configured prefixes.

The script is runnable in two modes:

* ``--dry-run``: uses an internal CPU-only mock vLLM module
  (no real model, no GPU). Used by
  ``test_bench_phase4_extended_pinning.py`` to gate the
  orchestration before any GPU spend.
* (default GPU mode): imports the real ``vllm`` and runs against
  an actual ``AsyncLLMEngine``. Intended for Phase 4C on an H100.

Per-cell artifacts:

    <output_dir>/cell_A/streaming_summary.json
    <output_dir>/cell_B/streaming_summary.json
    <output_dir>/cell_C/streaming_summary.json
    <output_dir>/comparison.json

Discipline (durable):
  * No ``Int4ProtectedAttentionImpl`` touched (AST gate in tests).
  * No kernel paths touched.
  * No Phase 4 Tier B work.
  * No VC brief edits.
  * No claim about pinning winning — this script PRODUCES the
    measurement; Phase 4D INTERPRETS it.
"""

from __future__ import annotations

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()

import argparse
import asyncio
import collections
import dataclasses
import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- #
# Cell configuration
# ---------------------------------------------------------------- #


@dataclasses.dataclass(frozen=True)
class CellConfig:
    """Static config for one Phase 4B cell."""
    name: str
    enable_prefix_caching: bool
    extended_pinning: bool
    pin_first_n_blocks: int = 0


CELLS: Dict[str, CellConfig] = {
    "A": CellConfig(
        name="A_prefix_off_pinning_off",
        enable_prefix_caching=False,
        extended_pinning=False,
        pin_first_n_blocks=0,
    ),
    "B": CellConfig(
        name="B_prefix_on_pinning_off",
        enable_prefix_caching=True,
        extended_pinning=False,
        pin_first_n_blocks=0,
    ),
    "C": CellConfig(
        name="C_prefix_on_pinning_on",
        enable_prefix_caching=True,
        extended_pinning=True,
        # Default to position-based pinning of 4 blocks
        # (128 tokens at block_size=32) — covers the first
        # 4 cohort prefix blocks of every admission.
        pin_first_n_blocks=4,
    ),
}


# ---------------------------------------------------------------- #
# Per-cell metrics extraction
# ---------------------------------------------------------------- #


def extract_cell_metrics(
    *, result: Any, cell: CellConfig,
) -> Dict[str, Any]:
    """Project StreamingRunCellResult onto the Phase 4B per-cell schema.

    Surfaces the extended_pinning_stats fields the user requested:
      pinned_blocks_total, pinned_evictions_avoided,
      forced_pin_evictions, pin_budget_rejections,
      pinned_memory_overhead_bytes, evictor_path_taken.
    """
    pin_stats = dict(
        getattr(result, "extended_pinning_stats", {}) or {}
    )
    pinning_enabled = bool(pin_stats.get("enabled", False))

    return {
        "cell_name": cell.name,
        "config": {
            "enable_prefix_caching": cell.enable_prefix_caching,
            "extended_pinning": cell.extended_pinning,
            "pin_first_n_blocks": cell.pin_first_n_blocks,
        },
        "n_requests_admitted": int(result.n_requests_admitted),
        "n_requests_completed": int(result.n_requests_completed),
        "n_decode_tokens": int(result.n_decode_tokens),
        "tokens_per_second": float(result.tokens_per_second),
        "wall_clock_seconds": float(result.wall_clock_seconds),
        "ttft_p50_ms": float(result.ttft_p50_ms),
        "ttft_p99_ms": float(result.ttft_p99_ms),
        "e2e_p50_ms": float(result.e2e_p50_ms),
        "e2e_p99_ms": float(result.e2e_p99_ms),
        "prompt_builder_name": getattr(
            result, "prompt_builder_name", "pareto_unique_head",
        ),
        # User-required pinning fields.
        "extended_pinning_stats": pin_stats,
        "pinned_blocks_total": int(
            pin_stats.get("pinned_blocks_total", 0)
        ),
        "pinned_evictions_avoided": int(
            pin_stats.get("pinned_evictions_avoided", 0)
        ),
        "forced_pin_evictions": int(
            pin_stats.get("forced_pin_evictions", 0)
        ),
        "pin_budget_rejections": int(
            pin_stats.get("pin_budget_rejections", 0)
        ),
        "pinned_memory_overhead_bytes": int(
            pin_stats.get("pinned_memory_overhead_bytes", 0)
        ),
        "evictor_path_taken": pin_stats.get(
            "evictor_path_taken", "n/a",
        ) if pinning_enabled else "n/a",
    }


# ---------------------------------------------------------------- #
# Comparison block
# ---------------------------------------------------------------- #


def _ratio(numer: float, denom: float) -> Optional[float]:
    if denom == 0:
        return None
    return float(numer) / float(denom)


def build_comparison(
    *,
    cells: Dict[str, Dict[str, Any]],
    workload: Dict[str, Any],
    seed: int,
) -> Dict[str, Any]:
    """Build the Phase 4B comparison JSON."""
    out: Dict[str, Any] = {
        "phase": "4B",
        "seed": int(seed),
        "workload": dict(workload),
        "cells": cells,
        "comparison": {},
        "warnings": [],
    }

    cell_b = cells.get(CELLS["B"].name)
    cell_c = cells.get(CELLS["C"].name)
    if cell_b is not None and cell_c is not None:
        out["comparison"]["B_vs_C"] = {
            "tokens_per_second_ratio": _ratio(
                cell_c["tokens_per_second"],
                cell_b["tokens_per_second"],
            ),
            "ttft_p99_ratio": _ratio(
                cell_c["ttft_p99_ms"], cell_b["ttft_p99_ms"],
            ),
            "ttft_p50_ratio": _ratio(
                cell_c["ttft_p50_ms"], cell_b["ttft_p50_ms"],
            ),
            "e2e_p99_ratio": _ratio(
                cell_c["e2e_p99_ms"], cell_b["e2e_p99_ms"],
            ),
            "e2e_p50_ratio": _ratio(
                cell_c["e2e_p50_ms"], cell_b["e2e_p50_ms"],
            ),
            "completion_ratio": _ratio(
                cell_c["n_requests_completed"],
                cell_b["n_requests_completed"],
            ),
            # C-only enrichment: how much eviction protection
            # actually fired? Surfaced for the Phase 4D decision.
            "c_pinned_evictions_avoided": int(
                cell_c.get("pinned_evictions_avoided", 0)
            ),
            "c_forced_pin_evictions": int(
                cell_c.get("forced_pin_evictions", 0)
            ),
            "c_pinned_blocks_total": int(
                cell_c.get("pinned_blocks_total", 0)
            ),
        }

    # Per-cell warnings.
    for cell_dict in cells.values():
        cell_name = cell_dict["cell_name"]
        cfg = cell_dict["config"]
        if (
            cfg["extended_pinning"]
            and cell_dict["evictor_path_taken"] == "no_known_path"
        ):
            out["warnings"].append(
                f"cell {cell_name}: extended pinning is ON but "
                "the evictor wrap resolved to 'no_known_path' — "
                "running in allocate-wrap-only mode. "
                "pinned_evictions_avoided cannot increment in this "
                "mode. See PHASE4_VLLM_EVICTOR_HOOK_RESEARCH.md "
                "for recovery options."
            )
        if (
            cfg["extended_pinning"]
            and cell_dict["pinned_blocks_total"] == 0
            and cell_dict["n_requests_admitted"] > 0
        ):
            out["warnings"].append(
                f"cell {cell_name}: extended pinning is ON and "
                f"{cell_dict['n_requests_admitted']} requests "
                "admitted, but pinned_blocks_total=0. Either no "
                "PinSpec was configured (check --pin-first-n-blocks "
                "and --pin-tokens-file) or the spec didn't match "
                "any admitted prompts."
            )
        if (
            cfg["extended_pinning"]
            and cell_dict["forced_pin_evictions"] > 0
        ):
            out["warnings"].append(
                f"cell {cell_name}: forced_pin_evictions="
                f"{cell_dict['forced_pin_evictions']}. The pinned "
                "set saturates the free pool under memory pressure; "
                "reduce --pin-first-n-blocks or --pin-max-budget-blocks."
            )

    return out


# ---------------------------------------------------------------- #
# Per-cell driver
# ---------------------------------------------------------------- #


async def run_one_cell(
    *,
    cell: CellConfig,
    model: str,
    shared_prefix_length: int,
    n_shared_prefixes: int,
    unique_tail_choices: Sequence[int],
    n_requests: int,
    arrival_rate: float,
    arrival_alpha: float,
    max_wall_seconds: float,
    max_decode_tokens: int,
    gpu_memory_utilization: float,
    swap_space_gb: int,
    seed: int,
    sample_interval_seconds: float,
    pin_max_budget_blocks: int,
    vllm_module: Any,
    output_dir: Optional[Path] = None,
) -> Any:
    """Run a single Phase 4B cell. Returns the
    ``StreamingRunCellResult``."""
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver,
        ArrivalScheduler,
        ParetoArrivalConfig,
        SwapCounterSampler,
    )

    driver = AsyncEngineDriver(
        model=model,
        gpu_memory_utilization=gpu_memory_utilization,
        swap_space_gb=swap_space_gb,
        seed=seed,
        enable_prefix_caching=cell.enable_prefix_caching,
        shared_prefix_length=shared_prefix_length,
        shared_prefix_unique_tail_choices=list(unique_tail_choices),
        n_shared_prefixes=n_shared_prefixes,
        extended_pinning=cell.extended_pinning,
        pin_first_n_blocks=cell.pin_first_n_blocks,
        pin_max_budget_blocks=pin_max_budget_blocks,
        max_decode_tokens=max_decode_tokens,
        sample_interval_seconds=sample_interval_seconds,
        vllm_module=vllm_module,
    )

    arrival = ArrivalScheduler(
        seed=seed,
        pareto=ParetoArrivalConfig(
            base_rate_per_sec=arrival_rate, alpha=arrival_alpha,
        ),
    )
    sampler = SwapCounterSampler()

    result = await driver.run(
        scheduler=arrival,
        sampler=sampler,
        max_requests=n_requests,
        max_wall_seconds=max_wall_seconds,
        workload_name=cell.name,
    )

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "streaming_summary.json").write_text(
            json.dumps(asdict(result), indent=2, sort_keys=True),
        )

    return result


# ---------------------------------------------------------------- #
# Three-cell orchestrator
# ---------------------------------------------------------------- #


async def run_three_cells(
    *,
    model: str,
    shared_prefix_length: int,
    n_shared_prefixes: int,
    unique_tail_choices: Sequence[int],
    n_requests: int,
    arrival_rate: float,
    arrival_alpha: float,
    max_wall_seconds: float,
    max_decode_tokens: int,
    gpu_memory_utilization: float,
    swap_space_gb: int,
    seed: int,
    sample_interval_seconds: float,
    pin_max_budget_blocks: int,
    vllm_module_factory: Any,
    cells_to_run: Sequence[str],
    output_dir: Optional[Path] = None,
    pin_first_n_blocks_override: Optional[int] = None,
) -> Dict[str, Any]:
    """Run cells sequentially; aggregate into comparison JSON.

    ``pin_first_n_blocks_override``: when not None, overrides
    cell C's compiled-in ``pin_first_n_blocks`` for this run.
    Other cells are not affected (they have pinning OFF).
    """
    cells_out: Dict[str, Dict[str, Any]] = {}
    workload = {
        "model": model,
        "shared_prefix_length": shared_prefix_length,
        "n_shared_prefixes": n_shared_prefixes,
        "unique_tail_choices": list(unique_tail_choices),
        "n_requests": n_requests,
        "arrival_rate": arrival_rate,
        "arrival_alpha": arrival_alpha,
        "max_wall_seconds": max_wall_seconds,
        "max_decode_tokens": max_decode_tokens,
        "gpu_memory_utilization": gpu_memory_utilization,
        "seed": seed,
        "pin_max_budget_blocks": pin_max_budget_blocks,
        "pin_first_n_blocks_override": pin_first_n_blocks_override,
    }

    for cell_key in cells_to_run:
        if cell_key not in CELLS:
            raise ValueError(
                f"unknown cell key {cell_key!r}; expected one of A, B, C"
            )
        cell = CELLS[cell_key]
        # Apply CLI override to cell C's pin_first_n_blocks if set.
        if (
            pin_first_n_blocks_override is not None
            and cell.extended_pinning
        ):
            cell = dataclasses.replace(
                cell, pin_first_n_blocks=pin_first_n_blocks_override,
            )
        cell_dir = output_dir / f"cell_{cell_key}" if output_dir else None
        logger.info(
            "Phase 4B: running cell %s (%s)", cell_key, cell.name,
        )
        vllm_module = vllm_module_factory(cell=cell)
        cell_start = time.perf_counter()
        result = await run_one_cell(
            cell=cell,
            model=model,
            shared_prefix_length=shared_prefix_length,
            n_shared_prefixes=n_shared_prefixes,
            unique_tail_choices=unique_tail_choices,
            n_requests=n_requests,
            arrival_rate=arrival_rate,
            arrival_alpha=arrival_alpha,
            max_wall_seconds=max_wall_seconds,
            max_decode_tokens=max_decode_tokens,
            gpu_memory_utilization=gpu_memory_utilization,
            swap_space_gb=swap_space_gb,
            seed=seed,
            sample_interval_seconds=sample_interval_seconds,
            pin_max_budget_blocks=pin_max_budget_blocks,
            vllm_module=vllm_module,
            output_dir=cell_dir,
        )
        cell_elapsed = time.perf_counter() - cell_start
        logger.info(
            "Phase 4B: cell %s done in %.2fs "
            "(completed=%d, decode_tokens=%d, tps=%.1f)",
            cell_key, cell_elapsed,
            result.n_requests_completed,
            result.n_decode_tokens,
            result.tokens_per_second,
        )
        cells_out[cell.name] = extract_cell_metrics(
            result=result, cell=cell,
        )

    comparison = build_comparison(
        cells=cells_out, workload=workload, seed=seed,
    )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "comparison.json").write_text(
            json.dumps(comparison, indent=2, sort_keys=True),
        )
    return comparison


# ---------------------------------------------------------------- #
# Dry-run mock vLLM
#
# Same V2 block_allocator shape as bench_phase3_cache_aware.py's
# mock, plus an LRUEvictor stub with ``free_table`` so the
# extended-pinning evictor wrap can resolve a path.
# ---------------------------------------------------------------- #


class _DryRunOutputItem:
    def __init__(self, token_ids: List[int]):
        self.token_ids = token_ids


class _DryRunOutput:
    def __init__(self, token_ids: List[int]):
        self.outputs = [_DryRunOutputItem(token_ids)]


class _DryRunLRUEvictor:
    """Mimics vLLM's LRUEvictor — has ``free_table`` dict and
    ``evict()`` that pops the LRU-most entry."""

    def __init__(self) -> None:
        self.free_table: Dict[int, Any] = {}
        self.evict_call_count: int = 0

    def evict(self):
        self.evict_call_count += 1
        if not self.free_table:
            raise RuntimeError("evictor.free_table empty")
        block_id = next(iter(self.free_table))
        meta = self.free_table.pop(block_id)
        return (block_id, meta)


class _DryRunPrefixCachingAllocator:
    """Mimics PrefixCachingBlockAllocator with both
    ``_cached_blocks`` (for the prefix-hit probe — Phase 3A) and
    ``evictor`` (for the extended-pinning evictor wrap — Phase 4B)."""

    def __init__(self) -> None:
        self._cached_blocks: Dict[int, Any] = {}
        self.evictor = _DryRunLRUEvictor()


class _DryRunNonCachingAllocator:
    """No _cached_blocks and no evictor — probe + pinning resolve
    to no_known_path."""
    pass


class _DryRunCpuGpuBlockAllocator:
    def __init__(self, *, enable_prefix_caching: bool):
        if enable_prefix_caching:
            self.gpu_allocator: Any = _DryRunPrefixCachingAllocator()
        else:
            self.gpu_allocator = _DryRunNonCachingAllocator()


class _DryRunBlockManager:
    def __init__(self, *, enable_prefix_caching: bool, block_size: int = 32):
        self.block_size = block_size
        self._enable_prefix_caching = enable_prefix_caching
        self.block_allocator = _DryRunCpuGpuBlockAllocator(
            enable_prefix_caching=enable_prefix_caching,
        )
        self.block_tables: Dict[int, List[Any]] = {}
        self._next_block_number: int = 1

    def _seq_id_of(self, seq_or_group: Any) -> Any:
        get_seqs = getattr(seq_or_group, "get_seqs", None)
        if callable(get_seqs):
            seqs = get_seqs()
            if seqs:
                return getattr(seqs[0], "seq_id", id(seqs[0]))
        return getattr(seq_or_group, "seq_id", id(seq_or_group))

    def _tokens_of(self, seq_group: Any) -> List[int]:
        get_seqs = getattr(seq_group, "get_seqs", None)
        if callable(get_seqs):
            seqs = get_seqs()
            if seqs:
                get_ids = getattr(seqs[0], "get_prompt_token_ids", None)
                if callable(get_ids):
                    return list(get_ids())
        return []

    def allocate(self, seq_group: Any) -> None:
        seq_id = self._seq_id_of(seq_group)
        tokens = self._tokens_of(seq_group)
        n_full_blocks = max(1, len(tokens) // self.block_size)
        block_numbers: List[int] = []
        for _ in range(n_full_blocks):
            bn = self._next_block_number
            self._next_block_number += 1
            block_numbers.append(bn)
        # If prefix caching is on, populate _cached_blocks
        # (Phase 3A probe relies on this) AND seed the evictor's
        # free pool with these blocks so the pinning evictor wrap
        # has something non-trivial to observe.
        if self._enable_prefix_caching:
            from kv_policy.prefix_hit_probe import _content_hash_of_chunk
            for i, bn in enumerate(block_numbers):
                chunk = tokens[i * self.block_size : (i + 1) * self.block_size]
                if chunk:
                    h = _content_hash_of_chunk(chunk)
                    self.block_allocator.gpu_allocator._cached_blocks[h] = (
                        object()
                    )
                # Drop the block into the LRU evictor's free pool
                # (in real vLLM this happens when ref_count drops to
                # 0 — we simulate it here so the pinning evictor
                # wrap can be exercised by the dry-run).
                evictor = getattr(
                    self.block_allocator.gpu_allocator, "evictor", None,
                )
                if evictor is not None:
                    evictor.free_table[bn] = f"block_{bn}_metadata"
        self.block_tables[seq_id] = [
            type("_MockBlock", (), {"block_number": bn})()
            for bn in block_numbers
        ]

    def free(self, seq_or_seq_group: Any) -> None:
        seq_id = self._seq_id_of(seq_or_seq_group)
        self.block_tables.pop(seq_id, None)


class _DryRunScheduler:
    def __init__(self, *, enable_prefix_caching: bool):
        self.waiting: "collections.deque[Any]" = collections.deque()
        self.block_manager = _DryRunBlockManager(
            enable_prefix_caching=enable_prefix_caching,
        )

    def schedule(self) -> List[Any]:
        admitted = []
        while self.waiting:
            admitted.append(self.waiting.popleft())
        return admitted


class _DryRunInnerEngine:
    def __init__(self, *, enable_prefix_caching: bool):
        self.scheduler = [
            _DryRunScheduler(enable_prefix_caching=enable_prefix_caching),
        ]


class _DryRunSequence:
    def __init__(self, seq_id: int, prompt_token_ids: List[int]):
        self.seq_id = seq_id
        self._prompt = list(prompt_token_ids)

    def get_prompt_token_ids(self) -> List[int]:
        return list(self._prompt)


class _DryRunSequenceGroup:
    def __init__(self, *, request_id: str, arrival_time: float,
                 seqs: List[_DryRunSequence]):
        self.request_id = request_id
        self.arrival_time = arrival_time
        self._seqs = seqs

    def get_seqs(self) -> List[_DryRunSequence]:
        return list(self._seqs)


class _DryRunAsyncEngine:
    def __init__(self, *, enable_prefix_caching: bool):
        self.engine = _DryRunInnerEngine(
            enable_prefix_caching=enable_prefix_caching,
        )
        self.shutdown_calls = 0
        self._n_decode_per_request = 4

    async def generate(self, prompt_dict: Any, sp: Any, request_id: str):
        sched = self.engine.scheduler[0]
        prompt_tokens = list(prompt_dict.get("prompt_token_ids", []))
        seq = _DryRunSequence(
            seq_id=hash(request_id) & 0x7FFFFFFF,
            prompt_token_ids=prompt_tokens,
        )
        sg = _DryRunSequenceGroup(
            request_id=request_id, arrival_time=time.monotonic(), seqs=[seq],
        )
        sched.waiting.append(sg)
        admitted = sched.schedule()
        for adm in admitted:
            sched.block_manager.allocate(adm)
        cumulative: List[int] = []
        for tok in range(self._n_decode_per_request):
            await asyncio.sleep(0.001)
            cumulative.append(tok + 1)
            yield _DryRunOutput(list(cumulative))
        sched.block_manager.free(sg)

    def shutdown_background_loop(self) -> None:
        self.shutdown_calls += 1


class _DryRunAsyncEngineArgs:
    def __init__(self, **kwargs: Any):
        self.kwargs = kwargs
        self.enable_prefix_caching = kwargs.get("enable_prefix_caching", False)


class _DryRunAsyncLLMEngineFactory:
    def __init__(self) -> None:
        self.last_engine: Optional[_DryRunAsyncEngine] = None

    def from_engine_args(self, args: _DryRunAsyncEngineArgs):
        engine = _DryRunAsyncEngine(
            enable_prefix_caching=args.enable_prefix_caching,
        )
        self.last_engine = engine
        return engine


class _DryRunSamplingParams:
    def __init__(self, **kwargs: Any):
        self.kwargs = kwargs


class _DryRunVLLM:
    """Phase 4B dry-run vLLM module stand-in."""

    def __init__(self) -> None:
        self._factory = _DryRunAsyncLLMEngineFactory()
        self.AsyncLLMEngine = self._factory
        self.AsyncEngineArgs = _DryRunAsyncEngineArgs
        self.SamplingParams = _DryRunSamplingParams


def make_dry_run_vllm_module_factory():
    """Factory function for ``run_three_cells(vllm_module_factory=...)``
    that constructs a fresh ``_DryRunVLLM`` per cell."""

    def factory(*, cell: CellConfig) -> _DryRunVLLM:
        del cell
        return _DryRunVLLM()

    return factory


def make_real_vllm_module_factory():
    """Factory function that imports the real vllm module."""
    try:
        import vllm  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Real-mode Phase 4B requires vLLM. Install with "
            "`pip install vllm`. For CPU dry-run, pass --dry-run."
        ) from exc

    def factory(*, cell: CellConfig) -> Any:
        del cell
        return vllm

    return factory


# ---------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------- #


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="bench_phase4_extended_pinning",
        description=(
            "Phase 4B — three-cell Extended Pinning bench. "
            "Runs cells A (prefix off, pinning off), B (prefix "
            "on, pinning off), C (prefix on, pinning on) and "
            "emits comparison.json. Use --dry-run for CPU-only "
            "orchestration verification before GPU spend."
        ),
    )
    parser.add_argument(
        "--model", default="Qwen/Qwen2.5-7B-Instruct",
    )
    parser.add_argument(
        "--shared-prefix-length", type=int, default=256,
    )
    parser.add_argument(
        "--n-shared-prefixes", type=int, default=4,
    )
    parser.add_argument(
        "--shared-prefix-unique-tail-choices",
        default="32,64,128,256",
    )
    parser.add_argument(
        "--n-requests", type=int, default=100,
    )
    parser.add_argument(
        "--arrival-rate", type=float, default=4.0,
    )
    parser.add_argument(
        "--arrival-alpha", type=float, default=1.5,
    )
    parser.add_argument(
        "--max-wall-seconds", type=float, default=60.0,
    )
    parser.add_argument(
        "--max-decode-tokens", type=int, default=32,
    )
    parser.add_argument(
        "--gpu-memory-utilization", type=float, default=0.5,
    )
    parser.add_argument(
        "--swap-space-gb", type=int, default=8,
    )
    parser.add_argument(
        "--seed", type=int, default=42,
    )
    parser.add_argument(
        "--sample-interval-seconds", type=float, default=0.1,
    )
    parser.add_argument(
        "--pin-first-n-blocks", type=int, default=None,
        help=(
            "Override cell C's first_n_blocks_per_request pinning "
            "value. Default is the cell's compiled-in value "
            "(currently 4). Set higher to pin more of each "
            "request's prefix; set 0 to disable position-based "
            "pinning entirely (operator would then need to wire "
            "PinSpecs via a tokens file — not currently exposed "
            "by this bench script)."
        ),
    )
    parser.add_argument(
        "--pin-max-budget-blocks", type=int, default=1024,
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True,
    )
    parser.add_argument(
        "--cells", default="A,B,C",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cells_to_run = [s.strip() for s in args.cells.split(",") if s.strip()]
    for c in cells_to_run:
        if c not in CELLS:
            print(
                f"unknown cell {c!r}; expected one of A, B, C",
                file=sys.stderr,
            )
            return 2

    tail_choices = [
        int(s.strip())
        for s in args.shared_prefix_unique_tail_choices.split(",")
        if s.strip()
    ]
    if not tail_choices:
        print(
            "--shared-prefix-unique-tail-choices must list at least one length",
            file=sys.stderr,
        )
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        factory = make_dry_run_vllm_module_factory()
    else:
        factory = make_real_vllm_module_factory()

    comparison = asyncio.new_event_loop().run_until_complete(
        run_three_cells(
            model=args.model,
            shared_prefix_length=args.shared_prefix_length,
            n_shared_prefixes=args.n_shared_prefixes,
            unique_tail_choices=tail_choices,
            n_requests=args.n_requests,
            arrival_rate=args.arrival_rate,
            arrival_alpha=args.arrival_alpha,
            max_wall_seconds=args.max_wall_seconds,
            max_decode_tokens=args.max_decode_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
            swap_space_gb=args.swap_space_gb,
            seed=args.seed,
            sample_interval_seconds=args.sample_interval_seconds,
            pin_max_budget_blocks=args.pin_max_budget_blocks,
            vllm_module_factory=factory,
            cells_to_run=cells_to_run,
            output_dir=args.output_dir,
            pin_first_n_blocks_override=args.pin_first_n_blocks,
        )
    )

    print(
        "Phase 4B comparison written to "
        f"{args.output_dir / 'comparison.json'}"
    )
    bvc = comparison.get("comparison", {}).get("B_vs_C")
    if bvc is not None:
        print(
            "B_vs_C: "
            f"tps_ratio={bvc.get('tokens_per_second_ratio')!r}, "
            f"ttft_p99_ratio={bvc.get('ttft_p99_ratio')!r}, "
            f"e2e_p99_ratio={bvc.get('e2e_p99_ratio')!r}, "
            f"c_pinned_blocks={bvc.get('c_pinned_blocks_total')}, "
            f"c_pinned_evictions_avoided={bvc.get('c_pinned_evictions_avoided')}"
        )
    if comparison.get("warnings"):
        print("Warnings:")
        for w in comparison["warnings"]:
            print(f"  * {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
