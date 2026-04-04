"""
Policy Phase P3 — Deployment Lifecycle Tests

Tests for:
- P3-A: Lifecycle statuses and transitions
- P3-B: Activation and rollback behavior
- P3-C: Approval-aware hooks
- P3-D: Audit metadata and deployment history
- P3-E: Simulation-to-deployment linkage
- P3-F: PolicyService lifecycle methods
- P3-G: Backward compatibility / P0-P2 regression
"""

import json
import unittest
from unittest.mock import MagicMock

from agentic.policy.profile_schema import (
    DomainProfile,
    ProfileRegistry,
    get_profile_registry,
)
from agentic.policy.interaction_modes import InteractionMode
from agentic.policy.policy_lifecycle import (
    ProfileStatus,
    DeploymentRecord,
    PolicyLifecycleManager,
    PolicyLifecycleError,
)
from agentic.policy.policy_service import PolicyService


# =============================================================================
# Helpers
# =============================================================================


def _make_registry() -> ProfileRegistry:
    """Create a fresh registry for test isolation."""
    return ProfileRegistry()


def _make_candidate(
    profile_id: str = "trading_v2",
    version: str = "2.0.0",
    min_coherence: float = 0.50,
) -> DomainProfile:
    return DomainProfile(
        profile_id=profile_id,
        profile_version=version,
        min_coherence=min_coherence,
    )


def _make_unified(coherence_score: float = 0.70) -> dict:
    return {
        "coherence": {
            "coherence_score": coherence_score,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40},
    }


# =============================================================================
# P3-A: Lifecycle statuses and transitions
# =============================================================================


class TestProfileStatus(unittest.TestCase):
    """Test lifecycle status enum."""

    def test_all_statuses_exist(self):
        self.assertEqual(ProfileStatus.DRAFT.value, "draft")
        self.assertEqual(ProfileStatus.VALIDATED.value, "validated")
        self.assertEqual(ProfileStatus.ACTIVE.value, "active")
        self.assertEqual(ProfileStatus.SUPERSEDED.value, "superseded")
        self.assertEqual(ProfileStatus.ARCHIVED.value, "archived")

    def test_status_count(self):
        self.assertEqual(len(ProfileStatus), 5)


class TestLifecycleTransitions(unittest.TestCase):
    """Test valid and invalid lifecycle transitions."""

    def setUp(self):
        self.registry = _make_registry()
        self.mgr = PolicyLifecycleManager(self.registry)
        self.candidate = _make_candidate()

    def test_draft_to_validated(self):
        """DRAFT -> VALIDATED is valid."""
        self.mgr.stage_candidate("trading", self.candidate, "admin")
        record = self.mgr.validate_candidate("trading", "admin")
        self.assertEqual(record.status, ProfileStatus.VALIDATED)

    def test_validated_to_active(self):
        """VALIDATED -> ACTIVE is valid."""
        self.mgr.stage_candidate("trading", self.candidate, "admin")
        self.mgr.validate_candidate("trading", "admin")
        record = self.mgr.activate("trading", "admin", require_validation=True)
        self.assertEqual(record.status, ProfileStatus.ACTIVE)

    def test_draft_to_active_without_validation(self):
        """DRAFT -> ACTIVE is valid when require_validation=False."""
        self.mgr.stage_candidate("trading", self.candidate, "admin")
        record = self.mgr.activate("trading", "admin")
        self.assertEqual(record.status, ProfileStatus.ACTIVE)

    def test_draft_to_active_blocked_when_validation_required(self):
        """DRAFT -> ACTIVE raises when require_validation=True."""
        self.mgr.stage_candidate("trading", self.candidate, "admin")
        with self.assertRaises(PolicyLifecycleError):
            self.mgr.activate("trading", "admin", require_validation=True)

    def test_no_candidate_raises(self):
        """Activating without staged candidate raises."""
        with self.assertRaises(PolicyLifecycleError):
            self.mgr.activate("trading", "admin")

    def test_validate_without_candidate_raises(self):
        """Validating without staged candidate raises."""
        with self.assertRaises(PolicyLifecycleError):
            self.mgr.validate_candidate("trading", "admin")


# =============================================================================
# P3-B: Activation and rollback
# =============================================================================


class TestActivation(unittest.TestCase):
    """Test profile activation behavior."""

    def setUp(self):
        self.registry = _make_registry()
        self.mgr = PolicyLifecycleManager(self.registry)

    def test_activation_updates_registry(self):
        """Activated profile becomes the active registry profile."""
        candidate = _make_candidate(min_coherence=0.30)
        self.mgr.stage_candidate("trading", candidate, "admin")
        self.mgr.activate("trading", "admin")

        # Registry should now return the candidate
        active = self.registry.get("trading")
        self.assertEqual(active.min_coherence, 0.30)
        self.assertEqual(active.profile_id, "trading_v2")

    def test_activation_supersedes_previous(self):
        """Previous ACTIVE record is marked SUPERSEDED."""
        c1 = _make_candidate("v1", "1.0.0")
        self.mgr.stage_candidate("trading", c1, "admin")
        self.mgr.activate("trading", "admin")

        c2 = _make_candidate("v2", "2.0.0")
        self.mgr.stage_candidate("trading", c2, "admin")
        self.mgr.activate("trading", "admin")

        history = self.mgr.get_deployment_history("trading")
        statuses = [r["status"] for r in history]
        # Most recent first: active, superseded, draft, active(first), draft(first)
        self.assertIn("active", statuses)
        self.assertIn("superseded", statuses)

    def test_activation_records_previous_version(self):
        """Activation record carries previous_profile_id and previous_version."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        record = self.mgr.activate("trading", "admin")

        self.assertEqual(record.previous_profile_id, "trading")
        self.assertEqual(record.previous_version, "1.0.0")

    def test_activation_clears_candidate(self):
        """After activation, no candidate is staged."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        self.mgr.activate("trading", "admin")

        self.assertIsNone(self.mgr.get_candidate("trading"))

    def test_activation_with_approval_id(self):
        """Activation records the approval_id."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        record = self.mgr.activate(
            "trading", "admin", approval_id="appr-12345",
        )
        self.assertEqual(record.approval_id, "appr-12345")


class TestRollback(unittest.TestCase):
    """Test profile rollback behavior."""

    def setUp(self):
        self.registry = _make_registry()
        self.mgr = PolicyLifecycleManager(self.registry)

    def test_rollback_restores_previous(self):
        """Rollback restores the previous active profile."""
        original = self.registry.get("trading")
        original_coherence = original.min_coherence  # 0.55

        candidate = _make_candidate(min_coherence=0.30)
        self.mgr.stage_candidate("trading", candidate, "admin")
        self.mgr.activate("trading", "admin")

        # Verify candidate is active
        self.assertEqual(self.registry.get("trading").min_coherence, 0.30)

        # Rollback
        record = self.mgr.rollback("trading", "ops", "regression")
        self.assertEqual(record.status, ProfileStatus.ACTIVE)
        self.assertEqual(self.registry.get("trading").min_coherence, original_coherence)

    def test_rollback_without_history_raises(self):
        """Rollback with no previous version raises."""
        with self.assertRaises(PolicyLifecycleError):
            self.mgr.rollback("trading", "ops")

    def test_rollback_rationale_prefix(self):
        """Rollback record rationale starts with 'ROLLBACK:'."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        self.mgr.activate("trading", "admin")
        record = self.mgr.rollback("trading", "ops", "bad thresholds")
        self.assertTrue(record.rationale.startswith("ROLLBACK:"))


# =============================================================================
# P3-C: Approval hooks
# =============================================================================


class TestApprovalHooks(unittest.TestCase):
    """Test approval-aware activation hooks."""

    def setUp(self):
        self.registry = _make_registry()
        self.mgr = PolicyLifecycleManager(self.registry)

    def test_approval_payload_structure(self):
        """Approval payload has expected fields."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        payload = self.mgr.request_activation_approval(
            "trading", "admin", "tuning",
        )
        self.assertEqual(payload["approval_type"], "policy_activation")
        self.assertEqual(payload["domain"], "trading")
        self.assertEqual(payload["candidate_profile_id"], "trading_v2")
        self.assertEqual(payload["actor"], "admin")
        self.assertIn("requested_at", payload)

    def test_approval_payload_includes_current(self):
        """Payload includes current profile info."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        payload = self.mgr.request_activation_approval("trading", "admin")
        self.assertEqual(payload["current_profile_id"], "trading")
        self.assertEqual(payload["current_profile_version"], "1.0.0")

    def test_approval_payload_with_simulation(self):
        """Payload carries simulation summary and changed_flags."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        sim = {"changed_flags": ["needs_grounding", "stability_status"]}
        payload = self.mgr.request_activation_approval(
            "trading", "admin", simulation_summary=sim,
        )
        self.assertEqual(payload["changed_flags"], ["needs_grounding", "stability_status"])
        self.assertEqual(payload["simulation_summary"], sim)

    def test_approval_without_candidate_raises(self):
        """Requesting approval without staged candidate raises."""
        with self.assertRaises(PolicyLifecycleError):
            self.mgr.request_activation_approval("trading", "admin")

    def test_approval_payload_serializable(self):
        """Approval payload is JSON-serializable."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        payload = self.mgr.request_activation_approval("trading", "admin")
        json.dumps(payload)  # should not raise


# =============================================================================
# P3-D: Deployment history and audit
# =============================================================================


class TestDeploymentHistory(unittest.TestCase):
    """Test deployment history tracking."""

    def setUp(self):
        self.registry = _make_registry()
        self.mgr = PolicyLifecycleManager(self.registry)

    def test_empty_history(self):
        """No history for domains without lifecycle events."""
        self.assertEqual(self.mgr.get_deployment_history("trading"), [])

    def test_stage_creates_history(self):
        """Staging creates a DRAFT history entry."""
        self.mgr.stage_candidate("trading", _make_candidate(), "admin")
        history = self.mgr.get_deployment_history("trading")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "draft")

    def test_full_lifecycle_history(self):
        """Full stage->validate->activate creates history entries."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        self.mgr.validate_candidate("trading", "admin")
        self.mgr.activate("trading", "admin")
        history = self.mgr.get_deployment_history("trading")
        statuses = [r["status"] for r in history]
        # Most recent first; includes builtin superseded record
        self.assertEqual(statuses[0], "active")
        self.assertIn("superseded", statuses)
        self.assertIn("draft", statuses)
        self.assertIn("validated", statuses)

    def test_history_entries_have_record_id(self):
        """Each history entry has a unique record_id."""
        self.mgr.stage_candidate("trading", _make_candidate(), "admin")
        self.mgr.validate_candidate("trading", "admin")
        history = self.mgr.get_deployment_history("trading")
        ids = [r["record_id"] for r in history]
        self.assertTrue(all(id.startswith("plr-") for id in ids))
        self.assertEqual(len(set(ids)), len(ids))  # unique

    def test_history_entries_serializable(self):
        """All history entries are JSON-serializable."""
        self.mgr.stage_candidate("trading", _make_candidate(), "admin")
        self.mgr.activate("trading", "admin")
        history = self.mgr.get_deployment_history("trading")
        json.dumps(history)  # should not raise

    def test_get_active_record(self):
        """get_active_record returns the current ACTIVE entry."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        self.mgr.activate("trading", "admin")
        active = self.mgr.get_active_record("trading")
        self.assertEqual(active["status"], "active")
        self.assertEqual(active["profile_id"], "trading_v2")

    def test_get_active_record_none_before_lifecycle(self):
        """get_active_record returns None for domains without explicit activation."""
        self.assertIsNone(self.mgr.get_active_record("trading"))

    def test_get_candidate(self):
        """get_candidate returns staged candidate info."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        result = self.mgr.get_candidate("trading")
        self.assertIsNotNone(result)
        self.assertEqual(result["record"]["status"], "draft")

    def test_get_candidate_none(self):
        """get_candidate returns None when nothing staged."""
        self.assertIsNone(self.mgr.get_candidate("trading"))


class TestDeploymentRecordSchema(unittest.TestCase):
    """Test DeploymentRecord structure."""

    def test_to_dict_all_fields(self):
        record = DeploymentRecord(
            record_id="plr-abc",
            domain="trading",
            profile_id="trading_v2",
            profile_version="2.0.0",
            status=ProfileStatus.ACTIVE,
            created_at="2026-04-04T00:00:00+00:00",
            actor="admin@corp.com",
            rationale="tuning",
            previous_profile_id="trading",
            previous_version="1.0.0",
            approval_id="appr-123",
            simulation_summary={"changed_flags": ["needs_grounding"]},
        )
        d = record.to_dict()
        self.assertEqual(d["status"], "active")
        self.assertEqual(d["approval_id"], "appr-123")
        self.assertEqual(d["simulation_summary"]["changed_flags"], ["needs_grounding"])

    def test_to_dict_serializable(self):
        record = DeploymentRecord(
            record_id="plr-xyz",
            domain="trading",
            profile_id="t",
            profile_version="1.0.0",
            status=ProfileStatus.DRAFT,
            created_at="2026-04-04T00:00:00+00:00",
            actor="admin",
        )
        json.dumps(record.to_dict())


# =============================================================================
# P3-E: Simulation-to-deployment linkage
# =============================================================================


class TestSimulationDeploymentLink(unittest.TestCase):
    """Test that simulation results can be linked to deployments."""

    def setUp(self):
        self.registry = _make_registry()
        self.mgr = PolicyLifecycleManager(self.registry)

    def test_validate_with_simulation_summary(self):
        """Simulation summary attached during validation."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        sim = {"changed_flags": ["needs_grounding"], "is_identical": False}
        record = self.mgr.validate_candidate("trading", "admin", simulation_summary=sim)
        self.assertEqual(record.simulation_summary, sim)

    def test_activation_inherits_validation_simulation(self):
        """Activation inherits simulation from validation if not overridden."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        sim = {"changed_flags": ["needs_grounding"]}
        self.mgr.validate_candidate("trading", "admin", simulation_summary=sim)
        record = self.mgr.activate("trading", "admin", require_validation=True)
        self.assertEqual(record.simulation_summary, sim)

    def test_activation_simulation_overrides_validation(self):
        """Explicit simulation at activation overrides validation's."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        self.mgr.validate_candidate(
            "trading", "admin",
            simulation_summary={"changed_flags": ["old"]},
        )
        new_sim = {"changed_flags": ["new"]}
        record = self.mgr.activate(
            "trading", "admin",
            require_validation=True,
            simulation_summary=new_sim,
        )
        self.assertEqual(record.simulation_summary, new_sim)

    def test_approval_payload_carries_simulation(self):
        """Approval payload includes simulation for reviewer."""
        candidate = _make_candidate()
        self.mgr.stage_candidate("trading", candidate, "admin")
        sim = {"changed_flags": ["stability_status"], "is_identical": False}
        payload = self.mgr.request_activation_approval(
            "trading", "admin", simulation_summary=sim,
        )
        self.assertEqual(payload["simulation_summary"], sim)


# =============================================================================
# P3-F: PolicyService lifecycle methods
# =============================================================================


class TestPolicyServiceLifecycle(unittest.TestCase):
    """Test PolicyService P3 lifecycle methods."""

    def setUp(self):
        self.svc = PolicyService()
        # Reset the global registry before each test to avoid pollution
        get_profile_registry().reset()

    def tearDown(self):
        get_profile_registry().reset()

    def test_stage_and_activate(self):
        """Full stage->activate flow through PolicyService."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, "admin")
        result = self.svc.activate_profile("trading", "admin", rationale="test")
        self.assertEqual(result["status"], "active")

    def test_stage_validate_activate(self):
        """Full stage->validate->activate flow."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, "admin")
        self.svc.validate_candidate("trading", "admin")
        result = self.svc.activate_profile(
            "trading", "admin", require_validation=True,
        )
        self.assertEqual(result["status"], "active")

    def test_rollback_through_service(self):
        """Rollback via PolicyService."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, "admin")
        self.svc.activate_profile("trading", "admin")
        result = self.svc.rollback_profile("trading", "ops", "bad")
        self.assertEqual(result["status"], "active")
        self.assertTrue(result["rationale"].startswith("ROLLBACK:"))

    def test_approval_request_through_service(self):
        """Approval request via PolicyService."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, "admin")
        payload = self.svc.request_activation_approval("trading", "admin")
        self.assertEqual(payload["approval_type"], "policy_activation")

    def test_deployment_history_through_service(self):
        """Deployment history via PolicyService."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, "admin")
        self.svc.activate_profile("trading", "admin")
        history = self.svc.get_deployment_history("trading")
        self.assertGreater(len(history), 0)

    def test_get_active_deployment(self):
        """Active deployment via PolicyService."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, "admin")
        self.svc.activate_profile("trading", "admin")
        active = self.svc.get_active_deployment("trading")
        self.assertIsNotNone(active)
        self.assertEqual(active["status"], "active")

    def test_lifecycle_creates_audit_entries(self):
        """Lifecycle operations create audit entries."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, "admin")
        self.svc.validate_candidate("trading", "admin")
        self.svc.activate_profile("trading", "admin")

        log = self.svc.get_policy_audit_log()
        types = [e["event_type"] for e in log]
        self.assertIn("stage_candidate", types)
        self.assertIn("validate_candidate", types)
        self.assertIn("activate_profile", types)

    def test_rollback_creates_audit_entry(self):
        """Rollback creates audit entry."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, "admin")
        self.svc.activate_profile("trading", "admin")
        self.svc.rollback_profile("trading", "ops", "bad")

        log = self.svc.get_policy_audit_log()
        types = [e["event_type"] for e in log]
        self.assertIn("rollback_profile", types)

    def test_approval_request_creates_audit_entry(self):
        """Approval request creates audit entry."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, "admin")
        self.svc.request_activation_approval("trading", "admin")

        log = self.svc.get_policy_audit_log()
        types = [e["event_type"] for e in log]
        self.assertIn("request_activation_approval", types)

    def test_lifecycle_manager_cached(self):
        """get_lifecycle_manager returns same instance."""
        mgr1 = self.svc.get_lifecycle_manager()
        mgr2 = self.svc.get_lifecycle_manager()
        self.assertIs(mgr1, mgr2)


# =============================================================================
# P3-G: Backward compatibility / P0-P2 regression
# =============================================================================


class TestP3BackwardCompat(unittest.TestCase):
    """Ensure P0-P2 functionality is not broken by P3."""

    def setUp(self):
        get_profile_registry().reset()

    def test_version_bumped(self):
        from agentic.policy import __version__
        self.assertEqual(__version__, "1.4.0")

    def test_p0_exports_present(self):
        from agentic.policy import DomainProfile, ProfileRegistry, get_profile_registry
        self.assertIsNotNone(DomainProfile)

    def test_p1_exports_present(self):
        from agentic.policy import PolicyService, get_policy_service
        self.assertIsNotNone(PolicyService)

    def test_p2_exports_present(self):
        from agentic.policy import simulate_policy, compare_policy, SIM_VERSION
        self.assertIsNotNone(simulate_policy)

    def test_p3_exports_present(self):
        from agentic.policy import (
            ProfileStatus, DeploymentRecord,
            PolicyLifecycleManager, PolicyLifecycleError,
        )
        self.assertIsNotNone(ProfileStatus)

    def test_registry_get_unchanged(self):
        """Registry get() still works without lifecycle involvement."""
        registry = get_profile_registry()
        profile = registry.get("trading")
        self.assertEqual(profile.profile_id, "trading")
        self.assertEqual(profile.min_coherence, 0.55)

    def test_compute_policy_unchanged(self):
        """compute_policy_flags still works."""
        from agentic.policy import compute_policy_flags
        flags = compute_policy_flags(_make_unified(), domain="trading")
        self.assertIn("needs_grounding", flags)

    def test_simulation_unchanged(self):
        """Simulation still works."""
        from agentic.policy import simulate_policy
        result = simulate_policy(_make_unified(), domain="trading")
        self.assertIn("flags", result)

    def test_facade_markers_unchanged(self):
        from agentic.policy.governance_binding import _FACADE_STATUS
        self.assertEqual(_FACADE_STATUS, "provisional")

    def test_insight_window_markers_unchanged(self):
        from agentic.policy.insight_window_gating import _INSIGHT_WINDOW_PATH
        self.assertEqual(_INSIGHT_WINDOW_PATH, "policy_engine")


if __name__ == "__main__":
    unittest.main()
