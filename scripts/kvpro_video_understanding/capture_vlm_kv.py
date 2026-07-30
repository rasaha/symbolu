"""KVPro × video-understanding — KV CAPTURE (POD-ONLY, needs GPU + Qwen2.5-VL + a video).

Feeds a video + a question into Qwen2.5-VL, and captures the decoder KV cache separated into
VISUAL vs TEXT token positions, per layer, for analyze_kv_outliers.py. Also measures how the KV cache
GROWS with clip length (the memory-bound-ness where a KVPro density win would live).

Why Qwen2.5-VL: its language backbone IS Qwen2.5 — the family our KVPro tooling already targets — so
this tests "does KVPro carry over when much of the context is visual tokens?" rather than a new model.

Usage (pod):
  pip install -U transformers accelerate qwen-vl-utils decord
  python capture_vlm_kv.py --model Qwen/Qwen2.5-VL-7B-Instruct --video /path/clip.mp4 \
      --frames 8,32,128 --question "Describe what happens in this video." \
      --out-dir artifacts/kvpro_video/capture --save-layers 0,7,15,23,27
Then (CPU):
  python analyze_kv_outliers.py --kv artifacts/kvpro_video/capture/frames128
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(description="Capture Qwen2.5-VL KV over video (pod-only)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-VL-7B-Instruct")
    ap.add_argument("--video", required=True, help="path to a video file")
    ap.add_argument("--frames", default="8,32,128", help="frame counts to sweep (KV grows with these)")
    ap.add_argument("--question", default="Describe what happens in this video.")
    ap.add_argument("--save-layers", default="0,7,15,23,27", help="layer indices to dump for analysis")
    ap.add_argument("--out-dir", default="artifacts/kvpro_video/capture")
    ap.add_argument("--max-pixels", type=int, default=360 * 420, help="cap per-frame tokens (VRAM)")
    args = ap.parse_args(argv)

    import torch
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    try:
        from qwen_vl_utils import process_vision_info
    except Exception as e:
        print(f"[FAIL] qwen-vl-utils missing: {e}. pip install qwen-vl-utils", file=sys.stderr)
        return 3
    if not torch.cuda.is_available():
        print("[FAIL] no CUDA device — capture is GPU-only.", file=sys.stderr)
        return 2

    save_layers = [int(x) for x in args.save_layers.split(",")]
    frame_counts = [int(x) for x in args.frames.split(",")]
    os.makedirs(args.out_dir, exist_ok=True)

    print(f"loading {args.model} ...")
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map="cuda")
    proc = AutoProcessor.from_pretrained(args.model, max_pixels=args.max_pixels)
    cfg = model.config
    vis_ids = {getattr(cfg, "image_token_id", -10), getattr(cfg, "video_token_id", -11)}
    print("visual token ids:", vis_ids)

    growth = []
    for nf in frame_counts:
        messages = [{"role": "user", "content": [
            {"type": "video", "video": args.video, "nframes": nf, "max_pixels": args.max_pixels},
            {"type": "text", "text": args.question}]}]
        text = proc.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = proc(text=[text], images=image_inputs, videos=video_inputs,
                      padding=True, return_tensors="pt").to("cuda")

        torch.cuda.reset_peak_memory_stats()
        with torch.no_grad():
            out = model(**inputs, use_cache=True)
        pkv = out.past_key_values                      # per-layer (B, H_kv, S, D)
        ids = inputs["input_ids"][0]
        tt = torch.zeros_like(ids, dtype=torch.int64)
        for vid in vis_ids:
            tt |= (ids == vid).to(torch.int64)
        S = ids.shape[0]; n_vis = int(tt.sum().item()); n_txt = S - n_vis
        n_layers = len(pkv)
        # KV bytes at bf16: 2(K,V) * n_layers * S * H_kv * D * 2 bytes
        k0 = pkv[0][0]
        H_kv, D = k0.shape[1], k0.shape[3]
        kv_bytes = 2 * n_layers * S * H_kv * D * 2
        peak = torch.cuda.max_memory_allocated()

        sub = os.path.join(args.out_dir, f"frames{nf}")
        os.makedirs(sub, exist_ok=True)
        for L in save_layers:
            if L >= n_layers:
                continue
            K = pkv[L][0][0].transpose(0, 1).contiguous().float().cpu()   # (S, H_kv, D)
            torch.save({"k": K, "token_type": tt.cpu(), "layer": L,
                        "model": args.model, "frames": nf}, os.path.join(sub, f"layer{L:02d}.pt"))
        row = {"frames": nf, "seq_len": S, "visual_tokens": n_vis, "text_tokens": n_txt,
               "visual_frac": round(n_vis / S, 3), "n_layers": n_layers, "H_kv": H_kv, "head_dim": D,
               "kv_cache_bytes_bf16": kv_bytes, "kv_cache_MiB": round(kv_bytes / 2**20, 1),
               "peak_gpu_bytes": peak}
        growth.append(row)
        print(f"  frames={nf}: seq={S} (visual {n_vis}={row['visual_frac']*100:.0f}%) "
              f"KV={row['kv_cache_MiB']} MiB  peak={peak/2**20:.0f} MiB")

    json.dump({"model": args.model, "video": args.video, "growth": growth,
               "note": "KV cache grows with clip length; visual tokens dominate — the KVPro density lever."},
              open(os.path.join(args.out_dir, "kv_growth.json"), "w"), indent=2)
    print(f"\nwrote per-layer KV + kv_growth.json to {args.out_dir}")
    print("next (CPU):  python analyze_kv_outliers.py --kv "
          f"{os.path.join(args.out_dir, 'frames'+str(frame_counts[-1]))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
