"""
Binding Attention Heads
========================

Two attention head implementations for the binding benchmark:

Model A: SoftmaxBindingHead
  - Standard linear softmax attention over token embeddings.
  - Computes Q/K/V projections, softmax(QK^T/sqrt(d)) * V.
  - Baseline for role-filler binding.

Model B: ResonanceBindingHead
  - Interference-based attention using per-token amplitude cross-terms.
  - Decomposes each token into two amplitude components (a1, a2) with
    a learned mixing gate g, then computes the scalar cross-term:
        I_k = 2 * sqrt(g_k * (1 - g_k)) * (a1_k . a2_k)
    This is O(L) per token, not O(L^2) pairwise.
  - The cross-term acts as a key-side bias on attention scores:
    tokens with high interference signal attract more attention,
    strengthening correct role-filler bindings.

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
    Interference-based attention layer using per-token amplitude cross-terms.

    Each token is decomposed into two amplitude components with a learned
    mixing gate, and the scalar cross-term modulates attention:

    1. Amplitude decomposition:
       a1_k = W_1 x_k   (first amplitude component, per head)
       a2_k = W_2 x_k   (second amplitude component, per head)
       g_k  = sigmoid(W_g x_k)   (mixing gate ∈ (0,1), per head)

    2. Per-token cross-term (O(L), not O(L²)):
       I_k = 2√(g_k(1-g_k)) · sum_d(a1_k[d] · a2_k[d])
       This is a scalar per token per head.

    3. Key-side attention bias:
       score[i,j] = QK^T/√d + λ · I_j
       Tokens with constructive interference (high cross-term)
       attract more attention from all query positions, strengthening
       correct role-filler bindings and suppressing spurious associations.
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

        # Interference amplitude projections: two components per token
        self.amp1_proj = nn.Linear(embed_dim, embed_dim)
        self.amp2_proj = nn.Linear(embed_dim, embed_dim)

        # Mixing gate: per-token, per-head balance between components
        self.gate_proj = nn.Linear(embed_dim, num_heads)

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
        Compute per-token interference cross-term.

        Cross-term: I_k = 2√(g_k(1-g_k)) · (a1_k · a2_k)
        This is a scalar per token per head — O(L).

        Args:
            x: [B, L, D] input embeddings.

        Returns:
            interference: [B, H, L] per-token interference signal.
        """
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        # Two amplitude projections: [B, L, D] -> [B, L, H, d_h]
        a1 = self.amp1_proj(x).view(B, L, H, d_h)
        a2 = self.amp2_proj(x).view(B, L, H, d_h)

        # Mixing gate: [B, L, H] -> sigmoid gives g ∈ (0, 1)
        g = torch.sigmoid(self.gate_proj(x))  # [B, L, H]

        # Dot product of amplitude components, summed over head_dim: [B, L, H]
        amp_product = (a1 * a2).sum(dim=-1)

        # Mixing factor: 2√(g(1-g)), maximized at g=0.5
        mix = 2.0 * torch.sqrt(g * (1.0 - g) + 1e-8)  # [B, L, H]

        # Per-token interference: [B, L, H] -> [B, H, L]
        interference = (mix * amp_product).permute(0, 2, 1)

        # Store internals for diagnostics (detached to avoid graph retention)
        self._last_g = g.detach()                    # [B, L, H]
        self._last_a1 = a1.detach()                  # [B, L, H, d_h]
        self._last_a2 = a2.detach()                  # [B, L, H, d_h]
        self._last_interference = interference.detach()  # [B, H, L]

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

        # Compute per-token interference cross-terms: O(L)
        interference = self._compute_interference(x)  # [B, H, L]

        # Key-side bias: tokens with high interference attract more attention.
        # interference.unsqueeze(2) -> [B, H, 1, L] broadcasts across query dim.
        gate = torch.sigmoid(self.interference_gate)  # [H, 1, 1]
        scores = scores + gate * interference.unsqueeze(2)

        # Normalize
        attn_weights = F.softmax(scores, dim=-1)
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
      2. N transformer layers with per-token interference cross-terms
      3. Name pooling -> per-name logits

    Each token's interference signal I_k = 2√(g(1-g)) · (a1·a2) acts as
    a key-side bias on attention scores — O(L) per token, not O(L²).
    This helps maintain correct role-filler assignments under distractors
    by amplifying attention to structurally resonant tokens.
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

    def get_last_internals(self) -> Dict[str, Tensor]:
        """
        Retrieve internal tensors from the last forward pass.

        Returns dict with keys (from the last interference layer):
            g: [B, L, H] mixing gate values
            a1: [B, L, H, d_h] first amplitude component
            a2: [B, L, H, d_h] second amplitude component
            interference: [B, H, L] per-token interference signal
        """
        # Use the last layer's internals (deepest representation)
        last_layer = self.layers[-1]
        mapping = {
            "_last_g": "g",
            "_last_a1": "a1",
            "_last_a2": "a2",
            "_last_interference": "interference",
        }
        result = {}
        for attr, key in mapping.items():
            val = getattr(last_layer, attr, None)
            if val is not None:
                result[key] = val
        return result


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
