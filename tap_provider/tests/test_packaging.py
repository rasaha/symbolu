"""Phase 5H — TAP distribution guards (fast, deterministic)."""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = REPO / "tap_provider"
BUILD = REPO / "packaging" / "dgm-tap-provider"
PYPROJECT = BUILD / "pyproject.toml"


def test_single_canonical_source():
    _ignored = {"__pycache__", "packaging", "build", "dist"}
    inits = [p for p in REPO.rglob("tap_provider/__init__.py")
             if not (_ignored & set(p.relative_to(REPO).parts))
             and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)]
    assert inits == [CANONICAL / "__init__.py"], inits


def test_build_packages_canonical_via_symlink():
    link = BUILD / "tap_provider"
    assert link.is_symlink()
    assert link.resolve() == CANONICAL.resolve()


def test_distribution_metadata_and_dependencies():
    from tap_provider.version import __version__
    assert __version__ == "0.1.0"
    text = PYPROJECT.read_text()
    assert 'name = "dgm-tap-provider"' in text
    assert 'attr = "tap_provider.version.__version__"' in text
    assert 'decision-governance==1.0.0' in text
    assert 'dgm-provider-framework==0.1.0' in text
    # does NOT depend on ActionGate — peers are independent
    assert 'dgm-actiongate-provider' not in text
    assert 'actiongate_provider' not in text
    # owns no kernel/framework source; excludes its own tests from the dist
    assert 'include = ["tap_provider*"]' in text
    assert "tap_provider.tests" in text
