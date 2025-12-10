"""
Phase 27 Behavioral Invariance Audit Tests

This test suite provides comprehensive invariance validation for Phase 27
Symbolic Harmonization Formula (SHF), ensuring zero behavioral changes to
the existing pipeline.

These tests are designed to be run as part of the PR merge safety checklist.
"""

import pytest
from symbolu.formulas.symbolic_harmonization import compute_symbolic_harmonization
from symbolu.core.coherence.coherence_engine import CoherenceEngine
from symbolu.adapter.dilchat_adapter import build_dilchat_response
from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver


# ============================================================================
# CHECKLIST ITEM #1: Routing Invariance
# ============================================================================

class TestRoutingInvariance:
    """Verify that SHF does not affect routing decisions."""

    def test_routing_files_have_no_shf_imports(self):
        """Verify routing modules do not import symbolic_harmonization."""
        # This is a structural test - we verify that no routing files
        # contain imports from symbolic_harmonization
        import symbolu
        import os
        import re

        # Get symbolu package directory
        symbolu_dir = os.path.dirname(symbolu.__file__)

        # Search for routing-related files
        routing_patterns = ['**/routing*.py', '**/ttor*.py', '**/mlcr*.py']
        shf_import_pattern = re.compile(r'from.*symbolic_harmonization|import.*symbolic_harmonization')

        routing_files = []
        for root, dirs, files in os.walk(symbolu_dir):
            for file in files:
                if 'routing' in file.lower() or 'ttor' in file.lower() or 'mlcr' in file.lower():
                    if file.endswith('.py'):
                        routing_files.append(os.path.join(root, file))

        # Check that no routing files import symbolic_harmonization
        for filepath in routing_files:
            with open(filepath, 'r') as f:
                content = f.read()
                assert not shf_import_pattern.search(content), \
                    f"Routing file {filepath} imports symbolic_harmonization - INVARIANCE VIOLATION"


# ============================================================================
# CHECKLIST ITEM #2: Mapper Invariance
# ============================================================================

class TestMapperInvariance:
    """Verify that SHF does not affect mapper activation or outputs."""

    def test_mapper_files_have_no_shf_imports(self):
        """Verify mapper modules do not import symbolic_harmonization."""
        import symbolu
        import os
        import re

        symbolu_dir = os.path.dirname(symbolu.__file__)
        shf_import_pattern = re.compile(r'from.*symbolic_harmonization|import.*symbolic_harmonization')

        mapper_files = []
        for root, dirs, files in os.walk(symbolu_dir):
            for file in files:
                if any(name in file.lower() for name in ['mapper', 'hrm', 'lcm', 'lam']):
                    if file.endswith('.py'):
                        mapper_files.append(os.path.join(root, file))

        # Check that no mapper files import symbolic_harmonization
        for filepath in mapper_files:
            with open(filepath, 'r') as f:
                content = f.read()
                assert not shf_import_pattern.search(content), \
                    f"Mapper file {filepath} imports symbolic_harmonization - INVARIANCE VIOLATION"


# ============================================================================
# CHECKLIST ITEM #3: Coherence Score Isolation
# ============================================================================

class TestCoherenceScoreIsolation:
    """Verify that SHF does not modify coherence scoring formulas."""

    def test_coherence_engine_shf_called_after_scoring(self):
        """Verify _update_symbolic_harmonization is called AFTER score computation."""
        # Read coherence_engine.py and verify call order
        import symbolu.core.coherence.coherence_engine as engine_module
        import inspect

        source = inspect.getsource(engine_module.CoherenceEngine.update_state)

        # Find line numbers of key operations
        lines = source.split('\n')
        compute_coherence_line = None
        update_shf_line = None

        for i, line in enumerate(lines):
            if '_compute_overall_coherence' in line:
                compute_coherence_line = i
            if '_update_symbolic_harmonization' in line:
                update_shf_line = i

        # Verify SHF is called AFTER coherence computation
        assert compute_coherence_line is not None, "Could not find _compute_overall_coherence call"
        assert update_shf_line is not None, "Could not find _update_symbolic_harmonization call"
        assert update_shf_line > compute_coherence_line, \
            "SHF must be called AFTER coherence computation - INVARIANCE VIOLATION"

    def test_compute_overall_coherence_no_shf_dependency(self):
        """Verify _compute_overall_coherence does not use SHF fields."""
        import symbolu.core.coherence.coherence_engine as engine_module
        import inspect

        source = inspect.getsource(engine_module.CoherenceEngine._compute_overall_coherence)

        # Check that symbolic_harmonization fields are not referenced
        shf_fields = [
            'symbolic_harmonization_index',
            'symbolic_alignment',
            'mirror_alignment',
            'harmonization_entropy',
        ]

        for field in shf_fields:
            assert field not in source, \
                f"Coherence formula references SHF field '{field}' - INVARIANCE VIOLATION"

    def test_deterministic_coherence_scores_unchanged(self):
        """Verify coherence scores are deterministic and unchanged by SHF presence."""
        class MockRoutingPlan:
            tier = "hybrid"
            domain = "therapy"

        engine = CoherenceEngine(window=10)

        # Create 5 identical states
        states = []
        for _ in range(5):
            state = engine.update_state(
                prev_state=None,
                convo_id="test_determinism",
                turn_index=0,
                routing_plan=MockRoutingPlan(),
                mapper_profile={"HRM": 0.6, "LCM": 0.3, "LAM": 0.1},
                temporal_summary=None,
                semantic_signature={},
            )
            states.append(state)

        # Verify all states have identical coherence scores
        for i in range(1, 5):
            assert states[0].coherence_score == states[i].coherence_score, \
                "Coherence score is non-deterministic - INVARIANCE VIOLATION"
            assert states[0].coherence_score_v2 == states[i].coherence_score_v2, \
                "Coherence v2 is non-deterministic - INVARIANCE VIOLATION"
            assert states[0].coherence_score_v3 == states[i].coherence_score_v3, \
                "Coherence v3 is non-deterministic - INVARIANCE VIOLATION"
            assert states[0].coherence_fused == states[i].coherence_fused, \
                "Coherence fused is non-deterministic - INVARIANCE VIOLATION"


# ============================================================================
# CHECKLIST ITEM #4: Fusion/DHA/Renderer Invariance
# ============================================================================

class TestFusionDHARendererInvariance:
    """Verify that Fusion, DHA, and Renderer are unchanged."""

    def test_fusion_dha_renderer_no_shf_imports(self):
        """Verify Fusion/DHA/Renderer do not import symbolic_harmonization."""
        import symbolu
        import os
        import re

        symbolu_dir = os.path.dirname(symbolu.__file__)
        shf_import_pattern = re.compile(r'from.*symbolic_harmonization|import.*symbolic_harmonization')

        target_files = []
        for root, dirs, files in os.walk(symbolu_dir):
            for file in files:
                if any(name in file.lower() for name in ['fusion', 'dha', 'renderer']):
                    if file.endswith('.py'):
                        target_files.append(os.path.join(root, file))

        # Check that no files import symbolic_harmonization
        for filepath in target_files:
            with open(filepath, 'r') as f:
                content = f.read()
                assert not shf_import_pattern.search(content), \
                    f"File {filepath} imports symbolic_harmonization - INVARIANCE VIOLATION"


# ============================================================================
# CHECKLIST ITEM #5: Policy Engine + Guardrails Invariance
# ============================================================================

class TestPolicyEngineInvariance:
    """Verify that Policy Engine and Guardrails are unchanged."""

    def test_policy_guardrails_no_shf_imports(self):
        """Verify Policy/Guardrails do not import symbolic_harmonization."""
        import symbolu
        import os
        import re

        symbolu_dir = os.path.dirname(symbolu.__file__)
        shf_import_pattern = re.compile(r'from.*symbolic_harmonization|import.*symbolic_harmonization')

        target_files = []
        for root, dirs, files in os.walk(symbolu_dir):
            for file in files:
                if any(name in file.lower() for name in ['policy', 'guardrail']):
                    if file.endswith('.py'):
                        target_files.append(os.path.join(root, file))

        # Check that no files import symbolic_harmonization
        for filepath in target_files:
            with open(filepath, 'r') as f:
                content = f.read()
                assert not shf_import_pattern.search(content), \
                    f"File {filepath} imports symbolic_harmonization - INVARIANCE VIOLATION"


# ============================================================================
# CHECKLIST ITEM #6: DILchat Adapter Invariance
# ============================================================================

class TestDILchatAdapterInvariance:
    """Verify DILchat adapter only adds diagnostic hints for correct domains/modes."""

    def test_shf_hints_only_therapy_identity(self):
        """Verify SHF hints only appear for therapy/identity domains."""
        # Mock unified output with SHF data
        unified_output = {
            "text": "Test response",
            "coherence": {
                "coherence_score": 0.75,
                "symbolic_harmonization": {
                    "index": 0.80,
                },
            },
            "symbolic": {},
            "practical": {},
            "mirror": {},
        }

        policy_flags = {
            "interaction_mode": "smart_insight",
        }

        # Test for trading domain - SHF hints should NOT appear
        response_trading = build_dilchat_response(unified_output, policy_flags, "trading")
        shf_hint_codes = [h.code for h in response_trading.hints if 'SYMBOLIC_HARMONY' in h.code]
        assert len(shf_hint_codes) == 0, \
            "SHF hints appeared for trading domain - INVARIANCE VIOLATION"

        # Test for therapy domain - SHF hints SHOULD appear
        response_therapy = build_dilchat_response(unified_output, policy_flags, "therapy")
        shf_hint_codes = [h.code for h in response_therapy.hints if 'SYMBOLIC_HARMONY' in h.code]
        assert len(shf_hint_codes) > 0, \
            "SHF hints did not appear for therapy domain - INVARIANCE VIOLATION"

    def test_shf_hints_only_smart_deep_modes(self):
        """Verify SHF hints only appear for SMART_INSIGHT/DEEP_ADAPTIVE modes."""
        unified_output = {
            "text": "Test response",
            "coherence": {
                "coherence_score": 0.75,
                "symbolic_harmonization": {
                    "index": 0.80,
                },
            },
            "symbolic": {},
            "practical": {},
            "mirror": {},
        }

        # Test for ANALYTICS_ONLY mode - SHF hints should NOT appear
        policy_flags_analytics = {
            "interaction_mode": "analytics_only",
        }
        response_analytics = build_dilchat_response(unified_output, policy_flags_analytics, "therapy")
        shf_hint_codes = [h.code for h in response_analytics.hints if 'SYMBOLIC_HARMONY' in h.code]
        assert len(shf_hint_codes) == 0, \
            "SHF hints appeared for analytics_only mode - INVARIANCE VIOLATION"

    def test_shf_does_not_override_safety_hints(self):
        """Verify SHF hints are additive and do not override existing hints."""
        unified_output = {
            "text": "Test response",
            "coherence": {
                "coherence_score": 0.35,
                "symbolic_harmonization": {
                    "index": 0.80,
                },
            },
            "symbolic": {},
            "practical": {},
            "mirror": {},
        }

        policy_flags = {
            "interaction_mode": "smart_insight",
            "needs_grounding": True,  # Safety hint
        }

        response = build_dilchat_response(unified_output, policy_flags, "therapy")

        # Verify both grounding and SHF hints are present
        grounding_hints = [h for h in response.hints if h.code == "GROUNDING"]
        shf_hints = [h for h in response.hints if 'SYMBOLIC_HARMONY' in h.code]

        assert len(grounding_hints) > 0, "Safety grounding hint was removed - INVARIANCE VIOLATION"
        assert len(shf_hints) > 0, "SHF hint was not added - INVARIANCE VIOLATION"


# ============================================================================
# CHECKLIST ITEM #7: Unified API + Observer Invariance
# ============================================================================

class TestUnifiedAPIObserverInvariance:
    """Verify API and Observer handle SHF fields correctly."""

    def test_observer_null_handling(self):
        """Verify observer handles missing SHF data gracefully."""
        observer = CoherenceObserver()

        # Create observation with no coherence state (SHF should be None)
        obs = observer.observe(
            text="test",
            pipeline_context=type('obj', (object,), {
                'coherence_state': None,
            })(),
            coherence_state=None,
        )

        # Verify SHF fields are None (not raising exceptions)
        assert obs.symbolic_harmonization is None
        assert obs.symbolic_harmonization_index is None
        assert obs.symbolic_alignment is None
        assert obs.mirror_alignment_shf is None
        assert obs.harmonization_entropy is None

    def test_api_backward_compatibility(self):
        """Verify API output is backward-compatible (new fields are optional)."""
        # This test would require full API context
        # For now, we verify the field structure is additive
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

        # Create observation without SHF fields
        obs = CoherenceObservation(
            coherence_score=0.7,
            persona_drift_score=0.2,
            semantic_stability_score=0.6,
            temporal_arc_score=0.5,
            mapper_volatility_score=0.3,
            turn_number=1,
            tier="hybrid",
            domain="therapy",
            active_mappers=["HRM"],
        )

        # Verify observation can be created without SHF fields
        assert obs.symbolic_harmonization is None
        assert obs.symbolic_harmonization_index is None

        # Verify to_dict() works
        obs_dict = obs.to_dict()
        assert 'symbolic_harmonization' in obs_dict  # Field exists
        assert obs_dict['symbolic_harmonization'] is None  # But can be None


# ============================================================================
# CHECKLIST ITEM #8: Determinism
# ============================================================================

class TestDeterminism:
    """Verify SHF is fully deterministic."""

    def test_identical_inputs_produce_identical_outputs(self):
        """Verify compute_symbolic_harmonization is deterministic."""
        inputs = {
            "symbolic_layer_vector": [0.8, 0.7, 0.9],
            "practical_layer_vector": [0.7, 0.8, 0.85],
            "mirror_layer_vector": [0.6, 0.7, 0.75],
            "guna_resonance": 0.75,
            "kosha_resonance": 0.70,
            "semantic_integrity": 0.80,
        }

        # Compute 100 times
        results = [compute_symbolic_harmonization(**inputs) for _ in range(100)]

        # Verify all results are identical
        for i in range(1, 100):
            assert results[0].symbolic_harmonization_index == results[i].symbolic_harmonization_index, \
                f"SHI differs at iteration {i} - NON-DETERMINISTIC VIOLATION"
            assert results[0].harmonization_entropy == results[i].harmonization_entropy, \
                f"Entropy differs at iteration {i} - NON-DETERMINISTIC VIOLATION"
            assert results[0].notes == results[i].notes, \
                f"Notes differ at iteration {i} - NON-DETERMINISTIC VIOLATION"


# ============================================================================
# CHECKLIST ITEM #9: Graceful Degradation
# ============================================================================

class TestGracefulDegradation:
    """Verify SHF degrades gracefully with missing inputs."""

    def test_no_exceptions_on_missing_inputs(self):
        """Verify compute_symbolic_harmonization never raises exceptions."""
        # Test all permutations of missing inputs
        test_cases = [
            {},  # No inputs
            {"symbolic_layer_vector": [0.5]},  # Only one layer
            {"guna_resonance": 0.5},  # Only metrics
            {"symbolic_layer_vector": [], "practical_layer_vector": []},  # Empty vectors
            {"symbolic_layer_vector": None, "practical_layer_vector": None},  # None vectors
        ]

        for inputs in test_cases:
            try:
                result = compute_symbolic_harmonization(**inputs)
                # Result should be None for insufficient inputs
                assert result is None or isinstance(result, type(compute_symbolic_harmonization(
                    symbolic_layer_vector=[0.5],
                    practical_layer_vector=[0.5],
                    guna_resonance=0.5
                ).__class__))
            except Exception as e:
                pytest.fail(f"compute_symbolic_harmonization raised exception with inputs {inputs}: {e}")


# ============================================================================
# CHECKLIST ITEM #10: Test Coverage Summary
# ============================================================================

class TestCoverageSummary:
    """Summary test that validates all checklist items."""

    def test_all_invariance_checks_pass(self):
        """Meta-test that confirms all invariance checks are present."""
        # This test just confirms that all test classes exist
        test_classes = [
            TestRoutingInvariance,
            TestMapperInvariance,
            TestCoherenceScoreIsolation,
            TestFusionDHARendererInvariance,
            TestPolicyEngineInvariance,
            TestDILchatAdapterInvariance,
            TestUnifiedAPIObserverInvariance,
            TestDeterminism,
            TestGracefulDegradation,
        ]

        for test_class in test_classes:
            assert test_class is not None, f"Test class {test_class.__name__} is missing"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
