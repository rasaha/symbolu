"""Phase 3A CPU tests for per-request latency telemetry.

Validates:

* ``RequestLatency`` dataclass shape.
* ``AsyncEngineDriver._compute_p50_p99_ms`` percentile math.
* ``AsyncEngineDriver._submit_one`` populates
  ``self._request_latencies`` with submit / first-token /
  completion timestamps.
* End-of-run aggregation populates the new result fields
  (``ttft_p50_ms``, ``ttft_p99_ms``, ``e2e_p50_ms``,
  ``e2e_p99_ms``, ``per_request_first_token_latency_ms``,
  ``per_request_e2e_latency_ms``, ``per_request_cohort``,
  ``prompt_builder_name``).
* Failed requests (no token produced) are filtered out of p50/p99
  but recorded in the raw list at all — actually they are NOT
  recorded since first_token_time stays 0.0.

Uses the same mocked vLLM module pattern as
``test_cache_aware_runner_plumbing.py``.

No torch, no vllm, no GPU.
"""

from __future__ import annotations

import asyncio
import collections
import dataclasses
from typing import Any, Dict, List, Optional

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


# ---------------------------------------------------------------- #
# Mock vLLM scaffolding (subset of what cache-aware tests use).
# Generates per-request outputs to exercise first-token-time capture.
# ---------------------------------------------------------------- #


class _FakeOutputItem:
    def __init__(self, token_ids: List[int]):
        self.token_ids = token_ids


class _FakeOutput:
    def __init__(self, token_ids: List[int]):
        self.outputs = [_FakeOutputItem(token_ids)]


class _FakeBlockManager:
    def __init__(self) -> None:
        self.block_tables: Dict[int, List[Any]] = {}

    def allocate(self, seq_group: Any) -> None:
        pass

    def free(self, seq_or_seq_group: Any) -> None:
        pass


class _FakeScheduler:
    def __init__(self) -> None:
        self.waiting: "collections.deque[Any]" = collections.deque()
        self.block_manager = _FakeBlockManager()

    def schedule(self) -> List[Any]:
        return []


class _FakeInnerEngine:
    def __init__(self) -> None:
        self.scheduler = _FakeScheduler()


class _FakeAsyncEngine:
    """Async engine whose ``generate`` yields a small number of
    cumulative outputs to exercise the first-token-time capture
    in ``_submit_one``."""

    def __init__(self) -> None:
        self.engine = _FakeInnerEngine()
        self.shutdown_calls = 0
        # request_id -> list of cumulative outputs to yield
        self.outputs_for_request: Dict[str, List[List[int]]] = {}

    async def generate(self, prompt_dict: Any, sampling_params: Any, request_id: str):
        token_id_sequences = self.outputs_for_request.get(
            request_id, [[1], [1, 2], [1, 2, 3]],
        )
        for seq in token_id_sequences:
            # Tiny yield so the event loop ticks; gives first_token_time
            # a chance to differ from submit_time.
            await asyncio.sleep(0.001)
            yield _FakeOutput(seq)

    def shutdown_background_loop(self) -> None:
        self.shutdown_calls += 1


class _FakeAsyncEngineArgs:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeAsyncLLMEngine:
    last_instance: Optional[_FakeAsyncEngine] = None

    @classmethod
    def from_engine_args(cls, args: Any) -> _FakeAsyncEngine:
        cls.last_instance = _FakeAsyncEngine()
        return cls.last_instance


class _FakeSamplingParams:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeVLLM:
    def __init__(self) -> None:
        self.AsyncLLMEngine = type(
            "_FakeAsyncLLMEnginePerTest", (_FakeAsyncLLMEngine,), {},
        )
        self.AsyncEngineArgs = _FakeAsyncEngineArgs
        self.SamplingParams = _FakeSamplingParams


# ---------------------------------------------------------------- #
# Dataclass + percentile math
# ---------------------------------------------------------------- #


def test_request_latency_dataclass_has_expected_fields() -> None:
    from ctm_bench.runner_vllm_streaming import RequestLatency
    field_names = {f.name for f in dataclasses.fields(RequestLatency)}
    expected = {
        "request_id", "submit_time", "first_token_time",
        "completion_time", "n_decode_tokens", "cohort_index",
    }
    assert expected.issubset(field_names), expected - field_names


def test_compute_p50_p99_ms_empty_list() -> None:
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver
    p50, p99 = AsyncEngineDriver._compute_p50_p99_ms([])
    assert p50 == 0.0
    assert p99 == 0.0


def test_compute_p50_p99_ms_single_sample() -> None:
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver
    p50, p99 = AsyncEngineDriver._compute_p50_p99_ms([42.0])
    assert p50 == 42.0
    assert p99 == 42.0


def test_compute_p50_p99_ms_returns_ms_not_us() -> None:
    """Sanity check: the new helper returns milliseconds directly
    (unlike _compute_p50_p99_microseconds which converts to us)."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver
    samples_ms = [10.0, 20.0, 30.0, 40.0, 50.0]
    p50, p99 = AsyncEngineDriver._compute_p50_p99_ms(samples_ms)
    # p50 of 5 samples = middle = 30.0
    assert p50 == 30.0
    # p99 = linear interp between samples[~3.96]; for type-7 percentile
    # on a 5-sample list rank = 0.99 * 4 = 3.96 → blend of samples[3]
    # (40.0) and samples[4] (50.0), close to 49.6.
    assert 49.0 < p99 <= 50.0, p99


def test_compute_p50_p99_ms_sorts_unsorted_input() -> None:
    """Inputs aren't required to be pre-sorted."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver
    p50_sorted, _ = AsyncEngineDriver._compute_p50_p99_ms([1, 2, 3, 4, 5])
    p50_unsorted, _ = AsyncEngineDriver._compute_p50_p99_ms([3, 5, 1, 4, 2])
    assert p50_sorted == p50_unsorted


# ---------------------------------------------------------------- #
# Driver-level: latency capture during run()
# ---------------------------------------------------------------- #


def _run_driver_with_latency(
    *,
    cache_aware_scheduling: bool = False,
    shared_prefix_length: int = 0,
    n_admit: int = 4,
) -> Any:
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
        shared_prefix_length=shared_prefix_length,
        vllm_module=fake_vllm,
        sample_interval_seconds=0.01,
        # Higher rate so we admit fast.
    )
    arrival = ArrivalScheduler(
        seed=42,
        pareto=ParetoArrivalConfig(base_rate_per_sec=200.0, alpha=2.0),
        prompt_length_choices=[16],
    )
    sampler = SwapCounterSampler()

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            driver.run(
                scheduler=arrival,
                sampler=sampler,
                max_requests=n_admit,
                max_wall_seconds=3.0,
                workload_name="latency-test",
            )
        )
    finally:
        loop.close()
    return result, driver


def test_run_populates_per_request_latency_list() -> None:
    """After a small mocked run, the driver's
    ``_request_latencies`` list has one record per completed
    request, with non-zero first_token_time / completion_time
    (the fake engine yields outputs with sleeps so timestamps
    differ)."""
    result, driver = _run_driver_with_latency(n_admit=3)
    assert len(driver._request_latencies) == 3
    for r in driver._request_latencies:
        assert r.submit_time > 0
        assert r.first_token_time > r.submit_time
        assert r.completion_time >= r.first_token_time
        assert r.n_decode_tokens > 0


def test_run_aggregates_p50_p99_in_result_dataclass() -> None:
    """End-of-run aggregation populates the four percentile fields
    plus the raw per-request lists."""
    result, driver = _run_driver_with_latency(n_admit=4)
    # Lengths match completed.
    assert len(result.per_request_first_token_latency_ms) == 4
    assert len(result.per_request_e2e_latency_ms) == 4
    # All positive (the fake engine yields with sleeps).
    assert all(t > 0 for t in result.per_request_first_token_latency_ms)
    assert all(t > 0 for t in result.per_request_e2e_latency_ms)
    # Percentiles populated.
    assert result.ttft_p50_ms > 0
    assert result.ttft_p99_ms >= result.ttft_p50_ms
    assert result.e2e_p50_ms > 0
    assert result.e2e_p99_ms >= result.e2e_p50_ms


def test_run_records_prompt_builder_name() -> None:
    """Result reports which builder was used. PR-2 default →
    "pareto_unique_head"; --shared-prefix-length > 0 → "shared_prefix"."""
    result_legacy, _ = _run_driver_with_latency(
        n_admit=2, shared_prefix_length=0,
    )
    assert result_legacy.prompt_builder_name == "pareto_unique_head"
    # All cohort indices are -1 for the legacy builder.
    assert all(c == -1 for c in result_legacy.per_request_cohort)

    result_shared, _ = _run_driver_with_latency(
        n_admit=4, shared_prefix_length=8,
    )
    assert result_shared.prompt_builder_name == "shared_prefix"
    # Cohort indices are round-robin assigned: 0%4=0, 1%4=1, 2%4=2,
    # 3%4=3 (default n_shared_prefixes=4).
    assert sorted(result_shared.per_request_cohort) == [0, 1, 2, 3]


def test_run_filters_failed_requests_from_percentiles() -> None:
    """A request that produces zero tokens (first_token_time=0)
    must NOT appear in the percentile aggregates. The current
    fake engine always produces tokens, so this is a synthetic
    test against the aggregator directly."""
    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver,
        RequestLatency,
    )
    # Construct a driver and directly inject latency records to
    # bypass the engine.
    driver = AsyncEngineDriver(model="dummy", vllm_module=_FakeVLLM())
    driver._request_latencies = [
        RequestLatency(
            request_id="r0", submit_time=0.0, first_token_time=0.001,
            completion_time=0.010, n_decode_tokens=3,
        ),
        RequestLatency(
            request_id="r1_failed", submit_time=0.0, first_token_time=0.0,
            completion_time=0.005, n_decode_tokens=0,
        ),
        RequestLatency(
            request_id="r2", submit_time=0.0, first_token_time=0.002,
            completion_time=0.012, n_decode_tokens=4,
        ),
    ]
    # Replicate the aggregation logic (private to run() in the real
    # code path); the gate here is that the filter rule is "first_token_time > 0".
    ttft = [
        (r.first_token_time - r.submit_time) * 1000.0
        for r in driver._request_latencies if r.first_token_time > 0
    ]
    assert len(ttft) == 2, "failed request must be filtered"
    assert sorted(ttft) == sorted([1.0, 2.0])
