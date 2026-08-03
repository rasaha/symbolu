"""Canonical package packaging guards — metadata, typing marker, CLI, boundary."""
from __future__ import annotations

import pathlib

import ugence_actiongate_provider

PKG = pathlib.Path(ugence_actiongate_provider.__file__).resolve().parent
ROOT = PKG.parents[1]  # src/ugence_actiongate_provider -> src -> packages/providers/actiongate


def test_py_typed_marker_present():
    assert (PKG / "py.typed").exists()


def test_cli_entry_points_present():
    assert (PKG / "cli.py").exists()
    assert (PKG / "__main__.py").exists()
    from ugence_actiongate_provider.cli import main
    assert callable(main)


def test_pyproject_declares_framework_only_core_dependency():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'name = "ugence-actiongate-provider"' in text
    core = text.split("[project.optional")[0].split("dependencies = ")[1]
    assert "ugence-governance-provider-framework" in core
    assert "tap" not in core.lower()
    assert "ai-hiring" not in core.lower()
    assert "torch" not in core.lower() and "transformers" not in core.lower()


def test_version_info_reports_not_production_certified():
    info = ugence_actiongate_provider.version_info()
    assert info.production_certified is False
    assert info.distribution == "ugence-actiongate-provider"
    assert info.implementation_version == "0.1.0"


def test_descriptor_features_are_authorization_only():
    from ugence_actiongate_provider.configuration import build_actiongate_provider
    p = build_actiongate_provider(); p.initialize()
    feats = p.descriptor().capabilities.features
    assert "authorize" in feats
    for exec_feat in ("dispatch", "execute", "reconcile", "compensate", "observe"):
        assert exec_feat not in feats
