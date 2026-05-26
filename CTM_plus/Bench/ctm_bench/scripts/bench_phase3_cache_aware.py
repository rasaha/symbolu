"""Phase 3B — three-cell cache-aware-vs-FCFS bench driver.

Runs three streaming-mode cells on a shared-prefix chat workload
and emits a comparison JSON for Phase 3D decision analysis:

| Cell | ``enable_prefix_caching`` | ``cache_aware_scheduling`` | Role                  |
|------|---------------------------|----------------------------|-----------------------|
| A    | OFF                       | OFF                        | sanity / throughput floor |
| B    | ON                        | OFF                        | stock vLLM (the realistic competitor) |
| C    | ON                        | ON                         | the proposal           |

The load-bearing comparison is **B vs C**: both have prefix caching
on, the only difference is the cache-aware admission reorder.
Cell A is the no-prefix-caching floor for sanity checking.

The script is runnable in two modes:

* ``--dry-run``: uses an internal CPU-only mock vLLM module. No
  real model, no GPU. Used by ``test_bench_phase3_cache_aware.py``
  to gate orchestration before any GPU spend.
* (default GPU mode): imports the real ``vllm`` and runs against
  an actual ``AsyncLLMEngine``. Intended for Phase 3C on an H100
  pod.

Per-cell artifacts:

    <output_dir>/cell_A/streaming_summary.json   (per-cell driver output)
    <output_dir>/cell_B/streaming_summary.json
    <output_dir>/cell_C/streaming_summary.json
    <output_dir>/comparison.json                 (the aggregate)

The comparison JSON schema is documented in :func:`build_comparison`.

Discipline (durable):
  * No ``Int4ProtectedAttentionImpl`` touched (grep gate in tests).
  * No kernel paths touched (grep gate in tests).
  * No Phase 4 work.
  * No VC brief edits.
  * No claim about cache-aware winning — this script PRODUCES the
    measurement; Phase 3D INTERPRETS it.
"""

from __future__ import annotations

# Self-bootstrap KVPolicy on sys.path so the runner's imports of
# `kv_policy.*` work when launched as `python -m`. Same pattern as
# run_streaming.py.
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
from typing import Any, Dict, List, Optional, Sequence, Tuple


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- #
# Cell configuration — the static spec of A / B / C.
# ---------------------------------------------------------------- #


@dataclasses.dataclass(frozen=True)
class CellConfig:
    """Static config for one Phase 3B cell.

    ``cache_aware_measurement_only=True`` installs the cache-aware
    tree wraps in measurement-only mode (no reorder) so the cell
    surfaces a tree-based realized_hit_tokens_total comparable
    against a full-mode cell C. Cell B uses this to bridge the
    measurement gap created by the prefix-hit probe failing on real
    vLLM 0.7.3 (vLLM uses chained content_hash; our flat probe
    can't match it). See PHASE3_VLLM_NATIVE_PREFIX_HITS_RESEARCH.md.
    """
    name: str
    enable_prefix_caching: bool
    cache_aware_scheduling: bool
    cache_aware_measurement_only: bool = False


CELLS: Dict[str, CellConfig] = {
    "A": CellConfig(
        name="A_prefix_off_cache_aware_off",
        enable_prefix_caching=False,
        cache_aware_scheduling=False,
        cache_aware_measurement_only=False,
    ),
    "B": CellConfig(
        name="B_prefix_on_cache_aware_off",
        enable_prefix_caching=True,
        cache_aware_scheduling=False,
        # Phase 3C measurement bridge: tree wraps fire for hit count;
        # no admission reorder (cell B is stock FCFS by design).
        cache_aware_measurement_only=True,
    ),
    "C": CellConfig(
        name="C_prefix_on_cache_aware_on",
        enable_prefix_caching=True,
        cache_aware_scheduling=True,
        cache_aware_measurement_only=False,
    ),
}


# ---------------------------------------------------------------- #
# Per-cell metrics extraction — maps StreamingRunCellResult into
# the Phase 3B comparison schema. Pure function; takes the
# dataclass + the cell config and emits a JSON-ready dict.
# ---------------------------------------------------------------- #


def extract_cell_metrics(
    *, result: Any, cell: CellConfig,
) -> Dict[str, Any]:
    """Project StreamingRunCellResult onto the Phase 3B per-cell schema.

    realized_hit_tokens_total preference order (Phase 3C fix):
      1. cache_aware tree's realized_hit_tokens_total (full mode or
         measurement-only). Apples-to-apples across cells B and C
         because both install the same tree instrument.
      2. prefix-hit probe's cache_hit_tokens (fallback for cells
         without the tree install, e.g. cell A).

    realized_hit_source flags which instrument supplied the number
    so downstream analysis (Phase 3D) knows which to compare.
    """
    probe = dict(getattr(result, "native_prefix_hit_stats", {}) or {})
    cas = dict(getattr(result, "cache_aware_scheduler_stats", {}) or {})

    if cas.get("enabled"):
        prediction_accuracy = float(cas.get("prediction_accuracy", 0.0))
        reordered_count = int(cas.get("reordered_count", 0))
        starvation_overrides = int(cas.get("starvation_overrides", 0))
        tree_realized = int(cas.get("realized_hit_tokens_total", 0))
        cache_aware_extra: Optional[Dict[str, Any]] = {
            "measurement_only": bool(cas.get("measurement_only", False)),
            "predicted_hit_tokens_total": int(
                cas.get("predicted_hit_tokens_total", 0)
            ),
            "realized_hit_tokens_total_via_tree": tree_realized,
            "tree_inserts": int(cas.get("tree_inserts", 0)),
            "tree_evictions": int(cas.get("tree_evictions", 0)),
            "tree_tracked_tokens": int(cas.get("tree_tracked_tokens", 0)),
            "admissions": int(cas.get("admissions", 0)),
        }
        # Tree is the apples-to-apples instrument when it's installed.
        realized_hit_tokens_total = tree_realized
        realized_hit_source = "cache_aware_tree"
    else:
        prediction_accuracy = 0.0
        reordered_count = 0
        starvation_overrides = 0
        cache_aware_extra = None
        # Fall back to the probe (only meaningful when its
        # path_taken != 'no_known_path').
        realized_hit_tokens_total = int(probe.get("cache_hit_tokens", 0))
        realized_hit_source = "prefix_hit_probe"

    return {
        "cell_name": cell.name,
        "config": {
            "enable_prefix_caching": cell.enable_prefix_caching,
            "cache_aware_scheduling": cell.cache_aware_scheduling,
            "cache_aware_measurement_only": cell.cache_aware_measurement_only,
        },
        "n_requests_admitted": int(result.n_requests_admitted),
        "n_requests_completed": int(result.n_requests_completed),
        "n_decode_tokens": int(result.n_decode_tokens),
        "tokens_per_second": float(result.tokens_per_second),
        "wall_clock_seconds": float(result.wall_clock_seconds),
        "realized_hit_tokens_total": realized_hit_tokens_total,
        "realized_hit_source": realized_hit_source,
        "realized_hit_blocks_total_via_probe": int(
            probe.get("cache_hit_blocks", 0)
        ),
        "prediction_accuracy": prediction_accuracy,
        "reordered_count": reordered_count,
        "starvation_overrides": starvation_overrides,
        "ttft_p50_ms": float(result.ttft_p50_ms),
        "ttft_p99_ms": float(result.ttft_p99_ms),
        "e2e_p50_ms": float(result.e2e_p50_ms),
        "e2e_p99_ms": float(result.e2e_p99_ms),
        "prefix_hit_probe_path_taken": probe.get("path_taken", "no_known_path"),
        "prefix_hit_probe_vllm_version_hint": probe.get(
            "vllm_version_hint", "unknown",
        ),
        "prefix_hit_probe_allocate_calls": int(probe.get("allocate_calls", 0)),
        "prompt_builder_name": getattr(
            result, "prompt_builder_name", "pareto_unique_head",
        ),
        "cache_aware_extra": cache_aware_extra,
    }


# ---------------------------------------------------------------- #
# Comparison block — pairwise ratios + warnings.
# ---------------------------------------------------------------- #


def _ratio(numer: float, denom: float) -> Optional[float]:
    """Return numer/denom, or None when denom is zero (avoid div0
    + signal undefined in the JSON)."""
    if denom == 0:
        return None
    return float(numer) / float(denom)


def build_comparison(
    *,
    cells: Dict[str, Dict[str, Any]],
    workload: Dict[str, Any],
    seed: int,
) -> Dict[str, Any]:
    """Build the Phase 3B comparison JSON from a {name -> metrics} map.

    Schema sketch::

        {
          "phase": "3B",
          "seed": 42,
          "workload": {...},
          "cells": {"A_...": {...}, "B_...": {...}, "C_...": {...}},
          "comparison": {
            "B_vs_C": {
              "realized_hit_tokens_ratio": float | null,
              "realized_hit_tokens_delta": int,
              "tokens_per_second_ratio": float | null,
              "ttft_p99_ratio": float | null,
              "e2e_p99_ratio": float | null,
              "completion_ratio": float | null,
            }
          },
          "warnings": [str, ...],
        }
    """
    out: Dict[str, Any] = {
        "phase": "3B",
        "seed": int(seed),
        "workload": dict(workload),
        "cells": cells,
        "comparison": {},
        "warnings": [],
    }

    # B vs C (the load-bearing comparison).
    cell_b = cells.get(CELLS["B"].name)
    cell_c = cells.get(CELLS["C"].name)
    if cell_b is not None and cell_c is not None:
        out["comparison"]["B_vs_C"] = {
            "realized_hit_tokens_ratio": _ratio(
                cell_c["realized_hit_tokens_total"],
                cell_b["realized_hit_tokens_total"],
            ),
            "realized_hit_tokens_delta": (
                int(cell_c["realized_hit_tokens_total"])
                - int(cell_b["realized_hit_tokens_total"])
            ),
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
        }

    # Per-cell warnings.
    for cell_dict in cells.values():
        cell_name = cell_dict["cell_name"]
        path = cell_dict["prefix_hit_probe_path_taken"]
        if (
            cell_dict["config"]["enable_prefix_caching"]
            and path == "no_known_path"
        ):
            out["warnings"].append(
                f"cell {cell_name}: prefix-hit probe lands on "
                f"'no_known_path'; realized_hit_tokens_total may "
                "be unreliable. See "
                "PHASE3_VLLM_NATIVE_PREFIX_HITS_RESEARCH.md for "
                "recovery options."
            )
        if (
            cell_dict["config"]["enable_prefix_caching"]
            and path == "cached_blocks_derived"
        ):
            out["warnings"].append(
                f"cell {cell_name}: prefix-hit probe lands on "
                "'cached_blocks_derived' (flat-hash approximation). "
                "Probe count may diverge from vLLM's chained content_hash. "
                "Use the count as the B-vs-C ratio numerator/denominator, "
                "not as an absolute claim."
            )
        if (
            not cell_dict["config"]["enable_prefix_caching"]
            and cell_dict["realized_hit_tokens_total"] > 0
        ):
            out["warnings"].append(
                f"cell {cell_name}: prefix caching is OFF but "
                f"realized_hit_tokens_total={cell_dict['realized_hit_tokens_total']} > 0. "
                "This indicates a probe-side false positive (e.g. mock "
                "allocator state leaking across cells) or a real "
                "vLLM-side anomaly. Investigate before trusting "
                "the B-vs-C ratio."
            )

    return out


# ---------------------------------------------------------------- #
# Per-cell driver — runs one AsyncEngineDriver against the
# resolved vllm module + configured workload. Reusable from
# CPU tests (dry-run mock module) and from real GPU runs.
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
    vllm_module: Any,
    output_dir: Optional[Path] = None,
) -> Any:
    """Run a single Phase 3B cell. Returns the
    ``StreamingRunCellResult`` instance for the cell.

    Always passes ``collect_native_prefix_hits=True`` so all
    three cells emit directly-comparable probe stats.
    """
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
        cache_aware_scheduling=cell.cache_aware_scheduling,
        cache_aware_measurement_only=cell.cache_aware_measurement_only,
        shared_prefix_length=shared_prefix_length,
        shared_prefix_unique_tail_choices=list(unique_tail_choices),
        n_shared_prefixes=n_shared_prefixes,
        collect_native_prefix_hits=True,
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
    vllm_module_factory: Any,
    cells_to_run: Sequence[str],
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run cells sequentially (each cell needs its own engine init
    since ``enable_prefix_caching`` is an engine-level setting).

    ``vllm_module_factory`` is called once per cell to obtain a
    fresh vllm module instance. This lets dry-run callers
    instantiate a fresh mock per cell (so cell-A state doesn't
    leak into cell-B's probe).

    Returns the full comparison dict (the comparison.json contents).
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
    }

    for cell_key in cells_to_run:
        if cell_key not in CELLS:
            raise ValueError(
                f"unknown cell key {cell_key!r}; expected one of A, B, C"
            )
        cell = CELLS[cell_key]
        cell_dir = output_dir / f"cell_{cell_key}" if output_dir else None
        logger.info("Phase 3B: running cell %s (%s)", cell_key, cell.name)
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
            vllm_module=vllm_module,
            output_dir=cell_dir,
        )
        cell_elapsed = time.perf_counter() - cell_start
        logger.info(
            "Phase 3B: cell %s done in %.2fs "
            "(completed=%d, decode_tokens=%d, tps=%.1f)",
            cell_key, cell_elapsed,
            result.n_requests_completed,
            result.n_decode_tokens,
            result.tokens_per_second,
        )
        cells_out[cell.name] = extract_cell_metrics(result=result, cell=cell)

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
# Dry-run mock vLLM — CPU-only fake that's enough to drive the
# orchestration end-to-end without a GPU.
#
# The mock's allocator EXPOSES the V2 ``block_allocator.gpu_allocator``
# shape so the prefix-hit probe can resolve a path. When the cell's
# config has ``enable_prefix_caching=True``, the mock's GPU
# allocator exposes ``_cached_blocks`` (cached_blocks_derived path).
# When False, it exposes neither attribute (no_known_path).
# ---------------------------------------------------------------- #


class _DryRunOutputItem:
    def __init__(self, token_ids: List[int]):
        self.token_ids = token_ids


class _DryRunOutput:
    def __init__(self, token_ids: List[int]):
        self.outputs = [_DryRunOutputItem(token_ids)]


class _DryRunPrefixCachingAllocator:
    """Mimics PrefixCachingBlockAllocator's _cached_blocks dict.
    Populated by the parent block manager's allocate() to simulate
    block-level content_hash insertion."""

    def __init__(self) -> None:
        self._cached_blocks: Dict[int, Any] = {}


class _DryRunNonCachingAllocator:
    """No _cached_blocks, no cache_hits — probe resolves to
    no_known_path on this shape."""
    pass


class _DryRunCpuGpuBlockAllocator:
    """V2 wrapper that exposes .gpu_allocator (the probe's
    canonical resolution path)."""

    def __init__(self, *, enable_prefix_caching: bool):
        if enable_prefix_caching:
            self.gpu_allocator: Any = _DryRunPrefixCachingAllocator()
        else:
            self.gpu_allocator = _DryRunNonCachingAllocator()


class _DryRunBlockManager:
    """Mock BlockSpaceManager. .allocate populates block_tables
    (V1-shape list-of-blocks for the cache-aware install's
    iteration path) AND, when prefix caching is on, inserts the
    request's block-level content_hashes into the GPU allocator's
    _cached_blocks (so the probe's cached_blocks_derived path can
    measure hits)."""

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
        n_full_blocks = len(tokens) // self.block_size
        block_numbers: List[int] = []
        for i in range(n_full_blocks):
            bn = self._next_block_number
            self._next_block_number += 1
            block_numbers.append(bn)
            # Insert content_hash into the GPU allocator so the probe
            # can see it on subsequent allocates of the same prefix.
            if self._enable_prefix_caching:
                from kv_policy.prefix_hit_probe import _content_hash_of_chunk
                chunk = tokens[i * self.block_size : (i + 1) * self.block_size]
                h = _content_hash_of_chunk(chunk)
                # If the chunk's hash already maps, this is a "hit"
                # (reused block) — but we still mark the block_table
                # entry so the cache-aware install's tree.insert sees
                # consistent block_ids.
                self.block_allocator.gpu_allocator._cached_blocks[h] = object()
        # Block-table shape: V1 list-of-block-objects-with-.block_number
        # (the cache-aware install's _block_ids_for_seq handles both
        # V1 and V2; we use V1 here to keep the mock minimal).
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
        # Drain all waiting (mimics vLLM's _schedule_prefills draining
        # under unbounded budget).
        admitted = []
        while self.waiting:
            admitted.append(self.waiting.popleft())
        return admitted


class _DryRunInnerEngine:
    def __init__(self, *, enable_prefix_caching: bool):
        self.scheduler = [
            _DryRunScheduler(enable_prefix_caching=enable_prefix_caching),
        ]


class _DryRunAsyncEngine:
    """Mock async engine. ``generate(...)`` is an async iterator
    that yields a few cumulative outputs to exercise the
    first-token/e2e latency capture."""

    def __init__(self, *, enable_prefix_caching: bool):
        self.engine = _DryRunInnerEngine(
            enable_prefix_caching=enable_prefix_caching,
        )
        self.shutdown_calls = 0
        self._n_decode_per_request = 4

    async def generate(self, prompt_dict: Any, sampling_params: Any, request_id: str):
        # Add the request to the scheduler.waiting so the schedule wrap
        # has a chance to fire with n > 1 (when multiple in-flight
        # requests overlap).
        sched = self.engine.scheduler[0]
        # Build a minimal SequenceGroup stand-in for the scheduler.
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
        # Allocate for the just-admitted request (mimics
        # _allocate_and_set_running in vLLM 0.7.3).
        for adm in admitted:
            sched.block_manager.allocate(adm)
        # Yield a small number of growing outputs with sleeps so
        # first_token_time and completion_time differ.
        cumulative: List[int] = []
        for tok in range(self._n_decode_per_request):
            await asyncio.sleep(0.001)
            cumulative.append(tok + 1)
            yield _DryRunOutput(list(cumulative))
        # Free the sequence when done (mimics vLLM's per-seq free).
        sched.block_manager.free(sg)

    def shutdown_background_loop(self) -> None:
        self.shutdown_calls += 1


class _DryRunSequence:
    def __init__(self, seq_id: int, prompt_token_ids: List[int]):
        self.seq_id = seq_id
        self._prompt = list(prompt_token_ids)

    def get_prompt_token_ids(self) -> List[int]:
        return list(self._prompt)


class _DryRunSequenceGroup:
    def __init__(
        self, *, request_id: str, arrival_time: float,
        seqs: List[_DryRunSequence],
    ):
        self.request_id = request_id
        self.arrival_time = arrival_time
        self._seqs = seqs

    def get_seqs(self) -> List[_DryRunSequence]:
        return list(self._seqs)


class _DryRunAsyncEngineArgs:
    def __init__(self, **kwargs: Any):
        self.kwargs = kwargs
        self.enable_prefix_caching = kwargs.get("enable_prefix_caching", False)


class _DryRunAsyncLLMEngineFactory:
    """Wraps the AsyncLLMEngine.from_engine_args entry point so the
    mock engine inherits the cell's enable_prefix_caching setting
    from the engine args."""

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
    """The Phase 3B dry-run vLLM module stand-in. One instance per
    cell so cell state doesn't leak across cells (matches the real
    GPU path where each cell gets a fresh engine).
    """

    def __init__(self) -> None:
        self._factory = _DryRunAsyncLLMEngineFactory()
        # AsyncLLMEngine is referenced by the runner as a class with
        # a from_engine_args classmethod; we expose the factory's
        # bound method to satisfy that contract.
        self.AsyncLLMEngine = self._factory
        self.AsyncEngineArgs = _DryRunAsyncEngineArgs
        self.SamplingParams = _DryRunSamplingParams


def make_dry_run_vllm_module_factory():
    """Return a factory function suitable for
    ``run_three_cells(vllm_module_factory=...)`` that constructs
    a fresh ``_DryRunVLLM`` per cell."""

    def factory(*, cell: CellConfig) -> _DryRunVLLM:
        del cell  # the mock reads enable_prefix_caching from
                  # AsyncEngineArgs, not from the cell config
        return _DryRunVLLM()

    return factory


# ---------------------------------------------------------------- #
# Real-vLLM module factory — used in GPU mode.
# ---------------------------------------------------------------- #


def make_real_vllm_module_factory():
    """Return a factory that imports the real vllm module once and
    returns it for every cell. Each cell still gets a fresh engine
    because the runner calls ``AsyncLLMEngine.from_engine_args`` on
    that module per ``AsyncEngineDriver.run``."""
    try:
        import vllm  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Real-mode Phase 3B requires vLLM. Install with "
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
        prog="bench_phase3_cache_aware",
        description=(
            "Phase 3B — three-cell cache-aware vs FCFS bench. "
            "Runs cells A (prefix off, cache-aware off), B (prefix "
            "on, cache-aware off), C (prefix on, cache-aware on) "
            "and emits comparison.json. Use --dry-run for CPU-only "
            "orchestration verification before GPU spend."
        ),
    )
    parser.add_argument(
        "--model", default="Qwen/Qwen2.5-7B-Instruct",
    )
    parser.add_argument(
        "--shared-prefix-length", type=int, default=256,
        help="Phase 3 design default: 256 tokens.",
    )
    parser.add_argument(
        "--n-shared-prefixes", type=int, default=4,
        help="Phase 3 design default: 4 cohorts.",
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
        "--output-dir", type=Path, required=True,
    )
    parser.add_argument(
        "--cells", default="A,B,C",
        help="Comma-separated subset of cells to run.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Use the CPU mock vLLM module instead of importing real vllm.",
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
            print(f"unknown cell {c!r}; expected one of A, B, C", file=sys.stderr)
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
            vllm_module_factory=factory,
            cells_to_run=cells_to_run,
            output_dir=args.output_dir,
        )
    )

    print("Phase 3B comparison written to "
          f"{args.output_dir / 'comparison.json'}")
    bvc = comparison.get("comparison", {}).get("B_vs_C")
    if bvc is not None:
        print(
            "B_vs_C: realized_hit_ratio="
            f"{bvc.get('realized_hit_tokens_ratio')!r}, "
            "tps_ratio="
            f"{bvc.get('tokens_per_second_ratio')!r}, "
            "ttft_p99_ratio="
            f"{bvc.get('ttft_p99_ratio')!r}"
        )
    if comparison.get("warnings"):
        print("Warnings:")
        for w in comparison["warnings"]:
            print(f"  * {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
