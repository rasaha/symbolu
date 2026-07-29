"""
mistral_adapter.py — the token-language path (Mistral stand-in).

IMPORTANT (honesty boundary): a real Mistral is not available in this sandbox (no GPU, no
transformers/torch). This module is an EXPLICIT, small, local causal-transformer stand-in for the
token path. It is used *identically* across every arm, so relative comparisons between arms are
valid even though absolute perplexity is not Mistral's. It plays the same structural role the spec
assigns to Mistral: token-level self-attention over text, a causal LM head (language capability),
and a pooled hidden state the event bridge can read/write.

    tokens → embedding + positional → 1-layer causal self-attention → hidden H_tok ∈ R^(T × d)
    H_tok → LM head            (next-token loss / perplexity  → §10 language preservation)
    pool(H_tok) → task head    (H0 / H1 answer the task from text alone)

For §5 Level B, `H_tok` and its pooled vector are the interface the token↔event bridge uses; the
LoRA path (H8) adds a trainable low-rank term to `H_tok` that BOTH heads read, so task-only training
of the LoRA can drift the LM — the drift we measure as the language regression.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .autograd import (Tensor, index_rows, matmul, add, add_bias, row_softmax, row_mean, tanh,
                       scale, cross_entropy)
from ._common import RNG, param, zeros_param


def _transpose(t: Tensor) -> Tensor:
    r, c = t.shape
    out = [[t.data[i][j] for i in range(r)] for j in range(c)]
    res = Tensor(out, t.requires_grad, (t,))

    def _bw():
        for i in range(r):
            for j in range(c):
                t.grad[i][j] += res.grad[j][i]
    res._backward = _bw
    return res


def _causal_mask(T: int) -> Tensor:
    # 0 where allowed (j<=i), -1e9 where future (j>i)
    return Tensor([[0.0 if j <= i else -1e9 for j in range(T)] for i in range(T)])


class TokenModel:
    """LM-pretrainable causal token encoder + LM head + task head + optional LoRA."""

    def __init__(self, vocab_size: int, d: int, max_len: int, n_class: int, rng: RNG,
                 lora_rank: int = 4):
        self.d = d
        self.max_len = max_len
        self.vocab_size = vocab_size
        self.emb = param(vocab_size, d, rng)
        self.pos = param(max_len, d, rng)
        self.Wq = param(d, d, rng)
        self.Wk = param(d, d, rng)
        self.Wv = param(d, d, rng)
        self.Wo = param(d, d, rng)
        self.lm_head = param(d, vocab_size, rng)
        self.task_head = param(d, n_class, rng)
        self.task_b = zeros_param(1, n_class)
        # LoRA low-rank adapter on the hidden state (used only by H8)
        self.lora_A = zeros_param(d, lora_rank)   # init 0 → identity at start
        self.lora_B = param(lora_rank, d, rng)
        self.mask_cache: Dict[int, Tensor] = {}

    def clone(self) -> "TokenModel":
        """Deep copy of all parameters (so H0/H1 fine-tuning never mutates the frozen base)."""
        import copy
        m = TokenModel.__new__(TokenModel)
        for k, v in self.__dict__.items():
            if isinstance(v, Tensor):
                nt = Tensor([row[:] for row in v.data], v.requires_grad)
                setattr(m, k, nt)
            elif k == "mask_cache":
                m.mask_cache = {}
            else:
                setattr(m, k, copy.copy(v))
        return m

    # -------- parameter groups --------
    def base_params(self) -> Dict[str, Tensor]:
        return {"tok.emb": self.emb, "tok.pos": self.pos, "tok.Wq": self.Wq, "tok.Wk": self.Wk,
                "tok.Wv": self.Wv, "tok.Wo": self.Wo, "tok.lm_head": self.lm_head}

    def task_params(self) -> Dict[str, Tensor]:
        return {"tok.task_head": self.task_head, "tok.task_b": self.task_b}

    def lora_params(self) -> Dict[str, Tensor]:
        return {"tok.lora_A": self.lora_A, "tok.lora_B": self.lora_B}

    # -------- forward --------
    def hidden(self, ids: List[int], use_lora: bool = False) -> Tensor:
        T = len(ids)
        x = add(index_rows(self.emb, ids), index_rows(self.pos, list(range(T))))
        Q, K, V = matmul(x, self.Wq), matmul(x, self.Wk), matmul(x, self.Wv)
        scores = scale(matmul(Q, _transpose(K)), 1.0 / math.sqrt(self.d))
        if T not in self.mask_cache:
            self.mask_cache[T] = _causal_mask(T)
        A = row_softmax(add(scores, self.mask_cache[T]))
        H = tanh(add(matmul(matmul(A, V), self.Wo), x))     # residual
        if use_lora:
            H = add(H, matmul(matmul(H, self.lora_A), self.lora_B))   # low-rank delta
        return H

    def lm_loss(self, ids: List[int], use_lora: bool = False) -> Tuple[Tensor, int]:
        """Sum next-token CE over positions 0..T-2 (predict ids[t+1] from hidden[t])."""
        return self._lm_loss_graph(self.hidden(ids, use_lora=use_lora), ids, use_lora)

    def _lm_loss_graph(self, H: Tensor, ids: List[int], use_lora: bool):
        T = len(ids)
        logits_all = matmul(H, self.lm_head)      # T x V  (keeps graph)
        loss_sum = None
        n = 0
        for t in range(T - 1):
            tgt = ids[t + 1]
            if tgt == 0:
                break
            row = _row_select(logits_all, t)      # 1 x V
            l = cross_entropy(row, tgt)
            loss_sum = l if loss_sum is None else add(loss_sum, l)
            n += 1
        if loss_sum is None:
            return Tensor([[0.0]]), 0
        return loss_sum, n

    def pooled(self, ids: List[int], use_lora: bool = False) -> Tensor:
        return row_mean(self.hidden(ids, use_lora=use_lora))    # 1 x d

    def task_logits_from_pooled(self, pooled: Tensor) -> Tensor:
        return add_bias(matmul(pooled, self.task_head), self.task_b)


def _row_select(t: Tensor, i: int) -> Tensor:
    """Differentiable single-row selection (1 x c) from (r x c)."""
    c = t.shape[1]
    out = [t.data[i][:]]
    res = Tensor(out, t.requires_grad, (t,))

    def _bw():
        for j in range(c):
            t.grad[i][j] += res.grad[0][j]
    res._backward = _bw
    return res


def perplexity(model: TokenModel, texts_ids: List[List[int]], use_lora: bool = False) -> float:
    tot_loss, tot_n = 0.0, 0
    for ids in texts_ids:
        loss, n = model._lm_loss_graph(model.hidden(ids, use_lora=use_lora), ids, use_lora)
        if n:
            tot_loss += loss.data[0][0]
            tot_n += n
    if tot_n == 0:
        return float("inf")
    return math.exp(tot_loss / tot_n)
