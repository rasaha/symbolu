"""Platform freeze tooling tests (Task 16)."""
from __future__ import annotations

import copy
import pathlib

import pytest

from platform_freeze import version as V
from platform_freeze.api_snapshot import snapshot_all
from platform_freeze.compat import classify, compare_snapshots, is_compatible
from platform_freeze.dependencies import dependency_report
from platform_freeze.hashing import tree_hash
from platform_freeze.hiring_baseline import discover_hiring
from platform_freeze.invariants import REGISTER, invariants_ok, verify_invariants
from platform_freeze.manifest import build_manifest, load_manifest, verify_manifest
from platform_freeze.classify_change import classify_change
from platform_freeze.verify import run_verification

REPO = pathlib.Path(__file__).resolve().parents[2]


# --- manifest & reproducibility --------------------------------------------

def test_manifest_is_reproducible():
    assert build_manifest()["manifest_digest"] == build_manifest()["manifest_digest"]


def test_stored_manifest_verifies():
    v = verify_manifest(load_manifest())
    assert v["passed"], v
    assert v["manifest_digest_match"]


def test_manifest_has_expected_shape():
    m = load_manifest()
    assert m["platform_version"] == "1.0.0"
    assert set(m["components"]) == set(V.COMPONENT_VERSIONS)
    assert len(m["frozen_invariants"]) == 20
    assert set(m["approved_change_classes"]) == {"PATCH", "MINOR", "MAJOR", "APPLICATION_LOCAL"}


def test_tree_hash_is_stable():
    for t in V.CORE_TREES:
        assert tree_hash(t) == tree_hash(t)


# --- API compatibility ------------------------------------------------------

def test_current_api_is_self_compatible():
    snaps = snapshot_all(V.PUBLIC_API_MODULES)
    assert is_compatible(compare_snapshots(snaps, snaps))


def test_compat_detects_removed_symbol():
    snaps = snapshot_all(V.PUBLIC_API_MODULES)
    broken = copy.deepcopy(snaps)
    mod = V.PUBLIC_API_MODULES[0]
    removed = sorted(broken[mod]["symbols"])[0]
    del broken[mod]["symbols"][removed]
    diffs = compare_snapshots(snaps, broken)
    assert not is_compatible(diffs) and classify(diffs) == "MAJOR"


def test_compat_reports_additive_symbol_as_minor():
    snaps = snapshot_all(V.PUBLIC_API_MODULES)
    added = copy.deepcopy(snaps)
    added[V.PUBLIC_API_MODULES[0]]["symbols"]["BrandNewThing"] = {"kind": "constant", "value": "1"}
    diffs = compare_snapshots(snaps, added)
    assert is_compatible(diffs) and classify(diffs) == "MINOR"


# --- dependency direction & ownership --------------------------------------

def test_dependency_direction_and_ownership_frozen():
    rep = dependency_report()
    assert rep["passed"], rep


def test_version_consistency():
    import actiongate_provider
    import decision_governance
    import governance_providers
    import tap_provider
    assert decision_governance.__version__ == "1.0.0"
    assert governance_providers.__version__ == "0.1.0"
    assert actiongate_provider.__version__ == "0.2.0"
    assert tap_provider.__version__ == "0.1.0"


# --- invariants -------------------------------------------------------------

def test_invariant_register_complete():
    assert len(REGISTER) == 20
    ids = [i.id for i in REGISTER]
    assert ids == [f"F{n}" for n in range(1, 21)]
    assert all(i.authoritative_test for i in REGISTER)


def test_invariants_verify():
    results = verify_invariants()
    assert invariants_ok(results), [r for r in results if r["status"] not in ("VERIFIED", "REFERENCED")]
    assert sum(1 for r in results if r["status"] == "VERIFIED") >= 10


# --- change classification --------------------------------------------------

def test_classify_change_docs_only_is_not_major():
    result = classify_change("HEAD", "HEAD")   # no diff → PATCH
    assert result["proposed_classification"] == "PATCH"
    assert not result["requires_approval"]


def test_classify_change_reports_evidence():
    result = classify_change(V.FREEZE_COMMIT, "HEAD")
    assert "api_classification" in result and "dependency_violations" in result
    assert result["proposed_classification"] in ("PATCH", "MINOR", "APPLICATION_LOCAL")


# --- full verification ------------------------------------------------------

def test_full_verification_passes_and_is_reproducible():
    r1 = run_verification()
    r2 = run_verification()
    assert r1["passed"], r1["checks"]
    assert r1["substantive_digest"] == r2["substantive_digest"]


# --- AI hiring baseline discovery + docs -----------------------------------

def test_hiring_baseline_discovery():
    d = discover_hiring()
    assert d["present"]["ai_hiring"] and d["present"]["domains/hiring"]
    assert d["present"]["applications/ai_hiring"]
    assert d["uses_dgm_kernel"] is True
    # documented finding: hiring does not yet use the provider framework
    assert d["uses_provider_framework"] is False


def test_documentation_completeness():
    for name in ("PLATFORM_OVERVIEW", "ARCHITECTURE_INVARIANTS", "PUBLIC_API_POLICY",
                 "VERSIONING_POLICY", "COMPATIBILITY_POLICY", "PROVIDER_DEVELOPMENT_GUIDE",
                 "MAINTENANCE_POLICY", "SECURITY_BOUNDARIES", "MIGRATION_POLICY",
                 "AI_HIRING_INTEGRATION_GUIDE"):
        assert (REPO / "docs" / "platform-v1" / f"{name}.md").exists(), name
    for name in ("AI_HIRING_REENTRY_BASELINE", "PLATFORM_BOUNDARY",
                 "AI_HIRING_COMPLETION_ROADMAP"):
        assert (REPO / "docs" / "ai-hiring" / f"{name}.md").exists(), name
    assert (REPO / "CHANGELOG_PLATFORM_V1.md").exists()


def test_platform_boundary_and_gap_docs_have_content():
    boundary = (REPO / "docs" / "ai-hiring" / "PLATFORM_BOUNDARY.md").read_text()
    for owner in ("AI Hiring", "DGM", "TAP", "ActionGate", "External systems"):
        assert owner in boundary
    roadmap = (REPO / "docs" / "ai-hiring" / "AI_HIRING_COMPLETION_ROADMAP.md").read_text()
    for cap in ("Job requisition", "Offer authorization", "Audit reconstruction"):
        assert cap in roadmap
    for phase in ("H1", "H2", "H3", "H4", "H5", "H6"):
        assert phase in roadmap


def test_freeze_tooling_not_imported_by_platform():
    rep = dependency_report()
    assert not any("platform_freeze" in v.get("imported", "")
                   for v in rep["dependency_violations"])
