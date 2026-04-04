"""
Activation Patch E2E Tests — Prove S3/S4 signals reach governance.

These tests call GovernanceService.authorize() with sovereign_projection_metadata
and verify that S3/S4 audit fields are populated in the response.

This is the "proof fix" — the S3/S4 signal pipeline was dormant because
JEPACompositeSignal lacked a projection_metadata field. After the activation
patch, passing sovereign_projection_metadata on AuthorizationRequest must
cause the composite to carry it, and the diagnostic/guna/governor resolvers
to extract real signals.
"""

import pytest


class TestS3S4ActivationE2E:
    """True E2E tests: authorize() with projection_metadata → populated audit fields."""

    def _authorize_with_projection(self, projection_metadata):
        """Helper: build request with projection_metadata and authorize."""
        from agentic.agentic_framework.governance_service import (
            GovernanceService, AuthorizationRequest,
        )
        svc = GovernanceService()
        req = AuthorizationRequest(
            actor_id="e2e-test",
            action_type="file_read",
            tool_name="read_file",
            quality_score=0.9,
            coherence_score=0.9,
            sovereign_projection_metadata=projection_metadata,
        )
        return svc.authorize(req)

    # -----------------------------------------------------------------
    # S3: Reasoning diagnostics reach audit
    # -----------------------------------------------------------------

    def test_s3_diagnostics_populated_via_authorize(self):
        """Passing reasoning_diagnostics in projection_metadata populates
        sovereign_diagnostics on the audit event."""
        projection = {
            "reasoning_diagnostics": {
                "mauna_active": True,
                "active_intervention": "mauna_hold",
                "active_logic_template": "observation",
                "dominant_bhava": "O7_REASONING",
                "entropy_delta": -0.02,
            },
        }
        resp = self._authorize_with_projection(projection)
        diag = resp.audit_event.sovereign_diagnostics
        assert diag is not None, "S3 diagnostics must be populated when projection_metadata has reasoning_diagnostics"
        assert diag["mauna_active"] is True
        assert diag["active_intervention"] == "mauna_hold"
        assert diag["source"] == "inference_bridge"
        assert diag["available"] is True

    def test_s3_diagnostics_absent_without_metadata(self):
        """Without projection_metadata, sovereign_diagnostics should be None."""
        from agentic.agentic_framework.governance_service import (
            GovernanceService, AuthorizationRequest,
        )
        svc = GovernanceService()
        req = AuthorizationRequest(
            actor_id="e2e-test",
            action_type="file_read",
            quality_score=0.9,
            coherence_score=0.9,
        )
        resp = svc.authorize(req)
        assert resp.audit_event.sovereign_diagnostics is None

    # -----------------------------------------------------------------
    # S4: Guna anomaly signals reach audit
    # -----------------------------------------------------------------

    def test_s4_guna_anomalies_populated_via_authorize(self):
        """Passing guna_anomalies in projection_metadata populates
        sovereign_guna_anomalies on the audit event."""
        projection = {
            "guna_anomalies": {
                "collapse": True,
                "oscillation": False,
                "stagnation": False,
                "dominant_guna": "tamas",
            },
        }
        resp = self._authorize_with_projection(projection)
        guna = resp.audit_event.sovereign_guna_anomalies
        assert guna is not None, "S4 guna anomalies must be populated when projection_metadata has guna_anomalies"
        assert guna["collapse"] is True
        assert guna["dominant_guna"] == "tamas"
        assert guna["available"] is True

    def test_s4_guna_anomalies_absent_without_metadata(self):
        """Without guna_anomalies, sovereign_guna_anomalies should be None."""
        projection = {
            "reasoning_diagnostics": {"mauna_active": False},
        }
        resp = self._authorize_with_projection(projection)
        assert resp.audit_event.sovereign_guna_anomalies is None

    # -----------------------------------------------------------------
    # S4: Governor telemetry reaches audit
    # -----------------------------------------------------------------

    def test_s4_governor_telemetry_populated_via_authorize(self):
        """Passing governor_telemetry in projection_metadata populates
        sovereign_governor_telemetry on the audit event."""
        projection = {
            "governor_telemetry": {
                "s_drift": 0.12,
                "coupling": 0.85,
                "tamas_ratio": 0.3,
                "brake_reason": "entropy_spike",
            },
        }
        resp = self._authorize_with_projection(projection)
        telem = resp.audit_event.sovereign_governor_telemetry
        assert telem is not None, "S4 governor telemetry must be populated"
        assert telem["s_drift"] == 0.12
        assert telem["brake_reason"] == "entropy_spike"

    # -----------------------------------------------------------------
    # Combined: all S3+S4 signals in one request
    # -----------------------------------------------------------------

    def test_combined_s3_s4_all_populated(self):
        """All S3+S4 audit fields populated when full projection_metadata is provided."""
        projection = {
            "reasoning_diagnostics": {
                "mauna_active": False,
                "active_intervention": None,
                "dominant_bhava": "O3_EMOTIONAL",
                "entropy_delta": 0.05,
            },
            "guna_anomalies": {
                "collapse": False,
                "oscillation": True,
                "stagnation": False,
                "dominant_guna": "rajas",
            },
            "governor_telemetry": {
                "s_drift": 0.01,
                "coupling": 0.92,
            },
        }
        resp = self._authorize_with_projection(projection)
        assert resp.audit_event.sovereign_diagnostics is not None
        assert resp.audit_event.sovereign_diagnostics["available"] is True
        assert resp.audit_event.sovereign_guna_anomalies is not None
        assert resp.audit_event.sovereign_guna_anomalies["available"] is True
        assert resp.audit_event.sovereign_governor_telemetry is not None

    # -----------------------------------------------------------------
    # Guna anomaly → confidence penalty effect
    # -----------------------------------------------------------------

    def test_guna_collapse_applies_confidence_penalty(self):
        """Guna collapse should result in a measurable confidence penalty."""
        from agentic.agentic_framework.governance_service import (
            GovernanceService, AuthorizationRequest, _build_confidence_signals,
        )
        svc = GovernanceService()

        # Baseline: no anomalies
        req_clean = AuthorizationRequest(
            actor_id="e2e-test",
            action_type="file_read",
            tool_name="read_file",
            quality_score=0.9,
            coherence_score=0.9,
        )
        resp_clean = svc.authorize(req_clean)

        # With collapse anomaly
        req_collapse = AuthorizationRequest(
            actor_id="e2e-test",
            action_type="file_read",
            tool_name="read_file",
            quality_score=0.9,
            coherence_score=0.9,
            sovereign_projection_metadata={
                "guna_anomalies": {
                    "collapse": True,
                    "oscillation": False,
                    "stagnation": False,
                    "dominant_guna": "tamas",
                },
            },
        )
        resp_collapse = svc.authorize(req_collapse)

        # Collapse should produce lower confidence
        assert resp_collapse.confidence_score <= resp_clean.confidence_score
        # And the guna penalty should be recorded in snapshot
        snap = resp_collapse.audit_event.request_snapshot
        assert snap["sovereign_guna_confidence_penalty"] > 0

    # -----------------------------------------------------------------
    # Aggregate sovereign penalty cap
    # -----------------------------------------------------------------

    def test_aggregate_sovereign_penalty_capped_at_020(self):
        """Even if entropy + insight + guna penalties sum > 0.20,
        effective penalty must not exceed 0.20."""
        from agentic.agentic_framework.governance_service import (
            GovernanceService, AuthorizationRequest, _build_confidence_signals,
        )
        svc = GovernanceService()
        req = AuthorizationRequest(
            actor_id="e2e-test",
            action_type="file_read",
            tool_name="read_file",
            quality_score=0.9,
            coherence_score=0.9,
            sovereign_projection_metadata={
                "guna_anomalies": {
                    "collapse": True,
                    "oscillation": True,
                    "stagnation": True,
                    "dominant_guna": "tamas",
                },
            },
        )
        resp = svc.authorize(req)
        snap = resp.audit_event.request_snapshot

        entropy_p = snap.get("entropy_confidence_penalty", 0) or 0
        insight_p = snap.get("sovereign_insight_confidence_penalty", 0) or 0
        guna_p = snap.get("sovereign_guna_confidence_penalty", 0) or 0
        raw_sum = entropy_p + insight_p + guna_p

        # Get raw gate confidence + JEPA adjustment
        risk = svc.classifier.classify(req.tool_name or req.action_type)
        signals = _build_confidence_signals(req, risk)
        gate = svc.gate.evaluate(signals, req.tool_name or req.action_type)
        raw_confidence = gate.confidence.overall
        jepa_adj = snap["jepa_confidence_adjustment"]

        # The effective confidence should use min(0.20, raw_sum) as penalty
        capped_penalty = min(0.20, raw_sum)
        expected = max(0.0, raw_confidence + jepa_adj - capped_penalty)
        assert abs(resp.confidence_score - expected) < 0.001, (
            f"Confidence {resp.confidence_score} != expected {expected} "
            f"(raw_sum={raw_sum}, capped={capped_penalty})"
        )
