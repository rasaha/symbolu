"""Deterministic resolution + declarative configuration."""
from __future__ import annotations

import pytest

from ugence_governance_provider_framework.metadata import ProviderKind
from ugence_governance_provider_framework.resolution import ResolutionRequest, SelectionRule, resolve
from ugence_governance_provider_framework.errors import ProviderResolutionError, ProviderConfigurationError
from ugence_governance_provider_framework.configuration import ProvidersConfiguration
from ugence_governance_provider_framework.registry import ProviderRegistry
from ugence_governance_provider_framework.reference import DeterministicActionGovernanceProvider


def test_explicit_id(registry):
    p, rec = resolve(registry, ResolutionRequest(
        ProviderKind.ACTION_GOVERNANCE, provider_id="deterministic-action"))
    assert rec.selection_rule is SelectionRule.EXPLICIT_ID
    assert rec.selected_id == "deterministic-action"


def test_global_default_marker(registry):
    p, rec = resolve(registry, ResolutionRequest(ProviderKind.ACTION_GOVERNANCE))
    assert rec.resolved and rec.selection_rule is SelectionRule.GLOBAL_DEFAULT


def test_single_compatible():
    reg = ProviderRegistry()
    reg.register(DeterministicActionGovernanceProvider(default=False).descriptor())
    p, rec = resolve(reg, ResolutionRequest(ProviderKind.ACTION_GOVERNANCE))
    assert rec.selection_rule is SelectionRule.SINGLE_COMPATIBLE


def test_ambiguous_never_guesses():
    reg = ProviderRegistry()
    reg.register(DeterministicActionGovernanceProvider(provider_id="a", default=False).descriptor())
    reg.register(DeterministicActionGovernanceProvider(provider_id="b", default=False).descriptor())
    with pytest.raises(ProviderResolutionError):
        resolve(reg, ResolutionRequest(ProviderKind.ACTION_GOVERNANCE))


def test_resolution_record_has_candidates(registry):
    p, rec = resolve(registry, ResolutionRequest(ProviderKind.EXECUTION if False else ProviderKind.ACTION_GOVERNANCE))
    assert "deterministic-action" in rec.candidate_ids
    assert rec.compatibility["deterministic-action"] is True


def test_explicit_missing_fails(registry):
    with pytest.raises(ProviderResolutionError):
        resolve(registry, ResolutionRequest(ProviderKind.ACTION_GOVERNANCE, provider_id="ghost"))


def test_config_parse_and_defaults():
    cfg = ProvidersConfiguration.from_mapping({"providers": {
        "assertion": {"default": "a1", "registered": [{"id": "a1"}]},
        "action_governance": {"default": "act1", "registered": [{"id": "act1"}]},
    }})
    assert cfg.default_for(ProviderKind.ASSERTION_GOVERNANCE) == "a1"
    assert cfg.default_for(ProviderKind.ACTION_GOVERNANCE) == "act1"


def test_config_rejects_unknown_kind():
    with pytest.raises(ProviderConfigurationError):
        ProvidersConfiguration.from_mapping({"providers": {"telepathy": {"registered": []}}})


def test_config_rejects_contradictory_defaults():
    with pytest.raises(ProviderConfigurationError):
        ProvidersConfiguration.from_mapping({"providers": {"action_governance": {
            "registered": [{"id": "a", "default": True}, {"id": "b", "default": True}]}}})
