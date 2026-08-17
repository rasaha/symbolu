"""A stale ``build/lib`` tree cannot contaminate a freshly built wheel.

``python -m build`` reuses ``build/lib`` across runs, so a module **deleted from
source** survives there and is silently copied back into the next wheel. That is
not hypothetical: during the ADR §20 move of ``AssessedSystemBinding`` an
untracked ``build/lib`` resurrected the deleted pre-move module into a wheel, so
a second definition of a contract this package is the single canonical owner of
was one build away from shipping.

The defense is one line of posture — remove the package-local ``build/`` tree
immediately before building — and this test is its proof. It runs end to end in
a **temporary copy** of the package:

1. seed a fake deleted module (``contracts/binding.py``) carrying a duplicate
   ``AssessedSystemBinding`` definition under ``build/lib``;
2. build *without* the cleanup and show the stale artifact really does reach the
   wheel — the defect is demonstrated, not assumed;
3. run the hardened cleanup;
4. prove the stale tree is gone before the build;
5. build again and inspect the completed **wheel**, not the source tree;
6. confirm the stale member is absent and exactly one ``AssessedSystemBinding``
   definition exists in the distribution.

Nothing is written inside the repository: the working tree's own ``build/``
directory is never created, touched or removed by this test.
"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil
import subprocess
import sys
import zipfile

import pytest

# packages/governance-contracts/tests/packaging/ -> packages/governance-contracts/
PKG_ROOT = pathlib.Path(__file__).resolve().parents[2]
VERIFIER = PKG_ROOT / "verify_governance_contracts_distribution.py"

STALE_MODULE = "ugence_governance_contracts/contracts/binding.py"
STALE_SOURCE = '''"""Pre-move module, deleted from source by the ADR §20 relocation."""

class AssessedSystemBinding:  # a duplicate definition that must never ship
    pass


class SystemBindingAuthenticityStatus:
    pass
'''

_BUILD_AVAILABLE = importlib.util.find_spec("build") is not None
requires_build = pytest.mark.skipif(
    not _BUILD_AVAILABLE, reason="the `build` package is not installed"
)


def _load_verifier(pkg_root: pathlib.Path):
    """Import the verifier module with ``PKG`` rebound to a temporary copy.

    The verifier resolves its target from ``__file__``, so loading the *copy*
    is what makes the cleanup operate on the copy — the real package is never a
    candidate for deletion in this test.
    """

    path = pkg_root / VERIFIER.name
    spec = importlib.util.spec_from_file_location(f"_verifier_{pkg_root.name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.PKG == pkg_root, (module.PKG, pkg_root)
    return module


def _copy_package(dest: pathlib.Path) -> pathlib.Path:
    """A standalone copy of the distribution: sources, metadata and verifier."""

    pkg = dest / "governance-contracts"
    shutil.copytree(
        PKG_ROOT,
        pkg,
        ignore=shutil.ignore_patterns(
            "__pycache__", "build", "dist", "_dist_wheels", "*.egg-info"
        ),
    )
    return pkg


def _seed_stale_build_tree(pkg: pathlib.Path) -> pathlib.Path:
    """Plant the deleted module in ``build/lib``, exactly as a real build would."""

    stale = pkg / "build" / "lib" / STALE_MODULE
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text(STALE_SOURCE)
    # ``build/lib`` must otherwise mirror the package, or setuptools discards it.
    src = pkg / "src" / "ugence_governance_contracts"
    for path in src.rglob("*"):
        if "__pycache__" in path.parts:
            continue
        target = pkg / "build" / "lib" / path.relative_to(pkg / "src")
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    return stale


def _build_wheel(pkg: pathlib.Path, out: pathlib.Path) -> pathlib.Path:
    # Isolation is deliberate: it is what the verifier itself uses, and the
    # system setuptools on some distributions cannot build in-process.
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", str(pkg), "-o", str(out)],
        check=True,
        capture_output=True,
    )
    wheels = sorted(out.glob("ugence_governance_contracts-*.whl"))
    assert wheels, f"no wheel produced in {out}"
    return wheels[-1]


def _members(wheel: pathlib.Path) -> set[str]:
    with zipfile.ZipFile(wheel) as z:
        return set(z.namelist())


def _binding_definition_sites(wheel: pathlib.Path) -> list[str]:
    sites = []
    with zipfile.ZipFile(wheel) as z:
        for member in sorted(z.namelist()):
            if member.endswith(".py") and "class AssessedSystemBinding" in (
                z.read(member).decode("utf-8")
            ):
                sites.append(member)
    return sites


# --------------------------------------------------------------------------- #
# The cleanup target is exact, and narrow
# --------------------------------------------------------------------------- #
def test_the_cleanup_target_is_the_package_local_build_directory():
    verifier = _load_verifier(PKG_ROOT)
    target = verifier.stale_build_tree()
    assert target == PKG_ROOT / "build"
    assert target.parent == PKG_ROOT
    assert target.name == "build"
    # Not the repository root, not a parent, not the source or test trees.
    for protected in (PKG_ROOT / "src", PKG_ROOT / "tests", PKG_ROOT.parent, PKG_ROOT):
        assert target != protected.resolve()


def test_the_cleanup_is_a_no_op_when_no_build_tree_exists(tmp_path):
    pkg = _copy_package(tmp_path)
    verifier = _load_verifier(pkg)
    assert not (pkg / "build").exists()
    assert verifier.remove_stale_build_tree() is False
    # Source, tests and metadata are all still there.
    assert (pkg / "src" / "ugence_governance_contracts" / "__init__.py").is_file()
    assert (pkg / "tests").is_dir()
    assert (pkg / "pyproject.toml").is_file()


def test_the_cleanup_refuses_a_symlinked_build_tree(tmp_path):
    """A symlink must never be followed into somebody else's directory."""

    pkg = _copy_package(tmp_path)
    elsewhere = tmp_path / "not-the-package"
    elsewhere.mkdir()
    (elsewhere / "keep.txt").write_text("user file")
    try:
        (pkg / "build").symlink_to(elsewhere, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - platform dependent
        pytest.skip("symlinks unavailable on this platform")

    verifier = _load_verifier(pkg)
    with pytest.raises(AssertionError, match="symlink"):
        verifier.remove_stale_build_tree()
    assert (elsewhere / "keep.txt").is_file(), "the symlink target was followed"


def test_the_cleanup_removes_only_the_build_tree(tmp_path):
    pkg = _copy_package(tmp_path)
    _seed_stale_build_tree(pkg)
    before = {
        p.relative_to(pkg)
        for p in pkg.rglob("*")
        if "build" not in p.relative_to(pkg).parts and "__pycache__" not in p.parts
    }

    verifier = _load_verifier(pkg)
    assert verifier.remove_stale_build_tree() is True
    assert not (pkg / "build").exists()

    after = {
        p.relative_to(pkg)
        for p in pkg.rglob("*")
        if "build" not in p.relative_to(pkg).parts and "__pycache__" not in p.parts
    }
    assert after == before


# --------------------------------------------------------------------------- #
# The seeded end-to-end proof
# --------------------------------------------------------------------------- #
@requires_build
def test_an_unclean_build_really_does_ship_the_stale_module(tmp_path):
    """Step 2 — demonstrate the defect the cleanup exists to prevent.

    Without this, the hardened result below would prove nothing: a wheel that
    never contained the stale member would pass either way.
    """

    pkg = _copy_package(tmp_path)
    _seed_stale_build_tree(pkg)
    wheel = _build_wheel(pkg, tmp_path / "unclean")

    assert STALE_MODULE in _members(wheel), (
        "the stale build tree did not contaminate the wheel, so this test no "
        "longer demonstrates the defect it was written for"
    )
    assert sorted(_binding_definition_sites(wheel)) == [
        STALE_MODULE,
        "ugence_governance_contracts/contracts/system_identity.py",
    ]


@requires_build
def test_the_hardened_verifier_removes_the_stale_tree_before_building(tmp_path):
    """Steps 3-6 — cleanup, proof of removal, rebuild, wheel inspection."""

    pkg = _copy_package(tmp_path)
    stale = _seed_stale_build_tree(pkg)
    assert stale.is_file()

    verifier = _load_verifier(pkg)

    # 3 + 4: the hardened cleanup runs and the stale tree is gone *before* build.
    assert verifier.remove_stale_build_tree() is True
    assert not (pkg / "build").exists()
    assert not stale.exists()
    assert not verifier.stale_build_tree().exists()

    # 5: build, then inspect the completed wheel rather than the source tree.
    wheel = _build_wheel(pkg, tmp_path / "clean")
    members = _members(wheel)

    # 6: the stale member is absent and exactly one definition exists.
    assert STALE_MODULE not in members
    assert not [m for m in members if m.endswith("/binding.py")]
    assert _binding_definition_sites(wheel) == [
        "ugence_governance_contracts/contracts/system_identity.py"
    ]
    assert len(_binding_definition_sites(wheel)) == 1


@requires_build
def test_the_installed_distribution_holds_exactly_one_binding_definition(tmp_path):
    """The wheel installs to exactly one module defining the contract."""

    pkg = _copy_package(tmp_path)
    _seed_stale_build_tree(pkg)
    _load_verifier(pkg).remove_stale_build_tree()
    wheel = _build_wheel(pkg, tmp_path / "install")

    site = tmp_path / "site"
    with zipfile.ZipFile(wheel) as z:
        z.extractall(site)

    installed = site / "ugence_governance_contracts"
    definitions = [
        path.relative_to(site).as_posix()
        for path in sorted(installed.rglob("*.py"))
        if "class AssessedSystemBinding" in path.read_text()
    ]
    assert definitions == ["ugence_governance_contracts/contracts/system_identity.py"]
    assert not (installed / "contracts" / "binding.py").exists()


def _package_entries() -> set[str]:
    return {p.name for p in PKG_ROOT.iterdir()}


@pytest.fixture(scope="module", autouse=True)
def working_tree_is_untouched():
    """Every test in this module operates only on temporary copies.

    Snapshotted rather than asserted absolutely: running the distribution
    verifier by hand legitimately leaves a ``build/`` tree behind, and that is
    not this module's doing. What must hold is that *these* tests add nothing —
    so the package directory is compared against itself, before and after.
    """

    before = _package_entries()
    yield
    added = _package_entries() - before
    assert not added, f"this test module left generated entries behind: {sorted(added)}"


def test_this_module_builds_only_inside_temporary_directories(tmp_path):
    """The seeded builds land in pytest's tmp_path, never in the package."""

    pkg = _copy_package(tmp_path)
    assert tmp_path in pkg.parents
    verifier = _load_verifier(pkg)
    # The copy's cleanup target is inside the copy, so the real package root can
    # never be the thing removed.
    assert tmp_path in verifier.stale_build_tree().parents
    assert PKG_ROOT not in verifier.stale_build_tree().parents
