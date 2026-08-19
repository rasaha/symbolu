"""Typed contract-validation errors for the Ugence Benchmark Registry.

Every rejection this package raises is one of these types. **None of them is
ever the inverse of a trusted resolution**: not raising is not a claim that
anything resolved. These are *structural* refusals at construction time — the
package holds no registry, no trust anchor and no approval boundary, and reaches
no admission decision (ADR §16.2 stages 2-6 remain unperformed for every object
this package can build).

The base type subclasses :class:`ValueError`, mirroring the merged
``ugence_governance_contracts`` ``EvidenceContractError`` /
``SystemIdentityContractError`` and the merged trusted-evidence contract error,
so existing ``ValueError`` handling in consuming code still catches a structural
rejection.
"""

from __future__ import annotations

from typing import Optional

from .reasons import BenchmarkRefusalReason

__all__ = [
    "BenchmarkContractError",
    "BenchmarkCanonicalizationError",
    "BenchmarkLifecycleError",
]


class BenchmarkContractError(ValueError):
    """A structural benchmark-definition contract invariant was violated.

    Raised at construction time when a coordinate is missing, blank, padded,
    non-canonical, mistyped, inexact, temporally impossible, duplicated, or
    internally inconsistent. It signals only that the *shape* was refused.

    It is **never** an assertion that a benchmark was approved, published,
    registered, unrevoked, in scope or resolvable. Conversely, a successfully
    constructed contract has established exactly one thing — that it is
    internally consistent and digest-bound — and ADR B-9 rules that "possession
    is not validity".
    """

    #: The typed refusal code this structural rejection maps to. Every raise
    #: site in this package supplies one; ``None`` remains possible only for a
    #: subclass a consumer might define.
    reason: Optional[BenchmarkRefusalReason] = None


class BenchmarkCanonicalizationError(BenchmarkContractError):
    """The value cannot be canonicalized under the declared, versioned rules.

    Raised for a naive datetime, a non-NFC string, a ``float``, a mapping, a
    ``bytes`` value, or any type the canonical encoder does not admit. These are
    refusals, never coercions: the encoder has no permissive fallback and never
    repairs a value into a serializable shape (ADR §22.8 — "unknown types fail
    closed ... never a best-effort serialization").
    """

    reason = BenchmarkRefusalReason.BENCHMARK_CANONICALIZATION_FAILED


class BenchmarkLifecycleError(BenchmarkContractError):
    """A proposed benchmark lifecycle transition is not in the ratified relation.

    The transition relation is the closed set of arrows drawn in ADR §29. A
    transition outside it is refused; it is never downgraded to a warning and
    never silently applied (B-7 — "no silent fallback").
    """

    reason = BenchmarkRefusalReason.BENCHMARK_INVALID_LIFECYCLE_TRANSITION
