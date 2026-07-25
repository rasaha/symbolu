"""Distribution guards for all three Phase 6B packages (Task 17)."""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

_DISTS = {
    "baseline_assertion_provider": ("dgm-baseline-assertion-provider",
                                    "dgm-baseline-assertion-provider"),
    "baseline_action_provider": ("dgm-baseline-action-provider", "dgm-baseline-action-provider"),
    "provider_heterogeneity_validation": ("dgm-provider-heterogeneity-validation",
                                          "dgm-provider-heterogeneity-validation"),
}


def test_symlinks_point_to_canonical_source():
    for pkg, (distdir, _name) in _DISTS.items():
        link = REPO / "packaging" / distdir / pkg
        assert link.is_symlink()
        assert link.resolve() == (REPO / pkg).resolve()


def test_distribution_metadata():
    for pkg, (distdir, name) in _DISTS.items():
        text = (REPO / "packaging" / distdir / "pyproject.toml").read_text()
        assert f'name = "{name}"' in text
        assert f'attr = "{pkg}.version.__version__"' in text
        assert 'decision-governance==1.0.0' in text
        assert f'include = ["{pkg}*"]' in text
        assert f"{pkg}.tests" in text


def test_heterogeneity_depends_on_both_baselines():
    text = (REPO / "packaging" / "dgm-provider-heterogeneity-validation" / "pyproject.toml").read_text()
    assert 'dgm-baseline-assertion-provider==0.1.0' in text
    assert 'dgm-baseline-action-provider==0.1.0' in text


def test_versions_are_010():
    from baseline_action_provider.version import __version__ as bav
    from baseline_assertion_provider.version import __version__ as bassv
    from provider_heterogeneity_validation.version import __version__ as phv
    assert bassv == bav == phv == "0.1.0"
