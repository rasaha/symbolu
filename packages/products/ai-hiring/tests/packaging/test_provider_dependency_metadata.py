"""Provider dependency-metadata tests (source pyproject + installed metadata).

Asserts the canonical dependency normalization at the packaging layer:

* the ``tap`` / ``actiongate`` extras resolve the CANONICAL distributions
  (``ugence-tap-provider`` / ``ugence-actiongate-provider``);
* the legacy ``dgm-tap-provider`` / ``dgm-actiongate-provider`` distributions are
  NOT AI Hiring dependencies (neither core nor optional);
* TAP / ActionGate are never core (default) dependencies;
* the distribution version reflects the packaging patch bump (0.1.1) while the
  product version and production-certification status are unchanged.

The source-level pyproject checks run in every environment; the installed
wheel-METADATA checks run only when the package is pip-installed (they are the
authoritative Requires-Dist audit and are also exercised by the distribution
verifier and CI).
"""

from __future__ import annotations

import pathlib

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

import pytest

import ugence_ai_hiring

# packages/products/ai-hiring/src/ugence_ai_hiring -> .../ai-hiring
_PKG_DIR = pathlib.Path(ugence_ai_hiring.__file__).resolve().parents[2]
_PYPROJECT = _PKG_DIR / "pyproject.toml"

# The pyproject-source checks only apply in a source checkout. When the package is
# installed as a wheel there is no adjacent pyproject.toml; the authoritative
# Requires-Dist audit for the installed case is the wheel-METADATA test below (and
# the distribution verifier). Skip the source checks rather than fail spuriously.
_HAVE_PYPROJECT = _PYPROJECT.exists()
_needs_pyproject = pytest.mark.skipif(
    not _HAVE_PYPROJECT,
    reason="installed package (no source pyproject.toml); wheel METADATA is audited separately",
)

_LEGACY_DISTS = ("dgm-tap-provider", "dgm-actiongate-provider")


def _pyproject() -> dict:
    return tomllib.loads(_PYPROJECT.read_text())


@_needs_pyproject
def test_tap_extra_resolves_canonical_distribution():
    extras = _pyproject()["project"]["optional-dependencies"]
    tap = extras["tap"]
    assert any(dep.startswith("ugence-tap-provider") for dep in tap), tap
    assert not any("dgm-tap-provider" in dep for dep in tap), tap


@_needs_pyproject
def test_actiongate_extra_resolves_canonical_distribution():
    extras = _pyproject()["project"]["optional-dependencies"]
    ag = extras["actiongate"]
    assert any(dep.startswith("ugence-actiongate-provider") for dep in ag), ag
    assert not any("dgm-actiongate-provider" in dep for dep in ag), ag


@_needs_pyproject
def test_no_legacy_dgm_distribution_anywhere_in_pyproject():
    text = _PYPROJECT.read_text()
    for dist in _LEGACY_DISTS:
        # It may be mentioned in a comment only as historical context; assert it is
        # never a declared requirement string.
        pp = _pyproject()
        core = pp["project"].get("dependencies", [])
        assert not any(dist in dep for dep in core), f"{dist} is a core dependency"
        for name, deps in pp["project"].get("optional-dependencies", {}).items():
            assert not any(dist in dep for dep in deps), f"{dist} in extra {name}"


@_needs_pyproject
def test_tap_and_actiongate_are_not_core_dependencies():
    core = _pyproject()["project"]["dependencies"]
    joined = " ".join(core)
    for token in ("tap-provider", "actiongate-provider", "tap_provider", "actiongate_provider"):
        assert token not in joined, f"provider leaked into core deps: {token}"


@_needs_pyproject
def test_all_extra_does_not_silently_bundle_providers():
    """The documented ``all`` extra is the API bundle; it must not pull providers."""
    extras = _pyproject()["project"]["optional-dependencies"]
    all_deps = " ".join(extras.get("all", []))
    for token in ("tap-provider", "actiongate-provider"):
        assert token not in all_deps, f"providers silently added to 'all': {token}"


def test_distribution_version_reflects_patch_bump():
    assert ugence_ai_hiring.__version__ == "0.1.1"
    info = ugence_ai_hiring.version_info()
    assert info.distribution_version == "0.1.1"
    # Product maturity + certification are unchanged by a dependency swap.
    assert info.product_version == "0.6.0"
    assert info.production_certified is False


def test_optional_integration_probe_keys_are_preserved_and_canonical():
    """The version-info schema keys are retained; the probed modules are canonical."""
    from ugence_ai_hiring.version import _OPTIONAL_INTEGRATIONS

    assert _OPTIONAL_INTEGRATIONS["tap_legacy"] == "ugence_tap_provider"
    assert _OPTIONAL_INTEGRATIONS["actiongate_legacy"] == "ugence_actiongate_provider"
    # Schema stability: the historical keys still exist for compatibility.
    info = ugence_ai_hiring.version_info().to_dict()
    assert "tap_legacy" in info["optional_integrations"]
    assert "actiongate_legacy" in info["optional_integrations"]


def test_installed_wheel_metadata_requires_canonical_not_legacy():
    """When genuinely pip-installed, Requires-Dist maps the extras to canonical.

    Skipped in a source checkout (where the package resolves from ``src/`` and any
    ``importlib.metadata`` result would come from a transient build egg-info, not a
    real wheel). The authoritative wheel-METADATA audit runs in the distribution
    verifier and CI against a clean install.
    """
    import importlib.metadata as md
    import pytest

    if "site-packages" not in str(pathlib.Path(ugence_ai_hiring.__file__).resolve()):
        pytest.skip("source checkout — wheel METADATA audited by the distribution verifier")

    try:
        dist = md.distribution("ugence-ai-hiring")
    except md.PackageNotFoundError:  # pragma: no cover
        pytest.skip("ugence-ai-hiring not pip-installed")

    requires = dist.requires or []
    joined = "\n".join(requires)
    assert "ugence-tap-provider" in joined
    assert "ugence-actiongate-provider" in joined
    assert "dgm-tap-provider" not in joined
    assert "dgm-actiongate-provider" not in joined
