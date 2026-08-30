"""Evidence-manifest integrity: only this run's output may count as evidence.

The manifest previously hashed whatever sat in a repository directory, where
seven reference records are committed — several of them recording
``"result": "NOT_EXECUTED"``. A run that scanned nothing still reported non-null
scan hashes. These tests are mostly negative: they prove that committed or stale
files, a pre-populated output directory, and failed or skipped producers cannot
yield non-null current-run evidence.

No container gate is executed or marked passed here.
"""
from __future__ import annotations

import importlib.util
import json
import os

import pytest

from depaths import REPO

CI = os.path.join(REPO, "deployment", "governance-studio", "ci")
REFERENCE = os.path.join(REPO, "deployment", "governance-studio", "reference-evidence")
ARTIFACTS = os.path.join(REPO, "deployment", "governance-studio", "artifacts")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(CI, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def builder():
    return _load("build_evidence_manifest")


ALL_STEPS = [
    "runtime-package-inventory", "image-layer-secret-scan", "image-sbom",
    "container-vulnerability-scan", "container-runtime-verification",
]
FILES = {
    "runtime-package-inventory": "runtime-image-packages.txt",
    "image-layer-secret-scan": "secret-scan.json",
    "image-sbom": "sbom.image.cdx.json",
    "container-vulnerability-scan": "container-scan.json",
    "container-runtime-verification": "runtime-egress-report.json",
}


def _all(outcome):
    return {s: outcome for s in ALL_STEPS}


def _populate(d):
    for f in FILES.values():
        (d / f).write_text("pretend evidence")
    return d


def _manifest(builder, d, producers):
    return builder.build(str(d), producers, "commit-sha", "run-1", "attempt-1")


# --- positive control --------------------------------------------------------

def test_successful_producers_yield_hashed_evidence(builder, tmp_path):
    m = _manifest(builder, _populate(tmp_path), _all("success"))
    assert m["run_completeness"] == "COMPLETE"
    assert m["missing_mandatory_evidence"] == []
    for key, e in m["artifacts"].items():
        assert e["sha256"] and e["status"] == "PRESENT", key


# --- the four required negatives ---------------------------------------------

def test_prepopulated_output_directory_yields_no_evidence(builder, tmp_path):
    """Files present, but no producer ran: nothing may be hashed."""
    m = _manifest(builder, _populate(tmp_path), {})
    assert m["run_completeness"] == "INCOMPLETE"
    for key, e in m["artifacts"].items():
        assert e["sha256"] is None, key
        assert e["producer_outcome"] == "did-not-run", key
        assert e["status"] == "NOT_PRODUCED_THIS_RUN", key
        assert e["file_present_but_disregarded"] is True, key


def test_failed_producer_yields_no_evidence(builder, tmp_path):
    """A failed producer may have left a partial file; it is not evidence."""
    m = _manifest(builder, _populate(tmp_path), _all("failure"))
    assert m["run_completeness"] == "INCOMPLETE"
    assert sorted(m["missing_mandatory_evidence"]) == sorted(m["artifacts"])
    for key, e in m["artifacts"].items():
        assert e["sha256"] is None and e["producer_outcome"] == "failure", key


def test_skipped_producer_yields_no_evidence(builder, tmp_path):
    m = _manifest(builder, _populate(tmp_path), _all("skipped"))
    assert m["run_completeness"] == "INCOMPLETE"
    for key, e in m["artifacts"].items():
        assert e["sha256"] is None and e["producer_outcome"] == "skipped", key


def test_committed_reference_records_are_unreachable(builder, tmp_path):
    """The committed NOT_EXECUTED records must not be hashable as run evidence.

    They live outside the run-scoped evidence directory, so even with every
    producer reporting success the manifest finds nothing.
    """
    assert os.path.isfile(os.path.join(REFERENCE, "container-scan.json"))
    empty = tmp_path / "run-scoped"
    empty.mkdir()
    m = _manifest(builder, empty, _all("success"))
    assert m["run_completeness"] == "INCOMPLETE"
    for key, e in m["artifacts"].items():
        assert e["sha256"] is None, key
        assert e["status"] == "PRODUCER_SUCCEEDED_BUT_ARTIFACT_MISSING", key


def test_a_stale_file_from_an_earlier_run_is_not_evidence(builder, tmp_path):
    """Only the producer's outcome in THIS run admits a file."""
    d = _populate(tmp_path)
    producers = _all("success")
    producers["container-vulnerability-scan"] = "failure"   # stale file remains on disk
    m = _manifest(builder, d, producers)
    e = m["artifacts"]["vuln_report"]
    assert e["sha256"] is None and e["file_present_but_disregarded"] is True
    assert m["run_completeness"] == "INCOMPLETE"
    assert m["missing_mandatory_evidence"] == ["vuln_report"]


# --- provenance and hygiene ---------------------------------------------------

def test_manifest_records_commit_run_attempt_and_producing_step(builder, tmp_path):
    m = _manifest(builder, _populate(tmp_path), _all("success"))
    assert m["source_commit"] == "commit-sha"
    assert m["workflow_run_id"] == "run-1"
    assert m["workflow_run_attempt"] == "attempt-1"
    for key, e in m["artifacts"].items():
        assert e["producer_step"] in ALL_STEPS, key


def test_manifest_marks_no_gate_passed(builder, tmp_path):
    m = _manifest(builder, _populate(tmp_path), _all("success"))
    blob = json.dumps(m).lower()
    assert "passed" not in blob.replace("no container gate is marked passed", "")
    assert "no container gate is marked passed" in m["gate_note"].lower()


def test_runtime_output_directory_is_git_ignored():
    """A run's output must never be committable back into the repository."""
    ignore = open(os.path.join(REPO, "deployment", "governance-studio", ".gitignore"),
                  encoding="utf-8").read()
    assert "artifacts/" in ignore


def test_reference_records_are_kept_not_deleted():
    """The committed records were relocated and labelled, never blindly removed."""
    for name in ("container-scan.json", "secret-scan.json", "sbom.cdx.json",
                 "image-metadata.json", "npm-dependency-audit.json",
                 "python-dependency-audit.json", "runtime-package-inventory.json"):
        assert os.path.isfile(os.path.join(REFERENCE, name)), name
    readme = open(os.path.join(REFERENCE, "README.md"), encoding="utf-8").read()
    assert "evidence produced by any CI run" in readme  # "**not** evidence produced by …"
    # and the runtime directory holds no committed file
    if os.path.isdir(ARTIFACTS):
        assert not [f for f in os.listdir(ARTIFACTS) if not f.startswith(".")]
