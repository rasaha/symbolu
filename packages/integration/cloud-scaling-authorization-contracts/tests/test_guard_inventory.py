"""The guard inventory this package's CI sweep is measured against.

Fast and static — no mutation runs here. What these properties defend is the *denominator*.
A sweep reporting "every guard killed" says nothing if the inventory quietly stopped listing
a guard, or if the shard arithmetic dropped one.

This package already records two inventories — the owner-ratified canonical 65 and the
peripheral 28 — over narrower scopes and a narrower shape than the sweep's. Reconciling them
here rather than in prose is the point: a count nobody can re-derive is a count nobody can
defend.
"""

from __future__ import annotations

import importlib
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts" / "cloud_scaling"))
guard_sweep = importlib.import_module("guard_sweep")

CONFIG = guard_sweep.PACKAGES["authorization-contracts"]
SHARDS = 8


@pytest.fixture(scope="module")
def guards():
    return guard_sweep.inventory(CONFIG)


def test_the_inventory_is_the_size_the_checked_in_report_records(guards):
    assert len(guards) == 109


def test_the_recorded_65_and_28_are_re_derived_and_agree(guards):
    """Both ratified counts, recomputed from source rather than trusted."""

    agreement = guard_sweep.reconcile(CONFIG, guards)
    assert agreement["canonical-65"]["measured"] == 65
    assert agreement["peripheral-28"]["measured"] == 28
    assert all(row["agrees"] for row in agreement.values())


def test_the_sweeps_definition_is_wider_than_the_ratified_ones_and_says_so(guards):
    """109 is not 65 + 28, and the difference is accounted for rather than waved at.

    The ratified inventories are defined over four of the six modules and over a narrower
    shape — a ``raise`` alone in the body of its enclosing ``if``. Everything else in this
    inventory is a guard those definitions were never meant to reach, not a guard that
    appeared from nowhere.
    """

    ratified_scope = {"reconciliation.py", "candidate.py", "attestation.py", "target.py"}
    outside_scope = [g for g in guards if g.module not in ratified_scope]
    wider_shape = [
        g for g in guards if g.module in ratified_scope and not g.recorded_in
    ]
    assert len(outside_scope) + len(wider_shape) == len(guards) - 65 - 28


def test_every_guard_belongs_to_exactly_one_shard(guards):
    """Assignment is disjoint and total, proved over the real inventory."""

    seen = set()
    for shard in range(1, SHARDS + 1):
        mine = {g.index for g in guards if guard_sweep.shard_of(g.index, SHARDS) == shard}
        assert not (seen & mine), f"shard {shard} overlaps an earlier shard"
        seen |= mine
    assert seen == {g.index for g in guards}, "some guard belongs to no shard"
