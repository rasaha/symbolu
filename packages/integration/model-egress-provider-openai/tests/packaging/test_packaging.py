"""The distribution says what the source does: one first-party dependency, no other."""

from __future__ import annotations

import pathlib

try:  # 3.11+
    import tomllib
except ModuleNotFoundError:  # 3.10
    import tomli as tomllib

import ugence_model_egress_provider_openai as pkg

PKG = pathlib.Path(__file__).resolve().parents[2]


def _pyproject() -> dict:
    return tomllib.loads((PKG / "pyproject.toml").read_text(encoding="utf-8"))


def test_the_version_is_stated_once_and_agrees_everywhere():
    project = _pyproject()["project"]
    assert project["dynamic"] == ["version"]
    assert _pyproject()["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "ugence_model_egress_provider_openai.version.__version__"}
    readme = (PKG / "README.md").read_text(encoding="utf-8")
    assert f"**Version:** {pkg.__version__}" in readme


def test_the_only_dependency_is_the_unit_at_a_version_that_carries_the_lp_rulings():
    project = _pyproject()["project"]
    assert project["dependencies"] == ["ugence-model-egress-unit>=0.3.0"]
    assert set(project.get("optional-dependencies", {})) == {"test"}
    assert project["license"] == {"text": "Proprietary"}
    assert (PKG / "LICENSE").read_text(encoding="utf-8").strip() == "Proprietary"


def test_the_readme_states_the_posture():
    readme = (PKG / "README.md").read_text(encoding="utf-8")
    for phrase in ("cannot reach", "LIVE_VENDOR_EGRESS = False", "genuine_call", "FakeTransport",
                   "api.openai.com", "/v1/responses", "gpt-5.4-mini-2026-03-17"):
        assert phrase in readme, phrase
