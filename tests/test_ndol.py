"""Tests for the NDOL software memory controller.

Two kinds of assertions:
  * correctness — data round-trips byte-exactly through every path (no hardware);
  * architecture — the modeled speedups behave as the §2/§3 model predicts.
"""
from __future__ import annotations

import os

from ndol import (
    BenefitFunction,
    Compressor,
    NANDModel,
    NDOLController,
    Regime,
    RegimeDetector,
    StridePredictor,
    Tier,
)
from ndol.model import T_R_US


# ------------------------------ correctness -------------------------------- #
def test_write_read_roundtrip_is_byte_exact():
    c = NDOLController()
    payloads = {i: os.urandom(4096) for i in range(50)}
    for lba, data in payloads.items():
        c.write(lba, data)
    for lba, data in payloads.items():
        assert c.read(lba) == data


def test_vsp_buffer_never_returns_wrong_data():
    # EQSPEC invariant: a buffered page is served only on exact LBA match.
    c = NDOLController()
    for lba in range(100):
        c.write(lba, f"page-{lba}".encode().ljust(512, b"\0"))
    # Sequential access trains the predictor and fills the prefetch buffer.
    for lba in range(100):
        assert c.read(lba) == f"page-{lba}".encode().ljust(512, b"\0")
    assert c.metrics.vsp_hits > 0  # speculation actually fired


def test_compression_preserves_random_access():
    c = NDOLController()
    data = {lba: (b"A" * 2000 + os.urandom(48)) for lba in (5, 99, 7, 42)}
    for lba, d in data.items():
        c.write(lba, d)
    for lba in (42, 5, 99, 7):  # out of write order
        assert c.read(lba) == data[lba]


# ------------------------------ VSP ---------------------------------------- #
def test_stride_predictor_confidence_and_prediction():
    p = StridePredictor()
    for lba in range(0, 50, 5):  # stride 5
        p.observe(lba)
    # The first transition can't match the default stride, so confidence
    # approaches (not equals) 1 as the run lengthens: here 8/9 ≈ 0.89.
    assert p.confidence > 0.85
    assert p.predict(3) == [50, 55, 60]


def test_vsp_speedup_on_sequential_access():
    c = NDOLController()
    for lba in range(200):
        c.write(lba, os.urandom(8192))
    c.metrics.__init__()  # reset accounting after warm writes
    for lba in range(200):
        c.read(lba)
    r = c.report()
    assert r["vsp_hit_rate"] > 0.5
    assert r["speedup_vs_baseline"] > 1.5


def test_no_speculation_in_bandwidth_bound_regime():
    bf = BenefitFunction(NANDModel())
    # High confidence, but bus saturated → must not speculate.
    assert bf.should_speculate(Regime.BANDWIDTH_BOUND, 0.99, idle_dies=8) is False
    # Latency-bound, idle dies, high confidence → speculate.
    assert bf.should_speculate(Regime.LATENCY_BOUND, 0.99, idle_dies=8) is True
    # No idle dies → never speculate.
    assert bf.should_speculate(Regime.LATENCY_BOUND, 0.99, idle_dies=0) is False


# ------------------------------ MDPC --------------------------------------- #
def test_mdpc_page_dedup_serves_duplicates_once():
    c = NDOLController()
    for lba in range(10):
        c.write(lba, f"v{lba}".encode())
    out = c.read_many([3, 3, 3, 7, 7])  # 5 requests, 2 unique pages
    assert out == [b"v3", b"v3", b"v3", b"v7", b"v7"]
    assert c.metrics.dedup_saved == 3


def test_mdpc_interleave_hides_array_time():
    # Latency-bound batch: total ≈ one t_R + N transfers, not N full reads.
    c = NDOLController(n_dies=16)
    for lba in range(8):
        c.write(lba, os.urandom(16384))
    c.metrics.__init__()
    c.read_many(list(range(8)), queue_depth=8)
    r = c.report()
    assert r["speedup_vs_baseline"] > 2.0


# ------------------------------ LMTP --------------------------------------- #
def test_lmtp_places_hot_lbas_in_slc():
    c = NDOLController(slc_capacity=3)
    for lba in range(20):
        c.write(lba, b"x")
    # Make 0,1,2 hot.
    for _ in range(10):
        for lba in (0, 1, 2):
            c.read(lba)
    c.retrain_tiers()
    assert c.tier.tier(0) == Tier.SLC
    assert c.tier.tier(1) == Tier.SLC
    assert c.tier.tier(2) == Tier.SLC
    # A cold, rarely-touched LBA lands in the QLC tail.
    assert c.tier.tier(19) == Tier.QLC


# ------------------------------ INCS-CR ------------------------------------ #
def test_incs_pushdown_wins_for_cheap_ops_selective_filter():
    c = NDOLController()
    for lba in range(100):
        c.write(lba, (b"\x01" if lba % 50 == 0 else b"\x00") * 16384)
    matches = c.scan(list(range(100)), predicate=lambda p: p[:1] == b"\x01", ops_per_byte=0.5)
    assert len(matches) == 2          # selective filter → big A_BW
    assert c.last_scan_pushdown is True


def test_incs_pushdown_refused_for_expensive_ops():
    # Corrected §3.5: high ops/byte makes the fabric slower than shipping to host.
    c = NDOLController(fabric_gops=10.0, host_gops=50.0)
    for lba in range(100):
        c.write(lba, os.urandom(16384))
    c.scan(list(range(100)), predicate=lambda p: True, ops_per_byte=20.0)
    assert c.last_scan_pushdown is False


# ------------------------------ model -------------------------------------- #
def test_baseline_read_model_matches_doc_numbers():
    m = NANDModel(page_bytes=16384, bw_bus_gbps=2.0)
    assert abs(m.t_xfer_us() - 8.192) < 0.01          # 16KB / 2GB/s ≈ 8.2us
    assert abs(m.t_read_single(Tier.TLC) - 58.192) < 0.01  # 50 + 8.2 ≈ 58us


def test_regime_detector_saturation_point():
    rd = RegimeDetector(n_dies=16)
    assert rd.classify(1) is Regime.LATENCY_BOUND
    assert rd.classify(16) is Regime.BANDWIDTH_BOUND
    assert rd.idle_dies(4) == 12
