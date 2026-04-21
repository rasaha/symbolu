"""Tests for §3.4 sweep harness — smoke, determinism, tiebreaker."""

from __future__ import annotations

from symbolu_bcvf_llm.characterization.sweep import (
    FAMILY_MAGNITUDES,
    V1_DEFAULTS,
    _eval_cell,
    pick_winner_tuple,
    run_ablation_grid,
    run_primary_grid,
)


def test_eval_cell_smoke_baseline():
    cell = _eval_cell(
        grid="t", family="baseline", family_params={},
        T=V1_DEFAULTS["T"], beta=V1_DEFAULTS["beta"], delta=V1_DEFAULTS["delta"],
        sigma_logit=3.0, V=64, seed=0,
    )
    assert cell.family == "baseline"
    assert cell.total_cost < 1e-3  # baseline should be near-zero


def test_eval_cell_determinism():
    kwargs = dict(
        grid="t", family="outlier", family_params={"accel_mag": 0.3},
        T=0.1, beta=200.0, delta=0.5, sigma_logit=3.0, V=64, seed=42,
    )
    c1 = _eval_cell(**kwargs)
    c2 = _eval_cell(**kwargs)
    assert c1.total_cost == c2.total_cost
    assert c1.per_source_costs == c2.per_source_costs


def test_primary_grid_runs_and_has_all_families():
    cells = run_primary_grid(V=64)
    families_seen = {c.family for c in cells}
    assert families_seen == set(FAMILY_MAGNITUDES.keys())


def test_ablation_grid_all_cost_orders_present():
    cells = run_ablation_grid(V=64)
    orders = {c.cost_order for c in cells}
    assert orders == {"ZEROTH", "FIRST", "SECOND"}


def test_pick_winner_returns_none_on_all_failures():
    # Fabricate empty sensitivity (every cell fails trivially by truncating)
    winner, cands = pick_winner_tuple([])
    assert winner is None
    assert cands == []
