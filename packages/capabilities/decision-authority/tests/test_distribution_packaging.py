"""Independent-distribution packaging guards (fast, deterministic).

Verify, without building anything, that the canonical Decision Authority package
is the ONE source tree and that the legacy ``decision_governance`` namespace is a
logic-free compatibility shim — so the two cannot drift:

* exactly one canonical kernel source tree (``ugence_decision_authority``);
* the legacy ``decision_governance`` package is a single logic-free shim module
  that re-exports the canonical package;
* the canonical build config uses the src layout, sources its version from the
  single authoritative ``version.py``, declares only pydantic, and excludes
  consuming layers and tests;
* the legacy ``decision-governance`` distribution is a compatibility shell that
  depends on the canonical wheel (no duplicated implementation).

The heavyweight build/install/consume proof lives in
``verify_decision_authority_distribution.py``; these are the fast regression guards.
"""

from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[4]
PKG = pathlib.Path(__file__).resolve().parents[1]
CANON = PKG / "src" / "ugence_decision_authority"
PKG_PYPROJECT = PKG / "pyproject.toml"
LEGACY_SHIM = REPO / "decision_governance"
LEGACY_DIST_PYPROJECT = REPO / "packaging" / "decision-governance" / "pyproject.toml"


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_exactly_one_canonical_kernel_source_tree():
    """The kernel implementation exists once, under the canonical namespace."""
    _ignored = {"__pycache__", "build", "dist"}
    inits = [
        p for p in REPO.rglob("ugence_decision_authority/__init__.py")
        if not (_ignored & set(p.relative_to(REPO).parts))
        and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)
    ]
    assert inits == [CANON / "__init__.py"], inits


def test_legacy_namespace_is_a_logic_free_shim():
    """``decision_governance`` is a single __init__.py compat shim → no duplicate
    kernel source, and it points at the canonical package."""
    py_files = [
        p for p in LEGACY_SHIM.rglob("*.py")
        if "__pycache__" not in p.parts
    ]
    assert py_files == [LEGACY_SHIM / "__init__.py"], py_files
    text = _read(LEGACY_SHIM / "__init__.py")
    assert "ugence_decision_authority" in text
    # No pydantic model / service definitions leaked into the shim.
    assert "class " not in text and "BaseModel" not in text


def test_canonical_pyproject_metadata():
    text = _read(PKG_PYPROJECT)
    assert 'name = "ugence-decision-authority"' in text
    assert 'where = ["src"]' in text
    assert 'include = ["ugence_decision_authority*"]' in text
    assert 'attr = "ugence_decision_authority.version.__version__"' in text
    assert 'dynamic = ["version"]' in text
    # Single authoritative version — no hard-coded second copy in the build config.
    assert '"1.0.0"' not in text
    # Only the real runtime dependency; not the root's numpy/etc.
    assert "pydantic" in text
    assert "numpy" not in text


def test_canonical_distribution_excludes_consuming_layers_and_tests():
    text = _read(PKG_PYPROJECT)
    # src layout: tests live outside src and are never packaged.
    assert (PKG / "tests").is_dir()
    assert not (CANON / "tests").exists()
    for forbidden in ("ai_hiring", "domains", "applications", "governance_providers",
                      "storygraph", "actiongate", "symbolu"):
        assert forbidden not in text


def test_legacy_distribution_is_a_compatibility_shell():
    """The legacy ``decision-governance`` wheel depends on the canonical package
    and carries no implementation of its own."""
    text = _read(LEGACY_DIST_PYPROJECT)
    assert 'name = "decision-governance"' in text
    assert "ugence-decision-authority" in text  # depends on the canonical wheel
    assert 'include = ["decision_governance*"]' in text
