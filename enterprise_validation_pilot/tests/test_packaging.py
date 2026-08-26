"""Pilot distribution guards (Task 118, fast/deterministic)."""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = REPO / "enterprise_validation_pilot"
BUILD = REPO / "packaging" / "dgm-enterprise-validation-pilot"
PYPROJECT = BUILD / "pyproject.toml"


def test_single_canonical_source():
    _ignored = {"__pycache__", "packaging", "build", "dist"}
    inits = [p for p in REPO.rglob("enterprise_validation_pilot/__init__.py")
             if not (_ignored & set(p.relative_to(REPO).parts))
             and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)]
    assert inits == [CANONICAL / "__init__.py"], inits


def test_build_packages_canonical_via_symlink():
    link = BUILD / "enterprise_validation_pilot"
    assert link.is_symlink()
    assert link.resolve() == CANONICAL.resolve()


def test_distribution_metadata_and_dependencies():
    from enterprise_validation_pilot.version import __version__
    assert __version__ == "0.1.0"
    text = PYPROJECT.read_text()
    assert 'name = "dgm-enterprise-validation-pilot"' in text
    assert 'attr = "enterprise_validation_pilot.version.__version__"' in text
    for dep in ('decision-governance==1.0.0', 'dgm-provider-framework==0.1.0',
                'dgm-actiongate-provider==0.2.0', 'dgm-tap-provider==0.1.0'):
        assert dep in text, dep
    assert 'include = ["enterprise_validation_pilot*"]' in text
    assert "enterprise_validation_pilot.tests" in text  # tests excluded from dist


def test_dataset_is_packaged_as_data():
    text = PYPROJECT.read_text()
    assert '"enterprise_validation_pilot.datasets" = ["*.json"]' in text
    assert (CANONICAL / "datasets" / "enterprise_pilot_v1.json").exists()
