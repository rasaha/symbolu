"""Tiny conditional word-level LM for the pilot (trained from scratch, CPU).

HF model download is blocked in this sandbox, so a real pretrained LM is not
available. This is the smallest honest substitute: a 1-layer GRU LM whose control
code is injected at EVERY timestep (concatenated to the token embedding), so the
conditioning persists through generation rather than washing out from an initial
hidden state. Fluency is therefore SMOKE-LEVEL — the pilot tests the steering
pipeline and the relative ordering of arms, not production text quality.

A `Vocab` is shared across arms so perplexity/proxy scores are comparable.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

PAD, BOS, EOS, UNK = "<pad>", "<bos>", "<eos>", "<unk>"


class Vocab:
    def __init__(self, texts: List[str], extra: Optional[List[str]] = None):
        words = set()
        for t in texts:
            words.update(t.lower().split())
        for w in (extra or []):
            words.add(w.lower())
        self.itos = [PAD, BOS, EOS, UNK] + sorted(words)
        self.stoi = {w: i for i, w in enumerate(self.itos)}

    def __len__(self):
        return len(self.itos)

    def encode(self, text: str) -> List[int]:
        return [self.stoi.get(w, self.stoi[UNK]) for w in text.lower().split()]

    def decode(self, ids: List[int]) -> str:
        skip = {self.stoi[PAD], self.stoi[BOS], self.stoi[EOS]}
        return " ".join(self.itos[i] for i in ids if i not in skip)


class CondGRU(nn.Module):
    def __init__(self, vocab_size: int, code_dim: int, emb: int = 48, hid: int = 96):
        super().__init__()
        self.emb = nn.Embedding(vocab_size, emb)
        self.code_proj = nn.Linear(code_dim, emb) if code_dim > 0 else None
        in_dim = emb + (emb if code_dim > 0 else 0)
        self.gru = nn.GRU(in_dim, hid, batch_first=True)
        self.out = nn.Linear(hid, vocab_size)
        self.code_dim = code_dim

    def forward(self, ids, code=None, h=None):
        x = self.emb(ids)                                   # [B,T,E]
        if self.code_proj is not None and code is not None:
            c = self.code_proj(code).unsqueeze(1).expand(-1, x.shape[1], -1)
            x = torch.cat([x, c], dim=-1)
        y, h = self.gru(x, h)
        return self.out(y), h


def _pad_batch(seqs: List[List[int]], pad_id: int):
    m = max(len(s) for s in seqs)
    return torch.tensor([s + [pad_id] * (m - len(s)) for s in seqs], dtype=torch.long)


def train_model(corpus, vocab: Vocab, codes: Optional[Dict[str, np.ndarray]] = None,
                code_dim: int = 0, steps: int = 400, lr: float = 5e-3,
                batch: int = 32, seed: int = 0, device: str = "cpu") -> CondGRU:
    """Train a (conditional if codes given) LM. corpus: list[(text, axis)]."""
    torch.manual_seed(seed)
    g = torch.Generator().manual_seed(seed)
    model = CondGRU(len(vocab), code_dim).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    pad_id = vocab.stoi[PAD]
    bos, eos = vocab.stoi[BOS], vocab.stoi[EOS]

    seqs = [[bos] + vocab.encode(t) + [eos] for t, _ in corpus]
    axes = [a for _, a in corpus]
    n = len(seqs)
    model.train()
    for _ in range(steps):
        idx = torch.randint(0, n, (batch,), generator=g).tolist()
        bs = [seqs[i] for i in idx]
        x = _pad_batch([s[:-1] for s in bs], pad_id).to(device)
        y = _pad_batch([s[1:] for s in bs], pad_id).to(device)
        code = None
        if codes is not None and code_dim > 0:
            code = torch.tensor(
                np.stack([codes[axes[i]] for i in idx]), dtype=torch.float32, device=device)
        logits, _ = model(x, code)
        loss = F.cross_entropy(logits.reshape(-1, len(vocab)), y.reshape(-1),
                               ignore_index=pad_id)
        opt.zero_grad(); loss.backward(); opt.step()
    model.eval()
    return model


@torch.no_grad()
def generate(model: CondGRU, vocab: Vocab, prompt: str, code: Optional[np.ndarray] = None,
             max_len: int = 12, temp: float = 0.8, seed: int = 0, device: str = "cpu") -> str:
    torch.manual_seed(seed)
    g = torch.Generator().manual_seed(seed)
    bos, eos = vocab.stoi[BOS], vocab.stoi[EOS]
    ids = [bos] + vocab.encode(prompt)
    code_t = None
    if code is not None and model.code_dim > 0:
        code_t = torch.tensor(code[None, :], dtype=torch.float32, device=device)
    h = None
    cur = torch.tensor([ids], dtype=torch.long, device=device)
    logits, h = model(cur, code_t)
    out = list(ids)
    for _ in range(max_len):
        last = logits[:, -1, :] / max(temp, 1e-6)
        probs = F.softmax(last, dim=-1)
        nxt = torch.multinomial(probs, 1, generator=g).item()
        if nxt == eos:
            break
        out.append(nxt)
        cur = torch.tensor([[nxt]], dtype=torch.long, device=device)
        logits, h = model(cur, code_t, h)
    return vocab.decode(out)


@torch.no_grad()
def perplexity(model: CondGRU, vocab: Vocab, text: str, device: str = "cpu") -> float:
    """Perplexity of `text` under an UNCONDITIONAL model (fluency proxy)."""
    bos, eos, pad_id = vocab.stoi[BOS], vocab.stoi[EOS], vocab.stoi[PAD]
    ids = [bos] + vocab.encode(text) + [eos]
    if len(ids) < 2:
        return float("nan")
    x = torch.tensor([ids[:-1]], dtype=torch.long, device=device)
    y = torch.tensor([ids[1:]], dtype=torch.long, device=device)
    logits, _ = model(x, None)
    loss = F.cross_entropy(logits.reshape(-1, len(vocab)), y.reshape(-1), ignore_index=pad_id)
    return float(torch.exp(loss).item())
