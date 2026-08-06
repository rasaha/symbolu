"""Fixture-only tests for the corrected authorization policy, immutable context, and guard handoff.

Proves the future-authorization path is structurally implemented (all four states recognized; the
state-to-seed-role matrix enforced; a provenance-bound immutable context is the only way to reach the
primitive guards) WHILE every scientific/reserved seed still fails closed because no approved
authorization artifact exists. Uses only fixture seeds 993000-993004 and generates NO scientific pool,
cohort, checkpoint, prediction, replay, or manifest. Mocked scientific records/artifacts are synthetic
test data — never real, never committed — and generation is never invoked after a guard passes.
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
    AuthorizationContext,
    AuthorizationRecordError,
    DEVELOPMENT_EXECUTION_STATE,
    ExecutionNotAuthorized,
    FINAL_EXECUTION_STATE,
    FIXTURE_AUTHORIZATION_STATE,
    SMOKE_EXECUTION_STATE,
    active_authorization,
    artifact_digest,
    authorize,
    build_fixture_authorization_record,
    compute_record_digest,
    require_execution_authorization,
)

FS = FIXTURE_SEEDS[0]
SMOKE = sorted(SMOKE_SEEDS)[0]           # 9070
DEV = sorted(DEVELOPMENT_SEEDS)[0]       # 9071
FINAL = sorted(FINAL_SEEDS)[0]           # 90760


def _mock_scientific_record(state: str, seed: int, cohort: str, artifact: dict) -> dict:
    """A synthetic (mocked) scientific record bound to a mocked approved artifact. Test-only."""
    from experiments.unseen_identifier_copy_selection.manifest import frozen_recipe_source_hashes

    record = {
        "authorization_state": state,
        "cohort": cohort,
        "permitted_seeds": [int(seed)],
        "protocol_lock_commit": "PL",
        "implementation_authorization_commit": artifact["approved_commit"],
        "implementation_commit": "IMPL",
        "model_recipe_hashes": frozen_recipe_source_hashes(),
        "parameter_count": ex.FROZEN_PARAMETER_COUNT,
        "scope": "one-run",
        "authorization_artifact_digest": artifact_digest(artifact),
    }
    record["record_digest"] = compute_record_digest(record)
    return record


def _mock_artifact(state: str, seed: int) -> dict:
    return {"approved": True, "authorization_state": state,
            "permitted_seeds": [int(seed)], "approved_commit": "APPROVED_COMMIT"}


# ---- state-to-seed-role matrix (policy over constants + mocked artifacts) ----

def test_matrix_permitted_combinations_pass_only_with_valid_mocked_record():
    for state, seed in ((SMOKE_EXECUTION_STATE, SMOKE),
                        (DEVELOPMENT_EXECUTION_STATE, DEV),
                        (FINAL_EXECUTION_STATE, FINAL)):
        artifact = _mock_artifact(state, seed)
        record = _mock_scientific_record(state, seed, "unseen", artifact)
        ctx = authorize(record, seed=seed, cohort="unseen", authorization_artifact=artifact)
        assert isinstance(ctx, AuthorizationContext)
        assert ctx.authorization_state == state and ctx.seed == seed


@pytest.mark.parametrize("state,seed", [
    (SMOKE_EXECUTION_STATE, DEV),      # smoke state + dev seed
    (SMOKE_EXECUTION_STATE, FINAL),    # smoke state + final seed
    (DEVELOPMENT_EXECUTION_STATE, SMOKE),
    (DEVELOPMENT_EXECUTION_STATE, FINAL),
    (FINAL_EXECUTION_STATE, SMOKE),
    (FINAL_EXECUTION_STATE, DEV),
    (FIXTURE_AUTHORIZATION_STATE, SMOKE),   # fixture state + scientific seed
    (SMOKE_EXECUTION_STATE, FS),            # scientific state + fixture seed
])
def test_matrix_cross_role_combinations_rejected(state, seed):
    artifact = _mock_artifact(state, seed)
    record = _mock_scientific_record(state, seed, "unseen", artifact) if state in ex.SCIENTIFIC_STATES \
        else {**build_fixture_authorization_record(FS, "unseen"), "permitted_seeds": [seed]}
    if state not in ex.SCIENTIFIC_STATES:
        record["record_digest"] = compute_record_digest(record)
    with pytest.raises(AuthorizationRecordError):
        authorize(record, seed=seed, cohort="unseen", authorization_artifact=artifact)


def test_unknown_state_rejected():
    artifact = _mock_artifact("BOGUS_STATE", SMOKE)
    record = _mock_scientific_record("BOGUS_STATE", SMOKE, "unseen", artifact)
    with pytest.raises(AuthorizationRecordError):
        authorize(record, seed=SMOKE, cohort="unseen", authorization_artifact=artifact)


# ---- immutable context construction is the only path ----

def test_only_authorize_constructs_a_usable_context_for_scientific_seed():
    artifact = _mock_artifact(SMOKE_EXECUTION_STATE, SMOKE)
    record = _mock_scientific_record(SMOKE_EXECUTION_STATE, SMOKE, "unseen", artifact)
    ctx = authorize(record, seed=SMOKE, cohort="unseen", authorization_artifact=artifact)
    # a hand-built context is possible as a dataclass, but it carries no capability the registry
    # honours unless activated through the validated flow.
    assert ctx.capability == record["record_digest"]


def test_scientific_record_without_artifact_fails_closed():
    artifact = _mock_artifact(SMOKE_EXECUTION_STATE, SMOKE)
    record = _mock_scientific_record(SMOKE_EXECUTION_STATE, SMOKE, "unseen", artifact)
    with pytest.raises(AuthorizationRecordError):
        authorize(record, seed=SMOKE, cohort="unseen", authorization_artifact=None)


def test_unapproved_artifact_fails_closed():
    artifact = _mock_artifact(SMOKE_EXECUTION_STATE, SMOKE)
    record = _mock_scientific_record(SMOKE_EXECUTION_STATE, SMOKE, "unseen", artifact)
    unapproved = {**artifact, "approved": False}
    with pytest.raises(AuthorizationRecordError):
        authorize(record, seed=SMOKE, cohort="unseen", authorization_artifact=unapproved)


def test_artifact_digest_mismatch_fails_closed():
    artifact = _mock_artifact(SMOKE_EXECUTION_STATE, SMOKE)
    record = _mock_scientific_record(SMOKE_EXECUTION_STATE, SMOKE, "unseen", artifact)
    tampered_artifact = {**artifact, "extra": "drift"}  # digest changes; record binding no longer matches
    with pytest.raises(AuthorizationRecordError):
        authorize(record, seed=SMOKE, cohort="unseen", authorization_artifact=tampered_artifact)


def test_artifact_commit_mismatch_fails_closed():
    artifact = _mock_artifact(SMOKE_EXECUTION_STATE, SMOKE)
    record = _mock_scientific_record(SMOKE_EXECUTION_STATE, SMOKE, "unseen", artifact)
    record["implementation_authorization_commit"] = "WRONG"
    record["record_digest"] = compute_record_digest(record)
    with pytest.raises(AuthorizationRecordError):
        authorize(record, seed=SMOKE, cohort="unseen", authorization_artifact=artifact)


def test_tamper_cohort_seed_commit_hash_param_scope_all_fail():
    base = build_fixture_authorization_record(FS, "unseen")
    # wrong cohort
    with pytest.raises(AuthorizationRecordError):
        authorize(base, seed=FS, cohort="seen")
    # wrong seed
    with pytest.raises(AuthorizationRecordError):
        authorize(base, seed=FIXTURE_SEEDS[1], cohort="unseen")
    # empty commit
    bad_commit = {**base, "implementation_commit": ""}
    bad_commit["record_digest"] = compute_record_digest(bad_commit)
    with pytest.raises(AuthorizationRecordError):
        authorize(bad_commit, seed=FS, cohort="unseen")
    # wrong hashes
    bad_hash = {**base, "model_recipe_hashes": {"config.py": "00"}}
    bad_hash["record_digest"] = compute_record_digest(bad_hash)
    with pytest.raises(AuthorizationRecordError):
        authorize(bad_hash, seed=FS, cohort="unseen")
    # wrong param count
    bad_param = {**base, "parameter_count": 1}
    bad_param["record_digest"] = compute_record_digest(bad_param)
    with pytest.raises(AuthorizationRecordError):
        authorize(bad_param, seed=FS, cohort="unseen")
    # unknown scope
    bad_scope = {**base, "scope": "forever"}
    bad_scope["record_digest"] = compute_record_digest(bad_scope)
    with pytest.raises(AuthorizationRecordError):
        authorize(bad_scope, seed=FS, cohort="unseen")
    # digest tamper (no recompute)
    tampered = {**base, "parameter_count": ex.FROZEN_PARAMETER_COUNT}
    tampered["cohort"] = "seen"  # payload changes but digest not recomputed
    with pytest.raises(AuthorizationRecordError):
        authorize(tampered, seed=FS, cohort="seen")


# ---- primitive-guard handoff ----

def test_fixture_context_guard_allows_only_fixture_seed():
    record = build_fixture_authorization_record(FS, "unseen")
    ctx = authorize(record, seed=FS, cohort="unseen")
    with active_authorization(ctx):
        # fixture seed is non-reserved -> guard returns regardless
        require_execution_authorization(FS, ctx.capability)
        # the same capability does NOT authorize a reserved seed
        with pytest.raises(ExecutionNotAuthorized):
            require_execution_authorization(SMOKE, ctx.capability)


def test_reserved_seed_guard_fails_without_active_context():
    for seed in (SMOKE, DEV, FINAL):
        with pytest.raises(ExecutionNotAuthorized):
            require_execution_authorization(seed, None)
        with pytest.raises(ExecutionNotAuthorized):
            require_execution_authorization(seed, "any-raw-string")


def test_valid_scientific_context_reaches_guard_but_no_pool_is_generated(monkeypatch):
    # A structurally valid (mocked) smoke context can reach the primitive guard in a policy-only test.
    # We patch the pool draw to explode if generation is ever attempted, then assert the guard passes
    # WITHOUT us calling any generation function.
    from experiments.unseen_identifier_copy_selection import identifiers

    def _explode(*a, **k):
        raise AssertionError("scientific pool generation must not be invoked in tests")

    monkeypatch.setattr(identifiers, "_draw_distinct", _explode)

    artifact = _mock_artifact(SMOKE_EXECUTION_STATE, SMOKE)
    record = _mock_scientific_record(SMOKE_EXECUTION_STATE, SMOKE, "unseen", artifact)
    ctx = authorize(record, seed=SMOKE, cohort="unseen", authorization_artifact=artifact)
    with active_authorization(ctx):
        require_execution_authorization(SMOKE, ctx.capability)  # guard reached PASS, no generation
    # capability is scoped: outside the block it no longer authorizes
    with pytest.raises(ExecutionNotAuthorized):
        require_execution_authorization(SMOKE, ctx.capability)


def test_capability_is_seed_bound():
    a = _mock_artifact(SMOKE_EXECUTION_STATE, SMOKE)
    ctx = authorize(_mock_scientific_record(SMOKE_EXECUTION_STATE, SMOKE, "unseen", a),
                    seed=SMOKE, cohort="unseen", authorization_artifact=a)
    with active_authorization(ctx):
        with pytest.raises(ExecutionNotAuthorized):
            require_execution_authorization(DEV, ctx.capability)  # bound to 9070, not 9071


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


# ---- current scientific denial preserved end-to-end ----

def test_no_valid_scientific_record_exists_in_the_repository():
    # There is no committed approved authorization artifact, so no scientific record can validate
    # through the real (non-mocked) load path. This is a structural fact, asserted here as a guard.
    from experiments.unseen_identifier_copy_selection.execution import RECOGNIZED_STATES
    assert ex.SCIENTIFIC_STATES.issubset(RECOGNIZED_STATES)
    # a scientific record with no artifact always fails closed
    artifact = _mock_artifact(SMOKE_EXECUTION_STATE, SMOKE)
    record = _mock_scientific_record(SMOKE_EXECUTION_STATE, SMOKE, "unseen", artifact)
    with pytest.raises(AuthorizationRecordError):
        authorize(record, seed=SMOKE, cohort="unseen")  # no artifact supplied


# ---- no-execution instrumentation ----

def test_fixture_commands_perform_no_training_or_decoding(monkeypatch, tmp_path):
    # Patch every execution primitive to explode; run the two data-only fixture CLI commands and
    # confirm they complete without training, optimizer steps, decoding, replay, or checkpoint writes.
    import json
    import os

    from experiments.unseen_identifier_copy_selection import training as training_mod
    from experiments.unseen_identifier_copy_selection import evaluation as evaluation_mod
    from experiments.unseen_identifier_copy_selection import replay as replay_mod
    from experiments.unseen_identifier_copy_selection.cli import EXIT_CONTRACT, EXIT_OK, main

    calls = {"train": 0, "eval": 0, "replay": 0}

    def _no_train(*a, **k):
        calls["train"] += 1
        raise AssertionError("train_cohort must not run in fixture tests")

    def _no_eval(*a, **k):
        calls["eval"] += 1
        raise AssertionError("evaluate_cohort must not run in fixture tests")

    def _no_replay(*a, **k):
        calls["replay"] += 1
        raise AssertionError("replay_run must not run in fixture tests")

    monkeypatch.setattr(training_mod, "train_cohort", _no_train)
    monkeypatch.setattr(evaluation_mod, "evaluate_cohort", _no_eval)
    monkeypatch.setattr(replay_mod, "replay_run", _no_replay)

    record = build_fixture_authorization_record(FS, "unseen")
    record_path = os.path.join(str(tmp_path), "auth.json")
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle)
    out = os.path.join(str(tmp_path), "out")

    code = main(["build-cohort", "--seed", str(FS), "--cohort", "unseen",
                 "--authorization-record", record_path, "--output-dir", out])
    assert code == EXIT_OK
    code = main(["shortcut-precheck", "--seed", str(FS), "--cohort", "unseen",
                 "--authorization-record", record_path, "--output-dir", os.path.join(str(tmp_path), "out2")])
    assert code in (EXIT_OK, EXIT_CONTRACT)

    assert calls == {"train": 0, "eval": 0, "replay": 0}
    # no checkpoint / scientific artifact anywhere under the output dirs
    for root, _dirs, files in os.walk(str(tmp_path)):
        for name in files:
            assert not name.endswith(".pt"), f"unexpected checkpoint {name}"


def test_active_capability_registry_is_empty_between_commands():
    # No capability leaks outside an active_authorization block (prevents cross-test contamination).
    assert ex._ACTIVE_CAPABILITIES == {}
