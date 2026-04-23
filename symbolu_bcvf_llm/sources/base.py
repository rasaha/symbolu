"""§4.2 Source protocol — the abstract interface every source satisfies.

A source at outer decoding step `t` exposes two methods:

    lookahead() -> (probs, valid_mask)
        Probabilities for the L-step forward speculation from the
        source's current conditioning.

            probs       : np.ndarray, shape (L, V), dtype fp32
            valid_mask  : np.ndarray, shape (L,),  dtype bool
                          True at positions where the source has
                          defined logits (pre-EOS per §2.7.4).

    commit(token_id) -> None
        Advance the source's context by one token. After commit,
        a fresh lookahead() reflects the new context.

The outer decoding loop (§4.6) follows the pattern:

    for t in range(max_tokens):
        lookaheads = [src.lookahead() for src in sources]
        next_token = blend(lookaheads)
        if eos: break
        for src in sources:
            src.commit(next_token)

Pull-based rather than streaming because:
  - Each outer step blocks on the blend decision — there's nothing
    to stream between sources until the committed token is chosen.
  - Tests are easier: a test fabricates a stateful MockSource and
    pokes it through the loop deterministically.
  - KV-cache amortization (§2.3.4) fits naturally inside commit().

§2.7.2 fp32 boundary is the source's responsibility — `probs` must
be returned in fp32 regardless of the internal model dtype. Upcast
happens inside the source before returning.
"""

from __future__ import annotations

from typing import Optional, Protocol, Tuple, runtime_checkable

import numpy as np


@runtime_checkable
class Source(Protocol):
    """Abstract source protocol (§4.2). See module docstring."""

    L: int
    vocab_size: int
    eos_token_id: Optional[int]

    def lookahead(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return `(probs, valid_mask)` for the current context.

        probs      : (L, V) fp32 — softmax output along the lookahead axis.
        valid_mask : (L,)  bool  — True at positions with defined logits.
        """
        ...

    def commit(self, token_id: int) -> None:
        """Append the committed token to this source's context."""
        ...


@runtime_checkable
class BatchedScoringSource(Source, Protocol):
    """Optional extension — a source that can teacher-force score a
    sequence in one forward pass (§6.2 Phase 2 optimization).

    Sources that implement this protocol provide a fast path for
    vanilla + blend scoring by computing log-probs for all target
    tokens in a single batched forward pass, instead of the
    per-token lookahead/commit loop. BCVF-trust scoring continues to
    use the speculation-based path to preserve §2.3.2 semantics.

    Implementors: `HuggingFaceSource` (§4.4). Callers: the §6.3
    `score_choice_vanilla` / `score_choice_blend` when the source
    satisfies this protocol; fallback to per-token loop otherwise.
    """

    def score_teacher_forced(
        self, target_tokens: "np.ndarray | list[int]"
    ) -> np.ndarray:
        """Return fp64 per-position probabilities given teacher-forcing.

        For each position `k ∈ [0, K-1]` (K = len(target_tokens)),
        produce the full probability vector `p(· | prompt ⊕ target[:k])`.
        The caller indexes into these to compute log P(target[k]).

        Returns: shape (K, V) fp64.

        MUST NOT mutate the source's committed-prefix state — leaves
        `self` in the same state as before the call.
        """
        ...


def stable_softmax(z: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically-stable softmax returning fp32 regardless of input dtype.

    Callers: any Source implementation that owns the softmax boundary.
    §2.7.2 requires fp32 at the BCVF boundary; callers producing
    fp16/bf16 logits upstream must upcast to fp64 here and cast down
    to fp32 on return to preserve the stencil-cancellation precision
    §2.7.2 discusses.
    """
    z64 = z.astype(np.float64, copy=False)
    z_shift = z64 - np.max(z64, axis=axis, keepdims=True)
    e = np.exp(z_shift)
    p = e / np.sum(e, axis=axis, keepdims=True)
    return p.astype(np.float32)


def truncating_valid_mask(
    lookahead_tokens: np.ndarray,
    eos_token_id: Optional[int],
    L: int,
) -> np.ndarray:
    """Return a (L,) bool mask: False at positions past the first EOS.

    If `eos_token_id is None` or EOS never appears, returns all True.
    The first EOS position itself is marked True — the source has a
    defined logit there; positions after the EOS are marked False
    because the source has no natural way to continue.
    """
    mask = np.ones(L, dtype=bool)
    if eos_token_id is None:
        return mask
    eos_positions = np.where(lookahead_tokens == eos_token_id)[0]
    if len(eos_positions) == 0:
        return mask
    first_eos = int(eos_positions[0])
    if first_eos + 1 < L:
        mask[first_eos + 1 :] = False
    return mask
