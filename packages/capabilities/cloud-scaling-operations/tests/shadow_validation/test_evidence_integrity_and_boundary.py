"""Fixture evidence generation, integrity verification, and the harness boundary."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from shadow_validation.evidence import (
    generate_fixture_evidence, FIXTURE_ARTIFACT_NAMES, list_schemas, load_schema, validate,
)
from shadow_validation.integrity import (
    scan_harness_source, verify_evidence_dir, reproduce_scenarios,
)
from shadow_mutation_canaries import run_mutation_canaries


def _gen():
    d = tempfile.mkdtemp(prefix="shadow-ev-")
    generate_fixture_evidence(d, canary_results=run_mutation_canaries())
    return d


def test_generate_all_artifacts_and_labels():
    d = _gen()
    for name in FIXTURE_ARTIFACT_NAMES:
        assert (Path(d) / name).exists(), name
    for p in Path(d).glob("fixture_*.json"):
        obj = json.loads(p.read_text())
        if "evidence_class" in obj:
            assert obj["evidence_class"] == "FAKE_LOCAL_FIXTURE"
            assert obj.get("real_environment_observed") is False
            assert obj.get("real_cluster_accessed") is False


def test_integrity_verifier_passes_on_generated_evidence():
    d = _gen()
    report = verify_evidence_dir(d)
    assert report["ok"] is True, [c for c in report["checks"] if not c["passed"]]


def test_decisions_are_all_shadow_proposed_only():
    d = _gen()
    decisions = [json.loads(l) for l in
                 (Path(d) / "fixture_shadow_decisions.jsonl").read_text().splitlines() if l]
    assert decisions
    for x in decisions:
        assert x["execution_mode"] == "SHADOW"
        assert x["execution_status"] == "NOT_EXECUTED"
        assert x["proposed_only"] is True


def test_harness_source_imports_no_live_executor():
    assert scan_harness_source() == []


def test_scenarios_reproducible():
    r = reproduce_scenarios()
    assert r["reproducible"] and r["all_ok"]


def test_all_schemas_present():
    assert len(list_schemas()) == 11


def test_aggregate_verdict_ok_and_no_real_claim():
    d = _gen()
    agg = json.loads((Path(d) / "fixture_aggregate_shadow_report.json").read_text())
    assert agg["verdict"] == "CLOUD_SCALING_OPERATIONS_SHADOW_HARNESS_FIXTURE_OK"
    assert agg["real_environment_observed"] is False
    validate(agg, load_schema("aggregate_shadow_report"))
