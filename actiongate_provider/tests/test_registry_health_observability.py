"""Registry/config integration, health & lifecycle, observability."""
from __future__ import annotations

import pytest

from governance_providers.api import (
    ProviderConfigurationError, ProviderKind, ProviderRegistry, ResolutionRequest, resolve)
from actiongate_provider.configuration import (
    ActionGateSettings, build_actiongate_provider)
from actiongate_provider.core import ActionGateEngine
from actiongate_provider.health import check as health_check
from actiongate_provider.observability import ActionGateInvocationLog
from actiongate_provider.provider import ActionGateProvider
from governance_providers.api import ActionGovernanceRequest, ProviderLifecycleState


def test_registers_and_resolves_via_framework():
    reg = ProviderRegistry()
    provider = build_actiongate_provider()
    reg.register(provider.descriptor())
    p, rec = resolve(reg, ResolutionRequest(ProviderKind.ACTION_GOVERNANCE))
    assert rec.selected_id == "actiongate"
    assert isinstance(reg.get_provider("actiongate"), ActionGateProvider)


def test_configuration_mode_validation():
    ActionGateSettings.from_settings({"mode": "in_process"})
    ActionGateSettings.from_settings({"mode": "remote"})
    with pytest.raises(ProviderConfigurationError):
        ActionGateSettings.from_settings({"mode": "carrier_pigeon"})


def test_remote_mode_builds_and_authorizes():
    p = build_actiongate_provider(settings=ActionGateSettings(mode="remote")); p.initialize()
    assert p.descriptor().metadata["mode"] == "remote"
    assert p.authorize(ActionGovernanceRequest("OK")).outcome.value == "AUTHORIZED"


def test_health_reports_all_dimensions():
    p = build_actiongate_provider(); p.initialize()
    hr = health_check(p, ActionGateSettings())
    assert hr.healthy and hr.available and hr.configuration_valid
    assert hr.protocol_compatible and hr.policy_available


def test_health_degrades_when_engine_unavailable():
    p = build_actiongate_provider(ActionGateEngine(available=False)); p.initialize()
    h = p.health()
    assert not h.healthy and h.state is ProviderLifecycleState.DEGRADED


def test_lifecycle_transitions():
    p = build_actiongate_provider()
    assert p.state is ProviderLifecycleState.REGISTERED
    p.initialize()
    assert p.state is ProviderLifecycleState.AVAILABLE
    p.shutdown()
    assert p.state is ProviderLifecycleState.STOPPED


def test_observability_records_outcome_and_error():
    log = ActionGateInvocationLog()
    p = build_actiongate_provider(invocation_log=log); p.initialize()
    p.authorize(ActionGovernanceRequest("OK"))
    bad = build_actiongate_provider(ActionGateEngine(fail="timeout"), invocation_log=log)
    bad.initialize()
    with pytest.raises(Exception):
        bad.authorize(ActionGovernanceRequest("OK"))
    recs = log.all()
    assert recs[0].completed and recs[0].outcome == "AUTHORIZED"
    assert recs[0].provider_version and recs[0].mapping_version and recs[0].policy_version
    assert not recs[1].completed and recs[1].error_class == "ProviderTimeoutError"
    assert recs[1].failure_class == "RETRYABLE"
