"""Single-source + packaging-metadata tests."""

from __future__ import annotations

import importlib
import importlib.util
import json
import pathlib
import re
import sys

import pytest

import ugence_cloud_scaling_controller
from ugence_cloud_scaling_controller.version import __version__

_PKG_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SCRIPTS = _PKG_ROOT / "scripts"


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
    assert __version__ == "0.4.0"


def test_version_single_source_consistency():
    """Every hardcoded version string in the package must agree with version.py.

    Regression guard: a version bump previously drifted across several hardcoded
    spots (manifest, authority inventory, the distribution verifier's
    EXPECTED_VERSION, and — outside this test's reach — a CI workflow smoke check).
    Keep the in-package spots pinned to the single source of truth so drift fails a
    fast unit test instead of only CI. Files are skipped individually if absent
    (e.g. a wheel-only environment ships neither the manifest nor the verifier).
    """
    checked = 0

    manifest = _PKG_ROOT / "module_manifest.json"
    if manifest.exists():
        assert json.loads(manifest.read_text())["version"] == __version__, "module_manifest.json"
        checked += 1

    inventory = _PKG_ROOT / "artifacts" / "wheel_authority_inventory.json"
    if inventory.exists():
        assert json.loads(inventory.read_text())["version"] == __version__, "wheel_authority_inventory.json"
        checked += 1

    verifier = _PKG_ROOT / "verify_cloud_scaling_controller_distribution.py"
    if verifier.exists():
        m = re.search(r'EXPECTED_VERSION\s*=\s*"([^"]+)"', verifier.read_text())
        assert m and m.group(1) == __version__, "verifier EXPECTED_VERSION"
        checked += 1

    if checked == 0:
        pytest.skip("no version-bearing metadata files present (wheel-only environment)")


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
