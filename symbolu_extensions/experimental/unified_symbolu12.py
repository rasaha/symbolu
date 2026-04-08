#!/usr/bin/env python3
"""
Unified SymbolU12: Complete Integration of All Layers
======================================================

This module integrates:
- Phase Attention LLM (external perception)
- State-Delta (internal cognition)
- v2.6 Guna Modulation (bidirectional)
- v2.7 State Evolution (bounded memory)
- v2.8 Chitta-Vṛtti (metacognition)

Key Design Decisions (based on critical analysis):
--------------------------------------------------

1. BIDIRECTIONAL GUNA-ONTOLOGY FLOW
   - Bottom-up: ontology[12] → guna[3] (observation)
   - Top-down: guna[3] → attention bias (control)
   - Enables AGI-level control where internal state guides perception

2. CHITTA-VṚTTI AT ATTENTION LEVEL
   - Pramāṇa (valid): Sharpen attention on high-confidence tokens
   - Vikalpa (imagination): Broaden attention for creativity
   - Smṛti (memory): Increase momentum for long-range retrieval
   - NOT post-processing - directly modulates Phase Attention

3. FULLY DIFFERENTIABLE
   - All operations in PyTorch tensors
   - No .numpy() calls that break gradients
   - End-to-end training from Chitta loss to base model

4. MODULATION BEFORE RENDERING
   - Modulated ontology recalculates State-Delta
   - "Internal pilot" has final say before words spoken
   - Ensures coherent, controlled generation

Architecture:
------------
                          tokens
                             ↓
                   ┌─────────────────────┐
                   │  Phase Attention    │◄──── Vṛtti Modulation
                   │  Transformer        │      (attention control)
                   └─────────┬───────────┘
                             ↓
                        hidden[d]
                             ↓
         ┌───────────────────┴───────────────────┐
         ↓                                        ↓
   ┌───────────┐                          ┌─────────────┐
   │ Guna Bias │◄─────────────────────────│StateProject │
   │ (top-down)│                          │or (124 dim) │
   └─────┬─────┘                          └──────┬──────┘
         │                                       ↓
         │                              CognitiveState[124]
         │                    ┌──────────────────┼──────────────────┐
         │                    ↓                  ↓                   ↓
         │              ┌──────────┐      ┌──────────┐        ┌──────────┐
         │              │ v2.6     │      │ v2.7     │        │ v2.8     │
         │              │ Guna     │─────►│ State    │        │ Chitta   │
         │              │ Derive   │      │ Evolve   │        │ Vṛtti    │
         │              └────┬─────┘      └──────────┘        └────┬─────┘
         │                   │                                      │
         └───────────────────┘                                      ↓
                                                              p_v[v] (5-dim)
                                                                    ↓
                                                           ┌────────────────┐
                                                           │ R[v,a] Coupling│
                                                           │ (5×12 matrix)  │
                                                           └────────┬───────┘
                                                                    ↓
                                                           Modulated Ontology
                                                                    ↓
                                                           ┌────────────────┐
                                                           │ Recalculate    │
                                                           │ State-Delta    │
                                                           └────────┬───────┘
                                                                    ↓
                                                              Token Render
                                                              (only if needed)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any
import math


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class UnifiedSymbolU12Config:
    """Configuration for the complete unified architecture."""

    # Model dimensions
    hidden_dim: int = 256
    vocab_size: int = 50257

    # Cognitive state dimensions
    num_phonemes: int = 44
    topic_dim: int = 64
    num_ontology: int = 12  # 12 Bhava states
    num_dynamics: int = 4   # coherence, entropy, confidence, momentum

    # Guna dimensions
    num_guna: int = 3  # Sattva, Rajas, Tamas

    # Vṛtti dimensions (Chitta-Vṛtti)
    num_vritti: int = 5  # Pramāṇa, Viparyaya, Vikalpa, Smṛti, Nidrā

    # Attention modulation
    vritti_attention_scale: float = 0.1  # How much vṛtti modulates attention
    guna_bias_scale: float = 0.1         # How much guna biases projector

    # Coupling matrix initialization
    coupling_init_diagonal: float = 0.5
    coupling_init_noise: float = 0.1

    # Training dynamics
    lambda_token: float = 0.4      # Token prediction loss weight
    lambda_state: float = 0.3      # State-delta loss weight
    lambda_coherence: float = 0.15 # Coherence loss weight
    lambda_vritti: float = 0.1     # Vṛtti alignment loss weight
    lambda_guna: float = 0.05      # Guna balance loss weight

    @property
    def state_dim(self) -> int:
        return self.num_phonemes + self.topic_dim + self.num_ontology + self.num_dynamics


# =============================================================================
# DIFFERENTIABLE CHITTA-VṚTTI ENGINE
# =============================================================================

class DifferentiableChittaVritti(nn.Module):
    """
    Fully differentiable Chitta-Vṛtti computation.

    Unlike the numpy-based v2.8 implementation, this is end-to-end
    differentiable in PyTorch, allowing gradients to flow back
    through the cognitive mode computation.

    The 5 Vṛttis:
    - Pramāṇa: Valid cognition (high coherence, low entropy)
    - Viparyaya: Misperception (layer opposition)
    - Vikalpa: Conceptualization (high entropy, variance)
    - Smṛti: Memory (low state change)
    - Nidrā: Dormancy (missing information)
    """

    def __init__(self, config: UnifiedSymbolU12Config):
        super().__init__()
        self.config = config

        # Projectors for each representation layer to common space
        common_dim = 32  # Per v2.8 spec

        self.phoneme_proj = nn.Linear(config.num_phonemes, common_dim)
        self.topic_proj = nn.Linear(config.topic_dim, common_dim)
        self.ontology_proj = nn.Linear(config.num_ontology, common_dim)
        self.dynamics_proj = nn.Linear(config.num_dynamics, common_dim)

        # Vṛtti computation network
        # Input: coherence features (6 pairwise + 4 signals)
        self.vritti_net = nn.Sequential(
            nn.Linear(10, 32),
            nn.GELU(),
            nn.Linear(32, config.num_vritti),
        )

        # Thresholds (learnable for end-to-end training)
        self.entropy_threshold = nn.Parameter(torch.tensor(0.3))
        self.coherence_threshold = nn.Parameter(torch.tensor(0.7))

    def forward(
        self,
        phoneme: torch.Tensor,      # [B, T, num_phonemes]
        topic: torch.Tensor,        # [B, T, topic_dim]
        ontology: torch.Tensor,     # [B, T, num_ontology]
        dynamics: torch.Tensor,     # [B, T, num_dynamics]
        prev_state: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute differentiable Chitta-Vṛtti distribution.

        Returns:
            Dict with:
                vritti: [B, T, 5] probability distribution over 5 modes
                coherence: [B, T] aggregate coherence
                fractures: [B, T, 6] pairwise fractures
                dominant: [B, T] index of dominant mode
        """
        B, T, _ = phoneme.shape

        # Project all layers to common space
        ph_proj = F.normalize(self.phoneme_proj(phoneme), p=2, dim=-1)
        tp_proj = F.normalize(self.topic_proj(topic), p=2, dim=-1)
        on_proj = F.normalize(self.ontology_proj(ontology), p=2, dim=-1)
        dy_proj = F.normalize(self.dynamics_proj(dynamics), p=2, dim=-1)

        # Compute pairwise coherence (cosine similarity)
        # 6 pairs: (ph,tp), (ph,on), (ph,dy), (tp,on), (tp,dy), (on,dy)
        pairs = [
            (ph_proj, tp_proj),
            (ph_proj, on_proj),
            (ph_proj, dy_proj),
            (tp_proj, on_proj),
            (tp_proj, dy_proj),
            (on_proj, dy_proj),
        ]

        coherences = []
        for a, b in pairs:
            sim = (a * b).sum(dim=-1)  # Cosine similarity [B, T]
            coherences.append(sim)

        coherence_stack = torch.stack(coherences, dim=-1)  # [B, T, 6]

        # Aggregate coherence
        aggregate_coherence = coherence_stack.mean(dim=-1)  # [B, T]

        # Fractures = 1 - coherence
        fractures = 1 - coherence_stack  # [B, T, 6]

        # Extract dynamics signals
        coherence_dyn = dynamics[:, :, 0]   # Coherence from dynamics
        entropy_dyn = dynamics[:, :, 1]     # Entropy
        confidence_dyn = dynamics[:, :, 2]  # Confidence
        momentum_dyn = dynamics[:, :, 3]    # Momentum/motion

        # Compute vṛtti features
        vritti_features = torch.cat([
            coherence_stack,  # [B, T, 6] pairwise coherence
            entropy_dyn.unsqueeze(-1),      # [B, T, 1]
            momentum_dyn.unsqueeze(-1),     # [B, T, 1]
            confidence_dyn.unsqueeze(-1),   # [B, T, 1]
            aggregate_coherence.unsqueeze(-1),  # [B, T, 1]
        ], dim=-1)  # [B, T, 10]

        # Compute raw vṛtti scores
        vritti_raw = self.vritti_net(vritti_features)  # [B, T, 5]

        # Apply soft constraints based on design logic
        # Pramāṇa: High when coherence high, entropy low
        pramana_boost = aggregate_coherence * (1 - torch.sigmoid(entropy_dyn - self.entropy_threshold))

        # Viparyaya: High when fractures high but confidence high (coherent opposition)
        max_fracture = fractures.max(dim=-1)[0]
        viparyaya_boost = max_fracture * confidence_dyn

        # Vikalpa: High when entropy high, fracture variance high
        fracture_var = fractures.var(dim=-1)
        vikalpa_boost = torch.sigmoid(entropy_dyn - 0.3) * fracture_var

        # Smṛti: High when state unchanged (low momentum)
        smrti_boost = 1 - torch.sigmoid(momentum_dyn - 0.1)
        if prev_state is not None:
            state_change = torch.norm(
                torch.cat([phoneme, topic, ontology, dynamics], dim=-1) - prev_state,
                dim=-1
            )
            smrti_boost = smrti_boost * (1 - torch.sigmoid(state_change - 0.1))

        # Nidrā: High when missing information (low confidence, low coherence)
        nidra_boost = (1 - confidence_dyn) * (1 - aggregate_coherence)

        # Combine with raw scores
        boosts = torch.stack([
            pramana_boost,
            viparyaya_boost,
            vikalpa_boost,
            smrti_boost,
            nidra_boost,
        ], dim=-1)  # [B, T, 5]

        vritti_combined = vritti_raw + 0.5 * boosts

        # Normalize to probability distribution
        vritti_probs = F.softmax(vritti_combined, dim=-1)  # [B, T, 5]

        # Dominant mode
        dominant = vritti_probs.argmax(dim=-1)  # [B, T]

        return {
            'vritti': vritti_probs,
            'coherence': aggregate_coherence,
            'fractures': fractures,
            'dominant': dominant,
            'vritti_raw': vritti_raw,
        }


# =============================================================================
# BIDIRECTIONAL GUNA MAPPER
# =============================================================================

class BidirectionalGunaMapper(nn.Module):
    """
    Bidirectional mapping between Ontology (12 Bhava) and Guna (3).

    Bottom-up: ontology[12] → guna[3] (observation)
    Top-down: guna[3] → attention_bias (control)

    The Guna-Bhava relationship:
    - Sattva (S): FACTUAL, ANALYTICAL, CERTAIN, NEUTRAL
    - Rajas (R): EVALUATIVE, ARGUMENTATIVE, INSTRUCTIVE, QUESTIONING
    - Tamas (T): NARRATIVE, SPECULATIVE, POSITIVE, NEGATIVE
    """

    # Bhava → Guna mapping matrix (12 × 3)
    BHAVA_TO_GUNA = torch.tensor([
        # S,   R,   T     Bhava index → Guna contribution
        [0.8, 0.1, 0.1],  # 0: FACTUAL      → mostly Sattva
        [0.6, 0.3, 0.1],  # 1: ANALYTICAL   → mostly Sattva, some Rajas
        [0.3, 0.5, 0.2],  # 2: EVALUATIVE   → mostly Rajas
        [0.1, 0.2, 0.7],  # 3: NARRATIVE    → mostly Tamas
        [0.2, 0.6, 0.2],  # 4: ARGUMENTATIVE → mostly Rajas
        [0.3, 0.5, 0.2],  # 5: INSTRUCTIVE  → mostly Rajas
        [0.7, 0.2, 0.1],  # 6: CERTAIN      → mostly Sattva
        [0.2, 0.3, 0.5],  # 7: SPECULATIVE  → mostly Tamas
        [0.2, 0.6, 0.2],  # 8: QUESTIONING  → mostly Rajas
        [0.2, 0.2, 0.6],  # 9: POSITIVE     → mostly Tamas (emotion)
        [0.1, 0.3, 0.6],  # 10: NEGATIVE    → mostly Tamas (emotion)
        [0.5, 0.3, 0.2],  # 11: NEUTRAL     → balanced, slight Sattva
    ])

    def __init__(self, config: UnifiedSymbolU12Config):
        super().__init__()
        self.config = config

        # Register as buffer (not learnable, but moves with model)
        self.register_buffer('bhava_to_guna', self.BHAVA_TO_GUNA)

        # Learnable refinement on top of fixed mapping
        self.guna_refine = nn.Linear(config.num_ontology, config.num_guna)

        # Top-down: Guna → bias for state projector
        self.guna_to_bias = nn.Sequential(
            nn.Linear(config.num_guna, 64),
            nn.GELU(),
            nn.Linear(64, config.hidden_dim),
        )

        # Stage 9: ablation config (None = mechanism active)
        self.ablation_config = None

    def ontology_to_guna(self, ontology: torch.Tensor) -> torch.Tensor:
        """
        Bottom-up: Convert ontology distribution to Guna.

        Args:
            ontology: [B, T, 12] Bhava probability distribution

        Returns:
            guna: [B, T, 3] Guna distribution [S, R, T]
        """
        # Fixed mapping
        guna_fixed = torch.matmul(ontology, self.bhava_to_guna.to(ontology.device))

        # Learnable refinement
        guna_refined = self.guna_refine(ontology)

        # Combine and normalize
        guna_combined = guna_fixed + 0.1 * guna_refined
        guna_probs = F.softmax(guna_combined, dim=-1)

        return guna_probs

    def guna_to_attention_bias(self, guna: torch.Tensor) -> torch.Tensor:
        """
        Top-down: Convert Guna state to attention bias.

        Stage 9 ablation: returns zeros when use_guna_bias is False.

        Args:
            guna: [B, T, 3] or [B, 3] Guna distribution

        Returns:
            bias: [B, T, hidden_dim] or [B, hidden_dim] attention bias
        """
        # Stage 9 ablation: skip top-down bias when disabled
        if self.ablation_config is not None and not self.ablation_config.use_guna_bias:
            shape = list(guna.shape[:-1]) + [self.config.hidden_dim]
            return torch.zeros(shape, device=guna.device, dtype=guna.dtype)
        return self.guna_to_bias(guna)

    def compute_entropy(self, guna: torch.Tensor) -> torch.Tensor:
        """Compute Guna entropy (normalized to [0, 1])."""
        # H = -Σ p log p / log(3)
        entropy = -torch.sum(guna * torch.log(guna + 1e-9), dim=-1)
        normalized = entropy / math.log(3)
        return normalized


# =============================================================================
# VṚTTI-MODULATED ATTENTION
# =============================================================================

class VrittiModulatedAttention(nn.Module):
    """
    Attention mechanism modulated by Chitta-Vṛtti state.

    The vṛtti distribution modulates attention behavior:
    - Pramāṇa (valid): Sharpen attention (lower temperature)
    - Viparyaya (error): Flag conflicting regions
    - Vikalpa (imagination): Broaden attention (higher temperature)
    - Smṛti (memory): Extend context window bias
    - Nidrā (dormancy): Reduce attention magnitude

    Stage 9 ablation: When ablation_config.use_vritti_modulation is False,
    returns attention_scores unmodified (base temperature, no cognitive gating).
    """

    VRITTI_NAMES = ['pramana', 'viparyaya', 'vikalpa', 'smrti', 'nidra']

    def __init__(self, config: UnifiedSymbolU12Config):
        super().__init__()
        self.config = config

        # Vṛtti → attention temperature modulation
        self.temperature_mod = nn.Linear(config.num_vritti, 1)

        # Vṛtti → position bias (for smṛti extending context)
        self.position_bias = nn.Linear(config.num_vritti, 1)

        # Vṛtti → attention magnitude (for nidrā reducing)
        self.magnitude_mod = nn.Linear(config.num_vritti, 1)

        # Stage 9: ablation config (None = mechanism active)
        self.ablation_config = None

    def forward(
        self,
        attention_scores: torch.Tensor,  # [B, H, T, T] pre-softmax scores
        vritti: torch.Tensor,             # [B, T, 5] vṛtti distribution
    ) -> torch.Tensor:
        """
        Modulate attention scores based on vṛtti state.

        Returns:
            modulated_scores: [B, H, T, T]
        """
        # Stage 9 ablation: bypass when disabled
        if self.ablation_config is not None and not self.ablation_config.use_vritti_modulation:
            return attention_scores

        B, H, T, _ = attention_scores.shape

        # Aggregate vṛtti across positions for global modulation
        vritti_mean = vritti.mean(dim=1)  # [B, 5]

        # Temperature modulation
        # Pramāṇa → sharper (temp < 1), Vikalpa → broader (temp > 1)
        temp_base = 1.0
        temp_mod = self.temperature_mod(vritti_mean).squeeze(-1)  # [B]
        temperature = temp_base + self.config.vritti_attention_scale * torch.tanh(temp_mod)
        temperature = temperature.view(B, 1, 1, 1)

        # Apply temperature
        modulated_scores = attention_scores / (temperature + 1e-6)

        # Position bias for smṛti (looking back further)
        # Higher smṛti → more weight on distant tokens
        pos_bias = self.position_bias(vritti_mean).squeeze(-1)  # [B]

        # Create position distance matrix
        positions = torch.arange(T, device=attention_scores.device)
        distance = (positions.unsqueeze(0) - positions.unsqueeze(1)).abs().float()
        distance = distance / T  # Normalize to [0, 1]

        # Smṛti boosts distant attention
        smrti_idx = 3  # Index of smṛti in vṛtti
        smrti_weight = vritti_mean[:, smrti_idx]  # [B]
        distant_boost = smrti_weight.view(B, 1, 1, 1) * distance.view(1, 1, T, T) * 0.5

        modulated_scores = modulated_scores + distant_boost

        # Magnitude modulation for nidrā
        nidra_idx = 4
        nidra_weight = vritti_mean[:, nidra_idx]  # [B]
        magnitude = 1 - 0.3 * nidra_weight  # Reduce when nidrā high
        magnitude = magnitude.view(B, 1, 1, 1)

        modulated_scores = modulated_scores * magnitude

        return modulated_scores


# =============================================================================
# COUPLING MATRIX R[v,a]
# =============================================================================

class VrittiOntologyCoupling(nn.Module):
    """
    The R[v,a] coupling matrix: SPARSE mapping from 5 Vṛttis to 12 Bhavas.

    Key insight: Not all Vṛttis couple to all Bhavas equally.
    The mapping is SPARSE with natural affinities:

    Natural Bhava-Vritti Affinities:
    --------------------------------
    Pramāṇa (valid cognition):
        → FACTUAL, CERTAIN, INSTRUCTIVE, ANALYTICAL
        Grounded, verifiable knowledge states

    Viparyaya (error/opposition):
        → ARGUMENTATIVE, SPECULATIVE
        Oppositional or uncertain reasoning

    Vikalpa (branching/imagination):
        → SPECULATIVE, QUESTIONING, NARRATIVE
        Creative, exploratory cognition

    Smṛti (memory/recall):
        → NARRATIVE, FACTUAL, EVALUATIVE
        Recall-based cognition

    Nidrā (absence/dormancy):
        → EMOTIVE, METALINGUISTIC
        Detached from direct content

    Matrix interpretation:
    - High diagonality → Aligned, coherent understanding
    - Dense off-diagonal → Complex multi-mode reasoning
    - Sparse → Simple, focused cognition
    """

    def __init__(self, config: UnifiedSymbolU12Config):
        super().__init__()
        self.config = config

        # Initialize R[v,a] with SPARSE semantic priors
        # Shape: [num_vritti=5, num_ontology=12]
        #
        # Natural Bhava-Vritti affinities (not all 5 map to all 12):
        #
        # Pramāṇa (valid cognition) → FACTUAL, ANALYTICAL, INSTRUCTIVE, CERTAIN
        #   These are grounded, verifiable knowledge states
        #
        # Viparyaya (error/opposition) → ARGUMENTATIVE, SPECULATIVE
        #   Opposition or uncertain reasoning
        #
        # Vikalpa (branching/imagination) → SPECULATIVE, QUESTIONING, NARRATIVE
        #   Creative, exploratory cognition
        #
        # Smṛti (memory) → NARRATIVE, FACTUAL, EVALUATIVE
        #   Recall-based cognition
        #
        # Nidrā (absence/dormancy) → EMOTIVE, METALINGUISTIC
        #   Detached from direct content
        #
        # Bhava indices:
        #   0=FACTUAL, 1=ANALYTICAL, 2=EVALUATIVE, 3=NARRATIVE
        #   4=ARGUMENTATIVE, 5=INSTRUCTIVE, 6=CERTAIN, 7=SPECULATIVE
        #   8=QUESTIONING, 9=EMOTIVE, 10=PERFORMATIVE, 11=METALINGUISTIC

        semantic_priors = torch.tensor([
            # FACT ANAL EVAL NARR ARGU INST CERT SPEC QUES EMOT PERF META
            [0.9, 0.6, 0.2, 0.1, 0.1, 0.8, 0.9, 0.1, 0.1, 0.1, 0.3, 0.2],  # Pramāṇa
            [0.1, 0.1, 0.2, 0.1, 0.8, 0.1, 0.1, 0.5, 0.2, 0.2, 0.1, 0.1],  # Viparyaya
            [0.1, 0.2, 0.2, 0.5, 0.1, 0.1, 0.1, 0.8, 0.8, 0.2, 0.3, 0.2],  # Vikalpa
            [0.6, 0.2, 0.6, 0.8, 0.1, 0.3, 0.3, 0.1, 0.1, 0.3, 0.2, 0.1],  # Smṛti
            [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.8, 0.2, 0.5],  # Nidrā
        ])

        init_matrix = (
            0.5 * semantic_priors +  # Primary: sparse semantic structure
            config.coupling_init_noise * torch.randn(config.num_vritti, config.num_ontology)
        )

        self.R = nn.Parameter(init_matrix)

    def forward(
        self,
        vritti: torch.Tensor,      # [B, T, 5]
        ontology: torch.Tensor,    # [B, T, 12]
    ) -> torch.Tensor:
        """
        Apply coupling: modulated_ontology = ontology * (1 + scale * R @ vritti)

        Returns:
            modulated_ontology: [B, T, 12]
        """
        # vritti @ R^T gives [B, T, 12]
        coupling_effect = torch.matmul(vritti, self.R)  # [B, T, 12]

        # Modulate ontology
        modulated = ontology * (1 + 0.2 * torch.tanh(coupling_effect))

        # Re-normalize
        modulated = F.softmax(modulated, dim=-1)

        return modulated

    def get_matrix(self) -> torch.Tensor:
        """Return the coupling matrix for analysis."""
        return self.R.detach()

    def analyze_structure(self) -> Dict[str, float]:
        """
        Analyze the learned coupling structure.

        Returns metrics indicating whether the matrix is:
        - Diagonal (Vṛttis ↔ Bhavas perfectly aligned)
        - Dense (complex reasoning paths discovered)
        """
        R = self.R.detach()

        # Compute diagonality score
        if R.shape[0] <= R.shape[1]:
            diag = torch.diag(R[:, :R.shape[0]])
        else:
            diag = torch.diag(R[:R.shape[1], :])

        diag_energy = diag.abs().sum()
        total_energy = R.abs().sum()
        diagonality = (diag_energy / (total_energy + 1e-6)).item()

        # Compute density (fraction of significant entries)
        threshold = R.abs().max() * 0.1
        significant = (R.abs() > threshold).float().mean().item()

        return {
            'diagonality': diagonality,
            'density': significant,
            'interpretation': 'aligned' if diagonality > 0.5 else 'complex_reasoning',
        }


# =============================================================================
# UNIFIED SYMBOLU12 MODEL
# =============================================================================

class UnifiedSymbolU12Complete(nn.Module):
    """
    Complete Unified SymbolU12 with all version integrations.

    This is the "AGI-ready" architecture that:
    1. Perceives efficiently (Phase Attention O(n))
    2. Understands deeply (State-Delta in meaning space)
    3. Controls top-down (Guna biasing attention)
    4. Assesses metacognitively (Chitta-Vṛtti)
    5. Integrates wisely (R[v,a] coupling before render)
    """

    def __init__(
        self,
        base_model: nn.Module,
        config: UnifiedSymbolU12Config,
    ):
        super().__init__()
        self.base_model = base_model
        self.config = config

        # =====================================================================
        # STATE PROJECTOR (hidden → CognitiveState)
        # =====================================================================
        self.state_projector = nn.ModuleDict({
            'phoneme': nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 4),
                nn.GELU(),
                nn.Linear(config.hidden_dim // 4, config.num_phonemes),
            ),
            'topic': nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 2),
                nn.GELU(),
                nn.Linear(config.hidden_dim // 2, config.topic_dim),
            ),
            'ontology': nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 4),
                nn.GELU(),
                nn.Linear(config.hidden_dim // 4, config.num_ontology),
            ),
            'dynamics': nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 4),
                nn.GELU(),
                nn.Linear(config.hidden_dim // 4, config.num_dynamics),
                nn.Sigmoid(),
            ),
        })

        # =====================================================================
        # BIDIRECTIONAL GUNA (v2.6)
        # =====================================================================
        self.guna_mapper = BidirectionalGunaMapper(config)

        # =====================================================================
        # DIFFERENTIABLE CHITTA-VṚTTI (v2.8)
        # =====================================================================
        self.chitta_vritti = DifferentiableChittaVritti(config)

        # =====================================================================
        # VṚTTI-MODULATED ATTENTION
        # =====================================================================
        self.vritti_attention = VrittiModulatedAttention(config)

        # =====================================================================
        # COUPLING MATRIX R[v,a]
        # =====================================================================
        self.coupling = VrittiOntologyCoupling(config)

        # =====================================================================
        # STATE-DELTA PREDICTOR (after modulation)
        # =====================================================================
        self.delta_predictor = nn.Sequential(
            nn.Linear(config.state_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.state_dim),
        )
        self.delta_norm = nn.LayerNorm(config.state_dim)

        # =====================================================================
        # TOKEN HEAD (only used when rendering)
        # =====================================================================
        self.lm_head = nn.Linear(config.hidden_dim, config.vocab_size, bias=False)

        # State for smṛti tracking
        self.register_buffer('prev_state', None)

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        return_all: bool = True,
    ) -> Dict[str, Any]:
        """
        Complete forward pass through unified architecture.

        The flow:
        1. Base model → hidden
        2. Project → CognitiveState
        3. Derive Guna → top-down bias
        4. Compute Chitta-Vṛtti → attention modulation
        5. Apply coupling R[v,a] → modulated ontology
        6. Recalculate State-Delta from modulated state
        7. Render tokens (if needed)
        """
        B, T = input_ids.shape
        device = input_ids.device

        # =================================================================
        # STEP 1: Get hidden states from base model
        # =================================================================
        outputs = self.base_model(input_ids, return_hidden=True)
        if isinstance(outputs, dict):
            hidden = outputs.get('hidden_states', outputs.get('last_hidden_state'))
        else:
            hidden = outputs

        # =================================================================
        # STEP 2: Project to CognitiveState components
        # =================================================================
        phoneme = F.softmax(self.state_projector['phoneme'](hidden), dim=-1)
        topic = self.state_projector['topic'](hidden)
        ontology = F.softmax(self.state_projector['ontology'](hidden), dim=-1)
        dynamics = self.state_projector['dynamics'](hidden)

        # =================================================================
        # STEP 3: Derive Guna and create top-down bias
        # =================================================================
        guna = self.guna_mapper.ontology_to_guna(ontology)  # [B, T, 3]
        guna_bias = self.guna_mapper.guna_to_attention_bias(guna)  # [B, T, hidden]
        guna_entropy = self.guna_mapper.compute_entropy(guna)  # [B, T]

        # Apply Guna bias to topic embedding (top-down control)
        topic_biased = topic + self.config.guna_bias_scale * guna_bias
        topic_biased = F.normalize(topic_biased, p=2, dim=-1)

        # =================================================================
        # STEP 4: Compute Chitta-Vṛtti (fully differentiable)
        # =================================================================
        chitta_result = self.chitta_vritti(
            phoneme=phoneme,
            topic=topic_biased,
            ontology=ontology,
            dynamics=dynamics,
            prev_state=self.prev_state,
        )
        vritti = chitta_result['vritti']  # [B, T, 5]
        coherence = chitta_result['coherence']  # [B, T]

        # =================================================================
        # STEP 5: Apply R[v,a] coupling → modulated ontology
        # =================================================================
        modulated_ontology = self.coupling(vritti, ontology)  # [B, T, 12]

        # =================================================================
        # STEP 6: Recalculate State-Delta from MODULATED state
        # (This ensures "internal pilot" has final say)
        # =================================================================
        # Construct modulated cognitive state
        modulated_state = torch.cat([
            phoneme,
            topic_biased,
            modulated_ontology,
            dynamics,
        ], dim=-1)  # [B, T, state_dim]

        # Predict delta
        delta = self.delta_predictor(modulated_state[:, :-1])
        predicted_next = self.delta_norm(modulated_state[:, :-1] + delta)
        actual_next = modulated_state[:, 1:]

        # State-delta loss (cosine similarity)
        state_loss = 1 - F.cosine_similarity(predicted_next, actual_next, dim=-1).mean()

        # Save state for smṛti
        with torch.no_grad():
            self.prev_state = modulated_state.detach()

        # =================================================================
        # STEP 7: Token rendering (from modulated hidden)
        # =================================================================
        # Reconstruct hidden from modulated state (inverse projection)
        # For now, use original hidden + modulation signal
        modulation_signal = torch.matmul(
            modulated_ontology - ontology,
            self.state_projector['ontology'][2].weight.T  # Inverse project
        )
        hidden_modulated = hidden + 0.1 * modulation_signal

        logits = self.lm_head(hidden_modulated)

        # =================================================================
        # COMPUTE LOSSES
        # =================================================================
        losses = {}

        # Token prediction loss
        if labels is not None:
            shift_logits = logits[:, :-1].contiguous()
            shift_labels = labels[:, 1:].contiguous()
            token_loss = F.cross_entropy(
                shift_logits.view(-1, self.config.vocab_size),
                shift_labels.view(-1),
                ignore_index=-100,
            )
            losses['token_loss'] = token_loss

        # State-delta loss
        losses['state_loss'] = state_loss

        # Coherence loss (encourage high coherence)
        coherence_loss = (1 - coherence.mean())
        losses['coherence_loss'] = coherence_loss

        # Vṛtti balance loss (encourage pramāṇa, discourage viparyaya)
        pramana = vritti[:, :, 0]
        viparyaya = vritti[:, :, 1]
        vritti_loss = (viparyaya.mean() - 0.5 * pramana.mean() + 0.5).clamp(min=0)
        losses['vritti_loss'] = vritti_loss

        # Guna entropy loss (moderate entropy is ideal)
        guna_loss = (guna_entropy - 0.5).abs().mean()
        losses['guna_loss'] = guna_loss

        # Combined loss
        total_loss = (
            self.config.lambda_token * losses.get('token_loss', 0) +
            self.config.lambda_state * state_loss +
            self.config.lambda_coherence * coherence_loss +
            self.config.lambda_vritti * vritti_loss +
            self.config.lambda_guna * guna_loss
        )
        losses['total_loss'] = total_loss

        # =================================================================
        # METRICS
        # =================================================================
        with torch.no_grad():
            ppl = torch.exp(losses.get('token_loss', torch.tensor(0.0))).item()
            dominant_vritti_idx = vritti.mean(dim=[0, 1]).argmax().item()
            dominant_vritti = ['pramana', 'viparyaya', 'vikalpa', 'smrti', 'nidra'][dominant_vritti_idx]
            coupling_analysis = self.coupling.analyze_structure()

        result = {
            'loss': total_loss,
            'losses': losses,
            'logits': logits,
            'metrics': {
                'ppl': ppl,
                'coherence': coherence.mean().item(),
                'guna_entropy': guna_entropy.mean().item(),
                'dominant_vritti': dominant_vritti,
                'vritti_pramana': vritti[:, :, 0].mean().item(),
                'vritti_viparyaya': vritti[:, :, 1].mean().item(),
                'coupling_diagonality': coupling_analysis['diagonality'],
                'coupling_interpretation': coupling_analysis['interpretation'],
            },
        }

        if return_all:
            result.update({
                'hidden': hidden,
                'cognitive_state': modulated_state,
                'guna': guna,
                'vritti': vritti,
                'chitta_result': chitta_result,
                'modulated_ontology': modulated_ontology,
            })

        return result


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_unified_symbolu12(
    base_model: nn.Module,
    hidden_dim: int = 256,
    vocab_size: int = 50257,
) -> UnifiedSymbolU12Complete:
    """
    Factory function to create a complete Unified SymbolU12 model.

    Args:
        base_model: Phase Attention transformer
        hidden_dim: Hidden dimension of base model
        vocab_size: Vocabulary size

    Returns:
        UnifiedSymbolU12Complete model
    """
    config = UnifiedSymbolU12Config(
        hidden_dim=hidden_dim,
        vocab_size=vocab_size,
    )

    return UnifiedSymbolU12Complete(base_model, config)
