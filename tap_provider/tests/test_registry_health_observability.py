"""Registry/config integration, health & lifecycle, observability."""
from __future__ import annotations

import pytest

from governance_providers.api import (
    AssertionGovernanceRequest, ProviderConfigurationError, ProviderKind,
    ProviderLifecycleState, ProviderRegistry, ResolutionRequest, resolve)
from tap_provider.configuration import TapSettings, build_tap_provider
from tap_provider.core import TapEngine
from tap_provider.health import check as health_check
from tap_provider.observability import TapInvocationLog
from tap_provider.provider import TAPProvider


def test_registers_and_resolves_via_framework():
    reg = ProviderRegistry()
    provider = build_tap_provider()
    reg.register(provider.descriptor())
    p, rec = resolve(reg, ResolutionRequest(ProviderKind.ASSERTION_GOVERNANCE))
    assert rec.selected_id == "tap"
    assert isinstance(reg.get_provider("tap"), TAPProvider)


def test_configuration_validation():
    TapSettings.from_settings({"mode": "in_process"})
    TapSettings.from_settings({"mode": "remote"})
    with pytest.raises(ProviderConfigurationError):
        TapSettings.from_settings({"mode": "smoke_signal"})
    with pytest.raises(ProviderConfigurationError):
        TapSettings.from_settings({"evidence_resolution": "web_crawl"})
    with pytest.raises(ProviderConfigurationError):
        TapSettings.from_settings({"secret_refs": {"k": "plaintext-secret"}})


def test_remote_mode_builds_and_evaluates():
    p = build_tap_provider(settings=TapSettings(mode="remote")); p.initialize()
    assert p.descriptor().metadata["mode"] == "remote"
    r = p.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    assert r.coverage.value == "SUPPORTED"


def test_health_reports_all_dimensions():
    p = build_tap_provider(); p.initialize()
    hr = health_check(p, TapSettings())
    assert hr.healthy and hr.available and hr.configuration_valid
    assert hr.protocol_compatible and hr.evaluator_ready
    assert hr.evidence_resolver_ready and hr.policy_available


def test_health_degrades_when_engine_unavailable():
    p = build_tap_provider(TapEngine(available=False)); p.initialize()
    h = p.health()
    assert not h.healthy and h.state is ProviderLifecycleState.DEGRADED


def test_lifecycle_transitions():
    p = build_tap_provider()
    assert p.state is ProviderLifecycleState.REGISTERED
    p.initialize()
    assert p.state is ProviderLifecycleState.AVAILABLE
    p.shutdown()
    assert p.state is ProviderLifecycleState.STOPPED


def test_observability_records_outcome_coverage_and_error():
    log = TapInvocationLog()
    p = build_tap_provider(invocation_log=log); p.initialize()
    p.evaluate(AssertionGovernanceRequest("OK", evidence_refs=("e1",)))
    # fail-safe path still records a normalized error classification
    bad = build_tap_provider(TapEngine(fail="timeout"), invocation_log=log)
    bad.initialize()
    bad.evaluate(AssertionGovernanceRequest("OK", evidence_refs=("e1",)))
    recs = log.all()
    assert recs[0].completed and recs[0].outcome == "SUPPORTED"
    assert recs[0].provider_version and recs[0].mapping_version and recs[0].policy_version
    assert recs[0].evidence_count == 1 and recs[0].evidence_coverage == 1.0
    assert recs[0].fingerprint
    assert not recs[1].completed and recs[1].outcome == "INDETERMINATE"
    assert recs[1].error_class == "ProviderTimeoutError"
    assert recs[1].failure_class == "RETRYABLE"


def test_duplicate_and_ambiguous_default_rejected():
    from governance_providers.api import ProviderRegistrationError
    reg = ProviderRegistry()
    reg.register(build_tap_provider(settings=TapSettings(provider_id="tap-a")).descriptor())
    # a second default for the same kind is rejected
    with pytest.raises(ProviderRegistrationError):
        reg.register(build_tap_provider(settings=TapSettings(provider_id="tap-b")).descriptor())
