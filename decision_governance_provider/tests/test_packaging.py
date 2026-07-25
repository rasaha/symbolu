"""Phase 5F — provider-framework independent-distribution guards (fast).

The framework ships as its own ``decision-governance-provider`` distribution that
depends on the kernel distribution. These guard against source drift and config
regressions; the deep isolated-install proof is exercised separately (a clean
venv installs both wheels and runs the provider conformance kit).
"""

from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = REPO / "decision_governance_provider"
BUILD = REPO / "packaging" / "decision-governance-provider"
PYPROJECT = BUILD / "pyproject.toml"


def test_single_canonical_framework_source():
    _ignored = {"__pycache__", "packaging", "build", "dist"}
    inits = [
        p for p in REPO.rglob("decision_governance_provider/__init__.py")
        if not (_ignored & set(p.relative_to(REPO).parts))
        and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)
    ]
    assert inits == [CANONICAL / "__init__.py"], inits


def test_build_packages_canonical_via_symlink():
    link = BUILD / "decision_governance_provider"
    assert link.is_symlink()
    assert link.resolve() == CANONICAL.resolve()


def test_version_single_source_and_metadata():
    from decision_governance_provider.version import __version__
    assert __version__ == "0.1.0"
    text = PYPROJECT.read_text()
    assert 'name = "decision-governance-provider"' in text
    assert 'attr = "decision_governance_provider.version.__version__"' in text
    assert 'dynamic = ["version"]' in text
    # depends on the kernel distribution; excludes its own tests.
    assert 'decision-governance==1.0.0' in text
    assert "decision_governance_provider.tests" in text
    assert 'include = ["decision_governance_provider*"]' in text
