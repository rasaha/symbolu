"""Distribution guards (Task 18, fast/deterministic)."""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = REPO / "comparative_governance_benchmark"
BUILD = REPO / "packaging" / "dgm-comparative-governance-benchmark"
PYPROJECT = BUILD / "pyproject.toml"


def test_single_canonical_source():
    _ignored = {"__pycache__", "packaging", "build", "dist"}
    inits = [p for p in REPO.rglob("comparative_governance_benchmark/__init__.py")
             if not (_ignored & set(p.relative_to(REPO).parts))
             and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)]
    assert inits == [CANONICAL / "__init__.py"], inits


def test_build_packages_canonical_via_symlink():
    link = BUILD / "comparative_governance_benchmark"
    assert link.is_symlink()
    assert link.resolve() == CANONICAL.resolve()


def test_distribution_metadata_and_dependencies():
    from comparative_governance_benchmark.version import __version__
    assert __version__ == "0.1.0"
    text = PYPROJECT.read_text()
    assert 'name = "dgm-comparative-governance-benchmark"' in text
    assert 'attr = "comparative_governance_benchmark.version.__version__"' in text
    for dep in ('decision-governance==1.0.0', 'dgm-provider-framework==0.1.0',
                'dgm-actiongate-provider==0.2.0', 'dgm-tap-provider==0.1.0',
                'dgm-enterprise-validation-pilot==0.1.0'):
        assert dep in text, dep
    assert 'include = ["comparative_governance_benchmark*"]' in text
    assert "comparative_governance_benchmark.tests" in text
