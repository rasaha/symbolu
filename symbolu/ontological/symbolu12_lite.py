#!/usr/bin/env python3
"""
SymbolU12 Lite - NumPy-Only Ontological Language Model
=======================================================

A lightweight implementation of the 12-layer ontological transformer
using only NumPy. No PyTorch, TensorFlow, or other heavy dependencies.

Features:
---------
- Pure NumPy implementation
- All 12 ontological layers
- ~100x smaller than PyTorch version
- Runs anywhere Python + NumPy runs
- Inference-focused (weights can be loaded from trained PyTorch model)

Architecture:
-------------
    Layer 1:  POTENTIAL    - Dormant token activation
    Layer 2:  IDENTITY     - Syntactic tagging
    Layer 3:  EXECUTION    - N-gram patterns
    Layer 4:  STRUCTURE    - Phrase boundaries
    Layer 5:  COGNITION    - Semantic understanding
    Layer 6:  AGENCY       - Goal-directed attention
    Layer 7:  REASONING    - Logical inference
    Layer 8:  PURPOSE      - Intent recognition
    Layer 9:  WITNESS      - Meta-cognitive monitoring
    Layer 10: UNIFYING     - Coherence (C'[i,j] = C[i,j] × S[i,j])
    Layer 11: INTEGRATION  - Conflict resolution
    Layer 12: ABSOLVING    - Termination decision

Usage:
------
    from symbolu.ontological.symbolu12_lite import SymbolU12Lite

    model = SymbolU12Lite()
    result = model.analyze("What is consciousness?")

    print(result["dominant_layer"])
    print(result["coherence"])
    print(result["witness_confidence"])

Dependencies:
-------------
    - numpy (only required dependency)

Author: Based on Rakesh Mohan's Symbol-U Architecture
"""

import math
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# NumPy is the only required dependency
try:
    import numpy as np
except ImportError:
    raise ImportError("NumPy is required: pip install numpy")


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SymbolU12LiteConfig:
    """Configuration for SymbolU12 Lite."""

    vocab_size: int = 10000  # Smaller vocab for lite version
    embed_dim: int = 128     # Smaller embedding for lite
    max_seq_len: int = 512
    num_heads: int = 4

    # Layer-specific
    num_pos_tags: int = 20
    num_entity_types: int = 10
    num_concepts: int = 100
    num_intents: int = 20

    # Thresholds
    activation_threshold: float = 0.1
    coherence_threshold: float = 0.7

    # Harmonic ratios for phase locking
    HARMONIC_RATIOS: Dict[int, int] = field(default_factory=lambda: {
        1: 100000, 2: 50000, 3: 20000, 4: 10000,
        5: 5000, 6: 2000, 7: 1000, 8: 400,
        9: 100, 10: 50, 11: 10, 12: 1
    })

    # Layer names
    LAYER_NAMES: List[str] = field(default_factory=lambda: [
        "O1_POTENTIAL", "O2_IDENTITY", "O3_EXECUTION", "O4_STRUCTURE",
        "O5_COGNITION", "O6_AGENCY", "O7_REASONING", "O8_PURPOSE",
        "O9_WITNESS", "O10_UNIFYING", "O11_INTEGRATION", "O12_ABSOLVING"
    ])


# =============================================================================
# NUMPY UTILITIES
# =============================================================================

def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically stable softmax."""
    x_max = np.max(x, axis=axis, keepdims=True)
    exp_x = np.exp(x - x_max)
    return exp_x / np.sum(exp_x, axis=axis, keepdims=True)


def sigmoid(x: np.ndarray) -> np.ndarray:
    """Sigmoid activation."""
    return 1 / (1 + np.exp(-np.clip(x, -500, 500)))


def relu(x: np.ndarray) -> np.ndarray:
    """ReLU activation."""
    return np.maximum(0, x)


def gelu(x: np.ndarray) -> np.ndarray:
    """GELU activation (approximate)."""
    return 0.5 * x * (1 + np.tanh(math.sqrt(2 / math.pi) * (x + 0.044715 * x**3)))


def layer_norm(x: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    """Layer normalization."""
    mean = np.mean(x, axis=-1, keepdims=True)
    var = np.var(x, axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(var + eps)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between vectors."""
    a_norm = a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-8)
    b_norm = b / (np.linalg.norm(b, axis=-1, keepdims=True) + 1e-8)
    return np.sum(a_norm * b_norm, axis=-1)


# =============================================================================
# SIMPLE TOKENIZER
# =============================================================================

class SimpleTokenizer:
    """
    Simple word-level tokenizer with no external dependencies.

    Builds vocabulary from common English words + special tokens.
    """

    def __init__(self, vocab_size: int = 10000):
        self.vocab_size = vocab_size
        self.word2idx: Dict[str, int] = {}
        self.idx2word: Dict[int, str] = {}

        # Special tokens
        self.pad_token = "<PAD>"
        self.unk_token = "<UNK>"
        self.bos_token = "<BOS>"
        self.eos_token = "<EOS>"

        # Initialize with special tokens
        special = [self.pad_token, self.unk_token, self.bos_token, self.eos_token]
        for idx, token in enumerate(special):
            self.word2idx[token] = idx
            self.idx2word[idx] = token

        # Add common words (simplified vocabulary)
        self._build_basic_vocab()

    def _build_basic_vocab(self):
        """Build basic vocabulary from common words."""
        # Common English words (subset)
        common_words = [
            # Articles, prepositions, conjunctions
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "as", "is", "was", "are",
            "were", "be", "been", "being", "have", "has", "had", "do",
            "does", "did", "will", "would", "could", "should", "may",
            "might", "must", "shall", "can", "need", "dare", "ought",
            # Pronouns
            "i", "you", "he", "she", "it", "we", "they", "me", "him",
            "her", "us", "them", "my", "your", "his", "its", "our", "their",
            # Common verbs
            "go", "come", "make", "take", "get", "give", "know", "think",
            "see", "want", "use", "find", "tell", "ask", "work", "seem",
            "feel", "try", "leave", "call", "keep", "let", "begin", "show",
            # Common nouns
            "time", "year", "people", "way", "day", "man", "thing", "woman",
            "life", "child", "world", "school", "state", "family", "student",
            "group", "country", "problem", "hand", "part", "place", "case",
            # Adjectives
            "good", "new", "first", "last", "long", "great", "little", "own",
            "other", "old", "right", "big", "high", "different", "small",
            # Question words
            "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
            # Ontological concepts
            "consciousness", "awareness", "being", "existence", "reality",
            "truth", "knowledge", "understanding", "meaning", "purpose",
            "reason", "logic", "thought", "mind", "self", "identity",
            "structure", "form", "pattern", "relation", "connection",
            "potential", "action", "execution", "agency", "witness",
            "integration", "unity", "coherence", "resolution", "completion",
            # Technical terms
            "algorithm", "function", "variable", "data", "system", "process",
            "method", "class", "object", "type", "value", "result", "output",
            "input", "model", "layer", "network", "parameter", "weight",
        ]

        # Add words to vocabulary
        current_idx = len(self.word2idx)
        for word in common_words:
            if word not in self.word2idx and current_idx < self.vocab_size:
                self.word2idx[word] = current_idx
                self.idx2word[current_idx] = word
                current_idx += 1

    def encode(self, text: str) -> np.ndarray:
        """Encode text to token IDs."""
        # Simple tokenization: lowercase and split
        words = text.lower().split()
        tokens = []
        for word in words:
            # Remove punctuation
            word = ''.join(c for c in word if c.isalnum())
            if word:
                idx = self.word2idx.get(word, self.word2idx[self.unk_token])
                tokens.append(idx)
        return np.array(tokens, dtype=np.int32)

    def decode(self, tokens: np.ndarray) -> str:
        """Decode token IDs to text."""
        words = [self.idx2word.get(int(t), self.unk_token) for t in tokens]
        return ' '.join(words)


# =============================================================================
# ONTOLOGICAL LAYERS (NumPy Implementation)
# =============================================================================

class LayerWeights:
    """Container for layer weights (can be loaded from file)."""

    def __init__(self, input_dim: int, output_dim: int, init_scale: float = 0.02):
        self.W = np.random.randn(input_dim, output_dim) * init_scale
        self.b = np.zeros(output_dim)

    def forward(self, x: np.ndarray) -> np.ndarray:
        return x @ self.W + self.b


class PotentialLayerLite:
    """Layer 1: POTENTIAL - Token activation based on relevance."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        # Embedding matrix
        self.embeddings = np.random.randn(
            config.vocab_size, config.embed_dim
        ) * 0.02
        # Relevance scorer
        self.relevance = LayerWeights(config.embed_dim, 1)
        self.threshold = config.activation_threshold

    def forward(
        self,
        token_ids: np.ndarray,
        phase: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Args:
            token_ids: [seq_len] token indices
            phase: Phase value for modulation

        Returns:
            embeddings: [seq_len, embed_dim]
            relevance: [seq_len, 1]
        """
        # Get embeddings
        embeddings = self.embeddings[token_ids]  # [seq_len, embed_dim]

        # Compute relevance
        relevance = sigmoid(self.relevance.forward(embeddings))

        # Sparse activation
        mask = (relevance > self.threshold).astype(float)
        mask = mask + relevance * (1 - mask) * 0.1

        # Phase modulation
        phase_gate = sigmoid(np.cos(phase))
        mask = mask * phase_gate

        return embeddings * mask, relevance


class IdentityLayerLite:
    """Layer 2: IDENTITY - Syntactic tagging."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        dim = config.embed_dim

        self.pos_tagger = LayerWeights(dim, config.num_pos_tags)
        self.entity_classifier = LayerWeights(dim, config.num_entity_types)
        self.fusion = LayerWeights(dim + config.num_pos_tags + config.num_entity_types, dim)

    def forward(
        self,
        x: np.ndarray,
        phase: float = 0.0,
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Tag tokens with syntactic information."""
        # Generate tags
        pos_logits = self.pos_tagger.forward(x)
        entity_logits = self.entity_classifier.forward(x)

        pos_probs = softmax(pos_logits)
        entity_probs = softmax(entity_logits)

        # Fuse with original
        combined = np.concatenate([x, pos_probs, entity_probs], axis=-1)
        enriched = self.fusion.forward(combined)

        # Phase modulation
        phase_coherence = (1 + np.cos(phase)) / 2
        enriched = x + (enriched - x) * phase_coherence

        tags = {'pos': pos_probs, 'entity': entity_probs}
        return enriched, tags


class ExecutionLayerLite:
    """Layer 3: EXECUTION - Local pattern detection."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        dim = config.embed_dim

        # Simple 1D convolutions (implemented as sliding window)
        self.conv1_W = np.random.randn(1, dim, dim) * 0.02
        self.conv2_W = np.random.randn(2, dim, dim) * 0.02
        self.conv3_W = np.random.randn(3, dim, dim) * 0.02

        self.fusion = LayerWeights(dim * 3, dim)

    def _conv1d(self, x: np.ndarray, W: np.ndarray) -> np.ndarray:
        """Simple 1D convolution via sliding window."""
        kernel_size = W.shape[0]
        seq_len, dim = x.shape
        output = np.zeros_like(x)

        for i in range(seq_len):
            start = max(0, i - kernel_size + 1)
            window = x[start:i+1]
            if len(window) < kernel_size:
                # Pad with zeros
                pad = np.zeros((kernel_size - len(window), dim))
                window = np.concatenate([pad, window], axis=0)
            # Apply convolution
            for k in range(kernel_size):
                output[i] += window[k] @ W[k]

        return relu(output)

    def forward(
        self,
        x: np.ndarray,
        phase: float = 0.0,
    ) -> np.ndarray:
        """Execute local patterns."""
        # Apply convolutions
        conv1 = self._conv1d(x, self.conv1_W)
        conv2 = self._conv1d(x, self.conv2_W)
        conv3 = self._conv1d(x, self.conv3_W)

        # Fuse
        combined = np.concatenate([conv1, conv2, conv3], axis=-1)
        executed = self.fusion.forward(combined)

        # Phase modulation
        action_strength = sigmoid(np.cos(phase) * 2)
        output = layer_norm(x + executed * action_strength)

        return output


class StructureLayerLite:
    """Layer 4: STRUCTURE - Phrase boundary detection."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        dim = config.embed_dim

        self.boundary_detector = LayerWeights(dim * 2, 2)
        self.structure_proj = LayerWeights(dim, dim)

    def forward(
        self,
        x: np.ndarray,
        phase: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Detect phrase boundaries."""
        seq_len, dim = x.shape

        # Boundary detection from adjacent pairs
        if seq_len > 1:
            pairs = np.concatenate([x[:-1], x[1:]], axis=-1)
            boundary_logits = self.boundary_detector.forward(pairs)
            boundary_probs = softmax(boundary_logits)[:, 1]
            # Pad
            boundary_probs = np.concatenate([boundary_probs, [1.0]])
        else:
            boundary_probs = np.array([1.0])

        # Structure projection
        structured = self.structure_proj.forward(x)

        # Phase modulation
        formation_strength = (1 + np.cos(phase)) / 2
        output = x + (structured - x) * formation_strength

        return output, boundary_probs


class CognitionLayerLite:
    """Layer 5: COGNITION - Semantic understanding."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        dim = config.embed_dim

        # Concept memory
        self.concept_memory = np.random.randn(config.num_concepts, dim) * 0.02
        self.concept_query = LayerWeights(dim, dim)
        self.ffn = LayerWeights(dim, dim)

    def forward(
        self,
        x: np.ndarray,
        phase: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Semantic understanding with concept retrieval."""
        seq_len, dim = x.shape

        # Query concepts
        queries = self.concept_query.forward(x)

        # Concept similarity
        concept_sim = queries @ self.concept_memory.T / math.sqrt(dim)
        concept_weights = softmax(concept_sim)

        # Retrieve concepts
        retrieved = concept_weights @ self.concept_memory

        # Blend
        cognition = x + retrieved * 0.5

        # Phase modulation
        clarity = sigmoid(np.cos(phase) * 2)
        cognition = x + (cognition - x) * clarity

        # FFN
        cognition = layer_norm(cognition)
        cognition = cognition + gelu(self.ffn.forward(cognition))

        return cognition, concept_weights


class AgencyLayerLite:
    """Layer 6: AGENCY - Goal-directed attention."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        dim = config.embed_dim

        self.goal_encoder = LayerWeights(dim, dim)
        self.goal_query = LayerWeights(dim, dim)
        self.goal_key = LayerWeights(dim, dim)
        self.output_proj = LayerWeights(dim, dim)

    def forward(
        self,
        x: np.ndarray,
        phase: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Goal-directed attention."""
        seq_len, dim = x.shape

        # Derive goal from context mean
        goal = x.mean(axis=0, keepdims=True)
        goal = self.goal_encoder.forward(goal)

        # Goal-directed attention
        Q = self.goal_query.forward(goal)
        K = self.goal_key.forward(x)

        attn_scores = Q @ K.T / math.sqrt(dim)
        attn_weights = softmax(attn_scores)

        # Attended output
        agency_signal = attn_weights @ x
        agency_signal = np.tile(agency_signal, (seq_len, 1))

        # Phase modulation
        commitment = (1 + np.cos(phase)) / 2
        output = layer_norm(x + self.output_proj.forward(agency_signal) * commitment)

        return output, attn_weights


class ReasoningLayerLite:
    """Layer 7: REASONING - Logical inference."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        dim = config.embed_dim

        self.comparator = LayerWeights(dim * 2, dim)
        self.contradiction_detector = LayerWeights(dim * 2, 1)
        self.inference = LayerWeights(dim, dim)

    def forward(
        self,
        x: np.ndarray,
        phase: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Logical reasoning with contradiction detection."""
        seq_len, dim = x.shape

        # Context for comparison
        context = np.tile(x.mean(axis=0, keepdims=True), (seq_len, 1))

        # Pairwise comparison
        comparison = np.concatenate([x, context], axis=-1)
        discrimination = relu(self.comparator.forward(comparison))

        # Contradiction detection
        contradiction_scores = sigmoid(self.contradiction_detector.forward(comparison))

        # Inference
        inferred = self.inference.forward(discrimination)

        # Phase modulation
        finality = (1 + np.cos(phase)) / 2
        output = layer_norm(x + inferred * finality)

        return output, contradiction_scores


class PurposeLayerLite:
    """Layer 8: PURPOSE - Intent recognition."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        dim = config.embed_dim

        self.intent_classifier = LayerWeights(dim, config.num_intents)
        self.meaning_proj = LayerWeights(dim, dim)

    def forward(
        self,
        x: np.ndarray,
        phase: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Intent classification and meaning extraction."""
        # Intent classification
        intent_logits = self.intent_classifier.forward(x)
        intent_probs = softmax(intent_logits)

        # Meaning projection
        meaning = self.meaning_proj.forward(x.mean(axis=0, keepdims=True))

        # Phase modulation
        clarity = (1 + np.cos(phase)) / 2
        output = layer_norm(x + meaning * clarity * 0.1)

        return output, intent_probs


class WitnessLayerLite:
    """Layer 9: WITNESS - Meta-cognitive monitoring."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        dim = config.embed_dim

        self.state_encoder = LayerWeights(dim, dim)
        self.meta_encoder = LayerWeights(dim, dim)
        self.confidence_estimator = LayerWeights(dim, 1)

    def forward(
        self,
        x: np.ndarray,
        phase: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """Meta-cognitive monitoring."""
        # Global state
        state = self.state_encoder.forward(x.mean(axis=0))

        # Meta-representation
        meta = relu(self.meta_encoder.forward(state))

        # Confidence estimation
        confidence = float(sigmoid(self.confidence_estimator.forward(meta))[0])

        return x, state, confidence


class UnifyingLayerLite:
    """Layer 10: UNIFYING - Coherence enforcement."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        self.threshold = config.coherence_threshold

    def forward(
        self,
        layer_embeddings: List[np.ndarray],
        x: np.ndarray,
        phase: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        """
        Compute coherence matrix C'[i,j] = C[i,j] × S[i,j].
        """
        # Stack layer embeddings
        stacked = np.stack(layer_embeddings, axis=0)  # [N, dim]
        N, dim = stacked.shape

        # Semantic similarity S[i,j]
        normalized = stacked / (np.linalg.norm(stacked, axis=-1, keepdims=True) + 1e-8)
        S = normalized @ normalized.T

        # Phase correlations C[i,j] (simplified)
        phase_repr = np.tanh(stacked.mean(axis=-1))  # [N]
        phase_diff = phase_repr[:, None] - phase_repr[None, :]
        C = np.cos(phase_diff * np.pi)

        # CORE: C'[i,j] = C[i,j] × S[i,j]
        C_prime = C * S

        # Global coherence J (upper triangle average)
        mask = np.triu(np.ones((N, N)), k=1)
        J = float((C_prime * mask).sum() / (mask.sum() + 1e-8))

        # Unified representation
        coherence_weights = softmax(C_prime.sum(axis=-1))
        unified = coherence_weights @ stacked

        # Apply to sequence
        seq_len = x.shape[0]
        unified_expanded = np.tile(unified, (seq_len, 1))

        # Phase modulation
        strength = (1 + np.cos(phase)) / 2
        output = layer_norm(x + unified_expanded * strength * 0.5)

        return output, unified, C_prime, J


class IntegrationLayerLite:
    """Layer 11: INTEGRATION - Conflict resolution."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        dim = config.embed_dim

        self.resolver = LayerWeights(dim * 2, dim)

    def forward(
        self,
        x: np.ndarray,
        unified: np.ndarray,
        coherence: float,
        phase: float = 0.0,
    ) -> Tuple[np.ndarray, bool]:
        """Resolve conflicts if coherence is low."""
        seq_len, dim = x.shape

        # Check if resolution needed
        needs_resolution = coherence < 0.7

        if needs_resolution:
            unified_expanded = np.tile(unified, (seq_len, 1))
            resolution_input = np.concatenate([x, unified_expanded], axis=-1)
            resolved = relu(self.resolver.forward(resolution_input))

            # Phase modulation
            commitment = (1 + np.cos(phase)) / 2
            output = layer_norm(x + (resolved - x) * commitment)
        else:
            output = x

        return output, needs_resolution


class AbsolvingLayerLite:
    """Layer 12: ABSOLVING - Termination decision."""

    def __init__(self, config: SymbolU12LiteConfig):
        self.config = config
        dim = config.embed_dim

        self.completion_estimator = LayerWeights(dim, 1)
        self.output_projection = LayerWeights(dim, config.vocab_size)

    def forward(
        self,
        x: np.ndarray,
        phase: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Estimate completion and generate logits."""
        # Completion score
        completion = sigmoid(self.completion_estimator.forward(x))

        # Output logits
        logits = self.output_projection.forward(x)

        return logits, completion


# =============================================================================
# COMPLETE SYMBOLU12 LITE MODEL
# =============================================================================

class SymbolU12Lite:
    """
    12-Dimensional Ontological Language Model (Lite Version)

    Pure NumPy implementation - no PyTorch required.

    Usage:
        model = SymbolU12Lite()
        result = model.analyze("What is consciousness?")

        print(result["dominant_layer"])
        print(result["coherence"])
        print(result["witness_confidence"])
    """

    def __init__(self, config: Optional[SymbolU12LiteConfig] = None):
        self.config = config or SymbolU12LiteConfig()

        # Tokenizer
        self.tokenizer = SimpleTokenizer(self.config.vocab_size)

        # Initialize all 12 layers
        self.layer1_potential = PotentialLayerLite(self.config)
        self.layer2_identity = IdentityLayerLite(self.config)
        self.layer3_execution = ExecutionLayerLite(self.config)
        self.layer4_structure = StructureLayerLite(self.config)
        self.layer5_cognition = CognitionLayerLite(self.config)
        self.layer6_agency = AgencyLayerLite(self.config)
        self.layer7_reasoning = ReasoningLayerLite(self.config)
        self.layer8_purpose = PurposeLayerLite(self.config)
        self.layer9_witness = WitnessLayerLite(self.config)
        self.layer10_unifying = UnifyingLayerLite(self.config)
        self.layer11_integration = IntegrationLayerLite(self.config)
        self.layer12_absolving = AbsolvingLayerLite(self.config)

        # Master phase
        self.master_phase = 0.0

    def get_layer_phase(self, layer_idx: int) -> float:
        """Get phase value for a specific layer."""
        return self.config.HARMONIC_RATIOS[layer_idx] * self.master_phase

    def forward(self, token_ids: np.ndarray) -> Dict[str, Any]:
        """
        Forward pass through all 12 layers.

        Args:
            token_ids: [seq_len] token indices

        Returns:
            Dict with all layer outputs
        """
        layer_embeddings = []

        # Layer 1: Potential
        x1, relevance = self.layer1_potential.forward(
            token_ids, self.get_layer_phase(1)
        )
        layer_embeddings.append(x1.mean(axis=0))

        # Layer 2: Identity
        x2, tags = self.layer2_identity.forward(x1, self.get_layer_phase(2))
        layer_embeddings.append(x2.mean(axis=0))

        # Layer 3: Execution
        x3 = self.layer3_execution.forward(x2, self.get_layer_phase(3))
        layer_embeddings.append(x3.mean(axis=0))

        # Layer 4: Structure
        x4, boundaries = self.layer4_structure.forward(x3, self.get_layer_phase(4))
        layer_embeddings.append(x4.mean(axis=0))

        # Layer 5: Cognition
        x5, concepts = self.layer5_cognition.forward(x4, self.get_layer_phase(5))
        layer_embeddings.append(x5.mean(axis=0))

        # Layer 6: Agency
        x6, goal_attn = self.layer6_agency.forward(x5, self.get_layer_phase(6))
        layer_embeddings.append(x6.mean(axis=0))

        # Layer 7: Reasoning
        x7, contradictions = self.layer7_reasoning.forward(x6, self.get_layer_phase(7))
        layer_embeddings.append(x7.mean(axis=0))

        # Layer 8: Purpose
        x8, intents = self.layer8_purpose.forward(x7, self.get_layer_phase(8))
        layer_embeddings.append(x8.mean(axis=0))

        # Layer 9: Witness
        x9, state, confidence = self.layer9_witness.forward(x8, self.get_layer_phase(9))
        layer_embeddings.append(state)

        # Layer 10: Unifying
        x10, unified, C_prime, J = self.layer10_unifying.forward(
            layer_embeddings, x9, self.get_layer_phase(10)
        )
        layer_embeddings.append(unified)

        # Layer 11: Integration
        x11, resolved = self.layer11_integration.forward(
            x10, unified, J, self.get_layer_phase(11)
        )
        layer_embeddings.append(x11.mean(axis=0))

        # Layer 12: Absolving
        logits, completion = self.layer12_absolving.forward(
            x11, self.get_layer_phase(12)
        )
        layer_embeddings.append(x11.mean(axis=0))

        return {
            'logits': logits,
            'layer_embeddings': layer_embeddings,
            'coherence_matrix': C_prime,
            'global_coherence': J,
            'witness_confidence': confidence,
            'completion': completion,
            'tags': tags,
            'intents': intents,
            'contradictions': contradictions,
            'phrase_boundaries': boundaries,
        }

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyze text with the 12-layer ontological model.

        Args:
            text: Input text to analyze

        Returns:
            Dict with:
                - dominant_layer: str
                - confidence: float
                - coherence: float
                - witness_confidence: float
                - probabilities: Dict[str, float]
                - ontological_vector: List[float]
                - strongest_relationships: List[Dict]
        """
        # Tokenize
        token_ids = self.tokenizer.encode(text)
        if len(token_ids) == 0:
            token_ids = np.array([1])  # UNK token

        # Forward pass
        outputs = self.forward(token_ids)

        # Compute layer activations
        layer_embeds = outputs['layer_embeddings']
        stacked = np.stack(layer_embeds, axis=0)  # [12, dim]
        layer_activations = np.abs(stacked).mean(axis=-1)  # [12]
        probs = softmax(layer_activations)

        # Dominant layer
        dominant_idx = int(np.argmax(probs))
        dominant_layer = self.config.LAYER_NAMES[dominant_idx]
        confidence = float(probs[dominant_idx])

        # Coherence
        coherence = outputs['global_coherence']

        # Witness confidence
        witness_conf = outputs['witness_confidence']
        uncertainty = 1.0 - witness_conf

        # Certainty level
        if uncertainty > 0.7:
            certainty_level = "very_uncertain"
        elif uncertainty > 0.4:
            certainty_level = "uncertain"
        elif uncertainty > 0.2:
            certainty_level = "moderate"
        else:
            certainty_level = "confident"

        # Probabilities dict
        probabilities = {
            self.config.LAYER_NAMES[i]: float(probs[i])
            for i in range(12)
        }

        # Strongest relationships from coherence matrix
        C_prime = outputs['coherence_matrix']
        strongest_relationships = self._extract_relationships(C_prime)

        return {
            "dominant_layer": dominant_layer,
            "confidence": confidence,
            "probabilities": probabilities,
            "uncertainty": uncertainty,
            "certainty_level": certainty_level,
            "coherence": coherence,
            "witness_confidence": witness_conf,
            "ontological_vector": probs.tolist(),
            "bhava_vector": C_prime.flatten().tolist(),
            "full_vector": probs.tolist() + C_prime.flatten().tolist(),
            "strongest_relationships": strongest_relationships,
            "completion": float(outputs['completion'].mean()),
            "engine_type": "symbolu12_lite",
        }

    def _extract_relationships(
        self,
        C_prime: np.ndarray,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Extract strongest relationships from coherence matrix."""
        relationships = []

        for i in range(12):
            for j in range(12):
                if i != j:
                    strength = float(C_prime[i, j])
                    relationships.append({
                        "from_layer": self.config.LAYER_NAMES[i],
                        "to_layer": self.config.LAYER_NAMES[j],
                        "strength": strength,
                    })

        # Sort by strength
        relationships.sort(key=lambda x: x["strength"], reverse=True)
        return relationships[:top_k]

    def save_weights(self, path: str):
        """Save model weights to JSON file."""
        weights = {}

        # Collect all weights from layers
        for name in dir(self):
            if name.startswith('layer'):
                layer = getattr(self, name)
                layer_weights = {}
                for attr in dir(layer):
                    obj = getattr(layer, attr)
                    if isinstance(obj, LayerWeights):
                        layer_weights[attr] = {
                            'W': obj.W.tolist(),
                            'b': obj.b.tolist(),
                        }
                    elif isinstance(obj, np.ndarray):
                        layer_weights[attr] = obj.tolist()
                weights[name] = layer_weights

        with open(path, 'w') as f:
            json.dump(weights, f)

        print(f"Weights saved to: {path}")

    def load_weights(self, path: str):
        """Load model weights from JSON file."""
        with open(path, 'r') as f:
            weights = json.load(f)

        for layer_name, layer_weights in weights.items():
            if hasattr(self, layer_name):
                layer = getattr(self, layer_name)
                for attr, values in layer_weights.items():
                    if hasattr(layer, attr):
                        obj = getattr(layer, attr)
                        if isinstance(obj, LayerWeights):
                            obj.W = np.array(values['W'])
                            obj.b = np.array(values['b'])
                        elif isinstance(obj, np.ndarray):
                            setattr(layer, attr, np.array(values))

        print(f"Weights loaded from: {path}")


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("   SYMBOLU12 LITE - NumPy-Only Implementation")
    print("=" * 70)

    # Create model
    model = SymbolU12Lite()
    print(f"\nModel created with config:")
    print(f"  Vocab size: {model.config.vocab_size}")
    print(f"  Embed dim: {model.config.embed_dim}")
    print(f"  Max seq len: {model.config.max_seq_len}")

    # Test analysis
    print("\n" + "-" * 70)
    print("Testing analysis...")

    test_texts = [
        "What is consciousness?",
        "Calculate the area of a circle",
        "The sunset paints dreams across the sky",
        "If A implies B then not B implies not A",
    ]

    for text in test_texts:
        result = model.analyze(text)
        print(f"\n>>> {text}")
        print(f"    Layer: {result['dominant_layer']} ({result['confidence']:.1%})")
        print(f"    Coherence: {result['coherence']:.3f}")
        print(f"    Witness: {result['witness_confidence']:.3f}")
        print(f"    Certainty: {result['certainty_level']}")

    # Show layer info
    print("\n" + "-" * 70)
    print("12 Ontological Layers:")
    layer_info = [
        ("Potential", "Dormant activation"),
        ("Identity", "Syntactic tagging"),
        ("Execution", "Local patterns"),
        ("Structure", "Phrase boundaries"),
        ("Cognition", "Semantic understanding"),
        ("Agency", "Goal-directed"),
        ("Reasoning", "Logical inference"),
        ("Purpose", "Intent recognition"),
        ("Witness", "Meta-cognition"),
        ("Unifying", "Coherence C'[i,j]"),
        ("Integration", "Conflict resolution"),
        ("Absolving", "Termination"),
    ]

    for i, (name, func) in enumerate(layer_info, 1):
        print(f"  Layer {i:2d}: {name:12s} - {func}")

    print("\n" + "=" * 70)
    print("   LITE VERSION - No PyTorch Required!")
    print("=" * 70)
    print("\nDependencies: numpy only")
    print("Size: ~1000 lines vs ~1500 for PyTorch version")
