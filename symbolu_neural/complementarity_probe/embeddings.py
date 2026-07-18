"""Transformer sentence embeddings `E` for the complementarity probe.

`E` is the thing `U` must beat: a modern contextual sentence representation.
Two backends:

- ``hf``       : a real pretrained Transformer (mean-pooled last hidden state).
                 This is the ONLY backend whose results support a scientific
                 conclusion about complementarity.
- ``hashing``  : a deterministic, offline char-n-gram hashing embedding. It is
                 NOT a semantic encoder; it exists solely so the harness, smoke
                 test, and CI run with no network/model. Results on this backend
                 are meaningless for the real question and are labeled as such.

Any conclusion in a committed report MUST come from the ``hf`` backend.
"""
from __future__ import annotations

import hashlib
from typing import List, Sequence

import numpy as np


class Embedder:
    backend: str
    dim: int

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        raise NotImplementedError

    @property
    def is_semantic(self) -> bool:
        return False


class HashingEmbedder(Embedder):
    """Offline, deterministic, NON-semantic. For smoke/CI only."""

    backend = "hashing"

    def __init__(self, dim: int = 256, ngram: int = 3):
        self.dim = dim
        self.ngram = ngram

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float64)
        t = "".join(c if c.isalnum() else " " for c in text.lower())
        toks = t.split()
        for w in toks:
            pad = f"#{w}#"
            for i in range(len(pad) - self.ngram + 1):
                g = pad[i : i + self.ngram]
                h = int(hashlib.md5(g.encode()).hexdigest(), 16)
                v[h % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts])

    @property
    def is_semantic(self) -> bool:
        return False


class HFEmbedder(Embedder):
    """Mean-pooled last hidden state of a pretrained Transformer."""

    backend = "hf"

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._torch = torch
        self.model_name = model_name
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()
        self.dim = int(self.model.config.hidden_size)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        torch = self._torch
        out = []
        with torch.no_grad():
            for i in range(0, len(texts), 32):
                batch = list(texts[i : i + 32])
                enc = self.tok(batch, padding=True, truncation=True, return_tensors="pt")
                h = self.model(**enc).last_hidden_state          # [B, T, D]
                mask = enc["attention_mask"].unsqueeze(-1).float()
                pooled = (h * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                out.append(pooled.cpu().numpy())
        return np.concatenate(out, 0).astype(np.float64)

    @property
    def is_semantic(self) -> bool:
        return True


def get_embedder(backend: str = "hashing", model_name: str | None = None) -> Embedder:
    if backend == "hf":
        return HFEmbedder(model_name or "sentence-transformers/all-MiniLM-L6-v2")
    if backend == "hashing":
        return HashingEmbedder()
    raise ValueError(f"unknown embedding backend: {backend!r}")
