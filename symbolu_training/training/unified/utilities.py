"""Utility classes and functions extracted from train_unified_llm.py.

Includes byte-level tokenizer fallback, CSR (Cognitive Speech Recognition)
helpers for sparse delayed supervision, and the Sovereign R-Matrix with
associated Vrtti / ontological-layer helpers.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple


class _SimpleByteTokenizer:
    """Minimal byte-level tokenizer fallback when HuggingFace is unavailable."""

    name_or_path = "byte-fallback"
    eos_token_id = 0
    model_max_length = int(1e12)

    def encode(self, text, return_tensors=None, **kwargs):
        ids = [b + 1 for b in text.encode("utf-8", errors="replace")]  # 1-indexed
        if return_tensors == "pt":
            return torch.tensor([ids], dtype=torch.long)
        return ids

    def decode(self, ids, skip_special_tokens=False, **kwargs):
        if isinstance(ids, torch.Tensor):
            ids = ids.tolist()
        if isinstance(ids, list) and ids and isinstance(ids[0], list):
            ids = ids[0]
        return bytes([max(0, i - 1) for i in ids]).decode("utf-8", errors="replace")

    def convert_ids_to_tokens(self, ids):
        if isinstance(ids, torch.Tensor):
            ids = ids.tolist()
        return [chr(max(0, i - 1)) if 0 < i < 128 else f"<{i}>" for i in ids]

    @property
    def vocab_size(self):
        return 256


CSR_STOPWORDS = {
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
    'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
    'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her',
    'she', 'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there',
    'their', 'what', 'so', 'up', 'out', 'if', 'about', 'who', 'get',
    'which', 'go', 'me', 'when', 'make', 'can', 'like', 'time', 'no',
    'just', 'him', 'know', 'take', 'people', 'into', 'year', 'your',
    'good', 'some', 'could', 'them', 'see', 'other', 'than', 'then',
    'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
    'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first',
    'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these',
    'give', 'day', 'most', 'us'
}


class WholeWordCSRHelper:
    """
    V9.7.0: Helper for Sparse Delayed Supervision.

    Computes word boundaries, content weights, and whole-word varna targets
    for a batch of token sequences.

    This enables ontological supervision at the semantic level (whole words)
    rather than the syntactic level (subword tokens).
    """

    def __init__(self, tokenizer, csr_provider):
        """
        Initialize the helper.

        Args:
            tokenizer: HuggingFace tokenizer (GPT-2 style with Ġ prefix)
            csr_provider: CSREmbeddingProvider instance for varna lookup
        """
        self.tokenizer = tokenizer
        self.csr_provider = csr_provider
        self._cache = {}  # Cache whole-word varna lookups

    def compute_word_boundaries(self, input_ids: torch.Tensor) -> tuple:
        """
        Compute word boundaries and content weights for a batch.

        Args:
            input_ids: (batch_size, seq_len) tensor of token IDs

        Returns:
            word_end_mask: (batch_size, seq_len) tensor, 1.0 at word ends
            content_weight: (batch_size, seq_len) tensor, 1.0 for content words
            whole_word_varna: (batch_size, seq_len, 12) tensor of varna targets
        """
        batch_size, seq_len = input_ids.shape
        device = input_ids.device

        # Initialize outputs
        word_end_mask = torch.zeros(batch_size, seq_len, device=device)
        content_weight = torch.ones(batch_size, seq_len, device=device)
        whole_word_varna = torch.zeros(batch_size, seq_len, 12, device=device)

        # Process each sequence in batch
        for b in range(batch_size):
            ids = input_ids[b].tolist()
            tokens = self.tokenizer.convert_ids_to_tokens(ids)

            # Track current word being built
            current_word_tokens = []
            current_word_start = 0

            for i, token in enumerate(tokens):
                # Check if this token starts a new word (has Ġ prefix or is special)
                is_word_start = (
                    token.startswith('Ġ') or
                    token.startswith('<') or  # Special tokens
                    i == 0  # First token always starts a word
                )

                if is_word_start and current_word_tokens:
                    # Previous word ended at i-1
                    self._finalize_word(
                        word_end_mask, content_weight, whole_word_varna,
                        b, i - 1, current_word_tokens
                    )
                    current_word_tokens = []
                    current_word_start = i

                # Add to current word (strip Ġ prefix)
                clean_token = token.lstrip('Ġ') if token.startswith('Ġ') else token
                if not token.startswith('<'):  # Skip special tokens
                    current_word_tokens.append(clean_token)

            # Finalize last word
            if current_word_tokens:
                self._finalize_word(
                    word_end_mask, content_weight, whole_word_varna,
                    b, seq_len - 1, current_word_tokens
                )

        return word_end_mask, content_weight, whole_word_varna

    def _finalize_word(
        self,
        word_end_mask: torch.Tensor,
        content_weight: torch.Tensor,
        whole_word_varna: torch.Tensor,
        batch_idx: int,
        end_pos: int,
        word_tokens: list
    ):
        """
        Finalize a word: mark boundary, compute weight, get varna.

        Args:
            word_end_mask: Mask tensor to update
            content_weight: Weight tensor to update
            whole_word_varna: Varna tensor to update
            batch_idx: Batch index
            end_pos: Position of word end token
            word_tokens: List of subword tokens forming the word
        """
        # Mark word end
        word_end_mask[batch_idx, end_pos] = 1.0

        # Reconstruct whole word
        whole_word = ''.join(word_tokens).lower()

        # Check if stopword
        if whole_word in CSR_STOPWORDS:
            content_weight[batch_idx, end_pos] = 0.0
        else:
            content_weight[batch_idx, end_pos] = 1.0

        # Get varna for whole word (cached)
        varna = self._get_whole_word_varna(whole_word)
        if varna is not None:
            whole_word_varna[batch_idx, end_pos] = varna

    def _get_whole_word_varna(self, word: str) -> Optional[torch.Tensor]:
        """
        Get 12D varna vector for a whole word.

        Uses CSR provider's G2P and varna lookup, with caching.
        """
        if word in self._cache:
            return self._cache[word]

        if self.csr_provider is None:
            return None

        try:
            # Get phonemes for whole word
            phonemes = self.csr_provider.token_to_phonemes(word)
            if not phonemes:
                self._cache[word] = None
                return None

            # Convert phonemes to varna affinity
            # Use the provider's internal method
            varna = self.csr_provider._phonemes_to_varna_affinity(phonemes)
            if varna is not None:
                self._cache[word] = varna
            else:
                self._cache[word] = None
            return varna

        except Exception:
            self._cache[word] = None
            return None


def calculate_sparse_csr_loss(
    hidden_states: torch.Tensor,
    whole_word_varna: torch.Tensor,
    word_end_mask: torch.Tensor,
    content_weight: torch.Tensor,
    csr_projector: torch.nn.Module,
    tau: float = 0.07,
    lambda_csr: float = 0.1,
    content_word_only: bool = False
) -> tuple:
    """
    V9.7.0: Calculate CSR loss with Sparse Delayed Supervision.

    Only applies loss at word boundaries, using whole-word varna targets.

    Math:
        L_CSR = Σ(RawLoss × WordEndMask × ContentWeight) / (Σ(WordEndMask × ContentWeight) + ε)

    Args:
        hidden_states: (batch, seq, hidden_dim) from alignment layer
        whole_word_varna: (batch, seq, 12) varna targets for whole words
        word_end_mask: (batch, seq) binary mask for word boundaries
        content_weight: (batch, seq) weight (0 for stopwords, 1 for content)
        csr_projector: Linear layer projecting hidden → varna space
        tau: Temperature for InfoNCE
        lambda_csr: CSR loss weight
        content_word_only: If True, apply content_weight; otherwise all words

    Returns:
        (csr_loss, metrics_dict)
    """
    # Project hidden states to varna space
    varna_predicted = csr_projector(hidden_states)  # (B, S, 12)

    # Normalize both for cosine similarity
    varna_pred_norm = F.normalize(varna_predicted, dim=-1)
    varna_target_norm = F.normalize(whole_word_varna, dim=-1)

    # Cosine similarity per position
    similarity = (varna_pred_norm * varna_target_norm).sum(dim=-1)  # (B, S)

    # Raw loss: (1 - similarity) / tau
    raw_loss = (1 - similarity) / tau

    # Apply masks
    if content_word_only:
        mask = word_end_mask * content_weight  # (B, S)
    else:
        mask = word_end_mask  # (B, S)

    # Masked loss
    masked_loss = raw_loss * mask

    # Normalize by number of valid positions
    num_valid = mask.sum() + 1e-6
    csr_loss = (masked_loss.sum() / num_valid) * lambda_csr

    # Compute metrics
    with torch.no_grad():
        # Average similarity at word boundaries
        valid_sim = (similarity * mask).sum() / num_valid
        # Number of content words vs stopwords
        num_content = (word_end_mask * content_weight).sum()
        num_stopword = (word_end_mask * (1 - content_weight)).sum()

    metrics = {
        'csr_sparse_loss': csr_loss.item(),
        'csr_sparse_similarity': valid_sim.item(),
        'csr_num_content_words': num_content.item(),
        'csr_num_stopwords': num_stopword.item(),
        'csr_num_boundaries': mask.sum().item(),
    }

    return csr_loss, metrics


SOVEREIGN_R_MATRIX = torch.tensor([
    # O1    O2    O3    O4    O5    O6    O7    O8    O9   O10   O11   O12
    # POT  IDEN  EXEC  STRC  COGN  AGEN  REAS  PURP  WITN  UNIF  INTG  ABSL
    [0.1, 0.5, 0.7, 0.7, 0.8, 0.6, 0.9, 0.8, 0.6, 0.7, 0.5, 0.9],  # Pramāṇa (Truth)
    [0.1, 0.2, 0.2, 0.4, 0.4, 0.4, 0.1, 0.1, 0.2, 0.2, 0.2, 0.3],  # Vikalpa (Fancy)
    [0.1, 0.2, 0.4, 0.4, 0.2, 0.3, 0.1, 0.1, 0.1, 0.1, 0.1, 0.0],  # Viparyaya (Error)
    [0.7, 0.1, 0.1, 0.3, 0.1, 0.1, 0.0, 0.0, 0.3, 0.3, 0.4, 0.1],  # Nidrā (Sleep)
    [0.1, 0.1, 0.3, 0.3, 0.2, 0.2, 0.1, 0.0, 0.2, 0.2, 0.2, 0.8],  # Smṛti (Memory)
], dtype=torch.float32)

# Vṛtti names for logging/debugging (English functional equivalents)
VRTTI_NAMES = ["Fact", "Imagination", "Error", "Void", "Memory"]

# 12 Ontological Layer names (patent-exact sequence)
ONTOLOGICAL_LAYER_NAMES = [
    "O1_POTENTIAL",    # Dormant capacity, latent possibility
    "O2_IDENTITY",     # Classificatory marking, role assignment
    "O3_EXECUTION",    # Immediate somatic initiation, karma
    "O4_STRUCTURE",    # Shaping force, embodiment
    "O5_COGNITION",    # Mental processing, understanding
    "O6_AGENCY",       # Self-direction, ego function
    "O7_REASONING",    # Intellect, truth discrimination
    "O8_PURPOSE",      # Soul intention, meaning
    "O9_WITNESSES",    # Observer awareness
    "O10_UNIFYING",    # Atman, self-integration
    "O11_INTEGRATION", # Brahman, cosmic unity
    "O12_ABSOLVING",   # Release, resolution, coherence
]


def get_layer_vrtti_weights(layer_idx: int, device: torch.device = None) -> torch.Tensor:
    """
    Get the Vṛtti probability weights for a specific layer (Aspect).

    Args:
        layer_idx: Layer index (0-11)
        device: Target device for the tensor

    Returns:
        Tensor of shape (5,) with Vṛtti weights for this layer
    """
    layer_idx = min(layer_idx, 11)  # Clamp to 12 Aspects
    weights = SOVEREIGN_R_MATRIX[:, layer_idx]
    if device is not None:
        weights = weights.to(device)
    return weights


def get_pramana_weights(device: torch.device = None) -> torch.Tensor:
    """
    Get the Pramāṇa (Truth) row for confidence scoring.

    The Pramāṇa row indicates how much each layer should prioritize
    truth discrimination. Used by Sattvic Brake to assess model confidence.

    Returns:
        Tensor of shape (12,) with Pramāṇa weights per layer
    """
    weights = SOVEREIGN_R_MATRIX[0, :]  # Row 0 = Pramāṇa
    if device is not None:
        weights = weights.to(device)
    return weights


def get_layer_gradient_scale(layer_idx: int, mode: str = "truth") -> float:
    """
    Get gradient scale factor for a layer based on R-Matrix Vṛtti targets.

    This allows HierarchicalGradientScaler to apply Vṛtti-aware scaling:
    - "truth" mode: Scale by Pramāṇa (higher = more important for truth)
    - "stability" mode: Scale by 1 - Viparyaya (avoid error-prone layers)
    - "memory" mode: Scale by Smṛti (prioritize context retention)

    Args:
        layer_idx: Layer index (0-11)
        mode: Weighting mode ("truth", "stability", "memory")

    Returns:
        Scale factor in [0.1, 1.0] range
    """
    layer_idx = min(layer_idx, 11)

    if mode == "truth":
        # Pramāṇa row (index 0)
        return float(SOVEREIGN_R_MATRIX[0, layer_idx])
    elif mode == "stability":
        # 1 - Viparyaya (index 2): lower error tendency = higher scale
        return float(1.0 - SOVEREIGN_R_MATRIX[2, layer_idx])
    elif mode == "memory":
        # Smṛti row (index 4)
        return float(SOVEREIGN_R_MATRIX[4, layer_idx])
    else:
        # Default: average of Pramāṇa and Smṛti
        pramana = SOVEREIGN_R_MATRIX[0, layer_idx]
        smriti = SOVEREIGN_R_MATRIX[4, layer_idx]
        return float((pramana + smriti) / 2)


def get_dominant_vrtti(layer_idx: int) -> Tuple[int, str, float]:
    """
    Get the dominant Vṛtti for a layer based on R-Matrix.

    Returns:
        (vrtti_index, vrtti_name, weight)
    """
    layer_idx = min(layer_idx, 11)
    vrtti_weights = SOVEREIGN_R_MATRIX[:, layer_idx]
    dominant_idx = torch.argmax(vrtti_weights).item()
    return (
        dominant_idx,
        VRTTI_NAMES[dominant_idx],
        float(vrtti_weights[dominant_idx])
    )
