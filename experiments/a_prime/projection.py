"""A1.4 deterministic projection P for Milestone A' — ENGINEERING PIPELINE ONLY.

Implements the pre-registered, parameter-free per-stimulus -> per-phoneme
projection and the section-4 word-level aggregation defined in
``MILESTONE_A_PRIME_PREREGISTRATION_AMENDMENT_1.md`` (A1.4) and
``MILESTONE_A_PRIME_PREREGISTRATION.md`` (section 4).

This module produces NO A' result. It computes the deterministic map
``E' = P(E)`` and the aggregation only. It contains:

* no semantic observable ``Y``;
* no probe ``P_probe``, no baseline suite, no conditional-MI estimator;
* no inference, no PASS / FAIL / INCONCLUSIVE / failure-state decision.

Properties (validated in ``test_projection.py``):

* **Deterministic / reproducible** — given identical ``(sequences, ratings)``
  the output is bit-stable. No randomness, no tuned hyper-parameters; the
  per-phoneme estimate is the Moore-Penrose least-squares solution
  ``e = X^+ r`` of the assumed additive model ``r ~= X e`` (the canonical
  minimum-norm solution resolves any rank deficiency without a choice).
* **Additive / order-free by construction** — ``X`` holds phoneme *counts*,
  so position/order is intentionally discarded (the additive branch). The
  estimate therefore cannot encode order/interaction information.

It is a deliberately conservative, gloss-independent input transform; it
makes no claim about meaning. See ``MILESTONE_A_PRIME_EXECUTION_STATUS.md``
for why A' itself is not runnable with currently-available data.
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np


def build_incidence(
    sequences: Sequence[Sequence[str]],
    vocab: list[str] | None = None,
    add_intercept: bool = True,
) -> tuple[np.ndarray, list[str]]:
    """Phoneme incidence/count design matrix.

    Parameters
    ----------
    sequences : list of phoneme-token sequences (one per stimulus). Order is
        ignored — only counts enter (additive branch).
    vocab : fixed phoneme inventory; if ``None`` it is the sorted set of tokens
        observed across ``sequences`` (deterministic).
    add_intercept : append a single all-ones column (A1.4 step 3).

    Returns
    -------
    (X, vocab) where ``X`` has shape ``(n_stimuli, n_phonemes [+ 1])``; the
    intercept, when added, is the last column.
    """
    if vocab is None:
        vocab = sorted({p for seq in sequences for p in seq})
    index = {p: i for i, p in enumerate(vocab)}
    n, m = len(sequences), len(vocab)
    X = np.zeros((n, m), dtype=float)
    for r, seq in enumerate(sequences):
        for p in seq:
            if p in index:  # tokens outside the fixed vocab are dropped
                X[r, index[p]] += 1.0
    if add_intercept:
        X = np.hstack([X, np.ones((n, 1))])
    return X, vocab


def project_per_phoneme(
    sequences: Sequence[Sequence[str]],
    ratings: Iterable[float],
    vocab: list[str] | None = None,
) -> tuple[list[str], np.ndarray]:
    """Per-phoneme E' values via the A1.4 closed-form projection ``e = X^+ r``.

    The intercept column is solved jointly and then discarded (A1.4 step 4).
    Deterministic and parameter-free.

    Returns ``(vocab, e)`` where ``e[i]`` is the per-phoneme value for
    ``vocab[i]``.
    """
    X, vocab = build_incidence(sequences, vocab=vocab, add_intercept=True)
    r = np.asarray(list(ratings), dtype=float).reshape(-1)
    if r.shape[0] != X.shape[0]:
        raise ValueError(
            f"ratings length {r.shape[0]} != n_stimuli {X.shape[0]}"
        )
    coef = np.linalg.pinv(X) @ r           # min-norm least squares
    return vocab, coef[: len(vocab)]        # drop the trailing intercept


def aggregate_to_items(
    item_sequences: Sequence[Sequence[str]],
    vocab: Sequence[str],
    phoneme_values: Sequence[float],
    aggs: tuple[str, ...] = ("mean", "sum", "min", "max"),
) -> np.ndarray:
    """Section-4 aggregation: per-item E'_feat from per-phoneme values.

    Phonemes absent from ``vocab`` are skipped (no imputation, A1.4 step 5).
    An item with zero covered phonemes yields a row of NaN — coverage is a
    downstream feasibility concern (pre-registration section 9.0), handled
    elsewhere, not here.
    """
    value = {p: float(v) for p, v in zip(vocab, phoneme_values)}
    funcs = {"mean": np.mean, "sum": np.sum, "min": np.min, "max": np.max}
    out = np.full((len(item_sequences), len(aggs)), np.nan)
    for i, seq in enumerate(item_sequences):
        vals = [value[p] for p in seq if p in value]
        if vals:
            for j, a in enumerate(aggs):
                out[i, j] = float(funcs[a](vals))
    return out
