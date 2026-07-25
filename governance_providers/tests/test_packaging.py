"""Phase 5F — provider-framework distribution guards (fast, deterministic).

The framework ships as its own private ``dgm-provider-framework`` distribution
that depends on the kernel distribution and owns no kernel files. The deep proof
(build + isolated 2-wheel install + conformance) is exercised separately.
"""

from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = REPO / "governance_providers"
BUILD = REPO / "packaging" / "dgm-provider-framework"
PYPROJECT = BUILD / "pyproject.toml"


def test_single_canonical_source():
    _ignored = {"__pycache__", "packaging", "build", "dist"}
    inits = [
        p for p in REPO.rglob("governance_providers/__init__.py")
        if not (_ignored & set(p.relative_to(REPO).parts))
        and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)
    ]
    assert inits == [CANONICAL / "__init__.py"], inits


def test_build_packages_canonical_via_symlink():
    link = BUILD / "governance_providers"
    assert link.is_symlink()
    assert link.resolve() == CANONICAL.resolve()


def test_distribution_metadata_and_dependency():
    from governance_providers.version import __version__
    assert __version__ == "0.1.0"
    text = PYPROJECT.read_text()
    assert 'name = "dgm-provider-framework"' in text
    assert 'attr = "governance_providers.version.__version__"' in text
    assert 'dynamic = ["version"]' in text
    # depends on the independent DGM distribution; never bundles kernel files.
    assert 'decision-governance==1.0.0' in text
    assert "decision_governance" not in text.replace("decision-governance==1.0.0", "")
    assert "governance_providers.tests" in text
    assert 'include = ["governance_providers*"]' in text
