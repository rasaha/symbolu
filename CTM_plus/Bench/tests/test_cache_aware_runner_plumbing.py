"""CPU plumbing tests for v2 cache-reuse Phase 1 PR-2.

Validates the integration of ``install_cache_aware_scheduler`` into
``ctm_bench.runner_vllm_streaming.AsyncEngineDriver`` and the CLI
flag on ``ctm_bench.scripts.run_streaming``.

Acceptance gates exercised here (per the Phase 1 integration note
and the PR-2 approval):

* Default ``cache_aware_scheduling=False`` — flag-OFF path is the
  pre-PR-2 stock behaviour (no install branch entered, empty stats).
* ``cache_aware_scheduling=True`` invokes
  ``install_cache_aware_scheduler`` with the live scheduler +
  block_manager from the (mocked) vLLM engine.
* ``StreamingRunCellResult.cache_aware_scheduler_stats`` is the new
  populated telemetry field; empty dict when OFF, populated dict
  (with the expected keys) when ON.
* The install handle's ``teardown()`` is invoked at run-end, even
  on the zero-admission path (where ``finally`` is the only exit).
* The new CLI flag ``--cache-aware-scheduling`` is wired through
  ``argparse`` to the driver constructor argument.

No torch, no vllm, no GPU. The vLLM module is mocked via the
``AsyncEngineDriver(vllm_module=...)`` injection point that the
existing CPU tests use.
"""

from __future__ import annotations

import asyncio
import collections
import dataclasses
import subprocess
import sys
from typing import Any, Dict, List, Optional

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


# ---------------------------------------------------------------- #
# Mock vLLM module shape — enough for AsyncEngineDriver.run() to
# walk into the install path without a GPU.
# ---------------------------------------------------------------- #


class _FakeBlockManager:
    def __init__(self) -> None:
        self.block_tables: Dict[int, List[Any]] = {}
        self.allocate_calls: int = 0
        self.free_calls: int = 0

    def allocate(self, seq_group: Any) -> None:
        self.allocate_calls += 1

    def free(self, seq_or_seq_group: Any) -> None:
        self.free_calls += 1


class _FakeScheduler:
    def __init__(self) -> None:
        self.waiting: "collections.deque[Any]" = collections.deque()
        self.block_manager = _FakeBlockManager()
        self.schedule_calls: int = 0

    def schedule(self) -> List[Any]:
        self.schedule_calls += 1
        return []


class _FakeInnerEngine:
    def __init__(self) -> None:
        self.scheduler = _FakeScheduler()


class _FakeAsyncEngine:
    def __init__(self) -> None:
        self.engine = _FakeInnerEngine()
        self.shutdown_calls: int = 0

    async def generate(self, *args: Any, **kwargs: Any):  # pragma: no cover
        # Not reached when max_requests=0.
        if False:
            yield None

    def shutdown_background_loop(self) -> None:
        self.shutdown_calls += 1


class _FakeAsyncEngineArgs:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeAsyncLLMEngine:
    """Class with from_engine_args classmethod returning a fresh
    ``_FakeAsyncEngine`` per call."""

    last_args: Optional[_FakeAsyncEngineArgs] = None
    last_instance: Optional[_FakeAsyncEngine] = None

    @classmethod
    def from_engine_args(cls, args: _FakeAsyncEngineArgs) -> _FakeAsyncEngine:
        cls.last_args = args
        cls.last_instance = _FakeAsyncEngine()
        return cls.last_instance


class _FakeSamplingParams:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeVLLM:
    """Stand-in for the ``vllm`` module — exposes the three names
    that ``runner_vllm_streaming.run()`` reads off it."""

    def __init__(self) -> None:
        # Use a fresh _FakeAsyncLLMEngine subclass per instance so
        # classmethod state ``last_instance`` doesn't leak across tests.
        self.AsyncLLMEngine = type(
            "_FakeAsyncLLMEnginePerTest",
            (_FakeAsyncLLMEngine,),
            {},
        )
        self.AsyncEngineArgs = _FakeAsyncEngineArgs
        self.SamplingParams = _FakeSamplingParams


def _run_driver(
    *,
    cache_aware_scheduling: bool,
    max_starvation_seconds: float = 30.0,
) -> tuple[Any, _FakeVLLM, Any]:
    """Spin up an AsyncEngineDriver with a mocked vLLM, run it for
    zero requests, and return ``(result, fake_vllm, driver)``."""
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver,
        ArrivalScheduler,
        ParetoArrivalConfig,
        SwapCounterSampler,
    )

    fake_vllm = _FakeVLLM()
    driver = AsyncEngineDriver(
        model="dummy",
        cache_aware_scheduling=cache_aware_scheduling,
        cache_aware_max_starvation_seconds=max_starvation_seconds,
        vllm_module=fake_vllm,
        # Tiny sample interval so the sampler loop has a chance to
        # tick at least once during the brief wall budget. Not load-
        # bearing for the assertions; it just keeps the run faster.
        sample_interval_seconds=0.02,
    )
    arrival = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=10.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            driver.run(
                scheduler=arrival,
                sampler=sampler,
                max_requests=0,           # admit nothing
                max_wall_seconds=0.05,     # exit immediately
                workload_name="cpu-mock",
            )
        )
    finally:
        loop.close()
    return result, fake_vllm, driver


# ---------------------------------------------------------------- #
# Constructor parameter wiring
# ---------------------------------------------------------------- #


def test_async_engine_driver_default_cache_aware_off() -> None:
    """Default constructor leaves cache-aware scheduling OFF.

    Pre-PR-2 callers that don't pass the new arg must see the same
    behaviour as before (regression gate)."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    driver = AsyncEngineDriver(model="dummy")
    assert driver.cache_aware_scheduling is False
    assert driver.cache_aware_max_starvation_seconds == 30.0
    assert driver._cache_aware_install is None


def test_async_engine_driver_accepts_cache_aware_true() -> None:
    """Constructor accepts the new flag plus the starvation override."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    driver = AsyncEngineDriver(
        model="dummy",
        cache_aware_scheduling=True,
        cache_aware_max_starvation_seconds=15.0,
    )
    assert driver.cache_aware_scheduling is True
    assert driver.cache_aware_max_starvation_seconds == 15.0


def test_async_engine_driver_accepts_measurement_only() -> None:
    """Phase 3C: cache_aware_measurement_only flag is accepted +
    plumbs to the install."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    driver = AsyncEngineDriver(
        model="dummy",
        cache_aware_measurement_only=True,
    )
    assert driver.cache_aware_measurement_only is True
    assert driver.cache_aware_scheduling is False


def test_async_engine_driver_rejects_both_cache_aware_modes() -> None:
    """Mutually exclusive: cache_aware_scheduling and
    cache_aware_measurement_only cannot both be True."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    with pytest.raises(ValueError, match="mutually exclusive"):
        AsyncEngineDriver(
            model="dummy",
            cache_aware_scheduling=True,
            cache_aware_measurement_only=True,
        )


def test_run_measurement_only_installs_tree_without_reorder() -> None:
    """End-to-end mocked run: measurement_only=True installs the
    allocate / free wraps (tree-inserts > 0 once a request runs)
    but leaves the scheduler.schedule wrap untouched."""
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver,
        ArrivalScheduler,
        ParetoArrivalConfig,
        SwapCounterSampler,
    )

    fake_vllm = _FakeVLLM()
    driver = AsyncEngineDriver(
        model="dummy",
        cache_aware_measurement_only=True,
        vllm_module=fake_vllm,
        sample_interval_seconds=0.02,
    )
    arrival = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=10.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            driver.run(
                scheduler=arrival, sampler=sampler,
                max_requests=0, max_wall_seconds=0.05,
                workload_name="meas-only-test",
            )
        )
    finally:
        loop.close()

    # Stats dict reports the measurement-only mode.
    s = result.cache_aware_scheduler_stats
    assert s.get("enabled") is True
    assert s.get("measurement_only") is True
    assert s.get("reordered_count", 0) == 0   # no schedule wrap fired

    # The engine's scheduler.schedule was NOT wrapped — bound-method
    # identity recovers to the class method.
    engine = fake_vllm.AsyncLLMEngine.last_instance
    assert engine is not None
    sched = engine.engine.scheduler
    assert sched.schedule.__func__ is _FakeScheduler.schedule
    # But allocate/free WERE wrapped + later torn down. Post-teardown
    # they're back to the class methods.
    assert sched.block_manager.allocate.__func__ is _FakeBlockManager.allocate
    assert sched.block_manager.free.__func__ is _FakeBlockManager.free


# ---------------------------------------------------------------- #
# StreamingRunCellResult field
# ---------------------------------------------------------------- #


def test_streaming_run_cell_result_has_cache_aware_stats_field() -> None:
    """The result dataclass exposes the new ``cache_aware_scheduler_stats``
    field with the empty-dict default (parity with the other stats
    fields)."""
    from ctm_bench.runner_vllm_streaming import StreamingRunCellResult

    field_names = {f.name for f in dataclasses.fields(StreamingRunCellResult)}
    assert "cache_aware_scheduler_stats" in field_names

    # Default-constructed (with the minimum required args) leaves
    # the new field as an empty dict.
    result = StreamingRunCellResult(
        workload_name="t",
        policy_name="lru",
        seed=0,
        n_requests_admitted=0,
        n_requests_completed=0,
        n_decode_tokens=0,
        wall_clock_seconds=0.0,
        swap_in_blocks=0,
        swap_out_blocks=0,
        preemption_events=0,
    )
    assert result.cache_aware_scheduler_stats == {}


# ---------------------------------------------------------------- #
# run() path — flag OFF (regression gate)
# ---------------------------------------------------------------- #


def test_run_flag_off_does_not_install() -> None:
    """Flag-OFF path: cache_aware_scheduler_stats is empty, the
    install handle is None, and the engine's scheduler methods are
    untouched. This is the byte-identical-with-pre-PR-2 gate."""
    result, fake_vllm, driver = _run_driver(cache_aware_scheduling=False)

    assert result.cache_aware_scheduler_stats == {}
    assert driver._cache_aware_install is None
    engine = fake_vllm.AsyncLLMEngine.last_instance
    assert engine is not None
    sched = engine.engine.scheduler
    # The .schedule and block_manager.{allocate,free} bound methods
    # are bare class methods — no install wrap was applied.
    assert sched.schedule.__func__ is _FakeScheduler.schedule
    assert (
        sched.block_manager.allocate.__func__
        is _FakeBlockManager.allocate
    )
    assert (
        sched.block_manager.free.__func__
        is _FakeBlockManager.free
    )


# ---------------------------------------------------------------- #
# run() path — flag ON
# ---------------------------------------------------------------- #


def test_run_flag_on_installs_and_populates_stats() -> None:
    """Flag-ON path: install_cache_aware_scheduler wraps the
    scheduler + block_manager; stats are populated in the result
    dict with the expected keys; teardown reverts the wraps."""
    result, fake_vllm, driver = _run_driver(cache_aware_scheduling=True)

    # Stats dict populated with the canonical key set.
    s = result.cache_aware_scheduler_stats
    assert isinstance(s, dict)
    assert s.get("enabled") is True
    expected_keys = {
        "admissions",
        "reordered_count",
        "starvation_overrides",
        "predicted_hit_tokens_total",
        "realized_hit_tokens_total",
        "prediction_accuracy",
        "tree_inserts",
        "tree_evictions",
        "tree_tracked_tokens",
    }
    missing = expected_keys - set(s.keys())
    assert not missing, f"stats() missing keys: {missing}"

    # Teardown ran in the finally block — bound methods are back to
    # the originals.
    engine = fake_vllm.AsyncLLMEngine.last_instance
    assert engine is not None
    sched = engine.engine.scheduler
    assert sched.schedule.__func__ is _FakeScheduler.schedule
    assert (
        sched.block_manager.allocate.__func__
        is _FakeBlockManager.allocate
    )
    assert (
        sched.block_manager.free.__func__
        is _FakeBlockManager.free
    )

    # The install handle survives on the driver (stats already
    # snapshotted into the result before teardown; the handle's
    # teardown() is idempotent so repeated calls are safe).
    assert driver._cache_aware_install is not None
    assert driver._cache_aware_install.enabled is True


def test_run_flag_on_passes_max_starvation_seconds() -> None:
    """The override is plumbed into the install call (visible on the
    CacheAwareScheduler's max_starvation_seconds attribute)."""
    _, _, driver = _run_driver(
        cache_aware_scheduling=True, max_starvation_seconds=7.5,
    )
    install = driver._cache_aware_install
    assert install is not None
    assert install.cas is not None
    assert install.cas.max_starvation_seconds == 7.5


# ---------------------------------------------------------------- #
# Install-failure path — engine teardown still happens.
# ---------------------------------------------------------------- #


def test_run_flag_on_engine_teardown_on_install_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If install_cache_aware_scheduler raises, the engine's
    shutdown is invoked (same pattern as the ctm_plus / route-A
    install error paths)."""
    from ctm_bench import runner_vllm_streaming as rvs
    from kv_policy import cache_aware_install as cai

    # Force the install to raise so we can observe the cleanup path.
    def _raising_install(**kwargs: Any):
        raise RuntimeError("simulated install failure")

    monkeypatch.setattr(
        cai, "install_cache_aware_scheduler", _raising_install,
    )

    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver,
        ArrivalScheduler,
        ParetoArrivalConfig,
        SwapCounterSampler,
    )

    fake_vllm = _FakeVLLM()
    driver = AsyncEngineDriver(
        model="dummy",
        cache_aware_scheduling=True,
        vllm_module=fake_vllm,
        sample_interval_seconds=0.02,
    )
    arrival = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=10.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()

    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(RuntimeError, match="simulated install failure"):
            loop.run_until_complete(
                driver.run(
                    scheduler=arrival, sampler=sampler,
                    max_requests=0, max_wall_seconds=0.05,
                    workload_name="cpu-mock-fail",
                )
            )
    finally:
        loop.close()

    # Engine shutdown was invoked once during the cleanup path.
    engine = fake_vllm.AsyncLLMEngine.last_instance
    assert engine is not None
    assert engine.shutdown_calls == 1


# ---------------------------------------------------------------- #
# CLI flag wiring — invoke `--help` and verify the flag appears.
# ---------------------------------------------------------------- #


# ---------------------------------------------------------------- #
# Audit fix regression tests (Findings #2, #3, #5)
# ---------------------------------------------------------------- #


def test_resolve_block_size_from_engine_reads_cache_config() -> None:
    """Audit fix #3: helper reads vLLM's actual block_size from
    ``engine.engine.cache_config.block_size`` (the canonical vLLM
    0.7.3 V0 location) instead of hardcoding 32."""
    from ctm_bench.runner_vllm_streaming import _resolve_block_size_from_engine

    class _CacheCfg:
        block_size = 16

    class _Inner:
        cache_config = _CacheCfg()

    class _Engine:
        engine = _Inner()

    assert _resolve_block_size_from_engine(_Engine()) == 16


def test_resolve_block_size_falls_back_to_default() -> None:
    """Audit fix #3: when no recognized config path exists,
    return the documented default (32) rather than raising."""
    from ctm_bench.runner_vllm_streaming import _resolve_block_size_from_engine

    class _Bare:
        pass

    assert _resolve_block_size_from_engine(
        _Bare(), default=32,
    ) == 32
    # Different defaults pass through.
    assert _resolve_block_size_from_engine(
        _Bare(), default=64,
    ) == 64


def test_resolve_block_size_handles_engine_lacks_inner_engine() -> None:
    """Edge case: passed object IS the inner engine (no .engine
    attribute) — helper uses the object directly."""
    from ctm_bench.runner_vllm_streaming import _resolve_block_size_from_engine

    class _CacheCfg:
        block_size = 8

    class _DirectEngine:
        cache_config = _CacheCfg()

    assert _resolve_block_size_from_engine(_DirectEngine()) == 8


def test_resolve_block_size_handles_string_block_size_value() -> None:
    """Defensive: helper coerces to int; non-int-coercible value
    falls back to default."""
    from ctm_bench.runner_vllm_streaming import _resolve_block_size_from_engine

    class _CacheCfg:
        block_size = "not-an-int"

    class _Inner:
        cache_config = _CacheCfg()

    class _E:
        engine = _Inner()

    # Falls back to default since int() raises on "not-an-int".
    assert _resolve_block_size_from_engine(_E(), default=32) == 32


def test_probe_torn_down_when_cache_aware_install_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit fix #5: when the cache-aware install fails AFTER the
    prefix-hit probe is installed, the probe's monkey-patch on
    block_manager.allocate must be torn down by the finally block.

    Pre-fix: self._prefix_hit_probe was assigned AFTER both
    installs, so a cache-aware-install failure left
    self._prefix_hit_probe == None and the finally block skipped
    teardown. The probe wrap leaked onto the (now dead) engine."""
    from ctm_bench import runner_vllm_streaming as rvs
    from kv_policy import cache_aware_install as cai
    from kv_policy import prefix_hit_probe as php

    # Track whether probe.teardown was invoked.
    teardowns_called: List[str] = []

    real_install_probe = php.install_prefix_hit_probe

    def _wrapped_install_probe(**kwargs: Any):
        probe = real_install_probe(**kwargs)
        original_teardown = probe.teardown

        def _tracked():
            teardowns_called.append("probe")
            original_teardown()
        probe.teardown = _tracked
        return probe

    monkeypatch.setattr(
        php, "install_prefix_hit_probe", _wrapped_install_probe,
    )

    # Force the cache-aware install to raise after the probe is in.
    def _raising_cache_aware_install(**kwargs: Any):
        raise RuntimeError("simulated cache-aware install failure")

    monkeypatch.setattr(
        cai, "install_cache_aware_scheduler",
        _raising_cache_aware_install,
    )

    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver,
        ArrivalScheduler,
        ParetoArrivalConfig,
        SwapCounterSampler,
    )

    fake_vllm = _FakeVLLM()
    driver = AsyncEngineDriver(
        model="dummy",
        collect_native_prefix_hits=True,
        cache_aware_scheduling=True,
        vllm_module=fake_vllm,
        sample_interval_seconds=0.02,
    )
    arrival = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=10.0, alpha=2.0),
    )
    sampler = SwapCounterSampler()

    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(RuntimeError, match="simulated cache-aware"):
            loop.run_until_complete(
                driver.run(
                    scheduler=arrival, sampler=sampler,
                    max_requests=0, max_wall_seconds=0.05,
                    workload_name="probe-teardown-test",
                )
            )
    finally:
        loop.close()

    # Pre-fix: teardown was NOT called (probe leaked).
    # Post-fix: teardown IS called via the finally block.
    assert "probe" in teardowns_called, (
        f"probe.teardown was not invoked; "
        f"calls={teardowns_called}; "
        f"driver._prefix_hit_probe={driver._prefix_hit_probe}"
    )


def test_cancelled_request_still_records_latency() -> None:
    """Audit fix #2: when a request's coroutine is cancelled
    (e.g., via task.cancel() at wall-budget time), the latency
    record must still be appended via the new finally block.

    Pre-fix: except Exception did NOT catch CancelledError (which
    is BaseException-derived in Py 3.8+), so the latency-record
    append was skipped. The slowest requests (the ones reorder
    most-affects via push-back) were silently dropped from p99."""
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver, RequestLatency,
    )

    fake_vllm = _FakeVLLM()
    driver = AsyncEngineDriver(
        model="dummy",
        vllm_module=fake_vllm,
    )

    # Configure the mock engine's generate() to sleep forever so
    # we can cancel mid-flight.
    class _SlowEngine:
        async def generate(self, prompt_dict, sp, request_id):
            await asyncio.sleep(10)
            yield None  # never reached

    fake_engine = _SlowEngine()

    async def _drive():
        task = asyncio.create_task(
            driver._submit_one(
                fake_engine, "cancel_me", [1, 2, 3],
                sampling_params=None, request_id_counter=0,
            )
        )
        # Let the coroutine start.
        await asyncio.sleep(0.05)
        # Cancel mid-flight (mimics wall-budget cancellation).
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_drive())
    finally:
        loop.close()

    # Pre-fix: _request_latencies would be empty (CancelledError
    # bypassed the append). Post-fix: one record exists with
    # first_token_time=0 (never emitted a token) but a meaningful
    # completion_time (capturing the cancellation latency).
    assert len(driver._request_latencies) == 1, (
        f"cancelled request was not recorded; "
        f"records={driver._request_latencies}"
    )
    r = driver._request_latencies[0]
    assert r.request_id == "cancel_me"
    assert r.first_token_time == 0.0  # never emitted
    # Completion time captures the wall-clock at cancellation.
    assert r.completion_time > r.submit_time


def test_cli_help_lists_cache_aware_flag() -> None:
    """``python -m ctm_bench.scripts.run_streaming --help`` mentions
    the new ``--cache-aware-scheduling`` flag.

    This is the cheapest argparse-level smoke for the CLI plumbing:
    if the flag isn't in --help, it isn't in the parser, period.
    """
    result = subprocess.run(
        [sys.executable, "-m", "ctm_bench.scripts.run_streaming", "--help"],
        cwd="/home/user/symbolu/CTM_plus/Bench",
        capture_output=True,
        text=True,
        timeout=30,
    )
    # argparse exits 0 on --help.
    assert result.returncode == 0, (
        f"--help failed: stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    assert "--cache-aware-scheduling" in result.stdout
    assert "--cache-aware-max-starvation-seconds" in result.stdout
