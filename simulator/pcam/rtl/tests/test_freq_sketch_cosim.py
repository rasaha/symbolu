"""
Pytest wrapper for the cocotb freq_sketch parity harness.

This file is pytest-collectable. When cocotb and a SystemVerilog
simulator backend (verilator or iverilog) are available, the single
test below invokes ``make cosim`` via subprocess and asserts a clean
exit. When either dependency is missing, the test skips with a clear
pointer to the install hint — it does NOT fail, and it does NOT fake
a pass.

The actual cocotb tests live in ``cosim_freq_sketch.py`` alongside
this file. They are not pytest tests (they take a ``dut`` argument
that only cocotb can provide) and are loaded by the Makefile via
``MODULE=cosim_freq_sketch``.

What a clean cosim run proves
-----------------------------
Bit-for-bit observational parity between the SystemVerilog
``freq_sketch`` module and ``simulator.pcam.kv_policy.FrequencySketch``
on four deterministic scenarios:

1. Single-key saturation — 20 increments of the same key; counter
   must saturate at 15.
2. Distinct keys under light load — 32 distinct keys plus an
   uninserted probe; estimates must match exactly.
3. Event-driven halving at ``reset_threshold`` — saturate key 0,
   drive to the threshold, fire the halving FSM; post-halve size
   must be exactly ``reset_threshold // 2`` and key 0's estimate
   must drop from 15 to 7.
4. Randomized 200-step differential with a fixed seed; estimates
   must match at every spot check.

The Python reference is itself a bit-parity port of the vendored
CTM+ reference per ADR-0001, so a green cosim run transitively
proves the RTL matches the spec.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

THIS_DIR = Path(__file__).parent


def _check_tooling() -> tuple[bool, str | None]:
    """
    Return ``(True, None)`` if cocotb and a simulator backend are both
    available; otherwise ``(False, reason)`` with a human-readable
    install hint. Does not raise.
    """
    try:
        import cocotb  # noqa: F401
    except ImportError:
        return False, (
            "cocotb is not installed. Install with `pip install cocotb` "
            "and a SystemVerilog backend (apt install verilator OR "
            "apt install iverilog) before running this test."
        )

    if shutil.which("verilator") is None and shutil.which("iverilog") is None:
        return False, (
            "No SystemVerilog simulator on PATH. Install verilator "
            "(`apt install verilator`) or Icarus Verilog "
            "(`apt install iverilog`) before running this test."
        )

    return True, None


def test_freq_sketch_rtl_parity():
    """
    Invoke the cocotb cosimulation of ``freq_sketch.sv`` against the
    canonical Python reference and assert a clean exit.

    Skips cleanly when cocotb or a simulator backend is unavailable.
    See the module docstring for the scenarios exercised.
    """
    ok, reason = _check_tooling()
    if not ok:
        pytest.skip(reason)

    result = subprocess.run(
        ["make", "-C", str(THIS_DIR), "cosim"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Dump both streams so a failing cosim is diagnosable from the
        # pytest report without having to re-run the Makefile by hand.
        raise AssertionError(
            "cocotb cosimulation of freq_sketch.sv failed.\n"
            "------ STDOUT ------\n"
            f"{result.stdout}\n"
            "------ STDERR ------\n"
            f"{result.stderr}"
        )
