"""TAP distribution guards after canonical migration (fast, deterministic).

TAP's canonical source now lives in ``packages/providers/tap`` (distribution
``ugence-tap-provider``, namespace ``ugence_tap_provider``). ``tap_provider`` is a
logic-free compatibility facade, and ``packaging/dgm-tap-provider`` is a
compatibility distribution that ships only that facade and depends on the
canonical wheel.
"""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
FACADE = REPO / "tap_provider"
CANONICAL = REPO / "packages" / "providers" / "tap"
CANONICAL_PKG = CANONICAL / "src" / "ugence_tap_provider"
LEGACY_DIST = REPO / "packaging" / "dgm-tap-provider"


def test_single_canonical_implementation():
    """Exactly one TAP implementation package: ``ugence_tap_provider``."""
    assert (CANONICAL_PKG / "__init__.py").exists()
    assert (CANONICAL_PKG / "provider.py").exists()
    assert (CANONICAL_PKG / "core" / "__init__.py").exists()


def test_facade_is_logic_free():
    """The legacy ``tap_provider`` package is only the shim ``__init__.py`` (+ tests)."""
    impl_dirs = [p for p in FACADE.iterdir()
                 if p.is_dir() and p.name not in ("tests", "__pycache__")]
    assert impl_dirs == [], impl_dirs
    impl_files = [p.name for p in FACADE.glob("*.py")]
    assert impl_files == ["__init__.py"], impl_files


def test_canonical_pyproject_metadata():
    text = (CANONICAL / "pyproject.toml").read_text()
    assert 'name = "ugence-tap-provider"' in text
    assert 'attr = "ugence_tap_provider.version.DISTRIBUTION_VERSION"' in text
    # Core hard dependency is the framework only (checked on the dependencies line,
    # not on comment prose which legitimately names ActionGate to disclaim it).
    assert 'dependencies = ["ugence-governance-provider-framework>=0.1.0"]' in text
    core_deps = text.split("[project.optional")[0]
    assert "actiongate" not in core_deps.lower().split("dependencies = ")[1]
    assert "ugence-decision-authority" not in core_deps.split("dependencies = ")[1]


def test_legacy_distribution_is_compat_only():
    text = (LEGACY_DIST / "pyproject.toml").read_text()
    assert 'name = "dgm-tap-provider"' in text
    assert "ugence-tap-provider" in text
    # Ships only the facade namespace; excludes its own tests from the dist.
    assert 'include = ["tap_provider*"]' in text
    assert "tap_provider.tests" in text
    # Peers are independent: no ActionGate dependency.
    assert "dgm-actiongate-provider" not in text
    assert "actiongate_provider" not in text


def test_legacy_distribution_symlinks_the_facade():
    link = LEGACY_DIST / "tap_provider"
    assert link.is_symlink()
    assert link.resolve() == FACADE.resolve()


def test_version_reporting_consistent():
    from tap_provider.version import __version__ as facade_v
    from ugence_tap_provider.version import __version__ as canon_v, DISTRIBUTION_VERSION
    assert facade_v == canon_v == "0.1.0"
    assert DISTRIBUTION_VERSION == "0.1.0"
