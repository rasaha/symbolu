"""Independent-distribution packaging guards (fast, deterministic, no build).

Verifies the canonical/facade/legacy-distribution structure without building
anything. The heavyweight build/install/consume proof lives in
``scripts/verify_tap_provider_distribution.py``.
"""
from __future__ import annotations

import pathlib

# packages/providers/tap/tests/packaging -> repo root
REPO = pathlib.Path(__file__).resolve().parents[5]
PKG = pathlib.Path(__file__).resolve().parents[2]
CANON = PKG / "src" / "ugence_tap_provider"
PKG_PYPROJECT = PKG / "pyproject.toml"
FACADE = REPO / "tap_provider"
LEGACY_DIST = REPO / "packaging" / "dgm-tap-provider"


def _read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


def test_exactly_one_canonical_tap_source_tree():
    _ignored = {"__pycache__", "build", "dist"}
    inits = [p for p in REPO.rglob("ugence_tap_provider/__init__.py")
             if not (_ignored & set(p.relative_to(REPO).parts))
             and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)]
    assert inits == [CANON / "__init__.py"], inits


def test_legacy_namespace_is_single_logic_free_shim():
    _ignored = {"__pycache__", "packaging", "build", "dist"}
    inits = [p for p in REPO.rglob("tap_provider/__init__.py")
             if not (_ignored & set(p.relative_to(REPO).parts))
             and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)]
    assert inits == [FACADE / "__init__.py"], inits
    # No implementation .py directly under the facade package (tests are separate).
    impl = [p for p in FACADE.glob("*.py")]
    assert impl == [FACADE / "__init__.py"], impl
    text = _read(FACADE / "__init__.py")
    assert "ugence_tap_provider" in text
    assert "COMPATIBILITY" in text.upper()


def test_canonical_pyproject_declares_minimal_deps():
    text = _read(PKG_PYPROJECT)
    assert 'name = "ugence-tap-provider"' in text
    assert 'attr = "ugence_tap_provider.version.DISTRIBUTION_VERSION"' in text
    assert 'dependencies = ["ugence-governance-provider-framework>=0.1.0"]' in text
    core = text.split("[project.optional")[0].split("dependencies = ")[1]
    for forbidden in ("actiongate", "ai-hiring", "torch", "transformers",
                      "fastapi", "boto3", "kubernetes", "openai", "anthropic"):
        assert forbidden not in core.lower(), forbidden


def test_legacy_distribution_is_compat_only():
    text = _read(LEGACY_DIST / "pyproject.toml")
    assert 'name = "dgm-tap-provider"' in text
    assert "ugence-tap-provider" in text
    assert "dgm-actiongate-provider" not in text


def test_no_actiongate_or_ai_hiring_source_in_canonical():
    offenders = []
    for p in CANON.rglob("*.py"):
        low = p.read_text().lower()
        if "import actiongate" in low or "import ai_hiring" in low:
            offenders.append(p.name)
    assert not offenders, offenders


def test_import_isolation_no_source_path_injection():
    # Importing the package must not add the repo root or arbitrary paths to sys.path
    # beyond what the test harness already configured.
    import sys
    before = list(sys.path)
    import ugence_tap_provider.api  # noqa: F401
    assert list(sys.path) == before
