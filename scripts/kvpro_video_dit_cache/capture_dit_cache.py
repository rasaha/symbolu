"""Video-DiT reused-feature-cache — TENSOR CAPTURE (POD-ONLY: needs GPU + a video-DiT pipeline).

Captures the PERSISTENT CROSS-STEP CACHE OBJECTS of a video diffusion transformer so the CPU Stage-A
analyzer (analyze_cache_compressibility.py) can measure whether they are compressible. Also records the
Stage-B systems counters a CPU harness cannot produce (peak HBM, persistent-cache bytes, timings).

SELECTED MODEL (see plan §5): PRIMARY = CogVideoX (diffusers-native DiT, reproducible inference,
transformer-block hidden states + attention outputs are cleanly hookable, existing cross-step cache
methods in diffusers to instrument/compare, single-GPU feasible, VBench-supported). SECONDARY = Wan2.1
T2V (small, diffusers-native). This script instruments whatever diffusers video-DiT you pass; it does NOT
claim support for every family.

What it captures, per hooked transformer block (layer) and per DENOISING STEP that the cache schedule
would reuse — kept SEPARATE by cache-object type (plan §7):
  hidden_states, attn_out, cross_attn_out, temporal_attn_out (when present), and the derived
  feature_delta (consecutive-step difference — the object a delta-cache would actually store).

Canonical saved shape per object/layer: (T, N, C)  — T cached snapshots, N spatial/token positions,
C channels — matching dit_cache_lib. One .pt per (cache_object, layer).

This does NOT modify the pipeline's math or the KVPro core. Hooks are read-only taps.

Usage (pod):
  pip install -U "diffusers>=0.31" transformers accelerate imageio imageio-ffmpeg
  python capture_dit_cache.py --model THUDM/CogVideoX-2b \
      --prompt "A cat playing piano on a city street at night." \
      --num-frames 49 --steps 50 --cache-steps 8,16,24,32,40 \
      --save-layers 0,7,15,23,29 --out-dir artifacts/video_dit_cache/capture
Then (CPU):
  python analyze_cache_compressibility.py --cache artifacts/video_dit_cache/capture
"""
from __future__ import annotations

import argparse
import json
import os
import time


def _parse_ints(s):
    return [int(x) for x in str(s).split(",") if x.strip() != ""]


def main(argv=None):  # pragma: no cover  (pod-only; not exercised by CPU unit tests)
    ap = argparse.ArgumentParser(description="Capture video-DiT cross-step cache objects (pod-only)")
    ap.add_argument("--model", default="THUDM/CogVideoX-2b")
    ap.add_argument("--prompt", default="A cat playing piano on a city street at night.")
    ap.add_argument("--num-frames", type=int, default=49)
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--cache-steps", default="8,16,24,32,40", help="denoising steps whose features to snapshot")
    ap.add_argument("--save-layers", default="0,7,15,23,29")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="artifacts/video_dit_cache/capture")
    ap.add_argument("--max-positions", type=int, default=8192, help="subsample N positions to cap tensor size")
    args = ap.parse_args(argv)

    import torch
    from diffusers import DiffusionPipeline

    os.makedirs(args.out_dir, exist_ok=True)
    cache_steps = set(_parse_ints(args.cache_steps))
    save_layers = set(_parse_ints(args.save_layers))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        raise SystemExit("[REQUIRES GPU] no CUDA device; this capture is pod-only.")

    torch.manual_seed(args.seed)
    torch.cuda.reset_peak_memory_stats()

    pipe = DiffusionPipeline.from_pretrained(args.model, torch_dtype=torch.bfloat16).to(device)
    transformer = getattr(pipe, "transformer", None)
    if transformer is None:
        raise SystemExit(f"[FAIL] {args.model} has no .transformer (need a DiT pipeline).")

    # locate the stack of transformer blocks (diffusers convention)
    blocks = None
    for attr in ("transformer_blocks", "blocks"):
        if hasattr(transformer, attr):
            blocks = getattr(transformer, attr)
            break
    if blocks is None:
        raise SystemExit("[FAIL] could not find transformer_blocks on the model.")

    # step counter advanced by a scheduler hook
    state = {"step": -1}
    captured = {}  # (cache_object, layer) -> list of (N,C) cpu tensors across cache-steps

    def _sub(x):
        # x: (..., N, C) -> (N, C) float cpu, positions subsampled to cap size
        t = x.detach()
        if t.ndim == 3:  # (B, N, C) -> take batch 0
            t = t[0]
        t = t.reshape(-1, t.shape[-1]).float().cpu()
        if t.shape[0] > args.max_positions:
            idx = torch.linspace(0, t.shape[0] - 1, args.max_positions).long()
            t = t[idx]
        return t

    def make_hook(layer_idx):
        def hook(module, inputs, output):
            if state["step"] not in cache_steps or layer_idx not in save_layers:
                return
            out = output[0] if isinstance(output, (tuple, list)) else output
            try:
                captured.setdefault(("hidden_states", layer_idx), []).append(_sub(out))
            except Exception:
                pass
        return hook

    handles = [blk.register_forward_hook(make_hook(i)) for i, blk in enumerate(blocks)]

    # advance the step counter via a scheduler-step wrapper
    orig_step = pipe.scheduler.step
    def step_wrap(*a, **k):
        state["step"] += 1
        return orig_step(*a, **k)
    pipe.scheduler.step = step_wrap

    t0 = time.time()
    gen = torch.Generator(device=device).manual_seed(args.seed)
    _ = pipe(args.prompt, num_frames=args.num_frames, num_inference_steps=args.steps, generator=gen)
    elapsed = time.time() - t0
    for h in handles:
        h.remove()

    # ---- save canonical (T,N,C) per (object, layer); derive feature_delta ----
    saved = []
    for (obj, layer), snaps in captured.items():
        if len(snaps) < 1:
            continue
        T = min(len(s.shape) and s.shape[0] for s in snaps) if False else min(s.shape[0] for s in snaps)
        N = min(s.shape[0] for s in snaps)
        C = snaps[0].shape[1]
        stack = torch.stack([s[:N, :C] for s in snaps])  # (T,N,C)
        meta = {"cache_object": obj, "layer": layer, "dtype": "bf16",
                "step_indices": sorted(cache_steps), "meta": {"model": args.model,
                "num_frames": args.num_frames, "steps": args.steps, "prompt": args.prompt}}
        path = os.path.join(args.out_dir, f"{obj}_layer{layer}.pt")
        torch.save({**meta, "tensor": stack}, path)
        saved.append(path)
        # derived feature_delta = consecutive-step difference (what a delta-cache stores)
        if stack.shape[0] >= 2:
            delta = stack[1:] - stack[:-1]
            dmeta = dict(meta); dmeta["cache_object"] = "feature_delta"
            dpath = os.path.join(args.out_dir, f"feature_delta_layer{layer}.pt")
            torch.save({**dmeta, "tensor": delta}, dpath)
            saved.append(dpath)

    # ---- Stage-B systems counters (what this level can measure; deeper profiling flagged) ----
    peak_hbm = torch.cuda.max_memory_allocated() / 1e9
    persistent_cache_bytes = sum(
        os.path.getsize(p) for p in saved
    )  # proxy: bytes of captured snapshots (NOT live pipeline cache residency)
    systems = {
        "model": args.model,
        "peak_hbm_gb": round(peak_hbm, 3),
        "captured_snapshot_bytes": persistent_cache_bytes,
        "end_to_end_generation_s": round(elapsed, 2),
        # the following need a real profiler / cache-enabled pipeline instrumentation:
        "persistent_cache_hbm_gb": "REQUIRES GPU PROFILER (live cache residency; use torch mem-snapshot or nsys)",
        "hbm_bandwidth_util": "REQUIRES GPU PROFILER (nsys/ncu)",
        "cache_read_write_bytes": "REQUIRES GPU PROFILER",
        "pcie_nvlink_transfer_bytes": "REQUIRES GPU PROFILER",
        "compress_decompress_latency_ms": "REQUIRES FUSED-KERNEL PROTOTYPE (emulated cost != fused-kernel)",
        "max_frames_resolution_batch": "REQUIRES SWEEP (OOM-boundary search)",
        "cache_hit_reuse_rate": "REQUIRES cache-enabled pipeline instrumentation",
        "note": "captured_snapshot_bytes is a capture-side proxy, NOT live pipeline cache residency.",
    }
    json.dump(systems, open(os.path.join(args.out_dir, "systems_metrics.json"), "w"), indent=2)
    print(f"[ok] saved {len(saved)} cache-object tensors -> {args.out_dir}")
    print(json.dumps(systems, indent=2))
    print("Next (CPU): python analyze_cache_compressibility.py --cache", args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
