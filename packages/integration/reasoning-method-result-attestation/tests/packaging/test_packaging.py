"""Packaging, public-API parity and the posture the README states."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import zipfile

import pytest

import ugence_reasoning_method_result_attestation as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
PROJECT = PKG_DIR.parents[1]
PYPROJECT = PROJECT / "pyproject.toml"
PUBLIC_API = PROJECT / "public_api.json"


def test_the_distribution_is_named_and_versioned_exactly():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'name = "ugence-reasoning-method-result-attestation"' in text
    assert PKG_DIR.name == "ugence_reasoning_method_result_attestation" and pkg.__version__ == "0.1.0"
    assert pkg.MATURITY == "REFERENCE_GRADE_NOT_PRODUCTION_READY"


def test_the_public_api_manifest_equals_the_live_package_surface():
    manifest = json.loads(PUBLIC_API.read_text(encoding="utf-8"))
    assert manifest["distribution"] == "ugence-reasoning-method-result-attestation"
    assert manifest["namespace"] == "ugence_reasoning_method_result_attestation"
    assert manifest["package_version"] == pkg.__version__
    assert manifest["maturity"] == pkg.MATURITY
    assert sorted(manifest["symbols"]) == sorted(pkg.__all__)
    sys.path.insert(0, str(PROJECT / "scripts"))
    import generate_public_api  # noqa: E402

    assert generate_public_api.build()["symbols"] == manifest["symbols"]


def test_every_exported_symbol_resolves_and_is_unique():
    assert len(pkg.__all__) == len(set(pkg.__all__))
    for symbol in pkg.__all__:
        assert hasattr(pkg, symbol), symbol


def test_py_typed_and_src_layout():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert (PKG_DIR / "py.typed").exists()
    assert 'ugence_reasoning_method_result_attestation = ["py.typed"]' in text
    assert "Typing :: Typed" in text and PKG_DIR.parent.name == "src"


def test_no_test_material_lives_inside_the_package_tree():
    for path in PKG_DIR.rglob("*"):
        assert path.name != "conftest.py" and not path.name.startswith("test_"), path


def test_the_readme_and_changelog_state_the_posture():
    readme = (PROJECT / "README.md").read_text(encoding="utf-8").lower()
    assert (PROJECT / "CHANGELOG.md").exists() and (PROJECT / "LICENSE").exists()
    for phrase in (
        "provenance and integrity",
        "not production-ready",
        "reference-grade",
        "readinesscomparisonresult",
        "not that the comparison is correct",
        "does not run a comparison",
        "no second trust",
        "no key for any comparison engine exists",
        "comparison_result_attestation",
        "imports neither the engine nor the advisor",
    ):
        assert phrase in readme, phrase
    for word in ("audited", "production-ready and", "independently verified"):
        assert word not in readme.replace("not production-ready", ""), word


@pytest.mark.skipif(
    subprocess.run([sys.executable, "-c", "import build"], capture_output=True).returncode != 0,
    reason="the build frontend is not installed",
)
def test_the_wheel_contains_exactly_the_package_and_nothing_from_tests(tmp_path):
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path), str(PROJECT)],
        check=True, capture_output=True,
    )
    wheel = next(tmp_path.glob("*.whl"))
    names = zipfile.ZipFile(wheel).namelist()
    tops = {n.split("/", 1)[0] for n in names if "/" in n}
    assert {t for t in tops if not t.endswith(".dist-info")} == {"ugence_reasoning_method_result_attestation"}
    assert not any(n.startswith("tests/") or "/tests/" in n or n.rsplit("/", 1)[-1].startswith("test_") or "conftest" in n or "_fixtures" in n for n in names), names
    assert "ugence_reasoning_method_result_attestation/py.typed" in names
    shipped = {n.rsplit("/", 1)[-1] for n in names if n.startswith("ugence_reasoning_method_result_attestation/")}
    assert shipped == {
        "__init__.py", "attestation.py", "canonical.py", "errors.py", "identifiers.py",
        "outcomes.py", "py.typed", "roles.py", "signing.py", "trust.py", "verification.py", "version.py",
    }
