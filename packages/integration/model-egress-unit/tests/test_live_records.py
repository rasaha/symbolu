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
    assert d["status"] == "DESIGNATED_IN_PART_RULINGS_PENDING"
    assert d["vendor"]["name"] == "OpenAI" and d["vendor"]["api_host"] == "api.openai.com"
    assert d["custody"]["secret_manager"] == "Google Secret Manager"
    assert d["custody"]["api_host"] == "secretmanager.googleapis.com"
    for field in ("model", "account", "data_processing_terms", "region"):
        assert d["vendor"][field].startswith("UNDESIGNATED"), field
    for field in ("gcp_project", "secret_name", "rotation_policy", "custody_owner"):
        assert d["custody"][field].startswith("UNDESIGNATED"), field
    assert d["custody"]["meu_identity_to_secret_manager"].startswith("UNRULED (LP-2a)")
    assert "genuine_call True admitted only" in d["record_contract"]["genuine_call"]
    assert d["designated_by"] == "Rakesh Mohan" and d["designated_at"] == "2026-09-11"
    text = DESIGNATION.read_text(encoding="utf-8")
    assert not re.search(r"\bsk-[A-Za-z0-9_-]{8,}", text), "an OpenAI-shaped key"
    assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}\.", text) and "PRIVATE KEY" not in text
    assert "AIza" not in text, "a Google API key shape"


def test_the_validation_record_is_blocked_and_every_row_is_unexecuted():
    v = json.loads(VALIDATION.read_text(encoding="utf-8"))
    assert v["meu_live_status"] == "BLOCKED_PENDING_OWNER_RULINGS"
    assert v["meu_live_status"] in v["status_vocabulary"]
    rows = v["validation_matrix"]
    assert len(rows) == 11 and all(r["result"] is None for r in rows)
    assert [r["row"] for r in rows] == list(range(1, 12))
    assert rows[0]["required"] == "REFUSED_CREDENTIAL_NOT_COMMISSIONED"
    assert any("genuine_call" in b for b in v["blocked_by"])
    e = v["evidence"]
    assert e["accepting_owner"] is None and e["ci_run_or_signed_report"] is None and e["runs"] == []


def test_the_shipped_adapters_match_the_records_claims():
    """The record says the only custody adapter is the inert reference and the
    result contract refuses genuine_call; the package agrees."""
    assert meu.ReferenceCustodyAdapter.is_production_authoritative is False
    assert meu.LIVE_VENDOR_EGRESS is False
    import inspect
    assert "genuine_call" in inspect.getsource(meu.EgressResult.__post_init__)
