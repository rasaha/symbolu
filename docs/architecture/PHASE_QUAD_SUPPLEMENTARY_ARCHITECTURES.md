# Phase-Quad Supplementary Architectures Compendium

## Status: MASTER REFERENCE DOCUMENT

**Author**: Claude (Architecture Documentation)
**Date**: January 2026
**Version**: 1.0

---

## Executive Summary

This document catalogs all **supplementary architectures** that have been integrated with the core **Phase-Quad** architecture (Phase Integrator + Quad Proposal). Each enhancement extends the base architecture with specialized capabilities while maintaining compatibility with the core design principles.

### Architecture Evolution Timeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE-QUAD ARCHITECTURE EVOLUTION                                          │
│                                                                             │
│  V10.0: Core Phase-Quad                                                     │
│         ├── Local Attention (O(n·w))                                        │
│         ├── Phase Integrator (persistent memory)                            │
│         └── Quad Proposal (sparse retrieval)                                │
│                                                                             │
│  V10.3.0: +SRK (Sovereign Reasoning Kernel)                                 │
│         └── 32D Ontological State governance                                │
│                                                                             │
│  V10.3.4: +Kosha Consciousness System                                       │
│         └── 5-sheath consciousness modeling                                 │
│                                                                             │
│  V10.5: +Interference-Aware Proposal Scoring                                │
│         └── Proposal-proposal compatibility for composition                 │
│                                                                             │
│  V10.6: +MoE FFN (Mixture of Experts)                                       │
│         └── Sparse expert routing for compute efficiency                    │
│                                                                             │
│  V10.6.2: +No-Write Contracts                                               │
│         └── Prevents token injection into Phase control                     │
│                                                                             │
│  V10.7: +HP-Quad (Hierarchical Phase-Quad)                                  │
│         └── Multi-timescale processing with boundary detection              │
│                                                                             │
│  V10.7+: +Reflective Phase-Quad                                             │
│         └── Self-evaluation and latent revision loops                       │
│                                                                             │
│  V10.8: +RLM-Phase-Quad Integration                                         │
│         └── Unlimited context via recursive decomposition                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Table of Contents

1. [Core Phase-Quad Architecture](#1-core-phase-quad-architecture)
2. [MoE FFN (V10.6)](#2-moe-ffn-v106)
3. [Hierarchical Phase-Quad (V10.7)](#3-hierarchical-phase-quad-v107)
4. [Reflective Phase-Quad](#4-reflective-phase-quad)
5. [RLM-Phase-Quad Integration (V10.8)](#5-rlm-phase-quad-integration-v108)
6. [Interference-Aware Proposal Scoring (V10.5)](#6-interference-aware-proposal-scoring-v105)
7. [Sovereign Reasoning Kernel (V10.3.0)](#7-sovereign-reasoning-kernel-v1030)
8. [Kosha Consciousness System (V10.3.4)](#8-kosha-consciousness-system-v1034)
9. [No-Write Contracts (V10.6.2)](#9-no-write-contracts-v1062)
10. [Architecture Compatibility Matrix](#10-architecture-compatibility-matrix)
11. [CLI Reference](#11-cli-reference)

---

## 1. Core Phase-Quad Architecture

### Overview

The foundational architecture that all supplements build upon. Replaces O(n²) full attention with three specialized mechanisms.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CORE PHASE-QUAD BLOCK                                │
│                                                                             │
│  Input: x ∈ ℝ^(B×N×D)                                                       │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. LOCAL ATTENTION                                     O(n·w)     │   │
│  │     - Windowed self-attention (window_size w, typically 64-128)    │   │
│  │     - Captures syntax, local dependencies, texture                 │   │
│  │     - No global information flow                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  2. PHASE INTEGRATOR                                    O(n)       │   │
│  │     - RNN-like persistent state (GRU cell)                         │   │
│  │     - Maintains context across sequence                            │   │
│  │     - State dimension: d_phase (typically 256-512)                 │   │
│  │     - KEY INSIGHT: State mechanism, not attention mechanism        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  3. QUAD PROPOSAL                                       O(n·k)     │   │
│  │     - Generates k proposals per position                           │   │
│  │     - Retrieves from external memory bank                          │   │
│  │     - Sparse attention (top-k selection)                           │   │
│  │     - Provides non-local information without quadratic cost        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  Output: y ∈ ℝ^(B×N×D)                                                      │
│                                                                             │
│  Total Complexity: O(n·w) + O(n) + O(n·k) = O(n) (linear!)                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Properties

| Property | Standard Transformer | Phase-Quad |
|----------|---------------------|------------|
| Complexity | O(n²) | O(n) |
| Memory | O(n²) | O(n) |
| State Persistence | None | Yes (Phase Integrator) |
| Sparse Retrieval | No | Yes (Quad Proposal) |
| Local Processing | No | Yes (Local Attention) |

### Implementation Location

- **Module**: `symbolu/phase_transformer.py`
- **CLI**: Base model in `train_hard_probes.py`

---

## 2. MoE FFN (V10.6)

### Purpose

Replace dense FFN with Mixture of Experts for **~2x compute savings** while maintaining quality.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MOE FFN (MIXTRAL-STYLE)                                                    │
│                                                                             │
│  Standard FFN:                                                              │
│    x → Linear(d, 4d) → GELU → Linear(4d, d) → x                            │
│    FLOPs: 8BNd²                                                             │
│                                                                             │
│  MoE FFN (8 experts, 2 active):                                             │
│    x → Router → top-2 experts → weighted sum → x                            │
│    FLOPs: 2BNd² (75% savings on FFN, ~50% overall)                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ROUTER                                                             │   │
│  │    r = softmax(W_r @ x)          # [B, N, num_experts]              │   │
│  │    top_k = argtopk(r, k=2)       # Select 2 of 8 experts            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                    │                                                        │
│         ┌─────────┴─────────┐                                               │
│         ▼                   ▼                                               │
│    ┌──────────┐       ┌──────────┐                                          │
│    │ Expert_i │       │ Expert_j │     (2 of 8 active)                      │
│    │ FFN(d,4d)│       │ FFN(d,4d)│                                          │
│    └──────────┘       └──────────┘                                          │
│         │                   │                                               │
│         └────────┬──────────┘                                               │
│                  ▼                                                          │
│    output = r_i * Expert_i(x) + r_j * Expert_j(x)                           │
│                                                                             │
│  Auxiliary Losses:                                                          │
│  ├── Load Balance: Encourage uniform expert utilization                     │
│  └── Router Z-loss: Stabilize router probabilities                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Properties

| Configuration | Default | Range |
|---------------|---------|-------|
| num_experts | 8 | 4-16 |
| top_k | 2 | 1-4 |
| load_balance_weight | 0.01 | 0.001-0.1 |
| router_z_weight | 0.001 | 0.0001-0.01 |

### Implementation Location

- **Module**: `symbolu/moe_ffn.py`
- **Design Doc**: `docs/architecture/MOE_QUAD_PROPOSAL_DESIGN.md`
- **CLI**: `--test-moe-ffn`, `--moe-num-experts`, `--moe-top-k`

### Integration with Phase-Quad

```
Phase-Quad Block:
  ├── Local Attention
  ├── Phase Integrator  ← NO MoE (must be dense for state coherence)
  ├── Quad Proposal
  └── FFN              ← MoE HERE (standard position)
```

---

## 3. Hierarchical Phase-Quad (V10.7)

### Purpose

**Multi-timescale processing** inspired by HM-RNN (Chung et al., 2016). Different levels operate at different temporal resolutions with learned boundary detection.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HIERARCHICAL PHASE-QUAD (HP-QUAD)                                          │
│                                                                             │
│  Token₁ → Token₂ → Token₃ → Token₄ → Token₅ → ...                           │
│    │        │        │        │        │                                    │
│    ▼        ▼        ▼        ▼        ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LEVEL 1: FAST (Every Token)                     d_phase = 128      │   │
│  │  - Local Attention + Phase₁                                         │   │
│  │  - Syntax, texture, immediate context                               │   │
│  │  - Updates: EVERY token                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                         │                                                   │
│                   Boundary Detector z₁                                      │
│                    (phrase boundaries)                                      │
│                         │ if z₁ = 1                                         │
│                         ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LEVEL 2: MEDIUM (At Boundaries)                 d_phase = 256      │   │
│  │  - Phase₂ Integrator                                                │   │
│  │  - Semantic coherence, topic tracking                               │   │
│  │  - Updates: ~15% of tokens (at boundaries)                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                         │                                                   │
│                   Boundary Detector z₂                                      │
│                  (paragraph boundaries)                                     │
│                         │ if z₂ = 1                                         │
│                         ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LEVEL 3: SLOW (Major Transitions)               d_phase = 512      │   │
│  │  - Phase₃ + Quad Proposal                                           │   │
│  │  - Document-level memory, cross-document retrieval                  │   │
│  │  - Updates: ~3% of tokens (at major transitions)                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Boundary Detector:                                                         │
│    z = σ(W_z · [h; phase]) > threshold                                     │
│    Uses Straight-Through Estimator for gradient flow                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Properties

| Configuration | Default | Description |
|---------------|---------|-------------|
| num_levels | 3 | Number of hierarchy levels |
| d_phase_levels | (128, 256, 512) | Phase dimension per level |
| chunk_sizes | (1, 8, 64) | Retrieval granularity per level |
| boundary_threshold | 0.5 | Threshold for boundary detection |
| target_boundary_rate | 0.15 | Target rate for regularization |

### Implementation Location

- **Module**: `symbolu/hp_quad.py`
- **Design Doc**: `docs/architecture/HIERARCHICAL_PHASE_QUAD_DESIGN.md`
- **CLI**: `--test-hp-quad`, `--hp-num-levels`, `--hp-boundary-ablation`

---

## 4. Reflective Phase-Quad

### Purpose

**Self-evaluation and revision** without external prompting. The model internally evaluates output quality and revises until a threshold is met.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  REFLECTIVE PHASE-QUAD                                                      │
│                                                                             │
│  Input                                                                      │
│    │                                                                        │
│    ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. GENERATOR (Phase-Quad Core)                                     │   │
│  │     - Local Attention + Phase Integrator + Quad Proposal            │   │
│  │     → Produces: candidate_output                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│    │                                                                        │
│    ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  2. CRITIC (Quality Estimator)                                      │   │
│  │     - Process Reward Model (learned)                                │   │
│  │     - Evaluates: Coherence, Correctness, Completeness               │   │
│  │     → Produces: quality_score ∈ [0, 1]                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│    │                                                                        │
│    ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  3. DECISION GATE                                                   │   │
│  │                                                                     │   │
│  │     IF quality ≥ threshold:                                         │   │
│  │         → OUTPUT (done)                                             │   │
│  │     ELIF revisions < max_revisions:                                 │   │
│  │         → REVISE (loop back with context)                           │   │
│  │     ELSE:                                                           │   │
│  │         → OUTPUT with uncertainty_flag                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│    │                                                                        │
│    │ (if revising)                                                          │
│    ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  4. REVISION ENCODER                                                │   │
│  │     - Encodes: (original_input, previous_attempt, quality_dims)     │   │
│  │     → Produces: revision_context                                    │   │
│  │     → Feeds back to Generator                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              └──────────→ Loop to Generator                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Properties

| Configuration | Default | Description |
|---------------|---------|-------------|
| quality_threshold | 0.7 | Minimum quality to accept output |
| max_revisions | 3 | Maximum revision iterations |
| quality_dims | 3 | (coherence, correctness, completeness) |
| temperature | 1.0 | Revision sampling temperature |

### Comparison: o1 vs Reflective Phase-Quad

| Aspect | o1 (Token CoT) | Reflective Phase-Quad |
|--------|----------------|----------------------|
| Revision space | Token sequence | Latent representation |
| Cost | High (many tokens) | Lower (hidden state) |
| Interpretability | High (readable) | Lower (latent) |
| Memory efficiency | Poor | Good |
| Revision granularity | Word-level | Concept-level |

### Implementation Location

- **Design Doc**: `docs/architecture/REFLECTIVE_PHASE_QUAD_DESIGN.md`
- **Module**: Integrated into `symbolu/rlm_phase_quad.py`

---

## 5. RLM-Phase-Quad Integration (V10.8)

### Purpose

Combine **Recursive Language Models** (unlimited context) with **Phase-Quad** (efficient processing) for handling 10M+ token contexts.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  RLM-PHASE-QUAD INTEGRATED SYSTEM                                           │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 1: RLM ORCHESTRATION                                           │ │
│  │                                                                       │ │
│  │  [10M+ token document] → REPL Environment                             │ │
│  │                              │                                        │ │
│  │                        HP-Quad Boundary Detection                     │ │
│  │                              │                                        │ │
│  │                    Semantic Chunking (learned boundaries)             │ │
│  │                              │                                        │ │
│  │                    Decomposition Strategy (LLM-generated)             │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                         sub-queries                                         │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 2: PHASE-QUAD PROCESSING                                       │ │
│  │                                                                       │ │
│  │  For each chunk:                                                      │ │
│  │    ├── Local Attention (syntax)                                       │ │
│  │    ├── Phase Integrator (PERSISTENT across chunks!)                   │ │
│  │    ├── Quad Proposal (retrieval from accumulated memory)              │ │
│  │    └── Result → stored in REPL                                        │ │
│  │                                                                       │ │
│  │  Memory Banks sync: REPL variables → Quad memory banks                │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                         sub-results                                         │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 3: REFLECTIVE QUALITY CONTROL                                  │ │
│  │                                                                       │ │
│  │  For each sub-result:                                                 │ │
│  │    ├── Critic evaluates quality                                       │ │
│  │    ├── If quality < threshold: trigger deeper decomposition           │ │
│  │    └── Quality scores propagate to synthesis                          │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  SYNTHESIS                                                            │ │
│  │                                                                       │ │
│  │  Combine all sub-results with merged Phase State                      │ │
│  │  → Final answer with quality metadata                                 │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Purpose |
|-----------|---------|
| REPLEnvironment | Stores context, chunks, sub-results, search cache |
| PhaseStateManager | Persistent Phase State across recursive branches |
| BoundaryAwareChunker | HP-Quad boundaries for semantic chunking |
| MemoryBankSynchronizer | REPL variables → Quad memory banks |
| QualityAwareRecursionController | Reflective quality gates |

### Key Properties

| Configuration | Default | Description |
|---------------|---------|-------------|
| max_recursion_depth | 5 | Maximum recursion depth |
| max_context | 10M+ | Effectively unlimited |
| min_chunk_size | 100 | Minimum tokens per chunk |
| max_chunk_size | 4096 | Maximum tokens per chunk |
| quality_threshold | 0.7 | Quality gate threshold |

### Implementation Location

- **Module**: `symbolu/rlm_phase_quad.py`
- **Design Doc**: `docs/architecture/RLM_PHASE_QUAD_INTEGRATION_DESIGN.md`
- **CLI**: `--test-rlm-phase-quad`, `--rlm-pq-max-context`, `--rlm-pq-scalability-test`

---

## 6. Interference-Aware Proposal Scoring (V10.5)

### Purpose

**Proposal-proposal compatibility** scoring for compositional tasks. Helps when blending multiple concepts/styles in generation.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  INTERFERENCE-AWARE PROPOSAL SCORING                                        │
│                                                                             │
│  Standard Quad Proposal:                                                    │
│    proposals → score individually → select top-k                            │
│                                                                             │
│  With Interference Scoring:                                                 │
│    proposals → score individually                                           │
│                    │                                                        │
│                    ├── + Proposal-Proposal Compatibility Matrix             │
│                    │                                                        │
│                    └── Interference term: λ * I_ij (if compositional task)  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  TASK CLASSIFIER (Auto-enable)                                      │   │
│  │                                                                     │   │
│  │  Compositional (ENABLE interference):                               │   │
│  │    - "Compare X, Y, Z"                                              │   │
│  │    - "Synthesize across factors"                                    │   │
│  │    - Long-form writing with style blending                          │   │
│  │                                                                     │   │
│  │  Factual/Code (DISABLE interference):                               │   │
│  │    - "What is X?"                                                   │   │
│  │    - Code generation                                                │   │
│  │    - Retrieval-heavy tasks                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Gating Conditions:                                                         │
│  ├── Task must be compositional (auto-classified)                           │
│  ├── Decoding step > min_step (default: 8)                                  │
│  └── Proposal entropy > entropy_gate (default: 1.2)                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Properties

| Configuration | Text LLM | Vision |
|---------------|----------|--------|
| lambda | 0.01-0.03 | 0.05-0.08 |
| min_step | 8 | 4 |
| entropy_gate | 1.2 | 0.8 |
| auto_classify | Yes | No |

### Implementation Location

- **Module**: `symbolu/text_interference.py`
- **CLI**: `--test-interference`, `--interference-lambda`

---

## 7. Sovereign Reasoning Kernel (V10.3.0)

### Purpose

**32D Ontological State governance** for reasoning-based (not just retrieval-based) intelligence. Ensures structural integrity across domains.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SOVEREIGN REASONING KERNEL (SRK)                                           │
│                                                                             │
│  DUAL-PROCESS ARCHITECTURE:                                                 │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  SYSTEM 1: Linguistic Engine ("Body")                                 │ │
│  │  - Standard autoregressive learning                                   │ │
│  │  - Next-token prediction                                              │ │
│  │  - Learns grammar, facts, patterns                                    │ │
│  │  → Enables fluent language generation                                 │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                              ↕                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  SYSTEM 2: Ontological Governor ("Soul")                              │ │
│  │                                                                       │ │
│  │  32D Sovereign State:                                                 │ │
│  │    ├── 12 Bhavas (Astrological Houses)                                │ │
│  │    ├── 5 Koshas (Consciousness Sheaths)                               │ │
│  │    ├── 5 Vrittis (Mental States)                                      │ │
│  │    └── 6 Gunas (Qualities) + 4 Padding                                │ │
│  │                                                                       │ │
│  │  Intervention Points:                                                 │ │
│  │    L4: Ontology injection                                             │ │
│  │    L7: CSR Alignment (Phase Extraction Hook)                          │ │
│  │    L9: Witnessing (Sakshi observation)                                │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  KEY INSIGHT: When model learns mathematical rigor in one domain,           │
│               that rigor is structurally preserved in other domains.        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation Location

- **Design Doc**: `docs/architecture/SOVEREIGN_REASONING_KERNEL_DESIGN.md`
- **Integration**: Layer hooks in `train_hard_probes.py`

---

## 8. Kosha Consciousness System (V10.3.4)

### Purpose

Model **5 sheaths of consciousness** from Vedantic philosophy for richer internal state representation.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  KOSHA CONSCIOUSNESS SYSTEM (5 SHEATHS)                                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ANNAMAYA (Physical)        - Token embeddings, surface form        │   │
│  │  PRANAMAYA (Energy)         - Activation patterns, information flow │   │
│  │  MANOMAYA (Mental)          - Attention patterns, reasoning         │   │
│  │  VIJNANAMAYA (Wisdom)       - High-level abstractions               │   │
│  │  ANANDAMAYA (Bliss)         - Unified understanding                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Components:                                                                │
│  ├── KoshaShiftController: Manages transitions between sheaths             │
│  ├── KoshaGyroscopicLoss: Maintains stability during shifts                │
│  ├── KoshaPhaseCorrector: Aligns Phase state with Kosha state              │
│  └── KoshaDiagnostics: Monitors Kosha activation patterns                  │
│                                                                             │
│  Integration with Phase-Quad:                                               │
│  - Kosha state influences Phase Integrator                                  │
│  - Higher Koshas modulate Quad Proposal retrieval                           │
│  - Domain separation: Kosha operates at designated layers                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation Location

- **Integration**: `train_hard_probes.py` (local implementations)
- **CLI**: `--enable-kosha`, `--kosha-layer`

---

## 9. No-Write Contracts (V10.6.2)

### Purpose

**Prevent token injection into Phase control**. Ensures control signals remain low-dimensional and broadcastable.

### Contract Specification

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  NO-WRITE CONTRACT (V10.6.2)                                                │
│                                                                             │
│  THE CONTRACT IN ONE SENTENCE:                                              │
│  "intent_phase (and any control) must be low-dimensional, broadcastable,    │
│   and not token-position dependent."                                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PREVENT (Violations):                                              │   │
│  │  ├── Token-wise content injected into Phase control                 │   │
│  │  ├── Control signals with sequence length dimension                 │   │
│  │  └── Control signals with d_model as last dimension                 │   │
│  │                                                                     │   │
│  │  ALLOW (Valid Shapes):                                              │   │
│  │  ├── Scalars                                                        │   │
│  │  ├── Per-head/per-layer: [layers, heads], [batch, heads]            │   │
│  │  ├── Broadcastable: [B, H, 1, 1]                                    │   │
│  │  └── Phase control: [B, d_phase] where d_phase << d_model           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Validation Function:                                                       │
│    def validate_no_write_contract(tensor, name, config):                    │
│        if tensor has seq_len dimension: VIOLATION                           │
│        if tensor.shape[-1] == d_model: VIOLATION                            │
│        return VALID                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation Location

- **Validation**: `train_hard_probes.py` (`validate_no_write_contract()`)
- **CLI**: `--enforce-no-write-contracts`

---

## 10. Architecture Compatibility Matrix

### Which architectures can be combined?

| Base | +MoE | +HP-Quad | +Reflective | +RLM | +Interference | +SRK | +Kosha |
|------|------|----------|-------------|------|---------------|------|--------|
| **Phase-Quad** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **+MoE** | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **+HP-Quad** | ✅ | - | ✅ | ✅ (boundary chunking) | ✅ | ✅ | ✅ |
| **+Reflective** | ✅ | ✅ | - | ✅ (quality gates) | ⚠️ | ✅ | ✅ |
| **+RLM** | ✅ | ✅ | ✅ | - | ⚠️ | ✅ | ⚠️ |
| **+Interference** | ✅ | ⚠️ | ⚠️ | ⚠️ | - | ✅ | ✅ |

Legend: ✅ = Fully compatible, ⚠️ = Partially compatible (requires care)

### Recommended Combinations

| Use Case | Recommended Stack |
|----------|------------------|
| **Cost Efficiency** | Phase-Quad + MoE |
| **Long Documents** | Phase-Quad + HP-Quad + RLM |
| **High Quality** | Phase-Quad + Reflective |
| **Unlimited Context** | Phase-Quad + HP-Quad + RLM + Reflective |
| **Full Stack** | Phase-Quad + MoE + HP-Quad + Reflective + RLM |

---

## 11. CLI Reference

### Complete CLI Flags

```bash
# ============================================================================
# CORE BENCHMARKS
# ============================================================================

# Basic Phase-Quad training
python train_hard_probes.py

# ============================================================================
# MOE FFN (V10.6)
# ============================================================================
python train_hard_probes.py --test-moe-ffn
python train_hard_probes.py --test-moe-ffn --moe-num-experts 16 --moe-top-k 2
python train_hard_probes.py --test-moe-ffn --moe-ablation

# ============================================================================
# HP-QUAD (V10.7)
# ============================================================================
python train_hard_probes.py --test-hp-quad
python train_hard_probes.py --test-hp-quad --hp-num-levels 3 \
    --hp-d-phase-levels 128,256,512 --hp-chunk-sizes 1,8,64
python train_hard_probes.py --test-hp-quad --hp-boundary-ablation

# ============================================================================
# RLM-PHASE-QUAD (V10.8)
# ============================================================================
python train_hard_probes.py --test-rlm-phase-quad
python train_hard_probes.py --test-rlm-phase-quad --rlm-pq-max-context 100000
python train_hard_probes.py --test-rlm-phase-quad --rlm-pq-scalability-test

# ============================================================================
# INTERFERENCE SCORING (V10.5)
# ============================================================================
python train_hard_probes.py --test-interference
python train_hard_probes.py --test-interference --interference-lambda 0.02

# ============================================================================
# KOSHA/SRK CONSCIOUSNESS (V10.3.4)
# ============================================================================
python train_hard_probes.py --enable-kosha --kosha-layer 2
python train_hard_probes.py --enable-witness --witness-layer 2

# ============================================================================
# CONTRACTS (V10.6.2)
# ============================================================================
python train_hard_probes.py --enforce-no-write-contracts
```

---

## Summary Table

| Architecture | Version | Purpose | Complexity | Key Benefit |
|--------------|---------|---------|------------|-------------|
| **Core Phase-Quad** | V10.0 | Replace O(n²) attention | O(n) | Linear scaling |
| **MoE FFN** | V10.6 | Sparse experts | ~2x cheaper | Cost savings |
| **HP-Quad** | V10.7 | Multi-timescale | +20% overhead | Long-range memory |
| **Reflective** | V10.7+ | Self-revision | Variable | Quality improvement |
| **RLM Integration** | V10.8 | Unlimited context | Recursive | 10M+ tokens |
| **Interference** | V10.5 | Proposal compatibility | Minimal | Composition quality |
| **SRK** | V10.3.0 | 32D state governance | Per-layer hooks | Reasoning transfer |
| **Kosha** | V10.3.4 | 5-sheath consciousness | Per-layer hooks | Rich state |
| **No-Write** | V10.6.2 | Control validation | Minimal | Safety |

---

## Appendix: Module Locations

| Architecture | Module | Design Doc |
|--------------|--------|------------|
| Core Phase-Quad | `symbolu/phase_transformer.py` | - |
| MoE FFN | `symbolu/moe_ffn.py` | `MOE_QUAD_PROPOSAL_DESIGN.md` |
| HP-Quad | `symbolu/hp_quad.py` | `HIERARCHICAL_PHASE_QUAD_DESIGN.md` |
| Reflective | (integrated) | `REFLECTIVE_PHASE_QUAD_DESIGN.md` |
| RLM Integration | `symbolu/rlm_phase_quad.py` | `RLM_PHASE_QUAD_INTEGRATION_DESIGN.md` |
| Interference | `symbolu/text_interference.py` | - |
| SRK | (train_hard_probes.py) | `SOVEREIGN_REASONING_KERNEL_DESIGN.md` |
| Kosha | (train_hard_probes.py) | - |

---

**End of Document**
