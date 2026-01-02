"""
Sovereign Embedding - Composite Embedding Layer for Transformers.

This module implements the SovereignEmbedding layer that replaces
the standard nn.Embedding with a composite embedding that combines:
- Learned Body (896 dims): Semantic nuance and context
- Enforced Header (128 dims): R-Signal, C-Signal, S-Signal, Guna

The key insight is to separate what must be LEARNED (semantic nuance)
from what must be ENFORCED (ontological structure).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass(frozen=True)
class SovereignEmbeddingConfig:
    """Configuration for SovereignEmbedding layer."""

    vocab_size: int = 50257  # GPT-2 vocab size
    d_model: int = 1024  # Total embedding dimension

    # Body dimensions (learned semantic)
    body_dim: int = 896

    # Header dimensions (enforced signals)
    r_dim: int = 48  # Intent/ontology projection
    c_dim: int = 32  # Sound/physics projection
    s_dim: int = 32  # Referent projection
    g_dim: int = 16  # Guna/entropy projection

    # Signal input sizes
    r_classes: int = 12  # Ontology layers
    c_input: int = 32  # SHA256 hash bytes
    s_classes: int = 17  # Referent categories
    g_input: int = 3  # Guna states

    # Dropout
    dropout: float = 0.1

    def __post_init__(self):
        """Validate configuration."""
        header_dim = self.r_dim + self.c_dim + self.s_dim + self.g_dim
        expected_d_model = self.body_dim + header_dim
        if expected_d_model != self.d_model:
            raise ValueError(
                f"Dimension mismatch: body({self.body_dim}) + header({header_dim}) "
                f"= {expected_d_model} != d_model({self.d_model})"
            )


class SovereignEmbedding(nn.Module):
    """
    Sovereign Embedding Layer - Composite embedding for transformers.

    Architecture:
    ```
    Input: (input_ids, c_signals, s_signals, r_signals, g_states)
             │
             ▼
    ┌────────────────────────────────────────────────────────────────┐
    │ BODY (Learned)                                                  │
    │   nn.Embedding(vocab_size, 896) → [B, Seq, 896]                │
    └────────────────────────────────────────────────────────────────┘
             │
             ▼
    ┌────────────────────────────────────────────────────────────────┐
    │ HEADER (Enforced)                                               │
    │   R: nn.Embedding(12, 48)  → [B, Seq, 48]                      │
    │   C: nn.Linear(32, 32)     → [B, Seq, 32]                      │
    │   S: nn.Embedding(17, 32)  → [B, Seq, 32]                      │
    │   G: nn.Linear(3, 16)      → [B, Seq, 16]                      │
    └────────────────────────────────────────────────────────────────┘
             │
             ▼
    ┌────────────────────────────────────────────────────────────────┐
    │ CONCATENATION                                                   │
    │   Full = [Body | R | C | S | G] → [B, Seq, 1024]               │
    └────────────────────────────────────────────────────────────────┘
    ```
    """

    def __init__(self, config: Optional[SovereignEmbeddingConfig] = None):
        """
        Initialize SovereignEmbedding.

        Args:
            config: Configuration object (defaults to SovereignEmbeddingConfig())
        """
        super().__init__()

        if config is None:
            config = SovereignEmbeddingConfig()

        self.config = config

        # Body embedding (learned semantic nuance)
        self.body_embed = nn.Embedding(config.vocab_size, config.body_dim)

        # Header projections (enforced structure)
        self.r_embed = nn.Embedding(config.r_classes, config.r_dim)
        self.c_proj = nn.Linear(config.c_input, config.c_dim)
        self.s_embed = nn.Embedding(config.s_classes, config.s_dim)
        self.g_proj = nn.Linear(config.g_input, config.g_dim)

        # Layer normalization for stability
        self.body_norm = nn.LayerNorm(config.body_dim)
        self.header_norm = nn.LayerNorm(
            config.r_dim + config.c_dim + config.s_dim + config.g_dim
        )

        # Dropout
        self.dropout = nn.Dropout(config.dropout)

        # Position embedding (optional, if not using rotary)
        self.position_embed = nn.Embedding(2048, config.d_model)

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Initialize embedding weights."""
        # Body: standard embedding init
        nn.init.normal_(self.body_embed.weight, mean=0.0, std=0.02)

        # R-Signal: ontology embeddings (slightly larger init for emphasis)
        nn.init.normal_(self.r_embed.weight, mean=0.0, std=0.05)

        # C-Signal: linear projection
        nn.init.xavier_uniform_(self.c_proj.weight)
        nn.init.zeros_(self.c_proj.bias)

        # S-Signal: referent embeddings
        nn.init.normal_(self.s_embed.weight, mean=0.0, std=0.02)

        # G-Signal: guna projection
        nn.init.xavier_uniform_(self.g_proj.weight)
        nn.init.zeros_(self.g_proj.bias)

        # Position: standard init
        nn.init.normal_(self.position_embed.weight, mean=0.0, std=0.02)

    def forward(
        self,
        input_ids: torch.Tensor,
        c_signals: torch.Tensor,
        s_signals: torch.Tensor,
        r_signals: torch.Tensor,
        g_states: torch.Tensor,
        position_ids: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute sovereign embeddings.

        Args:
            input_ids: Token IDs [B, Seq]
            c_signals: Sound signatures [B, Seq, 32]
            s_signals: Referent categories [B, Seq]
            r_signals: Intent/ontology [B, Seq]
            g_states: Guna states [B, Seq, 3]
            position_ids: Optional position IDs [B, Seq]

        Returns:
            Combined embeddings [B, Seq, d_model]
        """
        B, Seq = input_ids.shape

        # Body: learned semantic embedding
        body = self.body_embed(input_ids)  # [B, Seq, 896]
        body = self.body_norm(body)

        # Header construction
        header_r = self.r_embed(r_signals)  # [B, Seq, 48]
        header_c = self.c_proj(c_signals)  # [B, Seq, 32]
        header_s = self.s_embed(s_signals)  # [B, Seq, 32]
        header_g = self.g_proj(g_states)  # [B, Seq, 16]

        # Concatenate header components
        header = torch.cat([header_r, header_c, header_s, header_g], dim=-1)
        header = self.header_norm(header)  # [B, Seq, 128]

        # Full embedding = Body | Header
        full_embed = torch.cat([body, header], dim=-1)  # [B, Seq, 1024]

        # Add position embeddings if provided
        if position_ids is None:
            position_ids = torch.arange(Seq, device=input_ids.device).unsqueeze(0)
            position_ids = position_ids.expand(B, -1)

        position_embed = self.position_embed(position_ids)
        full_embed = full_embed + position_embed

        # Dropout
        full_embed = self.dropout(full_embed)

        return full_embed

    def get_body_embedding(self, input_ids: torch.Tensor) -> torch.Tensor:
        """Get only the body (learned semantic) embedding."""
        return self.body_norm(self.body_embed(input_ids))

    def get_header_embedding(
        self,
        c_signals: torch.Tensor,
        s_signals: torch.Tensor,
        r_signals: torch.Tensor,
        g_states: torch.Tensor,
    ) -> torch.Tensor:
        """Get only the header (enforced structure) embedding."""
        header_r = self.r_embed(r_signals)
        header_c = self.c_proj(c_signals)
        header_s = self.s_embed(s_signals)
        header_g = self.g_proj(g_states)

        header = torch.cat([header_r, header_c, header_s, header_g], dim=-1)
        return self.header_norm(header)

    @property
    def embedding_dim(self) -> int:
        """Total embedding dimension."""
        return self.config.d_model

    @property
    def body_dim(self) -> int:
        """Body embedding dimension."""
        return self.config.body_dim

    @property
    def header_dim(self) -> int:
        """Header embedding dimension."""
        return (
            self.config.r_dim
            + self.config.c_dim
            + self.config.s_dim
            + self.config.g_dim
        )


class SovereignOutputHead(nn.Module):
    """
    Output head for Sovereign model that predicts tokens AND signals.

    This enables the multi-objective loss by providing predictions for:
    - Token logits (next word)
    - R-Signal logits (intent prediction)
    - S-Signal logits (referent prediction)
    - C-Signal reconstruction (phonetic structure)
    """

    def __init__(self, config: Optional[SovereignEmbeddingConfig] = None):
        """
        Initialize output head.

        Args:
            config: Configuration object
        """
        super().__init__()

        if config is None:
            config = SovereignEmbeddingConfig()

        self.config = config

        # Token prediction (tied with body embedding)
        self.token_proj = nn.Linear(config.d_model, config.vocab_size, bias=False)

        # Signal prediction heads
        self.r_head = nn.Linear(config.d_model, config.r_classes)
        self.s_head = nn.Linear(config.d_model, config.s_classes)
        self.c_head = nn.Linear(config.d_model, config.c_input)

    def forward(
        self, hidden_states: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Compute output predictions.

        Args:
            hidden_states: Transformer output [B, Seq, d_model]

        Returns:
            Tuple of:
            - token_logits: [B, Seq, vocab_size]
            - r_logits: [B, Seq, r_classes]
            - s_logits: [B, Seq, s_classes]
            - c_pred: [B, Seq, c_input]
        """
        token_logits = self.token_proj(hidden_states)
        r_logits = self.r_head(hidden_states)
        s_logits = self.s_head(hidden_states)
        c_pred = torch.tanh(self.c_head(hidden_states))  # Bound to [-1, 1]

        return token_logits, r_logits, s_logits, c_pred

    def tie_weights(self, embedding: SovereignEmbedding):
        """Tie token projection weights with body embedding."""
        # Create a projection from vocab to body_dim, then to full d_model
        # This is a simplified tie - in practice you might want more sophisticated tying
        pass  # TODO: Implement weight tying if needed


def test_sovereign_embedding():
    """Test SovereignEmbedding forward pass."""
    print("\n" + "=" * 70)
    print("SOVEREIGN EMBEDDING - FORWARD PASS TEST")
    print("=" * 70)

    config = SovereignEmbeddingConfig()
    embedding = SovereignEmbedding(config)

    # Create dummy inputs
    B, Seq = 2, 10
    input_ids = torch.randint(0, config.vocab_size, (B, Seq))
    c_signals = torch.randn(B, Seq, 32)
    s_signals = torch.randint(0, config.s_classes, (B, Seq))
    r_signals = torch.randint(0, config.r_classes, (B, Seq))
    g_states = torch.rand(B, Seq, 3)

    # Forward pass
    output = embedding(input_ids, c_signals, s_signals, r_signals, g_states)

    print(f"\nInput shapes:")
    print(f"  input_ids: {input_ids.shape}")
    print(f"  c_signals: {c_signals.shape}")
    print(f"  s_signals: {s_signals.shape}")
    print(f"  r_signals: {r_signals.shape}")
    print(f"  g_states: {g_states.shape}")

    print(f"\nOutput shape: {output.shape}")
    print(f"Expected: [{B}, {Seq}, {config.d_model}]")

    assert output.shape == (B, Seq, config.d_model), "Shape mismatch!"
    print("\n[PASS] Forward pass successful!")

    # Test output head
    output_head = SovereignOutputHead(config)
    token_logits, r_logits, s_logits, c_pred = output_head(output)

    print(f"\nOutput head shapes:")
    print(f"  token_logits: {token_logits.shape}")
    print(f"  r_logits: {r_logits.shape}")
    print(f"  s_logits: {s_logits.shape}")
    print(f"  c_pred: {c_pred.shape}")

    print("\n[PASS] Output head successful!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_sovereign_embedding()
