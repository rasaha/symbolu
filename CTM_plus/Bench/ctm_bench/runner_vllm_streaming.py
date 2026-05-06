"""Streaming Mode B runner — scaffolding for roadmap #3.

**Status: scaffolding only.** Full implementation is gated on
partner request or explicit multi-day authorization. This
module ships pure-Python helpers (`ArrivalScheduler`,
`SwapCounterSampler` state machine, `RunCellResult` dataclass)
that can be unit-tested without vLLM, plus stub classes that
raise ``NotImplementedError`` for the GPU path with a clear
message pointing at the design doc.

See ``Bench/scripts/MODE_B_STREAMING_DESIGN.md`` for the full
architectural plan.

Solves two problems from the May 2026 GPU run:

* **Problem A** — CTM+ cannot install into vLLM 0.5+ (the
  ``CpuGpuBlockAllocator`` has no public eviction-policy hook).
* **Problem B** — batch-mode FCFS execution does not trigger
  swap/preemption, so swap counters always read zero.

Phase 1 (this module's first GPU implementation) addresses B
alone — LRU through ``AsyncLLMEngine`` with ``preemption_mode=
"swap"`` and a Pareto-shape arrival schedule, with periodic
swap-counter sampling. Phase 2 adds A — a CTM+-aware allocator
patch.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


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
# AsyncEngineDriver — STUB. GPU path. Unimplemented.
# ---------------------------------------------------------------- #


class AsyncEngineDriver:
    """Drives an ``AsyncLLMEngine`` with a streaming arrival
    schedule.

    **NOT IMPLEMENTED.** This is the GPU-touching component that
    requires the full multi-day rewrite. The class signature is
    fixed so contract tests can verify the intended API; calling
    :meth:`run` raises :class:`NotImplementedError` with a
    pointer to the design doc.
    """

    def __init__(
        self,
        *,
        model: str,
        gpu_memory_utilization: float = 0.30,
        swap_space_gb: int = 8,
        seed: int = 42,
        scheduler_config_overrides: Optional[Dict[str, object]] = None,
        ctm_plus_evictor: bool = False,
    ) -> None:
        self.model = model
        self.gpu_memory_utilization = gpu_memory_utilization
        self.swap_space_gb = swap_space_gb
        self.seed = seed
        self.scheduler_config_overrides = (
            dict(scheduler_config_overrides) if scheduler_config_overrides else {}
        )
        self.ctm_plus_evictor = ctm_plus_evictor

    async def run(
        self,
        *,
        scheduler: ArrivalScheduler,
        sampler: SwapCounterSampler,
        max_requests: int,
        max_wall_seconds: float,
        workload_name: str,
    ) -> StreamingRunCellResult:
        raise NotImplementedError(
            "AsyncEngineDriver.run is the GPU path of the streaming "
            "runner and is not implemented in this scaffolding "
            "commit. The full implementation is roadmap #3 Phase 1 "
            "(2-3 days). See "
            "Bench/scripts/MODE_B_STREAMING_DESIGN.md for the "
            "architectural plan and Bench/scripts/MODE_B_RUNBOOK.md "
            "§9.6 for context. The pure-Python pieces of the "
            "runner (ArrivalScheduler, SwapCounterSampler) are "
            "implemented and unit-tested; the vLLM integration is "
            "what's gated."
        )


# ---------------------------------------------------------------- #
# CTMAwarePrefixCachingAllocator — STUB. GPU path. Unimplemented.
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
