"""
Mixture of Experts Feed-Forward Network (MoE FFN).

Standard Mixtral-style MoE for compute efficiency in Phase-Quad architecture.

Key features:
- Lightweight router (single linear layer)
- Top-K expert selection (default: top-2 of 8)
- Load balance loss for uniform expert utilization
- Router z-loss for training stability

Usage:
    moe_ffn = MoEFFN(d_model=512, num_experts=8, top_k=2)
    output, aux_losses = moe_ffn(x)

    # Add aux losses to training loss
    loss = main_loss + 0.01 * aux_losses["load_balance_loss"]

Reference: Designed per Mixtral architecture for Phase-Quad integration.
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass
import time

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


@dataclass
class MoEConfig:
    """
    Configuration for MoE FFN.

    Attributes:
        num_experts: Total number of experts (default: 8)
        top_k: Number of experts to activate per token (default: 2)
        d_ff_multiplier: FFN hidden dim multiplier (default: 4)
        load_balance_weight: Weight for load balance loss (default: 0.01)
        router_z_weight: Weight for router z-loss (default: 0.001)
        dropout: Dropout rate (default: 0.1)
        expert_capacity_factor: Capacity factor for expert batching (default: 1.25)
    """
    num_experts: int = 8
    top_k: int = 2
    d_ff_multiplier: int = 4
    load_balance_weight: float = 0.01
    router_z_weight: float = 0.001
    dropout: float = 0.1
    expert_capacity_factor: float = 1.25


class ExpertFFN(nn.Module):
    """Single expert FFN (standard 2-layer MLP with GELU)."""

    def __init__(self, d_model: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(d_model, d_ff)
        self.fc2 = nn.Linear(d_ff, d_model)
        self.dropout = nn.Dropout(dropout)
        self.act = nn.GELU()

    def forward(self, x: Tensor) -> Tensor:
        """Forward pass: x -> fc1 -> GELU -> dropout -> fc2 -> dropout."""
        x = self.fc1(x)
        x = self.act(x)
        x = self.dropout(x)
        x = self.fc2(x)
        x = self.dropout(x)
        return x


class MoEFFN(nn.Module):
    """
    Mixture of Experts Feed-Forward Network.

    Replaces standard dense FFN with sparse MoE for compute efficiency.
    Each token is routed to top-K experts, providing ~(num_experts/top_k)x
    capacity with only ~(top_k/num_experts + overhead)x compute.

    Args:
        d_model: Model dimension
        d_ff: FFN hidden dimension (default: 4 * d_model)
        num_experts: Number of expert FFNs (default: 8)
        top_k: Number of experts to activate per token (default: 2)
        dropout: Dropout rate (default: 0.1)
        load_balance_weight: Weight for load balance loss (default: 0.01)
        router_z_weight: Weight for router z-loss (default: 0.001)
    """

    def __init__(
        self,
        d_model: int,
        d_ff: Optional[int] = None,
        num_experts: int = 8,
        top_k: int = 2,
        dropout: float = 0.1,
        load_balance_weight: float = 0.01,
        router_z_weight: float = 0.001,
    ):
        super().__init__()
        self.d_model = d_model
        self.d_ff = d_ff or 4 * d_model
        self.num_experts = num_experts
        self.top_k = top_k
        self.load_balance_weight = load_balance_weight
        self.router_z_weight = router_z_weight

        # Lightweight router: single linear layer (NOT deep MLP)
        self.router = nn.Linear(d_model, num_experts, bias=False)

        # Expert FFNs
        self.experts = nn.ModuleList([
            ExpertFFN(d_model, self.d_ff, dropout)
            for _ in range(num_experts)
        ])

    def forward(self, x: Tensor) -> Tuple[Tensor, Dict[str, Tensor]]:
        """
        Forward pass with sparse expert routing.

        Args:
            x: [B, N, D] input tensor

        Returns:
            output: [B, N, D] MoE output
            aux: Dict with auxiliary losses and diagnostics
        """
        B, N, D = x.shape

        # Compute router logits and probabilities
        router_logits = self.router(x)  # [B, N, num_experts]
        router_probs = F.softmax(router_logits, dim=-1)

        # Select top-k experts per token
        top_k_probs, top_k_indices = torch.topk(router_probs, self.top_k, dim=-1)

        # Normalize selected expert weights to sum to 1
        top_k_weights = top_k_probs / (top_k_probs.sum(dim=-1, keepdim=True) + 1e-6)

        # Compute weighted expert outputs
        output = self._compute_expert_outputs(x, top_k_indices, top_k_weights)

        # Compute auxiliary losses and diagnostics
        aux = self._compute_aux_losses(router_logits, router_probs, top_k_indices)

        return output, aux

    def _compute_expert_outputs(
        self,
        x: Tensor,
        top_k_indices: Tensor,
        top_k_weights: Tensor,
    ) -> Tensor:
        """
        Compute weighted sum of expert outputs.

        Uses simple loop for clarity. For production, consider:
        - Batched expert computation
        - Expert parallelism across devices
        """
        B, N, D = x.shape
        output = torch.zeros_like(x)

        # Process each expert position
        for k in range(self.top_k):
            expert_idx = top_k_indices[:, :, k]  # [B, N]
            expert_weight = top_k_weights[:, :, k]  # [B, N]

            # Process each expert
            for e in range(self.num_experts):
                mask = (expert_idx == e)  # [B, N] boolean
                if mask.any():
                    # Gather tokens for this expert
                    expert_input = x[mask]  # [num_tokens, D]

                    # Apply expert FFN
                    expert_output = self.experts[e](expert_input)

                    # Weighted addition to output
                    output[mask] += expert_weight[mask].unsqueeze(-1) * expert_output

        return output

    def _compute_aux_losses(
        self,
        router_logits: Tensor,
        router_probs: Tensor,
        top_k_indices: Tensor,
    ) -> Dict[str, Tensor]:
        """
        Compute auxiliary losses for MoE training.

        Returns:
            Dict with:
            - load_balance_loss: Encourages uniform expert utilization
            - router_z_loss: Stabilizes router training
            - expert_utilization: Per-expert usage fraction
            - router_entropy: Entropy of router distribution
        """
        B, N, E = router_probs.shape
        device = router_probs.device

        # =====================================================================
        # Load Balance Loss (from Switch Transformer)
        # =====================================================================
        # Fraction of tokens routed to each expert
        expert_mask = F.one_hot(top_k_indices, E).float()  # [B, N, top_k, E]
        tokens_per_expert = expert_mask.sum(dim=[0, 1, 2])  # [E]
        total_tokens = B * N * self.top_k
        expert_frac = tokens_per_expert / total_tokens  # [E]

        # Mean router probability per expert (across all tokens)
        expert_prob = router_probs.mean(dim=[0, 1])  # [E]

        # Load balance loss: E * sum(f_i * P_i)
        # Minimized when experts are uniformly utilized
        load_balance_loss = E * (expert_frac * expert_prob).sum()

        # =====================================================================
        # Router Z-Loss (from ST-MoE)
        # =====================================================================
        # Penalizes large router logits to stabilize training
        router_z_loss = torch.logsumexp(router_logits, dim=-1).pow(2).mean()

        # =====================================================================
        # Diagnostics (not used in loss, just for monitoring)
        # =====================================================================
        # Router entropy (higher = more uniform routing)
        router_entropy = -(router_probs * torch.log(router_probs + 1e-6)).sum(-1).mean()

        # Expert utilization stats
        expert_utilization = expert_frac.detach()
        utilization_std = expert_utilization.std()
        utilization_max = expert_utilization.max()
        utilization_min = expert_utilization.min()

        return {
            # Losses
            "load_balance_loss": self.load_balance_weight * load_balance_loss,
            "router_z_loss": self.router_z_weight * router_z_loss,
            "moe_aux_loss": (
                self.load_balance_weight * load_balance_loss +
                self.router_z_weight * router_z_loss
            ),
            # Diagnostics
            "expert_utilization": expert_utilization,
            "utilization_std": utilization_std,
            "utilization_max": utilization_max,
            "utilization_min": utilization_min,
            "router_entropy": router_entropy,
        }


class MoEFFNBenchmark:
    """
    Benchmark utilities for MoE FFN.

    Compares dense vs MoE FFN on:
    - Throughput (tokens/sec)
    - Memory usage
    - Quality (loss/accuracy)
    - Expert utilization
    """

    def __init__(self, d_model: int, device: str = "cuda"):
        self.d_model = d_model
        self.device = device

    def benchmark_throughput(
        self,
        dense_ffn: nn.Module,
        moe_ffn: MoEFFN,
        batch_size: int = 32,
        seq_len: int = 256,
        num_iterations: int = 100,
        warmup: int = 10,
    ) -> Dict[str, float]:
        """
        Compare throughput between dense and MoE FFN.

        Returns:
            Dict with tokens/sec for each variant
        """
        x = torch.randn(batch_size, seq_len, self.d_model, device=self.device)
        total_tokens = batch_size * seq_len

        results = {}

        # Benchmark dense FFN
        dense_ffn.eval()
        with torch.no_grad():
            # Warmup
            for _ in range(warmup):
                _ = dense_ffn(x)

            if self.device == "cuda":
                torch.cuda.synchronize()

            start = time.perf_counter()
            for _ in range(num_iterations):
                _ = dense_ffn(x)

            if self.device == "cuda":
                torch.cuda.synchronize()

            dense_time = time.perf_counter() - start
            results["dense_tokens_per_sec"] = (total_tokens * num_iterations) / dense_time

        # Benchmark MoE FFN
        moe_ffn.eval()
        with torch.no_grad():
            # Warmup
            for _ in range(warmup):
                _, _ = moe_ffn(x)

            if self.device == "cuda":
                torch.cuda.synchronize()

            start = time.perf_counter()
            for _ in range(num_iterations):
                _, _ = moe_ffn(x)

            if self.device == "cuda":
                torch.cuda.synchronize()

            moe_time = time.perf_counter() - start
            results["moe_tokens_per_sec"] = (total_tokens * num_iterations) / moe_time

        # Compute speedup
        results["speedup"] = results["moe_tokens_per_sec"] / results["dense_tokens_per_sec"]

        return results

    def benchmark_expert_utilization(
        self,
        moe_ffn: MoEFFN,
        dataloader,
        max_batches: int = 100,
    ) -> Dict[str, Tensor]:
        """
        Measure expert utilization across a dataset.

        Returns:
            Dict with per-expert utilization statistics
        """
        moe_ffn.eval()
        all_utilizations = []

        with torch.no_grad():
            for i, batch in enumerate(dataloader):
                if i >= max_batches:
                    break

                x = batch[0].to(self.device) if isinstance(batch, (list, tuple)) else batch.to(self.device)
                _, aux = moe_ffn(x)
                all_utilizations.append(aux["expert_utilization"])

        if not all_utilizations:
            return {}

        # Aggregate statistics
        stacked = torch.stack(all_utilizations, dim=0)  # [num_batches, num_experts]

        return {
            "mean_utilization": stacked.mean(dim=0),
            "std_utilization": stacked.std(dim=0),
            "min_utilization": stacked.min(dim=0).values,
            "max_utilization": stacked.max(dim=0).values,
            "utilization_imbalance": stacked.std(dim=0).mean(),
        }

    def full_benchmark(
        self,
        num_experts: int = 8,
        top_k: int = 2,
        batch_size: int = 32,
        seq_len: int = 256,
    ) -> Dict[str, any]:
        """
        Run full benchmark suite.

        Returns comprehensive diagnostics for decision-making.
        """
        d_ff = 4 * self.d_model

        # Create models
        dense_ffn = nn.Sequential(
            nn.Linear(self.d_model, d_ff),
            nn.GELU(),
            nn.Linear(d_ff, self.d_model),
        ).to(self.device)

        moe_ffn = MoEFFN(
            d_model=self.d_model,
            d_ff=d_ff,
            num_experts=num_experts,
            top_k=top_k,
        ).to(self.device)

        # Throughput benchmark
        throughput = self.benchmark_throughput(dense_ffn, moe_ffn, batch_size, seq_len)

        # Parameter count
        dense_params = sum(p.numel() for p in dense_ffn.parameters())
        moe_params = sum(p.numel() for p in moe_ffn.parameters())

        # Single forward pass for aux losses
        x = torch.randn(batch_size, seq_len, self.d_model, device=self.device)
        moe_ffn.eval()
        with torch.no_grad():
            _, aux = moe_ffn(x)

        return {
            "throughput": throughput,
            "params": {
                "dense": dense_params,
                "moe": moe_params,
                "ratio": moe_params / dense_params,
            },
            "expert_utilization": aux["expert_utilization"].cpu().tolist(),
            "utilization_std": aux["utilization_std"].item(),
            "router_entropy": aux["router_entropy"].item(),
            "load_balance_loss": aux["load_balance_loss"].item(),
            "config": {
                "d_model": self.d_model,
                "d_ff": d_ff,
                "num_experts": num_experts,
                "top_k": top_k,
            },
        }


def create_moe_ffn(
    d_model: int,
    config: Optional[MoEConfig] = None,
) -> MoEFFN:
    """
    Factory function to create MoE FFN with config.

    Args:
        d_model: Model dimension
        config: MoE configuration (uses defaults if None)

    Returns:
        Configured MoEFFN module
    """
    if config is None:
        config = MoEConfig()

    return MoEFFN(
        d_model=d_model,
        d_ff=d_model * config.d_ff_multiplier,
        num_experts=config.num_experts,
        top_k=config.top_k,
        dropout=config.dropout,
        load_balance_weight=config.load_balance_weight,
        router_z_weight=config.router_z_weight,
    )
