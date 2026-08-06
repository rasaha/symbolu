"""Fixture-only tests for the executable CLI and the fail-closed authorization-record schema.

Uses only fixture seeds (993000-993004). Never trains, evaluates, replays, generates a scientific
cohort, or consumes a reserved seed. The train/evaluate/replay subcommands are exercised only through
their authorization-refusal paths (which return before any model runs).
"""
from __future__ import annotations

import json
import os

import pytest

from experiments.unseen_identifier_copy_selection import cli
from experiments.unseen_identifier_copy_selection.cli import (
    EXIT_AUTH_REFUSED,
    EXIT_OK,
    _one_explicit_seed,
    build_parser,
    main,
)
from experiments.unseen_identifier_copy_selection.config import FIXTURE_SEEDS, RESERVED_SEEDS
from experiments.unseen_identifier_copy_selection.execution import (
    AuthorizationRecordError,
    FIXTURE_AUTHORIZATION_STATE,
    build_fixture_authorization_record,
    compute_record_digest,
    validate_authorization_record,
)

FS = FIXTURE_SEEDS[0]


def _write_record(tmp_path, record) -> str:
    path = os.path.join(tmp_path, "auth.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle)
    return path


# ---- CLI surface ---------------------------------------------------------

def test_parser_exposes_exactly_the_frozen_subcommands():
    parser = build_parser()
    # the subparsers action carries the frozen names
    actions = [a for a in parser._actions if hasattr(a, "choices") and a.choices]
    names = set()
    for a in actions:
        names |= set(a.choices)
    assert names == {"build-cohort", "shortcut-precheck", "train", "evaluate", "replay", "assemble-manifest"}


def test_help_builds_without_model_or_writes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["build-cohort", "--help"])
    assert exc.value.code == 0
    # --help wrote nothing to the cwd
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize("bad", ["9070,9071", "9070-9073", "90760:90764", "*", "?", "all", "dev", "final"])
def test_seed_contract_rejects_non_singleton(bad):
    with pytest.raises(Exception):
        _one_explicit_seed(bad)


def test_seed_contract_accepts_single_integer():
    assert _one_explicit_seed("993000") == 993000


def test_every_subcommand_requires_all_four_arguments():
    parser = build_parser()
    for name in ("build-cohort", "shortcut-precheck", "train", "evaluate", "replay", "assemble-manifest"):
        with pytest.raises(SystemExit):
            parser.parse_args([name, "--seed", "993000"])  # missing cohort/record/output-dir


# ---- authorization-record validation (fail-closed) -----------------------

def test_valid_fixture_record_round_trips():
    record = build_fixture_authorization_record(FS, "unseen")
    validate_authorization_record(record, seed=FS, cohort="unseen")  # must not raise


def test_reserved_seed_cannot_build_a_fixture_record():
    for seed in sorted(RESERVED_SEEDS):
        with pytest.raises(AuthorizationRecordError):
            build_fixture_authorization_record(seed, "unseen")


def test_forged_reserved_seed_record_fails_validation():
    record = build_fixture_authorization_record(FS, "unseen")
    forged = {**record, "permitted_seeds": [9070]}
    forged["record_digest"] = compute_record_digest(forged)
    with pytest.raises(AuthorizationRecordError):
        validate_authorization_record(forged, seed=9070, cohort="unseen")


def test_digest_tamper_rejected():
    record = build_fixture_authorization_record(FS, "unseen")
    tampered = {**record, "parameter_count": 1}  # digest no longer matches
    with pytest.raises(AuthorizationRecordError):
        validate_authorization_record(tampered, seed=FS, cohort="unseen")


def test_unknown_state_rejected():
    record = build_fixture_authorization_record(FS, "unseen")
    forged = {**record, "authorization_state": "SMOKE_EXECUTION"}
    forged["record_digest"] = compute_record_digest(forged)
    with pytest.raises(AuthorizationRecordError):
        validate_authorization_record(forged, seed=FS, cohort="unseen")


def test_wrong_cohort_and_wrong_seed_rejected():
    record = build_fixture_authorization_record(FS, "unseen")
    with pytest.raises(AuthorizationRecordError):
        validate_authorization_record(record, seed=FS, cohort="seen")
    with pytest.raises(AuthorizationRecordError):
        validate_authorization_record(record, seed=FIXTURE_SEEDS[1], cohort="unseen")


def test_missing_keys_rejected():
    record = build_fixture_authorization_record(FS, "unseen")
    incomplete = {k: v for k, v in record.items() if k != "model_recipe_hashes"}
    with pytest.raises(AuthorizationRecordError):
        validate_authorization_record(incomplete, seed=FS, cohort="unseen")


def test_all_four_states_recognized_only_fixture_usable_without_artifact():
    from experiments.unseen_identifier_copy_selection.execution import (
        DEVELOPMENT_EXECUTION_STATE,
        FINAL_EXECUTION_STATE,
        RECOGNIZED_STATES,
        SCIENTIFIC_STATES,
        SMOKE_EXECUTION_STATE,
    )
    assert RECOGNIZED_STATES == frozenset({
        FIXTURE_AUTHORIZATION_STATE, SMOKE_EXECUTION_STATE,
        DEVELOPMENT_EXECUTION_STATE, FINAL_EXECUTION_STATE,
    })
    assert SCIENTIFIC_STATES == frozenset({
        SMOKE_EXECUTION_STATE, DEVELOPMENT_EXECUTION_STATE, FINAL_EXECUTION_STATE,
    })
    # recognition is not activation: only the fixture state is usable with no approved artifact
    assert FIXTURE_AUTHORIZATION_STATE not in SCIENTIFIC_STATES


# ---- CLI end-to-end on fixture seeds (data only; no model) ----------------

def test_cli_build_cohort_writes_evidence_for_fixture_seed(tmp_path):
    record = build_fixture_authorization_record(FS, "unseen")
    record_path = _write_record(str(tmp_path), record)
    out = os.path.join(str(tmp_path), "out")
    code = main(["build-cohort", "--seed", str(FS), "--cohort", "unseen",
                 "--authorization-record", record_path, "--output-dir", out])
    assert code == EXIT_OK
    run_dir = os.path.join(out, str(FS), "unseen")
    assert os.path.exists(os.path.join(run_dir, "manifest.json"))
    assert not os.path.exists(os.path.join(run_dir, ".incomplete"))  # marker cleared on success


def test_cli_shortcut_precheck_runs_on_fixture_seed(tmp_path):
    record = build_fixture_authorization_record(FS, "unseen")
    record_path = _write_record(str(tmp_path), record)
    out = os.path.join(str(tmp_path), "out")
    code = main(["shortcut-precheck", "--seed", str(FS), "--cohort", "unseen",
                 "--authorization-record", record_path, "--output-dir", out])
    assert code in (cli.EXIT_OK, cli.EXIT_CONTRACT)  # pass/fail both terminate cleanly, no crash


def test_cli_train_refuses_reserved_seed_before_any_training(tmp_path):
    # A reserved seed is refused at authorization validation; training never begins (no torch run).
    record = build_fixture_authorization_record(FS, "unseen")
    forged = {**record, "permitted_seeds": [9070]}
    forged["record_digest"] = compute_record_digest(forged)
    record_path = _write_record(str(tmp_path), forged)
    out = os.path.join(str(tmp_path), "out")
    code = main(["train", "--seed", "9070", "--cohort", "unseen",
                 "--authorization-record", record_path, "--output-dir", out])
    assert code == EXIT_AUTH_REFUSED
    assert not os.path.exists(out)  # nothing generated


def test_cli_missing_record_file_is_auth_refused(tmp_path):
    out = os.path.join(str(tmp_path), "out")
    code = main(["build-cohort", "--seed", str(FS), "--cohort", "unseen",
                 "--authorization-record", os.path.join(str(tmp_path), "nope.json"),
                 "--output-dir", out])
    assert code == EXIT_AUTH_REFUSED


def _scientific_record_no_doc(seed=9070):
    from experiments.unseen_identifier_copy_selection.execution import SMOKE_EXECUTION_STATE
    from experiments.unseen_identifier_copy_selection.manifest import frozen_recipe_source_hashes
    record = {
        "authorization_state": SMOKE_EXECUTION_STATE, "cohort": "unseen", "permitted_seeds": [seed],
        "protocol_lock_commit": "PL", "implementation_authorization_commit": "a" * 40,
        "implementation_commit": "b" * 40, "model_recipe_hashes": frozen_recipe_source_hashes(),
        "parameter_count": 209_728, "scope": "one-run",
        "authorization_document_commit": "a" * 40,
        "authorization_document_path":
            "docs/research/hybrid_llm/benchmarks/UNSEEN_IDENTIFIER_EXECUTION_AUTHORIZATION.json",
        "authorization_document_digest": "c" * 64,
    }
    record["record_digest"] = compute_record_digest(record)
    return record


def test_cli_scientific_state_requires_committed_document_and_refuses_before_output(tmp_path):
    # A scientific record whose document is not committed in the real repo is refused, and refusal
    # occurs before the output directory is created (authorization precedes side effects).
    record_path = _write_record(str(tmp_path), _scientific_record_no_doc())
    out = os.path.join(str(tmp_path), "out")
    code = main(["build-cohort", "--seed", "9070", "--cohort", "unseen",
                 "--authorization-record", record_path, "--output-dir", out])
    assert code == EXIT_AUTH_REFUSED
    assert not os.path.exists(out)  # no output dir; no cohort generated


def test_cli_arbitrary_authority_ref_without_committed_doc_still_refused(tmp_path):
    # Even pointing --authority-ref/--repo-dir at the real repo, no committed authorization document
    # exists, so seed 9070 remains refused (present-day denial preserved).
    record_path = _write_record(str(tmp_path), _scientific_record_no_doc())
    out = os.path.join(str(tmp_path), "out")
    code = main(["build-cohort", "--seed", "9070", "--cohort", "unseen",
                 "--authorization-record", record_path, "--repo-dir", ".",
                 "--authority-ref", "HEAD", "--output-dir", out])
    assert code == EXIT_AUTH_REFUSED
    assert not os.path.exists(out)


def test_cli_one_seed_only_unchanged():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["build-cohort", "--seed", "9070,9071", "--cohort", "unseen",
                           "--authorization-record", "r.json", "--output-dir", "o"])
