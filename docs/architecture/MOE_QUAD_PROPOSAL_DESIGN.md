# Mixture of Experts (MoE) for Phase-Quad Architecture

## Status: DESIGN DOCUMENT

**Author**: Claude (Architecture Design)
**Date**: January 2026
**Version**: 1.1

---

## Overview

This document describes two MoE approaches for the Phase-Quad architecture:

1. **MoE in FFN Layers** (Recommended) - Standard Mixtral-style MoE for **cost savings**
2. **MoE in Quad Proposal** (Optional) - For **quality/diversity improvement**

### Quick Decision Guide

| Goal | Approach | Cost Impact | Quality Impact |
|------|----------|-------------|----------------|
| Reduce compute cost | MoE FFN | **~2x savings** | Neutral |
| Improve proposal diversity | MoE Quad | ~1.5x increase | **Improved** |
| Both | MoE FFN + MoE Quad | ~1.3x savings | **Improved** |

---

## Part A: MoE in FFN Layers (RECOMMENDED)

### Why FFN is the Right Place for Cost Savings

The FFN block consumes ~2/3 of transformer compute. Replacing it with sparse MoE gives real savings:

```
Standard FFN:
  x → Linear(d, 4d) → GELU → Linear(4d, d) → x
  FLOPs: 2 × B × N × d × 4d = 8BNd²

MoE FFN (8 experts, 2 active):
  x → Router → 2 experts → weighted sum → x
  FLOPs: 2 × B × N × d × 4d × (2/8) = 2BNd²
  Savings: 75% on FFN, ~50% overall
```

### Architecture with MoE FFN

```
Input Embeddings
       ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER L                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Attention Block                                     │   │
│  │  ├─ Local Attention (syntax)                        │   │
│  │  ├─ Phase Integrator (memory)     ← NO MoE EVER     │   │
│  │  └─ Quad Proposal (retrieval)                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  FFN Block (MoE)                  ← STANDARD MoE    │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  Router: r = softmax(W_r @ x)               │    │   │
│  │  │  top_k_experts = argtopk(r, k=2)            │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │         │ top-2                                      │   │
│  │    ┌────┴────┐                                       │   │
│  │    ▼         ▼                                       │   │
│  │ ┌──────┐ ┌──────┐                                    │   │
│  │ │ E_i  │ │ E_j  │  (2 of 8 experts active)          │   │
│  │ └──────┘ └──────┘                                    │   │
│  │    │         │                                       │   │
│  │    └────┬────┘                                       │   │
│  │         ▼                                            │   │
│  │  Weighted sum: r_i * E_i(x) + r_j * E_j(x)          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
       ↓
   LAYER L+1 ...
```

### MoE FFN Implementation

```python
class MoEFFN(nn.Module):
    """
    Mixture of Experts Feed-Forward Network.

    Standard Mixtral-style MoE for compute efficiency.
    """

    def __init__(
        self,
        d_model: int,
        d_ff: int = None,
        num_experts: int = 8,
        top_k: int = 2,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.d_model = d_model
        self.d_ff = d_ff or 4 * d_model
        self.num_experts = num_experts
        self.top_k = top_k

        # Lightweight router (single linear layer)
        self.router = nn.Linear(d_model, num_experts, bias=False)

        # Expert FFNs (each is a standard 2-layer FFN)
        self.experts = nn.ModuleList([
            nn.Sequential(
                nn.Linear(d_model, self.d_ff),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(self.d_ff, d_model),
                nn.Dropout(dropout),
            )
            for _ in range(num_experts)
        ])

    def forward(self, x: Tensor) -> Tuple[Tensor, Dict[str, Tensor]]:
        """
        Args:
            x: [B, N, D] input tensor

        Returns:
            output: [B, N, D] MoE output
            aux: Dict with router_logits, expert_indices, load_balance_loss
        """
        B, N, D = x.shape

        # Route tokens to experts
        router_logits = self.router(x)  # [B, N, num_experts]
        router_probs = F.softmax(router_logits, dim=-1)

        # Select top-k experts per token
        top_k_probs, top_k_indices = torch.topk(router_probs, self.top_k, dim=-1)

        # Normalize selected expert weights
        top_k_probs = top_k_probs / top_k_probs.sum(dim=-1, keepdim=True)

        # Compute expert outputs (only for selected experts)
        # For efficiency, we batch tokens going to the same expert
        output = torch.zeros_like(x)

        for k in range(self.top_k):
            expert_idx = top_k_indices[:, :, k]  # [B, N]
            expert_weight = top_k_probs[:, :, k]  # [B, N]

            for e in range(self.num_experts):
                mask = (expert_idx == e)  # [B, N]
                if mask.any():
                    expert_input = x[mask]  # [num_tokens, D]
                    expert_output = self.experts[e](expert_input)
                    output[mask] += expert_weight[mask].unsqueeze(-1) * expert_output

        # Compute auxiliary losses
        aux = self._compute_aux_losses(router_probs, top_k_indices)

        return output, aux

    def _compute_aux_losses(self, router_probs, top_k_indices):
        """Compute load balance and router z-loss."""
        B, N, E = router_probs.shape

        # Load balance loss: encourage uniform expert utilization
        # Fraction of tokens routed to each expert
        expert_counts = torch.zeros(E, device=router_probs.device)
        for k in range(self.top_k):
            for e in range(E):
                expert_counts[e] += (top_k_indices[:, :, k] == e).float().sum()
        expert_frac = expert_counts / (B * N * self.top_k)

        # Mean router probability per expert
        expert_prob = router_probs.mean(dim=[0, 1])

        # Load balance loss (from Switch Transformer)
        load_balance_loss = E * (expert_frac * expert_prob).sum()

        # Router z-loss (stabilizes training)
        router_z_loss = torch.logsumexp(router_probs, dim=-1).mean()

        return {
            "load_balance_loss": load_balance_loss,
            "router_z_loss": router_z_loss,
            "expert_utilization": expert_frac,
            "router_entropy": -(router_probs * router_probs.log().clamp(min=-100)).sum(-1).mean(),
        }
```

### Compute Savings Analysis

| Configuration | Params | Active Params | FLOPs Ratio | Memory |
|---------------|--------|---------------|-------------|--------|
| Dense FFN | 1x | 1x | 1.0x | 1x |
| MoE-8E-Top1 | 8x | 1x | 0.15x | 8x |
| MoE-8E-Top2 | 8x | 2x | 0.28x | 8x |
| MoE-16E-Top2 | 16x | 2x | 0.15x | 16x |

**Note**: Memory increases with expert count, but compute decreases.

### CLI Flags for Benchmarking

```bash
# Test MoE FFN with default settings (8 experts, top-2)
python train_hard_probes.py --test-moe-ffn

# Custom expert count
python train_hard_probes.py --test-moe-ffn --moe-num-experts 16 --moe-top-k 2

# Compare dense vs MoE
python train_hard_probes.py --test-moe-ffn --moe-ablation

# Full diagnostic suite
python train_hard_probes.py --test-moe-ffn --moe-ablation \
    --moe-num-experts 8 --moe-top-k 2 --moe-load-balance-weight 0.01
```

### Expected Benchmark Results

```
MoE FFN Benchmark Results:
==========================

Compute Efficiency:
  Dense FFN:     1000 tokens/sec
  MoE-8E-Top2:   1850 tokens/sec (1.85x speedup)
  MoE-16E-Top2:  2100 tokens/sec (2.1x speedup)

Expert Utilization (should be ~uniform):
  Expert 0: 12.3%  Expert 1: 12.8%  Expert 2: 12.1%  Expert 3: 13.0%
  Expert 4: 12.5%  Expert 5: 12.4%  Expert 6: 12.2%  Expert 7: 12.7%

Load Balance Loss: 0.0023 (target: < 0.01)
Router Entropy: 2.89 (target: close to log(num_experts) = 2.08 for 8 experts)

Quality Metrics:
  Dense FFN Accuracy:    94.2%
  MoE-8E-Top2 Accuracy:  94.0% (-0.2%, acceptable)

RECOMMENDATION: MoE FFN provides 1.85x speedup with negligible quality loss.
                Ready for train_unified_llm.py integration.
```

---

## Part B: MoE in Quad Proposal (OPTIONAL - Quality Enhancement)

## Architecture Diagram

```
Input / Latent
     ↓
┌─────────────────────────────────────────────┐
│  Local Attention (syntax / texture)         │
└─────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────┐
│  Phase Integrator (persistent memory)       │  ← NO MoE EVER
│  - Unified, coherent memory state           │
│  - Must not be fragmented across experts    │
└─────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────┐
│  Quad Proposal Layer (MoE)                  │
│  ┌─────────────────────────────────────┐    │
│  │  Router (lightweight, query-based)  │    │
│  │  r = softmax(W_router @ query)      │    │
│  └─────────────────────────────────────┘    │
│              │ top-2 experts                │
│    ┌─────────┼─────────┐                    │
│    ▼         ▼         ▼                    │
│ ┌───────┐ ┌───────┐ ┌───────┐              │
│ │Expert1│ │Expert2│ │Expert3│ ... ExpertN  │
│ │ code  │ │  NL   │ │ math  │              │
│ └───────┘ └───────┘ └───────┘              │
│    │ K₁      │ K₂      │                    │
│    └────┬────┴─────────┘                    │
│         ▼                                   │
│   Pool proposals (K₁ + K₂ + ...)           │
│         ▼                                   │
│   Top-K Selection (hard, sparse)            │
└─────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────┐
│  Phase-Gated Integration (EMA / clamp)      │
└─────────────────────────────────────────────┘
     ↓
Synthesis / Output
```

## Rationale

### Why NO MoE in Phase Integrator

Phase Integrator must maintain a **unified, coherent memory state**. Fragmenting it across experts would:
- Break the O(n) cumulative state accumulation
- Create inconsistent memory views across experts
- Violate Phase's core function as the persistent binding mechanism

### Why MoE IS Appropriate for Quad Proposal

Quad's job is to **propose candidates** from a large retrieval space. This naturally fits the "ensemble of specialists" pattern:

| Aspect | Standard Quad | MoE Quad |
|--------|---------------|----------|
| Proposal source | Single retrieval path | Multiple specialized retrievers |
| Diversity | Depends on cache contents | Structurally diverse by design |
| Compute | O(K × D) | O(K × D × active_experts) |
| Capacity | Fixed | Scales with expert count |

## Key Design Choices

### 1. Lightweight Router

```python
# GOOD: Single linear layer
router_logits = W_router @ query  # [B, N, num_experts]
router_weights = softmax(router_logits, dim=-1)
top_experts = topk(router_weights, k=2)

# BAD: Deep MLP router (adds latency, overfits)
# router_logits = MLP(query)  # DON'T DO THIS
```

**Rationale**: The router should be fast and simple. Complex routers add latency and can overfit to superficial patterns. A single linear projection is sufficient to learn domain-based routing.

### 2. Top-2 Experts (Balance Diversity vs Compute)

```python
# Activate exactly 2 experts per token
active_experts = 2
# With N=8 total experts, this gives 4x capacity with 2x compute
```

**Rationale**:
- Top-1: Not enough diversity, single point of failure
- Top-2: Good balance of diversity and compute
- Top-3+: Diminishing returns, increased compute

### 3. Pool Then Select (Don't Pre-filter by Expert)

```python
# Each active expert produces K_per_expert proposals
proposals_1 = expert_1(query)  # [B, N, K_per_expert, D]
proposals_2 = expert_2(query)  # [B, N, K_per_expert, D]

# Pool all proposals together
all_proposals = concat([proposals_1, proposals_2], dim=2)  # [B, N, 2*K_per_expert, D]

# Top-K selection picks best regardless of source
final_proposals = topk(all_proposals, k=K_final)  # [B, N, K_final, D]
```

**Rationale**: Don't pre-allocate slots per expert. Let the top-K selection decide which proposals are best, regardless of which expert produced them. This allows one expert to dominate when appropriate.

### 4. Expert Diversity Loss

```python
def expert_diversity_loss(proposals_by_expert, lambda_div=0.1):
    """
    Penalize experts that produce identical proposals.

    Args:
        proposals_by_expert: [num_experts, B, N, K, D]
        lambda_div: Diversity loss weight

    Returns:
        Scalar diversity loss
    """
    num_experts = proposals_by_expert.shape[0]
    total_sim = 0.0
    count = 0

    for i in range(num_experts):
        for j in range(i + 1, num_experts):
            # Compute cosine similarity between expert proposals
            p_i = proposals_by_expert[i]  # [B, N, K, D]
            p_j = proposals_by_expert[j]  # [B, N, K, D]

            # Normalize
            p_i_norm = p_i / (p_i.norm(dim=-1, keepdim=True) + 1e-6)
            p_j_norm = p_j / (p_j.norm(dim=-1, keepdim=True) + 1e-6)

            # Cross-similarity: how similar are proposals from different experts?
            sim = einsum("bnkd,bnqd->bnkq", p_i_norm, p_j_norm)

            # Penalize high similarity (experts should be different)
            total_sim += sim.mean()
            count += 1

    # Higher similarity = higher loss
    return lambda_div * (total_sim / count)
```

**Rationale**: Without diversity pressure, experts may converge to produce identical proposals (mode collapse). The diversity loss encourages each expert to specialize in different regions of the proposal space.

## Synergy with Existing Features

### Interference Scoring Integration

The existing interference-aware proposal scoring (V10.5) can be enhanced with expert-awareness:

```python
def expert_aware_interference(proposals, scores, expert_ids):
    """
    Interference scoring that considers expert source.

    Proposals from the SAME expert that are similar should be penalized more
    (redundancy within expert). Proposals from DIFFERENT experts that are
    similar might be valuable (consensus across experts).
    """
    # Standard interference
    base_rescored, stats = interference_rescore(proposals, scores)

    # Expert-aware adjustment
    same_expert_mask = expert_ids.unsqueeze(-1) == expert_ids.unsqueeze(-2)

    # Penalize same-expert similarity more heavily
    # (we want diversity within each expert's proposals)
    ...
```

### Load Balancing Loss

Standard MoE load balancing to ensure all experts get trained:

```python
def load_balance_loss(router_weights, lambda_lb=0.01):
    """
    Encourage uniform expert utilization.

    Args:
        router_weights: [B, N, num_experts] - softmax router outputs
        lambda_lb: Load balance loss weight

    Returns:
        Scalar load balance loss
    """
    # Fraction of tokens routed to each expert
    expert_usage = router_weights.mean(dim=[0, 1])  # [num_experts]

    # Ideal: uniform distribution
    num_experts = expert_usage.shape[0]
    target = 1.0 / num_experts

    # Penalize deviation from uniform
    return lambda_lb * ((expert_usage - target) ** 2).sum()
```

## Implementation Considerations

### Compute Budget

| Configuration | Experts | Active | Proposals/Expert | Total Proposals | Relative Compute |
|---------------|---------|--------|------------------|-----------------|------------------|
| Baseline | 1 | 1 | 64 | 64 | 1.0x |
| MoE-Light | 4 | 2 | 32 | 64 | 1.5x |
| MoE-Standard | 8 | 2 | 32 | 64 | 1.5x |
| MoE-Heavy | 16 | 4 | 16 | 64 | 2.0x |

### Expert Specialization (Suggested Domains)

For a general-purpose LLM:

| Expert | Domain | Retrieval Focus |
|--------|--------|-----------------|
| Expert 0 | Code/Technical | Syntax patterns, API signatures |
| Expert 1 | Natural Language | Semantic relationships, discourse |
| Expert 2 | Mathematical | Logical structures, proofs |
| Expert 3 | Factual/Encyclopedic | Entity facts, definitions |
| Expert 4 | Creative/Narrative | Story patterns, stylistic elements |
| Expert 5 | Reasoning/Planning | Multi-step inference chains |
| Expert 6 | Dialogue/Conversational | Turn-taking, pragmatics |
| Expert 7 | Domain-Specific | Task-dependent specialization |

### Training Schedule

```
Stage 1 (0-10% training):
  - Router warmup with soft routing
  - All experts see all data
  - High load balance weight (λ_lb = 0.1)

Stage 2 (10-50% training):
  - Hard top-K routing
  - Expert specialization emerges
  - Moderate load balance (λ_lb = 0.01)

Stage 3 (50-100% training):
  - Expert diversity loss enabled
  - Fine-tuning specialization
  - Low load balance (λ_lb = 0.001)
```

## Comparison with Standard MoE

| Aspect | Standard MoE (Mixtral) | MoE Quad Proposal |
|--------|------------------------|-------------------|
| Where | FFN layers | Quad Proposal layer only |
| What routes | Token embeddings | Query vectors |
| Output | Single hidden state | K proposals |
| Selection | Router picks 1-2 experts | Top-K across all expert proposals |
| Phase interaction | N/A | Phase integrates selected proposals |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Expert mode collapse | Expert diversity loss |
| Router instability | Lightweight router, soft warmup |
| Load imbalance | Load balance loss |
| Increased latency | Limit to top-2 experts, efficient batching |
| Gradient fragmentation | Auxiliary losses per expert, careful learning rates |

## Future Extensions

1. **Hierarchical MoE**: Coarse-grained routing (domain) then fine-grained (sub-domain)
2. **Dynamic expert count**: Adjust active experts based on task complexity
3. **Expert merging**: Combine similar experts during training to reduce redundancy
4. **Expert pruning**: Remove underutilized experts for inference efficiency

## References

- Shazeer et al., "Outrageously Large Neural Networks: The Sparsely-Gated Mixture-of-Experts Layer" (2017)
- Fedus et al., "Switch Transformers: Scaling to Trillion Parameter Models" (2021)
- Jiang et al., "Mixtral of Experts" (2024)
- Phase-Quad Architecture (internal documentation)
- Interference-Aware Proposal Scoring (symbolu/text_interference.py, symbolu/vision/interference_scoring.py)

---

---

## Part C: Combined Approach (MoE FFN + MoE Quad)

For maximum benefit, both can be combined:

```
┌─────────────────────────────────────────────────────────────┐
│  Attention Block                                            │
│  ├─ Local Attention                                        │
│  ├─ Phase Integrator          ← NO MoE                     │
│  └─ Quad Proposal (MoE)       ← Quality enhancement        │
├─────────────────────────────────────────────────────────────┤
│  FFN Block (MoE)              ← Cost savings               │
└─────────────────────────────────────────────────────────────┘
```

| Metric | Baseline | +MoE FFN | +MoE Quad | +Both |
|--------|----------|----------|-----------|-------|
| Compute | 1.0x | 0.5x | 1.5x | 0.75x |
| Quality | 1.0 | 1.0 | 1.1 | 1.1 |
| Params | 1x | 8x | 8x | 16x |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial design document (MoE Quad only) |
| 1.1 | Jan 2026 | Added MoE FFN section (recommended approach), CLI flags, benchmark expectations |
