"""Fixture-only tests for the phase-scoped executable CLI.

Uses only fixture seeds (993000-993004). Never trains, evaluates, replays, generates a reserved
cohort, or consumes a reserved seed. Reserved subcommands are exercised only through their
protocol-refusal paths (which return before any model runs).
"""
from __future__ import annotations

import os

import pytest

from experiments.unseen_identifier_copy_selection import cli
from experiments.unseen_identifier_copy_selection.cli import (
    EXIT_OK,
    EXIT_PROTOCOL_REFUSED,
    _one_explicit_seed,
    build_parser,
    main,
)
from experiments.unseen_identifier_copy_selection.config import FIXTURE_SEEDS

FS = FIXTURE_SEEDS[0]


# ---- CLI surface ---------------------------------------------------------

def test_parser_exposes_exactly_the_frozen_subcommands():
    parser = build_parser()
    subaction = next(a for a in parser._subparsers._actions if a.choices and "build-cohort" in a.choices)
    assert set(subaction.choices) == {
        "build-cohort", "shortcut-precheck", "train", "evaluate", "replay", "assemble-manifest"}


def test_help_builds_without_model_or_writes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["build-cohort", "--help"])
    assert exc.value.code == 0
    assert os.listdir(tmp_path) == []  # --help wrote nothing


@pytest.mark.parametrize("bad", ["9070,9071", "9070-9073", "90760:90764", "*", "?", "all", "dev", "final"])
def test_seed_contract_rejects_non_singleton(bad):
    with pytest.raises(Exception):
        _one_explicit_seed(bad)


def test_seed_contract_accepts_single_integer():
    assert _one_explicit_seed("993000") == 993000


def test_every_subcommand_requires_phase_seed_cohort_output():
    parser = build_parser()
    for name in ("build-cohort", "shortcut-precheck", "train", "evaluate", "replay", "assemble-manifest"):
        with pytest.raises(SystemExit):
            parser.parse_args([name, "--seed", "993000"])  # missing --phase/--cohort/--output-dir
        with pytest.raises(SystemExit):
            parser.parse_args([name, "--phase", "fixture", "--seed", "993000", "--cohort", "unseen"])  # no output


def test_phase_choices_are_the_four_phases():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["build-cohort", "--phase", "bogus", "--seed", "993000",
                           "--cohort", "unseen", "--output-dir", "o"])


# ---- CLI end-to-end on the fixture phase (data only; no model) ------------

def test_cli_build_cohort_writes_evidence_for_fixture_phase(tmp_path):
    out = os.path.join(str(tmp_path), "out")
    code = main(["build-cohort", "--phase", "fixture", "--seed", str(FS), "--cohort", "unseen",
                 "--output-dir", out])
    assert code == EXIT_OK
    run_dir = os.path.join(out, str(FS), "unseen")
    assert os.path.exists(os.path.join(run_dir, "manifest.json"))
    assert not os.path.exists(os.path.join(run_dir, ".incomplete"))  # marker cleared on success


def test_cli_shortcut_precheck_runs_on_fixture_phase(tmp_path):
    out = os.path.join(str(tmp_path), "out")
    code = main(["shortcut-precheck", "--phase", "fixture", "--seed", str(FS), "--cohort", "unseen",
                 "--output-dir", out])
    assert code in (cli.EXIT_OK, cli.EXIT_CONTRACT)


# ---- protocol refusals (before any side effect) ---------------------------

def test_cli_reserved_seed_under_fixture_phase_refused(tmp_path):
    # cross-role: a reserved seed named under the fixture phase is refused before any generation.
    out = os.path.join(str(tmp_path), "out")
    code = main(["train", "--phase", "fixture", "--seed", "9070", "--cohort", "unseen",
                 "--output-dir", out])
    assert code == EXIT_PROTOCOL_REFUSED
    assert not os.path.exists(out)


def test_cli_fixture_seed_under_scientific_phase_refused(tmp_path):
    # cross-role the other way: a fixture seed named under a reserved phase is refused.
    out = os.path.join(str(tmp_path), "out")
    code = main(["build-cohort", "--phase", "smoke", "--seed", str(FS), "--cohort", "unseen",
                 "--output-dir", out])
    assert code == EXIT_PROTOCOL_REFUSED
    assert not os.path.exists(out)


def test_cli_final_seed_under_smoke_phase_refused(tmp_path):
    out = os.path.join(str(tmp_path), "out")
    code = main(["train", "--phase", "smoke", "--seed", "90760", "--cohort", "unseen",
                 "--output-dir", out])
    assert code == EXIT_PROTOCOL_REFUSED
    assert not os.path.exists(out)


def test_cli_reserved_seed_requires_explicit_phase_flag(tmp_path):
    # No --phase at all is an argparse error (phase is required); nothing runs.
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["build-cohort", "--seed", "9070", "--cohort", "unseen", "--output-dir", "o"])
