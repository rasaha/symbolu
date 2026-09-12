from __future__ import annotations

import pathlib

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import ugence_model_egress_validation as pkg

PKG = pathlib.Path(__file__).resolve().parents[2]


def _pyproject():
    return tomllib.loads((PKG / "pyproject.toml").read_text(encoding="utf-8"))


def test_the_version_is_stated_once_and_agrees_everywhere():
    project = _pyproject()["project"]
    assert project["dynamic"] == ["version"]
    assert f"**Version:** {pkg.__version__}" in (PKG / "README.md").read_text(encoding="utf-8")


def test_the_dependencies_are_the_unit_and_the_adapter_and_nothing_else():
    project = _pyproject()["project"]
    assert project["dependencies"] == ["ugence-model-egress-unit>=0.4.1", "ugence-model-egress-provider-openai>=0.1.2"]
    assert project["license"] == {"text": "Proprietary"}
    assert (PKG / "LICENSE").read_text(encoding="utf-8").strip() == "Proprietary"


def test_the_readme_states_the_posture():
    readme = (PKG / "README.md").read_text(encoding="utf-8")
    for phrase in ("opens no network connection", "marks no infrastructure-dependent row as passed",
                   "LIVE_VENDOR_EGRESS = False", "never edits", "OFFLINE_CONFORMANT", "exit 2"):
        assert phrase in readme, phrase
