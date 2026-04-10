"""
cocotb parity harness for ``simulator/pcam/rtl/core/freq_sketch.sv``.

This module is loaded by cocotb when invoked via ``make cosim`` from
``simulator/pcam/rtl/tests/Makefile``. It is NOT a pytest module — the
tests below take a ``dut`` argument that only cocotb can provide. The
pytest wrapper at ``test_freq_sketch_cosim.py`` drives the make target
via subprocess and skips if cocotb / verilator are unavailable.

What it proves
--------------
Bit-for-bit observational parity between the SystemVerilog
``freq_sketch`` module and the canonical Python reference at
``simulator.pcam.kv_policy.FrequencySketch`` on a deterministic trace.
The Python reference is itself a bit-parity port of the vendored CTM+
reference per ADR-0001, so a cocotb green signal here transitively
proves the RTL matches the vendored spec.

What it does NOT prove
----------------------
- It does not exercise ``KVCachePolicy`` RTL parity. That is Phase 3+.
- It does not stress the halving FSM at production capacities. We use
  a small CAPACITY override so the halving trigger is reachable in a
  short test.
- It does not validate timing closure or synthesis results. That is a
  separate workstream from behavioral parity.

Reference
---------
The Python oracle is reached via
``from simulator.pcam.kv_policy import FrequencySketch``. Run the
cosim from the repo root so the package is importable; the Makefile
sets PYTHONPATH accordingly.
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Make sure the repo root is on sys.path before importing the reference.
# The Makefile sets PYTHONPATH, but add a belt-and-suspenders fallback.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import cocotb  # noqa: E402
from cocotb.clock import Clock  # noqa: E402
from cocotb.triggers import RisingEdge, Timer  # noqa: E402

from simulator.pcam.kv_policy import FrequencySketch  # noqa: E402


# ---------------------------------------------------------------------------
# The RTL is elaborated with CAPACITY=64 in the Makefile so the halving
# trigger (reset_threshold = 64 * 10 = 640) is reachable in a short test.
# The Python reference is constructed with the same capacity so the
# width, depth, reset_threshold, and seed hashes all match.
# ---------------------------------------------------------------------------
DUT_CAPACITY = 64
CLK_PERIOD_NS = 4  # 250 MHz, matching the existing tb_pcam_top convention


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _reset(dut) -> None:
    """Drive active-low reset for a handful of cycles, idle all inputs."""
    dut.rst_n.value = 0
    dut.inc_valid.value = 0
    dut.inc_key.value = 0
    dut.est_valid.value = 0
    dut.est_key.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    for _ in range(3):
        await RisingEdge(dut.clk)


async def _start_clock(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, units="ns").start())


async def _wait_not_busy(dut, timeout_cycles: int = 2048) -> None:
    """Wait until the DUT reports busy == 0. Used to stall through halving."""
    for _ in range(timeout_cycles):
        if int(dut.busy.value) == 0:
            return
        await RisingEdge(dut.clk)
    raise TimeoutError(
        f"DUT stayed busy for more than {timeout_cycles} cycles"
    )


async def _increment(dut, key: int) -> int:
    """
    Drive one increment. Waits for the ``inc_done`` pulse and returns the
    observed ``inc_min_count``. Stalls through halving events automatically
    via ``_wait_not_busy``.
    """
    await _wait_not_busy(dut)
    dut.inc_valid.value = 1
    dut.inc_key.value = key
    # Wait for inc_done to pulse. Under the happy path this takes one
    # cycle; under a threshold-crossing event, it takes WIDTH + ~2 cycles
    # while the halving FSM runs and the deferred key is replayed.
    observed = 0
    for _ in range(2048):
        await RisingEdge(dut.clk)
        if int(dut.inc_done.value) == 1:
            observed = int(dut.inc_min_count.value)
            break
    else:
        raise TimeoutError(f"inc_done never asserted for key={key}")
    dut.inc_valid.value = 0
    # One extra cycle so the done pulse clears before the next drive.
    await RisingEdge(dut.clk)
    return observed


async def _estimate(dut, key: int) -> int:
    """
    Drive one estimate lookup. The estimate path is combinational with a
    1-cycle output register, so we pulse ``est_valid`` for one cycle and
    read ``est_value`` on the next rising edge.
    """
    dut.est_valid.value = 1
    dut.est_key.value = key
    await RisingEdge(dut.clk)
    dut.est_valid.value = 0
    await RisingEdge(dut.clk)
    return int(dut.est_value.value)


# ===========================================================================
# Scenario 1 — single-key saturation
# ===========================================================================


@cocotb.test()
async def test_single_key_saturation(dut):
    """
    Drive 20 increments of the same key. The RTL counter must saturate
    at 15 and match the Python reference estimate after every bump.
    """
    await _start_clock(dut)
    await _reset(dut)

    ref = FrequencySketch(capacity=DUT_CAPACITY)

    key = 42
    for step in range(1, 21):
        rtl_min = await _increment(dut, key)
        ref_min = ref.increment(key)
        assert rtl_min == ref_min, (
            f"[step {step}] inc_min_count diverged on key={key}: "
            f"rtl={rtl_min}, ref={ref_min}"
        )

    rtl_est = await _estimate(dut, key)
    ref_est = ref.estimate(key)
    assert rtl_est == ref_est == 15, (
        f"post-saturation estimate diverged: rtl={rtl_est}, ref={ref_est}"
    )


# ===========================================================================
# Scenario 2 — distinct keys, light load
# ===========================================================================


@cocotb.test()
async def test_distinct_keys_light_load(dut):
    """
    Insert 32 distinct keys, one increment each. Both sides must return
    identical estimates for every inserted key and for an uninserted
    probe key.
    """
    await _start_clock(dut)
    await _reset(dut)

    ref = FrequencySketch(capacity=DUT_CAPACITY)

    for k in range(32):
        await _increment(dut, k)
        ref.increment(k)

    # Probe every inserted key plus one never-seen key.
    for k in list(range(32)) + [9999]:
        rtl_est = await _estimate(dut, k)
        ref_est = ref.estimate(k)
        assert rtl_est == ref_est, (
            f"estimate diverged on key={k}: rtl={rtl_est}, ref={ref_est}"
        )


# ===========================================================================
# Scenario 3 — event-driven halving at reset_threshold
# ===========================================================================


@cocotb.test()
async def test_halving_fires_at_reset_threshold(dut):
    """
    At CAPACITY=64, reset_threshold = 640. Saturate key 0 up front,
    then drive filler keys until the threshold crossing triggers the
    halving FSM. After halving:

      - size_count must be exactly 640 >> 1 = 320
      - key 0's estimate must drop from 15 to 7
      - post-halve parity against the reference must hold

    The ``_increment`` helper stalls through ``busy``, so the halving
    FSM is absorbed into the last increment's latency.
    """
    await _start_clock(dut)
    await _reset(dut)

    ref = FrequencySketch(capacity=DUT_CAPACITY)
    assert ref.reset_threshold == 640

    # Saturate key 0 on both sides.
    for _ in range(15):
        await _increment(dut, 0)
        ref.increment(0)

    rtl_est_pre = await _estimate(dut, 0)
    assert rtl_est_pre == ref.estimate(0) == 15

    # Drive filler keys until just below the threshold. 15 + 624 = 639.
    for k in range(1, 625):
        await _increment(dut, k)
        ref.increment(k)

    # One more increment crosses the threshold and triggers halving.
    # Use a never-seen key to avoid perturbing key 0's pre-halve state.
    await _increment(dut, 0xDEAD_BEEF)
    ref.increment(0xDEAD_BEEF)

    # Post-halve parity.
    rtl_size = int(dut.size_count.value)
    assert rtl_size == ref.size, (
        f"post-halve size diverged: rtl={rtl_size}, ref={ref.size}"
    )
    rtl_est_post = await _estimate(dut, 0)
    ref_est_post = ref.estimate(0)
    assert rtl_est_post == ref_est_post == 7, (
        f"post-halve key=0 estimate diverged: "
        f"rtl={rtl_est_post}, ref={ref_est_post}"
    )


# ===========================================================================
# Scenario 4 — randomized differential (safety net)
# ===========================================================================


@cocotb.test()
async def test_randomized_parity_200_steps(dut):
    """
    Drive a 200-step pseudo-random increment stream through both the
    DUT and the reference with a fixed seed. Spot-check estimates
    every 25 steps.
    """
    await _start_clock(dut)
    await _reset(dut)

    ref = FrequencySketch(capacity=DUT_CAPACITY)
    rng = random.Random(0xC0DECAFE)
    key_universe = list(range(80))

    for step in range(200):
        key = rng.choice(key_universe)
        rtl_min = await _increment(dut, key)
        ref_min = ref.increment(key)
        assert rtl_min == ref_min, (
            f"[step {step}] inc_min_count diverged on key={key}: "
            f"rtl={rtl_min}, ref={ref_min} (size rtl={int(dut.size_count.value)}, "
            f"ref={ref.size})"
        )
        if step % 25 == 0:
            for probe in rng.sample(key_universe, 4):
                rtl_est = await _estimate(dut, probe)
                ref_est = ref.estimate(probe)
                assert rtl_est == ref_est, (
                    f"[step {step}] estimate diverged on probe={probe}: "
                    f"rtl={rtl_est}, ref={ref_est}"
                )
