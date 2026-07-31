"""CPU unit tests for the video-DiT cache-compression feasibility harness.

Covers the eight areas required by the plan (§12.7): tensor-metadata validation, quant/dequant,
protected-channel encoding, net-byte accounting, reconstruction metrics, error-gate behavior, gate
freezing, and verdict generation. No GPU, no model — validates the analysis/verdict math itself.

These tests prove the LOGIC is correct; they do NOT produce any workload result. Every real feasibility
number is 'REQUIRES GPU' until Stage B runs (see the results template).
"""
from __future__ import annotations

import os
import sys
import tempfile

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dit_cache_lib as L
import verdict as V
import analyze_cache_compressibility as A

H_N, C = 256, 128
NPROT = max(1, int(0.04 * C))


def _concentrated(seed, outlier_channels, T=4, scale=25.0):
    g = torch.Generator().manual_seed(seed)
    x = torch.randn(T, H_N, C, generator=g)
    x[:, :, outlier_channels] *= scale
    return x


def _diffuse(seed, T=4):
    g = torch.Generator().manual_seed(seed)
    return torch.randn(T, H_N, C, generator=g)


# ---- 1. tensor metadata validation ---------------------------------------- #
def test_tensor_metadata_roundtrip_and_shape():
    x = _concentrated(1, list(range(NPROT)))
    meta = {"cache_object": "hidden_states", "layer": 3, "dtype": "bf16"}
    p = os.path.join(tempfile.mkdtemp(), "hidden_states_layer3.pt")
    torch.save({**meta, "tensor": x}, p)
    blob = torch.load(p, weights_only=False)
    assert blob["cache_object"] in L.CACHE_OBJECTS
    assert blob["tensor"].shape == (4, H_N, C)
    assert blob["layer"] == 3


def test_cache_object_vocabulary_is_closed():
    for obj in ("hidden_states", "attn_out", "cross_attn_out", "temporal_attn_out",
                "residual_block", "feature_delta", "predicted_residual"):
        assert obj in L.CACHE_OBJECTS


# ---- 2. quant / dequant --------------------------------------------------- #
def test_quant_dequant_shapes_and_monotonic_bits():
    x = _diffuse(2)
    for gran in ("per_tensor", "per_channel", "per_block"):
        x8 = L.quantize_uniform(x, 8, gran)
        x4 = L.quantize_uniform(x, 4, gran)
        assert x8.shape == x.shape and x4.shape == x.shape
        # more bits => lower (or equal) reconstruction error
        assert L.rel_l2(x, x8) <= L.rel_l2(x, x4) + 1e-6, (gran, L.rel_l2(x, x8), L.rel_l2(x, x4))


def test_quant_dequant_finer_granularity_not_worse():
    x = _concentrated(3, list(range(NPROT)))
    e_tensor = L.rel_l2(x, L.quantize_uniform(x, 4, "per_tensor"))
    e_block = L.rel_l2(x, L.quantize_uniform(x, 4, "per_block", block_size=32))
    assert e_block <= e_tensor + 1e-6, (e_block, e_tensor)


# ---- 3. protected-channel encoding ---------------------------------------- #
def test_protection_helps_on_concentrated():
    x = _concentrated(4, list(range(NPROT)))
    mask = L.top_channel_mask(x, 0.04)
    e_uniform = L.rel_l2(x, L.quantize_uniform(x, 4, "per_block", block_size=32))
    e_prot = L.rel_l2(x, L.protected_quantize(x, 4, mask, granularity="per_block", block_size=32))
    assert e_uniform / (e_prot + 1e-12) > 1.30, (e_uniform, e_prot)


def test_protection_negligible_on_diffuse():
    x = _diffuse(5)
    mask = L.top_channel_mask(x, 0.04)
    e_uniform = L.rel_l2(x, L.quantize_uniform(x, 4, "per_block", block_size=32))
    e_prot = L.rel_l2(x, L.protected_quantize(x, 4, mask, granularity="per_block", block_size=32))
    assert e_uniform / (e_prot + 1e-12) < 1.30, (e_uniform, e_prot)


def test_lowrank_residual_reduces_error():
    x = _concentrated(6, list(range(NPROT)))
    xq = L.quantize_uniform(x, 4, "per_block", block_size=32)
    xlr = L.lowrank_residual_reconstruct(x, xq, rank=8)
    assert L.rel_l2(x, xlr) <= L.rel_l2(x, xq) + 1e-6


# ---- 4. net-byte accounting ----------------------------------------------- #
def test_byte_accounting_density_and_overheads():
    x = _diffuse(7)
    ba = L.byte_account(x, 4, "per_block", protect_frac=0.04, block_size=32, baseline_bits=16)
    # int4 of bf16 with 4% bf16 protection + overheads => net density strictly between 1x and 4x
    assert 1.0 < ba["net_density_x"] < 4.0, ba
    # overheads are actually counted
    assert ba["scale_meta_bytes"] > 0 and ba["protect_index_bytes"] >= 0
    assert ba["compressed_bytes"] < ba["baseline_bytes"]


def test_byte_accounting_protection_costs_density():
    x = _diffuse(8)
    d0 = L.byte_account(x, 4, "per_block", protect_frac=0.0, block_size=32)["net_density_x"]
    d4 = L.byte_account(x, 4, "per_block", protect_frac=0.04, block_size=32)["net_density_x"]
    assert d4 < d0, (d4, d0)  # protecting channels at bf16 lowers net density


# ---- 5. reconstruction metrics -------------------------------------------- #
def test_reconstruction_metrics_identity_and_order():
    x = _diffuse(9)
    assert L.rel_l2(x, x) < 1e-9
    assert abs(L.cosine_sim(x, x) - 1.0) < 1e-5  # fp32 accumulation tolerance
    assert L.max_channel_rel_err(x, x) < 1e-6
    xq = L.quantize_uniform(x, 4, "per_block")
    assert L.rel_l2(x, xq) > 0 and L.cosine_sim(x, xq) < 1.0


def test_temporal_and_spatial_redundancy_signals():
    # temporally redundant: snapshots are near-copies
    base = _diffuse(10)
    x = base.clone()
    x[1] = base[0] + 0.01 * torch.randn_like(base[0])
    tr = L.temporal_redundancy(torch.stack([base[0], x[1]]))
    assert tr["consecutive_cosine_mean"] > 0.99
    sr = L.spatial_redundancy(base)
    assert 0.0 <= sr["lowrank_energy_frac_at_10pct"] <= 1.0


# ---- 6. error-gate behavior ----------------------------------------------- #
def test_gate_admits_good_rejects_bad():
    x = _concentrated(11, list(range(NPROT)))
    mask = L.top_channel_mask(x, 0.04)
    good = L.protected_quantize(x[0], 4, mask, granularity="per_block", block_size=32)
    bad = L.quantize_uniform(x[0], 4, "per_tensor")  # coarse -> worse
    tight = {"max_rel_l2": 0.01, "min_cosine": 0.9999}
    loose = {"max_rel_l2": 0.9, "min_cosine": 0.0}
    assert L.gate_admit(x[0], good, loose)["admit"] is True
    assert L.gate_admit(x[0], bad, tight)["admit"] is False
    # never silently admits a violator: action is a real fallback
    rej = L.gate_admit(x[0], bad, tight)
    assert rej["admit"] is False and "recompute" in rej["action"] or "full_precision" in rej["action"]


def test_error_accumulation_bounded_flag():
    x = _concentrated(12, list(range(NPROT)))
    mask = L.top_channel_mask(x, 0.04)
    enc = lambda t: L.protected_quantize(t, 4, mask, granularity="per_block", block_size=32)  # noqa: E731
    acc = L.error_accumulation(x, enc, reuse_len=6)
    assert len(acc["error_trajectory"]) == 6
    assert isinstance(acc["bounded"], bool)


# ---- 7. gate freezing ----------------------------------------------------- #
def test_gate_freeze_detects_tampering():
    frozen = V.freeze(V.FROZEN_GATES)
    # unchanged gates pass against their own freeze hash
    V.assert_gates_frozen(V.FROZEN_GATES, expected=frozen)
    # a post-hoc threshold change is caught
    tampered = dict(V.FROZEN_GATES)
    tampered["g2_min_net_density_x"] = 1.01
    try:
        V.assert_gates_frozen(tampered, expected=frozen)
        raise AssertionError("freeze guard failed to catch tampering")
    except AssertionError as e:
        assert "changed after freeze" in str(e)


def test_placeholder_freeze_blocks_until_calibrated():
    # default module-level FROZEN_SHA256 is a placeholder => must refuse until calibration freezes it
    try:
        V.assert_gates_frozen(V.FROZEN_GATES)  # expected defaults to placeholder
        raise AssertionError("should have refused an unfrozen (placeholder) gate set")
    except AssertionError as e:
        assert "not yet frozen" in str(e)


# ---- 8. verdict generation ------------------------------------------------ #
def test_verdict_representation_only_without_systems():
    ev = {"cache_bytes": 2e9, "net_density_x": 1.6, "cache_rel_l2": 0.02,
          "cache_cosine": 0.999, "uniform_vs_protected_err_ratio": 1.8}
    out = V.decide(ev)
    assert out["verdict"] == "CONTINUE — representation feasibility only", out["verdict"]
    assert out["systems_evaluated"] is False
    assert out["gates"]["g4_systems_value"] == "REQUIRES GPU"


def test_verdict_stop_not_compressible():
    ev = {"cache_bytes": 2e9, "net_density_x": 1.05, "cache_rel_l2": 0.02,
          "cache_cosine": 0.999, "uniform_vs_protected_err_ratio": 1.8}
    assert V.decide(ev)["verdict"] == "STOP — cache material but not compressible"


def test_verdict_stop_uniform_sufficient():
    ev = {"cache_bytes": 2e9, "net_density_x": 1.6, "cache_rel_l2": 0.02,
          "cache_cosine": 0.999, "uniform_vs_protected_err_ratio": 1.05}
    assert V.decide(ev)["verdict"] == "STOP — uniform compression already sufficient"


def test_verdict_stop_quality_fail():
    ev = {"cache_bytes": 2e9, "net_density_x": 1.6, "cache_rel_l2": 0.5,
          "cache_cosine": 0.5, "uniform_vs_protected_err_ratio": 1.8}
    assert V.decide(ev)["verdict"] == "STOP — protected compression fails quality"


def test_verdict_full_systems_paths():
    base = {"cache_bytes": 2e9, "net_density_x": 1.6, "cache_rel_l2": 0.02,
            "cache_cosine": 0.999, "uniform_vs_protected_err_ratio": 1.8,
            "cache_residency_frac_of_hbm": 0.3}
    # systems value but not strong-baseline
    ev1 = {**base, "systems_improvement_frac": 0.2, "latency_regression_frac": 0.05, "pareto_improvement_frac": 0.0}
    assert V.decide(ev1)["verdict"] == "CONTINUE — systems feasibility demonstrated"
    # differentiated (beats strong baseline)
    ev2 = {**base, "systems_improvement_frac": 0.2, "latency_regression_frac": 0.05, "pareto_improvement_frac": 0.2}
    assert V.decide(ev2)["verdict"] == "CONTINUE — differentiated result requiring prior-art and patent review"
    # overhead erases systems benefit
    ev3 = {**base, "systems_improvement_frac": 0.02, "latency_regression_frac": 0.3, "pareto_improvement_frac": 0.0}
    assert V.decide(ev3)["verdict"] == "STOP — compression overhead erases systems benefit"


# ---- integration: analyzer end-to-end on synthetic capture ---------------- #
def test_analyzer_end_to_end_on_synthetic_capture():
    d = tempfile.mkdtemp()
    x = _concentrated(20, list(range(NPROT)), T=6)
    meta = {"cache_object": "hidden_states", "layer": 0, "dtype": "bf16",
            "step_indices": [8, 16, 24, 32, 40, 48]}
    torch.save({**meta, "tensor": x}, os.path.join(d, "hidden_states_layer0.pt"))
    out = A.run(d, out_json=None, out_csv=None)
    assert out["dominant_cache_object_by_residency"] == "hidden_states"
    assert out["provisional_verdict"]["verdict"].startswith("CONTINUE") or \
           out["provisional_verdict"]["verdict"].startswith("STOP")
    # provisional verdict can never claim systems feasibility from CPU
    assert out["provisional_verdict"]["systems_evaluated"] is False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
