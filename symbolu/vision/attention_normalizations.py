"""
Alternative attention normalizations for Phase-Quad architecture.

Implements Lagrangian-derived attention weight normalizations as alternatives
to standard softmax. Each normalization corresponds to a different regularizer
in the constrained optimization:

    max_{a in Delta^n}  a^T s  +  tau * R(a)

where R(a) is the regularizer and Delta^n is the probability simplex.

Supported normalizations:

1. **Softmax** (baseline): R(a) = H(a) = -sum_i a_i log a_i  (Shannon entropy)
   Solution: a_i = exp(s_i/tau) / sum_j exp(s_j/tau)

2. **Sparsemax**: R(a) = -0.5 ||a||_2^2  (negative squared L2 norm)
   Solution: Euclidean projection of scores onto the simplex.
   Produces exact zeros -> sparse attention.

3. **Entmax(alpha)**: Generalizes softmax (alpha=1) and sparsemax (alpha=2).
   alpha=1.5 gives a practical sparsity/softness tradeoff.
   R(a) = Tsallis entropy with parameter alpha.

4. **Kernel (linear) attention**: Replace softmax with positive feature map phi.
   Attn(Q,K,V) = phi(Q)(phi(K)^T V) / phi(Q)(phi(K)^T 1)
   O(n*d) instead of O(n^2) but quality depends on kernel choice.

References:
- Martins & Astudillo (2016): "From Softmax to Sparsemax"
- Peters et al. (2019): "Sparse Sequence-to-Sequence Models" (entmax)
- Katharopoulos et al. (2020): "Transformers are RNNs" (linear attention)
"""

from typing import Optional, Literal
from enum import Enum

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


class AttentionNormType(Enum):
    """Available attention normalization types."""
    SOFTMAX = "softmax"
    SPARSEMAX = "sparsemax"
    ENTMAX15 = "entmax15"       # entmax with alpha=1.5
    ENTMAX_ALPHA = "entmax"     # entmax with configurable alpha
    KERNEL_ELU = "kernel_elu"   # Linear attention with ELU+1 kernel
    KERNEL_RBF = "kernel_rbf"   # Linear attention with random RBF features
    TOP_M_SOFTMAX = "top_m_softmax"  # Top-M mask + softmax (production variant)


# ---------------------------------------------------------------------------
# Sparsemax: Euclidean projection onto the simplex
# ---------------------------------------------------------------------------

def _sparsemax_threshold(z: Tensor, dim: int = -1) -> Tensor:
    """
    Compute the sparsemax threshold tau for the simplex projection.

    For input z, sparsemax solves:
        min_{p in Delta} ||p - z||_2^2
    which yields p_i = max(z_i - tau, 0) where tau is chosen so sum(p) = 1.

    This is equivalent to finding the largest k such that:
        (sum of top-k z values - 1) / k < z_{(k)}

    Args:
        z: Input scores [..., n].
        dim: Dimension to normalize over.

    Returns:
        tau: Threshold values [..., 1].
    """
    z_sorted, _ = z.sort(dim=dim, descending=True)
    n = z.size(dim)
    rng = torch.arange(1, n + 1, device=z.device, dtype=z.dtype)

    # Reshape range for broadcasting
    shape = [1] * z.dim()
    shape[dim] = n
    rng = rng.view(shape)

    # Cumulative sum of sorted values
    cumsum = z_sorted.cumsum(dim=dim)

    # Check: is z_{(k)} > (cumsum_{(k)} - 1) / k ?
    support = z_sorted > (cumsum - 1) / rng

    # Number of elements in the support
    k = support.sum(dim=dim, keepdim=True).clamp(min=1)

    # Threshold
    tau = (cumsum.gather(dim, k.long() - 1) - 1) / k.float()
    return tau


def sparsemax(z: Tensor, dim: int = -1) -> Tensor:
    """
    Sparsemax: Euclidean projection of scores onto the probability simplex.

    Replaces softmax with a sparser alternative derived from the Lagrangian:
        max_{a in Delta^n}  a^T s  -  0.5 ||a||_2^2

    Properties:
    - Produces exact zeros (sparse attention weights)
    - No exponential blow-up
    - Winner-take-most behavior
    - Differentiable (subgradient where outputs hit zero)

    Args:
        z: Input scores (logits) of any shape.
        dim: Dimension to normalize over (default: -1).

    Returns:
        p: Sparse probability distribution, same shape as z.
    """
    tau = _sparsemax_threshold(z, dim=dim)
    p = (z - tau).clamp(min=0)
    return p


class Sparsemax(nn.Module):
    """Module wrapper for sparsemax."""

    def __init__(self, dim: int = -1):
        super().__init__()
        self.dim = dim

    def forward(self, z: Tensor) -> Tensor:
        return sparsemax(z, dim=self.dim)


# ---------------------------------------------------------------------------
# Entmax: Tsallis-entropy regularized attention (alpha-entmax)
# ---------------------------------------------------------------------------

def _entmax_bisect(
    z: Tensor,
    alpha: float = 1.5,
    dim: int = -1,
    n_iter: int = 50,
    ensure_sum_one: bool = True,
) -> Tensor:
    """
    Compute entmax via bisection on the threshold.

    For alpha > 1, entmax_alpha solves:
        max_{p in Delta}  p^T z  +  H_alpha(p)

    where H_alpha is the Tsallis alpha-entropy:
        H_alpha(p) = (1 - sum_i p_i^alpha) / (alpha * (alpha - 1))

    The solution has the form:
        p_i = [(alpha - 1) z_i - tau]_+^{1/(alpha-1)}

    where tau is chosen to satisfy sum(p) = 1.

    Args:
        z: Input scores [..., n].
        alpha: Entmax alpha parameter. alpha=1 -> softmax, alpha=2 -> sparsemax.
        dim: Dimension to normalize.
        n_iter: Number of bisection iterations.
        ensure_sum_one: Re-normalize output to ensure exact sum=1.

    Returns:
        p: Attention weights [..., n].
    """
    alpha_minus_1 = alpha - 1.0
    inv_alpha_minus_1 = 1.0 / alpha_minus_1

    # Bisection bounds for threshold tau
    z_max = z.max(dim=dim, keepdim=True).values
    z_min = z.min(dim=dim, keepdim=True).values

    # tau must be in range such that at least one p_i > 0
    tau_lo = z_min - 1.0
    tau_hi = z_max

    for _ in range(n_iter):
        tau_mid = (tau_lo + tau_hi) / 2.0

        # p_i = max(0, (alpha-1)*z_i - tau)^{1/(alpha-1)}
        inner = (alpha_minus_1 * z - tau_mid).clamp(min=0)
        p = inner.pow(inv_alpha_minus_1)

        # Check if sum(p) > 1 or < 1
        p_sum = p.sum(dim=dim, keepdim=True)
        mask = p_sum > 1.0

        # If sum > 1, increase tau; if sum < 1, decrease tau
        tau_lo = torch.where(mask, tau_mid, tau_lo)
        tau_hi = torch.where(mask, tau_hi, tau_mid)

    # Final computation
    inner = (alpha_minus_1 * z - tau_mid).clamp(min=0)
    p = inner.pow(inv_alpha_minus_1)

    if ensure_sum_one:
        p = p / (p.sum(dim=dim, keepdim=True) + 1e-10)

    return p


def entmax(z: Tensor, alpha: float = 1.5, dim: int = -1) -> Tensor:
    """
    Entmax: alpha-entmax attention normalization.

    Generalizes softmax (alpha=1) and sparsemax (alpha=2) with tunable
    sparsity via the alpha parameter.

    For Phase-Quad, entmax(1.5) is recommended as it provides:
    - Moderate sparsity (fewer but stronger attention weights)
    - Smooth gradients (unlike sparsemax which has kinks)
    - Compatible with TopK selection (natural synergy)

    The Lagrangian formulation:
        max_{a in Delta^n}  a^T s  +  H_alpha(a)
    where H_alpha is the Tsallis alpha-entropy.

    Args:
        z: Input scores (logits).
        alpha: Sparsity parameter.
            - alpha=1.0: softmax (dense, no zeros)
            - alpha=1.5: moderate sparsity (recommended)
            - alpha=2.0: sparsemax (maximum sparsity)
        dim: Dimension to normalize.

    Returns:
        p: Attention weights with possible exact zeros.
    """
    if alpha == 1.0:
        return F.softmax(z, dim=dim)
    if alpha == 2.0:
        return sparsemax(z, dim=dim)

    return _entmax_bisect(z, alpha=alpha, dim=dim)


def entmax15(z: Tensor, dim: int = -1) -> Tensor:
    """
    Entmax with alpha=1.5 (recommended default).

    This is the sweet spot between softmax (alpha=1, fully dense)
    and sparsemax (alpha=2, maximally sparse). Provides:
    - Natural sparsity without hard cutoffs
    - Better gradient flow than sparsemax
    - Improved interpretability over softmax
    """
    return entmax(z, alpha=1.5, dim=dim)


class Entmax(nn.Module):
    """Module wrapper for entmax with configurable alpha."""

    def __init__(self, alpha: float = 1.5, dim: int = -1):
        super().__init__()
        self.alpha = alpha
        self.dim = dim

    def forward(self, z: Tensor) -> Tensor:
        return entmax(z, alpha=self.alpha, dim=self.dim)


# ---------------------------------------------------------------------------
# Top-M Softmax: deterministic sparse attention (production variant)
# ---------------------------------------------------------------------------

def top_m_softmax(z: Tensor, m: int, dim: int = -1) -> Tensor:
    """
    Top-M mask + softmax: keep only the top-M logits, softmax over them.

    Production-grade sparse attention that provides:
    - Deterministic sparsity: exactly M non-zero weights, always
    - Stable gradients: softmax over M elements (well-understood)
    - Predictable compute: fixed sparsity ratio regardless of input
    - Compatible with learned temperature for sharpness control

    Equivalent to top-k sampling applied to attention weights.
    For Phase-Quad with K proposals, M << K concentrates attention
    on the most relevant proposals while maintaining softmax's smooth
    gradient landscape.

    Args:
        z: Input scores (logits) of any shape.
        m: Number of top elements to keep (rest are masked to -inf).
        dim: Dimension to normalize over (default: -1).

    Returns:
        p: Attention weights with exactly (n - M) zeros per row.
    """
    n = z.size(dim)
    m = min(m, n)  # Can't keep more than we have

    # Find the top-M values and their indices
    topk_vals, topk_idx = z.topk(m, dim=dim)

    # Create mask: -inf everywhere, then scatter top-M values back
    mask = torch.full_like(z, float("-inf"))
    mask.scatter_(dim, topk_idx, topk_vals)

    return F.softmax(mask, dim=dim)


class TopMSoftmax(nn.Module):
    """Module wrapper for top-M softmax."""

    def __init__(self, m: int, dim: int = -1):
        super().__init__()
        self.m = m
        self.dim = dim

    def forward(self, z: Tensor) -> Tensor:
        return top_m_softmax(z, m=self.m, dim=self.dim)


# ---------------------------------------------------------------------------
# Kernel (Linear) Attention: softmax-free via positive feature maps
# ---------------------------------------------------------------------------

def elu_feature_map(x: Tensor) -> Tensor:
    """
    ELU+1 feature map for linear attention.

    phi(x) = elu(x) + 1

    Ensures positivity while preserving gradient flow.
    Simple and effective for moderate sequence lengths.

    Args:
        x: Input features [..., d].

    Returns:
        phi_x: Positive features [..., d].
    """
    return F.elu(x) + 1.0


def rbf_random_features(
    x: Tensor,
    projection_matrix: Tensor,
    is_query: bool = True,
) -> Tensor:
    """
    Random Fourier features for approximate RBF kernel attention.

    Approximates softmax kernel via:
        k(q, k) approx phi(q)^T phi(k)
    where phi uses random projections from N(0, 1).

    Args:
        x: Input features [..., d].
        projection_matrix: Random projection [d, m] from N(0, 1).
        is_query: If True, applies query-specific normalization.

    Returns:
        phi_x: Random features [..., m].
    """
    # Project: x @ W -> [..., m]
    projected = x @ projection_matrix

    # Random Fourier features: [cos(x@W), sin(x@W)] / sqrt(m)
    m = projection_matrix.size(1) // 2
    cos_proj = torch.cos(projected[..., :m])
    sin_proj = torch.sin(projected[..., :m])

    features = torch.cat([cos_proj, sin_proj], dim=-1)

    # Normalize
    normalizer = 1.0 / (m ** 0.5)
    features = features * normalizer

    # For numerical stability, apply exp normalization for queries
    if is_query:
        # Subtract max for numerical stability (approximation of softmax kernel)
        data_dash = features * (x.shape[-1] ** -0.25)
    else:
        data_dash = features * (x.shape[-1] ** -0.25)

    return data_dash.clamp(min=1e-6)  # Ensure positivity


class KernelAttention(nn.Module):
    """
    Kernel (linear) attention module.

    Replaces softmax(Q K^T / sqrt(d)) V with:
        phi(Q) (phi(K)^T V) / (phi(Q) (phi(K)^T 1))

    This changes complexity from O(n^2 d) to O(n d^2) which is beneficial
    when n >> d (long sequences).

    For Phase-Quad with TopK proposals (K typically 64), the sequence
    length is small, so this is mainly useful for the local mixer path
    when operating on larger windows.

    Args:
        feature_map: Type of positive feature map.
        head_dim: Dimension per attention head (for RBF features).
        num_features: Number of random features for RBF kernel.
    """

    def __init__(
        self,
        feature_map: Literal["elu", "rbf"] = "elu",
        head_dim: int = 64,
        num_features: int = 256,
    ):
        super().__init__()
        self.feature_map_type = feature_map

        if feature_map == "rbf":
            # Random projection matrix (frozen, not learned)
            projection = torch.randn(head_dim, num_features)
            self.register_buffer("projection_matrix", projection)
        else:
            self.projection_matrix = None

    def phi(self, x: Tensor, is_query: bool = True) -> Tensor:
        """Apply the positive feature map."""
        if self.feature_map_type == "elu":
            return elu_feature_map(x)
        elif self.feature_map_type == "rbf":
            return rbf_random_features(x, self.projection_matrix, is_query)
        else:
            raise ValueError(f"Unknown feature map: {self.feature_map_type}")

    def forward(
        self,
        q: Tensor,
        k: Tensor,
        v: Tensor,
    ) -> Tensor:
        """
        Compute kernel attention.

        Args:
            q: Queries [B, H, N_q, D_h].
            k: Keys [B, H, N_k, D_h].
            v: Values [B, H, N_k, D_h].

        Returns:
            output: [B, H, N_q, D_h].
        """
        # Apply feature map
        q_prime = self.phi(q, is_query=True)   # [B, H, N_q, D']
        k_prime = self.phi(k, is_query=False)  # [B, H, N_k, D']

        # Compute KV product first: [B, H, D', D_h]
        kv = torch.einsum("bhnd,bhnv->bhdv", k_prime, v)

        # Denominator: [B, H, N_q, 1]
        z = torch.einsum("bhnd,bhd->bhn", q_prime, k_prime.sum(dim=2))
        z = z.unsqueeze(-1).clamp(min=1e-6)  # Avoid division by zero

        # Numerator: [B, H, N_q, D_h]
        output = torch.einsum("bhnd,bhdv->bhnv", q_prime, kv)

        # Normalize
        output = output / z

        return output


# ---------------------------------------------------------------------------
# Unified normalization dispatcher
# ---------------------------------------------------------------------------

def get_attention_normalizer(
    norm_type: AttentionNormType,
    alpha: float = 1.5,
    dim: int = -1,
    head_dim: int = 64,
    num_features: int = 256,
    top_m: int = 8,
) -> nn.Module:
    """
    Factory function to create an attention normalizer module.

    Args:
        norm_type: Type of normalization.
        alpha: Alpha parameter for entmax (ignored for other types).
        dim: Dimension to normalize over (ignored for kernel attention).
        head_dim: Head dimension (for kernel attention RBF features).
        num_features: Number of random features (for RBF kernel).
        top_m: Number of top elements for top-M softmax.

    Returns:
        Module that normalizes attention scores to weights.
    """
    if norm_type == AttentionNormType.SOFTMAX:
        return _SoftmaxNorm(dim=dim)
    elif norm_type == AttentionNormType.SPARSEMAX:
        return Sparsemax(dim=dim)
    elif norm_type == AttentionNormType.ENTMAX15:
        return Entmax(alpha=1.5, dim=dim)
    elif norm_type == AttentionNormType.ENTMAX_ALPHA:
        return Entmax(alpha=alpha, dim=dim)
    elif norm_type == AttentionNormType.TOP_M_SOFTMAX:
        return TopMSoftmax(m=top_m, dim=dim)
    elif norm_type in (AttentionNormType.KERNEL_ELU, AttentionNormType.KERNEL_RBF):
        feature_map = "elu" if norm_type == AttentionNormType.KERNEL_ELU else "rbf"
        return KernelAttention(
            feature_map=feature_map,
            head_dim=head_dim,
            num_features=num_features,
        )
    else:
        raise ValueError(f"Unknown attention normalization type: {norm_type}")


class _SoftmaxNorm(nn.Module):
    """Standard softmax normalization (baseline)."""

    def __init__(self, dim: int = -1):
        super().__init__()
        self.dim = dim

    def forward(self, z: Tensor) -> Tensor:
        return F.softmax(z, dim=self.dim)


# ---------------------------------------------------------------------------
# Sparsity diagnostics
# ---------------------------------------------------------------------------

def attention_sparsity_metrics(weights: Tensor, dim: int = -1) -> dict:
    """
    Compute sparsity diagnostics for attention weights.

    Useful for comparing normalizations. Reports:
    - sparsity: Fraction of exact zeros
    - entropy: Shannon entropy of the distribution
    - gini: Gini coefficient (inequality measure)
    - top1_mass: Mass concentrated in the top-1 element
    - top5_mass: Mass concentrated in the top-5 elements

    Args:
        weights: Attention weights [..., n] summing to ~1 along dim.
        dim: Normalization dimension.

    Returns:
        Dictionary of sparsity metrics.
    """
    with torch.no_grad():
        n = weights.size(dim)

        # Sparsity (fraction of zeros)
        zero_mask = (weights == 0.0)
        sparsity = zero_mask.float().mean().item()

        # Shannon entropy
        log_w = torch.log(weights + 1e-10)
        entropy = -(weights * log_w).sum(dim=dim).mean().item()

        # Maximum possible entropy (uniform distribution)
        max_entropy = torch.log(torch.tensor(float(n))).item()
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

        # Top-1 mass
        top1 = weights.max(dim=dim).values.mean().item()

        # Top-5 mass
        k5 = min(5, n)
        top5 = weights.topk(k5, dim=dim).values.sum(dim=dim).mean().item()

        # Gini coefficient
        sorted_w, _ = weights.sort(dim=dim)
        n_float = float(n)
        indices = torch.arange(1, n + 1, device=weights.device, dtype=weights.dtype)
        shape = [1] * weights.dim()
        shape[dim] = n
        indices = indices.view(shape)
        numerator = (2 * indices - n_float - 1) * sorted_w
        gini = numerator.sum(dim=dim) / (n_float * sorted_w.sum(dim=dim) + 1e-10)
        gini = gini.mean().item()

        return {
            "sparsity": sparsity,
            "entropy": entropy,
            "normalized_entropy": normalized_entropy,
            "top1_mass": top1,
            "top5_mass": top5,
            "gini": gini,
        }


def logit_sharpness_metrics(logits: Tensor, dim: int = -1) -> dict:
    """
    Compute logit sharpness diagnostics BEFORE normalization.

    Logit scale determines how entmax/sparsemax behave — high variance
    logits produce sparser outputs regardless of alpha. Tracking this
    during training reveals whether sparsity drift is caused by alpha
    choice or by Q/K weight growth.

    Reports:
    - logit_std: Standard deviation of logits (primary sharpness indicator)
    - logit_range: Max - min across the normalization dimension
    - logit_mean: Mean logit value (shift indicator)

    Args:
        logits: Raw attention scores before normalization [..., n].
        dim: Dimension that will be normalized.

    Returns:
        Dictionary of logit sharpness metrics.
    """
    with torch.no_grad():
        logit_std = logits.std(dim=dim).mean().item()
        logit_range = (
            logits.max(dim=dim).values - logits.min(dim=dim).values
        ).mean().item()
        logit_mean = logits.mean().item()

        return {
            "logit_std": logit_std,
            "logit_range": logit_range,
            "logit_mean": logit_mean,
        }
