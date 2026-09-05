"""Packaging and public-API parity properties."""

from __future__ import annotations

import json
import pathlib
import sys

import ugence_control_plane_root as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
PROJECT = PKG_DIR.parents[1]
PYPROJECT = PROJECT / "pyproject.toml"
PUBLIC_API = PROJECT / "public_api.json"


def test_the_distribution_is_named_and_versioned_exactly():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'name = "ugence-control-plane-root"' in text
    assert PKG_DIR.name == "ugence_control_plane_root" and pkg.__version__ == "0.1.1"


def test_the_public_api_manifest_equals_the_live_package_surface():
    manifest = json.loads(PUBLIC_API.read_text(encoding="utf-8"))
    assert manifest["distribution"] == "ugence-control-plane-root"
    assert manifest["package_version"] == pkg.__version__
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
    assert 'ugence_control_plane_root = ["py.typed"]' in text
    assert "Typing :: Typed" in text and PKG_DIR.parent.name == "src"


def test_no_test_material_lives_inside_the_package_tree():
    for path in PKG_DIR.rglob("*"):
        assert path.name != "conftest.py" and not path.name.startswith("test_"), path


def test_the_readme_and_changelog_state_the_posture():
    readme = (PROJECT / "README.md").read_text(encoding="utf-8").lower()
    assert (PROJECT / "CHANGELOG.md").exists() and (PROJECT / "LICENSE").exists()
    # This package's posture, not a sibling's: it is a root, it stores, it
    # unifies nothing, and it is not the AI Control Plane.
    assert "composition root" in readme
    assert "unifies no" in readme
    assert "not the ai control plane" in readme
    assert "auditreference" in readme
    assert "tamper-evident" in readme and "tamper-proof" in readme
