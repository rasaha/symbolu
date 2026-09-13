"""Ruling 7, recorded as an inertness condition rather than as invented behaviour.

The owner's ruling: *"The absence of mapping content creates no new GERL routing or
refusal result in Stage 1 because Stage 1 has no classifier, closure verifier, resolver
consumer, admission boundary or executor. Record this as an inertness condition, not as
invented runtime behaviour."*

That is a claim about what this package **does not introduce**, so it is asserted the
only way such a claim can be: over the package's whole surface, showing there is no
refusal code, no routing outcome and no result type anywhere in it. What the artifact
raises are Python exceptions at construction time, inside a contract package that
executes nothing.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import _change_effect_policy_fixtures as fx
import ugence_change_effect_policy as pkg
from ugence_change_effect_policy import (
    ChangeEffectPolicyError,
    DelegationEntryRefused,
    MappingCoordinateRefused,
    OperativeWithoutMappingRefused,
)

SRC = pathlib.Path(pkg.__file__).resolve().parent
MODULES = sorted(SRC.glob("*.py"))


def test_the_package_declares_no_refusal_code_register() -> None:
    """No code table, so nothing here can be quoted as a GERL refusal result.

    The rule's refusal register is a closed, classified set of codes owned elsewhere.
    A code defined here would be a new member of it in all but name.
    """

    offenders = [
        name
        for name in dir(pkg)
        if not name.startswith("_")
        and any(word in name.lower() for word in ("refusal_code", "refusal_register",
                                                  "routing_result", "route_result",
                                                  "outcome", "disposition"))
    ]
    assert offenders == [], f"a refusal or routing register exists: {offenders}"


def test_no_exception_carries_a_refusal_code() -> None:
    """The refusals are typed exceptions, not coded governance results.

    An exception carrying a ``code`` would be a refusal result wearing an exception's
    clothes, and a consumer could route on it.
    """

    for error_type in (
        DelegationEntryRefused,
        MappingCoordinateRefused,
        OperativeWithoutMappingRefused,
    ):
        raised = None
        try:
            if error_type is DelegationEntryRefused:
                fx.policy(delegation_table=("anything",))
            elif error_type is MappingCoordinateRefused:
                fx.policy(mapping_coordinate=fx.mapping_coordinate(policy_id="TBD"))
            else:
                fx.policy(metadata=fx.metadata(lifecycle_state=pkg.ACTIVE_LIFECYCLE_STATE))
        except error_type as exc:
            raised = exc
        assert raised is not None, error_type.__name__
        for attribute in ("code", "refusal_code", "result", "outcome", "route",
                          "disposition", "classification"):
            assert not hasattr(raised, attribute), f"{error_type.__name__}.{attribute}"


def test_every_refusal_is_raised_at_construction_and_nowhere_else() -> None:
    """A construction-time type refusal, not a runtime decision on a change.

    Every ``raise`` in the package sits inside ``__post_init__``, a field validator it
    calls, or the adapter's own shape checks — and never inside anything that takes a
    change, a record or a caller. There is no evaluation path for a refusal to be a
    decision *about* anything.
    """

    raising_functions = set()
    for path, tree in (
        (p, ast.parse(p.read_text(encoding="utf-8"))) for p in MODULES
    ):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(isinstance(inner, ast.Raise) for inner in ast.walk(node)):
                    raising_functions.add(node.name)
    assert raising_functions == {
        "__post_init__",
        "_require_str",
        "_require_digest",
        "_require_tzaware",
        "_refuse_sentinel_coordinate",
        "change_effect_coordinate",
        "describe",
        "_canonical_projection",
    }


def test_every_refusal_shares_one_base_so_none_is_mistaken_for_a_result() -> None:
    for error_type in (
        DelegationEntryRefused,
        MappingCoordinateRefused,
        OperativeWithoutMappingRefused,
        pkg.ChangeEffectPolicyFieldError,
    ):
        assert issubclass(error_type, ChangeEffectPolicyError)
        assert issubclass(error_type, Exception)


def test_the_absence_of_mapping_content_is_not_observable_as_a_result() -> None:
    """The inertness condition itself.

    The initial shipped artifact has no mapping coordinate, and therefore no mapping
    content behind one. Nothing in the package reports that as a routing outcome, a
    refusal code or a classification: the only observable consequence is that
    ``is_operative`` is ``False`` and the artifact cannot enter the operative lifecycle
    state. There is no classifier, closure verifier, resolver consumer, admission
    boundary or executor here for it to be a result *to*.
    """

    artifact = fx.policy()
    assert artifact.mapping_coordinate is None
    assert artifact.is_operative is False

    # And the artifact still describes cleanly: absence is a lawful state, not an error.
    descriptor = pkg.ChangeEffectPolicyFamilyAdapter().describe(artifact)
    assert descriptor.lifecycle_is_active is False
    assert descriptor.canonical_projection["mapping_coordinate"] is None


def test_promoting_a_mapping_less_artifact_is_the_only_thing_absence_forecloses() -> None:
    with pytest.raises(OperativeWithoutMappingRefused):
        fx.policy(metadata=fx.metadata(lifecycle_state=pkg.ACTIVE_LIFECYCLE_STATE))
