"""ToyFeatureBackbone — a deterministic, FROZEN char featurizer for the toy path.

This is NOT a language model. It is an interpretable surface featurizer used only
to exercise the Stage-1 pipeline end-to-end on CPU without downloading a real
backbone. Per-character hidden state reserves two interpretable dimensions:

    dim 0 = is_vowel(char)      -> sum-pooling over a unit gives its vowel count
    dim 1 = 1.0  (constant)     -> sum-pooling gives the unit's length
    dims 2.. = fixed pseudo-random per char (capacity / distractors)

Because these surface features are linearly present and pool deterministically,
a linear head CAN learn a surface-defined toy rule and GENERALIZE to unseen
words. That validates the harness (data -> heads -> loss -> metrics -> kill
criteria) and demonstrates a PASS path. It says NOTHING about whether real Vritti
structure exists in real text — that requires a real pretrained LM and real human
labels (see README "Interpreting pass/fail").
"""
from __future__ import annotations

import torch
import torch.nn as nn

_VOWELS = set("aeiouAEIOU")


class ToyFeatureBackbone(nn.Module):
    d_model: int

    def __init__(self, d_model: int = 32, vocab_size: int = 256, seed: int = 0):
        super().__init__()
        assert d_model >= 4
        self.d_model = d_model
        self.vocab_size = vocab_size
        g = torch.Generator().manual_seed(seed)
        table = 0.05 * torch.randn(vocab_size, d_model, generator=g)
        table[:, 0] = 0.0
        table[:, 1] = 1.0                       # constant -> length under sum-pool
        for code in range(vocab_size):
            if chr(code) in _VOWELS:
                table[code, 0] = 1.0            # vowel indicator
        self.embed = nn.Embedding(vocab_size, d_model)
        with torch.no_grad():
            self.embed.weight.copy_(table)
        self.embed.weight.requires_grad_(False)  # FROZEN

    def encode(self, input_ids: torch.Tensor,
               attention_mask: torch.Tensor = None) -> torch.Tensor:
        return self.embed(input_ids)            # [B,L,d]


class HFEncodeAdapter(nn.Module):
    """Adapts a HuggingFace causal LM to the .encode(ids,mask)->h interface."""

    def __init__(self, name: str):
        super().__init__()
        from transformers import AutoModel
        self.model = AutoModel.from_pretrained(name)
        self.d_model = self.model.config.hidden_size
        for p in self.model.parameters():
            p.requires_grad_(False)             # FROZEN

    def encode(self, input_ids: torch.Tensor,
               attention_mask: torch.Tensor = None) -> torch.Tensor:
        out = self.model(input_ids=input_ids, attention_mask=attention_mask)
        return out.last_hidden_state
