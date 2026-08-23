"""Compatibility ratchet: the legacy consumer copy still matches this package.

This package is the **canonical owner** of the deterministic representation and
fingerprinting rules for Agent Constitution contracts (ADR §4, ratified owner
decision 2). There is one source of truth, and it is
``ugence_agent_constitution.serialization.canonical_json``.

``ugence_policy_workflow_compiler.serialization.canonical_json`` predates this
package and carries its own copy of the same semantics. That copy is a legacy
consumer implementation awaiting migration onto the published contract — not a
reference this package follows, and not a second authority. This module asserts, in
that direction, that the consumer copy still produces what this package produces, so
it cannot drift unnoticed before it is retired.

The direction is visible in the assertions themselves: this package's output is the
**expected** value and the consumer copy's is the **observed** one. A failure here
means the consumer copy is wrong, not that the question is open.

The compiler's module is loaded directly off disk by path. That exercises the file
without importing its distribution, so the ratchet adds nothing to this package's
dependency boundary.

Migrating the compiler onto the published contract and deleting this module is
follow-up work outside AC-0: it modifies another package.

The test skips when the compiler source is absent (an installed wheel, a partial
checkout). A skip means the consumer copy was not checked in that run. It says
nothing about this package's own canonicalization, which is authoritative regardless
and is gated independently by ``test_canonical_json.py``.
"""

from __future__ import annotations

import importlib.util
import pathlib

import fixtures
import pytest

from ugence_agent_constitution import ArtifactKind, dumps, dumps_pretty

#: The legacy consumer copy under migration. Named for what it is: not a reference,
#: not an authority, and not something this package defers to.
LEGACY_CONSUMER_COPY = (
    pathlib.Path(__file__).resolve().parents[4]
    / "tooling"
    / "policy-workflow-compiler"
    / "src"
    / "ugence_policy_workflow_compiler"
    / "serialization"
    / "canonical_json.py"
)


def _load_consumer_copy():
    if not LEGACY_CONSUMER_COPY.is_file():
        pytest.skip(f"legacy consumer copy not present at {LEGACY_CONSUMER_COPY}")
    spec = importlib.util.spec_from_file_location(
        "_legacy_consumer_canonical_json", LEGACY_CONSUMER_COPY
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _corpus():
    """Values chosen to hit every branch of the recursion, not just happy dicts."""
    return [
        fixtures.manifest(),
        fixtures.constitution(),
        fixtures.contract(),
        fixtures.subject(),
        fixtures.requirement(),
        ArtifactKind.AGENT_CONSTITUTION,
        {"z": 1, "a": {"n": None, "b": True}},
        {"set": {"b", "a", "c"}},
        {"frozen": frozenset({3, 1, 2})},
        {"tuple": (1, "two", 3.0)},
        [1, [2, [3, [4]]]],
        {"unicode": "Rückerstattung ✓", "empty": "", "zero": 0},
        {"nested_models": [fixtures.requirement(), fixtures.entry_ref()]},
        None,
        [],
        {},
    ]


def test_the_consumer_copy_still_reproduces_this_packages_compact_output():
    consumer = _load_consumer_copy()
    for value in _corpus():
        expected = dumps(value)  # this package: authoritative
        observed = consumer.dumps(value)  # legacy copy: under migration
        assert observed == expected, (
            f"legacy consumer copy has drifted from the canonical definition "
            f"on {value!r}; this package is correct by ratification (ADR §4)"
        )


def test_the_consumer_copy_still_reproduces_this_packages_pretty_output():
    consumer = _load_consumer_copy()
    for value in _corpus():
        expected = dumps_pretty(value)  # this package: authoritative
        observed = consumer.dumps_pretty(value)  # legacy copy: under migration
        assert observed == expected, (
            f"legacy consumer copy has drifted from the canonical definition "
            f"on {value!r}; this package is correct by ratification (ADR §4)"
        )


def test_the_consumer_copy_still_offers_the_surface_the_ratchet_compares():
    """Matching output is not enough if the copy's surface has moved underneath it."""
    consumer = _load_consumer_copy()
    for name in ("to_canonical_obj", "dumps", "dumps_pretty", "loads"):
        assert callable(getattr(consumer, name))


def test_this_packages_canonicalization_does_not_consult_the_consumer_copy():
    """Ownership is a runtime property, not only a docstring: this package's output
    must not depend on the legacy copy being present, loadable, or agreeing."""
    before = [dumps(v) for v in _corpus()]
    _load_consumer_copy()  # may skip; if it loads, it must not perturb anything
    after = [dumps(v) for v in _corpus()]
    assert before == after
