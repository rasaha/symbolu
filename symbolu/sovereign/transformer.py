"""
Sovereign-1 Transformer: Hybrid Quadratic + Phase Architecture
===============================================================

The SovereignTransformer implements the core "body" of Sovereign-1:
- Quadratic layers (O(n²)) for high-fidelity context gathering
- PID Governor at the nexus for control-theoretic gating
- Phase layers (O(n)) for linear reasoning on authorized signal

Key Innovation: Virtual Nexus
-----------------------------
Instead of pre-compiling 3 separate models, we use one model with
a movable PID insertion point:
- 4/8 Mode: PID after layer 4 (logic-heavy tasks)
- 6/6 Mode: PID after layer 6 (default/creative)
- 8/4 Mode: PID after layer 8 (memory-heavy tasks)

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 8
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu.sovereign.pid_governor import PIDGovernor, PIDGovernorConfig


@dataclass
class SovereignTransformerConfig:
    """Configuration for Sovereign Transformer."""

    # Architecture
    vocab_size: int = 50257
    embed_dim: int = 1024  # 896 semantic + 128 state
    num_layers: int = 12
    num_heads: int = 16
    ff_dim: int = 4096
    max_seq_len: int = 8192
    dropout: float = 0.1

    # State partition
    semantic_dim: int = 896
    state_dim: int = 128

    # Default nexus position (6/6 mode)
    default_nexus: int = 6

    # Phase attention parameters
    sync_steps: int = 3
    sync_lr: float = 0.1


class AmbidextrousLayer(nn.Module):
    """
    Transformer layer that can operate in either Quadratic or Phase mode.

    This enables the Virtual Nexus - a single model architecture that
    can switch between attention modes at runtime.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        ff_dim: int,
        dropout: float = 0.1,
        sync_steps: int = 3,
        sync_lr: float = 0.1,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.sync_steps = sync_steps

        # Shared projections (used by both modes)
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # Phase-specific components
        self.phase_proj = nn.Linear(self.head_dim, self.head_dim)
        self.sync_lr = nn.Parameter(torch.tensor(sync_lr))

        # Feed-forward network
        self.ff = nn.Sequential(
            nn.Linear(embed_dim, ff_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ff_dim, embed_dim),
            nn.Dropout(dropout),
        )

        # Layer norms
        self.norm1 = nn.LayerNorm(embed_dim)
        self.norm2 = nn.LayerNorm(embed_dim)

        self.dropout = nn.Dropout(dropout)

    def _quadratic_attention(
        self,
        Q: torch.Tensor,
        K: torch.Tensor,
        V: torch.Tensor,
        causal_mask: bool = True,
    ) -> torch.Tensor:
        """Standard O(n²) scaled dot-product attention."""
        B, H, N, d = Q.shape

        # Scaled dot-product attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d)  # [B, H, N, N]

        # Causal mask
        if causal_mask:
            mask = torch.triu(torch.ones(N, N, device=Q.device), diagonal=1).bool()
            scores = scores.masked_fill(mask, float('-inf'))

        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        return torch.matmul(attn_weights, V)  # [B, H, N, d]

    def _phase_attention(
        self,
        Q: torch.Tensor,
        K: torch.Tensor,
        V: torch.Tensor,
        causal_mask: bool = True,
    ) -> torch.Tensor:
        """O(n) phase synchronization attention."""
        B, H, N, d = Q.shape

        # Compute phases from Q
        phases = torch.sigmoid(self.phase_proj(Q)) * (2 * math.pi)  # [B, H, N, d]

        # Mean-field approximation: compute global mean phase
        if causal_mask:
            # Cumulative mean for causal
            phase_cumsum = torch.cumsum(phases, dim=2)
            counts = torch.arange(1, N + 1, device=phases.device).float()
            phase_mean = phase_cumsum / counts.view(1, 1, N, 1)
        else:
            phase_mean = phases.mean(dim=2, keepdim=True)

        # Phase synchronization steps
        for _ in range(self.sync_steps):
            phase_diff = phases - phase_mean
            coupling = torch.sin(phase_diff)
            phases = phases + self.sync_lr * coupling

            if causal_mask:
                phase_cumsum = torch.cumsum(phases, dim=2)
                phase_mean = phase_cumsum / counts.view(1, 1, N, 1)
            else:
                phase_mean = phases.mean(dim=2, keepdim=True)

        # Coherence as attention weights
        coherence = (1 + torch.cos(phases - phase_mean)) / 2  # [B, H, N, d]

        # Global value aggregation (O(n))
        if causal_mask:
            V_cumsum = torch.cumsum(V, dim=2)
            V_global = V_cumsum / counts.view(1, 1, N, 1)
        else:
            V_global = V.mean(dim=2, keepdim=True)

        # Blend local and global based on coherence
        output = coherence * V + (1 - coherence) * V_global

        return output

    def forward(
        self,
        x: torch.Tensor,
        mode: str = "quadratic",
        causal_mask: bool = True,
    ) -> torch.Tensor:
        """
        Forward pass with configurable attention mode.

        Args:
            x: [B, N, D] input tensor
            mode: "quadratic" for O(n²) or "phase" for O(n)
            causal_mask: Apply causal masking

        Returns:
            [B, N, D] output tensor
        """
        B, N, D = x.shape
        residual = x

        # Self-attention
        x = self.norm1(x)

        # Project to Q, K, V
        Q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # Select attention mode
        if mode == "quadratic":
            attn_out = self._quadratic_attention(Q, K, V, causal_mask)
        elif mode == "phase":
            attn_out = self._phase_attention(Q, K, V, causal_mask)
        else:
            raise ValueError(f"Unknown attention mode: {mode}")

        # Reshape and project
        attn_out = attn_out.transpose(1, 2).contiguous().view(B, N, D)
        attn_out = self.out_proj(attn_out)
        attn_out = self.dropout(attn_out)

        # Residual connection
        x = residual + attn_out

        # Feed-forward
        x = x + self.ff(self.norm2(x))

        return x


class SovereignTransformer(nn.Module):
    """
    Sovereign-1 Hybrid Transformer Architecture.

    Combines quadratic (O(n²)) and phase (O(n)) attention with
    a PID Governor at the nexus for cognitive control.

    Architecture (default 6/6 mode):
    --------------------------------
    Input → Embedding → [L1-L6: Quadratic] → PID → [L7-L12: Phase] → Output

    The nexus position is configurable at runtime:
    - 4/8 Mode: More phase attention (logic-heavy)
    - 6/6 Mode: Balanced (default)
    - 8/4 Mode: More quadratic attention (memory-heavy)
    """

    # Ontology to nexus position mapping
    ONTOLOGY_TO_NEXUS = {
        # Logic-heavy: More phase attention (earlier nexus)
        "O7_REASONING": 4,
        "O10_UNIFYING": 4,
        # Balanced: Default creative mode
        "O6_AGENCY": 6,
        "O9_WITNESSES": 6,
        # Memory-heavy: More quadratic attention (later nexus)
        "O4_STRUCTURE": 8,
        "O5_COGNITION": 8,
        # Default
        "default": 6,
    }

    def __init__(
        self,
        config: Optional[SovereignTransformerConfig] = None,
    ):
        super().__init__()
        self.config = config or SovereignTransformerConfig()

        # Embeddings
        self.token_embedding = nn.Embedding(
            self.config.vocab_size,
            self.config.semantic_dim,
        )
        self.position_embedding = nn.Embedding(
            self.config.max_seq_len,
            self.config.semantic_dim,
        )

        # State placeholder (injected by Observer, not learned)
        self.register_buffer(
            'state_placeholder',
            torch.zeros(self.config.state_dim)
        )

        # Ambidextrous layers (can run quadratic or phase)
        self.layers = nn.ModuleList([
            AmbidextrousLayer(
                embed_dim=self.config.embed_dim,
                num_heads=self.config.num_heads,
                ff_dim=self.config.ff_dim,
                dropout=self.config.dropout,
                sync_steps=self.config.sync_steps,
                sync_lr=self.config.sync_lr,
            )
            for _ in range(self.config.num_layers)
        ])

        # PID Governor
        pid_config = PIDGovernorConfig(
            semantic_dim=self.config.semantic_dim,
            state_dim=self.config.state_dim,
        )
        self.pid_governor = PIDGovernor(
            config=pid_config,
            embed_dim=self.config.embed_dim,
        )

        # Output projection
        self.ln_f = nn.LayerNorm(self.config.embed_dim)
        self.lm_head = nn.Linear(self.config.semantic_dim, self.config.vocab_size, bias=False)

        # Tie weights
        self.lm_head.weight = self.token_embedding.weight

    def _embed(
        self,
        token_ids: torch.Tensor,
        state_delta: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Create 1024-D embeddings with state partition.

        Args:
            token_ids: [B, N] token indices
            state_delta: [B, N, 128] from Observer (optional)

        Returns:
            [B, N, 1024] embeddings
        """
        B, N = token_ids.shape
        device = token_ids.device

        # Semantic body [896D]
        positions = torch.arange(N, device=device)
        semantic = self.token_embedding(token_ids) + self.position_embedding(positions)

        # State partition [128D]
        if state_delta is not None:
            state = state_delta
        else:
            state = self.state_placeholder.expand(B, N, -1)

        # Concatenate to 1024D
        return torch.cat([semantic, state], dim=-1)

    def select_nexus(self, dominant_ontology: Optional[str] = None) -> int:
        """
        Select nexus position based on dominant ontology.

        Args:
            dominant_ontology: e.g., "O7_REASONING", "O6_AGENCY"

        Returns:
            Nexus position (4, 6, or 8)
        """
        if dominant_ontology is None:
            return self.config.default_nexus

        return self.ONTOLOGY_TO_NEXUS.get(
            dominant_ontology,
            self.config.default_nexus
        )

    def forward(
        self,
        token_ids: torch.Tensor,
        state_delta: Optional[torch.Tensor] = None,
        nexus_position: Optional[int] = None,
        pid_state: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
        causal_mask: bool = True,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass through hybrid Sovereign architecture.

        Args:
            token_ids: [B, N] input token indices
            state_delta: [B, N, 128] target state from Observer
            nexus_position: Where to insert PID (4, 6, or 8)
            pid_state: (integral_error, prev_error) for streaming
            causal_mask: Apply causal masking

        Returns:
            Dict with:
                - logits: [B, N, V] output logits
                - authority: [B, N] authority scores from PID
                - hidden_states: [B, N, D] final hidden states
                - pid_state: Updated PID state for streaming
        """
        B, N = token_ids.shape
        nexus = nexus_position or self.config.default_nexus

        # Embed with state partition
        x = self._embed(token_ids, state_delta)

        # Target state for PID (use input state_delta or zeros)
        if state_delta is None:
            target_state = torch.zeros(
                B, N, self.config.state_dim,
                device=token_ids.device
            )
        else:
            target_state = state_delta

        # Process through layers with Virtual Nexus
        authority = None
        new_pid_state = pid_state

        for i, layer in enumerate(self.layers):
            # Select attention mode based on nexus position
            if i < nexus:
                mode = "quadratic"
            else:
                mode = "phase"

            # Run layer
            x = layer(x, mode=mode, causal_mask=causal_mask)

            # Insert PID Governor at nexus
            if i == nexus - 1:
                x, authority, new_pid_state = self.pid_governor(
                    x, target_state, pid_state
                )

        # Final layer norm
        x = self.ln_f(x)

        # Extract semantic body for language modeling
        semantic_body = x[..., :self.config.semantic_dim]

        # Output projection
        logits = self.lm_head(semantic_body)

        return {
            'logits': logits,
            'authority': authority,
            'hidden_states': x,
            'pid_state': new_pid_state,
        }

    def generate(
        self,
        token_ids: torch.Tensor,
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_k: int = 50,
        state_delta: Optional[torch.Tensor] = None,
        nexus_position: Optional[int] = None,
    ) -> torch.Tensor:
        """
        Autoregressive generation with PID control.

        Args:
            token_ids: [B, N] prompt tokens
            max_new_tokens: Number of tokens to generate
            temperature: Sampling temperature
            top_k: Top-k filtering
            state_delta: Initial state (optional)
            nexus_position: Nexus position (optional)

        Returns:
            [B, N + max_new_tokens] generated tokens
        """
        self.eval()
        device = token_ids.device

        # Initialize PID state
        pid_state = None
        self.pid_governor.reset_state()

        generated = token_ids.clone()

        with torch.no_grad():
            for _ in range(max_new_tokens):
                # Truncate to max length
                if generated.shape[1] > self.config.max_seq_len:
                    generated = generated[:, -self.config.max_seq_len:]

                # Forward pass
                outputs = self.forward(
                    generated,
                    state_delta=state_delta,
                    nexus_position=nexus_position,
                    pid_state=pid_state,
                )

                logits = outputs['logits'][:, -1, :]  # Last position
                pid_state = outputs['pid_state']

                # Apply temperature
                logits = logits / temperature

                # Top-k filtering
                if top_k > 0:
                    v, _ = torch.topk(logits, top_k)
                    logits[logits < v[:, [-1]]] = float('-inf')

                # Sample
                probs = F.softmax(logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)

                # Append
                generated = torch.cat([generated, next_token], dim=1)

        return generated
