"""BTRR training loop (lazy torch). Fail-closed on reserved seeds.

Not exercised in this implementation task (no torch, no authorization). Provided as the faithful
train->freeze->digest path required by the single-checkpoint invariant. Reserved-seed access is guarded
before any side effect; only inadmissible unit-fixture seeds may run in implementation tests, and even
those require torch which is absent here.
"""
from __future__ import annotations

from .config import (BATCH_SIZE, GRADIENT_CLIP, LEARNING_RATE, MAX_UPDATES, OUTPUT_MARKER)
from .execution import assert_generation_allowed


def train_checkpoint(seed: int, examples, *, authorization_token: str | None = None):
    """Train ONE checkpoint for `seed`, then freeze. Raises before any effect on reserved seeds.

    Returns an object exposing `.digest()` for the single-checkpoint invariant. Requires torch.
    """
    assert_generation_allowed(seed, authorization_token)  # centralized fail-closed guard (same as generators)
    import torch  # lazy
    from .model import build_model, parameter_digest
    from .tokenizer import BTRRTokenizer

    tok = BTRRTokenizer()
    model = build_model(seed)
    opt = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE,
                            betas=(0.9, 0.95), weight_decay=0.01)
    model.train()
    step = 0
    while step < MAX_UPDATES and examples:
        batch = examples[step % max(1, len(examples) // BATCH_SIZE)]
        ids = torch.tensor([tok.encode(batch["input"] + OUTPUT_MARKER + batch["output"],
                                       add_bos=True)], dtype=torch.long)
        logits = model(ids[:, :-1])
        loss = torch.nn.functional.cross_entropy(
            logits.reshape(-1, logits.shape[-1]), ids[:, 1:].reshape(-1))
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), GRADIENT_CLIP)
        opt.step(); step += 1
    model.eval()

    class _Frozen:
        def __init__(self, m): self._d = parameter_digest(m); self.model = m
        def digest(self): return self._d
    return _Frozen(model)
