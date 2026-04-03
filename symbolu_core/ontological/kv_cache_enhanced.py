#!/usr/bin/env python3
"""
Enhanced KV Cache with Patent Formula Integration
==================================================

Integrates BCVF, SCC, and USE patent formulas with KV cache for:
1. Hallucination detection during generation
2. Coherence scoring for cached states
3. User-facing confidence metrics
4. Intelligent cache invalidation based on consistency

Patent Formulas Applied:
- BCVF (B1-B5): Bidirectional Consistency Verification
- SCC (S1-S3): Semantic Coherence Checking with entropy
- USE (S5): User Semantic Entropy for confidence estimation

Core Innovation:
    Cache entries are scored by consistency Lagrangian:
    L = λf(1-sf)² + λb(1-sb)² + λc(sf-sb)²

    Low-quality entries (high L) can be pruned to prevent
    hallucination propagation through cached states.
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import deque

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    raise ImportError("PyTorch required for enhanced KV cache")

import numpy as np


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class EnhancedCacheConfig:
    """Configuration for patent-enhanced KV cache."""

    # Cache settings
    max_seq_len: int = 2048
    max_cache_entries: int = 4096

    # BCVF consistency weights (B1)
    lambda_forward: float = 1.0
    lambda_backward: float = 1.0
    lambda_consistency: float = 0.5
    beta: float = 2.0  # Temperature for weight conversion

    # Entropy thresholds (S5)
    entropy_spike_threshold: float = 0.3
    hallucination_entropy_threshold: float = 0.7
    target_entropy: float = 0.3

    # Coherence thresholds (S1-S2)
    min_coherence_for_cache: float = 0.5
    coherence_window: int = 5

    # Cache pruning
    enable_consistency_pruning: bool = True
    prune_threshold: float = 0.3  # Remove entries with weight < threshold

    # User experience
    show_confidence: bool = True
    confidence_levels: Dict[str, float] = field(default_factory=lambda: {
        "high": 0.8,
        "medium": 0.5,
        "low": 0.0
    })


# =============================================================================
# SEMANTIC ENTROPY TRACKER (S5)
# =============================================================================

class SemanticEntropyTracker:
    """
    Tracks semantic entropy during generation for hallucination detection.

    Formula (S5): H_sem = -Σ p(x) log p(x)

    Stability constraint (S8-S9): dH/dt ≤ 0 for coherent generation
    """

    def __init__(self, config: EnhancedCacheConfig):
        self.config = config
        self.history: deque = deque(maxlen=config.coherence_window * 2)
        self.step = 0

    def compute_entropy(self, probs: torch.Tensor) -> torch.Tensor:
        """Compute semantic entropy from probability distribution."""
        probs = probs + 1e-10
        probs = probs / probs.sum(dim=-1, keepdim=True)
        entropy = -torch.sum(probs * torch.log(probs), dim=-1)

        # Normalize by max entropy
        max_entropy = math.log(probs.shape[-1])
        return entropy / max_entropy

    def update(self, probs: torch.Tensor) -> Dict[str, float]:
        """
        Update entropy tracking and return metrics.

        Returns:
            Dict with 'entropy', 'trend', 'is_spike', 'confidence'
        """
        entropy = self.compute_entropy(probs).mean().item()
        self.history.append(entropy)
        self.step += 1

        # Compute trend
        trend = 0.0
        if len(self.history) >= 2:
            trend = self.history[-1] - self.history[-2]

        # Detect spike
        is_spike = trend > self.config.entropy_spike_threshold

        # Compute confidence (inverse of entropy risk)
        confidence = 1.0 - entropy
        if is_spike:
            confidence *= 0.5  # Penalize spikes
        if trend > 0:
            confidence *= (1.0 - min(abs(trend), 1.0))

        confidence = max(0.0, min(1.0, confidence))

        return {
            'entropy': entropy,
            'trend': trend,
            'is_spike': is_spike,
            'confidence': confidence,
            'hallucination_risk': 1.0 - confidence
        }

    def detect_hallucination(self) -> bool:
        """Check if current state indicates hallucination."""
        if not self.history:
            return False

        current = self.history[-1]

        # High absolute entropy
        if current > self.config.hallucination_entropy_threshold:
            return True

        # Entropy spike
        if len(self.history) >= 2:
            if self.history[-1] - self.history[-2] > self.config.entropy_spike_threshold:
                return True

        return False

    def get_confidence_level(self) -> Tuple[str, float]:
        """Get user-facing confidence level."""
        if not self.history:
            return "unknown", 0.5

        confidence = 1.0 - self.history[-1]

        if confidence >= self.config.confidence_levels["high"]:
            return "high", confidence
        elif confidence >= self.config.confidence_levels["medium"]:
            return "medium", confidence
        else:
            return "low", confidence

    def reset(self):
        """Reset entropy history for new generation."""
        self.history.clear()
        self.step = 0


# =============================================================================
# COHERENCE SCORER (S1-S2)
# =============================================================================

class CoherenceScorer:
    """
    Computes layer coherence for cache quality assessment.

    Formula (S1-S2): Coherence via cross-layer cosine similarity
    C(l_i, l_j) = cos(h_i, h_j) where h are layer representations
    """

    def __init__(self, config: EnhancedCacheConfig):
        self.config = config
        self.layer_history: List[torch.Tensor] = []

    def compute_coherence(
        self,
        layer_output: torch.Tensor,
        previous_output: Optional[torch.Tensor] = None
    ) -> float:
        """
        Compute coherence between current and previous layer outputs.

        Returns coherence score in [0, 1].
        """
        if previous_output is None:
            if not self.layer_history:
                return 1.0
            previous_output = self.layer_history[-1]

        # Mean pool to get fixed-size representation
        current = layer_output.mean(dim=1)  # [B, D]
        previous = previous_output.mean(dim=1)  # [B, D]

        # Cosine similarity
        coherence = F.cosine_similarity(current, previous, dim=-1)

        return coherence.mean().item()

    def update(self, layer_output: torch.Tensor) -> float:
        """Update history and compute coherence with previous."""
        coherence = self.compute_coherence(layer_output)

        # Keep limited history
        self.layer_history.append(layer_output.detach())
        if len(self.layer_history) > self.config.coherence_window:
            self.layer_history.pop(0)

        return coherence

    def get_global_coherence(self) -> float:
        """Compute global coherence across all stored layers."""
        if len(self.layer_history) < 2:
            return 1.0

        coherences = []
        for i in range(len(self.layer_history) - 1):
            c = self.compute_coherence(
                self.layer_history[i + 1],
                self.layer_history[i]
            )
            coherences.append(c)

        return sum(coherences) / len(coherences)

    def reset(self):
        """Reset layer history."""
        self.layer_history.clear()


# =============================================================================
# CONSISTENCY LAGRANGIAN (B1)
# =============================================================================

class ConsistencyLagrangian:
    """
    Computes BCVF Consistency Lagrangian for cache entry scoring.

    Formula (B1): L = λf(1-sf)² + λb(1-sb)² + λc(sf-sb)²

    Where:
        sf = forward feasibility (coherence-based)
        sb = backward goal-achievement (entropy-based)
    """

    def __init__(self, config: EnhancedCacheConfig):
        self.config = config

    def compute(
        self,
        forward_score: float,
        backward_score: float
    ) -> float:
        """Compute Lagrangian value (lower is better)."""
        sf = max(0.0, min(1.0, forward_score))
        sb = max(0.0, min(1.0, backward_score))

        L = (
            self.config.lambda_forward * (1.0 - sf) ** 2 +
            self.config.lambda_backward * (1.0 - sb) ** 2 +
            self.config.lambda_consistency * (sf - sb) ** 2
        )

        return L

    def compute_weight(self, lagrangian: float) -> float:
        """Convert Lagrangian to consistency weight (B2)."""
        return math.exp(-self.config.beta * lagrangian)

    def score_cache_entry(
        self,
        coherence: float,
        confidence: float
    ) -> Tuple[float, float]:
        """
        Score a cache entry using coherence and confidence.

        Args:
            coherence: Layer coherence score (used as sf)
            confidence: Entropy-based confidence (used as sb)

        Returns:
            (lagrangian, weight) tuple
        """
        lagrangian = self.compute(coherence, confidence)
        weight = self.compute_weight(lagrangian)
        return lagrangian, weight


# =============================================================================
# ENHANCED KV CACHE ENTRY
# =============================================================================

@dataclass
class CacheEntry:
    """A single KV cache entry with consistency metadata."""
    key: torch.Tensor
    value: torch.Tensor
    position: int
    coherence: float = 1.0
    confidence: float = 1.0
    lagrangian: float = 0.0
    consistency_weight: float = 1.0
    is_valid: bool = True

    @property
    def quality_category(self) -> str:
        """Categorize entry quality."""
        if self.consistency_weight >= 0.8:
            return "high_quality"
        elif self.consistency_weight >= 0.5:
            return "acceptable"
        elif self.consistency_weight >= 0.3:
            return "low_quality"
        else:
            return "reject"


# =============================================================================
# ENHANCED KV CACHE
# =============================================================================

class EnhancedKVCache(nn.Module):
    """
    KV Cache enhanced with BCVF, SCC, and USE patent formulas.

    Features:
    1. Consistency scoring for each cached entry
    2. Hallucination detection during retrieval
    3. Automatic pruning of low-quality entries
    4. User-facing confidence metrics

    Usage:
        cache = EnhancedKVCache(dim=512, num_heads=8)

        # During generation
        k, v = cache.get_or_compute(x, layer_output)

        # Check for hallucination
        if cache.detect_hallucination():
            print("Warning: Potential hallucination!")

        # Get user confidence
        level, score = cache.get_confidence()
        print(f"Confidence: {level} ({score:.1%})")
    """

    def __init__(
        self,
        dim: int,
        num_heads: int,
        config: Optional[EnhancedCacheConfig] = None
    ):
        super().__init__()
        self.dim = dim
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.config = config or EnhancedCacheConfig()

        # Patent formula components
        self.entropy_tracker = SemanticEntropyTracker(self.config)
        self.coherence_scorer = CoherenceScorer(self.config)
        self.lagrangian = ConsistencyLagrangian(self.config)

        # Cache storage
        self.entries: List[CacheEntry] = []
        self.k_cache: Optional[torch.Tensor] = None
        self.v_cache: Optional[torch.Tensor] = None

        # Metrics
        self.total_entries = 0
        self.pruned_entries = 0
        self.hallucination_warnings = 0

    def clear(self):
        """Clear cache and reset trackers."""
        self.entries.clear()
        self.k_cache = None
        self.v_cache = None
        self.entropy_tracker.reset()
        self.coherence_scorer.reset()

    def _compute_entry_scores(
        self,
        layer_output: torch.Tensor,
        output_probs: Optional[torch.Tensor] = None
    ) -> Tuple[float, float, float, float]:
        """
        Compute consistency scores for a cache entry.

        Returns:
            (coherence, confidence, lagrangian, weight)
        """
        # Coherence from layer output
        coherence = self.coherence_scorer.update(layer_output)

        # Confidence from entropy (if probs available)
        if output_probs is not None:
            metrics = self.entropy_tracker.update(output_probs)
            confidence = metrics['confidence']
        else:
            confidence = 0.8  # Default

        # Consistency Lagrangian
        lagrangian, weight = self.lagrangian.score_cache_entry(
            coherence, confidence
        )

        return coherence, confidence, lagrangian, weight

    def update(
        self,
        key: torch.Tensor,
        value: torch.Tensor,
        layer_output: Optional[torch.Tensor] = None,
        output_probs: Optional[torch.Tensor] = None
    ) -> CacheEntry:
        """
        Add new entry to cache with consistency scoring.

        Args:
            key: Key tensor [B, seq, num_heads, head_dim]
            value: Value tensor [B, seq, num_heads, head_dim]
            layer_output: Layer output for coherence scoring
            output_probs: Output probabilities for entropy

        Returns:
            CacheEntry with consistency metadata
        """
        # Compute scores if layer output available
        if layer_output is not None:
            coherence, confidence, lagrangian, weight = self._compute_entry_scores(
                layer_output, output_probs
            )
        else:
            coherence = confidence = 1.0
            lagrangian = 0.0
            weight = 1.0

        # Create entry
        position = len(self.entries)
        entry = CacheEntry(
            key=key,
            value=value,
            position=position,
            coherence=coherence,
            confidence=confidence,
            lagrangian=lagrangian,
            consistency_weight=weight
        )

        # Check if entry should be rejected
        if self.config.enable_consistency_pruning:
            if weight < self.config.prune_threshold:
                entry.is_valid = False
                self.pruned_entries += 1

        # Add to cache
        self.entries.append(entry)
        self.total_entries += 1

        # Update tensor caches
        if self.k_cache is None:
            self.k_cache = key
            self.v_cache = value
        else:
            self.k_cache = torch.cat([self.k_cache, key], dim=1)
            self.v_cache = torch.cat([self.v_cache, value], dim=1)

        return entry

    def get(
        self,
        include_invalid: bool = False
    ) -> Tuple[Optional[torch.Tensor], Optional[torch.Tensor]]:
        """
        Get cached keys and values.

        Args:
            include_invalid: Whether to include low-quality entries

        Returns:
            (k_cache, v_cache) tensors
        """
        if not include_invalid and self.config.enable_consistency_pruning:
            # Filter valid entries only
            valid_entries = [e for e in self.entries if e.is_valid]
            if not valid_entries:
                return None, None

            k = torch.cat([e.key for e in valid_entries], dim=1)
            v = torch.cat([e.value for e in valid_entries], dim=1)
            return k, v

        return self.k_cache, self.v_cache

    def detect_hallucination(self) -> bool:
        """Check if current generation indicates hallucination."""
        return self.entropy_tracker.detect_hallucination()

    def get_confidence(self) -> Tuple[str, float]:
        """Get user-facing confidence level."""
        return self.entropy_tracker.get_confidence_level()

    def get_coherence(self) -> float:
        """Get global coherence score."""
        return self.coherence_scorer.get_global_coherence()

    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive cache metrics."""
        valid_entries = [e for e in self.entries if e.is_valid]

        return {
            'total_entries': self.total_entries,
            'valid_entries': len(valid_entries),
            'pruned_entries': self.pruned_entries,
            'hallucination_warnings': self.hallucination_warnings,
            'avg_coherence': np.mean([e.coherence for e in self.entries]) if self.entries else 0.0,
            'avg_confidence': np.mean([e.confidence for e in self.entries]) if self.entries else 0.0,
            'avg_weight': np.mean([e.consistency_weight for e in self.entries]) if self.entries else 0.0,
            'global_coherence': self.get_coherence(),
            'current_confidence': self.get_confidence(),
            'hallucination_detected': self.detect_hallucination()
        }

    def get_user_report(self) -> str:
        """Generate user-friendly report on generation quality."""
        metrics = self.get_metrics()
        level, conf = metrics['current_confidence']

        report = []
        report.append("=" * 50)
        report.append("Generation Quality Report")
        report.append("=" * 50)

        # Confidence
        report.append(f"\nConfidence: {level.upper()} ({conf:.1%})")

        # Coherence
        coh = metrics['global_coherence']
        report.append(f"Coherence:  {coh:.1%}")

        # Hallucination warning
        if metrics['hallucination_detected']:
            report.append("\n⚠️ WARNING: Potential hallucination detected!")
            report.append("   The model may be generating unreliable content.")
            self.hallucination_warnings += 1
        else:
            report.append("\n✓ Generation appears consistent")

        # Quality breakdown
        if self.entries:
            categories = {}
            for e in self.entries:
                cat = e.quality_category
                categories[cat] = categories.get(cat, 0) + 1

            report.append(f"\nEntry Quality Breakdown:")
            for cat, count in sorted(categories.items()):
                pct = count / len(self.entries) * 100
                report.append(f"  {cat}: {count} ({pct:.1f}%)")

        report.append("=" * 50)
        return "\n".join(report)


# =============================================================================
# ENHANCED ATTENTION WITH PATENT FORMULAS
# =============================================================================

class PatentEnhancedAttention(nn.Module):
    """
    Attention module with integrated BCVF/SCC/USE formulas.

    Combines:
    - Efficient attention computation
    - Enhanced KV cache with consistency scoring
    - Hallucination detection
    - User confidence reporting
    """

    def __init__(
        self,
        dim: int,
        num_heads: int = 8,
        config: Optional[EnhancedCacheConfig] = None
    ):
        super().__init__()
        self.dim = dim
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.config = config or EnhancedCacheConfig()

        # Projections
        self.qkv = nn.Linear(dim, dim * 3, bias=False)
        self.out_proj = nn.Linear(dim, dim, bias=False)

        # Enhanced cache
        self.cache = EnhancedKVCache(dim, num_heads, self.config)

    def clear_cache(self):
        """Clear KV cache."""
        self.cache.clear()

    def forward(
        self,
        x: torch.Tensor,
        use_cache: bool = False,
        output_probs: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Forward pass with enhanced caching.

        Args:
            x: Input tensor [B, seq, dim]
            use_cache: Whether to use/update cache
            output_probs: Output probabilities for entropy tracking

        Returns:
            (output, metrics) tuple
        """
        B, seq_len, _ = x.shape

        # QKV projection
        qkv = self.qkv(x).reshape(B, seq_len, 3, self.num_heads, self.head_dim)
        q, k, v = qkv.unbind(dim=2)

        # Handle caching
        if use_cache:
            # Update cache with consistency scoring
            self.cache.update(
                key=k,
                value=v,
                layer_output=x,
                output_probs=output_probs
            )

            # Get cached KV (may exclude invalid entries)
            cached_k, cached_v = self.cache.get()
            if cached_k is not None:
                k = cached_k
                v = cached_v

        # Reshape for attention
        q = q.transpose(1, 2)  # [B, heads, seq, head_dim]
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        # Attention computation
        if hasattr(F, 'scaled_dot_product_attention'):
            out = F.scaled_dot_product_attention(q, k, v)
        else:
            scale = 1.0 / math.sqrt(self.head_dim)
            attn = torch.matmul(q, k.transpose(-2, -1)) * scale
            attn = F.softmax(attn, dim=-1)
            out = torch.matmul(attn, v)

        # Reshape and project
        out = out.transpose(1, 2).reshape(B, seq_len, self.dim)
        out = self.out_proj(out)

        # Get metrics
        metrics = self.cache.get_metrics()

        return out, metrics

    def detect_hallucination(self) -> bool:
        """Check for hallucination in current generation."""
        return self.cache.detect_hallucination()

    def get_confidence(self) -> Tuple[str, float]:
        """Get user-facing confidence."""
        return self.cache.get_confidence()

    def get_report(self) -> str:
        """Get user report on generation quality."""
        return self.cache.get_user_report()


# =============================================================================
# DEMO AND TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Enhanced KV Cache with Patent Formula Integration")
    print("=" * 70)

    # Create enhanced attention
    dim = 256
    num_heads = 4
    attn = PatentEnhancedAttention(dim, num_heads)

    print(f"\nConfiguration:")
    print(f"  Dimension: {dim}")
    print(f"  Heads: {num_heads}")
    print(f"  Max seq len: {attn.config.max_seq_len}")
    print(f"  Consistency pruning: {attn.config.enable_consistency_pruning}")

    # Simulate generation
    print("\n" + "-" * 70)
    print("Simulating generation with cache...")

    batch_size = 2
    attn.clear_cache()

    # Process prompt
    prompt_len = 50
    prompt = torch.randn(batch_size, prompt_len, dim)
    prompt_probs = F.softmax(torch.randn(batch_size, 1000), dim=-1)

    out, metrics = attn(prompt, use_cache=True, output_probs=prompt_probs)
    print(f"\n1. Processed prompt ({prompt_len} tokens)")
    print(f"   Coherence: {metrics['global_coherence']:.3f}")
    print(f"   Confidence: {metrics['current_confidence']}")

    # Generate tokens
    for i in range(10):
        new_token = torch.randn(batch_size, 1, dim)

        # Simulate varying quality (entropy increases mid-generation)
        if 4 <= i <= 6:
            # High entropy = low confidence
            token_probs = F.softmax(torch.randn(batch_size, 1000) * 0.5, dim=-1)
        else:
            # Low entropy = high confidence
            token_probs = F.softmax(torch.randn(batch_size, 1000) * 2.0, dim=-1)

        out, metrics = attn(new_token, use_cache=True, output_probs=token_probs)

        if attn.detect_hallucination():
            print(f"   Token {i+1}: ⚠️ Hallucination warning!")

    # Final report
    print("\n" + attn.get_report())

    print("\n" + "-" * 70)
    print("Patent Formulas Applied:")
    print("-" * 70)
    print("""
BCVF (B1): Consistency Lagrangian
    L = λf(1-sf)² + λb(1-sb)² + λc(sf-sb)²

    - sf = coherence score (from layer similarity)
    - sb = confidence score (from entropy)
    - Low L = high quality entry
    - High L = potential hallucination

SCC (S1-S2): Layer Coherence
    C(l_i, l_j) = cos(mean(h_i), mean(h_j))

    - Measures alignment between layer outputs
    - High coherence = consistent reasoning
    - Low coherence = confused generation

USE (S5): Semantic Entropy
    H_sem = -Σ p(x) log p(x)

    - Tracks entropy during generation
    - Spike detection: dH/dt > threshold → warning
    - Converts to user-facing confidence level
    """)

    print("=" * 70)
