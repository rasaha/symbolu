"""
Phase 4 tests for real-runtime benchmark paths.

Scope:

- ``benchmarks.vllm_bridge``: VLLMBridgeUnavailable, ensure_vllm_available
  fail-clean behavior without vllm, derived-trace construction from
  synthetic (prompt_tokens, completion_tokens) tuples, DerivedRunResult
  summary shape.
- ``benchmarks.pcam_vllm_demo`` real path: --real-vllm fail-clean exit
  code and error message (without vllm), run_real_vllm_path routing
  through the bridge.
- ``benchmarks.pcam_trace_extract``: TraceExtractorUnavailable,
  ensure_transformers_available fail-clean without torch/transformers,
  _attention_to_block_mass / _events_from_block_attention pure-Python
  paths verified against a mock attention tensor.
- ``benchmarks.pcam_compare_baselines`` Phase 4 additions:
  InRepoBaselineAdapter wiring, _try_build_inrepo_adapters skip
  semantics, set_sequence hook, end-to-end compare with
  --include-inrepo-baselines on the demo trace.

All tests are deterministic, CPU-only, and do not require torch,
transformers, vllm, or any model weights.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.pcam_trace_replay import build_demo_trace
from benchmarks.pcam_compare_baselines import (
    InRepoBaselineAdapter,
    LRUBaseline,
    _try_build_inrepo_adapters,
    run as compare_run,
    run_baseline,
)
from benchmarks.pcam_trace_extract import (
    TraceExtractorUnavailable,
    _attention_to_block_mass,
    _events_from_block_attention,
    ensure_transformers_available,
    run as extract_run,
)
from benchmarks.pcam_vllm_demo import (
    RealVLLMNotAvailable,
    _attempt_real_vllm_path,
    run as demo_run,
)
from benchmarks.vllm_bridge import (
    DerivedRunResult,
    VLLMBridgeUnavailable,
    _derive_trace_from_vllm_run,
    ensure_vllm_available,
)
from simulator.pcam.trace import EventKind, TraceEvent


# ===========================================================================
# vllm_bridge — import path and fail-clean behavior
# ===========================================================================


class TestVLLMBridgeImportPath:
    def test_module_imports_without_vllm(self):
        """
        vllm_bridge must import cleanly even when ``vllm`` is not
        installed. The vllm import is lazy and happens only inside
        ``ensure_vllm_available`` and ``generate_with_derived_trace``.
        """
        import benchmarks.vllm_bridge as bridge
        assert bridge.VLLMBridgeUnavailable is VLLMBridgeUnavailable
        assert bridge.ensure_vllm_available is ensure_vllm_available

    def test_ensure_vllm_available_fails_clean(self):
        with pytest.raises(VLLMBridgeUnavailable) as excinfo:
            ensure_vllm_available()
        msg = str(excinfo.value)
        assert "vllm" in msg
        assert "pip install vllm" in msg

    def test_real_vllm_not_available_is_bridge_exception_alias(self):
        """Phase 3 test imports ``RealVLLMNotAvailable`` — it must
        still exist and must be the same class as
        ``VLLMBridgeUnavailable``."""
        assert RealVLLMNotAvailable is VLLMBridgeUnavailable


# ===========================================================================
# vllm_bridge — derived trace construction (pure Python, no vllm)
# ===========================================================================


class TestDerivedTraceConstruction:
    def test_single_sequence_derivation(self):
        """One prompt with prompt_tokens=32 and completion_tokens=48 at
        block_size=16 should produce 5 blocks and the matching lifecycle."""
        trace = _derive_trace_from_vllm_run(
            prompt_token_counts=[32],
            completion_token_counts=[48],
            block_size=16,
            sink_tokens=4,
        )
        kinds = [e.kind for e in trace]

        # Exactly one sequence
        assert kinds.count(EventKind.REGISTER_SEQUENCE) == 1
        assert kinds.count(EventKind.COMPLETE_SEQUENCE) == 1
        # Two phase-set events (PREFILL then DECODE)
        assert kinds.count(EventKind.SET_PHASE) == 2
        # 5 blocks = (32 + 48) / 16
        assert kinds.count(EventKind.ENSURE_BLOCK) == 5
        # Exactly one attention event per generated token
        assert kinds.count(EventKind.ON_BLOCK_ATTENTION) == 48

    def test_first_block_is_sink(self):
        trace = _derive_trace_from_vllm_run(
            prompt_token_counts=[16],
            completion_token_counts=[0],
            block_size=16,
            sink_tokens=4,
        )
        ensures = [e for e in trace if e.kind is EventKind.ENSURE_BLOCK]
        assert len(ensures) == 1
        # The first block's positions must include positions 0..3 so
        # PCAM's sink pinning fires during replay.
        first_positions = ensures[0].args["positions"]
        assert all(p < 4 for p in first_positions)

    def test_multi_sequence_block_ids_are_globally_unique(self):
        trace = _derive_trace_from_vllm_run(
            prompt_token_counts=[16, 16, 16],
            completion_token_counts=[8, 8, 8],
            block_size=16,
        )
        block_ids = [
            e.args["block_id"]
            for e in trace
            if e.kind is EventKind.ENSURE_BLOCK
        ]
        assert len(block_ids) == len(set(block_ids))

    def test_empty_sequence_is_skipped(self):
        """A sequence with zero total tokens must not emit a
        register_sequence."""
        trace = _derive_trace_from_vllm_run(
            prompt_token_counts=[0, 8],
            completion_token_counts=[0, 8],
            block_size=16,
        )
        register_events = [
            e for e in trace if e.kind is EventKind.REGISTER_SEQUENCE
        ]
        # Only sequence 2 (the non-empty one) should register.
        assert len(register_events) == 1
        assert register_events[0].args["seq_id"] == 2

    def test_derived_run_result_summary_shape(self):
        trace = _derive_trace_from_vllm_run(
            prompt_token_counts=[32, 16],
            completion_token_counts=[8, 4],
            block_size=16,
        )
        result = DerivedRunResult(
            trace=trace,
            prompts=["prompt A", "prompt B"],
            completions=["out A", "out B"],
            prompt_token_counts=[32, 16],
            completion_token_counts=[8, 4],
            model="fake-model",
            block_size=16,
        )
        summary = result.summary()
        assert summary["model"] == "fake-model"
        assert summary["num_prompts"] == 2
        assert summary["total_prompt_tokens"] == 48
        assert summary["total_completion_tokens"] == 12
        assert summary["derived_events"] == len(trace)


# ===========================================================================
# pcam_vllm_demo — real path wiring without vllm
# ===========================================================================


class TestPCAMVLLMDemoRealPath:
    def test_attempt_real_vllm_path_still_fails_clean(self):
        with pytest.raises(RealVLLMNotAvailable):
            _attempt_real_vllm_path()

    def test_run_with_real_vllm_returns_error_exit_code(self, capsys):
        rc = demo_run(["--real-vllm", "--quiet"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "ERROR:" in err
        assert "vllm" in err

    def test_run_synthetic_still_works(self, capsys):
        """Phase 3 default path must still produce its report."""
        rc = demo_run(["--quiet"])
        assert rc == 0
        assert capsys.readouterr().out == ""


# ===========================================================================
# pcam_trace_extract — fail-clean and pure-Python helpers
# ===========================================================================


class TestTraceExtractor:
    def test_ensure_transformers_fails_clean(self):
        with pytest.raises(TraceExtractorUnavailable) as excinfo:
            ensure_transformers_available()
        msg = str(excinfo.value)
        assert "torch" in msg or "transformers" in msg
        assert "pip install" in msg

    def test_extract_run_cli_fails_clean(self, tmp_path, capsys):
        out_path = tmp_path / "trace.json"
        rc = extract_run(
            ["--model", "gpt2", "--prompt", "hi", "--out", str(out_path)]
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "ERROR:" in err
        assert not out_path.exists()

    def test_attention_to_block_mass_simple(self):
        """
        A 1-batch, 1-head attention matrix over 4 positions with
        uniform attention should produce one block of mass 4.0 at
        block_size=16 (all positions fit in block 0).
        """
        matrix = [[[[1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0]]]]
        per_block = _attention_to_block_mass(matrix, block_size=16)
        assert per_block == {0: pytest.approx(4.0)}

    def test_attention_to_block_mass_two_blocks(self):
        """
        4 positions at block_size=2 should bucket into 2 blocks, each
        receiving mass proportional to its positions' received
        attention.
        """
        # Uniform attention: each query attends equally to every key.
        matrix = [[[[0.25, 0.25, 0.25, 0.25],
                    [0.25, 0.25, 0.25, 0.25],
                    [0.25, 0.25, 0.25, 0.25],
                    [0.25, 0.25, 0.25, 0.25]]]]
        per_block = _attention_to_block_mass(matrix, block_size=2)
        # Each of 4 keys gets 0.25 * 4 queries = 1.0 mass.
        # Block 0 (keys 0, 1) = 2.0; block 1 (keys 2, 3) = 2.0.
        assert per_block == {0: pytest.approx(2.0), 1: pytest.approx(2.0)}

    def test_events_from_block_attention_has_lifecycle(self):
        per_block = {0: 1.5, 1: 0.3, 2: 0.05}
        events = _events_from_block_attention(
            per_block, block_size=16, sink_tokens=4, seq_id=7
        )
        kinds = [e.kind for e in events]
        assert kinds[0] is EventKind.REGISTER_SEQUENCE
        assert events[0].args["seq_id"] == 7
        assert kinds[1] is EventKind.SET_PHASE
        assert kinds[-1] is EventKind.COMPLETE_SEQUENCE
        assert kinds.count(EventKind.ENSURE_BLOCK) == 3
        assert kinds.count(EventKind.ON_BLOCK_ATTENTION) == 3

    def test_events_from_block_attention_sink_positions(self):
        events = _events_from_block_attention(
            {0: 1.0, 1: 1.0}, block_size=16, sink_tokens=4
        )
        ensure_events = [
            e for e in events if e.kind is EventKind.ENSURE_BLOCK
        ]
        # Block 0 must carry sink-triggering positions.
        assert all(p < 4 for p in ensure_events[0].args["positions"])
        # Block 1 must carry a non-sink position.
        assert all(p >= 4 for p in ensure_events[1].args["positions"])


# ===========================================================================
# InRepoBaselineAdapter — wiring and correctness on the demo trace
# ===========================================================================


class TestInRepoBaselineAdapter:
    def test_build_adapters_succeeds_in_default_env(self):
        """
        The in-repo baselines live at simulator/pcam/baselines/ and
        do not require numpy / torch at import time. The factory must
        return three adapters and an empty skip list in this
        environment.
        """
        adapters, skipped = _try_build_inrepo_adapters(
            max_blocks=128, sink_tokens=4
        )
        names = [a.name for a in adapters]
        assert "SinkLRU (in-repo)" in names
        assert "H2O (in-repo)" in names
        assert "IndustryStyle (in-repo)" in names
        assert skipped == []

    def test_adapter_set_sequence_routes_updates(self):
        """
        The adapter's ``set_sequence`` hook is invoked on
        register_sequence events. Verify it updates the internal
        ``_last_seq_id`` used by record_access.
        """
        adapters, _ = _try_build_inrepo_adapters(
            max_blocks=64, sink_tokens=4
        )
        assert adapters, "in-repo baselines should import cleanly here"
        adapter = adapters[0]
        adapter.set_sequence(42)
        assert adapter._last_seq_id == 42

    def test_adapter_records_sink_evictions_correctly(self):
        """
        SinkLRU should NOT evict block 0 (the sink) when the demo
        trace admits it first with num_sinks=1. This mirrors PCAM's
        zero-sink-eviction guarantee on the sink-aware baselines.
        """
        events = build_demo_trace()
        adapters, _ = _try_build_inrepo_adapters(
            max_blocks=256, sink_tokens=4
        )
        sinklru = next(a for a in adapters if "SinkLRU" in a.name)
        row = run_baseline(events, sinklru)
        assert row["policy"] == "SinkLRU (in-repo)"
        assert row["sink_evictions"] == 0

    def test_compare_cli_with_inrepo_flag_includes_adapters(
        self, tmp_path, capsys
    ):
        out_path = tmp_path / "compare_phase4.json"
        rc = compare_run(
            [
                "--max-blocks", "128",
                "--include-inrepo-baselines",
                "--json", str(out_path),
                "--quiet",
            ]
        )
        assert rc == 0
        data = json.loads(out_path.read_text())
        policies = {row["policy"] for row in data["rows"]}
        # Phase 3 baseline set PLUS the Phase 4 in-repo additions.
        assert {"PCAM", "LRU", "LFU"}.issubset(policies)
        assert "SinkLRU (in-repo)" in policies
        assert "H2O (in-repo)" in policies

    def test_compare_cli_without_inrepo_flag_matches_phase3(
        self, tmp_path
    ):
        """
        The Phase 4 default must NOT include in-repo baselines —
        Phase 3 consumers must see an unchanged policy set.
        """
        out_path = tmp_path / "compare_phase3_compat.json"
        rc = compare_run(
            [
                "--max-blocks", "128",
                "--json", str(out_path),
                "--quiet",
            ]
        )
        assert rc == 0
        data = json.loads(out_path.read_text())
        policies = {row["policy"] for row in data["rows"]}
        assert policies == {"PCAM", "LRU", "LFU"}
