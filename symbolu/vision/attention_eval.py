"""
Evaluation infrastructure for comparing attention normalizations in Phase-Quad.

Provides side-by-side comparison of softmax, sparsemax, entmax, and kernel
attention variants without modifying the original Phase-Quad architecture.

Usage:
    evaluator = AttentionNormEvaluator(embed_dim=768, num_heads=12, topk=64)

    # Run all variants on the same input
    results = evaluator.compare_all(x, proposals, scores)

    # Print comparison table
    evaluator.print_comparison(results)

    # Get recommendation for Phase-Quad
    recommendation = evaluator.recommend(results)

The evaluator measures:
- Sparsity: Fraction of zero attention weights
- Entropy: Information-theoretic spread of attention
- Concentration: How much mass in top elements
- Gradient norms: Training signal quality
- Output similarity: How different each variant's output is from softmax
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from symbolu.vision.attention_normalizations import (
    AttentionNormType,
    sparsemax,
    entmax,
    entmax15,
    top_m_softmax,
    attention_sparsity_metrics,
)
from symbolu.vision.alternative_attention import AlternativeAttentionToProposals


@dataclass
class AttentionVariantResult:
    """Results from evaluating one attention normalization variant."""
    name: str
    norm_type: AttentionNormType
    output: Tensor                     # [B, N, D] output
    attention_weights: Optional[Tensor]  # [B, N, H, K] weights (None for kernel)
    sparsity_metrics: Dict[str, float]
    forward_time_ms: float = 0.0
    grad_norm: float = 0.0
    output_norm: float = 0.0


@dataclass
class ComparisonReport:
    """Comparison report across all variants."""
    variants: List[AttentionVariantResult]
    softmax_baseline: Optional[AttentionVariantResult] = None
    cosine_similarities: Dict[str, float] = field(default_factory=dict)
    recommendation: str = ""


class AttentionNormEvaluator(nn.Module):
    """
    Side-by-side evaluator for attention normalization variants.

    Creates independent instances of AlternativeAttentionToProposals
    with each normalization type and runs them on identical inputs
    for controlled comparison.

    This does NOT modify any existing Phase-Quad modules. It creates
    fresh, independent modules purely for evaluation.

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        topk: Number of proposals K (for output shape inference).
        dropout: Attention dropout (set to 0 for deterministic comparison).
        variants: List of normalization types to compare.
            Default: all implemented variants.
    """

    def __init__(
        self,
        embed_dim: int = 768,
        num_heads: int = 12,
        topk: int = 64,
        dropout: float = 0.0,
        variants: Optional[List[AttentionNormType]] = None,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.topk = topk

        if variants is None:
            variants = [
                AttentionNormType.SOFTMAX,
                AttentionNormType.SPARSEMAX,
                AttentionNormType.ENTMAX15,
                AttentionNormType.ENTMAX_ALPHA,  # entmax(1.3)
                AttentionNormType.TOP_M_SOFTMAX,  # production variant
                AttentionNormType.KERNEL_ELU,
            ]

        self.variant_types = variants

        # Create independent modules for each variant
        self.variant_modules = nn.ModuleDict()
        for vtype in variants:
            # Use alpha=1.3 for the configurable entmax variant
            alpha = 1.3 if vtype == AttentionNormType.ENTMAX_ALPHA else 1.5
            self.variant_modules[vtype.value] = AlternativeAttentionToProposals(
                embed_dim=embed_dim,
                num_heads=num_heads,
                dropout=dropout,
                norm_type=vtype,
                entmax_alpha=alpha,
            )

    @torch.no_grad()
    def compare_all(
        self,
        x: Tensor,
        proposals: Tensor,
        scores: Optional[Tensor] = None,
    ) -> ComparisonReport:
        """
        Run all variants on identical inputs and collect metrics.

        Args:
            x: Current representation [B, N, D].
            proposals: TopK proposals [B, N, K, D].
            scores: Optional retrieval scores [B, N, K].

        Returns:
            ComparisonReport with per-variant results and cross-comparisons.
        """
        results = []
        softmax_output = None

        for vtype in self.variant_types:
            module = self.variant_modules[vtype.value]

            # Forward pass
            output = module(x, proposals, scores)

            # Collect sparsity metrics
            sparsity = module.get_sparsity_metrics()

            result = AttentionVariantResult(
                name=vtype.value,
                norm_type=vtype,
                output=output.detach(),
                attention_weights=None,
                sparsity_metrics=sparsity,
                output_norm=output.norm().item(),
            )
            results.append(result)

            if vtype == AttentionNormType.SOFTMAX:
                softmax_output = output.detach()

        # Compute cosine similarities to softmax baseline
        cosine_sims = {}
        if softmax_output is not None:
            baseline_flat = softmax_output.flatten()
            for r in results:
                if r.norm_type != AttentionNormType.SOFTMAX:
                    variant_flat = r.output.flatten()
                    sim = F.cosine_similarity(
                        baseline_flat.unsqueeze(0),
                        variant_flat.unsqueeze(0),
                    ).item()
                    cosine_sims[r.name] = sim

        report = ComparisonReport(
            variants=results,
            softmax_baseline=next(
                (r for r in results if r.norm_type == AttentionNormType.SOFTMAX),
                None,
            ),
            cosine_similarities=cosine_sims,
        )

        # Generate recommendation
        report.recommendation = self._generate_recommendation(report)

        return report

    def compare_with_gradients(
        self,
        x: Tensor,
        proposals: Tensor,
        scores: Optional[Tensor] = None,
        target: Optional[Tensor] = None,
    ) -> ComparisonReport:
        """
        Compare variants including gradient analysis.

        Runs forward + backward pass to measure gradient norms,
        which indicates training signal quality.

        Args:
            x: Current representation [B, N, D] (requires_grad=True).
            proposals: TopK proposals [B, N, K, D].
            scores: Optional retrieval scores [B, N, K].
            target: Optional target for loss computation [B, N, D].
                If None, uses L2 norm of output as surrogate loss.

        Returns:
            ComparisonReport with gradient analysis.
        """
        results = []
        softmax_output = None

        for vtype in self.variant_types:
            module = self.variant_modules[vtype.value]

            # Ensure clean gradients
            x_var = x.detach().requires_grad_(True)

            # Forward
            output = module(x_var, proposals, scores)

            # Backward with surrogate loss
            if target is not None:
                loss = F.mse_loss(output, target)
            else:
                loss = output.norm()

            loss.backward()

            # Collect gradient norm
            grad_norm = x_var.grad.norm().item() if x_var.grad is not None else 0.0

            sparsity = module.get_sparsity_metrics()

            result = AttentionVariantResult(
                name=vtype.value,
                norm_type=vtype,
                output=output.detach(),
                attention_weights=None,
                sparsity_metrics=sparsity,
                grad_norm=grad_norm,
                output_norm=output.detach().norm().item(),
            )
            results.append(result)

            if vtype == AttentionNormType.SOFTMAX:
                softmax_output = output.detach()

        # Cosine similarities
        cosine_sims = {}
        if softmax_output is not None:
            baseline_flat = softmax_output.flatten()
            for r in results:
                if r.norm_type != AttentionNormType.SOFTMAX:
                    variant_flat = r.output.flatten()
                    sim = F.cosine_similarity(
                        baseline_flat.unsqueeze(0),
                        variant_flat.unsqueeze(0),
                    ).item()
                    cosine_sims[r.name] = sim

        report = ComparisonReport(
            variants=results,
            softmax_baseline=next(
                (r for r in results if r.norm_type == AttentionNormType.SOFTMAX),
                None,
            ),
            cosine_similarities=cosine_sims,
        )
        report.recommendation = self._generate_recommendation(report)
        return report

    def _generate_recommendation(self, report: ComparisonReport) -> str:
        """
        Generate a recommendation based on comparison results.

        Evaluates variants against Phase-Quad desiderata:
        1. Sparsity: Helps TopK proposal selection
        2. Gradient quality: Smooth training
        3. Output stability: Not too far from softmax baseline
        """
        lines = ["Attention Normalization Recommendation for Phase-Quad:"]
        lines.append("=" * 55)

        best_sparse = None
        best_sparse_val = -1.0

        for r in report.variants:
            sparsity = r.sparsity_metrics.get("attn/sparsity", 0.0)
            entropy = r.sparsity_metrics.get("attn/entropy", float("inf"))
            top1 = r.sparsity_metrics.get("attn/top1_mass", 0.0)

            line = (
                f"  {r.name:12s}: "
                f"sparsity={sparsity:.3f}  "
                f"entropy={entropy:.3f}  "
                f"top1={top1:.3f}  "
                f"grad_norm={r.grad_norm:.4f}"
            )
            lines.append(line)

            # Track best sparsity with reasonable output similarity
            sim = report.cosine_similarities.get(r.name, 1.0)
            if sparsity > best_sparse_val and sim > 0.5:
                best_sparse_val = sparsity
                best_sparse = r.name

        lines.append("")

        # Similarity to softmax
        if report.cosine_similarities:
            lines.append("Cosine similarity to softmax baseline:")
            for name, sim in report.cosine_similarities.items():
                lines.append(f"  {name:12s}: {sim:.4f}")
            lines.append("")

        # Recommendation
        if best_sparse and best_sparse != "softmax":
            lines.append(
                f"Recommendation: Use '{best_sparse}' for Phase-Quad proposals."
            )
            lines.append(
                "Rationale: Provides sparsity that complements TopK selection "
                "while maintaining output quality."
            )
        else:
            lines.append(
                "Recommendation: Stick with softmax (alternatives show "
                "no clear advantage on this input)."
            )

        return "\n".join(lines)

    @staticmethod
    def format_comparison_table(report: ComparisonReport) -> str:
        """
        Format comparison results as a readable table.

        Args:
            report: ComparisonReport from compare_all or compare_with_gradients.

        Returns:
            Formatted string table.
        """
        header = (
            f"{'Variant':>12s} | {'Sparsity':>9s} | {'Entropy':>8s} | "
            f"{'Top1':>6s} | {'Top5':>6s} | {'Gini':>6s} | "
            f"{'GradNorm':>9s} | {'CosSim':>7s}"
        )
        separator = "-" * len(header)
        lines = [header, separator]

        for r in report.variants:
            sp = r.sparsity_metrics
            cos_sim = report.cosine_similarities.get(r.name, 1.0)

            line = (
                f"{r.name:>12s} | "
                f"{sp.get('attn/sparsity', 0.0):9.4f} | "
                f"{sp.get('attn/entropy', 0.0):8.4f} | "
                f"{sp.get('attn/top1_mass', 0.0):6.4f} | "
                f"{sp.get('attn/top5_mass', 0.0):6.4f} | "
                f"{sp.get('attn/gini', 0.0):6.4f} | "
                f"{r.grad_norm:9.4f} | "
                f"{cos_sim:7.4f}"
            )
            lines.append(line)

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Standalone normalization comparison (no neural network parameters)
# ---------------------------------------------------------------------------

def compare_normalizations_on_scores(
    scores: Tensor,
    dim: int = -1,
) -> Dict[str, Dict[str, float]]:
    """
    Compare softmax, sparsemax, and entmax(1.5) directly on raw scores.

    Lightweight comparison that doesn't require neural network modules.
    Useful for quick analysis of how different normalizations behave
    on actual score distributions from the Quad retriever.

    Args:
        scores: Raw attention scores [..., n].
        dim: Dimension to normalize.

    Returns:
        Dictionary mapping normalization name -> sparsity metrics.
    """
    results = {}

    with torch.no_grad():
        # Softmax
        w_softmax = F.softmax(scores, dim=dim)
        results["softmax"] = attention_sparsity_metrics(w_softmax, dim=dim)

        # Sparsemax
        w_sparse = sparsemax(scores, dim=dim)
        results["sparsemax"] = attention_sparsity_metrics(w_sparse, dim=dim)

        # Entmax 1.3 (recommended for Phase-Quad)
        w_entmax13 = entmax(scores, alpha=1.3, dim=dim)
        results["entmax13"] = attention_sparsity_metrics(w_entmax13, dim=dim)

        # Entmax 1.5 (standard literature variant)
        w_entmax15 = entmax15(scores, dim=dim)
        results["entmax15"] = attention_sparsity_metrics(w_entmax15, dim=dim)

        # Entmax 1.25 (softer)
        w_entmax125 = entmax(scores, alpha=1.25, dim=dim)
        results["entmax125"] = attention_sparsity_metrics(w_entmax125, dim=dim)

        # Entmax 1.75 (harder)
        w_entmax175 = entmax(scores, alpha=1.75, dim=dim)
        results["entmax175"] = attention_sparsity_metrics(w_entmax175, dim=dim)

        # Top-M softmax (production variant, M=24)
        n = scores.size(dim)
        m = min(24, n)
        w_topm = top_m_softmax(scores, m=m, dim=dim)
        results["top_m_softmax"] = attention_sparsity_metrics(w_topm, dim=dim)

    return results


def analyze_quad_scores_for_attention(
    proposal_scores: Tensor,
) -> Dict[str, Dict[str, float]]:
    """
    Analyze Quad retriever scores to recommend attention normalization.

    Takes raw proposal scores from QuadRetriever and evaluates how
    different normalizations would distribute attention weights.

    This is the recommended entry point for deciding which normalization
    to use in Phase-Quad:

        # After quad retrieval
        proposals, scores = quad_retriever(x, S, meta)

        # Analyze
        analysis = analyze_quad_scores_for_attention(scores)
        # -> Shows sparsity/entropy/concentration for each normalization

    Args:
        proposal_scores: Raw scores from QuadRetriever [B, N, K].

    Returns:
        Comparison metrics for each normalization type.
    """
    return compare_normalizations_on_scores(proposal_scores, dim=-1)
