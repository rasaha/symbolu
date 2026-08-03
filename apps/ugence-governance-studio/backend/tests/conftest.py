"""Shared test fixtures."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from ugence_governance_studio_api import create_app
from ugence_governance_studio_api.scenarios.catalog import ScenarioCatalog
from ugence_governance_studio_api.settings import ApiSettings

SCENARIOS = (
    "procurement",
    "customer_support",
    "cybersecurity_success",
    "cybersecurity_no_feasible_team",
)


@pytest.fixture()
def settings() -> ApiSettings:
    return ApiSettings(environment="test", enable_docs=True)


@pytest.fixture()
def client(settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture()
def catalog() -> ScenarioCatalog:
    return ScenarioCatalog()


def result_of(response):
    body = response.json()
    return body["result"]
