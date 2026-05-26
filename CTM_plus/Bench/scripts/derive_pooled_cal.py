"""Derive a pooled-layer calibration from a per-layer calibration.

The May 2026 Phase 4 GPU run (v5) used POOLED-LAYER calibration —
all 28 layers' Q-vector statistics were accumulated into one bucket.
This produced MRL = 0.221, below the methodology's >= 0.3 healthy
bar. Per-layer recalibration landed post-findings and is what the
phase8a_remeasure.sh run used (and the Phase 4 trig algorithm win
shrank from v5's -11% swap_out to a much weaker -1.3%).

To investigate the -11% vs -1.3% gap, we need to re-run Cell 3 with
v5's calibration methodology. Three options:

  1. Re-run calibrate_qcenters_vllm.py with num_layers=1. Cheapest,
     but produces a JSON with num_layers=1 — the runner crashes on
     index lookup because runtime_num_layers=28 (from model config)
     while target_layer=27 means trig_score_block looks up
     stats.e_q_real[27][head][f] -- IndexError.

  2. Modify the runner to pass cal_num_layers instead of model's
     num_hidden_layers. Cleaner, but a code change beyond the
     investigation scope.

  3. **Derive a broadcast-pooled JSON from a per-layer JSON.**
     Average the per-layer stats across the layer axis, then
     broadcast the result back to num_layers=28 by replicating the
     pooled values for every layer index. The runtime behaviour is
     mathematically equivalent to v5's pooled calibration: every
     layer's lookup returns the same (pooled) value.

This script implements option 3. Reproducible, no GPU spend, no
code change to the production path.

Note on equivalence: with vLLM's shared RotaryEmbedding (one
instance fires once per layer per forward pass), each layer
contributes equal weight to the per-layer accumulation. So the
arithmetic mean of per-layer e_q_real / e_q_imag / e_q_norm IS the
pooled-layer mean v5 would have collected. The token count is
preserved.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


def derive_pooled(per_layer: dict) -> dict:
    n_layers = int(per_layer["num_layers"])
    n_heads = int(per_layer["num_heads"])
    n_bands = int(per_layer["num_bands"])

    def pooled_field(name: str):
        arr = per_layer[name]
        pooled = [
            [
                statistics.fmean(arr[l][h][b] for l in range(n_layers))
                for b in range(n_bands)
            ]
            for h in range(n_heads)
        ]
        # Broadcast: replicate the pooled values for every layer.
        return [pooled for _ in range(n_layers)]

    out = dict(per_layer)
    out["e_q_real"] = pooled_field("e_q_real")
    out["e_q_imag"] = pooled_field("e_q_imag")
    out["e_q_norm"] = pooled_field("e_q_norm")
    out["calibration_corpus"] = (
        per_layer.get("calibration_corpus", "unspecified")
        + "__broadcast_pooled"
    )
    return out


def mrl_summary(payload: dict) -> dict:
    """Mean resultant length per band, averaged across (layer, head).
    Used to verify the pooled vs per-layer methodology difference.
    """
    import math
    n_layers = int(payload["num_layers"])
    n_heads = int(payload["num_heads"])
    n_bands = int(payload["num_bands"])
    per_band_mrl = []
    for b in range(n_bands):
        accum = []
        for l in range(n_layers):
            for h in range(n_heads):
                norm = payload["e_q_norm"][l][h][b]
                if norm <= 0:
                    continue
                re = payload["e_q_real"][l][h][b]
                im = payload["e_q_imag"][l][h][b]
                accum.append(math.sqrt(re * re + im * im) / norm)
        per_band_mrl.append(statistics.fmean(accum) if accum else 0.0)
    return {
        "min": min(per_band_mrl),
        "max": max(per_band_mrl),
        "mean": statistics.fmean(per_band_mrl),
        "median": statistics.median(per_band_mrl),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True,
                        help="Per-layer QCenterStats JSON.")
    parser.add_argument("--output", required=True,
                        help="Path to write the broadcast-pooled JSON.")
    args = parser.parse_args(argv)

    src = json.load(open(args.input))
    dst = derive_pooled(src)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(dst, indent=2))

    print(f"Wrote {args.output}")
    print(f"  num_layers (preserved): {dst['num_layers']}")
    print(f"  num_heads: {dst['num_heads']}, num_bands: {dst['num_bands']}")
    print(f"  corpus_label: {dst['calibration_corpus']}")
    print()
    print("MRL comparison (mean across layer x head, per band):")
    src_mrl = mrl_summary(src)
    dst_mrl = mrl_summary(dst)
    for k in ("min", "max", "mean", "median"):
        print(f"  {k:7s}: per-layer={src_mrl[k]:.4f}  pooled={dst_mrl[k]:.4f}")
    print()
    print("If pooled MRL ~ 0.22, this matches v5's reported value")
    print("(audit: 'MRL=0.221, below the methodology's >=0.3 bar').")
    return 0


if __name__ == "__main__":
    sys.exit(main())
