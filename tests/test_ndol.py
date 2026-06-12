"""Tests for the NDOL software memory controller.

Two kinds of assertions:
  * correctness — data round-trips byte-exactly through every path (no hardware);
  * architecture — the modeled speedups behave as the §2/§3 model predicts.
"""
from __future__ import annotations

import math
import os

from ndol import (
    BenefitFunction,
    Compressor,
    FileStore,
    KVAwareController,
    NANDModel,
    NDOLController,
    PhaseScheduler,
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


# ------------------------------ USE scheduler ------------------------------ #
def test_scheduler_converges_to_collision_free_splay_homogeneous():
    # Equal windows → splay state tiles the bus with zero contention.
    s = PhaseScheduler()
    res = s.schedule(t_r=[50.0] * 8, t_xfer=[5.0] * 8)
    assert res.converged
    assert res.contention_us < 1e-6
    # Splay state's mean pairwise coherence is -1/(N-1) ≈ -0.14, well below the
    # fully-aligned value of +1 — i.e. maximally spread.
    assert res.coherence < 0.0


def test_scheduler_weighted_splay_beats_equal_spacing_when_heterogeneous():
    # Mixed-tier dies: unequal transfer windows. The weighted repulsive update
    # must not be worse than naive equal spacing (2πi/N).
    s = PhaseScheduler()
    t_r = [25.0, 50.0, 100.0, 50.0]
    t_xfer = [16.0, 8.0, 2.0, 8.0]
    res = s.schedule(t_r, t_xfer)
    t_cycle = max(tr + tx for tr, tx in zip(t_r, t_xfer))
    widths = [tx / t_cycle for tx in t_xfer]
    equal = [2 * math.pi * i / 4 for i in range(4)]
    c_equal = s.contention(equal, widths, t_cycle)
    assert res.converged
    assert res.contention_us <= c_equal + 1e-9


def test_scheduler_can_be_disabled():
    c = NDOLController(use_scheduler=False)
    for lba in range(8):
        c.write(lba, os.urandom(16384))
    c.metrics.__init__()
    c.read_many(list(range(8)), queue_depth=8)
    assert c.last_schedule is None


# ------------------------------ FileStore ---------------------------------- #
def test_filestore_roundtrip_and_persistence(tmp_path):
    path = str(tmp_path / "ndol.dat")
    c = NDOLController(store=FileStore(path))
    payloads = {i: os.urandom(4096) for i in range(30)}
    for lba, data in payloads.items():
        c.write(lba, data)
    for lba, data in payloads.items():
        assert c.read(lba) == data
    c.store.close()

    # Reopen: the FTL index sidecar survives, data still byte-exact.
    c2 = NDOLController(store=FileStore(path))
    for lba, data in payloads.items():
        assert c2.read(lba) == data
    c2.store.close()


def test_filestore_overwrite_returns_latest():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        store = FileStore(os.path.join(d, "x.dat"))
        c = NDOLController(store=store)
        c.write(5, b"old" * 100)
        c.write(5, b"new" * 100)
        assert c.read(5) == b"new" * 100
        store.close()


# ------------------------------ benchmark ---------------------------------- #
def test_bench_sequential_beats_random():
    from ndol.bench import replay, trace_random, trace_sequential

    span = 256
    seq = replay("seq", trace_sequential(512), span=span)
    rnd = replay("rnd", trace_random(512, span), span=span)
    assert seq.speedup >= 1.5
    assert seq.speedup > rnd.speedup  # predictable access prefetches better


def test_bench_incs_boundary_is_monotone_and_flips():
    from ndol.bench import incs_boundary

    rows = incs_boundary()
    # Low ops/byte pushes down; high ops/byte refuses (corrected §3.5).
    assert rows[0][1] is True
    assert rows[-1][1] is False


# ------------------------- KVAwareController (int4_protected) -------------- #
def _make_kv(n_blocks: int = 100, protected_every: int = 10):
    c = KVAwareController()
    for bid in range(n_blocks):
        c.write_block(bid, f"kvblock-{bid}".encode().ljust(1280, b"\0"),
                      protected=(bid % protected_every == 0))
    c.metrics.__init__()
    return c


def test_kv_gather_is_byte_identical_to_full_read():
    # gather == full-read: the EQSPEC invariant, by construction.
    c = _make_kv()
    retained = [3, 17, 42, 99]
    out = c.step(retained)
    for bid, blob in zip(retained, out):
        assert blob == c.comp.decompress(c.store.read(bid))


def test_kv_protect_mask_drives_tiering():
    c = _make_kv(protected_every=10)
    assert c._tier_of(0) is Tier.SLC    # protected -> fast tier
    assert c._tier_of(10) is Tier.SLC
    assert c._tier_of(3) is Tier.QLC    # 4-bit bulk -> dense tier


def test_kv_read_skip_yields_bandwidth_amplification_and_speedup():
    c = _make_kv(n_blocks=100)
    retained = list(range(8))  # read-skip keeps ~8% of blocks
    for _ in range(20):        # stable attention across steps
        c.step(retained)
    r = c.kv_report()
    # ~100/8 full-attention reduction, compounded by VSP on the stable set.
    assert r["bandwidth_amplification"] > 10.0
    assert r["speedup_vs_baseline"] > 5.0
    assert r["vsp_hit_rate"] > 0.5      # stable retained set hits the prefetch buffer


def test_kv_baseline_is_full_attention():
    c = _make_kv(n_blocks=50)
    c.step([1, 2, 3])
    # One step's baseline accounts a full read of all 50 blocks.
    assert c.metrics.blocks_skipped == 47
    assert c.metrics.blocks_gathered == 3
