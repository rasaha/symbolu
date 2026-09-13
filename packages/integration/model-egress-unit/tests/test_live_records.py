"""The two live-provider records beside the package: designated in part, ruled in
nothing, holding no secret, and blocking every row."""

from __future__ import annotations

import json
import pathlib
import re

import ugence_model_egress_unit as meu

PKG = pathlib.Path(meu.__file__).resolve().parents[2]
DESIGNATION = PKG / "MEU_LIVE_PROVIDER_DESIGNATION.json"
VALIDATION = PKG / "MEU_LIVE_VALIDATION.json"


def test_the_designation_names_the_vendor_and_the_secret_manager_and_nothing_secret():
    d = json.loads(DESIGNATION.read_text(encoding="utf-8"))
    assert d["status"] == "RULED_INFRASTRUCTURE_DESIGNATIONS_PENDING"
    assert d["vendor"]["name"] == "OpenAI" and d["vendor"]["api_host"] == "api.openai.com"
    assert d["custody"]["secret_manager"].startswith("Google Cloud Secret Manager")
    assert d["custody"]["api_host"] == "secretmanager.googleapis.com"
    assert d["vendor"]["model"].startswith("gpt-5.4-mini-2026-03-17") and d["vendor"]["endpoint"].startswith("/v1/responses")
    assert "ugence-meu-validation" in d["vendor"]["account"] and "UNDESIGNATED" in d["vendor"]["account"]
    for field in ("data_processing_terms", "region"):
        assert d["vendor"][field].startswith("UNDESIGNATED"), field
    for field in ("gcp_project", "workload_identity", "secret_name", "iam_binding", "audit_logging", "rotation_procedure"):
        assert d["custody"][field].startswith("UNDESIGNATED"), field
    assert d["custody"]["custody_owner"] == "Rakesh Mohan — Founder, Ugence Labs"
    assert d["custody"]["rotation_policy"].startswith("at least every 90 days")
    assert d["custody"]["meu_identity_to_secret_manager"].startswith("RULED (LP-2)")
    assert d["limits"]["max_input_tokens_per_request"] == 8192 and d["limits"]["max_output_tokens_per_request"] == 1024
    assert d["limits"]["max_genuine_validation_calls"] == 10 and d["limits"]["total_commissioning_budget_usd"] == 25
    assert d["limits"]["concurrency"] == 1 and d["limits"]["streaming"] is False
    assert len(d["order"]) == 11
    assert "genuine_call True admitted only" in d["record_contract"]["genuine_call"]
    assert d["designated_by"] == "Rakesh Mohan" and d["designated_at"] == "2026-09-11"
    text = DESIGNATION.read_text(encoding="utf-8")
    assert not re.search(r"\bsk-[A-Za-z0-9_-]{8,}", text), "an OpenAI-shaped key"
    assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}\.", text) and "PRIVATE KEY" not in text
    assert "AIza" not in text, "a Google API key shape"


def test_the_validation_record_is_blocked_and_every_row_is_unexecuted():
    v = json.loads(VALIDATION.read_text(encoding="utf-8"))
    assert v["meu_live_status"] == "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS"
    assert v["meu_live_status"] in v["status_vocabulary"]
    rows = v["validation_matrix"]
    assert len(rows) == 18 and all(r["result"] is None for r in rows)
    assert [r["row"] for r in rows] == list(range(1, 19))
    assert rows[0]["required"] == "REFUSED_CREDENTIAL_NOT_COMMISSIONED"
    assert any("genuine_call" in b for b in v["blocked_by"]) and any("step 8" in b for b in v["blocked_by"])
    e = v["evidence"]
    assert e["accepting_owner"] is None and e["ci_run_or_signed_report"] is None and e["runs"] == []


def test_the_shipped_adapters_match_the_records_claims():
    """The record says the only custody adapter is the inert reference and the
    result contract refuses genuine_call; the package agrees."""
    assert meu.ReferenceCustodyAdapter.is_production_authoritative is False
    assert meu.LIVE_VENDOR_EGRESS is False
    import inspect
    assert "genuine_call" in inspect.getsource(meu.EgressResult.__post_init__)


def test_the_records_limits_and_destination_agree_with_the_code():
    d = json.loads(DESIGNATION.read_text(encoding="utf-8"))
    L = meu.COMMISSIONING_LIMITS
    assert d["limits"]["max_input_tokens_per_request"] == L.max_input_tokens
    assert d["limits"]["max_output_tokens_per_request"] == L.max_output_tokens
    assert d["limits"]["max_genuine_validation_calls"] == L.max_genuine_calls
    assert d["limits"]["total_commissioning_budget_usd"] * 100 == L.budget_usd_cents
    assert meu.OPENAI_RESPONSES.host == d["vendor"]["api_host"]
    assert d["vendor"]["endpoint"].startswith(meu.OPENAI_RESPONSES.path)
    assert meu.is_pinned_snapshot(d["vendor"]["model"].split(" ")[0])


def test_lp8_the_validation_record_binds_the_execution_posture_to_the_unit_constants():
    v = json.loads(VALIDATION.read_text(encoding="utf-8"))
    posture = v["live_execution_posture"]
    assert posture["required"] == meu.LIVE_VALIDATION_EXECUTION_POSTURE == "DEPLOYED_MEU_INSTANCE"
    assert posture["forbidden_holders"] == list(meu.FORBIDDEN_CREDENTIAL_HOLDERS)
    assert posture["custody_adapter"].startswith(meu.PRODUCTION_FORM_CUSTODY_ADAPTER)
    assert posture["instance_reference"].startswith("UNDESIGNATED") and posture["workload_identity_principal"].startswith("UNDESIGNATED")
    assert "exactly" in posture["sequence_completion"] and "max_calls" in posture["sequence_completion"]
    assert "no production commissioning" in posture["outcome_scope"]
    assert "repository CI" in posture["offline_testing"]
    row12 = next(r for r in v["validation_matrix"] if r["row"] == 12)
    assert any("deployed MEU instance" in p and "never by a developer machine, CI runner, browser" in p for p in row12["prerequisites"])
    assert row12["result"] is None
    assert any(b.startswith("LP-8:") for b in v["blocked_by"])
    # the seventeen obligations are untouched: LP-8 adds no eighteenth
    d = json.loads(DESIGNATION.read_text(encoding="utf-8"))
    assert d["step8_required_values"]["obligation_count"] == 17 and len(d["step8_required_values"]["obligations"]) == 17
