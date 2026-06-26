"""Char-level LM data: tokenizer + contiguous-block dataset + split."""
from __future__ import annotations

from typing import List, Tuple

import torch


class CharTokenizer:
    def __init__(self, text: str):
        chars = sorted(set(text))
        self.stoi = {c: i for i, c in enumerate(chars)}
        self.itos = {i: c for c, i in self.stoi.items()}
        self.vocab_size = len(chars)

    def encode(self, s: str) -> torch.Tensor:
        return torch.tensor([self.stoi[c] for c in s if c in self.stoi], dtype=torch.long)

    def decode(self, ids) -> str:
        return "".join(self.itos[int(i)] for i in ids)


def load_corpus(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def split_ids(ids: torch.Tensor, val_frac: float = 0.1) -> Tuple[torch.Tensor, torch.Tensor]:
    n = int(len(ids) * (1 - val_frac))
    return ids[:n], ids[n:]


def make_batches(ids: torch.Tensor, block: int, batch: int, generator=None):
    """Yield (x,y) random contiguous blocks. y is x shifted by 1."""
    max_start = len(ids) - block - 1
    while True:
        starts = torch.randint(0, max_start, (batch,), generator=generator)
        x = torch.stack([ids[s:s + block] for s in starts])
        y = torch.stack([ids[s + 1:s + 1 + block] for s in starts])
        yield x, y


def iter_val_blocks(ids: torch.Tensor, block: int, batch: int):
    """Deterministic non-overlapping blocks for evaluation."""
    n = (len(ids) - 1) // block
    xs, ys = [], []
    for i in range(n):
        s = i * block
        xs.append(ids[s:s + block]); ys.append(ids[s + 1:s + 1 + block])
        if len(xs) == batch:
            yield torch.stack(xs), torch.stack(ys); xs, ys = [], []
    if xs:
        yield torch.stack(xs), torch.stack(ys)
