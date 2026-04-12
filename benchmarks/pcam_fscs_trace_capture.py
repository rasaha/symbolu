#!/usr/bin/env python3
"""
Capture an annotated KV-cache trace from FSCS-wrapped Mistral for PCAM replay.

This script bridges FSCS (the attention-operator research) and PCAM (the
memory-policy product). It runs a small eval pass through FSCS-wrapped
Mistral, captures per-layer attention mass and FSCS diagnostic signals,
and emits a PCAM-compatible TraceEvent JSON that includes three new
annotation fields per block:

    boundary_score   — structural boundary sensitivity [0, 1]
    band_class       — layer band importance multiplier (global=1.3, mid=1.0, local=0.8)
    instability_hint — attention instability / future-read demand [0, 1]

The output trace can be replayed through `simulator.pcam.trace.replay`
in two modes:
    baseline  — new signal weights off (existing four-signal scoring)
    enhanced  — new signal weights on  (six-signal scoring with Stage 1-3)

Usage:

    python3 benchmarks/pcam_fscs_trace_capture.py \
        --model mistralai/Mistral-7B-v0.3 \
        --quantize bf16 \
        --num-samples 4 \
        --seq-len 512 \
        --output results/pcam_traces/fscs_annotated.jsonl

The output is one JSON object per line (JSONL), where each line is a
TraceEvent dict. This matches the format consumed by pcam_trace_replay.py.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulator.pcam.trace import EventKind, TraceEvent


# ---------------------------------------------------------------------------
# Band assignment (mirrors FSCS MistralFSCSWrapper._assign_band)
# ---------------------------------------------------------------------------

def assign_band_class(layer_idx: int, num_layers: int) -> float:
    """
    Assign a band-class multiplier based on layer depth.

    Same thirds-based partition as MistralFSCSWrapper._assign_band:
        layers 0..(L/3-1)   → global  (1.3)
        layers L/3..(2L/3-1) → mid    (1.0)
        layers 2L/3..(L-1)  → local   (0.8)
    """
    third = num_layers // 3
    if layer_idx < third:
        return 1.3   # global — expensive to miss
    if layer_idx < 2 * third:
        return 1.0   # mid — neutral
    return 0.8       # local — cheaper to recompute


# ---------------------------------------------------------------------------
# Boundary heuristic (mirrors FSCS FSCSBoundaryDetector logic)
# ---------------------------------------------------------------------------

_BOUNDARY_CHARS = set("\n.!?;:{}()[]")

def compute_boundary_scores(
    tokenizer: Any,
    input_ids: Any,  # [N] tensor of token IDs
    block_size: int,
) -> Dict[int, float]:
    """
    Compute per-block boundary scores from token content.

    Strategy: decode each token to text, check if it contains any
    boundary character, compute the fraction of boundary tokens per
    block. The fraction is the block's boundary_score ∈ [0, 1].
    """
    import torch

    ids = input_ids.tolist() if hasattr(input_ids, 'tolist') else list(input_ids)
    n = len(ids)

    # Decode each token individually (fast for small sequences)
    boundary_flags = []
    for tid in ids:
        try:
            text = tokenizer.decode([tid])
        except Exception:
            text = ""
        is_boundary = any(c in text for c in _BOUNDARY_CHARS)
        boundary_flags.append(1.0 if is_boundary else 0.0)

    # Aggregate to block level: fraction of boundary tokens per block
    per_block: Dict[int, float] = {}
    for pos, flag in enumerate(boundary_flags):
        block_id = pos // block_size
        if block_id not in per_block:
            per_block[block_id] = {"sum": 0.0, "count": 0}
        per_block[block_id]["sum"] += flag
        per_block[block_id]["count"] += 1

    return {
        bid: d["sum"] / max(1, d["count"])
        for bid, d in per_block.items()
    }


# ---------------------------------------------------------------------------
# Main capture logic
# ---------------------------------------------------------------------------

def capture_annotated_trace(
    model_name: str,
    quantize: Optional[str],
    num_samples: int,
    seq_len: int,
    block_size: int,
    output_path: str,
) -> Dict[str, Any]:
    """
    Run eval on FSCS-wrapped Mistral and emit an annotated PCAM trace.

    Returns a summary dict with trace stats.
    """
    import torch
    from symbolu.fscs.core import FSCSConfig
    from symbolu_training.training.unified.mistral_fscs_wrapper import (
        MistralFSCSWrapper,
    )

    print(f"Loading {model_name} ({quantize or 'bf16'})...", flush=True)
    cfg = FSCSConfig(use_ema_cache=False, use_per_band_coarse=False)
    quant = None if quantize in (None, "none", "bf16") else quantize
    wrapper = MistralFSCSWrapper(
        model_name=model_name,
        quantize=quant,
        fscs_cfg=cfg,
    )
    device = next(wrapper.backbone.parameters()).device
    tokenizer = wrapper.tokenizer
    num_layers = len(wrapper.gated_layers)

    # Tokenize a small corpus
    print("Tokenizing eval text...", flush=True)
    from datasets import load_dataset
    ds = load_dataset("wikitext", "wikitext-2-raw-v1", split="validation")
    text = "\n\n".join(s for s in ds["text"] if s.strip())
    enc = tokenizer(text, return_tensors="pt", add_special_tokens=False)
    all_ids = enc.input_ids[0]
    n_total = (all_ids.shape[0] // seq_len) * seq_len
    all_ids = all_ids[:n_total].view(-1, seq_len)
    if all_ids.shape[0] > num_samples:
        all_ids = all_ids[:num_samples]
    print(f"Eval shape: {tuple(all_ids.shape)}", flush=True)

    # Collect trace events
    all_events: List[Dict[str, Any]] = []
    total_blocks = 0

    wrapper.eval()
    with torch.no_grad():
        for sample_idx in range(all_ids.shape[0]):
            input_ids = all_ids[sample_idx:sample_idx+1].to(device)
            seq_id = sample_idx + 1
            N = input_ids.shape[1]

            # Compute boundary scores for this sequence
            boundary_scores = compute_boundary_scores(
                tokenizer, all_ids[sample_idx], block_size,
            )

            # Run forward pass through the FSCS wrapper
            out = wrapper(input_ids=input_ids)

            # Collect per-layer coherence from the gated layers
            per_layer_coherence: Dict[int, float] = {}
            for layer_idx, gl in enumerate(wrapper.gated_layers):
                per_layer_coherence[layer_idx] = gl.last_mean_pi

            # Emit trace events for this sequence
            all_events.append(TraceEvent(
                EventKind.REGISTER_SEQUENCE, {"seq_id": seq_id}
            ).to_dict())
            all_events.append(TraceEvent(
                EventKind.SET_PHASE,
                {"seq_id": seq_id, "phase": "DECODE"},
            ).to_dict())

            # Emit one block per (layer, block_position) pair
            num_blocks_in_seq = (N + block_size - 1) // block_size
            for layer_idx in range(num_layers):
                band = assign_band_class(layer_idx, num_layers)
                # Instability = 1.0 - gate_fraction (higher gate = more stable = lower instability)
                gate_frac = per_layer_coherence.get(layer_idx, 0.0)
                instability = max(0.0, min(1.0, 1.0 - gate_frac * 5.0))

                for blk_pos in range(num_blocks_in_seq):
                    block_id = (
                        sample_idx * num_layers * num_blocks_in_seq
                        + layer_idx * num_blocks_in_seq
                        + blk_pos
                    )
                    start_pos = blk_pos * block_size
                    positions = list(range(
                        start_pos,
                        min(start_pos + block_size, N)
                    ))

                    boundary = boundary_scores.get(blk_pos, 0.0)

                    # Attention mass proxy: uniform across blocks for now.
                    # Real per-block attention mass requires output_attentions=True
                    # which doubles VRAM; we use a simple position-based proxy
                    # where earlier positions get higher mass (attention-sink effect).
                    attention_mass = 1.0 / (1.0 + 0.01 * start_pos)

                    all_events.append(TraceEvent(
                        EventKind.ENSURE_BLOCK,
                        {
                            "block_id": block_id,
                            "sequence_id": seq_id,
                            "positions": positions,
                            "boundary_score": round(boundary, 4),
                            "band_class": band,
                            "instability_hint": round(instability, 4),
                        },
                    ).to_dict())

                    all_events.append(TraceEvent(
                        EventKind.ON_BLOCK_ATTENTION,
                        {
                            "block_id": block_id,
                            "attention_sum": round(attention_mass, 6),
                            "sequence_id": seq_id,
                        },
                    ).to_dict())
                    total_blocks += 1

            # Eviction pressure: request victims after each sequence
            # to give the policy something to decide
            evict_count = max(1, total_blocks // 10)
            all_events.append(TraceEvent(
                EventKind.SELECT_VICTIMS,
                {"count": evict_count},
            ).to_dict())

            all_events.append(TraceEvent(
                EventKind.COMPLETE_SEQUENCE,
                {"seq_id": seq_id},
            ).to_dict())

            print(f"  sample {sample_idx+1}/{all_ids.shape[0]}: "
                  f"{num_blocks_in_seq * num_layers} blocks, "
                  f"{evict_count} victims requested", flush=True)

    # Write JSONL
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for event in all_events:
            f.write(json.dumps(event) + "\n")

    summary = {
        "model": model_name,
        "num_samples": all_ids.shape[0],
        "seq_len": seq_len,
        "block_size": block_size,
        "num_layers": num_layers,
        "total_events": len(all_events),
        "total_blocks": total_blocks,
        "output": output_path,
    }
    print(f"\nTrace written: {output_path} ({len(all_events)} events, "
          f"{total_blocks} blocks)", flush=True)
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="Capture annotated KV-cache trace from FSCS/Mistral"
    )
    p.add_argument("--model", default="mistralai/Mistral-7B-v0.3")
    p.add_argument("--quantize", default="bf16")
    p.add_argument("--num-samples", type=int, default=4)
    p.add_argument("--seq-len", type=int, default=512)
    p.add_argument("--block-size", type=int, default=16)
    p.add_argument("--output", default="results/pcam_traces/fscs_annotated.jsonl")
    args = p.parse_args()

    capture_annotated_trace(
        model_name=args.model,
        quantize=args.quantize,
        num_samples=args.num_samples,
        seq_len=args.seq_len,
        block_size=args.block_size,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
