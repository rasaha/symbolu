#!/usr/bin/env python3
"""
BPC Evaluation Suite
======================

Comprehensive evaluation with anti-calibration ablations.

Core metrics:
  1) Validation CE loss / PPL
  2) Logit std, mean, entropy
  3) Cross-coherence proxy (cosine(z_t, z_{t+k}))
  4) Counterfactual sensitivity (||z - z_cf|| distribution)
  5) Random-subspace control

Ablation matrix (A0-A7):
  A0: Baseline CE
  A1: Baseline CE + scale-matched logits
  A2: CE + BPC (full)
  A3: CE + MLP head baseline
  A4: CE + projection-only
  A5: CE + BPC with random U_r
  A6: CE + BPC with lambda_cf=0
  A7: CE + BPC with lambda_rollout=0

Calibration checks:
  - logit std within 1% for scale-matched baseline
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@dataclass
class EvalConfig:
    """Configuration for evaluation suite."""
    checkpoint_dir: str = "runs/bpc"
    ablations: List[str] = None  # default: all A0..A7
    subspace_path: Optional[str] = None
    target_layer: int = 6
    subspace_rank: int = 32
    rollout_steps: int = 4
    num_eval_batches: int = 50
    num_coherence_samples: int = 200
    num_cf_samples: int = 200
    batch_size: int = 8
    seq_len: int = 256
    dataset: str = "wikitext103"
    output_dir: str = "results/bpc_eval"
    device: str = "auto"

    def __post_init__(self):
        if self.ablations is None:
            self.ablations = [f"A{i}" for i in range(8)]


class BPCEvaluator:
    """Runs the full BPC evaluation suite."""

    def __init__(self, config: EvalConfig):
        self.config = config
        if config.device == "auto":
            self.device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )
        else:
            self.device = torch.device(config.device)

        self.results: Dict[str, Dict[str, Any]] = {}

        # Output
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_model(self, checkpoint_path: str) -> Tuple[nn.Module, dict]:
        """Load model from checkpoint."""
        from symbolu.phase_transformer import StandardTransformer

        ckpt = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
        model_config = ckpt.get("model_config", {
            "vocab_size": 50257, "embed_dim": 768,
            "num_layers": 12, "num_heads": 12,
        })
        model = StandardTransformer(**model_config)
        model.load_state_dict(ckpt["model_state_dict"], strict=False)
        model.to(self.device).eval()
        return model, ckpt

    def load_subspace(self, path: Optional[str] = None) -> Optional[torch.Tensor]:
        """Load PCA subspace."""
        if path and Path(path).exists():
            data = torch.load(path, map_location=self.device, weights_only=True)
            return data["U_r"], data.get("mean", None)
        return None, None

    @torch.no_grad()
    def compute_val_metrics(
        self, model: nn.Module, dataloader, scale_factor: float = 1.0
    ) -> Dict[str, float]:
        """Compute validation CE loss, PPL, logit stats."""
        model.eval()
        total_loss = 0.0
        total_tokens = 0
        logit_stds = []
        logit_means = []
        entropies = []

        for i, batch in enumerate(dataloader):
            if i >= self.config.num_eval_batches:
                break

            input_ids, targets = batch
            input_ids = input_ids.to(self.device)
            targets = targets.to(self.device)

            outputs = model(input_ids)
            logits = outputs["logits"] * scale_factor
            B, T, V = logits.shape

            loss = F.cross_entropy(
                logits.reshape(-1, V), targets.reshape(-1), ignore_index=-100
            )
            total_loss += loss.item() * B * T
            total_tokens += B * T

            logit_stds.append(logits.std().item())
            logit_means.append(logits.mean().item())
            probs = F.softmax(logits, dim=-1)
            ent = -(probs * torch.log(probs + 1e-9)).sum(-1).mean().item()
            entropies.append(ent)

        avg_loss = total_loss / max(1, total_tokens)
        return {
            "val_loss": avg_loss,
            "val_ppl": math.exp(min(avg_loss, 20)),
            "logit_std": float(np.mean(logit_stds)),
            "logit_mean": float(np.mean(logit_means)),
            "entropy": float(np.mean(entropies)),
            "normalized_entropy": float(np.mean(entropies)) / math.log(50257),
        }

    @torch.no_grad()
    def compute_cross_coherence(
        self, model: nn.Module, U_r: torch.Tensor, h_mean: torch.Tensor,
        dataloader, K: int = 4, layer: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Cross-coherence proxy: cosine(z_t, z_{t+k}) averaged over k.

        Measures whether belief coordinates maintain coherence over short windows.
        """
        model.eval()
        if layer is None:
            layer = self.config.target_layer

        all_cosines = {k: [] for k in range(1, K + 1)}
        count = 0

        for i, batch in enumerate(dataloader):
            if count >= self.config.num_coherence_samples:
                break

            input_ids = batch[0].to(self.device)
            outputs = model(input_ids, extract_layers=[layer])
            hidden = outputs["hidden_states"][0]  # [B, T, D]

            # Project to belief coordinates
            centered = hidden - h_mean
            z = centered @ U_r  # [B, T, r]

            B, T, r = z.shape

            # Compute cosine similarities at different lags
            for k in range(1, K + 1):
                if T <= k:
                    continue
                z_t = z[:, :-k, :]  # [B, T-k, r]
                z_tk = z[:, k:, :]  # [B, T-k, r]

                cos = F.cosine_similarity(z_t, z_tk, dim=-1)  # [B, T-k]
                all_cosines[k].extend(cos.reshape(-1).cpu().tolist())

            count += B

        result = {}
        for k in range(1, K + 1):
            if all_cosines[k]:
                vals = np.array(all_cosines[k])
                result[f"cross_coherence_k{k}_mean"] = float(vals.mean())
                result[f"cross_coherence_k{k}_std"] = float(vals.std())
            else:
                result[f"cross_coherence_k{k}_mean"] = 0.0
                result[f"cross_coherence_k{k}_std"] = 0.0

        return result

    @torch.no_grad()
    def compute_cf_sensitivity(
        self, model: nn.Module, U_r: torch.Tensor, h_mean: torch.Tensor,
        dataloader, vocab_size: int = 50257, layer: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Counterfactual sensitivity: distribution of ||z - z_cf||.
        """
        from bpc.counterfactual import CFConfig, CounterfactualPerturber

        model.eval()
        if layer is None:
            layer = self.config.target_layer

        perturber = CounterfactualPerturber(CFConfig(), vocab_size)

        z_dists = []
        res_dists = []
        count = 0

        for i, batch in enumerate(dataloader):
            if count >= self.config.num_cf_samples:
                break

            input_ids = batch[0].to(self.device)
            outputs = model(input_ids, extract_layers=[layer])
            hidden = outputs["hidden_states"][0]

            cf_ids, cf_positions, _ = perturber.perturb(input_ids)
            cf_outputs = model(cf_ids, extract_layers=[layer])
            cf_hidden = cf_outputs["hidden_states"][0]

            for pos in cf_positions:
                pos = pos.item()
                if pos >= hidden.shape[1]:
                    continue

                h_orig = hidden[:, pos, :]
                h_cf = cf_hidden[:, pos, :]

                z_orig = (h_orig - h_mean) @ U_r
                z_cf = (h_cf - h_mean) @ U_r
                z_dist = (z_orig - z_cf).pow(2).sum(-1).sqrt()
                z_dists.extend(z_dist.cpu().tolist())

                # Residual
                proj_orig = z_orig @ U_r.T + h_mean
                proj_cf = z_cf @ U_r.T + h_mean
                res_orig = h_orig - proj_orig
                res_cf = h_cf - proj_cf
                res_dist = (res_orig - res_cf).pow(2).sum(-1).sqrt()
                res_dists.extend(res_dist.cpu().tolist())

            count += input_ids.shape[0]

        z_dists = np.array(z_dists) if z_dists else np.array([0.0])
        res_dists = np.array(res_dists) if res_dists else np.array([0.0])

        return {
            "cf_z_dist_mean": float(z_dists.mean()),
            "cf_z_dist_std": float(z_dists.std()),
            "cf_z_dist_median": float(np.median(z_dists)),
            "cf_z_dist_p95": float(np.percentile(z_dists, 95)),
            "cf_res_dist_mean": float(res_dists.mean()),
            "cf_res_dist_std": float(res_dists.std()),
            "cf_z_dists": z_dists.tolist()[:500],  # truncate for JSON
            "cf_res_dists": res_dists.tolist()[:500],
        }

    @torch.no_grad()
    def compute_random_subspace_control(
        self, model: nn.Module, embed_dim: int, dataloader,
        vocab_size: int = 50257, layer: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run same metrics with random orthonormal U_r."""
        r = self.config.subspace_rank
        Q, _ = torch.linalg.qr(torch.randn(embed_dim, r, device=self.device))
        h_mean = torch.zeros(embed_dim, device=self.device)

        coherence = self.compute_cross_coherence(
            model, Q, h_mean, dataloader, layer=layer,
        )
        cf_sens = self.compute_cf_sensitivity(
            model, Q, h_mean, dataloader, vocab_size=vocab_size, layer=layer,
        )

        return {
            f"random_{k}": v
            for metrics in [coherence, cf_sens]
            for k, v in metrics.items()
        }

    def evaluate_ablation(
        self, ablation: str, checkpoint_path: str, ref_logit_std: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Evaluate a single ablation condition."""
        print(f"\n{'='*60}")
        print(f"  Evaluating {ablation}")
        print(f"{'='*60}")

        model, ckpt = self.load_model(checkpoint_path)
        model_config = ckpt.get("model_config", {})
        vocab_size = model_config.get("vocab_size", 50257)
        max_seq_len = model_config.get("max_seq_len", 8192)
        num_layers = model_config.get("num_layers", 12)
        # Ensure eval seq_len fits within model's max_seq_len
        eval_seq_len = min(self.config.seq_len, max_seq_len - 1)
        # Clamp target layer to model's actual layers
        actual_target_layer = min(self.config.target_layer, num_layers - 1)

        from bpc.trainer import create_dataloader
        val_loader = create_dataloader(
            self.config.dataset, self.config.batch_size,
            eval_seq_len, "validation", vocab_size=vocab_size,
        )

        # Scale factor for A1
        scale_factor = 1.0
        if ablation == "A1" and ref_logit_std is not None:
            # First pass to measure current logit std
            initial_metrics = self.compute_val_metrics(model, val_loader, 1.0)
            current_std = initial_metrics["logit_std"]
            if current_std > 0:
                scale_factor = ref_logit_std / current_std
            print(f"  Scale matching: {current_std:.4f} -> {ref_logit_std:.4f} (s={scale_factor:.4f})")
            # Recreate dataloader (iterator exhausted)
            val_loader = create_dataloader(
                self.config.dataset, self.config.batch_size,
                eval_seq_len, "validation", vocab_size=vocab_size,
            )

        # Core metrics
        val_metrics = self.compute_val_metrics(model, val_loader, scale_factor)
        print(f"  Val loss: {val_metrics['val_loss']:.4f}, PPL: {val_metrics['val_ppl']:.1f}")
        print(f"  Logit std: {val_metrics['logit_std']:.4f}, Entropy: {val_metrics['entropy']:.2f}")

        result = {
            "ablation": ablation,
            "checkpoint": checkpoint_path,
            "scale_factor": scale_factor,
            **val_metrics,
        }

        # Subspace-dependent metrics
        embed_dim = model_config.get("embed_dim", 768)
        subspace_path = self.config.subspace_path or os.path.join(
            os.path.dirname(checkpoint_path), "..", "subspace", "U_r.pt"
        )
        U_r, h_mean = self.load_subspace(subspace_path)

        if U_r is not None:
            if h_mean is None:
                h_mean = torch.zeros(embed_dim, device=self.device)

            val_loader2 = create_dataloader(
                self.config.dataset, self.config.batch_size,
                eval_seq_len, "validation", vocab_size=vocab_size,
            )
            coherence = self.compute_cross_coherence(
                model, U_r, h_mean, val_loader2, self.config.rollout_steps,
                layer=actual_target_layer,
            )
            result.update(coherence)
            print(f"  Cross-coherence k=1: {coherence.get('cross_coherence_k1_mean', 0):.4f}")

            val_loader3 = create_dataloader(
                self.config.dataset, self.config.batch_size,
                eval_seq_len, "validation", vocab_size=vocab_size,
            )
            cf_sens = self.compute_cf_sensitivity(
                model, U_r, h_mean, val_loader3, vocab_size=vocab_size,
                layer=actual_target_layer,
            )
            result.update(cf_sens)
            print(f"  CF z-dist mean: {cf_sens['cf_z_dist_mean']:.4f}")

        # Random subspace control
        val_loader4 = create_dataloader(
            self.config.dataset, self.config.batch_size,
            eval_seq_len, "validation", vocab_size=vocab_size,
        )
        random_ctrl = self.compute_random_subspace_control(
            model, embed_dim, val_loader4, vocab_size=vocab_size,
            layer=actual_target_layer,
        )
        result.update(random_ctrl)

        return result

    def run_calibration_check(self, results: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Verify scale-matched baseline truly matches logit std within 1%.
        """
        if "A2" not in results or "A1" not in results:
            return {"calibration_check": "SKIP (missing A1 or A2)"}

        bpc_std = results["A2"]["logit_std"]
        matched_std = results["A1"]["logit_std"]

        rel_error = abs(bpc_std - matched_std) / max(bpc_std, 1e-8)
        passed = rel_error < 0.01

        return {
            "calibration_bpc_logit_std": bpc_std,
            "calibration_matched_logit_std": matched_std,
            "calibration_relative_error": rel_error,
            "calibration_passed": passed,
        }

    def run_full_suite(self):
        """Run evaluation across all ablation conditions."""
        print("\n" + "=" * 70)
        print("  BPC EVALUATION SUITE")
        print("=" * 70)

        # First pass: evaluate A2 to get reference logit_std
        ref_logit_std = None
        for ablation in self.config.ablations:
            ckpt_path = os.path.join(
                self.config.checkpoint_dir, ablation, "checkpoints", "best.pt"
            )
            if not os.path.exists(ckpt_path):
                ckpt_path = os.path.join(
                    self.config.checkpoint_dir, ablation, "checkpoints", "final.pt"
                )
            if not os.path.exists(ckpt_path):
                print(f"\n  SKIP {ablation}: no checkpoint found at {ckpt_path}")
                continue

            result = self.evaluate_ablation(
                ablation, ckpt_path, ref_logit_std
            )
            self.results[ablation] = result

            if ablation == "A2":
                ref_logit_std = result["logit_std"]

        # Calibration check
        calibration = self.run_calibration_check(self.results)
        self.results["calibration"] = calibration
        print(f"\n  Calibration check: {calibration}")

        # Save results
        results_path = self.output_dir / "eval_results.json"
        with open(results_path, "w") as f:
            # Filter out numpy arrays for JSON serialization
            clean = {}
            for k, v in self.results.items():
                if isinstance(v, dict):
                    clean[k] = {
                        kk: (vv if not isinstance(vv, (np.ndarray, np.floating)) else float(vv))
                        for kk, vv in v.items()
                    }
                else:
                    clean[k] = v
            json.dump(clean, f, indent=2, default=str)
        print(f"\n  Results saved to {results_path}")

        # Generate comparison table
        self._print_comparison_table()

        # Generate plots
        self._generate_plots()

        return self.results

    def _print_comparison_table(self):
        """Print comparison table across ablations."""
        print("\n" + "=" * 90)
        print("  COMPARISON TABLE")
        print("=" * 90)
        header = f"{'Ablation':<8} {'Val PPL':>10} {'Val Loss':>10} {'Logit Std':>10} {'Entropy':>10} {'CC k=1':>10}"
        print(header)
        print("-" * 68)
        for abl in sorted(self.results.keys()):
            if abl == "calibration":
                continue
            r = self.results[abl]
            cc = r.get("cross_coherence_k1_mean", 0)
            print(
                f"{abl:<8} {r.get('val_ppl', 0):10.2f} {r.get('val_loss', 0):10.4f} "
                f"{r.get('logit_std', 0):10.4f} {r.get('entropy', 0):10.2f} {cc:10.4f}"
            )

    def _generate_plots(self):
        """Generate diagnostic plots."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("  matplotlib not available, skipping plots")
            return

        ablations = [a for a in sorted(self.results.keys()) if a != "calibration"]
        if not ablations:
            return

        # 1. PPL comparison bar chart
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # PPL
        ppls = [self.results[a].get("val_ppl", 0) for a in ablations]
        axes[0, 0].bar(ablations, ppls, color="steelblue", alpha=0.8)
        axes[0, 0].set_ylabel("Validation PPL")
        axes[0, 0].set_title("Perplexity by Ablation")
        axes[0, 0].tick_params(axis="x", rotation=45)

        # Logit std
        stds = [self.results[a].get("logit_std", 0) for a in ablations]
        axes[0, 1].bar(ablations, stds, color="coral", alpha=0.8)
        axes[0, 1].set_ylabel("Logit Std")
        axes[0, 1].set_title("Logit Standard Deviation")
        axes[0, 1].tick_params(axis="x", rotation=45)

        # Entropy
        ents = [self.results[a].get("entropy", 0) for a in ablations]
        axes[1, 0].bar(ablations, ents, color="green", alpha=0.8)
        axes[1, 0].set_ylabel("Entropy")
        axes[1, 0].set_title("Output Entropy")
        axes[1, 0].tick_params(axis="x", rotation=45)

        # Cross-coherence k=1
        ccs = [self.results[a].get("cross_coherence_k1_mean", 0) for a in ablations]
        axes[1, 1].bar(ablations, ccs, color="purple", alpha=0.8)
        axes[1, 1].set_ylabel("Cosine(z_t, z_{t+1})")
        axes[1, 1].set_title("Cross-Coherence k=1")
        axes[1, 1].tick_params(axis="x", rotation=45)

        plt.tight_layout()
        plt.savefig(self.output_dir / "ablation_comparison.png", dpi=150)
        plt.close()

        # 2. CF sensitivity distributions
        fig, ax = plt.subplots(figsize=(10, 5))
        for abl in ablations:
            dists = self.results[abl].get("cf_z_dists", [])
            if dists:
                ax.hist(dists, bins=50, alpha=0.4, label=abl, density=True)
        ax.set_xlabel("||z - z_cf||")
        ax.set_ylabel("Density")
        ax.set_title("Counterfactual Sensitivity Distribution")
        ax.legend()
        plt.tight_layout()
        plt.savefig(self.output_dir / "cf_sensitivity.png", dpi=150)
        plt.close()

        print(f"  Plots saved to {self.output_dir}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="BPC Evaluation Suite")
    parser.add_argument("--checkpoint_dir", type=str, default="runs/bpc")
    parser.add_argument("--ablations", nargs="+", default=None)
    parser.add_argument("--subspace_path", type=str, default=None)
    parser.add_argument("--output_dir", type=str, default="results/bpc_eval")
    parser.add_argument("--num_eval_batches", type=int, default=50)
    parser.add_argument("--device", type=str, default="auto")
    args = parser.parse_args()

    config = EvalConfig(
        checkpoint_dir=args.checkpoint_dir,
        ablations=args.ablations,
        subspace_path=args.subspace_path,
        output_dir=args.output_dir,
        num_eval_batches=args.num_eval_batches,
        device=args.device,
    )

    evaluator = BPCEvaluator(config)
    evaluator.run_full_suite()


if __name__ == "__main__":
    main()
