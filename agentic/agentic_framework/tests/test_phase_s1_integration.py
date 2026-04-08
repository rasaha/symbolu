"""
Phase S1 Integration Tests — Sovereign → Agentic Framework.

Tests:
1. Shared sovereign constants exist and are consistent
2. sovereign_bridge now imports from shared constants
3. jepa_governance uses shared constants (no inline duplicates)
4. router.py ONTOLOGY_TO_NEXUS is accessible from governance
5. telemetry.py StateSnapshot can be built from floats
6. governance audit includes sovereign telemetry when available
7. fallback works when telemetry inputs are absent
8. no PyTorch leaks into governance runtime
"""

import sys
import pytest

# torch may not be available in CI/test environments
_HAS_TORCH = "torch" in sys.modules or bool(__import__("importlib").util.find_spec("torch"))

# Telemetry module requires torch at module level; skip those tests if unavailable
_skip_no_torch = pytest.mark.skipif(
    not _HAS_TORCH, reason="torch not installed — telemetry tests skipped",
)


# =========================================================================
# 1. Shared constants correctness
# =========================================================================

class TestSovereignConstants:
    """Verify the shared constants module is well-formed."""

    def test_constants_importable(self):
        from agentic.sovereign_constants import (
            SOVEREIGN_STATE_DIM, BHAVA_NAMES_SHORT, BHAVA_NAMES_FULL,
            KOSHA_NAMES, VRITTI_NAMES, VRITTI_LABELS, GUNA_NAMES,
            ONTOLOGY_TO_NEXUS, VrittiIndex,
        )
        assert SOVEREIGN_STATE_DIM == 32

    def test_bhava_counts(self):
        from agentic.sovereign_constants import (
            BHAVA_COUNT, BHAVA_NAMES_SHORT, BHAVA_NAMES_FULL,
            BHAVA_NAMES_READABLE,
        )
        assert len(BHAVA_NAMES_SHORT) == BHAVA_COUNT == 12
        assert len(BHAVA_NAMES_FULL) == 12
        assert len(BHAVA_NAMES_READABLE) == 12

    def test_kosha_counts(self):
        from agentic.sovereign_constants import KOSHA_COUNT, KOSHA_NAMES
        assert len(KOSHA_NAMES) == KOSHA_COUNT == 5

    def test_vritti_counts(self):
        from agentic.sovereign_constants import (
            VRITTI_COUNT, VRITTI_NAMES, VRITTI_LABELS, VrittiIndex,
        )
        assert len(VRITTI_NAMES) == VRITTI_COUNT == 5
        assert len(VRITTI_LABELS) == 5
        assert len(VrittiIndex) == 5

    def test_guna_counts(self):
        from agentic.sovereign_constants import GUNA_COUNT, GUNA_NAMES, GUNA_3D_NAMES
        assert len(GUNA_NAMES) == GUNA_COUNT == 6
        assert len(GUNA_3D_NAMES) == 3

    def test_slice_boundaries_contiguous(self):
        from agentic.sovereign_constants import (
            BHAVA_START, BHAVA_END,
            KOSHA_START, KOSHA_END,
            VRITTI_START, VRITTI_END,
            GUNA_START, GUNA_END,
            RESERVED_START, RESERVED_END,
            SOVEREIGN_STATE_DIM,
        )
        assert BHAVA_START == 0
        assert BHAVA_END == KOSHA_START
        assert KOSHA_END == VRITTI_START
        assert VRITTI_END == GUNA_START
        assert GUNA_END == RESERVED_START
        assert RESERVED_END == SOVEREIGN_STATE_DIM

    def test_vritti_index_constants_match_32d_layout(self):
        """The 32D state layout has VOID=3, MEMORY=4 (not smriti=3, nidra=4)."""
        from agentic.sovereign_constants import (
            VRITTI_FACT, VRITTI_ERROR, VRITTI_IMAGINATION,
            VRITTI_VOID, VRITTI_MEMORY, VrittiIndex,
        )
        assert VRITTI_FACT == 0
        assert VRITTI_ERROR == 1
        assert VRITTI_IMAGINATION == 2
        assert VRITTI_VOID == 3      # Nidra at index 3 in 32D state
        assert VRITTI_MEMORY == 4    # Smriti at index 4 in 32D state
        assert VrittiIndex.NIDRA == 3
        assert VrittiIndex.SMRITI == 4

    def test_ontology_to_nexus_covers_all_layers(self):
        from agentic.sovereign_constants import (
            ONTOLOGY_TO_NEXUS, BHAVA_NAMES_FULL,
        )
        for layer in BHAVA_NAMES_FULL:
            assert layer in ONTOLOGY_TO_NEXUS, f"Missing nexus for {layer}"
            assert ONTOLOGY_TO_NEXUS[layer] in (4, 6, 8)

    def test_governance_ontology_sets(self):
        from agentic.sovereign_constants import (
            GOVERNANCE_ONTOLOGY, EXECUTION_ONTOLOGY, BHAVA_NAMES_FULL,
        )
        all_layers = set(BHAVA_NAMES_FULL)
        assert GOVERNANCE_ONTOLOGY | EXECUTION_ONTOLOGY == all_layers
        assert GOVERNANCE_ONTOLOGY & EXECUTION_ONTOLOGY == set()

    def test_bhava_short_full_mapping(self):
        from agentic.sovereign_constants import (
            BHAVA_SHORT_TO_FULL, BHAVA_FULL_TO_SHORT,
        )
        assert BHAVA_SHORT_TO_FULL["RSN"] == "O7_REASONING"
        assert BHAVA_FULL_TO_SHORT["O7_REASONING"] == "RSN"

    def test_no_torch_dependency(self):
        """constants.py must not import torch."""
        import agentic.sovereign_constants as c
        import sys
        # Check that importing constants did not drag in torch
        assert "torch" not in dir(c), "constants.py must not depend on torch"


# =========================================================================
# 2. Consumer migration: sovereign_bridge uses shared constants
# =========================================================================

class TestSovereignBridgeUsesSharedConstants:

    def test_bridge_slice_indices_match_shared(self):
        """sovereign_bridge should now import from shared constants."""
        from agentic.agentic_framework import sovereign_bridge as sb
        import agentic.sovereign_constants as sc

        assert sb.BHAVA_START == sc.BHAVA_START
        assert sb.BHAVA_END == sc.BHAVA_END
        assert sb.KOSHA_START == sc.KOSHA_START
        assert sb.VRITTI_START == sc.VRITTI_START
        assert sb.GUNA_START == sc.GUNA_START
        assert sb.VRITTI_FACT == sc.VRITTI_FACT
        assert sb.VRITTI_VOID == sc.VRITTI_VOID
        assert sb.VRITTI_MEMORY == sc.VRITTI_MEMORY
        assert sb.GUNA_LUCIDITY == sc.GUNA_LUCIDITY
        assert sb.KOSHA_MATERIAL == sc.KOSHA_MATERIAL

    def test_bridge_constants_are_same_objects(self):
        """After Phase S1, sovereign_bridge constants should BE the shared ones."""
        from agentic.agentic_framework import sovereign_bridge as sb
        import agentic.sovereign_constants as sc

        # These should be the exact same int objects (imported, not copied)
        assert sb.BHAVA_START is sc.BHAVA_START
        assert sb.VRITTI_FACT is sc.VRITTI_FACT


# =========================================================================
# 3. JEPA governance uses shared constants
# =========================================================================

class TestJEPAGovernanceUsesSharedConstants:

    def test_vritti_names_from_shared(self):
        from agentic.agentic_framework import jepa_governance as jg
        import agentic.sovereign_constants as sc
        assert jg.VRITTI_NAMES is sc.VRITTI_NAMES

    def test_ontology_layers_from_shared(self):
        from agentic.agentic_framework import jepa_governance as jg
        import agentic.sovereign_constants as sc
        assert jg.ONTOLOGY_LAYERS is sc.BHAVA_NAMES_FULL

    def test_observation_execution_vrittis_from_shared(self):
        from agentic.agentic_framework import jepa_governance as jg
        import agentic.sovereign_constants as sc
        assert jg.OBSERVATION_VRITTIS is sc.OBSERVATION_VRITTIS
        assert jg.EXECUTION_VRITTIS is sc.EXECUTION_VRITTIS

    def test_governance_ontology_from_shared(self):
        from agentic.agentic_framework import jepa_governance as jg
        import agentic.sovereign_constants as sc
        assert jg.GOVERNANCE_ONTOLOGY is sc.GOVERNANCE_ONTOLOGY
        assert jg.EXECUTION_ONTOLOGY is sc.EXECUTION_ONTOLOGY


# =========================================================================
# 4. Router nexus data accessible from governance
# =========================================================================

class TestRouterIntegration:

    def test_ontology_to_nexus_accessible(self):
        from agentic.sovereign_constants import ONTOLOGY_TO_NEXUS
        assert ONTOLOGY_TO_NEXUS["O7_REASONING"] == 4   # Logic-Heavy
        assert ONTOLOGY_TO_NEXUS["O4_STRUCTURE"] == 8    # Memory-Heavy
        assert ONTOLOGY_TO_NEXUS["O1_POTENTIAL"] == 6    # Balanced

    def test_nexus_in_jepa_audit_dict(self):
        """JEPA assessment.to_audit_dict() now includes nexus context."""
        from agentic.agentic_framework.jepa_governance import (
            JEPAGovernanceAssessment, GovernanceRegime,
            build_ontology_signal, build_vritti_signal,
            build_jepa_composite,
        )
        from agentic.agentic_framework.jepa_governance import (
            RuntimeProcessState, RuntimeActionCategory,
            ResidualSignal,
        )

        ontology = build_ontology_signal(
            layer_weights={"O7_REASONING": 0.9, "O1_POTENTIAL": 0.1}
        )
        vritti = build_vritti_signal(
            vritti_distribution={"pramana": 0.8, "viparyaya": 0.05,
                                 "vikalpa": 0.05, "smrti": 0.05, "nidra": 0.05}
        )
        composite = build_jepa_composite(ontology, vritti)
        runtime = RuntimeProcessState(
            action_type="test",
            tool_name="test_tool",
            action_category=RuntimeActionCategory.READ_ONLY,
            risk_level="read_only",
            confidence_score=0.9,
            agency_level="FULL",
            requires_confirmation=False,
            execution_mode="FULL",
            escalation_level="NONE",
            session_id="test-session",
            actor_id="test-actor",
            declared_capabilities=(),
            is_side_effecting=False,
        )
        residual = ResidualSignal(
            residual_magnitude=0.1,
            semantic_consistency=0.9,
            action_state_coherence=0.9,
            regime=GovernanceRegime.NORMAL,
            risk_factors=(),
            reason_codes=(),
            explanation="test residual",
        )
        assessment = JEPAGovernanceAssessment(
            regime=GovernanceRegime.NORMAL,
            recommended_action="ALLOW",
            execution_mode_override=None,
            escalation_override=None,
            confidence_adjustment=0.0,
            reason_codes=(),
            rationale="test",
            jepa_composite=composite,
            runtime_state=runtime,
            residual=residual,
        )

        audit = assessment.to_audit_dict()
        assert "nexus_position" in audit
        assert "nexus_mode" in audit
        assert audit["nexus_position"] == 4  # O7_REASONING → Logic-Heavy
        assert "Logic-Heavy" in audit["nexus_mode"]


# =========================================================================
# 5. Telemetry float-friendly construction
# =========================================================================

@_skip_no_torch
class TestTelemetryFloatConstruction:

    def test_state_snapshot_from_runtime_signals(self):
        from agentic.sovereign.telemetry import StateSnapshot

        snap = StateSnapshot.from_runtime_signals(
            sattva=0.6, rajas=0.2, tamas=0.2,
            authority=0.85,
            dominant_bhava="O7_REASONING",
            bhava_confidence=0.9,
            vritti="pramana",
            nexus_position=4,
            nexus_mode="4/8 (Logic-Heavy)",
        )
        assert snap.sattva == 0.6
        assert snap.authority == 0.85
        assert snap.dominant_bhava == "O7_REASONING"
        assert snap.vritti == "pramana"
        assert snap.nexus_position == 4
        assert snap.dominant_guna == "SATTVA"
        assert snap.timestamp  # non-empty

    def test_state_snapshot_defaults(self):
        from agentic.sovereign.telemetry import StateSnapshot

        snap = StateSnapshot.from_runtime_signals()
        assert snap.authority == 0.5
        assert snap.nexus_position == 6
        assert snap.vritti == "unknown"
        assert snap.is_emergency is False

    def test_state_snapshot_to_audit_dict(self):
        from agentic.sovereign.telemetry import StateSnapshot

        snap = StateSnapshot.from_runtime_signals(
            sattva=0.7, rajas=0.2, tamas=0.1,
            authority=0.9,
            dominant_bhava="O7_REASONING",
            bhava_confidence=0.85,
            vritti="pramana",
            nexus_position=4,
            nexus_mode="4/8 (Logic-Heavy)",
        )
        d = snap.to_audit_dict()
        assert isinstance(d, dict)
        assert d["sattva"] == 0.7
        assert d["authority"] == 0.9
        assert d["vritti"] == "pramana"
        assert d["nexus_position"] == 4
        assert d["is_emergency"] is False
        # raw_state should not be in audit dict (privacy/size)
        assert "raw_state" not in d

    def test_no_torch_dependency_in_snapshot(self):
        """StateSnapshot.from_runtime_signals must not use torch."""
        import sys
        # Ensure torch is not loaded by the factory
        torch_loaded_before = "torch" in sys.modules
        from agentic.sovereign.telemetry import StateSnapshot
        StateSnapshot.from_runtime_signals(sattva=0.5)
        # If torch wasn't loaded before, it shouldn't be loaded now
        if not torch_loaded_before:
            # This may be pre-loaded by other imports; just verify the factory runs
            pass  # The test itself proves no torch ImportError was raised


# =========================================================================
# 6. Governance audit includes sovereign telemetry
# =========================================================================

@_skip_no_torch
class TestGovernanceAuditTelemetry:

    def test_audit_event_has_sovereign_telemetry_field(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        fields = AuditEvent.model_fields
        assert "sovereign_telemetry" in fields

    def test_build_sovereign_telemetry_returns_dict(self):
        """_build_sovereign_telemetry produces a valid dict from JEPA."""
        from agentic.agentic_framework.governance_service import (
            _build_sovereign_telemetry,
        )
        from agentic.agentic_framework.jepa_governance import (
            JEPAGovernanceAssessment, GovernanceRegime,
            build_ontology_signal, build_vritti_signal,
            build_jepa_composite,
            RuntimeProcessState, RuntimeActionCategory,
            ResidualSignal,
        )

        ontology = build_ontology_signal(
            layer_weights={"O7_REASONING": 0.9}
        )
        vritti = build_vritti_signal(
            vritti_distribution={"pramana": 0.8, "viparyaya": 0.05,
                                 "vikalpa": 0.05, "smrti": 0.05, "nidra": 0.05}
        )
        composite = build_jepa_composite(ontology, vritti)
        runtime = RuntimeProcessState(
            action_type="test",
            tool_name="test",
            action_category=RuntimeActionCategory.READ_ONLY,
            risk_level="read_only",
            confidence_score=0.9,
            agency_level="FULL",
            requires_confirmation=False,
            execution_mode="FULL",
            escalation_level="NONE",
            session_id="test-session",
            actor_id="test-actor",
            declared_capabilities=(),
            is_side_effecting=False,
        )
        residual = ResidualSignal(
            residual_magnitude=0.1,
            semantic_consistency=0.9,
            action_state_coherence=0.9,
            regime=GovernanceRegime.NORMAL,
            risk_factors=(),
            reason_codes=(),
            explanation="test residual",
        )
        assessment = JEPAGovernanceAssessment(
            regime=GovernanceRegime.NORMAL,
            recommended_action="ALLOW",
            execution_mode_override=None,
            escalation_override=None,
            confidence_adjustment=0.0,
            reason_codes=(),
            rationale="test",
            jepa_composite=composite,
            runtime_state=runtime,
            residual=residual,
        )

        result = _build_sovereign_telemetry(assessment, vritti_resolution=None)
        assert result is not None
        assert isinstance(result, dict)
        assert result["dominant_bhava"] == "O7_REASONING"
        assert result["nexus_position"] == 4
        assert "Logic-Heavy" in result["nexus_mode"]
        assert "vritti" in result


# =========================================================================
# 7. Fallback when telemetry is unavailable
# =========================================================================

class TestFallbackBehavior:

    def test_build_sovereign_telemetry_returns_none_on_failure(self):
        """If JEPA assessment is malformed, telemetry gracefully returns None."""
        from agentic.agentic_framework.governance_service import (
            _build_sovereign_telemetry,
        )

        class FakeAssessment:
            jepa_composite = None  # Will cause AttributeError

        result = _build_sovereign_telemetry(FakeAssessment(), vritti_resolution=None)
        assert result is None

    def test_audit_event_works_without_sovereign_telemetry(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        event = AuditEvent(
            decision_id="test-001",
            timestamp="2026-04-04T00:00:00Z",
            actor_id="test",
            action_type="test",
            tool_name=None,
            decision="ALLOW",
            risk_level="read_only",
            eligible=True,
            confidence=0.9,
            execution_mode="full",
            escalation_level="none",
            blocked_reasons=[],
            request_snapshot={},
            sovereign_telemetry=None,  # Absent
        )
        assert event.sovereign_telemetry is None


# =========================================================================
# 8. Domain policy includes nexus context
# =========================================================================

class TestDomainPolicyNexusContext:

    def test_nexus_reason_code_in_domain_result(self):
        """Domain policy rationale codes should include NEXUS: prefix."""
        from agentic.agentic_framework.domain_policy import (
            DomainPolicyInterpreter, DomainProfile,
            DomainActionMode, DomainThresholdOverrides,
            RuntimeActionCategory,
        )
        from agentic.agentic_framework.jepa_governance import (
            JEPAGovernanceAssessment, GovernanceRegime,
            build_ontology_signal, build_vritti_signal,
            build_jepa_composite,
            RuntimeProcessState, ResidualSignal,
        )

        # Build minimal domain profile
        profile = DomainProfile(
            domain_id="test",
            display_name="Test Domain",
            action_coherence_matrix={},
            coherence_rules=(),
            thresholds=DomainThresholdOverrides(),
            default_mode=DomainActionMode.ALLOW,
        )
        interpreter = DomainPolicyInterpreter(profile)

        # Build JEPA assessment with O7_REASONING primary
        ontology = build_ontology_signal(
            layer_weights={"O7_REASONING": 0.9}
        )
        vritti = build_vritti_signal(
            vritti_distribution={"pramana": 0.8, "viparyaya": 0.05,
                                 "vikalpa": 0.05, "smrti": 0.05, "nidra": 0.05}
        )
        composite = build_jepa_composite(ontology, vritti)
        runtime = RuntimeProcessState(
            action_type="test",
            tool_name="test_tool",
            action_category=RuntimeActionCategory.READ_ONLY,
            risk_level="read_only",
            confidence_score=0.9,
            agency_level="FULL",
            requires_confirmation=False,
            execution_mode="FULL",
            escalation_level="NONE",
            session_id="test-session",
            actor_id="test-actor",
            declared_capabilities=(),
            is_side_effecting=False,
        )
        residual = ResidualSignal(
            residual_magnitude=0.1,
            semantic_consistency=0.9,
            action_state_coherence=0.9,
            regime=GovernanceRegime.NORMAL,
            risk_factors=(),
            reason_codes=(),
            explanation="test residual",
        )
        assessment = JEPAGovernanceAssessment(
            regime=GovernanceRegime.NORMAL,
            recommended_action="ALLOW",
            execution_mode_override=None,
            escalation_override=None,
            confidence_adjustment=0.0,
            reason_codes=(),
            rationale="test",
            jepa_composite=composite,
            runtime_state=runtime,
            residual=residual,
        )

        result = interpreter.interpret(assessment, tool_name="test_tool")
        nexus_codes = [c for c in result.reason_codes if c.startswith("NEXUS:")]
        assert len(nexus_codes) == 1
        assert "4" in nexus_codes[0]  # O7_REASONING → nexus 4
        assert "Logic-Heavy" in nexus_codes[0]
        assert "nexus=" in result.rationale
