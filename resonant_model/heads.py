"""
Binding Attention Heads
========================

Two attention head implementations for the binding benchmark:

Model A: SoftmaxBindingHead
  - Standard linear softmax attention over token embeddings.
  - Computes Q/K/V projections, softmax(QK^T/sqrt(d)) * V.
  - Baseline for role-filler binding.

Model B: ResonanceBindingHead
  - Interference-based attention using phase cross-terms.
  - Encodes tokens as phase vectors, computes pairwise interference
    via cos(phi_i - phi_j) cross-terms.
  - Interference matrix modulates attention: tokens whose phases
    constructively interfere get amplified; destructive interference
    suppresses spurious bindings.

Both heads:
  - Accept tokenized passage+question input.
  - Produce per-name logits for answer selection.
  - Use the same embedding dimension and parameter budget.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


@dataclass
class HeadConfig:
    """Shared configuration for binding heads."""
    vocab_size: int = 256          # character-level vocab
    embed_dim: int = 128           # embedding dimension
    num_heads: int = 4             # attention heads
    num_layers: int = 2            # transformer layers
    max_seq_len: int = 512         # max sequence length
    max_names: int = 24            # max answer candidates
    dropout: float = 0.1


# ─── Tokenizer ────────────────────────────────────────────────────────────────

class CharTokenizer:
    """Simple character-level tokenizer for binding benchmarks."""

    PAD = 0
    UNK = 1
    SEP = 2  # separator between passage and question

    def __init__(self, vocab_size: int = 256):
        self.vocab_size = vocab_size

    def encode(
        self,
        passage: str,
        question: str,
        max_len: int = 512,
    ) -> Tensor:
        """Encode passage + question into token IDs."""
        text = passage + chr(self.SEP) + question
        ids = []
        for ch in text[:max_len]:
            code = ord(ch)
            if code < self.vocab_size:
                ids.append(code)
            else:
                ids.append(self.UNK)
        # Pad
        while len(ids) < max_len:
            ids.append(self.PAD)
        return torch.tensor(ids, dtype=torch.long)

    def find_name_positions(
        self,
        text: str,
        names: List[str],
        max_len: int = 512,
    ) -> Dict[str, List[int]]:
        """Find character-level start positions of each name in text."""
        positions: Dict[str, List[int]] = {}
        for name in names:
            starts = []
            idx = 0
            while idx < min(len(text), max_len):
                pos = text.find(name, idx)
                if pos == -1 or pos >= max_len:
                    break
                starts.append(pos)
                idx = pos + len(name)
            positions[name] = starts
        return positions


# ─── Shared Components ────────────────────────────────────────────────────────

class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding."""

    def __init__(self, embed_dim: int, max_len: int = 512):
        super().__init__()
        pe = torch.zeros(max_len, embed_dim)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, embed_dim, 2).float() * (-math.log(10000.0) / embed_dim)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # [1, max_len, D]

    def forward(self, x: Tensor) -> Tensor:
        return x + self.pe[:, :x.size(1)]


class NamePooler(nn.Module):
    """
    Pool token representations at name positions to produce per-name logits.

    For each candidate name, averages the hidden states at all positions
    where that name appears, then projects to a scalar logit.
    """

    def __init__(self, embed_dim: int):
        super().__init__()
        self.project = nn.Linear(embed_dim, 1)

    def forward(
        self,
        hidden: Tensor,
        name_masks: Tensor,
    ) -> Tensor:
        """
        Args:
            hidden: [B, L, D] hidden states.
            name_masks: [B, N_names, L] binary masks for each name's positions.

        Returns:
            logits: [B, N_names] score per candidate name.
        """
        # Expand for masking: [B, N_names, L, D]
        hidden_exp = hidden.unsqueeze(1).expand(-1, name_masks.size(1), -1, -1)
        mask_exp = name_masks.unsqueeze(-1)  # [B, N_names, L, 1]

        # Masked mean pooling
        masked = hidden_exp * mask_exp
        counts = mask_exp.sum(dim=2).clamp(min=1)  # [B, N_names, 1]
        pooled = masked.sum(dim=2) / counts  # [B, N_names, D]

        logits = self.project(pooled).squeeze(-1)  # [B, N_names]
        return logits


# ─── Model A: Softmax Baseline ───────────────────────────────────────────────

class SoftmaxAttentionLayer(nn.Module):
    """Standard multi-head self-attention with softmax normalization."""

    def __init__(self, embed_dim: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.attn = nn.MultiheadAttention(
            embed_dim, num_heads, dropout=dropout, batch_first=True,
        )
        self.norm1 = nn.LayerNorm(embed_dim)
        self.norm2 = nn.LayerNorm(embed_dim)
        self.ff = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim * 4, embed_dim),
            nn.Dropout(dropout),
        )

    def forward(self, x: Tensor) -> Tensor:
        # Self-attention with residual
        attn_out, _ = self.attn(x, x, x)
        x = self.norm1(x + attn_out)
        # Feed-forward with residual
        ff_out = self.ff(x)
        x = self.norm2(x + ff_out)
        return x


class SoftmaxBindingHead(nn.Module):
    """
    Model A: Standard softmax attention head for binding tasks.

    Architecture:
      1. Character embedding + positional encoding
      2. N transformer layers with softmax attention
      3. Name pooling -> per-name logits
    """

    def __init__(self, config: Optional[HeadConfig] = None):
        super().__init__()
        self.config = config or HeadConfig()
        c = self.config

        self.embedding = nn.Embedding(c.vocab_size, c.embed_dim, padding_idx=0)
        self.pos_enc = PositionalEncoding(c.embed_dim, c.max_seq_len)
        self.drop = nn.Dropout(c.dropout)

        self.layers = nn.ModuleList([
            SoftmaxAttentionLayer(c.embed_dim, c.num_heads, c.dropout)
            for _ in range(c.num_layers)
        ])

        self.pooler = NamePooler(c.embed_dim)
        self.tokenizer = CharTokenizer(c.vocab_size)

    def forward(
        self,
        token_ids: Tensor,
        name_masks: Tensor,
    ) -> Tensor:
        """
        Args:
            token_ids: [B, L] character token IDs.
            name_masks: [B, N_names, L] binary masks for name positions.

        Returns:
            logits: [B, N_names] per-name answer scores.
        """
        x = self.embedding(token_ids)
        x = self.pos_enc(x)
        x = self.drop(x)

        for layer in self.layers:
            x = layer(x)

        logits = self.pooler(x, name_masks)
        return logits

    def get_attention_type(self) -> str:
        return "softmax"


# ─── Model B: Resonance Interference Head ────────────────────────────────────

class InterferenceAttentionLayer(nn.Module):
    """
    Interference-based attention layer using phase cross-terms.

    Instead of softmax(QK^T/sqrt(d)), computes:

    1. Phase encoding: phi_i = 2*pi * sigmoid(W_phase * x_i)
    2. Interference matrix: I[i,j] = mean_k(cos(phi_i[k] - phi_j[k]))
       This captures constructive/destructive interference between tokens.
    3. Cross-term modulation: A[i,j] = (QK^T/sqrt(d)) * (1 + lambda * I[i,j])
       The interference cross-terms amplify structurally coherent bindings
       and suppress spurious nearest-name associations.
    4. Normalize via softmax over the modulated scores.

    The key insight: interference cross-terms encode structural similarity
    between role-filler pairs. Tokens that play similar structural roles
    (e.g., both are recipients) have aligned phases and constructively
    interfere, strengthening the correct binding signal.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        lambda_interference: float = 0.3,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.lambda_interference = lambda_interference

        # Standard Q/K/V projections
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # Phase projection: maps embeddings to phase vectors
        self.phase_proj = nn.Linear(embed_dim, embed_dim)

        # Learnable interference strength per head
        self.interference_gate = nn.Parameter(
            torch.full((num_heads, 1, 1), lambda_interference)
        )

        self.norm1 = nn.LayerNorm(embed_dim)
        self.norm2 = nn.LayerNorm(embed_dim)
        self.ff = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim * 4, embed_dim),
            nn.Dropout(dropout),
        )
        self.dropout = nn.Dropout(dropout)

    def _compute_interference(self, x: Tensor) -> Tensor:
        """
        Compute pairwise interference matrix from phase encodings.

        Args:
            x: [B, L, D] input embeddings.

        Returns:
            interference: [B, H, L, L] interference cross-term matrix.
        """
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        # Phase encoding: map to [0, 2*pi]
        phases = torch.sigmoid(self.phase_proj(x)) * (2 * math.pi)
        # Reshape to heads: [B, H, L, d_h]
        phases = phases.view(B, L, H, d_h).transpose(1, 2)

        # Pairwise phase difference: [B, H, L, L, d_h]
        phase_diff = phases.unsqueeze(3) - phases.unsqueeze(2)

        # Interference cross-term: mean cosine of phase differences
        # Constructive: cos(0) = 1, Destructive: cos(pi) = -1
        interference = torch.cos(phase_diff).mean(dim=-1)  # [B, H, L, L]

        return interference

    def forward(self, x: Tensor) -> Tensor:
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        # Compute Q, K, V
        Q = self.q_proj(x).view(B, L, H, d_h).transpose(1, 2)  # [B, H, L, d_h]
        K = self.k_proj(x).view(B, L, H, d_h).transpose(1, 2)
        V = self.v_proj(x).view(B, L, H, d_h).transpose(1, 2)

        # Standard attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d_h)  # [B, H, L, L]

        # Compute interference cross-terms
        interference = self._compute_interference(x)  # [B, H, L, L]

        # Modulate attention with interference:
        # Positive interference amplifies (constructive binding).
        # Negative interference suppresses (destructive/spurious).
        gate = torch.sigmoid(self.interference_gate)  # [H, 1, 1] -> learned per head
        modulated_scores = scores * (1.0 + gate * interference)

        # Normalize
        attn_weights = F.softmax(modulated_scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        # Aggregate values
        attn_out = torch.matmul(attn_weights, V)  # [B, H, L, d_h]
        attn_out = attn_out.transpose(1, 2).reshape(B, L, D)
        attn_out = self.out_proj(attn_out)

        # Residual + norm
        x = self.norm1(x + attn_out)
        ff_out = self.ff(x)
        x = self.norm2(x + ff_out)

        return x


class ResonanceBindingHead(nn.Module):
    """
    Model B: Resonance interference head for binding tasks.

    Architecture:
      1. Character embedding + positional encoding
      2. N transformer layers with interference-modulated attention
      3. Name pooling -> per-name logits

    The interference cross-terms cos(phi_i - phi_j) act as a structural
    binding signal that augments the standard Q/K dot-product attention.
    This helps maintain correct role-filler assignments under distractors
    by amplifying structurally coherent token relationships and suppressing
    spurious nearest-name associations.
    """

    def __init__(
        self,
        config: Optional[HeadConfig] = None,
        lambda_interference: float = 0.3,
    ):
        super().__init__()
        self.config = config or HeadConfig()
        c = self.config

        self.embedding = nn.Embedding(c.vocab_size, c.embed_dim, padding_idx=0)
        self.pos_enc = PositionalEncoding(c.embed_dim, c.max_seq_len)
        self.drop = nn.Dropout(c.dropout)

        self.layers = nn.ModuleList([
            InterferenceAttentionLayer(
                c.embed_dim, c.num_heads, c.dropout, lambda_interference,
            )
            for _ in range(c.num_layers)
        ])

        self.pooler = NamePooler(c.embed_dim)
        self.tokenizer = CharTokenizer(c.vocab_size)

    def forward(
        self,
        token_ids: Tensor,
        name_masks: Tensor,
    ) -> Tensor:
        """
        Args:
            token_ids: [B, L] character token IDs.
            name_masks: [B, N_names, L] binary masks for name positions.

        Returns:
            logits: [B, N_names] per-name answer scores.
        """
        x = self.embedding(token_ids)
        x = self.pos_enc(x)
        x = self.drop(x)

        for layer in self.layers:
            x = layer(x)

        logits = self.pooler(x, name_masks)
        return logits

    def get_attention_type(self) -> str:
        return "resonance_interference"


# ─── Utilities ────────────────────────────────────────────────────────────────

def count_parameters(model: nn.Module) -> int:
    """Count total trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def build_name_masks(
    tokenizer: CharTokenizer,
    passage: str,
    question: str,
    names: List[str],
    max_len: int = 512,
    max_names: int = 24,
) -> Tuple[Tensor, List[str]]:
    """
    Build binary masks indicating where each name appears in the token sequence.

    Returns:
        name_masks: [1, max_names, max_len] binary mask.
        padded_names: List of name strings (padded to max_names with empty).
    """
    full_text = passage + chr(CharTokenizer.SEP) + question
    positions = tokenizer.find_name_positions(full_text, names, max_len)

    masks = torch.zeros(1, max_names, max_len)
    padded_names = list(names[:max_names])

    for i, name in enumerate(padded_names):
        for start in positions.get(name, []):
            end = min(start + len(name), max_len)
            masks[0, i, start:end] = 1.0

    # Pad names list
    while len(padded_names) < max_names:
        padded_names.append("")

    return masks, padded_names
