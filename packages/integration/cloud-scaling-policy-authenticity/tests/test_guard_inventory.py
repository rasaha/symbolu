"""The guard inventory this package's CI sweep is measured against.

Fast and static — no mutation runs here. What these properties defend is the *denominator*:
a sweep that reports "every guard killed" says nothing if the inventory quietly stopped
listing a guard, or if the shard arithmetic silently dropped one.
"""

from __future__ import annotations

import importlib
import sys

import pytest

from _policy_fixtures import _find_repo_root

REPO = _find_repo_root()
sys.path.insert(0, str(REPO / "scripts" / "cloud_scaling"))
guard_sweep = importlib.import_module("guard_sweep")

CONFIG = guard_sweep.PACKAGES["policy-authenticity"]
SHARDS = 8


@pytest.fixture(scope="module")
def guards():
    return guard_sweep.inventory(CONFIG)


@pytest.mark.invariant
def test_the_inventory_is_the_size_the_checked_in_report_records(guards):
    """A drifted denominator is the failure mode a sweep cannot see from inside itself."""

    assert len(guards) == 115


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
def test_all_three_refusal_shapes_are_inventoried(guards):
    """Phase 5B refuses three ways, and a definition that knows one of them is not enough.

    The raise-only reading this package could have inherited from the Phase 5A sweep misses
    every ``typed-refusal tuple`` below — seventeen guards, including the two most recently
    added gates.
    """

    shapes = {g.shape for g in guards}
    assert shapes == {"raise", "typed-refusal call", "typed-refusal tuple"}
    assert sum(1 for g in guards if g.shape == "typed-refusal tuple") == 17


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
