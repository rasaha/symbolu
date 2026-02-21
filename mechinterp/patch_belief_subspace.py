#!/usr/bin/env python3
"""
Activation Patching on Belief Subspace
========================================

Causal validation that the learned belief subspace carries semantically
meaningful information by patching projected components between sequences.

Procedure:
  1. Take sequences A and B with known structural difference
  2. At layer L*, compute projected belief components
  3. Patch belief from B into A
  4. Measure downstream KL divergence shift

Controls:
  - Random subspace of same rank (should have weaker, noisy effect)
  - Residual patching (complement of belief subspace)
  - Norm-matched noise (rules out "any perturbation changes output")
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@dataclass
class PatchConfig:
    """Configuration for activation patching."""
    checkpoint_path: str = ""
    subspace_path: str = ""
    target_layer: int = 6
    subspace_rank: int = 32
    num_pairs: int = 100
    patch_position: str = "middle"  # "middle", "early", "late", or int
    seq_len: int = 128
    batch_size: int = 1
    dataset: str = "wikitext103"
    output_dir: str = "results/patching"
    device: str = "auto"


class HookManager:
    """Manages forward hooks for activation patching."""

    def __init__(self):
        self.hooks = []
        self.activations = {}
        self._patch_fn = None
        self._patch_layer = None

    def register_capture_hook(self, model: nn.Module, layer_idx: int, name: str):
        """Register a hook to capture activations at a specific layer."""
        block = model.blocks[layer_idx]

        def hook_fn(module, input, output, name=name):
            self.activations[name] = output.detach()

        handle = block.register_forward_hook(hook_fn)
        self.hooks.append(handle)

    def register_patch_hook(
        self, model: nn.Module, layer_idx: int,
        patch_fn,
    ):
        """Register a hook to patch activations at a specific layer."""
        block = model.blocks[layer_idx]

        def hook_fn(module, input, output):
            return patch_fn(output)

        handle = block.register_forward_hook(hook_fn)
        self.hooks.append(handle)
        self._patch_layer = layer_idx

    def remove_all(self):
        for h in self.hooks:
            h.remove()
        self.hooks = []
        self.activations = {}


class BeliefPatcher:
    """
    Performs activation patching experiments on the belief subspace.
    """

    def __init__(self, config: PatchConfig):
        self.config = config
        if config.device == "auto":
            self.device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )
        else:
            self.device = torch.device(config.device)

        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_model(self) -> nn.Module:
        from symbolu.phase_transformer import StandardTransformer

        ckpt = torch.load(
            self.config.checkpoint_path,
            map_location=self.device,
            weights_only=False,
        )
        model_config = ckpt.get("model_config", {
            "vocab_size": 50257, "embed_dim": 768,
            "num_layers": 12, "num_heads": 12,
        })
        model = StandardTransformer(**model_config)
        model.load_state_dict(ckpt["model_state_dict"], strict=False)
        model.to(self.device).eval()
        return model

    def load_subspace(self) -> Tuple[torch.Tensor, torch.Tensor]:
        data = torch.load(
            self.config.subspace_path,
            map_location=self.device,
            weights_only=True,
        )
        U_r = data["U_r"]
        h_mean = data.get("mean", torch.zeros(U_r.shape[0], device=self.device))
        return U_r, h_mean

    def generate_paired_sequences(
        self, dataloader, num_pairs: int,
    ) -> List[Tuple[torch.Tensor, torch.Tensor]]:
        """
        Generate pairs of sequences (A, B) with structural differences.
        Uses consecutive sequences from validation set as natural pairs.
        """
        pairs = []
        prev_batch = None

        for batch in dataloader:
            input_ids = batch[0] if isinstance(batch, (list, tuple)) else batch
            input_ids = input_ids.to(self.device)

            if prev_batch is not None:
                B = min(prev_batch.shape[0], input_ids.shape[0])
                for b in range(B):
                    pairs.append((prev_batch[b:b+1], input_ids[b:b+1]))
                    if len(pairs) >= num_pairs:
                        return pairs

            prev_batch = input_ids

        return pairs

    def _get_patch_position(self, seq_len: int) -> int:
        """Get the position to patch based on config."""
        pos = self.config.patch_position
        if pos == "middle":
            return seq_len // 2
        elif pos == "early":
            return seq_len // 4
        elif pos == "late":
            return 3 * seq_len // 4
        elif isinstance(pos, int):
            return min(pos, seq_len - 1)
        else:
            return seq_len // 2

    @torch.no_grad()
    def compute_kl_divergence(
        self,
        logits_original: torch.Tensor,
        logits_patched: torch.Tensor,
        position: int,
    ) -> float:
        """
        Compute KL(original || patched) at the next-token position.
        """
        p = F.log_softmax(logits_original[:, position, :], dim=-1)
        q = F.softmax(logits_patched[:, position, :], dim=-1)
        kl = F.kl_div(p, q, reduction="batchmean", log_target=False)
        return kl.item()

    @torch.no_grad()
    def run_single_patch(
        self,
        model: nn.Module,
        seq_a: torch.Tensor,
        seq_b: torch.Tensor,
        U_r: torch.Tensor,
        h_mean: torch.Tensor,
        patch_type: str = "belief",
    ) -> Dict[str, float]:
        """
        Run a single patching experiment.

        patch_type: "belief", "random", "residual", "noise"
        """
        layer = self.config.target_layer
        pos = self._get_patch_position(seq_a.shape[1])

        # 1. Get activations from both sequences
        hooks = HookManager()
        hooks.register_capture_hook(model, layer, "A")
        out_a = model(seq_a)
        h_a = hooks.activations["A"]  # [1, T, D]
        hooks.remove_all()

        hooks.register_capture_hook(model, layer, "B")
        out_b = model(seq_b)
        h_b = hooks.activations["B"]  # [1, T, D]
        hooks.remove_all()

        logits_original = out_a["logits"]

        # 2. Compute projections
        D = h_a.shape[-1]
        r = U_r.shape[1]

        h_a_pos = h_a[:, pos, :]  # [1, D]
        h_b_pos = h_b[:, pos, :]  # [1, D]

        if patch_type == "belief":
            # Patch belief component from B into A
            z_a = (h_a_pos - h_mean) @ U_r  # [1, r]
            z_b = (h_b_pos - h_mean) @ U_r  # [1, r]
            h_a_proj = z_a @ U_r.T + h_mean
            h_b_proj = z_b @ U_r.T + h_mean
            h_patched_pos = (h_a_pos - h_a_proj) + h_b_proj

        elif patch_type == "random":
            # Random orthonormal subspace of same rank
            Q, _ = torch.linalg.qr(torch.randn(D, r, device=self.device))
            z_a = h_a_pos @ Q
            z_b = h_b_pos @ Q
            h_a_proj = z_a @ Q.T
            h_b_proj = z_b @ Q.T
            h_patched_pos = (h_a_pos - h_a_proj) + h_b_proj

        elif patch_type == "residual":
            # Patch residual (complement of belief subspace)
            z_a = (h_a_pos - h_mean) @ U_r
            z_b = (h_b_pos - h_mean) @ U_r
            h_a_res = h_a_pos - (z_a @ U_r.T + h_mean)
            h_b_res = h_b_pos - (z_b @ U_r.T + h_mean)
            # Keep belief, swap residual
            h_a_proj = z_a @ U_r.T + h_mean
            h_patched_pos = h_a_proj + h_b_res

        elif patch_type == "noise":
            # Norm-matched random noise
            belief_diff = (h_b_pos - h_mean) @ U_r @ U_r.T - (h_a_pos - h_mean) @ U_r @ U_r.T
            noise_norm = belief_diff.norm()
            noise = torch.randn_like(h_a_pos)
            noise = noise / noise.norm() * noise_norm
            h_patched_pos = h_a_pos + noise

        else:
            raise ValueError(f"Unknown patch type: {patch_type}")

        # 3. Forward with patched activation
        def patch_fn(output):
            out = output.clone()
            out[:, pos, :] = h_patched_pos
            return out

        hooks.register_patch_hook(model, layer, patch_fn)
        out_patched = model(seq_a)
        logits_patched = out_patched["logits"]
        hooks.remove_all()

        # 4. Compute KL divergence
        kl = self.compute_kl_divergence(logits_original, logits_patched, pos)

        # Patch magnitude
        patch_magnitude = (h_patched_pos - h_a_pos).norm().item()

        return {
            "kl_divergence": kl,
            "patch_magnitude": patch_magnitude,
            "patch_type": patch_type,
            "position": pos,
        }

    def run_experiment(self) -> Dict[str, Any]:
        """Run full patching experiment across many pairs."""
        print("\n" + "=" * 70)
        print("  ACTIVATION PATCHING EXPERIMENT")
        print("=" * 70)

        model = self.load_model()
        U_r, h_mean = self.load_subspace()

        from bpc.trainer import create_dataloader
        val_loader = create_dataloader(
            self.config.dataset,
            batch_size=1,
            seq_len=self.config.seq_len,
            split="validation",
        )

        pairs = self.generate_paired_sequences(val_loader, self.config.num_pairs)
        print(f"  Generated {len(pairs)} sequence pairs")

        results = {
            "belief": [], "random": [], "residual": [], "noise": [],
        }

        for i, (seq_a, seq_b) in enumerate(pairs):
            if i % 20 == 0:
                print(f"  Processing pair {i}/{len(pairs)}...")

            for patch_type in ["belief", "random", "residual", "noise"]:
                try:
                    r = self.run_single_patch(
                        model, seq_a, seq_b, U_r, h_mean, patch_type
                    )
                    results[patch_type].append(r)
                except Exception as e:
                    print(f"    Error on pair {i}, type={patch_type}: {e}")
                    continue

        # Aggregate results
        summary = {}
        for patch_type, rs in results.items():
            if not rs:
                continue
            kls = [r["kl_divergence"] for r in rs]
            mags = [r["patch_magnitude"] for r in rs]
            summary[patch_type] = {
                "n_pairs": len(rs),
                "kl_mean": float(np.mean(kls)),
                "kl_std": float(np.std(kls)),
                "kl_median": float(np.median(kls)),
                "kl_p25": float(np.percentile(kls, 25)),
                "kl_p75": float(np.percentile(kls, 75)),
                "magnitude_mean": float(np.mean(mags)),
                "kl_values": kls,
            }

        # Compute success rate: belief patch KL > random patch KL
        if results["belief"] and results["random"]:
            belief_kls = [r["kl_divergence"] for r in results["belief"]]
            random_kls = [r["kl_divergence"] for r in results["random"]]
            n_compare = min(len(belief_kls), len(random_kls))
            successes = sum(
                1 for i in range(n_compare) if belief_kls[i] > random_kls[i]
            )
            summary["patch_success_rate"] = successes / max(1, n_compare)
        else:
            summary["patch_success_rate"] = 0.0

        # Print summary
        print("\n  PATCHING RESULTS:")
        print(f"  {'Type':<12} {'KL Mean':>10} {'KL Std':>10} {'KL Median':>10} {'Magnitude':>10}")
        print(f"  {'-'*52}")
        for pt in ["belief", "random", "residual", "noise"]:
            if pt in summary:
                s = summary[pt]
                print(
                    f"  {pt:<12} {s['kl_mean']:10.4f} {s['kl_std']:10.4f} "
                    f"{s['kl_median']:10.4f} {s['magnitude_mean']:10.4f}"
                )
        print(f"\n  Patch success rate (belief > random): {summary.get('patch_success_rate', 0):.2%}")

        # Save
        save_path = self.output_dir / "patching_results.json"
        # Remove kl_values for clean JSON
        clean_summary = {}
        for k, v in summary.items():
            if isinstance(v, dict):
                clean_summary[k] = {kk: vv for kk, vv in v.items() if kk != "kl_values"}
            else:
                clean_summary[k] = v
        with open(save_path, "w") as f:
            json.dump(clean_summary, f, indent=2)

        # Generate plots
        self._generate_plots(summary)

        return summary

    def _generate_plots(self, summary: Dict[str, Any]):
        """Generate patching diagnostic plots."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("  matplotlib not available, skipping plots")
            return

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # 1. KL distribution comparison
        colors = {"belief": "blue", "random": "orange", "residual": "green", "noise": "red"}
        for patch_type in ["belief", "random", "residual", "noise"]:
            if patch_type in summary and "kl_values" in summary[patch_type]:
                vals = summary[patch_type]["kl_values"]
                axes[0].hist(
                    vals, bins=30, alpha=0.4,
                    label=f"{patch_type} (mean={np.mean(vals):.3f})",
                    color=colors.get(patch_type, "gray"),
                    density=True,
                )
        axes[0].set_xlabel("KL Divergence")
        axes[0].set_ylabel("Density")
        axes[0].set_title("KL Divergence Distribution by Patch Type")
        axes[0].legend()

        # 2. Bar chart of mean KL
        types = []
        means = []
        stds = []
        for pt in ["belief", "random", "residual", "noise"]:
            if pt in summary:
                types.append(pt)
                means.append(summary[pt]["kl_mean"])
                stds.append(summary[pt]["kl_std"])

        if types:
            bars = axes[1].bar(
                types, means,
                yerr=stds, capsize=5,
                color=[colors.get(t, "gray") for t in types],
                alpha=0.7,
            )
            axes[1].set_ylabel("Mean KL Divergence")
            axes[1].set_title("Mean KL by Patch Type (±1 std)")

        plt.tight_layout()
        plt.savefig(self.output_dir / "patching_kl_distributions.png", dpi=150)
        plt.close()

        print(f"  Patching plots saved to {self.output_dir}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Activation Patching on Belief Subspace")
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--subspace", type=str, required=True)
    parser.add_argument("--num_pairs", type=int, default=100)
    parser.add_argument("--target_layer", type=int, default=6)
    parser.add_argument("--output_dir", type=str, default="results/patching")
    parser.add_argument("--device", type=str, default="auto")
    args = parser.parse_args()

    config = PatchConfig(
        checkpoint_path=args.checkpoint,
        subspace_path=args.subspace,
        num_pairs=args.num_pairs,
        target_layer=args.target_layer,
        output_dir=args.output_dir,
        device=args.device,
    )

    patcher = BeliefPatcher(config)
    patcher.run_experiment()


if __name__ == "__main__":
    main()
