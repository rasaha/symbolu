"""Tests for production-shape workload replay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_presets_registered():
    """All three presets are exposed under names that match their
    preset.name field."""
    from ctm_bench.scripts.production_shape_replay import (
        PRESETS,
        CHAT_SHORT_LONG_MIX,
        RAG_BURSTY,
        AGENTIC_SUSTAINED_LONG,
    )

    assert "chat_short_long_mix" in PRESETS
    assert "rag_bursty" in PRESETS
    assert "agentic_sustained_long" in PRESETS
    assert PRESETS["chat_short_long_mix"] is CHAT_SHORT_LONG_MIX
    assert PRESETS["rag_bursty"] is RAG_BURSTY
    assert PRESETS["agentic_sustained_long"] is AGENTIC_SUSTAINED_LONG


def test_preset_length_distribution_weights_sum_to_one():
    """Weights in length_distribution must sum to 1.0 — otherwise
    the KVSimulator's _sample_context_length silently truncates the
    last weight, distorting the workload."""
    from ctm_bench.scripts.production_shape_replay import PRESETS

    for name, preset in PRESETS.items():
        total = sum(w for w, _, _ in preset.length_distribution)
        assert abs(total - 1.0) < 1e-6, (
            f"preset {name} length weights sum to {total}, not 1.0"
        )


def test_preset_carries_shape_caveat():
    """Every preset must declare an explicit shape_caveat — the
    string is rendered into the report so partners cannot mistake
    parametric models for real-dataset claims."""
    from ctm_bench.scripts.production_shape_replay import PRESETS

    for name, preset in PRESETS.items():
        assert preset.shape_caveat, (
            f"preset {name} missing shape_caveat"
        )
        assert len(preset.shape_caveat) > 30, (
            f"preset {name} shape_caveat looks like a placeholder"
        )


def test_build_arrival_schedule_uniform_is_deterministic():
    """With burstiness=None, schedule is uniform Bernoulli; same
    seed must produce the same schedule."""
    from ctm_bench.scripts.production_shape_replay import (
        build_arrival_schedule,
    )

    a = build_arrival_schedule(
        total_steps=200, base_rate=0.15,
        burstiness_alpha=None, seed=42,
    )
    b = build_arrival_schedule(
        total_steps=200, base_rate=0.15,
        burstiness_alpha=None, seed=42,
    )
    assert a == b
    # Different seeds produce different schedules.
    c = build_arrival_schedule(
        total_steps=200, base_rate=0.15,
        burstiness_alpha=None, seed=137,
    )
    assert a != c


def test_build_arrival_schedule_uniform_rate_matches_base():
    """Uniform Bernoulli schedule's mean arrival rate should be
    close to base_rate over many steps."""
    from ctm_bench.scripts.production_shape_replay import (
        build_arrival_schedule,
    )

    schedule = build_arrival_schedule(
        total_steps=10_000, base_rate=0.15,
        burstiness_alpha=None, seed=42,
    )
    realised_rate = sum(schedule) / len(schedule)
    assert abs(realised_rate - 0.15) < 0.02


def test_build_arrival_schedule_pareto_is_deterministic():
    """Pareto-bursty schedule must be deterministic per seed."""
    from ctm_bench.scripts.production_shape_replay import (
        build_arrival_schedule,
    )

    a = build_arrival_schedule(
        total_steps=200, base_rate=0.15,
        burstiness_alpha=1.5, seed=42,
    )
    b = build_arrival_schedule(
        total_steps=200, base_rate=0.15,
        burstiness_alpha=1.5, seed=42,
    )
    assert a == b


def test_build_arrival_schedule_pareto_is_burstier_than_uniform():
    """The Pareto-gap schedule must produce larger maximum gaps
    than uniform Bernoulli at the same base rate — that's the
    definition of burstiness."""
    from ctm_bench.scripts.production_shape_replay import (
        build_arrival_schedule,
    )

    uniform = build_arrival_schedule(
        total_steps=2000, base_rate=0.15,
        burstiness_alpha=None, seed=42,
    )
    bursty = build_arrival_schedule(
        total_steps=2000, base_rate=0.15,
        burstiness_alpha=1.2, seed=42,
    )

    def max_gap(s):
        idx = [i for i, v in enumerate(s) if v]
        return max(idx[i + 1] - idx[i] for i in range(len(idx) - 1))

    # Pareto with low alpha should produce a strictly larger max gap.
    assert max_gap(bursty) > max_gap(uniform)


def test_build_arrival_schedule_rejects_invalid_alpha():
    """alpha <= 0 is mathematically invalid for Pareto."""
    from ctm_bench.scripts.production_shape_replay import (
        build_arrival_schedule,
    )

    with pytest.raises(ValueError):
        build_arrival_schedule(
            total_steps=100, base_rate=0.1,
            burstiness_alpha=0.0, seed=42,
        )
    with pytest.raises(ValueError):
        build_arrival_schedule(
            total_steps=100, base_rate=0.1,
            burstiness_alpha=-1.0, seed=42,
        )


def test_render_report_leads_with_recompute_cost():
    """Report must lead with recompute_cost as the lead metric and
    label important_evictions with the §11 caveat."""
    from ctm_bench.scripts.production_shape_replay import render_report

    fake_results = [{
        "preset": "test_preset",
        "description": "Test preset for unit test.",
        "shape_caveat": "Parametric model, not a real-dataset claim.",
        "config": {
            "max_blocks": 128, "block_size": 16, "total_steps": 100,
            "arrival_rate": 0.15, "completion_rate": 0.05,
            "max_concurrent": 8,
            "length_distribution": [[1.0, 256, 1024]],
            "arrival_burstiness_alpha": None,
        },
        "seeds": [42],
        "n_arrivals_first_seed": 15,
        "arrival_gap_mean_first_seed": 6.5,
        "arrival_gap_max_first_seed": 12,
        "policies": {
            "lru": {
                "recompute_cost": 1000, "blocks_evicted": 100,
                "accuracy": 0.85, "important_evictions": 5,
            },
            "ctm_plus": {
                "recompute_cost": 980, "blocks_evicted": 95,
                "accuracy": 0.86, "important_evictions": 0,
            },
        },
    }]
    report = render_report(fake_results)
    # Lead-with-recompute_cost framing.
    assert "recompute_cost" in report
    assert "Lead metric: **recompute_cost**" in report
    # important_evictions must carry the policy-coupling caveat.
    assert "policy-coupled" in report
    assert "§11.2" in report
    # Honest scope statement at the end.
    assert "workload-shape" in report
    assert "real-attention" in report
    # The lead-finding callout should compute CTM+ vs LRU.
    assert "CTM+ vs LRU on recompute_cost" in report


def test_render_report_handles_empty():
    from ctm_bench.scripts.production_shape_replay import render_report

    report = render_report([])
    assert "No presets ran" in report


def test_render_report_flags_regression_when_ctm_worse():
    """When CTM+ is worse than LRU on recompute_cost, the report
    must say so — no papering over."""
    from ctm_bench.scripts.production_shape_replay import render_report

    fake = [{
        "preset": "regression_test",
        "description": "test", "shape_caveat": "test caveat that is long enough",
        "config": {
            "max_blocks": 64, "block_size": 16, "total_steps": 100,
            "arrival_rate": 0.2, "completion_rate": 0.05,
            "max_concurrent": 16,
            "length_distribution": [[1.0, 4096, 16384]],
            "arrival_burstiness_alpha": None,
        },
        "seeds": [42],
        "n_arrivals_first_seed": 10,
        "arrival_gap_mean_first_seed": 10.0,
        "arrival_gap_max_first_seed": 25,
        "policies": {
            "lru": {
                "recompute_cost": 1000, "blocks_evicted": 100,
                "accuracy": 0.62, "important_evictions": 10,
            },
            "ctm_plus": {
                "recompute_cost": 1220, "blocks_evicted": 130,
                "accuracy": 0.57, "important_evictions": 0,
            },
        },
    }]
    report = render_report(fake)
    assert "CTM+ worse" in report
    # Negative pp delta on accuracy.
    assert "-5." in report or "−5." in report or "-4.9" in report or "-5.0" in report


def test_main_cli_runs_one_preset_to_stdout(capsys, monkeypatch):
    """CLI smoke test — run one preset, no output dir, verify
    report goes to stdout. Uses a tiny preset to keep test time low."""
    from ctm_bench.scripts.production_shape_replay import (
        PRESETS, ReplayPreset, main,
    )

    # Replace one preset with a tiny one for the test.
    tiny = ReplayPreset(
        name="chat_short_long_mix",  # reuse the name so CLI accepts it
        description="tiny test preset",
        shape_caveat="parametric tiny preset for unit test only",
        max_blocks=32, block_size=16, total_steps=50,
        arrival_rate=0.2, completion_rate=0.1, max_concurrent=4,
        length_distribution=((1.0, 64, 256),),
    )
    monkeypatch.setitem(PRESETS, "chat_short_long_mix", tiny)

    rc = main(["--preset", "chat_short_long_mix", "--seeds", "42"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Production-Shape Workload Replay" in out
    assert "chat_short_long_mix" in out
    assert "recompute_cost" in out


def test_main_cli_writes_output_dir(tmp_path, monkeypatch):
    """CLI with --output-dir must produce results.json + report.md."""
    from ctm_bench.scripts.production_shape_replay import (
        PRESETS, ReplayPreset, main,
    )

    tiny = ReplayPreset(
        name="agentic_sustained_long",
        description="tiny test preset",
        shape_caveat="parametric tiny preset for unit test only",
        max_blocks=32, block_size=16, total_steps=50,
        arrival_rate=0.2, completion_rate=0.1, max_concurrent=4,
        length_distribution=((1.0, 64, 256),),
    )
    monkeypatch.setitem(PRESETS, "agentic_sustained_long", tiny)

    rc = main([
        "--preset", "agentic_sustained_long",
        "--seeds", "42",
        "--output-dir", str(tmp_path),
    ])
    assert rc == 0
    assert (tmp_path / "results.json").exists()
    assert (tmp_path / "report.md").exists()
    data = json.loads((tmp_path / "results.json").read_text())
    assert "runs" in data
    assert len(data["runs"]) == 1
    run = data["runs"][0]
    assert run["preset"] == "agentic_sustained_long"
    assert "policies" in run
    # Schema check: every policy aggregation must include recompute_cost.
    for policy_name, m in run["policies"].items():
        assert "recompute_cost" in m, (
            f"policy {policy_name} missing recompute_cost"
        )


def test_main_cli_rejects_empty_seeds(capsys):
    from ctm_bench.scripts.production_shape_replay import main

    rc = main(["--preset", "chat_short_long_mix", "--seeds", ",,"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "must list at least one seed" in err
