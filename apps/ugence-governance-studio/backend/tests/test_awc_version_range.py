"""P3B packaging protection P1 — supported AWC version range.

Proves the backend is bounded to the 0.2.x AWC compatibility surface, that the
reproducible demo environment pins ==0.2.1, and that readiness FAILS CLOSED when
the installed AWC version is outside the supported range.
"""
from __future__ import annotations

import os
import tomllib

import pytest
from starlette.testclient import TestClient

import ugence_agent_workforce_composer.api as awc_api
from ugence_governance_studio_api import create_app
from ugence_governance_studio_api.scenarios.catalog import ScenarioCatalog
from ugence_governance_studio_api.settings import ApiSettings
from ugence_governance_studio_api.version import (
    PINNED_AWC_VERSION,
    SUPPORTED_AWC_MAX_EXCLUSIVE,
    SUPPORTED_AWC_MIN,
    awc_version_supported,
    version_info,
)

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pyproject() -> dict:
    with open(os.path.join(_BACKEND, "pyproject.toml"), "rb") as fh:
        return tomllib.load(fh)


def test_pyproject_bounds_awc_to_supported_minor():
    deps = _pyproject()["project"]["dependencies"]
    awc = next(d for d in deps if d.startswith("ugence-agent-workforce-composer"))
    assert ">=0.2.1" in awc
    assert "<0.3.0" in awc


def test_reproducible_env_locks_exact_version():
    with open(os.path.join(_BACKEND, "constraints.txt"), "r", encoding="utf-8") as fh:
        text = fh.read()
    assert "ugence-agent-workforce-composer==0.2.1" in text
    assert PINNED_AWC_VERSION == "0.2.1"


@pytest.mark.parametrize("version,expected", [
    ("0.2.0", False),   # below the tested minimum
    ("0.2.1", True),    # the pinned/minimum version
    ("0.2.9", True),    # within the supported minor line
    ("0.3.0", False),   # next minor — contracts may change; refused
    ("0.3.1", False),
    ("1.0.0", False),
])
def test_range_boundaries(version, expected):
    assert awc_version_supported(version) is expected


def test_version_info_reports_range():
    info = version_info()
    assert info["supported_awc_range"] == f">={SUPPORTED_AWC_MIN},<{SUPPORTED_AWC_MAX_EXCLUSIVE}"
    assert info["pinned_awc_version"] == "0.2.1"
    assert info["awc_version_supported"] is True


def test_installed_awc_is_in_range():
    assert awc_version_supported(awc_api.__version__) is True


def test_readiness_fails_when_awc_out_of_range(monkeypatch):
    monkeypatch.setattr(awc_api, "__version__", "0.3.0")
    result = ScenarioCatalog().readiness()
    assert result["checks"]["awc_version_in_supported_range"] is False
    assert result["ready"] is False


def test_ready_endpoint_503_when_awc_out_of_range(monkeypatch):
    monkeypatch.setattr(awc_api, "__version__", "0.1.0")
    client = TestClient(create_app(ApiSettings(environment="test")))
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["ready"] is False
    assert r.json()["checks"]["awc_version_in_supported_range"] is False
