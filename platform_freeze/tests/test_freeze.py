"""Platform freeze tooling tests (Task 16)."""
from __future__ import annotations

import copy
import json
import pathlib
import subprocess

import pytest

from platform_freeze import version as V
from platform_freeze.api_snapshot import snapshot_all
from platform_freeze.compat import classify, compare_snapshots, is_compatible
from platform_freeze.dependencies import dependency_report
from platform_freeze.hashing import (
    TrackedFilesUnavailable,
    _tracked,
    tree_hash,
    tree_manifest,
)
from platform_freeze.hiring_baseline import discover_hiring
from platform_freeze.invariants import REGISTER, invariants_ok, verify_invariants
from platform_freeze.manifest import (
    MANIFEST_PATH,
    build_manifest,
    load_manifest,
    verify_manifest,
)
from platform_freeze.classify_change import classify_change
from platform_freeze.verify import main as verify_main, run_verification

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


def test_tree_hash_ignores_untracked_build_output():
    """The property the tracked-files scoping exists to deliver.

    ``python -m build`` leaves a ``build/lib/…`` copy of every module beside the source.
    A directory walk cannot tell those apart from source, so a digest computed after a
    build did not reproduce on a clean checkout — and the mismatch looked exactly like
    tampering. On a package tree that is 10 of 46 files, and 78 of 214, so this is not a
    rounding error.

    The artefact is planted inside a genuinely frozen tree rather than a synthetic one,
    because ``tree_hash`` resolves paths against the real repository root and a fixture
    that avoided that would prove nothing about the function as called.
    """

    tree = REPO / V.CORE_TREES[0]
    before = tree_hash(V.CORE_TREES[0])
    planted = tree / "build" / "lib" / "planted_by_a_build.py"
    assert not planted.exists(), "the fixture must not collide with real content"

    try:
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text("SHOULD_NOT_BE_HASHED = True\n", encoding="utf-8")
        _tracked.cache_clear()  # tracked-ness is cached per run; this plants a new file
        assert tree_hash(V.CORE_TREES[0]) == before, (
            "an untracked build artefact changed the tree hash")
        assert tree_manifest(V.CORE_TREES[0])["files"].get(
            "build/lib/planted_by_a_build.py") is None
    finally:
        planted.unlink(missing_ok=True)
        for parent in (planted.parent, planted.parent.parent):
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        _tracked.cache_clear()

    assert tree_hash(V.CORE_TREES[0]) == before, "the fixture did not clean up after itself"


def _plant(tree, rel, body="PLANTED = True\n"):
    """Create an untracked file under a frozen tree; caller removes it."""

    target = tree / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    _tracked.cache_clear()
    return target


def _unplant(target, tree):
    target.unlink(missing_ok=True)
    for parent in sorted(target.parents, key=lambda q: -len(q.parts)):
        if parent == tree:
            break
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    _tracked.cache_clear()


@pytest.mark.parametrize("rel", [
    "build/lib/from_a_build.py",
    "src.egg-info/from_packaging.py",
    "an_untracked_module.py",
])
def test_untracked_python_never_enters_the_v1_digest(rel):
    """V1 is defined over the tracked tree. Three shapes of untracked ``.py``, none count.

    ``build/`` and ``egg-info/`` are what ``python -m build`` leaves behind; a bare
    untracked module is what a work-in-progress file looks like. A directory walk could
    tell none of them from source, which is why a digest taken after a build did not
    reproduce on a clean checkout.
    """

    name = V.CORE_TREES[0]
    tree = REPO / name
    before = tree_hash(name)
    planted = _plant(tree, rel)
    try:
        assert tree_hash(name) == before, f"untracked {rel} changed the digest"
        assert rel not in tree_manifest(name)["files"]
    finally:
        _unplant(planted, tree)
    assert tree_hash(name) == before, "the fixture did not clean up after itself"


def test_a_tracked_python_change_does_move_the_digest(tmp_path):
    """The other half: V1 must still notice what it is supposed to notice.

    Addition, modification and deletion of a *tracked* ``.py`` each move the value. Without
    this, an implementation that returned a constant would satisfy every exclusion test
    above.
    """

    name = V.CORE_TREES[0]
    tree = REPO / name
    tracked_py = sorted(
        p for p in tree.rglob("*.py")
        if "__pycache__" not in p.parts
    )
    assert tracked_py, "fixture assumption: the frozen tree has tracked python"
    victim = tracked_py[0]
    original = victim.read_bytes()
    before = tree_hash(name)

    try:
        victim.write_bytes(original + b"\n# modified\n")
        _tracked.cache_clear()
        assert tree_hash(name) != before, "a tracked modification must move the digest"

        victim.unlink()
        _tracked.cache_clear()
        assert tree_hash(name) != before, "a tracked deletion must move the digest"
    finally:
        victim.write_bytes(original)
        _tracked.cache_clear()

    assert tree_hash(name) == before, "the fixture did not restore the tree"


def test_tracked_non_python_is_outside_v1_by_design():
    """V1's scope is tracked ``*.py`` — not "every tracked file".

    Widening is a different algorithm needing its own name, version and an owner ruling
    that the tree is permanently frozen; it is not a setting on this one. Asserted so the
    boundary is a decision on the record rather than an artefact of the implementation.

    Two ways, because neither alone is enough. The structural half holds for every frozen
    tree and cannot skip. The concrete half needs a tree that actually tracks a
    non-Python file — none of the four core trees does, so it uses a behaviour tree, and
    without it the structural assertion would be satisfied by a tree that simply had
    nothing else to exclude.
    """

    for name in list(V.CORE_TREES) + list(V.BEHAVIOUR_TREES):
        stray = [f for f in tree_manifest(name)["files"] if not f.endswith(".py")]
        assert stray == [], f"{name}: V1 covered non-python {stray}"

    witness = "enterprise_validation_pilot"
    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "--", witness],
        capture_output=True, text=True, check=True).stdout.split()
    non_python = [f for f in tracked if not f.endswith(".py")]
    assert non_python, (
        f"fixture assumption: {witness} tracks a non-python file to exclude")

    covered = tree_manifest(witness)["files"]
    for rel in non_python:
        assert str(pathlib.Path(rel).relative_to(witness)) not in covered, (
            f"{rel} is tracked and non-python; V1 must not cover it")


def test_tree_hash_fails_loudly_when_tracked_files_cannot_be_listed(monkeypatch):
    """No git means failure, not a quieter answer.

    A directory-walk fallback would return a *different* digest under the same name —
    silently wrong rather than loudly absent, and indistinguishable from a real mismatch.
    """

    def _no_git(*_args, **_kwargs):
        raise OSError("git not found")

    _tracked.cache_clear()
    monkeypatch.setattr("platform_freeze.hashing.subprocess.run", _no_git)
    try:
        with pytest.raises(TrackedFilesUnavailable):
            tree_hash(V.CORE_TREES[0])
    finally:
        _tracked.cache_clear()


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
    assert actiongate_provider.__version__ == "0.1.0"
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


# --- behaviour-tree verification: the negative controls ---------------------
#
# The three behaviour hashes were written into the manifest from the day it was added and
# never compared against anything. Nothing in the tooling could have told a correct value
# from a wrong one, which is why the imported values sat drifted and the freeze stayed
# green over them. ``verify_manifest`` now requires the expected key set exactly, and the
# four ways that requirement can be violated are asserted below.
#
# Each is asserted on *both* surfaces the freeze is read through: ``verify_manifest``
# against the stored manifest, and the ``platform_freeze.verify`` CLI. Agreement between
# them is the property, not an implementation detail — the CLI reports its own check list,
# and a check that reaches only one of the two is a check half the readers never see.


def _cli(tmp_path, manifest_path=None) -> int:
    """The CLI's exit code, with reports written somewhere disposable."""

    argv = ["--output", str(tmp_path / "reports")]
    if manifest_path is not None:
        argv += ["--manifest", str(manifest_path)]
    return verify_main(argv)


def _manifest_with(tmp_path, mutate) -> tuple[dict, pathlib.Path]:
    """The stored manifest, mutated in memory and on disk. The real one is untouched."""

    stored = load_manifest()
    mutate(stored)
    path = tmp_path / "MUTATED_PLATFORM_FREEZE_V1.json"
    path.write_text(json.dumps(stored, indent=2, sort_keys=True) + "\n")
    return stored, path


def _behaviour(result: dict) -> dict:
    return result["checks"]["behaviour_tree_hashes"]


@pytest.mark.parametrize("tree", V.BEHAVIOUR_TREES)
def test_a_tracked_behaviour_file_modification_fails_both_surfaces(tmp_path, tree, capsys):
    """The case the freeze exists for: someone edits a frozen behaviour tree.

    A comment is appended rather than code changed, so the only thing under test is the
    digest — nothing that could fail for an unrelated reason such as an import error.
    """

    victim = sorted(
        REPO / rel for rel in subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "--", tree],
            capture_output=True, text=True, check=True).stdout.split()
        if rel.endswith(".py")
    )[0]
    original = victim.read_bytes()

    try:
        victim.write_bytes(original + b"\n# negative control\n")
        _tracked.cache_clear()

        stored = verify_manifest(load_manifest())
        assert not stored["passed"]
        assert _behaviour(stored)["mismatched_keys"] == [tree], _behaviour(stored)
        assert _behaviour(stored)["missing_keys"] == []
        assert _behaviour(stored)["extra_keys"] == []

        assert _cli(tmp_path) == 1
        assert f"FAIL manifest:behaviour_tree_hashes" in capsys.readouterr().out
    finally:
        victim.write_bytes(original)
        _tracked.cache_clear()

    assert verify_manifest(load_manifest())["passed"], "the fixture did not restore the tree"


def test_a_missing_behaviour_key_fails_both_surfaces(tmp_path, capsys):
    """Dropping a key is a coverage regression, and plain equality would call it "not equal".

    This is the failure that most needs naming: a key silently removed from the manifest
    removes the tree from the freeze entirely, and without an expected key set there is
    nothing left to notice its absence.
    """

    dropped = V.BEHAVIOUR_TREES[0]
    stored, path = _manifest_with(
        tmp_path, lambda m: m["behaviour_tree_hashes"].pop(dropped))

    result = verify_manifest(stored)
    assert not result["passed"]
    assert _behaviour(result)["missing_keys"] == [dropped], _behaviour(result)
    assert _behaviour(result)["mismatched_keys"] == []

    assert _cli(tmp_path, path) == 1
    out = capsys.readouterr().out
    assert "FAIL manifest:behaviour_tree_hashes" in out
    assert f"behaviour_tree_hashes.missing_keys: {dropped}" in out


def test_an_extra_behaviour_key_fails_both_surfaces(tmp_path, capsys):
    """A key nobody ratified is an unauthorized widening of the freeze, not a bonus."""

    stored, path = _manifest_with(
        tmp_path,
        lambda m: m["behaviour_tree_hashes"].update({"unratified_tree": "0" * 64}))

    result = verify_manifest(stored)
    assert not result["passed"]
    assert _behaviour(result)["extra_keys"] == ["unratified_tree"], _behaviour(result)
    assert _behaviour(result)["missing_keys"] == []
    assert _behaviour(result)["mismatched_keys"] == []

    assert _cli(tmp_path, path) == 1
    out = capsys.readouterr().out
    assert "FAIL manifest:behaviour_tree_hashes" in out
    assert "behaviour_tree_hashes.extra_keys: unratified_tree" in out


def test_an_incorrect_behaviour_digest_fails_both_surfaces(tmp_path, capsys):
    """A wrong value must fail even though the key set is perfect.

    Without this, an implementation that compared only key sets would satisfy the three
    tests above — and that is precisely the shape of the defect being corrected, where the
    keys were present and the values were not the tree's.
    """

    wrong = V.BEHAVIOUR_TREES[-1]
    stored, path = _manifest_with(
        tmp_path, lambda m: m["behaviour_tree_hashes"].update({wrong: "f" * 64}))

    result = verify_manifest(stored)
    assert not result["passed"]
    assert _behaviour(result)["mismatched_keys"] == [wrong], _behaviour(result)
    assert _behaviour(result)["missing_keys"] == []
    assert _behaviour(result)["extra_keys"] == []

    assert _cli(tmp_path, path) == 1
    out = capsys.readouterr().out
    assert "FAIL manifest:behaviour_tree_hashes" in out
    assert f"behaviour_tree_hashes.mismatched_keys: {wrong}" in out


def test_the_two_surfaces_agree_on_the_unmutated_repository(tmp_path):
    """Both green together, so the four tests above are not measuring a permanent red."""

    assert verify_manifest(load_manifest())["passed"]
    assert _cli(tmp_path) == 0
    assert MANIFEST_PATH.exists()


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
