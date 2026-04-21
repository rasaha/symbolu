"""Tests for §3.3 trace generator: determinism + family shapes."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.characterization.traces import (
    TraceBundle,
    generate_trace,
)


ALL_FAMILIES = [
    ("baseline", {}),
    ("constant_bias", {"alpha_mag": 0.1}),
    ("linear_drift", {"drift_rate": 0.02}),
    ("accelerating", {"accel_mag": 0.2}),
    ("noise_floor", {"sigma_noise": 0.005}),
    ("outlier", {"accel_mag": 0.3}),
    ("eos_truncation", {"outer_family": "outlier", "accel_mag": 0.3, "k_eos": 2}),
]


@pytest.mark.parametrize("family,params", ALL_FAMILIES)
def test_generate_trace_shape(family, params):
    b = generate_trace(family=family, L=5, V=128, seed=0, **params)
    assert isinstance(b, TraceBundle)
    assert b.sources.shape == (3, 5, 128)
    assert np.isfinite(b.sources).all()


@pytest.mark.parametrize("family,params", ALL_FAMILIES)
def test_generate_trace_deterministic(family, params):
    b1 = generate_trace(family=family, L=5, V=128, seed=7, **params)
    b2 = generate_trace(family=family, L=5, V=128, seed=7, **params)
    np.testing.assert_array_equal(b1.sources, b2.sources)
    if b1.valid_masks is None:
        assert b2.valid_masks is None
    else:
        np.testing.assert_array_equal(b1.valid_masks, b2.valid_masks)


def test_baseline_all_sources_identical():
    b = generate_trace(family="baseline", L=5, V=64, seed=0)
    np.testing.assert_array_equal(b.sources[0], b.sources[1])
    np.testing.assert_array_equal(b.sources[0], b.sources[2])
    assert b.truth_label is None


def test_constant_bias_probability_space_exact():
    b = generate_trace(family="constant_bias", L=5, V=64, seed=0, alpha_mag=0.1)
    e_01 = b.sources[0] - b.sources[1]  # (L, V)
    # Should be constant in l within fp64 tolerance.
    diff = e_01 - e_01[0]
    assert float(np.max(np.abs(diff))) < 1e-12


def test_linear_drift_probability_space_exact():
    b = generate_trace(family="linear_drift", L=5, V=64, seed=0, drift_rate=0.02)
    e_01 = b.sources[1] - b.sources[0]  # (L, V), should be l * drift_direction
    # 2nd-difference in l must be zero (linear).
    a = e_01[2:] - 2.0 * e_01[1:-1] + e_01[:-2]
    assert float(np.max(np.abs(a))) < 1e-12


def test_outlier_truth_label_is_source_0():
    b = generate_trace(family="outlier", L=5, V=64, seed=0, accel_mag=0.3)
    assert b.truth_label == 0
    # Sources 1 and 2 should be identical (both = p_base).
    np.testing.assert_array_equal(b.sources[1], b.sources[2])


def test_accelerating_truth_label_is_source_1():
    b = generate_trace(family="accelerating", L=5, V=64, seed=0, accel_mag=0.2)
    assert b.truth_label == 1


def test_eos_truncation_valid_mask_matches_k_eos():
    b = generate_trace(
        family="eos_truncation", L=5, V=64, seed=0,
        outer_family="outlier", accel_mag=0.3, k_eos=1,
    )
    assert b.valid_masks is not None
    # Source 0 valid at l=0 and l=1, invalid from l=2 onward.
    assert b.valid_masks[0].tolist() == [True, True, False, False, False]
    # Sources 1 and 2 fully valid.
    assert b.valid_masks[1].all()
    assert b.valid_masks[2].all()
    # Truth label inherited from outer outlier family.
    assert b.truth_label == 0


def test_unknown_family_raises():
    with pytest.raises(ValueError):
        generate_trace(family="not_a_family", L=5, V=64, seed=0)
