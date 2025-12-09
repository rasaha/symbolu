"""
Temporal Pipeline Snapshot Tests (v1.0)
========================================

Deterministic snapshot tests for temporal behavior of the Symbol-U pipeline.

These tests verify that multi-turn state and temporal evolution are stable
and deterministic across runs, including:
    - Bhava trajectories
    - Momentum and slope
    - Tension corridors
    - Recovery detection
    - Cross-domain interpretation

Test Categories:
    TEST 1 - Single-run temporal pipeline snapshot
    TEST 2 - Multi-turn deterministic replay snapshot

CRITICAL: These tests are LLM-free and fully deterministic.
All LLM-enhanced rendering is mocked to avoid API calls.
"""

import pytest
import json
from pathlib import Path
from typing import Any, Dict, List
from dataclasses import dataclass, field
from unittest.mock import patch, MagicMock

# Import snapshot utilities from renderer
from symbolu.renderer.tests.snapshot_utils import assert_snapshot

# Import Pipeline and models
from symbolu.mechanical.pipeline.orchestrator import SymbolUPipeline
from symbolu.mechanical.pipeline.models import (
    UserRequest,
    RenderedOutput,
    PipelineContext,
)

# Import Temporal tracking
from symbolu.temporal import TemporalBhavaTracker, CrossDomainIntelligence


# =============================================================================
# SNAPSHOT DIRECTORY
# =============================================================================

SNAPSHOT_DIR = Path(__file__).parent.parent / "snapshots"


# =============================================================================
# DETERMINISTIC MOCK FIXTURES
# =============================================================================

class DeterministicUUIDGenerator:
    """
    Generate deterministic UUIDs for testing.
    Ensures reproducible candidate IDs across test runs.
    """

    def __init__(self, prefix: str = "test") -> None:
        self.counter = 0
        self.prefix = prefix

    def generate(self) -> str:
        self.counter += 1
        return f"{self.prefix}_{self.counter:08d}"


@dataclass
class TemporalTurnResult:
    """
    Captures the result of a single temporal analysis turn.
    """
    turn_number: int
    input_text: str
    smi: float
    bhava_id: int
    bhava_direction: str
    kosha_id: int
    ontology_id: int
    trajectory_summary: Dict[str, Any] = field(default_factory=dict)
    momentum: Dict[str, Any] = field(default_factory=dict)
    tension_state: Dict[str, Any] = field(default_factory=dict)
    recovery_state: Dict[str, Any] = field(default_factory=dict)
    cross_domain_interpretation: Dict[str, Any] = field(default_factory=dict)


# Deterministic analysis results for the test conversation
# These values are designed to trigger temporal patterns:
# - rising SMI -> stability -> falling SMI
# - upward/downward Bhava shifts
# - tension corridor detection
# - recovery trajectory detection

DETERMINISTIC_ANALYSIS_RESULTS = [
    # Turn 1: "I'm very stressed today." - High stress, tense state
    {
        "smi": 0.78,
        "bhava_id": 3,
        "bhava_direction": "downward",
        "kosha_id": 2,
        "ontology_id": 3,
    },
    # Turn 2: "Things feel slightly better now." - Moderate stress, slight improvement
    {
        "smi": 0.62,
        "bhava_id": 4,
        "bhava_direction": "neutral",
        "kosha_id": 3,
        "ontology_id": 4,
    },
    # Turn 3: "I think I'm stabilizing." - Stability, balanced state
    {
        "smi": 0.48,
        "bhava_id": 5,
        "bhava_direction": "upward",
        "kosha_id": 4,
        "ontology_id": 5,
    },
    # Turn 4: "Now I feel I'm recovering gradually." - Recovery, improving state
    {
        "smi": 0.35,
        "bhava_id": 6,
        "bhava_direction": "upward",
        "kosha_id": 4,
        "ontology_id": 6,
    },
]


def temporal_turn_to_dict(turn: TemporalTurnResult) -> Dict[str, Any]:
    """Convert TemporalTurnResult to serializable dict."""
    return {
        "turn_number": turn.turn_number,
        "input_text": turn.input_text,
        "smi": turn.smi,
        "bhava_id": turn.bhava_id,
        "bhava_direction": turn.bhava_direction,
        "kosha_id": turn.kosha_id,
        "ontology_id": turn.ontology_id,
        "trajectory_summary": turn.trajectory_summary,
        "momentum": turn.momentum,
        "tension_state": turn.tension_state,
        "recovery_state": turn.recovery_state,
        "cross_domain_interpretation": turn.cross_domain_interpretation,
    }


def temporal_snapshot_to_string(
    turns: List[TemporalTurnResult],
    final_pattern_summary: Dict[str, Any],
) -> str:
    """
    Convert temporal analysis results to deterministic snapshot string.
    """
    lines = [
        "=" * 70,
        "TEMPORAL PIPELINE SNAPSHOT",
        "=" * 70,
        "",
        f"Total Turns: {len(turns)}",
        "",
    ]

    for turn in turns:
        lines.extend([
            "-" * 50,
            f"TURN {turn.turn_number}",
            "-" * 50,
            "",
            f"Input: {turn.input_text}",
            "",
            "Analysis:",
            f"  SMI: {turn.smi}",
            f"  Bhava ID: {turn.bhava_id}",
            f"  Bhava Direction: {turn.bhava_direction}",
            f"  Kosha ID: {turn.kosha_id}",
            f"  Ontology ID: {turn.ontology_id}",
            "",
            "Trajectory:",
            json.dumps(turn.trajectory_summary, indent=2, sort_keys=True),
            "",
            "Momentum:",
            json.dumps(turn.momentum, indent=2, sort_keys=True),
            "",
            "Tension State:",
            json.dumps(turn.tension_state, indent=2, sort_keys=True),
            "",
            "Recovery State:",
            json.dumps(turn.recovery_state, indent=2, sort_keys=True),
            "",
            "Cross-Domain Interpretation:",
            json.dumps(turn.cross_domain_interpretation, indent=2, sort_keys=True),
            "",
        ])

    lines.extend([
        "=" * 70,
        "FINAL PATTERN SUMMARY",
        "=" * 70,
        "",
        json.dumps(final_pattern_summary, indent=2, sort_keys=True),
        "",
        "=" * 70,
    ])

    return "\n".join(lines)


def temporal_snapshot_to_json(
    turns: List[TemporalTurnResult],
    trajectory: Dict[str, Any],
    momentum: Dict[str, Any],
    tension: Dict[str, Any],
    recovery: Dict[str, Any],
    cross_domain: Dict[str, Any],
) -> str:
    """
    Convert temporal analysis to JSON snapshot for structured comparison.
    """
    data = {
        "turns": [temporal_turn_to_dict(t) for t in turns],
        "trajectory": trajectory,
        "momentum": momentum,
        "tension": tension,
        "recovery": recovery,
        "cross_domain": cross_domain,
    }
    return json.dumps(data, indent=2, sort_keys=True)


def multiturn_replay_snapshot_to_json(
    run1_data: Dict[str, Any],
    run2_data: Dict[str, Any],
) -> str:
    """
    Convert two temporal runs to JSON snapshot for determinism verification.
    """
    data = {
        "run1": run1_data,
        "run2": run2_data,
    }
    return json.dumps(data, indent=2, sort_keys=True)


# =============================================================================
# MOCK LLM CLIENT
# =============================================================================

class MockLLMClient:
    """
    Mock LLM client that returns deterministic responses.
    Ensures no actual API calls are made during tests.
    """

    def create(self, *args, **kwargs):
        """Return mocked enhanced output."""
        return {"content": "MOCKED ENHANCED OUTPUT"}


# =============================================================================
# PIPELINE FIXTURE WITH TEMPORAL TRACKING
# =============================================================================

@pytest.fixture
def temporal_pipeline(monkeypatch):
    """
    Create a pipeline instance with mocked LLM and temporal tracking.

    Mocks:
        - LLM-enhanced renderer to avoid API calls
        - UUID generation for candidate IDs

    Provides:
        - Fresh TemporalBhavaTracker instance
        - CrossDomainIntelligence instance
    """
    # Mock the LLM client
    mock_llm = MockLLMClient()

    # Try to patch the LLM client if it exists
    try:
        import symbolu.renderer.llm_client as llm_module
        monkeypatch.setattr(llm_module, "create", mock_llm.create)
    except (ImportError, AttributeError):
        # LLM client may not exist or have different structure
        pass

    # Create pipeline
    pipeline = SymbolUPipeline()

    # UUID counter for deterministic IDs
    uuid_gen = DeterministicUUIDGenerator("temporal_candidate")

    def mock_generate_candidates(ctx, explain_log, activation_plan):
        """Generate candidates with deterministic IDs."""
        from symbolu.mechanical.fusion.schemas.candidate import Candidate, CandidateSource

        query_text = ctx.request.text
        domain = explain_log.get("meta", {}).get("domain", "general")

        candidates = [
            Candidate(
                id=f"hrm_{uuid_gen.generate()}",
                text=f"From a deeper perspective: {query_text}",
                source=CandidateSource.HRM,
                channel_scores={"hrm": 0.8, "lcm": 0.4, "moe": 0.3},
                domain=domain,
                relevance_score=0.7,
                confidence=0.8,
            ),
            Candidate(
                id=f"lcm_{uuid_gen.generate()}",
                text=f"To clarify: {query_text}",
                source=CandidateSource.LCM,
                channel_scores={"hrm": 0.3, "lcm": 0.9, "moe": 0.4},
                domain=domain,
                relevance_score=0.75,
                confidence=0.85,
            ),
            Candidate(
                id=f"moe_{uuid_gen.generate()}",
                text=f"Based on domain knowledge: {query_text}",
                source=CandidateSource.MOE,
                channel_scores={"hrm": 0.4, "lcm": 0.5, "moe": 0.85},
                domain=domain,
                relevance_score=0.7,
                confidence=0.75,
            ),
        ]

        return candidates

    # Patch the generate_candidates method
    pipeline._generate_candidates = mock_generate_candidates

    return pipeline


@pytest.fixture
def temporal_tracker():
    """
    Create a fresh TemporalBhavaTracker instance.
    """
    return TemporalBhavaTracker(window_size=10)


@pytest.fixture
def cross_domain_intel():
    """
    Create a CrossDomainIntelligence instance.
    """
    return CrossDomainIntelligence()


@pytest.fixture
def conversation_inputs() -> List[str]:
    """
    Standard multi-turn conversation inputs designed to trigger temporal patterns.

    Pattern progression:
        Turn 1: High stress (tense state)
        Turn 2: Slight improvement (stabilizing)
        Turn 3: Stability (balanced)
        Turn 4: Recovery (improving)
    """
    return [
        "I'm very stressed today.",
        "Things feel slightly better now.",
        "I think I'm stabilizing.",
        "Now I feel I'm recovering gradually.",
    ]


# =============================================================================
# TEST 1 - SINGLE-RUN TEMPORAL PIPELINE SNAPSHOT
# =============================================================================

class TestTemporalPipelineSnapshot:
    """
    Test temporal pipeline snapshot with single run.

    Produces a combined summary object containing:
        - turns: per-turn analysis results
        - trajectory: overall trajectory analysis
        - momentum: momentum indicators
        - tension: tension corridor analysis
        - recovery: recovery pattern analysis
        - cross_domain: cross-domain interpretations
    """

    def test_temporal_pipeline_snapshot(
        self,
        temporal_pipeline: SymbolUPipeline,
        temporal_tracker: TemporalBhavaTracker,
        cross_domain_intel: CrossDomainIntelligence,
        conversation_inputs: List[str],
    ):
        """
        Snapshot test for temporal pipeline with single conversation run.

        Expected behavior:
            - Tracks consciousness state evolution across turns
            - Detects trajectory trends (rising -> stable -> falling)
            - Identifies tension corridors
            - Recognizes recovery patterns
            - Provides cross-domain interpretations
        """
        turns: List[TemporalTurnResult] = []

        for turn_num, (input_text, analysis) in enumerate(
            zip(conversation_inputs, DETERMINISTIC_ANALYSIS_RESULTS),
            start=1
        ):
            # Add analysis to temporal tracker
            temporal_tracker.add_analysis(
                text=input_text,
                smi=analysis["smi"],
                bhava_id=analysis["bhava_id"],
                bhava_direction=analysis["bhava_direction"],
                kosha_id=analysis["kosha_id"],
                ontology_id=analysis["ontology_id"],
            )

            # Get pattern summary after this turn
            pattern_summary = temporal_tracker.get_pattern_summary()

            # Get cross-domain interpretation
            detected_patterns = cross_domain_intel.detect_pattern(
                smi=analysis["smi"],
                bhava_id=analysis["bhava_id"],
                bhava_direction=analysis["bhava_direction"],
                kosha_id=analysis["kosha_id"],
                ontology_id=analysis["ontology_id"],
                temporal_trend=pattern_summary["trajectory"]["trend"],
            )

            # Build cross-domain interpretation summary
            cross_domain_summary = {}
            if detected_patterns:
                top_pattern = detected_patterns[0]
                cross_domain_summary = {
                    "top_pattern": top_pattern[0],
                    "confidence": top_pattern[1],
                    "all_patterns": [
                        {"name": p[0], "confidence": p[1]}
                        for p in detected_patterns[:3]
                    ],
                }

                # Add domain-specific interpretation
                try:
                    domain_transfer = cross_domain_intel.transfer_pattern_to_domain(
                        pattern_name=top_pattern[0],
                        domain="psychology",
                    )
                    cross_domain_summary["psychology_interpretation"] = (
                        domain_transfer["interpretation"]
                    )
                except ValueError:
                    pass

            # Create turn result
            turn_result = TemporalTurnResult(
                turn_number=turn_num,
                input_text=input_text,
                smi=analysis["smi"],
                bhava_id=analysis["bhava_id"],
                bhava_direction=analysis["bhava_direction"],
                kosha_id=analysis["kosha_id"],
                ontology_id=analysis["ontology_id"],
                trajectory_summary=pattern_summary["trajectory"],
                momentum=pattern_summary["momentum"],
                tension_state=pattern_summary["tension"],
                recovery_state=pattern_summary["recovery"],
                cross_domain_interpretation=cross_domain_summary,
            )

            turns.append(turn_result)

        # Get final pattern summary
        final_summary = temporal_tracker.get_pattern_summary()

        # Convert to snapshot string
        snapshot_output = temporal_snapshot_to_string(turns, final_summary)

        # Assert against snapshot
        snapshot_path = SNAPSHOT_DIR / "temporal_pipeline.snap"
        assert_snapshot(snapshot_output, snapshot_path)

    def test_temporal_pipeline_json_snapshot(
        self,
        temporal_pipeline: SymbolUPipeline,
        temporal_tracker: TemporalBhavaTracker,
        cross_domain_intel: CrossDomainIntelligence,
        conversation_inputs: List[str],
    ):
        """
        JSON snapshot for structured temporal analysis comparison.
        """
        turns: List[TemporalTurnResult] = []

        for turn_num, (input_text, analysis) in enumerate(
            zip(conversation_inputs, DETERMINISTIC_ANALYSIS_RESULTS),
            start=1
        ):
            temporal_tracker.add_analysis(
                text=input_text,
                smi=analysis["smi"],
                bhava_id=analysis["bhava_id"],
                bhava_direction=analysis["bhava_direction"],
                kosha_id=analysis["kosha_id"],
                ontology_id=analysis["ontology_id"],
            )

            pattern_summary = temporal_tracker.get_pattern_summary()

            detected_patterns = cross_domain_intel.detect_pattern(
                smi=analysis["smi"],
                bhava_id=analysis["bhava_id"],
                bhava_direction=analysis["bhava_direction"],
                kosha_id=analysis["kosha_id"],
                ontology_id=analysis["ontology_id"],
                temporal_trend=pattern_summary["trajectory"]["trend"],
            )

            cross_domain_summary = {}
            if detected_patterns:
                top_pattern = detected_patterns[0]
                cross_domain_summary = {
                    "top_pattern": top_pattern[0],
                    "confidence": top_pattern[1],
                    "all_patterns": [
                        {"name": p[0], "confidence": p[1]}
                        for p in detected_patterns[:3]
                    ],
                }

            turn_result = TemporalTurnResult(
                turn_number=turn_num,
                input_text=input_text,
                smi=analysis["smi"],
                bhava_id=analysis["bhava_id"],
                bhava_direction=analysis["bhava_direction"],
                kosha_id=analysis["kosha_id"],
                ontology_id=analysis["ontology_id"],
                trajectory_summary=pattern_summary["trajectory"],
                momentum=pattern_summary["momentum"],
                tension_state=pattern_summary["tension"],
                recovery_state=pattern_summary["recovery"],
                cross_domain_interpretation=cross_domain_summary,
            )

            turns.append(turn_result)

        # Get final summary components
        final_summary = temporal_tracker.get_pattern_summary()

        # Get final cross-domain patterns
        final_analysis = DETERMINISTIC_ANALYSIS_RESULTS[-1]
        final_patterns = cross_domain_intel.detect_pattern(
            smi=final_analysis["smi"],
            bhava_id=final_analysis["bhava_id"],
            bhava_direction=final_analysis["bhava_direction"],
            kosha_id=final_analysis["kosha_id"],
            ontology_id=final_analysis["ontology_id"],
            temporal_trend=final_summary["trajectory"]["trend"],
        )

        cross_domain_final = {
            "detected_patterns": [
                {"name": p[0], "confidence": p[1]}
                for p in final_patterns
            ],
            "pattern_count": len(final_patterns),
        }

        # Convert to JSON snapshot
        snapshot_output = temporal_snapshot_to_json(
            turns=turns,
            trajectory=final_summary["trajectory"],
            momentum=final_summary["momentum"],
            tension=final_summary["tension"],
            recovery=final_summary["recovery"],
            cross_domain=cross_domain_final,
        )

        snapshot_path = SNAPSHOT_DIR / "temporal_pipeline_json.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 2 - MULTI-TURN DETERMINISTIC REPLAY SNAPSHOT
# =============================================================================

class TestTemporalMultiturnReplaySnapshot:
    """
    Test deterministic replay of temporal tracking.

    Runs the same conversation twice with fresh trackers and verifies
    that temporal signatures match exactly.
    """

    def test_temporal_multiturn_deterministic_replay(
        self,
        conversation_inputs: List[str],
    ):
        """
        Snapshot test for deterministic replay.

        Expected behavior:
            - Two independent runs produce identical temporal signatures
            - State evolution is reproducible
            - No randomness in temporal calculations
        """
        def run_temporal_analysis() -> Dict[str, Any]:
            """Run a complete temporal analysis and return results."""
            tracker = TemporalBhavaTracker(window_size=10)
            intel = CrossDomainIntelligence()
            turns_data = []

            for turn_num, (input_text, analysis) in enumerate(
                zip(conversation_inputs, DETERMINISTIC_ANALYSIS_RESULTS),
                start=1
            ):
                tracker.add_analysis(
                    text=input_text,
                    smi=analysis["smi"],
                    bhava_id=analysis["bhava_id"],
                    bhava_direction=analysis["bhava_direction"],
                    kosha_id=analysis["kosha_id"],
                    ontology_id=analysis["ontology_id"],
                )

                pattern_summary = tracker.get_pattern_summary()

                detected_patterns = intel.detect_pattern(
                    smi=analysis["smi"],
                    bhava_id=analysis["bhava_id"],
                    bhava_direction=analysis["bhava_direction"],
                    kosha_id=analysis["kosha_id"],
                    ontology_id=analysis["ontology_id"],
                    temporal_trend=pattern_summary["trajectory"]["trend"],
                )

                turn_data = {
                    "turn_number": turn_num,
                    "input_text": input_text,
                    "analysis": analysis,
                    "trajectory": pattern_summary["trajectory"],
                    "momentum": pattern_summary["momentum"],
                    "tension": pattern_summary["tension"],
                    "recovery": pattern_summary["recovery"],
                    "state": pattern_summary["state"],
                    "detected_patterns": [
                        {"name": p[0], "confidence": p[1]}
                        for p in detected_patterns[:3]
                    ],
                }

                turns_data.append(turn_data)

            final_summary = tracker.get_pattern_summary()

            return {
                "turns": turns_data,
                "final_state": final_summary["state"],
                "final_trajectory": final_summary["trajectory"],
                "final_momentum": final_summary["momentum"],
                "final_tension": final_summary["tension"],
                "final_recovery": final_summary["recovery"],
                "final_stats": final_summary["stats"],
            }

        # Run 1: First temporal analysis
        run1_data = run_temporal_analysis()

        # Run 2: Second temporal analysis (fresh tracker)
        run2_data = run_temporal_analysis()

        # Create combined snapshot
        snapshot_output = multiturn_replay_snapshot_to_json(run1_data, run2_data)

        # Assert against snapshot
        snapshot_path = SNAPSHOT_DIR / "temporal_multiturn.snap"
        assert_snapshot(snapshot_output, snapshot_path)

    def test_temporal_replay_determinism_verification(
        self,
        conversation_inputs: List[str],
    ):
        """
        Verify that two runs produce identical results (non-snapshot test).
        """
        def run_temporal_analysis():
            tracker = TemporalBhavaTracker(window_size=10)

            for input_text, analysis in zip(
                conversation_inputs, DETERMINISTIC_ANALYSIS_RESULTS
            ):
                tracker.add_analysis(
                    text=input_text,
                    smi=analysis["smi"],
                    bhava_id=analysis["bhava_id"],
                    bhava_direction=analysis["bhava_direction"],
                    kosha_id=analysis["kosha_id"],
                    ontology_id=analysis["ontology_id"],
                )

            return tracker.get_pattern_summary()

        run1 = run_temporal_analysis()
        run2 = run_temporal_analysis()

        # Verify exact match
        assert run1 == run2, (
            "Temporal analysis must be deterministic: two runs with same input "
            "should produce identical results"
        )


# =============================================================================
# TEST 3 - TEMPORAL STATE CLASSIFICATION TESTS
# =============================================================================

class TestTemporalStateClassification:
    """
    Verify temporal state classification behavior.
    """

    def test_tension_corridor_detection(self):
        """
        Verify tension corridor is detected when SMI stays high.
        """
        tracker = TemporalBhavaTracker(window_size=10)

        # Add multiple high-SMI entries to trigger tension corridor
        for i in range(4):
            tracker.add_analysis(
                text=f"High stress entry {i}",
                smi=0.75 + (i * 0.02),  # 0.75, 0.77, 0.79, 0.81
                bhava_id=3,
                bhava_direction="downward",
                kosha_id=2,
                ontology_id=3,
            )

        summary = tracker.get_pattern_summary()

        assert summary["tension"]["current"] is True, "Should detect current tension"
        assert summary["tension"]["corridor_length"] >= 2, (
            "Should have tension corridor of at least 2"
        )
        assert summary["state"] == "TENSE", "State should be TENSE"

    def test_recovery_trajectory_detection(self):
        """
        Verify recovery is detected when SMI drops from peak.
        """
        tracker = TemporalBhavaTracker(window_size=10)

        # Start with high SMI (peak)
        tracker.add_analysis(
            text="Peak stress",
            smi=0.85,
            bhava_id=2,
            bhava_direction="downward",
            kosha_id=1,
            ontology_id=2,
        )

        # Drop to lower SMI (recovery)
        tracker.add_analysis(
            text="Recovering",
            smi=0.55,
            bhava_id=5,
            bhava_direction="upward",
            kosha_id=4,
            ontology_id=5,
        )

        summary = tracker.get_pattern_summary()

        assert summary["recovery"]["active"] is True, "Should detect active recovery"
        assert summary["recovery"]["progress"] > 0, "Recovery progress should be > 0"

    def test_stable_state_detection(self):
        """
        Verify stable state is detected when SMI is consistent and moderate.
        """
        tracker = TemporalBhavaTracker(window_size=10)

        # Add consistent moderate SMI entries
        for i in range(4):
            tracker.add_analysis(
                text=f"Stable entry {i}",
                smi=0.45 + (i * 0.01),  # 0.45, 0.46, 0.47, 0.48
                bhava_id=5,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=4,
            )

        summary = tracker.get_pattern_summary()

        assert summary["state"] == "STABLE", "State should be STABLE"
        assert summary["trajectory"]["trend"] == "stable", "Trend should be stable"


# =============================================================================
# TEST 4 - CROSS-DOMAIN PATTERN DETECTION
# =============================================================================

class TestCrossDomainPatterns:
    """
    Verify cross-domain pattern detection behavior.
    """

    def test_acute_anxiety_pattern_detection(self):
        """
        Verify acute anxiety pattern is detected with high SMI and downward bhava.
        """
        intel = CrossDomainIntelligence()

        patterns = intel.detect_pattern(
            smi=0.85,
            bhava_id=2,
            bhava_direction="downward",
            kosha_id=1,
            ontology_id=2,
            temporal_trend="rising",
        )

        pattern_names = [p[0] for p in patterns]
        assert "acute_anxiety" in pattern_names, "Should detect acute_anxiety pattern"

    def test_recovery_trajectory_pattern_detection(self):
        """
        Verify recovery trajectory pattern is detected with improving metrics.
        """
        intel = CrossDomainIntelligence()

        patterns = intel.detect_pattern(
            smi=0.42,
            bhava_id=6,
            bhava_direction="upward",
            kosha_id=4,
            ontology_id=5,
            temporal_trend="falling",
        )

        pattern_names = [p[0] for p in patterns]
        assert "recovery_trajectory" in pattern_names, (
            "Should detect recovery_trajectory pattern"
        )

    def test_domain_transfer(self):
        """
        Verify pattern can be transferred to different domains.
        """
        intel = CrossDomainIntelligence()

        # Get transfer for psychology domain
        transfer = intel.transfer_pattern_to_domain(
            pattern_name="recovery_trajectory",
            domain="psychology",
        )

        assert transfer["pattern"] == "recovery_trajectory"
        assert transfer["domain"] == "psychology"
        assert transfer["category"] == "recovery"
        assert "interpretation" in transfer
        assert len(transfer["interpretation"]) > 0


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
