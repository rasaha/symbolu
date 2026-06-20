"""Tiny CPU stub backbone that mimics a HF CausalLM closely enough for MistralCGWrapper.

Used by the CPU tests (gate=0 equivalence, ΔBhava behaviour) so we never need to download
Mistral-7B or touch a GPU. It exposes exactly the surface MistralCGWrapper relies on:

    .config.{hidden_size, vocab_size, num_attention_heads}
    .parameters()                       (for freeze + device/dtype sync)
    .get_input_embeddings()
    .lm_head                            (Linear hidden->vocab)
    __call__(input_ids, attention_mask, output_hidden_states=True)
        -> object with .hidden_states (tuple; [-1] is [B,T,D]) and .logits
    .gradient_checkpointing_enable/disable

Deterministic: hidden states are a fixed function of the token ids, so successive forwards on
different inputs produce different pooled states (needed for the ΔBhava != 0 test).
"""

from __future__ import annotations

from types import SimpleNamespace

try:  # torch optional at import time; tests skip if absent
    import torch
    import torch.nn as nn
    _TORCH = True
except Exception:  # pragma: no cover
    _TORCH = False


if _TORCH:

    class _Cfg:
        def __init__(self, hidden_size, vocab_size, num_attention_heads):
            self.hidden_size = hidden_size
            self.vocab_size = vocab_size
            self.num_attention_heads = num_attention_heads

    class StubBackbone(nn.Module):
        """Minimal deterministic stand-in for a HF CausalLM backbone."""

        def __init__(self, hidden_size=64, vocab_size=128, num_attention_heads=8, seed=0):
            super().__init__()
            torch.manual_seed(seed)
            self.config = _Cfg(hidden_size, vocab_size, num_attention_heads)
            self.embed = nn.Embedding(vocab_size, hidden_size)
            self.lm_head = nn.Linear(hidden_size, vocab_size, bias=False)
            # A small fixed linear so hidden states depend on token content non-trivially.
            self.mix = nn.Linear(hidden_size, hidden_size)
            self.gradient_checkpointing = False

        def get_input_embeddings(self):
            return self.embed

        def gradient_checkpointing_enable(self, **kwargs):
            self.gradient_checkpointing = True

        def gradient_checkpointing_disable(self):
            self.gradient_checkpointing = False

        def forward(self, input_ids, attention_mask=None, output_hidden_states=True, **kwargs):
            h = self.embed(input_ids)
            h = h + torch.tanh(self.mix(h))  # [B, T, D], deterministic in input_ids
            logits = self.lm_head(h)
            return SimpleNamespace(hidden_states=(h,), logits=logits)

        # HF models are callable; nn.Module.__call__ routes to forward already.

    def build_stub_wrapper(hidden_size=64, vocab_size=128, num_heads=8, seed=0,
                           phase_adapter_hidden=32):
        """Construct a MistralCGWrapper around a StubBackbone (no download, CPU only).

        Returns (wrapper, backbone). Raises ImportError if the wrapper deps are unavailable —
        callers (tests) should skip in that case.
        """
        from symbolu_training.training.unified.mistral_wrapper import MistralCGWrapper

        backbone = StubBackbone(hidden_size, vocab_size, num_heads, seed=seed)
        wrapper = MistralCGWrapper(
            pretrained_model=backbone,
            pretrained_tokenizer=None,
            phase_adapter_hidden=phase_adapter_hidden,
        )
        wrapper.eval()
        return wrapper, backbone

else:  # pragma: no cover - torch missing

    def build_stub_wrapper(*args, **kwargs):
        raise ImportError("torch is required for the stub backbone")
