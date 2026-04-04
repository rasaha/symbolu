"""
Tests for JEPA Governance — composite latent state + runtime + residual governor.

Covers:
    - Normal aligned case
    - Process drift detection
    - Semantic shift detection
    - Dual anomaly detection
    - Unknown / missing signal fail-closed
    - Ontology signal construction
    - Vritti signal construction
    - JEPA composite construction (R[v,a] coupling)
    - Runtime process state construction
    - Residual comparison logic
    - Authorization impact via GovernanceService
    - Audit payload completeness
"""

from __future__ import annotations

import pytest

from agentic.agentic_framework.jepa_governance import (
    GovernanceRegime,
    RuntimeActionCategory,
    OntologySignal,
    VrittiSignal,
    JEPACompositeSignal,
    RuntimeProcessState,
    ResidualSignal,
    JEPAGovernanceAssessment,
    build_ontology_signal,
    build_vritti_signal,
    build_jepa_composite,
    build_runtime_process_state,
    compute_residual,
    assess_governance,
    jepa_governance_check,
    ONTOLOGY_LAYERS,
)


# =============================================================================
# Helpers
# =============================================================================

def _balanced_ontology() -> dict:
    return {l: 0.5 for l in ONTOLOGY_LAYERS}

def _pramana_vritti() -> dict:
    return {"pramana": 0.7, "viparyaya": 0.05, "vikalpa": 0.1,
            "smrti": 0.1, "nidra": 0.05}

def _nidra_vritti() -> dict:
    return {"pramana": 0.05, "viparyaya": 0.05, "vikalpa": 0.05,
            "smrti": 0.05, "nidra": 0.8}

def _viparyaya_vritti() -> dict:
    return {"pramana": 0.05, "viparyaya": 0.7, "vikalpa": 0.1,
            "smrti": 0.1, "nidra": 0.05}

def _vikalpa_vritti() -> dict:
    return {"pramana": 0.1, "viparyaya": 0.05, "vikalpa": 0.65,
            "smrti": 0.1, "nidra": 0.1}


# =============================================================================
# Test: Ontology Signal
# =============================================================================

class TestOntologySignal:
    def test_build_from_weights(self):
        weights = _balanced_ontology()
        weights["O7_REASONING"] = 0.95
        sig = build_ontology_signal(layer_weights=weights)
        assert sig.primary_layer == "O7_REASONING"
        assert sig.confidence > 0
        assert len(sig.layer_weights) == 12

    def test_governance_vs_execution_strength(self):
        weights = {l: 0.1 for l in ONTOLOGY_LAYERS}
        weights["O7_REASONING"] = 0.9
        weights["O8_PURPOSE"] = 0.8
        sig = build_ontology_signal(layer_weights=weights)
        assert sig.governance_strength > sig.execution_strength
        assert sig.is_governance_dominant()

    def test_missing_both_raises(self):
        with pytest.raises(ValueError):
            build_ontology_signal()


# =============================================================================
# Test: Vritti Signal
# =============================================================================

class TestVrittiSignal:
    def test_build_from_distribution(self):
        sig = build_vritti_signal(
            vritti_distribution=_pramana_vritti(),
            coherence=0.8,
            score=0.7,
        )
        assert sig.primary_vritti == "pramana"
        assert sig.is_execution_mode()
        assert not sig.is_observation_mode()

    def test_observation_mode(self):
        sig = build_vritti_signal(
            vritti_distribution=_nidra_vritti(),
            coherence=0.3,
        )
        assert sig.primary_vritti == "nidra"
        assert sig.is_observation_mode()

    def test_misperception_risk(self):
        sig = build_vritti_signal(vritti_distribution=_viparyaya_vritti())
        assert sig.misperception_risk() == pytest.approx(0.7, abs=0.01)

    def test_missing_data_defaults_to_nidra(self):
        sig = build_vritti_signal()
        assert sig.primary_vritti == "nidra"
        assert sig.confidence == 0.0


# =============================================================================
# Test: JEPA Composite
# =============================================================================

class TestJEPAComposite:
    def test_aligned_pramana_reasoning(self):
        """Pramana vritti + strong O7_REASONING → high alignment."""
        ontology = build_ontology_signal(
            layer_weights={l: 0.3 for l in ONTOLOGY_LAYERS} | {"O7_REASONING": 0.95}
        )
        vritti = build_vritti_signal(
            vritti_distribution=_pramana_vritti(),
            coherence=0.8,
            score=0.8,
        )
        jepa = build_jepa_composite(ontology, vritti)
        assert jepa.ontology_vritti_alignment > 0.5
        assert jepa.integrated_confidence > 0
        assert "ALIGNED" in jepa.coupling_evidence[0]

    def test_misaligned_nidra_reasoning(self):
        """Nidra vritti + strong O7_REASONING → lower alignment."""
        ontology = build_ontology_signal(
            layer_weights={l: 0.1 for l in ONTOLOGY_LAYERS} | {"O7_REASONING": 0.95}
        )
        vritti = build_vritti_signal(
            vritti_distribution=_nidra_vritti(),
            coherence=0.3,
        )
        jepa = build_jepa_composite(ontology, vritti)
        # Nidra couples to O1_POTENTIAL, not O7_REASONING
        assert "MISALIGNED" in jepa.coupling_evidence[0]

    def test_expected_ontology_uses_coupling_matrix(self):
        """Expected ontology should come from R[v,a] matrix multiplication."""
        vritti = build_vritti_signal(
            vritti_distribution=_pramana_vritti(),
            coherence=0.8,
        )
        ontology = build_ontology_signal(layer_weights=_balanced_ontology())
        jepa = build_jepa_composite(ontology, vritti)
        # Pramana strongly couples to O7_REASONING (R=0.95)
        assert jepa.expected_ontology["O7_REASONING"] > jepa.expected_ontology["O1_POTENTIAL"]

    def test_summary_is_human_readable(self):
        ontology = build_ontology_signal(layer_weights=_balanced_ontology())
        vritti = build_vritti_signal(vritti_distribution=_pramana_vritti(), coherence=0.7)
        jepa = build_jepa_composite(ontology, vritti)
        assert "JEPA" in jepa.summary
        assert "align=" in jepa.summary


# =============================================================================
# Test: Runtime Process State
# =============================================================================

class TestRuntimeProcessState:
    def test_read_only_classification(self):
        rt = build_runtime_process_state(
            tool_name="search_files", risk_level="read_only",
        )
        assert rt.action_category == RuntimeActionCategory.READ_ONLY
        assert not rt.is_side_effecting

    def test_destructive_classification(self):
        rt = build_runtime_process_state(
            tool_name="delete_db", risk_level="destructive",
        )
        assert rt.action_category == RuntimeActionCategory.DESTRUCTIVE
        assert rt.is_side_effecting

    def test_unknown_risk(self):
        rt = build_runtime_process_state(tool_name="mystery", risk_level="unknown")
        assert rt.action_category == RuntimeActionCategory.UNKNOWN


# =============================================================================
# Test: Residual (regime classification)
# =============================================================================

class TestResidualNormal:
    def test_normal_regime(self):
        """Pramana + balanced ontology + read-only = NORMAL."""
        result = jepa_governance_check(
            layer_weights=_balanced_ontology() | {"O7_REASONING": 0.8},
            vritti_distribution=_pramana_vritti(),
            coherence=0.8,
            score=0.8,
            tool_name="search_files",
            risk_level="read_only",
        )
        assert result.regime == GovernanceRegime.NORMAL
        assert result.recommended_action == "ALLOW"
        assert result.confidence_adjustment == 0.0


class TestResidualProcessDrift:
    def test_nidra_destructive_action(self):
        """Nidra vritti + destructive action = drift or anomaly."""
        result = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            vritti_distribution=_nidra_vritti(),
            coherence=0.5,
            score=0.3,
            tool_name="drop_table",
            risk_level="destructive",
        )
        assert result.regime in (
            GovernanceRegime.PROCESS_DRIFT,
            GovernanceRegime.DUAL_ANOMALY,
        )
        assert result.recommended_action in ("DEGRADE", "HALT")

    def test_viparyaya_mutating_action(self):
        """High viparyaya + mutating action = process drift."""
        result = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            vritti_distribution=_viparyaya_vritti(),
            coherence=0.5,
            score=0.5,
            tool_name="write_file",
            risk_level="write",
        )
        assert result.regime in (
            GovernanceRegime.PROCESS_DRIFT,
            GovernanceRegime.DUAL_ANOMALY,
        )


class TestResidualSemanticShift:
    def test_low_alignment_triggers_shift(self):
        """Very different ontology from what vritti expects → semantic shift."""
        # Nidra expects O1_POTENTIAL, but ontology is dominated by O7_REASONING
        ontology = build_ontology_signal(
            layer_weights={l: 0.05 for l in ONTOLOGY_LAYERS} | {"O7_REASONING": 0.95}
        )
        vritti = build_vritti_signal(
            vritti_distribution=_nidra_vritti(),
            coherence=0.7,
            score=0.5,
        )
        jepa = build_jepa_composite(ontology, vritti)
        runtime = build_runtime_process_state(
            tool_name="read_log", risk_level="read_only",
        )
        assessment = assess_governance(jepa, runtime)
        # Low alignment should trigger SEMANTIC_SHIFT or PROCESS_DRIFT
        assert assessment.regime in (
            GovernanceRegime.SEMANTIC_SHIFT,
            GovernanceRegime.PROCESS_DRIFT,
        )


class TestResidualDualAnomaly:
    def test_dual_anomaly(self):
        """Misaligned ontology+vritti AND low action coherence = dual anomaly."""
        # nidra vritti expects O1_POTENTIAL dominance, but ontology is
        # O7_REASONING-dominant → creates real alignment mismatch.
        misaligned_weights = {l: 0.05 for l in ONTOLOGY_LAYERS}
        misaligned_weights["O7_REASONING"] = 0.95
        misaligned_weights["O1_POTENTIAL"] = 0.01
        result = jepa_governance_check(
            layer_weights=misaligned_weights,
            vritti_distribution=_nidra_vritti(),
            coherence=0.1,
            score=0.1,
            tool_name="rm_rf",
            risk_level="destructive",
        )
        # Misaligned ontology/vritti + incoherent runtime → DUAL_ANOMALY
        assert result.regime in (
            GovernanceRegime.DUAL_ANOMALY,
            GovernanceRegime.SEMANTIC_SHIFT,
        )
        assert result.recommended_action in ("HALT", "CONFIRM")


class TestResidualUnknown:
    def test_zero_signals_fail_closed(self):
        """All-zero signals → UNKNOWN → HALT."""
        result = jepa_governance_check(
            layer_weights={l: 0.0 for l in ONTOLOGY_LAYERS},
            coherence=0.0,
            score=0.0,
        )
        assert result.regime == GovernanceRegime.UNKNOWN
        assert result.recommended_action == "HALT"
        assert result.confidence_adjustment == -0.50

    def test_no_vritti_data_fail_closed(self):
        """Missing vritti → defaults to nidra → fail-closed on non-read."""
        result = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            tool_name="execute_code",
            risk_level="execute",
        )
        # Default vritti is nidra, which + execute = at least PROCESS_DRIFT
        assert result.regime != GovernanceRegime.NORMAL


# =============================================================================
# Test: Regime → Governance Behavior
# =============================================================================

class TestRegimeBehavior:
    def test_normal_allows(self):
        result = jepa_governance_check(
            layer_weights=_balanced_ontology() | {"O7_REASONING": 0.9},
            vritti_distribution=_pramana_vritti(),
            coherence=0.85,
            score=0.85,
            risk_level="read_only",
        )
        assert result.recommended_action == "ALLOW"
        assert result.execution_mode_override is None
        assert result.escalation_override is None

    def test_dual_anomaly_halts(self):
        # Misaligned ontology (reasoning-heavy) with nidra vritti creates
        # real misalignment that triggers DUAL_ANOMALY or SEMANTIC_SHIFT.
        misaligned_weights = {l: 0.02 for l in ONTOLOGY_LAYERS}
        misaligned_weights["O7_REASONING"] = 0.90
        misaligned_weights["O1_POTENTIAL"] = 0.01
        result = jepa_governance_check(
            layer_weights=misaligned_weights,
            vritti_distribution=_nidra_vritti(),
            coherence=0.05,
            score=0.05,
            risk_level="destructive",
        )
        # Severe misalignment → HALT or CONFIRM
        assert result.recommended_action in ("HALT", "CONFIRM")
        assert result.execution_mode_override in ("BLOCKED", "CONFIRM_REQUIRED")

    def test_unknown_halts(self):
        result = jepa_governance_check(
            layer_weights={l: 0.0 for l in ONTOLOGY_LAYERS},
        )
        assert result.recommended_action == "HALT"
        assert result.execution_mode_override == "BLOCKED"


# =============================================================================
# Test: Audit Payload
# =============================================================================

class TestAuditPayload:
    def test_audit_dict_has_all_fields(self):
        result = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            vritti_distribution=_pramana_vritti(),
            coherence=0.7,
            score=0.7,
            tool_name="test_tool",
            risk_level="write",
        )
        audit = result.to_audit_dict()
        required_keys = {
            "regime", "recommended_action", "execution_mode_override",
            "escalation_override", "confidence_adjustment", "reason_codes",
            "rationale", "ontology_primary", "ontology_confidence",
            "vritti_primary", "vritti_confidence",
            "ontology_vritti_alignment", "integrated_confidence",
            "residual_magnitude", "semantic_consistency",
            "action_state_coherence", "action_category",
            "tool_name", "risk_level",
        }
        assert required_keys.issubset(set(audit.keys()))


# =============================================================================
# Test: GovernanceService Integration
# =============================================================================

class TestGovernanceServiceIntegration:
    def test_jepa_runs_during_authorization(self):
        """GovernanceService should run JEPA check without errors."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        svc = GovernanceService()
        resp = svc.authorize(AuthorizationRequest(
            actor_id="test",
            action_type="test_action",
            tool_name="search_files",
            quality_score=0.8,
            coherence_score=0.8,
        ))
        # Should complete without error
        assert resp.governance_decision is not None

    def test_jepa_override_on_low_signals(self):
        """Very low signals should cause JEPA to influence the decision."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        svc = GovernanceService()
        resp = svc.authorize(AuthorizationRequest(
            actor_id="test",
            action_type="dangerous_action",
            tool_name="rm_rf_everything",
            quality_score=0.05,
            coherence_score=0.05,
            agency_level="FULL",
        ))
        # With very low signals, JEPA should contribute to a DENY
        assert resp.governance_decision.value in ("DENY", "DEFER")


# =============================================================================
# Test: Reason Codes
# =============================================================================

class TestReasonCodes:
    def test_regime_in_reason_codes(self):
        result = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            vritti_distribution=_pramana_vritti(),
            coherence=0.8,
            score=0.8,
            risk_level="read_only",
        )
        assert any("REGIME_" in code for code in result.reason_codes)

    def test_observation_mode_executing_code(self):
        """Side effect during observation vritti should flag."""
        result = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            vritti_distribution=_nidra_vritti(),
            coherence=0.6,
            score=0.4,
            risk_level="execute",
            tool_name="run_code",
        )
        has_observation_flag = any(
            "OBSERVATION" in c or "DORMANCY" in c or "SIDE_EFFECT" in c
            for c in result.reason_codes
        )
        assert has_observation_flag or result.regime != GovernanceRegime.NORMAL

    def test_vikalpa_destructive_flagged(self):
        """High imagination + destructive action should be flagged in reason codes."""
        result = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            vritti_distribution=_vikalpa_vritti(),
            coherence=0.5,
            score=0.5,
            risk_level="destructive",
        )
        # With balanced ontology the regime may stay NORMAL, but the risk
        # factor and reason code must still be present.
        assert "IMAGINATIVE_DESTRUCTIVE" in result.reason_codes


# =============================================================================
# Test: Direct compute_residual() intermediate values (Test C1)
# =============================================================================

class TestComputeResidualIntermediates:
    """Directly test compute_residual() to verify intermediate values."""

    def test_read_only_always_semantically_consistent(self):
        """Read-only actions should have semantic_consistency=1.0."""
        ontology = build_ontology_signal(
            layer_weights={l: 0.9 for l in ONTOLOGY_LAYERS}
        )
        vritti = build_vritti_signal(
            vritti_distribution=_pramana_vritti(), coherence=0.8,
        )
        jepa = build_jepa_composite(ontology, vritti)
        runtime = build_runtime_process_state(
            tool_name="search", risk_level="read_only",
        )
        residual = compute_residual(jepa, runtime)
        assert residual.semantic_consistency == 1.0
        assert residual.action_state_coherence == 1.0

    def test_destructive_weak_execution_reduces_consistency(self):
        """Destructive action with weak O3_EXECUTION → lower semantic consistency."""
        weights = {l: 0.5 for l in ONTOLOGY_LAYERS}
        weights["O3_EXECUTION"] = 0.1  # Weak execution ontology
        # Make governance dominant
        weights["O7_REASONING"] = 0.9
        weights["O8_PURPOSE"] = 0.9
        ontology = build_ontology_signal(layer_weights=weights)
        vritti = build_vritti_signal(
            vritti_distribution=_pramana_vritti(), coherence=0.8,
        )
        jepa = build_jepa_composite(ontology, vritti)
        runtime = build_runtime_process_state(
            tool_name="drop_table", risk_level="destructive",
        )
        residual = compute_residual(jepa, runtime)
        # Should have reduced semantic consistency due to:
        # 1. governance-dominant ontology executing side effects
        # 2. weak O3_EXECUTION for destructive action
        assert residual.semantic_consistency < 0.5
        assert "DESTRUCTIVE_WITHOUT_EXECUTION_ONTOLOGY" in residual.reason_codes

    def test_observation_mode_side_effect_reduces_coherence(self):
        """Side-effecting action during observation vritti reduces coherence."""
        ontology = build_ontology_signal(layer_weights=_balanced_ontology())
        vritti = build_vritti_signal(
            vritti_distribution=_nidra_vritti(), coherence=0.5,
        )
        jepa = build_jepa_composite(ontology, vritti)
        runtime = build_runtime_process_state(
            tool_name="write_file", risk_level="write",
        )
        residual = compute_residual(jepa, runtime)
        assert residual.action_state_coherence < 0.6
        assert "SIDE_EFFECT_IN_OBSERVATION_MODE" in residual.reason_codes

    def test_residual_magnitude_is_weighted_blend(self):
        """Residual magnitude = 0.35*align + 0.30*semantic + 0.35*action."""
        ontology = build_ontology_signal(layer_weights=_balanced_ontology())
        vritti = build_vritti_signal(
            vritti_distribution=_pramana_vritti(), coherence=0.9, score=0.9,
        )
        jepa = build_jepa_composite(ontology, vritti)
        runtime = build_runtime_process_state(
            tool_name="read_log", risk_level="read_only",
        )
        residual = compute_residual(jepa, runtime)
        expected = (
            0.35 * (1.0 - jepa.ontology_vritti_alignment)
            + 0.30 * (1.0 - residual.semantic_consistency)
            + 0.35 * (1.0 - residual.action_state_coherence)
        )
        assert abs(residual.residual_magnitude - min(1.0, expected)) < 0.01


# =============================================================================
# Test: PRIVILEGED path coverage (Test C2)
# =============================================================================

class TestPrivilegedPath:
    """Test PRIVILEGED action category in residual computation."""

    def test_privileged_weak_agency_flagged(self):
        """Privileged action with weak O6_AGENCY → flagged."""
        weights = {l: 0.5 for l in ONTOLOGY_LAYERS}
        weights["O6_AGENCY"] = 0.1  # Weak agency
        result = jepa_governance_check(
            layer_weights=weights,
            vritti_distribution=_pramana_vritti(),
            coherence=0.8,
            score=0.8,
            tool_name="admin_grant",
            risk_level="privileged",
        )
        assert "PRIVILEGED_WITHOUT_AGENCY_ONTOLOGY" in result.reason_codes

    def test_privileged_strong_agency_ok(self):
        """Privileged action with strong O6_AGENCY → no agency flag."""
        weights = _balanced_ontology()
        weights["O6_AGENCY"] = 0.8
        result = jepa_governance_check(
            layer_weights=weights,
            vritti_distribution=_pramana_vritti(),
            coherence=0.8,
            score=0.8,
            tool_name="admin_grant",
            risk_level="privileged",
        )
        assert "PRIVILEGED_WITHOUT_AGENCY_ONTOLOGY" not in result.reason_codes

    def test_privileged_is_side_effecting(self):
        """Privileged actions must be classified as side-effecting."""
        rt = build_runtime_process_state(
            tool_name="sudo_cmd", risk_level="privileged",
        )
        assert rt.action_category == RuntimeActionCategory.PRIVILEGED
        assert rt.is_side_effecting


# =============================================================================
# Test: Boundary tests for thresholds 0.20 / 0.40 / 0.50
# =============================================================================

class TestThresholdBoundaries:
    """Test regime classification around boundary thresholds."""

    def test_alignment_at_critical_boundary(self):
        """Alignment just below 0.60 → should trigger DUAL_ANOMALY or SEMANTIC_SHIFT.

        Alignment is on [0, 1] where 0.5 = orthogonal (cosine 0),
        0.0 = anti-correlated, 1.0 = aligned.
        """
        from agentic.agentic_framework.jepa_governance import _classify_regime
        # alignment=0.59, with low action coherence → DUAL_ANOMALY
        regime = _classify_regime(
            alignment=0.59,
            semantic_consistency=0.6,
            action_state_coherence=0.4,
            residual_magnitude=0.5,
            integrated_confidence=0.3,
        )
        assert regime == GovernanceRegime.DUAL_ANOMALY

    def test_alignment_at_low_boundary(self):
        """Alignment just below 0.70 → SEMANTIC_SHIFT."""
        from agentic.agentic_framework.jepa_governance import _classify_regime
        regime = _classify_regime(
            alignment=0.69,
            semantic_consistency=0.8,
            action_state_coherence=0.8,
            residual_magnitude=0.3,
            integrated_confidence=0.3,
        )
        assert regime == GovernanceRegime.SEMANTIC_SHIFT

    def test_alignment_just_above_low_boundary(self):
        """Alignment at 0.71 with good coherence → not SEMANTIC_SHIFT."""
        from agentic.agentic_framework.jepa_governance import _classify_regime
        regime = _classify_regime(
            alignment=0.71,
            semantic_consistency=0.8,
            action_state_coherence=0.8,
            residual_magnitude=0.2,
            integrated_confidence=0.3,
        )
        assert regime == GovernanceRegime.NORMAL

    def test_action_coherence_at_050_boundary(self):
        """Action coherence just below 0.50 → PROCESS_DRIFT."""
        from agentic.agentic_framework.jepa_governance import _classify_regime
        regime = _classify_regime(
            alignment=0.80,  # above _ALIGNMENT_LOW (0.70)
            semantic_consistency=0.8,
            action_state_coherence=0.49,
            residual_magnitude=0.3,
            integrated_confidence=0.3,
        )
        assert regime == GovernanceRegime.PROCESS_DRIFT

    def test_residual_magnitude_above_040(self):
        """Residual magnitude above 0.40 → PROCESS_DRIFT."""
        from agentic.agentic_framework.jepa_governance import _classify_regime
        regime = _classify_regime(
            alignment=0.80,  # above _ALIGNMENT_LOW (0.70)
            semantic_consistency=0.6,
            action_state_coherence=0.6,
            residual_magnitude=0.41,
            integrated_confidence=0.3,
        )
        assert regime == GovernanceRegime.PROCESS_DRIFT

    def test_integrated_confidence_below_005_unknown(self):
        """Integrated confidence < 0.05 → UNKNOWN regardless of other signals."""
        from agentic.agentic_framework.jepa_governance import _classify_regime
        regime = _classify_regime(
            alignment=0.9,
            semantic_consistency=0.9,
            action_state_coherence=0.9,
            residual_magnitude=0.1,
            integrated_confidence=0.04,
        )
        assert regime == GovernanceRegime.UNKNOWN


# =============================================================================
# Test: All-zero vritti fail-closed
# =============================================================================

class TestAllZeroVritti:
    """All-zero vritti distribution must fail-closed to nidra."""

    def test_all_zero_vritti_becomes_nidra(self):
        """All-zero vritti distribution → nidra (dormancy)."""
        sig = build_vritti_signal(
            vritti_distribution={"pramana": 0.0, "viparyaya": 0.0,
                                  "vikalpa": 0.0, "smrti": 0.0, "nidra": 0.0},
        )
        assert sig.primary_vritti == "nidra"
        assert sig.distribution["nidra"] == 1.0
        assert sig.coherence == 0.0
        assert sig.confidence == 0.0

    def test_all_zero_vritti_with_execution_triggers_drift(self):
        """All-zero vritti + execute action → not NORMAL."""
        result = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            vritti_distribution={"pramana": 0.0, "viparyaya": 0.0,
                                  "vikalpa": 0.0, "smrti": 0.0, "nidra": 0.0},
            coherence=0.5,
            score=0.5,
            tool_name="run_code",
            risk_level="execute",
        )
        assert result.regime != GovernanceRegime.NORMAL


# =============================================================================
# Test: Override propagation in GovernanceService
# =============================================================================

class TestOverridePropagation:
    """Test that JEPA overrides propagate correctly through GovernanceService."""

    def test_jepa_override_recorded_in_audit(self):
        """JEPA override details must appear in audit event."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        svc = GovernanceService()
        resp = svc.authorize(AuthorizationRequest(
            actor_id="test",
            action_type="search_files",
            tool_name="search_files",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
            agency_level="FULL",
        ))
        snapshot = resp.audit_event.request_snapshot
        assert "jepa_regime" in snapshot
        assert "jepa_reason_codes" in snapshot
        assert "jepa_overrode_baseline" in snapshot
        assert "jepa_baseline_decision" in snapshot
        assert "jepa_confidence_adjustment" in snapshot

    def test_jepa_deny_override_shows_in_audit(self):
        """When JEPA causes DENY, audit should show the override."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        svc = GovernanceService()
        resp = svc.authorize(AuthorizationRequest(
            actor_id="test",
            action_type="delete_everything",
            tool_name="rm_rf",
            quality_score=0.05,
            coherence_score=0.05,
            internal_consistency=0.05,
            goal_alignment=0.05,
            trajectory_confidence=0.05,
            agency_level="FULL",
        ))
        # With very low signals, the decision should be DENY
        assert resp.governance_decision.value in ("DENY", "DEFER")
        snapshot = resp.audit_event.request_snapshot
        assert isinstance(snapshot["jepa_reason_codes"], list)

    def test_audit_has_all_jepa_fields(self):
        """Audit snapshot must contain all JEPA override detail fields."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        svc = GovernanceService()
        resp = svc.authorize(AuthorizationRequest(
            actor_id="test",
            action_type="search_files",
            tool_name="search",
            quality_score=0.9,
            coherence_score=0.9,
            agency_level="FULL",
        ))
        snapshot = resp.audit_event.request_snapshot
        required_keys = {
            "jepa_regime", "jepa_reason_codes", "jepa_overrode_baseline",
            "jepa_baseline_decision", "jepa_confidence_adjustment",
            "jepa_recommended_action", "jepa_execution_mode_override",
            "jepa_escalation_override",
        }
        assert required_keys.issubset(set(snapshot.keys())), (
            f"Missing keys: {required_keys - set(snapshot.keys())}"
        )


# =============================================================================
# Test: Invalid key validation
# =============================================================================

class TestInputValidation:
    """Validate that unknown keys in layer_weights and vritti_distribution are handled."""

    def test_unknown_layer_weights_keys_handled(self):
        """Unknown layer_weights keys should not crash, just warn."""
        sig = build_ontology_signal(
            layer_weights={
                "O7_REASONING": 0.9,
                "UNKNOWN_LAYER": 0.5,  # Should be ignored
            }
        )
        # Should still work — unknown key ignored, canonical layers used
        assert sig.primary_layer == "O7_REASONING"
        assert len(sig.layer_weights) == 12
        assert "UNKNOWN_LAYER" not in sig.layer_weights

    def test_unknown_vritti_keys_handled(self):
        """Unknown vritti_distribution keys should not crash."""
        sig = build_vritti_signal(
            vritti_distribution={
                "pramana": 0.8,
                "unknown_mode": 0.2,  # Should be ignored
            },
            coherence=0.7,
        )
        assert sig.primary_vritti == "pramana"
        assert "unknown_mode" not in sig.distribution

    def test_missing_vritti_keys_default_to_zero(self):
        """Missing vritti keys should default to 0.0."""
        sig = build_vritti_signal(
            vritti_distribution={"pramana": 1.0},  # Others missing
            coherence=0.8,
        )
        assert sig.distribution["viparyaya"] == 0.0
        assert sig.distribution["vikalpa"] == 0.0

    def test_missing_layer_keys_default_to_zero(self):
        """Missing layer keys should default to 0.0."""
        sig = build_ontology_signal(
            layer_weights={"O7_REASONING": 0.9},  # Others missing
        )
        assert sig.layer_weights["O1_POTENTIAL"] == 0.0
        assert sig.layer_weights["O12_ABSOLVING"] == 0.0


# =============================================================================
# Test: Shared safe wrapper and override function
# =============================================================================

class TestSafeWrapper:
    """Test safe_jepa_governance_check and apply_jepa_override."""

    def test_safe_wrapper_returns_assessment_on_success(self):
        """Safe wrapper should return normal assessment when JEPA works."""
        from agentic.agentic_framework.jepa_governance import safe_jepa_governance_check
        result = safe_jepa_governance_check(
            layer_weights=_balanced_ontology() | {"O7_REASONING": 0.9},
            vritti_distribution=_pramana_vritti(),
            coherence=0.8,
            score=0.8,
            risk_level="read_only",
        )
        assert result.regime == GovernanceRegime.NORMAL
        assert result.recommended_action == "ALLOW"

    def test_safe_wrapper_returns_unknown_on_error(self):
        """Safe wrapper should return UNKNOWN assessment on internal error."""
        from agentic.agentic_framework.jepa_governance import safe_jepa_governance_check
        # Pass invalid layer_weights type to trigger error inside jepa_governance_check
        result = safe_jepa_governance_check(
            layer_weights=None,  # Will cause ValueError
            olm_signals=None,    # Also None → ValueError
        )
        assert result.regime == GovernanceRegime.UNKNOWN
        assert result.recommended_action == "HALT"
        assert "JEPA_UNAVAILABLE" in result.reason_codes

    def test_shared_override_normal_no_change(self):
        """apply_jepa_override with NORMAL regime should not change decision."""
        from agentic.agentic_framework.jepa_governance import apply_jepa_override
        assessment = jepa_governance_check(
            layer_weights=_balanced_ontology() | {"O7_REASONING": 0.9},
            vritti_distribution=_pramana_vritti(),
            coherence=0.8,
            score=0.8,
            risk_level="read_only",
        )
        result = apply_jepa_override("ALLOW", True, assessment)
        assert result["decision"] == "ALLOW"
        assert result["eligible"] is True
        assert result["overrode"] is False

    def test_shared_override_halt_forces_deny(self):
        """apply_jepa_override with HALT action should force DENY."""
        from agentic.agentic_framework.jepa_governance import apply_jepa_override
        # Create an assessment with UNKNOWN regime (HALT)
        assessment = jepa_governance_check(
            layer_weights={l: 0.0 for l in ONTOLOGY_LAYERS},
        )
        assert assessment.recommended_action == "HALT"
        result = apply_jepa_override("ALLOW", True, assessment)
        assert result["decision"] == "DENY"
        assert result["eligible"] is False
        assert result["overrode"] is True

    def test_shared_override_never_weakens_deny(self):
        """apply_jepa_override must never upgrade DENY to ALLOW."""
        from agentic.agentic_framework.jepa_governance import apply_jepa_override
        assessment = jepa_governance_check(
            layer_weights=_balanced_ontology() | {"O7_REASONING": 0.9},
            vritti_distribution=_pramana_vritti(),
            coherence=0.8,
            score=0.8,
            risk_level="read_only",
        )
        # Even with NORMAL regime, DENY baseline must stay DENY
        result = apply_jepa_override("DENY", False, assessment)
        assert result["decision"] == "DENY"
        assert result["eligible"] is False

    def test_shared_override_degrade_downgrades_allow(self):
        """DEGRADE recommended_action should downgrade ALLOW to DEFER."""
        from agentic.agentic_framework.jepa_governance import apply_jepa_override
        # Use nidra + balanced ontology to get PROCESS_DRIFT (DEGRADE)
        assessment = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            vritti_distribution=_nidra_vritti(),
            coherence=0.5,
            score=0.3,
            tool_name="write_file",
            risk_level="write",
        )
        if assessment.recommended_action == "DEGRADE":
            result = apply_jepa_override("ALLOW", True, assessment)
            assert result["decision"] == "DEFER"
            assert result["overrode"] is True


# =============================================================================
# Test: GovernanceService JEPA Rationale & Override Integration
# =============================================================================


class TestGovernanceServiceJEPARationale:
    """Test that JEPA info appears in rationale codes and strings."""

    def test_rationale_codes_contain_jepa_regime(self):
        """Rationale codes should include JEPA_REGIME when JEPA runs."""
        from agentic.agentic_framework.governance_service import (
            GovernanceService, AuthorizationRequest,
        )
        svc = GovernanceService()
        resp = svc.authorize(AuthorizationRequest(
            actor_id="test",
            action_type="read_file",
            tool_name="read_file",
            quality_score=0.9,
            coherence_score=0.9,
        ))
        codes = resp.rationale_codes
        jepa_regime_codes = [c for c in codes if c.startswith("JEPA_REGIME:")]
        assert len(jepa_regime_codes) == 1

    def test_rationale_codes_contain_jepa_override_when_overriding(self):
        """JEPA_OVERRIDE: must appear when JEPA actually changes the decision."""
        from agentic.agentic_framework.jepa_governance import apply_jepa_override
        # Force a HALT assessment (UNKNOWN regime)
        assessment = jepa_governance_check(
            layer_weights={l: 0.0 for l in ONTOLOGY_LAYERS},
        )
        assert assessment.recommended_action == "HALT"
        result = apply_jepa_override("ALLOW", True, assessment)
        assert result["overrode"] is True

        # Now verify via GovernanceService with very low signals
        from agentic.agentic_framework.governance_service import (
            GovernanceService, AuthorizationRequest,
        )
        svc = GovernanceService()
        resp = svc.authorize(AuthorizationRequest(
            actor_id="test",
            action_type="execute_code",
            tool_name="execute_code",
            quality_score=0.05,
            coherence_score=0.05,
        ))
        codes = resp.rationale_codes
        # Must have JEPA_REGIME
        assert any(c.startswith("JEPA_REGIME:") for c in codes)
        # If JEPA overrode, must have JEPA_OVERRIDE
        snap = resp.audit_event.request_snapshot
        if snap["jepa_overrode_baseline"]:
            assert any(c.startswith("JEPA_OVERRIDE:") for c in codes)

    def test_audit_snapshot_has_jepa_fields(self):
        """Audit event request_snapshot should contain JEPA fields."""
        from agentic.agentic_framework.governance_service import (
            GovernanceService, AuthorizationRequest,
        )
        svc = GovernanceService()
        resp = svc.authorize(AuthorizationRequest(
            actor_id="test",
            action_type="read_file",
            tool_name="read_file",
            quality_score=0.9,
            coherence_score=0.9,
        ))
        snap = resp.audit_event.request_snapshot
        required = {
            "jepa_regime", "jepa_reason_codes", "jepa_overrode_baseline",
            "jepa_confidence_adjustment", "jepa_recommended_action",
            "jepa_execution_mode_override", "jepa_escalation_override",
        }
        assert required.issubset(set(snap.keys()))


class TestGovernanceServiceJEPAEffectiveValues:
    """Test that JEPA confidence_adjustment, execution_mode_override,
    and escalation_override are applied to the effective response."""

    def test_confidence_adjustment_isolated(self):
        """JEPA confidence_adjustment must reduce confidence_score below raw gate value.

        We directly compute what the gate would produce, then verify the
        response confidence is lower by the JEPA adjustment amount.
        """
        from agentic.agentic_framework.governance_service import (
            GovernanceService, AuthorizationRequest, _build_confidence_signals,
        )
        from agentic.agentic_framework.mcp_gateway import ToolRiskLevel
        svc = GovernanceService()
        req = AuthorizationRequest(
            actor_id="test",
            action_type="read_file",
            tool_name="read_file",
            quality_score=0.9,
            coherence_score=0.9,
        )
        resp = svc.authorize(req)
        # Get the raw gate confidence
        risk = svc.classifier.classify(req.tool_name or req.action_type)
        signals = _build_confidence_signals(req, risk)
        gate = svc.gate.evaluate(signals, req.tool_name or req.action_type)
        raw_confidence = gate.confidence.overall
        jepa_adj = resp.audit_event.request_snapshot["jepa_confidence_adjustment"]
        entropy_penalty = resp.audit_event.request_snapshot.get(
            "entropy_confidence_penalty", 0.0
        ) or 0.0
        insight_penalty = resp.audit_event.request_snapshot.get(
            "sovereign_insight_confidence_penalty", 0.0
        ) or 0.0
        guna_penalty = resp.audit_event.request_snapshot.get(
            "sovereign_guna_confidence_penalty", 0.0
        ) or 0.0
        # Phase S4: aggregate sovereign penalty is capped at 0.20
        sovereign_penalty = min(0.20, entropy_penalty + insight_penalty + guna_penalty)
        expected = max(0.0, raw_confidence + jepa_adj - sovereign_penalty)
        assert abs(resp.confidence_score - expected) < 0.001

    def test_confidence_never_negative(self):
        """Confidence after JEPA adjustment should never go below 0."""
        from agentic.agentic_framework.governance_service import (
            GovernanceService, AuthorizationRequest,
        )
        svc = GovernanceService()
        resp = svc.authorize(AuthorizationRequest(
            actor_id="test",
            action_type="execute_code",
            tool_name="execute_code",
            quality_score=0.01,
            coherence_score=0.01,
        ))
        assert resp.confidence_score >= 0.0

    def test_execution_mode_override_applied(self):
        """When JEPA overrides execution_mode, response must reflect the stricter mode."""
        from agentic.agentic_framework.governance_service import (
            GovernanceService, AuthorizationRequest,
        )
        svc = GovernanceService()
        # Very low signals to trigger non-NORMAL regime with exec override
        resp = svc.authorize(AuthorizationRequest(
            actor_id="test",
            action_type="execute_code",
            tool_name="execute_code",
            quality_score=0.05,
            coherence_score=0.05,
        ))
        snap = resp.audit_event.request_snapshot
        jepa_exec_override = snap["jepa_execution_mode_override"]
        if jepa_exec_override is not None:
            # JEPA wanted to override → response execution_mode should be at
            # least as strict as the override
            _EXEC_SEVERITY = {"full": 0, "cautious": 1, "confirm": 2,
                              "confirm_required": 2, "blocked": 3}
            resp_sev = _EXEC_SEVERITY.get(resp.execution_mode.value, 0)
            jepa_sev = _EXEC_SEVERITY.get(jepa_exec_override.lower(), 0)
            assert resp_sev >= jepa_sev

    def test_escalation_override_applied(self):
        """When JEPA overrides escalation, response must reflect the stricter level."""
        from agentic.agentic_framework.governance_service import (
            GovernanceService, AuthorizationRequest,
        )
        svc = GovernanceService()
        resp = svc.authorize(AuthorizationRequest(
            actor_id="test",
            action_type="execute_code",
            tool_name="execute_code",
            quality_score=0.05,
            coherence_score=0.05,
        ))
        snap = resp.audit_event.request_snapshot
        jepa_esc_override = snap["jepa_escalation_override"]
        if jepa_esc_override is not None:
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            resp_sev = _ESC_SEVERITY.get(resp.escalation_level.value, 0)
            jepa_sev = _ESC_SEVERITY.get(jepa_esc_override.lower(), 0)
            assert resp_sev >= jepa_sev


# =============================================================================
# Test: apply_jepa_override edge cases
# =============================================================================


class TestApplyJepaOverrideEdgeCases:
    """Edge cases for the shared override function."""

    def test_eligible_false_when_decision_deny(self):
        """eligible must be False whenever decision is DENY."""
        from agentic.agentic_framework.jepa_governance import apply_jepa_override
        # Baseline is DENY but eligible is True (shouldn't happen, but enforce)
        assessment = jepa_governance_check(
            layer_weights=_balanced_ontology() | {"O7_REASONING": 0.9},
            vritti_distribution=_pramana_vritti(),
            coherence=0.8,
            score=0.8,
            risk_level="read_only",
        )
        # NORMAL regime → no change, but baseline was DENY
        result = apply_jepa_override("DENY", True, assessment)
        assert result["decision"] == "DENY"
        assert result["eligible"] is False

    def test_eligible_false_when_decision_defer(self):
        """eligible must be False whenever decision is DEFER."""
        from agentic.agentic_framework.jepa_governance import apply_jepa_override
        assessment = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            vritti_distribution=_nidra_vritti(),
            coherence=0.5,
            score=0.3,
            tool_name="write_file",
            risk_level="write",
        )
        if assessment.recommended_action == "DEGRADE":
            result = apply_jepa_override("ALLOW", True, assessment)
            assert result["decision"] == "DEFER"
            assert result["eligible"] is False

    def test_baseline_defer_with_halt(self):
        """Baseline DEFER + HALT recommended → DENY."""
        from agentic.agentic_framework.jepa_governance import apply_jepa_override
        assessment = jepa_governance_check(
            layer_weights={l: 0.0 for l in ONTOLOGY_LAYERS},
        )
        assert assessment.recommended_action == "HALT"
        result = apply_jepa_override("DEFER", True, assessment)
        assert result["decision"] == "DENY"
        assert result["eligible"] is False

    def test_baseline_defer_with_degrade(self):
        """Baseline DEFER + DEGRADE → stays DEFER (already degraded)."""
        from agentic.agentic_framework.jepa_governance import apply_jepa_override
        assessment = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            vritti_distribution=_nidra_vritti(),
            coherence=0.5,
            score=0.3,
            tool_name="write_file",
            risk_level="write",
        )
        if assessment.recommended_action == "DEGRADE":
            result = apply_jepa_override("DEFER", True, assessment)
            # DEGRADE only downgrades ALLOW→DEFER, not DEFER→DENY
            assert result["decision"] == "DEFER"
            assert result["eligible"] is False

    def test_degrade_forced_not_vacuous(self):
        """Ensure DEGRADE path is actually exercised (non-vacuous test)."""
        from agentic.agentic_framework.jepa_governance import apply_jepa_override
        # Construct nidra+balanced with specific params that produce PROCESS_DRIFT
        assessment = jepa_governance_check(
            layer_weights=_balanced_ontology(),
            vritti_distribution=_nidra_vritti(),
            coherence=0.5,
            score=0.3,
            tool_name="write_file",
            risk_level="write",
        )
        # The test must actually exercise the DEGRADE path
        assert assessment.regime in (
            GovernanceRegime.PROCESS_DRIFT,
            GovernanceRegime.SEMANTIC_SHIFT,
            GovernanceRegime.DUAL_ANOMALY,
        ), f"Expected non-NORMAL regime, got {assessment.regime}"
        result = apply_jepa_override("ALLOW", True, assessment)
        assert result["decision"] in ("DEFER", "DENY")
        assert result["overrode"] is True


# =============================================================================
# Test: _make_unavailable_assessment fields
# =============================================================================


class TestMakeUnavailableAssessment:
    """Directly test _make_unavailable_assessment output fields."""

    def test_unavailable_assessment_fields(self):
        from agentic.agentic_framework.jepa_governance import _make_unavailable_assessment
        assessment = _make_unavailable_assessment("test error", {"tool_name": "foo"})
        assert assessment.regime == GovernanceRegime.UNKNOWN
        assert assessment.recommended_action == "HALT"
        assert assessment.confidence_adjustment == -0.50
        assert assessment.execution_mode_override == "BLOCKED"
        assert assessment.escalation_override == "HALT"
        assert "JEPA_UNAVAILABLE" in assessment.reason_codes
        assert "UNKNOWN_REGIME" in assessment.reason_codes
        assert assessment.residual.residual_magnitude == 1.0
        assert assessment.residual.semantic_consistency == 0.0


# =============================================================================
# Test: Coupling validation failure
# =============================================================================


class TestCouplingValidation:
    """Test that _validate_coupling_import checks exact key names."""

    def test_validation_rejects_wrong_keys(self):
        from agentic.agentic_framework.jepa_governance import _validate_coupling_import
        from unittest.mock import patch
        # Mock get_aspect_weights to return wrong key names
        bad_result = {f"WRONG_{i}": 0.1 for i in range(12)}
        with patch("agentic.agentic_framework.jepa_governance._get_aspect_weights",
                    return_value=bad_result):
            with pytest.raises(ImportError, match="wrong keys"):
                _validate_coupling_import()

    def test_validation_rejects_non_dict(self):
        from agentic.agentic_framework.jepa_governance import _validate_coupling_import
        from unittest.mock import patch
        with patch("agentic.agentic_framework.jepa_governance._get_aspect_weights",
                    return_value=[0.1] * 12):
            with pytest.raises(ImportError, match="expected dict"):
                _validate_coupling_import()


# =============================================================================
# Test: Shared signal approximation
# =============================================================================


class TestSharedApproximation:
    """Test that the shared approximation functions are used by both paths."""

    def test_approximate_layer_weights_uses_goal_alignment_for_agency(self):
        """O6_AGENCY must use goal_alignment, not quality."""
        from agentic.agentic_framework.jepa_governance import approximate_layer_weights
        # goal_alignment=0.9, quality=0.1 → O6_AGENCY = 0.9*0.7 = 0.63
        w = approximate_layer_weights(
            quality=0.1, coherence=0.5, goal_alignment=0.9,
            overall_confidence=0.5,
        )
        assert abs(w["O6_AGENCY"] - 0.9 * 0.7) < 0.001
        assert abs(w["O8_PURPOSE"] - 0.9 * 0.8) < 0.001

    def test_approximate_vritti_no_smrti(self):
        """Shared vritti approximation must NOT include hardcoded smrti."""
        from agentic.agentic_framework.jepa_governance import approximate_vritti
        dist = approximate_vritti(quality=0.5, coherence=0.5, overall_confidence=0.5)
        assert dist["smrti"] == 0.0
        assert abs(sum(dist.values()) - 1.0) < 0.01

    def test_approximate_vritti_all_zero_inputs(self):
        """All-zero inputs produce a valid normalized distribution."""
        from agentic.agentic_framework.jepa_governance import approximate_vritti
        dist = approximate_vritti(quality=0.0, coherence=0.0, overall_confidence=0.0)
        assert abs(sum(dist.values()) - 1.0) < 0.01
        # Should have nidra and/or viparyaya dominant (dormancy/misperception)
        assert dist["pramana"] == 0.0 or dist["nidra"] > 0 or dist["viparyaya"] > 0


# =============================================================================
# Test: MCP Gateway integration
# =============================================================================


class TestMCPGatewayIntegration:
    """End-to-end MCP gateway tests with JEPA integration."""

    @pytest.fixture
    def gateway(self):
        """Create a SafeMCPGateway with a mock client."""
        from agentic.agentic_framework.mcp_gateway import (
            SafeMCPGateway, MockMCPClient, ToolRiskLevel,
        )
        client = MockMCPClient()
        client.register_tool(
            "read_data",
            lambda params: {"data": "ok"},
            ToolRiskLevel.READ_ONLY,
        )
        client.register_tool(
            "write_data",
            lambda params: {"written": True},
            ToolRiskLevel.WRITE,
        )
        return SafeMCPGateway(mcp_client=client)

    @pytest.mark.asyncio
    async def test_call_tool_success_has_jepa_audit(self, gateway):
        """Successful call_tool must record JEPA fields in audit."""
        from agentic.agentic_framework.mcp_gateway import MCPToolCall
        result = await gateway.call_tool(MCPToolCall(
            tool_name="read_data",
            parameters={"key": "val"},
            quality_score=0.9,
            coherence_score=0.9,
        ))
        assert result.success
        assert len(gateway.audit_log) == 1
        entry = gateway.audit_log[0]
        assert entry.jepa_regime is not None
        assert entry.jepa_recommended_action is not None
        assert entry.jepa_reason_codes is not None
        assert entry.jepa_confidence_adjustment is not None

    @pytest.mark.asyncio
    async def test_call_tool_jepa_adjusted_confidence(self, gateway):
        """MCPToolResult.confidence must reflect JEPA adjustment."""
        from agentic.agentic_framework.mcp_gateway import MCPToolCall
        result = await gateway.call_tool(MCPToolCall(
            tool_name="read_data",
            parameters={},
            quality_score=0.9,
            coherence_score=0.9,
        ))
        entry = gateway.audit_log[0]
        adj = entry.jepa_confidence_adjustment
        # Result confidence = max(0, raw + adj)
        # Since raw is what the gate produced, result should have the adjustment
        # We can verify: result.confidence <= raw_confidence (adj <= 0 always)
        assert adj is not None
        if adj < 0:
            # Confidence in result should be less than raw gate confidence
            assert result.confidence < entry.confidence - adj + 0.001

    @pytest.mark.asyncio
    async def test_call_tool_forbidden_no_jepa(self, gateway):
        """Forbidden capability early exit should have no JEPA in audit."""
        from agentic.agentic_framework.mcp_gateway import (
            MCPToolCall, MCPToolDefinition, ToolRiskLevel, GatewayDecision,
        )
        # Register a tool with forbidden capability
        gateway.register_tool(MCPToolDefinition(
            name="evil_tool",
            description="bad",
            risk_level=ToolRiskLevel.PRIVILEGED,
            capabilities=["credential_access"],
        ))
        result = await gateway.call_tool(MCPToolCall(
            tool_name="evil_tool",
            parameters={},
        ))
        assert result.decision == GatewayDecision.BLOCKED
        entry = gateway.audit_log[0]
        # JEPA didn't run on this path
        assert entry.jepa_regime is None

    @pytest.mark.asyncio
    async def test_call_tool_jepa_escalation_override(self, gateway):
        """MCPToolResult.escalation_level must reflect JEPA override."""
        from agentic.agentic_framework.mcp_gateway import MCPToolCall
        # Low signals to trigger JEPA escalation override
        result = await gateway.call_tool(MCPToolCall(
            tool_name="read_data",
            parameters={},
            quality_score=0.1,
            coherence_score=0.1,
        ))
        entry = gateway.audit_log[0]
        if entry.jepa_escalation_override is not None:
            from agentic.agentic_framework.confidence_gate import EscalationLevel
            _ESC_SEV = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            result_sev = _ESC_SEV.get(result.escalation_level.value, 0)
            jepa_sev = _ESC_SEV.get(entry.jepa_escalation_override.lower(), 0)
            assert result_sev >= jepa_sev


# =============================================================================
# Test: MCP _jepa_check directly
# =============================================================================


class TestMCPJepaCheck:
    """Direct test of MCP _jepa_check signal approximation."""

    def test_jepa_check_uses_shared_approximation(self):
        """MCP _jepa_check must use approximate_layer_weights/approximate_vritti."""
        from agentic.agentic_framework.mcp_gateway import (
            SafeMCPGateway, MockMCPClient, MCPToolCall, MCPToolDefinition,
            ToolRiskLevel,
        )
        from agentic.agentic_framework.confidence_gate import create_confidence_gate
        client = MockMCPClient()
        gw = SafeMCPGateway(mcp_client=client)
        tool_def = gw._get_tool_definition("test_tool")
        call = MCPToolCall(
            tool_name="test_tool",
            parameters={},
            quality_score=0.7,
            coherence_score=0.7,
        )
        signals = gw._build_signals(call, tool_def)
        gate_decision = gw.gate.evaluate(signals, "test_tool")
        # Phase 1: _jepa_check now returns (assessment, vritti_resolution, entropy_resolution)
        assessment, vritti_resolution, entropy_resolution = gw._jepa_check(
            call, tool_def, gate_decision,
        )
        # Must return a full assessment, never None
        assert assessment is not None
        assert assessment.regime is not None
        assert hasattr(assessment, "confidence_adjustment")
        # Phase 1: Verify signal provenance metadata
        assert vritti_resolution is not None
        assert vritti_resolution.source is not None
        assert entropy_resolution is not None


# =============================================================================
# Test: Durable audit persistence of JEPA fields
# =============================================================================


class TestDurableAuditJEPAPersistence:
    """Test that JEPA fields survive into the durable audit store."""

    def test_event_from_mcp_audit_with_jepa(self):
        """event_from_mcp_audit must embed JEPA fields in request_snapshot."""
        from agentic.ledger.governance_audit_store import event_from_mcp_audit
        event = event_from_mcp_audit(
            timestamp="2024-01-01T00:00:00Z",
            request_id="test-123",
            tool_name="test_tool",
            parameters={"key": "val"},
            decision="BLOCKED",
            confidence=0.5,
            risk_level="write",
            jepa_regime="dual_anomaly",
            jepa_recommended_action="HALT",
            jepa_reason_codes=["SIDE_EFFECT_IN_OBSERVATION_MODE", "REGIME_DUAL_ANOMALY"],
            jepa_confidence_adjustment=-0.40,
            jepa_execution_mode_override="BLOCKED",
            jepa_escalation_override="HALT",
            jepa_overrode=True,
        )
        snap = event.request_snapshot
        assert snap["jepa_regime"] == "dual_anomaly"
        assert snap["jepa_recommended_action"] == "HALT"
        assert "SIDE_EFFECT_IN_OBSERVATION_MODE" in snap["jepa_reason_codes"]
        assert snap["jepa_confidence_adjustment"] == -0.40
        assert snap["jepa_execution_mode_override"] == "BLOCKED"
        assert snap["jepa_escalation_override"] == "HALT"
        assert snap["jepa_overrode"] is True

    def test_event_from_mcp_audit_without_jepa(self):
        """event_from_mcp_audit without JEPA args should have no JEPA in snapshot."""
        from agentic.ledger.governance_audit_store import event_from_mcp_audit
        event = event_from_mcp_audit(
            timestamp="2024-01-01T00:00:00Z",
            request_id="test-456",
            tool_name="test_tool",
            parameters={"key": "val"},
            decision="ALLOWED",
            confidence=0.8,
            risk_level="read_only",
        )
        snap = event.request_snapshot
        assert "jepa_regime" not in snap
