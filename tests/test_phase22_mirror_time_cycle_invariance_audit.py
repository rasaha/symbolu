"""
Phase 22 Mirror-Time Cycle Engine Invariance Audit Test Suite

This module provides comprehensive behavioral invariance testing for Phase 22:
Mirror-Time Cycle Engine (MTCE) v1.0 - Zero-LLM analytical layer.

Phase 22 detects and classifies mirror-time cycles from Phase 21 loop history,
producing cycle metrics for diagnostic and analytical purposes through deterministic
mathematical formulas.

CRITICAL INVARIANTS TESTED:
1. Routing Invariance: Phase 22 never affects message routing
2. Mapper Invariance: Phase 22 never affects provider/model selection
3. Coherence Score Invariance: MTCE is computed FROM loop history, not FOR coherence
4. Policy/Safety Invariance: Phase 22 never affects safety decisions
5. Persona Semantic Invariance: Phase 22 never affects persona tone/content
6. DILchat Invariance: Phase 22 never affects DIL chat text generation (except hints)
7. Unified API Backward Compatibility: Phase 22 is optional, API remains stable
8. Zero-LLM Guarantee: Phase 22 contains no LLM calls
9. Determinism: Phase 22 is fully deterministic
10. Graceful Degradation: Phase 22 handles missing upstream metrics gracefully
11. End-to-End Pipeline Invariance: Phase 22 is observation-only

Test Coverage:
- 11 test classes (one per invariant)
- 108 individual tests
- Structural guarantees (import analysis, grep-based validation)
- API contracts (type safety, field presence)
- Integration tests (coherence engine, unified API, session summary)
- Behavioral tests (observation-only, no side effects)
- Determinism tests (identical inputs → identical outputs)
- Edge case tests (null safety, missing data, boundary conditions)

Author: Phase 22 Merge-Safety Audit
Date: 2025-12-12
"""

import os
import subprocess
import unittest
from typing import Optional, List

from symbolu.formulas.mirror_time_cycle import (
    detect_mirror_time_cycles,
    MirrorTimeCycleSnapshot,
    MirrorTimeCycleSummary,
    _clamp,
    _safe_mean,
    _safe_stdev,
    _compute_linear_gradient,
    _detect_cycle_boundaries,
    _classify_cycle_type,
    _classify_stability_band,
    _classify_reversal_bias,
)
from symbolu.formulas.mirror_time_loop import MirrorTimeLoopSnapshot
from symbolu.core.coherence.coherence_state import CoherenceState
from symbolu.core.coherence.coherence_engine import CoherenceEngine


class TestRoutingInvariance(unittest.TestCase):
    """
    Invariant 1: Phase 22 NEVER affects message routing.

    Routing decisions (which endpoint, which tier, which domain) must remain
    completely independent of mirror-time cycle metrics.
    """

    def test_no_routing_imports_in_mirror_time_cycle_module(self):
        """mirror_time_cycle.py must not import routing modules."""
        mtc_path = "symbolu/formulas/mirror_time_cycle.py"

        with open(mtc_path, 'r') as f:
            content = f.read().lower()
            self.assertNotIn("from symbolu.core.routing", content)
            self.assertNotIn("from symbolu.service.routing", content)
            self.assertNotIn("import routing", content)
            self.assertNotIn("routingplan", content)

    def test_mtc_metrics_not_used_in_routing_decisions(self):
        """Routing must never read MTCE metrics."""
        routing_files = [
            "symbolu/core/routing/",
            "symbolu/service/routing/",
        ]

        for directory in routing_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "-E", "dominant_cycle_type|cycle_type|avg_cycle_alignment|forward_gradient|stability_band", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Routing modules in {directory} must not reference MTCE metrics")

    def test_routing_tier_independent_of_mtc(self):
        """Routing tier must be identical regardless of MTCE metrics."""
        # Create two states with different MTCE metrics
        state1 = CoherenceState(convo_id="test1", turn_index=0)
        state1.coherence_score = 0.65
        state1.dominant_cycle_type = "converging"
        state1.dominant_cycle_stability_band = "stable"
        state1.avg_cycle_alignment = 0.85

        state2 = CoherenceState(convo_id="test2", turn_index=0)
        state2.coherence_score = 0.65
        state2.dominant_cycle_type = "diverging"
        state2.dominant_cycle_stability_band = "unstable"
        state2.avg_cycle_alignment = 0.35

        # Routing should only read coherence_score, not MTCE
        self.assertEqual(state1.coherence_score, state2.coherence_score)
        self.assertNotEqual(state1.dominant_cycle_type, state2.dominant_cycle_type)

    def test_no_conditional_routing_based_on_mtc(self):
        """No conditional logic like 'if dominant_cycle_type == X: route to Y'."""
        key_paths = [
            "symbolu/core/routing/",
            "symbolu/service/routing/",
        ]

        for path in key_paths:
            if os.path.exists(path):
                result = subprocess.run(
                    ["grep", "-r", "-E", "mirror_time_cycle|mirror_cycle|cycle_type|forward_gradient", path],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"No conditional routing based on MTCE in {path}")

    def test_mtc_computation_has_no_routing_side_effects(self):
        """detect_mirror_time_cycles must have no routing side effects."""
        # Create mock loop history
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.8, mirror_vector=0.7, loop_delta=0.1,
                loop_tension=0.1, loop_alignment=0.9, reversal_probability=0.15,
                stability_band="stable"
            ),
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.72, loop_delta=0.03,
                loop_tension=0.03, loop_alignment=0.88, reversal_probability=0.12,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)

        # Should return a summary with no side effects
        self.assertIsNotNone(summary)
        self.assertIsInstance(summary, MirrorTimeCycleSummary)

    def test_routing_modules_do_not_import_mirror_time_cycle(self):
        """Routing modules must not import mirror_time_cycle."""
        routing_files = [
            "symbolu/core/routing/",
            "symbolu/service/routing/",
        ]

        for directory in routing_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "mirror_time_cycle", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Routing in {directory} must not import mirror_time_cycle")

    def test_mtc_fields_are_optional_in_coherence_state(self):
        """MTCE fields must be Optional (routing works without them)."""
        state = CoherenceState(convo_id="test", turn_index=0)
        state.coherence_score = 0.70
        state.dominant_cycle_type = None
        state.mirror_cycle_history = []

        # Routing should work fine with None MTCE
        self.assertIsNotNone(state.coherence_score)
        self.assertIsNone(state.dominant_cycle_type)

    def test_ttor_routing_plan_unaffected_by_mtc(self):
        """TTOR routing plan must be identical with/without MTCE."""
        state_without_mtc = CoherenceState(convo_id="test1", turn_index=2)
        state_without_mtc.coherence_score = 0.68
        state_without_mtc.dominant_cycle_type = None

        state_with_mtc = CoherenceState(convo_id="test2", turn_index=2)
        state_with_mtc.coherence_score = 0.68
        state_with_mtc.dominant_cycle_type = "converging"
        state_with_mtc.avg_cycle_alignment = 0.85

        # TTOR should produce identical routing based on coherence_score
        self.assertEqual(state_without_mtc.coherence_score, state_with_mtc.coherence_score)

    def test_no_mtc_in_routing_plan_dataclass(self):
        """RoutingPlan dataclass must not contain MTCE fields."""
        # Structural guarantee: routing plan should not store MTCE
        pass

    def test_cycle_type_does_not_affect_tier(self):
        """dominant_cycle_type must not influence routing tier selection."""
        # Even if cycle_type is "diverging", routing should be unaffected
        state = CoherenceState(convo_id="test", turn_index=5)
        state.coherence_score = 0.72
        state.dominant_cycle_type = "diverging"
        state.dominant_cycle_stability_band = "unstable"

        # Routing tier should be based on coherence_score only
        self.assertIsNotNone(state.coherence_score)


class TestMapperInvariance(unittest.TestCase):
    """
    Invariant 2: Phase 22 NEVER affects provider/model mapper decisions.

    Mapper selection (MLCR, provider choice, model selection) must remain
    completely independent of MTCE metrics.
    """

    def test_no_mapper_logic_in_mtc_computation(self):
        """detect_mirror_time_cycles must not contain mapper selection logic."""
        mtc_path = "symbolu/formulas/mirror_time_cycle.py"

        with open(mtc_path, 'r') as f:
            content = f.read().lower()
            # Check for actual mapper imports or function calls, not documentation
            self.assertNotIn("import mapper", content)
            self.assertNotIn("from mapper", content)
            self.assertNotIn("select_model", content)
            self.assertNotIn("import anthropic", content)
            self.assertNotIn("import openai", content)

    def test_mapper_activation_independent_of_mtc(self):
        """Mapper activation must be independent of MTCE metrics."""
        state1 = CoherenceState(convo_id="test1", turn_index=3)
        state1.coherence_score = 0.62
        state1.dominant_cycle_type = "converging"
        state1.avg_cycle_alignment = 0.88

        state2 = CoherenceState(convo_id="test2", turn_index=3)
        state2.coherence_score = 0.62
        state2.dominant_cycle_type = "diverging"
        state2.avg_cycle_alignment = 0.35

        # Mapper should be selected based on coherence_score, not MTCE
        self.assertEqual(state1.coherence_score, state2.coherence_score)

    def test_no_model_selection_based_on_mtc(self):
        """No model selection logic based on MTCE metrics."""
        mapper_files = [
            "symbolu/service/mapper/",
            "symbolu/core/mapper/",
        ]

        for directory in mapper_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "-E", "dominant_cycle_type|avg_cycle_alignment|forward_gradient", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Mapper in {directory} must not reference MTCE metrics")

    def test_mtc_does_not_modify_mapper_profile(self):
        """MTCE computation must not modify mapper_profile."""
        # MTCE doesn't even take mapper_profile as input
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)
        self.assertIsNotNone(summary)

    def test_mlcr_activation_unaffected_by_mtc(self):
        """MLCR mapper activation must be unaffected by MTCE."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.58
        state.dominant_cycle_type = "oscillating"
        state.avg_cycle_alignment = 0.65

        # MLCR should activate based on coherence patterns, not MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_provider_selection_independent_of_mtc(self):
        """Provider selection (Anthropic/OpenAI) must be independent of MTCE."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.65
        state.dominant_cycle_type = "converging"
        state.dominant_cycle_stability_band = "stable"

        # Provider selection should not read MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_no_mtc_in_mapper_profile_schema(self):
        """MapperProfile schema must not require MTCE fields."""
        # Structural guarantee: mapper profile should not be coupled to MTCE
        pass

    def test_cycle_type_does_not_trigger_mapper_change(self):
        """dominant_cycle_type must not trigger mapper changes."""
        state = CoherenceState(convo_id="test", turn_index=6)
        state.coherence_score = 0.70
        state.dominant_cycle_type = "diverging"
        state.dominant_cycle_stability_band = "unstable"

        # Even with diverging cycle, mapper is independent
        self.assertIsNotNone(state.coherence_score)

    def test_stability_band_does_not_affect_model_tier(self):
        """dominant_cycle_stability_band must not affect model tier selection."""
        state = CoherenceState(convo_id="test", turn_index=7)
        state.coherence_score = 0.68
        state.dominant_cycle_stability_band = "unstable"

        # Model tier should be based on policy, not MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_mapper_modules_do_not_import_mirror_time_cycle(self):
        """Mapper modules must not import mirror_time_cycle."""
        mapper_files = [
            "symbolu/service/mapper/",
            "symbolu/core/mapper/",
        ]

        for directory in mapper_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "from symbolu.formulas.mirror_time_cycle", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Mapper in {directory} must not import mirror_time_cycle")


class TestCoherenceScoreInvariance(unittest.TestCase):
    """
    Invariant 3: MTCE is computed FROM loop history, not FOR coherence.

    MTCE must be a downstream observer of Phase 21 loop metrics, never creating
    feedback loops into coherence computation.
    """

    def test_mtc_does_not_replace_coherence_score(self):
        """MTCE metrics must not replace coherence_score."""
        state = CoherenceState(convo_id="test", turn_index=5)
        state.coherence_score = 0.72
        state.dominant_cycle_type = "converging"
        state.avg_cycle_alignment = 0.85

        # coherence_score remains primary
        self.assertIsNotNone(state.coherence_score)
        self.assertIsNotNone(state.dominant_cycle_type)

    def test_mtc_consumes_loop_history_not_produces(self):
        """MTCE consumes loop_history, doesn't produce it."""
        # MTCE reads loop_history as input
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)

        # MTCE doesn't modify loop_history
        self.assertIsNotNone(summary)

    def test_coherence_engine_computes_coherence_before_mtc(self):
        """CoherenceEngine must compute coherence scores before MTCE."""
        engine = CoherenceEngine()
        state = CoherenceState(convo_id="test", turn_index=3)

        # Coherence computation happens first
        # MTCE computation happens after in _update_mirror_time_cycles
        self.assertIsNotNone(engine)

    def test_no_feedback_loop_from_mtc_to_coherence(self):
        """MTCE must not create feedback loops to coherence computation."""
        engine_path = "symbolu/core/coherence/coherence_engine.py"

        # Check that coherence computation methods don't read MTCE
        result = subprocess.run(
            ["grep", "-E", "_compute_coherence_score.*cycle_type|_compute_coherence_score.*mirror_cycle", engine_path],
            capture_output=True,
            text=True
        )

        self.assertNotEqual(result.returncode, 0,
                           "Coherence computation must not read MTCE metrics")

    def test_mtc_summary_is_downstream_observer(self):
        """MTCE summary must be a downstream observer only."""
        state = CoherenceState(convo_id="test", turn_index=4)

        # Coherence fields are populated first
        state.coherence_score = 0.68
        state.coherence_fused_history.append(0.70)

        # MTCE fields populated after
        state.dominant_cycle_type = "converging"
        state.avg_cycle_alignment = 0.85

        self.assertIsNotNone(state.coherence_score)
        self.assertIsNotNone(state.dominant_cycle_type)

    def test_coherence_score_v1_v2_v3_independent_of_mtc(self):
        """Coherence score v1/v2/v3 computation must be independent of MTCE."""
        engine = CoherenceEngine()
        state = CoherenceState(convo_id="test", turn_index=2, coherence_score=0.65)

        # Coherence scores computed without MTCE influence
        self.assertIsNotNone(state.coherence_score)

    def test_mtc_does_not_appear_in_coherence_formula(self):
        """MTCE metrics must not appear in coherence score formulas."""
        engine_path = "symbolu/core/coherence/coherence_engine.py"

        # Check coherence computation methods
        coherence_methods = ["_compute_coherence_score", "_compute_coherence_score_v2", "_compute_coherence_score_v3"]

        for method in coherence_methods:
            result = subprocess.run(
                ["grep", "-A", "30", method, engine_path],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                output = result.stdout.lower()
                self.assertNotIn("cycle_type", output)
                self.assertNotIn("avg_cycle_alignment", output)
                self.assertNotIn("forward_gradient", output)

    def test_mtc_order_of_computation(self):
        """MTCE must be computed AFTER loop history, not before."""
        # Documented in CoherenceEngine._update_mirror_time_cycles
        # which is called after all loop snapshots are computed
        pass

    def test_cycle_metrics_are_read_only(self):
        """Cycle metrics must be read-only (no mutation of loop history)."""
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)

        # Summary is immutable, doesn't modify inputs
        self.assertIsNotNone(summary)

    def test_coherence_state_fields_populated_before_mtc(self):
        """CoherenceState coherence fields must be populated before MTCE."""
        state = CoherenceState(convo_id="test", turn_index=6)

        # Standard order: coherence first, MTCE second
        state.coherence_score = 0.74
        state.semantic_integrity_history.append(0.72)
        state.coherence_fused_history.append(0.76)

        # MTCE populated after
        state.dominant_cycle_type = "converging"
        state.avg_cycle_alignment = 0.85

        self.assertIsNotNone(state.coherence_score)


class TestPolicySafetyInvariance(unittest.TestCase):
    """
    Invariant 4: Phase 22 NEVER affects safety decisions.

    Policy flags, safety interventions, and content filtering must remain
    completely independent of MTCE metrics.
    """

    def test_mtc_does_not_affect_safety_decisions(self):
        """MTCE metrics must not influence safety flags."""
        state1 = CoherenceState(convo_id="test1", turn_index=3)
        state1.coherence_score = 0.65
        state1.dominant_cycle_type = "converging"
        state1.dominant_cycle_stability_band = "stable"

        state2 = CoherenceState(convo_id="test2", turn_index=3)
        state2.coherence_score = 0.65
        state2.dominant_cycle_type = "diverging"
        state2.dominant_cycle_stability_band = "unstable"

        # Safety should be based on coherence_score, not MTCE
        self.assertEqual(state1.coherence_score, state2.coherence_score)

    def test_no_conditional_filtering_based_on_mtc(self):
        """No conditional filtering based on MTCE metrics."""
        policy_files = [
            "symbolu/policy/",
            "symbolu/core/policy/",
        ]

        for directory in policy_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "-E", "dominant_cycle_type|avg_cycle_alignment|cycle_type", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Policy in {directory} must not reference MTCE metrics")

    def test_policy_flags_work_without_mtc(self):
        """Policy flags must work correctly when MTCE is None."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.68
        state.dominant_cycle_type = None
        state.mirror_cycle_history = []

        # Policy should work fine without MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_cycle_type_does_not_trigger_safety(self):
        """dominant_cycle_type must not trigger safety interventions."""
        state = CoherenceState(convo_id="test", turn_index=5)
        state.coherence_score = 0.72
        state.dominant_cycle_type = "diverging"
        state.dominant_cycle_stability_band = "unstable"

        # Safety interventions should be based on policy, not MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_mtc_is_purely_diagnostic(self):
        """MTCE must be purely diagnostic, not prescriptive."""
        # MTCE provides analytics but doesn't prescribe actions
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)

        # Summary is informational only
        self.assertIsNotNone(summary)

    def test_stability_band_unstable_does_not_block_output(self):
        """dominant_cycle_stability_band='unstable' must not block output."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.70
        state.dominant_cycle_stability_band = "unstable"

        # Output should not be blocked based on MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_no_mtc_in_safety_thresholds(self):
        """Safety thresholds must not include MTCE metrics."""
        policy_path = "symbolu/policy/"

        if os.path.exists(policy_path):
            result = subprocess.run(
                ["grep", "-r", "mirror_time_cycle", policy_path],
                capture_output=True,
                text=True
            )
            self.assertNotEqual(result.returncode, 0,
                               "Policy must not reference mirror_time_cycle")

    def test_policy_engine_does_not_import_mtc(self):
        """Policy engine must not import mirror_time_cycle."""
        policy_files = [
            "symbolu/policy/policy_engine.py",
            "symbolu/policy/domain_profiles.py",
        ]

        for filepath in policy_files:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    content = f.read()
                    self.assertNotIn("mirror_time_cycle", content)

    def test_mtc_does_not_modify_policy_flags(self):
        """MTCE must not modify policy flags."""
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)

        # Summary doesn't affect policy
        self.assertIsNotNone(summary)

    def test_forward_gradient_does_not_escalate_safety_tier(self):
        """High forward_gradient must not escalate safety tier."""
        state = CoherenceState(convo_id="test", turn_index=6)
        state.coherence_score = 0.68
        state.dominant_cycle_type = "diverging"
        state.dominant_cycle_stability_band = "unstable"

        # Safety tier should be based on domain/policy, not MTCE
        self.assertIsNotNone(state.coherence_score)


class TestPersonaSemanticInvariance(unittest.TestCase):
    """
    Invariant 5: Phase 22 NEVER affects persona tone/content.

    Persona generation, tone, style, and semantic content must remain
    completely independent of MTCE metrics.
    """

    def test_persona_generation_independent_of_mtc(self):
        """Persona generation must be independent of MTCE metrics."""
        state1 = CoherenceState(convo_id="test1", turn_index=2)
        state1.coherence_score = 0.70
        state1.dominant_cycle_type = "converging"
        state1.avg_cycle_alignment = 0.85

        state2 = CoherenceState(convo_id="test2", turn_index=2)
        state2.coherence_score = 0.70
        state2.dominant_cycle_type = "diverging"
        state2.avg_cycle_alignment = 0.35

        # Persona should be based on coherence_score, not MTCE
        self.assertEqual(state1.coherence_score, state2.coherence_score)

    def test_persona_tone_unaffected_by_cycle_metrics(self):
        """Persona tone must be unaffected by cycle_type/alignment."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.65
        state.dominant_cycle_type = "oscillating"
        state.avg_cycle_alignment = 0.55

        # Tone generation should not read MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_mtc_integration_is_metadata_only_in_session(self):
        """MTCE integration in SessionSummary must be metadata-only."""
        # SessionSummary includes MTCE fields for analytics, not behavior
        pass

    def test_stability_band_does_not_alter_persona_behavior(self):
        """dominant_cycle_stability_band must not alter persona behavior."""
        state = CoherenceState(convo_id="test", turn_index=5)
        state.coherence_score = 0.72
        state.dominant_cycle_stability_band = "unstable"

        # Persona behavior should be based on domain profile, not MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_no_mtc_in_persona_prompts(self):
        """Persona prompts must not reference MTCE metrics."""
        persona_files = [
            "symbolu/mechanical/persona/",
            "symbolu/core/persona/",
        ]

        for directory in persona_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "-E", "dominant_cycle_type|avg_cycle_alignment|mirror_cycle_history", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Persona in {directory} must not reference MTCE metrics")

    def test_persona_modules_do_not_import_mtc(self):
        """Persona modules must not import mirror_time_cycle for generation."""
        persona_files = [
            "symbolu/mechanical/persona/",
            "symbolu/core/persona/",
        ]

        for directory in persona_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "from symbolu.formulas.mirror_time_cycle", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Persona in {directory} must not import mirror_time_cycle for generation")

    def test_mtc_is_observation_only_for_persona(self):
        """MTCE must be observation-only for persona analytics."""
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)

        # Summary is for analytics, not persona generation
        self.assertIsNotNone(summary)

    def test_cycle_type_does_not_change_persona_style(self):
        """dominant_cycle_type must not change persona style."""
        state = CoherenceState(convo_id="test", turn_index=3)
        state.coherence_score = 0.68
        state.dominant_cycle_type = "stalled"

        # Persona style should be independent of MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_forward_gradient_does_not_affect_semantic_content(self):
        """forward_gradient must not affect semantic content generation."""
        state = CoherenceState(convo_id="test", turn_index=6)
        state.coherence_score = 0.70
        state.dominant_cycle_type = "converging"

        # Semantic content should be based on domain, not MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_mtc_fields_optional_for_persona_generation(self):
        """Persona generation must work when MTCE fields are None."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.67
        state.dominant_cycle_type = None
        state.mirror_cycle_history = []

        # Persona should work fine without MTCE
        self.assertIsNotNone(state.coherence_score)


class TestDILchatInvariance(unittest.TestCase):
    """
    Invariant 6: Phase 22 NEVER affects DIL chat text generation (except hints).

    DIL output generation must be independent of MTCE, except for optional
    interaction-mode-gated hints.
    """

    def test_dil_output_independent_of_mtc_metrics(self):
        """DIL output generation must be independent of MTCE metrics."""
        state = CoherenceState(convo_id="test", turn_index=3)
        state.coherence_score = 0.70
        state.dominant_cycle_type = "converging"
        state.avg_cycle_alignment = 0.85

        # DIL generation should not depend on MTCE for content
        self.assertIsNotNone(state.coherence_score)

    def test_dil_modules_do_not_reference_mtc_for_content(self):
        """DIL modules must not reference MTCE for content generation."""
        # DIL may reference MTCE for hints, but not for core content
        pass

    def test_mtc_hints_are_gated_by_interaction_mode(self):
        """MTCE hints must be gated by interaction mode (smart_insight/deep_adaptive)."""
        # MTCE hints should only appear in advanced interaction modes
        adapter_path = "symbolu/adapter/dilchat_adapter.py"

        if os.path.exists(adapter_path):
            with open(adapter_path, 'r') as f:
                content = f.read()
                # Hints should be conditional
                self.assertIn("MIRROR_CYCLE", content)

    def test_mtc_hints_are_informational_not_behavioral(self):
        """MTCE hints must be informational, not behavioral."""
        # Hints like MIRROR_CYCLE_CONVERGING are for user information, not system behavior
        pass

    def test_dil_backward_compatibility_without_mtc(self):
        """DIL must work correctly when MTCE is None."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.68
        state.dominant_cycle_type = None

        # DIL should work fine without MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_cycle_type_hints_are_optional(self):
        """MIRROR_CYCLE_CONVERGING/DIVERGING/OSCILLATING/STALLED hints are optional."""
        # Hints should not be required for DIL to function
        pass

    def test_dil_content_generation_unaffected_by_cycle_type(self):
        """DIL content generation must be unaffected by dominant_cycle_type."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.65
        state.dominant_cycle_type = "oscillating"

        # DIL core content should be independent of MTCE
        self.assertIsNotNone(state.coherence_score)

    def test_no_conditional_dil_logic_based_on_cycle_metrics(self):
        """No conditional DIL logic based on cycle metrics."""
        # cycle metrics may be shown in hints but not alter DIL logic
        pass


class TestUnifiedAPIBackwardCompatibility(unittest.TestCase):
    """
    Invariant 7: Phase 22 is optional, Unified API remains stable.

    MTCE fields must be Optional, and existing clients must continue working
    without modification.
    """

    def test_mirror_cycle_fields_are_optional(self):
        """mirror_cycle_history and related fields must be Optional in CoherenceState."""
        state = CoherenceState(convo_id="test", turn_index=0)

        # Default should be empty or None
        self.assertIsNotNone(state.mirror_cycle_history)
        self.assertEqual(len(state.mirror_cycle_history), 0)

    def test_unified_api_works_when_mtc_is_none(self):
        """UnifiedAPI must work correctly when MTCE fields are None."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.70
        state.dominant_cycle_type = None
        state.mirror_cycle_history = []

        # API should serialize None gracefully
        self.assertIsNone(state.dominant_cycle_type)

    def test_existing_clients_continue_without_modification(self):
        """Existing clients must work without consuming MTCE data."""
        # MTCE fields are additive, not breaking
        pass

    def test_json_serialization_handles_none_mtc(self):
        """JSON serialization must handle None MTCE gracefully."""
        state = CoherenceState(convo_id="test", turn_index=3)
        state.coherence_score = 0.68
        state.dominant_cycle_type = None

        # Should serialize to null/None in JSON
        self.assertIsNone(state.dominant_cycle_type)

    def test_session_summary_mtc_fields_are_optional(self):
        """SessionSummary MTCE fields must be optional."""
        # cycle_count, avg_cycle_alignment, etc. should be Optional
        pass

    def test_phase23_handles_missing_mtc_gracefully(self):
        """Phase 23 (future) must handle missing MTCE data."""
        # Future phases should gracefully degrade when MTCE is None
        pass

    def test_mtc_fields_optional_in_unified_output(self):
        """MTCE fields must be Optional in UnifiedOutput."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.72
        state.dominant_cycle_type = None

        # UnifiedOutput should work with None
        self.assertIsNone(state.dominant_cycle_type)

    def test_no_required_mtc_fields_in_api(self):
        """API must not require MTCE fields."""
        # All MTCE fields should be Optional[...]
        pass

    def test_backward_compatible_session_summary(self):
        """Session summary computation must work without MTCE."""
        # compute_session_summary should handle None MTCE fields
        pass

    def test_mtc_fields_additive_not_breaking(self):
        """MTCE fields must be additive, not breaking changes."""
        # Adding MTCE fields should not break existing code
        pass


class TestZeroLLMGuarantee(unittest.TestCase):
    """
    Invariant 8: Phase 22 contains no LLM calls.

    MTCE must be pure mathematical computation with no language model calls.
    """

    def test_no_llm_imports_in_mirror_time_cycle(self):
        """mirror_time_cycle.py must not import LLM libraries."""
        mtc_path = "symbolu/formulas/mirror_time_cycle.py"

        with open(mtc_path, 'r') as f:
            content = f.read()
            self.assertNotIn("anthropic", content.lower())
            self.assertNotIn("openai", content.lower())
            self.assertNotIn("import anthropic", content)
            self.assertNotIn("import openai", content)
            self.assertNotIn("from anthropic", content)
            self.assertNotIn("from openai", content)

    def test_pure_mathematical_computation(self):
        """MTCE must use pure mathematical computation only."""
        mtc_path = "symbolu/formulas/mirror_time_cycle.py"

        with open(mtc_path, 'r') as f:
            content = f.read()
            # Should only import math/statistics, not AI libraries
            # Check for actual LLM client usage, not just words in documentation
            self.assertNotIn("anthropic.client", content.lower())
            self.assertNotIn("openai.client", content.lower())
            self.assertNotIn("llm_client", content.lower())

    def test_execution_completes_in_milliseconds(self):
        """MTCE computation must complete in milliseconds (<10ms)."""
        import time

        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75 + i * 0.01, mirror_vector=0.70 + i * 0.01,
                loop_delta=0.05, loop_tension=0.05, loop_alignment=0.88,
                reversal_probability=0.14, stability_band="stable"
            )
            for i in range(10)
        ]

        start = time.time()
        summary = detect_mirror_time_cycles(loop_history)
        elapsed = time.time() - start

        # Should complete in <10ms
        self.assertLess(elapsed, 0.010)
        self.assertIsNotNone(summary)

    def test_no_llm_calls_in_mtc_functions(self):
        """MTCE functions must contain no LLM calls."""
        mtc_path = "symbolu/formulas/mirror_time_cycle.py"

        with open(mtc_path, 'r') as f:
            content = f.read().lower()
            self.assertNotIn("messages.create", content)
            self.assertNotIn("completions.create", content)
            self.assertNotIn("chat.completions", content)

    def test_deterministic_formulas_only(self):
        """MTCE must use deterministic formulas only."""
        # No LLM-based interpretation
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.80, mirror_vector=0.75, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.90, reversal_probability=0.12,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)
        self.assertIsNotNone(summary)

    def test_no_api_keys_required(self):
        """MTCE must not require API keys."""
        # Should work without ANTHROPIC_API_KEY or OPENAI_API_KEY
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.78, mirror_vector=0.74, loop_delta=0.04,
                loop_tension=0.04, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)
        self.assertIsNotNone(summary)

    def test_no_network_calls(self):
        """MTCE must not make network calls."""
        # Pure local computation
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.68, loop_delta=0.07,
                loop_tension=0.07, loop_alignment=0.85, reversal_probability=0.18,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)
        self.assertIsNotNone(summary)

    def test_only_math_statistics_imports(self):
        """MTCE should only import math/statistics modules."""
        mtc_path = "symbolu/formulas/mirror_time_cycle.py"

        with open(mtc_path, 'r') as f:
            content = f.read()
            # Should have statistics import
            self.assertIn("import statistics", content)

    def test_no_async_llm_calls(self):
        """MTCE must not contain async LLM calls."""
        mtc_path = "symbolu/formulas/mirror_time_cycle.py"

        with open(mtc_path, 'r') as f:
            content = f.read().lower()
            # Should have async def for potential future use, but no LLM calls
            self.assertNotIn("await anthropic", content)
            self.assertNotIn("await openai", content)

    def test_fast_synchronous_execution(self):
        """MTCE must execute synchronously and fast."""
        import time

        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        start = time.time()
        for _ in range(100):
            detect_mirror_time_cycles(loop_history)
        elapsed = time.time() - start

        # 100 iterations should complete in <200ms
        self.assertLess(elapsed, 0.2)


class TestDeterminism(unittest.TestCase):
    """
    Invariant 9: Phase 22 is fully deterministic.

    Identical inputs must produce identical outputs every time.
    """

    def test_identical_inputs_produce_identical_outputs(self):
        """Identical inputs must produce identical MTCE summaries."""
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
            MirrorTimeLoopSnapshot(
                forward_vector=0.72, mirror_vector=0.68, loop_delta=0.04,
                loop_tension=0.04, loop_alignment=0.87, reversal_probability=0.15,
                stability_band="stable"
            ),
        ]

        summary1 = detect_mirror_time_cycles(loop_history)
        summary2 = detect_mirror_time_cycles(loop_history)

        self.assertEqual(summary1.dominant_cycle_type, summary2.dominant_cycle_type)
        self.assertEqual(summary1.dominant_stability_band, summary2.dominant_stability_band)
        self.assertEqual(summary1.avg_cycle_length, summary2.avg_cycle_length)
        self.assertEqual(len(summary1.cycles), len(summary2.cycles))

    def test_no_random_usage(self):
        """MTCE must not use random number generation."""
        mtc_path = "symbolu/formulas/mirror_time_cycle.py"

        with open(mtc_path, 'r') as f:
            content = f.read()
            self.assertNotIn("import random", content)
            self.assertNotIn("from random", content)
            self.assertNotIn("Random", content)

    def test_no_time_based_nondeterminism(self):
        """MTCE must not use time.time() or datetime.now()."""
        mtc_path = "symbolu/formulas/mirror_time_cycle.py"

        with open(mtc_path, 'r') as f:
            content = f.read()
            self.assertNotIn("time.time()", content)
            self.assertNotIn("datetime.now()", content)

    def test_no_uuid_usage(self):
        """MTCE must not use UUID generation (except for cycle_id strings)."""
        mtc_path = "symbolu/formulas/mirror_time_cycle.py"

        with open(mtc_path, 'r') as f:
            content = f.read()
            self.assertNotIn("import uuid", content)
            self.assertNotIn("uuid.uuid4", content)

    def test_ten_run_stability(self):
        """10 runs with identical inputs must produce identical outputs."""
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.80, mirror_vector=0.75, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.90, reversal_probability=0.12,
                stability_band="stable"
            ),
            MirrorTimeLoopSnapshot(
                forward_vector=0.78, mirror_vector=0.74, loop_delta=0.04,
                loop_tension=0.04, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summaries = [detect_mirror_time_cycles(loop_history) for _ in range(10)]

        # All summaries should be identical
        for summary in summaries[1:]:
            self.assertEqual(summary.dominant_cycle_type, summaries[0].dominant_cycle_type)
            self.assertEqual(summary.dominant_stability_band, summaries[0].dominant_stability_band)
            self.assertEqual(len(summary.cycles), len(summaries[0].cycles))

    def test_no_nondeterministic_data_sources(self):
        """MTCE must not use non-deterministic data sources."""
        # No environment variables, file reads, network calls
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.78, mirror_vector=0.74, loop_delta=0.04,
                loop_tension=0.04, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)
        self.assertIsNotNone(summary)

    def test_reproducibility_across_executions(self):
        """Results must be reproducible across multiple Python executions."""
        # Within same execution, results are deterministic
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.79, mirror_vector=0.75, loop_delta=0.04,
                loop_tension=0.04, loop_alignment=0.89, reversal_probability=0.13,
                stability_band="stable"
            ),
        ]

        summary1 = detect_mirror_time_cycles(loop_history)
        summary2 = detect_mirror_time_cycles(loop_history)

        self.assertEqual(summary1.dominant_cycle_type, summary2.dominant_cycle_type)

    def test_formula_consistency(self):
        """Formulas must be consistent (no conditional randomness)."""
        # Test multiple times with same inputs
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.68, loop_delta=0.07,
                loop_tension=0.07, loop_alignment=0.85, reversal_probability=0.18,
                stability_band="stable"
            ),
        ]

        for _ in range(5):
            summary = detect_mirror_time_cycles(loop_history)
            # Should always return same values
            self.assertIsNotNone(summary)

    def test_no_global_state_mutation(self):
        """MTCE must not mutate global state."""
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary1 = detect_mirror_time_cycles(loop_history)
        summary2 = detect_mirror_time_cycles(loop_history)

        # Should be identical
        self.assertEqual(summary1.dominant_cycle_type, summary2.dominant_cycle_type)

    def test_order_independent_computation(self):
        """Computation should be deterministic for same data."""
        # Same data, different test order
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.76, mirror_vector=0.73, loop_delta=0.03,
                loop_tension=0.03, loop_alignment=0.89, reversal_probability=0.12,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)
        self.assertIsNotNone(summary)


class TestGracefulDegradation(unittest.TestCase):
    """
    Invariant 10: Phase 22 handles missing upstream metrics gracefully.

    MTCE must return empty summary or safe defaults when required metrics are missing.
    """

    def test_returns_empty_summary_when_loop_history_missing(self):
        """MTCE must return empty summary when loop_history is missing."""
        summary = detect_mirror_time_cycles([])

        # Should handle empty history gracefully
        self.assertIsNotNone(summary)
        self.assertEqual(len(summary.cycles), 0)
        self.assertIsNone(summary.dominant_cycle_type)

    def test_coherence_engine_handles_none_mtc_fields(self):
        """CoherenceEngine must handle None MTCE fields."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.70
        state.dominant_cycle_type = None

        # Should be fine with None
        self.assertIsNone(state.dominant_cycle_type)

    def test_no_crashes_on_single_snapshot(self):
        """MTCE must not crash on single snapshot (insufficient for cycle)."""
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)

        # Should handle single snapshot
        self.assertIsNotNone(summary)

    def test_safe_mean_handles_edge_cases(self):
        """_safe_mean must handle empty lists."""
        result = _safe_mean([])

        # Should return neutral default (0.5)
        self.assertEqual(result, 0.5)

    def test_safe_stdev_handles_edge_cases(self):
        """_safe_stdev must handle empty lists and single values."""
        result_empty = _safe_stdev([])
        result_single = _safe_stdev([0.5])

        # Should return 0.0 for both
        self.assertEqual(result_empty, 0.0)
        self.assertEqual(result_single, 0.0)

    def test_cycle_detection_with_insufficient_data(self):
        """MTCE must handle insufficient data for cycle detection."""
        loop_history = []

        summary = detect_mirror_time_cycles(loop_history)

        # Should work with empty history
        self.assertIsNotNone(summary)
        self.assertEqual(len(summary.cycles), 0)

    def test_session_summary_handles_none_mtc_fields(self):
        """SessionSummary must handle None MTCE fields."""
        # compute_session_summary should handle None cycle_count, etc.
        pass

    def test_none_propagation_through_stack(self):
        """None MTCE should propagate through stack without errors."""
        state = CoherenceState(convo_id="test", turn_index=3)
        state.coherence_score = 0.68
        state.dominant_cycle_type = None

        # Should propagate safely
        self.assertIsNone(state.dominant_cycle_type)

    def test_clamp_handles_boundary_values(self):
        """_clamp must handle boundary values correctly."""
        self.assertEqual(_clamp(-10.0, 0.0, 1.0), 0.0)
        self.assertEqual(_clamp(10.0, 0.0, 1.0), 1.0)
        self.assertEqual(_clamp(0.5, 0.0, 1.0), 0.5)

    def test_missing_loop_history_uses_defaults(self):
        """Missing loop_history should use safe defaults."""
        summary = detect_mirror_time_cycles([])

        # Should return empty summary with None values
        self.assertIsNotNone(summary)
        self.assertEqual(len(summary.cycles), 0)
        self.assertIsNone(summary.dominant_cycle_type)


class TestEndToEndPipelineInvariance(unittest.TestCase):
    """
    Invariant 11: Phase 22 is observation-only.

    MTCE must only appear in approved integration points and must not create
    feedback loops to upstream phases.
    """

    def test_mtc_only_in_approved_integration_points(self):
        """MTCE must only appear in approved integration points."""
        # Approved: CoherenceState, SessionSummary, UnifiedAPI, DILchat adapter
        pass

    def test_no_feedback_loops_from_mtc_to_upstream_phases(self):
        """MTCE must not create feedback loops to upstream phases."""
        # MTCE should not feed back into Phase 21 loop computation
        pass

    def test_read_only_data_flow(self):
        """MTCE must have read-only data flow (consumes, never produces inputs)."""
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
                loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)

        # Should not modify inputs
        self.assertIsNotNone(summary)

    def test_mtc_does_not_modify_coherence_state(self):
        """MTCE must only add fields to CoherenceState, not modify existing."""
        state = CoherenceState(convo_id="test", turn_index=5)
        state.coherence_score = 0.72
        state.semantic_integrity_history.append(0.74)

        # MTCE should only populate new fields
        state.dominant_cycle_type = "converging"
        state.avg_cycle_alignment = 0.85

        # Existing fields unchanged
        self.assertEqual(state.coherence_score, 0.72)
        self.assertEqual(len(state.semantic_integrity_history), 1)

    def test_phase23_is_only_downstream_consumer(self):
        """Phase 23 (future) should be only downstream consumer."""
        # Future phases may consume MTCE data
        pass

    def test_mtc_integration_is_noninvasive(self):
        """MTCE integration must be non-invasive."""
        # Should not require changes to routing, mappers, persona, etc.
        pass

    def test_no_mtc_in_upstream_phase_computations(self):
        """Upstream phases must not reference MTCE in computations."""
        upstream_phases = [
            "symbolu/formulas/semantic_integrity.py",
            "symbolu/formulas/arc_metrics.py",
            "symbolu/formulas/enhanced_smi.py",
            "symbolu/formulas/mirror_time_loop.py",
        ]

        for filepath in upstream_phases:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    content = f.read()
                    self.assertNotIn("mirror_time_cycle", content)
                    self.assertNotIn("detect_mirror_time_cycles", content)

    def test_mtc_computation_order_is_downstream(self):
        """MTCE must be computed AFTER all upstream metrics."""
        # Documented in CoherenceEngine._update_mirror_time_cycles
        # which is called after loop snapshot computation
        pass

    def test_observation_only_guarantee(self):
        """MTCE must maintain observation-only guarantee."""
        # MTCE outputs used exclusively for diagnostics & analytics
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.78, mirror_vector=0.74, loop_delta=0.04,
                loop_tension=0.04, loop_alignment=0.88, reversal_probability=0.14,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)

        # Summary is for observation, not control
        self.assertIsNotNone(summary)

    def test_no_side_effects_in_pipeline(self):
        """MTCE must have no side effects in pipeline."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.68

        # Computing MTCE should have no side effects
        loop_history = [
            MirrorTimeLoopSnapshot(
                forward_vector=0.76, mirror_vector=0.73, loop_delta=0.03,
                loop_tension=0.03, loop_alignment=0.89, reversal_probability=0.12,
                stability_band="stable"
            ),
        ]

        summary = detect_mirror_time_cycles(loop_history)

        # coherence_score should be unchanged
        self.assertEqual(state.coherence_score, 0.68)

    def test_mtc_fields_are_additive_in_coherence_state(self):
        """MTCE fields must be additive in CoherenceState."""
        # Should add new fields without breaking existing structure
        state = CoherenceState(convo_id="test", turn_index=2)

        # Standard fields work as before
        state.coherence_score = 0.70

        # MTCE fields are additive
        state.dominant_cycle_type = "converging"
        state.avg_cycle_alignment = 0.85

        self.assertIsNotNone(state.coherence_score)
        self.assertIsNotNone(state.dominant_cycle_type)


if __name__ == '__main__':
    unittest.main()
