"""Config fail-closed validation and target-allowlist enforcement."""
from __future__ import annotations

import pytest

from shadow_validation.config import ShadowValidationConfig, ShadowConfigError
from shadow_validation.allowlist import TargetAllowlist, TargetRef


def test_fixture_config_is_valid_and_labelled():
    cfg = ShadowValidationConfig.fixture()
    assert cfg.is_fixture and cfg.execution_mode == "SHADOW" and cfg.mutation_enabled is False


@pytest.mark.parametrize("over", [
    {"environment_classification": "production"},
    {"environment_classification": ""},
    {"environment_classification": "customer-prod"},
    {"cluster_identifier": ""},
    {"cluster_identifier": "*"},
    {"context_name": ""},
    {"namespace_allowlist": ()},
    {"namespace_allowlist": ("prod-web",)},
    {"resource_kind_allowlist": ()},
    {"resource_name_allowlist": ()},
    {"maximum_target_count": 0},
    {"maximum_target_count": 100000},
    {"tls_verify": False},
    {"mutation_enabled": True},
    {"execution_mode": "live"},
])
def test_config_rejects_unsafe(over):
    with pytest.raises(ShadowConfigError):
        ShadowValidationConfig.fixture(**over)


def _allowlist():
    return TargetAllowlist(cluster_identifier="fake-cluster",
                           namespaces=("shadow-test",), resource_kinds=("Deployment",),
                           resource_name_patterns=("frontend", "web-*"),
                           maximum_target_count=2)


def test_allowlist_approves_exact_and_prefix():
    a = _allowlist()
    assert a.evaluate(TargetRef("fake-cluster", "shadow-test", "Deployment", "frontend")).allowed
    assert a.evaluate(TargetRef("fake-cluster", "shadow-test", "Deployment", "web-1")).allowed


@pytest.mark.parametrize("ref,why", [
    (TargetRef("other", "shadow-test", "Deployment", "frontend"), "cluster"),
    (TargetRef("fake-cluster", "kube-system", "Deployment", "frontend"), "namespace"),
    (TargetRef("fake-cluster", "shadow-test", "StatefulSet", "frontend"), "kind"),
    (TargetRef("fake-cluster", "shadow-test", "Deployment", "backend"), "name"),
    (TargetRef("fake-cluster", "shadow-test", "Secret", "db-creds"), "credential"),
    (TargetRef("fake-cluster", "", "Deployment", "frontend"), "namespace"),
])
def test_allowlist_rejects(ref, why):
    assert _allowlist().evaluate(ref).allowed is False


def test_allowlist_enforces_target_count_cap():
    a = _allowlist()
    refs = [TargetRef("fake-cluster", "shadow-test", "Deployment", f"web-{i}")
            for i in range(5)]
    approved, rejected = a.filter(refs)
    assert len(approved) == 2
    assert any("maximum_target_count" in r.reason for r in rejected)
