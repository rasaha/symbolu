"""The job: offline succeeds without a secret, live fails closed, and every gate is
reported whether or not it passed."""

from __future__ import annotations

import json

import pytest

from meu_validation_job import JobConfigRefused, evaluate_gates, load_config, run
from meu_validation_job.cli import main
from meu_validation_job.job import ci_marker_variables, load_records
from meu_validation_job.version import EXIT_NONCONFORMANT, EXIT_OK, EXIT_REFUSED
from ugence_model_egress_unit import CI_ENVIRONMENT_MARKERS, LIVE_VENDOR_EGRESS

from _fixtures import (ATTESTED_BY, INSTANCE, NOW, RESOURCE, SA, complete_designation,
                       config_mapping, write_config)
from synthetic_shapes import KINDS, synthetic_credential_shape

NO_CI = {"HOME": "/home/ugence"}


def _run(tmp_path, **over):
    config = load_config(write_config(tmp_path, **over))
    return run(config, now=NOW, environ=NO_CI)


# --- the default path -----------------------------------------------------------------

def test_offline_is_the_default_and_terminates_successfully_without_reading_a_secret(tmp_path):
    result = _run(tmp_path)
    assert result.exit_code == EXIT_OK and result.outcome == "OFFLINE_CONFORMANT"
    assert result.report["credential_materialized"] is False
    assert result.report["secret_version_accessed"] is None
    assert result.report["mode"] == "offline"
    assert result.report["offline_harness"]["summary"]["OFFLINE_NONCONFORMANT"] == 0
    assert json.loads(result.report_path.read_text(encoding="utf-8"))["outcome"] == "OFFLINE_CONFORMANT"


def test_the_report_is_identifiers_digests_timestamps_accounting_and_outcomes_only(tmp_path):
    report = _run(tmp_path).report
    assert report["accounting"] == {"input_tokens": 0, "output_tokens": 0, "usd_cents": 0}
    assert report["genuine_calls"] == {"authorized": None, "consumed": 0}
    assert report["network_opened"] is False and report["credential_present"] is False
    assert report["live_pass_claimed"] is False and report["live_vendor_egress"] is False
    assert all(row["result_in_record"] is None for row in report["offline_harness"]["rows"])
    assert report["ceilings"] == {"max_genuine_calls": 10, "budget_usd_cents": 2500,
                                  "max_input_tokens": 8192, "max_output_tokens": 1024,
                                  "concurrency": 1, "max_retries": 1, "store": False,
                                  "tools": False, "streaming": False, "background": False}


def test_a_run_leaves_the_canonical_records_byte_identical(tmp_path):
    import hashlib
    config = load_config(write_config(tmp_path))
    before = {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
              for p in (config.designation_record_path, config.validation_record_path)}
    run(config, now=NOW, environ=NO_CI)
    after = {p: hashlib.sha256(open(p, "rb").read()).hexdigest() for p in before}
    assert after == before


# --- live fails closed ------------------------------------------------------------------

def test_live_fails_closed_and_leads_with_the_earliest_outstanding_gate(tmp_path):
    """Not with the missing transport: that reads as "authorize it and it will run"."""

    assert LIVE_VENDOR_EGRESS is False
    result = _run(tmp_path, mode="live")
    assert result.exit_code == EXIT_REFUSED and result.outcome == "REFUSED"
    assert result.messages[0].startswith("live mode refused at STEP8_DESIGNATIONS")
    assert "LIVE_TRANSPORT" not in result.messages[0]
    assert result.report["credential_materialized"] is False
    assert "no Google client, custody adapter or transport was composed" in " ".join(result.messages)


def test_with_the_designations_accepted_live_is_refused_at_the_authorization_not_the_transport(tmp_path):
    """Accepting the designations moves the refusal forward one gate at a time. It never
    jumps to the transport, which is last."""

    result = _run(tmp_path, designation=complete_designation(), mode="live")
    assert result.exit_code == EXIT_REFUSED
    assert result.messages[0].startswith("live mode refused at LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION")
    assert result.report["blocked_gates"] == ["LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION",
                                              "LIVE_VENDOR_EGRESS", "LIVE_TRANSPORT"]
    assert result.report["credential_materialized"] is False


# --- the gates ---------------------------------------------------------------------------

def test_every_gate_is_reported_even_when_an_earlier_one_blocked(tmp_path):
    report = _run(tmp_path).report
    assert [g["gate"] for g in report["gates"]] == [
        "CONFIGURATION", "EXECUTION_POSTURE", "STEP8_DESIGNATIONS",
        "STEP8_INDEPENDENT_VERIFICATION", "LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION",
        "LIVE_VENDOR_EGRESS", "LIVE_TRANSPORT"]
    assert all(g["reason"] for g in report["gates"]), "a gate reported no reason"


def test_the_canonical_records_block_the_designation_and_the_authorization_gates(tmp_path):
    report = _run(tmp_path).report
    blocked = {g["gate"]: g["reason"] for g in report["gates"] if g["status"] == "BLOCKED"}
    assert "17 of 17 designation obligations are not supplied" in blocked["STEP8_DESIGNATIONS"]
    assert "NOT_GIVEN" in blocked["LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION"]


def test_an_incomplete_designation_blocks_materialization(tmp_path):
    designation = complete_designation()
    designation["step8_required_values"]["obligations"]["openai_project_id"] = "UNDESIGNATED"
    config = load_config(write_config(tmp_path, designation=designation))
    gates = evaluate_gates(config, designation_record=designation,
                           validation_record=load_records(config)[1],
                           variables=ci_marker_variables(NO_CI), now=NOW)
    assert gates.may_compose_components is False
    assert "1 of 17" in dict((o.gate, o.reason) for o in gates.outcomes)["STEP8_DESIGNATIONS"]


def test_a_designation_without_independent_verification_blocks_materialization(tmp_path):
    designation = complete_designation()
    designation["step8_required_values"]["attestation"]["independently_checked_by"] = None
    config = load_config(write_config(tmp_path, designation=designation))
    gates = evaluate_gates(config, designation_record=designation,
                           validation_record=load_records(config)[1],
                           variables=ci_marker_variables(NO_CI), now=NOW)
    assert gates.may_compose_components is False
    assert "no independent verification" in dict(
        (o.gate, o.reason) for o in gates.outcomes)["STEP8_INDEPENDENT_VERIFICATION"]


def test_a_complete_attested_designation_is_not_enough_to_materialize_a_credential(tmp_path):
    """Designation acceptance closes the designation gate and nothing else. Reading the
    real credential still waits on the owner's canonical authorization, because a run
    that may not call may not read."""

    config = load_config(write_config(tmp_path, designation=complete_designation()))
    designation, validation, _ = load_records(config)
    gates = evaluate_gates(config, designation_record=designation, validation_record=validation,
                           variables=ci_marker_variables(NO_CI), now=NOW)
    assert gates.status("EXECUTION_POSTURE") == "PASSED"
    assert gates.status("STEP8_DESIGNATIONS") == "PASSED"
    assert gates.status("STEP8_INDEPENDENT_VERIFICATION") == "PASSED"
    assert gates.may_compose_components is False
    assert gates.may_dispatch_a_genuine_call is False
    assert gates.blocked == ("LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION", "LIVE_VENDOR_EGRESS",
                             "LIVE_TRANSPORT")


@pytest.mark.parametrize("marker", ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE"])
def test_a_ci_runner_blocks_the_posture_gate_whatever_the_configuration_says(marker, tmp_path):
    config = load_config(write_config(tmp_path, designation=complete_designation()))
    designation, validation, _ = load_records(config)
    gates = evaluate_gates(config, designation_record=designation, validation_record=validation,
                           variables=ci_marker_variables({marker: "true"}), now=NOW)
    assert gates.may_compose_components is False
    assert "CI runner" in dict((o.gate, o.reason) for o in gates.outcomes)["EXECUTION_POSTURE"]


def test_the_environment_read_is_exactly_the_ci_marker_names(tmp_path):
    variables = ci_marker_variables({"CI": "1", "OPENAI_API_KEY": "must-never-be-read",
                                     "GOOGLE_APPLICATION_CREDENTIALS": "/x/key.json"})
    assert set(variables) == set(CI_ENVIRONMENT_MARKERS)
    assert "must-never-be-read" not in json.dumps(variables)


@pytest.mark.parametrize("principal", [
    "projects/p/serviceAccounts/000000000000-compute@developer.gserviceaccount.com",
    "user:someone@ugence.invalid",
])
def test_a_human_or_default_compute_principal_blocks_the_posture_gate(principal, tmp_path):
    config = load_config(write_config(tmp_path, workload_identity_principal=principal,
                                      designation=complete_designation()))
    designation, validation, _ = load_records(config)
    gates = evaluate_gates(config, designation_record=designation, validation_record=validation,
                           variables=ci_marker_variables(NO_CI), now=NOW)
    assert gates.may_compose_components is False


# --- configuration refusals ---------------------------------------------------------------

@pytest.mark.parametrize("over, why", [
    ({"environment": "production"}, "non-production"),
    ({"mode": "dry"}, "config.mode"),
    ({"schema": "meu-validation-job.config.v2"}, "config.schema"),
    ({"instance_reference": ""}, "instance_reference"),
    ({"workload_identity_principal": " "}, "workload_identity_principal"),
    ({"custody": {}}, "custody"),
])
def test_configuration_refusals(over, why, tmp_path):
    if over.get("custody") == {}:
        mapping = config_mapping(tmp_path)
        mapping["custody"] = {}
        path = tmp_path / "c.json"
        path.write_text(json.dumps(mapping), encoding="utf-8")
        with pytest.raises(JobConfigRefused, match=why):
            load_config(path)
        return
    with pytest.raises(JobConfigRefused, match=why):
        load_config(write_config(tmp_path, **over))


@pytest.mark.parametrize("endpoint", [
    "https://api.openai.com/v1/chat/completions",
    "https://api.openai.com/v1/responses/",
    "https://api.openai.com:8443/v1/responses",
    "http://api.openai.com/v1/responses",
    "https://evil.invalid/v1/responses",
    "https://api.openai.com/v1/responses?x=1",
])
def test_any_endpoint_but_exactly_the_responses_url_is_refused(endpoint, tmp_path):
    with pytest.raises(JobConfigRefused, match="designated destination"):
        load_config(write_config(tmp_path, endpoint=endpoint))


@pytest.mark.parametrize("kind", KINDS)
def test_a_raw_credential_in_any_configuration_field_is_refused_without_being_echoed(kind, tmp_path):
    value = synthetic_credential_shape(kind)
    with pytest.raises(JobConfigRefused) as info:
        load_config(write_config(tmp_path, instance_reference=value))
    assert value not in str(info.value)
    with pytest.raises(JobConfigRefused) as info:
        load_config(write_config(tmp_path, custody={"custody_authority_id": value}))
    assert value not in str(info.value)


def test_a_field_naming_credential_material_is_refused_even_if_its_value_is_innocuous(tmp_path):
    mapping = config_mapping(tmp_path)
    mapping["custody"]["api_key"] = "not-actually-a-key"
    path = tmp_path / "c.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    with pytest.raises(JobConfigRefused, match="names credential material"):
        load_config(path)


def test_an_unknown_field_is_refused_and_a_comment_key_is_not(tmp_path):
    mapping = config_mapping(tmp_path)
    mapping["_comment"] = "operators annotate configuration; JSON has no comments"
    path = tmp_path / "c.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    assert load_config(path).mode == "offline"
    mapping["enviroment"] = "non-production"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    with pytest.raises(JobConfigRefused, match="unknown field"):
        load_config(path)


@pytest.mark.parametrize("document, why", [
    ("[]", "must be a JSON object"), ("{", "not valid JSON"),
])
def test_a_malformed_configuration_document_is_refused(document, why, tmp_path):
    path = tmp_path / "c.json"
    path.write_text(document, encoding="utf-8")
    with pytest.raises(JobConfigRefused, match=why):
        load_config(path)


def test_a_missing_record_is_refused_by_path_without_guessing(tmp_path):
    config = load_config(write_config(tmp_path, designation_record_path=str(tmp_path / "gone.json")))
    with pytest.raises(JobConfigRefused, match="does not exist"):
        load_records(config)


# --- the command line ---------------------------------------------------------------------

def test_the_dry_run_writes_nothing_and_prints_every_gate(tmp_path, capsys, monkeypatch):
    for marker in CI_ENVIRONMENT_MARKERS:
        monkeypatch.delenv(marker, raising=False)
    path = write_config(tmp_path)
    assert main(["dry-run", "--config", str(path)]) == EXIT_NONCONFORMANT
    out = capsys.readouterr().out
    assert "nothing was run and no report was written" in out
    for gate in ("EXECUTION_POSTURE", "STEP8_DESIGNATION", "LIVE_TRANSPORT"):
        assert gate in out
    assert not (tmp_path / "report.json").exists()


def test_the_validate_command_runs_offline_and_reports(tmp_path, capsys, monkeypatch):
    for marker in CI_ENVIRONMENT_MARKERS:
        monkeypatch.delenv(marker, raising=False)
    path = write_config(tmp_path)
    assert main(["validate", "--config", str(path), "--now", "2026-09-13T12:00:00+00:00"]) == EXIT_OK
    assert "outcome OFFLINE_CONFORMANT" in capsys.readouterr().out
    assert (tmp_path / "report.json").is_file()


def test_a_refused_configuration_exits_two_without_a_traceback(tmp_path, capsys):
    path = tmp_path / "c.json"
    path.write_text("{}", encoding="utf-8")
    assert main(["validate", "--config", str(path)]) == EXIT_REFUSED
    assert "configuration refused" in capsys.readouterr().out
