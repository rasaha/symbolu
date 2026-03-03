"""
Hierarchical Phase-Quad (HP-Quad) Module.

Multi-timescale processing inspired by HM-RNN (Chung et al., 2016).
Extends Phase-Quad with hierarchical processing at multiple temporal scales.

Key features:
- Boundary detection for adaptive update frequency
- Multi-level Phase Integrator (fast/medium/slow)
- Hierarchical Quad Proposal with multi-granularity retrieval
- Top-down modulation from slow to fast layers

Usage:
    hp_quad = HPQuadBlock(d_model=512, num_levels=3)
    output, phase_states, aux = hp_quad(x)

    # Monitor boundary detection
    print(f"Boundary rate: {aux['boundary_rate']:.3f}")

Reference: Based on HM-RNN architecture, adapted for Phase-Quad.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import time

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


@dataclass
class HPQuadConfig:
    """
    Configuration for Hierarchical Phase-Quad.

    Attributes:
        num_levels: Number of hierarchy levels (default: 3)
        d_phase_levels: Phase dimension per level (default: (128, 256, 512))
        chunk_sizes: Chunk sizes per level (default: (1, 8, 64))
        boundary_threshold: Threshold for boundary detection (default: 0.5)
        boundary_temperature: Temperature for soft boundaries (default: 1.0)
        target_boundary_rate: Target rate for boundary regularization (default: 0.15)
        window_size: Local attention window size (default: 64)
        num_proposals: Number of Quad proposals per level (default: 4)
        dropout: Dropout rate (default: 0.1)
    """
    num_levels: int = 3
    d_phase_levels: Tuple[int, ...] = (128, 256, 512)
    chunk_sizes: Tuple[int, ...] = (1, 8, 64)
    boundary_threshold: float = 0.5
    boundary_temperature: float = 1.0
    target_boundary_rate: float = 0.15
    window_size: int = 64
    num_proposals: int = 4
    dropout: float = 0.1


class BoundaryDetector(nn.Module):
    """
    Learns to detect semantic boundaries for hierarchical processing.

    Uses Straight-Through Estimator (STE) for binary gradients during training.
    This allows backpropagation through hard boundary decisions.
    """

    def __init__(
        self,
        d_input: int,
        d_phase: int,
        threshold: float = 0.5,
        temperature: float = 1.0,
    ):
        super().__init__()
        self.threshold = threshold
        self.temperature = temperature

        # Boundary prediction from hidden state + phase state
        self.boundary_predictor = nn.Sequential(
            nn.Linear(d_input + d_phase, d_input // 2),
            nn.ReLU(),
            nn.Linear(d_input // 2, 1),
        )

    def forward(
        self,
        h: Tensor,           # [B, N, D] or [B, D] current hidden state
        phase: Tensor,       # [B, D_phase] phase state
    ) -> Tuple[Tensor, Tensor]:
        """
        Compute boundary probability and binary decision.

        Args:
            h: Hidden state, either [B, N, D] for sequence or [B, D] for single
            phase: Phase state [B, D_phase]

        Returns:
            z_soft: Boundary probability (for training)
            z_hard: Binary boundary decision (for gating)
        """
        # Handle both batched and unbatched inputs
        if h.dim() == 2:
            h = h.unsqueeze(1)  # [B, 1, D]

        B, N, D = h.shape

        # Expand phase to match sequence length
        phase_expanded = phase.unsqueeze(1).expand(-1, N, -1)  # [B, N, D_phase]

        # Concatenate and predict
        combined = torch.cat([h, phase_expanded], dim=-1)  # [B, N, D + D_phase]
        logits = self.boundary_predictor(combined).squeeze(-1)  # [B, N]

        # Soft probability
        z_soft = torch.sigmoid(logits / self.temperature)

        # Hard decision with Straight-Through Estimator
        z_hard = (z_soft > self.threshold).float()
        z_hard = z_soft + (z_hard - z_soft).detach()  # STE trick

        # Squeeze if input was unbatched
        if N == 1:
            z_soft = z_soft.squeeze(1)
            z_hard = z_hard.squeeze(1)

        return z_soft, z_hard


class HierarchicalPhaseIntegrator(nn.Module):
    """
    Phase Integrator operating at multiple timescales.

    Level 1: Fast (every token) - syntax, local context
    Level 2: Medium (boundary-triggered) - phrases, semantic units
    Level 3: Slow (major transitions) - paragraphs, topics

    Each level maintains its own phase state, updated at different frequencies.
    Top-down modulation allows slower layers to influence faster ones.
    """

    def __init__(
        self,
        d_model: int,
        d_phase_levels: Tuple[int, ...] = (128, 256, 512),
        num_levels: int = 3,
        boundary_threshold: float = 0.5,
        boundary_temperature: float = 1.0,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.num_levels = min(num_levels, len(d_phase_levels))
        self.d_phase_levels = d_phase_levels[:self.num_levels]

        # Phase update GRU for each level
        self.phase_grus = nn.ModuleList([
            nn.GRUCell(d_model, d_phase)
            for d_phase in self.d_phase_levels
        ])

        # Boundary detectors between levels (num_levels - 1 detectors)
        self.boundary_detectors = nn.ModuleList([
            BoundaryDetector(d_model, self.d_phase_levels[i], boundary_threshold, boundary_temperature)
            for i in range(self.num_levels - 1)
        ])

        # Top-down projection (slower → faster)
        self.top_down_projections = nn.ModuleList([
            nn.Linear(self.d_phase_levels[i+1], self.d_phase_levels[i])
            for i in range(self.num_levels - 1)
        ])

        # Output fusion
        total_phase_dim = sum(self.d_phase_levels)
        self.fusion = nn.Linear(d_model + total_phase_dim, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: Tensor,                                    # [B, N, D]
        phase_states: Optional[List[Tensor]] = None,  # List of [B, D_phase_i]
    ) -> Tuple[Tensor, List[Tensor], Dict[str, Tensor]]:
        """
        Hierarchical phase integration.

        Args:
            x: Input tensor [B, N, D]
            phase_states: Optional list of phase states per level

        Returns:
            output: [B, N, D] integrated output
            phase_states: Updated phase states for each level
            aux: Boundary statistics and diagnostics
        """
        B, N, D = x.shape
        device = x.device

        # Initialize phase states if not provided
        if phase_states is None:
            phase_states = [
                torch.zeros(B, d_phase, device=device)
                for d_phase in self.d_phase_levels
            ]

        # Storage for outputs and boundaries
        level_outputs = [[] for _ in range(self.num_levels)]
        all_boundaries = {f"level_{i}": [] for i in range(self.num_levels - 1)}

        # Process token by token
        for t in range(N):
            x_t = x[:, t, :]  # [B, D]

            # Level 1: Always updates (fast timescale)
            h_1 = self.phase_grus[0](x_t, phase_states[0])
            phase_states[0] = h_1
            level_outputs[0].append(h_1)

            # Process higher levels with boundary gating
            for level in range(1, self.num_levels):
                # Boundary detection for level-1 → level
                z_soft, z_hard = self.boundary_detectors[level - 1](
                    x_t, phase_states[level - 1]
                )
                all_boundaries[f"level_{level - 1}"].append(z_hard)

                # Update this level only at boundaries
                if z_hard.any():
                    # Get top-down context from higher level (if available)
                    if level < self.num_levels - 1:
                        top_down = self.top_down_projections[level](phase_states[level + 1])
                    else:
                        top_down = torch.zeros_like(phase_states[level])

                    # Mask for samples where boundary fired
                    mask = z_hard.unsqueeze(-1)  # [B, 1]

                    # Compute new state
                    h_new = self.phase_grus[level](x_t, phase_states[level] + top_down[:, :phase_states[level].size(-1)])

                    # Selective update
                    phase_states[level] = mask * h_new + (1 - mask) * phase_states[level]

                level_outputs[level].append(phase_states[level])

        # Stack outputs [B, N, D_phase]
        level_outputs = [
            torch.stack(outputs, dim=1)
            for outputs in level_outputs
        ]

        # Stack boundaries [B, N]
        boundary_tensors = {
            key: torch.stack(vals, dim=1) if vals else None
            for key, vals in all_boundaries.items()
        }

        # Hierarchical fusion
        all_phases = torch.cat(level_outputs, dim=-1)  # [B, N, sum(D_phase)]
        combined = torch.cat([x, all_phases], dim=-1)
        output = self.fusion(combined)
        output = self.dropout(output)

        # Compute boundary statistics
        aux = {
            "level_outputs": level_outputs,
        }

        # Add boundary rates for each level
        for i in range(self.num_levels - 1):
            if boundary_tensors[f"level_{i}"] is not None:
                aux[f"boundary_rate_level_{i}"] = boundary_tensors[f"level_{i}"].mean()
                aux[f"boundary_positions_level_{i}"] = boundary_tensors[f"level_{i}"]

        # Overall boundary rate (from level 0 → 1)
        if boundary_tensors.get("level_0") is not None:
            aux["boundary_rate"] = boundary_tensors["level_0"].mean()
            aux["boundary_positions"] = boundary_tensors["level_0"]
        else:
            aux["boundary_rate"] = torch.tensor(0.0, device=device)

        return output, phase_states, aux


class HierarchicalQuadProposal(nn.Module):
    """
    Quad Proposal with hierarchical retrieval at different granularities.

    Level 1: Token-level retrieval (fine-grained)
    Level 2: Chunk-level retrieval (phrases/sentences)
    Level 3: Document-level retrieval (coarse-grained)
    """

    def __init__(
        self,
        d_model: int,
        num_proposals: int = 4,
        num_levels: int = 3,
        chunk_sizes: Tuple[int, ...] = (1, 8, 64),
    ):
        super().__init__()
        self.d_model = d_model
        self.num_proposals = num_proposals
        self.num_levels = min(num_levels, len(chunk_sizes))
        self.chunk_sizes = chunk_sizes[:self.num_levels]

        # Proposal generators for each level
        self.proposal_generators = nn.ModuleList([
            nn.Linear(d_model, d_model * num_proposals)
            for _ in range(self.num_levels)
        ])

        # Retrieval keys for each level
        self.key_projections = nn.ModuleList([
            nn.Linear(d_model, d_model)
            for _ in range(self.num_levels)
        ])

        # Level-wise scoring
        self.level_scorers = nn.ModuleList([
            nn.Linear(d_model * 2, 1)
            for _ in range(self.num_levels)
        ])

        # Cross-level fusion
        self.cross_level_fusion = nn.Linear(d_model * self.num_levels, d_model)

    def forward(
        self,
        x: Tensor,                    # [B, N, D]
        memory_banks: Optional[List[Tensor]] = None,  # List of [B, M_i, D]
        boundaries: Optional[Tensor] = None,  # [B, N] boundary indicators
    ) -> Tuple[Tensor, Dict[str, Tensor]]:
        """
        Hierarchical retrieval with boundary-aware chunking.

        Args:
            x: Input tensor [B, N, D]
            memory_banks: Optional list of memory banks per level
            boundaries: Optional boundary indicators

        Returns:
            retrieved: [B, N, D] fused retrieval result
            aux: Per-level retrieval statistics
        """
        B, N, D = x.shape
        device = x.device

        if memory_banks is None:
            memory_banks = [None] * self.num_levels

        level_retrievals = []
        aux = {}

        for level in range(self.num_levels):
            chunk_size = self.chunk_sizes[level]
            generator = self.proposal_generators[level]
            key_proj = self.key_projections[level]
            scorer = self.level_scorers[level]

            # Chunk the input at this granularity
            if chunk_size > 1 and N >= chunk_size:
                # Average pool to create chunk representations
                x_chunked = F.avg_pool1d(
                    x.transpose(1, 2),
                    kernel_size=chunk_size,
                    stride=chunk_size,
                    ceil_mode=True
                ).transpose(1, 2)  # [B, N//chunk_size, D]
            else:
                x_chunked = x

            N_chunks = x_chunked.size(1)

            # Generate proposals
            proposals = generator(x_chunked)  # [B, N_chunks, D * num_proposals]
            proposals = proposals.view(B, N_chunks, self.num_proposals, D)

            # Retrieve from memory bank
            if level < len(memory_banks) and memory_banks[level] is not None:
                memory = memory_banks[level]  # [B, M, D]
                keys = key_proj(memory)  # [B, M, D]

                # Compute attention scores [B, N_chunks, num_proposals, M]
                scores = torch.einsum('bnpd,bmd->bnpm', proposals, keys)
                attn = F.softmax(scores, dim=-1)

                # Retrieve weighted sum [B, N_chunks, num_proposals, D]
                retrieved = torch.einsum('bnpm,bmd->bnpd', attn, memory)

                # Score proposals
                combined = torch.cat([proposals, retrieved], dim=-1)  # [B, N_chunks, num_proposals, 2D]
                proposal_scores = scorer(combined).squeeze(-1)  # [B, N_chunks, num_proposals]

                # V10.11: Differentiable proposal selection via softmax weighting.
                # Previous: argmax (non-differentiable) → no gradient through selection
                # → proposals never learned which retrieval pattern to prefer.
                # Now: soft-select = weighted sum of all proposals by their scores.
                # At inference, this still peaks on the best proposal (softmax is
                # sharp for confident scores), but gradients flow to all proposals.
                selection_weights = F.softmax(proposal_scores, dim=-1)  # [B, N_chunks, num_proposals]
                best_retrieved = torch.einsum('bnp,bnpd->bnd', selection_weights, retrieved)

                # Upsample back to original resolution if needed
                if chunk_size > 1 and N_chunks < N:
                    best_retrieved = F.interpolate(
                        best_retrieved.transpose(1, 2),
                        size=N,
                        mode='nearest'
                    ).transpose(1, 2)

                level_retrievals.append(best_retrieved)
                aux[f"level_{level}_scores"] = proposal_scores.detach()
            else:
                # No memory at this level, use zeros
                level_retrievals.append(torch.zeros(B, N, D, device=device))

        # Fuse across levels
        stacked = torch.cat(level_retrievals, dim=-1)  # [B, N, D * num_levels]
        retrieved = self.cross_level_fusion(stacked)

        return retrieved, aux


class HPQuadBlock(nn.Module):
    """
    Complete Hierarchical Phase-Quad block.

    Combines:
    - Local attention (Level 1)
    - Hierarchical Phase Integrator (Levels 1-3)
    - Hierarchical Quad Proposal (multi-granularity retrieval)
    - Top-down modulation
    """

    def __init__(
        self,
        d_model: int,
        n_heads: int = 8,
        d_phase_levels: Tuple[int, ...] = (128, 256, 512),
        num_levels: int = 3,
        window_size: int = 64,
        chunk_sizes: Tuple[int, ...] = (1, 8, 64),
        boundary_threshold: float = 0.5,
        boundary_temperature: float = 1.0,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.d_model = d_model
        self.num_levels = num_levels

        # Level 1: Local attention
        self.local_attention = nn.MultiheadAttention(
            d_model, n_heads, dropout=dropout, batch_first=True
        )
        self.local_norm = nn.LayerNorm(d_model)

        # Hierarchical Phase Integrator
        self.phase_integrator = HierarchicalPhaseIntegrator(
            d_model=d_model,
            d_phase_levels=d_phase_levels,
            num_levels=num_levels,
            boundary_threshold=boundary_threshold,
            boundary_temperature=boundary_temperature,
            dropout=dropout,
        )

        # Hierarchical Quad Proposal
        self.quad_proposal = HierarchicalQuadProposal(
            d_model=d_model,
            num_proposals=4,
            num_levels=num_levels,
            chunk_sizes=chunk_sizes,
        )

        # FFN
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_model * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 4, d_model),
            nn.Dropout(dropout),
        )
        self.ffn_norm = nn.LayerNorm(d_model)

        # Final output projection
        self.output_proj = nn.Linear(d_model * 2, d_model)
        self.output_norm = nn.LayerNorm(d_model)

    def forward(
        self,
        x: Tensor,
        phase_states: Optional[List[Tensor]] = None,
        memory_banks: Optional[List[Tensor]] = None,
        mask: Optional[Tensor] = None,
    ) -> Tuple[Tensor, List[Tensor], Dict[str, Tensor]]:
        """
        Forward pass through HP-Quad block.

        Args:
            x: [B, N, D] input
            phase_states: List of phase states per level
            memory_banks: List of memory banks per level for retrieval
            mask: Optional attention mask

        Returns:
            output: [B, N, D]
            phase_states: Updated phase states
            aux: Diagnostics including boundary rates
        """
        B, N, D = x.shape

        # Level 1: Local attention
        x_local = self.local_norm(x)
        x_local, _ = self.local_attention(x_local, x_local, x_local, attn_mask=mask)
        x = x + x_local

        # Hierarchical Phase Integration
        x_phase, phase_states, phase_aux = self.phase_integrator(x, phase_states)

        # Hierarchical Quad Proposal
        if memory_banks is None:
            memory_banks = [None] * self.num_levels
        x_retrieved, quad_aux = self.quad_proposal(
            x_phase,
            memory_banks,
            boundaries=phase_aux.get("boundary_positions"),
        )

        # Combine phase and retrieval
        x_combined = torch.cat([x_phase, x_retrieved], dim=-1)
        x_combined = self.output_proj(x_combined)
        x = x + x_combined

        # FFN
        x_ffn = self.ffn_norm(x)
        x = x + self.ffn(x_ffn)

        # Collect aux
        aux = {
            **phase_aux,
            **quad_aux,
        }

        return x, phase_states, aux


class HPQuadBenchmark:
    """
    Benchmark utilities for HP-Quad.

    Compares standard vs hierarchical processing on:
    - Throughput
    - Boundary detection quality
    - Memory efficiency
    - Long-range dependency handling
    """

    def __init__(self, d_model: int, device: str = "cuda"):
        self.d_model = d_model
        self.device = device

    def benchmark_throughput(
        self,
        standard_model: nn.Module,
        hp_model: HPQuadBlock,
        batch_size: int = 32,
        seq_len: int = 512,
        num_iterations: int = 50,
        warmup: int = 10,
    ) -> Dict[str, float]:
        """
        Compare throughput between standard and HP-Quad.

        Returns:
            Dict with tokens/sec for each variant
        """
        x = torch.randn(batch_size, seq_len, self.d_model, device=self.device)
        total_tokens = batch_size * seq_len

        results = {}

        # Benchmark standard
        standard_model.eval()
        with torch.no_grad():
            # Warmup
            for _ in range(warmup):
                _ = standard_model(x)

            if self.device == "cuda":
                torch.cuda.synchronize()

            start = time.perf_counter()
            for _ in range(num_iterations):
                _ = standard_model(x)

            if self.device == "cuda":
                torch.cuda.synchronize()

            standard_time = time.perf_counter() - start
            results["standard_tokens_per_sec"] = (total_tokens * num_iterations) / standard_time

        # Benchmark HP-Quad
        hp_model.eval()
        with torch.no_grad():
            # Warmup
            for _ in range(warmup):
                _, _, _ = hp_model(x)

            if self.device == "cuda":
                torch.cuda.synchronize()

            start = time.perf_counter()
            for _ in range(num_iterations):
                _, _, _ = hp_model(x)

            if self.device == "cuda":
                torch.cuda.synchronize()

            hp_time = time.perf_counter() - start
            results["hp_tokens_per_sec"] = (total_tokens * num_iterations) / hp_time

        # Compute relative performance
        results["speedup"] = results["hp_tokens_per_sec"] / results["standard_tokens_per_sec"]

        return results

    def benchmark_boundary_detection(
        self,
        hp_model: HPQuadBlock,
        batch_size: int = 16,
        seq_len: int = 256,
    ) -> Dict[str, float]:
        """
        Analyze boundary detection behavior.

        Returns:
            Dict with boundary statistics
        """
        hp_model.eval()
        x = torch.randn(batch_size, seq_len, self.d_model, device=self.device)

        with torch.no_grad():
            _, _, aux = hp_model(x)

        results = {
            "boundary_rate": aux.get("boundary_rate", torch.tensor(0.0)).item(),
        }

        # Per-level rates if available
        for i in range(hp_model.num_levels - 1):
            key = f"boundary_rate_level_{i}"
            if key in aux:
                results[key] = aux[key].item()

        return results

    def full_benchmark(
        self,
        num_levels: int = 3,
        d_phase_levels: Tuple[int, ...] = (128, 256, 512),
        chunk_sizes: Tuple[int, ...] = (1, 8, 64),
        batch_size: int = 32,
        seq_len: int = 512,
    ) -> Dict[str, any]:
        """
        Run full benchmark suite.

        Returns comprehensive diagnostics for decision-making.
        """
        # Create models
        # Standard single-level model
        standard_model = HPQuadBlock(
            d_model=self.d_model,
            d_phase_levels=(256,),
            num_levels=1,
            chunk_sizes=(1,),
        ).to(self.device)

        # Hierarchical HP-Quad
        hp_model = HPQuadBlock(
            d_model=self.d_model,
            d_phase_levels=d_phase_levels,
            num_levels=num_levels,
            chunk_sizes=chunk_sizes,
        ).to(self.device)

        # Throughput benchmark
        throughput = self.benchmark_throughput(
            standard_model, hp_model, batch_size, seq_len
        )

        # Boundary detection
        boundary = self.benchmark_boundary_detection(hp_model, batch_size, seq_len)

        # Parameter count
        standard_params = sum(p.numel() for p in standard_model.parameters())
        hp_params = sum(p.numel() for p in hp_model.parameters())

        return {
            "throughput": throughput,
            "boundary": boundary,
            "params": {
                "standard": standard_params,
                "hp_quad": hp_params,
                "ratio": hp_params / standard_params,
            },
            "config": {
                "d_model": self.d_model,
                "num_levels": num_levels,
                "d_phase_levels": d_phase_levels,
                "chunk_sizes": chunk_sizes,
            },
        }


def create_hp_quad(
    d_model: int,
    config: Optional[HPQuadConfig] = None,
) -> HPQuadBlock:
    """
    Factory function to create HP-Quad with config.

    Args:
        d_model: Model dimension
        config: HP-Quad configuration (uses defaults if None)

    Returns:
        Configured HPQuadBlock module
    """
    if config is None:
        config = HPQuadConfig()

    return HPQuadBlock(
        d_model=d_model,
        d_phase_levels=config.d_phase_levels,
        num_levels=config.num_levels,
        chunk_sizes=config.chunk_sizes,
        boundary_threshold=config.boundary_threshold,
        boundary_temperature=config.boundary_temperature,
        window_size=config.window_size,
        dropout=config.dropout,
    )
