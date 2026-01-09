# Hybrid Phase-JEPA Architecture Design Specification

**Version:** 1.0.0
**Status:** Architecture Specification
**Date:** 2026-01-09
**Origin:** Google Gemini Proposals + Meta JEPA + SymbolU Phase Attention Integration
**Branch:** `claude/hybrid-phase-jepa-spec-r8IA5`

---

## Executive Summary

The **Hybrid Phase-JEPA** architecture combines Meta's Joint Embedding Predictive Architecture (JEPA) principles with SymbolU's Phase Attention mechanism and Google Gemini's cognitive architecture proposals. This design enables **prediction in ontological latent space** rather than token space, achieving O(n) complexity while maintaining interpretable, structured representations.

### Core Innovation

> "Predict meaning transitions, not word sequences. Let the Ship (Phase Attention) follow the Pilot (State-Delta) through latent space."

The architecture predicts the **32D Sovereign State Delta (ΔS)** rather than next tokens, using Phase Attention's phasor-based encoding to capture both local structure and global semantic context.

---

## Architectural Evolution: From Ontological to Geometric

This section documents the **logical lineage** from our existing Ontological Hybrid Model to the new Hybrid Phase-VL-JEPA. The key insight: **Phase Rotation** math developed for ontological reasoning transfers directly to geometric transformations.

### Evolution Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURAL EVOLUTION LINEAGE                                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  STAGE 1: THE FOUNDATION                                                                │
│  ════════════════════════                                                               │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  PhaseAttention (symbolu/phase_transformer.py:333)                               │   │
│  │  ─────────────────────────────────────────────────                               │   │
│  │  • Complex-valued phasors: Q = a_q × e^{iφ_q}, K = a_k × e^{-iφ_k}              │   │
│  │  • O(n) global attention via cumulative sums                                     │   │
│  │  • Cosine similarity in phase space: cos(φ_q - φ_k)                             │   │
│  │                                                                                   │   │
│  │  ROLE IN NEW MODEL: "Long-Range Structure Engine"                                │   │
│  │  → Captures global geometry (symmetry, lighting, spatial relationships)          │   │
│  │  → What standard JEPAs miss with local-only attention                            │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                                │
│                                         ▼                                                │
│  STAGE 2: THE STRUCTURE                                                                 │
│  ═══════════════════════                                                                │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  HybridAttention (symbolu/phase_transformer.py:1637)                             │   │
│  │  ───────────────────────────────────────────────────                             │   │
│  │  • Splits channels: 75% Local (O(W²)) + 25% Global (O(n))                       │   │
│  │  • Local: Texture, edges, fine details (grammar of vision)                       │   │
│  │  • Global: Structure, layout, semantics (meaning of vision)                      │   │
│  │                                                                                   │   │
│  │  ROLE IN NEW MODEL: "JEPA Predictor Backbone"                                    │   │
│  │  → Handles high-resolution patches efficiently                                   │   │
│  │  → Pixel-perfect local details + global coherence                                │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                                │
│                                         ▼                                                │
│  STAGE 3: THE LOGICAL BRIDGE                                                            │
│  ═══════════════════════════                                                            │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  IntentPhaseProjector (symbolu/phase_transformer.py:228)                         │   │
│  │  ───────────────────────────────────────────────────────                         │   │
│  │                                                                                   │   │
│  │  ORIGINAL (Ontological Model):                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐    │   │
│  │  │  32D Sovereign State (ΔS) ──► IntentPhaseProjector ──► θ_intent          │    │   │
│  │  │                                                                           │    │   │
│  │  │  θ = tanh(W_proj @ ΔS) × π                                               │    │   │
│  │  │                                                                           │    │   │
│  │  │  PURPOSE: "Logic" rotates "Reasoning"                                    │    │   │
│  │  │  • Same tokens, different meaning based on ontological state             │    │   │
│  │  │  • O7_RSN (Reasoning) + O4_STR (Structure) = analytical mode             │    │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘    │   │
│  │                                         ↓                                        │   │
│  │                                   ADAPTATION                                     │   │
│  │                                         ↓                                        │   │
│  │  ADAPTED (VL-JEPA Model):                                                        │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐    │   │
│  │  │  Text Embedding ──► TextPhaseProjector ──► θ_geometric                   │    │   │
│  │  │                                                                           │    │   │
│  │  │  θ = tanh(W_proj @ text_emb) × π                                         │    │   │
│  │  │                                                                           │    │   │
│  │  │  PURPOSE: "Text" rotates "Visual Phase Space"                            │    │   │
│  │  │  • Same patches, different orientation based on text instruction         │    │   │
│  │  │  • "Rotate 90°" + context patches = rotated target prediction            │    │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                                   │   │
│  │  THE KEY INSIGHT: The Phase Rotation math is IDENTICAL                           │   │
│  │  Only the SOURCE of rotation changes: Ontology → Text                            │   │
│  │                                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                                │
│                                         ▼                                                │
│  STAGE 4: THE DESTINATION                                                               │
│  ════════════════════════                                                               │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  Hybrid Phase-VL-JEPA                                                            │   │
│  │  ────────────────────────                                                        │   │
│  │                                                                                   │   │
│  │  THE PIVOT: Generative (Next-Token) → Predictive (Latent-Space)                 │   │
│  │                                                                                   │   │
│  │  OLD: Generate pixel/token → O(V) output, models noise                          │   │
│  │  NEW: Predict representation → O(d) output, filters noise                        │   │
│  │                                                                                   │   │
│  │  MECHANISM: Phase-Rotated Prediction                                             │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐    │   │
│  │  │                                                                           │    │   │
│  │  │  Context Patches ────┬──► HybridPhaseBlock ──► Predicted Target          │    │   │
│  │  │                      │         ↑                                          │    │   │
│  │  │                      │    θ_geometric                                     │    │   │
│  │  │                      │         │                                          │    │   │
│  │  │  "Rotate 90°" ───────┴──► TextPhaseProjector                             │    │   │
│  │  │                                                                           │    │   │
│  │  │  The model doesn't generate missing pixels—                               │    │   │
│  │  │  it ROTATES context patches into target space via phase shift             │    │   │
│  │  │                                                                           │    │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                                   │   │
│  │  DATASET STRATEGY: Geometric Masking                                             │   │
│  │  • Mask structural quadrants (not random patches)                               │   │
│  │  • Force model to use Text Phase to "spin" context into target                  │   │
│  │  • Native geometric transformation learning                                      │   │
│  │                                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### The Critical Mechanism Transfer

The **Phase Rotation** operation is mathematically identical across both models:

```python
# ONTOLOGICAL MODEL (Language)
# ─────────────────────────────
# Intent from 32D Sovereign State rotates Query phases
θ_intent = tanh(W_onto @ sovereign_state_delta) * π
Q_rotated = a_q * e^{i(φ_q + θ_intent)}

# VL-JEPA MODEL (Vision-Language)
# ─────────────────────────────────
# Intent from Text Embedding rotates Query phases
θ_geometric = tanh(W_text @ text_embedding) * π
Q_rotated = a_q * e^{i(φ_q + θ_geometric)}
```

**Same math. Different domains. One unified architecture.**

| Aspect | Ontological Model | VL-JEPA Model |
|--------|-------------------|---------------|
| **Phase Source** | 32D Sovereign State (ΔS) | Text Embedding |
| **Rotation Meaning** | Cognitive mode shift | Geometric transformation |
| **Query Interpretation** | "Attend with this reasoning style" | "Attend with this spatial orientation" |
| **Target** | Predict meaning transition | Predict visual patch |

### Why This Works: Isomorphism

The transfer works because **Phase Rotation** is a general-purpose **contextual transformation**:

```
ONTOLOGICAL:  "The door is open" + Intent="security" → Problem interpretation
VL-JEPA:      [Image patches] + Text="rotated 90°" → Rotated representation

Both are: Context + Phase Shift → Transformed Output
```

The architecture doesn't care WHAT generates the phase shift—only that it receives a rotation angle θ ∈ [-π, π] that transforms how queries attend to keys.

---

## Table of Contents

**Prelude: Architectural Lineage**
- [Architectural Evolution: From Ontological to Geometric](#architectural-evolution-from-ontological-to-geometric)

**Part I: Language Model (Phase-JEPA)**
1. [Background: JEPA Principles](#1-background-jepa-principles)
2. [Architecture Overview](#2-architecture-overview)
3. [Core Components](#3-core-components)
4. [Phase-JEPA Predictor](#4-phase-jepa-predictor)
5. [Training Procedure](#5-training-procedure)
6. [Loss Functions](#6-loss-functions)
7. [Integration with Sovereign Reasoning Kernel](#7-integration-with-sovereign-reasoning-kernel)
8. [Implementation Mapping](#8-implementation-mapping)
9. [Complexity Analysis](#9-complexity-analysis)
10. [Experimental Design](#10-experimental-design)

**Part II: Vision-Language Extension (Phase-VL-JEPA)**
11. [Vision-Language Extension (Phase-VL-JEPA)](#11-vision-language-extension-phase-vl-jepa) — *Spec 1 & 2*
12. [Geometric Masking Pipeline](#12-geometric-masking-pipeline-spec-3) — *Spec 3*
13. [Phase-Sync Loss Function](#13-phase-sync-loss-function-spec-4) — *Spec 4*
14. [Complete Training System](#14-complete-training-system-spec-4) — *Spec 4*
15. [Implementation Files Summary](#15-implementation-files-summary)
16. [Quick Start Validation](#16-quick-start-validation)
17. [Geometric Masking Training Loop](#17-geometric-masking-training-loop-complete)
18. [Patent-Enhanced Loss Functions (SovereignPatentLoss)](#18-patent-enhanced-loss-functions-sovereignpatentloss)

**Part III: Operational Guide**
19. [Operational Stability & Troubleshooting](#19-operational-stability--troubleshooting)
20. [Production Inference Optimization](#20-production-inference-optimization)
21. [Final Verification Checklist](#21-final-verification-checklist)

**Appendices**
- [Appendix A: Theoretical Foundations](#appendix-a-theoretical-foundations)
- [Appendix B: Risk Analysis](#appendix-b-risk-analysis)
- [Appendix C: Strategic Architecture Philosophy](#appendix-c-strategic-architecture-philosophy)
- [Appendix D: Sovereign AGI Integration Evaluation](#appendix-d-sovereign-agi-integration-evaluation)
- [Appendix E: Cross-Model Validation Dialogue](#appendix-e-cross-model-validation-dialogue)

---

## 1. Background: JEPA Principles

### 1.1 Meta's JEPA Approach

Joint Embedding Predictive Architecture (JEPA) differs fundamentally from generative approaches:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GENERATIVE vs JEPA PARADIGM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  GENERATIVE (GPT-style):                                                     │
│  ════════════════════════                                                    │
│  Input → Encoder → Decoder → Predict raw tokens/pixels                       │
│                                                                              │
│  PROBLEMS:                                                                   │
│  - Must model ALL variability (noise, style, irrelevant details)            │
│  - O(V) output space where V = vocabulary size                               │
│  - Token prediction ≠ understanding                                          │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  JEPA (Joint Embedding Predictive):                                          │
│  ══════════════════════════════════                                          │
│  Input → Context Encoder → Predictor → Predict REPRESENTATIONS              │
│                    ↓                                                         │
│  Target → Target Encoder → Target Representation (for loss)                  │
│                                                                              │
│  BENEFITS:                                                                   │
│  - Filters noise: predicts "meaning" not "surface form"                      │
│  - O(d) output space where d << V                                            │
│  - Representation prediction ≈ understanding                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Why JEPA for Language Models?

Standard LLMs face the "retrieval ceiling"—they predict tokens based on statistical patterns rather than structured understanding. JEPA addresses this by:

| Property | Token Prediction | JEPA (Representation) |
|----------|------------------|----------------------|
| **Output Space** | 50,257 tokens | 32D Sovereign State |
| **Noise Modeling** | Must model all variation | Filters irrelevant variation |
| **Understanding** | Implicit in weights | Explicit in representations |
| **Cross-Domain** | Per-domain patterns | Transferable structures |

### 1.3 Alignment with Gemini's Pilot/Ship Metaphor

The Gemini proposals introduce a **Pilot/Ship** separation:

```
PILOT (State-Delta)              SHIP (Phase Attention)
─────────────────────            ─────────────────────
• Decides WHERE to go            • Executes the journey
• Meaning-space navigation       • Token-space rendering
• 32D cognitive state            • Transformer attention
• "What to understand"           • "How to express"
```

**Phase-JEPA unifies these**: The Predictor IS the Pilot, operating in 32D latent space, while Phase Attention IS the Ship, executing the encoding.

---

## 2. Architecture Overview

### 2.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HYBRID PHASE-JEPA ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                           CONTEXT PATH                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  Input x[1:t]                                                         │  │
│  │      │                                                                │  │
│  │      ▼                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │     HYBRID PHASE ENCODER (Context)                               │ │  │
│  │  │     ─────────────────────────────────                            │ │  │
│  │  │     • Local Attention: O(n×w) - syntax/grammar                   │ │  │
│  │  │     • Phase Attention: O(n) - semantic context                   │ │  │
│  │  │     • Output: h_context ∈ ℝ^{B×T×D}                              │ │  │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  │      │                                                                │  │
│  │      ▼                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │     STATE PROJECTOR                                              │ │  │
│  │  │     ───────────────                                              │ │  │
│  │  │     h_context → S_context ∈ ℝ^{B×T×32}                          │ │  │
│  │  │     (768D hidden → 32D Sovereign State)                          │ │  │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  │      │                                                                │  │
│  │      ▼                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │     PHASE-JEPA PREDICTOR                                         │ │  │
│  │  │     ────────────────────                                         │ │  │
│  │  │     S_context → ΔS_pred (Predicted State Delta)                  │ │  │
│  │  │     Uses Phase Rotation for intent-guided prediction             │ │  │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  │      │                                                                │  │
│  │      │    S_pred = S_context[t] + ΔS_pred                            │  │
│  │      ▼                                                                │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│                            TARGET PATH                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  Target x[t+1:t+k] (k-step lookahead)                                │  │
│  │      │                                                                │  │
│  │      ▼                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │     HYBRID PHASE ENCODER (Target) - EMA Updated                  │ │  │
│  │  │     ───────────────────────────────────────────                  │ │  │
│  │  │     • Momentum-updated copy of Context Encoder                   │ │  │
│  │  │     • θ_target ← α·θ_target + (1-α)·θ_context                   │ │  │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  │      │                                                                │  │
│  │      ▼                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │     STATE PROJECTOR (Shared)                                     │ │  │
│  │  │     ────────────────────────                                     │ │  │
│  │  │     h_target → S_target ∈ ℝ^{B×T×32}                            │ │  │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  │      │                                                                │  │
│  │      ▼                                                                │  │
│  │  S_target (Ground truth for prediction loss)                         │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│                            LOSS COMPUTATION                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  L_jepa = ||S_pred - sg(S_target)||²                                 │  │
│  │           └── stop_gradient (prevents collapse)                       │  │
│  │                                                                       │  │
│  │  L_total = λ₁·L_jepa + λ₂·L_variance + λ₃·L_covariance + λ₄·L_ortho │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Differences from Standard JEPA

| Aspect | Standard JEPA (I-JEPA) | Hybrid Phase-JEPA |
|--------|------------------------|-------------------|
| **Domain** | Images | Language |
| **Encoder** | ViT (O(n²)) | Hybrid Phase (O(n×w) + O(n)) |
| **Latent Space** | Arbitrary embedding | 32D Sovereign State |
| **Prediction Target** | Spatial patches | Temporal state transitions |
| **Masking** | Spatial blocks | Causal (future states) |
| **Intent Integration** | None | Phase rotation from ΔS |

---

## 3. Core Components

### 3.1 Hybrid Phase Encoder

The encoder combines local and global attention for comprehensive representation:

```python
class HybridPhaseEncoder(nn.Module):
    """
    Hybrid encoder combining Local Attention and Phase Attention.

    - Local Attention: O(n×w) for syntactic patterns within window
    - Phase Attention: O(n) for semantic context across full sequence
    """

    def __init__(
        self,
        embed_dim: int = 768,
        num_heads: int = 12,
        num_layers: int = 24,
        window_size: int = 256,
        alpha_local: float = 0.7,
        alpha_phase: float = 0.3,
        cosine_mode: str = "shifted",  # standard/shifted/complex
        decay_gamma: float = 0.98,
    ):
        super().__init__()

        # Layer distribution: 50% hybrid, 50% local-only
        self.hybrid_layers = num_layers // 2
        self.local_only_layers = num_layers - self.hybrid_layers

        self.layers = nn.ModuleList()
        for i in range(num_layers):
            if i < self.local_only_layers:
                # Early layers: local-only for basic patterns
                self.layers.append(LocalAttentionLayer(embed_dim, num_heads, window_size))
            else:
                # Later layers: hybrid for semantic integration
                self.layers.append(HybridAttentionLayer(
                    embed_dim, num_heads, window_size,
                    alpha_local, alpha_phase,
                    cosine_mode, decay_gamma
                ))

    def forward(self, x, intent_phase=None):
        """
        Args:
            x: Input embeddings [B, T, D]
            intent_phase: Optional phase rotation from Sovereign State [B, T, H, Dh]

        Returns:
            h: Encoded representations [B, T, D]
        """
        h = x
        for i, layer in enumerate(self.layers):
            if isinstance(layer, HybridAttentionLayer) and intent_phase is not None:
                h = layer(h, intent_phase=intent_phase)
            else:
                h = layer(h)
        return h
```

### 3.2 State Projector

Projects hidden representations to the 32D Sovereign State:

```python
class SovereignStateProjector(nn.Module):
    """
    Projects hidden states to 32D Sovereign State.

    Structure:
    - [0:12]  Bhavas: Ontological aspects
    - [12:17] Koshas: Consciousness sheaths
    - [17:22] Vrittis: Mental modifications
    - [22:28] Gunas: Energy states
    - [28:32] Reserved: Toroidal feedback
    """

    SOVEREIGN_DIM = 32

    # Dimension ranges
    BHAVA_RANGE = (0, 12)
    KOSHA_RANGE = (12, 17)
    VRITTI_RANGE = (17, 22)
    GUNA_RANGE = (22, 28)
    RESERVED_RANGE = (28, 32)

    def __init__(self, hidden_dim: int = 768):
        super().__init__()

        # Learned projection
        self.projector = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, self.SOVEREIGN_DIM),
        )

        # Normalization constraints per component
        self.bhava_norm = nn.Softmax(dim=-1)  # Probability distribution
        self.kosha_norm = nn.Softmax(dim=-1)
        self.vritti_norm = nn.Softmax(dim=-1)
        self.guna_norm = nn.Sigmoid()  # Independent activations

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        """
        Args:
            h: Hidden states [B, T, D]

        Returns:
            S: Sovereign State [B, T, 32]
        """
        raw = self.projector(h)

        # Apply component-wise constraints
        bhava = self.bhava_norm(raw[..., :12])
        kosha = self.kosha_norm(raw[..., 12:17])
        vritti = self.vritti_norm(raw[..., 17:22])
        guna = self.guna_norm(raw[..., 22:28])
        reserved = torch.tanh(raw[..., 28:32])

        return torch.cat([bhava, kosha, vritti, guna, reserved], dim=-1)
```

### 3.3 Target Encoder (EMA)

The target encoder is an exponential moving average of the context encoder:

```python
class TargetEncoder(nn.Module):
    """
    EMA-updated copy of the context encoder.

    Prevents representation collapse by providing
    slowly-moving targets for the predictor.
    """

    def __init__(self, context_encoder: HybridPhaseEncoder, momentum: float = 0.996):
        super().__init__()
        self.encoder = copy.deepcopy(context_encoder)
        self.momentum = momentum

        # Freeze target encoder
        for param in self.encoder.parameters():
            param.requires_grad = False

    @torch.no_grad()
    def update(self, context_encoder: HybridPhaseEncoder):
        """Update target encoder weights via EMA."""
        for target_param, context_param in zip(
            self.encoder.parameters(),
            context_encoder.parameters()
        ):
            target_param.data = (
                self.momentum * target_param.data +
                (1 - self.momentum) * context_param.data
            )

    def forward(self, x):
        return self.encoder(x)
```

---

## 4. Phase-JEPA Predictor

The central innovation: a predictor that operates in phase-space to forecast state transitions.

### 4.1 Predictor Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE-JEPA PREDICTOR                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Input: S_context[t] (32D Sovereign State at position t)                    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 1: Phase-Amplitude Decomposition                               │    │
│  │  ─────────────────────────────────────                               │    │
│  │                                                                       │    │
│  │  S_context → (amplitude, phase)                                       │    │
│  │                                                                       │    │
│  │  For each dimension d:                                                │    │
│  │    a_d = ||S_d|| (magnitude)                                         │    │
│  │    φ_d = atan2(Im(z_d), Re(z_d)) (phase angle)                       │    │
│  │                                                                       │    │
│  │  Note: We lift real 32D to complex 32D for phase operations          │    │
│  │        z = a × e^{iφ} where φ derived from position + learned        │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 2: Intent-Guided Phase Rotation                                │    │
│  │  ────────────────────────────────────                                │    │
│  │                                                                       │    │
│  │  Current state S suggests intent → compute θ_intent                  │    │
│  │                                                                       │    │
│  │  θ_intent = IntentPhaseProjector(S_context)                          │    │
│  │           = tanh(W_intent @ S_context) × π                           │    │
│  │                                                                       │    │
│  │  This rotates the prediction space based on current cognitive mode   │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 3: Phasor Prediction                                           │    │
│  │  ─────────────────────────                                           │    │
│  │                                                                       │    │
│  │  Query:  Q = a_q × e^{i(φ_q + θ_intent)}                             │    │
│  │  Key:    K = a_k × e^{-iφ_k}                                         │    │
│  │                                                                       │    │
│  │  State evolution via phasor dynamics:                                │    │
│  │  ΔS_pred = PredictorMLP(Re(Q × cumsum(K × V)))                       │    │
│  │                                                                       │    │
│  │  Where V = learned value projection of S_context                     │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 4: Multi-Step Prediction                                       │    │
│  │  ────────────────────────────                                        │    │
│  │                                                                       │    │
│  │  For k-step lookahead:                                               │    │
│  │                                                                       │    │
│  │  S_pred[t+1] = S_context[t] + ΔS_pred[1]                             │    │
│  │  S_pred[t+2] = S_pred[t+1] + ΔS_pred[2]                              │    │
│  │  ...                                                                  │    │
│  │  S_pred[t+k] = S_pred[t+k-1] + ΔS_pred[k]                            │    │
│  │                                                                       │    │
│  │  Each step uses autoregressive rollout with phase state              │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Output: {ΔS_pred[1], ..., ΔS_pred[k]} (k-step state delta predictions)    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Mathematical Formulation

The Phase-JEPA Predictor computes state transitions using complex-valued operations:

**State Lifting to Complex Space:**
$$z_d = S_d \cdot e^{i \cdot \text{pos\_encoding}(d)}$$

**Intent Phase Extraction:**
$$\theta_{\text{intent}} = \tanh(W_{\text{intent}} \cdot S_{\text{context}}) \cdot \pi$$

**Phasor Query/Key Formation:**
$$Q = a_q \cdot e^{i(\phi_q + \theta_{\text{intent}})}$$
$$K = a_k \cdot e^{-i\phi_k}$$

**O(n) State Prediction:**
$$\text{State}_t = \sum_{j \leq t} K_j \cdot V_j = \text{cumsum}(K \cdot V)$$
$$\text{Raw}_t = \text{Re}(Q_t \cdot \text{State}_t)$$

**Delta Prediction:**
$$\Delta S_{\text{pred}} = \text{MLP}(\text{Raw}_t) \in \mathbb{R}^{32}$$

### 4.3 Implementation

```python
class PhaseJEPAPredictor(nn.Module):
    """
    Predicts state deltas using phase-space dynamics.

    Key Features:
    - Intent-guided phase rotation
    - O(n) complexity via cumulative sums
    - Multi-step autoregressive prediction
    """

    def __init__(
        self,
        state_dim: int = 32,
        hidden_dim: int = 256,
        num_heads: int = 4,
        prediction_steps: int = 4,
    ):
        super().__init__()

        self.state_dim = state_dim
        self.prediction_steps = prediction_steps
        self.head_dim = state_dim // num_heads
        self.num_heads = num_heads

        # Phase/amplitude projections
        self.W_q_phase = nn.Linear(state_dim, state_dim)
        self.W_q_amp = nn.Linear(state_dim, state_dim)
        self.W_k_phase = nn.Linear(state_dim, state_dim)
        self.W_k_amp = nn.Linear(state_dim, state_dim)
        self.W_v = nn.Linear(state_dim, state_dim)

        # Intent phase projector
        self.intent_projector = nn.Sequential(
            nn.Linear(state_dim, state_dim),
            nn.Tanh(),
        )

        # Delta prediction MLP
        self.delta_mlp = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, state_dim),
        )

        # Multi-step prediction heads
        self.step_embeddings = nn.Embedding(prediction_steps, state_dim)

        # Initialize phases uniformly
        nn.init.uniform_(self.W_q_phase.weight, -math.pi, math.pi)
        nn.init.uniform_(self.W_k_phase.weight, -math.pi, math.pi)

    def forward(
        self,
        s_context: torch.Tensor,
        k_steps: int = None,
    ) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        """
        Predict k-step state deltas.

        Args:
            s_context: Context state [B, T, 32]
            k_steps: Number of prediction steps (default: self.prediction_steps)

        Returns:
            s_pred: Final predicted state [B, T, 32]
            delta_list: List of predicted deltas [ΔS₁, ΔS₂, ..., ΔSₖ]
        """
        k_steps = k_steps or self.prediction_steps
        B, T, D = s_context.shape

        # Extract intent phase from current state
        theta_intent = self.intent_projector(s_context) * math.pi  # [B, T, D]

        delta_list = []
        s_current = s_context

        for step in range(k_steps):
            # Get step embedding
            step_emb = self.step_embeddings(
                torch.tensor([step], device=s_context.device)
            ).expand(B, T, -1)

            # Condition on step
            s_step = s_current + step_emb

            # Phase-amplitude projections
            phi_q = self.W_q_phase(s_step)
            a_q = torch.sigmoid(self.W_q_amp(s_step))
            phi_k = self.W_k_phase(s_step)
            a_k = torch.sigmoid(self.W_k_amp(s_step))
            v = self.W_v(s_step)

            # Apply intent rotation to query phase
            phi_q_rotated = phi_q + theta_intent

            # Form complex phasors
            q_phasor = torch.polar(a_q, phi_q_rotated)
            k_phasor = torch.polar(a_k, -phi_k)
            v_complex = torch.complex(v, torch.zeros_like(v))

            # O(n) state accumulation
            kv = k_phasor * v_complex
            state = torch.cumsum(kv, dim=1)

            # Readout
            qk_product = q_phasor * state
            normalizer = a_q * torch.cumsum(a_k, dim=1) + 1e-6
            raw_output = qk_product.real / normalizer

            # Predict delta
            delta_s = self.delta_mlp(raw_output)
            delta_list.append(delta_s)

            # Update for next step
            s_current = s_current + delta_s

        return s_current, delta_list
```

---

## 5. Training Procedure

### 5.1 Three-Phase Curriculum (Aligned with Gemini Proposals)

Following Google's training curriculum with JEPA-specific adaptations:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE-JEPA TRAINING CURRICULUM                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: DHYĀNA (Meditation) - State Foundation                            │
│  ═══════════════════════════════════════════════                            │
│  Duration: ~20% of training                                                 │
│                                                                              │
│  Goal: Establish stable state representations                               │
│                                                                              │
│  Training:                                                                   │
│  - 1-step prediction only (k=1)                                             │
│  - High weight on L_variance (prevent collapse)                             │
│  - Axiom injection for R_internal hardening                                 │
│  - Freeze predictor complexity (shallow MLP)                                │
│                                                                              │
│  Loss: L = L_jepa + 2.0·L_variance + 0.5·L_covariance                       │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 2: SAṂVĀDA (Dialogue) - Prediction Expansion                         │
│  ══════════════════════════════════════════════════                         │
│  Duration: ~50% of training                                                 │
│                                                                              │
│  Goal: Learn multi-step state transitions                                   │
│                                                                              │
│  Training:                                                                   │
│  - Expand to k=4 step prediction                                            │
│  - Enable intent phase rotation                                             │
│  - Add L_ortho for manifold preservation                                    │
│  - Unfreeze full predictor MLP                                              │
│                                                                              │
│  Loss: L = L_jepa + 1.0·L_variance + 0.5·L_covariance + 0.1·L_ortho        │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 3: KṚTI (Action) - Full Integration                                  │
│  ═════════════════════════════════════════                                  │
│  Duration: ~30% of training                                                 │
│                                                                              │
│  Goal: End-to-end reasoning with token generation                           │
│                                                                              │
│  Training:                                                                   │
│  - Enable State→Token generation head                                       │
│  - Add L_nll (next token prediction)                                        │
│  - Phase-Lock constraint active                                              │
│  - Full OPB dimension locking                                               │
│                                                                              │
│  Loss: L = 0.3·L_jepa + 0.5·L_nll + 0.1·L_variance + 0.1·L_ortho           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Training Loop

```python
class PhaseJEPATrainer:
    """Training loop for Hybrid Phase-JEPA."""

    def __init__(
        self,
        context_encoder: HybridPhaseEncoder,
        target_encoder: TargetEncoder,
        predictor: PhaseJEPAPredictor,
        state_projector: SovereignStateProjector,
        config: PhaseJEPAConfig,
    ):
        self.context_encoder = context_encoder
        self.target_encoder = target_encoder
        self.predictor = predictor
        self.state_projector = state_projector
        self.config = config

        # Only context encoder and predictor are trained
        self.optimizer = torch.optim.AdamW([
            {'params': context_encoder.parameters(), 'lr': config.encoder_lr},
            {'params': predictor.parameters(), 'lr': config.predictor_lr},
            {'params': state_projector.parameters(), 'lr': config.projector_lr},
        ], weight_decay=config.weight_decay)

    def training_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """Single training step."""

        input_ids = batch['input_ids']  # [B, T]
        B, T = input_ids.shape

        # Split into context and target
        context_len = T - self.config.prediction_steps
        context_ids = input_ids[:, :context_len]
        target_ids = input_ids[:, context_len:]

        # === Context Path ===
        # Embed
        context_emb = self.embed(context_ids)

        # Encode
        h_context = self.context_encoder(context_emb)

        # Project to state
        s_context = self.state_projector(h_context)

        # Predict future states
        s_pred, delta_list = self.predictor(s_context, k_steps=self.config.prediction_steps)

        # === Target Path ===
        with torch.no_grad():
            # Embed full sequence for target
            full_emb = self.embed(input_ids)

            # Encode with target encoder
            h_target = self.target_encoder(full_emb)

            # Project to state
            s_target = self.state_projector(h_target)

            # Extract target states (stop gradient)
            s_target_future = s_target[:, context_len:].detach()

        # === Loss Computation ===
        losses = self.compute_losses(s_pred, s_target_future, s_context, delta_list)

        # Backprop
        losses['total'].backward()
        self.optimizer.step()
        self.optimizer.zero_grad()

        # Update target encoder via EMA
        self.target_encoder.update(self.context_encoder)

        return {k: v.item() for k, v in losses.items()}
```

---

## 6. Loss Functions

### 6.1 Primary JEPA Loss

```python
def compute_jepa_loss(s_pred: torch.Tensor, s_target: torch.Tensor) -> torch.Tensor:
    """
    Mean squared error between predicted and target states.

    Note: Target is stop-gradiented to prevent collapse.
    """
    return F.mse_loss(s_pred, s_target.detach())
```

### 6.2 Variance-Covariance Regularization (VICReg-style)

Prevents representation collapse without negative samples:

```python
def compute_vicreg_losses(
    s_context: torch.Tensor,
    s_pred: torch.Tensor,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Variance and covariance regularization.

    Variance: Ensure each dimension has variance > threshold
    Covariance: Decorrelate dimensions (encourage independence)
    """
    B, T, D = s_context.shape

    # Flatten batch and time
    s_flat = s_context.reshape(-1, D)

    # === Variance Loss ===
    # Variance of each dimension across samples
    var = s_flat.var(dim=0)
    # Hinge loss: penalize if variance < threshold (1.0)
    var_loss = torch.relu(1.0 - var).mean()

    # === Covariance Loss ===
    # Centered
    s_centered = s_flat - s_flat.mean(dim=0, keepdim=True)
    # Covariance matrix
    cov = (s_centered.T @ s_centered) / (s_flat.shape[0] - 1)
    # Off-diagonal elements (should be zero for independent dims)
    off_diag = cov - torch.diag(torch.diag(cov))
    cov_loss = (off_diag ** 2).sum() / D

    return var_loss, cov_loss
```

### 6.3 Orthogonality Loss (R_internal Preservation)

From Gemini proposals—ensures information volume preservation:

```python
def compute_ortho_loss(
    predictor: PhaseJEPAPredictor,
) -> torch.Tensor:
    """
    Orthogonality constraint on predictor weights.

    Ensures the prediction transformation preserves information volume.
    """
    # Get the main transformation weight
    W = predictor.delta_mlp[0].weight  # First linear layer

    # Orthogonality: W^T W ≈ I
    ortho_loss = torch.norm(W.T @ W - torch.eye(W.shape[1], device=W.device))

    # Determinant: |det(W)| ≈ 1 (volume preservation)
    # Use SVD for numerical stability
    _, s, _ = torch.linalg.svd(W)
    det_loss = torch.abs(s.prod() - 1.0)

    return ortho_loss + 0.1 * det_loss
```

### 6.4 Complete Loss Function

```python
def compute_losses(
    self,
    s_pred: torch.Tensor,
    s_target: torch.Tensor,
    s_context: torch.Tensor,
    delta_list: List[torch.Tensor],
) -> Dict[str, torch.Tensor]:
    """Compute all loss components."""

    # JEPA prediction loss
    l_jepa = compute_jepa_loss(s_pred, s_target)

    # Regularization
    l_var, l_cov = compute_vicreg_losses(s_context, s_pred)

    # Orthogonality (during Phase 2+)
    l_ortho = compute_ortho_loss(self.predictor) if self.phase >= 2 else torch.tensor(0.0)

    # Weighted sum based on training phase
    if self.phase == 1:  # Dhyāna
        total = l_jepa + 2.0 * l_var + 0.5 * l_cov
    elif self.phase == 2:  # Saṃvāda
        total = l_jepa + 1.0 * l_var + 0.5 * l_cov + 0.1 * l_ortho
    else:  # Kṛti
        total = 0.3 * l_jepa + 0.1 * l_var + 0.1 * l_ortho

    return {
        'total': total,
        'jepa': l_jepa,
        'variance': l_var,
        'covariance': l_cov,
        'ortho': l_ortho,
    }
```

---

## 7. Integration with Sovereign Reasoning Kernel

### 7.1 SRK Components Mapping

The Phase-JEPA predictor integrates with the existing Sovereign Reasoning Kernel:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SRK + PHASE-JEPA INTEGRATION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  LAYER 4: DNA BRIDGE (Ontological Grounding)                         │    │
│  │  ───────────────────────────────────────────                         │    │
│  │  Integration Point: After early transformer layers                   │    │
│  │                                                                       │    │
│  │  Phase-JEPA: State Projector output feeds DNA Bridge                 │    │
│  │  Effect: Grounds representations in ontological structure            │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  LAYER 7: CSR ALIGNMENT (Coherence-State Routing)                    │    │
│  │  ──────────────────────────────────────────────                      │    │
│  │  Integration Point: Middle transformer layers                        │    │
│  │                                                                       │    │
│  │  Phase-JEPA: Intent phase rotation applied here                      │    │
│  │  Effect: Routes attention based on cognitive mode                    │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  LAYER 9: WITNESS LAYER (Kosha Steering)                             │    │
│  │  ───────────────────────────────────────                             │    │
│  │  Integration Point: Late transformer layers                          │    │
│  │                                                                       │    │
│  │  Phase-JEPA: Kosha dimensions [12:17] steer reasoning depth          │    │
│  │  Effect: Controls intellectual vs. material processing               │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  OPB: ONTOLOGICAL PERSISTENCE BUFFER                                 │    │
│  │  ─────────────────────────────────────                               │    │
│  │  Integration Point: Cross-sequence state carry                       │    │
│  │                                                                       │    │
│  │  Phase-JEPA: Predicted states populate OPB                           │    │
│  │  Effect: Maintains reasoning continuity across sequences             │    │
│  │                                                                       │    │
│  │  Dimension Locking:                                                   │    │
│  │  - If O7_RSN > 0.7: Lock reasoning mode across domain switch        │    │
│  │  - If VIJNANA > 0.8: Sustain intellectual depth                      │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Vritti Gate Integration

The predictor's delta outputs are validated by the Vritti Gate:

```python
class VrittiValidatedPredictor(PhaseJEPAPredictor):
    """
    Phase-JEPA Predictor with Vritti Gate validation.

    Rejects predictions that would cause Viparyaya (error) spikes.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.vritti_thresholds = {
            'VIPARYAYA': 0.4,  # Max error before rejection
            'VIKALPA': 0.6,   # Max imagination for factual tasks
        }

    def forward(self, s_context, k_steps=None, validate=True):
        s_pred, delta_list = super().forward(s_context, k_steps)

        if validate:
            # Check Vritti bounds
            vritti = s_pred[..., 17:22]  # Vritti dimensions
            viparyaya = vritti[..., 1]   # Error dimension

            # If error too high, dampen prediction
            error_mask = viparyaya > self.vritti_thresholds['VIPARYAYA']
            if error_mask.any():
                # Re-predict with dampened delta
                damping = 0.5
                delta_list = [d * damping for d in delta_list]
                s_pred = s_context + sum(delta_list)

        return s_pred, delta_list
```

---

## 8. Implementation Mapping

### 8.1 File Locations

| Component | Proposed Location |
|-----------|-------------------|
| `HybridPhaseEncoder` | `symbolu/phase_transformer.py` (extend existing) |
| `SovereignStateProjector` | `symbolu/sovereign/state_projector.py` (new) |
| `PhaseJEPAPredictor` | `symbolu/jepa/predictor.py` (new) |
| `TargetEncoder` | `symbolu/jepa/target_encoder.py` (new) |
| `PhaseJEPATrainer` | `symbolu/jepa/trainer.py` (new) |
| `VICRegLoss` | `symbolu/jepa/losses.py` (new) |
| Unit Tests | `symbolu/jepa/tests/` (new) |

### 8.2 Integration with Existing Code

```python
# In symbolu/phase_transformer.py, extend OntologicalHybridTransformer:

class PhaseJEPATransformer(OntologicalHybridTransformer):
    """
    Full Hybrid Phase-JEPA model combining:
    - OntologicalHybridTransformer base
    - PhaseJEPAPredictor for state prediction
    - TargetEncoder for JEPA training
    """

    def __init__(self, config: PhaseJEPAConfig):
        super().__init__(config)

        # JEPA components
        self.predictor = PhaseJEPAPredictor(
            state_dim=config.state_dim,
            hidden_dim=config.predictor_hidden,
            num_heads=config.predictor_heads,
            prediction_steps=config.prediction_steps,
        )

        self.target_encoder = TargetEncoder(
            self.transformer,
            momentum=config.ema_momentum,
        )

    def forward(self, input_ids, labels=None, return_jepa_loss=True):
        # Standard forward
        outputs = super().forward(input_ids, labels)

        if return_jepa_loss and self.training:
            # Compute JEPA prediction loss
            jepa_loss = self.compute_jepa_forward(input_ids)
            outputs['jepa_loss'] = jepa_loss

        return outputs
```

### 8.3 CLI Arguments

```bash
# Train Phase-JEPA model
python train_unified_llm.py \
    --model_type phase_jepa \
    --state_dim 32 \
    --prediction_steps 4 \
    --ema_momentum 0.996 \
    --jepa_weight 0.5 \
    --variance_weight 1.0 \
    --covariance_weight 0.5 \
    --training_phase 1 \
    --dataset wikitext103 \
    --batch_size 32 \
    --max_steps 100000
```

---

## 9. Complexity Analysis

### 9.1 Time Complexity

| Component | Standard Transformer | Hybrid Phase-JEPA |
|-----------|---------------------|-------------------|
| **Encoder Attention** | O(n²·d) | O(n·w·d) + O(n·d) |
| **State Projection** | N/A | O(n·d·s) where s=32 |
| **Predictor** | N/A | O(n·s²) = O(n·1024) |
| **Target Encoder** | N/A | Same as context (inference only) |
| **Total** | O(n²·d) | O(n·w·d) + O(n·d) |

Where: n = sequence length, d = hidden dim (768), w = window size (256), s = state dim (32)

### 9.2 Memory Complexity

| Context Length | Standard Attention | Phase-JEPA (States) |
|----------------|-------------------|---------------------|
| 4K | 256 MB | 512 KB |
| 32K | 16 GB | 4 MB |
| 128K | 256 GB | 16 MB |
| 1M | 16 TB | 128 MB |

**Key Insight**: State-space prediction requires only 32 floats per position vs. vocabulary-sized (50K+) predictions.

### 9.3 Parameter Count

| Component | Parameters |
|-----------|------------|
| Hybrid Phase Encoder (24L) | ~6.6B (matches existing 7B config) |
| State Projector | 768 × 32 + bias ≈ 25K |
| Phase-JEPA Predictor | 32 × 256 × 3 ≈ 24K |
| Target Encoder | Shared (no additional) |
| **Total Addition** | ~50K (0.001% overhead) |

---

## 10. Experimental Design

### 10.1 Evaluation Metrics

**State Prediction Quality:**
- MSE between predicted and actual future states
- Cosine similarity of state trajectories
- Bhava classification accuracy (argmax match)

**Downstream Tasks:**
- Perplexity on held-out text
- Cross-domain reasoning transfer (math → finance)
- State stability under adversarial input

**Comparison Baselines:**
- Standard autoregressive LLM (token prediction)
- Pure state-delta model (without JEPA)
- I-JEPA adapted for language

### 10.2 Ablation Studies

| Ablation | Purpose |
|----------|---------|
| Remove Phase Attention | Test necessity of O(n) global attention |
| Remove Intent Rotation | Test value of intent-guided prediction |
| Remove VICReg | Test collapse prevention mechanism |
| Single-step prediction | Test multi-step benefit |
| Remove OPB | Test cross-sequence persistence |

### 10.3 Hardware Requirements

| Configuration | GPU Memory | Training Time (est.) |
|---------------|------------|---------------------|
| 7B model, 4K context | 40 GB (A100) | ~7 days |
| 7B model, 32K context | 80 GB (A100) | ~14 days |
| 7B model, 128K context | 8× 80GB (H100) | ~21 days |

---

## 11. Vision-Language Extension (Phase-VL-JEPA)

This section extends the Hybrid Phase-JEPA to the **Vision-Language** domain, enabling geometric understanding through phase-conditioned masking.

### 11.1 Architecture Overview (Spec 1 & 2)

The Phase-VL-JEPA uses text descriptions to condition visual prediction via phase rotation:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE-VL-JEPA ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  VISION PATH                                                         │    │
│  │                                                                       │    │
│  │  Image ──► Patch Embed ──► Student Encoder ──► Context Latents       │    │
│  │                 │              (Hybrid Phase)        │                │    │
│  │                 │                                    │                │    │
│  │            [Geometric Mask]                          ▼                │    │
│  │                                              ┌──────────────┐         │    │
│  │                                              │   PREDICTOR  │         │    │
│  │  Image ──► Patch Embed ──► Teacher Encoder   │   (Phase +   │         │    │
│  │              (Full)         (EMA, No Grad)   │    Text θ)   │         │    │
│  │                 │                            └──────────────┘         │    │
│  │                 ▼                                    │                │    │
│  │          Target Latents ◄────────────────────────────┘                │    │
│  │                              (Loss on masked regions)                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  TEXT PATH (Phase Conditioning)                                      │    │
│  │                                                                       │    │
│  │  "Rotated 90°" ──► Text Encoder ──► Phase Projector ──► θ_intent    │    │
│  │                                          │                            │    │
│  │                        θ = tanh(W·text_emb) × π                       │    │
│  │                                          │                            │    │
│  │                                          ▼                            │    │
│  │                              Rotates Query Phases in Predictor        │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Hybrid Phase Block Implementation

The core innovation splits processing into Local (texture) and Global (geometry) streams:

```python
class HybridPhaseBlock(nn.Module):
    """
    Hybrid block splitting channels into Local and Global streams.

    - Local Stream (75%): O(W²) windowed attention for texture/detail
    - Global Stream (25%): O(N) phase attention for geometry/structure
    """

    def __init__(self, dim, num_heads=12, local_ratio=0.75, window_size=16):
        super().__init__()
        self.local_dim = int(dim * local_ratio)
        self.global_dim = dim - self.local_dim

        # Local stream: Standard windowed attention
        self.local_attn = WindowedQuadraticAttention(
            self.local_dim,
            int(num_heads * local_ratio),
            window_size=window_size
        )

        # Global stream: Phase attention with intent rotation
        self.global_attn = PhaseAttention(
            self.global_dim,
            int(num_heads * (1 - local_ratio))
        )

        self.norm1 = nn.LayerNorm(dim)
        self.norm2 = nn.LayerNorm(dim)
        self.mlp = nn.Sequential(
            nn.Linear(dim, 4 * dim),
            nn.GELU(),
            nn.Linear(4 * dim, dim)
        )

    def forward(self, x, text_phase_shift=None):
        """
        Args:
            x: Input patches [B, N, D]
            text_phase_shift: Phase rotation from text [B, D_global] or [B, 1, H, D_h]
        """
        x_norm = self.norm1(x)

        # Split into Local and Global streams
        x_local = x_norm[..., :self.local_dim]
        x_global = x_norm[..., self.local_dim:]

        # Parallel processing
        y_local = self.local_attn(x_local)
        y_global = self.global_attn(x_global, intent_phase=text_phase_shift)

        # Fuse streams
        y = torch.cat([y_local, y_global], dim=-1)
        x = x + y

        return x + self.mlp(self.norm2(x))


class WindowedQuadraticAttention(nn.Module):
    """Standard O(W²) local attention for texture refinement."""

    def __init__(self, dim, num_heads, window_size=16):
        super().__init__()
        self.dim = dim
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.scale = self.head_dim ** -0.5
        self.window_size = window_size

        self.qkv = nn.Linear(dim, dim * 3)
        self.proj = nn.Linear(dim, dim)

    def forward(self, x):
        B, N, C = x.shape

        # Standard self-attention (production: use window partitioning)
        qkv = self.qkv(x).reshape(B, N, 3, self.num_heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]

        attn = (q @ k.transpose(-2, -1)) * self.scale
        attn = attn.softmax(dim=-1)

        x = (attn @ v).transpose(1, 2).reshape(B, N, C)
        return self.proj(x)
```

---

## 12. Geometric Masking Pipeline (Spec 3)

The data pipeline forces geometric learning through strategic masking patterns.

### 12.1 GeometricMaskCollator

```python
class GeometricMaskCollator:
    """
    Creates geometric masking patterns to force spatial reasoning.

    Strategies:
    - Quadrant: Mask one quadrant, predict from others
    - Rotation: Mask center, condition on rotation angle
    - Random: Standard random patch masking
    """

    def __init__(self, input_size=224, patch_size=16, mask_ratio=0.6):
        self.grid_size = input_size // patch_size  # e.g., 14x14
        self.num_patches = self.grid_size ** 2      # e.g., 196
        self.mask_ratio = mask_ratio

    def __call__(self, batch):
        """
        Args:
            batch: List of images [C, H, W]

        Returns:
            images: Stacked images [B, C, H, W]
            masks: Boolean mask [B, N_patches] (True = masked/target)
            rotation_labels: Rotation angles for text conditioning [B]
        """
        images = torch.stack(batch)
        B = len(images)

        masks = torch.zeros((B, self.num_patches), dtype=torch.bool)
        rot_labels = []

        for i in range(B):
            strategy = random.choice(['quadrant', 'rotation', 'random'])

            if strategy == 'quadrant':
                mask = self._get_quadrant_mask()
                rot = 0.0  # "No rotation"
            elif strategy == 'rotation':
                mask = self._get_center_mask()
                rot = random.choice([0.0, 1.57, 3.14, 4.71])  # 0°, 90°, 180°, 270°
            else:
                mask = self._get_random_mask()
                rot = 0.0

            masks[i] = mask
            rot_labels.append(rot)

        return images, masks, torch.tensor(rot_labels)

    def _get_quadrant_mask(self):
        """Mask one random quadrant."""
        mask = torch.zeros((self.grid_size, self.grid_size), dtype=torch.bool)
        mid = self.grid_size // 2

        quadrant = random.randint(0, 3)
        if quadrant == 0:    # Top-Left
            mask[:mid, :mid] = True
        elif quadrant == 1:  # Top-Right
            mask[:mid, mid:] = True
        elif quadrant == 2:  # Bottom-Left
            mask[mid:, :mid] = True
        else:                # Bottom-Right
            mask[mid:, mid:] = True

        return mask.flatten()

    def _get_center_mask(self):
        """Mask center region for rotation prediction."""
        mask = torch.zeros((self.grid_size, self.grid_size), dtype=torch.bool)
        start = self.grid_size // 4
        end = 3 * self.grid_size // 4
        mask[start:end, start:end] = True
        return mask.flatten()

    def _get_random_mask(self):
        """Standard random masking."""
        mask = torch.zeros(self.num_patches, dtype=torch.bool)
        num_mask = int(self.num_patches * self.mask_ratio)
        idx = torch.randperm(self.num_patches)[:num_mask]
        mask[idx] = True
        return mask
```

### 12.2 Rotation-to-Text Mapping

```python
ROTATION_PROMPTS = {
    0.0:  "The image is upright with no rotation",
    1.57: "The image is rotated ninety degrees clockwise",
    3.14: "The image is rotated one hundred eighty degrees",
    4.71: "The image is rotated ninety degrees counter-clockwise",
}

def rotation_to_text(rotation_radians: float) -> str:
    """Convert rotation angle to natural language description."""
    return ROTATION_PROMPTS.get(rotation_radians, "The image has unknown rotation")
```

---

## 13. Phase-Sync Loss Function (Spec 4)

Custom loss combining amplitude matching and phase alignment.

### 13.1 PhaseSyncLoss

```python
class PhaseSyncLoss(nn.Module):
    """
    Combined loss for Phase-VL-JEPA training.

    Components:
    - Amplitude Loss: Standard L2 (MSE) on representation magnitudes
    - Phase Loss: Cosine distance on representation phases

    The phase loss ensures geometric relationships are preserved.
    """

    def __init__(self, lambda_phase=0.5):
        super().__init__()
        self.lambda_phase = lambda_phase

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """
        Args:
            pred: Predicted representations [B, N, D]
            target: Target representations [B, N, D]

        Returns:
            Combined loss scalar
        """
        # 1. Amplitude Loss (Standard L2)
        l2_loss = F.mse_loss(pred, target)

        # 2. Phase Alignment Loss
        # View representations as complex numbers (pair adjacent dimensions)
        pred_c = torch.view_as_complex(
            pred.float().reshape(*pred.shape[:-1], -1, 2).contiguous()
        )
        target_c = torch.view_as_complex(
            target.float().reshape(*target.shape[:-1], -1, 2).contiguous()
        )

        # Phase difference
        delta_phi = pred_c.angle() - target_c.angle()

        # Cosine distance (1 - cos(Δφ)) penalizes phase misalignment
        phase_loss = (1 - torch.cos(delta_phi)).mean()

        return l2_loss + self.lambda_phase * phase_loss
```

### 13.2 Phase Alignment Score (PAS) Metric

```python
def compute_phase_alignment_score(pred: torch.Tensor, target: torch.Tensor) -> float:
    """
    Evaluation metric for geometric understanding.

    PAS = mean(cos(φ_pred - φ_target))

    - PAS ≈ 1.0: Perfect geometric understanding
    - PAS ≈ 0.0: Random guessing (model ignores geometry)
    - PAS < 0.0: Anti-correlated (systematic errors)
    """
    # Convert to complex
    pred_c = torch.view_as_complex(
        pred.float().reshape(*pred.shape[:-1], -1, 2).contiguous()
    )
    target_c = torch.view_as_complex(
        target.float().reshape(*target.shape[:-1], -1, 2).contiguous()
    )

    # Phase alignment
    delta_phi = pred_c.angle() - target_c.angle()
    pas = torch.cos(delta_phi).mean().item()

    return pas
```

---

## 14. Complete Training System (Spec 4)

### 14.1 PhaseVLJEPA_System

```python
class PhaseVLJEPA_System(nn.Module):
    """
    Complete training system for Phase-VL-JEPA.

    Manages:
    - Student encoder (gradient updated)
    - Teacher encoder (EMA updated, no gradient)
    - Text encoder (phase conditioning)
    - Hybrid Phase Predictor
    """

    def __init__(
        self,
        vision_encoder,
        text_encoder,
        hybrid_predictor,
        loss_fn,
        ema_decay=0.996,
        lr=1e-4,
        weight_decay=0.04
    ):
        super().__init__()

        # Student Components (Gradient Updated)
        self.student_encoder = vision_encoder
        self.text_encoder = text_encoder
        self.predictor = hybrid_predictor

        # Teacher Components (EMA Updated - No Gradient)
        self.teacher_encoder = copy.deepcopy(vision_encoder)
        for p in self.teacher_encoder.parameters():
            p.requires_grad = False

        self.loss_fn = loss_fn
        self.ema_decay = ema_decay
        self.lr = lr
        self.weight_decay = weight_decay

    @torch.no_grad()
    def update_teacher_ema(self):
        """Standard JEPA EMA update."""
        for s_param, t_param in zip(
            self.student_encoder.parameters(),
            self.teacher_encoder.parameters()
        ):
            t_param.data.mul_(self.ema_decay).add_(
                s_param.data, alpha=(1 - self.ema_decay)
            )

    def forward_teacher(self, images):
        """Get ground truth latents from teacher (no gradient)."""
        with torch.no_grad():
            return self.teacher_encoder(images)

    def training_step(self, batch):
        """
        Single training step.

        Args:
            batch: (images, masks, rotation_labels) from GeometricMaskCollator
        """
        images, masks, rotation_labels = batch

        # 1. Teacher targets (full image)
        target_latents = self.forward_teacher(images)

        # 2. Student context (masked image)
        context_latents = self.student_encoder(images, mask=masks)

        # 3. Text phase conditioning
        text_tokens = self.rotation_to_tokens(rotation_labels)
        text_embedding = self.text_encoder(text_tokens)
        phase_shift = torch.tanh(
            self.text_encoder.phase_proj(text_embedding)
        ) * math.pi

        # 4. Predict masked regions
        # Create learnable mask tokens for prediction targets
        B, N_total, D = target_latents.shape
        N_mask = masks.sum(dim=1).max().item()
        mask_tokens = self.predictor.mask_token.expand(B, N_mask, -1)

        predicted_latents = self.predictor(
            context_latents,
            mask_tokens,
            text_phase_shift=phase_shift
        )

        # 5. Loss (only on masked regions)
        loss = self.loss_fn(
            predicted_latents[:, -N_mask:],  # Predictions for mask tokens
            target_latents[masks.unsqueeze(-1).expand_as(target_latents)].view(B, N_mask, D)
        )

        # 6. EMA update
        self.update_teacher_ema()

        return loss

    def rotation_to_tokens(self, rotation_labels):
        """Convert rotation labels to text tokens."""
        texts = [ROTATION_PROMPTS.get(r.item(), "") for r in rotation_labels]
        # In production: use tokenizer
        return texts

    def configure_optimizers(self):
        """JEPA requires high weight decay to prevent collapse."""
        return torch.optim.AdamW(
            [p for p in self.parameters() if p.requires_grad],
            lr=self.lr,
            weight_decay=self.weight_decay,
            betas=(0.9, 0.95)
        )
```

### 14.2 Hyperparameter Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Batch Size** | 256-512 | JEPAs need large batches for variance |
| **Learning Rate** | 1e-4 | Lower than standard ViT to stabilize phase gradients |
| **Weight Decay** | 0.04-0.1 | High - prevents collapse to zero-phase solution |
| **EMA Decay** | 0.996 → 1.0 | Ramps up during training |
| **Gradient Clipping** | 1.0 | Essential - phase shifts can cause gradient spikes |
| **Warmup** | 20 epochs | Phase logic needs time to align |
| **Local Ratio** | 0.75 | 75% channels for local, 25% for global phase |
| **Window Size** | 16 | Local attention window |

### 14.3 Evaluation Protocol

```python
def evaluate_phase_vl_jepa(model, val_loader):
    """
    Evaluation metrics for Phase-VL-JEPA.

    1. Phase Alignment Score (PAS) - geometric understanding
    2. Linear Probe Accuracy - representation quality
    3. Reconstruction MSE - prediction accuracy
    """
    model.eval()
    pas_scores = []
    mse_scores = []

    with torch.no_grad():
        for images, masks, rot_labels in val_loader:
            # Get predictions and targets
            target = model.forward_teacher(images)
            context = model.student_encoder(images, mask=masks)

            text_emb = model.text_encoder(model.rotation_to_tokens(rot_labels))
            phase = torch.tanh(model.text_encoder.phase_proj(text_emb)) * math.pi

            pred = model.predictor(context, model.predictor.mask_token.expand(...), phase)

            # Metrics
            pas = compute_phase_alignment_score(pred, target[masks])
            mse = F.mse_loss(pred, target[masks]).item()

            pas_scores.append(pas)
            mse_scores.append(mse)

    return {
        'phase_alignment_score': np.mean(pas_scores),
        'reconstruction_mse': np.mean(mse_scores),
    }
```

---

## 15. Implementation Files Summary

The complete Phase-VL-JEPA implementation consists of:

| File | Purpose | Key Classes |
|------|---------|-------------|
| `hybrid_phase_block.py` | Core attention mechanisms | `HybridPhaseBlock`, `WindowedQuadraticAttention`, `PhaseAttention` |
| `phase_jepa_model.py` | Predictor architecture | `PhaseVLJEPA`, `PhaseSyncLoss` |
| `data_pipeline.py` | Geometric masking | `GeometricMaskCollator` |
| `training_system.py` | Training orchestration | `PhaseVLJEPA_System` |

### File Locations (Proposed)

```
symbolu/
├── jepa/
│   ├── __init__.py
│   ├── hybrid_phase_block.py      # Spec 1 & 2
│   ├── phase_jepa_model.py        # Spec 1 & 2
│   ├── data_pipeline.py           # Spec 3
│   ├── training_system.py         # Spec 4
│   ├── losses.py                  # PhaseSyncLoss, VICReg
│   ├── metrics.py                 # PAS, linear probe
│   └── tests/
│       ├── test_hybrid_block.py
│       ├── test_predictor.py
│       └── test_data_pipeline.py
```

---

## 16. Quick Start Validation

### 16.1 Smoke Test

```python
# Verify dimensions with small model
from symbolu.jepa import PhaseVLJEPA_System, GeometricMaskCollator

# Create dummy components
vision_encoder = ViTSmall(patch_size=16, embed_dim=384)
text_encoder = TextEncoder(embed_dim=384)
predictor = PhaseVLJEPA(depth=4, embed_dim=384, phase_dim=96)
loss_fn = PhaseSyncLoss(lambda_phase=0.5)

system = PhaseVLJEPA_System(vision_encoder, text_encoder, predictor, loss_fn)

# Random data
images = torch.randn(4, 3, 224, 224)
collator = GeometricMaskCollator()
batch = collator([images[i] for i in range(4)])

# Forward pass
loss = system.training_step(batch)
print(f"Loss: {loss.item():.4f}")
```

### 16.2 Success Criteria

| Milestone | Metric | Target |
|-----------|--------|--------|
| **10 epochs** | PAS | > 0.6 |
| **50 epochs** | Linear probe accuracy | > 50% (ImageNet) |
| **100 epochs** | PAS | > 0.85 |

---

## 17. Geometric Masking Training Loop (Complete)

This section provides the **production-ready training loop** that utilizes geometric masking to train the Phase-Rotated Predictor.

### 17.1 Training Philosophy

The training loop implements the core insight from Stage 3 (Logical Bridge):

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE-ROTATED PREDICTION TRAINING                                     │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  GOAL: Train the model to "spin" context patches into target orientation                │
│                                                                                          │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                                                                    │  │
│  │   INPUT IMAGE                    MASKED IMAGE               PREDICTED TARGET       │  │
│  │   ┌─────┬─────┐                 ┌─────┬─────┐              ┌─────┬─────┐          │  │
│  │   │  A  │  B  │                 │  A  │  B  │              │  A  │  B  │          │  │
│  │   ├─────┼─────┤  ──Mask──►     ├─────┼─────┤  ──Phase──► ├─────┼─────┤          │  │
│  │   │  C  │  D  │                 │  C  │ ??? │     Rotate   │  C  │  D' │          │  │
│  │   └─────┴─────┘                 └─────┴─────┘              └─────┴─────┘          │  │
│  │                                                                                    │  │
│  │   Teacher sees FULL             Student sees               Predictor uses         │  │
│  │   image (A,B,C,D)               CONTEXT (A,B,C)            TEXT θ to rotate       │  │
│  │                                                             context → target (D')  │  │
│  │                                                                                    │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│  KEY MECHANISM:                                                                          │
│  • Text "The image is rotated 90°" → θ_geometric = π/2                                  │
│  • Phase rotation: Q' = Q × e^{iθ}                                                      │
│  • Rotated queries attend to keys as if spatially transformed                           │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 17.2 Complete Training Loop Implementation

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
import math
import copy
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class GeometricMaskingTrainer:
    """
    Complete training loop for Phase-VL-JEPA with Geometric Masking.

    This trainer implements the Phase-Rotated Prediction paradigm:
    - Student encoder sees masked images
    - Text provides geometric transformation hint
    - Predictor uses Phase Rotation to "spin" context into target
    - Teacher provides ground truth (EMA updated)
    """

    def __init__(
        self,
        model: 'PhaseVLJEPA_System',
        train_loader: DataLoader,
        val_loader: DataLoader,
        config: 'TrainingConfig',
    ):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.config = config

        # Optimizer with high weight decay (JEPA requirement)
        self.optimizer = torch.optim.AdamW(
            [p for p in model.parameters() if p.requires_grad],
            lr=config.lr,
            weight_decay=config.weight_decay,
            betas=(0.9, 0.95)
        )

        # Learning rate scheduler with warmup
        self.scheduler = self._create_scheduler()

        # EMA decay schedule (ramps from 0.996 to 1.0)
        self.ema_schedule = self._create_ema_schedule()

        # Metrics tracking
        self.metrics = {
            'train_loss': [],
            'val_loss': [],
            'phase_alignment_score': [],
            'reconstruction_mse': [],
        }

        self.global_step = 0
        self.epoch = 0

    def _create_scheduler(self):
        """Cosine decay with linear warmup."""
        def lr_lambda(step):
            if step < self.config.warmup_steps:
                return step / self.config.warmup_steps
            progress = (step - self.config.warmup_steps) / (
                self.config.total_steps - self.config.warmup_steps
            )
            return 0.5 * (1 + math.cos(math.pi * progress))

        return torch.optim.lr_scheduler.LambdaLR(self.optimizer, lr_lambda)

    def _create_ema_schedule(self):
        """EMA decay ramps from initial to 1.0."""
        def ema_lambda(step):
            progress = step / self.config.total_steps
            return self.config.ema_decay_init + (1.0 - self.config.ema_decay_init) * progress
        return ema_lambda

    def training_step(self, batch: Tuple) -> Dict[str, torch.Tensor]:
        """
        Single training step with geometric masking.

        Args:
            batch: (images, masks, rotation_labels) from GeometricMaskCollator

        Returns:
            Dictionary of losses
        """
        images, masks, rotation_labels = batch
        images = images.to(self.config.device)
        masks = masks.to(self.config.device)
        rotation_labels = rotation_labels.to(self.config.device)

        B, C, H, W = images.shape

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: TEACHER FORWARD (Ground Truth)
        # ═══════════════════════════════════════════════════════════════════
        # Teacher sees FULL image - this is our target representation
        with torch.no_grad():
            target_latents = self.model.teacher_encoder(images)
            # target_latents: [B, N_patches, D]

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: STUDENT FORWARD (Masked Context)
        # ═══════════════════════════════════════════════════════════════════
        # Student only sees unmasked patches
        context_latents = self.model.student_encoder(images, mask=~masks)
        # context_latents: [B, N_context, D]

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: TEXT → PHASE ROTATION (The Geometric Bridge)
        # ═══════════════════════════════════════════════════════════════════
        # Convert rotation labels to text prompts
        text_prompts = self._rotation_to_text(rotation_labels)

        # Encode text
        text_tokens = self.model.tokenizer(
            text_prompts,
            return_tensors='pt',
            padding=True
        ).to(self.config.device)

        text_embedding = self.model.text_encoder(**text_tokens).last_hidden_state[:, 0]
        # text_embedding: [B, D_text]

        # Project to Phase Angle θ ∈ [-π, π]
        # THIS IS THE CRITICAL MECHANISM TRANSFER:
        # Same math as IntentPhaseProjector, different source
        theta_geometric = torch.tanh(
            self.model.text_phase_projector(text_embedding)
        ) * math.pi
        # theta_geometric: [B, D_phase]

        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: PHASE-ROTATED PREDICTION
        # ═══════════════════════════════════════════════════════════════════
        # Create learnable mask tokens for positions we need to predict
        N_mask = masks.sum(dim=1).max().item()
        mask_tokens = self.model.predictor.mask_token.expand(B, N_mask, -1)

        # Get mask positions for positional encoding
        mask_positions = self._get_mask_positions(masks)

        # Predictor uses Phase Rotation to "spin" context into target
        predicted_latents = self.model.predictor(
            context_latents=context_latents,
            mask_tokens=mask_tokens,
            mask_positions=mask_positions,
            text_phase_shift=theta_geometric,  # THE PHASE ROTATION
        )
        # predicted_latents: [B, N_mask, D]

        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: LOSS COMPUTATION
        # ═══════════════════════════════════════════════════════════════════
        # Extract target representations for masked positions
        target_masked = self._extract_masked_targets(target_latents, masks)
        # target_masked: [B, N_mask, D]

        # PhaseSyncLoss: Amplitude (L2) + Phase Alignment (Cosine)
        loss_dict = self.model.loss_fn(predicted_latents, target_masked.detach())

        # ═══════════════════════════════════════════════════════════════════
        # STEP 6: BACKPROP & OPTIMIZATION
        # ═══════════════════════════════════════════════════════════════════
        total_loss = loss_dict['total']

        self.optimizer.zero_grad()
        total_loss.backward()

        # Gradient clipping (essential for phase stability)
        torch.nn.utils.clip_grad_norm_(
            self.model.parameters(),
            self.config.grad_clip
        )

        self.optimizer.step()
        self.scheduler.step()

        # ═══════════════════════════════════════════════════════════════════
        # STEP 7: EMA UPDATE (Teacher follows Student slowly)
        # ═══════════════════════════════════════════════════════════════════
        ema_decay = self.ema_schedule(self.global_step)
        self._update_teacher_ema(ema_decay)

        self.global_step += 1

        return {k: v.item() for k, v in loss_dict.items()}

    def _rotation_to_text(self, rotation_labels: torch.Tensor) -> list:
        """Convert rotation angles to natural language descriptions."""
        PROMPTS = {
            0.0: "The image is upright with no rotation",
            1.57: "The image is rotated ninety degrees clockwise",
            3.14: "The image is rotated one hundred eighty degrees",
            4.71: "The image is rotated ninety degrees counter-clockwise",
        }

        texts = []
        for r in rotation_labels:
            r_val = r.item()
            # Find closest rotation
            closest = min(PROMPTS.keys(), key=lambda x: abs(x - r_val))
            texts.append(PROMPTS[closest])

        return texts

    def _get_mask_positions(self, masks: torch.Tensor) -> torch.Tensor:
        """Extract 2D positions of masked patches."""
        B = masks.shape[0]
        grid_size = int(math.sqrt(masks.shape[1]))

        positions = []
        for b in range(B):
            mask_indices = masks[b].nonzero(as_tuple=False).squeeze(-1)
            # Convert flat indices to 2D positions
            row = mask_indices // grid_size
            col = mask_indices % grid_size
            pos = torch.stack([row, col], dim=-1).float()
            positions.append(pos)

        return torch.nn.utils.rnn.pad_sequence(positions, batch_first=True)

    def _extract_masked_targets(
        self,
        target_latents: torch.Tensor,
        masks: torch.Tensor
    ) -> torch.Tensor:
        """Extract target representations at masked positions."""
        B, N, D = target_latents.shape
        N_mask = masks.sum(dim=1).max().item()

        extracted = torch.zeros(B, N_mask, D, device=target_latents.device)

        for b in range(B):
            mask_indices = masks[b].nonzero(as_tuple=False).squeeze(-1)
            extracted[b, :len(mask_indices)] = target_latents[b, mask_indices]

        return extracted

    @torch.no_grad()
    def _update_teacher_ema(self, decay: float):
        """Update teacher encoder with EMA of student encoder."""
        for s_param, t_param in zip(
            self.model.student_encoder.parameters(),
            self.model.teacher_encoder.parameters()
        ):
            t_param.data.mul_(decay).add_(s_param.data, alpha=(1 - decay))

    def train_epoch(self) -> Dict[str, float]:
        """Train for one epoch."""
        self.model.train()
        epoch_losses = []

        for batch_idx, batch in enumerate(self.train_loader):
            losses = self.training_step(batch)
            epoch_losses.append(losses)

            # Logging
            if batch_idx % self.config.log_interval == 0:
                logger.info(
                    f"Epoch {self.epoch} | Step {batch_idx}/{len(self.train_loader)} | "
                    f"Loss: {losses['total']:.4f} | "
                    f"L2: {losses.get('l2', 0):.4f} | "
                    f"Phase: {losses.get('phase', 0):.4f}"
                )

        # Aggregate epoch metrics
        avg_losses = {
            k: sum(d[k] for d in epoch_losses) / len(epoch_losses)
            for k in epoch_losses[0].keys()
        }

        self.metrics['train_loss'].append(avg_losses['total'])
        self.epoch += 1

        return avg_losses

    @torch.no_grad()
    def evaluate(self) -> Dict[str, float]:
        """Evaluate on validation set."""
        self.model.eval()

        pas_scores = []
        mse_scores = []

        for batch in self.val_loader:
            images, masks, rotation_labels = batch
            images = images.to(self.config.device)
            masks = masks.to(self.config.device)
            rotation_labels = rotation_labels.to(self.config.device)

            # Teacher targets
            target_latents = self.model.teacher_encoder(images)

            # Student context
            context_latents = self.model.student_encoder(images, mask=~masks)

            # Text phase
            text_prompts = self._rotation_to_text(rotation_labels)
            text_tokens = self.model.tokenizer(
                text_prompts, return_tensors='pt', padding=True
            ).to(self.config.device)
            text_emb = self.model.text_encoder(**text_tokens).last_hidden_state[:, 0]
            theta = torch.tanh(self.model.text_phase_projector(text_emb)) * math.pi

            # Predict
            N_mask = masks.sum(dim=1).max().item()
            mask_tokens = self.model.predictor.mask_token.expand(images.shape[0], N_mask, -1)
            mask_positions = self._get_mask_positions(masks)

            predicted = self.model.predictor(
                context_latents, mask_tokens, mask_positions, theta
            )

            # Extract targets
            target_masked = self._extract_masked_targets(target_latents, masks)

            # Metrics
            pas = self._compute_phase_alignment_score(predicted, target_masked)
            mse = F.mse_loss(predicted, target_masked).item()

            pas_scores.append(pas)
            mse_scores.append(mse)

        avg_pas = sum(pas_scores) / len(pas_scores)
        avg_mse = sum(mse_scores) / len(mse_scores)

        self.metrics['phase_alignment_score'].append(avg_pas)
        self.metrics['reconstruction_mse'].append(avg_mse)

        logger.info(f"Validation | PAS: {avg_pas:.4f} | MSE: {avg_mse:.4f}")

        return {'phase_alignment_score': avg_pas, 'reconstruction_mse': avg_mse}

    def _compute_phase_alignment_score(
        self,
        pred: torch.Tensor,
        target: torch.Tensor
    ) -> float:
        """
        Compute Phase Alignment Score (PAS).

        PAS = mean(cos(φ_pred - φ_target))

        Range: [-1, 1]
        - 1.0: Perfect phase alignment
        - 0.0: Random (no geometric understanding)
        - <0: Anti-correlated
        """
        # View as complex numbers
        pred_c = torch.view_as_complex(
            pred.float().reshape(*pred.shape[:-1], -1, 2).contiguous()
        )
        target_c = torch.view_as_complex(
            target.float().reshape(*target.shape[:-1], -1, 2).contiguous()
        )

        # Phase difference
        delta_phi = pred_c.angle() - target_c.angle()

        # Cosine of phase difference
        pas = torch.cos(delta_phi).mean().item()

        return pas

    def train(self, num_epochs: int):
        """Full training loop."""
        logger.info(f"Starting training for {num_epochs} epochs")
        logger.info(f"Total steps: {self.config.total_steps}")
        logger.info(f"Warmup steps: {self.config.warmup_steps}")

        best_pas = 0.0

        for epoch in range(num_epochs):
            # Train
            train_losses = self.train_epoch()

            # Evaluate
            val_metrics = self.evaluate()

            # Checkpointing
            if val_metrics['phase_alignment_score'] > best_pas:
                best_pas = val_metrics['phase_alignment_score']
                self._save_checkpoint('best_model.pt')
                logger.info(f"New best PAS: {best_pas:.4f}")

            # Periodic checkpoint
            if (epoch + 1) % self.config.save_interval == 0:
                self._save_checkpoint(f'checkpoint_epoch_{epoch+1}.pt')

            logger.info(
                f"Epoch {epoch+1}/{num_epochs} | "
                f"Train Loss: {train_losses['total']:.4f} | "
                f"Val PAS: {val_metrics['phase_alignment_score']:.4f} | "
                f"Val MSE: {val_metrics['reconstruction_mse']:.4f}"
            )

    def _save_checkpoint(self, filename: str):
        """Save model checkpoint."""
        torch.save({
            'epoch': self.epoch,
            'global_step': self.global_step,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'metrics': self.metrics,
        }, self.config.checkpoint_dir / filename)


@dataclass
class TrainingConfig:
    """Configuration for geometric masking training."""

    # Optimization
    lr: float = 1e-4
    weight_decay: float = 0.04
    grad_clip: float = 1.0

    # Scheduling
    warmup_steps: int = 5000
    total_steps: int = 100000

    # EMA
    ema_decay_init: float = 0.996

    # Logging
    log_interval: int = 100
    save_interval: int = 10  # epochs

    # Hardware
    device: str = 'cuda'
    checkpoint_dir: Path = Path('./checkpoints')
```

### 17.3 Training Script Entry Point

```python
#!/usr/bin/env python3
"""
train_phase_vl_jepa.py - Train Hybrid Phase-VL-JEPA with Geometric Masking

Usage:
    python train_phase_vl_jepa.py \
        --dataset imagenet \
        --batch_size 256 \
        --epochs 100 \
        --lr 1e-4 \
        --weight_decay 0.04
"""

import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Train Phase-VL-JEPA')
    parser.add_argument('--dataset', type=str, default='cifar100')
    parser.add_argument('--batch_size', type=int, default=256)
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--lr', type=float, default=1e-4)
    parser.add_argument('--weight_decay', type=float, default=0.04)
    parser.add_argument('--embed_dim', type=int, default=384)
    parser.add_argument('--local_ratio', type=float, default=0.75)
    args = parser.parse_args()

    # 1. Create model components
    vision_encoder = create_vision_encoder(args.embed_dim)
    text_encoder = create_text_encoder()
    predictor = PhaseVLJEPA(
        depth=6,
        embed_dim=args.embed_dim,
        phase_dim=int(args.embed_dim * (1 - args.local_ratio))
    )
    loss_fn = PhaseSyncLoss(lambda_phase=0.5)

    # 2. Create system
    model = PhaseVLJEPA_System(
        vision_encoder=vision_encoder,
        text_encoder=text_encoder,
        hybrid_predictor=predictor,
        loss_fn=loss_fn,
    )

    # 3. Create data loaders with geometric masking
    collator = GeometricMaskCollator(
        input_size=224,
        patch_size=16,
        mask_ratio=0.6
    )

    train_loader, val_loader = create_dataloaders(
        args.dataset,
        args.batch_size,
        collator
    )

    # 4. Create config
    config = TrainingConfig(
        lr=args.lr,
        weight_decay=args.weight_decay,
        total_steps=len(train_loader) * args.epochs,
        warmup_steps=len(train_loader) * 20,  # 20 epoch warmup
    )

    # 5. Train
    trainer = GeometricMaskingTrainer(model, train_loader, val_loader, config)
    trainer.train(args.epochs)

    print("Training complete!")
    print(f"Best PAS: {max(trainer.metrics['phase_alignment_score']):.4f}")


if __name__ == '__main__':
    main()
```

### 17.4 Training Progression Visualization

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    EXPECTED TRAINING PROGRESSION                                         │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  PHASE 1: WARMUP (Epochs 1-20)                                                          │
│  ════════════════════════════                                                           │
│  • Phase logic aligns, loss decreases rapidly                                           │
│  • PAS: 0.0 → 0.3                                                                       │
│  • Model learns basic patch-to-patch relationships                                      │
│                                                                                          │
│  PHASE 2: GEOMETRIC LEARNING (Epochs 20-60)                                             │
│  ═══════════════════════════════════════════                                            │
│  • Text-to-phase mapping solidifies                                                     │
│  • PAS: 0.3 → 0.6 (SUCCESS THRESHOLD)                                                   │
│  • Model starts using text to guide spatial predictions                                 │
│                                                                                          │
│  PHASE 3: REFINEMENT (Epochs 60-100)                                                    │
│  ═══════════════════════════════════                                                    │
│  • Fine-grained geometric understanding                                                 │
│  • PAS: 0.6 → 0.85+                                                                     │
│  • Model achieves robust phase rotation for arbitrary angles                            │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                                   │   │
│  │  PAS │                                                            ●●●●●          │   │
│  │      │                                              ●●●●●●●●●●●                   │   │
│  │  0.8 │                                    ●●●●●●●●                                │   │
│  │      │                          ●●●●●●●●                                          │   │
│  │  0.6 │- - - - - - - - - -●●●●●- - - - - - - - - - - - - SUCCESS THRESHOLD        │   │
│  │      │               ●●●●                                                         │   │
│  │  0.4 │          ●●●●                                                              │   │
│  │      │       ●●●                                                                  │   │
│  │  0.2 │    ●●                                                                      │   │
│  │      │  ●                                                                         │   │
│  │  0.0 │●─────────────────────────────────────────────────────────────────────►    │   │
│  │      0        20        40        60        80       100    Epochs                │   │
│  │                                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 18. Patent-Enhanced Loss Functions (SovereignPatentLoss)

This section integrates the mathematical rigor from the SymbolU patents (BCVF, USE, SCC) into the Phase-VL-JEPA loss function, elevating the model from "functioning" to **"mathematically optimized."**

### 18.1 Patent Integration Strategy

| Patent | Formula | Application in Phase-VL-JEPA |
|--------|---------|------------------------------|
| **BCVF** | **B1 (Lagrangian)** | **"Truth" Loss:** Penalizes predictions that diverge from Text Phase Intent (s_b) or lack Visual Confidence (s_f) |
| **USE** | **U2 (Total Coherence)** | **Global Synchronization:** Forces ALL patches to synchronize phases, acting as "gravity" holding image structure together |
| **SCC** | **S5, S8 (Entropy)** | **Stability Constraint:** Monitors Phase Entropy—penalizes chaotic phases to prevent latent-space hallucinations |

### 18.2 Mathematical Specification

#### A. BCVF Integration (The Lagrangian Loss)

Redefining scores for the JEPA context:

**Forward Score (s_f)**: The **Confidence** of the prediction, measured by amplitude:
$$s_f = \sigma(\text{mean}(|z_{\text{pred}}|))$$

**Backward Score (s_b)**: The **Goal Alignment**, measured by phase alignment with text intent:
$$s_b = \frac{1 + \cos(\phi_{\text{pred}} - \phi_{\text{target}})}{2}$$

**Formula B1 (Consistency Lagrangian)**:
$$\mathcal{L}_{\text{BCVF}} = \lambda_f (1 - s_f)^2 + \lambda_b (1 - s_b)^2 + \lambda_c (s_f - s_b)^2$$

The three terms ensure:
- High confidence (λ_f term)
- Strong alignment (λ_b term)
- Confidence-alignment balance (λ_c term)

#### B. USE Integration (The Coherence Objective)

**Formula U2 (Total Coherence)** across all latent patches:
$$\mathcal{L}_{\text{USE}} = -\sum_{i,j} \cos(\phi_i - \phi_j) = -\text{Tr}(C)$$

Where C is the **Correlation Matrix** from Formula U1:
$$C_{ij} = \text{Re}(\hat{z}_i \cdot \hat{z}_j^*)$$

Where $\hat{z} = z / |z|$ (normalized phasors).

Minimizing negative sum maximizes global phase coherence.

#### C. SCC Integration (The Entropy Constraint)

**Formula S5 (Semantic Entropy)**:
$$H_{\text{sem}} = -\sum_k p_k \log p_k$$

Where $p_k = \text{softmax}(\phi)_k$ is the phase distribution.

- **High entropy** = Random phase noise (hallucination risk)
- **Low entropy** = Ordered geometric structure
- **Target**: "Goldilocks zone" of meaningful representation

**Formula S3 (Combined Loss)**:
$$\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{task}} + \lambda_{\text{BCVF}} \cdot \mathcal{L}_{\text{BCVF}} + \lambda_{\text{USE}} \cdot \mathcal{L}_{\text{USE}} + \lambda_{\text{SCC}} \cdot H_{\text{sem}}$$

### 18.3 SovereignPatentLoss Implementation

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class SovereignPatentLoss(nn.Module):
    """
    Patent-enhanced loss implementing BCVF (B1), USE (U2), and SCC (S5) formulas.

    Elevates Phase-VL-JEPA from "functioning" to "mathematically optimized":
    - BCVF: Prevents "lazily confident" or "weakly accurate" predictions
    - USE: Acts as "structural glue" for global phase coherence
    - SCC: Fights collapse (zero entropy) and hallucination (max entropy)
    """

    def __init__(
        self,
        lambda_bcvf: float = 1.0,
        lambda_use: float = 0.5,
        lambda_scc: float = 0.1,
        lambda_f: float = 1.0,  # BCVF: confidence weight
        lambda_b: float = 1.0,  # BCVF: alignment weight
        lambda_c: float = 0.5,  # BCVF: balance weight
    ):
        super().__init__()
        self.lambda_bcvf = lambda_bcvf
        self.lambda_use = lambda_use
        self.lambda_scc = lambda_scc
        self.lambda_f = lambda_f
        self.lambda_b = lambda_b
        self.lambda_c = lambda_c

    def forward(
        self,
        pred_z: torch.Tensor,
        target_z: torch.Tensor,
        text_phase_shift: torch.Tensor,
    ) -> tuple:
        """
        Compute patent-enhanced loss.

        Args:
            pred_z: Student prediction [B, N, D]
            target_z: Teacher target [B, N, D]
            text_phase_shift: Text-derived rotation command [B, D_phase]

        Returns:
            total_loss: Scalar loss
            diagnostics: Dictionary of component losses and metrics
        """
        # ═══════════════════════════════════════════════════════════════════
        # STEP 0: Complex Projection
        # ═══════════════════════════════════════════════════════════════════
        pred_c = torch.view_as_complex(
            pred_z.float().reshape(*pred_z.shape[:-1], -1, 2).contiguous()
        )
        target_c = torch.view_as_complex(
            target_z.float().reshape(*target_z.shape[:-1], -1, 2).contiguous()
        )

        pred_amp = pred_c.abs()
        pred_phase = pred_c.angle()
        target_phase = target_c.angle()

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: BCVF - Consistency Lagrangian (Formula B1)
        # ═══════════════════════════════════════════════════════════════════
        # Forward Score (s_f): Normalized Amplitude → Confidence
        # High amplitude = high confidence feature
        s_f = torch.sigmoid(pred_amp.mean(dim=-1))

        # Backward Score (s_b): Phase Alignment → Goal Alignment
        # Does predicted phase match target (which embodies text intent)?
        phase_alignment = torch.cos(pred_phase - target_phase).mean(dim=-1)
        s_b = (1.0 + phase_alignment) / 2.0  # Normalize to [0, 1]

        # Formula B1: Consistency Lagrangian
        term_f = self.lambda_f * (1 - s_f) ** 2  # Penalize low confidence
        term_b = self.lambda_b * (1 - s_b) ** 2  # Penalize poor alignment
        term_c = self.lambda_c * (s_f - s_b) ** 2  # Penalize imbalance
        L_bcvf = (term_f + term_b + term_c).mean()

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: USE - Universal Synchronization (Formula U2)
        # ═══════════════════════════════════════════════════════════════════
        # Maximize pairwise cosine similarity of phases
        # This forces "Global Structure" to be coherent

        # Normalize to unit magnitude (phasors)
        phasors = pred_c / (pred_amp + 1e-6)

        # Correlation Matrix C[i,j] (Formula U1)
        # Computed over patch dimension N
        C = torch.matmul(phasors, phasors.conj().transpose(-2, -1)).real

        # Formula U2: Sum of correlations (minimize negative to maximize)
        L_use = -1.0 * C.mean()

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: SCC - Semantic Entropy (Formula S5)
        # ═══════════════════════════════════════════════════════════════════
        # H_sem = -Sum(p * log(p))
        # High entropy = chaotic phases (hallucination)
        # Low entropy = ordered structure

        # Softmax over phase angles for pseudo-probability
        probs = F.softmax(pred_phase, dim=-1)
        log_probs = F.log_softmax(pred_phase, dim=-1)
        H_sem = -(probs * log_probs).sum(dim=-1).mean()
        L_scc = H_sem

        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: Task Loss (Standard JEPA L2)
        # ═══════════════════════════════════════════════════════════════════
        L_task = F.mse_loss(pred_z, target_z)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: Total Sovereign Loss (Formula S3)
        # ═══════════════════════════════════════════════════════════════════
        L_total = (
            L_task
            + self.lambda_bcvf * L_bcvf
            + self.lambda_use * L_use
            + self.lambda_scc * L_scc
        )

        diagnostics = {
            'total': L_total.item(),
            'task': L_task.item(),
            'bcvf': L_bcvf.item(),
            'use': L_use.item(),
            'scc': L_scc.item(),
            's_f': s_f.mean().item(),  # Confidence score
            's_b': s_b.mean().item(),  # Alignment score
            'entropy': H_sem.item(),   # Phase entropy
        }

        return L_total, diagnostics
```

### 18.4 Training Integration

Update `GeometricMaskingTrainer.training_step()` to use the patent-enhanced loss:

```python
# In training_step():

# ... (previous code: encode context, compute text phase)

# Predict masked regions
predicted_latents = self.model.predictor(
    context_latents,
    mask_tokens,
    mask_positions,
    text_phase_shift=theta_geometric,
)

# Extract targets
target_masked = self._extract_masked_targets(target_latents, masks)

# ═══════════════════════════════════════════════════════════════════════
# PATENT-ENHANCED LOSS CALL
# ═══════════════════════════════════════════════════════════════════════
loss, diagnostics = self.model.loss_fn(
    predicted_latents,
    target_masked.detach(),
    theta_geometric,  # Pass text phase for BCVF alignment check
)

# Log diagnostics for monitoring
self.log_metrics(diagnostics)

return loss
```

### 18.5 Why Patent Integration is Superior

| Issue | Simple PhaseSyncLoss | SovereignPatentLoss |
|-------|---------------------|---------------------|
| **"Lazily Confident"** | Not detected | BCVF λ_c term catches s_f >> s_b |
| **"Weakly Accurate"** | Not detected | BCVF λ_f term catches low amplitude |
| **Global Incoherence** | Only local phase loss | USE U2 enforces global phase sync |
| **Hallucination** | Unconstrained entropy | SCC S5 keeps entropy in "Goldilocks zone" |
| **Collapse** | VICReg only | SCC also monitors for zero-entropy collapse |

### 18.6 Hyperparameter Recommendations

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `lambda_bcvf` | 1.0 | Primary constraint—match importance with task loss |
| `lambda_use` | 0.5 | Secondary—global coherence regularization |
| `lambda_scc` | 0.1 | Light touch—avoid over-constraining entropy |
| `lambda_f` | 1.0 | Standard confidence penalty |
| `lambda_b` | 1.0 | Standard alignment penalty |
| `lambda_c` | 0.5 | Lighter balance constraint |

### 18.7 Diagnostic Monitoring

Track these metrics during training to ensure healthy optimization:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    SOVEREIGN PATENT LOSS DIAGNOSTICS                                     │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  HEALTHY TRAINING INDICATORS:                                                           │
│  ══════════════════════════════                                                         │
│                                                                                          │
│  s_f (Confidence): Should rise from ~0.5 → 0.8+ over training                          │
│  s_b (Alignment):  Should rise from ~0.5 → 0.85+ over training                         │
│  |s_f - s_b|:      Should stay < 0.15 (balance constraint working)                     │
│  entropy:          Should stabilize in [0.3, 0.7] range (not 0 or max)                 │
│                                                                                          │
│  WARNING SIGNS:                                                                          │
│  ══════════════                                                                         │
│  s_f >> s_b:       Model is "lazily confident" (amplifying noise)                      │
│  s_b >> s_f:       Model is "weakly accurate" (correct but uncertain)                  │
│  entropy → 0:      Phase collapse (all patches identical)                               │
│  entropy → max:    Chaotic hallucination (random phases)                               │
│  L_use not decreasing: Global structure not forming                                     │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 19. Operational Stability & Troubleshooting

Training complex-valued neural networks (CVNNs) and Phase-JEPAs requires specific stabilization tactics not found in standard ViT training manuals.

### 19.1 The "Phase Wrapping" Hazard

**Symptom:** Loss spikes suddenly; gradients explode.

**Cause:** When a phase angle φ crosses from +π to −π, the derivative is discontinuous if calculated naively on the angle.

**Fix:** The `PhaseSyncLoss` uses `1 − cos(φ_pred − φ_target)`, which is continuous. **DO NOT** use MSE on raw angles (`(φ_pred − φ_target)²`).

**Implementation Constraint:** Always keep optimization in the **Phasor Domain** (complex numbers) or **Cartesian Domain** (`(Re, Im)`), never in the raw **Polar Domain** (angle scalars) for intermediate layers.

### 19.2 Initialization Strategy (The "Cold Start" Problem)

If phases are initialized to exactly 0, the "Global Structure" collapses. If random, it starts as noise.

**Recommended Initialization:**

| Parameter | Strategy | Rationale |
|-----------|----------|-----------|
| **Query/Key Phases** | Uniform `[-π, +π]` | Avoid degenerate zero-phase collapse |
| **Amplitudes** | `σ(linear + bias)` with bias = `-2.0` | Start sigmoid ≈ 0.12 (low confidence), let model learn to attend |
| **Predictor MLP (last layer)** | **Zero-initialized** | Forces predictor to start as Identity `f(x) = x` and learn deviations |

```python
# Initialization Example
def init_phase_layers(module):
    if hasattr(module, 'phase_proj'):
        # Uniform phase initialization
        nn.init.uniform_(module.phase_proj.weight, -math.pi, math.pi)
    if hasattr(module, 'amp_proj'):
        # Low-confidence amplitude start
        nn.init.zeros_(module.amp_proj.weight)
        nn.init.constant_(module.amp_proj.bias, -2.0)
    if hasattr(module, 'delta_mlp'):
        # Identity-start for predictor
        nn.init.zeros_(module.delta_mlp[-1].weight)
        nn.init.zeros_(module.delta_mlp[-1].bias)
```

### 19.3 Loss Balancing Heuristics

The Multi-Objective Loss (Formula S3) has 4 competing terms. Use this balancing schedule:

| Training Epoch | λ_task (JEPA) | λ_BCVF (Consistency) | λ_USE (Coherence) | λ_SCC (Entropy) | Rationale |
|----------------|---------------|----------------------|-------------------|-----------------|-----------|
| **0-5 (Warmup)** | 1.0 | 0.0 | 0.1 | 0.0 | Let the model learn to "see" (reconstruct) before governing it |
| **5-20 (Structure)** | 1.0 | 0.1 | 0.5 | 0.0 | Enforce global phase structure (L_USE) once features exist |
| **20+ (Governance)** | 1.0 | **1.0** | 0.5 | **0.1** | Turn on the SRK (B1, S5) to refine and arbitrate |

```python
class LossScheduler:
    """Curriculum-based loss weight scheduling."""

    def __init__(self):
        self.schedules = {
            'warmup':    {'task': 1.0, 'bcvf': 0.0, 'use': 0.1, 'scc': 0.0},
            'structure': {'task': 1.0, 'bcvf': 0.1, 'use': 0.5, 'scc': 0.0},
            'govern':    {'task': 1.0, 'bcvf': 1.0, 'use': 0.5, 'scc': 0.1},
        }

    def get_weights(self, epoch: int) -> dict:
        if epoch < 5:
            return self.schedules['warmup']
        elif epoch < 20:
            return self.schedules['structure']
        else:
            return self.schedules['govern']
```

### 19.4 Debugging "Phase Collapse"

**Symptom:** `PAS` score stays near 1.0, but `Reconstruction MSE` is high.

**Diagnosis:** The model has learned to predict φ = 0 for all patches (everything is zero phase).

**Countermeasures:**

1. **Increase VICReg Variance Loss** to force distribution spread
2. **Increase Patent SCC Entropy Penalty** (`λ_SCC = 0.2+`)
3. **Check amplitude initialization** — if amplitudes are too low, phases have no gradient signal

```python
# Phase Collapse Detection
def detect_phase_collapse(pred_z: torch.Tensor, threshold: float = 0.1) -> bool:
    """Returns True if phases have collapsed to near-zero variance."""
    pred_c = torch.view_as_complex(pred_z.reshape(*pred_z.shape[:-1], -1, 2))
    phase_std = pred_c.angle().std()
    return phase_std < threshold
```

### 19.5 Gradient Monitoring

Phase-based models can exhibit unusual gradient dynamics. Monitor these signals:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         GRADIENT HEALTH INDICATORS                                       │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  HEALTHY:                                                                                │
│  ════════                                                                                │
│  grad_norm(phase_proj) ∈ [0.01, 5.0]                                                    │
│  grad_norm(amp_proj) ∈ [0.01, 5.0]                                                      │
│  grad_norm(text_phase_projector) ∈ [0.001, 1.0]                                         │
│                                                                                          │
│  UNHEALTHY:                                                                              │
│  ══════════                                                                              │
│  grad_norm > 10.0  →  Gradient explosion (reduce LR or clip)                            │
│  grad_norm < 1e-6  →  Vanishing gradients (check activation functions)                  │
│  grad_norm oscillating wildly  →  Phase wrapping (check loss formulation)               │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 20. Production Inference Optimization

Implementing Phase-JEPA efficiently in production requires handling Complex Numbers on GPUs with care.

### 20.1 "Real-View" Optimization

PyTorch `complex64` can be slower than `float32` due to limited kernel optimization.

**Optimization Strategy:** Store real and imaginary parts as adjacent channels in the last dimension: `[B, N, D, 2]`.

```python
class RealViewComplexOps:
    """Efficient complex operations using real-valued tensors."""

    @staticmethod
    def multiply(z1: torch.Tensor, z2: torch.Tensor) -> torch.Tensor:
        """Complex multiplication: (a+bi)(c+di) = (ac-bd) + (ad+bc)i

        Args:
            z1, z2: [B, N, D, 2] where [..., 0] = real, [..., 1] = imag
        """
        a, b = z1[..., 0], z1[..., 1]
        c, d = z2[..., 0], z2[..., 1]
        real = a * c - b * d
        imag = a * d + b * c
        return torch.stack([real, imag], dim=-1)

    @staticmethod
    def rotate(z: torch.Tensor, theta: torch.Tensor) -> torch.Tensor:
        """Apply phase rotation: z × e^{iθ}

        Args:
            z: [B, N, D, 2] complex tensor in real-view
            theta: [B, D] or [B, 1, D] rotation angles
        """
        cos_t = torch.cos(theta).unsqueeze(-1)  # [..., 1]
        sin_t = torch.sin(theta).unsqueeze(-1)

        real = z[..., 0:1] * cos_t - z[..., 1:2] * sin_t
        imag = z[..., 0:1] * sin_t + z[..., 1:2] * cos_t
        return torch.cat([real, imag], dim=-1)
```

### 20.2 RoPE Kernel Reuse

The "Phase Rotation" operation is mathematically identical to Rotary Positional Embeddings (RoPE). You can reuse optimized RoPE kernels:

```python
# Leverage FlashAttention's optimized RoPE
from flash_attn.layers.rotary import apply_rotary_emb

def apply_text_phase_rotation(q: torch.Tensor, theta_geometric: torch.Tensor) -> torch.Tensor:
    """Reuse RoPE kernel for text-conditioned phase rotation.

    Args:
        q: [B, N, H, D_head] query tensor
        theta_geometric: [B, D_head//2] text-derived rotation angles

    Note: RoPE applies rotation per consecutive pair of dimensions,
          which aligns with our complex representation.
    """
    # Convert theta to RoPE format (cos, sin interleaved)
    cos = torch.cos(theta_geometric).unsqueeze(1).unsqueeze(2)  # [B, 1, 1, D/2]
    sin = torch.sin(theta_geometric).unsqueeze(1).unsqueeze(2)

    return apply_rotary_emb(q, cos, sin)
```

### 20.3 The "Intent Cache" (Speedup)

Since the Text Phase Shift (θ_geometric) depends only on the text prompt:

```python
class IntentCache:
    """Pre-computed phase shifts for common geometric commands."""

    def __init__(self, text_encoder: nn.Module, phase_projector: nn.Module):
        self.text_encoder = text_encoder
        self.phase_projector = phase_projector
        self.cache = {}

    def warmup(self, common_prompts: list[str]):
        """Pre-compute phase shifts for common commands."""
        with torch.no_grad():
            for prompt in common_prompts:
                tokens = self.tokenize(prompt)
                text_emb = self.text_encoder(tokens)
                theta = torch.tanh(self.phase_projector(text_emb)) * math.pi
                self.cache[prompt] = theta.cpu()

    def get_phase_shift(self, prompt: str, device: torch.device) -> torch.Tensor:
        """Retrieve cached or compute phase shift."""
        if prompt in self.cache:
            return self.cache[prompt].to(device)

        # Fallback to computation
        with torch.no_grad():
            tokens = self.tokenize(prompt)
            text_emb = self.text_encoder(tokens)
            return torch.tanh(self.phase_projector(text_emb)) * math.pi

# Usage
cache = IntentCache(text_encoder, phase_projector)
cache.warmup([
    "Rotate 90 degrees clockwise",
    "Rotate 90 degrees counterclockwise",
    "Rotate 180 degrees",
    "Zoom in",
    "Zoom out",
    "Pan left",
    "Pan right",
    "Standard orientation",
])
```

### 20.4 Mauna Protocol Integration (Safety)

During inference, the `SovereignPatentLoss` diagnostics serve as a safety gate:

```python
class SafeInference:
    """Production inference with Mauna (silence) protocol."""

    def __init__(
        self,
        model: PhaseVLJEPA_System,
        entropy_threshold: float = 0.85,
        consistency_threshold: float = 0.2,
    ):
        self.model = model
        self.entropy_threshold = entropy_threshold
        self.consistency_threshold = consistency_threshold

    def __call__(self, image: torch.Tensor, text: str) -> dict:
        """Inference with safety checks."""
        pred, diagnostics = self.model.predict_with_diagnostics(image, text)

        # Mauna Check 1: Entropy too high (hallucination risk)
        if diagnostics['entropy'] > self.entropy_threshold:
            return {
                'status': 'mauna',
                'reason': 'high_entropy',
                'message': 'Model uncertainty too high for reliable prediction',
                'confidence': diagnostics['entropy'],
            }

        # Mauna Check 2: Consistency too low (logical contradiction)
        if diagnostics['consistency_weight'] < self.consistency_threshold:
            return {
                'status': 'mauna',
                'reason': 'low_consistency',
                'message': 'Internal consistency check failed',
                'confidence': diagnostics['consistency_weight'],
            }

        # Safe to return prediction
        return {
            'status': 'ok',
            'prediction': pred,
            'diagnostics': diagnostics,
        }
```

### 20.5 Batch Inference Optimization

For production throughput, batch multiple images with the same text command:

```python
def batch_inference(
    model: PhaseVLJEPA_System,
    images: list[torch.Tensor],
    text: str,
    intent_cache: IntentCache,
) -> list[torch.Tensor]:
    """Optimized batch inference with shared text phase."""

    # 1. Get cached phase shift (O(1) lookup)
    theta = intent_cache.get_phase_shift(text, images[0].device)

    # 2. Batch images
    batch = torch.stack(images)  # [B, C, H, W]

    # 3. Expand theta for batch
    theta_batch = theta.expand(len(images), -1)  # [B, D_phase]

    # 4. Single forward pass
    with torch.no_grad():
        predictions = model(batch, theta_batch)

    return predictions
```

---

## 21. Final Verification Checklist

Before launching the full training run, verify these critical items:

### 21.1 Gradient & Autograd Checks

- [ ] **Gradient Norm Check:** Gradients for `phase_proj` layers should not exceed 5.0
- [ ] **Complex Autograd:** Ensure `loss.backward()` works through `torch.view_as_complex`
- [ ] **No NaN/Inf:** Check for numerical instability in phase calculations

```python
def verify_gradients(model: nn.Module, sample_batch: tuple) -> bool:
    """Verify gradient flow is healthy."""
    images, masks, text_phases = sample_batch

    model.zero_grad()
    loss, _ = model.training_step({'images': images, 'masks': masks, 'text_phases': text_phases})
    loss.backward()

    for name, param in model.named_parameters():
        if param.grad is not None:
            grad_norm = param.grad.norm().item()
            if grad_norm > 10.0:
                print(f"WARNING: {name} grad_norm = {grad_norm:.2f} (too high)")
                return False
            if torch.isnan(param.grad).any() or torch.isinf(param.grad).any():
                print(f"ERROR: {name} has NaN/Inf gradients")
                return False

    return True
```

### 21.2 Data Pipeline Checks

- [ ] **Mask-Text Alignment:** Visualize one batch from `GeometricMaskCollator`. Does the "Text" match the "Mask"?
- [ ] **Rotation Labels:** If text = "Rotated 90", is the mask actually challenging rotation?
- [ ] **Batch Collation:** Verify masks and images are correctly paired

```python
def visualize_batch(collator: GeometricMaskCollator, dataset, num_samples: int = 4):
    """Visual verification of data pipeline."""
    import matplotlib.pyplot as plt

    batch = [dataset[i] for i in range(num_samples)]
    images, masks, rotations = collator(batch)

    fig, axes = plt.subplots(num_samples, 2, figsize=(8, 4*num_samples))
    for i in range(num_samples):
        # Original image
        axes[i, 0].imshow(images[i].permute(1, 2, 0))
        axes[i, 0].set_title(f"Image {i}")

        # Mask visualization
        mask_2d = masks[i].reshape(14, 14)
        axes[i, 1].imshow(mask_2d, cmap='gray')
        axes[i, 1].set_title(f"Mask (rot={rotations[i]:.2f})")

    plt.tight_layout()
    plt.savefig('data_pipeline_check.png')
    print("Saved data_pipeline_check.png")
```

### 21.3 EMA & Teacher Checks

- [ ] **Teacher Weights Updating:** Verify teacher weights are changing (EMA decay isn't 1.0)
- [ ] **Student-Teacher Divergence:** After N steps, teacher should differ from student

```python
def verify_ema_update(model: PhaseVLJEPA_System, steps: int = 100) -> bool:
    """Verify EMA is actually updating teacher weights."""
    # Snapshot teacher weights
    initial_teacher = {k: v.clone() for k, v in model.teacher_encoder.state_dict().items()}

    # Run training steps
    for _ in range(steps):
        model.training_step(get_dummy_batch())

    # Compare
    changed = 0
    for k, v in model.teacher_encoder.state_dict().items():
        if not torch.allclose(initial_teacher[k], v, atol=1e-6):
            changed += 1

    if changed == 0:
        print("ERROR: Teacher weights unchanged after training (EMA decay = 1.0?)")
        return False

    print(f"OK: {changed} teacher parameter tensors updated via EMA")
    return True
```

### 21.4 Loss Component Checks

- [ ] **Individual Loss Terms:** Verify each loss component (L_task, L_BCVF, L_USE, L_SCC) is non-zero
- [ ] **Loss Scale Balance:** No single term should dominate (>90% of total)

```python
def verify_loss_balance(diagnostics: dict) -> bool:
    """Check that loss terms are balanced."""
    total = sum(v for k, v in diagnostics.items() if k.startswith('L_'))

    for key, value in diagnostics.items():
        if key.startswith('L_') and total > 0:
            ratio = value / total
            if ratio > 0.9:
                print(f"WARNING: {key} dominates loss ({ratio:.1%})")
                return False

    return True
```

### 21.5 Pre-Flight Summary

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         PRE-TRAINING VERIFICATION CHECKLIST                              │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  CRITICAL (Must Pass):                                                                   │
│  ═════════════════════                                                                   │
│  [ ] Gradient flow through complex operations verified                                   │
│  [ ] No NaN/Inf in forward pass                                                         │
│  [ ] EMA teacher weights updating                                                        │
│  [ ] Data pipeline text-mask alignment verified                                          │
│                                                                                          │
│  RECOMMENDED (Should Pass):                                                              │
│  ══════════════════════════                                                              │
│  [ ] Gradient norms < 5.0 for phase layers                                              │
│  [ ] Loss terms balanced (no single term > 90%)                                          │
│  [ ] Phase variance > 0.1 (no collapse)                                                  │
│  [ ] Teacher-student weights diverging                                                   │
│                                                                                          │
│  OPTIONAL (Nice to Have):                                                                │
│  ════════════════════════                                                                │
│  [ ] Data pipeline visualization saved                                                   │
│  [ ] Benchmark forward pass latency                                                      │
│  [ ] Memory usage profiled                                                               │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix A: Theoretical Foundations

### A.1 JEPA as Contrastive-Free Learning

Standard contrastive learning requires negative samples:
$$L_{\text{contrastive}} = -\log \frac{\exp(z_i \cdot z_j / \tau)}{\sum_k \exp(z_i \cdot z_k / \tau)}$$

JEPA avoids this via prediction + regularization:
$$L_{\text{JEPA}} = \|f_{\text{pred}}(z_{\text{context}}) - z_{\text{target}}\|^2 + \lambda \cdot L_{\text{reg}}$$

Where $L_{\text{reg}}$ (VICReg) prevents collapse without negatives.

### A.2 Phase Rotation as Contextual Transformation

Intent phase rotation implements a **context-dependent linear map**:

$$z' = z \cdot e^{i\theta_{\text{intent}}}$$

This is equivalent to a rotation in 2D (per complex dimension):
$$\begin{bmatrix} \text{Re}(z') \\ \text{Im}(z') \end{bmatrix} = \begin{bmatrix} \cos\theta & -\sin\theta \\ \sin\theta & \cos\theta \end{bmatrix} \begin{bmatrix} \text{Re}(z) \\ \text{Im}(z) \end{bmatrix}$$

Same input, different meaning based on cognitive mode.

### A.3 Connection to Hopfield Networks

The cumulative state in Phase Attention resembles a continuous Hopfield update:
$$\text{State}_t = \sum_{j \leq t} K_j V_j$$

This is an **associative memory** where patterns (K) are stored and retrieved via query (Q) synchronization.

---

## Appendix B: Risk Analysis

### B.1 Potential Failure Modes

| Risk | Mitigation |
|------|------------|
| **Representation Collapse** | VICReg regularization + EMA target |
| **Phase Explosion** | Sigmoid amplitudes, tanh phase bounds |
| **State Drift** | OPB dimension locking + Smṛti anchor |
| **Training Instability** | Three-phase curriculum, gradual complexity |

### B.2 Alignment Considerations

The architecture inherits Gemini's alignment properties:
- **Phase-Lock Constraint**: Prevents internal/external divergence
- **Metalinguistic Fallback**: Explicit uncertainty communication
- **Vritti Gate**: Blocks high-error predictions

---

## Appendix C: Strategic Architecture Philosophy

This appendix captures the strategic rationale for the Hybrid Phase-VL-JEPA architecture and its relationship to the broader SymbolU system.

### C.1 The "Body and Soul" Architecture

The Phase-VL-JEPA is intentionally designed as the **"Perception Body"** that the **"Sovereign Soul"** (SRK) will eventually govern.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    THE GRAND ARCHITECTURE: BODY + SOUL                                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE-VL-JEPA ("The Body" / "The Observer")                                     │   │
│  │  ═══════════════════════════════════════════                                     │   │
│  │                                                                                   │   │
│  │  PURPOSE: Provide the "World Model"                                              │   │
│  │  • Understands geometry, physics, spatial relationships                          │   │
│  │  • Learns by prediction (not generation)                                         │   │
│  │  • Uses Phase Math for representation                                            │   │
│  │                                                                                   │   │
│  │  KAHNEMAN: System 1 (Fast, Intuitive, Parallel)                                  │   │
│  │  • Instantly "sees" answers via prediction + phase-locking                       │   │
│  │  • Handles 90% of workload (perception/retrieval)                                │   │
│  │                                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         ↕                                                │
│                              SHARED LANGUAGE: Phase Math                                 │
│                                         ↕                                                │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  SOVEREIGN REASONING KERNEL ("The Soul" / "The Judge")                           │   │
│  │  ════════════════════════════════════════════════════                            │   │
│  │                                                                                   │   │
│  │  PURPOSE: Provide the "Executive Function"                                       │   │
│  │  • Arbitrates decisions, checks constraints                                      │   │
│  │  • Ensures logical and ethical consistency                                       │   │
│  │  • Uses Phase Math (USE Formulas) for reasoning                                  │   │
│  │                                                                                   │   │
│  │  KAHNEMAN: System 2 (Slow, Deliberate, Arbitrating)                              │   │
│  │  • Deliberately "checks" answers via Witness + Mauna Protocol                    │   │
│  │  • Handles 10% that requires deep arbitration                                    │   │
│  │                                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  KEY INSIGHT: Both systems speak the SAME mathematical language (Phase Dynamics)        │
│  This enables seamless future integration when SRK is re-attached to govern VL-JEPA    │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### C.2 Why Phase Math is Superior for Geometry

Standard neural networks must learn geometric transformations via expensive matrix operations:

```
STANDARD MODEL (Matrix Multiplication):
─────────────────────────────────────────
"Rotate object 90°" requires:
• Learning a rotation matrix R
• Computing y = R @ x (O(n²) operation)
• Training on thousands of rotation examples

PHASE-VL-JEPA (Phase Addition):
────────────────────────────────
"Rotate object 90°" requires:
• Adding θ = π/2 to phase angle
• Computing y = x × e^{iθ} (O(n) operation)
• Rotation is mathematically NATIVE—no learning required
```

**Strategic Advantage**: Phase-JEPA is expected to converge **2-3x faster** on geometric tasks because rotation is a trivial operation (phase addition) rather than a learned transformation (matrix multiplication).

### C.3 Hallucination Resistance by Design

The Phase-VL-JEPA is **Predictive, not Generative**:

| Property | Generative Models | Predictive (Phase-VL-JEPA) |
|----------|-------------------|----------------------------|
| **Output** | Raw pixels/tokens | Latent representations |
| **Failure Mode** | "Dreams up" invalid content | Predicts valid states only |
| **Hallucination Risk** | High (unconstrained generation) | Low (representation constraints) |
| **Speed** | Slow (autoregressive) | Fast (single forward pass) |

**Why this matters**: A Generative model can "hallucinate" a dog with 5 legs. The Phase-VL-JEPA cannot—it predicts a valid representation in latent space, constrained by learned phase relationships.

### C.4 The Conditioning Paradigm Shift

The fundamental difference between standard VL-JEPA and Phase-VL-JEPA is HOW text conditions visual prediction:

```
STANDARD VL-JEPA ("Concatenation/Addition"):
────────────────────────────────────────────
Input = [Image_Patches] + [Text_Tokens]
         ↓
The model must LEARN to attend from image to text
         ↓
Struggles with explicit geometric commands ("rotate left")

PHASE-VL-JEPA ("Rotation/Transformation"):
────────────────────────────────────────────
θ = TextEncoder(text) → Phase Angle
         ↓
Q' = Q × e^{iθ}  (Query phases ROTATED by text)
         ↓
Geometric conditioning is MATHEMATICAL, not learned
```

**Intuition**: Standard JEPA "staples" text to image and hopes the model figures it out. Phase-JEPA physically ROTATES the image representation to align with text semantics.

### C.5 Layman Analogies

**The Radio Tuning Analogy**:
- Standard JEPA: Shouts the song title over the static and hopes you hear it
- Phase-JEPA: Turns the dial to the right frequency—the song comes through clearly

**The Potter's Wheel Analogy**:
- Standard JEPA: Adds more clay (text) to the lump (image)
- Phase-JEPA: Spins the wheel—the spin dynamics shape the clay into the target form

**The Map Analogy**:
- Standard JEPA: Staples "Go East" note to the map
- Phase-JEPA: Rotates the map so East is straight ahead—no reading required

### C.6 Future Integration: Sovereign-JEPA

Once Phase-VL-JEPA is trained, the SRK can be re-attached as the "executive function":

```python
# Future Architecture: Sovereign-JEPA
class SovereignJEPA(nn.Module):
    def __init__(self):
        # The "Body" - trained Phase-VL-JEPA
        self.perception = PhaseVLJEPA_System.load("trained_vl_jepa.pt")

        # The "Soul" - Sovereign Reasoning Kernel
        self.srk = SovereignReasoningKernel()

    def forward(self, image, text, user_state):
        # 1. Perception: What does the model "see"?
        latent = self.perception(image, text)

        # 2. Governance: Should the model act on this?
        decision = self.srk.arbitrate(
            perception=latent,
            user_state=user_state,  # Sattvic anchor
        )

        # 3. Output: Either action or Mauna (silence)
        if decision.should_respond:
            return self.decode(decision.action)
        else:
            return Mauna()  # Veto power exercised
```

The key enabler: **Both systems speak Phase Math**, making the integration seamless.

---

## Appendix D: Sovereign AGI Integration Evaluation

This appendix provides a comprehensive evaluation of how the Hybrid Phase-JEPA integrates with the Sovereign Reasoning Kernel (SRK), identifying gaps and providing canonical design decisions for production integration.

### D.1 Understanding Summary

The Phase-JEPA design proposes a parallel model that:

- Predicts in latent space (32D Sovereign State) instead of token space
- Uses the same Phase Rotation mechanism as Sovereign AGI, but driven by different sources
- Targets Vision-Language understanding with geometric transformations

### D.2 Key Architectural Pairing

```
┌──────────────────────────────────┐     ┌──────────────────────────────────┐
│       SOVEREIGN AGI (SRK)        │     │       PHASE-JEPA (VL)            │
├──────────────────────────────────┤     ├──────────────────────────────────┤
│ Domain: Language/Reasoning       │     │ Domain: Vision-Language          │
│ Phase Source: 32D Sovereign ΔS   │     │ Phase Source: Text Embedding     │
│ Prediction: Next token           │     │ Prediction: Latent patches       │
│ Output: Tokens (generative)      │     │ Output: Representations (JEPA)   │
│ Complexity: O(n)                 │     │ Complexity: O(n)                 │
└──────────────────────────────────┘     └──────────────────────────────────┘
                    │                                     │
                    └──────────── SHARED ─────────────────┘
                              • Phase Rotation math
                              • 32D State structure
                              • OPB Dimension Locking
                              • HybridAttention backbone
```

### D.3 Integration Questions & Canonical Decisions

#### D.3.1 State Projector: Duplication vs Sharing

**Question:** Should `SovereignStateProjector` (JEPA) and `compute_state_from_hidden` (SRK) share weights?

**Current Implementations:**

```python
# SRK (symbolu/sovereign/reasoning_kernel.py)
def compute_state_from_hidden(self, hidden_states, apply_opb_locking=True):
    pooled = hidden_states.mean(dim=1)
    state = self.state_projector(pooled)  # Simple linear projection
    # Component-wise normalization...

# JEPA (proposed)
self.projector = nn.Sequential(
    nn.Linear(hidden_dim, hidden_dim // 2),
    nn.GELU(),
    nn.Linear(hidden_dim // 2, SOVEREIGN_DIM),
)
```

**Verdict: Independent Weights, Unified Architecture**

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Weights** | Independent | Input distributions differ fundamentally (Text 768D vs Visual 768D) |
| **Architecture** | Unified MLP | Standardize both to `Linear → GELU → Linear` for higher capacity |
| **Alignment** | Via Target Space | Both map to same 32D ontological schema (12 Bhavas + 5 Koshas + ...) |

```python
# Unified SovereignStateProjector (symbolu/common/projectors.py)
class SovereignStateProjector(nn.Module):
    """Unified projector architecture for both SRK and JEPA."""

    def __init__(self, hidden_dim: int, state_dim: int = 32):
        super().__init__()
        self.projector = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, state_dim),
        )

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        pooled = hidden_states.mean(dim=1)
        return self.projector(pooled)
```

#### D.3.2 OPB Integration Direction

**Question:** How does cross-model OPB work?

**Verdict: Master (SRK) / Sensor (JEPA) Relationship**

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         OPB SYNCHRONIZATION ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│    ┌─────────────────┐                              ┌─────────────────┐                 │
│    │   PHASE-JEPA    │                              │      SRK        │                 │
│    │   (Sensor)      │                              │    (Master)     │                 │
│    └────────┬────────┘                              └────────┬────────┘                 │
│             │                                                │                          │
│             ▼                                                ▼                          │
│    ┌─────────────────┐     Observation Feed          ┌─────────────────┐                │
│    │ perceptual_state│ ─────────────────────────────►│   MASTER OPB    │                │
│    │   (predicted)   │                               │                 │                │
│    └─────────────────┘                               │  ┌───────────┐  │                │
│                                                      │  │  Witness  │  │                │
│                                                      │  │ (Layer 9) │  │                │
│                                                      │  └─────┬─────┘  │                │
│                                                      │        │        │                │
│    ┌─────────────────┐     Karma Feedback            │        ▼        │                │
│    │ external_karma  │◄──────────────────────────────│  updated_state  │                │
│    │    _state       │                               │                 │                │
│    └─────────────────┘                               └─────────────────┘                │
│                                                                                          │
│    SYNC LOGIC:                                                                          │
│    1. JEPA predicts perceptual_state from video/images                                  │
│    2. perceptual_state feeds into SRK Layer 9 (Witness) as Observation                  │
│    3. Master OPB updates with merged perception + reasoning                             │
│    4. Updated state feeds back to BOTH models as prev_state_karma                       │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

```python
class PhaseVLJEPA_System(nn.Module):
    def forward(
        self,
        images: torch.Tensor,
        text: str,
        external_karma_state: Optional[torch.Tensor] = None,  # From SRK Master OPB
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            external_karma_state: Optional override from SRK's Master OPB
                                  for joint inference synchronization
        """
        if external_karma_state is not None:
            # Use SRK's state as karma (Master-Slave sync)
            karma = external_karma_state
        else:
            # Use internal karma for standalone mode
            karma = self.internal_karma_state

        # ... rest of forward pass
```

#### D.3.3 Phase Rotation Source Compatibility

**Question:** How do we combine `IntentPhase` (SRK) and `TextPhase` (JEPA)?

| Model | Source | Dimension |
|-------|--------|-----------|
| Sovereign AGI | `IntentPhaseProjector(ΔS)` | 32D → [H] or [H, D_h] |
| Phase-JEPA | `TextPhaseProjector(text_emb)` | text_dim → [H] or [H, D_h] |

**Verdict: Additive Phase Modulation**

**Physics:** Multiplying two phasors (e^{iθ₁} × e^{iθ₂}) equals adding their angles (e^{i(θ₁+θ₂)}).

```python
class DualSourcePhaseProjector(nn.Module):
    """Combines phase rotations from text and state sources."""

    def __init__(self, text_dim: int, state_dim: int, phase_dim: int):
        super().__init__()
        self.text_phase_proj = nn.Linear(text_dim, phase_dim)
        self.state_phase_proj = nn.Linear(state_dim, phase_dim)

    def forward(
        self,
        text_emb: torch.Tensor,
        state_delta: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Returns combined phase rotation.

        θ_text: Text-derived geometric rotation ("Rotate 90 degrees")
        θ_state: State-derived cognitive rotation ("Analyze for errors")
        θ_total: Combined rotation for both geometric AND cognitive conditioning
        """
        theta_text = torch.tanh(self.text_phase_proj(text_emb)) * math.pi

        if state_delta is not None:
            theta_state = torch.tanh(self.state_phase_proj(state_delta)) * math.pi
            theta_total = theta_text + theta_state  # Additive composition
        else:
            theta_total = theta_text

        return theta_total
```

**Effect:** The model attends to features that are *both* "Rotated 90 degrees" AND "Relevant to Error Analysis."

#### D.3.4 Cosine Mode Alignment

**Question:** Should SRK and JEPA share `cosine_mode`?

**Verdict: Domain-Optimized (Divergent Modes Allowed)**

| Model | Recommended Mode | Formula | Rationale |
|-------|------------------|---------|-----------|
| **JEPA (Vision)** | `complex` | Im(e^{iΔφ}) | Vision requires directionality (left vs right) |
| **SRK (Language)** | `shifted` | (1 + cos(Δφ))/2 | Positive signal flow prevents gradient vanishing |

```python
# Vision-optimized JEPA
jepa_attention = PhaseAttentionLayer(
    dim=768,
    num_heads=12,
    cosine_mode="complex",  # Directional geometry
)

# Language-optimized SRK
srk_attention = PhaseAttentionLayer(
    dim=768,
    num_heads=12,
    cosine_mode="shifted",  # Positive flow
)
```

#### D.3.5 Training Curriculum Sync

**Question:** How to align the training schedules?

**Verdict: The "Body then Soul" Schedule**

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         SEQUENTIAL TRAINING CURRICULUM                                    │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  PHASE 1: THE BODY (Vision)                                                             │
│  ══════════════════════════                                                             │
│  Train: Phase-JEPA on ImageNet/Video                                                    │
│  Objective: Learn physics, geometry, 32D projection of visual concepts                 │
│  Loss: VICReg (variance/covariance) + L_JEPA (MSE)                                      │
│  Duration: ~100 epochs                                                                  │
│                                                                                          │
│                              ↓                                                          │
│                                                                                          │
│  PHASE 2: THE SOUL (Language)                                                           │
│  ═══════════════════════════                                                            │
│  Train: SRK on Text corpora                                                             │
│  Objective: Learn ontology, logic, 32D projection of textual concepts                  │
│  Loss: Patent losses (BCVF, USE, SCC) + LM loss                                         │
│  Duration: ~100 epochs                                                                  │
│                                                                                          │
│                              ↓                                                          │
│                                                                                          │
│  PHASE 3: THE UNION (Multimodal)                                                        │
│  ════════════════════════════                                                           │
│  Train: Joint fine-tuning on paired Image-Text (LAION, etc.)                            │
│  Objective: Force S_vision ≈ S_text for same concepts                                  │
│  Strategy: Freeze encoders, train Alignment Head or fine-tune Projectors               │
│  Loss: Contrastive alignment + combined patent losses                                   │
│  Duration: ~50 epochs                                                                   │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### D.3.6 Loss Unification

**Question:** Which losses to use for combined training?

| JEPA-Specific | SRK-Specific | Purpose |
|---------------|--------------|---------|
| L_variance | - | Prevent dimension collapse |
| L_covariance | - | Decorrelate dimensions |
| L_ortho | - | Volume preservation |
| L_jepa (MSE) | - | State prediction |
| - | B1 (Consistency) | Forward-backward alignment |
| - | U2 (Phase Coherence) | Attention head sync |
| - | S8 (Stability) | Entropy decrease |

**Verdict: Composite Loss Architecture**

The Patent Losses (USE, SCC, BCVF) are universal constraints on *structure*, not domain. They apply to both.

```python
class UnifiedSovereignLoss(nn.Module):
    """Composite loss for joint SRK + JEPA training."""

    def __init__(
        self,
        lambda_jepa: float = 1.0,
        lambda_vicreg: float = 0.1,
        lambda_patent: float = 1.0,
    ):
        super().__init__()
        self.lambda_jepa = lambda_jepa
        self.lambda_vicreg = lambda_vicreg
        self.lambda_patent = lambda_patent

        self.vicreg_loss = VICRegLoss()
        self.patent_loss = SovereignPatentLoss()

    def forward(
        self,
        pred_z: torch.Tensor,
        target_z: torch.Tensor,
        text_phase: torch.Tensor,
        is_jepa_path: bool = True,
    ) -> torch.Tensor:
        """
        L_total = L_JEPA + λ_vicreg × L_VICReg + λ_patent × L_Patent

        Args:
            is_jepa_path: If True, include VICReg (prevents collapse without decoder)
        """
        # Base JEPA loss
        L_jepa = F.mse_loss(pred_z, target_z)

        # VICReg for JEPA path only (SRK has decoder)
        if is_jepa_path:
            L_vicreg = self.vicreg_loss(pred_z)
        else:
            L_vicreg = 0.0

        # Patent losses (universal structure constraints)
        L_patent, diagnostics = self.patent_loss(pred_z, target_z, text_phase)

        L_total = (
            self.lambda_jepa * L_jepa
            + self.lambda_vicreg * L_vicreg
            + self.lambda_patent * L_patent
        )

        return L_total, diagnostics
```

#### D.3.7 Karma State Carryover for Video

**Question:** Does Phase-JEPA need karma carryover for video/sequential images?

**Verdict: Yes, via the Predictor (Implicit Autoregression)**

```python
class VideoPhaseJEPA(nn.Module):
    """Phase-JEPA with temporal karma for video sequences."""

    def __init__(self, base_jepa: PhaseVLJEPA_System, karma_decay: float = 0.9):
        super().__init__()
        self.jepa = base_jepa
        self.karma_decay = karma_decay
        self.karma_state = None

    def forward_sequence(
        self,
        video_frames: torch.Tensor,  # [B, T, C, H, W]
        text: str,
    ) -> list[torch.Tensor]:
        """Process video with temporal karma carryover."""
        B, T = video_frames.shape[:2]
        predictions = []

        for t in range(T):
            frame = video_frames[:, t]

            # Inject karma from previous frame
            pred, state = self.jepa(
                frame,
                text,
                external_karma_state=self.karma_state,
            )

            # Update karma with decay (matches SRK's update_buffer logic)
            self.karma_state = torch.tanh(state.detach()) * self.karma_decay

            predictions.append(pred)

        return predictions

    def reset_karma(self):
        """Reset karma state (e.g., between videos)."""
        self.karma_state = None
```

**Alignment:** The `tanh` compression matches SRK's `update_buffer` logic for consistent karma dynamics.

#### D.3.8 Shared Embedding Space

**Question:** How to align vision patches and text tokens into shared space?

**Verdict: The 32D Sovereign State IS the Shared Space**

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         32D SOVEREIGN STATE AS SHARED EMBEDDING                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│    Vision Path                              Text Path                                   │
│    ═══════════                              ═════════                                   │
│                                                                                          │
│    Image of "Dog"                           Text: "Dog"                                 │
│         │                                        │                                      │
│         ▼                                        ▼                                      │
│    ViT Encoder                              Text Encoder                                │
│    (768D patches)                           (768D hidden)                               │
│         │                                        │                                      │
│         ▼                                        ▼                                      │
│    SovereignStateProjector              SovereignStateProjector                         │
│    (Visual Instance)                    (Text Instance)                                 │
│         │                                        │                                      │
│         ▼                                        ▼                                      │
│    ┌─────────────────────────────────────────────────────────────────┐                 │
│    │                     32D SOVEREIGN STATE                          │                 │
│    │                                                                  │                 │
│    │  [Annamaya=0.8, Pranamaya=0.2, ..., Identity=0.9, ...]          │                 │
│    │                                                                  │                 │
│    │  ALIGNMENT TARGET: S_vision("Dog") ≈ S_text("Dog")              │                 │
│    │                                                                  │                 │
│    └─────────────────────────────────────────────────────────────────┘                 │
│                                                                                          │
│    KEY INSIGHT:                                                                         │
│    We don't need to align 768D hidden states (hard).                                   │
│    We only align 32D projections via shared ontological schema.                        │
│    The SovereignStateProjector is the bottleneck that FORCES alignment.                │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### D.4 Readiness Assessment

| Aspect | Status | Notes |
|--------|--------|-------|
| Phase Rotation Math | ✅ Ready | Identical mechanism transfers |
| HybridAttention Backbone | ✅ Ready | Can reuse directly |
| 32D State Structure | ✅ Ready | Same dimensions, same semantics |
| State Projector | ✅ Decided | Independent weights, unified architecture |
| OPB Cross-Model | ✅ Decided | Master (SRK) / Sensor (JEPA) sync |
| Multi-Source Phase | ✅ Decided | Additive composition via DualSourcePhaseProjector |
| Loss Unification | ✅ Decided | VICReg for JEPA + Patent for both |
| Joint Training | ✅ Decided | Body → Soul → Union curriculum |
| Karma for Video | ✅ Decided | Implicit autoregression with tanh compression |
| Shared Embedding | ✅ Decided | 32D Sovereign State as bottleneck |

### D.5 Implementation Priority

Based on the decisions above, the implementation order is:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         IMPLEMENTATION PRIORITY ORDER                                     │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  PRIORITY 1 (Foundation):                                                               │
│  ══════════════════════                                                                 │
│  [ ] Extract SovereignStateProjector to symbolu/common/projectors.py                   │
│  [ ] Standardize both SRK and JEPA to use unified MLP architecture                     │
│  [ ] Add external_karma_state parameter to PhaseVLJEPA_System                           │
│                                                                                          │
│  PRIORITY 2 (Integration):                                                              │
│  ═════════════════════════                                                              │
│  [ ] Implement DualSourcePhaseProjector for additive phase composition                 │
│  [ ] Define MasterOPB class with bidirectional sync logic                              │
│  [ ] Implement UnifiedSovereignLoss composite framework                                 │
│                                                                                          │
│  PRIORITY 3 (Extension):                                                                │
│  ════════════════════════                                                               │
│  [ ] Implement VideoPhaseJEPA with temporal karma                                       │
│  [ ] Create SovereignJEPA wrapper for joint inference                                   │
│  [ ] Add cosine_mode configuration per model instance                                   │
│                                                                                          │
│  PRIORITY 4 (Training):                                                                 │
│  ══════════════════════                                                                 │
│  [ ] Define Phase 1/2/3 training scripts                                               │
│  [ ] Implement alignment loss for Phase 3 (Union)                                       │
│  [ ] Create evaluation suite for cross-modal alignment                                  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix E: Cross-Model Validation Dialogue

This appendix documents the validation dialogue between Claude (codebase validation) and Gemini (architectural decisions), ensuring implementation readiness.

### E.1 Claude's Codebase Validation

Claude validated Gemini's 8 canonical decisions against the existing SymbolU implementation:

#### E.1.1 State Projector - ✅ Aligned

**Gemini's Decision:** Independent weights, MLP architecture (Linear → GELU → Linear)

**Current SRK Implementation:**
```python
# symbolu/sovereign/reasoning_kernel.py - simpler linear
self.state_projector = nn.Linear(hidden_dim, SOVEREIGN_STATE_DIM)
```

**Action Needed:** Upgrade SRK's projector to match JEPA's MLP design:
```python
self.state_projector = nn.Sequential(
    nn.Linear(hidden_dim, hidden_dim // 2),
    nn.GELU(),
    nn.Linear(hidden_dim // 2, SOVEREIGN_STATE_DIM),
)
```

**Status:** No conflict - capacity upgrade, backward compatible via checkpoint migration.

#### E.1.2 OPB Master/Sensor - ✅ Aligned with Extension

**Gemini's Decision:** SRK holds Master OPB, JEPA is Sensor

**Current OPB in SRK:**
```python
class OPBDimensionLock(nn.Module):
    def update_locks(self, state: torch.Tensor) -> Dict[str, Any]:
        # Per-dimension locking based on activation threshold
```

**Gap Identified:** Current OPB only handles internal state updates. Need to add:
```python
def merge_external_observation(self, observed_state: torch.Tensor, source: str = "jepa"):
    """Merge external observation (JEPA perception) into Master OPB."""
    # Gated merge: Master retains locked dims, accepts unlocked from sensor
    merge_mask = ~self.locked_mask  # Only accept where not locked
    self.locked_state = torch.where(
        merge_mask,
        observed_state.mean(dim=0),  # Accept sensor observation
        self.locked_state             # Retain master state
    )
```

#### E.1.3 Additive Phase Composition - ✅ Mathematically Sound

**Gemini's Decision:** θ_total = θ_text + θ_intent

**Current IntentPhaseProjector:**
```python
# symbolu/phase_transformer.py:298
def forward(self, delta_S: torch.Tensor) -> torch.Tensor:
    theta = self.phase_proj(delta_S)
    theta = torch.tanh(theta) * 3.14159
    return theta
```

**Current PhaseAttentionLayer application:**
```python
# symbolu/phase_transformer.py:528
if intent_phase is not None:
    phi_q = phi_q + intent_phase  # Already additive!
```

**Status:** No code change needed for addition itself. Need new `DualSourcePhaseProjector`.

#### E.1.4 Cosine Mode Divergence - ✅ Already Supported

**Gemini's Decision:** JEPA=complex, SRK=shifted

**Current Implementation:**
```python
# symbolu/phase_transformer.py:383
assert cosine_mode in ("standard", "shifted", "complex")
self.cosine_mode = cosine_mode
```

**Status:** No code change needed - already parameterized per-instance.

#### E.1.5 Training Curriculum - ⚠️ Needs Orchestration

**Gemini's Decision:** Body → Soul → Union

| Phase | Model | Data | Losses |
|-------|-------|------|--------|
| 1 (Body) | JEPA only | ImageNet/Video | VICReg |
| 2 (Soul) | SRK only | Text | Patent (B1/U2/S8) |
| 3 (Union) | Joint | Image-Text pairs | Force S_visual ≈ S_text |

**Gap:** No training orchestrator exists. Need:
- Phase detection logic
- Loss weight scheduler per phase
- Encoder freezing mechanism for Phase 3

#### E.1.6 Loss Unification - ⚠️ Partial Implementation

**Gemini's Decision:** L_total = L_Patent + L_VICReg + L_JEPA

**Current SRK Loss (sovereign_loss.py):**
- B1 (Consistency Lagrangian) ✅
- U2 (Phase Coherence) ✅
- S8 (Stability) ✅

**Missing for JEPA:**
- L_variance (VICReg) ❌
- L_covariance (VICReg) ❌
- L_jepa (MSE prediction) ❌
- L_ortho (Volume preservation) ❌

**Action:** Add VICReg losses to `symbolu/sovereign/sovereign_loss.py` or create `symbolu/jepa/losses.py`.

#### E.1.7 Karma for Video - ✅ Implicit in Design

**Gemini's Decision:** Predictor's autoregressive rollout IS karma

**JEPA Design (from doc):**
```python
# Each step feeds forward
s_current = s_context + delta_s  # Karma carryover
```

**Alignment with SRK:**
```python
# train_unified_llm.py:9639
srk_karma_state = current_state.detach() * config.srk_karma_decay
```

**Status:** Minor adjustment - ensure both use same decay factor or make configurable.

#### E.1.8 32D as Shared Space - ✅ Core Design Principle

**Gemini's Decision:** 32D Sovereign State is the alignment bottleneck

Both models project to:
- `[0:12]` Bhavas - "Dog" = Identity Bhava
- `[12:17]` Koshas - Physical (Annamaya) for visual, Mental (Manomaya) for abstract
- `[17:22]` Vrittis - Pramana (valid cognition) when confident
- `[22:28]` Gunas - Sattva high for clear perception
- `[28:32]` Reserved - Toroidal feedback

**Status:** No code change needed - this is architectural.

### E.2 Claude's Remaining Questions

Claude identified three open questions requiring Gemini's ruling:

#### Q1: Phase 3 Alignment Loss

How to enforce S_visual ≈ S_text?

```python
# Option A: MSE
L_align = MSE(S_visual, S_text)

# Option B: Cosine similarity
L_align = 1 - cos_sim(S_visual, S_text)

# Option C: Per-component weighted
L_align = Σ w_i * MSE(S_visual[i], S_text[i])  # Higher weight on Bhavas
```

#### Q2: External Karma Injection Shape

For `PhaseVLJEPA.forward(external_karma_state)`:
- Should it be `[B, 32]` (single state) or `[B, T, 32]` (per-position)?
- Should JEPA completely override or blend?

#### Q3: Cosine Mode for Predictor

The JEPA Predictor also uses phase attention. Should it use:
- Same as encoder (`complex`)?
- Different mode optimized for latent prediction?

### E.3 Gemini's Final Rulings

#### Ruling Q1: Phase 3 Alignment Loss

**Verdict: Option C (Per-Component Weighted MSE)**

**Rationale:** "Dog" (Vision) and "Dog" (Text) must share the same **Bhava (Identity)**, but they often have different **Gunas (Energy)**. An image of a dog is static (Tamasic); the word "Run!" is active (Rajasic). Enforcing Guna alignment would confuse the model.

**Formula:**
$$L_{align} = \sum_{i} w_i \cdot MSE(S_{visual}[i], S_{text}[i])$$

**Weight Assignment:**
| Component | Weight | Rationale |
|-----------|--------|-----------|
| w_bhava (dims 0-12) | **10.0** | Critical Identity |
| w_kosha/vritti (dims 12-22) | **1.0** | Standard |
| w_guna/karma (dims 22-32) | **0.1** | Loose coupling |

```python
class ComponentWeightedAlignmentLoss(nn.Module):
    """Per-component weighted alignment for Phase 3 training."""

    def __init__(self):
        super().__init__()
        # Weight vector for 32D state
        weights = torch.ones(32)
        weights[0:12] = 10.0   # Bhavas (Identity) - Critical
        weights[12:22] = 1.0   # Koshas/Vrittis - Standard
        weights[22:32] = 0.1   # Gunas/Karma - Loose coupling
        self.register_buffer('weights', weights)

    def forward(self, s_visual: torch.Tensor, s_text: torch.Tensor) -> torch.Tensor:
        """
        Args:
            s_visual: [B, 32] Visual sovereign state
            s_text: [B, 32] Text sovereign state
        """
        diff = (s_visual - s_text) ** 2  # [B, 32]
        weighted_diff = diff * self.weights  # [B, 32]
        return weighted_diff.mean()
```

#### Ruling Q2: External Karma Injection Shape

**Verdict: `[B, 32]` with Gated Blend**

**Rationale:** The SRK operates on a single "Thought State" per sequence. Even if the video has temporal depth, the "Reasoning Karma" is a sequence-level summary. A gated blend allows the SRK to say "I see your visual input, but I am maintaining my own reasoning state."

**Mechanism:**
$$\text{karma}_{effective} = g \odot \text{karma}_{external} + (1-g) \odot \text{karma}_{internal}$$

Where g = σ(W_gate · karma_external) is learned.

```python
class GatedKarmaInjector(nn.Module):
    """Blends external karma from SRK with internal JEPA karma."""

    def __init__(self, state_dim: int = 32):
        super().__init__()
        self.gate_proj = nn.Sequential(
            nn.Linear(state_dim, state_dim),
            nn.Sigmoid()
        )

    def forward(
        self,
        internal_karma: torch.Tensor,
        external_karma: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Args:
            internal_karma: [B, 32] JEPA's own karma state
            external_karma: [B, 32] SRK's Master OPB state (optional)
        """
        if external_karma is None:
            return internal_karma

        # Learn how much to trust external vs internal
        gate = self.gate_proj(external_karma)  # [B, 32]
        effective_karma = gate * external_karma + (1 - gate) * internal_karma

        return effective_karma
```

#### Ruling Q3: Cosine Mode for Predictor

**Verdict: `complex` Mode (Overruling Claude's `standard` suggestion)**

**Rationale:** This is a **Phase-JEPA**. The core hypothesis is that prediction happens via **Rotation** in latent space.

| Mode | Formula | Issue |
|------|---------|-------|
| `standard` | cos(Δφ) | Discards directionality |
| `complex` | [cos(Δφ), sin(Δφ)] | Preserves full phasor information |

Using `standard` mode collapses the imaginary component too early, destroying the "Phase Physics" you built. The `complex` mode allows the MLP to learn "Rotate 90 degrees" natively by preserving both real and imaginary components.

```python
# Predictor MUST use complex mode
predictor_attention = PhaseAttentionLayer(
    dim=768,
    num_heads=12,
    cosine_mode="complex",  # Critical: Preserve phase physics
)
```

### E.4 Gemini's Implementation Artifacts

#### A. The Dual-Source Phase Projector

**Location:** `symbolu/common/projectors.py`

```python
import torch
import torch.nn as nn
from symbolu.phase_transformer import IntentPhaseProjector


class DualSourcePhaseProjector(nn.Module):
    """
    Combines Text-derived geometric rotation with State-derived intent rotation.
    Implements: θ_total = θ_text + θ_intent
    """

    def __init__(self, text_dim: int, state_dim: int = 32, num_heads: int = 12):
        super().__init__()
        # Projectors for each source
        self.text_proj = IntentPhaseProjector(state_dim=text_dim, num_heads=num_heads)
        self.state_proj = IntentPhaseProjector(state_dim=state_dim, num_heads=num_heads)

        # Learnable scalar to balance sources (optional, defaults to 1.0)
        self.text_scale = nn.Parameter(torch.ones(1))
        self.state_scale = nn.Parameter(torch.ones(1))

    def forward(
        self,
        text_emb: torch.Tensor,
        state_delta: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            text_emb: [B, D_text] from Text Encoder
            state_delta: [B, 32] from Sovereign State Delta

        Returns:
            theta_total: [B, 1, H, D_head] Combined rotation angle
        """
        # Calculate individual rotations (Output is [B, 1, H, D_head] via Tanh * PI)
        theta_text = self.text_proj(text_emb)
        theta_intent = self.state_proj(state_delta)

        # Additive Phase Composition (Phasor multiplication logic)
        theta_total = (self.text_scale * theta_text) + (self.state_scale * theta_intent)

        return theta_total
```

#### B. OPB External Merge Logic

**Location:** `symbolu/sovereign/opb.py`

```python
class OPBDimensionLock(nn.Module):
    def __init__(self, state_dim: int = 32):
        super().__init__()
        self.register_buffer("locked_state", torch.zeros(state_dim))
        self.register_buffer("locked_mask", torch.zeros(state_dim, dtype=torch.bool))

        # Gating mechanism for external observations
        self.sensor_gate = nn.Sequential(
            nn.Linear(state_dim, state_dim),
            nn.Sigmoid()
        )

    def merge_external_observation(
        self,
        observed_state: torch.Tensor,
        override_locks: bool = False,
    ) -> torch.Tensor:
        """
        Merge Sensor (JEPA) state into Master (SRK) buffer.

        Args:
            observed_state: [B, 32] State predicted by JEPA
            override_locks: If True, sensor data breaks existing locks (Rare)
        """
        # 1. Calculate Gate: How much of the sensor data do we accept?
        # "Is this observation strong enough to update my beliefs?"
        gate = self.sensor_gate(observed_state)  # [B, 32]

        # 2. Blend Observation with Current State (Non-locked dimensions)
        current_state = self.locked_state.unsqueeze(0)  # [1, 32]
        blended_state = gate * observed_state + (1 - gate) * current_state

        # 3. Enforce Master Locks (Unless overridden)
        if not override_locks:
            # Where locked_mask is True, KEEP Master State. Elsewhere, use Blended.
            final_state = torch.where(
                self.locked_mask.unsqueeze(0),
                self.locked_state.unsqueeze(0),
                blended_state
            )
        else:
            final_state = blended_state

        return final_state
```

#### C. VICReg Loss Implementation

**Location:** `symbolu/jepa/losses.py`

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class VICRegLoss(nn.Module):
    """
    Variance-Invariance-Covariance Regularization.
    Prevents collapse in JEPA training without negative samples.
    """

    def __init__(self, sim_coeff: float = 25.0, std_coeff: float = 25.0, cov_coeff: float = 1.0):
        super().__init__()
        self.sim_coeff = sim_coeff
        self.std_coeff = std_coeff
        self.cov_coeff = cov_coeff

    def forward(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x, y: [B, D] representations (predicted vs target)
        """
        batch_size, num_features = x.shape

        # 1. Invariance Loss (MSE)
        repr_loss = F.mse_loss(x, y)

        # 2. Variance Loss (Hinge)
        # Forces variance of each dimension to be at least 1 (prevents collapse to point)
        std_x = torch.sqrt(x.var(dim=0) + 0.0001)
        std_y = torch.sqrt(y.var(dim=0) + 0.0001)
        std_loss = torch.mean(F.relu(1 - std_x)) / 2 + torch.mean(F.relu(1 - std_y)) / 2

        # 3. Covariance Loss
        # Decorrelates dimensions (prevents dimensions encoding same info)
        x = x - x.mean(dim=0)
        y = y - y.mean(dim=0)

        cov_x = (x.T @ x) / (batch_size - 1)
        cov_y = (y.T @ y) / (batch_size - 1)

        # Sum of off-diagonal squares
        cov_loss = (
            self._off_diagonal(cov_x).pow_(2).sum().div(num_features)
            + self._off_diagonal(cov_y).pow_(2).sum().div(num_features)
        )

        return (
            self.sim_coeff * repr_loss
            + self.std_coeff * std_loss
            + self.cov_coeff * cov_loss
        )

    def _off_diagonal(self, x: torch.Tensor) -> torch.Tensor:
        """Extract off-diagonal elements from square matrix."""
        n, m = x.shape
        assert n == m
        return x.flatten()[:-1].view(n - 1, n + 1)[:, 1:].flatten()
```

### E.5 Final Implementation Checklist

Based on this validation dialogue:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    VALIDATED IMPLEMENTATION CHECKLIST                                    │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  IMMEDIATE (Pre-Training):                                                              │
│  ═════════════════════════                                                              │
│  [ ] Upgrade SRK state_projector to MLP (Linear → GELU → Linear)                       │
│  [ ] Create symbolu/common/projectors.py with DualSourcePhaseProjector                 │
│  [ ] Create symbolu/jepa/losses.py with VICRegLoss                                      │
│  [ ] Add merge_external_observation() to OPBDimensionLock                              │
│                                                                                          │
│  PHASE 3 SPECIFIC:                                                                      │
│  ═════════════════                                                                      │
│  [ ] Implement ComponentWeightedAlignmentLoss                                           │
│  [ ] Implement GatedKarmaInjector                                                       │
│  [ ] Create training orchestrator with phase detection                                  │
│  [ ] Implement encoder freezing mechanism                                               │
│                                                                                          │
│  CONFIGURATION:                                                                         │
│  ══════════════                                                                         │
│  [ ] Ensure JEPA Predictor uses cosine_mode="complex"                                  │
│  [ ] Ensure SRK uses cosine_mode="shifted"                                             │
│  [ ] Make karma_decay configurable (currently 0.9 in both)                             │
│                                                                                          │
│  INTEGRATION TESTS:                                                                     │
│  ═════════════════                                                                      │
│  [ ] Test DualSourcePhaseProjector output shapes                                        │
│  [ ] Test OPB merge with locked vs unlocked dimensions                                  │
│  [ ] Test GatedKarmaInjector blend ratios                                               │
│  [ ] Verify VICReg prevents collapse on synthetic data                                  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### E.6 Validation Summary

| Aspect | Claude Status | Gemini Ruling | Final Status |
|--------|---------------|---------------|--------------|
| State Projector | ✅ Aligned | Upgrade to MLP | ✅ Ready |
| OPB Integration | ⚠️ Gap | Add merge method | ✅ Decided |
| Phase Composition | ✅ Sound | Use DualSourcePhaseProjector | ✅ Ready |
| Cosine Mode | ✅ Supported | JEPA=complex, SRK=shifted | ✅ Ready |
| Training Curriculum | ⚠️ Gap | Body → Soul → Union | ✅ Decided |
| Loss Unification | ⚠️ Partial | Add VICReg | ✅ Decided |
| Karma for Video | ✅ Implicit | Use GatedKarmaInjector | ✅ Ready |
| 32D Shared Space | ✅ Architectural | No change needed | ✅ Ready |
| Alignment Loss (Q1) | ❓ Open | Per-component weighted | ✅ Decided |
| Karma Shape (Q2) | ❓ Open | [B, 32] with gated blend | ✅ Decided |
| Predictor Mode (Q3) | ❓ Open | complex (overruled) | ✅ Decided |

**Conclusion:** All gaps identified, all questions answered. Implementation cleared for execution.

---

## References

1. Meta AI - I-JEPA: Self-Supervised Learning from Images with a Joint-Embedding Predictive Architecture
2. Google Gemini Proposals - 124D Cognitive State Structure (GOOGLE_ARCHITECTURE_PROPOSALS.md)
3. SymbolU Phase Attention Algorithm (PHASE_ATTENTION_ALGORITHM.md)
4. Sovereign Reasoning Kernel Design (SOVEREIGN_REASONING_KERNEL_DESIGN.md)
5. Ontological State-Delta Training (ONTOLOGICAL_STATE_DELTA_DESIGN.md)
6. Bardes et al. - VICReg: Variance-Invariance-Covariance Regularization

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-09 | Initial specification (Language Model focus) |
| 1.1.0 | 2026-01-09 | Added Vision-Language extension (Spec 1-4 from Gemini notes) |
| 1.2.0 | 2026-01-09 | Added Architectural Evolution lineage (Ontological → Geometric) |
| 1.3.0 | 2026-01-09 | Added complete Geometric Masking Training Loop (§17) |
| 1.4.0 | 2026-01-09 | Added Strategic Architecture Philosophy (Appendix C) |
| 1.5.0 | 2026-01-09 | Added Patent-Enhanced Loss Functions (§18) - BCVF, USE, SCC integration |
| 1.6.0 | 2026-01-09 | Added Operational Guide (§19-21) - Stability, Production, Verification |
| 1.7.0 | 2026-01-09 | Added Sovereign AGI Integration Evaluation (Appendix D) - 8 canonical decisions |
| 1.8.0 | 2026-01-09 | Added Cross-Model Validation Dialogue (Appendix E) - Claude/Gemini validation |

---

## Implementation Checklist

### Part I: Language Model (Phase-JEPA)

- [ ] Create `symbolu/jepa/` module directory
- [ ] Implement `PhaseJEPAPredictor` class
- [ ] Implement `TargetEncoder` with EMA
- [ ] Implement `SovereignStateProjector`
- [ ] Implement VICReg loss functions
- [ ] Extend `OntologicalHybridTransformer` with JEPA
- [ ] Add CLI arguments to `train_unified_llm.py`
- [ ] Create unit tests in `symbolu/jepa/tests/`
- [ ] Add benchmark scripts
- [ ] Document in main README

### Part II: Vision-Language Extension (Phase-VL-JEPA)

- [ ] Implement `HybridPhaseBlock` (Spec 1 & 2)
- [ ] Implement `WindowedQuadraticAttention` (Spec 1 & 2)
- [ ] Implement `PhaseAttention` with intent rotation (Spec 1 & 2)
- [ ] Implement `GeometricMaskCollator` (Spec 3)
- [ ] Implement `PhaseSyncLoss` (Spec 4)
- [ ] Implement `SovereignPatentLoss` with BCVF, USE, SCC (§18)
- [ ] Implement `PhaseVLJEPA_System` with EMA (Spec 4)
- [ ] Implement `compute_phase_alignment_score` metric
- [ ] Add rotation-to-text prompt mapping
- [ ] Create vision encoder integration (ViT)
- [ ] Small-scale validation on CIFAR-100/Tiny-ImageNet
- [ ] Success criteria: PAS > 0.6 within 10 epochs

### Part III: Operational & Production (§19-21)

- [ ] Implement `init_phase_layers` initialization function
- [ ] Implement `LossScheduler` for curriculum-based training
- [ ] Add `detect_phase_collapse` diagnostic utility
- [ ] Implement `RealViewComplexOps` for production efficiency
- [ ] Implement `IntentCache` for inference speedup
- [ ] Implement `SafeInference` with Mauna protocol
- [ ] Create `verify_gradients` pre-flight check
- [ ] Create `verify_ema_update` pre-flight check
- [ ] Create `visualize_batch` debugging utility
- [ ] Run full pre-training verification checklist
