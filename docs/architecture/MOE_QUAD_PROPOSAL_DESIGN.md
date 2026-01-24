# Mixture of Experts (MoE) Quad Proposal Architecture

## Status: DESIGN DOCUMENT (Not Yet Implemented)

**Author**: Claude (Architecture Design)
**Date**: January 2026
**Version**: 1.0

---

## Overview

This document describes a proposed enhancement to the Phase-Quad architecture: adding Mixture of Experts (MoE) to the Quad Proposal layer to improve proposal diversity and enable domain specialization.

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

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial design document |
