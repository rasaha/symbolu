"""The distribution's own metadata, checked rather than assumed."""

from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PYPROJECT = (ROOT / "pyproject.toml").read_text()


@pytest.mark.invariant
def test_the_distribution_name_and_module_agree():
    assert 'name = "ugence-cloud-scaling-policy-authenticity"' in PYPROJECT
    assert (ROOT / "src" / "ugence_cloud_scaling_policy_authenticity" / "__init__.py").is_file()


@pytest.mark.invariant
def test_the_package_is_typed_and_ships_its_marker():
    assert (ROOT / "src" / "ugence_cloud_scaling_policy_authenticity" / "py.typed").is_file()
    assert 'ugence_cloud_scaling_policy_authenticity = ["py.typed"]' in PYPROJECT


@pytest.mark.invariant
def test_the_version_is_read_from_the_module():
    assert (
        'version = { attr = "ugence_cloud_scaling_policy_authenticity.version.__version__" }'
        in PYPROJECT
    )


@pytest.mark.invariant
def test_the_readme_and_changelog_ship():
    assert (ROOT / "README.md").is_file()
    assert (ROOT / "CHANGELOG.md").is_file()


@pytest.mark.invariant
def test_the_public_surface_is_importable_and_complete():
    import ugence_cloud_scaling_policy_authenticity as pkg

    for name in pkg.__all__:
        assert hasattr(pkg, name), name


@pytest.mark.adversarial
def test_the_public_surface_exports_nothing_private():
    import ugence_cloud_scaling_policy_authenticity as pkg

    assert not any(name.startswith("_") for name in pkg.__all__ if name != "__version__")
