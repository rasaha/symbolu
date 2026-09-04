"""BTRR training loop (lazy torch). Fail-closed on reserved seeds.

Trains exactly ONE checkpoint for a seed with the frozen recipe, then freezes it. Output-only next-token
cross-entropy (the prompt is masked with IGNORE_INDEX; only the structured-output tokens are supervised).
Requires torch; not runnable in a torch-free environment. Reserved-seed access is guarded before any side
effect via the centralized two-key guard.
"""
from __future__ import annotations

import random

from .config import (BATCH_SIZE, BETA1, BETA2, GRADIENT_CLIP, IGNORE_INDEX, LEARNING_RATE,
                     MAX_SEQ_LEN, MAX_UPDATES, OUTPUT_MARKER, VOCAB_SIZE, WEIGHT_DECAY)
from .execution import assert_generation_allowed


class FrozenCheckpoint:
    """A frozen, evaluated model exposing a stable digest for the single-checkpoint invariant."""

    def __init__(self, model, device: str) -> None:
        from .model import parameter_digest
        self.model = model
        self.device = device
        self._digest = parameter_digest(model)

    def digest(self) -> str:
        return self._digest


def train_checkpoint(seed: int, examples, *, authorization_token: str | None = None,
                     max_updates: int = MAX_UPDATES) -> FrozenCheckpoint:
    """Train ONE checkpoint for `seed`, then freeze. Raises before any effect on reserved seeds.

    `examples` = list of {"input": str, "output": str}. Returns a FrozenCheckpoint. Requires torch.
    """
    assert_generation_allowed(seed, authorization_token)  # centralized two-key guard; fail-closed
    import torch
    from .model import build_model
    from .tokenizer import BTRRTokenizer

    tok = BTRRTokenizer()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_model(seed).to(dev)
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, betas=(BETA1, BETA2),
                            weight_decay=WEIGHT_DECAY)

    # pre-tokenize: (full_ids, prompt_len) so the loss supervises output tokens only
    data: list[tuple[list[int], int]] = []
    for ex in examples:
        prompt = ex["input"] + OUTPUT_MARKER
        full_ids = tok.encode(prompt + ex["output"], add_bos=True, add_eos=True)
        prompt_len = len(tok.encode(prompt, add_bos=True))
        if len(full_ids) <= MAX_SEQ_LEN:
            data.append((full_ids, prompt_len))
    if not data:
        raise ValueError("no training examples fit within max_seq_len")

    rng = random.Random(int(seed))
    step = 0
    while step < max_updates:
        batch = [data[rng.randrange(len(data))] for _ in range(BATCH_SIZE)]
        maxlen = max(len(ids) for ids, _ in batch)
        inp = torch.full((BATCH_SIZE, maxlen), tok.pad_id, dtype=torch.long, device=dev)
        lbl = torch.full((BATCH_SIZE, maxlen), IGNORE_INDEX, dtype=torch.long, device=dev)
        for i, (ids, plen) in enumerate(batch):
            t = torch.tensor(ids, dtype=torch.long, device=dev)
            inp[i, :len(ids)] = t
            lbl[i, plen:len(ids)] = t[plen:]          # supervise output tokens only
        logits = model(inp[:, :-1])
        loss = torch.nn.functional.cross_entropy(
            logits.reshape(-1, VOCAB_SIZE), lbl[:, 1:].reshape(-1), ignore_index=IGNORE_INDEX)
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), GRADIENT_CLIP)
        opt.step(); step += 1

    model.eval()
    return FrozenCheckpoint(model, dev)
