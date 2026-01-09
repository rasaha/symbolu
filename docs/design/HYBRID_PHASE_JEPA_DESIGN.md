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

## Table of Contents

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
| 1.0.0 | 2026-01-09 | Initial specification |

---

## Implementation Checklist

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
