"""Fixture-only tests for the authorization state policy, matrix, and fixture-context handoff.

These cover the structural policy that validates BEFORE any Git provenance check (state recognition,
the state-to-seed-role matrix, record tamper, cohort/seed/commit/hash/param/scope), plus the
fixture-context primitive-guard handoff and no-execution behavior. The Git-provenance and
forgery-resistance suite lives in test_authorization_security.py. Uses only fixture seeds
993000-993004 and generates no scientific pool, cohort, checkpoint, prediction, replay, or manifest.
"""
from __future__ import annotations

import pytest

from experiments.unseen_identifier_copy_selection import execution as ex
from experiments.unseen_identifier_copy_selection.config import (
    DEVELOPMENT_SEEDS,
    FINAL_SEEDS,
    FIXTURE_SEEDS,
    SMOKE_SEEDS,
)
from experiments.unseen_identifier_copy_selection.execution import (
    AuthorizationRecordError,
    DEVELOPMENT_EXECUTION_STATE,
    ExecutionNotAuthorized,
    FINAL_EXECUTION_STATE,
    FIXTURE_AUTHORIZATION_STATE,
    SMOKE_EXECUTION_STATE,
    active_authorization,
    authorize,
    build_fixture_authorization_record,
    compute_record_digest,
    require_execution_authorization,
)

FS = FIXTURE_SEEDS[0]
SMOKE = sorted(SMOKE_SEEDS)[0]
DEV = sorted(DEVELOPMENT_SEEDS)[0]
FINAL = sorted(FINAL_SEEDS)[0]


def _fixture_state_record_with_seed(seed: int) -> dict:
    """A fixture-STATE record whose permitted seed is `seed` (used for cross-role rejection tests)."""
    record = {**build_fixture_authorization_record(FS, "unseen"), "permitted_seeds": [seed]}
    record["record_digest"] = compute_record_digest(record)
    return record


# ---- states + matrix (validated before any Git access) ----

def test_all_four_states_recognized_only_fixture_non_scientific():
    from experiments.unseen_identifier_copy_selection.execution import RECOGNIZED_STATES, SCIENTIFIC_STATES
    assert RECOGNIZED_STATES == frozenset({
        FIXTURE_AUTHORIZATION_STATE, SMOKE_EXECUTION_STATE,
        DEVELOPMENT_EXECUTION_STATE, FINAL_EXECUTION_STATE,
    })
    assert SCIENTIFIC_STATES == frozenset({
        SMOKE_EXECUTION_STATE, DEVELOPMENT_EXECUTION_STATE, FINAL_EXECUTION_STATE,
    })
    assert FIXTURE_AUTHORIZATION_STATE not in SCIENTIFIC_STATES


@pytest.mark.parametrize("seed", [SMOKE, DEV, FINAL])
def test_fixture_state_plus_scientific_seed_rejected_before_git(seed):
    # cross-role: fixture state may bind only fixture seeds; fails at the matrix, no Git needed
    record = _fixture_state_record_with_seed(seed)
    with pytest.raises(AuthorizationRecordError):
        authorize(record, seed=seed, cohort="unseen")


def test_valid_fixture_record_round_trips():
    record = build_fixture_authorization_record(FS, "unseen")
    authorize(record, seed=FS, cohort="unseen")  # must not raise (no Git required for fixtures)


def test_tamper_cohort_seed_commit_hash_param_scope_all_fail():
    base = build_fixture_authorization_record(FS, "unseen")
    with pytest.raises(AuthorizationRecordError):
        authorize(base, seed=FS, cohort="seen")               # wrong cohort
    with pytest.raises(AuthorizationRecordError):
        authorize(base, seed=FIXTURE_SEEDS[1], cohort="unseen")  # wrong seed
    for mutate in (
        {"implementation_commit": ""},
        {"model_recipe_hashes": {"config.py": "00"}},
        {"parameter_count": 1},
        {"scope": "forever"},
    ):
        bad = {**base, **mutate}
        bad["record_digest"] = compute_record_digest(bad)
        with pytest.raises(AuthorizationRecordError):
            authorize(bad, seed=FS, cohort="unseen")
    # digest tamper without recompute
    tampered = {**base, "cohort": "seen"}
    with pytest.raises(AuthorizationRecordError):
        authorize(tampered, seed=FS, cohort="seen")


def test_unknown_state_rejected_before_git():
    bad = {**build_fixture_authorization_record(FS, "unseen"), "authorization_state": "BOGUS"}
    bad["record_digest"] = compute_record_digest(bad)
    with pytest.raises(AuthorizationRecordError):
        authorize(bad, seed=FS, cohort="unseen")


# ---- fixture-context primitive-guard handoff ----

def test_fixture_context_guard_allows_only_fixture_seed():
    ctx = authorize(build_fixture_authorization_record(FS, "unseen"), seed=FS, cohort="unseen")
    with active_authorization(ctx):
        require_execution_authorization(FS, ctx.capability)          # fixture seed ungated
        with pytest.raises(ExecutionNotAuthorized):
            require_execution_authorization(SMOKE, ctx.capability)   # cannot authorize a reserved seed


def test_reserved_seed_guard_fails_without_active_context():
    for seed in (SMOKE, DEV, FINAL):
        with pytest.raises(ExecutionNotAuthorized):
            require_execution_authorization(seed, None)
        with pytest.raises(ExecutionNotAuthorized):
            require_execution_authorization(seed, "any-raw-string")


def test_direct_primitive_calls_cannot_bypass_guard():
    from experiments.unseen_identifier_copy_selection.identifiers import build_pools, generate_pool
    from experiments.unseen_identifier_copy_selection.tasks import generate_split
    for seed in (SMOKE, DEV, FINAL):
        with pytest.raises(ExecutionNotAuthorized):
            generate_split("C2", "unseen", seed, n=2)
        with pytest.raises(ExecutionNotAuthorized):
            build_pools(seed)
        with pytest.raises(ExecutionNotAuthorized):
            generate_pool(seed, "train", 8)


def test_no_scientific_document_exists_so_scientific_authorize_fails_closed(tmp_path):
    # A scientific record validated against the REAL repository has no committed authorization
    # document, so it fails closed. (Uses the real repo via default cwd.)
    from experiments.unseen_identifier_copy_selection.manifest import frozen_recipe_source_hashes
    record = {
        "authorization_state": SMOKE_EXECUTION_STATE, "cohort": "unseen", "permitted_seeds": [SMOKE],
        "protocol_lock_commit": "PL", "implementation_authorization_commit": "a" * 40,
        "implementation_commit": "b" * 40, "model_recipe_hashes": frozen_recipe_source_hashes(),
        "parameter_count": ex.FROZEN_PARAMETER_COUNT, "scope": "one-run",
        "authorization_document_commit": "a" * 40,
        "authorization_document_path":
            "docs/research/hybrid_llm/benchmarks/UNSEEN_IDENTIFIER_EXECUTION_AUTHORIZATION.json",
        "authorization_document_digest": "c" * 64,
    }
    record["record_digest"] = compute_record_digest(record)
    with pytest.raises(AuthorizationRecordError):
        authorize(record, seed=SMOKE, cohort="unseen")


def test_active_capability_registry_empty_between_operations():
    assert ex._ACTIVE_CAPABILITIES == {}
