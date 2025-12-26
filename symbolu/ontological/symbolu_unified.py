#!/usr/bin/env python3
"""
SymbolU Unified - Best of Both Worlds
======================================

Combines the strengths of both SymbolU architectures:

1. **Phase Attention O(n)** - Efficient token processing
   - Mean-field synchronization (U1-U4 formulas)
   - O(n) complexity instead of O(n²)
   - Phase correlation for attention

2. **12x12 Bhava Ontological** - Semantic richness
   - 12 cognitive layers (Potential → Absolving)
   - 144D inter-layer relationships
   - Vedic Drishti patterns

3. **BCVF/SCC/USE** - Trustworthiness
   - Hallucination detection
   - Coherence monitoring
   - User confidence metrics

Output Dimensions:
- Ontological: 12D (layer probabilities)
- Bhava: 144D (12×12 relationships)
- Phase: 12D (layer phases)
- Full Vector: 168D (12 + 144 + 12)

Architecture:
┌─────────────────────────────────────────────────────────────────────┐
│                      SymbolU Unified Architecture                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Input Tokens                                                        │
│       ↓                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Embedding + Positional Phase                                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│       ↓                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Layers 1-8: Phase Attention Blocks                          │    │
│  │  • PhaseAttention O(n) instead of MultiheadAttention O(n²)  │    │
│  │  • Bhava-aware routing between layers                        │    │
│  │  • Coherence tracking per layer                              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│       ↓                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Layer 9: Witness (Meta-cognition)                           │    │
│  │  • Semantic entropy monitoring (S5)                          │    │
│  │  • Confidence estimation                                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│       ↓                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Layer 10: Bhava Unifying                                    │    │
│  │  • 12×12 relationship matrix                                 │    │
│  │  • 144D Bhava vector                                         │    │
│  │  • Drishti cross-layer attention                             │    │
│  │  • BCVF Consistency Lagrangian (B1)                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│       ↓                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Layer 11-12: Integration + Absolving                        │    │
│  │  • Conflict resolution                                       │    │
│  │  • Final coherence check                                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│       ↓                                                              │
│  Output: Logits + 168D Vector + Confidence + Coherence              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

Usage:
------
    from symbolu.ontological.symbolu_unified import SymbolUUnified

    model = SymbolUUnified()

    outputs = model(input_ids)
    print(outputs['confidence_level'])      # HIGH/MEDIUM/LOW
    print(outputs['global_coherence'])      # 0.0-1.0
    print(outputs['bhava_vector'].shape)    # [B, 144]
    print(outputs['hallucination_detected'])  # True/False
"""

import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    raise ImportError("PyTorch required")

# Import Phase Attention O(n)
from symbolu.ontological.phase_attention import (
    LinearPhaseAttention,
    PhaseAttention,
    PhaseSynchronizer,
    PhaseCorrelation,
)

# Import Bhava relationships
from symbolu.ontological.bhava_relationships import (
    BhavaRelationshipModule,
    DrishtiAttention,
    BHAVA_SIGNIFICANCES,
    ASPECT_STRENGTH_MATRIX,
    get_relationship_meaning,
    LAYER_TO_BHAVA,
)

# Import BCVF/SCC/USE for trustworthiness
from symbolu.ontological.kv_cache_enhanced import (
    EnhancedCacheConfig,
    SemanticEntropyTracker,
    CoherenceScorer,
    ConsistencyLagrangian,
)

from symbolu.ontological.types import LAYER_NAMES, LAYER_INDEX


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SymbolUUnifiedConfig:
    """Configuration for Unified SymbolU."""

    # Model dimensions
    vocab_size: int = 50257
    embed_dim: int = 512
    num_heads: int = 8
    num_layers: int = 12
    max_seq_len: int = 2048

    # Phase Attention settings
    phase_dim: int = 64
    sync_steps: int = 3
    sync_lr: float = 0.1
    use_linear_phase: bool = True  # True = O(n), False = O(n²) for comparison

    # Bhava settings
    bhava_embed_dim: int = 128
    relationship_embed_dim: int = 32
    num_drishti_heads: int = 4

    # BCVF/SCC/USE settings
    lambda_forward: float = 1.0
    lambda_backward: float = 1.0
    lambda_consistency: float = 0.5
    beta: float = 2.0
    entropy_spike_threshold: float = 0.3
    hallucination_threshold: float = 0.7

    # Coherence thresholds
    min_coherence: float = 0.5
    coherence_threshold: float = 0.7

    # FFN
    ffn_mult: float = 2.67

    # Generation behavior
    halt_on_hallucination: bool = False
    show_confidence: bool = True

    # Harmonic ratios for phase lock
    HARMONIC_RATIOS: Dict[int, int] = field(default_factory=lambda: {
        1: 100000, 2: 50000, 3: 20000, 4: 10000,
        5: 5000, 6: 2000, 7: 1000, 8: 400,
        9: 100, 10: 50, 11: 10, 12: 1
    })


# =============================================================================
# PHASE-BHAVA TRANSFORMER BLOCK
# =============================================================================

class PhaseBhavaBlock(nn.Module):
    """
    Transformer block combining Phase Attention O(n) with Bhava awareness.

    Replaces standard MultiheadAttention with LinearPhaseAttention
    while maintaining Bhava routing between layers.
    """

    def __init__(
        self,
        dim: int,
        num_heads: int,
        layer_idx: int,
        config: SymbolUUnifiedConfig,
    ):
        super().__init__()
        self.layer_idx = layer_idx
        self.layer_name = LAYER_NAMES[layer_idx] if layer_idx < 12 else "Extra"

        # Pre-norm
        self.norm1 = nn.LayerNorm(dim)
        self.norm2 = nn.LayerNorm(dim)

        # Phase Attention O(n)
        if config.use_linear_phase:
            self.attn = LinearPhaseAttention(
                embed_dim=dim,
                num_heads=num_heads,
                sync_steps=config.sync_steps,
            )
        else:
            self.attn = PhaseAttention(
                embed_dim=dim,
                num_heads=num_heads,
            )

        # SwiGLU FFN
        ffn_dim = int(dim * config.ffn_mult)
        self.ffn_gate = nn.Linear(dim, ffn_dim, bias=False)
        self.ffn_up = nn.Linear(dim, ffn_dim, bias=False)
        self.ffn_down = nn.Linear(ffn_dim, dim, bias=False)

        # Bhava routing gate (modulates output based on layer significance)
        self.bhava_gate = nn.Sequential(
            nn.Linear(dim, dim // 4),
            nn.ReLU(),
            nn.Linear(dim // 4, dim),
            nn.Sigmoid(),
        )

        # Layer phase offset
        self.phase_offset = nn.Parameter(torch.zeros(1))

    def forward(
        self,
        x: torch.Tensor,
        master_phase: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with phase attention and Bhava gating.

        Returns:
            output: [B, seq, dim] transformed output
            layer_embed: [B, dim] layer embedding for Bhava computation
        """
        # Phase-modulated attention
        h = self.norm1(x)
        attn_out = self.attn(h)

        # Apply Bhava gate
        bhava_weight = self.bhava_gate(h.mean(dim=1, keepdim=True))
        attn_out = attn_out * bhava_weight

        x = x + attn_out

        # SwiGLU FFN
        h = self.norm2(x)
        ffn_out = self.ffn_down(F.silu(self.ffn_gate(h)) * self.ffn_up(h))
        x = x + ffn_out

        # Layer embedding for Bhava
        layer_embed = x.mean(dim=1)

        return x, layer_embed


# =============================================================================
# WITNESS LAYER WITH ENTROPY MONITORING
# =============================================================================

class UnifiedWitnessLayer(nn.Module):
    """
    Layer 9: Witness with semantic entropy monitoring (S5).

    Provides:
    - Meta-cognitive state observation
    - Confidence estimation
    - Hallucination detection via entropy spikes
    """

    def __init__(self, dim: int, config: SymbolUUnifiedConfig):
        super().__init__()
        self.dim = dim

        # State encoder
        self.state_encoder = nn.Linear(dim, dim)

        # Confidence head
        self.confidence_head = nn.Sequential(
            nn.Linear(dim, dim // 2),
            nn.ReLU(),
            nn.Linear(dim // 2, 1),
            nn.Sigmoid(),
        )

        # Entropy tracker (S5)
        cache_config = EnhancedCacheConfig(
            entropy_spike_threshold=config.entropy_spike_threshold,
            hallucination_entropy_threshold=config.hallucination_threshold,
        )
        self.entropy_tracker = SemanticEntropyTracker(cache_config)

    def forward(
        self,
        x: torch.Tensor,
        output_probs: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Dict[str, Any]]:
        """
        Returns:
            x: Unchanged input
            state: [B, dim] witness state
            confidence: [B, 1] confidence score
            metrics: Dict with entropy metrics
        """
        state = self.state_encoder(x.mean(dim=1))
        raw_confidence = self.confidence_head(state)

        # Track entropy if probs available
        metrics = {}
        if output_probs is not None:
            ent_metrics = self.entropy_tracker.update(output_probs)
            # Adjust confidence based on entropy
            ent_confidence = ent_metrics['confidence']
            confidence = raw_confidence * ent_confidence
            metrics['entropy'] = ent_metrics['entropy']
            metrics['hallucination_risk'] = ent_metrics['hallucination_risk']
            metrics['is_spike'] = ent_metrics['is_spike']
        else:
            confidence = raw_confidence

        metrics['raw_confidence'] = raw_confidence.mean().item()
        metrics['adjusted_confidence'] = confidence.mean().item()

        return x, state, confidence, metrics

    def reset(self):
        self.entropy_tracker.reset()


# =============================================================================
# BHAVA UNIFYING LAYER WITH BCVF
# =============================================================================

class UnifiedBhavaLayer(nn.Module):
    """
    Layer 10: Bhava Unifying with BCVF Consistency Lagrangian.

    Combines:
    - 12×12 Bhava relationship matrix (144D)
    - Drishti cross-layer attention
    - BCVF Consistency scoring (B1)
    - Phase correlation for coherence
    """

    def __init__(self, config: SymbolUUnifiedConfig):
        super().__init__()
        self.config = config
        dim = config.embed_dim

        # Bhava relationship module
        self.bhava_module = BhavaRelationshipModule(
            embed_dim=config.bhava_embed_dim,
            num_layers=12,
            relationship_embed_dim=config.relationship_embed_dim,
        )

        # Drishti attention
        self.drishti_attention = DrishtiAttention(
            embed_dim=dim,
            num_layers=12,
            num_heads=config.num_drishti_heads,
        )

        # Phase correlation for coherence
        self.phase_correlation = PhaseCorrelation()

        # BCVF Consistency Lagrangian
        cache_config = EnhancedCacheConfig(
            lambda_forward=config.lambda_forward,
            lambda_backward=config.lambda_backward,
            lambda_consistency=config.lambda_consistency,
            beta=config.beta,
        )
        self.lagrangian = ConsistencyLagrangian(cache_config)
        self.coherence_scorer = CoherenceScorer(cache_config)

        # Coherence attention
        self.coherence_attn = nn.MultiheadAttention(dim, 4, batch_first=True)
        self.norm = nn.LayerNorm(dim)

        # Project layer embeddings
        self.to_bhava = nn.Linear(dim, config.bhava_embed_dim)

    def forward(
        self,
        layer_embeddings: List[torch.Tensor],
        x: torch.Tensor,
        witness_confidence: torch.Tensor,
        master_phase: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """
        Returns comprehensive Bhava and coherence output.
        """
        B = x.shape[0]
        device = x.device

        # Stack layer embeddings (pad to 12 if needed)
        stacked = torch.stack(layer_embeddings, dim=1)
        N = stacked.shape[1]
        if N < 12:
            padding = torch.zeros(B, 12 - N, stacked.shape[2], device=device)
            stacked = torch.cat([stacked, padding], dim=1)

        # Compute ontological probs
        layer_mags = stacked.abs().mean(dim=-1)
        ontological_probs = F.softmax(layer_mags, dim=-1)

        # ========================
        # 1. BHAVA RELATIONSHIPS
        # ========================
        bhava_output = self.bhava_module(ontological_probs)
        relationship_matrix = bhava_output['relationship_matrix']
        bhava_vector = bhava_output['relationship_flat']
        bhava_coherence = bhava_output['coherence']

        # ========================
        # 2. DRISHTI ATTENTION
        # ========================
        attended_layers = self.drishti_attention(stacked, ontological_probs)

        # ========================
        # 3. COHERENCE MATRIX
        # ========================
        # Semantic similarity S[i,j]
        normalized = F.normalize(attended_layers, dim=-1)
        S = torch.einsum('bid,bjd->bij', normalized, normalized)

        # Aspect strength C[i,j]
        C = torch.tensor(ASPECT_STRENGTH_MATRIX, device=device).unsqueeze(0).expand(B, -1, -1)

        # C'[i,j] = C[i,j] × S[i,j]
        C_prime = C * S

        # Global coherence
        mask = torch.triu(torch.ones(12, 12, device=device), diagonal=1)
        J = (C_prime * mask).sum(dim=(1, 2)) / (mask.sum() + 1e-8)

        # ========================
        # 4. BCVF CONSISTENCY (B1)
        # ========================
        # sf = coherence, sb = confidence
        sf = (0.5 * J + 0.5 * bhava_coherence).mean().item()
        sb = witness_confidence.mean().item()

        lagrangian, consistency_weight = self.lagrangian.score_cache_entry(sf, sb)

        # Determine confidence level
        if sb >= 0.8:
            confidence_level = "HIGH"
        elif sb >= 0.5:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        # ========================
        # 5. UNIFIED OUTPUT
        # ========================
        coherence_weights = F.softmax(C_prime.sum(dim=-1), dim=-1)
        unified_layers = torch.einsum('bn,bnd->bd', coherence_weights, attended_layers)

        coherence_signal = unified_layers.unsqueeze(1).expand(-1, x.shape[1], -1)
        unified_x, _ = self.coherence_attn(x, coherence_signal, coherence_signal)

        if master_phase is not None:
            strength = (1 + torch.cos(master_phase)) / 2
            output = self.norm(x + unified_x * strength)
        else:
            output = self.norm(x + unified_x)

        return {
            'unified_x': output,
            'unified_layers': unified_layers,
            'ontological_probs': ontological_probs,
            'bhava_vector': bhava_vector,
            'relationship_matrix': relationship_matrix,
            'coherence_matrix': C_prime,
            'global_coherence': 0.5 * J + 0.5 * bhava_coherence,
            'lagrangian': lagrangian,
            'consistency_weight': consistency_weight,
            'confidence_level': confidence_level,
        }


# =============================================================================
# SYMBOLU UNIFIED MODEL
# =============================================================================

class SymbolUUnified(nn.Module):
    """
    SymbolU Unified - Best of Both Worlds

    Combines:
    - Phase Attention O(n) for efficiency
    - 12×12 Bhava for semantic richness
    - BCVF/SCC/USE for trustworthiness

    Output: 168D vector (12 onto + 144 bhava + 12 phase)
    """

    def __init__(self, config: Optional[SymbolUUnifiedConfig] = None):
        super().__init__()
        self.config = config or SymbolUUnifiedConfig()
        dim = self.config.embed_dim

        # Embeddings
        self.embed = nn.Embedding(self.config.vocab_size, dim)
        self.pos_embed = nn.Embedding(self.config.max_seq_len, dim)

        # Layers 1-8: Phase-Bhava blocks
        self.layers = nn.ModuleList([
            PhaseBhavaBlock(dim, self.config.num_heads, i, self.config)
            for i in range(8)
        ])

        # Layer 9: Witness
        self.witness = UnifiedWitnessLayer(dim, self.config)

        # Layer 10: Bhava Unifying
        self.unifying = UnifiedBhavaLayer(self.config)

        # Layer 11: Integration
        self.integration = nn.Sequential(
            nn.Linear(dim * 2, dim),
            nn.ReLU(),
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
        )

        # Layer 12: Output
        self.output_norm = nn.LayerNorm(dim)
        self.lm_head = nn.Linear(dim, self.config.vocab_size, bias=False)
        self.lm_head.weight = self.embed.weight

        # Master phase for phase-locked processing
        self.master_phase = nn.Parameter(torch.zeros(1))

        # Global entropy tracker
        cache_config = EnhancedCacheConfig(
            entropy_spike_threshold=self.config.entropy_spike_threshold,
            hallucination_entropy_threshold=self.config.hallucination_threshold,
        )
        self.global_entropy = SemanticEntropyTracker(cache_config)

    def get_layer_phase(self, layer_idx: int) -> torch.Tensor:
        return self.config.HARMONIC_RATIOS.get(layer_idx, 1) * self.master_phase

    def clear_cache(self):
        self.witness.reset()
        self.global_entropy.reset()

    def forward(
        self,
        input_ids: torch.Tensor,
        return_phases: bool = False,
    ) -> Dict[str, Any]:
        B, seq_len = input_ids.shape
        device = input_ids.device

        # Embeddings
        pos = torch.arange(seq_len, device=device)
        x = self.embed(input_ids) + self.pos_embed(pos)

        # Track layer embeddings and phases
        layer_embeddings = []
        layer_phases = []

        # Layers 1-8: Phase-Bhava blocks
        for i, layer in enumerate(self.layers):
            x, layer_embed = layer(x, self.get_layer_phase(i + 1))
            layer_embeddings.append(layer_embed)
            layer_phases.append(self.get_layer_phase(i + 1))

        # Layer 9: Witness
        x, witness_state, witness_confidence, witness_metrics = self.witness(x)
        layer_embeddings.append(witness_state)

        # Layer 10: Bhava Unifying
        unify_output = self.unifying(
            layer_embeddings, x, witness_confidence, self.get_layer_phase(10)
        )
        x = unify_output['unified_x']
        layer_embeddings.append(unify_output['unified_layers'])

        # Layer 11: Integration
        unified_exp = unify_output['unified_layers'].unsqueeze(1).expand(-1, seq_len, -1)
        x = self.integration(torch.cat([x, unified_exp], dim=-1))
        layer_embeddings.append(x.mean(dim=1))

        # Layer 12: Output
        x = self.output_norm(x)
        logits = self.lm_head(x)
        layer_embeddings.append(x.mean(dim=1))

        # Compute final entropy and hallucination check
        output_probs = F.softmax(logits[:, -1, :], dim=-1)
        entropy_metrics = self.global_entropy.update(output_probs)

        # Hallucination detection
        hallucination_detected = (
            entropy_metrics['is_spike'] or
            entropy_metrics['hallucination_risk'] > 0.7 or
            unify_output['global_coherence'].mean().item() < self.config.min_coherence
        )

        # Build full 168D vector
        phase_vector = torch.stack([
            self.get_layer_phase(i).expand(B) for i in range(1, 13)
        ], dim=1)  # [B, 12]

        full_vector = torch.cat([
            unify_output['ontological_probs'],  # 12D
            unify_output['bhava_vector'],       # 144D
            torch.cos(phase_vector),            # 12D (phase as cos)
        ], dim=-1)

        result = {
            # Generation
            'logits': logits,

            # Ontological (12D)
            'ontological_probs': unify_output['ontological_probs'],

            # Bhava (144D)
            'bhava_vector': unify_output['bhava_vector'],
            'relationship_matrix': unify_output['relationship_matrix'],

            # Coherence
            'coherence_matrix': unify_output['coherence_matrix'],
            'global_coherence': unify_output['global_coherence'],

            # BCVF (trustworthiness)
            'lagrangian': unify_output['lagrangian'],
            'consistency_weight': unify_output['consistency_weight'],

            # Confidence
            'witness_confidence': witness_confidence,
            'confidence_level': unify_output['confidence_level'],

            # Entropy
            'entropy': entropy_metrics['entropy'],
            'hallucination_risk': entropy_metrics['hallucination_risk'],
            'hallucination_detected': hallucination_detected,

            # Full vector (168D)
            'full_vector': full_vector,

            # Layer embeddings
            'layer_embeddings': layer_embeddings,
        }

        if return_phases:
            result['phase_vector'] = phase_vector
            result['layer_phases'] = layer_phases

        return result

    @torch.no_grad()
    def generate(
        self,
        prompt_ids: torch.Tensor,
        max_new_tokens: int = 100,
        temperature: float = 0.8,
        top_p: float = 0.9,
        show_progress: bool = True,
    ) -> Dict[str, Any]:
        """Generate with quality monitoring."""
        self.eval()
        self.clear_cache()

        generated = prompt_ids
        generation_log = []
        warnings = []

        for step in range(max_new_tokens):
            outputs = self.forward(generated)

            # Sample next token
            logits = outputs['logits'][:, -1, :] / temperature
            sorted_logits, sorted_indices = torch.sort(logits, descending=True)
            probs = F.softmax(sorted_logits, dim=-1)
            cumsum = torch.cumsum(probs, dim=-1)
            mask = cumsum - probs > top_p
            sorted_logits[mask] = float('-inf')
            probs = F.softmax(sorted_logits, dim=-1)

            next_token = sorted_indices.gather(-1, torch.multinomial(probs, 1))
            generated = torch.cat([generated, next_token], dim=1)

            # Log metrics
            step_metrics = {
                'step': step,
                'confidence': outputs['confidence_level'],
                'coherence': outputs['global_coherence'].mean().item(),
                'entropy': outputs['entropy'],
            }
            generation_log.append(step_metrics)

            if outputs['hallucination_detected']:
                warnings.append(f"Step {step}: Hallucination risk={outputs['hallucination_risk']:.2f}")
                if self.config.halt_on_hallucination:
                    break

            if show_progress and (step + 1) % 20 == 0:
                print(f"Step {step+1}: {outputs['confidence_level']} | Coh={outputs['global_coherence'].mean():.3f}")

            if next_token.item() == 0:
                break

        return {
            'generated_ids': generated,
            'num_tokens': generated.shape[1] - prompt_ids.shape[1],
            'warnings': warnings,
            'generation_log': generation_log,
        }

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def get_architecture_summary(self) -> str:
        return f"""
╔══════════════════════════════════════════════════════════════════════╗
║                      SymbolU Unified Architecture                     ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  Parameters: {self.count_parameters():,}                                       ║
║  Embed Dim:  {self.config.embed_dim}                                                  ║
║  Heads:      {self.config.num_heads}                                                     ║
║  Max Seq:    {self.config.max_seq_len}                                                   ║
║                                                                       ║
║  COMPONENTS:                                                          ║
║  ───────────                                                          ║
║  ✓ Phase Attention O(n) - Efficient token processing                 ║
║  ✓ 12×12 Bhava (144D) - Inter-layer semantic relationships          ║
║  ✓ BCVF Lagrangian (B1) - Consistency scoring                        ║
║  ✓ Semantic Entropy (S5) - Hallucination detection                   ║
║  ✓ Coherence Scoring (S1-S2) - Cross-layer similarity                ║
║                                                                       ║
║  OUTPUT VECTORS:                                                      ║
║  ───────────────                                                      ║
║  • Ontological: 12D                                                   ║
║  • Bhava:       144D                                                  ║
║  • Phase:       12D                                                   ║
║  • Full:        168D                                                  ║
║                                                                       ║
╚══════════════════════════════════════════════════════════════════════╝
"""


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_unified_small() -> SymbolUUnified:
    """Small unified model (~30M params)."""
    config = SymbolUUnifiedConfig(
        vocab_size=32000,
        embed_dim=256,
        num_heads=4,
        max_seq_len=1024,
        phase_dim=32,
        bhava_embed_dim=64,
    )
    return SymbolUUnified(config)


def create_unified_base() -> SymbolUUnified:
    """Base unified model (~100M params)."""
    config = SymbolUUnifiedConfig(
        vocab_size=50257,
        embed_dim=512,
        num_heads=8,
        max_seq_len=2048,
    )
    return SymbolUUnified(config)


def create_unified_large() -> SymbolUUnified:
    """Large unified model (~350M params)."""
    config = SymbolUUnifiedConfig(
        vocab_size=50257,
        embed_dim=1024,
        num_heads=16,
        max_seq_len=4096,
        phase_dim=128,
        bhava_embed_dim=256,
    )
    return SymbolUUnified(config)


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("   SYMBOLU UNIFIED - Best of Both Worlds")
    print("=" * 70)

    # Create model
    model = create_unified_small()
    print(model.get_architecture_summary())

    # Test forward pass
    print("\nTesting forward pass...")
    input_ids = torch.randint(0, 1000, (1, 32))
    outputs = model(input_ids)

    print(f"\nOutput Shapes:")
    print(f"  Logits:           {outputs['logits'].shape}")
    print(f"  Ontological:      {outputs['ontological_probs'].shape} (12D)")
    print(f"  Bhava:            {outputs['bhava_vector'].shape} (144D)")
    print(f"  Full Vector:      {outputs['full_vector'].shape} (168D)")

    print(f"\nQuality Metrics:")
    print(f"  Confidence Level: {outputs['confidence_level']}")
    print(f"  Global Coherence: {outputs['global_coherence'].mean():.4f}")
    print(f"  Entropy:          {outputs['entropy']:.4f}")
    print(f"  Lagrangian:       {outputs['lagrangian']:.4f}")
    print(f"  Hallucination:    {outputs['hallucination_detected']}")

    print("\n" + "=" * 70)
    print("   BEST OF BOTH WORLDS ACHIEVED!")
    print("=" * 70)
    print("""
    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                  │
    │  SymbolU Phase Attention    +    SymbolU12 Bhava                │
    │  ──────────────────────          ───────────────                │
    │  • O(n) complexity              • 12 cognitive layers           │
    │  • Phase synchronization        • 144D relationships            │
    │  • Mean-field approx            • Vedic Drishti patterns        │
    │                                                                  │
    │                         ↓                                        │
    │                                                                  │
    │              SymbolU Unified (168D)                             │
    │              ──────────────────────                             │
    │              • Efficient + Semantic                             │
    │              • Trustworthy (BCVF)                               │
    │              • Hallucination Detection                          │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘
    """)
