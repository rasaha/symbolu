"""
Phoneme Attention Head
======================

A deterministic attention mechanism based on phoneme similarity.
Can replace learned attention heads in transformer architectures.

Computational Advantage:
- Traditional attention: O(n² × d) where d=64-128 per head
- Phoneme attention: O(n² × 10) = 6-13x faster per head
- No learnable parameters = no gradient computation

Architecture:
    Input tokens → Phoneme vectors (10D) → Similarity matrix → Attention weights
                        ↓
              Uses symbolu.resonance engine
"""

from dataclasses import dataclass
from typing import Tuple, List, Optional, Dict
import math

from symbolu.resonance import (
    analyze_word,
    compute_resonance,
    WordVector,
    LAYER_NAMES,
)


@dataclass(frozen=True)
class AttentionOutput:
    """Output from phoneme attention computation."""
    attention_weights: Tuple[Tuple[float, ...], ...]  # [seq_len, seq_len]
    token_vectors: Tuple[WordVector, ...]  # 10D vector per token
    dominant_layers: Tuple[str, ...]  # Dominant layer per token
    computation_flops: int  # Estimated FLOPs


class PhonemeAttentionHead:
    """
    Deterministic attention head using phoneme similarity.

    Instead of learning Q, K, V projections, uses phoneme-derived
    10D vectors and cosine similarity for attention weights.

    Attributes:
        temperature: Softmax temperature (higher = softer attention)
        mask_self: Whether to mask self-attention (diagonal)
    """

    def __init__(
        self,
        temperature: float = 1.0,
        mask_self: bool = False,
    ):
        self.temperature = temperature
        self.mask_self = mask_self
        self._cache: Dict[str, WordVector] = {}

    def _get_vector(self, token: str) -> WordVector:
        """Get phoneme vector for token, with caching."""
        if token not in self._cache:
            self._cache[token] = analyze_word(token)
        return self._cache[token]

    def compute_attention(
        self,
        tokens: Tuple[str, ...],
    ) -> AttentionOutput:
        """
        Compute attention weights from phoneme similarity.

        Args:
            tokens: Sequence of word tokens

        Returns:
            AttentionOutput with attention matrix and metadata

        Complexity:
            O(n² × 10) where n = len(tokens)
            Compare to traditional: O(n² × 64)
        """
        n = len(tokens)
        if n == 0:
            return AttentionOutput(
                attention_weights=(),
                token_vectors=(),
                dominant_layers=(),
                computation_flops=0,
            )

        # Step 1: Convert tokens to 10D vectors
        vectors = tuple(self._get_vector(t) for t in tokens)

        # Step 2: Compute pairwise similarity matrix
        similarity_matrix: List[List[float]] = []
        for i in range(n):
            row: List[float] = []
            for j in range(n):
                if self.mask_self and i == j:
                    row.append(float('-inf'))  # Will become 0 after softmax
                else:
                    # Cosine similarity between 10D vectors
                    sim = self._cosine_similarity(
                        vectors[i].vector,
                        vectors[j].vector,
                    )
                    row.append(sim / self.temperature)
            similarity_matrix.append(row)

        # Step 3: Apply softmax to get attention weights
        attention_weights: List[Tuple[float, ...]] = []
        for row in similarity_matrix:
            softmax_row = self._softmax(row)
            attention_weights.append(tuple(softmax_row))

        # Compute FLOPs estimate
        # n² similarity computations × 10 dimensions × 2 (multiply + add)
        # + n × softmax (exp + sum + divide)
        flops = n * n * 10 * 2 + n * n * 3

        return AttentionOutput(
            attention_weights=tuple(attention_weights),
            token_vectors=vectors,
            dominant_layers=tuple(v.dominant_layer for v in vectors),
            computation_flops=flops,
        )

    def _cosine_similarity(
        self,
        a: Tuple[float, ...],
        b: Tuple[float, ...],
    ) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(y * y for y in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def _softmax(self, values: List[float]) -> List[float]:
        """Apply softmax to a list of values."""
        # Subtract max for numerical stability
        max_val = max(v for v in values if v != float('-inf'))
        exp_values = []
        for v in values:
            if v == float('-inf'):
                exp_values.append(0.0)
            else:
                exp_values.append(math.exp(v - max_val))
        total = sum(exp_values)
        if total == 0:
            return [1.0 / len(values)] * len(values)
        return [v / total for v in exp_values]

    def compare_to_traditional(
        self,
        seq_len: int,
        head_dim: int = 64,
    ) -> Dict[str, int]:
        """
        Compare FLOPs to traditional attention head.

        Args:
            seq_len: Sequence length
            head_dim: Traditional attention head dimension

        Returns:
            Dict with FLOP comparison
        """
        # Traditional attention:
        # Q, K, V projections: 3 × n × d × d_model (we ignore d_model)
        # QK^T: n × n × d
        # Softmax: n × n × 3
        # Attention × V: n × n × d
        traditional_flops = seq_len * seq_len * head_dim * 2 + seq_len * seq_len * 3

        # Phoneme attention:
        # Already computed in compute_attention
        phoneme_flops = seq_len * seq_len * 10 * 2 + seq_len * seq_len * 3

        return {
            "traditional_flops": traditional_flops,
            "phoneme_flops": phoneme_flops,
            "speedup_factor": traditional_flops / phoneme_flops if phoneme_flops > 0 else 0,
            "flops_saved": traditional_flops - phoneme_flops,
        }

    def clear_cache(self):
        """Clear the token vector cache."""
        self._cache.clear()


class HybridAttentionLayer:
    """
    Combines phoneme attention with traditional attention heads.

    Architecture:
        - 2 phoneme attention heads (deterministic, fast)
        - N-2 traditional attention heads (learned, expressive)

    The phoneme heads capture "phonetic intuition" while learned
    heads capture context-dependent semantics.
    """

    def __init__(
        self,
        num_phoneme_heads: int = 2,
        num_traditional_heads: int = 10,
        head_dim: int = 64,
    ):
        self.num_phoneme_heads = num_phoneme_heads
        self.num_traditional_heads = num_traditional_heads
        self.head_dim = head_dim
        self.phoneme_heads = [
            PhonemeAttentionHead(temperature=1.0 + i * 0.5)
            for i in range(num_phoneme_heads)
        ]

    def estimate_savings(self, seq_len: int) -> Dict[str, float]:
        """
        Estimate computational savings from using hybrid attention.

        Args:
            seq_len: Sequence length

        Returns:
            Dict with savings estimates
        """
        total_heads = self.num_phoneme_heads + self.num_traditional_heads

        # Traditional: all heads use learned attention
        all_traditional = total_heads * seq_len * seq_len * self.head_dim * 2

        # Hybrid: phoneme heads use 10D, rest use head_dim
        phoneme_cost = self.num_phoneme_heads * seq_len * seq_len * 10 * 2
        traditional_cost = self.num_traditional_heads * seq_len * seq_len * self.head_dim * 2
        hybrid_total = phoneme_cost + traditional_cost

        return {
            "all_traditional_flops": all_traditional,
            "hybrid_flops": hybrid_total,
            "flops_saved": all_traditional - hybrid_total,
            "percent_saved": (all_traditional - hybrid_total) / all_traditional * 100,
            "phoneme_heads": self.num_phoneme_heads,
            "traditional_heads": self.num_traditional_heads,
        }
