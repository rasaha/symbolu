"""
token_event_bridge.py — bounded token↔event cross-attention adapter (§5 Level B).

Two directed bridges, each ablatable (§12 removes each in turn):

    token → event   the K event slots attend over the T token hiddens, so each event row can be
                    refreshed by the textual context it was extracted from.
    event → token   the pooled token context attends over the K event slots, so the token
                    representation can read the governed event findings.

Both are thin adapters on top of a FROZEN base Mistral (§5 Level B: "freeze the base Mistral
initially; train only event encoder, event attention, and bridge adapters"). Neither bridge is ever
allowed to mutate an exact EventRecord — they operate only on the LEARNED rows; the exact records
and their evidence_ids ride through untouched.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .autograd import Tensor, matmul, row_softmax, add, scale, tanh, row_mean
from ._common import RNG, param


def _small(d: int, rng: RNG) -> Tensor:
    # small-init value projection: the bridge starts near residual pass-through and *learns* to
    # inject cross-modal context, instead of corrupting the other stream with noise at init.
    return param(d, d, rng, scale=0.1 / math.sqrt(d))


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


class CrossBridge:
    def __init__(self, d: int, rng: RNG):
        self.d = d
        # token→event
        self.t2e_q = param(d, d, rng)
        self.t2e_k = param(d, d, rng)
        self.t2e_v = _small(d, rng)
        # event→token
        self.e2t_q = param(d, d, rng)
        self.e2t_k = param(d, d, rng)
        self.e2t_v = _small(d, rng)

    def params(self, prefix="bridge") -> Dict[str, Tensor]:
        return {f"{prefix}.t2e_q": self.t2e_q, f"{prefix}.t2e_k": self.t2e_k,
                f"{prefix}.t2e_v": self.t2e_v, f"{prefix}.e2t_q": self.e2t_q,
                f"{prefix}.e2t_k": self.e2t_k, f"{prefix}.e2t_v": self.e2t_v}

    def token_to_event(self, E: Tensor, Htok: Tensor) -> Tensor:
        """Each event row (query) attends over token hiddens (keys/values). Returns K x d."""
        Q = matmul(E, self.t2e_q)
        K = matmul(Htok, self.t2e_k)
        V = matmul(Htok, self.t2e_v)
        A = row_softmax(scale(matmul(Q, _transpose(K)), 1.0 / math.sqrt(self.d)))
        return tanh(add(E, matmul(A, V)))    # residual onto the event rows

    def event_to_token(self, tok_ctx: Tensor, H_event: Tensor) -> Tensor:
        """Pooled token context (1 x d query) attends over event rows. Returns 1 x d."""
        Q = matmul(tok_ctx, self.e2t_q)
        K = matmul(H_event, self.e2t_k)
        V = matmul(H_event, self.e2t_v)
        A = row_softmax(scale(matmul(Q, _transpose(K)), 1.0 / math.sqrt(self.d)))
        return tanh(add(tok_ctx, matmul(A, V)))
