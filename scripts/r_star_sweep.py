#!/usr/bin/env python3
"""
scripts/r_star_sweep.py — Text-FSCS r* measurement harness.

EXPERIMENTAL. This script is code-complete but has not been executed in
this session (no GPU, no Mistral weights in the dev environment). It
requires an A100-80GB, mistralai/Mistral-7B-v0.3 weights, and the
dependencies listed in requirements.txt (plus transformers, datasets,
bitsandbytes, accelerate).

What this script does
---------------------
1. Loads mistralai/Mistral-7B-v0.3 via MistralFSCSWrapper, installing
   FSCS gated decoder layers on every decoder layer of the backbone.
   The backbone is frozen; only the FSCS control-plane parameters
   (per-band τ and α) are loaded in eval mode.

2. Establishes a BASELINE PPL on WikiText-2 (validation split) by
   running the same model with all FSCS gating effectively disabled
   (τ set to 0.99 across all bands so π ≈ 0 for every token). This
   gives us the "all full attention" reference.

3. Sweeps the gating threshold τ across a grid, running eval at each
   operating point and recording:
       - perplexity (ppl)
       - delta vs baseline (Δppl)
       - average fraction of tokens routed to the coarse branch
         (averaged over layers and tokens)
       - wall-clock eval latency (seconds)
       - Mode 2 (soft blend) vs Mode 3 (hard route) comparison at the
         same τ, to measure the soft-to-hard gap (§6.2)

4. Writes results to results/fscs_rstar/results.json. This file is the
   input to a later plotting script that produces the Δppl vs r curve
   from §5.2 of the spec.

5. Applies the GO / NO-GO criteria from §5.5:
       GO:       r* > 30% with Δppl < 0.5% and wall-clock speedup > 15%
       MARGINAL: r* = 15–30% or wall-clock speedup 8–15%
       NO-GO:    r* < 15% or Δppl > 1% at any gating level
   and writes the verdict to the results file.

Important caveat
----------------
Because we compute BOTH the full and coarse branches in every layer
(see the class docstring in symbolu/fscs/mistral_gated_layer.py), the
wall-clock numbers from this script do NOT reflect the savings that
would be realized under a production Mode 3 path where only one branch
runs per token. This script measures the QUALITY CEILING — it tells
you what Δppl you pay at each r, not what latency you save. A separate
compute-savings script would require implementing conditional per-token
compute dispatch, which is deferred.

Usage
-----
    python scripts/r_star_sweep.py \\
        --model mistralai/Mistral-7B-v0.3 \\
        --quantize 4bit \\
        --eval-dataset wikitext2 \\
        --max-eval-samples 256 \\
        --output results/fscs_rstar/results.json

    # For a faster smoke run on a small sample:
    python scripts/r_star_sweep.py --smoke

    # For Mode 2 vs Mode 3 comparison only at a fixed τ:
    python scripts/r_star_sweep.py --single-tau 0.5

See docs/FSCS_IMPLEMENTATION_STATUS.md for full scope and known gaps.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Text-FSCS r* measurement harness on frozen Mistral.",
    )
    p.add_argument(
        "--model", type=str, default="mistralai/Mistral-7B-v0.3",
        help="HuggingFace model ID for the Mistral backbone.",
    )
    p.add_argument(
        "--quantize", type=str, default="4bit",
        choices=["none", "bf16", "fp16", "4bit", "8bit"],
        help=(
            "Backbone quantization. '4bit'/'8bit' use bitsandbytes and "
            "require torch>=2.5 with recent transformers versions. "
            "'bf16'/'fp16'/'none' skip quantization and load in the "
            "chosen dtype (use these if your torch is older than 2.5; "
            "Mistral-7B fits in ~14GB at bf16)."
        ),
    )
    p.add_argument(
        "--eval-dataset", type=str, default="wikitext2",
        choices=["wikitext2", "wikitext103"],
        help="Eval dataset for PPL measurement.",
    )
    p.add_argument(
        "--max-eval-samples", type=int, default=256,
        help="Number of eval samples to use for PPL measurement per sweep point.",
    )
    p.add_argument(
        "--seq-len", type=int, default=2048,
        help="Sequence length for eval. Mistral-7B supports up to 32K+.",
    )
    p.add_argument(
        "--coarse-window", type=int, default=256,
        help="Sliding window size for the coarse attention branch.",
    )
    p.add_argument(
        "--tau-sweep", type=float, nargs="+",
        default=[0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20],
        help="Sweep values for the coherence gate threshold τ.",
    )
    p.add_argument(
        "--single-tau", type=float, default=None,
        help="If set, only run a single τ point (useful for quick comparison).",
    )
    # Per-band τ and layer-cap calibration overrides. Added after the
    # first frozen-Mistral r* sweep showed gate_frac ≈ 0 across the
    # spec's original τ defaults. These flags let an operator sweep
    # calibration without editing FSCSConfig directly.
    p.add_argument(
        "--tau-global", type=float, default=None,
        help=(
            "Override FSCSConfig.tau_global (initial per-band threshold "
            "for the global band). Lower = easier to route. Default set "
            "in FSCSConfig."
        ),
    )
    p.add_argument(
        "--tau-mid", type=float, default=None,
        help="Override FSCSConfig.tau_mid.",
    )
    p.add_argument(
        "--tau-local", type=float, default=None,
        help="Override FSCSConfig.tau_local.",
    )
    p.add_argument(
        "--beta-max-inference", type=float, default=None,
        help=(
            "Override FSCSConfig.beta_max_inference (layer cap at "
            "inference time). Spec presets: 0.3 train / 0.5 safe / "
            "0.7 aggressive. Higher = more tokens routed per layer."
        ),
    )
    p.add_argument(
        "--alpha-sharpness", type=float, default=None,
        help=(
            "Override FSCSConfig.alpha_sharpness (sigmoid sharpness α). "
            "Higher = sharper threshold transition. Default 10."
        ),
    )
    p.add_argument(
        "--coherence-gamma", type=float, default=None,
        help=(
            "Override FSCSConfig.gamma (output-delta sensitivity in "
            "coherence metric). Lower = wider coherence distribution. "
            "V1 spec: 5.0, V3 Mistral-tuned: 1.0."
        ),
    )
    p.add_argument(
        "--coherence-delta", type=float, default=None,
        help=(
            "Override FSCSConfig.delta_residual (residual-delta sensitivity "
            "in coherence metric). V1 spec: 3.0, V3 Mistral-tuned: 0.5."
        ),
    )
    p.add_argument(
        "--hard-threshold", type=float, default=None,
        help=(
            "Override FSCSConfig.hard_route_threshold (θ in Mode 3). "
            "V1 spec: 0.7, V3 Mistral-tuned: 0.5."
        ),
    )
    p.add_argument(
        "--eval-batch-size", type=int, default=1,
        help=(
            "Mini-batch size for the eval forward pass. Default 1 "
            "(safe anywhere). At bf16 on A100-80GB a batch of 8 "
            "uses ~32GB and roughly 5x the throughput of batch=1; "
            "batch=16 uses ~45GB and ~8x the throughput. Higher "
            "batch sizes produce identical PPL values to the extent "
            "that floating-point associativity holds."
        ),
    )
    p.add_argument(
        "--output", type=str,
        default="results/fscs_rstar/results.json",
        help="Output path for the results JSON.",
    )
    p.add_argument(
        "--smoke", action="store_true",
        help="Smoke mode: tiny sample count, one τ point, no hard-route pass.",
    )
    return p.parse_args()


def load_eval_tokens(
    tokenizer: Any,
    dataset: str,
    max_samples: int,
    seq_len: int,
) -> Any:
    """Load and tokenize the eval dataset into fixed-length chunks."""
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise ImportError(
            "datasets package required for eval. Install with: pip install datasets"
        ) from e

    if dataset == "wikitext2":
        ds = load_dataset("wikitext", "wikitext-2-raw-v1", split="validation")
    else:
        ds = load_dataset("wikitext", "wikitext-103-raw-v1", split="validation")

    # Concatenate all non-empty lines and tokenize
    full_text = "\n\n".join(s for s in ds["text"] if s.strip())
    enc = tokenizer(full_text, return_tensors="pt", add_special_tokens=False)
    input_ids = enc.input_ids[0]  # [total_len]

    # Chunk into sequences of length seq_len
    n = (input_ids.shape[0] // seq_len) * seq_len
    if n == 0:
        raise RuntimeError("Eval dataset is shorter than one sequence length.")
    input_ids = input_ids[:n].view(-1, seq_len)

    # Cap at max_samples
    if input_ids.shape[0] > max_samples:
        input_ids = input_ids[:max_samples]
    return input_ids


def eval_perplexity(
    wrapper: Any,
    eval_ids: Any,
    device: Any,
    label: str = "",
    batch_size: int = 1,
) -> Tuple[float, float, float]:
    """
    Run PPL evaluation on the wrapped model.

    Evaluates in mini-batches of ``batch_size`` sequences. On a 7B
    model at seq_len=2048 in bf16, batch_size=1 uses ~14GB VRAM and
    leaves an A100-80GB ~83% idle. Bumping batch_size dramatically
    speeds up the sweep without changing the measurement.

    Returns:
        (ppl, wall_clock_seconds, mean_gate_fraction_across_layers)
    """
    import torch
    import torch.nn.functional as F

    wrapper.eval()
    total_loss = 0.0
    total_tokens = 0
    gate_fractions: List[float] = []

    n_samples = eval_ids.shape[0]
    start = time.perf_counter()
    with torch.no_grad():
        for i in range(0, n_samples, batch_size):
            j = min(i + batch_size, n_samples)
            batch = eval_ids[i:j].to(device)
            out = wrapper(input_ids=batch)
            logits = out["logits"]  # [B, N, V]

            # Shift for next-token loss
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = batch[..., 1:].contiguous()
            loss = F.cross_entropy(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1),
                reduction="sum",
            )
            total_loss += loss.item()
            total_tokens += shift_labels.numel()
            gate_fractions.append(out.get("mean_gate_fraction", 0.0))

    wall = time.perf_counter() - start
    avg_loss = total_loss / max(1, total_tokens)
    ppl = math.exp(avg_loss)
    mean_gf = sum(gate_fractions) / max(1, len(gate_fractions))

    print(f"  [{label}] ppl={ppl:.4f}  gate_frac={mean_gf:.3f}  wall={wall:.2f}s")
    return ppl, wall, mean_gf


def apply_tau(wrapper: Any, tau: float) -> None:
    """Set all three bands to the same τ value for a sweep point."""
    wrapper.set_band_thresholds(
        tau_global=tau,
        tau_mid=tau,
        tau_local=tau,
    )


def apply_tau_per_band(
    wrapper: Any,
    tau_global: float,
    tau_mid: float,
    tau_local: float,
) -> None:
    """For the eventual per-band variant of the sweep."""
    wrapper.set_band_thresholds(tau_global, tau_mid, tau_local)


def run_sweep(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Run the full r* sweep and return the results dict.
    Torch, transformers, and the Mistral weights must be available.
    """
    # Lazy imports so that running `python scripts/r_star_sweep.py --help` works
    # in environments without torch installed.
    import torch
    from symbolu_training.training.unified.mistral_fscs_wrapper import (
        MistralFSCSWrapper,
    )
    from symbolu.fscs.core import FSCSConfig

    print("=" * 72)
    print("Text-FSCS r* measurement sweep")
    print("=" * 72)
    print(f"Model:             {args.model}")
    print(f"Quantize:          {args.quantize}")
    print(f"Eval dataset:      {args.eval_dataset}")
    print(f"Max eval samples:  {args.max_eval_samples}")
    print(f"Seq len:           {args.seq_len}")
    print(f"Coarse window:     {args.coarse_window}")
    print(f"τ sweep:           {args.tau_sweep}")
    print("=" * 72)

    # Construct the FSCS config, applying any CLI calibration overrides.
    # The defaults inside FSCSConfig have already been tuned by the V2
    # calibration pass after the first frozen-Mistral sweep; these
    # overrides let an operator probe alternative calibrations without
    # re-editing the config module.
    _cfg_kwargs: Dict[str, Any] = {
        "coarse_window": args.coarse_window,
        "use_hard_routing": False,  # Mode 2 (soft) first
    }
    if args.tau_global is not None:
        _cfg_kwargs["tau_global"] = args.tau_global
    if args.tau_mid is not None:
        _cfg_kwargs["tau_mid"] = args.tau_mid
    if args.tau_local is not None:
        _cfg_kwargs["tau_local"] = args.tau_local
    if args.beta_max_inference is not None:
        _cfg_kwargs["beta_max_inference"] = args.beta_max_inference
    if args.alpha_sharpness is not None:
        _cfg_kwargs["alpha_sharpness"] = args.alpha_sharpness
    if args.coherence_gamma is not None:
        _cfg_kwargs["gamma"] = args.coherence_gamma
    if args.coherence_delta is not None:
        _cfg_kwargs["delta_residual"] = args.coherence_delta
    if args.hard_threshold is not None:
        _cfg_kwargs["hard_route_threshold"] = args.hard_threshold
    cfg = FSCSConfig(**_cfg_kwargs)

    # Log the calibration for the record. These lines appear in the
    # run banner so results.json files are self-documenting.
    print(f"FSCS τ calibration: global={cfg.tau_global} "
          f"mid={cfg.tau_mid} local={cfg.tau_local}")
    print(f"FSCS α sharpness:   {cfg.alpha_sharpness}")
    print(f"FSCS β_max (infer): {cfg.beta_max_inference}")
    print(f"FSCS γ/δ/ρ:         {cfg.gamma}/{cfg.delta_residual}/{cfg.ema_decay}")
    print(f"FSCS hard θ:        {cfg.hard_route_threshold}")

    print("\n[1/4] Loading Mistral backbone + installing FSCS gated layers…")
    # Normalize --quantize flag values:
    #   "none" or "bf16"  -> None (load in bf16 via torch_dtype, no bnb)
    #   "4bit" or "8bit"  -> forwarded to MistralFSCSWrapper for bnb config
    _quant_arg = args.quantize.lower()
    if _quant_arg in ("none", "bf16", "fp16"):
        _quant_value = None
    else:
        _quant_value = _quant_arg
    wrapper = MistralFSCSWrapper(
        model_name=args.model,
        quantize=_quant_value,
        fscs_cfg=cfg,
    )
    device = next(wrapper.backbone.parameters()).device
    print(f"    Backbone device: {device}")
    print(f"    Number of gated layers: {len(wrapper.gated_layers)}")
    print(f"    FSCS trainable params: {wrapper.fscs_trainable_parameters()}")

    print("\n[2/4] Tokenizing eval set…")
    eval_ids = load_eval_tokens(
        wrapper.tokenizer,
        args.eval_dataset,
        args.max_eval_samples,
        args.seq_len,
    )
    print(f"    Eval shape: {tuple(eval_ids.shape)}")

    # ---- Baseline: τ = 0.99 effectively disables gating --------------
    print(f"\n[3/4] Baseline run (all full attention, τ=0.99, "
          f"eval_batch_size={args.eval_batch_size})…")
    apply_tau(wrapper, 0.99)
    baseline_ppl, baseline_wall, baseline_gf = eval_perplexity(
        wrapper, eval_ids, device, label="baseline",
        batch_size=args.eval_batch_size,
    )

    # ---- Sweep τ -----------------------------------------------------
    print("\n[4/4] τ sweep…")
    sweep_points: List[Dict[str, Any]] = []
    tau_values = [args.single_tau] if args.single_tau is not None else args.tau_sweep
    if args.smoke:
        tau_values = [0.5]

    for tau in tau_values:
        # Mode 2 (soft)
        wrapper.set_hard_routing(False)
        apply_tau(wrapper, tau)
        ppl_soft, wall_soft, gf_soft = eval_perplexity(
            wrapper, eval_ids, device, label=f"τ={tau:.2f} soft",
            batch_size=args.eval_batch_size,
        )

        # Mode 3 (hard) at the same τ — measures soft-to-hard gap
        if not args.smoke:
            wrapper.set_hard_routing(True)
            apply_tau(wrapper, tau)
            ppl_hard, wall_hard, gf_hard = eval_perplexity(
                wrapper, eval_ids, device, label=f"τ={tau:.2f} hard",
                batch_size=args.eval_batch_size,
            )
        else:
            ppl_hard, wall_hard, gf_hard = (ppl_soft, wall_soft, gf_soft)

        delta_soft = (ppl_soft - baseline_ppl) / baseline_ppl
        delta_hard = (ppl_hard - baseline_ppl) / baseline_ppl
        soft_to_hard = ppl_hard - ppl_soft

        sweep_points.append({
            "tau": tau,
            "soft": {
                "ppl": ppl_soft,
                "delta_pct": delta_soft * 100,
                "gate_fraction": gf_soft,
                "wall_seconds": wall_soft,
            },
            "hard": {
                "ppl": ppl_hard,
                "delta_pct": delta_hard * 100,
                "gate_fraction": gf_hard,
                "wall_seconds": wall_hard,
            },
            "soft_to_hard_delta_ppl": soft_to_hard,
        })

    # Restore wrapper state
    wrapper.set_hard_routing(False)

    # ---- Derive r* and GO / NO-GO verdict -----------------------------
    r_star = derive_r_star(sweep_points, threshold_pct=0.5)
    verdict = derive_verdict(sweep_points, baseline_wall, r_star)

    results = {
        "config": {
            "model": args.model,
            "quantize": args.quantize,
            "eval_dataset": args.eval_dataset,
            "max_eval_samples": args.max_eval_samples,
            "seq_len": args.seq_len,
            "coarse_window": args.coarse_window,
            "num_layers": len(wrapper.gated_layers),
            "fscs_trainable_params": wrapper.fscs_trainable_parameters(),
        },
        "baseline": {
            "ppl": baseline_ppl,
            "wall_seconds": baseline_wall,
            "gate_fraction": baseline_gf,
        },
        "sweep": sweep_points,
        "r_star": r_star,
        "verdict": verdict,
    }
    return results


def derive_r_star(
    sweep: List[Dict[str, Any]],
    threshold_pct: float = 0.5,
) -> Optional[float]:
    """
    r* = highest gate fraction such that Δppl (soft) < threshold_pct%.

    Returns None if no sweep point satisfies the threshold.
    """
    best: Optional[float] = None
    for point in sweep:
        if point["soft"]["delta_pct"] < threshold_pct:
            gf = point["soft"]["gate_fraction"]
            if best is None or gf > best:
                best = gf
    return best


def derive_verdict(
    sweep: List[Dict[str, Any]],
    baseline_wall: float,
    r_star: Optional[float],
) -> Dict[str, Any]:
    """Apply the §5.5 GO / MARGINAL / NO-GO criteria."""
    # Best wall-clock speedup seen in the sweep at any Δppl < 0.5% point
    best_speedup = 0.0
    for point in sweep:
        if point["soft"]["delta_pct"] < 0.5:
            wall_ratio = baseline_wall / max(1e-6, point["soft"]["wall_seconds"])
            speedup_pct = (wall_ratio - 1) * 100
            if speedup_pct > best_speedup:
                best_speedup = speedup_pct

    # Worst-case delta at any gating level
    worst_delta = max(p["soft"]["delta_pct"] for p in sweep) if sweep else 0.0

    if r_star is None:
        label = "NO-GO (no point with Δppl < 0.5%)"
    elif r_star < 0.15 or worst_delta > 1.0:
        label = "NO-GO"
    elif r_star > 0.30 and best_speedup > 15.0:
        label = "GO"
    elif r_star >= 0.15 or best_speedup >= 8.0:
        label = "MARGINAL"
    else:
        label = "NO-GO"

    return {
        "label": label,
        "r_star": r_star,
        "best_wall_speedup_pct": best_speedup,
        "worst_delta_pct": worst_delta,
        "notes": (
            "Wall-clock speedup measured here does NOT reflect production "
            "Mode 3 savings because this harness computes both full and "
            "coarse branches at every layer. See docs/FSCS_IMPLEMENTATION_STATUS.md."
        ),
    }


def main() -> int:
    args = parse_args()

    # Friendly guard: if torch or transformers isn't available, fail fast
    # with a useful message instead of a cryptic ImportError halfway through.
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError as e:
        print(
            "[r_star_sweep] torch and transformers are required to run "
            "this script. Install them in a venv with GPU support before "
            f"executing. Original error: {e}",
            file=sys.stderr,
        )
        return 2

    results = run_sweep(args)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 72)
    print("Sweep complete.")
    print(f"Results written to: {out_path}")
    print(f"Verdict:            {results['verdict']['label']}")
    print(f"r*:                 {results['r_star']}")
    print(f"Best wall speedup:  {results['verdict']['best_wall_speedup_pct']:.1f}%")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
