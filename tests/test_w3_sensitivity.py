"""Tests for the W3 sensitivity model (ndol/sim/w3_sensitivity.py).

Locks the conservative, iso-reliability conclusions so they can't silently
regress into the optimistic regime.
"""
from __future__ import annotations

from ndol.sim.w3_sensitivity import (
    E_default,
    Layout,
    Phys,
    iso_reliability_baseline_cells,
    naive_int4prot_tlc_cells,
)


def _iso_marginal(lay: Layout) -> float:
    ph, E = Phys(), E_default()
    return iso_reliability_baseline_cells(lay, ph, E) / lay.cells_per_token(ph, E)


def test_iso_baseline_is_tighter_than_naive_tlc():
    ph, E = Phys(), E_default()
    lay = Layout()
    # iso-reliability (densest uniform-strong) consumes fewer cells than naive TLC,
    # i.e. it is the harder (fairer) baseline.
    assert iso_reliability_baseline_cells(lay, ph, E) < naive_int4prot_tlc_cells(lay, ph, E)


def test_best_honest_marginal_does_not_exceed_1_25():
    # Most-favorable honest config: tiny protected, all-QLC, bulk UBER relaxed to
    # the 1e-4 cap, compacted pages.
    best = _iso_marginal(Layout(p_protect=0.01, tier_prot="QLC", target_prot="1e-15",
                                tier_bulk="QLC", target_bulk="1e-4", compacted=True))
    assert best < 1.25
    assert best < 1.50


def test_compaction_required_to_beat_iso():
    # Mixed pages force bulk to the strong target → W3 loses vs iso; compaction wins.
    assert _iso_marginal(Layout(compacted=False)) < 1.0
    assert _iso_marginal(Layout(compacted=True)) > 1.0


def test_marginal_decreases_with_protected_fraction():
    assert _iso_marginal(Layout(p_protect=0.01)) > _iso_marginal(Layout(p_protect=0.08))
    assert _iso_marginal(Layout(p_protect=0.20)) < 1.0      # large protected fraction loses


def test_slc_protected_is_worst_tier():
    # SLC's low density makes it the worst place for protected (capacity-wise).
    m_slc = _iso_marginal(Layout(tier_prot="SLC"))
    m_qlc = _iso_marginal(Layout(tier_prot="QLC", target_prot="1e-15"))
    assert m_slc < m_qlc


def test_qlc_endurance_dead_for_hot_kv():
    ph = Phys()
    assert ph.tier_viable("QLC", dwpd=0.3)        # cold/reused KV: fine
    assert not ph.tier_viable("QLC", dwpd=1.0)    # hot KV: QLC dead at 3-yr life
    assert not ph.tier_viable("TLC", dwpd=3.0)
