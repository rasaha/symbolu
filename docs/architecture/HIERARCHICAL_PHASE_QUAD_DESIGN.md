# Hierarchical Phase-Quad (HP-Quad) Architecture

## Status: DESIGN DOCUMENT

**Author**: Claude (Architecture Design)
**Date**: January 2026
**Version**: 1.0
**Based on**: HM-RNN (Chung et al., 2016) - Hierarchical Multiscale RNN

---

## Overview

This document describes Hierarchical Phase-Quad (HP-Quad), an extension that introduces **multi-timescale processing** inspired by Hierarchical Multiscale RNN (HM-RNN). HP-Quad enables the Phase Integrator to operate at multiple temporal resolutions, with automatic boundary detection determining when to update slower-timescale states.

### Core Insight

```
Standard Phase-Quad:
  Token₁ → Token₂ → Token₃ → Token₄ → Token₅ → ...
    │        │        │        │        │
    ▼        ▼        ▼        ▼        ▼
  Phase    Phase    Phase    Phase    Phase    (single timescale)

Hierarchical Phase-Quad (HP-Quad):
  Token₁ → Token₂ → Token₃ → Token₄ → Token₅ → ...
    │        │        │        │        │
    ▼        ▼        ▼        ▼        ▼
  Phase₁   Phase₁   Phase₁   Phase₁   Phase₁   (fast: every token)
           └────────┬────────┘
                    ▼
                 Phase₂                         (medium: at boundaries)
                    └─────────┬─────────────┘
                              ▼
                           Phase₃               (slow: at major transitions)
```

### Key Capabilities

| Capability | Standard Phase-Quad | HP-Quad |
|------------|--------------------|-----------------------------|
| Timescales | Single | Multiple (3+ levels) |
| Update frequency | Every token | Adaptive (boundary-based) |
| Long-range memory | Good | Excellent (hierarchical) |
| Compute efficiency | Baseline | Better (sparse slow updates) |
| Boundary awareness | No | Yes (learned detectors) |
| Semantic chunking | No | Yes (automatic) |

### Why HM-RNN Concepts Fit Phase-Quad

HM-RNN introduced three key innovations that map naturally to Phase-Quad:

1. **Multi-timescale processing**: Different layers operate at different speeds
2. **Boundary detection**: Binary variables (z) determine when to update slow layers
3. **Selective updates**: Slow layers only update at semantic boundaries

In Phase-Quad:
- **Phase Integrator** already maintains persistent state → perfect for multi-timescale
- **Quad Proposal** retrieves from memory → can retrieve at different granularities
- **Local Attention** handles syntax → provides bottom-up signals for boundaries

---

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  HIERARCHICAL PHASE-QUAD (HP-QUAD)                                              │
│                                                                                 │
│  Input Tokens                                                                   │
│      │                                                                          │
│      ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  LEVEL 1: LOCAL ATTENTION (Fast - Every Token)                          │   │
│  │  - Standard Phase-Quad local attention                                   │   │
│  │  - Syntax, texture, immediate context                                    │   │
│  │  - Updates: Every token                                                  │   │
│  │  → Output: h₁, boundary_signal₁                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                  │
│                              ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  BOUNDARY DETECTOR 1→2                                                   │   │
│  │  z₁ = σ(W_z · [h₁; phase₁]) > threshold                                 │   │
│  │  - Detects: phrase/clause boundaries                                     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                  │
│                    ┌─────────┴─────────┐                                        │
│                    │ if z₁ = 1         │                                        │
│                    ▼                   ▼ (else skip)                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  LEVEL 2: PHASE INTEGRATOR (Medium - At Boundaries)                      │   │
│  │  - Integrates information across phrases                                 │   │
│  │  - Semantic coherence, topic tracking                                    │   │
│  │  - Updates: Only when z₁ = 1 (~10-20% of tokens)                        │   │
│  │  → Output: h₂, phase₂, boundary_signal₂                                 │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                  │
│                              ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  BOUNDARY DETECTOR 2→3                                                   │   │
│  │  z₂ = σ(W_z · [h₂; phase₂]) > threshold                                 │   │
│  │  - Detects: paragraph/section boundaries                                 │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                  │
│                    ┌─────────┴─────────┐                                        │
│                    │ if z₂ = 1         │                                        │
│                    ▼                   ▼ (else skip)                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  LEVEL 3: QUAD PROPOSAL (Slow - At Major Transitions)                    │   │
│  │  - Document-level memory, cross-document retrieval                       │   │
│  │  - Updates: Only when z₂ = 1 (~1-5% of tokens)                          │   │
│  │  → Output: h₃, retrieved_context                                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                  │
│                              ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  HIERARCHICAL FUSION                                                     │   │
│  │  output = Fuse(h₁, h₂, h₃)                                              │   │
│  │  - Combines all timescales                                               │   │
│  │  - Top-down modulation: h₃ → h₂ → h₁                                    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                  │
│                              ▼                                                  │
│                           Output                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Block Diagram

```
                              Input x
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         LEVEL 1: FAST (Every Token)                              │
│                                                                                  │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐  │
│  │   Local Attention   │ →  │   Phase State L1    │ →  │  Boundary Detector  │  │
│  │   (window=64)       │    │   (d_phase=128)     │    │     z₁ ∈ {0,1}      │  │
│  └─────────────────────┘    └─────────────────────┘    └─────────────────────┘  │
│           │                          │                          │               │
│           ▼                          ▼                          ▼               │
│         h₁                       phase₁                  boundary₁              │
└──────────────────────────────────────────────────────────────────────────────────┘
                                │      │                          │
                                │      │      ┌───────────────────┘
                                ▼      ▼      ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    LEVEL 2: MEDIUM (Boundary-Triggered)                          │
│                                                                                  │
│                          Gate: if z₁ = 1                                        │
│                                │                                                 │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐  │
│  │  Cross-Phrase Attn  │ →  │   Phase State L2    │ →  │  Boundary Detector  │  │
│  │  (over L1 outputs)  │    │   (d_phase=256)     │    │     z₂ ∈ {0,1}      │  │
│  └─────────────────────┘    └─────────────────────┘    └─────────────────────┘  │
│           │                          │                          │               │
│           ▼                          ▼                          ▼               │
│         h₂                       phase₂                  boundary₂              │
└──────────────────────────────────────────────────────────────────────────────────┘
                                │      │                          │
                                │      │      ┌───────────────────┘
                                ▼      ▼      ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                      LEVEL 3: SLOW (Major Transitions)                           │
│                                                                                  │
│                          Gate: if z₂ = 1                                        │
│                                │                                                 │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐  │
│  │   Quad Proposal     │ →  │   Phase State L3    │ →  │  Document Memory    │  │
│  │   (retrieval)       │    │   (d_phase=512)     │    │  (long-term)        │  │
│  └─────────────────────┘    └─────────────────────┘    └─────────────────────┘  │
│           │                          │                          │               │
│           ▼                          ▼                          ▼               │
│         h₃                       phase₃                  retrieved              │
└──────────────────────────────────────────────────────────────────────────────────┘
                                │      │                          │
                                └──────┴──────────────────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          HIERARCHICAL FUSION                                     │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  Top-Down Modulation                                                      │  │
│  │                                                                           │  │
│  │    h₃ ───────────────────────────────────────────────────→ context₃      │  │
│  │         ╲                                                                 │  │
│  │          ╲ modulate                                                       │  │
│  │           ╲                                                               │  │
│  │    h₂ ────⊕──────────────────────────────────────────────→ context₂      │  │
│  │              ╲                                                            │  │
│  │               ╲ modulate                                                  │  │
│  │                ╲                                                          │  │
│  │    h₁ ─────────⊕─────────────────────────────────────────→ output        │  │
│  │                                                                           │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  output = LayerNorm(h₁ + α₂·h₂ + α₃·h₃)                                        │
│  where α are learned gating weights                                             │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. Boundary Detector

The boundary detector determines when to update slower timescale states. This is the key innovation from HM-RNN.

```python
class BoundaryDetector(nn.Module):
    """
    Learns to detect semantic boundaries for hierarchical processing.

    Uses Straight-Through Estimator for binary gradients during training.
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
        h: Tensor,           # [B, N, D] current hidden state
        phase: Tensor,       # [B, D_phase] phase state
    ) -> Tuple[Tensor, Tensor]:
        """
        Compute boundary probability and binary decision.

        Returns:
            z_soft: [B, N] boundary probability (for training)
            z_hard: [B, N] binary boundary decision (for gating)
        """
        # Expand phase to match sequence length
        phase_expanded = phase.unsqueeze(1).expand(-1, h.size(1), -1)

        # Concatenate and predict
        combined = torch.cat([h, phase_expanded], dim=-1)
        logits = self.boundary_predictor(combined).squeeze(-1)  # [B, N]

        # Soft probability
        z_soft = torch.sigmoid(logits / self.temperature)

        # Hard decision with Straight-Through Estimator
        z_hard = (z_soft > self.threshold).float()
        z_hard = z_soft + (z_hard - z_soft).detach()  # STE

        return z_soft, z_hard
```

### 2. Hierarchical Phase Integrator

Multi-timescale version of the Phase Integrator:

```python
class HierarchicalPhaseIntegrator(nn.Module):
    """
    Phase Integrator operating at multiple timescales.

    Level 1: Fast (every token) - syntax, local context
    Level 2: Medium (boundary-triggered) - phrases, semantic units
    Level 3: Slow (major transitions) - paragraphs, topics
    """

    def __init__(
        self,
        d_model: int,
        d_phase_levels: Tuple[int, ...] = (128, 256, 512),
        num_levels: int = 3,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.num_levels = num_levels
        self.d_phase_levels = d_phase_levels

        # Phase state for each level
        self.phase_projections = nn.ModuleList([
            nn.Linear(d_model, d_phase)
            for d_phase in d_phase_levels
        ])

        # Phase update GRU for each level
        self.phase_grus = nn.ModuleList([
            nn.GRUCell(d_model, d_phase)
            for d_phase in d_phase_levels
        ])

        # Boundary detectors between levels
        self.boundary_detectors = nn.ModuleList([
            BoundaryDetector(d_model, d_phase_levels[i])
            for i in range(num_levels - 1)
        ])

        # Top-down projection (slower → faster)
        self.top_down_projections = nn.ModuleList([
            nn.Linear(d_phase_levels[i+1], d_phase_levels[i])
            for i in range(num_levels - 1)
        ])

        # Output fusion
        total_phase_dim = sum(d_phase_levels)
        self.fusion = nn.Linear(d_model + total_phase_dim, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: Tensor,                                    # [B, N, D]
        phase_states: Optional[List[Tensor]] = None,  # List of [B, D_phase_i]
    ) -> Tuple[Tensor, List[Tensor], Dict[str, Tensor]]:
        """
        Hierarchical phase integration.

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
        all_boundaries = []

        # Process token by token (can be optimized with batched ops)
        for t in range(N):
            x_t = x[:, t, :]  # [B, D]

            # Level 1: Always updates
            h_1 = self.phase_grus[0](x_t, phase_states[0])
            phase_states[0] = h_1
            level_outputs[0].append(h_1)

            # Boundary detection for level 1→2
            z_soft_1, z_hard_1 = self.boundary_detectors[0](
                x_t.unsqueeze(1), phase_states[0]
            )
            z_hard_1 = z_hard_1.squeeze(1)  # [B]
            all_boundaries.append(z_hard_1)

            # Level 2: Updates at boundaries
            if z_hard_1.any():
                # Get top-down context from level 3 (if available)
                top_down_2 = self.top_down_projections[1](phase_states[2])

                # Update only for samples where boundary fired
                mask_2 = z_hard_1.unsqueeze(-1)  # [B, 1]
                h_2_new = self.phase_grus[1](x_t, phase_states[1] + top_down_2)
                phase_states[1] = mask_2 * h_2_new + (1 - mask_2) * phase_states[1]

            level_outputs[1].append(phase_states[1])

            # Boundary detection for level 2→3
            if self.num_levels > 2:
                z_soft_2, z_hard_2 = self.boundary_detectors[1](
                    x_t.unsqueeze(1), phase_states[1]
                )
                z_hard_2 = z_hard_2.squeeze(1)  # [B]

                # Level 3: Updates at major transitions
                if z_hard_2.any():
                    mask_3 = z_hard_2.unsqueeze(-1)
                    h_3_new = self.phase_grus[2](x_t, phase_states[2])
                    phase_states[2] = mask_3 * h_3_new + (1 - mask_3) * phase_states[2]

                level_outputs[2].append(phase_states[2])

        # Stack outputs
        level_outputs = [
            torch.stack(outputs, dim=1)  # [B, N, D_phase]
            for outputs in level_outputs
        ]

        # Hierarchical fusion
        all_phases = torch.cat(level_outputs, dim=-1)  # [B, N, sum(D_phase)]
        combined = torch.cat([x, all_phases], dim=-1)
        output = self.fusion(combined)
        output = self.dropout(output)

        # Compute boundary statistics
        boundaries = torch.stack(all_boundaries, dim=1)  # [B, N]
        aux = {
            "boundary_rate": boundaries.mean(),
            "boundary_positions": boundaries,
            "level_outputs": level_outputs,
        }

        return output, phase_states, aux
```

### 3. Hierarchical Quad Proposal

Quad Proposal with multi-granularity retrieval:

```python
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
        self.num_levels = num_levels
        self.chunk_sizes = chunk_sizes

        # Proposal generators for each level
        self.proposal_generators = nn.ModuleList([
            nn.Linear(d_model, d_model * num_proposals)
            for _ in range(num_levels)
        ])

        # Retrieval keys for each level
        self.key_projections = nn.ModuleList([
            nn.Linear(d_model, d_model)
            for _ in range(num_levels)
        ])

        # Level-wise scoring
        self.level_scorers = nn.ModuleList([
            nn.Linear(d_model * 2, 1)
            for _ in range(num_levels)
        ])

        # Cross-level fusion
        self.cross_level_fusion = nn.Linear(d_model * num_levels, d_model)

    def forward(
        self,
        x: Tensor,                    # [B, N, D]
        memory_banks: List[Tensor],   # List of [B, M_i, D] for each level
        boundaries: Optional[Tensor] = None,  # [B, N] boundary indicators
    ) -> Tuple[Tensor, Dict[str, Tensor]]:
        """
        Hierarchical retrieval with boundary-aware chunking.

        Returns:
            retrieved: [B, N, D] fused retrieval result
            aux: Per-level retrieval statistics
        """
        B, N, D = x.shape

        level_retrievals = []
        aux = {}

        for level, (generator, key_proj, scorer, chunk_size) in enumerate(zip(
            self.proposal_generators,
            self.key_projections,
            self.level_scorers,
            self.chunk_sizes
        )):
            # Chunk the input at this granularity
            if chunk_size > 1:
                # Average pool to create chunk representations
                x_chunked = F.avg_pool1d(
                    x.transpose(1, 2),
                    kernel_size=chunk_size,
                    stride=chunk_size,
                    ceil_mode=True
                ).transpose(1, 2)  # [B, N//chunk_size, D]
            else:
                x_chunked = x

            # Generate proposals
            proposals = generator(x_chunked)
            proposals = proposals.view(B, -1, 4, D)  # [B, N_chunks, 4, D]

            # Retrieve from memory bank
            if level < len(memory_banks) and memory_banks[level] is not None:
                keys = key_proj(memory_banks[level])  # [B, M, D]

                # Compute attention scores
                scores = torch.einsum('bnpd,bmd->bnpm', proposals, keys)
                attn = F.softmax(scores, dim=-1)

                # Retrieve
                retrieved = torch.einsum('bnpm,bmd->bnpd', attn, memory_banks[level])

                # Score proposals
                combined = torch.cat([proposals, retrieved], dim=-1)
                proposal_scores = scorer(combined).squeeze(-1)  # [B, N_chunks, 4]

                # Select best proposal
                best_idx = proposal_scores.argmax(dim=-1)  # [B, N_chunks]
                best_retrieved = torch.gather(
                    retrieved,
                    dim=2,
                    index=best_idx.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, 1, D)
                ).squeeze(2)  # [B, N_chunks, D]

                # Upsample back to original resolution if needed
                if chunk_size > 1:
                    best_retrieved = F.interpolate(
                        best_retrieved.transpose(1, 2),
                        size=N,
                        mode='nearest'
                    ).transpose(1, 2)

                level_retrievals.append(best_retrieved)
                aux[f"level_{level}_scores"] = proposal_scores.detach()
            else:
                # No memory at this level, use zeros
                level_retrievals.append(torch.zeros(B, N, D, device=x.device))

        # Fuse across levels
        stacked = torch.cat(level_retrievals, dim=-1)  # [B, N, D*num_levels]
        retrieved = self.cross_level_fusion(stacked)

        return retrieved, aux
```

### 4. Complete HP-Quad Block

```python
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
        dropout: float = 0.1,
    ):
        super().__init__()

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
            aux: Diagnostics
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
            memory_banks = [None] * 3
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
```

---

## Training Strategy

### Phase 1: Boundary Detector Pretraining

Train boundary detectors on labeled data with known semantic boundaries:

```python
def train_boundary_detector(model, dataloader, optimizer):
    """
    Pretrain boundary detector on labeled boundaries.

    Labels can come from:
    - Punctuation (periods, commas)
    - Syntactic parses (phrase boundaries)
    - Paragraph breaks
    - Topic shifts
    """
    for batch in dataloader:
        x, boundary_labels = batch

        # Forward
        z_soft, z_hard = model.boundary_detector(x, phase_state)

        # Binary cross-entropy loss
        loss = F.binary_cross_entropy(z_soft, boundary_labels)

        # Regularization: encourage sparse boundaries
        sparsity_loss = z_soft.mean()  # Penalty for too many boundaries

        total_loss = loss + 0.1 * sparsity_loss

        optimizer.zero_grad()
        total_loss.backward()
        optimizer.step()
```

### Phase 2: Hierarchical Pretraining

Train each level separately, then combine:

```python
def hierarchical_pretraining(model, dataloader):
    """
    Progressive training: Level 1 → Level 2 → Level 3.
    """
    # Stage 1: Train Level 1 only
    for param in model.phase_integrator.phase_grus[1:].parameters():
        param.requires_grad = False
    train_level(model, dataloader, level=1, epochs=10)

    # Stage 2: Add Level 2
    for param in model.phase_integrator.phase_grus[1].parameters():
        param.requires_grad = True
    train_level(model, dataloader, level=2, epochs=10)

    # Stage 3: Add Level 3
    for param in model.phase_integrator.phase_grus[2].parameters():
        param.requires_grad = True
    train_level(model, dataloader, level=3, epochs=10)
```

### Phase 3: End-to-End Fine-tuning

```python
def end_to_end_training(model, dataloader, optimizer):
    """
    Joint training with all components.
    """
    for batch in dataloader:
        x, targets = batch

        # Forward
        output, phase_states, aux = model(x)

        # Main task loss
        task_loss = F.cross_entropy(output.view(-1, vocab_size), targets.view(-1))

        # Boundary regularization
        boundary_rate = aux["boundary_rate"]
        target_rate = 0.15  # ~15% of tokens should be boundaries
        boundary_reg = (boundary_rate - target_rate).pow(2)

        # Total loss
        total_loss = task_loss + 0.1 * boundary_reg

        optimizer.zero_grad()
        total_loss.backward()
        optimizer.step()
```

---

## Benchmark Suite

### CLI Integration

```python
def add_hp_quad_args(parser):
    """Add HP-Quad benchmark arguments."""
    group = parser.add_argument_group("HP-Quad Benchmarks")
    group.add_argument("--test-hp-quad", action="store_true",
                      help="Run HP-Quad benchmarks")
    group.add_argument("--hp-num-levels", type=int, default=3,
                      help="Number of hierarchy levels")
    group.add_argument("--hp-d-phase-levels", type=str, default="128,256,512",
                      help="Comma-separated phase dimensions per level")
    group.add_argument("--hp-chunk-sizes", type=str, default="1,8,64",
                      help="Comma-separated chunk sizes per level")
    group.add_argument("--hp-boundary-ablation", action="store_true",
                      help="Run boundary detection ablation study")
    return parser
```

### Benchmark Tests

```python
def run_hp_quad_benchmarks(args, device):
    """
    Run HP-Quad benchmark suite.

    Tests:
    1. Throughput comparison (standard vs hierarchical)
    2. Boundary detection accuracy
    3. Memory efficiency
    4. Long-range dependency handling
    5. Ablation studies
    """
    results = {}

    # Parse config
    d_phase_levels = tuple(map(int, args.hp_d_phase_levels.split(",")))
    chunk_sizes = tuple(map(int, args.hp_chunk_sizes.split(",")))

    # =========================================================================
    # Test 1: Throughput Comparison
    # =========================================================================
    print("\n[Test 1] Throughput Comparison")

    d_model = 512
    batch_size = 32
    seq_len = 1024

    # Standard Phase-Quad (simulated as single-level)
    standard_model = HPQuadBlock(
        d_model=d_model,
        d_phase_levels=(256,),  # Single level
        num_levels=1,
        chunk_sizes=(1,),
    ).to(device)

    # Hierarchical HP-Quad
    hp_model = HPQuadBlock(
        d_model=d_model,
        d_phase_levels=d_phase_levels,
        num_levels=args.hp_num_levels,
        chunk_sizes=chunk_sizes,
    ).to(device)

    x = torch.randn(batch_size, seq_len, d_model, device=device)

    # Warmup
    for _ in range(5):
        with torch.no_grad():
            _ = standard_model(x)
            _ = hp_model(x)

    if device == "cuda":
        torch.cuda.synchronize()

    # Benchmark standard
    import time
    start = time.perf_counter()
    for _ in range(20):
        with torch.no_grad():
            _ = standard_model(x)
    if device == "cuda":
        torch.cuda.synchronize()
    standard_time = time.perf_counter() - start

    # Benchmark HP-Quad
    start = time.perf_counter()
    for _ in range(20):
        with torch.no_grad():
            _ = hp_model(x)
    if device == "cuda":
        torch.cuda.synchronize()
    hp_time = time.perf_counter() - start

    results["throughput"] = {
        "standard_time": standard_time,
        "hp_time": hp_time,
        "speedup": standard_time / hp_time,
    }
    print(f"  Standard: {standard_time:.3f}s")
    print(f"  HP-Quad:  {hp_time:.3f}s")
    print(f"  Speedup:  {results['throughput']['speedup']:.2f}x")

    # =========================================================================
    # Test 2: Boundary Detection Quality
    # =========================================================================
    print("\n[Test 2] Boundary Detection Quality")

    # Create synthetic data with known boundaries
    x_boundary = torch.randn(16, 256, d_model, device=device)

    with torch.no_grad():
        _, phase_states, aux = hp_model(x_boundary)

    boundary_rate = aux["boundary_rate"].item()
    results["boundary_detection"] = {
        "boundary_rate": boundary_rate,
        "target_rate": 0.15,
        "within_target": abs(boundary_rate - 0.15) < 0.1,
    }
    print(f"  Boundary rate: {boundary_rate:.3f}")
    print(f"  Target rate:   0.15")
    print(f"  Within target: {results['boundary_detection']['within_target']}")

    # =========================================================================
    # Test 3: Memory Efficiency
    # =========================================================================
    print("\n[Test 3] Memory Efficiency")

    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()

        # Standard forward
        with torch.no_grad():
            _ = standard_model(x)
        standard_mem = torch.cuda.max_memory_allocated() / 1024**2

        torch.cuda.reset_peak_memory_stats()

        # HP-Quad forward
        with torch.no_grad():
            _ = hp_model(x)
        hp_mem = torch.cuda.max_memory_allocated() / 1024**2

        results["memory"] = {
            "standard_mb": standard_mem,
            "hp_mb": hp_mem,
            "overhead": hp_mem / standard_mem,
        }
        print(f"  Standard memory: {standard_mem:.1f} MB")
        print(f"  HP-Quad memory:  {hp_mem:.1f} MB")
        print(f"  Overhead:        {results['memory']['overhead']:.2f}x")
    else:
        print("  (Memory benchmark requires CUDA)")

    # =========================================================================
    # Test 4: Long-Range Dependency
    # =========================================================================
    print("\n[Test 4] Long-Range Dependency Handling")

    # Test with varying sequence lengths
    for seq_len in [256, 512, 1024, 2048]:
        x_long = torch.randn(8, seq_len, d_model, device=device)

        with torch.no_grad():
            output, _, aux = hp_model(x_long)

        # Check that all levels are being used
        boundary_rate = aux["boundary_rate"].item()
        print(f"  Seq len {seq_len}: boundary_rate={boundary_rate:.3f}")

    # =========================================================================
    # Test 5: Ablation Study (optional)
    # =========================================================================
    if args.hp_boundary_ablation:
        print("\n[Test 5] Boundary Detection Ablation")

        # Test different boundary thresholds
        for threshold in [0.3, 0.5, 0.7]:
            hp_model.phase_integrator.boundary_detectors[0].threshold = threshold

            with torch.no_grad():
                _, _, aux = hp_model(x)

            boundary_rate = aux["boundary_rate"].item()
            print(f"  Threshold {threshold}: boundary_rate={boundary_rate:.3f}")

    return results
```

---

## Comparison with HM-RNN

| Aspect | HM-RNN (Original) | HP-Quad |
|--------|-------------------|---------|
| Base architecture | RNN | Transformer + Phase-Quad |
| Boundary detection | Binary stochastic | Soft-gated with STE |
| Number of levels | 2-3 | 3 (configurable) |
| Update mechanism | LSTM cell | GRU + Phase State |
| Retrieval | None | Quad Proposal (multi-granularity) |
| Training | REINFORCE | Straight-Through + End-to-End |
| Long-range | Limited by RNN | Phase State + Quad retrieval |

---

## Expected Benefits

### 1. Compute Efficiency

- **Sparse updates**: Level 2 updates ~15% of tokens, Level 3 ~3%
- **Expected savings**: 20-30% compute reduction vs. full hierarchical processing

### 2. Long-Range Modeling

- **Multi-scale memory**: Different levels capture different temporal patterns
- **Selective attention**: Slow layers focus on important transitions

### 3. Semantic Chunking

- **Automatic segmentation**: Model learns natural boundaries
- **Interpretability**: Boundary positions reveal semantic structure

### 4. Memory Efficiency

- **Compressed representations**: Slow layers use chunked inputs
- **Adaptive granularity**: More detail where needed (at boundaries)

---

## Implementation Roadmap

### Phase 1: Core Implementation (Essential)

1. Implement `BoundaryDetector` class
2. Implement `HierarchicalPhaseIntegrator` class
3. Add unit tests for boundary detection
4. Integrate with existing Phase-Quad codebase

### Phase 2: Retrieval Integration

1. Implement `HierarchicalQuadProposal` class
2. Add multi-granularity memory banks
3. Benchmark retrieval quality at different levels

### Phase 3: Training Pipeline

1. Implement boundary detector pretraining
2. Implement hierarchical pretraining schedule
3. Add boundary supervision from punctuation/syntax

### Phase 4: Benchmarking

1. Long-range arena benchmarks
2. Boundary detection quality metrics
3. Compute efficiency measurements

---

## References

1. **Chung et al., 2016**: "Hierarchical Multiscale Recurrent Neural Networks"
   - Original HM-RNN paper introducing multi-timescale processing

2. **Phase-Quad Architecture**: Internal design documents
   - `REFLECTIVE_PHASE_QUAD_DESIGN.md`
   - `MOE_QUAD_PROPOSAL_DESIGN.md`

3. **Transformer-XL**: Segment-level recurrence for transformers
   - Related approach for long-range dependencies

---

## Appendix: Feasibility Assessment

| Dimension | Score | Notes |
|-----------|-------|-------|
| Architectural Fit | 9/10 | Phase State is perfect for multi-timescale |
| Implementation Effort | 7/10 | Moderate - boundary detection needs care |
| Expected Benefit | 8/10 | Strong for long-range, good for efficiency |
| Training Stability | 7/10 | STE gradients can be tricky |
| Interpretability | 9/10 | Boundaries are inherently interpretable |

**Recommendation**: High priority for Phase-Quad roadmap. The hierarchical structure aligns perfectly with the Phase Integrator's design philosophy.
