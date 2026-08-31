"""Fixture-only tests for the lightweight experimental-phase protocol guards.

Verifies the retained protocol boundaries — explicit phase, exact seed-role validation, no implicit
or cross-role reserved runs, and the primitive-level guard threaded through the data generators.
Uses only fixture seeds (993000-993004); generates no reserved cohort and consumes no reserved seed.
"""
from __future__ import annotations

import pytest

from experiments.unseen_identifier_copy_selection.config import (
    DEVELOPMENT_SEEDS,
    FINAL_SEEDS,
    FIXTURE_SEEDS,
    RESERVED_SEEDS,
    SMOKE_SEEDS,
)
from experiments.unseen_identifier_copy_selection.execution import (
    PHASES,
    PHASE_SEEDS,
    ExecutionNotAuthorized,
    phase_for_seed,
    require_execution_authorization,
    validate_phase_seed,
)

FS = FIXTURE_SEEDS[0]
SMOKE = sorted(SMOKE_SEEDS)[0]
DEV = sorted(DEVELOPMENT_SEEDS)[0]
FINAL = sorted(FINAL_SEEDS)[0]


def test_phases_and_seed_sets_are_exact():
    assert PHASES == ("fixture", "smoke", "development", "final")
    assert PHASE_SEEDS["fixture"] == frozenset(FIXTURE_SEEDS)
    assert PHASE_SEEDS["smoke"] == frozenset(SMOKE_SEEDS)
    assert PHASE_SEEDS["development"] == frozenset(DEVELOPMENT_SEEDS)
    assert PHASE_SEEDS["final"] == frozenset(FINAL_SEEDS)
    # the four seed sets are pairwise disjoint
    sets = list(PHASE_SEEDS.values())
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            assert sets[i].isdisjoint(sets[j])


def test_phase_for_seed():
    assert phase_for_seed(FS) == "fixture"
    assert phase_for_seed(SMOKE) == "smoke"
    assert phase_for_seed(DEV) == "development"
    assert phase_for_seed(FINAL) == "final"
    assert phase_for_seed(12345) is None


def test_validate_phase_seed_accepts_exact_role():
    validate_phase_seed("fixture", FS)
    validate_phase_seed("smoke", SMOKE)
    validate_phase_seed("development", DEV)
    validate_phase_seed("final", FINAL)


@pytest.mark.parametrize("phase,seed", [
    ("fixture", SMOKE), ("fixture", FINAL),
    ("smoke", DEV), ("smoke", FINAL), ("smoke", FS),
    ("development", SMOKE), ("development", FINAL),
    ("final", SMOKE), ("final", DEV), ("final", FS),
])
def test_validate_phase_seed_rejects_cross_role(phase, seed):
    with pytest.raises(ExecutionNotAuthorized):
        validate_phase_seed(phase, seed)


def test_unknown_phase_rejected():
    with pytest.raises(ExecutionNotAuthorized):
        validate_phase_seed("staging", FS)


def test_primitive_guard_fixture_ungated():
    require_execution_authorization(FS)              # no phase needed for fixtures
    require_execution_authorization(FS, "fixture")


@pytest.mark.parametrize("seed,role", [(SMOKE, "smoke"), (DEV, "development"), (FINAL, "final")])
def test_primitive_guard_reserved_requires_matching_phase(seed, role):
    # no phase / wrong phase -> refused; exact role phase -> allowed
    with pytest.raises(ExecutionNotAuthorized):
        require_execution_authorization(seed, None)
    with pytest.raises(ExecutionNotAuthorized):
        require_execution_authorization(seed, "fixture")
    wrong = "development" if role != "development" else "smoke"
    with pytest.raises(ExecutionNotAuthorized):
        require_execution_authorization(seed, wrong)
    require_execution_authorization(seed, role)      # matching phase authorizes the primitive


def test_reserved_seeds_never_run_without_phase_via_build_cohort():
    from experiments.unseen_identifier_copy_selection.runner import build_cohort
    for seed in sorted(RESERVED_SEEDS):
        with pytest.raises(ExecutionNotAuthorized):
            build_cohort(seed, "unseen")            # no phase -> refused


def test_direct_primitive_calls_still_fail_closed_for_reserved_seeds():
    from experiments.unseen_identifier_copy_selection.identifiers import build_pools, generate_pool
    from experiments.unseen_identifier_copy_selection.tasks import generate_split
    for seed in sorted(RESERVED_SEEDS):
        with pytest.raises(ExecutionNotAuthorized):
            generate_split("C2", "unseen", seed, n=2)
        with pytest.raises(ExecutionNotAuthorized):
            build_pools(seed)
        with pytest.raises(ExecutionNotAuthorized):
            generate_pool(seed, "train", 8)
    # fixture seed remains ungated
    build_pools(FS)
