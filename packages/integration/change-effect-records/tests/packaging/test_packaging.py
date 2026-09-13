"""Packaging and public-API parity properties."""

from __future__ import annotations

import json
import pathlib
import sys

import ugence_change_effect_records as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
PROJECT = PKG_DIR.parents[1]
PYPROJECT = PROJECT / "pyproject.toml"
PUBLIC_API = PROJECT / "public_api.json"


def test_the_distribution_is_named_and_versioned_exactly():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'name = "ugence-change-effect-records"' in text
    assert PKG_DIR.name == "ugence_change_effect_records" and pkg.__version__ == "0.1.0"
    assert pkg.CONTRACT_VERSION == "change_effect_records.v1"


def test_the_public_api_manifest_equals_the_live_package_surface():
    manifest = json.loads(PUBLIC_API.read_text(encoding="utf-8"))
    assert manifest["distribution"] == "ugence-change-effect-records"
    assert manifest["namespace"] == "ugence_change_effect_records"
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
    assert 'ugence_change_effect_records = ["py.typed"]' in text
    assert "Typing :: Typed" in text and PKG_DIR.parent.name == "src"


def test_no_test_material_lives_inside_the_package_tree():
    for path in PKG_DIR.rglob("*"):
        assert path.name != "conftest.py" and not path.name.startswith("test_"), path


def test_the_readme_and_changelog_state_the_posture():
    # Whitespace-normalised: a prose assertion must not depend on where a line wraps.
    readme = " ".join(
        (PROJECT / "README.md").read_text(encoding="utf-8").lower().split())
    assert (PROJECT / "CHANGELOG.md").exists() and (PROJECT / "LICENSE").exists()
    assert "never" in readme and "contracts only" in readme

    # The four things the owner's Stage 1 authorization forbids, each named in the README
    # rather than merely avoided in the code.
    for forbidden in ("classifi", "admission boundary", "registers", "policy resolver"):
        assert forbidden in readme, forbidden

    # The rule version these shapes were scoped against, and its standing.
    assert "4.2.10" in readme and "erratum" in readme
    assert "ratifying a design authorizes no operation" in readme

    # What the types deliberately do not do is the point of them.
    assert "compute nothing across records" in readme
    assert "a record is a shape, not a finding, and not a permission" in readme

    changelog = " ".join(
        (PROJECT / "CHANGELOG.md").read_text(encoding="utf-8").lower().split())
    assert "deliberately absent" in changelog


def test_the_thirteen_record_types_are_all_exported_and_all_frozen():
    import dataclasses

    assert len(pkg.RECORD_TYPES) == 13
    for cls in pkg.RECORD_TYPES:
        assert cls.__name__ in pkg.__all__, cls.__name__
        assert dataclasses.is_dataclass(cls) and cls.__dataclass_params__.frozen
