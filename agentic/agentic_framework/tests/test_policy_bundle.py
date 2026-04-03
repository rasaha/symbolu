"""
Tests for the Policy Externalization Layer.

Covers:
    - Valid bundle construction and validation
    - Invalid bundle rejection
    - Scoped override precedence (global < tenant < domain < environment)
    - Field-by-field merge semantics
    - Fail-closed resolution on failure
    - Dict-based and JSON loading
    - Audit metadata propagation
    - Runtime integration: GovernanceService consumes resolved policy
    - Default global policy matches hardcoded values
"""

import json
import pytest
from unittest.mock import patch

from agentic.agentic_framework.policy_bundle import (
    PolicyBundle,
    PolicyMetadata,
    PolicyScope,
    PolicyScopeLevel,
    PolicyResolution,
    JEPAPolicy,
    ConfidencePolicy,
    SafetyPolicy,
    RiskPolicy,
    ShadowPolicy,
    DomainPolicyConfig,
    DEFAULT_GLOBAL_POLICY,
    FAIL_CLOSED_POLICY,
    FINANCE_TENANT_OVERRIDE,
    STAGING_ENV_OVERRIDE,
    PolicyValidationError,
    validate_policy_bundle,
    validate_or_raise,
    policy_bundle_from_dict,
    policy_bundle_from_json,
    resolve_effective_policy,
)


# =========================================================================
# Test: Bundle construction and defaults
# =========================================================================


class TestPolicyBundleConstruction:
    """Test that bundles construct with correct defaults."""

    def test_default_global_policy_is_valid(self):
        errors = validate_policy_bundle(DEFAULT_GLOBAL_POLICY)
        assert errors == [], f"Default global policy has errors: {errors}"

    def test_fail_closed_policy_is_valid(self):
        errors = validate_policy_bundle(FAIL_CLOSED_POLICY)
        assert errors == []

    def test_finance_override_is_valid(self):
        errors = validate_policy_bundle(FINANCE_TENANT_OVERRIDE)
        assert errors == []

    def test_staging_override_is_valid(self):
        errors = validate_policy_bundle(STAGING_ENV_OVERRIDE)
        assert errors == []

    def test_default_jepa_matches_hardcoded(self):
        """Default JEPA policy values must match the hardcoded governance values."""
        jepa = DEFAULT_GLOBAL_POLICY.jepa
        assert jepa.regime_actions["NORMAL"] == "ALLOW"
        assert jepa.regime_actions["DUAL_ANOMALY"] == "DENY"
        assert jepa.regime_confidence_adjustments["PROCESS_DRIFT"] == -0.15
        assert jepa.regime_execution_modes["SEMANTIC_SHIFT"] == "CONFIRM_REQUIRED"
        assert jepa.regime_escalations["DUAL_ANOMALY"] == "HALT"

    def test_default_confidence_matches_hardcoded(self):
        conf = DEFAULT_GLOBAL_POLICY.confidence
        assert conf.quality_weight == 0.30
        assert conf.coherence_weight == 0.25
        assert conf.escalation_halt_threshold == 0.35
        assert conf.execution_full_threshold == 0.75

    def test_default_safety_matches_hardcoded(self):
        safety = DEFAULT_GLOBAL_POLICY.safety
        assert safety.internal_consistency_threshold == 0.60
        assert safety.reversal_risk_threshold == 0.40
        assert "destructive_file_operations" in safety.forbidden_capabilities

    def test_metadata_fingerprint_deterministic(self):
        fp1 = DEFAULT_GLOBAL_POLICY.metadata.fingerprint()
        fp2 = DEFAULT_GLOBAL_POLICY.metadata.fingerprint()
        assert fp1 == fp2
        assert len(fp1) == 16

    def test_audit_dict_contains_required_fields(self):
        audit = DEFAULT_GLOBAL_POLICY.to_audit_dict()
        assert "policy_id" in audit
        assert "version" in audit
        assert "fingerprint" in audit
        assert "scope_level" in audit


# =========================================================================
# Test: Validation
# =========================================================================


class TestPolicyValidation:
    """Test that invalid bundles are rejected."""

    def test_missing_policy_id(self):
        bundle = PolicyBundle(
            metadata=PolicyMetadata(policy_id="", version="1.0.0"),
        )
        errors = validate_policy_bundle(bundle)
        assert any("policy_id" in e for e in errors)

    def test_missing_version(self):
        bundle = PolicyBundle(
            metadata=PolicyMetadata(policy_id="test", version=""),
        )
        errors = validate_policy_bundle(bundle)
        assert any("version" in e for e in errors)

    def test_invalid_regime_action(self):
        bundle = PolicyBundle(
            metadata=PolicyMetadata(policy_id="t", version="1"),
            jepa=JEPAPolicy(regime_actions={
                "NORMAL": "INVALID_ACTION",
                "PROCESS_DRIFT": "DEGRADE",
                "SEMANTIC_SHIFT": "CONFIRM",
                "DUAL_ANOMALY": "DENY",
                "UNKNOWN": "HALT",
            }),
        )
        errors = validate_policy_bundle(bundle)
        assert any("invalid value" in e for e in errors)

    def test_missing_regime_key(self):
        bundle = PolicyBundle(
            metadata=PolicyMetadata(policy_id="t", version="1"),
            jepa=JEPAPolicy(regime_actions={
                "NORMAL": "ALLOW",
                # Missing other regimes
            }),
        )
        errors = validate_policy_bundle(bundle)
        assert any("missing regimes" in e for e in errors)

    def test_confidence_adjustment_out_of_range(self):
        bundle = PolicyBundle(
            metadata=PolicyMetadata(policy_id="t", version="1"),
            jepa=JEPAPolicy(regime_confidence_adjustments={
                "NORMAL": 0.0,
                "PROCESS_DRIFT": 0.5,  # INVALID: must be <= 0
                "SEMANTIC_SHIFT": -0.20,
                "DUAL_ANOMALY": -0.30,
                "UNKNOWN": -0.25,
            }),
        )
        errors = validate_policy_bundle(bundle)
        assert any("outside [-1.0, 0.0]" in e for e in errors)

    def test_weights_dont_sum_to_one(self):
        bundle = PolicyBundle(
            metadata=PolicyMetadata(policy_id="t", version="1"),
            confidence=ConfidencePolicy(
                quality_weight=0.50,
                coherence_weight=0.50,
                stability_weight=0.50,
                action_weight=0.50,
            ),
        )
        errors = validate_policy_bundle(bundle)
        assert any("weights sum" in e for e in errors)

    def test_threshold_out_of_range(self):
        bundle = PolicyBundle(
            metadata=PolicyMetadata(policy_id="t", version="1"),
            confidence=ConfidencePolicy(escalation_halt_threshold=1.5),
        )
        errors = validate_policy_bundle(bundle)
        assert any("outside [0.0, 1.0]" in e for e in errors)

    def test_escalation_thresholds_misordered(self):
        bundle = PolicyBundle(
            metadata=PolicyMetadata(policy_id="t", version="1"),
            confidence=ConfidencePolicy(
                escalation_halt_threshold=0.80,
                escalation_confirm_threshold=0.50,
                escalation_notify_threshold=0.90,
            ),
        )
        errors = validate_policy_bundle(bundle)
        assert any("halt_threshold must be < confirm_threshold" in e for e in errors)

    def test_empty_forbidden_capabilities_rejected(self):
        bundle = PolicyBundle(
            metadata=PolicyMetadata(policy_id="t", version="1"),
            safety=SafetyPolicy(forbidden_capabilities=()),
        )
        errors = validate_policy_bundle(bundle)
        assert any("forbidden_capabilities" in e for e in errors)

    def test_invalid_shadow_containment_mode(self):
        bundle = PolicyBundle(
            metadata=PolicyMetadata(policy_id="t", version="1"),
            shadow=ShadowPolicy(provenance_fail_closed_mutating={
                "shadow": "INVALID_MODE",
            }),
        )
        errors = validate_policy_bundle(bundle)
        assert any("invalid mode" in e for e in errors)

    def test_validate_or_raise_raises(self):
        bundle = PolicyBundle(
            metadata=PolicyMetadata(policy_id="", version=""),
        )
        with pytest.raises(PolicyValidationError):
            validate_or_raise(bundle)


# =========================================================================
# Test: Scope matching
# =========================================================================


class TestPolicyScopeMatching:
    """Test scope matching logic."""

    def test_global_matches_everything(self):
        scope = PolicyScope(level=PolicyScopeLevel.GLOBAL)
        assert scope.matches() is True
        assert scope.matches(tenant_id="any", domain_id="any", environment="any") is True

    def test_tenant_scope_matches_tenant(self):
        scope = PolicyScope(level=PolicyScopeLevel.TENANT, tenant_id="acme")
        assert scope.matches(tenant_id="acme") is True
        assert scope.matches(tenant_id="other") is False

    def test_domain_scope_matches_domain(self):
        scope = PolicyScope(level=PolicyScopeLevel.DOMAIN, domain_id="finance")
        assert scope.matches(domain_id="finance") is True
        assert scope.matches(domain_id="devops") is False

    def test_environment_scope_matches_env(self):
        scope = PolicyScope(level=PolicyScopeLevel.ENVIRONMENT, environment="prod")
        assert scope.matches(environment="prod") is True
        assert scope.matches(environment="staging") is False

    def test_multi_field_scope(self):
        scope = PolicyScope(
            level=PolicyScopeLevel.ENVIRONMENT,
            tenant_id="acme",
            domain_id="finance",
            environment="prod",
        )
        assert scope.matches(tenant_id="acme", domain_id="finance", environment="prod") is True
        assert scope.matches(tenant_id="acme", domain_id="finance", environment="staging") is False

    def test_precedence_ordering(self):
        assert PolicyScopeLevel.GLOBAL.precedence < PolicyScopeLevel.TENANT.precedence
        assert PolicyScopeLevel.TENANT.precedence < PolicyScopeLevel.DOMAIN.precedence
        assert PolicyScopeLevel.DOMAIN.precedence < PolicyScopeLevel.ENVIRONMENT.precedence


# =========================================================================
# Test: Override resolution
# =========================================================================


class TestPolicyResolution:
    """Test scoped override resolution."""

    def test_no_overrides_returns_base(self):
        result = resolve_effective_policy(DEFAULT_GLOBAL_POLICY)
        assert result.effective_policy.jepa == DEFAULT_GLOBAL_POLICY.jepa
        assert result.applied_overrides == ()
        assert result.failed is False

    def test_tenant_override_applied(self):
        result = resolve_effective_policy(
            DEFAULT_GLOBAL_POLICY,
            overrides=[FINANCE_TENANT_OVERRIDE],
            tenant_id="finance-corp",
        )
        assert len(result.applied_overrides) == 1
        # Finance override has stricter thresholds
        eff = result.effective_policy
        assert eff.confidence.escalation_halt_threshold == 0.45
        assert eff.safety.internal_consistency_threshold == 0.70
        # JEPA should remain at base (not overridden)
        assert eff.jepa.regime_actions["NORMAL"] == "ALLOW"

    def test_non_matching_override_ignored(self):
        result = resolve_effective_policy(
            DEFAULT_GLOBAL_POLICY,
            overrides=[FINANCE_TENANT_OVERRIDE],
            tenant_id="other-corp",
        )
        assert len(result.applied_overrides) == 0
        eff = result.effective_policy
        assert eff.confidence.escalation_halt_threshold == 0.35  # Base value

    def test_environment_override_applied(self):
        result = resolve_effective_policy(
            DEFAULT_GLOBAL_POLICY,
            overrides=[STAGING_ENV_OVERRIDE],
            environment="staging",
        )
        assert len(result.applied_overrides) == 1
        eff = result.effective_policy
        assert eff.confidence.escalation_halt_threshold == 0.20

    def test_multiple_overrides_precedence(self):
        """Tenant + environment: environment wins (higher precedence)."""
        result = resolve_effective_policy(
            DEFAULT_GLOBAL_POLICY,
            overrides=[FINANCE_TENANT_OVERRIDE, STAGING_ENV_OVERRIDE],
            tenant_id="finance-corp",
            environment="staging",
        )
        assert len(result.applied_overrides) == 2
        eff = result.effective_policy
        # Staging env override (higher precedence) should win for confidence
        assert eff.confidence.escalation_halt_threshold == 0.20
        # But safety from finance tenant should persist (staging doesn't override it)
        assert eff.safety.internal_consistency_threshold == 0.70

    def test_inactive_override_ignored(self):
        inactive = PolicyBundle(
            metadata=PolicyMetadata(
                policy_id="inactive", version="1.0.0", active=False,
            ),
            scope=PolicyScope(level=PolicyScopeLevel.GLOBAL),
            confidence=ConfidencePolicy(escalation_halt_threshold=0.99),
        )
        result = resolve_effective_policy(
            DEFAULT_GLOBAL_POLICY,
            overrides=[inactive],
        )
        assert len(result.applied_overrides) == 0

    def test_resolution_metadata_for_audit(self):
        result = resolve_effective_policy(
            DEFAULT_GLOBAL_POLICY,
            overrides=[FINANCE_TENANT_OVERRIDE],
            tenant_id="finance-corp",
        )
        audit = result.to_audit_dict()
        assert audit["base_policy_id"] == "default-global"
        assert audit["base_version"] == "1.0.0"
        assert len(audit["applied_overrides"]) == 1
        assert "finance-tenant-strict" in audit["applied_overrides"][0]
        assert audit["failed"] is False

    def test_resolution_failure_returns_fail_closed(self):
        """If resolution raises, result uses FAIL_CLOSED_POLICY."""
        # Create an override with invalid data that will fail validation
        bad_override = PolicyBundle(
            metadata=PolicyMetadata(policy_id="bad", version="1"),
            scope=PolicyScope(level=PolicyScopeLevel.GLOBAL),
            confidence=ConfidencePolicy(
                quality_weight=5.0,  # Will cause weight sum validation failure
            ),
        )
        result = resolve_effective_policy(
            DEFAULT_GLOBAL_POLICY,
            overrides=[bad_override],
        )
        assert result.failed is True
        assert result.effective_policy.metadata.policy_id == "__fail_closed__"
        assert "PolicyValidationError" in result.failure_reason


# =========================================================================
# Test: Dict/JSON loading
# =========================================================================


class TestPolicyLoading:
    """Test loading bundles from dicts and JSON."""

    def test_load_from_dict(self):
        data = {
            "metadata": {"policy_id": "test-bundle", "version": "2.0.0"},
            "scope": {"level": "global"},
            "jepa": {
                "regime_actions": {
                    "NORMAL": "ALLOW",
                    "PROCESS_DRIFT": "DEGRADE",
                    "SEMANTIC_SHIFT": "CONFIRM",
                    "DUAL_ANOMALY": "DENY",
                    "UNKNOWN": "HALT",
                },
            },
        }
        bundle = policy_bundle_from_dict(data)
        assert bundle.metadata.policy_id == "test-bundle"
        assert bundle.metadata.version == "2.0.0"
        assert bundle.jepa.regime_actions["NORMAL"] == "ALLOW"

    def test_load_from_json(self):
        data = {
            "metadata": {"policy_id": "json-test", "version": "1.0.0"},
            "scope": {"level": "tenant", "tenant_id": "acme"},
        }
        bundle = policy_bundle_from_json(json.dumps(data))
        assert bundle.metadata.policy_id == "json-test"
        assert bundle.scope.tenant_id == "acme"
        assert bundle.scope.level == PolicyScopeLevel.TENANT

    def test_load_invalid_json_raises(self):
        with pytest.raises(PolicyValidationError):
            policy_bundle_from_dict({
                "metadata": {"policy_id": "", "version": ""},
            })

    def test_load_missing_metadata_raises(self):
        with pytest.raises((KeyError, TypeError)):
            policy_bundle_from_dict({})

    def test_load_with_safety_overrides(self):
        data = {
            "metadata": {"policy_id": "safe", "version": "1.0.0"},
            "safety": {
                "internal_consistency_threshold": 0.80,
                "forbidden_capabilities": [
                    "destructive_file_operations",
                    "malware_execution",
                ],
            },
        }
        bundle = policy_bundle_from_dict(data)
        assert bundle.safety.internal_consistency_threshold == 0.80
        assert len(bundle.safety.forbidden_capabilities) == 2

    def test_load_with_shadow_overrides(self):
        data = {
            "metadata": {"policy_id": "shadow-strict", "version": "1.0.0"},
            "shadow": {
                "enabled": True,
                "provenance_fail_closed_mutating": {
                    "shadow": "blocked",
                    "revoked": "blocked",
                    "quarantined": "blocked",
                    "unverified": "blocked",
                },
            },
        }
        bundle = policy_bundle_from_dict(data)
        assert bundle.shadow.provenance_fail_closed_mutating["unverified"] == "blocked"


# =========================================================================
# Test: Runtime integration
# =========================================================================


class TestRuntimeIntegration:
    """Test that GovernanceService and MCP can consume resolved policy."""

    def test_governance_service_accepts_policy(self):
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        resolution = resolve_effective_policy(DEFAULT_GLOBAL_POLICY)
        service = GovernanceService(policy_resolution=resolution)

        request = AuthorizationRequest(
            actor_id="test-actor",
            action_type="file_read",
            agency_level="FULL",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        response = service.authorize(request)
        # Should work normally with resolved policy
        assert response.governance_decision is not None
        # Audit should contain policy metadata
        assert response.audit_event.request_snapshot.get("policy_bundle") is not None

    def test_governance_service_uses_strict_thresholds_from_policy(self):
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        resolution = resolve_effective_policy(
            DEFAULT_GLOBAL_POLICY,
            overrides=[FINANCE_TENANT_OVERRIDE],
            tenant_id="finance-corp",
        )
        service = GovernanceService(policy_resolution=resolution)

        # Request with borderline scores — strict policy should be harder to pass
        request = AuthorizationRequest(
            actor_id="test-actor",
            action_type="file_write",
            agency_level="FULL",
            quality_score=0.65,
            coherence_score=0.65,
            internal_consistency=0.65,
            goal_alignment=0.65,
            trajectory_confidence=0.65,
        )
        response = service.authorize(request)
        # With finance strict policy (thresholds at 0.70), 0.65 should fail safety
        assert response.governance_decision.value in ("DENY", "DEFER")

    def test_governance_service_no_policy_backward_compatible(self):
        """GovernanceService without policy_resolution should still work."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        service = GovernanceService()
        request = AuthorizationRequest(
            actor_id="test-actor",
            action_type="file_read",
            agency_level="FULL",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        response = service.authorize(request)
        assert response.governance_decision is not None

    def test_policy_version_in_audit_event(self):
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest
        from agentic.ledger.governance_audit_store import GovernanceAuditStore

        resolution = resolve_effective_policy(DEFAULT_GLOBAL_POLICY)
        store = GovernanceAuditStore(":memory:")
        service = GovernanceService(
            policy_resolution=resolution,
            audit_store=store,
        )

        request = AuthorizationRequest(
            actor_id="test-actor",
            action_type="file_read",
            agency_level="FULL",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        service.authorize(request)

        events = store.list_recent(limit=1)
        assert len(events) == 1
        snapshot = events[0].get("request_snapshot", {})
        import json as _json
        if isinstance(snapshot, str):
            snapshot = _json.loads(snapshot)
        assert "policy_bundle" in snapshot
        assert snapshot["policy_bundle"]["policy_id"] == "default-global"
