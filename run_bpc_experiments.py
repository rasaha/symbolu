#!/usr/bin/env python3
"""
BPC Experiment Suite Runner
=============================

Orchestrates the full BPC experiment pipeline:
  1. Train baseline (A0)
  2. Train all ablations (A1-A7)
  3. Run evaluation suite
  4. Run activation patching
  5. Run scaling-law experiments
  6. Generate final report

Usage:
    # Full suite
    python run_bpc_experiments.py --mode full --max_steps 50000

    # Quick smoke test
    python run_bpc_experiments.py --mode smoke --max_steps 100

    # Only ablations
    python run_bpc_experiments.py --mode ablations --max_steps 50000

    # Only evaluation (assumes checkpoints exist)
    python run_bpc_experiments.py --mode eval --checkpoint_dir runs/bpc

    # Only scaling
    python run_bpc_experiments.py --mode scaling --max_steps 10000

    # Only activation patching
    python run_bpc_experiments.py --mode patching \
        --checkpoint runs/bpc/A2/checkpoints/best.pt \
        --subspace runs/bpc/A2/subspace/U_r.pt
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logger = logging.getLogger(__name__)


def run_ablations(args):
    """Train all ablation conditions."""
    from bpc.losses import BPCConfig
    from bpc.trainer import TrainConfig, run_training

    ablations = ["A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    if args.ablations:
        ablations = args.ablations

    results = {}
    bpc_logit_std = None  # for A1 scale matching

    for ablation in ablations:
        logger.info(f"\n{'='*60}")
        logger.info(f"  Training ablation: {ablation}")
        logger.info(f"{'='*60}")

        bpc_config = BPCConfig(
            target_layer=args.target_layer,
            subspace_rank=args.subspace_rank,
            rollout_steps=args.rollout_steps,
            lambda_rollout=args.lambda_rollout,
            lambda_cf=args.lambda_cf,
        )

        config = TrainConfig(
            ablation=ablation,
            max_steps=args.max_steps,
            batch_size=args.batch_size,
            seq_len=args.seq_len,
            embed_dim=args.embed_dim,
            num_layers=args.num_layers,
            num_heads=args.num_heads,
            learning_rate=args.learning_rate,
            dataset=args.dataset,
            bpc=bpc_config,
            output_dir=f"{args.output_dir}/{ablation}",
            device=args.device,
            seed=args.seed,
        )

        # Scale matching for A1
        if ablation == "A1" and bpc_logit_std is not None:
            config.scale_match_target_std = bpc_logit_std

        val_metrics = run_training(config)
        results[ablation] = val_metrics

        # Capture BPC logit std for scale matching
        if ablation == "A2":
            bpc_logit_std = val_metrics.get("val_logit_std")

    return results


def run_evaluation(args):
    """Run evaluation suite."""
    from eval.bpc_suite import EvalConfig, BPCEvaluator

    config = EvalConfig(
        checkpoint_dir=args.output_dir,
        output_dir=f"{args.output_dir}/eval_results",
        num_eval_batches=args.eval_batches,
        device=args.device,
    )

    evaluator = BPCEvaluator(config)
    return evaluator.run_full_suite()


def run_patching(args):
    """Run activation patching."""
    from mechinterp.patch_belief_subspace import PatchConfig, BeliefPatcher

    checkpoint = args.checkpoint or f"{args.output_dir}/A2/checkpoints/best.pt"
    subspace = args.subspace or f"{args.output_dir}/A2/subspace/U_r.pt"

    config = PatchConfig(
        checkpoint_path=checkpoint,
        subspace_path=subspace,
        target_layer=args.target_layer,
        num_pairs=args.num_pairs,
        output_dir=f"{args.output_dir}/patching_results",
        device=args.device,
    )

    patcher = BeliefPatcher(config)
    return patcher.run_experiment()


def run_scaling(args):
    """Run scaling-law experiments."""
    from bpc.scaling import ScalingConfig, ScalingExperiment

    config = ScalingConfig(
        max_steps=args.max_steps,
        batch_size=args.batch_size,
        seq_len=args.seq_len,
        output_dir=f"{args.output_dir}/scaling",
        device=args.device,
        seed=args.seed,
    )

    experiment = ScalingExperiment(config)
    return experiment.run_all()


def generate_report(all_results: dict, output_dir: str):
    """Generate final interpretation report."""
    report_path = Path(output_dir) / "REPORT.md"

    lines = [
        "# BPC Experiment Report",
        "",
        "## Result Interpretation",
        "",
    ]

    # Check ablation results
    ablation_results = all_results.get("ablations", {})
    eval_results = all_results.get("evaluation", {})
    patching_results = all_results.get("patching", {})
    scaling_results = all_results.get("scaling", {})

    # 1. Scale-matching check
    lines.append("### 1. Anti-Calibration Check")
    if "calibration" in eval_results:
        cal = eval_results["calibration"]
        if isinstance(cal, dict) and cal.get("calibration_passed"):
            lines.append("- Scale-matched baseline logit std matches BPC within 1%. PASS.")
        else:
            lines.append("- Scale matching did NOT pass. Results may reflect calibration artifacts.")
    else:
        lines.append("- Calibration data not available.")

    # 2. MLP head baseline
    lines.append("")
    lines.append("### 2. MLP Head Control")
    a2 = eval_results.get("A2", {})
    a3 = eval_results.get("A3", {})
    if a2 and a3:
        ppl_diff = a3.get("val_ppl", 0) - a2.get("val_ppl", 0)
        if ppl_diff > 0:
            lines.append(
                f"- BPC (A2) PPL={a2.get('val_ppl', '?'):.2f} vs MLP head (A3) PPL={a3.get('val_ppl', '?'):.2f}")
            lines.append("- BPC outperforms param-matched MLP head. Effect is NOT a trivial head change.")
        else:
            lines.append("- MLP head baseline matches or beats BPC. Effect may be trivial.")
    else:
        lines.append("- MLP head comparison not available.")

    # 3. Random subspace control
    lines.append("")
    lines.append("### 3. Random Subspace Control")
    a5 = eval_results.get("A5", {})
    if a2 and a5:
        ppl_bpc = a2.get("val_ppl", 0)
        ppl_rand = a5.get("val_ppl", 0)
        lines.append(f"- BPC with PCA basis: PPL={ppl_bpc:.2f}")
        lines.append(f"- BPC with random basis: PPL={ppl_rand:.2f}")
        if ppl_bpc < ppl_rand:
            lines.append("- PCA basis outperforms random. Belief subspace is structured.")
        else:
            lines.append("- Random basis matches PCA. Subspace may not be meaningful.")
    else:
        lines.append("- Random subspace comparison not available.")

    # 4. Activation patching
    lines.append("")
    lines.append("### 4. Causal Validation (Activation Patching)")
    if patching_results:
        sr = patching_results.get("patch_success_rate", 0)
        belief_kl = patching_results.get("belief", {}).get("kl_mean", 0)
        random_kl = patching_results.get("random", {}).get("kl_mean", 0)
        noise_kl = patching_results.get("noise", {}).get("kl_mean", 0)

        lines.append(f"- Belief patch success rate: {sr:.2%}")
        lines.append(f"- Mean KL: belief={belief_kl:.4f}, random={random_kl:.4f}, noise={noise_kl:.4f}")

        if sr > 0.6 and belief_kl > random_kl * 1.5:
            lines.append("- Belief subspace shows CAUSAL control over model behavior.")
        else:
            lines.append("- Belief patching does not show strong causal effect.")
    else:
        lines.append("- Activation patching not available.")

    # 5. Scaling laws
    lines.append("")
    lines.append("### 5. Scaling Laws")
    if scaling_results:
        alpha_b = scaling_results.get("alpha_baseline", 0)
        alpha_p = scaling_results.get("alpha_bpc", 0)
        ci_b = scaling_results.get("alpha_baseline_ci", [0, 0])
        ci_p = scaling_results.get("alpha_bpc_ci", [0, 0])
        interp = scaling_results.get("interpretation", {}).get("conclusion", "")

        lines.append(f"- alpha_baseline = {alpha_b:.4f} [{ci_b[0]:.4f}, {ci_b[1]:.4f}]")
        lines.append(f"- alpha_BPC = {alpha_p:.4f} [{ci_p[0]:.4f}, {ci_p[1]:.4f}]")
        lines.append(f"- {interp}")
    else:
        lines.append("- Scaling experiments not available.")

    # Final conclusion
    lines.append("")
    lines.append("### Final Conclusion")
    lines.append("")
    lines.append(
        "If improvements vanish under scale-matching or MLP baseline, "
        "the effect is NOT novel (calibration artifact). "
        "If belief-patching shows causal control AND scaling exponent improves, "
        "conclude genuine structural effect from BPC training."
    )

    report = "\n".join(lines)
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"Report saved to {report_path}")
    print(report)


def main():
    parser = argparse.ArgumentParser(description="BPC Experiment Suite")
    parser.add_argument("--mode", type=str, default="smoke",
                        choices=["full", "smoke", "ablations", "eval", "patching", "scaling"])

    # Model
    parser.add_argument("--embed_dim", type=int, default=768)
    parser.add_argument("--num_layers", type=int, default=12)
    parser.add_argument("--num_heads", type=int, default=12)

    # Training
    parser.add_argument("--max_steps", type=int, default=50000)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--seq_len", type=int, default=256)
    parser.add_argument("--learning_rate", type=float, default=3e-4)
    parser.add_argument("--dataset", type=str, default="wikitext103")
    parser.add_argument("--seed", type=int, default=42)

    # BPC
    parser.add_argument("--target_layer", type=int, default=6)
    parser.add_argument("--subspace_rank", type=int, default=32)
    parser.add_argument("--rollout_steps", type=int, default=4)
    parser.add_argument("--lambda_rollout", type=float, default=0.1)
    parser.add_argument("--lambda_cf", type=float, default=0.05)

    # Ablations
    parser.add_argument("--ablations", nargs="+", default=None)

    # Eval
    parser.add_argument("--eval_batches", type=int, default=50)

    # Patching
    parser.add_argument("--checkpoint", type=str, default=None)
    parser.add_argument("--subspace", type=str, default=None)
    parser.add_argument("--num_pairs", type=int, default=100)

    # Output
    parser.add_argument("--output_dir", type=str, default="runs/bpc")
    parser.add_argument("--device", type=str, default="auto")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Smoke test overrides
    if args.mode == "smoke":
        args.max_steps = 100
        args.batch_size = 2
        args.seq_len = 64
        args.embed_dim = 128
        args.num_layers = 4
        args.num_heads = 4
        args.target_layer = 2
        args.subspace_rank = 8
        args.eval_batches = 5
        args.num_pairs = 10
        args.ablations = ["A0", "A2"]
        args.output_dir = "runs/bpc_smoke"
        logger.info("=== SMOKE TEST MODE ===")

    all_results = {}
    start_time = time.time()

    try:
        if args.mode in ("full", "smoke", "ablations"):
            logger.info("\n" + "=" * 70)
            logger.info("  PHASE 1: TRAINING ABLATIONS")
            logger.info("=" * 70)
            all_results["ablations"] = run_ablations(args)

        if args.mode in ("full", "smoke", "eval"):
            logger.info("\n" + "=" * 70)
            logger.info("  PHASE 2: EVALUATION SUITE")
            logger.info("=" * 70)
            all_results["evaluation"] = run_evaluation(args)

        if args.mode in ("full", "patching"):
            logger.info("\n" + "=" * 70)
            logger.info("  PHASE 3: ACTIVATION PATCHING")
            logger.info("=" * 70)
            all_results["patching"] = run_patching(args)

        if args.mode in ("full", "scaling"):
            logger.info("\n" + "=" * 70)
            logger.info("  PHASE 4: SCALING-LAW EXPERIMENTS")
            logger.info("=" * 70)
            all_results["scaling"] = run_scaling(args)

    except Exception as e:
        logger.error(f"Experiment failed: {e}", exc_info=True)
        all_results["error"] = str(e)

    elapsed = time.time() - start_time
    all_results["elapsed_seconds"] = elapsed

    # Save all results
    results_path = Path(args.output_dir) / "all_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Generate report
    generate_report(all_results, args.output_dir)

    logger.info(f"\nTotal time: {elapsed:.0f}s")


if __name__ == "__main__":
    main()
