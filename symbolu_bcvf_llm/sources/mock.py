"""§4.3 MockSource — deterministic, torch-free source for testing.

Takes a `logits_fn: Callable[[Tuple[int, ...]], np.ndarray]` that
maps committed-prefix tuples to `(L, V)` logit arrays. MockSource
owns the state (committed prefix) and the softmax + EOS-mask
conversion; the caller only supplies the raw logits mapping.

Design intent: unit-test the outer decoding loop (§4.6) and the
eventual §5 trust-shaped decoder without pulling torch. The mock
is also the canonical way to construct integration traces for
regression tests — no GPU, no model download, no tokenizer.

Two construction patterns used by the §4.9 test suite:

    # Pattern 1 — greedy argmax of a fixed logit table.
    table = {(): np.array([[10, 0, 0], [0, 10, 0], ...]),
             (0,): np.array([...]),
             (0, 1): np.array([...])}
    src = MockSource(lambda prefix: table[prefix], L=5, V=3)

    # Pattern 2 — programmatic. Source drifts away from another.
    src = MockSource(
        lambda prefix: np.random.default_rng(hash(prefix) & 0xffffffff)
                       .normal(size=(5, V)),
        L=5, V=V,
    )

The mock never raises at lookup time — if the supplied fn produces
an array of the wrong shape, NumPy will complain downstream with a
clear broadcast error. MockSource does validate shape on return to
catch caller bugs early.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import numpy as np

from .base import Source, stable_softmax, truncating_valid_mask


class MockSource:
    """Implements the §4.2 `Source` protocol from a callable logits fn."""

    L: int
    vocab_size: int
    eos_token_id: Optional[int]

    def __init__(
        self,
        logits_fn: Callable[[Tuple[int, ...]], np.ndarray],
        L: int,
        V: int,
        eos_token_id: Optional[int] = None,
        initial_prefix: Optional[List[int]] = None,
    ) -> None:
        if L < 3:
            raise ValueError("MockSource requires L >= 3 (§2.3.4 stencil)")
        if V < 1:
            raise ValueError("MockSource requires V >= 1")
        self._logits_fn = logits_fn
        self.L = L
        self.vocab_size = V
        self.eos_token_id = eos_token_id
        self._committed: List[int] = list(initial_prefix or [])

    # §4.2 protocol -------------------------------------------------- #

    def lookahead(self) -> Tuple[np.ndarray, np.ndarray]:
        z = np.asarray(
            self._logits_fn(tuple(self._committed))
        )
        if z.shape != (self.L, self.vocab_size):
            raise ValueError(
                f"logits_fn returned shape {z.shape}; "
                f"expected ({self.L}, {self.vocab_size})"
            )
        probs = stable_softmax(z, axis=-1)
        lookahead_tokens = np.argmax(z, axis=-1)
        mask = truncating_valid_mask(lookahead_tokens, self.eos_token_id, self.L)
        return probs, mask

    def commit(self, token_id: int) -> None:
        if not (0 <= int(token_id) < self.vocab_size):
            raise ValueError(
                f"token_id {token_id} out of vocab range [0, {self.vocab_size})"
            )
        self._committed.append(int(token_id))

    # Introspection for tests ---------------------------------------- #

    @property
    def committed_prefix(self) -> Tuple[int, ...]:
        return tuple(self._committed)

    def reset(self, prefix: Optional[List[int]] = None) -> None:
        """Rewind committed state — test-only, not part of the §4.2 protocol."""
        self._committed = list(prefix or [])

    # §6.2 Phase 2 batched scoring ---------------------------------- #

    def score_teacher_forced(self, target_tokens) -> np.ndarray:
        """Teacher-forced per-position probabilities via the source's
        `logits_fn` callback (slow-path fallback).

        Mock sources' logits_fn returns a (L, V) lookahead; for
        teacher-forced scoring we read only position l=0 at each
        step. Iterates target_tokens, snapshotting + restoring the
        committed prefix so `self` ends unchanged — matches the
        §6.2 contract.

        For the HuggingFace batched path that does it in one forward
        pass, see ``HuggingFaceSource.score_teacher_forced``.
        """
        saved = tuple(self._committed)
        try:
            out_rows: List[np.ndarray] = []
            for target in target_tokens:
                probs_L_V, _mask = self.lookahead()
                row = probs_L_V[0].astype(np.float64)
                out_rows.append(row)
                self.commit(int(target))
            return np.stack(out_rows, axis=0) if out_rows else (
                np.zeros((0, self.vocab_size), dtype=np.float64)
            )
        finally:
            self._committed = list(saved)


# Structural check: MockSource must satisfy the Source protocol.
_: Source = MockSource(lambda _p: np.zeros((3, 2)), L=3, V=2)
