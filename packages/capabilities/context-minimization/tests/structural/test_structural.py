"""Structural (Mode A) minimization tests — required scenarios 10–16."""

from __future__ import annotations

import ast
import pathlib

import ugence_context_minimization
from ugence_context_minimization.api import (
    EquivalenceStatus,
    MinimizationMode,
    deduplicate_context,
    structural_minimize,
)

from support import context, unit


def test_exact_unprotected_duplicate_removed():
    ctx = context([
        unit("a", "same text here"),
        unit("b", "same text here"),
        unit("c", "unique"),
    ])
    r = structural_minimize(ctx)
    assert set(r.surviving_ids) == {"a", "c"}
    assert r.removed_ids == ("b",)
    assert r.mode is MinimizationMode.STRUCTURAL


def test_redundancy_set_collapse_keeps_one_representative():
    ctx = context([
        unit("a", "backup verified", redundancy_set="r1"),
        unit("b", "backup ok, verified", redundancy_set="r1"),
        unit("c", "backup done (verified)", redundancy_set="r1"),
    ])
    r = structural_minimize(ctx)
    assert r.surviving_ids == ("a",)
    assert set(r.removed_ids) == {"b", "c"}


def test_deterministic_representative_is_first_in_order():
    ctx = context([unit("z", "dup"), unit("y", "dup"), unit("x", "dup")])
    r = structural_minimize(ctx)
    assert r.surviving_ids == ("z",)  # first in source order wins, deterministically


def test_protected_unit_never_removed_even_as_duplicate():
    # 'b' is a protected exact-duplicate of 'a'. It must survive; the UNPROTECTED
    # copy 'a' is the one that can be dropped.
    ctx = context([unit("a", "dup"), unit("b", "dup", protected=True)])
    r = structural_minimize(ctx, protected_ids=["b"])
    assert "b" in r.surviving_ids
    assert r.protected_ids == ("b",)


def test_original_context_unchanged():
    units = (unit("a", "dup"), unit("b", "dup"))
    ctx = context(units)
    structural_minimize(ctx)
    assert ctx.units == units  # immutable input untouched


def test_stable_result_ordering_and_fingerprint():
    ctx = context([unit("a", "x"), unit("b", "x"), unit("c", "y")])
    r1 = structural_minimize(ctx)
    r2 = structural_minimize(ctx)
    assert r1.surviving_ids == r2.surviving_ids
    assert r1.fingerprint == r2.fingerprint
    assert r1.equivalence_status is EquivalenceStatus.NOT_EVALUATED


def test_low_level_primitive_returns_ids():
    ctx = context([unit("a", "x"), unit("b", "x")])
    kept, removed = deduplicate_context(ctx)
    assert kept == ["a"] and removed == ["b"]


def test_structural_mode_imports_no_actiongate():
    """The structural code path must not reach ActionGate/experiment/model modules."""
    pkg_root = pathlib.Path(ugence_context_minimization.__file__).resolve().parent
    src = (pkg_root / "structural.py").read_text()
    roots = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and not (node.level or 0):
            if node.module:
                roots.add(node.module.split(".")[0])
    forbidden = {"action_gate_ref", "action_gateway", "actiongate_context_ablation",
                 "experiments", "torch", "transformers"}
    assert not (roots & forbidden), roots & forbidden
