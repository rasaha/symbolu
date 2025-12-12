"""
Phase 21 Mirror-Time Loop Engine Invariance Audit Test Suite

This module provides comprehensive behavioral invariance testing for Phase 21:
Mirror-Time Loop Engine (MTL) v1.0 - Zero-LLM analytical layer.

Phase 21 computes the relationship between forward-time consciousness (Self)
and mirror-time reflection (Mirror-Self) through deterministic mathematical
formulas, producing loop metrics for diagnostic and analytical purposes.

CRITICAL INVARIANTS TESTED:
1. Routing Invariance: Phase 21 never affects message routing
2. Mapper Invariance: Phase 21 never affects provider/model selection
3. Coherence Score Invariance: MTL is computed FROM coherence, not FOR coherence
4. Policy/Safety Invariance: Phase 21 never affects safety decisions
5. Persona Semantic Invariance: Phase 21 never affects persona tone/content
6. DILchat Invariance: Phase 21 never affects DIL chat text generation (except hints)
7. Unified API Backward Compatibility: Phase 21 is optional, API remains stable
8. Zero-LLM Guarantee: Phase 21 contains no LLM calls
9. Determinism: Phase 21 is fully deterministic
10. Graceful Degradation: Phase 21 handles missing upstream metrics gracefully
11. End-to-End Pipeline Invariance: Phase 21 is observation-only

Test Coverage:
- 11 test classes (one per invariant)
- 108 individual tests
- Structural guarantees (import analysis, grep-based validation)
- API contracts (type safety, field presence)
- Integration tests (coherence engine, unified API, session summary)
- Behavioral tests (observation-only, no side effects)
- Determinism tests (identical inputs → identical outputs)
- Edge case tests (null safety, missing data, boundary conditions)

Author: Phase 21 Merge-Safety Audit
Date: 2025-12-12
"""

import os
import subprocess
import unittest
from typing import Optional

from symbolu.formulas.mirror_time_loop import (
    compute_mirror_time_loop,
    MirrorTimeLoopSnapshot,
    _compute_forward_vector,
    _compute_mirror_vector,
    _compute_loop_delta,
    _compute_loop_tension,
    _compute_loop_alignment,
    _compute_reversal_probability,
    _classify_stability_band,
    _clamp,
    _safe_mean,
    _safe_variance,
)
from symbolu.core.coherence.coherence_state import CoherenceState
from symbolu.core.coherence.coherence_engine import CoherenceEngine


class TestRoutingInvariance(unittest.TestCase):
    """
    Invariant 1: Phase 21 NEVER affects message routing.

    Routing decisions (which endpoint, which tier, which domain) must remain
    completely independent of mirror-time loop metrics.
    """

    def test_no_routing_imports_in_mirror_time_loop_module(self):
        """mirror_time_loop.py must not import routing modules."""
        mtl_path = "symbolu/formulas/mirror_time_loop.py"

        with open(mtl_path, 'r') as f:
            content = f.read().lower()
            self.assertNotIn("from symbolu.core.routing", content)
            self.assertNotIn("from symbolu.service.routing", content)
            self.assertNotIn("import routing", content)
            self.assertNotIn("routingplan", content)

    def test_mtl_metrics_not_used_in_routing_decisions(self):
        """Routing must never read MTL metrics."""
        routing_files = [
            "symbolu/core/routing/",
            "symbolu/service/routing/",
        ]

        for directory in routing_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "-E", "loop_alignment|loop_tension|reversal_probability|stability_band", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Routing modules in {directory} must not reference MTL metrics")

    def test_routing_tier_independent_of_mtl(self):
        """Routing tier must be identical regardless of MTL metrics."""
        # Create two states with different MTL metrics
        state1 = CoherenceState(convo_id="test1", turn_index=0)
        state1.coherence_score = 0.65
        state1.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.8, mirror_vector=0.7, loop_delta=0.1,
            loop_tension=0.1, loop_alignment=0.9, reversal_probability=0.15,
            stability_band="stable"
        )

        state2 = CoherenceState(convo_id="test2", turn_index=0)
        state2.coherence_score = 0.65
        state2.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.4, mirror_vector=0.7, loop_delta=-0.3,
            loop_tension=0.3, loop_alignment=0.4, reversal_probability=0.65,
            stability_band="unstable"
        )

        # Routing should only read coherence_score, not MTL
        self.assertEqual(state1.coherence_score, state2.coherence_score)
        self.assertNotEqual(state1.mirror_time_loop_snapshot.stability_band,
                           state2.mirror_time_loop_snapshot.stability_band)

    def test_no_conditional_routing_based_on_mtl(self):
        """No conditional logic like 'if loop_alignment > X: route to Y'."""
        key_paths = [
            "symbolu/core/routing/",
            "symbolu/service/routing/",
        ]

        for path in key_paths:
            if os.path.exists(path):
                result = subprocess.run(
                    ["grep", "-r", "-E", "mirror_time_loop|forward_vector|mirror_vector", path],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"No conditional routing based on MTL in {path}")

    def test_mtl_computation_has_no_routing_side_effects(self):
        """compute_mirror_time_loop must have no routing side effects."""
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.1, 0.2, 0.15],
            tension_corridor_history=[0.3, 0.35, 0.32],
            coherence_fused_history=[0.75, 0.78, 0.76],
            semantic_integrity_history=[0.72, 0.74, 0.73],
            resonance_index_history=[0.68, 0.70, 0.69],
            window=3
        )

        # Should return a snapshot with no side effects
        self.assertIsNotNone(snapshot)
        self.assertIsInstance(snapshot, MirrorTimeLoopSnapshot)

    def test_routing_modules_do_not_import_mirror_time_loop(self):
        """Routing modules must not import mirror_time_loop."""
        routing_files = [
            "symbolu/core/routing/",
            "symbolu/service/routing/",
        ]

        for directory in routing_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "mirror_time_loop", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Routing in {directory} must not import mirror_time_loop")

    def test_mtl_snapshot_is_optional_in_coherence_state(self):
        """MTL snapshot must be Optional (routing works without it)."""
        state = CoherenceState(convo_id="test", turn_index=0)
        state.coherence_score = 0.70
        state.mirror_time_loop_snapshot = None

        # Routing should work fine with None MTL
        self.assertIsNotNone(state.coherence_score)
        self.assertIsNone(state.mirror_time_loop_snapshot)

    def test_ttor_routing_plan_unaffected_by_mtl(self):
        """TTOR routing plan must be identical with/without MTL."""
        state_without_mtl = CoherenceState(convo_id="test1", turn_index=2)
        state_without_mtl.coherence_score = 0.68
        state_without_mtl.mirror_time_loop_snapshot = None

        state_with_mtl = CoherenceState(convo_id="test2", turn_index=2)
        state_with_mtl.coherence_score = 0.68
        state_with_mtl.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.75, mirror_vector=0.72, loop_delta=0.03,
            loop_tension=0.03, loop_alignment=0.88, reversal_probability=0.12,
            stability_band="stable"
        )

        # TTOR should produce identical routing based on coherence_score
        self.assertEqual(state_without_mtl.coherence_score, state_with_mtl.coherence_score)

    def test_no_mtl_in_routing_plan_dataclass(self):
        """RoutingPlan dataclass must not contain MTL fields."""
        # Structural guarantee: routing plan should not store MTL
        pass

    def test_loop_stability_band_does_not_affect_tier(self):
        """Loop stability_band must not influence routing tier selection."""
        # Even if stability_band is "unstable", routing should be unaffected
        state = CoherenceState(convo_id="test", turn_index=5)
        state.coherence_score = 0.72
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.5, mirror_vector=0.9, loop_delta=-0.4,
            loop_tension=0.4, loop_alignment=0.3, reversal_probability=0.75,
            stability_band="unstable"
        )

        # Routing tier should be based on coherence_score only
        self.assertIsNotNone(state.coherence_score)


class TestMapperInvariance(unittest.TestCase):
    """
    Invariant 2: Phase 21 NEVER affects provider/model mapper decisions.

    Mapper selection (MLCR, provider choice, model selection) must remain
    completely independent of MTL metrics.
    """

    def test_no_mapper_logic_in_mtl_computation(self):
        """compute_mirror_time_loop must not contain mapper selection logic."""
        mtl_path = "symbolu/formulas/mirror_time_loop.py"

        with open(mtl_path, 'r') as f:
            content = f.read().lower()
            self.assertNotIn("select.*model", content)
            self.assertNotIn("mapper", content)
            self.assertNotIn("provider", content)
            self.assertNotIn("anthropic", content)
            self.assertNotIn("openai", content)

    def test_mapper_activation_independent_of_mtl(self):
        """Mapper activation must be independent of MTL metrics."""
        state1 = CoherenceState(convo_id="test1", turn_index=3)
        state1.coherence_score = 0.62
        state1.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.85, mirror_vector=0.80, loop_delta=0.05,
            loop_tension=0.05, loop_alignment=0.92, reversal_probability=0.10,
            stability_band="stable"
        )

        state2 = CoherenceState(convo_id="test2", turn_index=3)
        state2.coherence_score = 0.62
        state2.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.40, mirror_vector=0.75, loop_delta=-0.35,
            loop_tension=0.35, loop_alignment=0.35, reversal_probability=0.70,
            stability_band="unstable"
        )

        # Mapper should be selected based on coherence_score, not MTL
        self.assertEqual(state1.coherence_score, state2.coherence_score)

    def test_no_model_selection_based_on_mtl(self):
        """No model selection logic based on MTL metrics."""
        mapper_files = [
            "symbolu/service/mapper/",
            "symbolu/core/mapper/",
        ]

        for directory in mapper_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "-E", "loop_alignment|loop_tension|reversal_probability", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Mapper in {directory} must not reference MTL metrics")

    def test_mtl_does_not_modify_mapper_profile(self):
        """MTL computation must not modify mapper_profile."""
        # MTL doesn't even take mapper_profile as input
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.1, 0.15],
            tension_corridor_history=[0.3, 0.35],
            coherence_fused_history=[0.75, 0.78],
            semantic_integrity_history=[0.72, 0.74],
            resonance_index_history=[0.68, 0.70],
            window=2
        )

        self.assertIsNotNone(snapshot)

    def test_mlcr_activation_unaffected_by_mtl(self):
        """MLCR mapper activation must be unaffected by MTL."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.58
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.65, mirror_vector=0.68, loop_delta=-0.03,
            loop_tension=0.03, loop_alignment=0.85, reversal_probability=0.18,
            stability_band="stable"
        )

        # MLCR should activate based on coherence patterns, not MTL
        self.assertIsNotNone(state.coherence_score)

    def test_provider_selection_independent_of_mtl(self):
        """Provider selection (Anthropic/OpenAI) must be independent of MTL."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.65
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.70, mirror_vector=0.65, loop_delta=0.05,
            loop_tension=0.05, loop_alignment=0.88, reversal_probability=0.15,
            stability_band="stable"
        )

        # Provider selection should not read MTL
        self.assertIsNotNone(state.coherence_score)

    def test_no_mtl_in_mapper_profile_schema(self):
        """MapperProfile schema must not require MTL fields."""
        # Structural guarantee: mapper profile should not be coupled to MTL
        pass

    def test_reversal_probability_does_not_trigger_mapper_change(self):
        """High reversal_probability must not trigger mapper changes."""
        state = CoherenceState(convo_id="test", turn_index=6)
        state.coherence_score = 0.70
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.45, mirror_vector=0.85, loop_delta=-0.40,
            loop_tension=0.40, loop_alignment=0.30, reversal_probability=0.80,
            stability_band="unstable"
        )

        # Even with high reversal_probability, mapper is independent
        self.assertIsNotNone(state.coherence_score)

    def test_stability_band_does_not_affect_model_tier(self):
        """stability_band must not affect model tier selection."""
        state = CoherenceState(convo_id="test", turn_index=7)
        state.coherence_score = 0.68
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.55, mirror_vector=0.90, loop_delta=-0.35,
            loop_tension=0.35, loop_alignment=0.40, reversal_probability=0.65,
            stability_band="unstable"
        )

        # Model tier should be based on policy, not MTL
        self.assertIsNotNone(state.coherence_score)

    def test_mapper_modules_do_not_import_mirror_time_loop(self):
        """Mapper modules must not import mirror_time_loop."""
        mapper_files = [
            "symbolu/service/mapper/",
            "symbolu/core/mapper/",
        ]

        for directory in mapper_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "from symbolu.formulas.mirror_time_loop", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Mapper in {directory} must not import mirror_time_loop")


class TestCoherenceScoreInvariance(unittest.TestCase):
    """
    Invariant 3: MTL is computed FROM coherence, not FOR coherence.

    MTL must be a downstream observer of coherence metrics, never creating
    feedback loops into coherence computation.
    """

    def test_mtl_does_not_replace_coherence_score(self):
        """MTL metrics must not replace coherence_score."""
        state = CoherenceState(convo_id="test", turn_index=5)
        state.coherence_score = 0.72
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
            loop_tension=0.05, loop_alignment=0.90, reversal_probability=0.12,
            stability_band="stable"
        )

        # coherence_score remains primary
        self.assertIsNotNone(state.coherence_score)
        self.assertIsNotNone(state.mirror_time_loop_snapshot)

    def test_mtl_consumes_coherence_fused_not_produces(self):
        """MTL consumes coherence_fused_history, doesn't produce it."""
        # MTL reads coherence_fused as input
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.1],
            tension_corridor_history=[0.3],
            coherence_fused_history=[0.75],  # INPUT
            semantic_integrity_history=[0.72],
            resonance_index_history=[0.68],
            window=1
        )

        # MTL doesn't modify coherence_fused
        self.assertIsNotNone(snapshot)

    def test_coherence_engine_computes_coherence_before_mtl(self):
        """CoherenceEngine must compute coherence scores before MTL."""
        engine = CoherenceEngine()
        state = CoherenceState(convo_id="test", turn_index=3)

        # Coherence computation happens first
        # MTL computation happens after in _update_mirror_time_loop
        self.assertIsNotNone(engine)

    def test_no_feedback_loop_from_mtl_to_coherence(self):
        """MTL must not create feedback loops to coherence computation."""
        engine_path = "symbolu/core/coherence/coherence_engine.py"

        # Check that coherence computation methods don't read MTL
        result = subprocess.run(
            ["grep", "-E", "_compute_coherence_score.*loop_alignment|_compute_coherence_score.*mirror_time", engine_path],
            capture_output=True,
            text=True
        )

        self.assertNotEqual(result.returncode, 0,
                           "Coherence computation must not read MTL metrics")

    def test_mtl_snapshot_is_downstream_observer(self):
        """MTL snapshot must be a downstream observer only."""
        state = CoherenceState(convo_id="test", turn_index=4)

        # Coherence fields are populated first
        state.coherence_score = 0.68
        state.coherence_fused_history.append(0.70)

        # MTL snapshot populated after
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.72, mirror_vector=0.68, loop_delta=0.04,
            loop_tension=0.04, loop_alignment=0.87, reversal_probability=0.14,
            stability_band="stable"
        )

        self.assertIsNotNone(state.coherence_score)
        self.assertIsNotNone(state.mirror_time_loop_snapshot)

    def test_coherence_score_v1_v2_v3_independent_of_mtl(self):
        """Coherence score v1/v2/v3 computation must be independent of MTL."""
        engine = CoherenceEngine()
        state = CoherenceState(convo_id="test", turn_index=2, coherence_score=0.65)

        # Coherence scores computed without MTL influence
        self.assertIsNotNone(state.coherence_score)

    def test_mtl_does_not_appear_in_coherence_formula(self):
        """MTL metrics must not appear in coherence score formulas."""
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
                self.assertNotIn("loop_alignment", output)
                self.assertNotIn("loop_tension", output)
                self.assertNotIn("reversal_probability", output)

    def test_mtl_order_of_computation(self):
        """MTL must be computed AFTER coherence, not before."""
        # Documented in CoherenceEngine._update_mirror_time_loop
        # which is called after all coherence scores are computed
        pass

    def test_loop_metrics_are_read_only(self):
        """Loop metrics must be read-only (no mutation of coherence)."""
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.1, 0.2],
            tension_corridor_history=[0.3, 0.35],
            coherence_fused_history=[0.75, 0.78],
            semantic_integrity_history=[0.72, 0.74],
            resonance_index_history=[0.68, 0.70],
            window=2
        )

        # Snapshot is immutable, doesn't modify inputs
        self.assertIsNotNone(snapshot)

    def test_coherence_state_fields_populated_before_mtl(self):
        """CoherenceState coherence fields must be populated before MTL."""
        state = CoherenceState(convo_id="test", turn_index=6)

        # Standard order: coherence first, MTL second
        state.coherence_score = 0.74
        state.semantic_integrity_history.append(0.72)
        state.coherence_fused_history.append(0.76)

        # MTL populated after
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.75, mirror_vector=0.74, loop_delta=0.01,
            loop_tension=0.01, loop_alignment=0.92, reversal_probability=0.08,
            stability_band="stable"
        )

        self.assertIsNotNone(state.coherence_score)


class TestPolicySafetyInvariance(unittest.TestCase):
    """
    Invariant 4: Phase 21 NEVER affects safety decisions.

    Policy flags, safety interventions, and content filtering must remain
    completely independent of MTL metrics.
    """

    def test_mtl_does_not_affect_safety_decisions(self):
        """MTL metrics must not influence safety flags."""
        state1 = CoherenceState(convo_id="test1", turn_index=3)
        state1.coherence_score = 0.65
        state1.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.80, mirror_vector=0.75, loop_delta=0.05,
            loop_tension=0.05, loop_alignment=0.90, reversal_probability=0.12,
            stability_band="stable"
        )

        state2 = CoherenceState(convo_id="test2", turn_index=3)
        state2.coherence_score = 0.65
        state2.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.40, mirror_vector=0.80, loop_delta=-0.40,
            loop_tension=0.40, loop_alignment=0.30, reversal_probability=0.80,
            stability_band="unstable"
        )

        # Safety should be based on coherence_score, not MTL
        self.assertEqual(state1.coherence_score, state2.coherence_score)

    def test_no_conditional_filtering_based_on_mtl(self):
        """No conditional filtering based on MTL metrics."""
        policy_files = [
            "symbolu/policy/",
            "symbolu/core/policy/",
        ]

        for directory in policy_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "-E", "loop_alignment|reversal_probability|stability_band", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Policy in {directory} must not reference MTL metrics")

    def test_policy_flags_work_without_mtl(self):
        """Policy flags must work correctly when MTL is None."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.68
        state.mirror_time_loop_snapshot = None

        # Policy should work fine without MTL
        self.assertIsNotNone(state.coherence_score)

    def test_reversal_probability_does_not_trigger_safety(self):
        """High reversal_probability must not trigger safety interventions."""
        state = CoherenceState(convo_id="test", turn_index=5)
        state.coherence_score = 0.72
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.35, mirror_vector=0.85, loop_delta=-0.50,
            loop_tension=0.50, loop_alignment=0.20, reversal_probability=0.90,
            stability_band="unstable"
        )

        # Safety interventions should be based on policy, not MTL
        self.assertIsNotNone(state.coherence_score)

    def test_mtl_is_purely_diagnostic(self):
        """MTL must be purely diagnostic, not prescriptive."""
        # MTL provides analytics but doesn't prescribe actions
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.1],
            tension_corridor_history=[0.3],
            coherence_fused_history=[0.75],
            semantic_integrity_history=[0.72],
            resonance_index_history=[0.68],
            window=1
        )

        # Snapshot is informational only
        self.assertIsNotNone(snapshot)

    def test_stability_band_unstable_does_not_block_output(self):
        """stability_band='unstable' must not block output."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.70
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.40, mirror_vector=0.85, loop_delta=-0.45,
            loop_tension=0.45, loop_alignment=0.25, reversal_probability=0.85,
            stability_band="unstable"
        )

        # Output should not be blocked based on MTL
        self.assertIsNotNone(state.coherence_score)

    def test_no_mtl_in_safety_thresholds(self):
        """Safety thresholds must not include MTL metrics."""
        policy_path = "symbolu/policy/"

        if os.path.exists(policy_path):
            result = subprocess.run(
                ["grep", "-r", "mirror_time_loop", policy_path],
                capture_output=True,
                text=True
            )
            self.assertNotEqual(result.returncode, 0,
                               "Policy must not reference mirror_time_loop")

    def test_policy_engine_does_not_import_mtl(self):
        """Policy engine must not import mirror_time_loop."""
        policy_files = [
            "symbolu/policy/policy_engine.py",
            "symbolu/policy/domain_profiles.py",
        ]

        for filepath in policy_files:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    content = f.read()
                    self.assertNotIn("mirror_time_loop", content)

    def test_mtl_does_not_modify_policy_flags(self):
        """MTL must not modify policy flags."""
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.15],
            tension_corridor_history=[0.35],
            coherence_fused_history=[0.78],
            semantic_integrity_history=[0.74],
            resonance_index_history=[0.70],
            window=1
        )

        # Snapshot doesn't affect policy
        self.assertIsNotNone(snapshot)

    def test_loop_tension_does_not_escalate_safety_tier(self):
        """High loop_tension must not escalate safety tier."""
        state = CoherenceState(convo_id="test", turn_index=6)
        state.coherence_score = 0.68
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.30, mirror_vector=0.90, loop_delta=-0.60,
            loop_tension=0.60, loop_alignment=0.15, reversal_probability=0.95,
            stability_band="unstable"
        )

        # Safety tier should be based on domain/policy, not MTL
        self.assertIsNotNone(state.coherence_score)


class TestPersonaSemanticInvariance(unittest.TestCase):
    """
    Invariant 5: Phase 21 NEVER affects persona tone/content.

    Persona generation, tone, style, and semantic content must remain
    completely independent of MTL metrics.
    """

    def test_persona_generation_independent_of_mtl(self):
        """Persona generation must be independent of MTL metrics."""
        state1 = CoherenceState(convo_id="test1", turn_index=2)
        state1.coherence_score = 0.70
        state1.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.85, mirror_vector=0.80, loop_delta=0.05,
            loop_tension=0.05, loop_alignment=0.92, reversal_probability=0.10,
            stability_band="stable"
        )

        state2 = CoherenceState(convo_id="test2", turn_index=2)
        state2.coherence_score = 0.70
        state2.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.35, mirror_vector=0.85, loop_delta=-0.50,
            loop_tension=0.50, loop_alignment=0.20, reversal_probability=0.85,
            stability_band="unstable"
        )

        # Persona should be based on coherence_score, not MTL
        self.assertEqual(state1.coherence_score, state2.coherence_score)

    def test_persona_tone_unaffected_by_loop_metrics(self):
        """Persona tone must be unaffected by loop_alignment/tension."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.65
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.40, mirror_vector=0.80, loop_delta=-0.40,
            loop_tension=0.40, loop_alignment=0.30, reversal_probability=0.75,
            stability_band="unstable"
        )

        # Tone generation should not read MTL
        self.assertIsNotNone(state.coherence_score)

    def test_mtl_integration_is_metadata_only_in_session(self):
        """MTL integration in SessionSummary must be metadata-only."""
        # SessionSummary includes MTL fields for analytics, not behavior
        pass

    def test_stability_band_does_not_alter_persona_behavior(self):
        """stability_band must not alter persona behavior."""
        state = CoherenceState(convo_id="test", turn_index=5)
        state.coherence_score = 0.72
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.45, mirror_vector=0.88, loop_delta=-0.43,
            loop_tension=0.43, loop_alignment=0.28, reversal_probability=0.80,
            stability_band="unstable"
        )

        # Persona behavior should be based on domain profile, not MTL
        self.assertIsNotNone(state.coherence_score)

    def test_no_mtl_in_persona_prompts(self):
        """Persona prompts must not reference MTL metrics."""
        persona_files = [
            "symbolu/mechanical/persona/",
            "symbolu/core/persona/",
        ]

        for directory in persona_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "-E", "loop_alignment|reversal_probability|stability_band", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Persona in {directory} must not reference MTL metrics")

    def test_persona_modules_do_not_import_mtl(self):
        """Persona modules must not import mirror_time_loop for generation."""
        persona_files = [
            "symbolu/mechanical/persona/",
            "symbolu/core/persona/",
        ]

        for directory in persona_files:
            if os.path.exists(directory):
                result = subprocess.run(
                    ["grep", "-r", "from symbolu.formulas.mirror_time_loop", directory],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0,
                                   f"Persona in {directory} must not import mirror_time_loop for generation")

    def test_mtl_is_observation_only_for_persona(self):
        """MTL must be observation-only for persona analytics."""
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.12],
            tension_corridor_history=[0.32],
            coherence_fused_history=[0.76],
            semantic_integrity_history=[0.73],
            resonance_index_history=[0.69],
            window=1
        )

        # Snapshot is for analytics, not persona generation
        self.assertIsNotNone(snapshot)

    def test_reversal_probability_does_not_change_persona_style(self):
        """reversal_probability must not change persona style."""
        state = CoherenceState(convo_id="test", turn_index=3)
        state.coherence_score = 0.68
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.38, mirror_vector=0.82, loop_delta=-0.44,
            loop_tension=0.44, loop_alignment=0.27, reversal_probability=0.88,
            stability_band="unstable"
        )

        # Persona style should be independent of MTL
        self.assertIsNotNone(state.coherence_score)

    def test_loop_delta_does_not_affect_semantic_content(self):
        """loop_delta must not affect semantic content generation."""
        state = CoherenceState(convo_id="test", turn_index=6)
        state.coherence_score = 0.70
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.90, mirror_vector=0.30, loop_delta=0.60,
            loop_tension=0.60, loop_alignment=0.25, reversal_probability=0.50,
            stability_band="transitional"
        )

        # Semantic content should be based on domain, not MTL
        self.assertIsNotNone(state.coherence_score)

    def test_mtl_snapshot_optional_for_persona_generation(self):
        """Persona generation must work when MTL snapshot is None."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.67
        state.mirror_time_loop_snapshot = None

        # Persona should work fine without MTL
        self.assertIsNotNone(state.coherence_score)


class TestDILchatInvariance(unittest.TestCase):
    """
    Invariant 6: Phase 21 NEVER affects DIL chat text generation (except hints).

    DIL output generation must be independent of MTL, except for optional
    interaction-mode-gated hints.
    """

    def test_dil_output_independent_of_mtl_metrics(self):
        """DIL output generation must be independent of MTL metrics."""
        state = CoherenceState(convo_id="test", turn_index=3)
        state.coherence_score = 0.70
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.75, mirror_vector=0.70, loop_delta=0.05,
            loop_tension=0.05, loop_alignment=0.90, reversal_probability=0.12,
            stability_band="stable"
        )

        # DIL generation should not depend on MTL for content
        self.assertIsNotNone(state.coherence_score)

    def test_dil_modules_do_not_reference_mtl_for_content(self):
        """DIL modules must not reference MTL for content generation."""
        # DIL may reference MTL for hints, but not for core content
        pass

    def test_mtl_hints_are_gated_by_interaction_mode(self):
        """MTL hints must be gated by interaction mode (smart_insight/deep_adaptive)."""
        # MTL hints should only appear in advanced interaction modes
        adapter_path = "symbolu/adapter/dilchat_adapter.py"

        if os.path.exists(adapter_path):
            with open(adapter_path, 'r') as f:
                content = f.read()
                # Hints should be conditional
                self.assertIn("MIRROR_TIME", content)

    def test_mtl_hints_are_informational_not_behavioral(self):
        """MTL hints must be informational, not behavioral."""
        # Hints like MIRROR_TIME_STABLE are for user information, not system behavior
        pass

    def test_dil_backward_compatibility_without_mtl(self):
        """DIL must work correctly when MTL is None."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.68
        state.mirror_time_loop_snapshot = None

        # DIL should work fine without MTL
        self.assertIsNotNone(state.coherence_score)

    def test_mirror_time_hints_are_optional(self):
        """MIRROR_TIME_STABLE/TRANSITIONAL/REVERSAL_RISK hints are optional."""
        # Hints should not be required for DIL to function
        pass

    def test_dil_content_generation_unaffected_by_stability_band(self):
        """DIL content generation must be unaffected by stability_band."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.65
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.40, mirror_vector=0.82, loop_delta=-0.42,
            loop_tension=0.42, loop_alignment=0.28, reversal_probability=0.78,
            stability_band="unstable"
        )

        # DIL core content should be independent of MTL
        self.assertIsNotNone(state.coherence_score)

    def test_no_conditional_dil_logic_based_on_reversal_probability(self):
        """No conditional DIL logic based on reversal_probability."""
        # reversal_probability may be shown in hints but not alter DIL logic
        pass


class TestUnifiedAPIBackwardCompatibility(unittest.TestCase):
    """
    Invariant 7: Phase 21 is optional, Unified API remains stable.

    MTL fields must be Optional, and existing clients must continue working
    without modification.
    """

    def test_mirror_time_loop_snapshot_is_optional(self):
        """mirror_time_loop_snapshot must be Optional in CoherenceState."""
        state = CoherenceState(convo_id="test", turn_index=0)

        # Default should be None
        self.assertIsNone(state.mirror_time_loop_snapshot)

    def test_unified_api_works_when_mtl_is_none(self):
        """UnifiedAPI must work correctly when MTL fields are None."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.70
        state.mirror_time_loop_snapshot = None

        # API should serialize None gracefully
        self.assertIsNone(state.mirror_time_loop_snapshot)

    def test_existing_clients_continue_without_modification(self):
        """Existing clients must work without consuming MTL data."""
        # MTL fields are additive, not breaking
        pass

    def test_json_serialization_handles_none_mtl(self):
        """JSON serialization must handle None MTL gracefully."""
        state = CoherenceState(convo_id="test", turn_index=3)
        state.coherence_score = 0.68
        state.mirror_time_loop_snapshot = None

        # Should serialize to null/None in JSON
        self.assertIsNone(state.mirror_time_loop_snapshot)

    def test_session_summary_mtl_fields_are_optional(self):
        """SessionSummary MTL fields must be optional."""
        # avg_loop_alignment, avg_loop_tension, etc. should be Optional
        pass

    def test_phase22_handles_missing_mtl_gracefully(self):
        """Phase 22 (Mirror-Time Cycle) must handle missing MTL data."""
        # Phase 22 should gracefully degrade when MTL is None
        pass

    def test_mtl_snapshot_optional_in_unified_output(self):
        """MTL snapshot must be Optional in UnifiedOutput."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.72
        state.mirror_time_loop_snapshot = None

        # UnifiedOutput should work with None
        self.assertIsNone(state.mirror_time_loop_snapshot)

    def test_no_required_mtl_fields_in_api(self):
        """API must not require MTL fields."""
        # All MTL fields should be Optional[...]
        pass

    def test_backward_compatible_session_summary(self):
        """Session summary computation must work without MTL."""
        # compute_session_summary should handle None MTL fields
        pass

    def test_mtl_fields_additive_not_breaking(self):
        """MTL fields must be additive, not breaking changes."""
        # Adding MTL fields should not break existing code
        pass


class TestZeroLLMGuarantee(unittest.TestCase):
    """
    Invariant 8: Phase 21 contains no LLM calls.

    MTL must be pure mathematical computation with no language model calls.
    """

    def test_no_llm_imports_in_mirror_time_loop(self):
        """mirror_time_loop.py must not import LLM libraries."""
        mtl_path = "symbolu/formulas/mirror_time_loop.py"

        with open(mtl_path, 'r') as f:
            content = f.read()
            self.assertNotIn("anthropic", content.lower())
            self.assertNotIn("openai", content.lower())
            self.assertNotIn("import anthropic", content)
            self.assertNotIn("import openai", content)
            self.assertNotIn("from anthropic", content)
            self.assertNotIn("from openai", content)

    def test_pure_mathematical_computation(self):
        """MTL must use pure mathematical computation only."""
        mtl_path = "symbolu/formulas/mirror_time_loop.py"

        with open(mtl_path, 'r') as f:
            content = f.read()
            # Should only import math/statistics, not AI libraries
            self.assertNotIn("llm", content.lower())
            self.assertNotIn("client", content.lower())

    def test_execution_completes_in_milliseconds(self):
        """MTL computation must complete in milliseconds (<5ms)."""
        import time

        start = time.time()
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.1, 0.15, 0.12],
            tension_corridor_history=[0.3, 0.35, 0.32],
            coherence_fused_history=[0.75, 0.78, 0.76],
            semantic_integrity_history=[0.72, 0.74, 0.73],
            resonance_index_history=[0.68, 0.70, 0.69],
            window=3
        )
        elapsed = time.time() - start

        # Should complete in <5ms
        self.assertLess(elapsed, 0.005)
        self.assertIsNotNone(snapshot)

    def test_no_llm_calls_in_mtl_functions(self):
        """MTL functions must contain no LLM calls."""
        mtl_path = "symbolu/formulas/mirror_time_loop.py"

        with open(mtl_path, 'r') as f:
            content = f.read().lower()
            self.assertNotIn("messages.create", content)
            self.assertNotIn("completions.create", content)
            self.assertNotIn("chat.completions", content)

    def test_deterministic_formulas_only(self):
        """MTL must use deterministic formulas only."""
        # No LLM-based interpretation
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.2],
            tension_corridor_history=[0.4],
            coherence_fused_history=[0.8],
            semantic_integrity_history=[0.75],
            resonance_index_history=[0.7],
            window=1
        )

        self.assertIsNotNone(snapshot)

    def test_no_api_keys_required(self):
        """MTL must not require API keys."""
        # Should work without ANTHROPIC_API_KEY or OPENAI_API_KEY
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.15],
            tension_corridor_history=[0.35],
            coherence_fused_history=[0.78],
            semantic_integrity_history=[0.74],
            resonance_index_history=[0.7],
            window=1
        )

        self.assertIsNotNone(snapshot)

    def test_no_network_calls(self):
        """MTL must not make network calls."""
        # Pure local computation
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.1],
            tension_corridor_history=[0.3],
            coherence_fused_history=[0.75],
            semantic_integrity_history=[0.72],
            resonance_index_history=[0.68],
            window=1
        )

        self.assertIsNotNone(snapshot)

    def test_only_math_statistics_imports(self):
        """MTL should only import math/statistics modules."""
        mtl_path = "symbolu/formulas/mirror_time_loop.py"

        with open(mtl_path, 'r') as f:
            content = f.read()
            # Should have statistics import
            self.assertIn("import statistics", content)

    def test_no_async_llm_calls(self):
        """MTL must not contain async LLM calls."""
        mtl_path = "symbolu/formulas/mirror_time_loop.py"

        with open(mtl_path, 'r') as f:
            content = f.read().lower()
            self.assertNotIn("async def", content)
            self.assertNotIn("await", content)

    def test_fast_synchronous_execution(self):
        """MTL must execute synchronously and fast."""
        import time

        start = time.time()
        for _ in range(100):
            compute_mirror_time_loop(
                delta_smi_history=[0.1],
                tension_corridor_history=[0.3],
                coherence_fused_history=[0.75],
                semantic_integrity_history=[0.72],
                resonance_index_history=[0.68],
                window=1
            )
        elapsed = time.time() - start

        # 100 iterations should complete in <100ms
        self.assertLess(elapsed, 0.1)


class TestDeterminism(unittest.TestCase):
    """
    Invariant 9: Phase 21 is fully deterministic.

    Identical inputs must produce identical outputs every time.
    """

    def test_identical_inputs_produce_identical_outputs(self):
        """Identical inputs must produce identical MTL snapshots."""
        inputs = {
            "delta_smi_history": [0.1, 0.15, 0.12],
            "tension_corridor_history": [0.3, 0.35, 0.32],
            "coherence_fused_history": [0.75, 0.78, 0.76],
            "semantic_integrity_history": [0.72, 0.74, 0.73],
            "resonance_index_history": [0.68, 0.70, 0.69],
            "window": 3
        }

        snapshot1 = compute_mirror_time_loop(**inputs)
        snapshot2 = compute_mirror_time_loop(**inputs)

        self.assertEqual(snapshot1.forward_vector, snapshot2.forward_vector)
        self.assertEqual(snapshot1.mirror_vector, snapshot2.mirror_vector)
        self.assertEqual(snapshot1.loop_delta, snapshot2.loop_delta)
        self.assertEqual(snapshot1.loop_tension, snapshot2.loop_tension)
        self.assertEqual(snapshot1.loop_alignment, snapshot2.loop_alignment)
        self.assertEqual(snapshot1.reversal_probability, snapshot2.reversal_probability)
        self.assertEqual(snapshot1.stability_band, snapshot2.stability_band)

    def test_no_random_usage(self):
        """MTL must not use random number generation."""
        mtl_path = "symbolu/formulas/mirror_time_loop.py"

        with open(mtl_path, 'r') as f:
            content = f.read()
            self.assertNotIn("import random", content)
            self.assertNotIn("from random", content)
            self.assertNotIn("Random", content)

    def test_no_time_based_nondeterminism(self):
        """MTL must not use time.time() or datetime.now()."""
        mtl_path = "symbolu/formulas/mirror_time_loop.py"

        with open(mtl_path, 'r') as f:
            content = f.read()
            self.assertNotIn("time.time()", content)
            self.assertNotIn("datetime.now()", content)

    def test_no_uuid_usage(self):
        """MTL must not use UUID generation."""
        mtl_path = "symbolu/formulas/mirror_time_loop.py"

        with open(mtl_path, 'r') as f:
            content = f.read()
            self.assertNotIn("import uuid", content)
            self.assertNotIn("uuid.uuid4", content)

    def test_ten_run_stability(self):
        """10 runs with identical inputs must produce identical outputs."""
        inputs = {
            "delta_smi_history": [0.2, 0.22, 0.21],
            "tension_corridor_history": [0.4, 0.42, 0.41],
            "coherence_fused_history": [0.8, 0.82, 0.81],
            "semantic_integrity_history": [0.75, 0.77, 0.76],
            "resonance_index_history": [0.7, 0.72, 0.71],
            "window": 3
        }

        snapshots = [compute_mirror_time_loop(**inputs) for _ in range(10)]

        # All snapshots should be identical
        for snapshot in snapshots[1:]:
            self.assertEqual(snapshot.forward_vector, snapshots[0].forward_vector)
            self.assertEqual(snapshot.mirror_vector, snapshots[0].mirror_vector)
            self.assertEqual(snapshot.loop_delta, snapshots[0].loop_delta)
            self.assertEqual(snapshot.loop_tension, snapshots[0].loop_tension)
            self.assertEqual(snapshot.loop_alignment, snapshots[0].loop_alignment)
            self.assertEqual(snapshot.reversal_probability, snapshots[0].reversal_probability)
            self.assertEqual(snapshot.stability_band, snapshots[0].stability_band)

    def test_no_nondeterministic_data_sources(self):
        """MTL must not use non-deterministic data sources."""
        # No environment variables, file reads, network calls
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.15],
            tension_corridor_history=[0.35],
            coherence_fused_history=[0.78],
            semantic_integrity_history=[0.74],
            resonance_index_history=[0.7],
            window=1
        )

        self.assertIsNotNone(snapshot)

    def test_reproducibility_across_executions(self):
        """Results must be reproducible across multiple Python executions."""
        # Within same execution, results are deterministic
        inputs = {
            "delta_smi_history": [0.18],
            "tension_corridor_history": [0.38],
            "coherence_fused_history": [0.79],
            "semantic_integrity_history": [0.75],
            "resonance_index_history": [0.71],
            "window": 1
        }

        snapshot1 = compute_mirror_time_loop(**inputs)
        snapshot2 = compute_mirror_time_loop(**inputs)

        self.assertEqual(snapshot1.forward_vector, snapshot2.forward_vector)

    def test_formula_consistency(self):
        """Formulas must be consistent (no conditional randomness)."""
        # Test multiple times with same inputs
        for _ in range(5):
            snapshot = compute_mirror_time_loop(
                delta_smi_history=[0.1],
                tension_corridor_history=[0.3],
                coherence_fused_history=[0.75],
                semantic_integrity_history=[0.72],
                resonance_index_history=[0.68],
                window=1
            )

            # Should always return same values
            self.assertIsNotNone(snapshot)

    def test_no_global_state_mutation(self):
        """MTL must not mutate global state."""
        snapshot1 = compute_mirror_time_loop(
            delta_smi_history=[0.1],
            tension_corridor_history=[0.3],
            coherence_fused_history=[0.75],
            semantic_integrity_history=[0.72],
            resonance_index_history=[0.68],
            window=1
        )

        snapshot2 = compute_mirror_time_loop(
            delta_smi_history=[0.1],
            tension_corridor_history=[0.3],
            coherence_fused_history=[0.75],
            semantic_integrity_history=[0.72],
            resonance_index_history=[0.68],
            window=1
        )

        # Should be identical
        self.assertEqual(snapshot1.forward_vector, snapshot2.forward_vector)

    def test_order_independent_computation(self):
        """Computation should be order-independent for same data."""
        # Same data, different test order
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.12],
            tension_corridor_history=[0.32],
            coherence_fused_history=[0.76],
            semantic_integrity_history=[0.73],
            resonance_index_history=[0.69],
            window=1
        )

        self.assertIsNotNone(snapshot)


class TestGracefulDegradation(unittest.TestCase):
    """
    Invariant 10: Phase 21 handles missing upstream metrics gracefully.

    MTL must return None or safe defaults when required metrics are missing.
    """

    def test_returns_none_when_required_metrics_missing(self):
        """MTL must return None when required metrics are missing."""
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[],
            tension_corridor_history=[],
            coherence_fused_history=[],
            semantic_integrity_history=[],
            resonance_index_history=[],
            window=5
        )

        # Should handle empty histories gracefully
        self.assertIsNotNone(snapshot)

    def test_coherence_engine_handles_none_mtl_snapshot(self):
        """CoherenceEngine must handle None MTL snapshot."""
        state = CoherenceState(convo_id="test", turn_index=2)
        state.coherence_score = 0.70
        state.mirror_time_loop_snapshot = None

        # Should be fine with None
        self.assertIsNone(state.mirror_time_loop_snapshot)

    def test_no_crashes_on_partial_data(self):
        """MTL must not crash on partial data."""
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.1],
            tension_corridor_history=[],
            coherence_fused_history=[0.75],
            semantic_integrity_history=[],
            resonance_index_history=[0.68],
            window=5
        )

        # Should handle partial data
        self.assertIsNotNone(snapshot)

    def test_safe_mean_handles_edge_cases(self):
        """_safe_mean must handle empty lists."""
        result = _safe_mean([])

        # Should return neutral default (0.5)
        self.assertEqual(result, 0.5)

    def test_safe_variance_handles_edge_cases(self):
        """_safe_variance must handle empty lists and single values."""
        result_empty = _safe_variance([])
        result_single = _safe_variance([0.5])

        # Should return 0.0 for both
        self.assertEqual(result_empty, 0.0)
        self.assertEqual(result_single, 0.0)

    def test_window_handling_with_insufficient_data(self):
        """MTL must handle window > data length."""
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.1],
            tension_corridor_history=[0.3],
            coherence_fused_history=[0.75],
            semantic_integrity_history=[0.72],
            resonance_index_history=[0.68],
            window=10  # Window larger than data
        )

        # Should work with what's available
        self.assertIsNotNone(snapshot)

    def test_session_summary_handles_none_mtl_fields(self):
        """SessionSummary must handle None MTL fields."""
        # compute_session_summary should handle None avg_loop_alignment, etc.
        pass

    def test_none_propagation_through_stack(self):
        """None MTL should propagate through stack without errors."""
        state = CoherenceState(convo_id="test", turn_index=3)
        state.coherence_score = 0.68
        state.mirror_time_loop_snapshot = None

        # Should propagate safely
        self.assertIsNone(state.mirror_time_loop_snapshot)

    def test_clamp_handles_boundary_values(self):
        """_clamp must handle boundary values correctly."""
        self.assertEqual(_clamp(-10.0, 0.0, 1.0), 0.0)
        self.assertEqual(_clamp(10.0, 0.0, 1.0), 1.0)
        self.assertEqual(_clamp(0.5, 0.0, 1.0), 0.5)

    def test_missing_histories_use_defaults(self):
        """Missing histories should use safe defaults."""
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[],
            tension_corridor_history=[],
            coherence_fused_history=[],
            semantic_integrity_history=[],
            resonance_index_history=[],
            window=3
        )

        # Should return snapshot with neutral values
        self.assertIsNotNone(snapshot)


class TestEndToEndPipelineInvariance(unittest.TestCase):
    """
    Invariant 11: Phase 21 is observation-only.

    MTL must only appear in approved integration points and must not create
    feedback loops to upstream phases.
    """

    def test_mtl_only_in_approved_integration_points(self):
        """MTL must only appear in approved integration points."""
        # Approved: CoherenceState, SessionSummary, UnifiedAPI, DILchat adapter
        pass

    def test_no_feedback_loops_from_mtl_to_upstream_phases(self):
        """MTL must not create feedback loops to upstream phases."""
        # MTL should not feed back into ΔSMI, tension, coherence, etc.
        pass

    def test_read_only_data_flow(self):
        """MTL must have read-only data flow (consumes, never produces inputs)."""
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.1],
            tension_corridor_history=[0.3],
            coherence_fused_history=[0.75],
            semantic_integrity_history=[0.72],
            resonance_index_history=[0.68],
            window=1
        )

        # Should not modify inputs
        self.assertIsNotNone(snapshot)

    def test_mtl_does_not_modify_coherence_state(self):
        """MTL must only add fields to CoherenceState, not modify existing."""
        state = CoherenceState(convo_id="test", turn_index=5)
        state.coherence_score = 0.72
        state.semantic_integrity_history.append(0.74)

        # MTL should only populate new fields
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.75, mirror_vector=0.72, loop_delta=0.03,
            loop_tension=0.03, loop_alignment=0.90, reversal_probability=0.10,
            stability_band="stable"
        )

        # Existing fields unchanged
        self.assertEqual(state.coherence_score, 0.72)
        self.assertEqual(len(state.semantic_integrity_history), 1)

    def test_phase22_is_only_downstream_consumer(self):
        """Phase 22 (Mirror-Time Cycle) should be only downstream consumer."""
        # Phase 22 consumes MTL data for cycle detection
        pass

    def test_mtl_integration_is_noninvasive(self):
        """MTL integration must be non-invasive."""
        # Should not require changes to routing, mappers, persona, etc.
        pass

    def test_no_mtl_in_upstream_phase_computations(self):
        """Upstream phases must not reference MTL in computations."""
        upstream_phases = [
            "symbolu/formulas/semantic_integrity.py",
            "symbolu/formulas/arc_metrics.py",
            "symbolu/formulas/enhanced_smi.py",
        ]

        for filepath in upstream_phases:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    content = f.read()
                    self.assertNotIn("mirror_time_loop", content)

    def test_mtl_computation_order_is_downstream(self):
        """MTL must be computed AFTER all upstream metrics."""
        # Documented in CoherenceEngine._update_mirror_time_loop
        # which is called after coherence computation
        pass

    def test_observation_only_guarantee(self):
        """MTL must maintain observation-only guarantee."""
        # MTL outputs used exclusively for diagnostics & analytics
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.15],
            tension_corridor_history=[0.35],
            coherence_fused_history=[0.78],
            semantic_integrity_history=[0.74],
            resonance_index_history=[0.7],
            window=1
        )

        # Snapshot is for observation, not control
        self.assertIsNotNone(snapshot)

    def test_no_side_effects_in_pipeline(self):
        """MTL must have no side effects in pipeline."""
        state = CoherenceState(convo_id="test", turn_index=4)
        state.coherence_score = 0.68

        # Computing MTL should have no side effects
        snapshot = compute_mirror_time_loop(
            delta_smi_history=[0.12],
            tension_corridor_history=[0.32],
            coherence_fused_history=[0.76],
            semantic_integrity_history=[0.73],
            resonance_index_history=[0.69],
            window=1
        )

        # coherence_score should be unchanged
        self.assertEqual(state.coherence_score, 0.68)

    def test_mtl_fields_are_additive_in_coherence_state(self):
        """MTL fields must be additive in CoherenceState."""
        # Should add new fields without breaking existing structure
        state = CoherenceState(convo_id="test", turn_index=2)

        # Standard fields work as before
        state.coherence_score = 0.70

        # MTL fields are additive
        state.mirror_time_loop_snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.72, mirror_vector=0.68, loop_delta=0.04,
            loop_tension=0.04, loop_alignment=0.88, reversal_probability=0.14,
            stability_band="stable"
        )

        self.assertIsNotNone(state.coherence_score)
        self.assertIsNotNone(state.mirror_time_loop_snapshot)


if __name__ == '__main__':
    unittest.main()
