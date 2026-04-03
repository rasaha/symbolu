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
