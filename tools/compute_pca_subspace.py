#!/usr/bin/env python3
"""
PCA Belief Subspace Extraction
================================

Computes the PCA basis U_r for the belief subspace from hidden states
at a target layer L* of a trained causal LM.

Usage:
    python tools/compute_pca_subspace.py \
        --checkpoint checkpoints/baseline.pt \
        --layer 6 \
        --rank 32 \
        --num_tokens 2000000 \
        --output subspace/U_r.pt

Outputs:
    - U_r (d x r) orthonormal matrix saved as .pt
    - Explained variance curve plot
    - Subspace energy ratio: E_proj / E_total
    - Mean and covariance statistics
"""

import argparse
import math
import os
import sys
from pathlib import Path

import torch
import torch.nn as nn
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class IncrementalPCA:
    """
    Memory-safe incremental PCA for large-scale hidden state collection.
    Avoids storing all hidden states in memory.
    """

    def __init__(self, n_components: int, device: torch.device = torch.device("cpu")):
        self.n_components = n_components
        self.device = device
        self._sum = None
        self._sum_sq = None
        self._count = 0
        self._cov_accum = None
        self._dim = None

    def partial_fit(self, X: torch.Tensor):
        """
        Update running statistics with a batch of data.
        X: [N, D] where N is batch size, D is feature dim.
        """
        X = X.to(self.device).float()
        N, D = X.shape

        if self._dim is None:
            self._dim = D
            self._sum = torch.zeros(D, device=self.device)
            self._sum_sq = torch.zeros(D, D, device=self.device)

        assert X.shape[1] == self._dim, f"Dim mismatch: {X.shape[1]} vs {self._dim}"

        self._sum += X.sum(dim=0)
        self._sum_sq += X.T @ X
        self._count += N

    @property
    def mean(self) -> torch.Tensor:
        return self._sum / max(1, self._count)

    @property
    def covariance(self) -> torch.Tensor:
        mean = self.mean
        return self._sum_sq / max(1, self._count) - mean.unsqueeze(1) * mean.unsqueeze(0)

    def compute(self) -> dict:
        """
        Compute PCA basis from accumulated statistics.

        Returns dict with:
            U_r: (D, r) orthonormal basis
            eigenvalues: (D,) sorted eigenvalues
            explained_variance_ratio: (D,) fraction of variance explained
            mean: (D,) mean hidden state
            covariance: (D, D) covariance matrix
            energy_ratio: scalar E_proj / E_total
        """
        assert self._count > 0, "No data accumulated"

        cov = self.covariance

        # Compute eigendecomposition
        eigenvalues, eigenvectors = torch.linalg.eigh(cov)

        # Sort descending
        idx = eigenvalues.argsort(descending=True)
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        # Clamp negative eigenvalues (numerical noise)
        eigenvalues = eigenvalues.clamp(min=0)

        # Top-r components
        U_r = eigenvectors[:, : self.n_components]  # (D, r)

        # Explained variance
        total_var = eigenvalues.sum()
        explained_variance_ratio = eigenvalues / total_var.clamp(min=1e-12)

        # Energy ratio for top-r
        energy_ratio = eigenvalues[: self.n_components].sum() / total_var.clamp(min=1e-12)

        # Verify orthonormality
        ortho_check = U_r.T @ U_r
        ortho_error = (ortho_check - torch.eye(self.n_components, device=self.device)).abs().max()

        return {
            "U_r": U_r,
            "eigenvalues": eigenvalues,
            "explained_variance_ratio": explained_variance_ratio,
            "mean": self.mean,
            "covariance": cov,
            "energy_ratio": energy_ratio.item(),
            "ortho_error": ortho_error.item(),
            "n_samples": self._count,
        }


def collect_hidden_states(
    model: nn.Module,
    dataloader,
    layer_idx: int,
    num_tokens: int,
    device: torch.device,
    pca: IncrementalPCA,
) -> int:
    """
    Collect hidden states from layer L* across dataset.

    Returns number of tokens processed.
    """
    model.eval()
    tokens_collected = 0

    with torch.no_grad():
        for batch in dataloader:
            if tokens_collected >= num_tokens:
                break

            if isinstance(batch, dict):
                input_ids = batch["input_ids"].to(device)
            elif isinstance(batch, (list, tuple)):
                input_ids = batch[0].to(device)
            else:
                input_ids = batch.to(device)

            # Forward with hidden state extraction
            outputs = model(input_ids, extract_layers=[layer_idx])
            hidden = outputs["hidden_states"][0]  # [B, T, D]

            # Flatten batch and time
            B, T, D = hidden.shape
            flat = hidden.reshape(-1, D)  # [B*T, D]

            pca.partial_fit(flat.cpu())
            tokens_collected += B * T

    return tokens_collected


def plot_explained_variance(
    eigenvalues: torch.Tensor,
    rank: int,
    save_path: str,
):
    """Plot explained variance curve."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        eigenvalues = eigenvalues.cpu().numpy()
        total = eigenvalues.sum()
        explained = eigenvalues / total
        cumulative = np.cumsum(explained)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        # Individual explained variance
        ax1.bar(range(min(100, len(explained))), explained[:100], alpha=0.7, color="steelblue")
        ax1.axvline(x=rank, color="red", linestyle="--", label=f"rank={rank}")
        ax1.set_xlabel("Component")
        ax1.set_ylabel("Explained Variance Ratio")
        ax1.set_title("Individual Explained Variance")
        ax1.legend()
        ax1.set_yscale("log")

        # Cumulative
        ax2.plot(cumulative[:100], "b-", linewidth=2)
        ax2.axvline(x=rank, color="red", linestyle="--", label=f"rank={rank}")
        ax2.axhline(
            y=cumulative[rank - 1] if rank <= len(cumulative) else cumulative[-1],
            color="green",
            linestyle=":",
            label=f"energy={cumulative[min(rank-1, len(cumulative)-1)]:.3f}",
        )
        ax2.set_xlabel("Number of Components")
        ax2.set_ylabel("Cumulative Explained Variance")
        ax2.set_title("Cumulative Explained Variance")
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Saved explained variance plot to {save_path}")
    except ImportError:
        print("  matplotlib not available, skipping plot")


def run_unit_test(U_r: torch.Tensor, tol: float = 1e-5):
    """Unit test: verify U_r^T U_r ~= I."""
    r = U_r.shape[1]
    product = U_r.T @ U_r
    identity = torch.eye(r, device=U_r.device)
    error = (product - identity).abs().max().item()
    passed = error < tol
    print(f"  Orthonormality test: max|U_r^T U_r - I| = {error:.2e} {'PASS' if passed else 'FAIL'}")
    return passed


def main():
    parser = argparse.ArgumentParser(description="Compute PCA belief subspace")
    parser.add_argument("--checkpoint", type=str, required=True, help="Model checkpoint path")
    parser.add_argument("--layer", type=int, default=6, help="Target layer L*")
    parser.add_argument("--rank", type=int, default=32, help="Subspace rank r")
    parser.add_argument("--num_tokens", type=int, default=2_000_000, help="Tokens to collect")
    parser.add_argument("--output", type=str, default="subspace/U_r.pt", help="Output path")
    parser.add_argument("--batch_size", type=int, default=8, help="Batch size")
    parser.add_argument("--seq_len", type=int, default=256, help="Sequence length")
    parser.add_argument("--dataset", type=str, default="wikitext103", help="Dataset name")
    parser.add_argument("--device", type=str, default="auto", help="Device")
    parser.add_argument("--model_type", type=str, default="standard", help="Model type")
    args = parser.parse_args()

    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)

    print(f"=== PCA Belief Subspace Extraction ===")
    print(f"  Checkpoint: {args.checkpoint}")
    print(f"  Layer L*: {args.layer}")
    print(f"  Rank r: {args.rank}")
    print(f"  Num tokens: {args.num_tokens:,}")
    print(f"  Device: {device}")

    # Load model
    print("\nLoading model...")
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)

    if "model_config" in checkpoint:
        config = checkpoint["model_config"]
    else:
        config = {
            "vocab_size": 50257,
            "embed_dim": 768,
            "num_layers": 12,
            "num_heads": 12,
        }

    from symbolu.phase_transformer import StandardTransformer
    model = StandardTransformer(**config)
    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"], strict=False)
    elif "model" in checkpoint:
        model.load_state_dict(checkpoint["model"], strict=False)
    model = model.to(device)
    model.eval()

    embed_dim = config.get("embed_dim", 768)
    print(f"  Model embed_dim: {embed_dim}")
    print(f"  Num layers: {config.get('num_layers', 12)}")

    # Create data
    print("\nPreparing data...")
    from bpc.trainer import create_dataloader
    dataloader = create_dataloader(
        dataset_name=args.dataset,
        batch_size=args.batch_size,
        seq_len=args.seq_len,
        split="validation",
    )

    # Compute PCA
    print("\nCollecting hidden states and computing PCA...")
    pca = IncrementalPCA(n_components=args.rank, device=torch.device("cpu"))
    tokens_collected = collect_hidden_states(
        model, dataloader, args.layer, args.num_tokens, device, pca
    )
    print(f"  Collected {tokens_collected:,} token hidden states")

    results = pca.compute()

    print(f"\n=== Results ===")
    print(f"  U_r shape: {results['U_r'].shape}")
    print(f"  Energy ratio (top-{args.rank}): {results['energy_ratio']:.4f}")
    print(f"  Orthonormality error: {results['ortho_error']:.2e}")

    # Unit test
    run_unit_test(results["U_r"])

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_dict = {
        "U_r": results["U_r"],
        "mean": results["mean"],
        "eigenvalues": results["eigenvalues"],
        "explained_variance_ratio": results["explained_variance_ratio"],
        "energy_ratio": results["energy_ratio"],
        "layer": args.layer,
        "rank": args.rank,
        "n_samples": results["n_samples"],
        "covariance": results["covariance"],
    }
    torch.save(save_dict, output_path)
    print(f"\n  Saved subspace to {output_path}")

    # Plot
    plot_path = str(output_path).replace(".pt", "_variance.png")
    plot_explained_variance(results["eigenvalues"], args.rank, plot_path)

    # Print top eigenvalues
    evals = results["eigenvalues"][:20].cpu().numpy()
    print(f"\n  Top-20 eigenvalues: {evals}")


if __name__ == "__main__":
    main()
