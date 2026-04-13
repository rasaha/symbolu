"""
Phase 3 tests for the benchmark / replay / demo scripts and the
shared reporting helper.

Scope is intentionally narrow:

- ``simulator.pcam._report`` primitives (format_table, section_header,
  emit_json)
- ``benchmarks.pcam_trace_replay`` — demo trace builder, replay flow,
  report rendering, JSON output, argparse
- ``benchmarks.pcam_compare_baselines`` — inline baselines (LRU/LFU),
  PCAM vs baseline shape, sink-eviction guarantee for PCAM
- ``benchmarks.pcam_vllm_demo`` — synthetic walkthrough end-to-end,
  --real-vllm error handling, argparse

These tests do NOT execute a real vLLM runtime, a real model, or
any external benchmark dataset. They are deterministic and CI-safe.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from simulator.pcam import PCAMConfig, TierHint
from simulator.pcam._report import emit_json, format_table, section_header

from benchmarks.pcam_trace_replay import (
    build_demo_trace,
    collect_metrics,
    render_report as render_replay_report,
    run as replay_run,
)
from benchmarks.pcam_compare_baselines import (
    LFUBaseline,
    LRUBaseline,
    run as compare_run,
    run_baseline,
    run_pcam,
)
from benchmarks.pcam_vllm_demo import (
    RealVLLMNotAvailable,
    _attempt_real_vllm_path,
    run as demo_run,
    run_synthetic_walkthrough,
)
from simulator.pcam.trace import EventKind, replay


# ===========================================================================
# _report primitives
# ===========================================================================


class TestReportHelpers:
    def test_section_header_wraps_title(self):
        header = section_header("hello")
        assert "hello" in header
        assert "=" in header

    def test_format_table_basic(self):
        out = format_table([(1, "a"), (22, "bb")], ["num", "label"])
        lines = out.splitlines()
        assert lines[0].startswith("num")
        assert "label" in lines[0]
        assert "--" in lines[1]
        assert "1" in lines[2]
        assert "22" in lines[3]

    def test_format_table_handles_short_rows(self):
        """A row with fewer cells than headers must not index-error."""
        out = format_table([(1,)], ["a", "b"])
        assert "1" in out

    def test_format_table_rejects_empty_headers(self):
        with pytest.raises(ValueError, match="headers"):
            format_table([], [])

    def test_emit_json_roundtrip(self, tmp_path: Path):
        path = tmp_path / "nested" / "out.json"
        data = {"evictions": 7, "mode": "demo", "tier": TierHint.HOT}
        emit_json(data, path)
        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["evictions"] == 7
        assert loaded["mode"] == "demo"
        # Enums fall back to str()
        assert "HOT" in loaded["tier"]


# ===========================================================================
# pcam_trace_replay
# ===========================================================================


class TestTraceReplayScript:
    def test_build_demo_trace_is_deterministic(self):
        a = build_demo_trace()
        b = build_demo_trace()
        assert len(a) == len(b)
        for ea, eb in zip(a, b):
            assert ea.kind is eb.kind
            assert ea.args == eb.args

    def test_demo_trace_has_every_event_kind_it_needs(self):
        events = build_demo_trace()
        kinds = {e.kind for e in events}
        required = {
            EventKind.REGISTER_SEQUENCE,
            EventKind.SET_PHASE,
            EventKind.ENSURE_BLOCK,
            EventKind.ON_BLOCK_ATTENTION,
            EventKind.SELECT_VICTIMS,
            EventKind.TIER_HINTS,
            EventKind.COMPLETE_SEQUENCE,
        }
        assert required.issubset(kinds)

    def test_collect_metrics_shape(self):
        events = build_demo_trace()
        cfg = PCAMConfig(max_blocks=256)
        policy = cfg.build_policy()
        result = replay(policy, events)
        metrics = collect_metrics(cfg, result)

        assert metrics["config.max_blocks"] == 256
        assert metrics["events_replayed"] == len(events)
        assert metrics["select_victims_calls"] >= 1
        assert metrics["tier_hint_calls"] >= 1
        assert "tier_distribution" in metrics
        assert set(metrics["tier_distribution"].keys()) == {
            "HOT", "WARM", "COLD", "EVICT",
        }
        # policy.* keys mirror get_stats() output
        assert "policy.evictions" in metrics
        assert "policy.step" in metrics

    def test_render_report_contains_sections(self):
        events = build_demo_trace()
        cfg = PCAMConfig(max_blocks=256)
        policy = cfg.build_policy()
        metrics = collect_metrics(cfg, replay(policy, events))
        report = render_replay_report(metrics)

        assert "PCAM Offline Trace Replay" in report
        assert "REPLAY-ONLY" in report
        assert "Config" in report
        assert "Replay summary" in report
        assert "Policy stats" in report
        assert "Tier-hint distribution" in report

    def test_run_with_quiet_and_json(self, tmp_path: Path, capsys):
        out_path = tmp_path / "replay.json"
        rc = replay_run(
            [
                "--max-blocks", "128",
                "--json", str(out_path),
                "--quiet",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert captured.out == ""  # --quiet suppresses report

        data = json.loads(out_path.read_text())
        assert data["config.max_blocks"] == 128
        assert data["events_replayed"] > 0


# ===========================================================================
# pcam_compare_baselines — inline baselines
# ===========================================================================


class TestLRUBaseline:
    def test_lru_evicts_oldest(self):
        baseline = LRUBaseline(sink_tokens=4)
        baseline.on_ensure(block_id=1, positions=[100])
        baseline.on_ensure(block_id=2, positions=[200])
        baseline.on_ensure(block_id=3, positions=[300])
        # Touch block 1 so it becomes the most recent
        baseline.on_attention(block_id=1, attention_sum=0.1)
        victims = baseline.on_select_victims(count=1)
        assert victims == [2]

    def test_lru_counts_sink_evictions(self):
        """LRU is sink-unaware — it may evict a sink block, and the
        comparison harness must count that."""
        baseline = LRUBaseline(sink_tokens=4)
        baseline.on_ensure(block_id=0, positions=[0, 1, 2, 3])  # sink
        baseline.on_ensure(block_id=1, positions=[100])
        baseline.on_ensure(block_id=2, positions=[200])
        baseline.on_attention(block_id=1, attention_sum=0.5)
        baseline.on_attention(block_id=2, attention_sum=0.5)
        # Now block 0 is the oldest — LRU should pick it.
        baseline.on_select_victims(count=1)
        assert baseline.metrics["sink_evictions"] == 1


class TestLFUBaseline:
    def test_lfu_evicts_least_used(self):
        baseline = LFUBaseline(sink_tokens=4)
        baseline.on_ensure(block_id=1, positions=[100])
        baseline.on_ensure(block_id=2, positions=[200])
        # Hit block 1 twice, block 2 zero times
        baseline.on_attention(block_id=1, attention_sum=0.5)
        baseline.on_attention(block_id=1, attention_sum=0.5)
        victims = baseline.on_select_victims(count=1)
        assert victims == [2]

    def test_lfu_records_attention_cost(self):
        baseline = LFUBaseline(sink_tokens=4)
        baseline.on_ensure(block_id=7, positions=[700])
        baseline.on_attention(block_id=7, attention_sum=0.42)
        baseline.on_select_victims(count=1)
        assert baseline.metrics["attention_weighted_cost"] == pytest.approx(0.42)


# ===========================================================================
# pcam_compare_baselines — PCAM vs baselines on the demo trace
# ===========================================================================


class TestCompareHarness:
    def _events(self):
        return build_demo_trace()

    def test_pcam_never_evicts_sinks(self):
        """
        By construction, PCAM's select_victims excludes pinned sinks.
        The demo trace admits one sink block; PCAM's sink_evictions
        count must be exactly 0.
        """
        cfg = PCAMConfig(max_blocks=256, sink_tokens=4)
        row = run_pcam(self._events(), cfg)
        assert row["sink_evictions"] == 0

    def test_baseline_rows_have_expected_shape(self):
        events = self._events()
        lru_row = run_baseline(events, LRUBaseline(sink_tokens=4))
        lfu_row = run_baseline(events, LFUBaseline(sink_tokens=4))
        for row in (lru_row, lfu_row):
            assert row["policy"] in ("LRU", "LFU")
            assert row["evictions"] >= 0
            assert row["sink_evictions"] >= 0
            assert row["attention_weighted_cost"] >= 0.0
            assert row["live_blocks"] >= 0
            assert row["live_sinks_remaining"] >= 0

    def test_compare_run_cli_quiet_with_json(self, tmp_path: Path, capsys):
        out_path = tmp_path / "compare.json"
        rc = compare_run(
            [
                "--max-blocks", "256",
                "--sink-tokens", "4",
                "--json", str(out_path),
                "--quiet",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert captured.out == ""

        data = json.loads(out_path.read_text())
        assert "rows" in data
        policies = {row["policy"] for row in data["rows"]}
        assert policies == {"PCAM", "LRU", "LFU"}

    def test_compare_run_default_renders_report(self, capsys):
        rc = compare_run(["--max-blocks", "128"])
        assert rc == 0
        report = capsys.readouterr().out
        assert "PCAM vs Baselines" in report
        assert "LRU" in report
        assert "LFU" in report
        assert "REPLAY-ONLY" in report


# ===========================================================================
# pcam_vllm_demo
# ===========================================================================


class TestVLLMDemo:
    def test_synthetic_walkthrough_runs_end_to_end(self):
        result = run_synthetic_walkthrough(max_blocks=128, sink_tokens=4)
        assert "transcript" in result
        assert "final_stats" in result
        assert "victim_ids" in result
        assert "tier_hints" in result

        stages = [entry["stage"] for entry in result["transcript"]]
        # Every pipeline stage is exercised at least once.
        assert "init" in stages
        assert "register_sequence" in stages
        assert "admit_sink_block" in stages
        assert "admit_filler_blocks" in stages
        assert "admit_entity_blocks" in stages
        assert "set_phase" in stages
        assert "select_victims" in stages
        assert "tier_hints" in stages
        assert "final_stats" in stages

    def test_synthetic_walkthrough_sink_hint_is_hot(self):
        """The sink block admitted by the demo must classify as HOT
        (sink clamp) regardless of attention."""
        result = run_synthetic_walkthrough()
        assert result["tier_hints"][0] == TierHint.HOT.value

    def test_real_vllm_flag_fails_clean_without_vllm(self):
        """
        When --real-vllm is passed and vllm is not installed, the
        attempt helper must raise ``RealVLLMNotAvailable`` with a
        clear install hint. The run() wrapper must return exit
        code 2 rather than producing bogus numbers.
        """
        with pytest.raises(RealVLLMNotAvailable):
            _attempt_real_vllm_path()

    def test_run_real_vllm_returns_error_exit_code(self, capsys):
        rc = demo_run(["--real-vllm", "--quiet"])
        assert rc == 2
        captured = capsys.readouterr()
        assert "ERROR:" in captured.err

    def test_run_synthetic_cli_quiet_with_json(self, tmp_path: Path, capsys):
        out_path = tmp_path / "demo.json"
        rc = demo_run(["--quiet", "--json", str(out_path)])
        assert rc == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        data = json.loads(out_path.read_text())
        assert "transcript" in data
        assert "final_stats" in data
