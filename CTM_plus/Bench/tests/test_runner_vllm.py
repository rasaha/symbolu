"""Tests for the Mode B (real-model via vLLM) runner.

These tests **must pass on a CPU-only host** — the lazy-import
contract means importing :mod:`runner_vllm` and constructing the
arg parser are cheap; only :func:`run_vllm` itself requires
vLLM + CUDA.

A test that actually exercises a real model belongs in a
GPU-only suite that this CPU CI does not run.
"""

from __future__ import annotations

import sys

import pytest


def test_runner_vllm_module_imports_on_cpu():
    """Importing runner_vllm must not pull in vLLM. If a future
    refactor moves an `import vllm` to module top, this test
    will surface it."""
    import ctm_bench.runner_vllm as mod
    # Sanity: the module exposes the expected public surface.
    assert hasattr(mod, "run_vllm")
    assert hasattr(mod, "workload_to_vllm_requests")
    assert hasattr(mod, "VLLMRequest")
    assert hasattr(mod, "main")


def test_runner_vllm_arg_parser_accepts_documented_workloads():
    """The CLI's --workload choices must match the four pinned
    workloads. If a workload is added or removed, this test
    will surface the drift."""
    from ctm_bench.runner_vllm import _build_parser

    parser = _build_parser()
    workload_action = next(
        a for a in parser._actions if a.dest == "workload"
    )
    assert set(workload_action.choices) == {
        "agentic_64k",
        "agentic_clustered_64k",
        "rag_128k",
        "chat_32k",
    }


def test_runner_vllm_arg_parser_rejects_fifo():
    """Mode B currently doesn't have a FIFO baseline (would
    require a separate vLLM block-manager patch). The CLI must
    reject it loud rather than silently fall back to LRU."""
    from ctm_bench.runner_vllm import _build_parser

    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--model", "x",
                "--workload", "rag_128k",
                "--policy", "fifo",
            ]
        )


def test_run_vllm_raises_clear_import_error_when_vllm_absent():
    """If vLLM is not installed, run_vllm should raise an
    ImportError with a message naming the missing package and
    pointing the user at `pip install vllm`."""
    from ctm_bench.runner_vllm import run_vllm
    from ctm_bench.workload import RAG_128K

    # Mock the vLLM import to fail unconditionally.
    import ctm_bench.runner_vllm as mod
    original = mod._import_vllm

    def fake_import_vllm():
        raise ImportError(
            "Mode B requires vLLM. Install with `pip install vllm`."
        )

    mod._import_vllm = fake_import_vllm  # type: ignore
    try:
        with pytest.raises(ImportError, match="vLLM"):
            run_vllm(RAG_128K, "lru", model="dummy")
    finally:
        mod._import_vllm = original  # type: ignore


def test_run_vllm_rejects_unsupported_policy():
    """FIFO is documented as not yet supported; the runner must
    raise NotImplementedError, not silently degrade."""
    from ctm_bench.runner_vllm import run_vllm
    from ctm_bench.workload import RAG_128K
    import ctm_bench.runner_vllm as mod

    # Bypass the vLLM check so we reach the policy-name check.
    original = mod._import_vllm
    mod._import_vllm = lambda: (object(), object())  # type: ignore
    try:
        with pytest.raises(NotImplementedError, match="FIFO"):
            run_vllm(RAG_128K, "fifo", model="dummy")
    finally:
        mod._import_vllm = original  # type: ignore


def test_extract_vllm_tier_counters_handles_missing_attributes():
    """The counter-extraction helper must return zero-filled
    counters when vLLM doesn't expose the expected attribute
    paths — never raise AttributeError."""
    from ctm_bench.runner_vllm import _extract_vllm_tier_counters

    class FakeEngine:
        pass

    counters = _extract_vllm_tier_counters(FakeEngine())
    assert "bytes_read" in counters
    assert counters["bytes_read"]["HBM"] == 0
    assert counters["bytes_read"]["DDR"] == 0
    assert counters["bytes_read"]["NVMe"] == 0
    # New: counter_source must be set so callers know what was
    # actually measured. "unavailable" is the no-engine default.
    assert counters["counter_source"] == "unavailable"


def test_extract_vllm_tier_counters_uses_block_allocator_swaps():
    """For vLLM 0.7+, the helper should call
    block_allocator.get_and_reset_swaps() and convert the swap
    count to bytes via the supplied block_size_bytes. We mock the
    full chain to verify the calculation."""
    from ctm_bench.runner_vllm import _extract_vllm_tier_counters

    class FakeBlockAllocator:
        def get_and_reset_swaps(self):
            return [(1, 100), (2, 101), (3, 102)]   # 3 swaps

    class FakeBlockManager:
        block_allocator = FakeBlockAllocator()

    class FakeScheduler:
        block_manager = FakeBlockManager()

    class FakeEngine:
        scheduler = FakeScheduler()

    counters = _extract_vllm_tier_counters(
        FakeEngine(), block_size_bytes=2_097_152   # 2 MiB
    )
    # 3 swaps × 2 MiB = 6 MiB = 6 * 1024 * 1024 = 6,291,456 bytes
    assert counters["bytes_read"]["DDR"] == 3 * 2_097_152
    assert counters["evictions_to_tier"]["DDR"] == 3
    assert counters["accesses_served"]["DDR"] == 3
    assert counters["counter_source"] == "vllm_0_7_block_allocator_swaps"


def test_extract_vllm_tier_counters_zero_swaps_marks_source():
    """If get_and_reset_swaps returns an empty iterable, the
    counter_source should reflect 'no swaps observed' rather
    than 'unavailable'."""
    from ctm_bench.runner_vllm import _extract_vllm_tier_counters

    class FakeBlockAllocator:
        def get_and_reset_swaps(self):
            return []

    class FakeBlockManager:
        block_allocator = FakeBlockAllocator()

    class FakeScheduler:
        block_manager = FakeBlockManager()

    class FakeEngine:
        scheduler = FakeScheduler()

    counters = _extract_vllm_tier_counters(
        FakeEngine(), block_size_bytes=2_097_152
    )
    assert counters["counter_source"] == "vllm_0_7_no_swaps_observed"
    assert counters["bytes_read"]["DDR"] == 0


def test_extract_vllm_tier_counters_legacy_v06_path():
    """For vLLM 0.6.x, gpu_allocator is present but no public
    swap counter exists. counter_source should reflect that."""
    from ctm_bench.runner_vllm import _extract_vllm_tier_counters

    class FakeGpuAllocator:
        pass

    class FakeBlockManager:
        gpu_allocator = FakeGpuAllocator()
        # No block_allocator (legacy path).

    class FakeScheduler:
        block_manager = FakeBlockManager()

    class FakeEngine:
        scheduler = FakeScheduler()

    counters = _extract_vllm_tier_counters(FakeEngine())
    assert counters["counter_source"] == "vllm_0_6_gpu_allocator_no_counter"


def test_runner_vllm_arg_parser_supports_dry_run():
    """--dry-run flag must be accepted by the CLI parser."""
    from ctm_bench.runner_vllm import _build_parser

    parser = _build_parser()
    args = parser.parse_args(
        [
            "--model", "x",
            "--workload", "rag_128k",
            "--policy", "lru",
            "--dry-run",
        ]
    )
    assert args.dry_run is True
