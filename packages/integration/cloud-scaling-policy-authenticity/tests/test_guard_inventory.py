"""The guard inventory this package's CI sweep is measured against.

Fast and static — no mutation runs here. What these properties defend is the *denominator*:
a sweep that reports "every guard killed" says nothing if the inventory quietly stopped
listing a guard, or if the shard arithmetic silently dropped one.
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest

from _policy_fixtures import _find_repo_root

REPO = _find_repo_root()
sys.path.insert(0, str(REPO / "scripts" / "cloud_scaling"))
guard_sweep = importlib.import_module("guard_sweep")

pytestmark = pytest.mark.skipif(
    os.environ.get("UGENCE_GUARD_SWEEP") == "1",
    reason=(
        "the gate-removal sweep runs this suite against a copy with one guard "
        "neutralised; these pins assert the guard count and the condition text of "
        "named guards, so inside that copy they would fail on the mutation itself "
        "and hand the sweep a kill its own test manufactured"
    ),
)

CONFIG = guard_sweep.PACKAGES["policy-authenticity"]
SHARDS = 8


@pytest.fixture(scope="module")
def guards():
    return guard_sweep.inventory(CONFIG)


@pytest.mark.invariant
def test_the_inventory_is_the_size_the_checked_in_report_records(guards):
    """A drifted denominator is the failure mode a sweep cannot see from inside itself."""

    assert len(guards) == 119


@pytest.mark.invariant
def test_every_guard_belongs_to_exactly_one_shard(guards):
    """Assignment is disjoint and total, proved over the real inventory, not the arithmetic."""

    seen = set()
    for shard in range(1, SHARDS + 1):
        mine = {g.index for g in guards if guard_sweep.shard_of(g.index, SHARDS) == shard}
        assert not (seen & mine), f"shard {shard} overlaps an earlier shard"
        seen |= mine
    assert seen == {g.index for g in guards}, "some guard belongs to no shard"


@pytest.mark.invariant
def test_every_refusal_shape_is_inventoried(guards):
    """Phase 5B refuses six ways, and a definition that knows one of them is not enough.

    The raise-only reading this package could have inherited from the Phase 5A sweep misses
    every one of the others — 49 of the 119 guards below, including gate 13's exact-type
    instant check and all six R-8 bound-reconciliation branches.

    ``raising-helper call`` was added after an audit found two guards no shape recognised:
    an ``if`` whose entire body is a call to an admission helper, with no ``raise`` and no
    ``return`` of its own. An ``if`` that *binds* such a call's result is a guard too — the
    conversion carve-out that said otherwise is withdrawn (ADR Phase 5 §9.1).

    ``returned outcome`` and ``outcome selection`` were added after a later audit found the
    two decision points in ``_terminal_outcome`` in neither inventory while the suite was
    killing them. Both are pinned by condition below: neutralised, the first turns a forged
    ``outcome`` attribute into ``VERIFIED``, and the second flattens every typed outcome to
    ``VERIFICATION_UNAVAILABLE``.
    """

    shapes = {g.shape for g in guards}
    assert shapes == {
        "raise",
        "typed-refusal call",
        "typed-refusal tuple",
        "raising-helper call",
        "returned outcome",
        "outcome selection",
    }
    assert sum(1 for g in guards if g.shape == "typed-refusal tuple") == 17
    assert sum(1 for g in guards if g.shape != "raise") == 49
    # Pinned by condition so a renumber cannot hide them.
    helper_calls = {(g.module, g.condition) for g in guards if g.shape == "raising-helper call"}
    assert helper_calls == {
        ("verified.py", "self.candidate_digest_fact is not None"),
        ("verification.py", "production_mode"),
    }
    terminal = {
        (g.module, g.lineno, g.shape)
        for g in guards
        if g.shape in {"returned outcome", "outcome selection"}
    }
    assert terminal == {
        ("verification.py", 1101, "outcome selection"),
        ("verification.py", 1102, "returned outcome"),
    }


#: Pinned by condition text rather than index, so adding a guard earlier in the file
#: renumbers the inventory without silently retargeting these assertions.
GATE_13_TYPING = ("verification.py", "type(value) is not datetime")
R8_BRANCHES = (
    ("verification.py", "not capacity_bounds"),
    ("verification.py", "type(action_type) is not str or action_type not in CANONICAL_ACTION_TYPES"),
    ("verification.py", "not matches"),
    ("verification.py", "len(matches) > 1"),
    ("verification.py", "type(carried) is not int or isinstance(carried, bool)"),
    ("verification.py", "carried > authenticated"),
)


def _find(guards, module, condition):
    return [g for g in guards if g.module == module and g.condition == condition]


@pytest.mark.invariant
def test_gate_13s_exact_type_check_is_inventoried_in_its_own_right(guards):
    """Not merely its call site.

    Gate 13 decides in ``_candidate_instant_type_problem`` and refuses at
    ``if mistyped is not None:``. Neutralising either disables it, so coverage is reachable
    from the call site alone — but an inventory listing only that never names the exact-type
    check, and a reader looking for the guard would not find it.
    """

    found = _find(guards, *GATE_13_TYPING)
    assert len(found) == 1, f"expected exactly one, found {[(g.index, g.lineno) for g in found]}"
    assert found[0].shape == "typed-refusal tuple"


@pytest.mark.invariant
@pytest.mark.parametrize("module, condition", R8_BRANCHES, ids=[c[1][:24] for c in R8_BRANCHES])
def test_each_r8_reconciliation_branch_is_inventoried_individually(guards, module, condition):
    """Six branches, six inventory entries — not one entry for the helper that holds them."""

    found = _find(guards, module, condition)
    assert len(found) == 1, f"expected exactly one, found {len(found)}"
    assert found[0].shape == "typed-refusal tuple"
