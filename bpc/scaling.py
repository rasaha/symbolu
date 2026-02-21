#!/usr/bin/env python3
"""
Scaling-Law Experiments
========================

Run BPC vs baseline at multiple compute points.
Fit loss vs compute: L(C) = a*C^{-alpha} + b
Report alpha with confidence intervals (bootstrap).

Axis: fixed tokens, vary params (30M, 60M, 120M, 200M)
For each point, run A0 (baseline) and A2 (BPC).
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)


@dataclass
class ScalingConfig:
    """Configuration for scaling-law experiments."""

    # Model size axis: (embed_dim, num_layers, num_heads)
    model_sizes: List[Tuple[int, int, int]] = None

    # Training
    max_steps: int = 10000
    batch_size: int = 8
    seq_len: int = 256
    learning_rate: float = 3e-4
    dataset: str = "wikitext103"
    seed: int = 42

    # BPC
    target_layer_ratio: float = 0.5  # target_layer = num_layers * ratio
    subspace_rank: int = 32
    lambda_rollout: float = 0.1
    lambda_cf: float = 0.05

    # Bootstrap
    n_bootstrap: int = 1000

    # Output
    output_dir: str = "results/scaling"
    device: str = "auto"

    def __post_init__(self):
        if self.model_sizes is None:
            self.model_sizes = [
                (256, 6, 4),     # ~30M params
                (512, 8, 8),     # ~60M params
                (768, 12, 12),   # ~127M params
                (1024, 12, 16),  # ~200M params
            ]


def count_model_params(embed_dim: int, num_layers: int, num_heads: int, vocab_size: int = 50257) -> int:
    """Estimate total parameter count for a standard transformer."""
    ff_dim = 4 * embed_dim
    # Embeddings
    params = vocab_size * embed_dim  # token embed
    params += 8192 * embed_dim  # position embed (max_seq_len)
    # Per layer: attn (QKV + O) + FF (up + down) + 2 layernorms
    per_layer = (4 * embed_dim * embed_dim) + (2 * embed_dim * ff_dim) + (4 * embed_dim)
    params += per_layer * num_layers
    # Final norm + lm_head (tied)
    params += 2 * embed_dim
    return params


def fit_scaling_law(
    compute_points: np.ndarray,
    loss_values: np.ndarray,
    n_bootstrap: int = 1000,
) -> Dict[str, Any]:
    """
    Fit L(C) = a * C^{-alpha} + b using log-log linear regression.

    For L - b = a * C^{-alpha}:
    log(L - b) = log(a) - alpha * log(C)

    We approximate by fitting log(L) = c0 - alpha * log(C) directly
    (valid when b is small relative to L).

    Returns alpha with bootstrap confidence intervals.
    """
    log_C = np.log(compute_points)
    log_L = np.log(loss_values)

    # Fit: log_L = c0 + c1 * log_C (c1 = -alpha)
    def _fit(x, y):
        A = np.vstack([x, np.ones(len(x))]).T
        result = np.linalg.lstsq(A, y, rcond=None)
        slope, intercept = result[0]
        return -slope, np.exp(intercept)  # alpha, a

    alpha, a = _fit(log_C, log_L)

    # Bootstrap confidence intervals
    alphas_boot = []
    n = len(log_C)
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        alpha_b, _ = _fit(log_C[idx], log_L[idx])
        alphas_boot.append(alpha_b)

    alphas_boot = np.array(alphas_boot)
    alpha_ci_low = np.percentile(alphas_boot, 2.5)
    alpha_ci_high = np.percentile(alphas_boot, 97.5)

    # Compute residuals
    predicted = a * compute_points ** (-alpha)
    residuals = loss_values - predicted
    rmse = np.sqrt(np.mean(residuals ** 2))

    return {
        "alpha": float(alpha),
        "a": float(a),
        "alpha_ci_low": float(alpha_ci_low),
        "alpha_ci_high": float(alpha_ci_high),
        "rmse": float(rmse),
        "r_squared": float(1 - np.var(residuals) / np.var(loss_values)),
    }


class ScalingExperiment:
    """Run scaling-law experiments comparing baseline and BPC."""

    def __init__(self, config: ScalingConfig):
        self.config = config
        if config.device == "auto":
            self.device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )
        else:
            self.device = torch.device(config.device)

        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_single_point(
        self,
        embed_dim: int,
        num_layers: int,
        num_heads: int,
        ablation: str,
    ) -> Dict[str, Any]:
        """Run training for a single compute point."""
        from bpc.losses import BPCConfig
        from bpc.trainer import TrainConfig, run_training

        target_layer = max(1, int(num_layers * self.config.target_layer_ratio))

        bpc_config = BPCConfig(
            target_layer=target_layer,
            subspace_rank=min(self.config.subspace_rank, embed_dim // 4),
            lambda_rollout=self.config.lambda_rollout,
            lambda_cf=self.config.lambda_cf,
        )

        n_params = count_model_params(embed_dim, num_layers, num_heads)
        run_name = f"{ablation}_d{embed_dim}_L{num_layers}"

        train_config = TrainConfig(
            ablation=ablation,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            max_steps=self.config.max_steps,
            batch_size=self.config.batch_size,
            seq_len=self.config.seq_len,
            learning_rate=self.config.learning_rate,
            dataset=self.config.dataset,
            bpc=bpc_config,
            output_dir=str(self.output_dir / run_name),
            device=self.config.device,
            seed=self.config.seed,
        )

        logger.info(f"Running {run_name}: {n_params:,} params")
        val_metrics = run_training(train_config)

        return {
            "ablation": ablation,
            "embed_dim": embed_dim,
            "num_layers": num_layers,
            "num_heads": num_heads,
            "n_params": n_params,
            "compute": n_params * self.config.max_steps * self.config.batch_size * self.config.seq_len,
            **val_metrics,
        }

    def run_all(self) -> Dict[str, Any]:
        """Run all scaling experiments."""
        logger.info("=== Scaling-Law Experiments ===")

        baseline_results = []
        bpc_results = []

        for embed_dim, num_layers, num_heads in self.config.model_sizes:
            n_params = count_model_params(embed_dim, num_layers, num_heads)
            logger.info(f"\n--- Compute point: d={embed_dim}, L={num_layers} ({n_params:,} params) ---")

            # Baseline (A0)
            base_result = self.run_single_point(embed_dim, num_layers, num_heads, "A0")
            baseline_results.append(base_result)

            # BPC (A2)
            bpc_result = self.run_single_point(embed_dim, num_layers, num_heads, "A2")
            bpc_results.append(bpc_result)

        # Fit scaling laws
        base_compute = np.array([r["compute"] for r in baseline_results], dtype=np.float64)
        base_loss = np.array([r["val_loss"] for r in baseline_results], dtype=np.float64)
        bpc_compute = np.array([r["compute"] for r in bpc_results], dtype=np.float64)
        bpc_loss = np.array([r["val_loss"] for r in bpc_results], dtype=np.float64)

        fit_baseline = fit_scaling_law(base_compute, base_loss, self.config.n_bootstrap)
        fit_bpc = fit_scaling_law(bpc_compute, bpc_loss, self.config.n_bootstrap)

        summary = {
            "baseline_results": baseline_results,
            "bpc_results": bpc_results,
            "baseline_fit": fit_baseline,
            "bpc_fit": fit_bpc,
            "alpha_baseline": fit_baseline["alpha"],
            "alpha_bpc": fit_bpc["alpha"],
            "alpha_baseline_ci": [fit_baseline["alpha_ci_low"], fit_baseline["alpha_ci_high"]],
            "alpha_bpc_ci": [fit_bpc["alpha_ci_low"], fit_bpc["alpha_ci_high"]],
        }

        # Interpretation
        alpha_diff = fit_bpc["alpha"] - fit_baseline["alpha"]
        ci_overlap = fit_bpc["alpha_ci_low"] <= fit_baseline["alpha_ci_high"]

        summary["interpretation"] = {
            "alpha_difference": alpha_diff,
            "ci_overlap": ci_overlap,
            "conclusion": (
                "Scaling exponent improves (alpha_BPC > alpha_baseline) with non-overlapping CIs"
                if alpha_diff > 0 and not ci_overlap
                else "No significant scaling advantage detected"
            ),
        }

        # Print
        print("\n" + "=" * 70)
        print("  SCALING-LAW RESULTS")
        print("=" * 70)
        print(f"  Baseline alpha: {fit_baseline['alpha']:.4f} [{fit_baseline['alpha_ci_low']:.4f}, {fit_baseline['alpha_ci_high']:.4f}]")
        print(f"  BPC alpha:      {fit_bpc['alpha']:.4f} [{fit_bpc['alpha_ci_low']:.4f}, {fit_bpc['alpha_ci_high']:.4f}]")
        print(f"  Alpha diff:     {alpha_diff:.4f}")
        print(f"  CIs overlap:    {ci_overlap}")
        print(f"  Conclusion:     {summary['interpretation']['conclusion']}")

        # Save
        save_path = self.output_dir / "scaling_results.json"
        with open(save_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info(f"Results saved to {save_path}")

        # Plots
        self._generate_plots(summary)

        return summary

    def _generate_plots(self, summary: Dict[str, Any]):
        """Generate scaling-law plots."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("  matplotlib not available, skipping scaling plots")
            return

        fig, ax = plt.subplots(figsize=(10, 7))

        # Baseline
        base = summary["baseline_results"]
        bpc = summary["bpc_results"]

        base_c = [r["compute"] for r in base]
        base_l = [r["val_loss"] for r in base]
        bpc_c = [r["compute"] for r in bpc]
        bpc_l = [r["val_loss"] for r in bpc]

        ax.scatter(base_c, base_l, color="blue", s=100, zorder=5, label="Baseline (A0)")
        ax.scatter(bpc_c, bpc_l, color="red", s=100, zorder=5, label="BPC (A2)")

        # Fit lines
        fit_b = summary["baseline_fit"]
        fit_p = summary["bpc_fit"]

        c_range = np.logspace(
            np.log10(min(base_c + bpc_c)) * 0.9,
            np.log10(max(base_c + bpc_c)) * 1.1,
            100,
        )

        pred_base = fit_b["a"] * c_range ** (-fit_b["alpha"])
        pred_bpc = fit_p["a"] * c_range ** (-fit_p["alpha"])

        ax.plot(c_range, pred_base, "b--", alpha=0.7,
                label=f"Baseline fit (alpha={fit_b['alpha']:.3f})")
        ax.plot(c_range, pred_bpc, "r--", alpha=0.7,
                label=f"BPC fit (alpha={fit_p['alpha']:.3f})")

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Compute (params * tokens)", fontsize=12)
        ax.set_ylabel("Validation Loss", fontsize=12)
        ax.set_title("Scaling Law: Baseline vs BPC", fontsize=14)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)

        # Annotate alpha values
        ax.text(
            0.02, 0.02,
            f"alpha_base={fit_b['alpha']:.4f} [{fit_b['alpha_ci_low']:.4f}, {fit_b['alpha_ci_high']:.4f}]\n"
            f"alpha_BPC={fit_p['alpha']:.4f} [{fit_p['alpha_ci_low']:.4f}, {fit_p['alpha_ci_high']:.4f}]",
            transform=ax.transAxes,
            fontsize=9,
            verticalalignment="bottom",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

        plt.tight_layout()
        plt.savefig(self.output_dir / "scaling_law.png", dpi=150, bbox_inches="tight")
        plt.close()

        print(f"  Scaling plot saved to {self.output_dir / 'scaling_law.png'}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="BPC Scaling-Law Experiments")
    parser.add_argument("--max_steps", type=int, default=10000)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--seq_len", type=int, default=256)
    parser.add_argument("--output_dir", type=str, default="results/scaling")
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    config = ScalingConfig(
        max_steps=args.max_steps,
        batch_size=args.batch_size,
        seq_len=args.seq_len,
        output_dir=args.output_dir,
        device=args.device,
        seed=args.seed,
    )

    experiment = ScalingExperiment(config)
    experiment.run_all()


if __name__ == "__main__":
    main()
