"""Constraint / obligation / reason-code / trace preservation, and canonical==legacy
encodings.

ActionGate emits typed constraints and obligations; the neutral result carries
string tuples. No supported control is silently discarded; unknown extension types
are preserved as ``ext:type=value``. The canonical package and the legacy facade
produce identical encodings.
"""
from __future__ import annotations

from ugence_governance_provider_framework.api import ActionGovernanceRequest

from ugence_actiongate_provider.configuration import build_actiongate_provider
from ugence_actiongate_provider.core import (
    ActionGateConstraint, ActionGateEngine, ActionGateObligation, ConstrainedRule)
from ugence_actiongate_provider.mapping import (
    KNOWN_CONSTRAINT_TYPES, KNOWN_OBLIGATION_TYPES, encode_constraints, encode_obligations)

_ALL_CONSTRAINTS = ("maximum_amount", "execution_deadline", "required_approval",
                    "allowed_region", "parameter_restriction", "rate_limit", "single_use")


def test_all_known_constraint_types_supported():
    assert set(_ALL_CONSTRAINTS) <= KNOWN_CONSTRAINT_TYPES
    encoded = encode_constraints(tuple(ActionGateConstraint(t, "v") for t in _ALL_CONSTRAINTS))
    assert encoded == tuple(f"{t}=v" for t in _ALL_CONSTRAINTS)
    assert all(not e.startswith("ext:") for e in encoded)


def test_unknown_constraint_preserved_as_ext():
    encoded = encode_constraints((ActionGateConstraint("bespoke_control", "42"),))
    assert encoded == ("ext:bespoke_control=42",)


def test_known_and_unknown_obligations_preserved():
    assert {"notification", "logging", "human_review"} <= KNOWN_OBLIGATION_TYPES
    encoded = encode_obligations((ActionGateObligation("human_review"),
                                  ActionGateObligation("notification", "ops"),
                                  ActionGateObligation("bespoke_obl", "x")))
    assert encoded == ("human_review", "notification=ops", "ext:bespoke_obl=x")


def test_reason_codes_and_trace_preserved_through_authorization():
    rule = ConstrainedRule(constraints=(ActionGateConstraint("single_use", "true"),),
                           obligations=(ActionGateObligation("human_review"),))
    p = build_actiongate_provider(ActionGateEngine(constrained={"C": rule})); p.initialize()
    r = p.authorize(ActionGovernanceRequest("C"))
    assert r.reason_codes and "policy_allow_with_constraints" in r.reason_codes
    assert r.provider_trace_id.startswith("ag-")


def test_ordering_does_not_change_semantics():
    a = encode_constraints((ActionGateConstraint("maximum_amount", "10"),
                            ActionGateConstraint("rate_limit", "5")))
    b = encode_constraints((ActionGateConstraint("rate_limit", "5"),
                            ActionGateConstraint("maximum_amount", "10")))
    assert set(a) == set(b)


def test_canonical_and_legacy_encodings_identical():
    import actiongate_provider.mapping as legacy
    import ugence_actiongate_provider.mapping as canon
    cs = (ActionGateConstraint("maximum_amount", "10"), ActionGateConstraint("x", "y"))
    obs = (ActionGateObligation("human_review"), ActionGateObligation("z", "w"))
    assert legacy.encode_constraints(cs) == canon.encode_constraints(cs)
    assert legacy.encode_obligations(obs) == canon.encode_obligations(obs)
