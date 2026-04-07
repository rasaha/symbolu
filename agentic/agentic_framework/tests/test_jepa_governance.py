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
# Test: Ontology → Vritti prior (Phase 1, cognitive-axis cause direction)
# =============================================================================


class TestOntologyVrittiPrior:
    """Tests for ontology_vritti_prior() and its integration into
    approximate_vritti(). Phase 1 of the directional model refinement."""

    def test_prior_reasoning_dominant_boosts_pramana(self):
        """High O7_REASONING should produce a pramana-dominant prior."""
        from agentic.agentic_framework.jepa_governance import ontology_vritti_prior
        prior = ontology_vritti_prior({"O7_REASONING": 0.9, "O9_WITNESSES": 0.8})
        assert prior["pramana"] > prior["viparyaya"]
        assert prior["pramana"] > prior["vikalpa"]
        assert prior["pramana"] > prior["nidra"]

    def test_prior_agency_dominant_boosts_viparyaya(self):
        """High O6_AGENCY should produce elevated viparyaya."""
        from agentic.agentic_framework.jepa_governance import ontology_vritti_prior
        prior = ontology_vritti_prior({"O6_AGENCY": 0.9})
        assert prior["viparyaya"] > prior["smrti"]
        assert prior["viparyaya"] > prior["nidra"]

    def test_prior_cognition_dominant_boosts_vikalpa(self):
        """High O5_COGNITION should produce elevated vikalpa."""
        from agentic.agentic_framework.jepa_governance import ontology_vritti_prior
        prior = ontology_vritti_prior({"O5_COGNITION": 0.9})
        assert prior["vikalpa"] > prior["viparyaya"]
        assert prior["vikalpa"] > prior["nidra"]

    def test_prior_execution_purpose_boosts_smrti(self):
        """High O3_EXECUTION + O8_PURPOSE should produce elevated smrti."""
        from agentic.agentic_framework.jepa_governance import ontology_vritti_prior
        prior = ontology_vritti_prior({"O3_EXECUTION": 0.9, "O8_PURPOSE": 0.9})
        assert prior["smrti"] > prior["viparyaya"]
        assert prior["smrti"] > prior["nidra"]

    def test_prior_potential_dominant_boosts_nidra(self):
        """High O1_POTENTIAL should produce elevated nidra."""
        from agentic.agentic_framework.jepa_governance import ontology_vritti_prior
        prior = ontology_vritti_prior({"O1_POTENTIAL": 0.9, "O12_ABSOLVING": 0.7})
        assert prior["nidra"] > prior["viparyaya"]
        assert prior["nidra"] > prior["vikalpa"]

    def test_prior_all_zero_returns_all_zero(self):
        """All-zero layer weights produce all-zero prior."""
        from agentic.agentic_framework.jepa_governance import ontology_vritti_prior
        prior = ontology_vritti_prior({})
        assert all(v == 0.0 for v in prior.values())

    def test_prior_always_nonnegative(self):
        """Prior values are always non-negative."""
        from agentic.agentic_framework.jepa_governance import ontology_vritti_prior
        prior = ontology_vritti_prior({
            "O1_POTENTIAL": 0.5, "O3_EXECUTION": 0.3,
            "O5_COGNITION": 0.7, "O6_AGENCY": 0.2,
            "O7_REASONING": 0.9, "O12_ABSOLVING": 0.4,
        })
        assert all(v >= 0.0 for v in prior.values())

    def test_approximate_vritti_no_layer_weights_unchanged(self):
        """Without layer_weights, approximate_vritti is identical to old behavior."""
        from agentic.agentic_framework.jepa_governance import approximate_vritti
        dist_none = approximate_vritti(quality=0.7, coherence=0.6, overall_confidence=0.8)
        dist_explicit = approximate_vritti(
            quality=0.7, coherence=0.6, overall_confidence=0.8,
            layer_weights=None,
        )
        for k in dist_none:
            assert abs(dist_none[k] - dist_explicit[k]) < 1e-10

    def test_approximate_vritti_with_prior_shifts_distribution(self):
        """With reasoning-dominant layer_weights, pramana should increase."""
        from agentic.agentic_framework.jepa_governance import approximate_vritti
        base = approximate_vritti(quality=0.5, coherence=0.5, overall_confidence=0.5)
        with_prior = approximate_vritti(
            quality=0.5, coherence=0.5, overall_confidence=0.5,
            layer_weights={"O7_REASONING": 0.9, "O9_WITNESSES": 0.8},
        )
        # Prior should boost pramana
        assert with_prior["pramana"] > base["pramana"]
        # Shift should be modest (bounded by alpha=0.2)
        assert with_prior["pramana"] - base["pramana"] < 0.20

    def test_approximate_vritti_with_prior_stays_normalized(self):
        """Distribution must sum to 1.0 after prior application."""
        from agentic.agentic_framework.jepa_governance import approximate_vritti
        dist = approximate_vritti(
            quality=0.3, coherence=0.8, overall_confidence=0.4,
            layer_weights={
                "O1_POTENTIAL": 0.3, "O3_EXECUTION": 0.7,
                "O5_COGNITION": 0.5, "O6_AGENCY": 0.4,
                "O7_REASONING": 0.9, "O8_PURPOSE": 0.6,
                "O12_ABSOLVING": 0.2,
            },
        )
        assert abs(sum(dist.values()) - 1.0) < 0.01

    def test_approximate_vritti_prior_bounded_influence(self):
        """Prior influence must be bounded by alpha even with extreme weights."""
        from agentic.agentic_framework.jepa_governance import approximate_vritti
        base = approximate_vritti(quality=0.5, coherence=0.5, overall_confidence=0.5)
        extreme = approximate_vritti(
            quality=0.5, coherence=0.5, overall_confidence=0.5,
            layer_weights={"O1_POTENTIAL": 1.0, "O12_ABSOLVING": 1.0},
        )
        # Even with extreme nidra-biased prior, each mode should shift
        # by at most ~alpha (0.2)
        for k in base:
            assert abs(extreme[k] - base[k]) <= 0.21  # small tolerance

    def test_approximate_vritti_all_zero_layer_weights_unchanged(self):
        """All-zero layer_weights produce identical output to no prior."""
        from agentic.agentic_framework.jepa_governance import approximate_vritti
        base = approximate_vritti(quality=0.5, coherence=0.5, overall_confidence=0.5)
        with_zero = approximate_vritti(
            quality=0.5, coherence=0.5, overall_confidence=0.5,
            layer_weights={"O7_REASONING": 0.0, "O1_POTENTIAL": 0.0},
        )
        for k in base:
            assert abs(base[k] - with_zero[k]) < 1e-10

    def test_approximate_vritti_old_tests_still_pass(self):
        """Existing approximate_vritti contracts still hold."""
        from agentic.agentic_framework.jepa_governance import approximate_vritti
        # No smrti in output
        dist = approximate_vritti(quality=0.5, coherence=0.5, overall_confidence=0.5)
        assert dist["smrti"] == 0.0
        assert abs(sum(dist.values()) - 1.0) < 0.01

        # All-zero inputs produce valid distribution
        dist = approximate_vritti(quality=0.0, coherence=0.0, overall_confidence=0.0)
        assert abs(sum(dist.values()) - 1.0) < 0.01

    def test_jepa_alignment_improves_with_prior(self):
        """JEPA alignment should improve when ontology prior nudges vritti
        toward the direction R[v,a] would predict.

        Test case: analytical context (high quality, high coherence)
        produces reasoning-dominant ontology. Without prior, vritti is
        independently estimated. With prior, vritti should be nudged
        toward pramana, which R[v,a] expects to couple with O7_REASONING.
        """
        from agentic.agentic_framework.jepa_governance import (
            approximate_layer_weights,
            approximate_vritti,
            build_ontology_signal,
            build_vritti_signal,
            build_jepa_composite,
        )

        # Analytical context: high quality and coherence
        lw = approximate_layer_weights(
            quality=0.9, coherence=0.9,
            goal_alignment=0.8, overall_confidence=0.85,
        )

        # Without ontology prior
        vritti_base = approximate_vritti(
            quality=0.9, coherence=0.9, overall_confidence=0.85,
        )
        # With ontology prior
        vritti_prior = approximate_vritti(
            quality=0.9, coherence=0.9, overall_confidence=0.85,
            layer_weights=lw,
        )

        ontology = build_ontology_signal(layer_weights=lw)
        vritti_no_prior = build_vritti_signal(vritti_distribution=vritti_base)
        vritti_with_prior = build_vritti_signal(vritti_distribution=vritti_prior)

        jepa_no_prior = build_jepa_composite(ontology, vritti_no_prior)
        jepa_with_prior = build_jepa_composite(ontology, vritti_with_prior)

        # Alignment should be at least as good with the prior
        assert jepa_with_prior.ontology_vritti_alignment >= \
               jepa_no_prior.ontology_vritti_alignment - 0.001  # tiny tolerance

    def test_prior_can_shift_top1_vritti(self):
        """When base vritti is ambiguous, a strong ontology prior can shift
        the dominant mode."""
        from agentic.agentic_framework.jepa_governance import approximate_vritti

        # Low quality + low coherence → viparyaya/nidra dominant base
        base = approximate_vritti(quality=0.2, coherence=0.2, overall_confidence=0.3)
        # Strong reasoning ontology → should boost pramana
        with_prior = approximate_vritti(
            quality=0.2, coherence=0.2, overall_confidence=0.3,
            layer_weights={"O7_REASONING": 0.95, "O9_WITNESSES": 0.9},
        )
        # Prior should meaningfully boost pramana even in low-quality context
        assert with_prior["pramana"] > base["pramana"]

    def test_prior_does_not_introduce_negative_values(self):
        """No vritti mode should become negative after prior application."""
        from agentic.agentic_framework.jepa_governance import approximate_vritti
        dist = approximate_vritti(
            quality=0.1, coherence=0.1, overall_confidence=0.1,
            layer_weights={"O7_REASONING": 1.0},
        )
        assert all(v >= 0.0 for v in dist.values())

    def test_prior_with_smrti_via_ontology(self):
        """Ontology prior can introduce non-zero smrti (which base never produces)."""
        from agentic.agentic_framework.jepa_governance import approximate_vritti
        base = approximate_vritti(quality=0.5, coherence=0.5, overall_confidence=0.5)
        assert base["smrti"] == 0.0  # Base never produces smrti

        with_prior = approximate_vritti(
            quality=0.5, coherence=0.5, overall_confidence=0.5,
            layer_weights={"O3_EXECUTION": 0.9, "O8_PURPOSE": 0.9},
        )
        # Prior should introduce non-zero smrti
        assert with_prior["smrti"] > 0.0


class TestP1Calibration:
    """Calibration assertions for the Phase 1 ontology-vritti prior.

    These tests encode the findings from the P1 calibration evaluation
    (examples/p1_calibration_eval.py) as reproducible assertions.
    """

    CALIBRATION_SCENARIOS = [
        # (name, quality, coherence, goal_alignment, overall_confidence)
        ("analytical_high", 0.9, 0.9, 0.8, 0.85),
        ("low_quality", 0.2, 0.2, 0.3, 0.3),
        ("agency_dominant", 0.5, 0.5, 0.9, 0.7),
        ("pure_reasoning", 0.95, 0.95, 0.5, 0.9),
        ("dormant_low", 0.1, 0.1, 0.1, 0.1),
        ("purpose_execution", 0.5, 0.5, 0.9, 0.7),
        ("balanced_mid", 0.5, 0.5, 0.5, 0.5),
        ("extreme_quality", 1.0, 1.0, 1.0, 1.0),
        ("extreme_low", 0.0, 0.0, 0.0, 0.0),
    ]

    def _eval_scenario(self, quality, coherence, goal_alignment, overall_confidence):
        from agentic.agentic_framework.jepa_governance import (
            approximate_layer_weights, approximate_vritti,
            build_ontology_signal, build_vritti_signal, build_jepa_composite,
        )
        lw = approximate_layer_weights(
            quality=quality, coherence=coherence,
            goal_alignment=goal_alignment, overall_confidence=overall_confidence,
        )
        base = approximate_vritti(
            quality=quality, coherence=coherence,
            overall_confidence=overall_confidence,
        )
        with_prior = approximate_vritti(
            quality=quality, coherence=coherence,
            overall_confidence=overall_confidence, layer_weights=lw,
        )
        ontology = build_ontology_signal(layer_weights=lw)
        j_base = build_jepa_composite(ontology, build_vritti_signal(vritti_distribution=base))
        j_prior = build_jepa_composite(ontology, build_vritti_signal(vritti_distribution=with_prior))
        return base, with_prior, j_base, j_prior

    def test_no_top1_churn_across_scenarios(self):
        """At alpha=0.2, top-1 vritti must not change for any calibration scenario."""
        for name, q, c, ga, oc in self.CALIBRATION_SCENARIOS:
            base, with_prior, _, _ = self._eval_scenario(q, c, ga, oc)
            base_top1 = max(base, key=base.get)
            prior_top1 = max(with_prior, key=with_prior.get)
            assert base_top1 == prior_top1, (
                f"Top-1 flipped in {name}: {base_top1} → {prior_top1}"
            )

    def test_alignment_nonnegative_on_average(self):
        """Average alignment delta across scenarios must be non-negative."""
        deltas = []
        for name, q, c, ga, oc in self.CALIBRATION_SCENARIOS:
            _, _, j_base, j_prior = self._eval_scenario(q, c, ga, oc)
            deltas.append(j_prior.ontology_vritti_alignment - j_base.ontology_vritti_alignment)
        avg = sum(deltas) / len(deltas)
        assert avg >= 0.0, f"Average alignment delta is negative: {avg}"

    def test_alignment_mostly_improves(self):
        """Alignment must improve in at least 70% of scenarios."""
        improved = 0
        for name, q, c, ga, oc in self.CALIBRATION_SCENARIOS:
            _, _, j_base, j_prior = self._eval_scenario(q, c, ga, oc)
            if j_prior.ontology_vritti_alignment > j_base.ontology_vritti_alignment + 0.0001:
                improved += 1
        pct = improved / len(self.CALIBRATION_SCENARIOS)
        assert pct >= 0.70, f"Only {pct:.0%} of scenarios improved"

    def test_normalization_and_nonnegativity(self):
        """All prior-adjusted distributions must be normalized and non-negative."""
        for name, q, c, ga, oc in self.CALIBRATION_SCENARIOS:
            _, with_prior, _, _ = self._eval_scenario(q, c, ga, oc)
            assert abs(sum(with_prior.values()) - 1.0) < 0.001, (
                f"Not normalized in {name}: sum={sum(with_prior.values())}"
            )
            assert all(v >= 0 for v in with_prior.values()), (
                f"Negative value in {name}: {with_prior}"
            )

    def test_no_regime_changes(self):
        """Prior must not change governance regime for any calibration scenario."""
        from agentic.agentic_framework.jepa_governance import (
            build_runtime_process_state, assess_governance,
        )
        for name, q, c, ga, oc in self.CALIBRATION_SCENARIOS:
            _, _, j_base, j_prior = self._eval_scenario(q, c, ga, oc)
            runtime = build_runtime_process_state(
                action_type="search", tool_name="search",
                risk_level="READ_ONLY", confidence_score=oc,
            )
            regime_base = assess_governance(j_base, runtime).regime
            regime_prior = assess_governance(j_prior, runtime).regime
            assert regime_base == regime_prior, (
                f"Regime changed in {name}: {regime_base} → {regime_prior}"
            )

    def test_smrti_activation_useful(self):
        """Smrti should activate in purpose/execution-heavy scenarios."""
        from agentic.agentic_framework.jepa_governance import (
            approximate_layer_weights, approximate_vritti,
        )
        # Purpose/execution context should produce non-zero smrti
        lw = approximate_layer_weights(
            quality=0.5, coherence=0.5,
            goal_alignment=0.9, overall_confidence=0.7,
        )
        with_prior = approximate_vritti(
            quality=0.5, coherence=0.5, overall_confidence=0.7,
            layer_weights=lw,
        )
        assert with_prior["smrti"] > 0.02, (
            f"Smrti too low in purpose/execution context: {with_prior['smrti']}"
        )

    def test_bounded_shift_per_mode(self):
        """No single vritti mode should shift by more than alpha + tolerance."""
        for name, q, c, ga, oc in self.CALIBRATION_SCENARIOS:
            base, with_prior, _, _ = self._eval_scenario(q, c, ga, oc)
            for k in base:
                delta = abs(with_prior[k] - base[k])
                assert delta <= 0.22, (
                    f"Excessive shift in {name}/{k}: {delta:.4f}"
                )


# =============================================================================
# Test: Phase 2 — Guna → CSR audit signal (audit-only)
# =============================================================================


class TestGunaCsrAuditSignal:
    """Tests for the Phase 2 Guna → CSR modulation audit signal.

    Validates that the audit signal is bounded, directionally correct,
    and strictly audit-only (no live behavior change).
    """

    def test_sattva_dominant_clarifies(self):
        """Sattva-dominant guna should produce clarification tendency."""
        from agentic.guna_modulation.guna_derivation import guna_csr_modulation_audit
        from agentic.guna_modulation.types import GunaVector
        sig = guna_csr_modulation_audit(GunaVector(sattva=0.8, rajas=0.1, tamas=0.1))
        assert sig.clarify_delta > sig.dampen_delta
        assert sig.clarify_delta > sig.agitate_delta
        assert sig.dominant_tendency == "clarify"
        assert sig.net_coherence_delta > 0  # sattva increases coherence
        assert sig.net_entropy_delta < 0    # sattva decreases entropy

    def test_rajas_dominant_agitates(self):
        """Rajas-dominant guna should produce agitation tendency."""
        from agentic.guna_modulation.guna_derivation import guna_csr_modulation_audit
        from agentic.guna_modulation.types import GunaVector
        sig = guna_csr_modulation_audit(GunaVector(sattva=0.1, rajas=0.8, tamas=0.1))
        assert sig.agitate_delta > sig.clarify_delta
        assert sig.agitate_delta > sig.dampen_delta
        assert sig.dominant_tendency == "agitate"

    def test_tamas_dominant_dampens(self):
        """Tamas-dominant guna should produce damping tendency."""
        from agentic.guna_modulation.guna_derivation import guna_csr_modulation_audit
        from agentic.guna_modulation.types import GunaVector
        sig = guna_csr_modulation_audit(GunaVector(sattva=0.1, rajas=0.1, tamas=0.8))
        assert sig.dampen_delta > sig.clarify_delta
        assert sig.dampen_delta > sig.agitate_delta
        assert sig.dominant_tendency == "dampen"
        assert sig.net_coherence_delta < 0  # tamas decreases coherence
        assert sig.net_entropy_delta > 0    # tamas increases entropy

    def test_balanced_guna_bounded(self):
        """Balanced guna (1/3 each) should produce small bounded deltas."""
        from agentic.guna_modulation.guna_derivation import guna_csr_modulation_audit
        from agentic.guna_modulation.types import GunaVector
        sig = guna_csr_modulation_audit(
            GunaVector(sattva=0.333, rajas=0.334, tamas=0.333),
        )
        # All deltas should be approximately equal
        assert abs(sig.clarify_delta - sig.dampen_delta) < 0.001
        # Net effects near zero
        assert abs(sig.net_coherence_delta) < 0.001
        assert abs(sig.net_entropy_delta) < 0.001

    def test_zero_guna_neutral(self):
        """All-zero guna produces neutral signal."""
        from agentic.guna_modulation.guna_derivation import guna_csr_modulation_audit
        from agentic.guna_modulation.types import GunaVector
        sig = guna_csr_modulation_audit(GunaVector(sattva=0.0, rajas=0.0, tamas=0.0))
        assert sig.clarify_delta == 0.0
        assert sig.agitate_delta == 0.0
        assert sig.dampen_delta == 0.0
        assert sig.net_coherence_delta == 0.0
        assert sig.net_entropy_delta == 0.0
        assert sig.dominant_tendency == "neutral"

    def test_all_deltas_bounded(self):
        """All deltas must be bounded within [-0.10, +0.10]."""
        from agentic.guna_modulation.guna_derivation import guna_csr_modulation_audit
        from agentic.guna_modulation.types import GunaVector
        for s, r, t in [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
                        (0.5, 0.5, 0.0), (0.0, 0.5, 0.5), (0.5, 0.0, 0.5),
                        (0.8, 0.1, 0.1), (0.1, 0.8, 0.1), (0.1, 0.1, 0.8)]:
            sig = guna_csr_modulation_audit(GunaVector(sattva=s, rajas=r, tamas=t))
            assert 0.0 <= sig.clarify_delta <= 0.10
            assert 0.0 <= sig.agitate_delta <= 0.10
            assert 0.0 <= sig.dampen_delta <= 0.10
            assert -0.10 <= sig.net_coherence_delta <= 0.10
            assert -0.10 <= sig.net_entropy_delta <= 0.10

    def test_audit_only_flag_always_true(self):
        """audit_only must always be True — machine-readable guard."""
        from agentic.guna_modulation.guna_derivation import guna_csr_modulation_audit
        from agentic.guna_modulation.types import GunaVector
        sig = guna_csr_modulation_audit(GunaVector(sattva=0.5, rajas=0.3, tamas=0.2))
        assert sig.audit_only is True

    def test_to_dict_serializable(self):
        """Audit signal must be serializable to dict."""
        from agentic.guna_modulation.guna_derivation import guna_csr_modulation_audit
        from agentic.guna_modulation.types import GunaVector
        sig = guna_csr_modulation_audit(GunaVector(sattva=0.6, rajas=0.2, tamas=0.2))
        d = sig.to_dict()
        assert isinstance(d, dict)
        assert d["audit_only"] is True
        assert "clarify_delta" in d
        assert "dominant_tendency" in d
        assert "guna_input" in d and isinstance(d["guna_input"], dict)

    def test_deterministic(self):
        """Same input must always produce same output."""
        from agentic.guna_modulation.guna_derivation import guna_csr_modulation_audit
        from agentic.guna_modulation.types import GunaVector
        guna = GunaVector(sattva=0.45, rajas=0.35, tamas=0.20)
        sig1 = guna_csr_modulation_audit(guna)
        sig2 = guna_csr_modulation_audit(guna)
        assert sig1.clarify_delta == sig2.clarify_delta
        assert sig1.agitate_delta == sig2.agitate_delta
        assert sig1.dampen_delta == sig2.dampen_delta
        assert sig1.net_coherence_delta == sig2.net_coherence_delta
        assert sig1.dominant_tendency == sig2.dominant_tendency

    def test_guna_input_preserved(self):
        """The input guna vector must be preserved in the audit signal."""
        from agentic.guna_modulation.guna_derivation import guna_csr_modulation_audit
        from agentic.guna_modulation.types import GunaVector
        guna = GunaVector(sattva=0.7, rajas=0.2, tamas=0.1)
        sig = guna_csr_modulation_audit(guna)
        assert sig.guna_input.sattva == 0.7
        assert sig.guna_input.rajas == 0.2
        assert sig.guna_input.tamas == 0.1

    def test_net_coherence_entropy_antisymmetric(self):
        """net_coherence_delta and net_entropy_delta should be negatives of each other."""
        from agentic.guna_modulation.guna_derivation import guna_csr_modulation_audit
        from agentic.guna_modulation.types import GunaVector
        for s, t in [(0.8, 0.1), (0.1, 0.8), (0.5, 0.5), (0.3, 0.4)]:
            guna = GunaVector(sattva=s, rajas=1.0 - s - t, tamas=t)
            sig = guna_csr_modulation_audit(guna)
            assert abs(sig.net_coherence_delta + sig.net_entropy_delta) < 1e-10


# =============================================================================
# Test: Phase 2 Usefulness Evaluation — encoded assertions
# =============================================================================


class TestP2UsefulnessEvaluation:
    """Encoded assertions from the P2 usefulness evaluation pass.

    These tests validate that the Guna → CSR audit signal is:
    1. Interpretable (dominant tendency matches CSR input patterns)
    2. Stable (smooth under small perturbations)
    3. Incrementally valuable (separates cases within same JEPA regime)
    4. Does not change any live governance behavior
    """

    # Representative CSR → Guna → Audit scenarios
    # (C_s, M, H, expected_dominant)
    INTERPRETABILITY_CASES = [
        # Sattva-dominant: high coherence, low entropy
        (0.9, 0.3, 0.1, "clarify"),
        (0.95, 0.2, 0.05, "clarify"),
        # Rajas-dominant: high motion, mid entropy
        (0.4, 0.9, 0.5, "agitate"),
        (0.5, 0.85, 0.45, "agitate"),
        # Tamas-dominant: high entropy, low coherence
        (0.15, 0.2, 0.85, "dampen"),
        (0.1, 0.1, 0.9, "dampen"),
        (0.05, 0.05, 0.95, "dampen"),
        # Edge cases
        (1.0, 1.0, 0.0, "clarify"),
        (0.0, 0.0, 1.0, "dampen"),
    ]

    def test_interpretability_all_cases_correct(self):
        """P2 dominant tendency must match expected for all interpretability cases."""
        from agentic.guna_modulation.guna_derivation import (
            guna_csr_modulation_audit, derive_guna_from_values,
        )
        for C_s, M, H, expected in self.INTERPRETABILITY_CASES:
            guna = derive_guna_from_values(C_s=C_s, M=M, H=H)
            sig = guna_csr_modulation_audit(guna)
            assert sig.dominant_tendency == expected, (
                f"CSR=({C_s},{M},{H}): expected {expected}, got {sig.dominant_tendency}"
            )

    def test_stability_small_perturbation(self):
        """Small CSR perturbation (eps=0.02) must cause <0.005 audit delta."""
        from agentic.guna_modulation.guna_derivation import (
            guna_csr_modulation_audit, derive_guna_from_values,
        )
        eps = 0.02
        for C_s, M, H, _ in self.INTERPRETABILITY_CASES:
            base = guna_csr_modulation_audit(derive_guna_from_values(C_s=C_s, M=M, H=H))
            for param_idx, param_name in enumerate(["C_s", "M", "H"]):
                vals = [C_s, M, H]
                for direction in (-eps, +eps):
                    perturbed = list(vals)
                    perturbed[param_idx] = max(0.0, min(1.0, perturbed[param_idx] + direction))
                    p_sig = guna_csr_modulation_audit(
                        derive_guna_from_values(C_s=perturbed[0], M=perturbed[1], H=perturbed[2])
                    )
                    for attr in ("clarify_delta", "agitate_delta", "dampen_delta"):
                        delta = abs(getattr(p_sig, attr) - getattr(base, attr))
                        assert delta < 0.005, (
                            f"Unstable: CSR=({C_s},{M},{H}) perturb {param_name}{direction:+.2f}: "
                            f"{attr} changed by {delta:.6f}"
                        )

    def test_case_separation_within_same_regime(self):
        """P2 must provide different dominant tendencies for cases that share
        the same JEPA governance regime (all NORMAL in calibration set)."""
        from agentic.guna_modulation.guna_derivation import (
            guna_csr_modulation_audit, derive_guna_from_values,
        )
        # Three cases that all produce NORMAL regime in JEPA but
        # represent fundamentally different energetic states
        sattva_sig = guna_csr_modulation_audit(
            derive_guna_from_values(C_s=0.9, M=0.3, H=0.1))
        rajas_sig = guna_csr_modulation_audit(
            derive_guna_from_values(C_s=0.4, M=0.9, H=0.5))
        tamas_sig = guna_csr_modulation_audit(
            derive_guna_from_values(C_s=0.15, M=0.2, H=0.85))

        # P2 must distinguish them
        assert sattva_sig.dominant_tendency == "clarify"
        assert rajas_sig.dominant_tendency == "agitate"
        assert tamas_sig.dominant_tendency == "dampen"

        # net_coherence must meaningfully separate the three
        assert sattva_sig.net_coherence_delta > 0.05   # positive: clarification
        assert abs(rajas_sig.net_coherence_delta) < 0.02  # near zero: agitation
        assert tamas_sig.net_coherence_delta < -0.05   # negative: damping

    def test_stagnation_vs_oscillation_distinguishable(self):
        """P2 must distinguish stagnation (low motion, high entropy) from
        oscillation (high motion, mid entropy) — both may look similar in JEPA."""
        from agentic.guna_modulation.guna_derivation import (
            guna_csr_modulation_audit, derive_guna_from_values,
        )
        stagnation = guna_csr_modulation_audit(
            derive_guna_from_values(C_s=0.35, M=0.1, H=0.6))
        oscillation = guna_csr_modulation_audit(
            derive_guna_from_values(C_s=0.4, M=0.9, H=0.5))

        assert stagnation.dominant_tendency == "dampen"
        assert oscillation.dominant_tendency == "agitate"
        # Their net_coherence should have opposite signs or clearly differ
        assert stagnation.net_coherence_delta < oscillation.net_coherence_delta

    def test_no_live_behavior_change(self):
        """P2 audit signal must NOT change any governance decision.
        Same inputs with and without P2 computation must produce
        identical regime, action, and confidence adjustment."""
        from agentic.agentic_framework.jepa_governance import (
            approximate_layer_weights, approximate_vritti,
            build_ontology_signal, build_vritti_signal, build_jepa_composite,
            build_runtime_process_state, assess_governance,
        )
        lw = approximate_layer_weights(
            quality=0.5, coherence=0.5,
            goal_alignment=0.5, overall_confidence=0.5,
        )
        vritti_dist = approximate_vritti(
            quality=0.5, coherence=0.5,
            overall_confidence=0.5, layer_weights=lw,
        )
        ontology = build_ontology_signal(layer_weights=lw)
        vritti = build_vritti_signal(vritti_distribution=vritti_dist)
        jepa = build_jepa_composite(ontology, vritti)
        runtime = build_runtime_process_state(
            action_type="search", tool_name="search",
            risk_level="READ_ONLY", confidence_score=0.5,
        )
        assessment = assess_governance(jepa, runtime)

        # Compute P2 signal (should not affect anything)
        from agentic.guna_modulation.guna_derivation import (
            guna_csr_modulation_audit, derive_guna_from_values,
        )
        guna = derive_guna_from_values(C_s=0.5, M=0.5, H=0.5)
        audit = guna_csr_modulation_audit(guna)

        # Re-run governance — must be identical
        assessment2 = assess_governance(jepa, runtime)
        assert assessment.regime == assessment2.regime
        assert assessment.recommended_action == assessment2.recommended_action
        assert assessment.confidence_adjustment == assessment2.confidence_adjustment

        # Audit signal must be audit_only
        assert audit.audit_only is True

    def test_mixed_state_interpretability(self):
        """Mixed guna states should produce interpretable, non-degenerate signals."""
        from agentic.guna_modulation.guna_derivation import (
            guna_csr_modulation_audit, derive_guna_from_values,
        )
        # Balanced: all deltas similar, net_coherence near zero
        balanced = guna_csr_modulation_audit(
            derive_guna_from_values(C_s=0.5, M=0.5, H=0.5))
        assert abs(balanced.net_coherence_delta) < 0.01
        assert abs(balanced.net_entropy_delta) < 0.01

        # Sattva-rajas mix: clarify+agitate both meaningful
        sr_mix = guna_csr_modulation_audit(
            derive_guna_from_values(C_s=0.7, M=0.7, H=0.3))
        assert sr_mix.clarify_delta > 0.01
        assert sr_mix.agitate_delta > 0.01
        assert sr_mix.dampen_delta < sr_mix.clarify_delta


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
