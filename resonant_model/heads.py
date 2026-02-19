"""
Binding Attention Heads
========================

Multiple attention head implementations for the binding benchmark:

Model A: SoftmaxBindingHead
  - Standard linear softmax attention over token embeddings.
  - Computes Q/K/V projections, softmax(QK^T/sqrt(d)) * V.
  - Baseline for role-filler binding.

Model B: ResonanceBindingHead (broadcast interference)
  - Per-token interference cross-term as key-side attention bias.
  - I_k = 2 * sqrt(g_k * (1 - g_k)) * (a1_k . a2_k)
  - O(L) per token. Known issue: query-independent broadcast.

Model C: QuadraticBindingHead (bilinear control)
  - Adds bilinear attention term: (U·h_i)^T(V·h_j).
  - Tests whether quadratic capacity alone helps binding,
    without any interference/phase mechanism.

Model B-v2: QueryConditionedBindingHead (query-conditioned interference)
  - Interaction term I_{i,j} = <a1_q_i, a1_k_j> · <a2_q_i, a2_k_j>
  - Multiplicative coupling gives binding selectivity.
  - O(L^2) but tests the corrected interference hypothesis.

Model B-v3: FeatureInterferenceBindingHead (interference as feature)
  - Injects interference into token embedding: x' = x + W_f · f_k
  - Standard QK attention decides whether to use the signal.
  - Prevents broadcast bias problem.

Model D: HybridQuadraticInterferenceHead (falsification test)
  - Quadratic bilinear as primary: (U·x_i)^T(W·x_j)/√d
  - Plus interference channel: λ · f_i^T · f_j / d_h
  - where f_k = √(g_k(1-g_k)) · (a1_k ⊙ a2_k)
  - If D > C: interference adds genuine value beyond quadratic capacity.
  - If D ≈ C: case closed — interference provides no incremental benefit.

All heads:
  - Accept tokenized passage+question input.
  - Produce per-name logits for answer selection.
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

        # Store non-detached gate for regularization during training
        self._gate_for_reg = g  # [B, L, H] — keeps gradient

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

    def compute_gate_regularization(
        self,
        entropy_weight: float = 1.0,
        variance_weight: float = 1.0,
    ) -> Tensor:
        """
        Compute gate regularization loss to prevent collapse.

        Two terms:
          1. Entropy: maximize gate entropy H(g) = -(g log g + (1-g) log(1-g)).
             Prevents degenerate gates (g near 0 or 1).
          2. Variance: encourage high variance of g across token positions.
             Prevents constant gates (same g for all tokens).

        Returns:
            Scalar regularization loss (to be minimized).
        """
        total = torch.tensor(0.0, device=next(self.parameters()).device)
        for layer in self.layers:
            g = getattr(layer, "_gate_for_reg", None)
            if g is None:
                continue
            # g: [B, L, H]

            # 1. Entropy maximization: minimize -H(g)
            # H(g) = -(g*log(g) + (1-g)*log(1-g)), max at g=0.5
            eps = 1e-7
            g_clamped = g.clamp(eps, 1.0 - eps)
            entropy = -(
                g_clamped * torch.log(g_clamped)
                + (1.0 - g_clamped) * torch.log(1.0 - g_clamped)
            )
            # Max possible entropy is log(2) ≈ 0.693. Normalize and negate.
            entropy_loss = -entropy.mean() / math.log(2.0)  # in [-1, 0]

            # 2. Variance encouragement across tokens (dim=1)
            # Penalize low std(g) across the sequence dimension
            g_std = g.std(dim=1)  # [B, H]
            variance_loss = -g_std.mean()  # encourage high variance

            total = total + entropy_weight * entropy_loss + variance_weight * variance_loss

        return total

    def get_amplitude_parameters(self) -> List[nn.Parameter]:
        """Return amplitude projection parameters (for freezing during warmup)."""
        params = []
        for layer in self.layers:
            params.extend(layer.amp1_proj.parameters())
            params.extend(layer.amp2_proj.parameters())
        return params

    def get_gate_parameters(self) -> List[nn.Parameter]:
        """Return gate-related parameters (for separate LR)."""
        params = []
        for layer in self.layers:
            params.extend(layer.gate_proj.parameters())
            params.append(layer.interference_gate)
        return params

    def get_non_gate_parameters(self) -> List[nn.Parameter]:
        """Return all parameters except gate-related ones."""
        gate_ids = {id(p) for p in self.get_gate_parameters()}
        return [p for p in self.parameters() if id(p) not in gate_ids]

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


# ─── Model C: Quadratic Attention Baseline ────────────────────────────────────

class QuadraticAttentionLayer(nn.Module):
    """
    Bilinear attention layer — quadratic capacity control.

    Adds a bilinear term to standard attention:
        score[i,j] = QK^T/√d + λ · (U·x_i)^T(V·x_j) / d

    This provides O(L²) quadratic scoring capacity WITHOUT any
    interference or phase mechanism — a control for whether benefits
    come from quadratic geometry alone.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        lambda_bilinear: float = 0.3,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        # Standard Q/K/V projections
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # Bilinear projections: two separate D->D maps
        self.u_proj = nn.Linear(embed_dim, embed_dim)
        self.w_proj = nn.Linear(embed_dim, embed_dim)

        # Learnable bilinear strength per head
        self.bilinear_gate = nn.Parameter(
            torch.full((num_heads, 1, 1), lambda_bilinear)
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

    def forward(self, x: Tensor) -> Tensor:
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        Q = self.q_proj(x).view(B, L, H, d_h).transpose(1, 2)
        K = self.k_proj(x).view(B, L, H, d_h).transpose(1, 2)
        V = self.v_proj(x).view(B, L, H, d_h).transpose(1, 2)

        # Standard attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d_h)

        # Bilinear term: (U·x_i)^T(W·x_j) per head
        U = self.u_proj(x).view(B, L, H, d_h).transpose(1, 2)  # [B, H, L, d_h]
        W = self.w_proj(x).view(B, L, H, d_h).transpose(1, 2)
        bilinear = torch.matmul(U, W.transpose(-2, -1)) / math.sqrt(d_h)

        gate = torch.sigmoid(self.bilinear_gate)  # [H, 1, 1]
        scores = scores + gate * bilinear

        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        attn_out = torch.matmul(attn_weights, V)
        attn_out = attn_out.transpose(1, 2).reshape(B, L, D)
        attn_out = self.out_proj(attn_out)

        x = self.norm1(x + attn_out)
        ff_out = self.ff(x)
        x = self.norm2(x + ff_out)
        return x


class QuadraticBindingHead(nn.Module):
    """
    Model C: Quadratic bilinear attention head for binding tasks.

    Control model — tests whether quadratic attention capacity alone
    (without interference/phase mechanism) improves binding.
    """

    def __init__(
        self,
        config: Optional[HeadConfig] = None,
        lambda_bilinear: float = 0.3,
    ):
        super().__init__()
        self.config = config or HeadConfig()
        c = self.config

        self.embedding = nn.Embedding(c.vocab_size, c.embed_dim, padding_idx=0)
        self.pos_enc = PositionalEncoding(c.embed_dim, c.max_seq_len)
        self.drop = nn.Dropout(c.dropout)

        self.layers = nn.ModuleList([
            QuadraticAttentionLayer(
                c.embed_dim, c.num_heads, c.dropout, lambda_bilinear,
            )
            for _ in range(c.num_layers)
        ])

        self.pooler = NamePooler(c.embed_dim)
        self.tokenizer = CharTokenizer(c.vocab_size)

    def forward(self, x: Tensor, name_masks: Tensor) -> Tensor:
        x = self.embedding(x)
        x = self.pos_enc(x)
        x = self.drop(x)
        for layer in self.layers:
            x = layer(x)
        return self.pooler(x, name_masks)

    def get_attention_type(self) -> str:
        return "quadratic_bilinear"


# ─── Model B-v2: Query-Conditioned Interference ─────────────────────────────

class QueryConditionedInterferenceLayer(nn.Module):
    """
    Query-conditioned interference: I_{i,j} depends on BOTH positions.

    Both query (i) and key (j) get amplitude decomposition:
        a1_q_i, a2_q_i  and  a1_k_j, a2_k_j

    Multiplicative coupling interaction:
        I_{i,j} = <a1_q_i, a1_k_j> · <a2_q_i, a2_k_j> / d_h

    Gated by mixing factors at both sides:
        score_{i,j} = QK^T/√d + λ · m_i · m_j · I_{i,j}
        where m = 2√(g(1-g))

    This is O(L²) but provides the selectivity needed for binding:
    the interference signal varies with the specific query-key pair,
    enabling role-dependent attention modulation.
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

        # Standard Q/K/V
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # Query-side amplitude projections
        self.amp1_q_proj = nn.Linear(embed_dim, embed_dim)
        self.amp2_q_proj = nn.Linear(embed_dim, embed_dim)

        # Key-side amplitude projections
        self.amp1_k_proj = nn.Linear(embed_dim, embed_dim)
        self.amp2_k_proj = nn.Linear(embed_dim, embed_dim)

        # Mixing gates (separate for query and key)
        self.gate_q_proj = nn.Linear(embed_dim, num_heads)
        self.gate_k_proj = nn.Linear(embed_dim, num_heads)

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
        Compute query-conditioned interference interaction.

        I_{i,j} = m_i · m_j · <a1_q_i, a1_k_j> · <a2_q_i, a2_k_j> / d_h

        Returns: [B, H, L, L] pairwise interference matrix.
        """
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        # Query-side amplitudes: [B, H, L, d_h]
        a1_q = self.amp1_q_proj(x).view(B, L, H, d_h).transpose(1, 2)
        a2_q = self.amp2_q_proj(x).view(B, L, H, d_h).transpose(1, 2)

        # Key-side amplitudes: [B, H, L, d_h]
        a1_k = self.amp1_k_proj(x).view(B, L, H, d_h).transpose(1, 2)
        a2_k = self.amp2_k_proj(x).view(B, L, H, d_h).transpose(1, 2)

        # Cross-component dot products: [B, H, L_q, L_k]
        dot1 = torch.matmul(a1_q, a1_k.transpose(-2, -1))
        dot2 = torch.matmul(a2_q, a2_k.transpose(-2, -1))

        # Multiplicative coupling (the binding-capable interaction)
        interference = dot1 * dot2 / d_h  # [B, H, L, L]

        # Mixing gates: [B, L, H]
        g_q = torch.sigmoid(self.gate_q_proj(x))
        g_k = torch.sigmoid(self.gate_k_proj(x))

        # Mixing factors: 2√(g(1-g))
        mix_q = 2.0 * torch.sqrt(g_q * (1.0 - g_q) + 1e-8)  # [B, L, H]
        mix_k = 2.0 * torch.sqrt(g_k * (1.0 - g_k) + 1e-8)

        # Outer product of mixing factors: [B, H, L, 1] * [B, H, 1, L]
        mix_q = mix_q.permute(0, 2, 1).unsqueeze(-1)   # [B, H, L, 1]
        mix_k = mix_k.permute(0, 2, 1).unsqueeze(-2)   # [B, H, 1, L]

        interference = mix_q * mix_k * interference  # [B, H, L, L]

        # Store for diagnostics
        self._last_g_q = g_q.detach()
        self._last_g_k = g_k.detach()
        self._gate_q_for_reg = g_q
        self._gate_k_for_reg = g_k

        return interference

    def forward(self, x: Tensor) -> Tensor:
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        Q = self.q_proj(x).view(B, L, H, d_h).transpose(1, 2)
        K = self.k_proj(x).view(B, L, H, d_h).transpose(1, 2)
        V = self.v_proj(x).view(B, L, H, d_h).transpose(1, 2)

        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d_h)

        # Query-conditioned interference: [B, H, L, L]
        interference = self._compute_interference(x)
        gate = torch.sigmoid(self.interference_gate)  # [H, 1, 1]
        scores = scores + gate * interference

        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        attn_out = torch.matmul(attn_weights, V)
        attn_out = attn_out.transpose(1, 2).reshape(B, L, D)
        attn_out = self.out_proj(attn_out)

        x = self.norm1(x + attn_out)
        ff_out = self.ff(x)
        x = self.norm2(x + ff_out)
        return x


class QueryConditionedBindingHead(nn.Module):
    """
    Model B-v2: Query-conditioned interference for binding tasks.

    Fixes the broadcast bias problem: I_{i,j} depends on both query
    and key positions via multiplicative coupling of amplitude components.
    O(L²) but provides genuine binding selectivity.
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
            QueryConditionedInterferenceLayer(
                c.embed_dim, c.num_heads, c.dropout, lambda_interference,
            )
            for _ in range(c.num_layers)
        ])

        self.pooler = NamePooler(c.embed_dim)
        self.tokenizer = CharTokenizer(c.vocab_size)

    def forward(self, x: Tensor, name_masks: Tensor) -> Tensor:
        x = self.embedding(x)
        x = self.pos_enc(x)
        x = self.drop(x)
        for layer in self.layers:
            x = layer(x)
        return self.pooler(x, name_masks)

    def get_attention_type(self) -> str:
        return "query_conditioned_interference"

    def compute_gate_regularization(
        self,
        entropy_weight: float = 1.0,
        variance_weight: float = 1.0,
    ) -> Tensor:
        """Gate regularization for query-conditioned variant (both q and k gates)."""
        total = torch.tensor(0.0, device=next(self.parameters()).device)
        eps = 1e-7
        for layer in self.layers:
            for g in [
                getattr(layer, "_gate_q_for_reg", None),
                getattr(layer, "_gate_k_for_reg", None),
            ]:
                if g is None:
                    continue
                g_clamped = g.clamp(eps, 1.0 - eps)
                entropy = -(
                    g_clamped * torch.log(g_clamped)
                    + (1.0 - g_clamped) * torch.log(1.0 - g_clamped)
                )
                entropy_loss = -entropy.mean() / math.log(2.0)
                variance_loss = -g.std(dim=1).mean()
                total = total + entropy_weight * entropy_loss + variance_weight * variance_loss
        return total

    def get_gate_parameters(self) -> List[nn.Parameter]:
        params = []
        for layer in self.layers:
            params.extend(layer.gate_q_proj.parameters())
            params.extend(layer.gate_k_proj.parameters())
            params.append(layer.interference_gate)
        return params

    def get_non_gate_parameters(self) -> List[nn.Parameter]:
        gate_ids = {id(p) for p in self.get_gate_parameters()}
        return [p for p in self.parameters() if id(p) not in gate_ids]

    def get_amplitude_parameters(self) -> List[nn.Parameter]:
        params = []
        for layer in self.layers:
            params.extend(layer.amp1_q_proj.parameters())
            params.extend(layer.amp2_q_proj.parameters())
            params.extend(layer.amp1_k_proj.parameters())
            params.extend(layer.amp2_k_proj.parameters())
        return params

    def get_last_internals(self) -> Dict[str, Tensor]:
        last_layer = self.layers[-1]
        result = {}
        g_q = getattr(last_layer, "_last_g_q", None)
        g_k = getattr(last_layer, "_last_g_k", None)
        if g_q is not None:
            result["g"] = (g_q + g_k) / 2  # average for diagnostics
        return result


# ─── Model B-v3: Interference as Feature ─────────────────────────────────────

class FeatureInterferenceLayer(nn.Module):
    """
    Interference-as-feature: inject cross-term into embedding, not scores.

    Per-token interference feature (vector, not scalar):
        f_j = √(g_j(1-g_j)) · (a1_j ⊙ a2_j)    [B, L, D]

    Injected into token representation:
        x'_j = x_j + λ · W_f(f_j)

    Then standard attention decides whether to use it:
        score[i,j] = q_i^T k'_j / √d

    This prevents the broadcast bias because the interference signal
    must compete through the standard QK mechanism — the query decides
    which interference-enhanced tokens to attend to.
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

        # Standard Q/K/V
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # Interference components (same as original)
        self.amp1_proj = nn.Linear(embed_dim, embed_dim)
        self.amp2_proj = nn.Linear(embed_dim, embed_dim)
        self.gate_proj = nn.Linear(embed_dim, num_heads)

        # Feature injection: maps D-dim interference feature to embedding
        self.feature_proj = nn.Linear(embed_dim, embed_dim)

        # Learnable interference strength
        self.interference_scale = nn.Parameter(
            torch.tensor(lambda_interference)
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

    def _compute_interference_feature(self, x: Tensor) -> Tensor:
        """
        Compute per-token interference feature vector.

        f_j = √(g_j(1-g_j)) · (a1_j ⊙ a2_j)

        Returns: [B, L, D] feature vector per token.
        """
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        a1 = self.amp1_proj(x).view(B, L, H, d_h)
        a2 = self.amp2_proj(x).view(B, L, H, d_h)
        g = torch.sigmoid(self.gate_proj(x))  # [B, L, H]

        # Element-wise product of amplitudes: [B, L, H, d_h]
        amp_product = a1 * a2

        # Mixing factor: √(g(1-g)), per head
        mix = torch.sqrt(g * (1.0 - g) + 1e-8)  # [B, L, H]

        # Scale each head's feature by its mixing factor
        feature = mix.unsqueeze(-1) * amp_product  # [B, L, H, d_h]

        # Reshape back to [B, L, D]
        feature = feature.reshape(B, L, D)

        # Store for diagnostics
        self._last_g = g.detach()
        self._last_a1 = a1.detach()
        self._last_a2 = a2.detach()
        self._gate_for_reg = g

        return feature

    def forward(self, x: Tensor) -> Tensor:
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        # Compute interference feature and inject into representation
        feature = self._compute_interference_feature(x)
        x_enhanced = x + self.interference_scale * self.feature_proj(feature)

        # Standard attention on enhanced representation
        Q = self.q_proj(x_enhanced).view(B, L, H, d_h).transpose(1, 2)
        K = self.k_proj(x_enhanced).view(B, L, H, d_h).transpose(1, 2)
        V = self.v_proj(x_enhanced).view(B, L, H, d_h).transpose(1, 2)

        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d_h)

        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        attn_out = torch.matmul(attn_weights, V)
        attn_out = attn_out.transpose(1, 2).reshape(B, L, D)
        attn_out = self.out_proj(attn_out)

        x = self.norm1(x + attn_out)
        ff_out = self.ff(x)
        x = self.norm2(x + ff_out)
        return x


class FeatureInterferenceBindingHead(nn.Module):
    """
    Model B-v3: Interference as feature injection for binding tasks.

    Instead of biasing attention scores (broadcast), injects the
    interference cross-term as a feature into the token embedding.
    Standard QK attention then decides what to attend to — preventing
    the query-independent salience problem.
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
            FeatureInterferenceLayer(
                c.embed_dim, c.num_heads, c.dropout, lambda_interference,
            )
            for _ in range(c.num_layers)
        ])

        self.pooler = NamePooler(c.embed_dim)
        self.tokenizer = CharTokenizer(c.vocab_size)

    def forward(self, x: Tensor, name_masks: Tensor) -> Tensor:
        x = self.embedding(x)
        x = self.pos_enc(x)
        x = self.drop(x)
        for layer in self.layers:
            x = layer(x)
        return self.pooler(x, name_masks)

    def get_attention_type(self) -> str:
        return "feature_interference"

    def compute_gate_regularization(
        self,
        entropy_weight: float = 1.0,
        variance_weight: float = 1.0,
    ) -> Tensor:
        """Gate regularization for feature interference variant."""
        total = torch.tensor(0.0, device=next(self.parameters()).device)
        eps = 1e-7
        for layer in self.layers:
            g = getattr(layer, "_gate_for_reg", None)
            if g is None:
                continue
            g_clamped = g.clamp(eps, 1.0 - eps)
            entropy = -(
                g_clamped * torch.log(g_clamped)
                + (1.0 - g_clamped) * torch.log(1.0 - g_clamped)
            )
            entropy_loss = -entropy.mean() / math.log(2.0)
            variance_loss = -g.std(dim=1).mean()
            total = total + entropy_weight * entropy_loss + variance_weight * variance_loss
        return total

    def get_gate_parameters(self) -> List[nn.Parameter]:
        params = []
        for layer in self.layers:
            params.extend(layer.gate_proj.parameters())
            params.append(layer.interference_scale)
        return params

    def get_non_gate_parameters(self) -> List[nn.Parameter]:
        gate_ids = {id(p) for p in self.get_gate_parameters()}
        return [p for p in self.parameters() if id(p) not in gate_ids]

    def get_amplitude_parameters(self) -> List[nn.Parameter]:
        params = []
        for layer in self.layers:
            params.extend(layer.amp1_proj.parameters())
            params.extend(layer.amp2_proj.parameters())
        return params

    def get_last_internals(self) -> Dict[str, Tensor]:
        last_layer = self.layers[-1]
        result = {}
        for attr, key in {"_last_g": "g", "_last_a1": "a1", "_last_a2": "a2"}.items():
            val = getattr(last_layer, attr, None)
            if val is not None:
                result[key] = val
        return result


# ─── Model D: Hybrid Quadratic + Interference (Falsification Test) ────────────

class HybridAttentionLayer(nn.Module):
    """
    Quadratic bilinear attention with an additive interference channel.

    score_{i,j} = QK^T/√d + λ_b · (U·x_i)^T(W·x_j)/√d + λ_I · f_i^T f_j / d_h

    where f_k = √(g_k(1-g_k)) · (a1_k ⊙ a2_k)  is the per-token
    interference feature vector (per head).

    The bilinear term provides quadratic capacity (proven to help binding).
    The interference channel tests whether the specific resonance structure
    adds incremental value beyond generic quadratic terms.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        lambda_bilinear: float = 0.3,
        lambda_interference: float = 0.3,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        # Standard Q/K/V projections
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # Bilinear projections (from quadratic head)
        self.u_proj = nn.Linear(embed_dim, embed_dim)
        self.w_proj = nn.Linear(embed_dim, embed_dim)

        # Interference components (from resonance head)
        self.amp1_proj = nn.Linear(embed_dim, embed_dim)
        self.amp2_proj = nn.Linear(embed_dim, embed_dim)
        self.gate_proj = nn.Linear(embed_dim, num_heads)

        # Learnable strength per head for each channel
        self.bilinear_gate = nn.Parameter(
            torch.full((num_heads, 1, 1), lambda_bilinear)
        )
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
        Compute pairwise interference interaction.

        f_k = √(g_k(1-g_k)) · (a1_k ⊙ a2_k)   per head
        I_{i,j} = f_i^T f_j / d_h

        Returns: [B, H, L, L] pairwise interference matrix.
        """
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        a1 = self.amp1_proj(x).view(B, L, H, d_h)  # [B, L, H, d_h]
        a2 = self.amp2_proj(x).view(B, L, H, d_h)
        g = torch.sigmoid(self.gate_proj(x))  # [B, L, H]

        # Per-token interference feature: [B, L, H, d_h]
        amp_product = a1 * a2
        mix = torch.sqrt(g * (1.0 - g) + 1e-8).unsqueeze(-1)  # [B, L, H, 1]
        feature = mix * amp_product  # [B, L, H, d_h]

        # Rearrange to [B, H, L, d_h] for matmul
        feature = feature.permute(0, 2, 1, 3)  # [B, H, L, d_h]

        # Pairwise dot product: [B, H, L, L]
        interference = torch.matmul(
            feature, feature.transpose(-2, -1)
        ) / math.sqrt(d_h)

        # Store for diagnostics
        self._last_g = g.detach()
        self._last_a1 = a1.detach()
        self._last_a2 = a2.detach()
        self._last_interference = interference.detach()
        self._gate_for_reg = g  # keeps gradient for regularization

        return interference

    def forward(self, x: Tensor) -> Tensor:
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        Q = self.q_proj(x).view(B, L, H, d_h).transpose(1, 2)
        K = self.k_proj(x).view(B, L, H, d_h).transpose(1, 2)
        V = self.v_proj(x).view(B, L, H, d_h).transpose(1, 2)

        # Channel 1: Standard attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d_h)

        # Channel 2: Bilinear quadratic term
        U = self.u_proj(x).view(B, L, H, d_h).transpose(1, 2)
        W = self.w_proj(x).view(B, L, H, d_h).transpose(1, 2)
        bilinear = torch.matmul(U, W.transpose(-2, -1)) / math.sqrt(d_h)
        scores = scores + torch.sigmoid(self.bilinear_gate) * bilinear

        # Channel 3: Interference
        interference = self._compute_interference(x)  # [B, H, L, L]
        scores = scores + torch.sigmoid(self.interference_gate) * interference

        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        attn_out = torch.matmul(attn_weights, V)
        attn_out = attn_out.transpose(1, 2).reshape(B, L, D)
        attn_out = self.out_proj(attn_out)

        x = self.norm1(x + attn_out)
        ff_out = self.ff(x)
        x = self.norm2(x + ff_out)
        return x


class HybridQuadraticInterferenceHead(nn.Module):
    """
    Model D: Hybrid quadratic + interference head for binding tasks.

    Falsification test: uses the quadratic bilinear mechanism (proven to
    help binding) as primary, with the interference cross-term as an
    additional channel. Comparing D vs C isolates the incremental
    contribution of interference structure beyond quadratic capacity.

    If D > C: interference adds genuine value.
    If D ≈ C: the case for interference is closed.
    """

    def __init__(
        self,
        config: Optional[HeadConfig] = None,
        lambda_bilinear: float = 0.3,
        lambda_interference: float = 0.3,
    ):
        super().__init__()
        self.config = config or HeadConfig()
        c = self.config

        self.embedding = nn.Embedding(c.vocab_size, c.embed_dim, padding_idx=0)
        self.pos_enc = PositionalEncoding(c.embed_dim, c.max_seq_len)
        self.drop = nn.Dropout(c.dropout)

        self.layers = nn.ModuleList([
            HybridAttentionLayer(
                c.embed_dim, c.num_heads, c.dropout,
                lambda_bilinear, lambda_interference,
            )
            for _ in range(c.num_layers)
        ])

        self.pooler = NamePooler(c.embed_dim)
        self.tokenizer = CharTokenizer(c.vocab_size)

    def forward(self, x: Tensor, name_masks: Tensor) -> Tensor:
        x = self.embedding(x)
        x = self.pos_enc(x)
        x = self.drop(x)
        for layer in self.layers:
            x = layer(x)
        return self.pooler(x, name_masks)

    def get_attention_type(self) -> str:
        return "hybrid_quadratic_interference"

    def compute_gate_regularization(
        self,
        entropy_weight: float = 1.0,
        variance_weight: float = 1.0,
    ) -> Tensor:
        """Gate regularization for hybrid variant."""
        total = torch.tensor(0.0, device=next(self.parameters()).device)
        eps = 1e-7
        for layer in self.layers:
            g = getattr(layer, "_gate_for_reg", None)
            if g is None:
                continue
            g_clamped = g.clamp(eps, 1.0 - eps)
            entropy = -(
                g_clamped * torch.log(g_clamped)
                + (1.0 - g_clamped) * torch.log(1.0 - g_clamped)
            )
            entropy_loss = -entropy.mean() / math.log(2.0)
            variance_loss = -g.std(dim=1).mean()
            total = total + entropy_weight * entropy_loss + variance_weight * variance_loss
        return total

    def get_gate_parameters(self) -> List[nn.Parameter]:
        """Return gate-related parameters (for separate LR)."""
        params = []
        for layer in self.layers:
            params.extend(layer.gate_proj.parameters())
            params.append(layer.interference_gate)
        return params

    def get_non_gate_parameters(self) -> List[nn.Parameter]:
        """Return all parameters except gate-related ones."""
        gate_ids = {id(p) for p in self.get_gate_parameters()}
        return [p for p in self.parameters() if id(p) not in gate_ids]

    def get_amplitude_parameters(self) -> List[nn.Parameter]:
        """Return amplitude projection parameters (for freezing during warmup)."""
        params = []
        for layer in self.layers:
            params.extend(layer.amp1_proj.parameters())
            params.extend(layer.amp2_proj.parameters())
        return params

    def get_last_internals(self) -> Dict[str, Tensor]:
        """Retrieve internals from the last forward pass."""
        last_layer = self.layers[-1]
        result = {}
        for attr, key in {
            "_last_g": "g",
            "_last_a1": "a1",
            "_last_a2": "a2",
            "_last_interference": "interference",
        }.items():
            val = getattr(last_layer, attr, None)
            if val is not None:
                result[key] = val
        return result


# ─── Model E: Scalable Quadratic Attention ────────────────────────────────────

class LowRankBilinearChannel(nn.Module):
    """
    A single low-rank bilinear attention channel.

    Full-rank bilinear: score = (Ux)^T(Wx) where U,W are D×D.
    Low-rank:           score = (U_b U_a x)^T (W_b W_a x)
      where U_a: D→r, U_b: r→D (rank-r bottleneck).

    Parameter savings: 2Dr per projection vs D² full-rank.
    At D=1024, r=64: 131K vs 1.05M per projection (87% reduction).
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        rank: int,
        use_spectral_norm: bool = False,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.rank = rank

        # Low-rank factorization: D → r → D
        u_down = nn.Linear(embed_dim, rank, bias=False)
        u_up = nn.Linear(rank, embed_dim, bias=False)
        w_down = nn.Linear(embed_dim, rank, bias=False)
        w_up = nn.Linear(rank, embed_dim, bias=False)

        if use_spectral_norm:
            u_down = nn.utils.parametrizations.spectral_norm(u_down)
            u_up = nn.utils.parametrizations.spectral_norm(u_up)
            w_down = nn.utils.parametrizations.spectral_norm(w_down)
            w_up = nn.utils.parametrizations.spectral_norm(w_up)

        self.u_down = u_down
        self.u_up = u_up
        self.w_down = w_down
        self.w_up = w_up

        # Per-head learnable strength
        self.gate = nn.Parameter(torch.zeros(num_heads, 1, 1))

    def forward(self, x: Tensor) -> Tensor:
        """
        Compute low-rank bilinear scores.

        Args:
            x: [B, L, D]

        Returns:
            scores: [B, H, L, L]
        """
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        # Low-rank projection: D → r → D, then reshape to per-head
        U = self.u_up(self.u_down(x)).view(B, L, H, d_h).transpose(1, 2)
        W = self.w_up(self.w_down(x)).view(B, L, H, d_h).transpose(1, 2)

        # Bilinear dot product: [B, H, L, L]
        scores = torch.matmul(U, W.transpose(-2, -1)) / math.sqrt(d_h)

        return torch.sigmoid(self.gate) * scores


class ScalableQuadraticAttentionLayer(nn.Module):
    """
    Multi-channel low-rank bilinear attention layer.

    score_{i,j} = QK^T/√d + Σ_{c=1}^{C} channel_c(x_i, x_j)

    Each channel is a low-rank bilinear: (U_c x)^T (W_c x) / √d_h
    with rank-r bottleneck factorization.

    Scaling dimensions:
      1. Low-rank (r): controls per-channel parameter cost.
         Full-rank: r = embed_dim (no bottleneck).
         Typical:   r = embed_dim // 4 or embed_dim // 8.

      2. Channels (C): number of independent bilinear interactions.
         Each channel learns a different "binding mode."
         C=1 recovers original quadratic head (if r=embed_dim).

      3. Spectral norm: constrains singular values of projections,
         prevents bilinear score explosion at initialization.

      4. Bilinear dropout: independent dropout on bilinear scores
         (separate from attention dropout), regularizes the
         quadratic channel to prevent over-reliance.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        num_channels: int = 1,
        rank: int = 0,  # 0 = full rank (embed_dim)
        use_spectral_norm: bool = False,
        bilinear_dropout: float = 0.0,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.num_channels = num_channels

        effective_rank = rank if rank > 0 else embed_dim

        # Standard Q/K/V
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # Multi-channel low-rank bilinear
        self.channels = nn.ModuleList([
            LowRankBilinearChannel(
                embed_dim, num_heads, effective_rank, use_spectral_norm,
            )
            for _ in range(num_channels)
        ])

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
        self.bilinear_dropout = nn.Dropout(bilinear_dropout) if bilinear_dropout > 0 else None

    def forward(self, x: Tensor) -> Tensor:
        B, L, D = x.shape
        H = self.num_heads
        d_h = self.head_dim

        Q = self.q_proj(x).view(B, L, H, d_h).transpose(1, 2)
        K = self.k_proj(x).view(B, L, H, d_h).transpose(1, 2)
        V = self.v_proj(x).view(B, L, H, d_h).transpose(1, 2)

        # Standard attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d_h)

        # Sum of bilinear channels
        for channel in self.channels:
            bilinear = channel(x)  # [B, H, L, L]
            if self.bilinear_dropout is not None:
                bilinear = self.bilinear_dropout(bilinear)
            scores = scores + bilinear

        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        attn_out = torch.matmul(attn_weights, V)
        attn_out = attn_out.transpose(1, 2).reshape(B, L, D)
        attn_out = self.out_proj(attn_out)

        x = self.norm1(x + attn_out)
        ff_out = self.ff(x)
        x = self.norm2(x + ff_out)
        return x


@dataclass
class ScalableQuadraticConfig:
    """Configuration for scalable quadratic attention."""
    num_channels: int = 1       # independent bilinear channels
    rank: int = 0               # 0 = full rank; >0 = low-rank bottleneck
    use_spectral_norm: bool = False
    bilinear_dropout: float = 0.0


class ScalableQuadraticBindingHead(nn.Module):
    """
    Model E: Scalable quadratic bilinear attention for binding tasks.

    Extends Model C with four scaling dimensions:
      1. Low-rank factorization (rank): D→r→D bottleneck reduces
         params from O(D²) to O(Dr) per projection.
      2. Multi-channel (num_channels): C independent bilinear
         interactions, each capturing a different binding mode.
      3. Spectral normalization: constrains projection norms
         to prevent score explosion.
      4. Bilinear dropout: regularizes quadratic channel independently.

    Param budget comparison (D=128, H=4, L=2 layers):
      Full rank, C=1:  +66K  (original Model C)
      Rank 32, C=1:    +33K  (50% reduction)
      Rank 32, C=4:    +131K (4 channels at 50% each)

    At scale (D=1024, L=6 layers):
      Full rank, C=1:  +12.6M
      Rank 64, C=1:    +1.6M  (87% reduction)
      Rank 64, C=4:    +6.3M  (4 channels at 87% each)
    """

    def __init__(
        self,
        config: Optional[HeadConfig] = None,
        scale_config: Optional[ScalableQuadraticConfig] = None,
    ):
        super().__init__()
        self.config = config or HeadConfig()
        self.scale_config = scale_config or ScalableQuadraticConfig()
        c = self.config
        sc = self.scale_config

        self.embedding = nn.Embedding(c.vocab_size, c.embed_dim, padding_idx=0)
        self.pos_enc = PositionalEncoding(c.embed_dim, c.max_seq_len)
        self.drop = nn.Dropout(c.dropout)

        self.layers = nn.ModuleList([
            ScalableQuadraticAttentionLayer(
                c.embed_dim, c.num_heads, c.dropout,
                num_channels=sc.num_channels,
                rank=sc.rank,
                use_spectral_norm=sc.use_spectral_norm,
                bilinear_dropout=sc.bilinear_dropout,
            )
            for _ in range(c.num_layers)
        ])

        self.pooler = NamePooler(c.embed_dim)
        self.tokenizer = CharTokenizer(c.vocab_size)

    def forward(self, x: Tensor, name_masks: Tensor) -> Tensor:
        x = self.embedding(x)
        x = self.pos_enc(x)
        x = self.drop(x)
        for layer in self.layers:
            x = layer(x)
        return self.pooler(x, name_masks)

    def get_attention_type(self) -> str:
        sc = self.scale_config
        parts = ["scalable_quadratic"]
        if sc.rank > 0:
            parts.append(f"r{sc.rank}")
        if sc.num_channels > 1:
            parts.append(f"c{sc.num_channels}")
        if sc.use_spectral_norm:
            parts.append("sn")
        if sc.bilinear_dropout > 0:
            parts.append(f"bd{sc.bilinear_dropout}")
        return "_".join(parts)


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
