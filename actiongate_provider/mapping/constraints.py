"""Constraint & obligation vocabulary mapping.

ActionGate returns *typed* constraints and obligations; the neutral
``ActionGovernanceResult`` carries string tuples. Each native control is encoded
as a ``"type=value"`` string so **no supported control is silently discarded**;
unknown extension types are preserved as ``"ext:type=value"`` rather than dropped.
"""

from __future__ import annotations

from ..core import ActionGateConstraint, ActionGateObligation

#: The constraint types ActionGate is known to emit (documentation + validation).
KNOWN_CONSTRAINT_TYPES: frozenset[str] = frozenset({
    "maximum_amount",
    "execution_deadline",
    "required_approval",
    "allowed_region",
    "parameter_restriction",
    "rate_limit",
    "single_use",
})

#: The obligation types ActionGate is known to emit.
KNOWN_OBLIGATION_TYPES: frozenset[str] = frozenset({
    "notification",
    "logging",
    "human_review",
})


def encode_constraint(c: ActionGateConstraint) -> str:
    prefix = "" if c.type in KNOWN_CONSTRAINT_TYPES else "ext:"
    return f"{prefix}{c.type}={c.value}"


def encode_obligation(o: ActionGateObligation) -> str:
    prefix = "" if o.type in KNOWN_OBLIGATION_TYPES else "ext:"
    return f"{prefix}{o.type}={o.value}" if o.value else f"{prefix}{o.type}"


def encode_constraints(constraints: tuple[ActionGateConstraint, ...]) -> tuple[str, ...]:
    return tuple(encode_constraint(c) for c in constraints)


def encode_obligations(obligations: tuple[ActionGateObligation, ...]) -> tuple[str, ...]:
    return tuple(encode_obligation(o) for o in obligations)
