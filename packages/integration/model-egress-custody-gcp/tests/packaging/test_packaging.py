from __future__ import annotations

import pathlib

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only a <3.11 run takes this branch
    import tomli as tomllib

import ugence_model_egress_custody_gcp as pkg

PKG = pathlib.Path(__file__).resolve().parents[2]


def _pyproject():
    return tomllib.loads((PKG / "pyproject.toml").read_text(encoding="utf-8"))


def test_the_version_is_stated_once_and_agrees_everywhere():
    project = _pyproject()["project"]
    assert project["dynamic"] == ["version"]
    assert f"**Version:** {pkg.__version__}" in (PKG / "README.md").read_text(encoding="utf-8")


def test_the_only_required_dependency_is_the_unit_and_the_sdk_is_an_extra():
    project = _pyproject()["project"]
    assert project["dependencies"] == ["ugence-model-egress-unit>=0.6.0"]
    extras = project["optional-dependencies"]
    assert extras["google"] == ["google-cloud-secret-manager>=2.20.0"]
    assert project["license"] == {"text": "Proprietary"}
    assert (PKG / "LICENSE").read_text(encoding="utf-8").strip() == "Proprietary"


def test_the_package_installs_as_one_source_tree_with_typing_marker():
    tool = _pyproject()["tool"]["setuptools"]
    assert tool["packages"]["find"]["where"] == ["src"]
    assert (PKG / "src" / "ugence_model_egress_custody_gcp" / "py.typed").is_file()
    assert len([p for p in (PKG / "src").iterdir() if p.is_dir()]) == 1


def test_the_readme_states_the_posture_plainly():
    readme = (PKG / "README.md").read_text(encoding="utf-8")
    for phrase in ("holds no credential", "LIVE_VENDOR_EGRESS = False", "injected client",
                   "imports no Google SDK", "type name only", "non-production"):
        assert phrase in readme, phrase
