"""The report carries no content; the drift checks catch every disagreement they name."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

import pytest

import ugence_model_egress_unit as meu
from ugence_model_egress_provider_openai import FAKE_RESPONSE_MARKER
from ugence_model_egress_validation import (
    REPORT_SCHEMA,
    SYNTHETIC_PROMPT,
    build_report,
    check_drift,
    load_records,
    records_directory,
    render,
    run_offline,
    scan,
    write_report,
)
from ugence_model_egress_validation.harness import RowOutcome

NOW = datetime(2026, 9, 11, 18, 30, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def run():
    return run_offline(now=NOW)


@pytest.fixture(scope="module")
def report(run):
    return build_report(run)


def test_the_report_claims_no_pass_opens_no_network_and_carries_no_content(report, run, tmp_path):
    assert report["schema"] == REPORT_SCHEMA
    assert report["live_pass_claimed"] is False and report["network_opened"] is False and report["credential_present"] is False
    assert report["audit_query_window"] is None
    assert report["infrastructure_dependent_rows_not_executed"] == [12, 18]
    assert report["summary"] == {"OFFLINE_CONFORMANT": 13, "OFFLINE_NONCONFORMANT": 0, "NOT_EXECUTABLE_OFFLINE": 5}
    assert report["commissioning_status"] == meu.COMMISSIONING_STATUS
    assert report["step8"]["statement"] == "17 mandatory designation obligations represented by 23 checked fields"
    for row in report["rows"]:
        assert row["result_in_record"] is None
        if row["status"] == "NOT_EXECUTABLE_OFFLINE":
            assert row["external_evidence_required"], row["row"]
    text = render(report)
    assert SYNTHETIC_PROMPT not in text and FAKE_RESPONSE_MARKER not in text
    for marker in run.known_markers:
        assert marker not in text
    assert scan(report, known_markers=run.known_markers) == []
    path = write_report(report, tmp_path / "nested" / "report.json")
    assert json.loads(path.read_text(encoding="utf-8"))["rows"][11]["status"] == "NOT_EXECUTABLE_OFFLINE"


def test_the_generator_refuses_a_report_that_would_carry_the_prompt_the_marker_or_a_key(run):
    import dataclasses
    from synthetic_shapes import synthetic_credential_shape
    for poison in (SYNTHETIC_PROMPT, run.known_markers[0], synthetic_credential_shape("openai_project_key"), FAKE_RESPONSE_MARKER):
        poisoned = dataclasses.replace(run, outcomes=[
            dataclasses.replace(o, observed=o.observed + " " + poison) if o.row == 1 else o for o in run.outcomes])
        with pytest.raises(ValueError):
            build_report(poisoned)


def test_the_generator_refuses_a_status_outside_the_vocabulary(run):
    import dataclasses
    bad = dataclasses.replace(run, outcomes=[
        dataclasses.replace(o, status="PASS") if o.row == 12 else o for o in run.outcomes])
    with pytest.raises(AssertionError):
        build_report(bad)


# --- drift -------------------------------------------------------------------------

def test_the_records_beside_the_unit_show_no_drift():
    records = load_records()
    assert records_directory().name == "model-egress-unit"
    assert check_drift(records["designation"], records["validation"]) == []
    assert records["validation"]["live_synthetic_validation_authorization"] == "NOT_GIVEN"
    assert records["validation"]["revoked_authorization_digests"] == []
    assert records["validation"]["authorizing_owner"] == records["designation"]["custody"]["custody_owner"]
    from ugence_model_egress_validation import validation_plan_digest
    assert len(validation_plan_digest()) == 64 and validation_plan_digest() == validation_plan_digest()
    row12 = records["validation"]["validation_matrix"][11]
    assert row12["row"] == 12 and len(row12["prerequisites"]) == 5 and "presuppose MET" in row12["contributes_to"]
    step8 = records["designation"]["step8_required_values"]
    assert step8["obligation_count"] == 17 and step8["checked_fields"] == 23 and len(step8["obligations"]) == 17
    assert step8["attestation"]["independently_checked_by"] is None


@pytest.mark.parametrize("mutate, expected", [
    (lambda d, v: d["limits"].__setitem__("max_genuine_validation_calls", 11), "max_genuine_validation_calls"),
    (lambda d, v: d["limits"].__setitem__("total_commissioning_budget_usd", 26), "budget_usd_cents"),
    (lambda d, v: d["limits"].__setitem__("streaming", True), "streaming"),
    (lambda d, v: d["vendor"].__setitem__("api_host", "api.openai.com.evil.example"), "api_host"),
    (lambda d, v: d["vendor"].__setitem__("endpoint", "/v1/chat/completions"), "endpoint"),
    (lambda d, v: d["vendor"].__setitem__("model", "gpt-5.4-mini (alias)"), "DESIGNATED_MODEL"),
    (lambda d, v: v.__setitem__("meu_live_status", "MET"), "COMMISSIONING_STATUS"),
    (lambda d, v: v.__setitem__("live_synthetic_validation_authorization", "owner-authorization-x"), "mirror LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION_DIGEST"),
    (lambda d, v: v.__setitem__("live_synthetic_validation_authorization", "yes"), "never an authorization"),
    (lambda d, v: v.__setitem__("authorizing_owner", "Someone Else"), "authorizing_owner"),
    (lambda d, v: v.__delitem__("revoked_authorization_digests"), "revoked_authorization_digests"),
    (lambda d, v: v["validation_matrix"].__getitem__(11).__setitem__("prerequisites", ["commissioning MET"]), "never a prerequisite"),
    (lambda d, v: v["validation_matrix"].__getitem__(11).__setitem__("prerequisites", []), "no prerequisites"),
    (lambda d, v: v["validation_matrix"].__getitem__(0).__setitem__("required", "PASS"), "differ from the harness"),
    (lambda d, v: v["validation_matrix"].__getitem__(11).__setitem__("result", "PASS"), "carries a result while the provider is blocked"),
    (lambda d, v: v["evidence"].__setitem__("runs", [{"fixture": True}]), "carries evidence while the provider is blocked"),
], ids=lambda x: x if isinstance(x, str) else "")
def test_each_named_drift_is_caught(mutate, expected):
    records = load_records()
    d, v = copy.deepcopy(records["designation"]), copy.deepcopy(records["validation"])
    mutate(d, v)
    drift = check_drift(d, v)
    assert any(expected in line for line in drift), drift


def test_step8_values_still_undesignated_forbid_any_status_but_blocked():
    records = load_records()
    d, v = copy.deepcopy(records["designation"]), copy.deepcopy(records["validation"])
    assert all(val == "UNDESIGNATED" for val in d["step8_required_values"]["obligations"].values())
    assert d["step8_required_values"]["attestation"]["independently_checked_by"] is None
    v["meu_live_status"] = "PENDING_VALIDATION"
    assert any("UNDESIGNATED but the status" in line for line in check_drift(d, v))
