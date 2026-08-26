"""ActionGate distribution guards after canonical migration (fast, deterministic).

ActionGate's canonical source now lives in ``packages/providers/actiongate``
(distribution ``ugence-actiongate-provider``, namespace ``ugence_actiongate_provider``).
``actiongate_provider`` is a logic-free compatibility facade, and
``packaging/dgm-actiongate-provider`` is a compatibility distribution that ships only
that facade and depends on the canonical wheel.
"""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
FACADE = REPO / "actiongate_provider"
CANONICAL = REPO / "packages" / "providers" / "actiongate"
CANONICAL_PKG = CANONICAL / "src" / "ugence_actiongate_provider"
LEGACY_DIST = REPO / "packaging" / "dgm-actiongate-provider"


def test_single_canonical_implementation():
    """Exactly one ActionGate implementation package: ``ugence_actiongate_provider``."""
    assert (CANONICAL_PKG / "__init__.py").exists()
    assert (CANONICAL_PKG / "provider.py").exists()
    assert (CANONICAL_PKG / "core.py").exists()


def test_facade_is_logic_free():
    """The legacy ``actiongate_provider`` package is only the shim ``__init__.py`` (+ tests)."""
    impl_dirs = [p for p in FACADE.iterdir()
                 if p.is_dir() and p.name not in ("tests", "__pycache__")]
    assert impl_dirs == [], impl_dirs
    impl_files = [p.name for p in FACADE.glob("*.py")]
    assert impl_files == ["__init__.py"], impl_files


def test_canonical_pyproject_metadata():
    text = (CANONICAL / "pyproject.toml").read_text()
    assert 'name = "ugence-actiongate-provider"' in text
    assert 'attr = "ugence_actiongate_provider.version.DISTRIBUTION_VERSION"' in text
    # Core hard dependency is the framework only (checked on the dependencies line,
    # not on comment prose which legitimately names TAP to disclaim it).
    assert 'dependencies = ["ugence-governance-provider-framework>=0.1.0"]' in text
    core_deps = text.split("[project.optional")[0].split("dependencies = ")[1]
    assert "tap" not in core_deps.lower()
    assert "decision-governance" not in core_deps
    assert "ugence-decision-authority" not in core_deps


def test_legacy_distribution_is_compat_only():
    text = (LEGACY_DIST / "pyproject.toml").read_text()
    assert 'name = "dgm-actiongate-provider"' in text
    assert "ugence-actiongate-provider" in text
    # Ships only the facade namespace; excludes its own tests from the dist.
    assert 'include = ["actiongate_provider*"]' in text
    assert "actiongate_provider.tests" in text
    # Dropped the unused kernel dependency from the old private wheel.
    assert "decision-governance==1.0.0" not in text
    # Peers are independent: no TAP dependency.
    assert "dgm-tap-provider" not in text
    assert "tap_provider" not in text


def test_legacy_distribution_symlinks_the_facade():
    link = LEGACY_DIST / "actiongate_provider"
    assert link.is_symlink()
    assert link.resolve() == FACADE.resolve()


def test_version_reporting_consistent():
    from actiongate_provider.version import __version__ as facade_v
    from ugence_actiongate_provider.version import __version__ as canon_v, DISTRIBUTION_VERSION
    assert facade_v == canon_v == "0.2.0"
    assert DISTRIBUTION_VERSION == "0.2.0"
