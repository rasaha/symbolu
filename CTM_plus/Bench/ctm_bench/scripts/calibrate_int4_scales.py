"""Offline calibration of INT4 KV-cache scales (audit Path #6).

GPTQ/AWQ-style: run a small calibration set through the model, capture
K and V tensors at every layer, compute static per-(layer, head,
head_dim) scales for K (and per-(layer, head) for V) that approximate
the dynamic per-block scales the current implementation computes at
inference. Save to a ``.pt`` file that ``INT4PerChannelCache`` can
load via ``calibration_path=...``.

Hypothesis: static calibrated scales reduce per-input variability in
the quantization landscape, which can improve quality on out-of-
distribution prefills. Published evidence on Qwen-family suggests
calibration can push perplexity from ~1.02× to ~1.01× and tighten
MMLU delta from ~-0.9pt to ~-0.5pt.

CLI
---

  python -m ctm_bench.scripts.calibrate_int4_scales \\
      --model Qwen/Qwen2.5-7B-Instruct \\
      --dtype float16 --device cuda \\
      --num-prompts 100 \\
      --asymmetric \\
      --output-path /tmp/qwen25_7b_calibration.pt

Output format
-------------

A torch ``.pt`` file containing a dict:

  {
      <layer_idx>: {
          "k_scale":  (1, num_kv_heads, head_dim)  float32
          "k_offset": (1, num_kv_heads, head_dim)  float32  # asymmetric only
          "v_scale":  (1, num_kv_heads, 1)          float32
          "v_offset": (1, num_kv_heads, 1)          float32  # asymmetric only
      },
      ...
  }

For symmetric calibration, ``k_offset`` and ``v_offset`` are omitted.

Loading
-------

::

    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache
    cache = INT4PerChannelCache(
        asymmetric=True,
        calibration_path="/tmp/qwen25_7b_calibration.pt",
    )
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Sequence

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


LOG = logging.getLogger("calibrate_int4")


CALIBRATION_PROMPTS: List[str] = [
    "The quick brown fox jumps over the lazy dog.",
    "Climate change refers to long-term shifts in temperatures and weather patterns.",
    "Quantum entanglement is a phenomenon where particles remain connected.",
    "The Roman Empire reached its greatest extent under the emperor Trajan.",
    "Photosynthesis is the process by which plants convert sunlight into energy.",
    "Machine learning algorithms can identify patterns in large datasets.",
    "Shakespeare wrote 37 plays and 154 sonnets during his lifetime.",
    "The Pacific Ocean is the largest and deepest of the Earth's oceans.",
    "DNA contains the genetic instructions for the development of organisms.",
    "The theory of relativity was developed by Albert Einstein in the early 1900s.",
    "Recursion is a programming technique where a function calls itself.",
    "The mitochondria is often called the powerhouse of the cell.",
    "The French Revolution began in 1789 and ended in 1799.",
    "Black holes are regions of spacetime where gravity is extremely strong.",
    "The water cycle includes evaporation, condensation, and precipitation.",
    "Polymorphism in object-oriented programming allows methods to do different things.",
    "Mount Everest is the highest mountain in the world at 8,849 meters.",
    "The human brain contains approximately 86 billion neurons.",
    "Renewable energy sources include solar, wind, and hydroelectric power.",
    "The Great Wall of China was built over many centuries to protect against invasions.",
]


def _check_versions() -> None:
    try:
        import transformers  # type: ignore
    except ImportError:
        raise SystemExit("transformers not installed; run: pip install 'transformers>=5.0'")
    try:
        import torch  # type: ignore
    except ImportError:
        raise SystemExit("torch not installed")
    t_major = int(transformers.__version__.split(".")[0])
    if t_major < 5:
        raise SystemExit(
            f"transformers {transformers.__version__} < 5.0; "
            f"DynamicCache.layers[i].keys API required"
        )
    pt_major, pt_minor = (int(s) for s in torch.__version__.split(".")[:2])
    if (pt_major, pt_minor) < (2, 5):
        raise SystemExit(
            f"torch {torch.__version__} < 2.5; transformers 5.x MoE "
            f"integration needs >= 2.5"
        )


def _expand_prompts(base: List[str], target_count: int) -> List[str]:
    """If the user requests more prompts than we have hand-curated,
    repeat with random shuffling so calibration sees variety."""
    import random
    rng = random.Random(2026)
    if target_count <= len(base):
        return base[:target_count]
    out = list(base)
    while len(out) < target_count:
        chunk = list(base)
        rng.shuffle(chunk)
        out.extend(chunk)
    return out[:target_count]


def calibrate(
    *,
    model,
    tokenizer,
    prompts: Sequence[str],
    asymmetric: bool,
    bits: int = 4,
) -> Dict[int, Dict[str, "torch.Tensor"]]:
    """Run ``prompts`` through ``model``, capture K and V from
    ``past_key_values`` at each layer, and compute aggregate per-layer
    scales.

    Returns a dict keyed by layer index. Each value is itself a dict
    with at least ``k_scale``; ``k_offset`` / ``v_scale`` /
    ``v_offset`` are added depending on asymmetric mode.
    """
    import torch

    qmax = (1 << (bits - 1)) - 1
    asym_div = float((1 << bits) - 1)
    sym_zero_shift = 1 << (bits - 1)

    # Accumulators keyed by layer_idx. We store running max/min/maxabs
    # (depending on mode) per-(H, D) for K and per-(H,) for V.
    k_running_max: Dict[int, "torch.Tensor"] = {}    # asymmetric
    k_running_min: Dict[int, "torch.Tensor"] = {}    # asymmetric
    k_running_max_abs: Dict[int, "torch.Tensor"] = {}  # symmetric
    v_running_max: Dict[int, "torch.Tensor"] = {}
    v_running_min: Dict[int, "torch.Tensor"] = {}
    v_running_max_abs: Dict[int, "torch.Tensor"] = {}

    model.eval()
    for prompt_idx, prompt in enumerate(prompts):
        if prompt_idx % 10 == 0:
            LOG.info("calibration prompt %d/%d", prompt_idx + 1, len(prompts))
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model(**inputs, use_cache=True)
        past = out.past_key_values
        # Iterate layers. transformers 5.x exposes past.layers[i].keys /.values
        n_layers = (
            len(past.layers) if hasattr(past, "layers") else len(past)
        )
        for li in range(n_layers):
            if hasattr(past, "layers"):
                k = past.layers[li].keys  # (B, H, S, D)
                v = past.layers[li].values
            else:
                k, v = past[li]
            # Reshape to vLLM block layout (S, H, D) per-batch and
            # aggregate along S (seq).
            # Use float32 internally for accumulator stability.
            k_f = k[0].transpose(0, 1).contiguous().to(torch.float32)  # (S, H, D)
            v_f = v[0].transpose(0, 1).contiguous().to(torch.float32)

            # K: per-(H, D) aggregates across S
            k_per_hd_max = k_f.amax(dim=0, keepdim=True)  # (1, H, D)
            k_per_hd_min = k_f.amin(dim=0, keepdim=True)
            k_per_hd_max_abs = k_f.abs().amax(dim=0, keepdim=True)

            # V: per-(H,) aggregates across S and D
            # (S, H, D) → (H,) via abs.amax over (S, D)
            v_per_h_max = v_f.amax(dim=(0, 2), keepdim=False).view(1, -1, 1)
            v_per_h_min = v_f.amin(dim=(0, 2), keepdim=False).view(1, -1, 1)
            v_per_h_max_abs = v_f.abs().amax(dim=(0, 2), keepdim=False).view(1, -1, 1)

            for key, src, store in (
                ("k_max", k_per_hd_max, k_running_max),
                ("k_min", k_per_hd_min, k_running_min),
                ("k_max_abs", k_per_hd_max_abs, k_running_max_abs),
                ("v_max", v_per_h_max, v_running_max),
                ("v_min", v_per_h_min, v_running_min),
                ("v_max_abs", v_per_h_max_abs, v_running_max_abs),
            ):
                if li in store:
                    if "max" in key and "abs" not in key:
                        store[li] = torch.maximum(store[li], src.cpu())
                    elif "min" in key:
                        store[li] = torch.minimum(store[li], src.cpu())
                    else:  # max_abs
                        store[li] = torch.maximum(store[li], src.cpu())
                else:
                    store[li] = src.cpu().clone()

    # Now derive scales/offsets per layer.
    LOG.info("Computing per-layer scales from accumulated statistics...")
    calibration: Dict[int, Dict[str, "torch.Tensor"]] = {}
    for li in sorted(k_running_max_abs.keys()):
        entry: Dict[str, "torch.Tensor"] = {}
        if asymmetric:
            x_max = k_running_max[li]
            x_min = k_running_min[li]
            scale = ((x_max - x_min) / asym_div).clamp(min=1e-8)
            offset = x_min + sym_zero_shift * scale
            entry["k_scale"] = scale
            entry["k_offset"] = offset
            v_max = v_running_max[li]
            v_min = v_running_min[li]
            v_scale = ((v_max - v_min) / asym_div).clamp(min=1e-8)
            v_offset = v_min + sym_zero_shift * v_scale
            entry["v_scale"] = v_scale
            entry["v_offset"] = v_offset
        else:
            k_scale = (k_running_max_abs[li] / float(qmax)).clamp(min=1e-8)
            v_scale = (v_running_max_abs[li] / float(qmax)).clamp(min=1e-8)
            entry["k_scale"] = k_scale
            entry["v_scale"] = v_scale
        calibration[li] = entry

    return calibration


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="calibrate_int4_scales",
        description="Offline INT4 KV-cache calibration (audit Path #6).",
    )
    parser.add_argument("--model", required=True,
                        help="HF model id, e.g. Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--dtype", default="float16",
                        choices=["float16", "bfloat16", "float32"])
    parser.add_argument("--device", default="auto")
    parser.add_argument("--num-prompts", type=int, default=100,
                        help="Calibration set size. More = better static scales, slower run.")
    parser.add_argument("--asymmetric", action="store_true",
                        help="Calibrate scale + offset (asymmetric); default is symmetric.")
    parser.add_argument("--bits", type=int, default=4,
                        help="Target bit width (must match the inference config that loads this calibration).")
    parser.add_argument("--output-path", type=Path, required=True)
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _check_versions()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    LOG.info("Loading %s (dtype=%s, device=%s)", args.model, args.dtype, args.device)
    torch_dtype = getattr(torch, args.dtype)
    device_map = args.device if args.device != "auto" else "auto"
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch_dtype, device_map=device_map,
    )
    model.eval()

    prompts = _expand_prompts(CALIBRATION_PROMPTS, args.num_prompts)
    LOG.info(
        "Calibrating with %d prompts (asymmetric=%s, bits=%d)",
        len(prompts), args.asymmetric, args.bits,
    )

    calibration = calibrate(
        model=model, tokenizer=tokenizer, prompts=prompts,
        asymmetric=args.asymmetric, bits=args.bits,
    )

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(calibration, args.output_path)
    LOG.info("Wrote calibration to %s (%d layers)", args.output_path, len(calibration))

    print()
    print("=" * 60)
    print(f"INT{args.bits} calibration — {args.model}")
    print("=" * 60)
    print(f"  num_prompts:  {len(prompts)}")
    print(f"  asymmetric:   {args.asymmetric}")
    print(f"  num_layers:   {len(calibration)}")
    print(f"  output:       {args.output_path}")
    print()
    print("  Per-layer scale ranges (first 3 layers, K):")
    for li in sorted(calibration.keys())[:3]:
        s = calibration[li]["k_scale"]
        print(
            f"    layer {li}: k_scale shape={tuple(s.shape)} "
            f"min={s.min().item():.6f} max={s.max().item():.6f} mean={s.mean().item():.6f}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
