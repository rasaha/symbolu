"""Independent-distribution packaging guards (fast, deterministic).

Verify, without building anything, that after the canonical-package migration:

* the framework implementation exists exactly once, under the canonical namespace
  ``ugence_governance_provider_framework`` (one physical source tree);
* the canonical build config uses the src layout, sources its version from the
  single authoritative ``version.py``, declares ONLY the neutral contracts leaf as
  a hard dependency, and declares Decision Authority as an OPTIONAL ``adapters``
  extra (so the core installs without a bounded capability);
* the legacy ``governance_providers`` namespace is a single logic-free shim module
  at the repository root (compatibility surface, no implementation);
* the legacy ``dgm-provider-framework`` distribution is a compatibility shell that
  depends on the canonical wheel (no duplicated implementation, no concrete
  providers, no Governance Contracts copy).

The heavyweight build/install/consume proof lives in
``verify_governance_provider_framework_distribution.py``; these are the fast guards.
"""

from __future__ import annotations

import pathlib

# packages/governance-provider-framework/tests/packaging -> repo root
REPO = pathlib.Path(__file__).resolve().parents[4]
PKG = pathlib.Path(__file__).resolve().parents[2]
CANON = PKG / "src" / "ugence_governance_provider_framework"
PKG_PYPROJECT = PKG / "pyproject.toml"
LEGACY_SHIM = REPO / "governance_providers"
LEGACY_DIST_PYPROJECT = REPO / "packaging" / "dgm-provider-framework" / "pyproject.toml"


def _read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


def test_exactly_one_canonical_framework_source_tree():
    _ignored = {"__pycache__", "build", "dist"}
    inits = [
        p for p in REPO.rglob("ugence_governance_provider_framework/__init__.py")
        if not (_ignored & set(p.relative_to(REPO).parts))
        and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)
    ]
    assert inits == [CANON / "__init__.py"], inits


def test_legacy_namespace_is_single_logic_free_shim():
    # Exactly one governance_providers/__init__.py (the shim) and no other source
    # files under it — the implementation lives only in the canonical tree.
    _ignored = {"__pycache__", "packaging", "build", "dist"}
    inits = [
        p for p in REPO.rglob("governance_providers/__init__.py")
        if not (_ignored & set(p.relative_to(REPO).parts))
        and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)
    ]
    assert inits == [LEGACY_SHIM / "__init__.py"], inits
    py_files = [p for p in LEGACY_SHIM.rglob("*.py") if "__pycache__" not in p.parts]
    assert py_files == [LEGACY_SHIM / "__init__.py"], py_files
    text = _read(LEGACY_SHIM / "__init__.py")
    assert "COMPATIBILITY-ONLY" in text
    assert "ugence_governance_provider_framework" in text


def test_canonical_build_config():
    text = _read(PKG_PYPROJECT)
    assert 'name = "ugence-governance-provider-framework"' in text
    assert 'dynamic = ["version"]' in text
    assert 'attr = "ugence_governance_provider_framework.version.__version__"' in text
    assert 'where = ["src"]' in text
    assert 'include = ["ugence_governance_provider_framework*"]' in text
    # Core hard dep is the neutral contracts leaf ONLY.
    assert '"ugence-governance-contracts>=0.1.0"' in text
    # Decision Authority is OPTIONAL (adapters extra), never a core dependency.
    assert 'adapters = ["decision-governance==1.0.0"]' in text
    # decision-governance must NOT appear in the core [project].dependencies line.
    deps_line = next(l for l in text.splitlines() if l.strip().startswith("dependencies = ["))
    assert "decision-governance" not in deps_line


def test_canonical_version_is_single_sourced():
    from ugence_governance_provider_framework.version import __version__
    assert __version__ == "0.1.0"


def test_legacy_distribution_is_compatibility_shell():
    text = _read(LEGACY_DIST_PYPROJECT)
    assert 'name = "dgm-provider-framework"' in text
    # depends on the canonical distribution; ships no implementation of its own.
    assert "ugence-governance-provider-framework" in text
    # no concrete providers, no Governance Contracts copy bundled here.
    assert "tap_provider" not in text
    assert "actiongate_provider" not in text
    # packages only the legacy shim namespace
    assert 'include = ["governance_providers*"]' in text
    assert "governance_providers.tests" in text


def test_legacy_distribution_symlink_points_at_shim():
    link = REPO / "packaging" / "dgm-provider-framework" / "governance_providers"
    assert link.is_symlink()
    assert link.resolve() == LEGACY_SHIM.resolve()
