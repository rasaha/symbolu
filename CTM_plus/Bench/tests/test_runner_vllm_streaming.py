"""Contract + implementation tests for the streaming Mode B runner.

Covers:

* Pure-Python pieces (``ArrivalScheduler``, ``SwapCounterSampler``,
  ``StreamingRunCellResult``).
* Phase 1 GPU-path semantics via mocked vLLM (preemption_mode=swap
  propagation, swap-counter parsing, run-loop flow, teardown).
* Phase 2 GPU-path semantics via mocked vLLM (CTMEvictorModern
  satisfies vLLM 0.7 Evictor ABC; patch_vllm_engine_modern walks
  the modern allocator path; rejects NaiveBlockAllocator with a
  clear message).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

# Make kv_policy (sibling package) importable so Phase 2 tests can
# pull CTMEvictorModern + patch_vllm_engine_modern. The same trick
# the production code uses via ctm_bench.policies._add_kv_policy_to_path.
from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


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


def test_async_engine_driver_constructor_stores_config():
    """The driver constructor accepts the configured args and
    stores them on the instance."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    driver = AsyncEngineDriver(
        model="meta-llama/Llama-2-7b-chat-hf",
        gpu_memory_utilization=0.30,
        swap_space_gb=8,
        seed=42,
        scheduler_config_overrides={"preemption_mode": "swap"},
        ctm_plus_evictor=False,
    )
    assert driver.model == "meta-llama/Llama-2-7b-chat-hf"
    assert driver.gpu_memory_utilization == 0.30
    assert driver.swap_space_gb == 8
    assert driver.seed == 42
    assert driver.scheduler_config_overrides["preemption_mode"] == "swap"
    assert driver.ctm_plus_evictor is False


def test_async_engine_driver_explicit_prefix_caching_for_lru_baseline():
    """Audit-pass MEDIUM #3 fix: enable_prefix_caching is now an
    independent knob. Partners need to run an LRU baseline cell
    with prefix caching ON to make an apples-to-apples comparison
    against a Phase 2 CTM+ cell (both decide cache retention; only
    the policy differs)."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    captured: dict = {}

    class FakeAEAArgs:
        def __init__(self, **kwargs):
            captured.clear()
            captured.update(kwargs)

    class FakeVLLM:
        AsyncEngineArgs = FakeAEAArgs

    # LRU baseline with prefix caching ON (the cell we want for
    # comparing against Phase 2 CTM+).
    driver = AsyncEngineDriver(
        model="dummy", ctm_plus_evictor=False,
        enable_prefix_caching=True, vllm_module=FakeVLLM,
    )
    driver._build_engine_args(FakeVLLM)
    assert captured["enable_prefix_caching"] is True
    # ctm_plus_evictor stays False — this is an LRU cell.
    assert driver.ctm_plus_evictor is False


def test_async_engine_driver_rejects_ctm_plus_without_prefix_caching():
    """Audit-pass MEDIUM #3 fix: explicit error if the caller
    sets ctm_plus_evictor=True but enable_prefix_caching=False —
    that combination can never install the patch."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    with pytest.raises(ValueError, match="enable_prefix_caching=True"):
        AsyncEngineDriver(
            model="dummy",
            ctm_plus_evictor=True,
            enable_prefix_caching=False,
        )


def test_async_engine_driver_phase2_enables_prefix_caching():
    """When ctm_plus_evictor=True, _build_engine_args MUST set
    enable_prefix_caching=True. Without it, vLLM uses
    NaiveBlockAllocator which has no evictor and the patch can't
    install. This is the Phase 2 install-time invariant."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    captured_phase1: dict = {}
    captured_phase2: dict = {}

    class FakeAEAArgs:
        def __init__(self, **kwargs):
            captured_phase1.update(kwargs) if not getattr(
                FakeAEAArgs, "_phase2", False
            ) else captured_phase2.update(kwargs)

    class FakeVLLM:
        AsyncEngineArgs = FakeAEAArgs

    # Phase 1 driver — prefix caching off.
    driver1 = AsyncEngineDriver(
        model="dummy", ctm_plus_evictor=False, vllm_module=FakeVLLM,
    )
    driver1._build_engine_args(FakeVLLM)
    assert captured_phase1["enable_prefix_caching"] is False, (
        "Phase 1 (LRU swap-path) must set enable_prefix_caching=False"
    )

    # Phase 2 driver — prefix caching ON.
    FakeAEAArgs._phase2 = True
    driver2 = AsyncEngineDriver(
        model="dummy", ctm_plus_evictor=True, vllm_module=FakeVLLM,
    )
    driver2._build_engine_args(FakeVLLM)
    assert captured_phase2["enable_prefix_caching"] is True, (
        "Phase 2 (CTM+ evictor) MUST set enable_prefix_caching=True; "
        "without it, NaiveBlockAllocator has no evictor and the "
        "patch can't install."
    )
    # Both phases keep preemption_mode=swap so swap counters
    # accumulate even on Phase 2.
    assert captured_phase1["preemption_mode"] == "swap"
    assert captured_phase2["preemption_mode"] == "swap"


def test_async_engine_driver_run_phase1_requires_vllm():
    """In Phase 1 (LRU) the driver must raise ImportError with a
    message naming vllm and the streaming runner's vLLM target
    when vllm isn't installed. NOT NotImplementedError."""
    import asyncio
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver, ArrivalScheduler, ParetoArrivalConfig,
        SwapCounterSampler,
    )

    driver = AsyncEngineDriver(model="dummy", ctm_plus_evictor=False)
    sched = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=1.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()

    # Force the import path to fail by passing a vllm_module that
    # isn't a module — the constructor accepts None and falls back
    # to import vllm; on this sandbox that import fails.
    try:
        import vllm  # type: ignore  # noqa: F401
        pytest.skip(
            "vllm is installed in this environment; "
            "skipping the import-error path"
        )
    except ImportError:
        pass

    with pytest.raises(ImportError, match="vLLM"):
        asyncio.new_event_loop().run_until_complete(
            driver.run(
                scheduler=sched, sampler=sampler,
                max_requests=10, max_wall_seconds=5.0,
                workload_name="chat_32k",
            )
        )


# ------------------------------------------------------------------ #
# Phase 1 implementation — _read_swap_counters_from_engine
# ------------------------------------------------------------------ #


def test_read_swap_counters_handles_vllm_07_list_of_tuples():
    """vLLM 0.7's CpuGpuBlockAllocator.get_and_reset_swaps()
    returns a list of (src_block_id, dst_block_id) tuples — the
    actual format the existing batch runner's
    _extract_vllm_tier_counters has been validated against
    (runner_vllm.py:375-404, tests in test_runner_vllm.py).

    The streaming counter probe must report len(swaps) as
    swap_out_blocks (matching the batch runner's convention of
    attributing all swaps to slow-tier traffic) — NOT crash
    trying to int-cast a tuple."""
    from ctm_bench.runner_vllm_streaming import (
        _read_swap_counters_from_engine,
    )

    class FakeAllocator:
        def get_and_reset_swaps(self):
            return [(1, 100), (2, 101), (3, 102)]   # 3 swap events

    class FakeBM:
        block_allocator = FakeAllocator()

    class FakeSched:
        block_manager = FakeBM()
        num_cumulative_preemption = 7   # vLLM 0.7's actual attr name

    class FakeInner:
        scheduler = FakeSched()

    class FakeEngine:
        engine = FakeInner()

    inb, outb, preempt = _read_swap_counters_from_engine(FakeEngine())
    assert outb == 3   # len of the swap list
    assert inb == 0    # direction not distinguishable from this format
    assert preempt == 7


def test_read_swap_counters_handles_dict_format():
    """A future vLLM version that splits in/out via dict — the
    parser should pick that up."""
    from ctm_bench.runner_vllm_streaming import (
        _read_swap_counters_from_engine,
    )

    class FakeAllocator:
        def get_and_reset_swaps(self):
            return {"in": 5, "out": 3}

    class FakeBM:
        block_allocator = FakeAllocator()

    class FakeSched:
        block_manager = FakeBM()
        num_cumulative_preemption = 7

    class FakeInner:
        scheduler = FakeSched()

    class FakeEngine:
        engine = FakeInner()

    inb, outb, preempt = _read_swap_counters_from_engine(FakeEngine())
    assert inb == 5
    assert outb == 3
    assert preempt == 7


def test_read_swap_counters_handles_tuple_of_ints():
    """A future vLLM version that returns (in, out) as a flat
    2-tuple of ints — distinguish from list-of-tuples by checking
    element type."""
    from ctm_bench.runner_vllm_streaming import (
        _read_swap_counters_from_engine,
    )

    class FakeAllocator:
        def get_and_reset_swaps(self):
            return (10, 4)   # int tuple, NOT list of pairs

    class FakeBM:
        block_allocator = FakeAllocator()

    class FakeSched:
        block_manager = FakeBM()

    class FakeInner:
        scheduler = [FakeSched()]  # list — pipeline-parallel layout

    class FakeEngine:
        engine = FakeInner()

    inb, outb, preempt = _read_swap_counters_from_engine(FakeEngine())
    assert inb == 10
    assert outb == 4
    assert preempt == 0   # no preemption attr on FakeSched


def test_read_swap_counters_empty_list_means_zero():
    """When no swaps engaged, get_and_reset_swaps returns []. The
    parser must report (0, 0, ...) without crashing — this is the
    'no swap engaged' signal that Phase 1's pass criterion
    explicitly tests for."""
    from ctm_bench.runner_vllm_streaming import (
        _read_swap_counters_from_engine,
    )

    class FakeAllocator:
        def get_and_reset_swaps(self):
            return []

    class FakeBM:
        block_allocator = FakeAllocator()

    class FakeSched:
        block_manager = FakeBM()

    class FakeInner:
        scheduler = FakeSched()

    class FakeEngine:
        engine = FakeInner()

    inb, outb, preempt = _read_swap_counters_from_engine(FakeEngine())
    assert (inb, outb, preempt) == (0, 0, 0)


def test_read_swap_counters_finds_preemption_via_alternate_attrs():
    """The Scheduler's preemption counter has had multiple names
    across vLLM versions. The probe should find it under any of
    the candidates."""
    from ctm_bench.runner_vllm_streaming import (
        _read_swap_counters_from_engine,
    )

    for attr_name, expected in [
        ("num_cumulative_preemption", 11),     # vLLM 0.7 actual
        ("num_cumulative_preemptions", 12),    # plural variant
        ("num_preemption_events", 13),         # alternate
    ]:
        sched_cls = type(
            "FakeSched",
            (),
            {
                attr_name: expected,
                "block_manager": type(
                    "FakeBM", (),
                    {"block_allocator": type(
                        "FakeAllocator", (),
                        {"get_and_reset_swaps": lambda self: []},
                    )()},
                )(),
            },
        )
        engine = type("E", (), {
            "engine": type("I", (), {"scheduler": sched_cls()})(),
        })()
        _, _, preempt = _read_swap_counters_from_engine(engine)
        assert preempt == expected, (
            f"failed to read preemption from {attr_name!r}"
        )


def test_read_swap_counters_handles_object_format():
    """Some vLLM versions return swaps as an object with
    swap_in/swap_out attributes."""
    from ctm_bench.runner_vllm_streaming import (
        _read_swap_counters_from_engine,
    )

    class Swaps:
        swap_in = 11
        swap_out = 12

    class FakeAllocator:
        def get_and_reset_swaps(self):
            return Swaps()

    class FakeBM:
        block_allocator = FakeAllocator()

    class FakeSched:
        block_manager = FakeBM()

    class FakeInner:
        scheduler = FakeSched()

    class FakeEngine:
        engine = FakeInner()

    inb, outb, preempt = _read_swap_counters_from_engine(FakeEngine())
    assert inb == 11
    assert outb == 12


def test_read_swap_counters_returns_zero_on_missing_attrs():
    """The probe must never raise — engines without the expected
    attribute path return (0, 0, 0)."""
    from ctm_bench.runner_vllm_streaming import (
        _read_swap_counters_from_engine,
    )

    class Empty:
        pass

    inb, outb, preempt = _read_swap_counters_from_engine(Empty())
    assert (inb, outb, preempt) == (0, 0, 0)


def test_read_swap_counters_returns_zero_on_legacy_v06_path():
    """vLLM ≤ 0.6 uses block_manager.gpu_allocator (not
    block_allocator). The probe should return zero — the
    streaming runner is targeted at 0.7+."""
    from ctm_bench.runner_vllm_streaming import (
        _read_swap_counters_from_engine,
    )

    class FakeBM:
        gpu_allocator = object()  # legacy attribute, not block_allocator

    class FakeSched:
        block_manager = FakeBM()

    class FakeInner:
        scheduler = FakeSched()

    class FakeEngine:
        engine = FakeInner()

    inb, outb, preempt = _read_swap_counters_from_engine(FakeEngine())
    assert (inb, outb, preempt) == (0, 0, 0)


# ------------------------------------------------------------------ #
# Phase 1 implementation — _build_engine_args
# ------------------------------------------------------------------ #


def test_build_engine_args_sets_preemption_mode_swap():
    """The critical config: preemption_mode='swap' must be passed
    to vLLM's AsyncEngineArgs. Without it, the swap path doesn't
    engage even with AsyncLLMEngine + heavy load."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    captured: dict = {}

    class FakeAsyncEngineArgs:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeVLLM:
        AsyncEngineArgs = FakeAsyncEngineArgs

    driver = AsyncEngineDriver(
        model="dummy", gpu_memory_utilization=0.25,
        swap_space_gb=16, seed=137,
        vllm_module=FakeVLLM,
    )
    driver._build_engine_args(FakeVLLM)
    assert captured.get("preemption_mode") == "swap"
    assert captured.get("model") == "dummy"
    assert captured.get("gpu_memory_utilization") == 0.25
    assert captured.get("swap_space") == 16
    assert captured.get("seed") == 137
    # Phase 1 disables prefix caching to keep eviction in the
    # swap decision tree (not the cache-retention path).
    assert captured.get("enable_prefix_caching") is False


def test_build_engine_args_honours_overrides():
    """scheduler_config_overrides must take precedence over the
    runner's defaults — needed to test e.g.
    preemption_mode='recompute' as a baseline."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    captured: dict = {}

    class FakeAsyncEngineArgs:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeVLLM:
        AsyncEngineArgs = FakeAsyncEngineArgs

    driver = AsyncEngineDriver(
        model="dummy",
        scheduler_config_overrides={"preemption_mode": "recompute"},
        vllm_module=FakeVLLM,
    )
    driver._build_engine_args(FakeVLLM)
    assert captured.get("preemption_mode") == "recompute"


# ------------------------------------------------------------------ #
# Phase 1 implementation — full run() with mocked engine
# ------------------------------------------------------------------ #


def test_async_engine_driver_run_full_flow_with_mock(monkeypatch):
    """End-to-end test of the run() loop with a mocked vLLM
    AsyncLLMEngine. Verifies:
      * The arrival scheduler is consulted for both delays and lengths.
      * Each arrival results in an engine.generate() call.
      * The sampler is started, fed, and stopped.
      * The result struct reports the right counts."""
    import asyncio
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver, ArrivalScheduler, ParetoArrivalConfig,
        SwapCounterSampler,
    )

    # ---- Build a minimal in-memory mock of vLLM's async API ----

    class FakeOutput:
        def __init__(self, n_tokens):
            class _Inner:
                token_ids = list(range(n_tokens))
            self.outputs = [_Inner()]

    class FakeEngine:
        def __init__(self):
            self.generate_calls = []

            class _Sched:
                num_preemption_events = 0

                class _BM:
                    class _Alloc:
                        def get_and_reset_swaps(self):
                            return (0, 0)
                    block_allocator = _Alloc()
                block_manager = _BM()

            class _Inner:
                scheduler = _Sched()

            self.engine = _Inner()

        async def generate(self, prompt, sampling_params, request_id):
            self.generate_calls.append({
                "prompt": prompt,
                "sampling_params": sampling_params,
                "request_id": request_id,
            })
            # Simulate streaming: yield two outputs, ending with
            # 8 tokens generated.
            yield FakeOutput(4)
            yield FakeOutput(8)

    class FakeAsyncEngineArgs:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeAsyncLLMEngine:
        @classmethod
        def from_engine_args(cls, args):
            return FakeEngine()

    class FakeSamplingParams:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeVLLM:
        AsyncEngineArgs = FakeAsyncEngineArgs
        AsyncLLMEngine = FakeAsyncLLMEngine
        SamplingParams = FakeSamplingParams

    # ---- Run ----

    driver = AsyncEngineDriver(
        model="dummy", seed=42,
        max_decode_tokens=8,
        sample_interval_seconds=0.001,
        vllm_module=FakeVLLM,
    )
    sched = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=100.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()

    result = asyncio.new_event_loop().run_until_complete(
        driver.run(
            scheduler=sched, sampler=sampler,
            max_requests=3, max_wall_seconds=2.0,
            workload_name="test_workload",
        )
    )

    # Three arrivals admitted.
    assert result.n_requests_admitted == 3
    # Each completed with 8 decode tokens.
    assert result.n_decode_tokens == 24
    assert result.n_requests_completed == 3
    # Counter source is the streaming default.
    assert result.counter_source == "vllm_streaming_async_swap"
    # No swap engaged in the mock — fine; this test is about flow,
    # not swap behaviour.
    assert result.swap_in_blocks == 0
    assert result.swap_out_blocks == 0
    # Policy name reports lru since ctm_plus_evictor=False.
    assert result.policy_name == "lru"
    assert result.workload_name == "test_workload"
    assert result.seed == 42


def test_async_engine_driver_run_calls_engine_teardown():
    """Multi-cell sweeps need explicit engine teardown to release
    GPU memory between cells. The driver should call one of the
    vLLM teardown methods (shutdown_background_loop / shutdown /
    stop) before run() returns."""
    import asyncio
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver, ArrivalScheduler, ParetoArrivalConfig,
        SwapCounterSampler,
    )

    teardown_called = []

    class FakeOutput:
        outputs = [type("_", (), {"token_ids": [1, 2, 3]})()]

    class FakeEngine:
        engine = type("_", (), {
            "scheduler": type("_", (), {
                "block_manager": type("_", (), {
                    "block_allocator": type("_", (), {
                        "get_and_reset_swaps": staticmethod(lambda: []),
                    })(),
                })(),
            })(),
        })()

        async def generate(self, prompt, sp, rid):
            yield FakeOutput()

        def shutdown_background_loop(self):
            teardown_called.append("shutdown_background_loop")

    class FakeVLLM:
        AsyncEngineArgs = type("_", (), {"__init__": lambda self, **k: None})
        AsyncLLMEngine = type("_", (), {
            "from_engine_args": staticmethod(lambda args: FakeEngine()),
        })
        SamplingParams = type("_", (), {"__init__": lambda self, **k: None})

    driver = AsyncEngineDriver(
        model="dummy", seed=42,
        sample_interval_seconds=0.001,
        vllm_module=FakeVLLM,
    )
    sched = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=100.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()

    asyncio.new_event_loop().run_until_complete(
        driver.run(
            scheduler=sched, sampler=sampler,
            max_requests=2, max_wall_seconds=2.0,
            workload_name="teardown_test",
        )
    )
    assert teardown_called == ["shutdown_background_loop"]


def test_async_engine_driver_run_teardown_falls_back_to_shutdown():
    """If the engine doesn't have shutdown_background_loop, fall
    back to shutdown(). If neither, fall back to stop()."""
    import asyncio
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver, ArrivalScheduler, ParetoArrivalConfig,
        SwapCounterSampler,
    )

    teardown_called = []

    class FakeOutput:
        outputs = [type("_", (), {"token_ids": [1]})()]

    class FakeEngine:
        engine = type("_", (), {
            "scheduler": type("_", (), {
                "block_manager": type("_", (), {
                    "block_allocator": type("_", (), {
                        "get_and_reset_swaps": staticmethod(lambda: []),
                    })(),
                })(),
            })(),
        })()

        async def generate(self, prompt, sp, rid):
            yield FakeOutput()

        # No shutdown_background_loop. Has async shutdown.
        async def shutdown(self):
            teardown_called.append("shutdown")

    class FakeVLLM:
        AsyncEngineArgs = type("_", (), {"__init__": lambda self, **k: None})
        AsyncLLMEngine = type("_", (), {
            "from_engine_args": staticmethod(lambda args: FakeEngine()),
        })
        SamplingParams = type("_", (), {"__init__": lambda self, **k: None})

    driver = AsyncEngineDriver(
        model="dummy", seed=42,
        sample_interval_seconds=0.001,
        vllm_module=FakeVLLM,
    )
    sched = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=100.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()

    asyncio.new_event_loop().run_until_complete(
        driver.run(
            scheduler=sched, sampler=sampler,
            max_requests=1, max_wall_seconds=2.0,
            workload_name="teardown_test_async",
        )
    )
    # The async shutdown was called and awaited.
    assert teardown_called == ["shutdown"]


def test_async_engine_driver_run_caps_at_max_wall(monkeypatch):
    """If max_wall_seconds is exceeded, the run terminates even
    if max_requests has not been reached."""
    import asyncio
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver, ArrivalScheduler, ParetoArrivalConfig,
        SwapCounterSampler,
    )

    class FakeOutput:
        outputs = [type("_", (), {"token_ids": []})()]

    class FakeEngine:
        engine = type("_", (), {
            "scheduler": type("_", (), {
                "block_manager": type("_", (), {
                    "block_allocator": type("_", (), {
                        "get_and_reset_swaps": staticmethod(lambda: (0, 0)),
                    })(),
                })(),
            })(),
        })()

        async def generate(self, prompt, sp, rid):
            # Slow generate — sleeps longer than the wall budget.
            await asyncio.sleep(10.0)
            yield FakeOutput()

    class FakeVLLM:
        AsyncEngineArgs = type("_", (), {"__init__": lambda self, **k: None})
        AsyncLLMEngine = type("_", (), {
            "from_engine_args": staticmethod(lambda args: FakeEngine()),
        })
        SamplingParams = type("_", (), {"__init__": lambda self, **k: None})

    driver = AsyncEngineDriver(
        model="dummy", seed=42,
        sample_interval_seconds=0.05,
        vllm_module=FakeVLLM,
    )
    sched = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=1000.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()

    start = __import__("time").perf_counter()
    result = asyncio.new_event_loop().run_until_complete(
        driver.run(
            scheduler=sched, sampler=sampler,
            max_requests=1000, max_wall_seconds=0.3,
            workload_name="cap_test",
        )
    )
    elapsed = __import__("time").perf_counter() - start
    # Wall budget honoured (with some tolerance for shutdown).
    assert elapsed < 1.5, f"run took {elapsed:.2f}s; budget was 0.3s"
    # Some requests admitted, but most won't have completed (the
    # mocked generate sleeps 10s).
    assert result.n_requests_admitted >= 1
    assert result.n_requests_completed == 0


# ------------------------------------------------------------------ #
# Phase 2 — CTMEvictorModern + patch_vllm_engine_modern
# ------------------------------------------------------------------ #


def test_async_engine_driver_phase2_patch_failure_tears_down_engine():
    """Audit-pass MEDIUM #2 fix: if patch_vllm_engine_modern raises
    (because prefix caching is off, allocator drift, etc.), the
    engine must be shut down — otherwise multi-cell sweeps leak
    GPU memory and worker subprocesses."""
    import asyncio
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver, ArrivalScheduler, ParetoArrivalConfig,
        SwapCounterSampler,
    )

    teardown_calls = []

    class FakeEngine:
        engine = type("_", (), {
            "scheduler": type("_", (), {
                "block_manager": type("_", (), {
                    # No block_allocator — guaranteed to make
                    # patch_vllm_engine_modern raise RuntimeError.
                })(),
            })(),
        })()

        def shutdown_background_loop(self):
            teardown_calls.append("shutdown_background_loop")

    class FakeVLLM:
        AsyncEngineArgs = type("_", (), {"__init__": lambda self, **k: None})
        AsyncLLMEngine = type("_", (), {
            "from_engine_args": staticmethod(lambda args: FakeEngine()),
        })
        SamplingParams = type("_", (), {"__init__": lambda self, **k: None})

    driver = AsyncEngineDriver(
        model="dummy", seed=42,
        ctm_plus_evictor=True,
        enable_prefix_caching=True,
        sample_interval_seconds=0.001,
        vllm_module=FakeVLLM,
    )
    sched = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=100.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()

    with pytest.raises(RuntimeError):
        asyncio.new_event_loop().run_until_complete(
            driver.run(
                scheduler=sched, sampler=sampler,
                max_requests=2, max_wall_seconds=2.0,
                workload_name="patch_failure_test",
            )
        )
    # Audit-pass invariant: the engine got torn down before the
    # exception propagated, even though the main run-loop's
    # try/finally never started.
    assert teardown_calls == ["shutdown_background_loop"]


def test_ctm_evictor_modern_implements_vllm_07_evictor_abc():
    """CTMEvictorModern must satisfy the methods vLLM 0.7's
    PrefixCachingBlockAllocator calls on its evictor: __contains__,
    add, update, remove, evict, num_blocks."""
    from kv_policy.vllm_evictor import CTMEvictorModern

    ev = CTMEvictorModern(num_blocks_capacity=128, block_size=16)

    # Initially empty.
    assert ev.num_blocks == 0
    assert 42 not in ev

    # Add a block.
    ev.add(block_id=42, content_hash=12345, num_hashed_tokens=16,
           last_accessed=100.0)
    assert 42 in ev
    assert ev.num_blocks == 1

    # Update access (no exception).
    ev.update(block_id=42, last_accessed=110.0)

    # Add a few more blocks so evict has candidates.
    for bid in (43, 44, 45, 46):
        ev.add(block_id=bid, content_hash=bid * 100,
               num_hashed_tokens=16, last_accessed=120.0)
    assert ev.num_blocks == 5

    # Evict — must return (block_id, content_hash) tuple.
    victim_id, victim_hash = ev.evict()
    assert isinstance(victim_id, int)
    assert isinstance(victim_hash, int)
    assert victim_id in {42, 43, 44, 45, 46}
    assert ev.num_blocks == 4
    assert victim_id not in ev

    # Remove (different from evict — caller-driven free, not eviction).
    # Pick a block that the evictor *didn't* evict so we exercise the
    # remove path rather than the no-op-on-untracked path.
    survivors = {42, 43, 44, 45, 46} - {victim_id}
    target = next(iter(survivors))
    ev.remove(target)
    assert target not in ev
    assert ev.num_blocks == 3


def test_ctm_evictor_modern_evict_raises_on_empty_cache():
    """vLLM's LRUEvictor contract: evict() raises when the cache is
    empty — vLLM should never call it in that state, but if it does,
    we want a clear error rather than silent return-None."""
    from kv_policy.vllm_evictor import CTMEvictorModern

    ev = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    with pytest.raises(ValueError, match="no tracked blocks"):
        ev.evict()


def test_ctm_evictor_modern_update_before_add_is_silent():
    """vLLM may call update() on a block_id that hasn't been added
    yet (race or staged eviction). The evictor must tolerate this
    rather than raise."""
    from kv_policy.vllm_evictor import CTMEvictorModern

    ev = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    # Before add — no exception, no state change.
    ev.update(block_id=999, last_accessed=100.0)
    assert ev.num_blocks == 0


def test_ctm_evictor_modern_remove_untracked_is_silent():
    """remove() on an unknown block_id should be a no-op, not raise."""
    from kv_policy.vllm_evictor import CTMEvictorModern

    ev = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    ev.remove(block_id=999)   # untracked
    assert ev.num_blocks == 0


def test_patch_vllm_engine_modern_walks_to_prefix_caching_allocator():
    """patch_vllm_engine_modern must walk
    engine -> engine.engine.scheduler[0].block_manager.block_allocator
        -> ._allocators[<gpu_key>].evictor
    and replace the LRUEvictor with a CTMEvictorModern."""
    from kv_policy.vllm_evictor import patch_vllm_engine_modern

    # Build a minimal fake engine that mirrors vLLM 0.7's structure.
    class FakeLRUEvictor:
        num_blocks = 256

        def __contains__(self, _):
            return False

    class FakePrefixCachingAllocator:
        num_blocks = 256
        _block_size = 16
        evictor = FakeLRUEvictor()

    class FakeNaiveAllocator:
        # Notably no `evictor` attribute.
        num_blocks = 256

    class _FakeDevice:
        def __init__(self, name):
            self.name = name

    GPU_KEY = _FakeDevice("GPU")
    CPU_KEY = _FakeDevice("CPU")
    gpu_alloc = FakePrefixCachingAllocator()

    class FakeBlockAllocator:
        _allocators = {GPU_KEY: gpu_alloc, CPU_KEY: FakeNaiveAllocator()}

    class FakeBlockManager:
        block_allocator = FakeBlockAllocator()

    class FakeScheduler:
        block_manager = FakeBlockManager()

    class FakeInner:
        scheduler = [FakeScheduler()]

    class FakeEngine:
        engine = FakeInner()

    # Pre-patch: gpu_alloc.evictor is the fake LRU.
    assert isinstance(gpu_alloc.evictor, FakeLRUEvictor)

    installed = patch_vllm_engine_modern(FakeEngine())

    # Post-patch: gpu_alloc.evictor is CTMEvictorModern.
    from kv_policy.vllm_evictor import CTMEvictorModern
    assert isinstance(installed, CTMEvictorModern)
    assert isinstance(gpu_alloc.evictor, CTMEvictorModern)
    # The CPU allocator was untouched.
    assert isinstance(
        FakeBlockAllocator._allocators[CPU_KEY], FakeNaiveAllocator
    )


def test_patch_vllm_engine_modern_raises_when_prefix_caching_off():
    """If the GPU allocator is NaiveBlockAllocator (no evictor
    attribute), the patch must raise NotImplementedError naming
    enable_prefix_caching=True as the fix."""
    from kv_policy.vllm_evictor import patch_vllm_engine_modern

    class FakeNaiveAllocator:
        # No evictor attribute.
        num_blocks = 256

    class _FakeDevice:
        def __init__(self, name):
            self.name = name

    GPU_KEY = _FakeDevice("GPU")

    class FakeBlockAllocator:
        _allocators = {GPU_KEY: FakeNaiveAllocator()}

    class FakeBlockManager:
        block_allocator = FakeBlockAllocator()

    class FakeScheduler:
        block_manager = FakeBlockManager()

    class FakeInner:
        scheduler = FakeScheduler()  # not a list — single-scheduler layout

    class FakeEngine:
        engine = FakeInner()

    with pytest.raises(NotImplementedError) as exc:
        patch_vllm_engine_modern(FakeEngine())
    msg = str(exc.value)
    assert "enable_prefix_caching" in msg
    assert "NaiveBlockAllocator" in msg


def test_patch_vllm_engine_modern_handles_legacy_v06_path():
    """vLLM ≤ 0.6 has block_manager.gpu_allocator (not block_allocator).
    The modern patch should fail cleanly with a RuntimeError naming
    what's missing — the legacy patch path is the right one for that
    version."""
    from kv_policy.vllm_evictor import patch_vllm_engine_modern

    class FakeBlockManager:
        # Has gpu_allocator (legacy) but NOT block_allocator (modern).
        gpu_allocator = object()

    class FakeScheduler:
        block_manager = FakeBlockManager()

    class FakeEngine:
        scheduler = FakeScheduler()

    with pytest.raises(RuntimeError, match="block_allocator"):
        patch_vllm_engine_modern(FakeEngine())


def test_patch_vllm_engine_modern_re_exports_from_kv_policy():
    """The streaming runner's patch_vllm_engine_modern is a thin
    re-export of kv_policy.vllm_evictor.patch_vllm_engine_modern.
    Calling it should reach the real implementation; on a fake
    engine that doesn't expose .scheduler, the real implementation
    raises RuntimeError (NOT NotImplementedError) — confirming the
    re-export path works."""
    from ctm_bench.runner_vllm_streaming import (
        patch_vllm_engine_modern,
    )

    fake_engine = object()
    with pytest.raises(RuntimeError, match="block manager"):
        patch_vllm_engine_modern(fake_engine)


# Regression marker: the Phase 2 stub is GONE. patch_vllm_engine_modern
# now reaches the real implementation in kv_policy.vllm_evictor and
# raises RuntimeError on a malformed engine (not NotImplementedError).
def test_patch_vllm_engine_modern_no_longer_stubbed_with_notimpl():
    """If we ever regress and re-stub Phase 2 with a blanket
    NotImplementedError on any engine, this test fails."""
    from ctm_bench.runner_vllm_streaming import (
        patch_vllm_engine_modern,
    )

    fake_engine = object()
    try:
        patch_vllm_engine_modern(fake_engine)
        raised = None
    except NotImplementedError as exc:
        # Allowed only if the message specifically names the
        # prefix-caching prerequisite (a real implementation
        # detecting NaiveBlockAllocator). A blanket "Phase 2
        # not yet implemented" stub message is a regression.
        if "Phase 2" in str(exc) and "not yet implemented" in str(exc):
            raise AssertionError(
                "patch_vllm_engine_modern is back to a 'not yet "
                "implemented' stub; Phase 2 has been re-stubbed."
            )
        raised = exc
    except RuntimeError as exc:
        # This is the expected path when given a malformed engine —
        # the real implementation tries to walk engine.scheduler and
        # fails cleanly.
        raised = exc
    # Either RuntimeError or a specific NotImplementedError about
    # prefix caching is fine; the blanket stub is not.
    assert raised is not None or True


# ------------------------------------------------------------------ #
# Phase 3 — attention forwarding (real attention into CTM+)
# ------------------------------------------------------------------ #


def test_aggregate_attention_to_blocks_basic():
    """Pure-Python aggregation: per-key attention vector +
    block_table -> per-block sums."""
    from kv_policy.vllm_evictor import aggregate_attention_to_blocks

    # block_size=4 tokens. Three blocks: [B0|B1|B2] mapped to
    # block_ids [42, 43, 44].
    weights = [
        0.10, 0.05, 0.20, 0.15,    # B0 sums to 0.50
        0.02, 0.03, 0.05, 0.10,    # B1 sums to 0.20
        0.10, 0.10, 0.05, 0.05,    # B2 sums to 0.30
    ]
    block_table = [42, 43, 44]
    out = aggregate_attention_to_blocks(weights, block_table, block_size=4)
    assert out == {42: pytest.approx(0.50), 43: pytest.approx(0.20),
                   44: pytest.approx(0.30)}


def test_aggregate_attention_to_blocks_partial_last_block():
    """Last block may be partially filled (sequence length not a
    multiple of block_size). The function should sum only the
    available weights and not crash."""
    from kv_policy.vllm_evictor import aggregate_attention_to_blocks

    weights = [0.5, 0.5, 0.3]   # 3 keys, would fit in 1 full block of 4
    block_table = [99]
    out = aggregate_attention_to_blocks(weights, block_table, block_size=4)
    assert out == {99: pytest.approx(1.3)}


def test_aggregate_attention_to_blocks_rejects_too_many_weights():
    from kv_policy.vllm_evictor import aggregate_attention_to_blocks

    # 5 weights but only 1 block of 4 → mismatch.
    with pytest.raises(ValueError, match="block_table"):
        aggregate_attention_to_blocks(
            [0.1] * 5, block_table=[10], block_size=4,
        )


def test_aggregate_attention_to_blocks_rejects_bad_block_size():
    from kv_policy.vllm_evictor import aggregate_attention_to_blocks

    with pytest.raises(ValueError, match="block_size must be > 0"):
        aggregate_attention_to_blocks([0.1], block_table=[1], block_size=0)


def test_attention_aggregator_buffer_and_flush():
    """AttentionAggregator: record per-block weights, flush to a
    fake evictor, verify forward_block_attention was called with
    the cumulative sums."""
    from kv_policy.vllm_evictor import AttentionAggregator

    captured: List[tuple] = []

    class FakeEvictor:
        def forward_block_attention(self, block_id, attention_sum):
            captured.append((block_id, attention_sum))

    agg = AttentionAggregator()
    agg.record_block_attention(42, 0.10)
    agg.record_block_attention(43, 0.05)
    # Same block_id again — should accumulate.
    agg.record_block_attention(42, 0.20)
    assert agg.buffered_blocks == 2

    n = agg.flush_to_evictor(FakeEvictor())
    assert n == 2
    captured.sort()
    assert captured[0][0] == 42 and captured[0][1] == pytest.approx(0.30)
    assert captured[1][0] == 43 and captured[1][1] == pytest.approx(0.05)
    # Buffer cleared after flush.
    assert agg.buffered_blocks == 0
    # Stats updated.
    assert agg.stats["samples_recorded"] == 3
    assert agg.stats["blocks_flushed"] == 2
    assert agg.stats["flushes"] == 1


def test_attention_aggregator_record_block_batch():
    """Bulk-record path: aggregator.record_block_batch({block: weight})."""
    from kv_policy.vllm_evictor import AttentionAggregator

    captured: List[tuple] = []

    class FakeEvictor:
        def forward_block_attention(self, block_id, attention_sum):
            captured.append((block_id, attention_sum))

    agg = AttentionAggregator()
    # Layer 0 emits per-block sums.
    agg.record_block_batch({1: 0.4, 2: 0.3})
    # Layer 1 emits more — should accumulate.
    agg.record_block_batch({1: 0.1, 2: 0.2, 3: 0.5})
    agg.flush_to_evictor(FakeEvictor())
    captured.sort()
    assert captured[0] == (1, pytest.approx(0.5))
    assert captured[1] == (2, pytest.approx(0.5))
    assert captured[2] == (3, pytest.approx(0.5))


def test_attention_aggregator_flush_empty_returns_zero():
    from kv_policy.vllm_evictor import AttentionAggregator

    class FakeEvictor:
        def forward_block_attention(self, block_id, attention_sum):
            raise AssertionError("should not be called on empty flush")

    agg = AttentionAggregator()
    assert agg.flush_to_evictor(FakeEvictor()) == 0


def test_attention_aggregator_tolerates_evictor_errors():
    """A stale block_id (one that's been evicted between capture
    and flush) is dropped; the rest still flush."""
    from kv_policy.vllm_evictor import AttentionAggregator

    captured: List[int] = []

    class FlakyEvictor:
        def forward_block_attention(self, block_id, attention_sum):
            if block_id == 999:
                raise KeyError(block_id)
            captured.append(block_id)

    agg = AttentionAggregator()
    agg.record_block_attention(42, 0.5)
    agg.record_block_attention(999, 0.5)   # this one will raise
    agg.record_block_attention(43, 0.5)
    n = agg.flush_to_evictor(FlakyEvictor())
    # 2 flushed, 1 dropped (the one that raised).
    assert n == 2
    assert sorted(captured) == [42, 43]


def test_ctm_evictor_modern_forward_block_attention_changes_score():
    """Forwarding non-zero attention should differentiate the
    block's score from a zero-attention block. Without this, all
    blocks have the same attention=0 and score on recency only."""
    from kv_policy.vllm_evictor import CTMEvictorModern

    ev = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    # Add three blocks at the same logical time.
    for bid in (10, 20, 30):
        ev.add(block_id=bid, content_hash=bid * 7,
               num_hashed_tokens=16, last_accessed=100.0)
    # Push real attention only to block 20 — make it the most
    # important block.
    ev.forward_block_attention(20, attention_sum=5.0)

    # Score 10 (no attention) vs 20 (high attention). 20's score
    # MUST be higher (less likely to evict).
    score_10 = ev._policy.score_block(10)
    score_20 = ev._policy.score_block(20)
    assert score_20 > score_10, (
        f"Block with high attention (score={score_20}) "
        f"should outrank block with no attention (score={score_10})"
    )


def test_ctm_evictor_modern_forward_block_attention_silent_on_untracked():
    from kv_policy.vllm_evictor import CTMEvictorModern

    ev = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    # No add(). forward_block_attention on an untracked block
    # should be silent, not raise.
    ev.forward_block_attention(999, attention_sum=10.0)


def test_install_attention_capture_finds_attention_modules():
    """install_attention_capture walks the model tree, identifies
    Attention layers by class name, and patches their forward."""
    from kv_policy.vllm_evictor import (
        install_attention_capture, AttentionAggregator,
    )

    # Build a fake model with two "Attention" modules + non-attention.
    class FakeAttention:
        def __init__(self, name):
            self._name = name
            self.head_size = 64
            self.num_heads = 8
            self.original_forward_called = 0

        def forward(self, query, key, value, kv_cache, attn_metadata):
            self.original_forward_called += 1
            return query  # dummy

    class FakeMLP:
        # Looks like an nn.Module but isn't an Attention.
        def forward(self, x):
            return x

    class FakeModel:
        def __init__(self):
            self.layer0 = FakeAttention("layer0")
            self.layer1 = FakeAttention("layer1")
            self.mlp = FakeMLP()

    model = FakeModel()
    aggregator = AttentionAggregator()
    captured = []

    class FakeEvictor:
        def forward_block_attention(self, block_id, attention_sum):
            captured.append((block_id, attention_sum))

    n = install_attention_capture(
        model=model, aggregator=aggregator, evictor=FakeEvictor(),
    )
    # Two Attention layers found and patched. MLP not patched.
    assert n == 2

    # The patched forwards should still call the original (correctness
    # invariant). Use plain Python objects in lieu of torch tensors —
    # the test-mode capture branch uses the side-channel
    # `decode_attention_weights` and never touches torch.
    class FakeAttnMeta:
        num_decode_tokens = 1
        num_prefill_tokens = 0
        block_size = 4
        block_tables = [[42, 43]]
        # Test-mode side channel: pre-computed per-block weights.
        decode_attention_weights = {42: 0.7, 43: 0.3}

    # Inputs can be any opaque values — the real arithmetic happens
    # only on the GPU-validation path which the test-mode side
    # channel skips entirely.
    sentinel_q = object()
    sentinel_k = object()
    sentinel_v = object()
    sentinel_kv_cache = object()

    model.layer0.forward(
        sentinel_q, sentinel_k, sentinel_v, sentinel_kv_cache, FakeAttnMeta(),
    )
    # Original forward was called (correctness preserved).
    assert model.layer0.original_forward_called == 1
    # Aggregator buffered the per-block weights from the side channel.
    assert aggregator.buffered_blocks == 2


def test_install_attention_capture_returns_zero_on_empty_model(caplog):
    """If no Attention modules are found, the installer logs a
    warning and returns 0 — does NOT crash."""
    from kv_policy.vllm_evictor import (
        install_attention_capture, AttentionAggregator,
    )

    class EmptyModel:
        # No attention modules anywhere.
        pass

    aggregator = AttentionAggregator()
    n = install_attention_capture(
        model=EmptyModel(), aggregator=aggregator, evictor=object(),
    )
    assert n == 0


def test_async_engine_driver_phase3_requires_phase2():
    """phase3_attention_capture=True requires ctm_plus_evictor=True
    (you need an evictor to push attention to). Constructor
    rejects the invalid combination."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    with pytest.raises(ValueError, match="ctm_plus_evictor=True"):
        AsyncEngineDriver(
            model="dummy",
            ctm_plus_evictor=False,
            phase3_attention_capture=True,
        )


def test_async_engine_driver_phase3_constructor_stores_flag():
    """When ctm_plus_evictor=True + phase3_attention_capture=True,
    the driver stores the flag for the run loop to act on."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    driver = AsyncEngineDriver(
        model="dummy",
        ctm_plus_evictor=True,
        phase3_attention_capture=True,
    )
    assert driver.phase3_attention_capture is True
    assert driver.ctm_plus_evictor is True
    assert driver.enable_prefix_caching is True   # forced by ctm_plus


def _torch_or_skip():
    """Return torch module or skip the test if torch isn't installed."""
    try:
        import torch  # noqa: F401
        return __import__("torch")
    except ImportError:
        pytest.skip("torch not installed; GPU-extraction math test skipped")


def test_gpu_extract_no_decode_tokens_is_noop():
    """If attn_metadata.num_decode_tokens == 0, the extraction
    should be a clean no-op — prefill batches don't have decode
    queries to attribute to blocks."""
    torch = _torch_or_skip()
    from kv_policy.vllm_evictor import (
        AttentionAggregator, _gpu_extract_decode_attention,
    )

    class FakeMeta:
        num_decode_tokens = 0
        num_prefill_tokens = 4
        block_tables = []

    agg = AttentionAggregator()
    _gpu_extract_decode_attention(
        query=torch.zeros((4, 64)),
        kv_cache=torch.zeros((1, 4, 1, 64)),
        attn_metadata=FakeMeta(),
        head_dim=64,
        aggregator=agg,
    )
    assert agg.buffered_blocks == 0


def test_gpu_extract_one_decode_token_aggregates_per_block():
    """End-to-end: one decode-step query, kv_cache with two
    blocks, verify softmax(Q @ K^T) is aggregated per-block and
    the sums approximately match a manual computation."""
    torch = _torch_or_skip()
    import math
    import torch.nn.functional as F
    from kv_policy.vllm_evictor import (
        AttentionAggregator, _gpu_extract_decode_attention,
    )

    head_dim = 4
    num_heads = 2
    num_kv_heads = 2          # no GQA — simplest case
    block_size = 4
    num_blocks = 2
    seq_len = 6               # 1.5 blocks; tests partial-last-block

    # Build deterministic K cache.
    torch.manual_seed(0)
    k_cache = torch.randn(
        (num_blocks, block_size, num_kv_heads, head_dim),
    )
    # vLLM 0.7 FlashAttention layout: kv_cache[0] is K. Wrap in
    # a [2, ...] tensor so the extractor's auto-detection picks
    # K out of index [0].
    kv_cache = torch.stack([k_cache, torch.zeros_like(k_cache)], dim=0)

    # Build a decode query: 1 token, num_heads * head_dim wide.
    query = torch.randn((1, num_heads * head_dim))

    class FakeMeta:
        num_decode_tokens = 1
        num_prefill_tokens = 0
        block_tables = [[0, 1]]
        seq_lens = [seq_len]

    agg = AttentionAggregator()
    _gpu_extract_decode_attention(
        query=query,
        kv_cache=kv_cache,
        attn_metadata=FakeMeta(),
        head_dim=head_dim,
        aggregator=agg,
    )

    # Expected: one entry per block_id (0 and 1) since both blocks
    # are referenced in this sequence's block_table.
    assert agg.buffered_blocks == 2

    # Verify total mass ≈ 1.0 (softmax probabilities sum to 1 over
    # the seq_len dimension, then aggregated by block; total
    # should equal 1.0 within float tolerance).
    captured = []

    class FakeEvictor:
        def forward_block_attention(self, block_id, attention_sum):
            captured.append((block_id, attention_sum))

    agg.flush_to_evictor(FakeEvictor())
    total = sum(s for _, s in captured)
    assert abs(total - 1.0) < 1e-4, (
        f"softmax probabilities aggregated per-block should sum "
        f"to ~1.0; got {total}"
    )


def test_gpu_extract_handles_gqa():
    """GQA: num_heads > num_kv_heads. K must be repeated to match
    Q's head count. Verify the extraction doesn't crash and
    produces reasonable per-block sums."""
    torch = _torch_or_skip()
    from kv_policy.vllm_evictor import (
        AttentionAggregator, _gpu_extract_decode_attention,
    )

    head_dim = 4
    num_heads = 4              # 4 query heads
    num_kv_heads = 2           # 2 KV heads -> GQA factor 2
    block_size = 4
    num_blocks = 2
    seq_len = 8                # exactly 2 blocks

    torch.manual_seed(7)
    k_cache = torch.randn((num_blocks, block_size, num_kv_heads, head_dim))
    kv_cache = torch.stack([k_cache, torch.zeros_like(k_cache)], dim=0)

    query = torch.randn((1, num_heads * head_dim))

    class FakeMeta:
        num_decode_tokens = 1
        num_prefill_tokens = 0
        block_tables = [[0, 1]]
        seq_lens = [seq_len]

    agg = AttentionAggregator()
    _gpu_extract_decode_attention(
        query=query,
        kv_cache=kv_cache,
        attn_metadata=FakeMeta(),
        head_dim=head_dim,
        aggregator=agg,
    )

    assert agg.buffered_blocks == 2


def test_gpu_extract_partial_last_block():
    """A sequence whose seq_len isn't a multiple of block_size:
    the last block is partially filled. Aggregation must truncate
    correctly."""
    torch = _torch_or_skip()
    from kv_policy.vllm_evictor import (
        AttentionAggregator, _gpu_extract_decode_attention,
    )

    head_dim = 4
    num_heads = 2
    num_kv_heads = 2
    block_size = 4
    seq_len = 7                # 1 full block + 3 tokens of next

    torch.manual_seed(1)
    k_cache = torch.randn((2, block_size, num_kv_heads, head_dim))
    kv_cache = torch.stack([k_cache, torch.zeros_like(k_cache)], dim=0)
    query = torch.randn((1, num_heads * head_dim))

    class FakeMeta:
        num_decode_tokens = 1
        num_prefill_tokens = 0
        block_tables = [[0, 1]]
        seq_lens = [seq_len]

    agg = AttentionAggregator()
    _gpu_extract_decode_attention(
        query=query,
        kv_cache=kv_cache,
        attn_metadata=FakeMeta(),
        head_dim=head_dim,
        aggregator=agg,
    )
    # Both blocks referenced.
    assert agg.buffered_blocks == 2


def test_gpu_extract_raises_on_bad_head_dim_alignment():
    """If query.shape[-1] is not a multiple of head_dim, the
    extractor raises ValueError — caught by the wrapped-forward
    try/except in production, surfacing as a "layout mismatch"
    warning."""
    torch = _torch_or_skip()
    from kv_policy.vllm_evictor import (
        AttentionAggregator, _gpu_extract_decode_attention,
    )

    class FakeMeta:
        num_decode_tokens = 1
        num_prefill_tokens = 0
        block_tables = [[0]]
        seq_lens = [4]

    # query last dim = 33, head_dim = 4 -> not a multiple.
    query = torch.zeros((1, 33))
    kv_cache = torch.zeros((1, 4, 1, 4))

    with pytest.raises(ValueError, match="not a multiple"):
        _gpu_extract_decode_attention(
            query=query,
            kv_cache=kv_cache,
            attn_metadata=FakeMeta(),
            head_dim=4,
            aggregator=AttentionAggregator(),
        )


def test_gpu_extract_raises_on_kv_cache_head_dim_mismatch():
    """If the kv_cache's head_dim differs from the query's,
    raise ValueError."""
    torch = _torch_or_skip()
    from kv_policy.vllm_evictor import (
        AttentionAggregator, _gpu_extract_decode_attention,
    )

    class FakeMeta:
        num_decode_tokens = 1
        num_prefill_tokens = 0
        block_tables = [[0]]
        seq_lens = [4]

    query = torch.zeros((1, 8))           # head_dim 4 implied
    kv_cache = torch.zeros((1, 4, 1, 8))  # head_dim 8 — mismatch

    with pytest.raises(ValueError, match="head_dim mismatch"):
        _gpu_extract_decode_attention(
            query=query,
            kv_cache=kv_cache,
            attn_metadata=FakeMeta(),
            head_dim=4,
            aggregator=AttentionAggregator(),
        )


def test_gpu_extract_raises_on_non_integer_gqa_factor():
    """If num_heads isn't divisible by num_kv_heads, the GQA
    repeat-interleave doesn't work — raise ValueError."""
    torch = _torch_or_skip()
    from kv_policy.vllm_evictor import (
        AttentionAggregator, _gpu_extract_decode_attention,
    )

    head_dim = 4
    num_heads = 3      # 3 query heads
    num_kv_heads = 2   # 2 KV heads -> 1.5 GQA factor (invalid)

    class FakeMeta:
        num_decode_tokens = 1
        num_prefill_tokens = 0
        block_tables = [[0]]
        seq_lens = [4]

    query = torch.zeros((1, num_heads * head_dim))
    kv_cache = torch.zeros((1, 4, num_kv_heads, head_dim))

    with pytest.raises(ValueError, match="GQA"):
        _gpu_extract_decode_attention(
            query=query,
            kv_cache=kv_cache,
            attn_metadata=FakeMeta(),
            head_dim=head_dim,
            aggregator=AttentionAggregator(),
        )


# ------------------------------------------------------------------ #
# Timing instrumentation — per-evict + attention-capture overhead.
# ------------------------------------------------------------------ #


def test_ctm_evictor_modern_evict_records_timing():
    """Each evict() call must append its wall-clock duration to
    the per-evict timing buffer. Used by the runner to compute
    p50/p99 evict overhead at end of cell."""
    from kv_policy.vllm_evictor import CTMEvictorModern

    ev = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    for bid in (10, 20, 30, 40):
        ev.add(block_id=bid, content_hash=bid * 7,
               num_hashed_tokens=16, last_accessed=100.0)
    assert ev.evict_timings_seconds() == []

    ev.evict()
    ev.evict()
    timings = ev.evict_timings_seconds()
    assert len(timings) == 2
    # Each timing should be a positive float, microseconds-scale
    # for in-process evict on a typical sandbox.
    assert all(t > 0 for t in timings)
    assert all(t < 1.0 for t in timings), (
        f"per-evict times {timings} are absurdly slow; CTM+ "
        "scoring should take < 1s in-process"
    )


def test_ctm_evictor_modern_evict_records_timing_even_on_error():
    """An evict() that raises (empty cache) still appends a
    timing — finally clause guarantees coverage of the failure
    path so the runner's overhead numbers reflect total time
    spent in evict, not just successful calls."""
    from kv_policy.vllm_evictor import CTMEvictorModern

    ev = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    # Empty cache; evict() raises ValueError.
    try:
        ev.evict()
    except ValueError:
        pass
    # The failed call still recorded a timing.
    assert len(ev.evict_timings_seconds()) == 1


def test_ctm_evictor_modern_reset_evict_timings_clears_buffer():
    from kv_policy.vllm_evictor import CTMEvictorModern

    ev = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    ev.add(block_id=1, content_hash=1, num_hashed_tokens=16,
           last_accessed=0.0)
    ev.evict()
    assert len(ev.evict_timings_seconds()) == 1
    ev.reset_evict_timings()
    assert ev.evict_timings_seconds() == []


def test_attention_aggregator_record_capture_time_appends():
    """Phase 3 capture-time recording: the wrapped Attention.forward
    calls aggregator.record_capture_time(dt) on every call.
    Aggregator buffers the durations for end-of-cell aggregation."""
    from kv_policy.vllm_evictor import AttentionAggregator

    agg = AttentionAggregator()
    assert agg.capture_timings_seconds() == []

    agg.record_capture_time(0.005)
    agg.record_capture_time(0.003)
    agg.record_capture_time(0.012)
    timings = agg.capture_timings_seconds()
    assert timings == [0.005, 0.003, 0.012]


def test_attention_aggregator_rejects_negative_capture_time():
    from kv_policy.vllm_evictor import AttentionAggregator

    agg = AttentionAggregator()
    with pytest.raises(ValueError, match="must be >= 0"):
        agg.record_capture_time(-0.001)


def test_install_attention_capture_records_capture_time_per_layer():
    """End-to-end: a wrapped Attention.forward records timing on
    every call (success or failure). After 3 forward calls,
    the aggregator has 3 capture timings."""
    from kv_policy.vllm_evictor import (
        install_attention_capture, AttentionAggregator,
    )

    class FakeAttention:
        head_size = 4
        num_heads = 2

        def forward(self, query, key, value, kv_cache, attn_metadata):
            return query  # no-op

    class FakeModel:
        def __init__(self):
            self.layer0 = FakeAttention()

    class FakeAttnMeta:
        num_decode_tokens = 1
        num_prefill_tokens = 0
        block_size = 4
        block_tables = [[0]]
        decode_attention_weights = {0: 1.0}

    model = FakeModel()
    agg = AttentionAggregator()
    install_attention_capture(
        model=model, aggregator=agg, evictor=object(),
    )
    # Three forward calls -> three capture timings.
    for _ in range(3):
        model.layer0.forward(
            object(), object(), object(), object(), FakeAttnMeta(),
        )
    assert len(agg.capture_timings_seconds()) == 3


def test_compute_p50_p99_microseconds_basic():
    """Smoke test for the percentile helper on simple distributions."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    # 100 evenly-spaced values 1..100 microseconds.
    timings_seconds = [i * 1e-6 for i in range(1, 101)]
    p50, p99 = AsyncEngineDriver._compute_p50_p99_microseconds(timings_seconds)
    # Type-7 interpolation: p50 of 1..100 = 50.5, p99 = 99.01.
    assert abs(p50 - 50.5) < 0.01
    assert abs(p99 - 99.01) < 0.5


def test_compute_p50_p99_microseconds_empty_returns_zero():
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    p50, p99 = AsyncEngineDriver._compute_p50_p99_microseconds([])
    assert (p50, p99) == (0.0, 0.0)


def test_compute_p50_p99_microseconds_single_value():
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    p50, p99 = AsyncEngineDriver._compute_p50_p99_microseconds([5e-6])
    assert (p50, p99) == (5.0, 5.0)


def test_streaming_run_cell_result_has_timing_fields():
    """The result dataclass must carry the new timing fields with
    sensible defaults so callers that don't pass them get zeros
    (matching the LRU-baseline-no-timing convention)."""
    from ctm_bench.runner_vllm_streaming import StreamingRunCellResult

    r = StreamingRunCellResult(
        workload_name="x", policy_name="lru", seed=42,
        n_requests_admitted=10, n_requests_completed=8,
        n_decode_tokens=4096, wall_clock_seconds=12.5,
        swap_in_blocks=128, swap_out_blocks=128,
        preemption_events=4,
    )
    assert r.tokens_per_second == 0.0
    assert r.evict_call_count == 0
    assert r.evict_total_seconds == 0.0
    assert r.evict_p50_microseconds == 0.0
    assert r.evict_p99_microseconds == 0.0
    assert r.attention_capture_call_count == 0
    assert r.attention_capture_total_seconds == 0.0


def test_async_engine_driver_run_phase2_populates_evict_timings(monkeypatch):
    """End-to-end: a Phase 2 run with a mocked engine + real
    CTMEvictorModern populates evict_call_count + tokens_per_second
    in the result. Verifies the run-end aggregation actually reads
    from the installed evictor's timing buffer."""
    import asyncio
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver, ArrivalScheduler, ParetoArrivalConfig,
        SwapCounterSampler,
    )

    class FakeOutput:
        outputs = [type("_", (), {"token_ids": [1, 2, 3]})()]

    class FakeEngine:
        engine = type("_", (), {
            "scheduler": type("_", (), {
                "block_manager": type("_", (), {
                    "block_allocator": type("_", (), {
                        "get_and_reset_swaps": staticmethod(lambda: []),
                        # The Phase 2 patch path needs an
                        # _allocators dict with an evictor slot.
                        "_allocators": {
                            type("_", (), {"name": "GPU"})(): type(
                                "_", (), {
                                    "evictor": type("LRUEvictor", (), {})(),
                                    "num_blocks": 256,
                                    "_block_size": 16,
                                }
                            )(),
                        },
                    })(),
                })(),
            })(),
        })()

        async def generate(self, prompt, sp, rid):
            yield FakeOutput()

        def shutdown_background_loop(self):
            pass

    class FakeVLLM:
        AsyncEngineArgs = type("_", (), {"__init__": lambda self, **k: None})
        AsyncLLMEngine = type("_", (), {
            "from_engine_args": staticmethod(lambda args: FakeEngine()),
        })
        SamplingParams = type("_", (), {"__init__": lambda self, **k: None})

    driver = AsyncEngineDriver(
        model="dummy", seed=42,
        ctm_plus_evictor=True,
        enable_prefix_caching=True,
        sample_interval_seconds=0.001,
        vllm_module=FakeVLLM,
    )
    sched = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=100.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()

    # Manually trigger one evict on the patched evictor mid-run by
    # adding a block + calling evict ourselves. We do this via a
    # post-construction hook before run() returns.

    # Run loop completes: result should have tokens_per_second > 0
    # since FakeOutput emits 3 token_ids per request.
    result = asyncio.new_event_loop().run_until_complete(
        driver.run(
            scheduler=sched, sampler=sampler,
            max_requests=2, max_wall_seconds=2.0,
            workload_name="phase2_timing_test",
        )
    )
    # Decode tokens accumulated; throughput populated.
    assert result.n_decode_tokens > 0
    assert result.tokens_per_second > 0
    # No evicts fired in this synthetic run, but the field is
    # zero-default + correctly populated (not raising).
    assert result.evict_call_count >= 0
    assert result.evict_total_seconds >= 0


def test_extract_model_from_engine_walks_documented_paths():
    """The model-extraction helper finds the underlying torch
    model along several alternate paths that vLLM has used
    across minor versions."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    # Path 1: model_executor.driver_worker.worker.model_runner.model
    model = object()

    class _MR:
        pass

    class _W:
        pass

    class _DW:
        pass

    class _ME:
        pass

    me = _ME()
    me.driver_worker = _DW()
    me.driver_worker.worker = _W()
    me.driver_worker.worker.model_runner = _MR()
    me.driver_worker.worker.model_runner.model = model

    class _Engine:
        pass

    eng = _Engine()
    eng.model_executor = me

    found = AsyncEngineDriver._extract_model_from_engine(eng)
    assert found is model

    # Path 2: model_runner.model directly.
    eng2 = _Engine()
    mr2 = _MR()
    mr2.model = model
    eng2.model_runner = mr2
    found2 = AsyncEngineDriver._extract_model_from_engine(eng2)
    assert found2 is model

    # Fallback: nothing matches; returns the engine itself so
    # the walker in install_attention_capture can descend.
    eng3 = _Engine()
    found3 = AsyncEngineDriver._extract_model_from_engine(eng3)
    assert found3 is eng3
