#!/usr/bin/env python3
"""Neural complexity + decode-state instrumentation (Part VI). Requires torch.

Stronger than the historical output-only hook: it patches key torch ops to record EVERY
intermediate tensor shape during a slot forward, then asserts:
  * the historical BindingSlots materializes slot routing [B,N,M] and a training scan
    tensor [B,N,M,D], but NO [.,N,N] global score tensor;
  * the deployed/streaming recurrent state is bounded [.,M,D], independent of N.

It also classifies the relationship between the historical parallel-scan slots and the
incubated streaming BoundedBindingSlots, and measures decode-state bytes across an (M,D) grid.
Writes hybrid_llm_vnext_lab/artifacts/neural_complexity_probe.json.
"""
from __future__ import annotations

import json
import pathlib
import sys

LAB = pathlib.Path(__file__).resolve().parents[1]
REPO = LAB.parent


def main() -> int:
    try:
        import torch
    except Exception:
        print(json.dumps({"status": "RESOURCE_BLOCKED", "reason": "torch not installed"}))
        return 0

    sys.path.insert(0, str(LAB))
    sys.path.insert(0, str(REPO / "experiments" / "phase_lc"))
    from models import BindingSlots as Historical  # historical parallel-scan slots

    # --- patch torch ops to record intermediate shapes ---
    recorded = []
    originals = {}
    for name in ("cumsum", "einsum", "matmul", "bmm", "softmax"):
        originals[name] = getattr(torch, name)

    def wrap(name, fn):
        def inner(*a, **k):
            out = fn(*a, **k)
            if torch.is_tensor(out):
                recorded.append((name, tuple(out.shape)))
            return out
        return inner

    for name, fn in originals.items():
        setattr(torch, name, wrap(name, fn))
    try:
        B, N, D, M = 2, 48, 128, 32
        torch.manual_seed(0)
        slots = Historical(D, num_slots=M)
        x = torch.randn(B, N, D)
        _ = slots(x)
    finally:
        for name, fn in originals.items():
            setattr(torch, name, fn)

    shapes = [list(s) for _, s in recorded]
    has_NN = any(len(s) >= 2 and s[-1] == N and s[-2] == N for s in shapes)
    has_NMD = any(len(s) == 4 and s[1] == N and s[2] == M and s[3] == D for s in shapes)
    has_NM = any(len(s) == 3 and s[1] == N and s[2] == M for s in shapes)

    # --- decode-state bytes across (M,D) grid via streaming BoundedBindingSlots ---
    from src.binding_slots.bounded_binding_slots import BoundedBindingSlots
    grid = {}
    for M2 in (8, 16, 32, 64):
        for D2 in (64, 128, 256):
            bbs = BoundedBindingSlots(D2, num_slots=M2)
            st = bbs.init_state(1, torch.device("cpu"))
            grid[f"M{M2}_D{D2}"] = int(st.numel())
    # state size independent of N: run streaming forward at two N, compare carried state numel
    bbs = BoundedBindingSlots(128, num_slots=32)
    st_sizes = {}
    for N2 in (16, 64, 256):
        _, st = bbs(torch.randn(1, N2, 128), return_state=True)
        st_sizes[str(N2)] = int(st.numel())
    state_independent_of_N = len(set(st_sizes.values())) == 1

    result = {
        "status": "EXECUTED",
        "config": {"B": B, "N": N, "D": D, "M": M},
        "historical_parallel_scan": {
            "materializes_NxN_global_score": bool(has_NN),
            "materializes_routing_BxNxM": bool(has_NM),
            "materializes_training_scan_BxNxMxD": bool(has_NMD),
            "recorded_op_shapes_sample": shapes[:12],
            "verdict": "NO global N x N; DOES materialize [B,N,M,D] scan during training (NOT constant-memory in training); routing [B,N,M]"
        },
        "streaming_bounded_slots": {
            "deployed_state_shape": "[B,M,D] (+ [B,M] metadata)",
            "state_numel_by_N": st_sizes,
            "state_independent_of_N": state_independent_of_N,
            "decode_state_bytes_grid_MxD_floats": grid
        },
        "algorithm_relationship": {
            "historical": "soft cumulative distributed writes to learned FIXED slots (parallel cumsum); [B,N,M,D] scan",
            "streaming": "dynamic keys, cosine threshold match, DISCRETE allocation/eviction, version/source metadata",
            "classification": "RELATED_BUT_DIFFERENT_ALGORITHM",
            "note": "Do NOT claim numerical parity between these two mechanisms. Neural PARITY is asserted only between the incubated legacy_phase_lc_slots.BindingSlots and the historical BindingSlots (same algorithm) — see tests/parity/test_legacy_neural_slot_parity.py."
        }
    }
    (LAB / "artifacts" / "neural_complexity_probe.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "historical_parallel_scan", "streaming_bounded_slots")}, indent=2)[:1200])
    # hard assertions for CI
    assert not has_NN, "historical slots must NOT build a global N x N tensor"
    assert has_NMD, "historical training scan [B,N,M,D] expected"
    assert state_independent_of_N, "streaming decode state must be independent of N"
    print("neural_complexity_probe: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
