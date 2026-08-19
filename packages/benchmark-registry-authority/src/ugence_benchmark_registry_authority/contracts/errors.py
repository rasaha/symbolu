"""Typed contract-validation errors for the benchmark registry authority.

Every error here is a **refusal**. None of them is a partial success, a warning,
or a repairable condition: BR-2A never normalizes an invalid value into an
accepted one, and never returns a degraded object in place of raising.

The hierarchy is deliberately rooted in :class:`ValueError` — the same posture
as the frozen BR-1 identity layer — so a caller that already handles malformed
input handles these too, while the exact classes stay available for callers who
want to distinguish a canonicalization refusal from a structural one.

These are **BR-2A's own** error types. They are not BR-1's and never replace
them: a BR-1 contract nested inside a BR-2A payload keeps raising BR-1's
:class:`ugence_benchmark_registry.BenchmarkContractError` from its own
``__post_init__``, and BR-2A's revalidation boundary catches that and re-raises
it as :class:`BenchmarkRegistryCanonicalizationError` with the offending path.
Two frozen vocabularies, neither shadowing the other.
"""

from __future__ import annotations

__all__ = [
    "BenchmarkRegistryContractError",
    "BenchmarkRegistryCanonicalizationError",
    "BenchmarkRegistryLifecycleError",
    "BenchmarkRegistryCompositionError",
]


class BenchmarkRegistryContractError(ValueError):
    """A BR-2 registry-authority contract refused its input.

    Raised by every ``__post_init__`` in this package. Carries an optional
    :attr:`reason` naming the typed refusal, so a caller can branch on the
    ratified vocabulary rather than on message text.

    Constructing one of this package's contracts proves **structure**, never
    authority: a refusal means the structure is wrong, and the *absence* of a
    refusal means only that the structure is right. It never means a publisher
    was authenticated, an approval was verified, an admission happened, or a
    resolution occurred.
    """

    #: The typed refusal this error corresponds to, when one applies. Set as an
    #: instance attribute by the validators rather than declared as a
    #: constructor argument, so an error can always be raised even where no
    #: ratified reason fits — which then fails closed rather than inventing a
    #: vocabulary member.
    reason = None


class BenchmarkRegistryCanonicalizationError(BenchmarkRegistryContractError):
    """Canonical bytes could not be produced, and none were.

    Raised when the object offered to the encoder is not an exact registered
    contract type, when a nested node fails structural revalidation, or when a
    value has no canonical form. The encoder has no permissive fallback: it
    never renders an unknown object, never substitutes a default, and never
    returns partial bytes.
    """


class BenchmarkRegistryLifecycleError(BenchmarkRegistryContractError):
    """A BR-2 registration-lifecycle rule was violated.

    Covers the closed transition relation, the one-representation-per-transition
    binding, terminal-state rules, and predecessor-state/predecessor-outcome
    requirements. Distinct from BR-1's
    :class:`ugence_benchmark_registry.BenchmarkLifecycleError`, which governs the
    *artifact's own* embedded lifecycle self-declaration; the two lifecycles are
    separate authorities and neither error type is raised for the other's rules.
    """


class BenchmarkRegistryCompositionError(BenchmarkRegistryContractError):
    """A composition root offered an adapter or configuration BR-2 refuses.

    **Defined at BR-2A, raised by nothing at BR-2A.** BR-2A ships no composition
    root, no adapter registry and no identity allow-list — §17 forbids all
    three — so no code path in this package can raise this. The type exists so
    that BR-2B and BR-2D, which do own those paths, raise an error the ratified
    contract already names, rather than minting one after the fact.

    Defining a typed error is not shipping the capability that raises it: this
    class executes nothing, admits nothing and refuses nothing on its own.
    """
