"""Backbone wrapper.

Symbol-U assumes (does not reinvent) a conventional sequence backbone. For the
MVP this wraps any HuggingFace causal LM and exposes:
  - hidden states  h:[B,L,d]
  - LM head logits over the vocabulary
  - freeze / partial-unfreeze controls for the staged training plan.

A tiny dependency-free DummyBackbone is provided so the package imports and the
shape contracts can be exercised without transformers/torch-hub downloads.
"""
from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn


class DummyBackbone(nn.Module):
    """Minimal stand-in: embedding -> 1 transformer layer -> tied LM head."""

    def __init__(self, vocab_size: int = 256, d_model: int = 64, n_pos: int = 128):
        super().__init__()
        self.d_model = d_model
        self.vocab_size = vocab_size
        self.tok = nn.Embedding(vocab_size, d_model)
        self.pos = nn.Embedding(n_pos, d_model)
        self.layer = nn.TransformerEncoderLayer(
            d_model, nhead=4, dim_feedforward=4 * d_model, batch_first=True
        )
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

    def hidden_states(self, input_ids: torch.Tensor,
                      attention_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        B, L = input_ids.shape
        pos = torch.arange(L, device=input_ids.device).unsqueeze(0)
        h = self.tok(input_ids) + self.pos(pos)
        kpm = None if attention_mask is None else (attention_mask == 0)
        return self.layer(h, src_key_padding_mask=kpm)

    def logits(self, h: torch.Tensor) -> torch.Tensor:
        return self.lm_head(h)


class BackboneWrapper(nn.Module):
    def __init__(self, model: nn.Module, d_model: int):
        super().__init__()
        self.model = model
        self.d_model = d_model

    @classmethod
    def from_pretrained(cls, name: str, d_model: int) -> "BackboneWrapper":
        from transformers import AutoModelForCausalLM  # lazy import
        m = AutoModelForCausalLM.from_pretrained(name, output_hidden_states=True)
        return cls(m, d_model)

    @classmethod
    def dummy(cls, vocab_size: int = 256, d_model: int = 64) -> "BackboneWrapper":
        return cls(DummyBackbone(vocab_size, d_model), d_model)

    def freeze(self) -> None:
        for p in self.model.parameters():
            p.requires_grad_(False)

    def unfreeze_last_n_layers(self, n: int) -> None:
        """Best-effort partial unfreeze for staged training (stage 2)."""
        if n <= 0:
            return
        blocks = [m for m in self.model.modules()
                  if isinstance(m, nn.TransformerEncoderLayer)]
        for blk in blocks[-n:]:
            for p in blk.parameters():
                p.requires_grad_(True)

    def forward(self, input_ids, attention_mask=None):
        if isinstance(self.model, DummyBackbone):
            h = self.model.hidden_states(input_ids, attention_mask)
            return h, self.model.logits(h)
        out = self.model(input_ids=input_ids, attention_mask=attention_mask)
        h = out.hidden_states[-1]
        return h, out.logits
