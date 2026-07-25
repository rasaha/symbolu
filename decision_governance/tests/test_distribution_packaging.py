"""Phase 5E.1 — independent-distribution packaging guards (fast, deterministic).

These verify, without building anything, that the kernel can ship as its own
``decision-governance`` distribution alongside the root ``symbolu`` distribution
*without source drift*:

* there is exactly one canonical kernel source tree (no duplicated copy);
* the independent build config packages that canonical tree directly (via a
  symlink whose real path is the canonical package) — so the two distributions
  cannot diverge;
* the version has a single authoritative source (``version.py``); the independent
  build derives it dynamically rather than hard-coding a second copy;
* the independent distribution declares only the kernel's real runtime dependency
  and excludes the consuming layers and kernel tests.

The heavyweight build/install/consume proof lives in
``packaging/verify_independent_distribution.py`` (run in CI); these tests are the
fast regression guards.
"""

from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = REPO / "decision_governance"
DGM_BUILD = REPO / "packaging" / "decision-governance"
DGM_PYPROJECT = DGM_BUILD / "pyproject.toml"


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_exactly_one_canonical_kernel_source_tree():
    """No duplicated kernel tree anywhere (a copy would be a drift hazard)."""
    _ignored = {"__pycache__", "packaging", "build", "dist"}
    inits = [
        p for p in REPO.rglob("decision_governance/__init__.py")
        # ignore build artifacts (build/, dist/, *.egg-info) and the packaging
        # symlink — none is a maintained source copy.
        if not (_ignored & set(p.relative_to(REPO).parts))
        and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)
    ]
    assert inits == [CANONICAL / "__init__.py"], inits


def test_independent_build_packages_the_canonical_tree_via_symlink():
    link = DGM_BUILD / "decision_governance"
    assert link.is_symlink(), "expected packaging/decision-governance/decision_governance symlink"
    # The symlink's real path IS the canonical kernel package — equivalence by
    # construction: both distributions package the same physical files.
    assert link.resolve() == CANONICAL.resolve()


def test_version_has_a_single_authoritative_source():
    from decision_governance.version import __version__
    assert __version__ == "1.0.0"
    # The independent build derives the version dynamically from version.py …
    text = _read(DGM_PYPROJECT)
    assert 'attr = "decision_governance.version.__version__"' in text
    assert 'dynamic = ["version"]' in text
    # … and does NOT hard-code a second copy of the version string.
    assert '"1.0.0"' not in text and "version = \"1.0.0\"" not in text


def test_independent_distribution_metadata():
    text = _read(DGM_PYPROJECT)
    assert 'name = "decision-governance"' in text
    # Only the kernel's real runtime dependency; not the root's numpy/etc.
    assert "pydantic" in text
    assert "numpy" not in text
    # Excludes kernel tests from the distribution.
    assert "decision_governance.tests" in text  # appears in the exclude list


def test_independent_distribution_excludes_consuming_layers():
    """The include glob is kernel-only; consuming layers can never be packaged."""
    text = _read(DGM_PYPROJECT)
    assert 'include = ["decision_governance*"]' in text
    for forbidden in ("ai_hiring", "domains", "applications", "symbolu", "agentic"):
        # none may appear as a packaged include
        assert f'"{forbidden}' not in text.replace('"decision_governance', "")


def test_root_distribution_still_includes_the_kernel():
    """Coexistence: the root symbolu wheel must keep bundling the kernel."""
    root = _read(REPO / "pyproject.toml")
    assert "decision_governance*" in root
    assert 'name = "symbolu"' in root
