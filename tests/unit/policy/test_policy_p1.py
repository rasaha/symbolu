"""
Policy Phase P1 — Service Exposure Tests

Tests for the Policy Phase P1 implementation:
- P1-A: PolicyService.compute_policy() wraps policy engine correctly
- P1-B: PolicyService.resolve_interaction_mode() with overrides
- P1-C: PolicyService.compute_session_policy() and compute_trading_guardrails()
- P1-D: Audit hooks — every call produces audit entries
- Backward compat: Direct imports still work
- GovernanceService.get_policy_service() integration
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

from agentic.policy.policy_service import (
    PolicyService,
    get_policy_service,
    P1_VERSION,
)
from agentic.policy.interaction_modes import InteractionMode
from agentic.policy.session_policy import SessionPolicyFlags
from agentic.policy.trading_guardrail_engine import TradingGuardrailFlags


# =============================================================================
# Helpers
# =============================================================================


def _make_unified(
    coherence_score: float = 0.70,
    persona_drift: float = 0.30,
    mapper_volatility: float = 0.20,
    temporal_arc: float = 0.80,
    normalized_entropy: float = 0.40,
) -> dict:
    """Build a minimal unified output dict for policy engine."""
    return {
        "coherence": {
            "coherence_score": coherence_score,
            "persona_drift_score": persona_drift,
            "mapper_volatility_score": mapper_volatility,
            "temporal_arc_score": temporal_arc,
        },
        "entropy": {
            "normalized_entropy": normalized_entropy,
        },
    }


def _make_session_summary(
    coherence_score: float = 0.75,
    persona_drift_score: float = 0.25,
    semantic_stability_score: float = 0.70,
    temporal_arc_score: float = 0.65,
    mapper_volatility_score: float = 0.20,
) -> MagicMock:
    """Build a mock SessionSummary."""
    mock = MagicMock()
    mock.coherence_score = coherence_score
    mock.persona_drift_score = persona_drift_score
    mock.semantic_stability_score = semantic_stability_score
    mock.temporal_arc_score = temporal_arc_score
    mock.mapper_volatility_score = mapper_volatility_score
    return mock


def _make_trading_summary(
    coherence_score: float = 0.50,
    mapper_volatility_score: float = 0.65,
    persona_drift_score: float = 0.50,
    tension_corridor: float = 0.75,
    resonance_index: float = 0.40,
    delta_smi: float = -0.15,
    max_tension_allowed: float = 0.70,
    max_negative_delta_smi: float = 0.12,
    max_volatility_allowed: float = 0.60,
) -> MagicMock:
    """Build a mock SessionSummary for trading guardrails."""
    mock = MagicMock()
    mock.coherence_score = coherence_score
    mock.mapper_volatility_score = mapper_volatility_score
    mock.persona_drift_score = persona_drift_score
    mock.tension_corridor = tension_corridor
    mock.resonance_index = resonance_index
    mock.delta_smi = delta_smi
    mock.max_tension_allowed = max_tension_allowed
    mock.max_negative_delta_smi = max_negative_delta_smi
    mock.max_volatility_allowed = max_volatility_allowed
    return mock


# =============================================================================
# P1-A: PolicyService.compute_policy()
# =============================================================================


class TestComputePolicy(unittest.TestCase):
    """Test PolicyService wraps compute_policy_flags correctly."""

    def setUp(self):
        self.svc = PolicyService()

    def test_returns_flags_dict(self):
        """compute_policy() returns a dict with flags key."""
        result = self.svc.compute_policy(_make_unified(), domain="trading")
        self.assertIn("flags", result)
        self.assertIsInstance(result["flags"], dict)

    def test_returns_metadata(self):
        """compute_policy() includes version, domain, timestamp."""
        result = self.svc.compute_policy(_make_unified(), domain="trading")
        self.assertEqual(result["domain"], "trading")
        self.assertEqual(result["version"], P1_VERSION)
        self.assertIn("timestamp", result)

    def test_flags_contain_expected_keys(self):
        """Flags dict has all standard policy flag keys."""
        result = self.svc.compute_policy(_make_unified(), domain="trading")
        flags = result["flags"]
        for key in [
            "needs_grounding",
            "allow_deep_reflection",
            "prefer_concrete",
            "prefer_arc_mode",
            "coherence_warning",
            "stability_status",
            "recommended_style",
            "recommended_mapper",
            "interaction_mode",
        ]:
            self.assertIn(key, flags, f"Missing flag: {key}")

    def test_deterministic_same_input(self):
        """Same input produces same flags (minus timestamp)."""
        unified = _make_unified()
        r1 = self.svc.compute_policy(unified, domain="trading")
        r2 = self.svc.compute_policy(unified, domain="trading")
        self.assertEqual(r1["flags"], r2["flags"])

    def test_trading_default_mode_analytics_only(self):
        """Trading domain defaults to analytics_only interaction mode."""
        result = self.svc.compute_policy(_make_unified(), domain="trading")
        self.assertEqual(result["flags"]["interaction_mode"], "analytics_only")

    def test_low_coherence_triggers_grounding(self):
        """Low coherence score triggers needs_grounding."""
        unified = _make_unified(coherence_score=0.30)
        result = self.svc.compute_policy(unified, domain="trading")
        self.assertTrue(result["flags"]["needs_grounding"])

    def test_high_coherence_no_grounding(self):
        """High coherence score does not trigger needs_grounding."""
        unified = _make_unified(coherence_score=0.80, persona_drift=0.20)
        result = self.svc.compute_policy(unified, domain="trading")
        self.assertFalse(result["flags"]["needs_grounding"])

    def test_admin_mode_override(self):
        """Admin override flows through to flags."""
        result = self.svc.compute_policy(
            _make_unified(),
            domain="trading",
            admin_mode_override="deep_adaptive",
        )
        self.assertEqual(result["flags"]["interaction_mode"], "deep_adaptive")


# =============================================================================
# P1-B: PolicyService.resolve_interaction_mode()
# =============================================================================


class TestResolveInteractionMode(unittest.TestCase):
    """Test interaction mode resolution through PolicyService."""

    def setUp(self):
        self.svc = PolicyService()

    def test_default_trading(self):
        """Trading domain defaults to ANALYTICS_ONLY."""
        result = self.svc.resolve_interaction_mode(domain="trading")
        self.assertEqual(result["mode"], InteractionMode.ANALYTICS_ONLY)
        self.assertEqual(result["mode_value"], "analytics_only")

    def test_returns_metadata(self):
        """Result includes mode_name, domain, version, timestamp."""
        result = self.svc.resolve_interaction_mode(domain="trading")
        self.assertEqual(result["mode_name"], "Analytics Only")
        self.assertEqual(result["domain"], "trading")
        self.assertEqual(result["version"], P1_VERSION)
        self.assertIn("timestamp", result)

    def test_user_override(self):
        """User override changes resolved mode."""
        result = self.svc.resolve_interaction_mode(
            domain="trading",
            user_override="smart_insight",
        )
        self.assertEqual(result["mode"], InteractionMode.SMART_INSIGHT)

    def test_admin_override_beats_user(self):
        """Admin override takes priority over user override."""
        result = self.svc.resolve_interaction_mode(
            domain="trading",
            user_override="smart_insight",
            admin_override="deep_adaptive",
        )
        self.assertEqual(result["mode"], InteractionMode.DEEP_ADAPTIVE)

    def test_invalid_override_falls_back(self):
        """Invalid override falls back to domain default."""
        result = self.svc.resolve_interaction_mode(
            domain="trading",
            user_override="nonexistent_mode",
        )
        self.assertEqual(result["mode"], InteractionMode.ANALYTICS_ONLY)


# =============================================================================
# P1-C: Session Policy
# =============================================================================


class TestComputeSessionPolicy(unittest.TestCase):
    """Test session policy computation through PolicyService."""

    def setUp(self):
        self.svc = PolicyService()

    def test_stable_session(self):
        """Stable session returns expected flags."""
        summary = _make_session_summary(coherence_score=0.80)
        result = self.svc.compute_session_policy(summary)
        self.assertIsNotNone(result["flags"])
        self.assertTrue(result["flags"]["session_is_stable"])

    def test_fragmented_session(self):
        """Low coherence returns fragmented session."""
        summary = _make_session_summary(coherence_score=0.30, persona_drift_score=0.60)
        result = self.svc.compute_session_policy(summary)
        self.assertTrue(result["flags"]["session_is_fragmented"])
        self.assertTrue(result["flags"]["session_needs_grounding"])

    def test_none_summary(self):
        """None session summary returns flags=None."""
        result = self.svc.compute_session_policy(None)
        self.assertIsNone(result["flags"])
        self.assertIsNone(result["flags_obj"])

    def test_flags_obj_and_dict_match(self):
        """flags_obj.to_dict() matches flags dict."""
        summary = _make_session_summary()
        result = self.svc.compute_session_policy(summary)
        self.assertEqual(result["flags"], result["flags_obj"].to_dict())

    def test_returns_metadata(self):
        """Result includes version and timestamp."""
        result = self.svc.compute_session_policy(_make_session_summary())
        self.assertEqual(result["version"], P1_VERSION)
        self.assertIn("timestamp", result)


# =============================================================================
# P1-C: Trading Guardrails
# =============================================================================


class TestComputeTradingGuardrails(unittest.TestCase):
    """Test trading guardrail computation through PolicyService."""

    def setUp(self):
        self.svc = PolicyService()

    def test_high_risk_scenario(self):
        """High tension + low resonance triggers recommend_no_action."""
        summary = _make_trading_summary()
        result = self.svc.compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )
        self.assertTrue(result["flags"]["recommend_no_action"])
        self.assertTrue(result["flags"]["high_tension_risk"])

    def test_safe_scenario(self):
        """No risk flags when metrics are healthy."""
        summary = _make_trading_summary(
            coherence_score=0.80,
            tension_corridor=0.30,
            resonance_index=0.70,
            delta_smi=0.05,
            mapper_volatility_score=0.20,
            persona_drift_score=0.20,
        )
        result = self.svc.compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )
        self.assertFalse(result["flags"]["recommend_no_action"])

    def test_flags_obj_and_dict_match(self):
        """flags_obj.to_dict() matches flags dict."""
        summary = _make_trading_summary()
        result = self.svc.compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )
        self.assertEqual(result["flags"], result["flags_obj"].to_dict())

    def test_returns_metadata(self):
        """Result includes version and timestamp."""
        result = self.svc.compute_trading_guardrails(
            summary=_make_trading_summary(),
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )
        self.assertEqual(result["version"], P1_VERSION)
        self.assertIn("timestamp", result)


# =============================================================================
# P1-D: Audit Hooks
# =============================================================================


class TestPolicyAuditLog(unittest.TestCase):
    """Test that every PolicyService call produces audit entries."""

    def setUp(self):
        self.svc = PolicyService()

    def test_compute_policy_creates_audit_entry(self):
        """compute_policy() produces an audit entry."""
        self.svc.compute_policy(_make_unified(), domain="trading")
        log = self.svc.get_policy_audit_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["event_type"], "compute_policy")
        self.assertEqual(log[0]["domain"], "trading")

    def test_resolve_interaction_mode_creates_audit_entry(self):
        """resolve_interaction_mode() produces an audit entry."""
        self.svc.resolve_interaction_mode(domain="trading")
        log = self.svc.get_policy_audit_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["event_type"], "resolve_interaction_mode")

    def test_session_policy_creates_audit_entry(self):
        """compute_session_policy() produces an audit entry."""
        self.svc.compute_session_policy(_make_session_summary())
        log = self.svc.get_policy_audit_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["event_type"], "compute_session_policy")

    def test_trading_guardrails_creates_audit_entry(self):
        """compute_trading_guardrails() produces an audit entry."""
        self.svc.compute_trading_guardrails(
            _make_trading_summary(), None, None, None, None
        )
        log = self.svc.get_policy_audit_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["event_type"], "compute_trading_guardrails")

    def test_multiple_calls_accumulate(self):
        """Multiple calls accumulate audit entries."""
        self.svc.compute_policy(_make_unified(), domain="trading")
        self.svc.resolve_interaction_mode(domain="trading")
        self.svc.compute_session_policy(_make_session_summary())
        log = self.svc.get_policy_audit_log()
        self.assertEqual(len(log), 3)

    def test_audit_entries_have_required_fields(self):
        """Audit entries contain event_type, timestamp, decision_id, summary."""
        self.svc.compute_policy(_make_unified(), domain="trading")
        entry = self.svc.get_policy_audit_log()[0]
        for field in ["event_type", "timestamp", "decision_id", "domain", "summary", "service_version"]:
            self.assertIn(field, entry, f"Missing audit field: {field}")

    def test_audit_decision_id_format(self):
        """Decision IDs start with ps- prefix."""
        self.svc.compute_policy(_make_unified(), domain="trading")
        entry = self.svc.get_policy_audit_log()[0]
        self.assertTrue(entry["decision_id"].startswith("ps-"))

    def test_audit_count(self):
        """get_policy_audit_count() tracks entries."""
        self.assertEqual(self.svc.get_policy_audit_count(), 0)
        self.svc.compute_policy(_make_unified(), domain="trading")
        self.assertEqual(self.svc.get_policy_audit_count(), 1)

    def test_clear_audit_log(self):
        """clear_policy_audit_log() empties the log."""
        self.svc.compute_policy(_make_unified(), domain="trading")
        self.svc.clear_policy_audit_log()
        self.assertEqual(self.svc.get_policy_audit_count(), 0)

    def test_audit_log_most_recent_first(self):
        """get_policy_audit_log() returns most recent first."""
        self.svc.compute_policy(_make_unified(), domain="trading")
        self.svc.resolve_interaction_mode(domain="trading")
        log = self.svc.get_policy_audit_log()
        self.assertEqual(log[0]["event_type"], "resolve_interaction_mode")
        self.assertEqual(log[1]["event_type"], "compute_policy")

    def test_compute_policy_audit_summary(self):
        """compute_policy audit entry has meaningful summary."""
        self.svc.compute_policy(_make_unified(), domain="trading")
        entry = self.svc.get_policy_audit_log()[0]
        summary = entry["summary"]
        self.assertIn("interaction_mode", summary)
        self.assertIn("needs_grounding", summary)
        self.assertIn("stability_status", summary)

    def test_none_session_audit_summary(self):
        """None session summary audit entry notes absence."""
        self.svc.compute_session_policy(None)
        entry = self.svc.get_policy_audit_log()[0]
        self.assertFalse(entry["summary"].get("session_summary_provided", True))


# =============================================================================
# PolicyService misc
# =============================================================================


class TestPolicyServiceMisc(unittest.TestCase):
    """Test PolicyService helper methods."""

    def test_get_domain_profile(self):
        """get_domain_profile returns profile with metadata."""
        svc = PolicyService()
        result = svc.get_domain_profile("trading")
        self.assertIn("profile", result)
        self.assertEqual(result["domain"], "trading")
        self.assertEqual(result["version"], P1_VERSION)

    def test_get_policy_service_factory(self):
        """get_policy_service() returns a PolicyService."""
        svc = get_policy_service()
        self.assertIsInstance(svc, PolicyService)

    def test_fresh_instances_have_separate_logs(self):
        """Each PolicyService instance has its own audit log."""
        svc1 = get_policy_service()
        svc2 = get_policy_service()
        svc1.compute_policy(_make_unified(), domain="trading")
        self.assertEqual(svc1.get_policy_audit_count(), 1)
        self.assertEqual(svc2.get_policy_audit_count(), 0)


# =============================================================================
# Backward Compatibility
# =============================================================================


class TestBackwardCompatibilityP1(unittest.TestCase):
    """Ensure direct imports still work alongside PolicyService."""

    def test_direct_compute_policy_flags_still_works(self):
        """Direct import of compute_policy_flags from policy_engine still works."""
        from agentic.policy.policy_engine import compute_policy_flags
        flags = compute_policy_flags(_make_unified(), domain="trading")
        self.assertIn("needs_grounding", flags)

    def test_direct_session_policy_still_works(self):
        """Direct import of compute_session_policy_flags still works."""
        from agentic.policy.session_policy import compute_session_policy_flags
        result = compute_session_policy_flags(_make_session_summary())
        self.assertIsInstance(result, SessionPolicyFlags)

    def test_direct_trading_guardrails_still_works(self):
        """Direct import of compute_trading_guardrails still works."""
        from agentic.policy.trading_guardrail_engine import compute_trading_guardrails
        result = compute_trading_guardrails(
            _make_trading_summary(), None, None, None, None
        )
        self.assertIsInstance(result, TradingGuardrailFlags)

    def test_package_level_imports(self):
        """P1 types are importable from agentic.policy."""
        from agentic.policy import (
            PolicyService,
            get_policy_service,
            P1_VERSION,
            SessionPolicyFlags,
            TradingGuardrailFlags,
        )
        self.assertIsNotNone(PolicyService)
        self.assertIsNotNone(P1_VERSION)


# =============================================================================
# GovernanceService integration
# =============================================================================


class TestGovernanceServicePolicyIntegration(unittest.TestCase):
    """Test GovernanceService.get_policy_service() integration."""

    def _make_governance_service(self):
        """Create a minimal GovernanceService for testing."""
        from agentic.agentic_framework.governance_service import GovernanceService
        return GovernanceService()

    def test_get_policy_service_returns_policy_service(self):
        """GovernanceService.get_policy_service() returns PolicyService."""
        gs = self._make_governance_service()
        ps = gs.get_policy_service()
        self.assertIsInstance(ps, PolicyService)

    def test_get_policy_service_is_cached(self):
        """Same PolicyService instance returned on repeated calls."""
        gs = self._make_governance_service()
        ps1 = gs.get_policy_service()
        ps2 = gs.get_policy_service()
        self.assertIs(ps1, ps2)

    def test_policy_audit_log_empty_without_usage(self):
        """get_policy_audit_log() returns empty before PolicyService is used."""
        gs = self._make_governance_service()
        self.assertEqual(gs.get_policy_audit_log(), [])

    def test_policy_audit_log_after_usage(self):
        """get_policy_audit_log() shows entries after PolicyService usage."""
        gs = self._make_governance_service()
        ps = gs.get_policy_service()
        ps.compute_policy(_make_unified(), domain="trading")
        log = gs.get_policy_audit_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["event_type"], "compute_policy")


# =============================================================================
# P0 Regression
# =============================================================================


class TestP0RegressionFromP1(unittest.TestCase):
    """Ensure P0 functionality is not broken by P1 additions."""

    def test_version_at_least_1_2(self):
        """Package version is at least 1.2.0 after P1."""
        from agentic.policy import __version__
        major, minor, patch = (int(x) for x in __version__.split("."))
        self.assertGreaterEqual((major, minor), (1, 2))

    def test_p0_exports_still_present(self):
        """P0 exports (DomainProfile, ProfileRegistry) still available."""
        from agentic.policy import (
            DomainProfile,
            ProfileRegistry,
            get_profile_registry,
        )
        self.assertIsNotNone(DomainProfile)
        self.assertIsNotNone(ProfileRegistry)
        self.assertIsNotNone(get_profile_registry)

    def test_facade_markers_unchanged(self):
        """Facade status markers from P0 still present."""
        from agentic.policy.governance_binding import _FACADE_STATUS
        self.assertEqual(_FACADE_STATUS, "provisional")

    def test_insight_window_markers_unchanged(self):
        """Insight window path markers from P0 still present."""
        from agentic.policy.insight_window_gating import _INSIGHT_WINDOW_PATH
        self.assertEqual(_INSIGHT_WINDOW_PATH, "policy_engine")


if __name__ == "__main__":
    unittest.main()
