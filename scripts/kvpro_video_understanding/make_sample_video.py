"""Generate a small SYNTHETIC test clip for the KVPro video-understanding SMOKE test.

Purpose: prove the capture->analyze pipeline runs end-to-end with zero downloads. It is a real,
decodable .mp4 with genuine visual variation (moving shapes on a shifting gradient), so Qwen2.5-VL
produces real visual tokens. BUT: for a TRUSTWORTHY feasibility read, use a NATURAL video from your
target domain (moderation clip, meeting recording, bodycam, sports, etc.) — synthetic patterns can
have different KV structure than natural scenes. This is a plumbing check, not the experiment.

Usage (pod):  pip install imageio imageio-ffmpeg numpy
              python make_sample_video.py --out /workspace/sample.mp4 --frames 64
"""
from __future__ import annotations

import argparse
import math


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make a synthetic smoke-test video (NOT for the real read)")
    ap.add_argument("--out", default="artifacts/kvpro_video/sample_smoke.mp4")
    ap.add_argument("--frames", type=int, default=64)
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--fps", type=int, default=8)
    args = ap.parse_args(argv)

    import numpy as np
    try:
        import imageio.v2 as imageio
    except Exception as e:
        raise SystemExit(f"[FAIL] needs imageio + imageio-ffmpeg: {e}\n  pip install imageio imageio-ffmpeg")

    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    S = args.size
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    frames = []
    for t in range(args.frames):
        ph = t / max(1, args.frames)
        # shifting gradient background
        bg_r = (0.5 + 0.5 * np.sin(2 * math.pi * (xx / S + ph)))
        bg_g = (0.5 + 0.5 * np.sin(2 * math.pi * (yy / S + 2 * ph)))
        bg_b = (0.5 + 0.5 * np.cos(2 * math.pi * (xx / S - yy / S + ph)))
        img = np.stack([bg_r, bg_g, bg_b], -1)
        # a moving bright square + a moving dark disc (real objects to attend to)
        cx = int((0.5 + 0.35 * math.cos(2 * math.pi * ph)) * S)
        cy = int((0.5 + 0.35 * math.sin(2 * math.pi * ph)) * S)
        img[max(0, cy-20):cy+20, max(0, cx-20):cx+20] = [1.0, 1.0, 1.0]
        dx = int((0.5 + 0.3 * math.sin(3 * math.pi * ph)) * S)
        dy = int((0.5 + 0.3 * math.cos(3 * math.pi * ph)) * S)
        disc = ((xx - dx) ** 2 + (yy - dy) ** 2) < (18 ** 2)
        img[disc] = [0.05, 0.05, 0.1]
        frames.append((np.clip(img, 0, 1) * 255).astype(np.uint8))

    imageio.mimwrite(args.out, frames, fps=args.fps, codec="libx264", quality=8)
    print(f"wrote {args.out}  ({args.frames} frames, {S}x{S}, {args.fps} fps)")
    print("NOTE: synthetic smoke clip — for a trustworthy feasibility read use a natural domain video.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
