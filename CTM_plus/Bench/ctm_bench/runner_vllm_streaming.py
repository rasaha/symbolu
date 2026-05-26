"""Streaming Mode B runner — Phase 1 implementation (roadmap #3).

**Status: Phase 1 implemented (LRU-only). Phase 2 (CTM+ on
modern vLLM) still stubbed.**

Phase 1 addresses Problem B from the May 2026 GPU run: batch-mode
FCFS execution does not trigger swap/preemption, so swap counters
always read zero. The streaming runner uses ``AsyncLLMEngine``
with ``preemption_mode="swap"``, a Pareto-shape arrival schedule
that exceeds steady-state capacity, and periodic
``block_allocator.get_and_reset_swaps()`` polling. Result:
real-model swap-counter evidence on LRU, which lets us
calibrate Mode A's tier-cost predictions against real silicon.

Phase 2 (Problem A — CTM+ install on vLLM 0.5+) remains stubbed
behind ``patch_vllm_engine_modern``.

See ``Bench/scripts/MODE_B_STREAMING_DESIGN.md`` for the
architectural plan.

The pure-Python helpers (``ArrivalScheduler``,
``SwapCounterSampler``, ``StreamingRunCellResult``) work
without vLLM and are unit-testable. The GPU-touching code
(``AsyncEngineDriver.run``) requires vLLM and a CUDA GPU at
execution time but is also unit-testable via the injectable
``async_engine_factory`` and ``vllm_module`` parameters.
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- #
# Result types — defined here so contract tests can use them.
# ---------------------------------------------------------------- #


class _DummyZero:
    """Minimal sentinel used by the result builder when there's no
    installed evictor to read counters off of (e.g., LRU baseline
    cells). Returns 0 for any getattr."""

    def __getattr__(self, name):
        return 0


@dataclass(frozen=True)
class StreamingRunCellResult:
    """Outcome of one (workload, policy, seed) streaming run."""

    workload_name: str
    policy_name: str
    seed: int
    n_requests_admitted: int
    n_requests_completed: int
    n_decode_tokens: int
    wall_clock_seconds: float
    swap_in_blocks: int
    swap_out_blocks: int
    preemption_events: int
    counter_source: str = "vllm_streaming_async_swap"
    # Derived throughput. ``tokens_per_second`` is
    # ``n_decode_tokens / wall_clock_seconds`` when both are
    # positive; 0.0 otherwise. Computed by the runner at end of
    # cell so partner-facing comparisons can use it directly.
    tokens_per_second: float = 0.0
    # Per-evict timing — populated only for cells running through
    # CTMEvictorModern (Phase 2 + Phase 3). LRU baseline cells
    # leave these at zero (vLLM's native evictor is not in our
    # control to time without further patches; aggregate
    # tokens_per_second is the apples-to-apples runtime metric
    # for those cells).
    evict_call_count: int = 0
    evict_total_seconds: float = 0.0
    evict_p50_microseconds: float = 0.0
    evict_p99_microseconds: float = 0.0
    # Phase 3 attention-capture timing — populated only when
    # phase3_attention_capture=True.
    attention_capture_call_count: int = 0
    attention_capture_total_seconds: float = 0.0
    # Phase 4 — trigonometric scoring. Populated only when
    # phase4_trig_calibration_path is set.
    phase4_window_pruning_invocations: int = 0
    phase4_blocks_captured_with_pre_rope_keys: int = 0
    # Diagnostic counters added after the May 2026 GPU run produced
    # phase4_blocks_captured_with_pre_rope_keys=0 with no log signal
    # to distinguish "hooks didn't fire" from "hooks fired but the
    # side-channel wasn't found" from "side-channel found but capture
    # function aborted". Populated whenever Phase 4 hooks are
    # installed, regardless of whether captures succeed.
    phase4_side_channel_pre_hook_calls: int = 0
    phase4_side_channel_metadata_found: int = 0
    phase4_side_channel_metadata_missing: int = 0
    phase4_rotary_pre_hook_calls: int = 0
    phase4_capture_attempts: int = 0
    phase4_capture_aborts_no_slot_mapping: int = 0
    phase4_capture_aborts_no_decode_tokens: int = 0
    phase4_capture_exceptions: int = 0
    # Set inside set_block_pre_rope_keys; the second tracks how many
    # of those calls landed on a block that wasn't yet in the evictor's
    # _tracked set (the "speculative storage" path that the May 2026
    # GPU run revealed was needed).
    phase4_set_pre_rope_keys_calls: int = 0
    phase4_set_pre_rope_keys_speculative: int = 0
    # Trig-blend-in-evict counters — added after the v5 GPU run
    # showed we measured the outcome (-11% swap_out/token) but not
    # the mechanism. _evict_calls is incremented every time evict()
    # entered the trig-blend branch; _changed_pick ticks only when
    # the trig signal flipped the pick away from what base-only
    # ordering would have chosen.
    phase4_trig_blend_evict_calls: int = 0
    phase4_trig_changed_pick: int = 0
    # I5 optimization counter — short-circuit on evicts where no
    # candidate has captured K. High values mean capture isn't keeping
    # up with eviction pace (typical at run start / heavy preemption).
    phase4_trig_blend_skips: int = 0
    phase4_capture_subsample_skips: int = 0
    # I1 trig-score-cache counters — every set_block_pre_rope_keys
    # computes the score once (computes); every trig_score_block
    # call is a cache lookup (lookups). Cache misses (recomputes)
    # should be near-zero in steady state; if they aren't, the
    # cache is being invalidated too aggressively.
    phase4_trig_score_computes: int = 0
    phase4_trig_score_lookups: int = 0
    phase4_trig_score_cache_misses: int = 0
    phase4_trig_score_compute_exceptions: int = 0
    # Stats dictionaries snapshotted from the live managers BEFORE
    # teardown. Empty when the corresponding manager isn't installed.
    # Phase 8b bridge verification reads these to assert the
    # route-A wrapper fired, the aggregator captured non-zero
    # attention, and forward_block_attention reached the evictor
    # with non-zero attention_sum (the audit's gap).
    int4_route_a_stats: Dict[str, Any] = field(default_factory=dict)
    attention_aggregator_stats: Dict[str, Any] = field(default_factory=dict)
    ctm_evictor_stats: Dict[str, Any] = field(default_factory=dict)
    # v2 cache-reuse PR-2: populated when cache_aware_scheduling=True.
    # Empty dict when the flag is OFF (the install branch is not
    # entered). When ON, mirrors CacheAwareInstall.stats() output —
    # see KVPolicy/kv_policy/cache_aware_install.py.
    cache_aware_scheduler_stats: Dict[str, Any] = field(default_factory=dict)
    # Phase 4B: populated when extended_pinning=True. Empty dict
    # when the flag is OFF. When ON, mirrors
    # ExtendedPinningInstall.stats() output —
    # see KVPolicy/kv_policy/extended_pinning.py.
    extended_pinning_stats: Dict[str, Any] = field(default_factory=dict)
    # Phase 3A latency telemetry: per-request first-token + e2e
    # latency, collected in _submit_one and aggregated to
    # p50/p99 here. Populated for every cell; the empty-list
    # default matches the pre-3A behaviour byte-for-byte
    # (zero overhead when no requests complete).
    per_request_first_token_latency_ms: List[float] = field(
        default_factory=list,
    )
    per_request_e2e_latency_ms: List[float] = field(default_factory=list)
    ttft_p50_ms: float = 0.0
    ttft_p99_ms: float = 0.0
    e2e_p50_ms: float = 0.0
    e2e_p99_ms: float = 0.0
    # Phase 3A workload-shape telemetry: which prompt builder
    # produced the requests, and (in shared-prefix mode) the cohort
    # assignment per request. Used by Phase 3B/C to verify that
    # the workload's prefix-sharing structure matches the
    # comparison-cell design.
    prompt_builder_name: str = "pareto_unique_head"
    per_request_cohort: List[int] = field(default_factory=list)
    # Phase 3A native prefix-hit probe stats. Empty dict when the
    # probe wasn't installed (default). When installed (via
    # collect_native_prefix_hits=True), mirrors PrefixHitProbe.stats().
    native_prefix_hit_stats: Dict[str, Any] = field(default_factory=dict)
    # Phase TIER5A — CPU swap pool occupancy gauge + swap-in
    # latency telemetry. All fields default to 0 / empty so
    # existing callers + tests are byte-identical to the
    # pre-TIER5A behaviour. Populated only when
    # ``collect_swap_telemetry=True`` on the driver AND the
    # underlying vLLM block_manager exposes the CPU-allocator
    # path (see KVPolicy/kv_policy/swap_telemetry.py for the
    # V1/V2 fallback walk).
    #
    # The "peak" gauge tracks max-observed CPU pool occupancy
    # across the cell; "final" is the last sample's value.
    # ``cpu_swap_pool_total_blocks`` is the engine's configured
    # CPU pool size (controlled by ``swap_space`` GB at engine
    # init). ``swap_in_latency_*_ms`` are computed via
    # SwapInLatencyProbe (LIFO teardown matches the Phase 3 + 4
    # install pattern). ``swap_telemetry_stats`` carries the
    # probe.stats() dict for partner-credible deep inspection.
    cpu_swap_pool_used_blocks_peak: int = 0
    cpu_swap_pool_used_blocks_final: int = 0
    cpu_swap_pool_total_blocks: int = 0
    swap_in_latency_p50_ms: float = 0.0
    swap_in_latency_p99_ms: float = 0.0
    swap_in_latency_call_count: int = 0
    swap_telemetry_stats: Dict[str, Any] = field(default_factory=dict)
    # Phase TIER5A.3 — verifier prompt output. Populated when the
    # driver runs with ``verifier_prompt_token_ids`` set: a single
    # deterministic request submitted before the pressure workload,
    # whose full output_token_ids are captured here for the G1
    # bit-identity verdict. Empty tuple when no verifier was
    # configured (the default for non-TIER5A cells).
    verifier_output_token_ids: Tuple[int, ...] = ()
    verifier_request_completed: bool = False


# ---------------------------------------------------------------- #
# ArrivalScheduler — pure-Python; testable without vLLM.
# ---------------------------------------------------------------- #


@dataclass(frozen=True)
class ParetoArrivalConfig:
    """Pareto-gap inter-arrival shape.

    ``alpha < 2`` produces heavy-tailed bursts; ``alpha → ∞``
    converges to deterministic uniform spacing.

    ``base_rate_per_sec`` is the long-run mean arrival rate the
    schedule is calibrated to. The Pareto draws are scaled so
    that ``E[gap] ≈ 1 / base_rate_per_sec`` for ``alpha > 1``.
    For ``alpha ≤ 1`` the mean is divergent and the realised
    rate is approximate.
    """

    base_rate_per_sec: float
    alpha: float


class ArrivalScheduler:
    """Generates per-arrival inter-arrival delays for the
    streaming runner. Pure-Python, deterministic per seed.

    Two modes:
      * ``pareto`` — synthesised heavy-tailed gaps via Pareto.
      * ``replay`` — reads ``(timestamp_seconds, prompt_length)``
        pairs from a CSV and replays them at the file's logical
        pace.

    The streaming runner consumes the schedule via
    :meth:`next_arrival_delay_seconds` and
    :meth:`next_prompt_length` until the schedule is exhausted
    or the run hits a wall-clock budget.
    """

    def __init__(
        self,
        *,
        seed: int,
        pareto: Optional[ParetoArrivalConfig] = None,
        replay_csv: Optional[Path] = None,
        prompt_length_choices: Optional[Sequence[int]] = None,
    ) -> None:
        if (pareto is None) == (replay_csv is None):
            raise ValueError(
                "Exactly one of `pareto` or `replay_csv` must be set"
            )
        if pareto is not None and pareto.alpha <= 0:
            raise ValueError(
                f"pareto.alpha must be > 0; got {pareto.alpha}"
            )
        self._mode = "pareto" if pareto is not None else "replay"
        self._pareto = pareto
        self._rng = random.Random(seed)
        self._replay: List[Tuple[float, int]] = []
        self._replay_idx = 0
        self._last_replay_ts: float = 0.0
        self._prompt_length_choices = (
            list(prompt_length_choices)
            if prompt_length_choices
            else [256, 512, 1024, 2048]
        )
        if replay_csv is not None:
            self._load_replay_csv(replay_csv)

    def _load_replay_csv(self, path: Path) -> None:
        """Parse a 2-column CSV (timestamp_seconds, prompt_length).
        Tolerates a header line — any line whose first field is
        not a float is skipped."""
        rows: List[Tuple[float, int]] = []
        for line in path.read_text().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            try:
                ts = float(parts[0])
                length = int(parts[1])
            except ValueError:
                continue
            rows.append((ts, length))
        rows.sort(key=lambda r: r[0])
        self._replay = rows

    def next_arrival_delay_seconds(self) -> Optional[float]:
        """Returns the delay until the next arrival, or ``None``
        when the schedule is exhausted (replay mode only;
        Pareto mode is unbounded)."""
        if self._mode == "pareto":
            assert self._pareto is not None
            target_mean_gap = 1.0 / self._pareto.base_rate_per_sec
            alpha = self._pareto.alpha
            # The variable ``U^(-1/alpha) - 1`` for U ~ Uniform(0,1)
            # has expected value ``1 / (alpha - 1)`` for alpha > 1
            # (verified: integrate u^(-1/alpha) du from 0 to 1).
            # Scale so that E[gap] = target_mean_gap.
            if alpha > 1.0:
                pareto_minus_one_mean = 1.0 / (alpha - 1.0)
                scale = target_mean_gap / pareto_minus_one_mean
            else:
                # alpha <= 1 has a divergent mean; fall back to
                # target_mean_gap as the scale and accept that the
                # realised rate will exceed the target on short runs.
                scale = target_mean_gap
            u = self._rng.random()
            if u <= 0.0:
                u = 1e-9
            gap_raw = (u ** (-1.0 / alpha)) - 1.0
            return max(1e-6, gap_raw * scale)

        # Replay mode.
        if self._replay_idx >= len(self._replay):
            return None
        ts, _ = self._replay[self._replay_idx]
        delay = ts - self._last_replay_ts
        if delay < 0:
            delay = 0.0
        self._last_replay_ts = ts
        return delay

    def next_prompt_length(self) -> int:
        """Returns the prompt length for the next arrival.

        In replay mode this comes from the CSV; in pareto mode
        it samples from ``prompt_length_choices`` uniformly.
        """
        if self._mode == "replay":
            if self._replay_idx >= len(self._replay):
                raise StopIteration("replay schedule exhausted")
            _, length = self._replay[self._replay_idx]
            self._replay_idx += 1
            return length
        return self._rng.choice(self._prompt_length_choices)


# ---------------------------------------------------------------- #
# Phase 3A — Prompt builders.
#
# Two synthetic shapes for the streaming workload:
#
#   * ParetoUniqueHeadPromptBuilder — the PR-2 legacy shape.
#     Per-request unique head token forces unique content_hash
#     chains, defeating prefix caching. Preserves behaviour for
#     callers that don't opt into shared-prefix mode.
#
#   * SharedPrefixPromptBuilder — N cohorts, each with a unique
#     token-ID prefix shared by every request in the cohort.
#     Each request's prompt is [cohort_prefix] + [unique_tail].
#     This is the workload shape that lets us measure realized
#     prefix-cache hits (cells B and C in the Phase 3 design).
#
# Both are pure-Python, deterministic per (seed, request_id), and
# return ``List[int]`` ready for vLLM's ``prompt_token_ids``.
# ---------------------------------------------------------------- #


class PromptBuilder:
    """Abstract base for synthetic prompt generators."""

    @property
    def name(self) -> str:
        raise NotImplementedError

    def build(
        self, *, request_id_counter: int, suggested_length: int,
    ) -> List[int]:
        raise NotImplementedError

    def cohort_of(self, request_id_counter: int) -> int:
        """Return the cohort index for this request, or -1 if the
        builder does not assign cohorts (default for non-shared-prefix
        shapes)."""
        return -1


class ParetoUniqueHeadPromptBuilder(PromptBuilder):
    """The legacy PR-2 builder.

    Prompt = ``[200 + (request_id_counter % 4096)] + [100] * (suggested_length - 1)``.
    The per-request unique head token defeats vLLM's prefix caching
    so memory pressure is observable. Default builder when no
    shared-prefix flags are set; preserves PR-2 byte-identical
    behaviour.
    """

    @property
    def name(self) -> str:
        return "pareto_unique_head"

    def build(
        self, *, request_id_counter: int, suggested_length: int,
    ) -> List[int]:
        if suggested_length < 1:
            return []
        head_tok = 200 + (request_id_counter % 4096)
        return [head_tok] + [100] * (suggested_length - 1)


class SharedPrefixPromptBuilder(PromptBuilder):
    """Cohort-shared prompts for Phase 3 prefix-cache measurement.

    Each request belongs to one of ``n_cohorts`` cohorts (round-robin
    by ``request_id_counter``). All requests in a cohort share an
    identical token-ID prefix of length ``shared_prefix_length``.
    The tail is per-request unique, with length drawn from
    ``unique_tail_choices``.

    Determinism: cohort prefixes are pre-generated at __init__ time
    from ``seed``. Per-request tails are seeded from
    ``(seed, request_id_counter)`` so each request's tail is
    reproducible without depending on rng state ordering.

    Token-ID ranges are chosen so the cohort prefix space
    ``[1000, 4999]`` and the tail space ``[6000, 9999]`` cannot
    collide. Cohorts are seeded per-index so cross-cohort
    content_hashes don't collide (different cohorts produce
    different prefix block hashes).
    """

    def __init__(
        self,
        *,
        seed: int,
        shared_prefix_length: int,
        unique_tail_choices: Sequence[int],
        n_cohorts: int,
    ) -> None:
        if shared_prefix_length < 1:
            raise ValueError(
                f"shared_prefix_length must be >= 1; got {shared_prefix_length}"
            )
        if n_cohorts < 1:
            raise ValueError(
                f"n_cohorts must be >= 1; got {n_cohorts}"
            )
        if not unique_tail_choices:
            raise ValueError(
                "unique_tail_choices must be non-empty"
            )
        self._seed = int(seed)
        self._shared_prefix_length = int(shared_prefix_length)
        self._tail_choices = [int(x) for x in unique_tail_choices]
        self._n_cohorts = int(n_cohorts)
        # Pre-generate the N cohort prefixes. Each cohort has its
        # own derived rng so different cohorts don't share token IDs
        # at the same position by accident.
        self._cohort_prefixes: List[List[int]] = []
        for c in range(self._n_cohorts):
            prefix_rng = random.Random(self._seed * 1_000_003 + c * 17)
            prefix = [
                prefix_rng.randint(1000, 4999)
                for _ in range(self._shared_prefix_length)
            ]
            self._cohort_prefixes.append(prefix)

    @property
    def name(self) -> str:
        return "shared_prefix"

    @property
    def n_cohorts(self) -> int:
        return self._n_cohorts

    @property
    def shared_prefix_length(self) -> int:
        return self._shared_prefix_length

    @property
    def tail_choices(self) -> List[int]:
        return list(self._tail_choices)

    def cohort_of(self, request_id_counter: int) -> int:
        return int(request_id_counter) % self._n_cohorts

    def build(
        self, *, request_id_counter: int, suggested_length: int,
    ) -> List[int]:
        # suggested_length is ignored — shared-prefix mode has its
        # own length distribution (prefix + tail), and conflating
        # it with the Pareto-shape length distribution would obscure
        # the workload shape.
        del suggested_length
        cohort_idx = self.cohort_of(request_id_counter)
        prefix = self._cohort_prefixes[cohort_idx]
        tail_rng = random.Random(
            self._seed * 1_000_003 + int(request_id_counter) * 31 + 7
        )
        tail_length = tail_rng.choice(self._tail_choices)
        tail = [tail_rng.randint(6000, 9999) for _ in range(tail_length)]
        return list(prefix) + tail


# ---------------------------------------------------------------- #
# Phase 3A — Per-request latency capture.
#
# Each completed request contributes one ``RequestLatency`` record
# to the driver's accumulator. p50 / p99 of first-token + e2e
# latency are computed at the end of ``run()`` and surfaced in the
# result dataclass for the cell-comparison harness (Phase 3B).
# ---------------------------------------------------------------- #


@dataclass
class RequestLatency:
    """Per-request latency samples."""
    request_id: str
    submit_time: float          # perf_counter at task creation
    first_token_time: float     # perf_counter at first non-empty output (0 if none)
    completion_time: float      # perf_counter at coroutine exit
    n_decode_tokens: int
    cohort_index: int = -1      # SharedPrefixPromptBuilder.cohort_of(); -1 if N/A


# ---------------------------------------------------------------- #
# SwapCounterSampler — pure-Python state machine; testable.
# ---------------------------------------------------------------- #


class SwapCounterSampler:
    """Accumulates per-cell swap counter totals across periodic
    samples.

    The streaming runner polls
    ``block_allocator.get_and_reset_swaps()`` on a fixed cadence
    (default 100 ms). Each call returns the swap activity since
    the last reset. We sum them into running totals.

    The sampler is a pure-Python state machine that the
    streaming runner feeds via :meth:`record_sample`; it does
    not call vLLM directly. This keeps it unit-testable and
    decouples it from the vLLM API surface.
    """

    def __init__(self) -> None:
        self._totals: Dict[str, int] = {
            "swap_in_blocks": 0,
            "swap_out_blocks": 0,
            "preemption_events": 0,
        }
        self._n_samples: int = 0
        self._stopped: bool = False

    def record_sample(
        self,
        *,
        swap_in_blocks: int = 0,
        swap_out_blocks: int = 0,
        preemption_events: int = 0,
    ) -> None:
        """Add one polling sample's deltas to the running totals.

        Negative deltas are rejected — counter resets always
        zero them, never decrement them. This is a hard invariant
        of the sampling design; an apparent negative delta would
        indicate the sampler ran across an engine restart, in
        which case the cell should be discarded.
        """
        if self._stopped:
            raise RuntimeError(
                "record_sample called after stop(); start a new "
                "sampler for the next cell"
            )
        for label, value in (
            ("swap_in_blocks", swap_in_blocks),
            ("swap_out_blocks", swap_out_blocks),
            ("preemption_events", preemption_events),
        ):
            if value < 0:
                raise ValueError(
                    f"{label} delta must be >= 0; got {value} "
                    "(possible engine restart mid-cell)"
                )
        self._totals["swap_in_blocks"] += swap_in_blocks
        self._totals["swap_out_blocks"] += swap_out_blocks
        self._totals["preemption_events"] += preemption_events
        self._n_samples += 1

    def stop(self) -> None:
        self._stopped = True

    @property
    def n_samples(self) -> int:
        return self._n_samples

    def totals(self) -> Dict[str, int]:
        return dict(self._totals)


# ---------------------------------------------------------------- #
# Counter probe — pulls swap deltas from a vLLM engine.
#
# Broken out so it can be unit-tested with a fake engine and so
# the AsyncEngineDriver's run loop is not littered with vLLM
# attribute-walking code.
# ---------------------------------------------------------------- #


def _resolve_block_size_from_engine(
    engine: Any, *, default: int = 32,
) -> int:
    """Audit fix #3: read vLLM's actual ``block_size`` instead of
    hardcoding 32.

    Stock vLLM 0.7.3 defaults to ``block_size=16``. The cache-aware
    install + prefix-hit probe previously hardcoded 32, which:
      * truncated tree-derived realized_hit to multiples of 32
        (losing up to 16 tokens per match);
      * chunked the probe's prompt-hash search at 32 tokens while
        vLLM's ``_cached_blocks`` is keyed by 16-token chained
        hashes (resulting in zero matches even when reuse is heavy).

    Reads ``engine.engine.cache_config.block_size`` (the canonical
    location in vLLM 0.7.3 V0). Falls back through scheduler config
    and the default if the canonical path isn't present.
    """
    inner = getattr(engine, "engine", engine)
    cache_config = getattr(inner, "cache_config", None)
    if cache_config is not None:
        bs = getattr(cache_config, "block_size", None)
        if bs is not None:
            try:
                return int(bs)
            except (TypeError, ValueError):
                pass
    # Defensive fallbacks for other vLLM minor versions.
    for cfg_attr in ("scheduler_config", "model_config"):
        cfg = getattr(inner, cfg_attr, None)
        if cfg is not None:
            bs = getattr(cfg, "block_size", None)
            if bs is not None:
                try:
                    return int(bs)
                except (TypeError, ValueError):
                    continue
    return int(default)


def _read_swap_counters_from_engine(engine: Any) -> Tuple[int, int, int]:
    """Read swap counter deltas since the last reset.

    Returns ``(swap_in_blocks, swap_out_blocks, preemption_total)``.
    Returns ``(0, 0, 0)`` on any attribute-walk failure — the
    sampler treats zero-deltas as "no swap activity," which is
    indistinguishable from "the engine doesn't expose this API,"
    and that's the right semantics here: the run continues, the
    final report flags the counter source.

    Walks two paths on the engine to support multiple vLLM minor
    versions:

    * ``engine.engine.scheduler[0].block_manager.block_allocator``
      (post-0.5 path, pipeline-parallel scheduler is a list)
    * ``engine.engine.scheduler.block_manager.block_allocator``
      (older path with a single Scheduler instance)

    **Swap-counter format note (verified against
    runner_vllm.py:375-404 and its tests):** vLLM 0.7's
    ``CpuGpuBlockAllocator.get_and_reset_swaps()`` returns a list
    of ``(src_block_id, dst_block_id)`` tuples — one per swap
    event since the last reset. The count is ``len(swaps)``; the
    direction (in vs out) cannot be inferred from the tuple
    alone without device-side context. We report ``len(swaps)``
    as ``swap_out_blocks`` (matching the existing
    ``_extract_vllm_tier_counters`` convention of attributing
    all swaps to "DDR" / slow-tier traffic), and report
    ``swap_in_blocks=0`` since we can't distinguish. If a future
    vLLM version splits the counter, the dict / object branches
    below pick that up automatically.

    **Preemption attribute (verified against vLLM 0.7
    scheduler.py):** the running total is
    ``num_cumulative_preemption`` (singular). We also try a few
    alternate names for forward compatibility.
    """
    inner = getattr(engine, "engine", engine)
    sched = getattr(inner, "scheduler", None)
    if sched is None:
        return (0, 0, 0)
    if isinstance(sched, list):
        if not sched:
            return (0, 0, 0)
        sched = sched[0]
    bm = getattr(sched, "block_manager", None)
    if bm is None:
        return (0, 0, 0)
    block_allocator = getattr(bm, "block_allocator", None)
    if block_allocator is None:
        # vLLM ≤ 0.6 uses block_manager.gpu_allocator instead. The
        # streaming runner is targeted at 0.7+, but we don't want
        # to crash on ≤ 0.6.
        return (0, 0, 0)

    swap_in = 0
    swap_out = 0
    try:
        swaps = block_allocator.get_and_reset_swaps()
    except (AttributeError, TypeError):
        swaps = None

    if swaps is not None:
        try:
            # vLLM 0.7's CpuGpuBlockAllocator returns a list of
            # (src_block_id, dst_block_id) tuples. Count is len(),
            # direction not distinguishable — attribute all to
            # swap_out per the existing batch runner's convention.
            if isinstance(swaps, list):
                # Distinguish list-of-tuples from list-of-ints:
                # if any element is itself a tuple/list, we have
                # the swap-event format.
                if swaps and isinstance(swaps[0], (tuple, list)):
                    n = len(swaps)
                    swap_out = n
                    swap_in = 0
                elif swaps and isinstance(swaps[0], int) and len(swaps) >= 2:
                    # Hypothetical [in, out] flat int list.
                    swap_in = int(swaps[0])
                    swap_out = int(swaps[1])
                else:
                    # Empty list or unknown format.
                    swap_in = 0
                    swap_out = 0
            elif isinstance(swaps, tuple) and len(swaps) >= 2 and all(
                isinstance(x, int) for x in swaps[:2]
            ):
                # (in, out) 2-tuple of ints.
                swap_in = int(swaps[0])
                swap_out = int(swaps[1])
            elif isinstance(swaps, dict):
                swap_in = int(swaps.get("in", swaps.get("swap_in", 0)))
                swap_out = int(swaps.get("out", swaps.get("swap_out", 0)))
            elif hasattr(swaps, "swap_in") and hasattr(swaps, "swap_out"):
                swap_in = int(swaps.swap_in)
                swap_out = int(swaps.swap_out)
            else:
                # Fall back to len() if iterable.
                try:
                    n = len(swaps)
                    swap_out = n
                except TypeError:
                    pass
        except (TypeError, ValueError):
            pass

    # Preemption running total. vLLM 0.7's actual attribute is
    # ``num_cumulative_preemption`` (singular). Older / newer
    # versions may use slightly different names; try several.
    preemption = 0
    for attr in (
        "num_cumulative_preemption",
        "num_cumulative_preemptions",
        "num_preemption_events",
    ):
        v = getattr(sched, attr, None)
        if v is not None:
            try:
                preemption = int(v)
                break
            except (TypeError, ValueError):
                continue

    return (swap_in, swap_out, preemption)


# ---------------------------------------------------------------- #
# AsyncEngineDriver — Phase 1 implementation (LRU-only).
# ---------------------------------------------------------------- #


# Type aliases for the injectable factory + module.
AsyncEngineFactory = Callable[..., Any]    # () -> async engine instance
SamplingParamsFactory = Callable[..., Any]  # (**kwargs) -> sampling params


class AsyncEngineDriver:
    """Drives an ``AsyncLLMEngine`` with a streaming arrival
    schedule, accumulating swap-counter samples during the run.

    **Phase 1 (this class) is LRU-only.** Setting
    ``ctm_plus_evictor=True`` raises ``NotImplementedError``
    pointing at Phase 2 (``patch_vllm_engine_modern``).

    The vLLM imports are deferred to :meth:`run` so this class
    can be constructed and inspected on a CPU-only host. Tests
    inject a fake engine via the constructor's ``vllm_module``
    parameter.
    """

    DEFAULT_SAMPLE_INTERVAL_SECONDS: float = 0.1

    def __init__(
        self,
        *,
        model: str,
        gpu_memory_utilization: float = 0.30,
        swap_space_gb: int = 8,
        seed: int = 42,
        scheduler_config_overrides: Optional[Dict[str, object]] = None,
        ctm_plus_evictor: bool = False,
        enable_prefix_caching: Optional[bool] = None,
        phase3_attention_capture: bool = False,
        phase3_capture_every_n: int = 4,
        phase4_trig_calibration_path: Optional[Path] = None,
        phase4_window_interval: int = 128,
        phase4_future_offsets: Optional[Sequence[int]] = None,
        phase4_num_layers: int = 0,
        phase4_capture_every_n: int = 1,
        phase4_trig_blend_candidate_count: int = 4,
        phase4_use_cython_evictor: bool = False,
        phase4_fast_hooks: bool = False,
        max_decode_tokens: int = 128,
        sample_interval_seconds: Optional[float] = None,
        kv_cache_dtype: Optional[str] = None,
        int4_kv_route_a: bool = False,
        int4_kv_k_group_size: int = 32,
        int4_kv_v_group_size: int = 32,
        int4_kv_asymmetric: bool = True,
        int4_kv_bits: int = 4,
        int4_kv_sink_size: int = 0,
        int4_kv_num_kv_heads: Optional[int] = None,
        cache_aware_scheduling: bool = False,
        cache_aware_measurement_only: bool = False,
        cache_aware_max_starvation_seconds: float = 30.0,
        shared_prefix_length: int = 0,
        shared_prefix_unique_tail_choices: Optional[Sequence[int]] = None,
        n_shared_prefixes: int = 4,
        collect_native_prefix_hits: bool = False,
        extended_pinning: bool = False,
        pin_first_n_blocks: int = 0,
        pin_tokens_file: Optional[Path] = None,
        pin_max_budget_blocks: int = 1024,
        swap_telemetry: bool = False,
        verifier_prompt_token_ids: Optional[Sequence[int]] = None,
        verifier_max_decode_tokens: Optional[int] = None,
        max_model_len: Optional[int] = None,
        preemption_mode: str = "swap",
        vllm_module: Any = None,
    ) -> None:
        self.model = model
        self.gpu_memory_utilization = gpu_memory_utilization
        self.swap_space_gb = swap_space_gb
        self.seed = seed
        self.scheduler_config_overrides = (
            dict(scheduler_config_overrides)
            if scheduler_config_overrides else {}
        )
        self.ctm_plus_evictor = ctm_plus_evictor
        # Audit-pass fix: prefix caching is now an explicit knob,
        # not yoked to ctm_plus_evictor. CTM+ REQUIRES prefix caching
        # (the patch installs on PrefixCachingBlockAllocator's
        # evictor slot); LRU works either way. Apples-to-apples
        # CTM+ vs LRU on the cache-retention question requires
        # BOTH cells to set enable_prefix_caching=True. The default
        # (None) preserves the prior behaviour: True iff
        # ctm_plus_evictor is True.
        if enable_prefix_caching is None:
            self.enable_prefix_caching = bool(ctm_plus_evictor)
        else:
            if ctm_plus_evictor and not enable_prefix_caching:
                raise ValueError(
                    "ctm_plus_evictor=True requires "
                    "enable_prefix_caching=True (the CTM+ patch "
                    "installs on PrefixCachingBlockAllocator's "
                    "evictor slot; without prefix caching there is "
                    "no evictor to swap)."
                )
            self.enable_prefix_caching = bool(enable_prefix_caching)
        if phase3_attention_capture and not ctm_plus_evictor:
            raise ValueError(
                "phase3_attention_capture=True requires "
                "ctm_plus_evictor=True. The capture hook pushes "
                "attention to a CTMEvictorModern; without the evictor, "
                "there's nowhere to push the attention to."
            )
        self.phase3_attention_capture = bool(phase3_attention_capture)
        self.phase3_capture_every_n = max(1, int(phase3_capture_every_n))

        # ---- Phase 4 wiring ----
        if phase4_trig_calibration_path is not None and not ctm_plus_evictor:
            raise ValueError(
                "phase4_trig_calibration_path requires "
                "ctm_plus_evictor=True. The trig score is consumed "
                "by CTMEvictorModern; without the evictor, the "
                "calibration data is unused."
            )
        if (
            phase4_trig_calibration_path is not None
            and phase3_attention_capture
        ):
            # Phase 3 and Phase 4 are competing hypotheses; running
            # both in one cell entangles their effects. Surface the
            # conflict as an explicit ValueError rather than letting
            # the cell quietly produce uninterpretable results.
            raise ValueError(
                "Phase 3 (attention forwarding) and Phase 4 "
                "(trig scoring) are competing hypotheses. Run them "
                "in separate cells of the four-cell experiment so "
                "their effects can be isolated. Got both flags set."
            )
        self.phase4_trig_calibration_path = phase4_trig_calibration_path
        self.phase4_window_interval = int(phase4_window_interval)
        self.phase4_future_offsets = (
            list(phase4_future_offsets)
            if phase4_future_offsets is not None
            else None
        )
        self.phase4_num_layers = int(phase4_num_layers)
        self.phase4_capture_every_n = max(1, int(phase4_capture_every_n))
        self.phase4_trig_blend_candidate_count = max(
            1, int(phase4_trig_blend_candidate_count),
        )
        self.phase4_use_cython_evictor = bool(phase4_use_cython_evictor)
        self.phase4_fast_hooks = bool(phase4_fast_hooks)
        # FP8 KV cache lane (the competitor for the route-B INT4 work).
        # When set, the value is forwarded to vLLM's AsyncEngineArgs as
        # ``kv_cache_dtype`` — "fp8" / "fp8_e4m3" / "fp8_e5m2" / "auto".
        # vLLM 0.7+ supports "fp8" on H100/A100 via the hardware tensor
        # cores. The runner's other measurement plumbing (swap counters,
        # tokens/sec) is unaffected by the KV dtype choice, so the same
        # cell shape covers FP16 baseline vs FP8 in two runs.
        # See ``Bench/scripts/FP8_INT4_THROUGHPUT_RUNBOOK.md`` for the
        # cell composition.
        if kv_cache_dtype is not None and kv_cache_dtype not in (
            "auto", "fp8", "fp8_e4m3", "fp8_e5m2", "fp16", "bf16",
        ):
            raise ValueError(
                f"kv_cache_dtype={kv_cache_dtype!r}; expected one of "
                f"'auto', 'fp8', 'fp8_e4m3', 'fp8_e5m2', 'fp16', 'bf16'"
            )
        self.kv_cache_dtype = kv_cache_dtype
        # Route-A INT4 KV-cache integration. Orthogonal to
        # ctm_plus_evictor (INT4 compression and CTM+ eviction compose
        # — see ROUTE_A_VLLM_CACHE_KV_PLAN.md). When True, the driver
        # installs `install_int4_cache_kv_route_a` on the model after
        # engine construction so the KIVI INT4 round-trip runs inside
        # each Attention.forward. This is the quality-path tier (the
        # algorithm runs under vLLM); the memory-realizing paged-buffer
        # swap is the documented follow-up.
        self.int4_kv_route_a = bool(int4_kv_route_a)
        self.int4_kv_k_group_size = int(int4_kv_k_group_size)
        self.int4_kv_v_group_size = int(int4_kv_v_group_size)
        self.int4_kv_asymmetric = bool(int4_kv_asymmetric)
        self.int4_kv_bits = int(int4_kv_bits)
        self.int4_kv_sink_size = int(int4_kv_sink_size)
        # KV-head count for route-A's 2-D→3-D reshape. None → the
        # install auto-detects from model.config.
        self.int4_kv_num_kv_heads = (
            int(int4_kv_num_kv_heads)
            if int4_kv_num_kv_heads is not None else None
        )
        self.max_decode_tokens = max_decode_tokens
        self.sample_interval_seconds = (
            sample_interval_seconds
            if sample_interval_seconds is not None
            else self.DEFAULT_SAMPLE_INTERVAL_SECONDS
        )
        self._vllm_module = vllm_module
        # Route-A INT4 install handles — set in run(); None until then.
        self._int4_route_a_manager: Any = None
        self._int4_route_a_teardown: Any = None
        # Audit fix (medium finding): initialize handles read by
        # _submit_one and the run-loop helpers so direct invocation
        # (e.g. unit tests) doesn't AttributeError before run() has
        # populated them.
        self._installed_evictor: Any = None
        self._attention_aggregator: Any = None
        # v2 cache-reuse PR-2 — cache-aware admission scheduling.
        # Orthogonal to int4_protected, CTM+ evictor, and route-A
        # INT4: lives at the scheduler layer. Default OFF preserves
        # pre-PR-2 behaviour exactly. The install handle is set in
        # run() and torn down in the finally block.
        #
        # Phase 3C — cache_aware_measurement_only is a separate
        # mode: installs the allocate/free tree wraps for
        # realized-hit measurement, but SKIPS the schedule reorder
        # wrap. Mutually exclusive with cache_aware_scheduling.
        # Used in cell B of the Phase 3 comparison so cells B and
        # C share the same measurement instrument.
        if cache_aware_scheduling and cache_aware_measurement_only:
            raise ValueError(
                "cache_aware_scheduling and "
                "cache_aware_measurement_only are mutually exclusive; "
                "set exactly one (or neither)."
            )
        self.cache_aware_scheduling = bool(cache_aware_scheduling)
        self.cache_aware_measurement_only = bool(cache_aware_measurement_only)
        self.cache_aware_max_starvation_seconds = float(
            cache_aware_max_starvation_seconds
        )
        self._cache_aware_install: Any = None

        # Phase 3A — synthetic prompt builder selection.
        # shared_prefix_length=0 keeps the PR-2 Pareto-unique-head
        # behaviour byte-identical. shared_prefix_length>=1 switches
        # to the cohort-shared shape used by the Phase 3 comparison
        # cells; per-cell flag wiring lives in run_streaming.py CLI.
        self.shared_prefix_length = int(shared_prefix_length)
        self.n_shared_prefixes = int(n_shared_prefixes)
        if self.shared_prefix_length > 0:
            tails = (
                list(shared_prefix_unique_tail_choices)
                if shared_prefix_unique_tail_choices is not None
                else [32, 64, 128, 256]
            )
            self._prompt_builder: PromptBuilder = SharedPrefixPromptBuilder(
                seed=self.seed,
                shared_prefix_length=self.shared_prefix_length,
                unique_tail_choices=tails,
                n_cohorts=self.n_shared_prefixes,
            )
        else:
            self._prompt_builder = ParetoUniqueHeadPromptBuilder()
        # Per-request latency accumulator (populated by _submit_one).
        self._request_latencies: List[RequestLatency] = []

        # Phase 3A — native prefix-hit probe (measurement-only wrap
        # of vLLM's block_manager.allocate that counts cache hits
        # without reordering). Off by default; opt-in via
        # collect_native_prefix_hits=True. The install handle is set
        # in run() and torn down in the finally block.
        self.collect_native_prefix_hits = bool(collect_native_prefix_hits)
        self._prefix_hit_probe: Any = None

        # Phase 4B — Extended pinning (eviction-protection policy).
        # Orthogonal to int4_protected and the cache-aware scheduler
        # layers; sits at the LRU evictor + allocator layer.
        # Off by default; opt-in via extended_pinning=True. Pin specs
        # are constructed from pin_first_n_blocks + pin_tokens_file
        # (one or both; union semantics in the manager).
        self.extended_pinning = bool(extended_pinning)
        self.pin_first_n_blocks = int(pin_first_n_blocks)
        self.pin_tokens_file = pin_tokens_file
        self.pin_max_budget_blocks = int(pin_max_budget_blocks)
        # Phase 4C operational knob: cap vLLM's max_model_len so the
        # engine can start under tight gpu_memory_utilization. Default
        # None preserves vLLM's per-model default (32768 for Qwen-7B).
        # Useful when the workload's actual prompt length is much
        # smaller than the model's max context and we want to force
        # eviction pressure via tight KV cache.
        self.max_model_len = (
            int(max_model_len) if max_model_len is not None else None
        )
        # Phase 4C diagnostic knob: vLLM's preemption policy. Default
        # "swap" matches the existing behavior (preemption swaps
        # blocks to CPU). "recompute" forces vLLM to evict cached
        # blocks under pressure instead of swapping — necessary to
        # exercise the LRUEvictor that extended-pinning wraps when
        # the bench's workload doesn't naturally produce eviction.
        if preemption_mode not in ("swap", "recompute"):
            raise ValueError(
                f"preemption_mode must be 'swap' or 'recompute'; "
                f"got {preemption_mode!r}"
            )
        self.preemption_mode = preemption_mode
        self._extended_pinning_install: Any = None

        # Phase TIER5A — swap-restore telemetry. Always-on for the
        # TIER5A bench (cells A/B/C all install it); opt-in via
        # ``swap_telemetry=True`` elsewhere. Installs the swap-in
        # latency probe AND drives a periodic CpuSwapPoolPeakTracker
        # poll on the same cadence as SwapCounterSampler. Both
        # surface the 7 swap-telemetry fields on
        # StreamingRunCellResult.
        self.swap_telemetry = bool(swap_telemetry)
        self._swap_in_latency_probe: Any = None
        self._cpu_swap_pool_peak_tracker: Any = None
        self._swap_telemetry_block_manager_ref: Any = None

        # Phase TIER5A.3 — verifier prompt. When configured, the
        # driver submits a single deterministic request BEFORE the
        # pressure workload and captures its full output_token_ids
        # on the StreamingRunCellResult. The G1 bit-identity verdict
        # compares this output across cells. None → no verifier
        # (the default for non-TIER5A cells).
        self.verifier_prompt_token_ids: Optional[List[int]] = (
            list(verifier_prompt_token_ids)
            if verifier_prompt_token_ids is not None else None
        )
        self.verifier_max_decode_tokens = (
            int(verifier_max_decode_tokens)
            if verifier_max_decode_tokens is not None else None
        )
        # Set in run() once the verifier request is constructed.
        self._verifier_request_id: Optional[str] = None
        self._verifier_output_token_ids: List[int] = []
        self._verifier_request_completed: bool = False

    @staticmethod
    def _extract_model_from_engine(inner_engine: Any) -> Any:
        """Walk an LLMEngine to find the underlying torch model
        whose Attention layers we want to monkey-patch.

        vLLM 0.7+ path:
          engine -> model_executor -> driver_worker.worker
              -> model_runner.model
        Try a few alternate names per vLLM minor version.
        """
        # Try the documented path first.
        for path in (
            ("model_executor", "driver_worker", "worker", "model_runner", "model"),
            ("model_executor", "driver_worker", "model_runner", "model"),
            ("model_executor", "model_runner", "model"),
            ("worker", "model_runner", "model"),
            ("model_runner", "model"),
            ("model",),
        ):
            cur = inner_engine
            ok = True
            for attr in path:
                cur = getattr(cur, attr, None)
                if cur is None:
                    ok = False
                    break
            if ok and cur is not None:
                return cur
        # Best-effort fallback: return the inner engine; the
        # walker in install_attention_capture will descend.
        return inner_engine

    def _import_vllm(self) -> Any:
        if self._vllm_module is not None:
            return self._vllm_module
        try:
            import vllm  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "Streaming Mode B requires vLLM. Install with "
                "`pip install vllm`. The streaming runner targets "
                "vLLM 0.7+ for the AsyncLLMEngine + preemption-mode "
                "swap path; older vLLM may need different "
                "scheduler-config keys."
            ) from exc
        return vllm

    def _build_engine_args(self, vllm: Any) -> Any:
        """Build the engine args dict. Broken out so tests can
        verify the critical config (preemption_mode=swap, etc.)
        without spinning up vLLM.

        Two distinct config regimes:

        * **Phase 1 (LRU + swap path).** ``ctm_plus_evictor=False``.
          ``enable_prefix_caching=False`` to keep eviction in the
          swap decision tree (under-pressure swap, the simulator's
          question).
        * **Phase 2 (CTM+ on cache retention).** ``ctm_plus_evictor=
          True``. ``enable_prefix_caching=True`` REQUIRED so vLLM's
          ``PrefixCachingBlockAllocator`` exists with an evictor
          slot the patch can swap. With prefix caching on, the
          evictor decides cache-retention, not under-pressure swap
          — different operational question; honest scope per
          MODE_B_STREAMING_DESIGN.md §4.4.
        """
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "gpu_memory_utilization": self.gpu_memory_utilization,
            "swap_space": self.swap_space_gb,
            "enforce_eager": True,
            "seed": self.seed,
            # Audit-pass fix: prefix caching is an independent knob.
            # Default behaviour preserved (True iff ctm_plus_evictor)
            # but partners can now set enable_prefix_caching=True
            # for an LRU baseline cell that's directly comparable to
            # a Phase 2 ctm_plus_evictor=True cell on the SAME
            # operational question (cache retention).
            "enable_prefix_caching": self.enable_prefix_caching,
            # preemption_mode: "swap" (default) swaps preempted
            # sequences to CPU; "recompute" instead evicts cached
            # blocks under pressure. Phase 4C diagnostic: the swap
            # path bypasses the LRUEvictor that extended-pinning
            # wraps, so recompute mode is needed to actually
            # exercise the pinning evictor wrap on workloads that
            # don't naturally fill the cache.
            "preemption_mode": self.preemption_mode,
        }
        # FP8 KV cache lane. Only set the field when the caller asked
        # for an override — leave the AsyncEngineArgs default in place
        # otherwise so vLLM picks "auto" (= weight dtype). Setting
        # kv_cache_dtype="fp8" on an A100/H100 routes K/V storage
        # through the hardware tensor cores at 2x compression.
        if self.kv_cache_dtype is not None:
            kwargs["kv_cache_dtype"] = self.kv_cache_dtype
        # Phase 4C: max_model_len override for tight-memory scenarios.
        # When None, leave vLLM's per-model default in place.
        if self.max_model_len is not None:
            kwargs["max_model_len"] = self.max_model_len
        # Allow the caller to override or extend the args, e.g. to
        # test with preemption_mode="recompute" for comparison.
        kwargs.update(self.scheduler_config_overrides)
        AsyncEngineArgs = vllm.AsyncEngineArgs
        return AsyncEngineArgs(**kwargs)

    async def _submit_one(
        self,
        engine: Any,
        request_id: str,
        prompt_token_ids: List[int],
        sampling_params: Any,
        request_id_counter: int = -1,
    ) -> int:
        """Submit one request to the async engine and consume its
        outputs. Returns the number of decode tokens generated.

        Phase 3A: also captures submit / first-token / completion
        timestamps into ``self._request_latencies`` for end-of-run
        p50/p99 aggregation. The capture is structurally no-op for
        callers that don't read ``self._request_latencies``.

        Robust to both the old async-iterator API
        (``async for output in engine.generate(...)``) and the
        newer ``await engine.add_request(...)`` + step-based loop.
        We use the iterator API since it's stable across 0.5 → 0.7.
        """
        submit_time = time.perf_counter()
        first_token_time = 0.0
        n_tokens = 0
        last_seen = 0
        evictor = self._installed_evictor
        cohort_index = self._prompt_builder.cohort_of(request_id_counter)
        is_verifier = (
            self._verifier_request_id is not None
            and request_id == self._verifier_request_id
        )
        try:
            async for output in engine.generate(
                {"prompt_token_ids": prompt_token_ids},
                sampling_params,
                request_id,
            ):
                if output.outputs:
                    # output.outputs[0].token_ids accumulates as
                    # generation proceeds; final value is the
                    # total decode count for this request.
                    new_n_tokens = len(output.outputs[0].token_ids)
                    # Phase TIER5A.3 — verifier output capture. Track
                    # the accumulated token_ids list so the post-run
                    # G1 verdict can compare bit-identity across
                    # cells. List is overwritten each yield; final
                    # value is the complete output.
                    if is_verifier:
                        try:
                            self._verifier_output_token_ids = list(
                                output.outputs[0].token_ids
                            )
                            if getattr(output, "finished", False):
                                self._verifier_request_completed = True
                        except Exception:
                            # Best-effort capture; never crash the
                            # decode loop on a token-id readback bug.
                            pass
                    if first_token_time == 0.0 and new_n_tokens > 0:
                        first_token_time = time.perf_counter()
                    n_tokens = new_n_tokens
                    # Phase 4: tick the window-pruning state with
                    # tokens emitted since last yield. When the
                    # counter crosses the interval, prune the 4
                    # lowest-trig-scoring blocks. This is the only
                    # path by which Phase 4's captured K influences
                    # eviction decisions; without it, the trig
                    # signal is captured-but-unused.
                    if evictor is not None and hasattr(
                        evictor, "window_pruning_passed"
                    ):
                        delta = n_tokens - last_seen
                        last_seen = n_tokens
                        if delta > 0 and evictor.window_pruning_passed(delta):
                            try:
                                target = max(
                                    0, len(evictor._tracked) - 4
                                )
                                evictor.window_pruning_pass(
                                    target_blocks=target,
                                )
                            except Exception as exc:
                                logger.warning(
                                    "window_pruning_pass failed: %s",
                                    exc,
                                )
        except Exception as exc:
            # Don't let one failed request kill the whole sweep.
            logger.warning(
                "request %s failed: %s", request_id, exc,
            )
        finally:
            # Audit fix #2: always record the latency snapshot, even
            # if the coroutine was cancelled at wall-budget time.
            # CancelledError is a BaseException (Py 3.8+), not caught
            # by `except Exception`, so without this finally block
            # the slowest requests (the ones cache-aware most-affects
            # via reorder push-back) were silently dropped from the
            # p99 aggregation. Cell C's e2e_p99 in the Phase 3
            # finding doc was a lower bound for this reason.
            completion_time = time.perf_counter()
            self._request_latencies.append(RequestLatency(
                request_id=request_id,
                submit_time=submit_time,
                first_token_time=first_token_time,
                completion_time=completion_time,
                n_decode_tokens=n_tokens,
                cohort_index=cohort_index,
            ))
        return n_tokens

    async def _run_attention_flusher(
        self,
        aggregator: Any,
        evictor: Any,
    ) -> None:
        """Phase 3: periodically flush the attention aggregator to
        the evictor. Running as a separate asyncio task lets the
        attention-capture hook record samples eagerly while we
        deliver them to CTM+'s scoring on a controlled cadence
        (matches the swap-counter sampler interval)."""
        try:
            while True:
                await asyncio.sleep(self.sample_interval_seconds)
                try:
                    aggregator.flush_to_evictor(evictor)
                except Exception as exc:
                    logger.warning(
                        "attention flush to evictor failed: %s", exc,
                    )
        except asyncio.CancelledError:
            # Final flush before exiting so anything captured in
            # the last interval still reaches the evictor.
            try:
                aggregator.flush_to_evictor(evictor)
            except Exception:
                pass

    async def _run_sampler(
        self,
        engine: Any,
        sampler: SwapCounterSampler,
    ) -> None:
        """Periodically poll swap counters from the engine and
        feed them into the sampler. Runs until cancelled."""
        # Track preemption monotonically — get_and_reset_swaps()
        # resets the swap counters each call, but preemption is
        # often a monotonic total. We compute the delta ourselves.
        last_preemption_total = 0
        try:
            while True:
                await asyncio.sleep(self.sample_interval_seconds)
                in_b, out_b, preempt_total = (
                    _read_swap_counters_from_engine(engine)
                )
                preempt_delta = max(0, preempt_total - last_preemption_total)
                last_preemption_total = preempt_total
                try:
                    sampler.record_sample(
                        swap_in_blocks=in_b,
                        swap_out_blocks=out_b,
                        preemption_events=preempt_delta,
                    )
                except RuntimeError:
                    # Sampler stopped; stop polling.
                    return
        except asyncio.CancelledError:
            pass

    async def _run_cpu_swap_pool_sampler(self) -> None:
        """Phase TIER5A — periodically poll the CPU swap pool gauge
        (``read_cpu_swap_pool``) and feed snapshots into the
        ``CpuSwapPoolPeakTracker`` set up at install time.

        Matches the cadence of ``_run_sampler`` so the gauge and
        counter timelines align. Without this loop, the peak
        degenerates to a single end-of-cell snapshot — likely 0
        after the swap-in restore has drained the CPU pool — and
        the G3 acceptance gate false-fails on a successful swap.

        Errors during a single read are swallowed (best-effort
        telemetry; never crash the run); the next sample tries
        again.
        """
        from kv_policy.swap_telemetry import read_cpu_swap_pool  # type: ignore
        bm = self._swap_telemetry_block_manager_ref
        tracker = self._cpu_swap_pool_peak_tracker
        if bm is None or tracker is None:
            return
        try:
            while True:
                await asyncio.sleep(self.sample_interval_seconds)
                try:
                    snapshot = read_cpu_swap_pool(bm)
                    tracker.observe(snapshot)
                except Exception as exc:
                    logger.debug(
                        "cpu_swap_pool sampler tick failed: %s", exc,
                    )
        except asyncio.CancelledError:
            # Final read so the end-of-cell snapshot is captured.
            try:
                snapshot = read_cpu_swap_pool(bm)
                tracker.observe(snapshot)
            except Exception:
                pass

    async def run(
        self,
        *,
        scheduler: ArrivalScheduler,
        sampler: SwapCounterSampler,
        max_requests: int,
        max_wall_seconds: float,
        workload_name: str,
    ) -> StreamingRunCellResult:
        """Run the streaming workload to completion or budget.

        Returns the cell result with swap-counter totals.

        When ``ctm_plus_evictor=True`` (Phase 2), the run also
        installs ``CTMEvictorModern`` on the engine's
        ``PrefixCachingBlockAllocator`` after construction. This
        path requires ``enable_prefix_caching=True`` (set by
        ``_build_engine_args``); if the patch can't install (e.g.
        prefix caching off, vLLM minor version mismatch), the
        underlying ``patch_vllm_engine_modern`` raises with a
        clear message.
        """
        vllm = self._import_vllm()
        engine_args = self._build_engine_args(vllm)
        AsyncLLMEngine = vllm.AsyncLLMEngine
        SamplingParams = vllm.SamplingParams

        engine = AsyncLLMEngine.from_engine_args(engine_args)

        # Audit-pass fix: the patch can raise (NotImplementedError
        # on enable_prefix_caching=False, RuntimeError on
        # allocator-version drift). If it raises here, before the
        # main run try/finally starts, the engine leaks GPU memory
        # and worker subprocesses. Tear down explicitly on failure.
        installed_evictor = None
        attention_aggregator = None
        if self.ctm_plus_evictor:
            try:
                # Phase 4: load calibration before installing the
                # evictor so the patch can hand the scorer to
                # CTMEvictorModern at construction time.
                trig_scorer = None
                if self.phase4_trig_calibration_path is not None:
                    from kv_policy.triattention import (  # type: ignore
                        QCenterStats, TrigScorer,
                    )
                    stats = QCenterStats.load(
                        self.phase4_trig_calibration_path
                    )
                    trig_scorer = TrigScorer(
                        stats=stats,
                        future_offsets=self.phase4_future_offsets,
                    )
                    logger.info(
                        "Phase 4: loaded calibration for %s "
                        "(%d layers, %d heads, %d bands; %d tokens, "
                        "corpus=%s)",
                        stats.model_name, stats.num_layers,
                        stats.num_heads, stats.num_bands,
                        stats.calibration_token_count,
                        stats.calibration_corpus,
                    )
                installed_evictor = patch_vllm_engine_modern(
                    getattr(engine, "engine", engine),
                    enable_logging=False,
                    trig_scorer=trig_scorer,
                    window_pruning_interval=self.phase4_window_interval,
                    trig_blend_candidate_count=self.phase4_trig_blend_candidate_count,
                    use_cython_evictor=self.phase4_use_cython_evictor,
                )
                logger.info(
                    "Phase 2: CTM+ evictor patch installed on "
                    "AsyncLLMEngine"
                )
                # Phase 4 GPU hooks: install_pre_rope_capture +
                # install_attn_metadata_side_channel, both pointing
                # at the same evictor. The capture hook reads the
                # side-channel during each rotary_emb pre-hook
                # firing.
                if self.phase4_trig_calibration_path is not None:
                    from kv_policy.triattention import (  # type: ignore
                        install_pre_rope_capture,
                        install_attn_metadata_side_channel,
                    )
                    inner_engine = getattr(engine, "engine", engine)
                    model = self._extract_model_from_engine(inner_engine)
                    n_attn = install_attn_metadata_side_channel(
                        model=model, evictor=installed_evictor,
                        via_monkey_patch=self.phase4_fast_hooks,
                    )
                    # Pull num_layers from the model config so
                    # call-counter indexing kicks in for shared-rotary
                    # models (Qwen2.5 / Llama / Mistral). Matches what
                    # the calibration script writes into the JSON.
                    config = getattr(model, "config", None)
                    runtime_num_layers = (
                        self.phase4_num_layers if self.phase4_num_layers
                        else int(getattr(
                            config, "num_hidden_layers",
                            getattr(config, "n_layers", 1),
                        )) if config is not None else 1
                    )
                    n_rotary = install_pre_rope_capture(
                        model=model, evictor=installed_evictor,
                        num_layers=runtime_num_layers,
                        capture_every_n=self.phase4_capture_every_n,
                        via_monkey_patch=self.phase4_fast_hooks,
                    )
                    logger.info(
                        "Phase 4: hooks installed (attn_metadata "
                        "side-channel on top-level model: %d, "
                        "pre-RoPE K capture on %d rotary_emb "
                        "modules; num_layers=%d, capture_every_n=%d).",
                        n_attn, n_rotary, runtime_num_layers,
                        self.phase4_capture_every_n,
                    )
                if self.phase3_attention_capture:
                    # Phase 3: install the attention-capture hook
                    # on the model's Attention layers. The hook
                    # pushes per-block attention sums to the
                    # aggregator; the run loop flushes the aggregator
                    # to the evictor periodically (after each
                    # decode-step batch).
                    from kv_policy.vllm_evictor import (  # type: ignore
                        AttentionAggregator,
                        install_attention_capture,
                    )
                    inner_engine = getattr(engine, "engine", engine)
                    model = self._extract_model_from_engine(inner_engine)
                    attention_aggregator = AttentionAggregator()
                    n_patched = install_attention_capture(
                        model=model,
                        aggregator=attention_aggregator,
                        evictor=installed_evictor,
                        capture_every_n=self.phase3_capture_every_n,
                        # Surface capture exceptions during bridge
                        # debugging. Day 5b iteration 2 May 2026
                        # had 0 samples; without this we couldn't
                        # see WHY. Keep on until bridge is green.
                        enable_logging=True,
                    )
                    logger.info(
                        "Phase 3: attention capture installed on "
                        "%d Attention layers (capture_every_n=%d)",
                        n_patched, self.phase3_capture_every_n,
                    )
            except BaseException:
                # Best-effort teardown then re-raise. Same chain
                # of teardown methods as the run-end finally
                # block — see comment there.
                for shutdown_name in (
                    "shutdown_background_loop",
                    "shutdown",
                    "stop",
                ):
                    shutdown = getattr(engine, shutdown_name, None)
                    if shutdown is None:
                        continue
                    try:
                        result = shutdown()
                        if asyncio.iscoroutine(result):
                            await result
                        break
                    except Exception:
                        continue
                raise

        # Route-A INT4 KV-cache install. Orthogonal to the CTM+
        # evictor — if both are on, INT4 compression and CTM+ eviction
        # compose (the §"What CTM+ Phase 4 gets out of this" point in
        # ROUTE_A_VLLM_CACHE_KV_PLAN.md). Installed AFTER the evictor
        # so the attention-forward wrap sits closest to the call.
        int4_route_a_manager = None
        int4_route_a_teardown = None
        if self.int4_kv_route_a:
            try:
                from kv_policy.int4_cache_kv_route_a import (  # type: ignore
                    install_int4_cache_kv_route_a,
                )
                inner_engine = getattr(engine, "engine", engine)
                model = self._extract_model_from_engine(inner_engine)
                int4_route_a_manager, int4_route_a_teardown = (
                    install_int4_cache_kv_route_a(
                        model=model,
                        k_group_size=self.int4_kv_k_group_size,
                        v_group_size=self.int4_kv_v_group_size,
                        asymmetric=self.int4_kv_asymmetric,
                        bits=self.int4_kv_bits,
                        sink_size=self.int4_kv_sink_size,
                        num_kv_heads=self.int4_kv_num_kv_heads,
                    )
                )
                logger.info(
                    "Route-A INT4 KV-cache installed (%s)",
                    int4_route_a_manager.config["scheme"],
                )
            except BaseException:
                # Same best-effort engine teardown as the ctm_plus
                # block: a failed install must not leak GPU memory.
                for shutdown_name in (
                    "shutdown_background_loop", "shutdown", "stop",
                ):
                    shutdown = getattr(engine, shutdown_name, None)
                    if shutdown is None:
                        continue
                    try:
                        result = shutdown()
                        if asyncio.iscoroutine(result):
                            await result
                        break
                    except Exception:
                        continue
                raise

        # Phase TIER5A — swap-restore telemetry install. Runs BEFORE
        # the allocate-wrapping layers (prefix_hit_probe / extended
        # _pinning / cache_aware) since its wrap target is the swap
        # entry point (block_manager.swap_in / block_allocator.swap
        # / cpu_allocator.swap_in), which is disjoint from the
        # allocate fan-out — install order doesn't change observed
        # behaviour, but installing innermost matches the LIFO
        # teardown discipline of the composition smoke.
        if self.swap_telemetry:
            try:
                from kv_policy.swap_telemetry import (  # type: ignore
                    CpuSwapPoolPeakTracker,
                    install_swap_in_latency_probe,
                )
                inner_engine_for_swap = getattr(engine, "engine", engine)
                sched_attr_swap = getattr(
                    inner_engine_for_swap, "scheduler", None,
                )
                if sched_attr_swap is None:
                    raise RuntimeError(
                        "swap_telemetry=True but the engine has no "
                        ".scheduler attribute"
                    )
                sched_for_swap = (
                    sched_attr_swap[0]
                    if isinstance(sched_attr_swap, list)
                    else sched_attr_swap
                )
                bm_for_swap = getattr(
                    sched_for_swap, "block_manager", None,
                )
                if bm_for_swap is None:
                    raise RuntimeError(
                        "swap_telemetry=True but the scheduler has no "
                        ".block_manager attribute"
                    )
                swap_probe = install_swap_in_latency_probe(
                    bm_for_swap, enable=True,
                )
                self._swap_in_latency_probe = swap_probe
                self._cpu_swap_pool_peak_tracker = CpuSwapPoolPeakTracker()
                self._swap_telemetry_block_manager_ref = bm_for_swap
                logger.info(
                    "Phase TIER5A: swap-restore telemetry installed "
                    "(probe_enabled=%s, hint_path=%s, "
                    "wrap_target=%s)",
                    swap_probe.enabled,
                    swap_probe.hint_path,
                    swap_probe.wrap_target_name,
                )
            except BaseException:
                # No prior installs yet (swap_telemetry is innermost);
                # just engine shutdown + re-raise.
                for shutdown_name in (
                    "shutdown_background_loop", "shutdown", "stop",
                ):
                    shutdown = getattr(engine, shutdown_name, None)
                    if shutdown is None:
                        continue
                    try:
                        result = shutdown()
                        if asyncio.iscoroutine(result):
                            await result
                        break
                    except Exception:
                        continue
                raise

        # Phase 3A — native prefix-hit probe install. Must run BEFORE
        # the cache-aware install so the probe is innermost in the
        # call chain (cache-aware wraps over the probe wraps over the
        # original allocate). The probe is measurement-only — no
        # admission reordering — so it composes cleanly with both
        # FCFS (cell B) and cache-aware (cell C) cells.
        prefix_hit_probe: Any = None
        if self.collect_native_prefix_hits:
            try:
                from kv_policy.prefix_hit_probe import (  # type: ignore
                    install_prefix_hit_probe,
                )
                inner_engine_for_probe = getattr(engine, "engine", engine)
                sched_attr_probe = getattr(inner_engine_for_probe, "scheduler", None)
                if sched_attr_probe is None:
                    raise RuntimeError(
                        "collect_native_prefix_hits=True but the engine "
                        "has no .scheduler attribute"
                    )
                sched_for_probe = (
                    sched_attr_probe[0]
                    if isinstance(sched_attr_probe, list)
                    else sched_attr_probe
                )
                bm_for_probe = getattr(sched_for_probe, "block_manager", None)
                if bm_for_probe is None:
                    raise RuntimeError(
                        "collect_native_prefix_hits=True but the scheduler "
                        "has no .block_manager attribute"
                    )
                # Audit fix #3: read vLLM's actual block_size at
                # install time, don't hardcode 32.
                resolved_block_size = _resolve_block_size_from_engine(
                    engine, default=32,
                )
                prefix_hit_probe = install_prefix_hit_probe(
                    block_manager=bm_for_probe,
                    block_size=resolved_block_size,
                    enable=True,
                )
                # Audit fix #5: assign the probe handle to self
                # IMMEDIATELY (before any later install can fail).
                # Previously self._prefix_hit_probe was assigned
                # several lines below, AFTER the cache-aware
                # install ran — meaning a cache-aware install
                # failure left the probe's allocate-wrap installed
                # but unreachable for teardown.
                self._prefix_hit_probe = prefix_hit_probe
                logger.info(
                    "Phase 3A: prefix-hit probe installed "
                    "(path_taken=%s, vllm_version_hint=%s, "
                    "block_size=%d)",
                    prefix_hit_probe.path_taken,
                    prefix_hit_probe.vllm_version_hint,
                    resolved_block_size,
                )
            except BaseException:
                # Tear down swap_telemetry probe (innermost; installed
                # before this) before engine shutdown.
                if self._swap_in_latency_probe is not None:
                    try:
                        self._swap_in_latency_probe.teardown()
                    except Exception as exc:
                        logger.warning(
                            "swap_telemetry teardown on prefix-hit "
                            "install failure failed: %s", exc,
                        )
                for shutdown_name in (
                    "shutdown_background_loop", "shutdown", "stop",
                ):
                    shutdown = getattr(engine, shutdown_name, None)
                    if shutdown is None:
                        continue
                    try:
                        result = shutdown()
                        if asyncio.iscoroutine(result):
                            await result
                        break
                    except Exception:
                        continue
                raise

        # Phase 4B — Extended pinning install. Sits between probe
        # (innermost) and cache-aware (outermost) in the call chain.
        # Probe wraps original allocate; pinning wraps probe's
        # allocate; cache-aware wraps pinning's allocate. The
        # pinning install ALSO wraps evictor.evict (only pinning
        # touches the evictor).
        extended_pinning_install: Any = None
        if self.extended_pinning:
            try:
                from kv_policy.extended_pinning import (  # type: ignore
                    PinSpec,
                    install_extended_pinning,
                )
                inner_engine_for_pin = getattr(engine, "engine", engine)
                sched_attr_pin = getattr(
                    inner_engine_for_pin, "scheduler", None,
                )
                if sched_attr_pin is None:
                    raise RuntimeError(
                        "extended_pinning=True but the engine has no "
                        ".scheduler attribute"
                    )
                sched_for_pin = (
                    sched_attr_pin[0]
                    if isinstance(sched_attr_pin, list)
                    else sched_attr_pin
                )
                bm_for_pin = getattr(sched_for_pin, "block_manager", None)
                if bm_for_pin is None:
                    raise RuntimeError(
                        "extended_pinning=True but the scheduler has no "
                        ".block_manager attribute"
                    )
                pin_specs = self._build_pin_specs()
                pin_block_size = _resolve_block_size_from_engine(
                    engine, default=32,
                )
                extended_pinning_install = install_extended_pinning(
                    block_manager=bm_for_pin,
                    pin_specs=pin_specs,
                    max_budget_blocks=self.pin_max_budget_blocks,
                    enable=True,
                    block_size=pin_block_size,
                )
                # Assign handle to self immediately (matches the
                # audit fix #5 pattern for the probe + cache-aware
                # installs) so any later install failure leaves the
                # finally block able to tear this down.
                self._extended_pinning_install = extended_pinning_install
                logger.info(
                    "Phase 4B: extended pinning installed "
                    "(n_specs=%d, evictor_path_taken=%s, "
                    "block_size=%d, max_budget_blocks=%d)",
                    len(pin_specs),
                    extended_pinning_install.evictor_path_taken,
                    pin_block_size,
                    self.pin_max_budget_blocks,
                )
            except BaseException:
                # Tear down probe (installed before this) before
                # propagating, then engine shutdown.
                if self._prefix_hit_probe is not None:
                    try:
                        self._prefix_hit_probe.teardown()
                    except Exception as exc:
                        logger.warning(
                            "prefix-hit probe teardown on "
                            "extended-pinning install failure failed: %s",
                            exc,
                        )
                if self._swap_in_latency_probe is not None:
                    try:
                        self._swap_in_latency_probe.teardown()
                    except Exception as exc:
                        logger.warning(
                            "swap_telemetry teardown on extended-"
                            "pinning install failure failed: %s", exc,
                        )
                for shutdown_name in (
                    "shutdown_background_loop", "shutdown", "stop",
                ):
                    shutdown = getattr(engine, shutdown_name, None)
                    if shutdown is None:
                        continue
                    try:
                        result = shutdown()
                        if asyncio.iscoroutine(result):
                            await result
                        break
                    except Exception:
                        continue
                raise

        # v2 cache-reuse PR-2 — cache-aware admission scheduler install.
        # Lives at the scheduler layer; orthogonal to int4_protected, CTM+,
        # and route-A INT4 (all of which act at the attention layer).
        # Walks engine.engine.scheduler{[0]}.block_manager — the same
        # path the swap-counter probe uses.
        #
        # Phase 3C: also installs (in measurement_only mode) when
        # cache_aware_measurement_only=True. Allocate/free wraps fire
        # for realized-hit measurement; schedule reorder wrap is
        # skipped so admission order is unchanged from stock FCFS.
        cache_aware_install: Any = None
        install_cache_aware = (
            self.cache_aware_scheduling
            or self.cache_aware_measurement_only
        )
        if install_cache_aware:
            try:
                from kv_policy.cache_aware_install import (  # type: ignore
                    install_cache_aware_scheduler,
                )
                inner_engine = getattr(engine, "engine", engine)
                sched_attr = getattr(inner_engine, "scheduler", None)
                if sched_attr is None:
                    raise RuntimeError(
                        "cache-aware install requested but the engine "
                        "has no .scheduler attribute"
                    )
                sched = (
                    sched_attr[0] if isinstance(sched_attr, list)
                    else sched_attr
                )
                bm = getattr(sched, "block_manager", None)
                if bm is None:
                    raise RuntimeError(
                        "cache-aware install requested but the scheduler "
                        "has no .block_manager attribute"
                    )
                # Audit fix #3: same resolved block_size as the
                # probe install (and falls back to 32 when the
                # probe wasn't installed — i.e. cache-aware-only
                # path with no probe).
                resolved_block_size = _resolve_block_size_from_engine(
                    engine, default=32,
                )
                cache_aware_install = install_cache_aware_scheduler(
                    scheduler=sched,
                    block_manager=bm,
                    enable=True,
                    measurement_only=self.cache_aware_measurement_only,
                    block_size=resolved_block_size,
                    max_starvation_seconds=(
                        self.cache_aware_max_starvation_seconds
                    ),
                )
                # Audit fix #5 (symmetry with probe): assign handle
                # to self immediately so any later failure leaves
                # the finally block able to tear this down.
                self._cache_aware_install = cache_aware_install
                logger.info(
                    "v2 cache-reuse: cache-aware install (%s) "
                    "(block_size=%d, max_starvation_seconds=%.1f)",
                    "measurement_only" if self.cache_aware_measurement_only
                    else "full",
                    resolved_block_size,
                    self.cache_aware_max_starvation_seconds,
                )
            except BaseException:
                # Audit fix #5 (continued): if the cache-aware install
                # fails, prior installs (probe + extended_pinning) would
                # otherwise leak — the main-loop try/finally is
                # unreachable from here because we're still in the
                # setup phase. Tear them down explicitly LIFO before
                # propagating the exception.
                if self._extended_pinning_install is not None:
                    try:
                        self._extended_pinning_install.teardown()
                    except Exception as exc:
                        logger.warning(
                            "extended pinning teardown on cache-aware "
                            "install failure failed: %s", exc,
                        )
                if self._prefix_hit_probe is not None:
                    try:
                        self._prefix_hit_probe.teardown()
                    except Exception as exc:
                        logger.warning(
                            "prefix-hit probe teardown on cache-aware "
                            "install failure failed: %s", exc,
                        )
                if self._swap_in_latency_probe is not None:
                    try:
                        self._swap_in_latency_probe.teardown()
                    except Exception as exc:
                        logger.warning(
                            "swap_telemetry teardown on cache-aware "
                            "install failure failed: %s", exc,
                        )
                # Best-effort engine teardown on install failure — same
                # chain as the ctm_plus and route-A install blocks above.
                for shutdown_name in (
                    "shutdown_background_loop", "shutdown", "stop",
                ):
                    shutdown = getattr(engine, shutdown_name, None)
                    if shutdown is None:
                        continue
                    try:
                        result = shutdown()
                        if asyncio.iscoroutine(result):
                            await result
                        break
                    except Exception:
                        continue
                raise

        # Stash so the run loop can flush after each decode batch.
        # NOTE: self._cache_aware_install and self._prefix_hit_probe
        # are also assigned inside their respective install blocks
        # immediately after construction (Audit fix #5) so that a
        # later install failure leaves the finally block able to
        # tear them down. These re-assignments are idempotent
        # noops — same object — but kept for symmetry with the
        # other handles that don't have the same failure-mode risk.
        self._attention_aggregator = attention_aggregator
        self._installed_evictor = installed_evictor
        self._int4_route_a_manager = int4_route_a_manager
        self._int4_route_a_teardown = int4_route_a_teardown
        self._cache_aware_install = cache_aware_install
        self._prefix_hit_probe = prefix_hit_probe
        self._extended_pinning_install = extended_pinning_install
        sampling_params = SamplingParams(
            temperature=0.0,
            max_tokens=self.max_decode_tokens,
            seed=self.seed,
        )

        sampler_task = asyncio.create_task(
            self._run_sampler(engine, sampler)
        )

        # Phase TIER5A — parallel sampler that polls
        # read_cpu_swap_pool on the same cadence and feeds the
        # CpuSwapPoolPeakTracker. Only spawned when swap_telemetry
        # is on AND the install succeeded (probe + tracker both
        # populated). Without this loop, peak collapses to the
        # final-snapshot value and G3 false-fails.
        cpu_swap_pool_sampler_task = None
        if (
            self.swap_telemetry
            and self._swap_in_latency_probe is not None
            and self._cpu_swap_pool_peak_tracker is not None
        ):
            cpu_swap_pool_sampler_task = asyncio.create_task(
                self._run_cpu_swap_pool_sampler()
            )

        # Phase 3: a parallel flusher that periodically pushes
        # accumulated per-block attention from the aggregator into
        # the evictor. The flush cadence matches the swap-counter
        # sampler — they're both polling-style; running them on
        # the same heartbeat keeps the state machines simple.
        attention_flush_task = None
        if self._attention_aggregator is not None and self._installed_evictor is not None:
            attention_flush_task = asyncio.create_task(
                self._run_attention_flusher(
                    self._attention_aggregator,
                    self._installed_evictor,
                )
            )

        n_admitted = 0
        n_completed = 0
        n_decode_tokens = 0
        submission_tasks: List[asyncio.Task] = []
        request_id_counter = 0
        start = time.perf_counter()

        # Phase TIER5A.3 — submit the verifier request FIRST, before
        # any pressure arrives. Doing so admits the verifier while
        # GPU memory is uncontested; the subsequent pressure workload
        # then has to choose whether to preempt the verifier (which
        # is exactly the path TIER5A is verifying — the int4_protected
        # KV layout must survive that preempt + restore cycle).
        if self.verifier_prompt_token_ids is not None:
            verifier_max_tokens = (
                self.verifier_max_decode_tokens
                if self.verifier_max_decode_tokens is not None
                else self.max_decode_tokens
            )
            verifier_sampling_params = SamplingParams(
                temperature=0.0,
                max_tokens=verifier_max_tokens,
                seed=self.seed,
            )
            self._verifier_request_id = (
                f"tier5a_verifier_{workload_name}_{self.seed}"
            )
            submission_tasks.append(
                asyncio.create_task(
                    self._submit_one(
                        engine=engine,
                        request_id=self._verifier_request_id,
                        prompt_token_ids=list(self.verifier_prompt_token_ids),
                        sampling_params=verifier_sampling_params,
                        request_id_counter=request_id_counter,
                    )
                )
            )
            n_admitted += 1
            request_id_counter += 1
            logger.info(
                "TIER5A verifier submitted (request_id=%s, "
                "prompt_tokens=%d, max_decode=%d)",
                self._verifier_request_id,
                len(self.verifier_prompt_token_ids),
                verifier_max_tokens,
            )

        try:
            while True:
                wall = time.perf_counter() - start
                if wall >= max_wall_seconds:
                    logger.info("wall budget exhausted (%.2fs)", wall)
                    break
                if n_admitted >= max_requests:
                    break

                delay = scheduler.next_arrival_delay_seconds()
                if delay is None:
                    # replay schedule exhausted
                    break
                if delay > 0:
                    # Cap the sleep so we don't sleep past the wall
                    # budget on a single heavy-tailed Pareto draw.
                    remaining = max_wall_seconds - wall
                    await asyncio.sleep(min(delay, max(0.0, remaining)))

                if time.perf_counter() - start >= max_wall_seconds:
                    break

                length = scheduler.next_prompt_length()
                # Phase 3A: prompt content is owned by self._prompt_builder
                # — either the legacy ParetoUniqueHeadPromptBuilder
                # (per-request unique head, defeats prefix caching;
                # default) or SharedPrefixPromptBuilder (cohort-shared,
                # used for cells B and C of the Phase 3 measurement).
                prompt_token_ids = self._prompt_builder.build(
                    request_id_counter=request_id_counter,
                    suggested_length=length,
                )
                request_id = f"streaming_{workload_name}_{request_id_counter}"
                current_request_id_counter = request_id_counter
                request_id_counter += 1

                task = asyncio.create_task(
                    self._submit_one(
                        engine, request_id, prompt_token_ids,
                        sampling_params,
                        request_id_counter=current_request_id_counter,
                    )
                )
                submission_tasks.append(task)
                n_admitted += 1

            # Drain in-flight requests within remaining wall budget.
            wall = time.perf_counter() - start
            remaining = max(0.0, max_wall_seconds - wall)
            if submission_tasks:
                done, pending = await asyncio.wait(
                    submission_tasks, timeout=remaining,
                )
                for t in done:
                    try:
                        result = t.result()
                        if isinstance(result, int):
                            n_decode_tokens += result
                            if result > 0:
                                n_completed += 1
                    except Exception as exc:
                        logger.warning("submission task error: %s", exc)
                for t in pending:
                    t.cancel()
        finally:
            sampler.stop()
            sampler_task.cancel()
            try:
                await sampler_task
            except asyncio.CancelledError:
                pass
            # Surface route-A INT4 stats so a silent no-op is
            # detectable: if `forward_calls == 0` the interception
            # never fired (wrong K/V arg indices, or this vLLM
            # version's attention layer doesn't take K/V positionally).
            if self._int4_route_a_manager is not None:
                st = self._int4_route_a_manager.stats
                if st["forward_calls"] == 0:
                    logger.warning(
                        "route-A INT4: forward_calls=0 — the "
                        "interception NEVER FIRED. Output is "
                        "baseline-identical. Check --int4-kv-* arg "
                        "indices against this vLLM version's "
                        "Attention.forward signature."
                    )
                else:
                    logger.info(
                        "route-A INT4 stats: forward_calls=%d, "
                        "tokens_compressed=%d, sink_passthrough=%d, "
                        "skipped_unknown_shape=%d",
                        st["forward_calls"], st["tokens_compressed"],
                        st["sink_tokens_passed_through"],
                        st["skipped_unknown_shape"],
                    )
                    if st["skipped_unknown_shape"] > 0:
                        logger.warning(
                            "route-A INT4: %d forwards skipped — 2-D "
                            "K/V arrived but num_kv_heads was unknown. "
                            "Pass --int4-kv-num-kv-heads explicitly.",
                            st["skipped_unknown_shape"],
                        )
            # Revert the route-A INT4 attention-forward wraps before
            # engine shutdown. Best-effort; never crash the run.
            if self._int4_route_a_teardown is not None:
                try:
                    self._int4_route_a_teardown()
                except Exception as exc:
                    logger.warning(
                        "route-A INT4 teardown failed: %s", exc,
                    )
            # v2 cache-reuse PR-2 — revert the scheduler / block_manager
            # wraps before engine shutdown. Best-effort; the install
            # handle's teardown() is itself a no-op on the disabled
            # path and idempotent on re-entry.
            #
            # LIFO chain: cache-aware (outermost) -> extended_pinning
            # -> prefix_hit_probe -> original.
            if self._cache_aware_install is not None:
                try:
                    self._cache_aware_install.teardown()
                except Exception as exc:
                    logger.warning(
                        "cache-aware scheduler teardown failed: %s", exc,
                    )
            # Phase 4B — revert extended pinning wraps.
            if self._extended_pinning_install is not None:
                try:
                    self._extended_pinning_install.teardown()
                except Exception as exc:
                    logger.warning(
                        "extended pinning teardown failed: %s", exc,
                    )
            # Phase 3A — revert the prefix-hit probe wrap.
            if self._prefix_hit_probe is not None:
                try:
                    self._prefix_hit_probe.teardown()
                except Exception as exc:
                    logger.warning(
                        "prefix-hit probe teardown failed: %s", exc,
                    )
            # Phase TIER5A — cancel CPU swap pool sampler + revert
            # swap-in latency probe wrap (innermost of the four; tears
            # down LAST in the LIFO chain).
            if cpu_swap_pool_sampler_task is not None:
                cpu_swap_pool_sampler_task.cancel()
                try:
                    await cpu_swap_pool_sampler_task
                except asyncio.CancelledError:
                    pass
            if self._swap_in_latency_probe is not None:
                try:
                    self._swap_in_latency_probe.teardown()
                except Exception as exc:
                    logger.warning(
                        "swap-in latency probe teardown failed: %s",
                        exc,
                    )
            if attention_flush_task is not None:
                attention_flush_task.cancel()
                try:
                    await attention_flush_task
                except asyncio.CancelledError:
                    pass
            # Shut down vLLM's worker subprocess explicitly. Without
            # this, a multi-cell sweep can leak GPU memory across
            # cells because the previous engine's workers stay alive
            # holding KV-cache allocations. Try several teardown
            # API names — vLLM has changed the public method across
            # 0.5 → 0.7. Best-effort; never crash the run.
            for shutdown_name in (
                "shutdown_background_loop",
                "shutdown",
                "stop",
            ):
                shutdown = getattr(engine, shutdown_name, None)
                if shutdown is None:
                    continue
                try:
                    result = shutdown()
                    if asyncio.iscoroutine(result):
                        await result
                    break
                except Exception as exc:
                    logger.warning(
                        "engine teardown via %s failed: %s",
                        shutdown_name, exc,
                    )

        wall = time.perf_counter() - start
        totals = sampler.totals()

        # Per-evict timing (Phase 2/3 only — Phase 1 LRU baseline
        # leaves these at zero since vLLM's native LRUEvictor is
        # not in our control to time).
        evict_timings: List[float] = []
        if self._installed_evictor is not None:
            evict_timings_method = getattr(
                self._installed_evictor, "evict_timings_seconds", None,
            )
            if callable(evict_timings_method):
                try:
                    evict_timings = list(evict_timings_method())
                except Exception:
                    evict_timings = []

        evict_p50_us, evict_p99_us = self._compute_p50_p99_microseconds(
            evict_timings
        )
        evict_total_seconds = sum(evict_timings)
        evict_call_count = len(evict_timings)

        # Phase 3 attention-capture timing.
        capture_timings: List[float] = []
        if self._attention_aggregator is not None:
            getter = getattr(
                self._attention_aggregator, "capture_timings_seconds", None,
            )
            if callable(getter):
                try:
                    capture_timings = list(getter())
                except Exception:
                    capture_timings = []

        attention_capture_total_seconds = sum(capture_timings)
        attention_capture_call_count = len(capture_timings)

        # Phase 4 metrics (populated when phase4_trig_calibration_path
        # was set; zeros otherwise).
        phase4_window_invocations = 0
        phase4_blocks_with_keys = 0
        if (
            self.phase4_trig_calibration_path is not None
            and self._installed_evictor is not None
        ):
            phase4_window_invocations = int(
                getattr(
                    self._installed_evictor,
                    "window_pruning_invocations",
                    0,
                )
            )
            phase4_blocks_with_keys = len(
                getattr(
                    self._installed_evictor,
                    "_block_pre_rope_keys",
                    {},
                )
            )

        # Throughput.
        if wall > 0 and n_decode_tokens > 0:
            tokens_per_second = n_decode_tokens / wall
        else:
            tokens_per_second = 0.0

        # Stats snapshots — populated from the live managers BEFORE
        # teardown. Phase 8b bridge verification reads these from the
        # streaming_summary.json to assert the bridge is working.
        int4_route_a_stats: Dict[str, Any] = {}
        if self._int4_route_a_manager is not None:
            try:
                int4_route_a_stats = dict(self._int4_route_a_manager.stats)
            except Exception:
                int4_route_a_stats = {}

        attention_aggregator_stats: Dict[str, Any] = {}
        if self._attention_aggregator is not None:
            try:
                attention_aggregator_stats = dict(
                    self._attention_aggregator.stats
                )
            except Exception:
                attention_aggregator_stats = {}

        # v2 cache-reuse PR-2 — snapshot scheduler stats. Empty dict
        # when the install was OFF; CacheAwareInstall.stats() returns
        # {"enabled": False} for the disabled stub but we keep the
        # empty-dict default for symmetry with the other stats fields.
        cache_aware_scheduler_stats: Dict[str, Any] = {}
        if self._cache_aware_install is not None:
            try:
                cache_aware_scheduler_stats = dict(
                    self._cache_aware_install.stats()
                )
            except Exception:
                cache_aware_scheduler_stats = {
                    "enabled": True, "error": "stats() raised",
                }

        # Phase 3A native prefix-hit probe — snapshot before
        # teardown of the underlying handle.
        native_prefix_hit_stats: Dict[str, Any] = {}
        if self._prefix_hit_probe is not None:
            try:
                native_prefix_hit_stats = dict(
                    self._prefix_hit_probe.stats()
                )
            except Exception:
                native_prefix_hit_stats = {
                    "installed": True, "error": "stats() raised",
                }

        # Phase 4B extended pinning — snapshot before teardown.
        extended_pinning_stats: Dict[str, Any] = {}
        if self._extended_pinning_install is not None:
            try:
                extended_pinning_stats = dict(
                    self._extended_pinning_install.stats()
                )
            except Exception:
                extended_pinning_stats = {
                    "enabled": True, "error": "stats() raised",
                }

        # Phase TIER5A — swap-restore telemetry: read probe + tracker
        # stats. The probe's teardown reverted the wrap but preserved
        # the recorded latencies_ms list; the tracker has no teardown
        # (pure data object), so its peak/final are stable to read.
        swap_telemetry_stats_dict: Dict[str, Any] = {}
        cpu_swap_pool_used_blocks_peak_val = 0
        cpu_swap_pool_used_blocks_final_val = 0
        cpu_swap_pool_total_blocks_val = 0
        swap_in_latency_p50_ms_val = 0.0
        swap_in_latency_p99_ms_val = 0.0
        swap_in_latency_call_count_val = 0
        if self._swap_in_latency_probe is not None:
            try:
                probe_stats = self._swap_in_latency_probe.stats()
                swap_telemetry_stats_dict["probe"] = dict(probe_stats)
                swap_in_latency_p50_ms_val = float(probe_stats.get("p50_ms", 0.0))
                swap_in_latency_p99_ms_val = float(probe_stats.get("p99_ms", 0.0))
                swap_in_latency_call_count_val = int(
                    probe_stats.get("call_count", 0)
                )
            except Exception as exc:
                swap_telemetry_stats_dict["probe_error"] = str(exc)
        if self._cpu_swap_pool_peak_tracker is not None:
            try:
                tracker_stats = self._cpu_swap_pool_peak_tracker.stats()
                swap_telemetry_stats_dict["tracker"] = dict(tracker_stats)
                cpu_swap_pool_used_blocks_peak_val = int(
                    tracker_stats.get("peak_used_blocks", 0)
                )
                cpu_swap_pool_used_blocks_final_val = int(
                    tracker_stats.get("final_used_blocks", 0)
                )
                cpu_swap_pool_total_blocks_val = int(
                    tracker_stats.get("total_blocks", 0)
                )
            except Exception as exc:
                swap_telemetry_stats_dict["tracker_error"] = str(exc)

        # Phase 3A latency aggregation. Filter out failed requests
        # (first_token_time == 0) so failures don't inflate the p50
        # with bogus near-zero latencies.
        ttft_ms_list: List[float] = []
        e2e_ms_list: List[float] = []
        per_request_cohort: List[int] = []
        for r in self._request_latencies:
            if r.first_token_time > 0:
                ttft_ms_list.append(
                    (r.first_token_time - r.submit_time) * 1000.0
                )
                e2e_ms_list.append(
                    (r.completion_time - r.submit_time) * 1000.0
                )
                per_request_cohort.append(r.cohort_index)
        ttft_p50_ms, ttft_p99_ms = self._compute_p50_p99_ms(ttft_ms_list)
        e2e_p50_ms, e2e_p99_ms = self._compute_p50_p99_ms(e2e_ms_list)

        ctm_evictor_stats: Dict[str, Any] = {}
        if self._installed_evictor is not None:
            try:
                # Phase 8b bridge counters — the two assertions Day 5b
                # needs to prove non-zero attention reaches the evictor.
                # These attrs are set by CTMEvictorModern.__init__ and
                # incremented inside forward_block_attention.
                ctm_evictor_stats["forward_block_attention_calls"] = int(
                    getattr(
                        self._installed_evictor,
                        "_forward_block_attention_calls", 0,
                    )
                )
                ctm_evictor_stats[
                    "forward_block_attention_nonzero_sum_calls"
                ] = int(
                    getattr(
                        self._installed_evictor,
                        "_forward_block_attention_nonzero_sum_calls", 0,
                    )
                )
                # The evictor's own get_stats() (proxies policy.stats)
                # — useful for the eviction/filler counts.
                policy_stats_fn = getattr(
                    self._installed_evictor, "get_stats", None,
                )
                if callable(policy_stats_fn):
                    ps = policy_stats_fn()
                    if isinstance(ps, dict):
                        ctm_evictor_stats["policy"] = dict(ps)
            except Exception:
                pass

        return StreamingRunCellResult(
            workload_name=workload_name,
            policy_name=("ctm_plus" if self.ctm_plus_evictor else "lru"),
            seed=self.seed,
            n_requests_admitted=n_admitted,
            n_requests_completed=n_completed,
            n_decode_tokens=n_decode_tokens,
            wall_clock_seconds=wall,
            swap_in_blocks=int(totals["swap_in_blocks"]),
            swap_out_blocks=int(totals["swap_out_blocks"]),
            preemption_events=int(totals["preemption_events"]),
            tokens_per_second=tokens_per_second,
            evict_call_count=evict_call_count,
            evict_total_seconds=evict_total_seconds,
            evict_p50_microseconds=evict_p50_us,
            evict_p99_microseconds=evict_p99_us,
            attention_capture_call_count=attention_capture_call_count,
            attention_capture_total_seconds=attention_capture_total_seconds,
            phase4_window_pruning_invocations=phase4_window_invocations,
            phase4_blocks_captured_with_pre_rope_keys=phase4_blocks_with_keys,
            phase4_side_channel_pre_hook_calls=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_side_channel_pre_hook_calls", 0,
                )
            ),
            phase4_side_channel_metadata_found=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_side_channel_metadata_found", 0,
                )
            ),
            phase4_side_channel_metadata_missing=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_side_channel_metadata_missing", 0,
                )
            ),
            phase4_rotary_pre_hook_calls=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_rotary_pre_hook_calls", 0,
                )
            ),
            phase4_capture_attempts=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_capture_attempts", 0,
                )
            ),
            phase4_capture_aborts_no_slot_mapping=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_capture_aborts_no_slot_mapping", 0,
                )
            ),
            phase4_capture_aborts_no_decode_tokens=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_capture_aborts_no_decode_tokens", 0,
                )
            ),
            phase4_capture_exceptions=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_capture_exceptions", 0,
                )
            ),
            phase4_set_pre_rope_keys_calls=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_set_pre_rope_keys_calls", 0,
                )
            ),
            phase4_set_pre_rope_keys_speculative=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_set_pre_rope_keys_speculative", 0,
                )
            ),
            phase4_trig_blend_evict_calls=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_trig_blend_evict_calls", 0,
                )
            ),
            phase4_trig_changed_pick=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_trig_changed_pick", 0,
                )
            ),
            phase4_trig_blend_skips=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_trig_blend_skips", 0,
                )
            ),
            phase4_capture_subsample_skips=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_capture_subsample_skips", 0,
                )
            ),
            phase4_trig_score_computes=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_trig_score_computes", 0,
                )
            ),
            phase4_trig_score_lookups=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_trig_score_lookups", 0,
                )
            ),
            phase4_trig_score_cache_misses=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_trig_score_cache_misses", 0,
                )
            ),
            phase4_trig_score_compute_exceptions=int(
                getattr(
                    self._installed_evictor or _DummyZero(),
                    "_phase4_trig_score_compute_exceptions", 0,
                )
            ),
            int4_route_a_stats=int4_route_a_stats,
            attention_aggregator_stats=attention_aggregator_stats,
            ctm_evictor_stats=ctm_evictor_stats,
            cache_aware_scheduler_stats=cache_aware_scheduler_stats,
            per_request_first_token_latency_ms=ttft_ms_list,
            per_request_e2e_latency_ms=e2e_ms_list,
            ttft_p50_ms=ttft_p50_ms,
            ttft_p99_ms=ttft_p99_ms,
            e2e_p50_ms=e2e_p50_ms,
            e2e_p99_ms=e2e_p99_ms,
            prompt_builder_name=self._prompt_builder.name,
            per_request_cohort=per_request_cohort,
            native_prefix_hit_stats=native_prefix_hit_stats,
            extended_pinning_stats=extended_pinning_stats,
            # Phase TIER5A — swap-restore telemetry surface.
            cpu_swap_pool_used_blocks_peak=cpu_swap_pool_used_blocks_peak_val,
            cpu_swap_pool_used_blocks_final=cpu_swap_pool_used_blocks_final_val,
            cpu_swap_pool_total_blocks=cpu_swap_pool_total_blocks_val,
            swap_in_latency_p50_ms=swap_in_latency_p50_ms_val,
            swap_in_latency_p99_ms=swap_in_latency_p99_ms_val,
            swap_in_latency_call_count=swap_in_latency_call_count_val,
            swap_telemetry_stats=swap_telemetry_stats_dict,
            # Phase TIER5A.3 — verifier output for the G1 verdict.
            verifier_output_token_ids=tuple(self._verifier_output_token_ids),
            verifier_request_completed=self._verifier_request_completed,
        )

    def _build_pin_specs(self) -> List[Any]:
        """Phase 4B: convert CLI/driver pin args into a list of
        ``PinSpec`` objects.

        Two input sources are supported (union semantics):
          * ``self.pin_first_n_blocks`` (int): if > 0, produces a
            single positional PinSpec.
          * ``self.pin_tokens_file`` (Path): if set, reads a JSON
            file containing one or more pin specs. Each entry is a
            dict with ``name`` plus exactly one of ``token_ids`` /
            ``first_n_blocks_per_request``.

        Returns ``[]`` when neither source is configured — the
        install proceeds with no PinSpecs (allocate-wrap still runs
        but pins nothing; the evictor wrap is a structural no-op).
        """
        from kv_policy.extended_pinning import PinSpec  # type: ignore
        specs: List[Any] = []
        if self.pin_first_n_blocks > 0:
            specs.append(PinSpec(
                name="positional_first_n",
                first_n_blocks_per_request=self.pin_first_n_blocks,
            ))
        if self.pin_tokens_file is not None:
            import json as _json
            raw = self.pin_tokens_file.read_text()
            data = _json.loads(raw)
            # Accept either a single object or a list of objects.
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                name = str(entry.get("name", "unnamed"))
                token_ids = entry.get("token_ids")
                first_n = entry.get("first_n_blocks_per_request")
                if token_ids is not None:
                    specs.append(PinSpec(
                        name=name, token_ids=tuple(token_ids),
                    ))
                elif first_n is not None:
                    specs.append(PinSpec(
                        name=name, first_n_blocks_per_request=int(first_n),
                    ))
                else:
                    raise ValueError(
                        f"pin spec {name!r} in {self.pin_tokens_file}: "
                        "must set token_ids or first_n_blocks_per_request"
                    )
        return specs

    @staticmethod
    def _compute_p50_p99_ms(
        timings_ms: List[float],
    ) -> Tuple[float, float]:
        """Phase 3A: compute (p50, p99) of a list of milliseconds,
        return as milliseconds (no unit conversion). Type-7 linear
        interpolation between sorted samples; returns (0.0, 0.0)
        for an empty list."""
        if not timings_ms:
            return (0.0, 0.0)
        sorted_ms = sorted(timings_ms)
        n = len(sorted_ms)

        def _percentile(p: float) -> float:
            if n == 1:
                return sorted_ms[0]
            rank = p * (n - 1)
            lo = int(rank)
            hi = min(lo + 1, n - 1)
            frac = rank - lo
            return sorted_ms[lo] * (1 - frac) + sorted_ms[hi] * frac

        return (_percentile(0.50), _percentile(0.99))

    @staticmethod
    def _compute_p50_p99_microseconds(
        timings_seconds: List[float],
    ) -> Tuple[float, float]:
        """Compute (p50, p99) of a list of seconds, return as
        microseconds. Uses linear interpolation between sorted
        samples (no numpy dependency).

        Returns (0.0, 0.0) for an empty list.
        """
        if not timings_seconds:
            return (0.0, 0.0)
        sorted_us = sorted(t * 1e6 for t in timings_seconds)
        n = len(sorted_us)

        def _percentile(p: float) -> float:
            if n == 1:
                return sorted_us[0]
            # Linear interpolation, type-7 (R/numpy default).
            rank = p * (n - 1)
            lo = int(rank)
            hi = min(lo + 1, n - 1)
            frac = rank - lo
            return sorted_us[lo] * (1 - frac) + sorted_us[hi] * frac

        return (_percentile(0.50), _percentile(0.99))


# ---------------------------------------------------------------- #
# Phase 2 — CTM+ evictor patch on modern vLLM (re-export from
# kv_policy.vllm_evictor where the implementation lives).
# ---------------------------------------------------------------- #


def patch_vllm_engine_modern(
    engine, *,
    enable_logging: bool = False,
    trig_scorer: Any = None,
    window_pruning_interval: int = 128,
    trig_blend_candidate_count: int = 4,
    use_cython_evictor: bool = False,
):
    """Patch a modern vLLM (0.5+) engine to use CTM+ for KV-cache
    eviction.

    Re-exported from :mod:`kv_policy.vllm_evictor` where the real
    implementation lives. ``trig_scorer`` and
    ``window_pruning_interval`` are forwarded for Phase 4 setup;
    leave them at defaults for Phase 2 / 3.

    See :func:`kv_policy.vllm_evictor.patch_vllm_engine_modern`
    for the full docstring and contract. Raises
    ``NotImplementedError`` if prefix caching is off (no evictor
    to swap) and ``RuntimeError`` if the allocator path can't be
    walked.
    """
    # Lazy import — kv_policy is in a sibling package; importing
    # at module top would require it on sys.path even when this
    # module is just being loaded for its pure-Python helpers.
    try:
        from kv_policy.vllm_evictor import (  # type: ignore
            patch_vllm_engine_modern as _real_patch,
        )
    except ImportError:
        # Try the path-injected import that the existing
        # runner_vllm.py uses.
        from ctm_bench.policies import _add_kv_policy_to_path
        _add_kv_policy_to_path()
        from kv_policy.vllm_evictor import (  # type: ignore
            patch_vllm_engine_modern as _real_patch,
        )
    return _real_patch(
        engine,
        enable_logging=enable_logging,
        trig_scorer=trig_scorer,
        window_pruning_interval=window_pruning_interval,
        trig_blend_candidate_count=trig_blend_candidate_count,
        use_cython_evictor=use_cython_evictor,
    )
