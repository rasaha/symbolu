"""The authority ``Scope`` value object and the monotonicity relation.

A ``Scope`` is the single shape used for authority in three places — an
:class:`~risk_authority.domain.authority.AuthorityGrant` (what a principal may
grant), a :class:`~risk_authority.domain.decision.RiskDecision` (what was
granted) and a :class:`~risk_authority.domain.envelope.RiskAuthorizationEnvelope`
(what the runtime may exercise). Because all three share one shape, the two
non-negotiable containment invariants (spec §29) reduce to one relation:

    Scope_envelope  ⊆  Scope_decision  ⊆  Scope_grant

:func:`subset_violations` computes that relation per dimension and returns the
reasons a candidate is *broader* than its bound. Empty list == contained.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

__all__ = ["Scope", "subset_violations"]


@dataclass(frozen=True)
class Scope:
    """A bounded authority scope across every governed dimension.

    Allow-dimensions are permissive sets (narrowing removes members).
    Deny-dimensions are prohibitive sets (narrowing *adds* members).
    Numeric ceilings narrow downward. ``None`` on a ceiling means "unbounded".
    """

    purposes: tuple[str, ...] = ()
    tools_allow: tuple[str, ...] = ()
    tools_deny: tuple[str, ...] = ()
    data_allow: tuple[str, ...] = ()
    data_deny: tuple[str, ...] = ()
    destinations: tuple[str, ...] = ()
    jurisdictions: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    actors: tuple[str, ...] = ()
    max_autonomy_level: int = 0
    max_transaction_minor_units: Optional[int] = None

    def normalized(self) -> "Scope":
        """Return a copy with allow/deny dimensions de-duplicated and sorted.

        Ordering is not semantic for these membership sets, so normalization
        keeps digests stable regardless of how a caller ordered inputs.
        """

        def norm(values: tuple[str, ...]) -> tuple[str, ...]:
            return tuple(sorted(set(values)))

        return Scope(
            purposes=norm(self.purposes),
            tools_allow=norm(self.tools_allow),
            tools_deny=norm(self.tools_deny),
            data_allow=norm(self.data_allow),
            data_deny=norm(self.data_deny),
            destinations=norm(self.destinations),
            jurisdictions=norm(self.jurisdictions),
            models=norm(self.models),
            actors=norm(self.actors),
            max_autonomy_level=self.max_autonomy_level,
            max_transaction_minor_units=self.max_transaction_minor_units,
        )


# Allow-dimensions: the candidate set must be a subset of the bound set.
_ALLOW_DIMS = (
    "purposes",
    "tools_allow",
    "data_allow",
    "destinations",
    "jurisdictions",
    "models",
    "actors",
)
# Deny-dimensions: the bound's denies must all be present in the candidate
# (the candidate may deny *more*, never fewer).
_DENY_DIMS = ("tools_deny", "data_deny")


def subset_violations(candidate: Scope, bound: Scope) -> list[str]:
    """Return reasons ``candidate`` exceeds ``bound`` (empty == contained).

    This is the machine form of the envelope- and delegation-monotonicity
    invariants: a candidate scope may be equal to or narrower than its bound
    on every dimension, never broader.
    """

    violations: list[str] = []

    for dim in _ALLOW_DIMS:
        extra = set(getattr(candidate, dim)) - set(getattr(bound, dim))
        if extra:
            violations.append(
                f"{dim}: {sorted(extra)} not permitted by bound"
            )

    for dim in _DENY_DIMS:
        missing = set(getattr(bound, dim)) - set(getattr(candidate, dim))
        if missing:
            violations.append(
                f"{dim}: candidate fails to deny {sorted(missing)} required by bound"
            )

    if candidate.max_autonomy_level > bound.max_autonomy_level:
        violations.append(
            "max_autonomy_level: "
            f"{candidate.max_autonomy_level} exceeds bound {bound.max_autonomy_level}"
        )

    c_amt = candidate.max_transaction_minor_units
    b_amt = bound.max_transaction_minor_units
    if b_amt is not None:
        # Bound is limited: candidate must be limited and no higher.
        if c_amt is None:
            violations.append(
                "max_transaction_minor_units: candidate is unbounded but bound is "
                f"{b_amt}"
            )
        elif c_amt > b_amt:
            violations.append(
                f"max_transaction_minor_units: {c_amt} exceeds bound {b_amt}"
            )
    # If the bound is unbounded (None), any candidate ceiling is contained.

    return violations
