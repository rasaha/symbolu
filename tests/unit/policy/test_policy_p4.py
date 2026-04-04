"""
Policy Phase P4 — Control-Plane Exposure & Operator-Readiness Tests

Tests for:
- P4-A: PolicyControlPlane instantiation and system snapshot
- P4-B: Per-domain status queries
- P4-C: Health report (stale candidates, fallback detection)
- P4-D: Deployment/approval/simulation history queries
- P4-E: PolicyService control-plane delegation methods
- P4-F: Tenant-scoping passthrough
- P4-G: Backward compatibility / P0-P3 regression
"""

import time
import unittest
from datetime import datetime, timezone, timedelta

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
from agentic.policy.policy_control_plane import (
    PolicyControlPlane,
    PolicyDomainStatus,
    PolicyHealthReport,
    P4_VERSION,
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
        },
        "identity": {"identity_stability_score": 0.80},
        "arc": {"arc_mode": "converging"},
        "formula": {"resonance": 0.70, "tension": 0.20, "delta_smi": 0.05},
    }


def _setup_control_plane():
    """Create a fresh registry, lifecycle manager, and control plane."""
    registry = _make_registry()
    mgr = PolicyLifecycleManager(registry)
    audit_log = []
    cp = PolicyControlPlane(registry, mgr, audit_log)
    return registry, mgr, audit_log, cp


# =============================================================================
# P4-A: System snapshot
# =============================================================================


class TestSystemSnapshot(unittest.TestCase):
    """Test get_system_snapshot() for all-domain overview."""

    def test_snapshot_returns_all_builtin_domains(self):
        _, _, _, cp = _setup_control_plane()
        snap = cp.get_system_snapshot()
        self.assertIn("domains", snap)
        self.assertIn("trading", snap["domains"])
        self.assertIn("therapy", snap["domains"])
        self.assertIn("identity", snap["domains"])
        self.assertIn("generic", snap["domains"])

    def test_snapshot_summary_counts(self):
        _, _, _, cp = _setup_control_plane()
        snap = cp.get_system_snapshot()
        summary = snap["summary"]
        self.assertEqual(summary["total_domains"], 4)
        self.assertEqual(summary["builtin_count"], 4)
        self.assertEqual(summary["custom_count"], 0)
        self.assertEqual(summary["fallback_domains"], [])

    def test_snapshot_includes_metadata(self):
        _, _, _, cp = _setup_control_plane()
        snap = cp.get_system_snapshot()
        self.assertEqual(snap["version"], P4_VERSION)
        self.assertIn("generated_at", snap)
        self.assertIsNone(snap["tenant_id"])

    def test_snapshot_tenant_id_passthrough(self):
        _, _, _, cp = _setup_control_plane()
        snap = cp.get_system_snapshot(tenant_id="tenant-42")
        self.assertEqual(snap["tenant_id"], "tenant-42")

    def test_snapshot_shows_custom_profile(self):
        registry, mgr, _, cp = _setup_control_plane()
        # Activate a custom profile
        candidate = _make_candidate("trading_v2", "2.0.0")
        mgr.stage_candidate("trading", candidate, actor="test")
        mgr.activate("trading", actor="test", rationale="test")

        snap = cp.get_system_snapshot()
        trading = snap["domains"]["trading"]
        self.assertEqual(trading["profile_id"], "trading_v2")
        self.assertEqual(trading["profile_version"], "2.0.0")
        self.assertFalse(trading["is_builtin"])

    def test_snapshot_shows_candidate(self):
        registry, mgr, _, cp = _setup_control_plane()
        candidate = _make_candidate()
        mgr.stage_candidate("trading", candidate, actor="test")

        snap = cp.get_system_snapshot()
        trading = snap["domains"]["trading"]
        self.assertTrue(trading["has_candidate"])
        self.assertEqual(trading["candidate_status"], "draft")


# =============================================================================
# P4-B: Per-domain status
# =============================================================================


class TestDomainStatus(unittest.TestCase):
    """Test get_domain_status() for single-domain queries."""

    def test_builtin_domain_status(self):
        _, _, _, cp = _setup_control_plane()
        status = cp.get_domain_status("trading")
        self.assertIsNotNone(status)
        self.assertEqual(status["domain"], "trading")
        self.assertEqual(status["profile_id"], "trading")
        self.assertTrue(status["is_builtin"])
        self.assertFalse(status["has_candidate"])
        self.assertEqual(status["deployment_count"], 0)

    def test_unknown_domain_returns_none(self):
        _, _, _, cp = _setup_control_plane()
        status = cp.get_domain_status("nonexistent")
        self.assertIsNone(status)

    def test_domain_with_active_deployment(self):
        registry, mgr, _, cp = _setup_control_plane()
        candidate = _make_candidate()
        mgr.stage_candidate("trading", candidate, actor="admin@corp.com")
        mgr.activate("trading", actor="admin@corp.com", rationale="tune")

        status = cp.get_domain_status("trading")
        self.assertIsNotNone(status["active_record_id"])
        self.assertEqual(status["last_activated_by"], "admin@corp.com")
        self.assertIsNotNone(status["last_activated_at"])
        self.assertGreater(status["deployment_count"], 0)

    def test_domain_status_tenant_passthrough(self):
        _, _, _, cp = _setup_control_plane()
        status = cp.get_domain_status("trading", tenant_id="t-1")
        self.assertEqual(status["tenant_id"], "t-1")

    def test_domain_fallback_detection(self):
        registry, _, _, cp = _setup_control_plane()
        # Register a profile with generic profile_id under a custom domain
        generic = DomainProfile(profile_id="generic", profile_version="1.0.0")
        registry.register(generic, domain_id="custom_domain")

        status = cp.get_domain_status("custom_domain")
        self.assertIsNotNone(status)
        self.assertTrue(status["is_fallback"])


# =============================================================================
# P4-C: Health report
# =============================================================================


class TestHealthReport(unittest.TestCase):
    """Test get_health_report() for policy health signals."""

    def test_healthy_baseline(self):
        _, _, _, cp = _setup_control_plane()
        report = cp.get_health_report()
        self.assertTrue(report["healthy"])
        self.assertEqual(report["warnings"], [])
        self.assertEqual(report["total_domains"], 4)
        self.assertEqual(report["builtin_count"], 4)
        self.assertEqual(report["custom_count"], 0)
        self.assertEqual(report["stale_candidates"], [])

    def test_health_report_version(self):
        _, _, _, cp = _setup_control_plane()
        report = cp.get_health_report()
        self.assertEqual(report["version"], P4_VERSION)
        self.assertIn("checked_at", report)

    def test_stale_candidate_detection(self):
        _, mgr, _, cp = _setup_control_plane()
        candidate = _make_candidate()
        mgr.stage_candidate("trading", candidate, actor="test")

        # Use a very short threshold so the candidate is immediately stale
        report = cp.get_health_report(stale_threshold_seconds=0)
        self.assertFalse(report["healthy"])
        self.assertEqual(len(report["stale_candidates"]), 1)
        self.assertEqual(report["stale_candidates"][0]["domain"], "trading")
        self.assertIn("stale candidate", report["warnings"][0].lower())

    def test_non_stale_candidate(self):
        _, mgr, _, cp = _setup_control_plane()
        candidate = _make_candidate()
        mgr.stage_candidate("trading", candidate, actor="test")

        # Use a very long threshold — candidate is fresh
        report = cp.get_health_report(stale_threshold_seconds=999999)
        self.assertEqual(len(report["stale_candidates"]), 0)
        self.assertIn("trading", report["domains_with_candidates"])

    def test_fallback_domain_warning(self):
        registry, _, _, cp = _setup_control_plane()
        # Register generic-profile under a non-generic domain
        generic = DomainProfile(profile_id="generic", profile_version="1.0.0")
        registry.register(generic, domain_id="weird_domain")

        report = cp.get_health_report()
        self.assertFalse(report["healthy"])
        self.assertIn("weird_domain", report["fallback_domains"])
        self.assertTrue(any("fallback" in w.lower() for w in report["warnings"]))

    def test_health_report_tenant_passthrough(self):
        _, _, _, cp = _setup_control_plane()
        report = cp.get_health_report(tenant_id="t-99")
        self.assertEqual(report["tenant_id"], "t-99")

    def test_deployment_count_aggregation(self):
        registry, mgr, _, cp = _setup_control_plane()
        # Activate a few profiles across domains
        for domain in ("trading", "therapy"):
            c = _make_candidate(f"{domain}_v2", "2.0.0")
            mgr.stage_candidate(domain, c, actor="test")
            mgr.activate(domain, actor="test")

        report = cp.get_health_report()
        # Each activation creates: draft + superseded(builtin) + active = 3 records
        # Two domains = 6 records minimum
        self.assertGreaterEqual(report["total_deployments"], 6)
        # Verify custom_count reflects the activated profiles
        self.assertEqual(report["custom_count"], 2)


# =============================================================================
# P4-D: History queries
# =============================================================================


class TestHistoryQueries(unittest.TestCase):
    """Test deployment, approval, and simulation history queries."""

    def setUp(self):
        self.registry, self.mgr, self.audit_log, self.cp = _setup_control_plane()

    def test_deployment_history_empty(self):
        result = self.cp.get_deployment_history("trading")
        self.assertEqual(result["domain"], "trading")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["version"], P4_VERSION)

    def test_deployment_history_with_records(self):
        c = _make_candidate()
        self.mgr.stage_candidate("trading", c, actor="test")
        self.mgr.activate("trading", actor="test")

        result = self.cp.get_deployment_history("trading")
        self.assertGreater(result["count"], 0)

    def test_deployment_history_status_filter(self):
        c = _make_candidate()
        self.mgr.stage_candidate("trading", c, actor="test")
        self.mgr.activate("trading", actor="test")

        active_only = self.cp.get_deployment_history(
            "trading", status_filter="active",
        )
        for rec in active_only["records"]:
            self.assertEqual(rec["status"], "active")

    def test_deployment_history_tenant_passthrough(self):
        result = self.cp.get_deployment_history("trading", tenant_id="t-5")
        self.assertEqual(result["tenant_id"], "t-5")

    def test_approval_history_empty(self):
        result = self.cp.get_approval_history()
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["count"], 0)

    def test_approval_history_with_entries(self):
        # Add audit entries manually (simulating what PolicyService does)
        self.audit_log.append({
            "event_type": "activate_profile",
            "domain": "trading",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {"actor": "test"},
        })
        self.audit_log.append({
            "event_type": "compute_policy",
            "domain": "trading",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {},
        })

        result = self.cp.get_approval_history()
        # Should only include lifecycle events, not compute_policy
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["event_type"], "activate_profile")

    def test_approval_history_domain_filter(self):
        self.audit_log.append({
            "event_type": "activate_profile",
            "domain": "trading",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {},
        })
        self.audit_log.append({
            "event_type": "activate_profile",
            "domain": "therapy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {},
        })

        result = self.cp.get_approval_history(domain="trading")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["domain"], "trading")

    def test_simulation_history_empty(self):
        result = self.cp.get_simulation_history()
        self.assertEqual(result["records"], [])
        self.assertEqual(result["count"], 0)

    def test_simulation_history_with_records(self):
        c = _make_candidate()
        sim = {"changed_flags": ["needs_grounding"], "verdict": "safe"}
        self.mgr.stage_candidate("trading", c, actor="test")
        self.mgr.validate_candidate(
            "trading", actor="test", simulation_summary=sim,
        )
        self.mgr.activate("trading", actor="test")

        result = self.cp.get_simulation_history()
        self.assertGreater(result["count"], 0)
        # At least one record should have simulation_summary
        has_sim = any(r.get("simulation_summary") for r in result["records"])
        self.assertTrue(has_sim)

    def test_simulation_history_domain_filter(self):
        c = _make_candidate("trading_v2", "2.0.0")
        sim = {"verdict": "ok"}
        self.mgr.stage_candidate("trading", c, actor="test")
        self.mgr.validate_candidate("trading", actor="test", simulation_summary=sim)
        self.mgr.activate("trading", actor="test")

        result = self.cp.get_simulation_history(domain="therapy")
        self.assertEqual(result["count"], 0)


# =============================================================================
# P4-E: PolicyService control-plane delegation
# =============================================================================


class TestPolicyServiceControlPlane(unittest.TestCase):
    """Test PolicyService P4 methods delegate to PolicyControlPlane."""

    def setUp(self):
        get_profile_registry().reset()
        self.svc = PolicyService()

    def tearDown(self):
        get_profile_registry().reset()

    def test_get_system_snapshot(self):
        snap = self.svc.get_system_snapshot()
        self.assertIn("domains", snap)
        self.assertIn("summary", snap)
        self.assertEqual(snap["version"], P4_VERSION)
        self.assertEqual(snap["summary"]["total_domains"], 4)

    def test_get_domain_status(self):
        status = self.svc.get_domain_status("trading")
        self.assertIsNotNone(status)
        self.assertEqual(status["domain"], "trading")
        self.assertTrue(status["is_builtin"])

    def test_get_domain_status_unknown(self):
        status = self.svc.get_domain_status("nonexistent")
        self.assertIsNone(status)

    def test_get_health_report(self):
        report = self.svc.get_health_report()
        self.assertIn("healthy", report)
        self.assertIn("warnings", report)
        self.assertEqual(report["version"], P4_VERSION)

    def test_get_active_profiles_summary(self):
        result = self.svc.get_active_profiles_summary()
        self.assertIn("profiles", result)
        self.assertIn("trading", result["profiles"])
        self.assertEqual(result["count"], 4)

    def test_get_filtered_deployment_history(self):
        result = self.svc.get_filtered_deployment_history("trading")
        self.assertIn("records", result)
        self.assertEqual(result["domain"], "trading")

    def test_get_approval_history(self):
        result = self.svc.get_approval_history()
        self.assertIn("entries", result)
        self.assertEqual(result["count"], 0)

    def test_get_simulation_history(self):
        result = self.svc.get_simulation_history()
        self.assertIn("records", result)
        self.assertEqual(result["count"], 0)

    def test_service_snapshot_after_activation(self):
        """Full flow: stage → activate → verify snapshot reflects it."""
        candidate = _make_candidate("trading_v2", "2.0.0")
        self.svc.stage_candidate("trading", candidate, actor="test")
        self.svc.activate_profile("trading", actor="test", rationale="tune")

        snap = self.svc.get_system_snapshot()
        trading = snap["domains"]["trading"]
        self.assertEqual(trading["profile_id"], "trading_v2")
        self.assertFalse(trading["is_builtin"])
        self.assertIsNotNone(trading["active_record_id"])

    def test_service_health_with_stale_candidate(self):
        """Stage a candidate and check health with zero-threshold."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, actor="test")

        # Access control plane directly to use custom threshold
        report = self.svc.get_control_plane().get_health_report(
            stale_threshold_seconds=0,
        )
        self.assertFalse(report["healthy"])
        self.assertGreater(len(report["stale_candidates"]), 0)

    def test_service_approval_history_populates(self):
        """Lifecycle actions through service should appear in approval history."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, actor="admin")
        self.svc.activate_profile("trading", actor="admin", rationale="go")

        result = self.svc.get_approval_history()
        self.assertGreater(result["count"], 0)
        event_types = {e["event_type"] for e in result["entries"]}
        self.assertIn("stage_candidate", event_types)
        self.assertIn("activate_profile", event_types)

    def test_service_simulation_history_populates(self):
        """Activation with simulation_summary should appear in simulation history."""
        candidate = _make_candidate()
        sim = {"changed_flags": [], "verdict": "identical"}
        self.svc.stage_candidate("trading", candidate, actor="admin")
        self.svc.validate_candidate(
            "trading", actor="admin", simulation_summary=sim,
        )
        self.svc.activate_profile("trading", actor="admin")

        result = self.svc.get_simulation_history(domain="trading")
        self.assertGreater(result["count"], 0)


# =============================================================================
# P4-F: Tenant-scoping passthrough
# =============================================================================


class TestTenantScoping(unittest.TestCase):
    """Verify tenant_id passthrough on all P4 surfaces."""

    def setUp(self):
        self.registry, self.mgr, self.audit_log, self.cp = _setup_control_plane()

    def test_snapshot_tenant(self):
        r = self.cp.get_system_snapshot(tenant_id="t-1")
        self.assertEqual(r["tenant_id"], "t-1")

    def test_domain_status_tenant(self):
        r = self.cp.get_domain_status("trading", tenant_id="t-2")
        self.assertEqual(r["tenant_id"], "t-2")

    def test_deployment_history_tenant(self):
        r = self.cp.get_deployment_history("trading", tenant_id="t-3")
        self.assertEqual(r["tenant_id"], "t-3")

    def test_approval_history_tenant(self):
        r = self.cp.get_approval_history(tenant_id="t-4")
        self.assertEqual(r["tenant_id"], "t-4")

    def test_simulation_history_tenant(self):
        r = self.cp.get_simulation_history(tenant_id="t-5")
        self.assertEqual(r["tenant_id"], "t-5")

    def test_health_report_tenant(self):
        r = self.cp.get_health_report(tenant_id="t-6")
        self.assertEqual(r["tenant_id"], "t-6")

    def test_active_profiles_summary_tenant(self):
        r = self.cp.get_active_profiles_summary(tenant_id="t-7")
        self.assertEqual(r["tenant_id"], "t-7")


# =============================================================================
# P4-G: Backward compatibility / P0-P3 regression
# =============================================================================


class TestP4BackwardCompat(unittest.TestCase):
    """Verify P4 additions don't break P0-P3 behavior."""

    def setUp(self):
        get_profile_registry().reset()
        self.svc = PolicyService()

    def tearDown(self):
        get_profile_registry().reset()

    def test_p1_compute_policy_still_works(self):
        unified = _make_unified()
        result = self.svc.compute_policy(unified, domain="trading")
        self.assertIn("flags", result)
        self.assertIn("profile_id", result)

    def test_p1_session_policy_still_works(self):
        result = self.svc.compute_session_policy(None)
        self.assertIn("flags", result)

    def test_p2_simulate_still_works(self):
        unified = _make_unified()
        result = self.svc.simulate_policy(unified, domain="trading")
        self.assertIn("flags", result)

    def test_p3_lifecycle_still_works(self):
        candidate = _make_candidate()
        record = self.svc.stage_candidate("trading", candidate, actor="test")
        self.assertEqual(record["status"], "draft")
        activated = self.svc.activate_profile("trading", actor="test")
        self.assertEqual(activated["status"], "active")

    def test_version_bumped(self):
        import agentic.policy as policy_mod
        version = policy_mod.__version__
        major, minor = int(version.split(".")[0]), int(version.split(".")[1])
        self.assertGreaterEqual((major, minor), (1, 5))

    def test_p4_exports_available(self):
        from agentic.policy import (
            PolicyControlPlane,
            PolicyDomainStatus,
            PolicyHealthReport,
            P4_VERSION,
        )
        self.assertIsNotNone(PolicyControlPlane)
        self.assertIsNotNone(PolicyDomainStatus)
        self.assertIsNotNone(PolicyHealthReport)
        self.assertEqual(P4_VERSION, "1.0.0")

    def test_audit_log_includes_p4_and_p3_events(self):
        """P4 queries don't pollute audit log; P3 actions still do."""
        candidate = _make_candidate()
        self.svc.stage_candidate("trading", candidate, actor="test")
        self.svc.activate_profile("trading", actor="test")

        # P4 reads should NOT add audit entries
        count_before = self.svc.get_policy_audit_count()
        self.svc.get_system_snapshot()
        self.svc.get_health_report()
        self.svc.get_domain_status("trading")
        count_after = self.svc.get_policy_audit_count()
        self.assertEqual(count_before, count_after)


# =============================================================================
# P4-H: PolicyDomainStatus and PolicyHealthReport dataclasses
# =============================================================================


class TestDataclasses(unittest.TestCase):
    """Test dataclass construction and serialization."""

    def test_domain_status_to_dict(self):
        status = PolicyDomainStatus(
            domain="trading",
            profile_id="trading",
            profile_version="1.0.0",
            is_builtin=True,
            has_candidate=False,
        )
        d = status.to_dict()
        self.assertEqual(d["domain"], "trading")
        self.assertTrue(d["is_builtin"])
        self.assertFalse(d["has_candidate"])
        self.assertIsNone(d["candidate_status"])

    def test_health_report_to_dict(self):
        report = PolicyHealthReport(
            total_domains=4,
            builtin_count=4,
            custom_count=0,
            fallback_domains=[],
            stale_candidates=[],
            domains_with_candidates=[],
            total_deployments=0,
            healthy=True,
            warnings=[],
            checked_at="2026-01-01T00:00:00+00:00",
        )
        d = report.to_dict()
        self.assertTrue(d["healthy"])
        self.assertEqual(d["total_domains"], 4)
        self.assertEqual(d["version"], P4_VERSION)


# =============================================================================
# P4-I: Active profiles summary
# =============================================================================


class TestActiveProfilesSummary(unittest.TestCase):
    """Test get_active_profiles_summary() queries."""

    def test_summary_all_builtins(self):
        _, _, _, cp = _setup_control_plane()
        result = cp.get_active_profiles_summary()
        self.assertEqual(result["count"], 4)
        for domain in ("trading", "therapy", "identity", "generic"):
            self.assertIn(domain, result["profiles"])
            self.assertTrue(result["profiles"][domain]["is_builtin"])
            self.assertIsNone(result["profiles"][domain]["activated_at"])

    def test_summary_after_activation(self):
        registry, mgr, _, cp = _setup_control_plane()
        candidate = _make_candidate("trading_v2", "2.0.0")
        mgr.stage_candidate("trading", candidate, actor="admin")
        mgr.activate("trading", actor="admin")

        result = cp.get_active_profiles_summary()
        trading = result["profiles"]["trading"]
        self.assertFalse(trading["is_builtin"])
        self.assertEqual(trading["profile_id"], "trading_v2")
        self.assertIsNotNone(trading["activated_at"])
        self.assertEqual(trading["activated_by"], "admin")


if __name__ == "__main__":
    unittest.main()
