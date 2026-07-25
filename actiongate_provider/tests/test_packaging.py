"""Phase 5G — ActionGate distribution guards (fast, deterministic)."""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = REPO / "actiongate_provider"
BUILD = REPO / "packaging" / "dgm-actiongate-provider"
PYPROJECT = BUILD / "pyproject.toml"


def test_single_canonical_source():
    _ignored = {"__pycache__", "packaging", "build", "dist"}
    inits = [p for p in REPO.rglob("actiongate_provider/__init__.py")
             if not (_ignored & set(p.relative_to(REPO).parts))
             and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)]
    assert inits == [CANONICAL / "__init__.py"], inits


def test_build_packages_canonical_via_symlink():
    link = BUILD / "actiongate_provider"
    assert link.is_symlink()
    assert link.resolve() == CANONICAL.resolve()


def test_distribution_metadata_and_dependencies():
    from actiongate_provider.version import __version__
    assert __version__ == "0.1.0"
    text = PYPROJECT.read_text()
    assert 'name = "dgm-actiongate-provider"' in text
    assert 'attr = "actiongate_provider.version.__version__"' in text
    assert 'decision-governance==1.0.0' in text
    assert 'dgm-provider-framework==0.1.0' in text
    # owns no kernel/framework source
    assert "actiongate_provider.tests" in text
    assert 'include = ["actiongate_provider*"]' in text
