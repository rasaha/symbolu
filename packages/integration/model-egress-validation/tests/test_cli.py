"""``offline`` writes the report and exits by conformance and drift; ``live`` refuses before
custody, reservation or dispatch; neither command mutates the canonical records."""

from __future__ import annotations

import hashlib
import json
import pathlib
import socket

import pytest

from ugence_model_egress_unit import STEP8_OBLIGATION_COUNT
from ugence_model_egress_validation.cli import main
from ugence_model_egress_validation.drift import records_directory


def _digests(directory: pathlib.Path) -> dict:
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in ("MEU_LIVE_PROVIDER_DESIGNATION.json", "MEU_LIVE_VALIDATION.json")}


def test_socket_refusal_is_active_for_this_suite():
    with pytest.raises(AssertionError, match="opened a socket"):
        socket.create_connection(("127.0.0.1", 9))
    with pytest.raises(AssertionError, match="opened a socket"):
        socket.socket().connect(("127.0.0.1", 9))


def test_offline_writes_a_redacted_report_exits_zero_and_leaves_both_records_byte_identical(tmp_path, capsys):
    records = records_directory()
    before = _digests(records)
    report = tmp_path / "out" / "report.json"
    rc = main(["offline", "--report", str(report), "--now", "2026-09-11T18:30:00+00:00"])
    assert rc == 0
    assert _digests(records) == before, "the offline command mutated a canonical record"
    out = capsys.readouterr().out
    assert "OFFLINE_CONFORMANT': 13" in out and "not executed: [12, 18]" in out
    assert "17 mandatory designation obligations represented by 23 checked fields, none supplied here" in out
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["drift"] == [] and data["live_pass_claimed"] is False
    assert data["step8"] == {"statement": "17 mandatory designation obligations represented by 23 checked fields",
                             "obligations": 17, "checked_fields": 23, "supplied_here": 0}
    # every infrastructure-dependent row: null in the record, not executed in the report, with its evidence named
    validation = json.loads((records / "MEU_LIVE_VALIDATION.json").read_text(encoding="utf-8"))
    assert all(r["result"] is None for r in validation["validation_matrix"])
    for row in data["rows"]:
        assert row["result_in_record"] is None
        if row["infrastructure_dependent"]:
            assert row["status"] == "NOT_EXECUTABLE_OFFLINE" and row["external_evidence_required"]
    assert [r["row"] for r in data["rows"] if r["status"] == "NOT_EXECUTABLE_OFFLINE"] == [12, 13, 14, 15, 18]


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


def test_live_refuses_with_exit_2_before_any_custody_reservation_or_dispatch(capsys, monkeypatch):
    """Every path that could touch custody, the budget, a transport or the harness is armed
    to raise; ``live`` must return 2 without reaching any of them."""

    import ugence_model_egress_unit as meu
    import ugence_model_egress_provider_openai as adapter
    import ugence_model_egress_validation.cli as cli
    import ugence_model_egress_validation.harness as harness

    def boom(*a, **k):
        raise AssertionError("live reached a component it must never touch")

    monkeypatch.setattr(adapter.OpenAIResponsesProvider, "__init__", boom)
    monkeypatch.setattr(adapter.OpenAIResponsesProvider, "execute", boom)
    monkeypatch.setattr(adapter.FakeTransport, "send", boom)
    monkeypatch.setattr(meu.CallBudget, "reserve", boom)
    monkeypatch.setattr(meu.CredentialLease, "use", boom)
    monkeypatch.setattr(meu, "materialize_with_audit", boom)
    monkeypatch.setattr(harness._MarkerCustody, "materialize", boom)
    monkeypatch.setattr(harness, "run_offline", boom)
    monkeypatch.setattr(cli, "run_offline", boom)
    records = records_directory()
    before = hashlib.sha256((records / "MEU_LIVE_VALIDATION.json").read_bytes()).hexdigest()
    rc = main(["live"])
    assert rc == 2
    assert hashlib.sha256((records / "MEU_LIVE_VALIDATION.json").read_bytes()).hexdigest() == before
    out = capsys.readouterr().out
    assert "live verifier refused" in out and "no live transport exists" in out
    assert "live_synthetic_validation_authorization is 'NOT_GIVEN'" in out
    assert "17 mandatory designation obligations represented by 23 checked fields (LP-7 ruling 12)." in out
    assert f"17 of {STEP8_OBLIGATION_COUNT} mandatory designation obligations are undesignated:" in out
    obligations = [line[4:] for line in out.splitlines() if line.startswith("  - ") and ":" not in line]
    assert len(obligations) == 17 and obligations[0] == "gcp_project_id" and obligations[-1] == "approved_processing_or_data_residency_region"
    assert "attestation (not a designation obligation):" in out and "  - independently_checked_by: not recorded" in out
    assert "18" not in out.replace("2026", "")  # no eighteenth anything


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        main([])
