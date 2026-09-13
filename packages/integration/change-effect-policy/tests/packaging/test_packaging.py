"""Packaging and public-API parity properties."""

from __future__ import annotations

import json
import pathlib

import ugence_change_effect_policy as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
PROJECT = PKG_DIR.parents[1]
PYPROJECT = PROJECT / "pyproject.toml"
PUBLIC_API = PROJECT / "public_api.json"


def test_the_distribution_is_named_and_versioned_exactly():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'name = "ugence-change-effect-policy"' in text
    assert PKG_DIR.name == "ugence_change_effect_policy" and pkg.__version__ == "0.1.0"
    assert pkg.CONTRACT_VERSION == "change_effect_policy.v1"


def _this_packages_generator():
    """Load *this* package's generator by path, not by module name.

    Seventeen packages ship ``scripts/generate_public_api.py`` and their packaging tests
    reach it with ``sys.path.insert`` plus ``import generate_public_api``. That module
    name is global: in a combined multi-package run the first import wins and every later
    package compares its own manifest against **a sibling's** generator. The failure is
    pre-existing and reproduces between two untouched packages, so it is reported rather
    than fixed across the repository here — but this package's own test must not be
    answerable by whichever sibling happened to import first, so it loads its generator
    from the file it means.
    """

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ugence_change_effect_policy_generate_public_api",
        PROJECT / "scripts" / "generate_public_api.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_public_api_manifest_equals_the_live_package_surface():
    manifest = json.loads(PUBLIC_API.read_text(encoding="utf-8"))
    assert manifest["distribution"] == "ugence-change-effect-policy"
    assert manifest["namespace"] == "ugence_change_effect_policy"
    assert manifest["package_version"] == pkg.__version__
    assert sorted(manifest["symbols"]) == sorted(pkg.__all__)
    assert _this_packages_generator().build()["symbols"] == manifest["symbols"]


def test_every_exported_symbol_resolves_and_is_unique():
    assert len(pkg.__all__) == len(set(pkg.__all__))
    for symbol in pkg.__all__:
        assert hasattr(pkg, symbol), symbol


def test_py_typed_and_src_layout():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert (PKG_DIR / "py.typed").exists()
    assert 'ugence_change_effect_policy = ["py.typed"]' in text
    assert "Typing :: Typed" in text and PKG_DIR.parent.name == "src"


def test_the_single_declared_dependency_is_the_policy_authority():
    """One first-party dependency, and specifically not the record graph or the ledger."""

    text = PYPROJECT.read_text(encoding="utf-8")
    block = text.split("dependencies = [", 1)[1].split("]", 1)[0]
    declared = [
        line.strip().strip('",')
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert declared == ["ugence-policy-authority>=0.1.0"]

    # Asserted over the *declared* list, not over the file text: the comment block above
    # names both exclusions on purpose, so a text search would flag the documentation of
    # the exclusion as the exclusion being violated.
    joined = " ".join(declared)
    assert "change-effect-records" not in joined
    assert "control-plane-root" not in joined
    # And the exclusions stay documented where a packager will read them.
    assert "ugence-change-effect-records" in text and "ugence-control-plane-root" in text


def test_no_test_material_lives_inside_the_package_tree():
    for path in PKG_DIR.rglob("*"):
        assert path.name != "conftest.py" and not path.name.startswith("test_"), path


def test_the_readme_and_changelog_state_the_posture():
    # Whitespace-normalised: a prose assertion must not depend on where a line wraps.
    readme = " ".join((PROJECT / "README.md").read_text(encoding="utf-8").lower().split())
    assert (PROJECT / "CHANGELOG.md").exists() and (PROJECT / "LICENSE").exists()
    assert "never" in readme and "contracts only" in readme

    # The distinction ruling 8 required the documents to draw, stated in the README
    # rather than only held in the code.
    assert "separately governed" in readme and "deferred out of stage 1" in readme
    assert "a policy artifact is not a permission" in readme

    # The inertness condition, named as such so it is not read as runtime behaviour.
    assert "inertness condition, not invented behaviour" in readme
    assert "construction-time type refusals" in readme

    # The rule version this artifact's membership was ruled against.
    assert "4.2.10" in readme and "erratum" in readme

    changelog = " ".join(
        (PROJECT / "CHANGELOG.md").read_text(encoding="utf-8").lower().split()
    )
    assert "deliberately not added" in changelog


def test_the_maturity_constants_are_exported_so_a_consumer_can_read_the_posture():
    assert pkg.MATURITY == "REFERENCE_GRADE_CONTRACT_ONLY"
    assert pkg.ENFORCEMENT_ENABLED is False
    assert "4.2.10" in pkg.RULE_VERSION
