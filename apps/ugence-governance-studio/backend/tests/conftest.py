"""Shared test fixtures."""
from __future__ import annotations

import os
import sys

import pytest
from starlette.testclient import TestClient

from ugence_governance_studio_api import create_app
from ugence_governance_studio_api.scenarios.catalog import ScenarioCatalog
from ugence_governance_studio_api.settings import ApiSettings

# Make this directory importable so the test modules can reach ``_support`` by
# its unique module name, mirroring the P3A suite's ``_loader`` pattern.
_TESTS = os.path.dirname(os.path.abspath(__file__))
if _TESTS not in sys.path:
    sys.path.insert(0, _TESTS)


@pytest.fixture()
def settings() -> ApiSettings:
    return ApiSettings(environment="test", enable_docs=True)


@pytest.fixture()
def client(settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture()
def catalog() -> ScenarioCatalog:
    return ScenarioCatalog()
