"""No security decision in this package is made by Python truthiness.

Closure-audit findings **F-04** and **F-05** were both instances of one defect:
the re-verifier decided whether to check a coordinate by asking whether the
caller's expected value was *truthy*. ``None`` skipped the check. So did ``""``.
So did ``0``, ``False``, and an empty tuple. A caller who passed nothing got the
same ``verified is True`` object as one who passed everything, and the
difference between "this matches my tenant" and "I never said which tenant"
was invisible in the result.

The structural correction is that a check is never conditional on a value's
emptiness. Either a coordinate is required — in which case it is validated at
construction and compared unconditionally — or the question is a different
question, with its own operation and its own result type.

This module is the standing guard on that property. It is deliberately a
*structural* test rather than a behavioural one: behavioural tests prove the
gates that exist today are unconditional, and this proves a new one cannot
quietly be written the old way.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest
import ugence_trusted_evidence_authority

PKG_ROOT = pathlib.Path(ugence_trusted_evidence_authority.__file__).resolve().parent
AUTHORITY_ROOT = PKG_ROOT / "authority"


def _sources(root: pathlib.Path):
    return sorted(root.rglob("*.py"))


def _parse(path: pathlib.Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_explicit_test(node: ast.AST) -> bool:
    """True when a condition states *what* it is testing, not merely truthiness.

    Explicit means a comparison (``is``, ``is not``, ``==``, ``!=``, ``<`` …),
    the negation of one, a call that returns a documented boolean, or a boolean
    combination of those. A bare name, attribute or subscript is **not**
    explicit: it asks "is this value truthy", which is the question that
    conflates absent, empty, zero and false.
    """

    if isinstance(node, (ast.Compare, ast.Call, ast.Constant)):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _is_explicit_test(node.operand)
    if isinstance(node, ast.BoolOp):
        return all(_is_explicit_test(value) for value in node.values)
    return False


@pytest.mark.parametrize("path", _sources(AUTHORITY_ROOT), ids=lambda p: p.name)
def test_no_condition_in_the_authority_layer_tests_bare_truthiness(path):
    """Every branch in the authority layer says what it is asking."""

    offenders = []
    for node in ast.walk(_parse(path)):
        if isinstance(node, (ast.If, ast.IfExp, ast.While)):
            if not _is_explicit_test(node.test):
                offenders.append((node.lineno, ast.dump(node.test)[:90]))
    assert not offenders, (path.name, offenders)


@pytest.mark.parametrize("path", _sources(PKG_ROOT), ids=lambda p: p.name)
def test_no_or_default_anywhere_in_the_package(path):
    """``x = a or b`` silently substitutes ``b`` for every falsy ``a``.

    That is the same defect as a truthiness gate wearing a different shape: an
    empty tenant id, a zero, or a ``False`` becomes the default and nobody sees
    it happen. Where a default is genuinely wanted the code must say
    ``b if a is None else a``, which distinguishes absent from empty.
    """

    offenders = []
    for node in ast.walk(_parse(path)):
        if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
            continue
        if not all(_is_explicit_test(value) for value in node.values):
            offenders.append((node.lineno, ast.dump(node)[:120]))
    assert not offenders, (path.name, offenders)


@pytest.mark.parametrize("path", _sources(PKG_ROOT), ids=lambda p: p.name)
def test_no_mapping_get_supplies_a_silent_default(path):
    """``d.get(k, fallback)`` hides a missing key behind a value.

    A bare ``d.get(k)`` is permitted only when the result is compared against
    ``None`` explicitly — which the truthiness test above already enforces —
    but a two-argument ``get`` substitutes without any comparison at all.
    """

    offenders = []
    for node in ast.walk(_parse(path)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and len(node.args) > 1
        ):
            offenders.append(node.lineno)
    assert not offenders, (path.name, offenders)


def test_the_scope_comparison_loop_has_no_condition_but_the_comparison():
    """The exact code path F-04/F-05 lived in, pinned structurally.

    Nine coordinates, one unconditional loop, one comparison. Nothing to skip.
    """

    path = AUTHORITY_ROOT / "reverification.py"
    verify_bound = None
    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.FunctionDef) and node.name == "verify_bound":
            verify_bound = node
    assert verify_bound is not None

    loops = [n for n in ast.walk(verify_bound) if isinstance(n, ast.For)]
    assert len(loops) == 1, "verify_bound compares in exactly one loop"
    loop = loops[0]

    # The loop iterates the declared coordinate list itself, so it cannot fall
    # out of step with what the expectation requires.
    assert isinstance(loop.iter, ast.Attribute)
    assert loop.iter.attr == "REQUIRED_COORDINATES"

    # Its body is a single comparison and a single refusal. No guard clause,
    # no `continue`, no membership test against a caller-supplied subset.
    conditions = [n for n in ast.walk(loop) if isinstance(n, ast.If)]
    assert len(conditions) == 1
    assert isinstance(conditions[0].test, ast.Compare)
    assert not any(isinstance(n, ast.Continue) for n in ast.walk(loop))


def test_the_expectation_declares_every_coordinate_as_required():
    """There is no optional coordinate for a loop to have to skip."""

    from ugence_trusted_evidence_authority.api import ReceiptScopeExpectation

    declared = [f.name for f in dataclasses.fields(ReceiptScopeExpectation)]
    assert set(declared) == set(ReceiptScopeExpectation.REQUIRED_COORDINATES)
    # And not one of them carries a default, so none can be omitted.
    for field in dataclasses.fields(ReceiptScopeExpectation):
        assert field.default is dataclasses.MISSING, field.name
        assert field.default_factory is dataclasses.MISSING, field.name
