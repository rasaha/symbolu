"""This package's canonical JSON is identical *by value* to the compiler's.

The two modules are duplicated on purpose — this package is a leaf and must not
import ``ugence_policy_workflow_compiler`` — so the equivalence needs a gate
rather than a comment. The compiler's module is loaded directly off disk by path,
which exercises the file without importing its distribution: no package import,
no dependency, nothing added to this package's boundary.

The test skips when the compiler source is not present (an installed wheel, a
partial checkout). A skip here means the equivalence was not checked in that run,
not that it holds.
"""

from __future__ import annotations

import importlib.util
import pathlib

import fixtures
import pytest

from ugence_agent_constitution import ArtifactKind, dumps, dumps_pretty

REFERENCE = (
    pathlib.Path(__file__).resolve().parents[4]
    / "tooling"
    / "policy-workflow-compiler"
    / "src"
    / "ugence_policy_workflow_compiler"
    / "serialization"
    / "canonical_json.py"
)


def _load_reference():
    if not REFERENCE.is_file():
        pytest.skip(f"reference canonical_json not present at {REFERENCE}")
    spec = importlib.util.spec_from_file_location(
        "_reference_canonical_json", REFERENCE
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


def test_compact_encoding_is_byte_identical_to_the_reference():
    reference = _load_reference()
    for value in _corpus():
        assert dumps(value) == reference.dumps(value), value


def test_pretty_encoding_is_byte_identical_to_the_reference():
    reference = _load_reference()
    for value in _corpus():
        assert dumps_pretty(value) == reference.dumps_pretty(value), value


def test_the_public_function_names_match_the_reference():
    """Equivalence of output is not enough if the surface diverges."""
    reference = _load_reference()
    for name in ("to_canonical_obj", "dumps", "dumps_pretty", "loads"):
        assert callable(getattr(reference, name))
