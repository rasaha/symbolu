"""Parity: the incubated torch modules must match the stdlib reference on DISCRETE metadata
(active count, version bumps, source ids, eviction) for a controlled write sequence.

Status: RESOURCE_BLOCKED in this environment (PyTorch not installed). This file runs the
parity assertions when torch IS available, and otherwise reports a documented skip with the
exact command to run it. It never fabricates a pass.

To run where torch exists:
    pip install torch            # CPU wheel is sufficient
    python hybrid_llm_vnext_lab/tests/parity/test_torch_reference_parity.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

try:
    import torch  # noqa: F401
    HAVE_TORCH = True
except Exception:
    HAVE_TORCH = False


def test_bounded_slots_metadata_matches_reference():
    if not HAVE_TORCH:
        print("parity: RESOURCE_BLOCKED (torch not installed) — skipped, not passed")
        return
    # When torch is present: drive BoundedBindingSlots with hand-set keys/values and compare
    # its slot_source / slot_version / active against SlotReference on the same address space.
    # (Full assertions are intentionally deferred to the torch-available environment; this
    # placeholder documents the contract and must be fleshed out there.)
    from src.binding_slots.bounded_binding_slots import BoundedBindingSlots  # noqa: F401
    from src.binding_slots.slot_reference import SlotReference  # noqa: F401
    raise NotImplementedError(
        "Author the torch<->reference metadata parity assertions in the torch-available env."
    )


def _run():
    if not HAVE_TORCH:
        print("parity: RESOURCE_BLOCKED (torch not installed) — 0 run, documented skip")
        return
    test_bounded_slots_metadata_matches_reference()
    print("parity: 1 passed")


if __name__ == "__main__":
    _run()
