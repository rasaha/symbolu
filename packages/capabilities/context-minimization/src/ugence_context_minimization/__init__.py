"""Ugence Context Minimization — an independent, stdlib-only capability.

Narrow responsibility:

    Reduce an already-assembled context through *extractive omission* while
    preserving a caller-defined deterministic equivalence condition, and FAIL
    CLOSED whenever equivalence cannot be established.

Two modes:

* **Structural** (:func:`~ugence_context_minimization.api.structural_minimize`) —
  structurally-lossless removal of exact duplicates / declared redundancy sets.
  Needs no oracle. Narrower than full Context Minimization.
* **Oracle-verified** (:func:`~ugence_context_minimization.api.minimize_context`) —
  extractive removal proven equivalent to the full context against a neutral
  :class:`~ugence_context_minimization.api.InvarianceOracle`. Requires an oracle.

Authority note: this package creates NO authorization. "Invariance" is defined
entirely by the supplied oracle; the minimizer compares the oracle's opaque
equivalence key and never interprets it. It is extractive, never generative — it
retains, removes, restores, or falls back, but never rewrites, paraphrases, or
summarizes. It imports only the Python standard library — never ActionGate, a
product, a model, or a tokenizer.

Import the curated surface from :mod:`ugence_context_minimization.api`.
"""

from __future__ import annotations

from .version import CONTRACT_VERSION, __version__

__all__ = ["__version__", "CONTRACT_VERSION"]
