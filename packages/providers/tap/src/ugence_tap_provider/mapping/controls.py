"""Assertion constraint & obligation vocabulary mapping.

TAP returns *typed* constraints and obligations; the neutral
``AssertionGovernanceResult`` carries string tuples. Each native control is
encoded as a ``"type=value"`` string (or bare ``"type"`` for a valueless
obligation) so **no supported control is silently discarded**; unknown extension
types are preserved as ``"ext:type=value"`` rather than dropped.

A *constraint* limits what may be asserted; an *obligation* requires an
additional step or disclosure. They are kept in separate tuples — never flattened
into one free-text explanation.
"""

from __future__ import annotations

from ..core import TapConstraint, TapObligation

#: Constraint types TAP is known to emit (documentation + validation).
KNOWN_CONSTRAINT_TYPES: frozenset[str] = frozenset({
    "required_qualifier",
    "allowed_scope",
    "maximum_confidence",
    "required_attribution",
    "temporal_limitation",
    "population_limitation",
    "metric_limitation",
    "approved_wording",
    "prohibited_wording",
})

#: Obligation types TAP is known to emit.
KNOWN_OBLIGATION_TYPES: frozenset[str] = frozenset({
    "include_citation",
    "include_uncertainty_disclosure",
    "request_human_review",
    "obtain_additional_evidence",
    "retain_source_attribution",
    "log_evidence_provenance",
})


def encode_constraint(c: TapConstraint) -> str:
    prefix = "" if c.type in KNOWN_CONSTRAINT_TYPES else "ext:"
    return f"{prefix}{c.type}={c.value}" if c.value else f"{prefix}{c.type}"


def encode_obligation(o: TapObligation) -> str:
    prefix = "" if o.type in KNOWN_OBLIGATION_TYPES else "ext:"
    return f"{prefix}{o.type}={o.value}" if o.value else f"{prefix}{o.type}"


def encode_constraints(constraints: tuple[TapConstraint, ...]) -> tuple[str, ...]:
    return tuple(encode_constraint(c) for c in constraints)


def encode_obligations(obligations: tuple[TapObligation, ...]) -> tuple[str, ...]:
    return tuple(encode_obligation(o) for o in obligations)
