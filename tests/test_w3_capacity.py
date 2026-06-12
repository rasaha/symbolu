"""Tests for the W3 capacity + endurance model (ndol/sim/w3_capacity.py)."""
from __future__ import annotations

from ndol.sim.w3_capacity import (
    Params,
    ecc_code_rate,
    h2,
    lifetime_years,
    sustainable_dwpd,
    tokens_per_gb,
)


def test_binary_entropy_endpoints():
    assert h2(0.0) == 0.0
    assert h2(1.0) == 0.0
    assert abs(h2(0.5) - 1.0) < 1e-12


def test_ecc_rate_decreases_with_rber():
    eta = 0.9
    rates = [ecc_code_rate(r, eta) for r in (1e-6, 5e-3, 2e-2, 5e-2, 1e-1)]
    assert rates == sorted(rates, reverse=True)      # strictly worse as RBER rises
    assert abs(rates[0] - eta) < 1e-3                # at ~0 RBER, rate ≈ η


def test_net_density_anchor_holds():
    # int4_protected on the SAME tier must reproduce the measured 1.80× vs bf16.
    p = Params()
    t = tokens_per_gb(p)
    assert abs(t["int4_protected / TLC"] / t["bf16 / TLC"] - p.int4prot_net_density) < 1e-6


def test_qlc_density_advantage_is_haircut_by_ecc():
    # After ECC, QLC/TLC usable bits/cell is well below the naive 4/3.
    p = Params()
    ratio = p.usable_bits_per_cell("QLC") / p.usable_bits_per_cell("TLC")
    assert 1.10 < ratio < 1.27          # ~1.20, not 1.333
    assert ratio < 4.0 / 3.0


def test_w3_is_below_all_qlc_capacity():
    # Tiering protected onto the safer tier costs capacity vs all-QLC: W3 is NOT
    # a capacity maximizer (its value is reliability, not extra density).
    t = tokens_per_gb(Params())
    assert t["int4_protected / TLC"] < t["W3 (protected→TLC, bulk→QLC)"] < t["int4_protected / all-QLC"]


def test_w3_capacity_collapses_at_high_qlc_rber():
    base = Params()
    t_lo = tokens_per_gb(base)
    p_hi = Params(rber={**base.rber, "QLC": 5e-2})
    t_hi = tokens_per_gb(p_hi)
    lo_marginal = t_lo["W3 (protected→TLC, bulk→QLC)"] / t_lo["int4_protected / TLC"]
    hi_marginal = t_hi["W3 (protected→TLC, bulk→QLC)"] / t_hi["int4_protected / TLC"]
    assert lo_marginal > 1.1            # benefit exists at low RBER
    assert hi_marginal <= 1.01          # collapses to ~no-benefit at EOL QLC RBER


def test_conservative_overall_gain_below_optimistic_222():
    # The hardened number must be below the earlier optimistic 2.22×.
    t = tokens_per_gb(Params())
    overall = t["W3 (protected→TLC, bulk→QLC)"] / t["bf16 / TLC"]
    assert 1.9 < overall < 2.22


def test_endurance_ordering_and_qlc_is_tight():
    p = Params()
    assert sustainable_dwpd(p, "QLC") < sustainable_dwpd(p, "TLC") < sustainable_dwpd(p, "SLC")
    assert sustainable_dwpd(p, "QLC") < 1.0                 # QLC sustains <1 DWPD for 3-yr life
    assert lifetime_years(p, "QLC", 10.0) < 0.5             # ~3 months at 10 DWPD
