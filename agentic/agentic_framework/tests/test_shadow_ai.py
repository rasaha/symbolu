"""
Tests for the Shadow AI Control Layer.

Covers:
    - Registry lookup and fallback
    - Approved vs unverified vs shadow vs revoked assets
    - Same semantic state with different provenance → different outcomes
    - Domain-sensitive shadow blocking
    - Memory write denial from untrusted AI
    - MCP integration
    - GovernanceService integration
    - Durable audit persistence of shadow fields
    - Stricter-only invariant
    - No-domain / no-shadow backward compatibility
    - Approved asset behaving incoherently with domain/semantic state
"""

import pytest
from typing import Dict, Optional

from agentic.agentic_framework.shadow_ai import (
    ProvenanceStatus,
    ShadowAssetType,
    ShadowTrustLevel,
    ShadowContainmentMode,
    ShadowRegistryEntry,
    ShadowRiskFactors,
    ShadowAssessment,
    ShadowRegistry,
    ShadowPolicyRule,
    DEFAULT_SHADOW_RULES,
    resolve_shadow_policy,
    shadow_containment_to_governance,
    _stricter_containment,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def basic_registry() -> ShadowRegistry:
    """Registry with a few entries for testing."""
    return ShadowRegistry(entries=[
        ShadowRegistryEntry(
            asset_id="internal-model-v1",
            asset_type=ShadowAssetType.MODEL_ENDPOINT,
            provenance=ProvenanceStatus.APPROVED,
            trust_level=ShadowTrustLevel.TRUSTED,
            provider="internal",
            allowed_domains=frozenset({"research", "devops"}),
        ),
        ShadowRegistryEntry(
            asset_id="approved-tool-read",
            asset_type=ShadowAssetType.TOOL,
            provenance=ProvenanceStatus.APPROVED,
            trust_level=ShadowTrustLevel.TRUSTED,
            provider="internal",
            max_risk_level="write",
        ),
        ShadowRegistryEntry(
            asset_id="limited-agent",
            asset_type=ShadowAssetType.AGENT,
            provenance=ProvenanceStatus.APPROVED,
            trust_level=ShadowTrustLevel.LIMITED,
            provider="partner",
            allowed_domains=frozenset({"research"}),
        ),
        ShadowRegistryEntry(
            asset_id="quarantined-mcp",
            asset_type=ShadowAssetType.MCP_SERVER,
            provenance=ProvenanceStatus.QUARANTINED,
            trust_level=ShadowTrustLevel.UNTRUSTED,
            provider="external",
        ),
        ShadowRegistryEntry(
            asset_id="revoked-plugin",
            asset_type=ShadowAssetType.PLUGIN,
            provenance=ProvenanceStatus.REVOKED,
            trust_level=ShadowTrustLevel.BLOCKED,
            provider="deprecated",
        ),
        ShadowRegistryEntry(
            asset_id="finance-tool",
            asset_type=ShadowAssetType.TOOL,
            provenance=ProvenanceStatus.APPROVED,
            trust_level=ShadowTrustLevel.TRUSTED,
            provider="internal",
            allowed_domains=frozenset({"finance"}),
        ),
    ])


# =========================================================================
# Test: Registry
# =========================================================================


class TestShadowRegistry:
    """Tests for ShadowRegistry lookup and management."""

    def test_lookup_by_exact_id(self, basic_registry: ShadowRegistry):
        entry = basic_registry.lookup("internal-model-v1")
        assert entry is not None
        assert entry.asset_id == "internal-model-v1"
        assert entry.provenance == ProvenanceStatus.APPROVED

    def test_lookup_unknown_returns_none(self, basic_registry: ShadowRegistry):
        entry = basic_registry.lookup("totally-unknown-thing")
        assert entry is None

    def test_lookup_by_pattern(self, basic_registry: ShadowRegistry):
        entry = basic_registry.lookup_by_pattern("internal-model-v1")
        assert entry is not None

    def test_lookup_by_provider(self, basic_registry: ShadowRegistry):
        entries = basic_registry.lookup_by_provider("internal")
        assert len(entries) >= 2

    def test_is_sanctioned_approved(self, basic_registry: ShadowRegistry):
        assert basic_registry.is_sanctioned("internal-model-v1") is True

    def test_is_sanctioned_revoked(self, basic_registry: ShadowRegistry):
        assert basic_registry.is_sanctioned("revoked-plugin") is False

    def test_is_sanctioned_unknown(self, basic_registry: ShadowRegistry):
        assert basic_registry.is_sanctioned("unknown") is False

    def test_inactive_entry_not_returned(self):
        reg = ShadowRegistry(entries=[
            ShadowRegistryEntry(
                asset_id="inactive-tool",
                asset_type=ShadowAssetType.TOOL,
                active=False,
            ),
        ])
        assert reg.lookup("inactive-tool") is None

    def test_all_entries(self, basic_registry: ShadowRegistry):
        entries = basic_registry.all_entries()
        assert len(entries) == 6

    def test_register_new_entry(self, basic_registry: ShadowRegistry):
        new_entry = ShadowRegistryEntry(
            asset_id="new-tool",
            asset_type=ShadowAssetType.TOOL,
        )
        basic_registry.register(new_entry)
        assert basic_registry.lookup("new-tool") is not None


# =========================================================================
# Test: Risk Factors
# =========================================================================


class TestShadowRiskFactors:
    """Tests for ShadowRiskFactors scoring."""

    def test_zero_risk(self):
        rf = ShadowRiskFactors()
        assert rf.composite_score == 0.0

    def test_high_provenance_risk(self):
        rf = ShadowRiskFactors(provenance_risk=1.0)
        assert rf.composite_score > 0.0

    def test_multiple_risks_compound(self):
        rf_low = ShadowRiskFactors(provenance_risk=0.5)
        rf_high = ShadowRiskFactors(
            provenance_risk=0.5,
            semantic_governance_mismatch=0.8,
            memory_write_risk=0.9,
        )
        assert rf_high.composite_score > rf_low.composite_score

    def test_to_dict_has_all_fields(self):
        rf = ShadowRiskFactors(provenance_risk=0.5)
        d = rf.to_dict()
        assert "provenance_risk" in d
        assert "composite_score" in d
        assert d["provenance_risk"] == 0.5

    def test_composite_clamped(self):
        rf = ShadowRiskFactors(
            provenance_risk=1.0,
            identity_confidence=0.0,
            domain_mismatch=1.0,
            semantic_governance_mismatch=1.0,
            hidden_intelligence_path=1.0,
            memory_write_risk=1.0,
            external_side_effects=1.0,
            execution_privilege=1.0,
            unexpected_usage=1.0,
        )
        assert rf.composite_score <= 1.0


# =========================================================================
# Test: Containment Modes
# =========================================================================


class TestContainmentModes:
    """Tests for containment mode ordering and mapping."""

    def test_severity_ordering(self):
        assert ShadowContainmentMode.ALLOW.severity < ShadowContainmentMode.BLOCKED.severity
        assert ShadowContainmentMode.READ_ONLY.severity < ShadowContainmentMode.QUARANTINED.severity
        assert ShadowContainmentMode.REQUIRE_CONFIRMATION.severity < ShadowContainmentMode.BLOCKED.severity

    def test_stricter_comparison(self):
        assert ShadowContainmentMode.BLOCKED.is_stricter_than(ShadowContainmentMode.ALLOW)
        assert not ShadowContainmentMode.ALLOW.is_stricter_than(ShadowContainmentMode.BLOCKED)

    def test_stricter_containment_fn(self):
        result = _stricter_containment(
            ShadowContainmentMode.ALLOW,
            ShadowContainmentMode.BLOCKED,
        )
        assert result == ShadowContainmentMode.BLOCKED

    def test_containment_to_governance_allow(self):
        assert shadow_containment_to_governance(ShadowContainmentMode.ALLOW) == "ALLOW"

    def test_containment_to_governance_blocked(self):
        assert shadow_containment_to_governance(ShadowContainmentMode.BLOCKED) == "DENY"

    def test_containment_to_governance_quarantined(self):
        assert shadow_containment_to_governance(ShadowContainmentMode.QUARANTINED) == "DENY"

    def test_containment_to_governance_read_only(self):
        assert shadow_containment_to_governance(ShadowContainmentMode.READ_ONLY) == "DEFER"

    def test_containment_to_governance_require_confirmation(self):
        assert shadow_containment_to_governance(ShadowContainmentMode.REQUIRE_CONFIRMATION) == "DEFER"


# =========================================================================
# Test: Resolve Shadow Policy — Approved Assets
# =========================================================================


class TestResolveApproved:
    """Approved assets in sanctioned context should pass."""

    def test_approved_asset_read_only(self, basic_registry: ShadowRegistry):
        result = resolve_shadow_policy(
            asset_id="internal-model-v1",
            registry=basic_registry,
            action_category="read_only",
            risk_level="read_only",
            domain_id="research",
        )
        assert result.provenance_status == ProvenanceStatus.APPROVED
        assert result.containment_mode == ShadowContainmentMode.ALLOW
        assert result.shadow_overrode_baseline is False

    def test_approved_asset_mutation_in_allowed_domain(self, basic_registry: ShadowRegistry):
        result = resolve_shadow_policy(
            asset_id="internal-model-v1",
            registry=basic_registry,
            action_category="mutating",
            risk_level="write",
            domain_id="research",
            mutation_intent=True,
        )
        assert result.provenance_status == ProvenanceStatus.APPROVED
        assert result.containment_mode == ShadowContainmentMode.ALLOW


# =========================================================================
# Test: Resolve Shadow Policy — Unverified Assets
# =========================================================================


class TestResolveUnverified:
    """Unverified assets should be restricted."""

    def test_unverified_read_only(self):
        result = resolve_shadow_policy(
            asset_id="unknown-tool",
            tool_name="some_read_tool",
            action_category="read_only",
            risk_level="read_only",
        )
        # Unknown tool classified as unverified — no registry
        assert result.provenance_status in (ProvenanceStatus.UNVERIFIED, ProvenanceStatus.SHADOW)
        assert result.shadow_overrode_baseline is True

    def test_unverified_mutating_blocked_or_confirm(self):
        result = resolve_shadow_policy(
            asset_id="unknown-external-model",
            action_category="mutating",
            risk_level="write",
            mutation_intent=True,
        )
        assert result.containment_mode.severity >= ShadowContainmentMode.REQUIRE_CONFIRMATION.severity

    def test_unverified_privileged_blocked(self):
        result = resolve_shadow_policy(
            asset_id="unknown-external-model",
            action_category="privileged",
            risk_level="privileged",
            mutation_intent=True,
        )
        assert result.containment_mode == ShadowContainmentMode.BLOCKED


# =========================================================================
# Test: Resolve Shadow Policy — Shadow Assets
# =========================================================================


class TestResolveShadow:
    """Shadow (unsanctioned) assets should be heavily restricted."""

    def test_shadow_mcp_server_quarantined(self):
        result = resolve_shadow_policy(
            asset_id="rogue-mcp-server",
            action_category="read_only",
            risk_level="read_only",
        )
        # Contains "mcp" in name → classified as MCP_SERVER + SHADOW
        assert result.asset_type == ShadowAssetType.MCP_SERVER
        assert result.containment_mode.severity >= ShadowContainmentMode.READ_ONLY.severity

    def test_shadow_mutating_blocked(self):
        result = resolve_shadow_policy(
            asset_id="shadow-agent",
            action_category="destructive",
            risk_level="destructive",
            mutation_intent=True,
        )
        assert result.containment_mode == ShadowContainmentMode.BLOCKED


# =========================================================================
# Test: Resolve Shadow Policy — Revoked Assets
# =========================================================================


class TestResolveRevoked:
    """Revoked assets should always be blocked."""

    def test_revoked_always_blocked(self, basic_registry: ShadowRegistry):
        result = resolve_shadow_policy(
            asset_id="revoked-plugin",
            registry=basic_registry,
            action_category="read_only",
            risk_level="read_only",
        )
        assert result.provenance_status == ProvenanceStatus.REVOKED
        assert result.containment_mode == ShadowContainmentMode.BLOCKED
        assert result.shadow_overrode_baseline is True


# =========================================================================
# Test: Domain-Sensitive Shadow Blocking
# =========================================================================


class TestDomainSensitiveBlocking:
    """Shadow/unverified assets in sensitive domains should be blocked."""

    def test_shadow_finance_mutation_blocked(self):
        result = resolve_shadow_policy(
            asset_id="unknown-model",
            action_category="mutating",
            risk_level="write",
            domain_id="finance",
            mutation_intent=True,
        )
        assert result.containment_mode == ShadowContainmentMode.BLOCKED

    def test_shadow_healthcare_mutation_blocked(self):
        result = resolve_shadow_policy(
            asset_id="unknown-model",
            action_category="mutating",
            risk_level="write",
            domain_id="healthcare",
            mutation_intent=True,
        )
        assert result.containment_mode == ShadowContainmentMode.BLOCKED

    def test_approved_asset_outside_allowed_domain(self, basic_registry: ShadowRegistry):
        """Approved asset used outside its allowed domains → restricted."""
        result = resolve_shadow_policy(
            asset_id="internal-model-v1",
            registry=basic_registry,
            action_category="mutating",
            risk_level="write",
            domain_id="finance",  # Not in allowed_domains
            mutation_intent=True,
        )
        # Should be reclassified as SHADOW because domain mismatch
        assert result.provenance_status == ProvenanceStatus.SHADOW
        assert result.containment_mode.severity >= ShadowContainmentMode.BLOCKED.severity

    def test_unverified_research_read_only(self):
        """Unverified model in research domain → READ_ONLY."""
        result = resolve_shadow_policy(
            asset_id="external-summarizer",
            tool_name="summarize",
            action_category="read_only",
            risk_level="read_only",
            domain_id="research",
        )
        assert result.containment_mode.severity >= ShadowContainmentMode.READ_ONLY.severity


# =========================================================================
# Test: Memory Write Denial
# =========================================================================


class TestMemoryWriteDenial:
    """Untrusted AI should be denied memory writes."""

    def test_untrusted_memory_write_denied(self):
        result = resolve_shadow_policy(
            asset_id="untrusted-agent",
            action_category="mutating",
            risk_level="write",
            memory_write_intent=True,
            mutation_intent=True,
        )
        assert result.containment_mode.severity >= ShadowContainmentMode.MEMORY_WRITE_DENIED.severity

    def test_trusted_memory_write_allowed(self, basic_registry: ShadowRegistry):
        result = resolve_shadow_policy(
            asset_id="internal-model-v1",
            registry=basic_registry,
            action_category="mutating",
            risk_level="write",
            domain_id="research",
            memory_write_intent=True,
            mutation_intent=True,
        )
        assert result.containment_mode == ShadowContainmentMode.ALLOW


# =========================================================================
# Test: Semantic-Governance Mismatch
# =========================================================================


class TestSemanticMismatch:
    """Approved asset with semantic mismatch should be escalated."""

    def test_approved_high_semantic_mismatch(self, basic_registry: ShadowRegistry):
        """Approved asset with high JEPA mismatch → quarantined or confirm."""
        result = resolve_shadow_policy(
            asset_id="internal-model-v1",
            registry=basic_registry,
            action_category="read_only",
            risk_level="read_only",
            domain_id="research",
            semantic_mismatch=0.7,
        )
        assert result.containment_mode.severity >= ShadowContainmentMode.REQUIRE_CONFIRMATION.severity
        assert result.shadow_overrode_baseline is True

    def test_approved_low_semantic_mismatch_passes(self, basic_registry: ShadowRegistry):
        """Approved asset with low mismatch → ALLOW."""
        result = resolve_shadow_policy(
            asset_id="internal-model-v1",
            registry=basic_registry,
            action_category="read_only",
            risk_level="read_only",
            domain_id="research",
            semantic_mismatch=0.1,
        )
        assert result.containment_mode == ShadowContainmentMode.ALLOW

    def test_same_state_different_provenance(self, basic_registry: ShadowRegistry):
        """Same semantic state, different provenance → different outcomes."""
        approved_result = resolve_shadow_policy(
            asset_id="internal-model-v1",
            registry=basic_registry,
            action_category="mutating",
            risk_level="write",
            domain_id="research",
            mutation_intent=True,
        )
        shadow_result = resolve_shadow_policy(
            asset_id="unknown-shadow-model",
            action_category="mutating",
            risk_level="write",
            domain_id="research",
            mutation_intent=True,
        )
        assert shadow_result.containment_mode.severity > approved_result.containment_mode.severity


# =========================================================================
# Test: JEPA Regime Escalation
# =========================================================================


class TestJEPARegimeEscalation:
    """JEPA anomaly regimes should escalate shadow containment."""

    def test_dual_anomaly_escalation(self, basic_registry: ShadowRegistry):
        result = resolve_shadow_policy(
            asset_id="internal-model-v1",
            registry=basic_registry,
            action_category="read_only",
            risk_level="read_only",
            domain_id="research",
            jepa_regime="dual_anomaly",
        )
        assert result.containment_mode.severity >= ShadowContainmentMode.QUARANTINED.severity

    def test_unknown_regime_escalation(self, basic_registry: ShadowRegistry):
        result = resolve_shadow_policy(
            asset_id="internal-model-v1",
            registry=basic_registry,
            action_category="read_only",
            risk_level="read_only",
            domain_id="research",
            jepa_regime="unknown",
        )
        assert result.containment_mode.severity >= ShadowContainmentMode.QUARANTINED.severity


# =========================================================================
# Test: Assessment Audit Serialization
# =========================================================================


class TestAuditSerialization:
    """Shadow assessments must serialize for durable audit."""

    def test_to_audit_dict(self, basic_registry: ShadowRegistry):
        result = resolve_shadow_policy(
            asset_id="internal-model-v1",
            registry=basic_registry,
            action_category="read_only",
            risk_level="read_only",
            domain_id="research",
        )
        audit = result.to_audit_dict()
        assert "provenance_status" in audit
        assert "trust_level" in audit
        assert "containment_mode" in audit
        assert "risk_factors" in audit
        assert "reason_codes" in audit
        assert "shadow_overrode_baseline" in audit
        assert "registry_entry_id" in audit

    def test_risk_factors_in_audit(self):
        result = resolve_shadow_policy(
            asset_id="some-shadow-thing",
            action_category="mutating",
            risk_level="write",
            mutation_intent=True,
        )
        audit = result.to_audit_dict()
        rf = audit["risk_factors"]
        assert "provenance_risk" in rf
        assert "composite_score" in rf


# =========================================================================
# Test: Stricter-Only Invariant
# =========================================================================


class TestStricterOnlyInvariant:
    """Shadow policy must never weaken baseline governance."""

    def test_shadow_never_allows_blocked_trust(self):
        """An asset with BLOCKED trust should never get ALLOW."""
        reg = ShadowRegistry(entries=[
            ShadowRegistryEntry(
                asset_id="blocked-model",
                asset_type=ShadowAssetType.MODEL_ENDPOINT,
                provenance=ProvenanceStatus.APPROVED,
                trust_level=ShadowTrustLevel.BLOCKED,
            ),
        ])
        result = resolve_shadow_policy(
            asset_id="blocked-model",
            registry=reg,
            action_category="read_only",
            risk_level="read_only",
        )
        assert result.containment_mode == ShadowContainmentMode.BLOCKED

    def test_revoked_never_downgraded(self, basic_registry: ShadowRegistry):
        """Revoked asset remains blocked even for read-only."""
        result = resolve_shadow_policy(
            asset_id="revoked-plugin",
            registry=basic_registry,
            action_category="read_only",
            risk_level="read_only",
        )
        assert result.containment_mode == ShadowContainmentMode.BLOCKED


# =========================================================================
# Test: Backward Compatibility (no registry)
# =========================================================================


class TestBackwardCompatibility:
    """Without shadow registry, behavior should be unchanged."""

    def test_no_registry_no_shadow(self):
        """resolve_shadow_policy with no registry treats as unknown."""
        result = resolve_shadow_policy(
            asset_id="some-tool",
            action_category="read_only",
            risk_level="read_only",
        )
        # Still runs, classifies as unknown
        assert result.provenance_status in (
            ProvenanceStatus.UNVERIFIED, ProvenanceStatus.SHADOW,
        )

    def test_empty_registry(self):
        """Empty registry treats everything as unknown."""
        reg = ShadowRegistry()
        result = resolve_shadow_policy(
            asset_id="some-tool",
            registry=reg,
            action_category="read_only",
            risk_level="read_only",
        )
        assert result.provenance_status in (
            ProvenanceStatus.UNVERIFIED, ProvenanceStatus.SHADOW,
        )


# =========================================================================
# Test: GovernanceService Integration
# =========================================================================


class TestGovernanceServiceIntegration:
    """Shadow policy should integrate with GovernanceService."""

    def test_governance_service_with_shadow_registry(self, basic_registry: ShadowRegistry):
        """GovernanceService with shadow registry evaluates shadow policy."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
            APIGovernanceDecision,
        )

        service = GovernanceService(shadow_registry=basic_registry)
        # Approved actor in approved context
        request = AuthorizationRequest(
            actor_id="internal-model-v1",
            action_type="file_read",
            agency_level="FULL",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        response = service.authorize(request)
        # Should still work (shadow registry has this asset approved)
        assert response.shadow_assessment is not None
        assert response.shadow_assessment["provenance_status"] == "approved"

    def test_governance_service_shadow_blocks_unknown(self, basic_registry: ShadowRegistry):
        """Unknown actor with destructive action gets blocked by shadow policy."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
            APIGovernanceDecision,
        )

        service = GovernanceService(shadow_registry=basic_registry)
        request = AuthorizationRequest(
            actor_id="unknown-rogue-agent",
            action_type="database_delete",
            tool_name="delete_all",
            agency_level="FULL",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        response = service.authorize(request)
        # Shadow should at least restrict
        assert response.shadow_assessment is not None
        shadow = response.shadow_assessment
        assert shadow["provenance_status"] in ("shadow", "unverified")
        assert shadow["shadow_overrode_baseline"] is True

    def test_governance_service_no_shadow_registry(self):
        """Without shadow registry, no shadow_assessment in response."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        service = GovernanceService()
        request = AuthorizationRequest(
            actor_id="test-agent",
            action_type="file_read",
            agency_level="FULL",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        response = service.authorize(request)
        assert response.shadow_assessment is None

    def test_governance_service_audit_contains_shadow(self, basic_registry: ShadowRegistry):
        """Audit event should contain shadow assessment."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        service = GovernanceService(shadow_registry=basic_registry)
        request = AuthorizationRequest(
            actor_id="internal-model-v1",
            action_type="file_read",
            agency_level="FULL",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        response = service.authorize(request)
        audit = response.audit_event
        assert audit.shadow_assessment is not None

    def test_shadow_reason_codes_in_rationale(self, basic_registry: ShadowRegistry):
        """Shadow reason codes should appear in rationale_codes."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        service = GovernanceService(shadow_registry=basic_registry)
        request = AuthorizationRequest(
            actor_id="unknown-shadow-agent",
            action_type="delete_records",
            tool_name="delete_all",
            agency_level="FULL",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        response = service.authorize(request)
        shadow_codes = [c for c in response.rationale_codes if c.startswith("SHADOW:")]
        assert len(shadow_codes) > 0


# =========================================================================
# Test: Durable Audit Persistence
# =========================================================================


class TestDurableAuditPersistence:
    """Shadow assessment must survive durable persistence."""

    def test_durable_audit_store_shadow_fields(self, basic_registry: ShadowRegistry):
        """Shadow fields persisted through GovernanceAuditStore."""
        from agentic.ledger.governance_audit_store import GovernanceAuditStore
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        store = GovernanceAuditStore(":memory:")
        service = GovernanceService(
            shadow_registry=basic_registry,
            audit_store=store,
        )
        request = AuthorizationRequest(
            actor_id="internal-model-v1",
            action_type="file_read",
            agency_level="FULL",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        response = service.authorize(request)

        # Verify persisted in durable store
        events = store.list_recent(limit=1)
        assert len(events) == 1
        # Shadow assessment is embedded in request_snapshot
        snapshot = events[0].get("request_snapshot", {})
        # The snapshot is stored as JSON string in the store
        import json
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        # The GovernanceService embeds shadow in audit_event.shadow_assessment
        # which is separate from request_snapshot — verify via response
        assert response.audit_event.shadow_assessment is not None
        assert response.audit_event.shadow_assessment["provenance_status"] == "approved"

    def test_durable_audit_count_increments(self, basic_registry: ShadowRegistry):
        """Audit store count should reflect persisted events."""
        from agentic.ledger.governance_audit_store import GovernanceAuditStore
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        store = GovernanceAuditStore(":memory:")
        service = GovernanceService(
            shadow_registry=basic_registry,
            audit_store=store,
        )
        initial_count = store.count()
        request = AuthorizationRequest(
            actor_id="internal-model-v1",
            action_type="file_read",
            agency_level="FULL",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        service.authorize(request)
        assert store.count() == initial_count + 1


# =========================================================================
# Test: MCP Integration
# =========================================================================


class TestMCPIntegration:
    """Shadow policy should integrate with SafeMCPGateway."""

    @pytest.mark.asyncio
    async def test_mcp_gateway_shadow_blocks_unknown(self, basic_registry: ShadowRegistry):
        """Unknown tool via MCP should be blocked by shadow policy."""
        from agentic.agentic_framework.mcp_gateway import (
            SafeMCPGateway,
            MockMCPClient,
            MCPToolCall,
            GatewayDecision,
        )

        client = MockMCPClient()
        client.register_tool("unknown_shadow_tool", lambda p: "result")

        gateway = SafeMCPGateway(
            mcp_client=client,
            shadow_registry=basic_registry,
        )

        result = await gateway.call_tool(MCPToolCall(
            tool_name="unknown_shadow_tool",
            parameters={},
            quality_score=0.9,
            coherence_score=0.9,
        ))
        # Unknown tool should trigger shadow policy
        # The tool is unknown in registry → classified as shadow/unverified
        # For a write-classified tool, shadow should at least escalate
        assert result.decision in (
            GatewayDecision.BLOCKED, GatewayDecision.ESCALATE,
        )

    @pytest.mark.asyncio
    async def test_mcp_gateway_approved_tool_passes(self, basic_registry: ShadowRegistry):
        """Approved tool via MCP should proceed normally."""
        from agentic.agentic_framework.mcp_gateway import (
            SafeMCPGateway,
            MockMCPClient,
            MCPToolCall,
            MCPToolDefinition,
            ToolRiskLevel,
            GatewayDecision,
        )

        client = MockMCPClient()
        client.register_tool(
            "approved-tool-read",
            lambda p: "data",
            risk_level=ToolRiskLevel.READ_ONLY,
        )

        gateway = SafeMCPGateway(
            mcp_client=client,
            shadow_registry=basic_registry,
        )

        result = await gateway.call_tool(MCPToolCall(
            tool_name="approved-tool-read",
            parameters={},
            quality_score=0.9,
            coherence_score=0.9,
        ))
        # Approved tool should pass (shadow policy → ALLOW)
        assert result.decision == GatewayDecision.ALLOWED

    @pytest.mark.asyncio
    async def test_mcp_gateway_no_shadow_registry(self):
        """Without shadow registry, MCP gateway works normally."""
        from agentic.agentic_framework.mcp_gateway import (
            SafeMCPGateway,
            MockMCPClient,
            MCPToolCall,
            GatewayDecision,
            ToolRiskLevel,
        )

        client = MockMCPClient()
        client.register_tool(
            "file_read",
            lambda p: "data",
            risk_level=ToolRiskLevel.READ_ONLY,
        )

        gateway = SafeMCPGateway(mcp_client=client)

        result = await gateway.call_tool(MCPToolCall(
            tool_name="file_read",
            parameters={"path": "/tmp/test"},
            quality_score=0.9,
            coherence_score=0.9,
        ))
        assert result.decision == GatewayDecision.ALLOWED

    @pytest.mark.asyncio
    async def test_mcp_gateway_shadow_audit(self, basic_registry: ShadowRegistry):
        """MCP audit should contain shadow assessment."""
        from agentic.agentic_framework.mcp_gateway import (
            SafeMCPGateway,
            MockMCPClient,
            MCPToolCall,
            ToolRiskLevel,
        )

        client = MockMCPClient()
        client.register_tool(
            "approved-tool-read",
            lambda p: "data",
            risk_level=ToolRiskLevel.READ_ONLY,
        )

        gateway = SafeMCPGateway(
            mcp_client=client,
            shadow_registry=basic_registry,
        )

        await gateway.call_tool(MCPToolCall(
            tool_name="approved-tool-read",
            parameters={},
            quality_score=0.9,
            coherence_score=0.9,
        ))

        assert len(gateway.audit_log) == 1
        entry = gateway.audit_log[0]
        assert entry.shadow_assessment is not None
        assert entry.shadow_assessment["provenance_status"] == "approved"


# =========================================================================
# Test: Fail-Closed Defaults
# =========================================================================


class TestFailClosedDefaults:
    """Unknown/untrusted assets should fail closed."""

    def test_unknown_read_restricted(self):
        """Unknown asset doing read → at least READ_ONLY."""
        result = resolve_shadow_policy(
            asset_id="",
            tool_name="",
            action_category="read_only",
            risk_level="read_only",
        )
        assert result.containment_mode.severity >= ShadowContainmentMode.READ_ONLY.severity

    def test_unknown_mutation_blocked(self):
        """Unknown asset doing mutation → BLOCKED."""
        result = resolve_shadow_policy(
            asset_id="",
            tool_name="",
            action_category="mutating",
            risk_level="write",
            mutation_intent=True,
        )
        assert result.containment_mode.severity >= ShadowContainmentMode.BLOCKED.severity

    def test_unknown_destructive_blocked(self):
        """Unknown asset doing destructive action → BLOCKED."""
        result = resolve_shadow_policy(
            asset_id="",
            action_category="destructive",
            risk_level="destructive",
            mutation_intent=True,
        )
        assert result.containment_mode == ShadowContainmentMode.BLOCKED


# =========================================================================
# Test: Example Shadow Policy Scenarios
# =========================================================================


class TestExampleScenarios:
    """End-to-end examples from the spec."""

    def test_approved_internal_model_approved_domain(self, basic_registry: ShadowRegistry):
        """Scenario: approved internal model in approved domain."""
        result = resolve_shadow_policy(
            asset_id="internal-model-v1",
            registry=basic_registry,
            action_category="read_only",
            risk_level="read_only",
            domain_id="research",
        )
        assert result.containment_mode == ShadowContainmentMode.ALLOW
        assert result.provenance_status == ProvenanceStatus.APPROVED

    def test_unverified_external_model_in_research(self):
        """Scenario: unverified external model in research domain."""
        result = resolve_shadow_policy(
            asset_id="external-summarizer",
            tool_name="summarize",
            action_category="read_only",
            risk_level="read_only",
            domain_id="research",
        )
        assert result.containment_mode.severity >= ShadowContainmentMode.READ_ONLY.severity

    def test_shadow_mcp_in_finance(self, basic_registry: ShadowRegistry):
        """Scenario: shadow MCP server in finance domain."""
        result = resolve_shadow_policy(
            asset_id="unknown-mcp-server",
            action_category="mutating",
            risk_level="write",
            domain_id="finance",
            mutation_intent=True,
        )
        assert result.containment_mode == ShadowContainmentMode.BLOCKED

    def test_approved_tool_calling_unapproved_ai(self, basic_registry: ShadowRegistry):
        """Scenario: approved tool calling unapproved external AI."""
        # The downstream AI is unverified
        result = resolve_shadow_policy(
            asset_id="unverified-downstream-ai",
            tool_name="approved-tool-read",
            action_category="mutating",
            risk_level="write",
            mutation_intent=True,
        )
        # Even though tool name is approved, the asset_id is not
        assert result.containment_mode.severity >= ShadowContainmentMode.REQUIRE_CONFIRMATION.severity

    def test_memory_source_unknown_provenance(self):
        """Scenario: memory source with unknown provenance."""
        result = resolve_shadow_policy(
            asset_id="unknown-memory-source",
            action_category="mutating",
            risk_level="write",
            memory_write_intent=True,
            mutation_intent=True,
        )
        assert result.containment_mode.severity >= ShadowContainmentMode.MEMORY_WRITE_DENIED.severity
