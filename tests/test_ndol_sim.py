"""Tests for the MQSim integration.

Trace-format tests run anywhere. The end-to-end MQSim test is skipped unless an
MQSim binary is present (build it under /tmp/MQSim or set $NDOL_MQSIM_DIR).
"""
from __future__ import annotations

import os

import pytest

from ndol.sim import kv_read_skip_traces, run_mqsim
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
