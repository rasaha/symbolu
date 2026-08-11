"""Single-source + packaging-metadata tests."""

from __future__ import annotations

import importlib
import importlib.util
import pathlib
import sys

import pytest

import ugence_cloud_scaling_controller
from ugence_cloud_scaling_controller.version import __version__

_SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "scripts"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location(
        "audit_single_source", _SCRIPTS / "audit_single_source.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_single_source_no_duplicates():
    audit = _load_audit_module()
    root = audit._repo_root()
    if not (root / ".git").exists():  # pragma: no cover - only in a git checkout
        pytest.skip("not a git checkout")
    result = audit.audit(root)
    assert result["single_source"], f"duplicate sources: {result['violations']}"
    # Every algorithm file must live in the canonical package.
    for f in result["algorithm_files"]:
        assert f["canonical"], f"algorithm module outside canonical package: {f['path']}"


def test_version_matches_metadata():
    assert __version__ == "0.2.0"


def test_py_typed_shipped():
    pkg_dir = pathlib.Path(ugence_cloud_scaling_controller.__file__).parent
    assert (pkg_dir / "py.typed").exists()


def test_public_api_exports():
    expected = {
        "CloudScalingController", "Controller", "InfraControllerConfig",
        "ScalingObservation", "ScalingRecommendation", "ActionResult",
        "evaluate", "__version__",
    }
    assert expected.issubset(set(ugence_cloud_scaling_controller.__all__))
    for name in expected:
        assert hasattr(ugence_cloud_scaling_controller, name)
