"""Distribution-level guarantees: metadata, wheel contents and the leaf direction."""

from __future__ import annotations

import pathlib
import re

import pytest

import ugence_cloud_scaling_authorization_contracts as pkg

SRC = pathlib.Path(pkg.__file__).resolve().parent
PROJECT = SRC.parents[1]
PYPROJECT = (PROJECT / "pyproject.toml").read_text(encoding="utf-8")


def test_version_is_the_declared_version():
    """``0.2.0`` since 5B-1: the candidate gained a required field and its digest moved.

    Pre-1.0, that is a minor bump, and the digest is a value two merged packages pin — so a
    version that stayed put would be telling a consumer nothing changed while the artifact
    they pin changed shape.
    """

    assert pkg.__version__ == "0.2.0"


def test_distribution_and_namespace_names():
    assert 'name = "ugence-cloud-scaling-authorization-contracts"' in PYPROJECT
    assert pkg.__name__ == "ugence_cloud_scaling_authorization_contracts"


def test_py_typed_is_present_and_declared():
    assert (SRC / "py.typed").exists()
    assert "py.typed" in PYPROJECT


def test_exactly_three_first_party_dependencies():
    block = PYPROJECT.split("dependencies = [", 1)[1].split("]", 1)[0]
    declared = re.findall(r'"([^"]+)"', block)
    assert sorted(d.split(">=")[0] for d in declared) == [
        "ugence-cloud-scaling-controller",
        "ugence-cloud-scaling-risk-integration",
        "ugence-risk-authority",
    ]


def test_no_third_party_runtime_dependency_is_added():
    block = PYPROJECT.split("dependencies = [", 1)[1].split("]", 1)[0]
    for forbidden in ("cryptography", "pynacl", "boto3", "kubernetes", "requests",
                      "pydantic", "numpy"):
        assert forbidden not in block


def test_public_api_is_exactly_the_declared_surface():
    assert len(pkg.__all__) == len(set(pkg.__all__)), "duplicate export"
    for symbol in pkg.__all__:
        assert hasattr(pkg, symbol), f"{symbol} is exported but absent"
    # Nothing public leaks that is not declared. Submodule names are reachable as an
    # unavoidable consequence of the import machinery, and ``annotations`` is the
    # ``from __future__`` flag object — neither is an exported contract.
    public = {n for n in dir(pkg) if not n.startswith("_")}
    submodules = {
        "attestation", "candidate", "canonical", "errors", "identifiers",
        "reconciliation", "target", "trust", "version",
    }
    declared = {n for n in pkg.__all__ if not n.startswith("_")}
    assert public - submodules - {"annotations"} == declared
    # ``__version__`` is dunder-named and so is excluded from ``public`` above; assert it
    # separately rather than letting it slip out of the parity check entirely.
    assert "__version__" in pkg.__all__ and hasattr(pkg, "__version__")


def test_no_test_material_lives_inside_the_package_source():
    for path in SRC.rglob("*"):
        assert path.name != "conftest.py", f"{path} would ship in the wheel"
        assert not path.name.startswith("test_"), f"{path} would ship in the wheel"
        assert path.name != "tests", f"{path} would ship in the wheel"


def test_setuptools_only_finds_the_one_namespace():
    assert 'include = ["ugence_cloud_scaling_authorization_contracts*"]' in PYPROJECT
    assert 'where = ["src"]' in PYPROJECT


def test_readme_exists_and_states_the_boundary():
    readme = (PROJECT / "README.md").read_text(encoding="utf-8")
    assert "candidate grants nothing" in readme.lower()
    for phrase in ("PRESENT_BUT_NOT_TRUST_VERIFIED", "Phase 5B", "5X"):
        assert phrase in readme
