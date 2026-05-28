"""Phase 6J — Generate the all-zeros companion to a calibrated
protect-mask artifact.

The naive cell of the Phase 6J bench needs a protect-mask file where
every channel is unprotected. We could hard-code an all-zeros tensor,
but the calibrated mask format depends on Phase 5B.0's output
(num_layers, H, D), so the simplest correctness-preserving approach
is to LOAD the calibrated mask, COPY ITS STRUCTURE with zeros, and
SAVE the result alongside it.

This script does that. It supports all three on-disk formats the
writer accepts (bare tensor, dict with 'mask' key, dict keyed by
layer index).

Run:
  python CTM_plus/Bench/scripts/make_phase6j_naive_protect_mask.py \
    --src /workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt \
    --dst /workspace/dev/build-logs/qwen2_5_7b_protect_mask_naive.pt

The script is safe to re-run: it verifies the structure of the
generated artifact matches the source and prints a side-by-side
summary so the operator can confirm "naive really is all-zeros".
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import torch
except ImportError:
    print("FAIL: torch import failed; cannot run mask generator")
    sys.exit(2)


def _zero_like_structure(raw):
    """Return an all-zeros copy of `raw` preserving its structure
    (bare tensor / dict-with-key / dict-keyed-by-layer)."""
    if isinstance(raw, torch.Tensor):
        return torch.zeros_like(raw)
    if isinstance(raw, dict):
        out = {}
        for k, v in raw.items():
            if isinstance(v, torch.Tensor):
                out[k] = torch.zeros_like(v)
            else:
                # Pass through any non-tensor metadata (e.g., calibration
                # notes, n_protect hint, model name) verbatim. The naive
                # mask file should describe ITSELF, not the calibrated
                # baseline, but for the writer's lookup path the data
                # field is all that matters.
                out[k] = v
        return out
    raise TypeError(
        f"Unrecognized protect-mask artifact root type: {type(raw).__name__}. "
        f"Expected torch.Tensor or dict. Update the generator if a new "
        f"format is needed."
    )


def _describe(raw, label):
    print(f"--- {label} ---")
    if isinstance(raw, torch.Tensor):
        nz = int((raw != 0).sum().item())
        total = int(raw.numel())
        print(f"  type: Tensor   shape: {tuple(raw.shape)}   dtype: {raw.dtype}")
        print(f"  nonzero: {nz} / {total} ({100.0 * nz / max(1, total):.2f}%)")
    elif isinstance(raw, dict):
        print(f"  type: dict   keys: {sorted(map(str, raw.keys()))[:8]}")
        for k, v in raw.items():
            if isinstance(v, torch.Tensor):
                nz = int((v != 0).sum().item())
                total = int(v.numel())
                print(f"    [{k!r}] Tensor shape={tuple(v.shape)} dtype={v.dtype}  "
                      f"nonzero={nz}/{total} ({100.0*nz/max(1,total):.2f}%)")
            else:
                print(f"    [{k!r}] {type(v).__name__}  (non-tensor, copied as-is)")
    else:
        print(f"  type: {type(raw).__name__}  (UNSUPPORTED — generator will reject)")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True, type=str,
                   help="Path to the calibrated protect-mask artifact.")
    p.add_argument("--dst", required=True, type=str,
                   help="Path where the all-zeros companion will be written.")
    p.add_argument("--force", action="store_true",
                   help="Overwrite --dst if it already exists.")
    args = p.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)

    if not src.exists():
        print(f"FAIL: source artifact does not exist: {src}")
        return 2

    if dst.exists() and not args.force:
        print(f"FAIL: destination exists ({dst}). Pass --force to overwrite.")
        return 2

    # Load (trusted — same file the writer's load_protect_mask_for_layer
    # uses; weights_only=False because the format may be a dict with
    # plain Python types).
    print(f"Loading source: {src}")
    raw = torch.load(src, map_location="cpu", weights_only=False)
    _describe(raw, "SOURCE (calibrated)")

    naive = _zero_like_structure(raw)
    _describe(naive, "DESTINATION (all-zeros companion)")

    # Sanity: confirm structure match.
    if isinstance(raw, torch.Tensor):
        assert isinstance(naive, torch.Tensor)
        assert naive.shape == raw.shape
        assert naive.dtype == raw.dtype
        assert int((naive != 0).sum().item()) == 0
    elif isinstance(raw, dict):
        assert isinstance(naive, dict)
        assert set(raw.keys()) == set(naive.keys())
        for k, v in raw.items():
            if isinstance(v, torch.Tensor):
                assert naive[k].shape == v.shape
                assert naive[k].dtype == v.dtype
                assert int((naive[k] != 0).sum().item()) == 0

    dst.parent.mkdir(parents=True, exist_ok=True)
    torch.save(naive, dst)
    print(f"Wrote: {dst}")
    print()
    print("Done. Naive cell can now be invoked with:")
    print(f"  PROTECT_MASK_PATH={dst} PHASE6J_NAIVE_FORCE_ZERO=1 python ...")
    print()
    print("Note: PHASE6J_NAIVE_FORCE_ZERO=1 is also needed because the")
    print("all-zeros mask still leaves channel 0 'protected' (the writer's")
    print("n_protect = max(1, mask_sum_per_head_max) = 1 with a degenerate")
    print("single-channel slot). The force-zero env flag zeros the protect")
    print("contribution at read time, eliminating that confound.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
