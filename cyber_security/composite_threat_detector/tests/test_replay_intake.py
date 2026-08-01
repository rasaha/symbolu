"""Sanitized-enterprise-replay intake infrastructure tests.

No enterprise data exists this phase, so these validate the READINESS scaffolding:
the version binding that closes the digest-audit gap, POST_HOC_ONLY labeling, the
pre-registered gates, and that every intake template is well-formed and covers the
required fields. Enterprise accuracy remains NOT RUN / REQUIRES ADDITIONAL ENTERPRISE DATA.
"""

from __future__ import annotations

import glob
import json
import os

from composite_threat_detector.policypack import (
    reference, replay, replay_gates as G,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INTAKE = os.path.join(ROOT, "replay_intake")
FIXTURE = os.path.join(ROOT, "composite_threat_detector", "policypack", "fixtures",
                       "account_takeover_replay.json")


def _fx():
    with open(FIXTURE) as fh:
        return json.load(fh)


# --- §1.7/§10.8 digest-gap closure ----------------------------------------
def test_replay_binds_full_version_set():
    res = replay.run_replay(reference.account_takeover_pack(), _fx()["records"])
    vb = res["version_binding"]
    for k in ("graph_structure_digest", "matcher_version", "partial_policy_version",
              "witness_tiebreak_version", "witness_minimality_basis", "schema_version",
              "compiler_version", "bundle_digest"):
        assert vb[k]
    assert vb["matcher_version"] == "ctd.storygraph.matcher/2.0.0"
    assert vb["witness_minimality_basis"] == "SEMANTIC_EQUIVALENCE_CLASS"
    # every finding carries the version binding
    assert all(f["version_binding"] for f in res["findings"])


def test_finding_digest_changes_if_matcher_version_changes(monkeypatch):
    base = replay.run_replay(reference.account_takeover_pack(), _fx()["records"])
    import composite_threat_detector.storygraph as SG
    monkeypatch.setattr(SG, "MATCHER_SEMANTICS_VERSION", "ctd.storygraph.matcher/9.9.9")
    changed = replay.run_replay(reference.account_takeover_pack(), _fx()["records"])
    assert base["report_digest"] != changed["report_digest"]


def test_post_hoc_only_labeled_on_execution_receipt():
    records = _fx()["records"] + [{
        "tenant": "enterprise-bank-a", "source_system": "payment_engine",
        "source_event_id": "t-5", "record_kind": "execution_receipt",
        "canonical_event_type": "EXECUTION_RECEIPT", "event_time": "2026-07-01T10:13:00Z",
        "ingestion_time": "2026-07-01T10:13:01Z", "source_ordering": 5,
        "workflow_id": "wf-takeover"}]
    res = replay.run_replay(reference.account_takeover_pack(), records)
    tk = next(f for f in res["findings"] if f["workflow_id"] == "wf-takeover")
    assert tk["post_hoc_only"] is True
    assert "POST_HOC_ONLY" in tk["explanation"]


# --- §13 pre-registered gates ---------------------------------------------
def test_gates_preregistered_and_sealed():
    assert set(G.ACCEPTANCE_GATES) == {
        "R1_policy_fit", "R2_data_quality", "R3_tenant_isolation",
        "R4_deterministic_replay", "R5_exact_completion_integrity", "R6_context_safety",
        "R7_explanation_quality", "R8_operational_burden", "R9_evidence_chain"}
    assert G.PREREGISTRATION["preregistered_before_findings"] is True
    assert G.preregistration_digest().startswith("sha-256:")
    assert G.DATA_QUALITY_MINIMUMS["max_cross_tenant_contamination"] == 0
    assert G.DATA_QUALITY_MINIMUMS["max_redaction_failures"] == 0


def test_r2_gate_fails_on_bad_quality():
    bad_dq = {"records_received": 100, "records_normalized": 80, "records_rejected": 20,
              "unknown_event_types": 5, "ordering_conflicts": 1,
              "redaction_failures": 1, "cross_tenant_contamination": 0}
    assert G.data_quality_gate(bad_dq)["pass"] is False


# --- §2/§15 intake package integrity --------------------------------------
def test_all_intake_files_present_and_valid():
    for name in ("replay_manifest.template.json", "replay_record.schema.json",
                 "source_event_mapping.template.json", "provider_mapping.template.json",
                 "reviewer_worksheet.template.json", "example_sanitized_record.json"):
        path = os.path.join(INTAKE, name)
        assert os.path.exists(path), name
        with open(path) as fh:
            json.load(fh)                          # valid JSON
    assert os.path.exists(os.path.join(INTAKE, "README.md"))
    assert os.path.exists(os.path.join(INTAKE, "policy_gap_report.template.md"))


def test_manifest_template_has_all_required_custody_fields():
    with open(os.path.join(INTAKE, "replay_manifest.template.json")) as fh:
        m = json.load(fh)
    for f in ("dataset_id", "dataset_version", "anonymized_tenant_id", "source_systems",
              "record_counts_by_source", "covered_time_period", "extraction_timestamp",
              "redaction_method", "hashing_method", "schema_versions", "known_omissions",
              "data_use_authorization_reference", "source_file_digests",
              "evaluated_code_commit", "story_policy_pack_version", "replay_run_id"):
        assert f in m, f


def test_example_record_is_labeled_synthetic_and_has_no_raw_pii():
    with open(os.path.join(INTAKE, "example_sanitized_record.json")) as fh:
        raw = fh.read()
    data = json.loads(raw)
    assert "NOT enterprise data" in data["_note"]
    # every identifier in the example is a redaction token
    for rec in data["records"]:
        for slot in ("actor", "account", "device", "beneficiary"):
            if slot in rec:
                assert rec[slot].startswith("redacted:")


def test_record_schema_matches_runtime_contract():
    with open(os.path.join(INTAKE, "replay_record.schema.json")) as fh:
        js = json.load(fh)
    # required record fields in the schema match the runtime replay contract
    assert set(js["required"]) == set(replay.REPLAY_RECORD_FIELDS)
