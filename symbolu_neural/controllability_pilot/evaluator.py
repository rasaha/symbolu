"""Offline proxy evaluators for the pilot (NO LLM judge available in sandbox).

Two independent, transparent axis scorers — both clearly PROXY-ONLY:

1. `LexiconScorer` — counts axis-keyword hits. Zero training, fully transparent.
   Cannot be gamed by the generator's training signal (it's external rules).
2. `ProxyClassifier` — a bag-of-words multinomial logistic regression trained on a
   HELD-OUT split of the corpus, applied to generated text. Marked proxy because
   it is a small linear model, not a human/LLM judge.

Plus distributional + fluency helpers (unigram JS divergence vs base; repetition).
A real study would replace both with human or strong-LLM judges (see README).
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import torch
import torch.nn.functional as F

from .data import AXES, axis_lexicons


class LexiconScorer:
    def __init__(self):
        self.lex = {a: set(ws) for a, ws in axis_lexicons().items()}

    def scores(self, text: str) -> Dict[str, float]:
        toks = text.lower().split()
        raw = {a: sum(1 for t in toks if t in self.lex[a]) for a in AXES}
        s = sum(raw.values())
        if s == 0:
            return {a: 1.0 / len(AXES) for a in AXES}
        return {a: raw[a] / s for a in AXES}

    def argmax(self, text: str) -> str:
        sc = self.scores(text)
        return max(sc, key=sc.get)


class ProxyClassifier:
    """BoW multinomial logistic regression (torch). Proxy-only."""

    def __init__(self, vocab_words: List[str]):
        self.words = sorted(set(vocab_words))
        self.idx = {w: i for i, w in enumerate(self.words)}
        self.W = None
        self.b = None

    def _feat(self, texts: List[str]) -> np.ndarray:
        X = np.zeros((len(texts), len(self.words)))
        for r, t in enumerate(texts):
            for w in t.lower().split():
                if w in self.idx:
                    X[r, self.idx[w]] += 1.0
        n = X.sum(1, keepdims=True)
        return X / np.clip(n, 1, None)

    def fit(self, texts: List[str], labels: List[str], epochs: int = 300, l2: float = 1e-3):
        X = torch.tensor(self._feat(texts), dtype=torch.float32)
        y = torch.tensor([AXES.index(l) for l in labels], dtype=torch.long)
        W = torch.zeros(len(self.words), len(AXES), requires_grad=True)
        b = torch.zeros(len(AXES), requires_grad=True)
        opt = torch.optim.LBFGS([W, b], lr=0.5, max_iter=epochs, line_search_fn="strong_wolfe")

        def closure():
            opt.zero_grad()
            loss = F.cross_entropy(X @ W + b, y) + l2 * (W * W).sum()
            loss.backward()
            return loss

        opt.step(closure)
        self.W, self.b = W.detach().numpy(), b.detach().numpy()
        return self

    def proba(self, text: str) -> Dict[str, float]:
        x = self._feat([text])[0]
        logits = x @ self.W + self.b
        e = np.exp(logits - logits.max())
        p = e / e.sum()
        return {AXES[i]: float(p[i]) for i in range(len(AXES))}

    def argmax(self, text: str) -> str:
        p = self.proba(text)
        return max(p, key=p.get)


def unigram_js(texts_a: List[str], texts_b: List[str]) -> float:
    """Jensen-Shannon divergence between unigram distributions (did output change?)."""
    def dist(texts):
        from collections import Counter
        c = Counter()
        for t in texts:
            c.update(t.lower().split())
        return c
    ca, cb = dist(texts_a), dist(texts_b)
    vocab = set(ca) | set(cb)
    if not vocab:
        return 0.0
    pa = np.array([ca[w] for w in vocab], dtype=float); pa /= max(pa.sum(), 1)
    pb = np.array([cb[w] for w in vocab], dtype=float); pb /= max(pb.sum(), 1)
    m = 0.5 * (pa + pb)

    def kl(p, q):
        mask = p > 0
        return float(np.sum(p[mask] * np.log2(p[mask] / np.clip(q[mask], 1e-12, None))))
    return 0.5 * kl(pa, m) + 0.5 * kl(pb, m)


def repetition_rate(text: str) -> float:
    toks = text.lower().split()
    if len(toks) < 2:
        return 0.0
    bigrams = list(zip(toks, toks[1:]))
    return 1.0 - len(set(bigrams)) / len(bigrams)
