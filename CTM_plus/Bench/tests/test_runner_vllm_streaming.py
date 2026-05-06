"""Contract tests for the streaming Mode B runner scaffolding.

These tests pin the API contract of the pure-Python pieces of
the streaming runner (``ArrivalScheduler``, ``SwapCounterSampler``,
``StreamingRunCellResult``) so that when the GPU implementation
lands the tests still pass. The GPU-path stubs
(``AsyncEngineDriver.run``, ``patch_vllm_engine_modern``) are
verified to raise ``NotImplementedError`` with a message
pointing at the design doc — that's the contract until they're
implemented.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest


# ------------------------------------------------------------------ #
# StreamingRunCellResult
# ------------------------------------------------------------------ #


def test_run_cell_result_is_frozen():
    """The result type must be immutable so cells can be safely
    aggregated / passed across tasks."""
    from ctm_bench.runner_vllm_streaming import StreamingRunCellResult

    r = StreamingRunCellResult(
        workload_name="chat_32k", policy_name="lru", seed=42,
        n_requests_admitted=10, n_requests_completed=8,
        n_decode_tokens=4096, wall_clock_seconds=12.5,
        swap_in_blocks=128, swap_out_blocks=128,
        preemption_events=4,
    )
    with pytest.raises(Exception):
        r.swap_in_blocks = 0  # type: ignore[misc]


def test_run_cell_result_default_counter_source():
    """The counter_source default must mark cells as coming from
    the streaming runner so cross-check tooling can distinguish
    them from the legacy batch runner's vllm_0_7_no_swaps_observed
    cells."""
    from ctm_bench.runner_vllm_streaming import StreamingRunCellResult

    r = StreamingRunCellResult(
        workload_name="chat_32k", policy_name="lru", seed=42,
        n_requests_admitted=1, n_requests_completed=1,
        n_decode_tokens=10, wall_clock_seconds=1.0,
        swap_in_blocks=0, swap_out_blocks=0, preemption_events=0,
    )
    assert r.counter_source == "vllm_streaming_async_swap"


# ------------------------------------------------------------------ #
# ArrivalScheduler — Pareto mode
# ------------------------------------------------------------------ #


def test_arrival_scheduler_pareto_deterministic_per_seed():
    """Same seed + same Pareto config must produce the same
    sequence of inter-arrival delays."""
    from ctm_bench.runner_vllm_streaming import (
        ArrivalScheduler, ParetoArrivalConfig,
    )

    cfg = ParetoArrivalConfig(base_rate_per_sec=2.0, alpha=1.5)
    a = ArrivalScheduler(seed=42, pareto=cfg)
    b = ArrivalScheduler(seed=42, pareto=cfg)
    seq_a = [a.next_arrival_delay_seconds() for _ in range(50)]
    seq_b = [b.next_arrival_delay_seconds() for _ in range(50)]
    assert seq_a == seq_b


def test_arrival_scheduler_pareto_different_seeds_diverge():
    from ctm_bench.runner_vllm_streaming import (
        ArrivalScheduler, ParetoArrivalConfig,
    )

    cfg = ParetoArrivalConfig(base_rate_per_sec=2.0, alpha=1.5)
    a = ArrivalScheduler(seed=42, pareto=cfg)
    b = ArrivalScheduler(seed=137, pareto=cfg)
    seq_a = [a.next_arrival_delay_seconds() for _ in range(50)]
    seq_b = [b.next_arrival_delay_seconds() for _ in range(50)]
    assert seq_a != seq_b


def test_arrival_scheduler_pareto_long_run_rate_is_close_to_target():
    """Over many draws, the realised rate should be close to
    base_rate_per_sec for alpha > 1 (where the mean exists)."""
    from ctm_bench.runner_vllm_streaming import (
        ArrivalScheduler, ParetoArrivalConfig,
    )

    cfg = ParetoArrivalConfig(base_rate_per_sec=2.0, alpha=2.5)
    sched = ArrivalScheduler(seed=42, pareto=cfg)
    N = 5000
    delays = [sched.next_arrival_delay_seconds() for _ in range(N)]
    assert all(d is not None for d in delays)
    total_time = sum(d for d in delays if d is not None)
    realised_rate = N / total_time
    # Allow generous tolerance — Pareto convergence is slow.
    assert 1.5 < realised_rate < 2.5, (
        f"realised rate {realised_rate:.2f} far from target 2.0"
    )


def test_arrival_scheduler_pareto_burstier_than_uniform():
    """At low alpha, the maximum gap must exceed what a uniform
    Bernoulli at the same rate would produce. This is the
    definition of burstiness."""
    from ctm_bench.runner_vllm_streaming import (
        ArrivalScheduler, ParetoArrivalConfig,
    )
    import random

    cfg_burst = ParetoArrivalConfig(base_rate_per_sec=1.0, alpha=1.2)
    burst = ArrivalScheduler(seed=42, pareto=cfg_burst)
    burst_delays = [
        burst.next_arrival_delay_seconds() for _ in range(2000)
    ]
    burst_max = max(d for d in burst_delays if d is not None)

    # Uniform exponential with rate 1.0/sec for comparison.
    rng = random.Random(42)
    uniform_delays = [rng.expovariate(1.0) for _ in range(2000)]
    uniform_max = max(uniform_delays)

    assert burst_max > uniform_max, (
        f"Pareto α=1.2 max gap {burst_max:.2f} not greater than "
        f"exponential max gap {uniform_max:.2f}"
    )


def test_arrival_scheduler_rejects_bad_alpha():
    from ctm_bench.runner_vllm_streaming import (
        ArrivalScheduler, ParetoArrivalConfig,
    )

    with pytest.raises(ValueError):
        ArrivalScheduler(
            seed=42,
            pareto=ParetoArrivalConfig(base_rate_per_sec=1.0, alpha=0.0),
        )
    with pytest.raises(ValueError):
        ArrivalScheduler(
            seed=42,
            pareto=ParetoArrivalConfig(
                base_rate_per_sec=1.0, alpha=-1.0
            ),
        )


def test_arrival_scheduler_requires_one_mode():
    """Cannot pass both pareto and replay_csv (or neither)."""
    from ctm_bench.runner_vllm_streaming import (
        ArrivalScheduler, ParetoArrivalConfig,
    )

    with pytest.raises(ValueError):
        ArrivalScheduler(seed=42)
    with pytest.raises(ValueError):
        ArrivalScheduler(
            seed=42,
            pareto=ParetoArrivalConfig(base_rate_per_sec=1.0, alpha=2.0),
            replay_csv=Path("/tmp/whatever.csv"),
        )


# ------------------------------------------------------------------ #
# ArrivalScheduler — Replay mode
# ------------------------------------------------------------------ #


def _write_replay_csv(tmp_path: Path, rows) -> Path:
    p = tmp_path / "replay.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_seconds", "prompt_length"])
        for ts, length in rows:
            w.writerow([ts, length])
    return p


def test_arrival_scheduler_replay_loads_csv(tmp_path):
    """Replay mode parses the CSV and yields delays equal to the
    diff between consecutive timestamps."""
    from ctm_bench.runner_vllm_streaming import ArrivalScheduler

    csv_path = _write_replay_csv(tmp_path, [
        (0.0, 256), (0.5, 512), (1.7, 1024), (1.7, 256),
    ])
    sched = ArrivalScheduler(seed=42, replay_csv=csv_path)
    # First arrival: delay relative to t=0.
    assert sched.next_arrival_delay_seconds() == pytest.approx(0.0)
    assert sched.next_prompt_length() == 256
    # Second arrival: 0.5s after first.
    assert sched.next_arrival_delay_seconds() == pytest.approx(0.5)
    assert sched.next_prompt_length() == 512
    # Third: 1.2s after second.
    assert sched.next_arrival_delay_seconds() == pytest.approx(1.2)
    assert sched.next_prompt_length() == 1024
    # Fourth: 0.0s gap (simultaneous arrival).
    assert sched.next_arrival_delay_seconds() == pytest.approx(0.0)
    assert sched.next_prompt_length() == 256
    # Schedule exhausted — delay returns None.
    assert sched.next_arrival_delay_seconds() is None


def test_arrival_scheduler_replay_skips_header_and_garbage(tmp_path):
    """Lines that aren't (float, int) tuples are skipped — the
    header line in particular must not blow up the parser."""
    from ctm_bench.runner_vllm_streaming import ArrivalScheduler

    csv_path = tmp_path / "replay.csv"
    csv_path.write_text(
        "timestamp_seconds,prompt_length\n"
        "0.0,256\n"
        "garbage line\n"
        "0.5,512\n"
        "1.0\n"  # too few fields
        "1.5,1024\n"
    )
    sched = ArrivalScheduler(seed=42, replay_csv=csv_path)
    # Three valid rows.
    assert sched.next_arrival_delay_seconds() == pytest.approx(0.0)
    assert sched.next_prompt_length() == 256
    assert sched.next_arrival_delay_seconds() == pytest.approx(0.5)
    assert sched.next_prompt_length() == 512
    assert sched.next_arrival_delay_seconds() == pytest.approx(1.0)
    assert sched.next_prompt_length() == 1024
    assert sched.next_arrival_delay_seconds() is None


def test_arrival_scheduler_replay_sorts_by_timestamp(tmp_path):
    """Out-of-order rows must be sorted into chronological order
    so the playback is consistent regardless of CSV ordering."""
    from ctm_bench.runner_vllm_streaming import ArrivalScheduler

    csv_path = _write_replay_csv(tmp_path, [
        (1.0, 100), (0.0, 200), (0.5, 300),
    ])
    sched = ArrivalScheduler(seed=42, replay_csv=csv_path)
    # Sorted: (0.0, 200), (0.5, 300), (1.0, 100)
    assert sched.next_arrival_delay_seconds() == pytest.approx(0.0)
    assert sched.next_prompt_length() == 200
    assert sched.next_arrival_delay_seconds() == pytest.approx(0.5)
    assert sched.next_prompt_length() == 300
    assert sched.next_arrival_delay_seconds() == pytest.approx(0.5)
    assert sched.next_prompt_length() == 100


# ------------------------------------------------------------------ #
# SwapCounterSampler
# ------------------------------------------------------------------ #


def test_swap_counter_sampler_starts_at_zero():
    from ctm_bench.runner_vllm_streaming import SwapCounterSampler

    s = SwapCounterSampler()
    assert s.totals() == {
        "swap_in_blocks": 0,
        "swap_out_blocks": 0,
        "preemption_events": 0,
    }
    assert s.n_samples == 0


def test_swap_counter_sampler_accumulates():
    from ctm_bench.runner_vllm_streaming import SwapCounterSampler

    s = SwapCounterSampler()
    s.record_sample(swap_in_blocks=10, swap_out_blocks=10, preemption_events=1)
    s.record_sample(swap_in_blocks=4, swap_out_blocks=6, preemption_events=2)
    assert s.totals() == {
        "swap_in_blocks": 14,
        "swap_out_blocks": 16,
        "preemption_events": 3,
    }
    assert s.n_samples == 2


def test_swap_counter_sampler_rejects_negative():
    """A negative delta means the engine restarted mid-cell;
    reject loud rather than silently corrupting the totals."""
    from ctm_bench.runner_vllm_streaming import SwapCounterSampler

    s = SwapCounterSampler()
    with pytest.raises(ValueError):
        s.record_sample(swap_in_blocks=-1)
    with pytest.raises(ValueError):
        s.record_sample(swap_out_blocks=-5)
    with pytest.raises(ValueError):
        s.record_sample(preemption_events=-1)


def test_swap_counter_sampler_rejects_record_after_stop():
    from ctm_bench.runner_vllm_streaming import SwapCounterSampler

    s = SwapCounterSampler()
    s.record_sample(swap_in_blocks=1, swap_out_blocks=1)
    s.stop()
    with pytest.raises(RuntimeError):
        s.record_sample(swap_in_blocks=1)


def test_swap_counter_sampler_totals_are_a_copy():
    """totals() must return a copy so callers cannot mutate the
    sampler's internal state by surprise."""
    from ctm_bench.runner_vllm_streaming import SwapCounterSampler

    s = SwapCounterSampler()
    s.record_sample(swap_in_blocks=5)
    snap = s.totals()
    snap["swap_in_blocks"] = 999
    assert s.totals()["swap_in_blocks"] == 5


# ------------------------------------------------------------------ #
# GPU-path stubs raise NotImplementedError pointing at the design doc.
# ------------------------------------------------------------------ #


def test_async_engine_driver_construct_then_run_raises_not_implemented():
    """The driver constructor accepts the configured args and
    stores them, but run() raises NotImplementedError with a
    pointer to MODE_B_STREAMING_DESIGN.md."""
    import asyncio
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver, ArrivalScheduler, ParetoArrivalConfig,
        SwapCounterSampler,
    )

    driver = AsyncEngineDriver(
        model="meta-llama/Llama-2-7b-chat-hf",
        gpu_memory_utilization=0.30,
        swap_space_gb=8,
        seed=42,
        scheduler_config_overrides={"preemption_mode": "swap"},
        ctm_plus_evictor=False,
    )
    # Constructor stores config faithfully.
    assert driver.model == "meta-llama/Llama-2-7b-chat-hf"
    assert driver.gpu_memory_utilization == 0.30
    assert driver.swap_space_gb == 8
    assert driver.seed == 42
    assert driver.scheduler_config_overrides["preemption_mode"] == "swap"
    assert driver.ctm_plus_evictor is False

    # run() raises with a clear message.
    sched = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=1.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()
    with pytest.raises(NotImplementedError) as exc:
        asyncio.get_event_loop().run_until_complete(
            driver.run(
                scheduler=sched, sampler=sampler,
                max_requests=10, max_wall_seconds=5.0,
                workload_name="chat_32k",
            )
        )
    msg = str(exc.value)
    assert "MODE_B_STREAMING_DESIGN.md" in msg
    assert "roadmap #3" in msg


def test_patch_vllm_engine_modern_raises_not_implemented():
    """The Phase-2 allocator patch is also stubbed; calling it
    must raise NotImplementedError pointing at the design doc."""
    from ctm_bench.runner_vllm_streaming import (
        patch_vllm_engine_modern,
    )

    fake_engine = object()
    with pytest.raises(NotImplementedError) as exc:
        patch_vllm_engine_modern(fake_engine)
    msg = str(exc.value)
    assert "MODE_B_STREAMING_DESIGN.md" in msg
    assert "Phase 2" in msg
    # Tells the reader to use the vLLM 0.4 path until this lands.
    assert "0.4" in msg
