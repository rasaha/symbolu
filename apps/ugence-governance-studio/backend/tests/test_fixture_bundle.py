"""P3B packaging protection P2 — three-way bundled-fixture drift protection.

Blocking test proving, for every bundled fixture:

    canonical source hash  ==  backend-packaged hash  ==  recorded manifest hash

covering all bundled scenario manifests, workflows, registries, policies,
expected outputs, replay records and v2 conformance artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os

import ugence_governance_studio_api as pkg
from ugence_governance_studio_api.scenarios.catalog import ScenarioCatalog

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP = os.path.dirname(_BACKEND)
_REPO = os.path.dirname(os.path.dirname(_APP))
_DATA = os.path.join(os.path.dirname(pkg.__file__), "data")
_CONFORMANCE_SRC = os.path.join(
    _REPO, "packages", "capabilities", "agent-workforce-composer",
    "conformance", "governance_studio_v2")


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _bundled_files():
    for dirpath, _dirs, files in os.walk(_DATA):
        for fname in sorted(files):
            if fname == "BUNDLED_FIXTURE_MANIFEST.json" or not fname.endswith(".json"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fname), _DATA).replace(os.sep, "/")
            yield rel, os.path.join(dirpath, fname)


def _source_path(rel: str) -> str:
    if rel.startswith("conformance_v2/"):
        return os.path.join(_CONFORMANCE_SRC, rel[len("conformance_v2/"):])
    return os.path.join(_APP, rel)


def test_recorded_manifest_exists_and_covers_all_categories():
    manifest = ScenarioCatalog().bundled_fixture_manifest()
    assert manifest["schema"] == "governance_studio.bundled_fixture_manifest.v1"
    for category in ("scenario manifests", "workflows", "registries", "policies",
                     "expected outputs", "replay records", "v2 conformance artifacts"):
        assert category in manifest["covers"]
    assert manifest["count"] == len(list(_bundled_files()))


def test_three_way_source_equals_packaged_equals_recorded():
    manifest = ScenarioCatalog().bundled_fixture_manifest()
    recorded = manifest["files"]
    for rel, packaged_path in _bundled_files():
        packaged_hash = _sha(packaged_path)
        # packaged == recorded
        assert rel in recorded, f"{rel} not recorded in bundled manifest"
        assert recorded[rel] == packaged_hash, f"recorded != packaged: {rel}"
        # packaged == canonical source
        src = _source_path(rel)
        assert os.path.isfile(src), f"source missing for {rel}"
        assert _sha(src) == packaged_hash, f"source != packaged: {rel}"


def test_specific_categories_present():
    rels = {rel for rel, _ in _bundled_files()}
    # scenario manifests, workflows, registries, policies, expected outputs, replay records
    assert "demo_data/procurement/scenario_manifest.json" in rels
    assert "demo_data/procurement/compiled_workflow.json" in rels
    assert "demo_data/procurement/agent_registry_snapshot.json" in rels
    assert "demo_data/procurement/eligibility_policy.json" in rels
    assert "expected_outputs/procurement/adaptation.json" in rels
    assert "expected_outputs/procurement/replay_record.json" in rels
    # v2 conformance artifacts
    assert "conformance_v2/procurement/v2_workflow.json" in rels
    assert "conformance_v2/procurement/v1_workflow.json" in rels


def test_ties_to_canonical_p3a_manifest():
    """demo_data + expected_outputs hashes equal the canonical P3A MANIFEST record."""
    with open(os.path.join(_APP, "expected_outputs", "MANIFEST.json"), "r", encoding="utf-8") as fh:
        p3a = json.load(fh)
    recorded = {**p3a.get("inputs", {}), **p3a.get("outputs", {})}
    tied = 0
    for rel, packaged_path in _bundled_files():
        if rel in recorded:
            tied += 1
            assert recorded[rel] == _sha(packaged_path), f"P3A manifest != packaged: {rel}"
    assert tied >= 60  # demo_data inputs + expected_outputs across four scenarios


def test_readiness_detects_bundled_tamper(monkeypatch):
    """Readiness fails if the recorded manifest disagrees with a bundled file."""
    catalog = ScenarioCatalog()
    real = catalog.bundled_fixture_manifest()
    tampered = json.loads(json.dumps(real))
    # corrupt one recorded hash
    first = sorted(tampered["files"])[0]
    tampered["files"][first] = "0" * 64
    monkeypatch.setattr(catalog, "bundled_fixture_manifest", lambda: tampered)
    ok, problems = catalog.verify_bundled_fixture_manifest()
    assert ok is False
    assert any(first in p for p in problems)
