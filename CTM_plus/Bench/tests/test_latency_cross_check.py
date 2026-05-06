"""Tests for the Mode B latency cross-check tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_summary(path: Path, cells: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"cells": cells, "pairs": []}))


def test_modeb_cell_per_token_wall_handles_zero_decode():
    """A cell with n_decode_tokens=0 (vLLM truncated the prompt
    so it generated nothing) must report per_token_wall_ms=None
    rather than divide by zero."""
    from ctm_bench.scripts.latency_cross_check import ModeBCell

    cell = ModeBCell(
        workload="rag_128k", policy="lru", seed=42,
        n_decode_tokens=0, wall_clock_seconds=6.21,
        counter_source="vllm_0_7_no_swaps_observed",
        slow_tier_bytes_per_decode_token=0.0,
        source_path="/tmp/x",
    )
    assert cell.per_token_wall_ms is None


def test_modeb_cell_per_token_wall_computes_correctly():
    from ctm_bench.scripts.latency_cross_check import ModeBCell

    cell = ModeBCell(
        workload="chat_32k", policy="lru", seed=42,
        n_decode_tokens=4096, wall_clock_seconds=19.24,
        counter_source="vllm_0_7_no_swaps_observed",
        slow_tier_bytes_per_decode_token=0.0,
        source_path="/tmp/y",
    )
    # 19.24s × 1000 / 4096 = 4.6973ms
    assert cell.per_token_wall_ms is not None
    assert abs(cell.per_token_wall_ms - 4.697) < 0.01


def test_load_mode_b_cells_walks_subdirs(tmp_path):
    """The loader must find vllm_summary.json files in nested
    subdirectories — that's how the per-seed cells are laid out."""
    from ctm_bench.scripts.latency_cross_check import load_mode_b_cells

    _write_summary(
        tmp_path / "chat_42" / "vllm_summary.json",
        [{
            "workload_name": "chat_32k", "policy_name": "lru", "seed": 42,
            "n_decode_tokens": 4096, "wall_clock_seconds": 19.24,
            "counter_source": "vllm_0_7_no_swaps_observed",
            "slow_tier_bytes_per_decode_token": 0,
        }],
    )
    _write_summary(
        tmp_path / "chat_137" / "vllm_summary.json",
        [{
            "workload_name": "chat_32k", "policy_name": "lru", "seed": 137,
            "n_decode_tokens": 4096, "wall_clock_seconds": 17.57,
            "counter_source": "vllm_0_7_no_swaps_observed",
            "slow_tier_bytes_per_decode_token": 0,
        }],
    )
    cells = load_mode_b_cells(tmp_path)
    assert len(cells) == 2
    seeds = sorted(c.seed for c in cells)
    assert seeds == [42, 137]


def test_load_mode_b_cells_tolerates_malformed_files(tmp_path):
    """Malformed JSON or schema-mismatched files must be skipped,
    not crash the run."""
    from ctm_bench.scripts.latency_cross_check import load_mode_b_cells

    # Valid file.
    _write_summary(
        tmp_path / "good" / "vllm_summary.json",
        [{
            "workload_name": "rag_128k", "policy_name": "lru", "seed": 42,
            "n_decode_tokens": 2048, "wall_clock_seconds": 22.11,
            "counter_source": "vllm_0_7_no_swaps_observed",
            "slow_tier_bytes_per_decode_token": 0,
        }],
    )
    # Malformed JSON.
    (tmp_path / "bad" / "vllm_summary.json").parent.mkdir()
    (tmp_path / "bad" / "vllm_summary.json").write_text("{not json")
    # Schema-mismatched (missing required fields).
    _write_summary(tmp_path / "schema_bad" / "vllm_summary.json",
                   [{"unrelated": "stuff"}])

    cells = load_mode_b_cells(tmp_path)
    # Only the good cell loads.
    assert len(cells) == 1
    assert cells[0].workload == "rag_128k"


def test_aggregate_mode_b_groups_by_workload(tmp_path):
    """Multiple seeds of the same workload should aggregate into
    one row with mean / min / max per_token_wall_ms."""
    from ctm_bench.scripts.latency_cross_check import (
        aggregate_mode_b_by_workload, load_mode_b_cells,
    )

    for seed, wall_s in [(42, 19.24), (137, 17.57), (271, 19.34)]:
        _write_summary(
            tmp_path / f"seed_{seed}" / "vllm_summary.json",
            [{
                "workload_name": "chat_32k", "policy_name": "lru", "seed": seed,
                "n_decode_tokens": 4096, "wall_clock_seconds": wall_s,
                "counter_source": "vllm_0_7_no_swaps_observed",
                "slow_tier_bytes_per_decode_token": 0,
            }],
        )
    cells = load_mode_b_cells(tmp_path)
    by_workload = aggregate_mode_b_by_workload(cells)
    assert "chat_32k" in by_workload
    cell = by_workload["chat_32k"]
    assert cell["n_seeds"] == 3
    assert sorted(cell["seeds"]) == [42, 137, 271]
    # Mean of (19.24, 17.57, 19.34) × 1000 / 4096 ≈ 4.572 ms
    assert abs(float(cell["per_token_wall_ms_mean"]) - 4.572) < 0.05


def test_aggregate_mode_b_skips_non_lru_policies(tmp_path):
    """The latency cross-check focuses on LRU baseline since
    that's all Mode B can produce on vLLM 0.7+. Non-LRU cells
    must be skipped from the aggregate."""
    from ctm_bench.scripts.latency_cross_check import (
        aggregate_mode_b_by_workload, load_mode_b_cells,
    )

    _write_summary(
        tmp_path / "lru" / "vllm_summary.json",
        [{
            "workload_name": "chat_32k", "policy_name": "lru", "seed": 42,
            "n_decode_tokens": 4096, "wall_clock_seconds": 19.24,
            "counter_source": "x", "slow_tier_bytes_per_decode_token": 0,
        }],
    )
    _write_summary(
        tmp_path / "ctm" / "vllm_summary.json",
        [{
            "workload_name": "chat_32k", "policy_name": "ctm_plus", "seed": 42,
            "n_decode_tokens": 4096, "wall_clock_seconds": 19.24,
            "counter_source": "x", "slow_tier_bytes_per_decode_token": 0,
        }],
    )
    cells = load_mode_b_cells(tmp_path)
    by_workload = aggregate_mode_b_by_workload(cells)
    assert by_workload["chat_32k"]["n_seeds"] == 1


def test_render_report_directional_match(tmp_path):
    """When Mode A predicts the same workload ordering as Mode B
    measures, the report must call out a successful directional
    match."""
    from ctm_bench.scripts.latency_cross_check import render_report

    mode_b_by_workload = {
        "chat_32k": {
            "n_seeds": 3,
            "n_decode_tokens_each": [4096, 4096, 4096],
            "wall_clock_seconds_each": [19.24, 17.57, 19.34],
            "per_token_wall_ms_mean": 4.57,
            "per_token_wall_ms_min": 4.29,
            "per_token_wall_ms_max": 4.72,
            "counter_sources": ["vllm_0_7_no_swaps_observed"],
            "seeds": [42, 137, 271],
        },
        "rag_128k": {
            "n_seeds": 3,
            "n_decode_tokens_each": [2048, 2048, 2048],
            "wall_clock_seconds_each": [22.11, 33.46, 24.03],
            "per_token_wall_ms_mean": 13.0,
            "per_token_wall_ms_min": 10.8,
            "per_token_wall_ms_max": 16.3,
            "counter_sources": ["vllm_0_7_no_swaps_observed"],
            "seeds": [42, 137, 271],
        },
    }
    mode_a_by_workload = {
        "chat_32k": {
            "n_seeds": 3,
            "avg_access_latency_ns_mean": 2077.0,
            "slow_tier_bytes_per_decode_token_mean": 16384.0,
        },
        "rag_128k": {
            "n_seeds": 3,
            "avg_access_latency_ns_mean": 3669.0,
            "slow_tier_bytes_per_decode_token_mean": 2048.0,
        },
    }
    report = render_report(mode_b_by_workload, mode_a_by_workload)
    assert "Rankings match" in report
    assert "chat_32k < rag_128k" in report


def test_render_report_directional_disagreement():
    """If Mode A and Mode B disagree on workload ordering, the
    report must flag it as a real finding to investigate."""
    from ctm_bench.scripts.latency_cross_check import render_report

    mode_b_by_workload = {
        # Mode B says chat is slower than rag.
        "chat_32k": {
            "n_seeds": 1, "n_decode_tokens_each": [4096],
            "wall_clock_seconds_each": [50.0],
            "per_token_wall_ms_mean": 12.2,
            "per_token_wall_ms_min": 12.2, "per_token_wall_ms_max": 12.2,
            "counter_sources": [], "seeds": [42],
        },
        "rag_128k": {
            "n_seeds": 1, "n_decode_tokens_each": [2048],
            "wall_clock_seconds_each": [10.0],
            "per_token_wall_ms_mean": 4.9,
            "per_token_wall_ms_min": 4.9, "per_token_wall_ms_max": 4.9,
            "counter_sources": [], "seeds": [42],
        },
    }
    mode_a_by_workload = {
        # Mode A says rag is slower than chat (opposite ordering).
        "chat_32k": {
            "n_seeds": 1, "avg_access_latency_ns_mean": 2000.0,
            "slow_tier_bytes_per_decode_token_mean": 0.0,
        },
        "rag_128k": {
            "n_seeds": 1, "avg_access_latency_ns_mean": 4000.0,
            "slow_tier_bytes_per_decode_token_mean": 0.0,
        },
    }
    report = render_report(mode_b_by_workload, mode_a_by_workload)
    assert "Rankings differ" in report


def test_render_report_handles_missing_mode_a():
    """When --mode-a-summary is omitted, the cross-check section
    must say so explicitly rather than silently rendering an
    empty table."""
    from ctm_bench.scripts.latency_cross_check import render_report

    report = render_report(
        {"chat_32k": {
            "n_seeds": 1, "n_decode_tokens_each": [4096],
            "wall_clock_seconds_each": [19.24],
            "per_token_wall_ms_mean": 4.7,
            "per_token_wall_ms_min": 4.7, "per_token_wall_ms_max": 4.7,
            "counter_sources": [], "seeds": [42],
        }},
        {},
    )
    assert "No Mode A predictions loaded" in report


def test_render_report_handles_no_mode_b():
    from ctm_bench.scripts.latency_cross_check import render_report

    report = render_report({}, {})
    assert "No Mode B cells found" in report


def test_main_cli_runs_end_to_end(tmp_path, capsys):
    """End-to-end CLI invocation: --mode-b-dir alone, no --mode-a,
    output to stdout."""
    from ctm_bench.scripts.latency_cross_check import main

    _write_summary(
        tmp_path / "cell_a" / "vllm_summary.json",
        [{
            "workload_name": "chat_32k", "policy_name": "lru", "seed": 42,
            "n_decode_tokens": 4096, "wall_clock_seconds": 19.24,
            "counter_source": "vllm_0_7_no_swaps_observed",
            "slow_tier_bytes_per_decode_token": 0,
        }],
    )
    rc = main(["--mode-b-dir", str(tmp_path)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Mode B Latency Cross-Check" in captured.out
    assert "chat_32k" in captured.out
