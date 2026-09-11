"""``offline`` writes the report and exits by conformance and drift; ``live`` refuses."""

from __future__ import annotations

import json

import pytest

from ugence_model_egress_unit import STEP8_REQUIRED_VALUES
from ugence_model_egress_validation.cli import main
from ugence_model_egress_validation.drift import records_directory


def test_offline_writes_a_redacted_report_and_exits_zero(tmp_path, capsys):
    report = tmp_path / "out" / "report.json"
    rc = main(["offline", "--report", str(report), "--now", "2026-09-11T18:30:00+00:00"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "OFFLINE_CONFORMANT': 13" in out and "not executed: [12, 18]" in out
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["drift"] == [] and data["live_pass_claimed"] is False
    assert data["generated_at"] == "2026-09-11T18:30:00+00:00"


def test_offline_exits_non_zero_on_drift(tmp_path, capsys):
    records = tmp_path / "records"
    records.mkdir()
    src = records_directory()
    designation = json.loads((src / "MEU_LIVE_PROVIDER_DESIGNATION.json").read_text(encoding="utf-8"))
    validation = json.loads((src / "MEU_LIVE_VALIDATION.json").read_text(encoding="utf-8"))
    validation["meu_live_status"] = "MET"
    (records / "MEU_LIVE_PROVIDER_DESIGNATION.json").write_text(json.dumps(designation), encoding="utf-8")
    (records / "MEU_LIVE_VALIDATION.json").write_text(json.dumps(validation), encoding="utf-8")
    rc = main(["offline", "--report", str(tmp_path / "r.json"), "--records", str(records), "--now", "2026-09-11T18:30:00+00:00"])
    assert rc == 1
    assert "drift:" in capsys.readouterr().out
    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["drift"]


def test_live_refuses_with_exit_2_and_names_every_undesignated_value(capsys):
    rc = main(["live"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "live verifier refused" in out and "no live transport exists" in out
    assert "18 step-8 designations are undesignated or unchecked" in out
    for name in ("gcp_project_id", "gcp_project_number", "openai_project_service_account_id",
                 "designated_model_availability_evidence", "approved_processing_or_data_residency_region",
                 "independently_checked_by"):
        assert f"  - {name}" in out
    assert len(STEP8_REQUIRED_VALUES) == 18


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        main([])
