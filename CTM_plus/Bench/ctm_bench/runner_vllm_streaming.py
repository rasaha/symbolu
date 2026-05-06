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
        max_decode_tokens: int = 128,
        sample_interval_seconds: Optional[float] = None,
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
        self.max_decode_tokens = max_decode_tokens
        self.sample_interval_seconds = (
            sample_interval_seconds
            if sample_interval_seconds is not None
            else self.DEFAULT_SAMPLE_INTERVAL_SECONDS
        )
        self._vllm_module = vllm_module

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
        without spinning up vLLM."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "gpu_memory_utilization": self.gpu_memory_utilization,
            "swap_space": self.swap_space_gb,
            "enforce_eager": True,
            "seed": self.seed,
            # Phase 1 wants the swap path, not the cache-retention
            # path. Prefix caching off keeps eviction in the swap
            # decision tree.
            "enable_prefix_caching": False,
            # The critical bit. preemption_mode="swap" tells vLLM's
            # scheduler to swap preempted sequences to CPU rather
            # than recomputing them. Without this, swap counters
            # stay zero even with AsyncLLMEngine + heavy load.
            "preemption_mode": "swap",
        }
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
    ) -> int:
        """Submit one request to the async engine and consume its
        outputs. Returns the number of decode tokens generated.

        Robust to both the old async-iterator API
        (``async for output in engine.generate(...)``) and the
        newer ``await engine.add_request(...)`` + step-based loop.
        We use the iterator API since it's stable across 0.5 → 0.7.
        """
        n_tokens = 0
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
                    n_tokens = len(output.outputs[0].token_ids)
        except Exception as exc:
            # Don't let one failed request kill the whole sweep.
            logger.warning(
                "request %s failed: %s", request_id, exc,
            )
        return n_tokens

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
        """
        if self.ctm_plus_evictor:
            raise NotImplementedError(
                "ctm_plus_evictor=True is roadmap #3 Phase 2 and "
                "not yet implemented. Use ctm_plus_evictor=False "
                "for Phase 1 (LRU swap-counter validation). See "
                "Bench/scripts/MODE_B_STREAMING_DESIGN.md §4.4."
            )

        vllm = self._import_vllm()
        engine_args = self._build_engine_args(vllm)
        AsyncLLMEngine = vllm.AsyncLLMEngine
        SamplingParams = vllm.SamplingParams

        engine = AsyncLLMEngine.from_engine_args(engine_args)
        sampling_params = SamplingParams(
            temperature=0.0,
            max_tokens=self.max_decode_tokens,
            seed=self.seed,
        )

        sampler_task = asyncio.create_task(
            self._run_sampler(engine, sampler)
        )

        n_admitted = 0
        n_completed = 0
        n_decode_tokens = 0
        submission_tasks: List[asyncio.Task] = []
        request_id_counter = 0
        start = time.perf_counter()

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
                # Synthetic prompt — token id 100 is "noise" but
                # decodes to a valid string for any tokenizer. The
                # bench question is about KV-cache pressure, not
                # output quality; content doesn't matter.
                prompt_token_ids = [100] * length
                request_id = f"streaming_{workload_name}_{request_id_counter}"
                request_id_counter += 1

                task = asyncio.create_task(
                    self._submit_one(
                        engine, request_id, prompt_token_ids,
                        sampling_params,
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
        )


# ---------------------------------------------------------------- #
# CTMAwarePrefixCachingAllocator — Phase 2 stub. Unimplemented.
# ---------------------------------------------------------------- #


def patch_vllm_engine_modern(engine, *, enable_logging: bool = False):
    """Patch a modern vLLM (0.5+) engine to use CTM+ for KV-cache
    eviction.

    **NOT IMPLEMENTED.** This is roadmap #3 Phase 2. Calling it
    raises :class:`NotImplementedError`. The Phase-2 plan is to
    subclass the GPU allocator's evictor (not the whole
    ``CpuGpuBlockAllocator``) and inject a CTM+-aware
    implementation that scores blocks by position + recency +
    frequency (option (b) in the design doc); attention
    forwarding (option (a)) is a follow-up.

    The existing ``kv_policy.vllm_evictor.patch_vllm_engine``
    handles vLLM ≤ 0.4.x. Together they cover the full vLLM
    version range, with the modern path explicitly behind a
    NotImplementedError until Phase 2 is authorised.
    """
    raise NotImplementedError(
        "patch_vllm_engine_modern is roadmap #3 Phase 2 and is not "
        "implemented yet. Use kv_policy.vllm_evictor.patch_vllm_engine "
        "with vLLM 0.4.x (roadmap #2) until this lands. See "
        "Bench/scripts/MODE_B_STREAMING_DESIGN.md §4.4 for the "
        "subclass-evictor plan."
    )
