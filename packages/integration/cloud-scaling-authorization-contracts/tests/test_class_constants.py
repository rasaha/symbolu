"""F-4: annotated class constants must not become dataclass fields.

`Final` alone does **not** make a name a class variable. A bare
``_ALLOWED_KEYS: Final[frozenset[str]] = frozenset(...)`` inside a dataclass body is a
real **field**: it appears in ``dataclasses.fields()``, becomes a constructor keyword,
joins ``__eq__`` and travels through ``dataclasses.replace()``. A caller could then hand a
validator its own key set.

The audit named two such constants. A sweep of the whole package found **four**, across
three classes. All are now ``ClassVar``, which is what actually excludes a name from the
field list. These tests keep it that way, and — more importantly — the sweep below fails on
*any* future ``Final``-annotated name inside *any* dataclass in the package, so the same
mistake cannot reappear under a different name.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import pathlib

import pytest

from ugence_cloud_scaling_authorization_contracts import (
    CapacityAuthorizationCandidate,
    ExecutionTargetScope,
    PolicyTargetBindingReference,
    ProducerAttestationEvidence,
)
from ugence_cloud_scaling_authorization_contracts import candidate as candidate_module

SRC = pathlib.Path(candidate_module.__file__).resolve().parent
SOURCES = sorted(SRC.rglob("*.py"))

DATACLASSES = (
    ProducerAttestationEvidence,
    ExecutionTargetScope,
    PolicyTargetBindingReference,
    CapacityAuthorizationCandidate,
)

#: The class constants that must remain reachable as constants while never being fields.
EXPECTED_CLASS_CONSTANTS = {
    ProducerAttestationEvidence: ("_ALLOWED_KEYS",),
    ExecutionTargetScope: ("_ALLOWED_KEYS", "_REQUIRED_KEYS"),
    PolicyTargetBindingReference: ("_ALLOWED_KEYS",),
}


@pytest.mark.parametrize("cls", DATACLASSES, ids=lambda c: c.__name__)
def test_no_private_constant_is_a_dataclass_field(cls):
    leaked = [f.name for f in dataclasses.fields(cls) if f.name.startswith("_")]
    assert not leaked, f"{cls.__name__} exposes class constants as fields: {leaked}"


@pytest.mark.parametrize("cls", DATACLASSES, ids=lambda c: c.__name__)
def test_no_private_constant_is_a_constructor_parameter(cls):
    leaked = [p for p in inspect.signature(cls).parameters if p.startswith("_")]
    assert not leaked, f"{cls.__name__} accepts class constants as keywords: {leaked}"


@pytest.mark.parametrize("cls,names", EXPECTED_CLASS_CONSTANTS.items(), ids=lambda v: getattr(v, "__name__", ""))
def test_callers_cannot_pass_a_constant_as_a_keyword(cls, names):
    """The concrete consequence: a caller cannot substitute a validator's key set."""

    for name in names:
        with pytest.raises(TypeError):
            cls(**{name: frozenset({"anything"})})


@pytest.mark.parametrize("cls,names", EXPECTED_CLASS_CONSTANTS.items(), ids=lambda v: getattr(v, "__name__", ""))
def test_the_constants_remain_reachable_as_class_constants(cls, names):
    """Excluding them from the fields must not remove them from the class."""

    for name in names:
        value = getattr(cls, name)
        assert isinstance(value, frozenset) and value, f"{cls.__name__}.{name} is unusable"


@pytest.mark.parametrize("cls,names", EXPECTED_CLASS_CONSTANTS.items(), ids=lambda v: getattr(v, "__name__", ""))
def test_constants_are_not_shared_mutable_state(cls, names):
    """``frozenset`` — a shared *mutable* class attribute would be a worse bug."""

    for name in names:
        assert isinstance(getattr(cls, name), frozenset)
        with pytest.raises(AttributeError):
            getattr(cls, name).add("mutated")  # type: ignore[attr-defined]


def test_no_serializer_emits_a_class_constant(candidate):
    """Constants must not reach the canonical form, and therefore not the digest."""

    def _walk(value):
        if isinstance(value, dict):
            for k, v in value.items():
                yield k
                yield from _walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                yield from _walk(v)

    for obj in (
        candidate,
        candidate.target_scope,
        candidate.policy_binding,
        candidate.producer_attestation,
    ):
        keys = list(_walk(obj.to_canonical_dict()))
        assert not [k for k in keys if isinstance(k, str) and k.startswith("_")], (
            f"{type(obj).__name__} serializes a private class constant"
        )
    # And the digest payload likewise.
    assert not [k for k in candidate.digest_payload() if k.startswith("_")]


def test_no_dataclass_in_the_package_annotates_a_field_as_Final():
    """The durable guard: sweep every dataclass in the distribution, not only the four.

    This is what catches the *next* occurrence. ``Final`` inside a dataclass body is always
    the bug; ``ClassVar`` is always the fix.
    """

    offenders = []
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            decorated = any(
                (isinstance(d, ast.Call) and getattr(d.func, "id", "") == "dataclass")
                or getattr(d, "id", "") == "dataclass"
                for d in node.decorator_list
            )
            if not decorated:
                continue
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign):
                    annotation = ast.unparse(stmt.annotation)
                    if annotation.startswith("Final") or annotation.startswith("typing.Final"):
                        offenders.append(
                            f"{path.name}:{stmt.lineno} {node.name}.{ast.unparse(stmt.target)}"
                        )
    assert not offenders, (
        "Final inside a dataclass body creates a real field, not a class constant; "
        f"use ClassVar instead: {offenders}"
    )
