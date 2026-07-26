"""
phase_block.py — Stage 5 Phase Transformer block + LM, and Stage 6 local fusion.

Stage 5 (Phase Transformer v1.3): a minimal pre-norm block
    y = x + Phase(LN1(x))
    z = y + FFN(LN2(y))
stacked into a causal LM with tied-embedding option and Phase-state caching.

Stage 6 (Local + Phase v1.4): optionally add a bounded sliding-window path with
PROTECTED ADDITIVE FUSION (no competitive gate):
    y = x + alpha_local · Local(x) + alpha_phase · Phase(LN1(x))
Both coefficients start at 1.0 so neither path begins disabled. They are learnable
scalars, never a softmax gate that could silently suppress the Phase path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from torch import Tensor

from .config import TransformerConfig
from .local_window import LocalWindowAttention
from .phase_core import LightweightPhaseAttention, PhaseState


class FeedForward(nn.Module):
    def __init__(self, dim: int, hidden: int, dropout: float = 0.0, eps: float = 1e-5):
        super().__init__()
        self.norm = nn.LayerNorm(dim, eps=eps)
        self.fc1 = nn.Linear(dim, hidden)
        self.fc2 = nn.Linear(hidden, dim)
        self.act = nn.GELU()
        self.dropout = nn.Dropout(dropout)
        nn.init.normal_(self.fc1.weight, std=0.02); nn.init.zeros_(self.fc1.bias)
        nn.init.normal_(self.fc2.weight, std=0.02); nn.init.zeros_(self.fc2.bias)

    def forward(self, x: Tensor) -> Tensor:
        return x + self.dropout(self.fc2(self.act(self.fc1(self.norm(x)))))


class PhaseTransformerBlock(nn.Module):
    """One block: (optional local +) phase attention with residuals, then FFN."""

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.config = config
        self.phase = LightweightPhaseAttention(config.phase)
        self.ffn = FeedForward(config.embed_dim, config.ffn_dim, config.dropout,
                               eps=config.phase.layernorm_eps)

        self.use_local = config.use_local_window
        if self.use_local:
            self.local = LocalWindowAttention(
                config.embed_dim, config.phase.num_heads, config.local_window_size,
                dropout=config.dropout, layernorm_eps=config.phase.layernorm_eps,
            )
            # Protected additive fusion coefficients (learnable scalars, not a gate).
            self.alpha_local = nn.Parameter(torch.tensor(float(config.local_alpha_init)))
            self.alpha_phase = nn.Parameter(torch.tensor(float(config.phase_alpha_init)))
        else:
            self.local = None

    def forward(self, x: Tensor, *,
                phase_state: Optional[PhaseState] = None,
                return_state: bool = False):
        # Phase path — note phase() already adds its own residual internally, so we
        # take only its delta to combine additively with the local delta.
        p_out = self.phase(x, initial_state=phase_state, return_state=return_state)
        if return_state:
            phase_full, new_state = p_out.output, p_out.state
        else:
            phase_full, new_state = p_out, None
        phase_delta = phase_full - x  # isolate Phase(LN1(x))·aux_scale contribution

        if self.use_local:
            local_delta = self.local(x, return_residual_add=False)
            y = x + self.alpha_local * local_delta + self.alpha_phase * phase_delta
        else:
            y = x + phase_delta

        z = self.ffn(y)
        if return_state:
            return z, new_state
        return z


class LightweightPhaseTransformerLM(nn.Module):
    """Causal language model built from PhaseTransformerBlocks (Stages 5/6)."""

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.config = config
        D = config.embed_dim
        self.token_embed = nn.Embedding(config.vocab_size, D)
        self.pos_embed = nn.Embedding(config.max_seq_len, D)
        self.drop = nn.Dropout(config.dropout)
        self.blocks = nn.ModuleList([PhaseTransformerBlock(config) for _ in range(config.num_layers)])
        self.norm_f = nn.LayerNorm(D, eps=config.phase.layernorm_eps)
        self.lm_head = nn.Linear(D, config.vocab_size, bias=False)
        nn.init.normal_(self.token_embed.weight, std=0.02)
        nn.init.normal_(self.pos_embed.weight, std=0.02)
        nn.init.normal_(self.lm_head.weight, std=0.02)
        if config.tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

    def num_parameters(self) -> int:
        seen, total = set(), 0
        for p in self.parameters():
            if id(p) in seen:
                continue
            seen.add(id(p))
            total += p.numel()
        return total

    def forward(self, input_ids: Tensor,
                labels: Optional[Tensor] = None,
                phase_states: Optional[List[PhaseState]] = None,
                return_states: bool = False):
        B, N = input_ids.shape
        start = 0 if phase_states is None else (phase_states[0].position if phase_states else 0)
        pos = torch.arange(start, start + N, device=input_ids.device).clamp(max=self.config.max_seq_len - 1)
        x = self.drop(self.token_embed(input_ids) + self.pos_embed(pos).unsqueeze(0))

        new_states: List[PhaseState] = []
        for i, block in enumerate(self.blocks):
            st = None if phase_states is None else phase_states[i]
            if return_states:
                x, ns = block(x, phase_state=st, return_state=True)
                new_states.append(ns)
            else:
                x = block(x, phase_state=st, return_state=False)

        x = self.norm_f(x)
        logits = self.lm_head(x)

        loss = None
        if labels is not None:
            loss = nn.functional.cross_entropy(
                logits[:, :-1].reshape(-1, logits.size(-1)),
                labels[:, 1:].reshape(-1),
            )
        if return_states:
            return logits, loss, new_states
        return logits, loss

    @torch.no_grad()
    def generate(self, prefix: Tensor, max_new_tokens: int, greedy: bool = True) -> Tensor:
        """Generate tokens using cached Phase state (O(1) state per step per layer)."""
        self.eval()
        B, _ = prefix.shape
        # Prime the state on the prefix.
        logits, _, states = self.forward(prefix, return_states=True)
        next_tok = logits[:, -1].argmax(-1, keepdim=True)
        out = [next_tok]
        for _ in range(max_new_tokens - 1):
            logits, _, states = self.forward(next_tok, phase_states=states, return_states=True)
            next_tok = logits[:, -1].argmax(-1, keepdim=True)
            out.append(next_tok)
        return torch.cat(out, dim=1)
