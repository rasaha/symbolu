"""Tests for the §6.2 pilot runner."""

from __future__ import annotations

import csv
import json

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.datasets.base import (
    DatasetAdapter,
    SceneRecord,
)
from symbolu_robotics.bcvf_autonomous.datasets.synthetic_realistic import (
    RealisticNoiseAdapter,
    RealisticNoiseConfig,
)
from symbolu_robotics.bcvf_autonomous.pilot import (
    SceneEvaluatorConfig,
    evaluate_scene_a0,
    evaluate_scene_a3,
    one_sided_sign_test,
    run_pilot,
)


# --------------------------------------------------------------------------- #
# Sign test
# --------------------------------------------------------------------------- #


def test_sign_test_all_positive_is_significant():
    deltas = [0.1, 0.2, 0.3, 0.5, 0.4]   # 5/5 A3 wins
    r = one_sided_sign_test(deltas)
    assert r.n_a3_wins == 5
    assert r.n_a0_wins == 0
    assert r.win_rate == pytest.approx(1.0)
    assert r.p_value_one_sided == pytest.approx(0.5 ** 5, rel=1e-6)


def test_sign_test_all_ties_returns_neutral():
    r = one_sided_sign_test([0.0, 0.0, 0.0])
    assert r.n_a3_wins == 0
    assert r.n_a0_wins == 0
    assert r.n_ties == 3
    assert r.win_rate == 0.5
    assert r.p_value_one_sided == 1.0


def test_sign_test_balanced_is_not_significant():
    deltas = [+1, -1, +1, -1, +1, -1, +1, -1]
    r = one_sided_sign_test(deltas)
    assert r.n_a3_wins == 4
    assert r.n_a0_wins == 4
    # P(>=4 successes out of 8 fair coins) = 0.6367...
    assert r.p_value_one_sided > 0.5


def test_sign_test_wilson_ci_within_unit_interval():
    deltas = [+1.0] * 9 + [-1.0]
    r = one_sided_sign_test(deltas)
    assert 0.0 <= r.win_rate_ci_low <= r.win_rate_ci_high <= 1.0


def test_sign_test_single_decisive_win_returns_textbook_p():
    """Pinned regression for the k=1 off-by-one in ``_binomial_tail_geq``.

    With one win and zero losses (n_decisive = 1), the exact one-sided
    sign-test p-value is P(X >= 1 | X ~ Bin(1, 0.5)) = 0.5. The pre-fix
    primitive returned 0.0, which would have flagged a single-win
    sweep as significant at any alpha — exactly the silent failure
    mode this test pins against.
    """
    r = one_sided_sign_test([+1.0])
    assert r.n_a3_wins == 1
    assert r.n_a0_wins == 0
    assert r.win_rate == pytest.approx(1.0)
    assert r.p_value_one_sided == pytest.approx(0.5, abs=1e-12)


def test_sign_test_one_win_among_five_decisive_is_not_significant():
    """k=1, n=5: P(X >= 1 | Bin(5, 0.5)) = 31/32 ~ 0.969 — clearly
    non-significant. The pre-fix code returned 0.0 (false significant)."""
    r = one_sided_sign_test([+1.0, -1.0, -1.0, -1.0, -1.0])
    assert r.n_a3_wins == 1
    assert r.n_a0_wins == 4
    assert r.p_value_one_sided == pytest.approx(31.0 / 32.0, abs=1e-12)


# --------------------------------------------------------------------------- #
# Scene evaluator — A0 vs A3 numerical sanity
# --------------------------------------------------------------------------- #


def _trivial_scene(T: int = 30, H: int = 5, M: int = 4) -> SceneRecord:
    """All M predictors agree exactly on the ego trace; no failure."""
    ego = np.zeros((T, 3), dtype=np.float64)
    ego[:, 0] = np.arange(T) * 0.1 * 5.0
    predictors = {}
    for m in range(M):
        traj = np.zeros((T, H, 3), dtype=np.float64)
        for t in range(T):
            for h in range(H):
                traj[t, h, 0] = ego[t, 0] + (h + 1) * 0.1 * 5.0
        predictors[f"M{m + 1}"] = traj
    return SceneRecord(
        scene_id="trivial",
        ego_trace=ego,
        predictor_trajectories=predictors,
        failure_metadata={
            "type": "constant_bias_sanity",
            "onset_step": None,
            "duration_steps": 0,
            "ground_truth_failing_predictor": "M4",
        },
    )


def test_evaluate_scene_a0_runs_on_trivial_scene():
    scene = _trivial_scene()
    m = evaluate_scene_a0(scene)
    assert m.config_label == "A0"
    assert m.n_steps == 30
    assert m.M == 4
    assert m.mean_forecast_xy_error >= 0


def test_evaluate_scene_a3_runs_on_trivial_scene():
    scene = _trivial_scene()
    m = evaluate_scene_a3(scene)
    assert m.config_label == "A3"
    assert m.n_steps == 30
    assert m.M == 4
    assert m.episode_record is not None
    assert m.episode_record.n_steps == 30
    assert m.episode_record.M == 4


def test_evaluate_scene_a3_lemma1_invariance_on_constant_bias():
    """Adapter's constant_bias_sanity scene must produce zero BCVF.

    This is the §6.2 acceptance gate the pilot DESIGN.md calls a
    hard pass/fail."""
    adapter = RealisticNoiseAdapter()
    sid = next(
        sid for sid in adapter.scene_ids()
        if sid.endswith("constant_bias_sanity")
    )
    rec = adapter.load_scene(sid)
    m = evaluate_scene_a3(rec)
    assert m.max_bcvf_total <= 1e-3, (
        f"Lemma-1 invariance violated on constant_bias_sanity: "
        f"max BCVF = {m.max_bcvf_total}"
    )


def test_attribution_within_top_half_uses_ceil_convention_for_M3():
    """Pinned regression: ``attribution_within_top_half`` must use the
    ceil top-k convention (matching ``baselines/shootout._attribution_top_half``).

    With M=3 and the failing predictor ranked 2nd-out-of-3, the
    documented "top half" means top-2, so within_top_half must be 1.0.
    The pre-fix implementation used ``M // 2`` (floor), which collapsed
    to "rank 1 only" for odd M, giving 0.0 here and silently making
    the field a duplicate of ``hit_rate``.
    """
    from symbolu_robotics.bcvf_autonomous.pilot.scene_evaluator import (
        _attribution_metrics,
    )
    # One window step, M=3, costs ranked: predictor 2 → rank 1, predictor 0 → rank 2,
    # predictor 1 → rank 3. Failing predictor is 0 (rank 2).
    per_step_costs = np.array([[0.5, 0.1, 1.0]])   # (T=1, M=3)
    metrics = _attribution_metrics(
        per_step_costs,
        failing_predictor_idx=0,
        onset_step=0,
        duration_steps=1,
        M=3,
    )
    assert metrics["hit_rate"] == 0.0       # not rank 1
    assert metrics["within_top_half"] == 1.0  # rank 2 is within top-2-of-3


def test_evaluate_scene_a3_attribution_hits_failing_predictor_on_camera_degradation():
    """The within-horizon high-frequency jitter pattern produces 2nd-order
    disagreement BCVF can detect; A3 should rank M4 (the injected
    outlier) at the top of per-predictor cost during the failure window."""
    adapter = RealisticNoiseAdapter()
    sid = next(
        sid for sid in adapter.scene_ids()
        if sid.endswith("camera_degradation")
    )
    rec = adapter.load_scene(sid)
    m = evaluate_scene_a3(rec)
    assert m.attribution_hit_rate >= 0.5, (
        f"camera_degradation attribution hit rate {m.attribution_hit_rate} "
        "< 0.5 — BCVF failed to attribute the injected outlier majority of "
        "the time during the failure window."
    )


# --------------------------------------------------------------------------- #
# Top-level runner — end-to-end smoke + artifact contracts
# --------------------------------------------------------------------------- #


def test_run_pilot_end_to_end_on_realistic_adapter(tmp_path):
    """Full pilot run: 21 scenes, three artifacts, one PilotResult."""
    adapter = RealisticNoiseAdapter()
    result = run_pilot(
        adapter=adapter,
        output_dir=tmp_path,
        pilot_label="smoke",
    )
    # Artifacts on disk
    assert (tmp_path / "smoke_paired_comparison.csv").exists()
    assert (tmp_path / "smoke_fleet_summary.json").exists()
    assert (tmp_path / "smoke_pilot_report.md").exists()

    # PilotResult shapes
    assert result.n_scenes == 21
    assert result.n_predictors == 4
    assert len(result.scene_metrics_a0) == 21
    assert len(result.scene_metrics_a3) == 21
    # Lemma-1 negative control passes on the realistic adapter.
    assert result.lemma1_negative_control_pass


def test_run_pilot_csv_has_one_row_per_scene(tmp_path):
    adapter = RealisticNoiseAdapter()
    run_pilot(adapter, tmp_path, pilot_label="csvtest")
    csv_path = tmp_path / "csvtest_paired_comparison.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 21
    expected_keys = {
        "scene_id", "failure_type", "err_A0", "err_A3", "delta",
        "attribution_hit_rate", "mean_bcvf_total",
    }
    assert expected_keys.issubset(rows[0].keys())


def test_run_pilot_fleet_summary_json_round_trips(tmp_path):
    adapter = RealisticNoiseAdapter()
    run_pilot(adapter, tmp_path, pilot_label="fleet")
    payload = json.loads(
        (tmp_path / "fleet_fleet_summary.json").read_text()
    )
    assert payload["n_episodes"] == 21
    assert "argmax_flips_per_step" in payload
    assert "near_vetoes" in payload


def test_run_pilot_report_markdown_has_required_sections(tmp_path):
    adapter = RealisticNoiseAdapter()
    run_pilot(adapter, tmp_path, pilot_label="md")
    md = (tmp_path / "md_pilot_report.md").read_text()
    for section in (
        "Headline result",
        "Per-failure-class breakdown",
        "Lemma-1 negative control",
        "Fleet summary highlights",
        "Scope caveats",
    ):
        assert section in md, f"missing section: {section}"


def test_run_pilot_responsive_class_wins_overall(tmp_path):
    """On the RealisticNoiseAdapter, the responsive class is
    `camera_degradation` — within-horizon high-frequency jitter that
    BCVF's second-order kernel detects. The overall sign-test should
    show A3 wins 5/5 on that class."""
    result = run_pilot(
        RealisticNoiseAdapter(),
        tmp_path,
        pilot_label="responsive",
    )
    cd = result.per_failure_class.get("camera_degradation")
    assert cd is not None
    assert cd.n_a3_wins == 5
    assert cd.n_a0_wins == 0


def test_run_pilot_smaller_N_via_config(tmp_path):
    """Pilot must scale down with adapter config for fast smoke
    iteration (the production execution at N=21 takes ~1 s; this
    keeps the test path under 300 ms)."""
    adapter = RealisticNoiseAdapter(
        config=RealisticNoiseConfig(num_scenes=4, steps_per_scene=80),
    )
    result = run_pilot(adapter, tmp_path, pilot_label="small")
    assert result.n_scenes == 4


# --------------------------------------------------------------------------- #
# NuScenesAdapter stub — import safety + clear remediation message
# --------------------------------------------------------------------------- #


def test_nuscenes_adapter_module_imports_cleanly():
    """The stub must import without raising even when nuscenes-devkit
    is not installed — the failure surfaces only at construction time."""
    from symbolu_robotics.bcvf_autonomous.datasets import nuscenes  # noqa: F401


def test_nuscenes_adapter_construction_raises_clear_error():
    from symbolu_robotics.bcvf_autonomous.datasets.nuscenes import (
        NuScenesAdapter,
    )
    # nuscenes-devkit is not installed in this sandbox; constructor
    # must raise ImportError with a remediation message.
    with pytest.raises((ImportError, NotImplementedError)) as exc_info:
        NuScenesAdapter(dataroot="/nonexistent")
    msg = str(exc_info.value).lower()
    assert "nuscenes" in msg or "devkit" in msg or "scaffolding" in msg
