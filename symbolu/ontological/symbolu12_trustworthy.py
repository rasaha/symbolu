#!/usr/bin/env python3
"""
SymbolU12 Trustworthy - Patent-Enhanced LLM
============================================

Combines SymbolU12 with enhanced KV cache using patent formulas:
- BCVF (B1-B5): Bidirectional Consistency Verification
- SCC (S1-S3): Semantic Coherence Checking
- USE (S5): User Semantic Entropy for confidence

Key Features:
1. Hallucination detection during generation
2. Real-time confidence indicators
3. Coherence-based cache pruning
4. User-friendly quality reports

This is the "trustworthy" variant that prioritizes generation
quality and user transparency over raw speed.
"""

import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    raise ImportError("PyTorch required")

from symbolu.ontological.kv_cache_enhanced import (
    EnhancedCacheConfig,
    EnhancedKVCache,
    PatentEnhancedAttention,
    SemanticEntropyTracker,
    CoherenceScorer,
    ConsistencyLagrangian,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SymbolU12TrustworthyConfig:
    """Configuration for trustworthy SymbolU12."""

    # Model dimensions
    vocab_size: int = 32000
    embed_dim: int = 512
    num_heads: int = 8
    num_layers: int = 12
    max_seq_len: int = 2048

    # Patent formula weights
    lambda_forward: float = 1.0
    lambda_backward: float = 1.0
    lambda_consistency: float = 0.5
    beta: float = 2.0

    # Hallucination detection
    entropy_spike_threshold: float = 0.3
    hallucination_threshold: float = 0.7

    # Coherence thresholds
    min_coherence: float = 0.5

    # Generation behavior
    halt_on_hallucination: bool = False
    show_confidence: bool = True
    prune_low_quality: bool = True

    # FFN
    ffn_mult: float = 2.67  # SwiGLU style


# =============================================================================
# TRUSTWORTHY LAYERS
# =============================================================================

class TrustworthyTransformerBlock(nn.Module):
    """
    Transformer block with patent-enhanced attention.

    Monitors coherence and entropy for each layer.
    """

    def __init__(
        self,
        dim: int,
        num_heads: int,
        layer_idx: int,
        config: SymbolU12TrustworthyConfig
    ):
        super().__init__()
        self.layer_idx = layer_idx

        # Pre-norm
        self.norm1 = nn.RMSNorm(dim)
        self.norm2 = nn.RMSNorm(dim)

        # Patent-enhanced attention
        cache_config = EnhancedCacheConfig(
            max_seq_len=config.max_seq_len,
            lambda_forward=config.lambda_forward,
            lambda_backward=config.lambda_backward,
            lambda_consistency=config.lambda_consistency,
            beta=config.beta,
            entropy_spike_threshold=config.entropy_spike_threshold,
            hallucination_entropy_threshold=config.hallucination_threshold,
            min_coherence_for_cache=config.min_coherence,
            enable_consistency_pruning=config.prune_low_quality,
        )
        self.attn = PatentEnhancedAttention(dim, num_heads, cache_config)

        # SwiGLU FFN
        ffn_dim = int(dim * config.ffn_mult)
        self.ffn_gate = nn.Linear(dim, ffn_dim, bias=False)
        self.ffn_up = nn.Linear(dim, ffn_dim, bias=False)
        self.ffn_down = nn.Linear(ffn_dim, dim, bias=False)

    def clear_cache(self):
        self.attn.clear_cache()

    def forward(
        self,
        x: torch.Tensor,
        use_cache: bool = False,
        output_probs: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        # Attention with metrics
        h = self.norm1(x)
        attn_out, metrics = self.attn(h, use_cache=use_cache, output_probs=output_probs)
        x = x + attn_out

        # SwiGLU FFN
        h = self.norm2(x)
        x = x + self.ffn_down(F.silu(self.ffn_gate(h)) * self.ffn_up(h))

        return x, metrics


# =============================================================================
# WITNESS LAYER (Layer 9)
# =============================================================================

class TrustworthyWitnessLayer(nn.Module):
    """
    Witness layer that observes generation state.

    Uses semantic entropy for confidence estimation (S5).
    """

    def __init__(self, dim: int, config: SymbolU12TrustworthyConfig):
        super().__init__()
        self.proj = nn.Linear(dim, dim + 1, bias=False)

        # Entropy tracker for witness confidence
        cache_config = EnhancedCacheConfig(
            entropy_spike_threshold=config.entropy_spike_threshold,
            hallucination_entropy_threshold=config.hallucination_threshold,
        )
        self.entropy_tracker = SemanticEntropyTracker(cache_config)

    def forward(
        self,
        x: torch.Tensor,
        output_probs: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, Any]]:
        # Project to get state + confidence
        out = self.proj(x.mean(dim=1))
        state = out[:, :-1]
        raw_confidence = torch.sigmoid(out[:, -1:])

        # Adjust confidence based on entropy
        metrics = {}
        if output_probs is not None:
            ent_metrics = self.entropy_tracker.update(output_probs)
            ent_confidence = ent_metrics['confidence']
            # Combine raw and entropy-based confidence
            adjusted_confidence = raw_confidence * ent_confidence
            metrics['entropy'] = ent_metrics['entropy']
            metrics['hallucination_risk'] = ent_metrics['hallucination_risk']
        else:
            adjusted_confidence = raw_confidence

        metrics['raw_confidence'] = raw_confidence.mean().item()
        metrics['adjusted_confidence'] = adjusted_confidence.mean().item()

        return x, adjusted_confidence, metrics

    def reset(self):
        self.entropy_tracker.reset()


# =============================================================================
# UNIFYING LAYER (Layer 10)
# =============================================================================

class TrustworthyUnifyingLayer(nn.Module):
    """
    Unifying layer that computes global coherence.

    Uses layer coherence scoring (S1-S2).
    """

    def __init__(self, dim: int, num_layers: int = 12):
        super().__init__()
        self.num_layers = num_layers
        self.proj = nn.Linear(dim, dim, bias=False)

    def forward(
        self,
        layer_outputs: List[torch.Tensor],
        x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, float, Dict[str, Any]]:
        # Stack layer outputs
        stacked = torch.stack([o.mean(dim=1) for o in layer_outputs], dim=1)

        # Compute coherence matrix (S1-S2)
        normalized = F.normalize(stacked, dim=-1)
        S = torch.bmm(normalized, normalized.transpose(1, 2))

        # Global coherence (upper triangle mean)
        n = self.num_layers
        mask = torch.triu(torch.ones(n, n, device=S.device), diagonal=1)
        J = (S * mask).sum() / (mask.sum() + 1e-10)

        # Unified representation
        weights = F.softmax(S.sum(dim=-1), dim=-1)
        unified = torch.einsum('bn,bnd->bd', weights, stacked)

        metrics = {
            'global_coherence': float(J),
            'layer_weights': weights.detach().cpu().numpy().tolist() if weights.dim() > 0 else []
        }

        return self.proj(unified).unsqueeze(1) + x, S, float(J), metrics


# =============================================================================
# COMPLETE TRUSTWORTHY MODEL
# =============================================================================

class SymbolU12Trustworthy(nn.Module):
    """
    SymbolU12 with patent-enhanced trustworthiness.

    Features:
    - Real-time hallucination detection
    - User-facing confidence indicators
    - Coherence-based quality scoring
    - Intelligent cache management

    Usage:
        model = SymbolU12Trustworthy()

        # Standard forward
        outputs = model(input_ids)
        print(f"Confidence: {outputs['confidence_level']}")

        # Generation with monitoring
        generated = model.generate(prompt, max_tokens=100)
        if outputs['hallucination_detected']:
            print("Warning: Potential hallucination!")
    """

    def __init__(self, config: Optional[SymbolU12TrustworthyConfig] = None):
        super().__init__()
        self.config = config or SymbolU12TrustworthyConfig()

        dim = self.config.embed_dim

        # Embeddings
        self.embed = nn.Embedding(self.config.vocab_size, dim)
        self.pos_embed = nn.Embedding(self.config.max_seq_len, dim)

        # 12 Ontological layers
        self.layers = nn.ModuleList()
        for i in range(self.config.num_layers):
            if i == 8:  # Witness layer
                self.layers.append(TrustworthyWitnessLayer(dim, self.config))
            elif i == 9:  # Unifying layer
                self.layers.append(TrustworthyUnifyingLayer(dim, self.config.num_layers))
            else:
                self.layers.append(TrustworthyTransformerBlock(
                    dim, self.config.num_heads, i, self.config
                ))

        # Output
        self.norm = nn.RMSNorm(dim)
        self.lm_head = nn.Linear(dim, self.config.vocab_size, bias=False)

        # Tie weights
        self.lm_head.weight = self.embed.weight

        # Global trackers
        self.global_entropy_tracker = SemanticEntropyTracker(EnhancedCacheConfig(
            entropy_spike_threshold=self.config.entropy_spike_threshold,
            hallucination_entropy_threshold=self.config.hallucination_threshold,
        ))
        self.global_coherence_scorer = CoherenceScorer(EnhancedCacheConfig())
        self.lagrangian = ConsistencyLagrangian(EnhancedCacheConfig(
            lambda_forward=self.config.lambda_forward,
            lambda_backward=self.config.lambda_backward,
            lambda_consistency=self.config.lambda_consistency,
            beta=self.config.beta,
        ))

    def clear_cache(self):
        """Clear all layer caches and reset trackers."""
        for layer in self.layers:
            if hasattr(layer, 'clear_cache'):
                layer.clear_cache()
            if hasattr(layer, 'reset'):
                layer.reset()
        self.global_entropy_tracker.reset()
        self.global_coherence_scorer.reset()

    def forward(
        self,
        input_ids: torch.Tensor,
        use_cache: bool = False,
        return_full_metrics: bool = False
    ) -> Dict[str, Any]:
        B, seq_len = input_ids.shape

        # Embeddings
        pos = torch.arange(seq_len, device=input_ids.device)
        x = self.embed(input_ids) + self.pos_embed(pos)

        # Track layer outputs for unifying
        layer_outputs = []
        all_metrics = []
        witness_confidence = None
        coherence_matrix = None
        global_coherence = 0.0

        # Forward through layers
        for i, layer in enumerate(self.layers):
            if i == 8:  # Witness
                x, witness_confidence, metrics = layer(x)
                all_metrics.append(('witness', metrics))
            elif i == 9:  # Unifying
                x, coherence_matrix, global_coherence, metrics = layer(layer_outputs, x)
                all_metrics.append(('unifying', metrics))
            else:
                x, metrics = layer(x, use_cache=use_cache)
                all_metrics.append((f'layer_{i}', metrics))

            layer_outputs.append(x)

        # Output logits
        x = self.norm(x)
        logits = self.lm_head(x)

        # Compute output probabilities for entropy
        probs = F.softmax(logits[:, -1, :], dim=-1)
        entropy_metrics = self.global_entropy_tracker.update(probs)

        # Compute consistency Lagrangian
        coherence = global_coherence
        confidence = entropy_metrics['confidence']
        lagrangian, weight = self.lagrangian.score_cache_entry(coherence, confidence)

        # Determine confidence level
        if confidence >= 0.8:
            confidence_level = "HIGH"
        elif confidence >= 0.5:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        # Check for hallucination
        hallucination_detected = (
            entropy_metrics['is_spike'] or
            entropy_metrics['hallucination_risk'] > 0.7 or
            global_coherence < self.config.min_coherence
        )

        result = {
            'logits': logits,
            'witness_confidence': witness_confidence,
            'coherence_matrix': coherence_matrix,
            'global_coherence': global_coherence,
            'entropy': entropy_metrics['entropy'],
            'confidence': confidence,
            'confidence_level': confidence_level,
            'lagrangian': lagrangian,
            'consistency_weight': weight,
            'hallucination_detected': hallucination_detected,
            'hallucination_risk': entropy_metrics['hallucination_risk'],
        }

        if return_full_metrics:
            result['layer_metrics'] = all_metrics

        return result

    @torch.no_grad()
    def generate(
        self,
        prompt_ids: torch.Tensor,
        max_new_tokens: int = 100,
        temperature: float = 0.8,
        top_p: float = 0.9,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Generate with real-time quality monitoring.

        Returns generated tokens plus quality metrics.
        """
        self.eval()
        self.clear_cache()

        generated = prompt_ids
        generation_log = []
        warnings = []

        # Process prompt
        outputs = self.forward(prompt_ids, use_cache=True)

        for step in range(max_new_tokens):
            # Sample next token
            logits = outputs['logits'][:, -1, :] / temperature

            # Top-p sampling
            sorted_logits, sorted_indices = torch.sort(logits, descending=True)
            probs = F.softmax(sorted_logits, dim=-1)
            cumsum = torch.cumsum(probs, dim=-1)
            mask = cumsum - probs > top_p
            sorted_logits[mask] = float('-inf')
            probs = F.softmax(sorted_logits, dim=-1)

            next_token_idx = torch.multinomial(probs, num_samples=1)
            next_token = sorted_indices.gather(-1, next_token_idx)

            # Append token
            generated = torch.cat([generated, next_token], dim=1)

            # Forward next token
            outputs = self.forward(next_token, use_cache=True)

            # Log quality metrics
            step_metrics = {
                'step': step,
                'confidence': outputs['confidence_level'],
                'coherence': outputs['global_coherence'],
                'entropy': outputs['entropy'],
                'hallucination_risk': outputs['hallucination_risk']
            }
            generation_log.append(step_metrics)

            # Check for hallucination
            if outputs['hallucination_detected']:
                warnings.append(f"Step {step}: Potential hallucination (risk={outputs['hallucination_risk']:.2f})")

                if self.config.halt_on_hallucination:
                    break

            # Progress
            if show_progress and (step + 1) % 10 == 0:
                print(f"Generated {step+1} tokens | "
                      f"Confidence: {outputs['confidence_level']} | "
                      f"Coherence: {outputs['global_coherence']:.2f}")

            # Check EOS
            if next_token.item() == 0:
                break

        # Compute final quality summary
        avg_coherence = sum(m['coherence'] for m in generation_log) / len(generation_log) if generation_log else 0
        avg_confidence = sum(1 if m['confidence'] == 'HIGH' else 0.5 if m['confidence'] == 'MEDIUM' else 0
                            for m in generation_log) / len(generation_log) if generation_log else 0

        return {
            'generated_ids': generated,
            'num_tokens': generated.shape[1] - prompt_ids.shape[1],
            'avg_coherence': avg_coherence,
            'avg_confidence': avg_confidence,
            'warnings': warnings,
            'generation_log': generation_log,
            'quality_report': self._generate_report(generation_log, warnings)
        }

    def _generate_report(self, log: List[Dict], warnings: List[str]) -> str:
        """Generate human-readable quality report."""
        lines = []
        lines.append("=" * 60)
        lines.append("SymbolU12 Trustworthy - Generation Quality Report")
        lines.append("=" * 60)

        if log:
            # Confidence distribution
            high = sum(1 for m in log if m['confidence'] == 'HIGH')
            med = sum(1 for m in log if m['confidence'] == 'MEDIUM')
            low = sum(1 for m in log if m['confidence'] == 'LOW')
            total = len(log)

            lines.append(f"\nTokens Generated: {total}")
            lines.append(f"\nConfidence Distribution:")
            lines.append(f"  HIGH:   {high:4d} ({high/total*100:5.1f}%)")
            lines.append(f"  MEDIUM: {med:4d} ({med/total*100:5.1f}%)")
            lines.append(f"  LOW:    {low:4d} ({low/total*100:5.1f}%)")

            # Coherence stats
            coherences = [m['coherence'] for m in log]
            lines.append(f"\nCoherence:")
            lines.append(f"  Average: {sum(coherences)/len(coherences):.3f}")
            lines.append(f"  Min:     {min(coherences):.3f}")
            lines.append(f"  Max:     {max(coherences):.3f}")

        # Warnings
        if warnings:
            lines.append(f"\n⚠️ Warnings ({len(warnings)}):")
            for w in warnings[:5]:  # Show first 5
                lines.append(f"  {w}")
            if len(warnings) > 5:
                lines.append(f"  ... and {len(warnings)-5} more")
        else:
            lines.append("\n✓ No hallucination warnings")

        lines.append("=" * 60)
        return "\n".join(lines)

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_trustworthy_small() -> SymbolU12Trustworthy:
    """Small trustworthy model (~50MB)."""
    config = SymbolU12TrustworthyConfig(
        vocab_size=32000,
        embed_dim=256,
        num_heads=4,
        max_seq_len=1024,
    )
    return SymbolU12Trustworthy(config)


def create_trustworthy_base() -> SymbolU12Trustworthy:
    """Base trustworthy model (~150MB)."""
    config = SymbolU12TrustworthyConfig(
        vocab_size=32000,
        embed_dim=512,
        num_heads=8,
        max_seq_len=2048,
    )
    return SymbolU12Trustworthy(config)


def create_trustworthy_large() -> SymbolU12Trustworthy:
    """Large trustworthy model (~500MB)."""
    config = SymbolU12TrustworthyConfig(
        vocab_size=50000,
        embed_dim=1024,
        num_heads=16,
        max_seq_len=4096,
    )
    return SymbolU12Trustworthy(config)


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("SymbolU12 Trustworthy - Patent-Enhanced LLM")
    print("=" * 70)

    # Create model
    model = create_trustworthy_small()
    print(f"\nModel Parameters: {model.count_parameters():,}")

    print("\nPatent Formulas Integrated:")
    print("-" * 50)
    print("""
BCVF (B1-B5): Bidirectional Consistency Verification
    L = λf(1-sf)² + λb(1-sb)² + λc(sf-sb)²

    - Scores each generation step
    - Low L = trustworthy output
    - High L = potential hallucination

SCC (S1-S3): Semantic Coherence Checking
    C(l_i, l_j) = cos(h_i, h_j)

    - Monitors cross-layer coherence
    - Detects reasoning inconsistencies

USE (S5): User Semantic Entropy
    H = -Σ p(x) log p(x)

    - Real-time confidence estimation
    - Spike detection for hallucinations
    - User-facing: HIGH/MEDIUM/LOW
    """)

    print("-" * 50)
    print("Simulating generation...")

    # Simulate forward pass
    batch_size = 1
    seq_len = 50
    input_ids = torch.randint(0, model.config.vocab_size, (batch_size, seq_len))

    outputs = model(input_ids)

    print(f"\nOutput Metrics:")
    print(f"  Confidence Level: {outputs['confidence_level']}")
    print(f"  Global Coherence: {outputs['global_coherence']:.4f}")
    print(f"  Entropy: {outputs['entropy']:.4f}")
    print(f"  Lagrangian: {outputs['lagrangian']:.4f}")
    print(f"  Consistency Weight: {outputs['consistency_weight']:.4f}")
    print(f"  Hallucination Detected: {outputs['hallucination_detected']}")

    print("\n" + "=" * 70)
