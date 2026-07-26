"""H6 — product package: config, version, composition, demo, accountability, CLI."""

from __future__ import annotations

import json

import pytest

from ai_hiring import product as P
from ai_hiring.product.config import (
    ExecutionMode,
    InvalidConfigValueError,
    UnknownConfigKeyError,
    UnsupportedExecutionModeError,
)


# --- version (pre-1.0) ------------------------------------------------------
def test_version_is_pre_1_0_and_not_production_certified():
    info = P.version_info()
    assert info.product_version.startswith("0.")  # pre-1.0
    assert info.production_certified is False
    assert P.PLATFORM_BASELINE == "v1.0"


# --- config: fail-closed ----------------------------------------------------
def test_defaults_are_valid_and_deterministic():
    cfg = P.ProductConfig()
    assert cfg.execution_mode is ExecutionMode.DETERMINISTIC_SIMULATION
    assert cfg.redact_pii is True


def test_unknown_key_rejected():
    with pytest.raises(UnknownConfigKeyError):
        P.load_config({"totally_unknown": 1})


@pytest.mark.parametrize("mode", ["PRODUCTION_LIVE", "PRODUCTION_DRY_RUN"])
def test_production_modes_fail_closed(mode):
    with pytest.raises(UnsupportedExecutionModeError):
        P.load_config({"execution_mode": mode})


def test_unknown_execution_mode_string_rejected():
    with pytest.raises(InvalidConfigValueError):
        P.load_config({"execution_mode": "WHATEVER"})


@pytest.mark.parametrize("bad", [
    {"tenant": ""},
    {"max_retries": -1},
    {"max_retries": 99},
    {"max_retries": True},   # bool is not an int here
    {"redact_pii": "yes"},
    {"extra_reviewers": ["", "ok"]},
])
def test_invalid_values_rejected(bad):
    with pytest.raises(InvalidConfigValueError):
        P.load_config(bad)


def test_valid_config_roundtrips():
    cfg = P.load_config({"tenant": "acme", "max_retries": 3, "extra_reviewers": ["r2"]})
    assert cfg.tenant == "acme" and cfg.max_retries == 3
    assert cfg.extra_reviewers == ("r2",)
    assert cfg.to_dict()["execution_mode"] == "DETERMINISTIC_SIMULATION"


# --- composition ------------------------------------------------------------
def test_dev_and_demo_platforms_are_deterministic_simulation():
    dev = P.build_dev_platform(P.load_config({"tenant": "t9"}))
    demo = P.build_demo_platform()
    assert dev.config.execution_mode is ExecutionMode.DETERMINISTIC_SIMULATION
    assert demo.config.execution_mode is ExecutionMode.DETERMINISTIC_SIMULATION
    assert dev.config.tenant == "t9"


def test_run_case_reconstructs_end_to_end():
    prod = P.build_demo_platform()
    run = prod.run_case(P.CaseSpec(case_id="c1"))
    assert run.reconciliation_outcome == "MATCHED"
    rc = prod.reconstruct(run.action_proposal_id)
    assert rc.reconstructed is True


# --- demo: deterministic & safe --------------------------------------------
def test_demo_is_reproducible():
    a = P.run_demo().summary()
    b = P.run_demo().summary()
    assert a == b
    assert len(a) == 5


def test_demo_produces_sample_report():
    res = P.run_demo()
    assert res.sample_report is not None
    assert res.sample_report.integrity["reconstructed"] is True


# --- accountability: redaction ---------------------------------------------
def test_accountability_redaction_masks_actor_and_subject():
    prod = P.build_demo_platform()
    run = prod.run_case(P.CaseSpec(case_id="ac1"))
    redacted = P.build_accountability_report(prod, run.action_proposal_id, redact=True)
    clear = P.build_accountability_report(prod, run.action_proposal_id, redact=False)

    assert redacted.human_decision["decided_by"].startswith("actor:")
    assert redacted.human_decision["decided_by"] != clear.human_decision["decided_by"]
    # subject reference on the recommendation is pseudonymized
    assert redacted.recommendation["candidate_subject_ref"].startswith("subject:")
    # redaction is deterministic
    again = P.build_accountability_report(prod, run.action_proposal_id, redact=True)
    assert again.human_decision["decided_by"] == redacted.human_decision["decided_by"]


def test_accountability_report_is_json_serializable():
    prod = P.build_demo_platform()
    run = prod.run_case(P.CaseSpec(case_id="ac2"))
    report = P.build_accountability_report(prod, run.action_proposal_id)
    blob = json.dumps(report.to_dict(), default=str)
    assert "action_proposal_id" in blob
    assert isinstance(report.render_text(), str)


def test_accountability_default_redaction_follows_config():
    prod = P.build_dev_platform(P.load_config({"redact_pii": False}))
    run = prod.run_case(P.CaseSpec(case_id="ac3"))
    report = P.build_accountability_report(prod, run.action_proposal_id)
    assert report.redacted is False


# --- CLI --------------------------------------------------------------------
def test_cli_version_json(capsys):
    from ai_hiring.product.cli import main
    rc = main(["--json", "version"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["production_certified"] is False


def test_cli_verify_passes(capsys):
    from ai_hiring.product.cli import main
    rc = main(["verify"])
    assert rc == 0
    assert "RESULT: PASS" in capsys.readouterr().out


def test_cli_demo_runs(capsys):
    from ai_hiring.product.cli import main
    rc = main(["demo"])
    assert rc == 0
    assert "demo-advance" in capsys.readouterr().out


def test_cli_report_redacted_by_default(capsys):
    from ai_hiring.product.cli import main
    rc = main(["report"])
    out = capsys.readouterr().out
    assert rc == 0 and "redacted: True" in out
