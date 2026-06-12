"""Tests for the MQSim integration.

Trace-format tests run anywhere. The end-to-end MQSim test is skipped unless an
MQSim binary is present (build it under /tmp/MQSim or set $NDOL_MQSIM_DIR).
"""
from __future__ import annotations

import os

import pytest

from ndol.sim import (
    kv_read_skip_traces,
    make_tier_config,
    run_mqsim,
    tiered_kv_traces,
)
from ndol.sim.mqsim import MQSimTrace


def _mqsim_dir() -> str | None:
    d = os.environ.get("NDOL_MQSIM_DIR", "/tmp/MQSim")
    return d if os.path.exists(os.path.join(d, "MQSim")) else None


# ------------------------------ trace format ------------------------------- #
def test_trace_rows_are_strictly_monotonic_and_well_formed(tmp_path):
    tr = MQSimTrace()
    # Same-timestamp burst must be nudged to strictly increasing arrivals.
    tr.add(1000, lba=0, size_sectors=8, is_read=True)
    tr.add(1000, lba=8, size_sectors=8, is_read=True)
    tr.add(1000, lba=16, size_sectors=8, is_read=False)
    path = str(tmp_path / "t.trace")
    assert tr.write(path) == 3
    rows = [line.split() for line in open(path).read().splitlines()]
    arrivals = [int(r[0]) for r in rows]
    assert arrivals == sorted(arrivals)
    assert len(set(arrivals)) == len(arrivals)        # strictly increasing
    assert all(len(r) == 5 for r in rows)             # arrival dev lba size type
    assert rows[-1][4] == "0"                         # write
    assert rows[0][4] == "1"                          # read


def test_kv_traces_baseline_is_full_attention_ndol_is_read_skip(tmp_path):
    out = kv_read_skip_traces(str(tmp_path), n_blocks=64, n_steps=8, retained=8, prefill=True)
    # baseline reads all 64 blocks/step; ndol reads 8/step. Both + 64 prefill writes.
    assert out["baseline_requests"] == 64 + 64 * 8
    assert out["ndol_requests"] == 64 + 8 * 8
    assert os.path.exists(out["baseline_trace"]) and os.path.exists(out["ndol_trace"])
    # read-skip issues strictly fewer device requests
    assert out["ndol_requests"] < out["baseline_requests"]


# ------------------------------ end-to-end MQSim --------------------------- #
@pytest.mark.skipif(_mqsim_dir() is None, reason="MQSim binary not built")
def test_mqsim_measures_read_skip_advantage(tmp_path):
    out = kv_read_skip_traces(str(tmp_path), n_blocks=32, n_steps=4, retained=8)
    base = run_mqsim(out["baseline_trace"], mqsim_dir=_mqsim_dir(), timeout_s=300)
    ndol = run_mqsim(out["ndol_trace"], mqsim_dir=_mqsim_dir(), timeout_s=300)
    assert base.is_valid and ndol.is_valid
    assert ndol.read_request_count < base.read_request_count
    # read-skip should not be slower per request than full-attention flooding
    assert ndol.device_response_time_us <= base.device_response_time_us


# ------------------------------ W3 tiering --------------------------------- #
def test_tiered_traces_split_protected_and_bulk(tmp_path):
    out = tiered_kv_traces(str(tmp_path), n_protected=8, n_bulk_window=24, n_steps=10)
    assert out["slc_requests"] == 8 * 10        # hot: re-read every step
    assert out["qlc_requests"] == 24 * 10       # cold: sliding window per step
    assert out["uniform_requests"] == out["slc_requests"] + out["qlc_requests"]


def test_make_tier_config_overrides_only_read_latency(tmp_path):
    import xml.etree.ElementTree as ET

    base = tmp_path / "base.xml"
    base.write_text(
        "<C><Flash_Parameter_Set>"
        "<Page_Read_Latency_LSB>75000</Page_Read_Latency_LSB>"
        "<Page_Read_Latency_MSB>75000</Page_Read_Latency_MSB>"
        "<Page_Program_Latency_LSB>750000</Page_Program_Latency_LSB>"
        "</Flash_Parameter_Set></C>"
    )
    out = make_tier_config(str(base), str(tmp_path / "slc.xml"), t_r_us=25.0)
    root = ET.parse(out).getroot()
    reads = [int(e.text) for e in root.iter() if e.tag.startswith("Page_Read_Latency")]
    assert reads == [25000, 25000]              # SLC t_R, µs→ns
    prog = next(e for e in root.iter() if e.tag.startswith("Page_Program"))
    assert prog.text == "750000"                # program latency untouched


@pytest.mark.skipif(_mqsim_dir() is None, reason="MQSim binary not built")
def test_mqsim_slc_faster_than_qlc(tmp_path):
    import os

    d = _mqsim_dir()
    out = tiered_kv_traces(str(tmp_path), n_protected=8, n_bulk_window=8, n_steps=4)
    slc_cfg = make_tier_config(os.path.join(d, "ssdconfig.xml"), str(tmp_path / "slc.xml"), 25.0)
    qlc_cfg = make_tier_config(os.path.join(d, "ssdconfig.xml"), str(tmp_path / "qlc.xml"), 100.0)
    slc = run_mqsim(out["tier_slc_trace"], mqsim_dir=d, ssdconfig=slc_cfg, timeout_s=300)
    qlc = run_mqsim(out["tier_qlc_trace"], mqsim_dir=d, ssdconfig=qlc_cfg, timeout_s=300)
    assert slc.device_response_time_us < qlc.device_response_time_us
