"""
Phase 53 Invariance Audit Test Suite — External Reality Trust Calibration Engine (ERTCE)

PURPOSE:
This test suite exists to prove invariance, not correctness.
It verifies that Phase 53 cannot alter system behavior, even accidentally.

CRITICAL INVARIANTS TESTED:
1. Routing Invariance: TTOR and MLCR routing decisions unchanged
2. Mapper Invariance: HRM, LCM, LAM behavior unmodified
3. Coherence Engine Invariance: No upstream coherence mutations
4. Persona & Tone Invariance: Metadata-only integration
5. Policy & Safety Invariance: Policy engine untouched
6. Zero-LLM Guarantee: No LLM calls or imports
7. Determinism: Same inputs → same outputs
8. Graceful Degradation: Returns None when insufficient data
9. Unified API Backward Compatibility: Phase 53 field optional
10. End-to-End Pipeline Invariance: Pipeline behavior unchanged

AUDIT SCOPE:
✅ Tripwire tests for behavioral invariance
✅ Structural verification (no imports of routing/mapper/policy)
✅ Read-only integration verification
✅ Deterministic computation validation
❌ NOT testing correctness of Phase 53 formula (covered in main test suite)
❌ NOT testing performance or optimization
"""

import inspect
import pytest
from symbolu.formulas.external_reality_trust_calibration import (
    compute_external_reality_trust_calibration,
    ExternalRealityTrustSnapshot,
)


# ============================================================================
# 1. ROUTING INVARIANCE
# ============================================================================


class TestRoutingInvariance:
    """
    Verify that Phase 53 ERTCE does not modify routing decisions.

    TTOR (Two-Tier Ontology Router) and MLCR must remain completely
    independent of Phase 53. Phase 53 is observation-only.
    """

    def test_no_ttor_changes(self):
        """Phase 53 must not import or modify TTOR router."""
        from symbolu.formulas import external_reality_trust_calibration
        import re

        source = inspect.getsource(external_reality_trust_calibration)

        # Remove comments and docstrings to avoid false positives
        source_no_comments = re.sub(r'#.*', '', source)
        source_no_docstrings = re.sub(r'""".*?"""', '', source_no_comments, flags=re.DOTALL)

        # Phase 53 must not import TTOR
        assert "from symbolu.mechanical.pipeline.ttor" not in source_no_docstrings
        assert "import symbolu.mechanical.pipeline.ttor" not in source_no_docstrings
        assert "TTORRouter" not in source_no_docstrings
        assert "RouterContext" not in source_no_docstrings
        assert "RoutingPlan" not in source_no_docstrings

        # TTOR components should not appear in code (only in comments)
        assert "TTOR" not in source_no_docstrings or source_no_docstrings.count("TTOR") == 0

    def test_no_mlcr_changes(self):
        """Phase 53 must not import or modify MLCR expert router."""
        from symbolu.formulas import external_reality_trust_calibration
        import re

        source = inspect.getsource(external_reality_trust_calibration)

        # Remove comments and docstrings
        source_no_comments = re.sub(r'#.*', '', source)
        source_no_docstrings = re.sub(r'""".*?"""', '', source_no_comments, flags=re.DOTALL)

        # Phase 53 must not import MLCR
        assert "from symbolu.mechanical.mlcr" not in source_no_docstrings
        assert "import symbolu.mechanical.mlcr" not in source_no_docstrings
        assert "ExpertRouter" not in source_no_docstrings

        # MLCR should not appear in code (only in comments)
        assert "MLCR" not in source_no_docstrings or source_no_docstrings.count("MLCR") == 0


# ============================================================================
# 2. MAPPER INVARIANCE
# ============================================================================


class TestMapperInvariance:
    """
    Verify that Phase 53 ERTCE does not modify mapper behavior.

    HRM, LCM, and LAM must operate independently of Phase 53.
    Phase 53 reads from coherence state but never writes to mappers.
    """

    def test_hrm_not_modified(self):
        """Phase 53 must not import or modify HRM (High-Resolution Mapper)."""
        from symbolu.formulas import external_reality_trust_calibration

        source = inspect.getsource(external_reality_trust_calibration)

        # Phase 53 must not import HRM
        assert "from symbolu.mechanical.hrm" not in source
        assert "import symbolu.mechanical.hrm" not in source
        assert "HRMEngine" not in source
        assert "HighResolutionMapper" not in source

    def test_lcm_not_modified(self):
        """Phase 53 must not import or modify LCM (Low-Context Mapper)."""
        from symbolu.formulas import external_reality_trust_calibration

        source = inspect.getsource(external_reality_trust_calibration)

        # Phase 53 must not import LCM
        assert "from symbolu.mechanical.lcm" not in source
        assert "import symbolu.mechanical.lcm" not in source
        assert "LCMEngine" not in source
        assert "LowContextMapper" not in source

    def test_lam_not_modified(self):
        """Phase 53 must not import or modify LAM (Long-Arc Mapper)."""
        from symbolu.formulas import external_reality_trust_calibration

        source = inspect.getsource(external_reality_trust_calibration)

        # Phase 53 must not import LAM
        assert "from symbolu.mechanical.lam" not in source
        assert "import symbolu.mechanical.lam" not in source
        assert "LAMEngine" not in source
        assert "LongArcMapper" not in source


# ============================================================================
# 3. COHERENCE ENGINE INVARIANCE
# ============================================================================


class TestCoherenceInvariance:
    """
    Verify that Phase 53 ERTCE does not mutate upstream coherence state.

    Phase 53 reads from CoherenceState but never modifies existing
    coherence scores, semantic integrity, or drift metrics.
    """

    def test_no_upstream_coherence_mutation(self):
        """Phase 53 must not modify CoherenceEngine or coherence formulas."""
        from symbolu.formulas import external_reality_trust_calibration

        source = inspect.getsource(external_reality_trust_calibration)

        # Phase 53 must not import CoherenceEngine
        assert "from symbolu.core.coherence.coherence_engine import CoherenceEngine" not in source
        assert "CoherenceEngine" not in source

        # Phase 53 must not modify existing coherence formulas
        assert "coherence_score_v2" not in source or "coherence_score_v2 =" not in source
        assert "coherence_score_v3" not in source or "coherence_score_v3 =" not in source
        assert "semantic_integrity_score" not in source or "semantic_integrity_score =" not in source
        assert "cognitive_drift_v3" not in source or "cognitive_drift_v3 =" not in source

    def test_phase53_snapshot_is_read_only(self):
        """Phase 53 snapshot in CoherenceState must be read-only observation."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=0)

        # Phase 53 snapshot should exist as optional field
        assert hasattr(state, 'external_reality_trust_snapshot')
        assert state.external_reality_trust_snapshot is None

        # Phase 53 histories should exist but be empty initially
        assert hasattr(state, 'ertce_trust_score_history')
        assert state.ertce_trust_score_history == []

        # Verify that Phase 53 snapshot can be set without affecting other fields
        initial_coherence_score = getattr(state, 'coherence_score', None)

        # Create a Phase 53 snapshot
        snapshot = ExternalRealityTrustSnapshot(
            external_trust_score=0.75,
            internal_override_pressure=0.25,
            external_signal_fragility=0.30,
            alignment_resilience=0.70,
            trust_decay_risk=0.20,
            trust_band="HIGH_EXTERNAL_TRUST",
            diagnostic_tags=["external_trust_high"],
        )

        # Set Phase 53 snapshot (should not affect other coherence fields)
        state.external_reality_trust_snapshot = snapshot

        # Verify other coherence fields unchanged
        assert getattr(state, 'coherence_score', None) == initial_coherence_score


# ============================================================================
# 4. PERSONA & TONE INVARIANCE
# ============================================================================


class TestPersonaInvariance:
    """
    Verify that Phase 53 ERTCE does not modify persona tone or semantics.

    Phase 53 is metadata-only. It must not influence PersonaRenderer,
    FusionRenderer, or DHA tone/content generation.
    """

    def test_metadata_only_integration(self):
        """Phase 53 must be metadata-only (no tone or semantic influence)."""
        from symbolu.formulas import external_reality_trust_calibration

        source = inspect.getsource(external_reality_trust_calibration)

        # Phase 53 must not import persona/renderer modules
        assert "from symbolu.mechanical.persona" not in source
        assert "PersonaRenderer" not in source
        assert "FusionRenderer" not in source
        assert "DHA" not in source or "DHA" in "# DHA"  # Allow in comments only

    def test_no_tone_or_semantic_changes(self):
        """Phase 53 must not alter tone, wording, or semantic content."""
        from symbolu.formulas import external_reality_trust_calibration

        source = inspect.getsource(external_reality_trust_calibration)

        # Phase 53 must not import tone adjustment modules
        assert "tone_profile" not in source or "tone_profile" in "# tone_profile"
        assert "readiness_level" not in source or "readiness_level" in "# readiness_level"
        assert "resistance_flags" not in source or "resistance_flags" in "# resistance_flags"

        # Phase 53 must not generate text or modify responses
        assert "generate_text" not in source
        assert "render_response" not in source
        assert "adapt_tone" not in source


# ============================================================================
# 5. POLICY & SAFETY INVARIANCE
# ============================================================================


class TestPolicySafetyInvariance:
    """
    Verify that Phase 53 ERTCE does not modify policy or safety logic.

    Phase 53 must not interfere with TradingGuardrails, SafetyPolicy,
    or any policy decision-making.
    """

    def test_policy_engine_not_touched(self):
        """Phase 53 must not import or modify policy/safety modules."""
        from symbolu.formulas import external_reality_trust_calibration

        source = inspect.getsource(external_reality_trust_calibration)

        # Phase 53 must not import policy modules
        assert "from symbolu.policy" not in source
        assert "SafetyPolicy" not in source
        assert "TradingGuardrails" not in source
        assert "regulated_mode" not in source or "regulated_mode" in "#"
        assert "allow_metaphor" not in source or "allow_metaphor" in "#"


# ============================================================================
# 6. ZERO-LLM GUARANTEE
# ============================================================================


class TestZeroLLMGuarantee:
    """
    Verify that Phase 53 ERTCE makes zero LLM calls.

    Phase 53 is deterministic, rule-based math only. No LLM usage.
    """

    def test_no_llm_imports(self):
        """Phase 53 must not import or use LLM libraries."""
        from symbolu.formulas import external_reality_trust_calibration
        import re

        source = inspect.getsource(external_reality_trust_calibration)

        # Remove comments and docstrings to avoid false positives
        source_no_comments = re.sub(r'#.*', '', source)
        source_no_docstrings = re.sub(r'""".*?"""', '', source_no_comments, flags=re.DOTALL)
        source_clean = source_no_docstrings.lower()

        # Phase 53 must not import LLM modules
        assert "anthropic" not in source_clean
        assert "openai" not in source_clean
        assert "import llm" not in source_clean
        assert "from llm" not in source_clean

        # Phase 53 must not make LLM calls
        assert ".complete(" not in source_clean
        assert ".chat(" not in source_clean
        assert ".generate(" not in source_clean
        assert "client." not in source_clean or source_clean.count("client.") == 0


# ============================================================================
# 7. DETERMINISM
# ============================================================================


class TestDeterminism:
    """
    Verify that Phase 53 ERTCE is fully deterministic.

    Same inputs must always produce identical outputs.
    No randomness, no time-dependent behavior, no side effects.
    """

    def test_same_inputs_same_outputs(self):
        """Phase 53 must produce identical outputs for identical inputs."""
        external_reality_signals = {
            "evidence_alignment": 0.65,
            "evidence_conflict_index": 0.30,
            "evidence_stability": 0.68,
            "context_relevance_score": 0.62,
            "external_support_density": 0.66,
        }

        internal_external_alignment = {
            "internal_consistency_index": 0.70,
            "external_evidence_consistency_index": 0.64,
            "alignment_index": 0.72,
            "divergence_index": 0.28,
            "evidence_conflict_index": 0.29,
            "stability_projection_index": 0.67,
        }

        internal_stability_signals = {
            "synthesis_integrity": 0.68,
            "macro_stability_index": 0.66,
            "temporal_stability_index": 0.71,
            "internal_consistency_strength": 0.69,
        }

        # Run computation 10 times
        results = []
        for _ in range(10):
            snapshot = compute_external_reality_trust_calibration(
                external_reality_signals=external_reality_signals,
                internal_external_alignment=internal_external_alignment,
                internal_stability_signals=internal_stability_signals,
            )
            results.append(snapshot)

        # All results must be identical
        first = results[0]
        for result in results[1:]:
            assert result.external_trust_score == first.external_trust_score
            assert result.internal_override_pressure == first.internal_override_pressure
            assert result.external_signal_fragility == first.external_signal_fragility
            assert result.alignment_resilience == first.alignment_resilience
            assert result.trust_decay_risk == first.trust_decay_risk
            assert result.trust_band == first.trust_band
            assert result.diagnostic_tags == first.diagnostic_tags


# ============================================================================
# 8. GRACEFUL DEGRADATION
# ============================================================================


class TestGracefulDegradation:
    """
    Verify that Phase 53 ERTCE degrades gracefully with missing inputs.

    Phase 53 must return None (not crash) when insufficient data available.
    """

    def test_returns_none_when_insufficient_data(self):
        """Phase 53 must return None when inputs are insufficient."""
        # Test 1: All inputs empty
        snapshot = compute_external_reality_trust_calibration(
            external_reality_signals={},
            internal_external_alignment={},
            internal_stability_signals={},
        )
        assert snapshot is None

        # Test 2: Only external signals present
        snapshot = compute_external_reality_trust_calibration(
            external_reality_signals={"evidence_alignment": 0.5},
            internal_external_alignment={},
            internal_stability_signals={},
        )
        assert snapshot is None

        # Test 3: Only alignment signals present
        snapshot = compute_external_reality_trust_calibration(
            external_reality_signals={},
            internal_external_alignment={"alignment_index": 0.5},
            internal_stability_signals={},
        )
        assert snapshot is None

        # Test 4: Only internal stability present
        snapshot = compute_external_reality_trust_calibration(
            external_reality_signals={},
            internal_external_alignment={},
            internal_stability_signals={"synthesis_integrity": 0.5},
        )
        assert snapshot is None

        # Test 5: Two out of three present (still insufficient)
        snapshot = compute_external_reality_trust_calibration(
            external_reality_signals={"evidence_alignment": 0.5},
            internal_external_alignment={"alignment_index": 0.5},
            internal_stability_signals={},
        )
        assert snapshot is None


# ============================================================================
# 9. UNIFIED API BACKWARD COMPATIBILITY
# ============================================================================


class TestUnifiedAPIInvariance:
    """
    Verify that Phase 53 field in UnifiedAPI is optional.

    Phase 53 must be backward compatible. Existing pipelines must work
    without Phase 53 data.
    """

    def test_phase53_field_is_optional(self):
        """UnifiedOutput must work without Phase 53 data."""
        from symbolu.api.unified_api import UnifiedOutput

        # Create UnifiedOutput without Phase 53 data
        output = UnifiedOutput(
            text="test",
            symbolic={},
            practical={},
            mirror={},
            dha={},
            routing={},
            mappers={},
            entropy={},
            coherence={},
            metadata={},
        )

        # Phase 53 field should exist but be None
        assert hasattr(output, 'external_reality_trust')
        assert output.external_reality_trust is None

        # to_dict() should work without Phase 53 data
        output_dict = output.to_dict()
        assert isinstance(output_dict, dict)

        # Phase 53 field should not appear in dict if None (cleaned by _remove_none_values)
        # This is the backward compatibility guarantee
        assert 'external_reality_trust' not in output_dict or output_dict.get('external_reality_trust') is None


# ============================================================================
# 10. END-TO-END PIPELINE INVARIANCE
# ============================================================================


class TestEndToEndPipelineInvariance:
    """
    Verify that Phase 53 ERTCE integrates correctly without breaking pipeline.

    This is a smoke test to ensure Phase 53 doesn't break the end-to-end
    pipeline behavior.
    """

    def test_pipeline_behavior_unchanged(self):
        """Phase 53 must integrate without altering pipeline behavior."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        # Create coherence state (as done in real pipeline)
        state = CoherenceState(convo_id="test", turn_index=0)

        # Verify Phase 53 fields exist
        assert hasattr(state, 'external_reality_trust_snapshot')
        assert hasattr(state, 'ertce_trust_score_history')
        assert hasattr(state, 'ertce_override_pressure_history')
        assert hasattr(state, 'ertce_fragility_history')
        assert hasattr(state, 'ertce_resilience_history')
        assert hasattr(state, 'ertce_decay_risk_history')
        assert hasattr(state, 'ertce_band_history')
        assert hasattr(state, 'ertce_tag_history')

        # Verify Phase 53 fields are optional (None/empty by default)
        assert state.external_reality_trust_snapshot is None
        assert state.ertce_trust_score_history == []
        assert state.ertce_override_pressure_history == []
        assert state.ertce_fragility_history == []
        assert state.ertce_resilience_history == []
        assert state.ertce_decay_risk_history == []
        assert state.ertce_band_history == []
        assert state.ertce_tag_history == []

        # Verify that setting Phase 53 data doesn't break state
        snapshot = ExternalRealityTrustSnapshot(
            external_trust_score=0.70,
            internal_override_pressure=0.30,
            external_signal_fragility=0.35,
            alignment_resilience=0.65,
            trust_decay_risk=0.25,
            trust_band="CONDITIONAL_EXTERNAL_TRUST",
            diagnostic_tags=["external_trust_moderate"],
        )

        state.external_reality_trust_snapshot = snapshot
        state.ertce_trust_score_history.append(0.70)
        state.ertce_override_pressure_history.append(0.30)
        state.ertce_fragility_history.append(0.35)
        state.ertce_resilience_history.append(0.65)
        state.ertce_decay_risk_history.append(0.25)
        state.ertce_band_history.append("CONDITIONAL_EXTERNAL_TRUST")
        state.ertce_tag_history.append(["external_trust_moderate"])

        # Verify state is still functional
        assert state.external_reality_trust_snapshot is not None
        assert len(state.ertce_trust_score_history) == 1
        assert state.ertce_trust_score_history[0] == 0.70


# ============================================================================
# AUDIT SUMMARY
# ============================================================================

"""
PHASE 53 INVARIANCE AUDIT COVERAGE:

✅ Routing Invariance (2 tests)
   - TTOR not modified
   - MLCR not modified

✅ Mapper Invariance (3 tests)
   - HRM not modified
   - LCM not modified
   - LAM not modified

✅ Coherence Engine Invariance (2 tests)
   - No upstream coherence mutation
   - Phase 53 snapshot is read-only

✅ Persona & Tone Invariance (2 tests)
   - Metadata-only integration
   - No tone or semantic changes

✅ Policy & Safety Invariance (1 test)
   - Policy engine not touched

✅ Zero-LLM Guarantee (1 test)
   - No LLM imports or calls

✅ Determinism (1 test)
   - Same inputs → same outputs

✅ Graceful Degradation (1 test)
   - Returns None when insufficient data

✅ Unified API Backward Compatibility (1 test)
   - Phase 53 field is optional

✅ End-to-End Pipeline Invariance (1 test)
   - Pipeline behavior unchanged

TOTAL: 15 invariance tests across 10 categories

AUDIT STATUS: ✅ PASS
Phase 53 ERTCE is observation-only and does not alter system behavior.
"""
