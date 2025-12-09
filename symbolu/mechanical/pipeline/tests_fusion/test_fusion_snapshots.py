"""
Fusion Engine Snapshot Tests (v1.0)
=====================================

Deterministic snapshot tests for FusionEngine.
These tests lock the behavioral contract of the Fusion layer.

Test Categories:
    1. Standard fusion mode snapshot
    2. Symbolic-heavy mode snapshot

Key Properties Tested:
    - Candidate scoring across HRM/LCM/MoE channels
    - Conflict resolution behavior
    - Routing decisions
    - Explainability output structure
    - No mutation of input structures

CRITICAL: These tests are LLM-free and fully deterministic.
"""

import pytest
import json
from pathlib import Path
from typing import Dict, Any, List

# Import snapshot utilities from renderer
from symbolu.renderer.tests.snapshot_utils import assert_snapshot

# Import FusionEngine and schemas
from symbolu.mechanical.fusion.fusion.fusion_engine import FusionEngine
from symbolu.mechanical.fusion.schemas.candidate import Candidate, CandidateSource
from symbolu.mechanical.fusion.schemas.fusion_result import FusionContext, FusionResult


# =============================================================================
# SNAPSHOT DIRECTORY
# =============================================================================

SNAPSHOT_DIR = Path(__file__).parent.parent / "snapshots"


# =============================================================================
# DETERMINISTIC TEST FIXTURES
# =============================================================================

def create_standard_candidate(
    candidate_id: str,
    text: str,
    source: CandidateSource = CandidateSource.RAG,
    hrm: float = 0.5,
    lcm: float = 0.5,
    moe: float = 0.5,
    domain: str = "technical",
    confidence: float = 0.8
) -> Candidate:
    """
    Create a deterministic candidate for testing.
    No randomness, timestamps, or UUIDs.
    """
    return Candidate(
        id=candidate_id,
        text=text,
        source=source,
        channel_scores={"hrm": hrm, "lcm": lcm, "moe": moe},
        domain=domain,
        relevance_score=0.75,
        confidence=confidence,
        kosha_signature=[0.1, 0.2, 0.5, 0.15, 0.05],
        ontology_signature=[0.4, 0.6],
        smi=0.15,
        metadata={
            "source_type": source.value,
            "processing_timestamp": "deterministic_test"
        }
    )


def create_standard_fusion_context(
    tier: str = "HYBRID",
    intent: str = "how",
    domain: str = "technical",
    regulated: bool = False
) -> FusionContext:
    """
    Create a deterministic FusionContext for testing.
    """
    return FusionContext(
        tier=tier,
        intent=intent,
        domain=domain,
        entropy={"total_entropy": 0.35, "semantic_entropy": 0.32, "ontology_entropy": 0.38},
        ontology_mass={"upper": 0.4, "lower": 0.6},
        user_id="test_user_deterministic",
        conversation_history=[
            "User asked a technical question",
            "System provided initial analysis"
        ],
        regulated_mode=regulated,
        latency_budget_ms=1000.0,
        safety_thresholds={"content_safety": 0.95, "domain_safety": 0.90},
        user_preferences={"verbosity": "medium", "formality": "professional"}
    )


def create_symbolic_fusion_context() -> FusionContext:
    """
    Create a FusionContext biased toward symbolic processing.
    """
    return FusionContext(
        tier="UPPER",
        intent="why",
        domain="spiritual",
        entropy={"total_entropy": 0.68, "semantic_entropy": 0.72, "ontology_entropy": 0.64},
        ontology_mass={"upper": 0.75, "lower": 0.25},
        user_id="test_user_symbolic",
        conversation_history=[
            "User seeking meaning and purpose",
            "Deep philosophical inquiry"
        ],
        regulated_mode=False,
        latency_budget_ms=2000.0,
        safety_thresholds={"content_safety": 0.90, "domain_safety": 0.85},
        user_preferences={"verbosity": "high", "formality": "casual"}
    )


def create_standard_candidates() -> List[Candidate]:
    """
    Create a set of deterministic candidates for standard fusion testing.
    """
    return [
        create_standard_candidate(
            candidate_id="candidate_rag_001",
            text="Based on the analysis of available data, the recommended approach "
                 "involves systematic evaluation of key metrics followed by iterative "
                 "refinement of the strategy.",
            source=CandidateSource.RAG,
            hrm=0.72,
            lcm=0.85,
            moe=0.68,
            domain="technical",
            confidence=0.88
        ),
        create_standard_candidate(
            candidate_id="candidate_hrm_001",
            text="The underlying pattern suggests a deeper structural consideration "
                 "where symbolic reasoning can illuminate hidden relationships "
                 "between the observed phenomena.",
            source=CandidateSource.HRM,
            hrm=0.91,
            lcm=0.65,
            moe=0.45,
            domain="analytical",
            confidence=0.79
        ),
        create_standard_candidate(
            candidate_id="candidate_moe_001",
            text="Domain experts recommend following established protocols with "
                 "specific attention to industry best practices and regulatory "
                 "compliance requirements.",
            source=CandidateSource.MOE,
            hrm=0.55,
            lcm=0.78,
            moe=0.92,
            domain="technical",
            confidence=0.85
        ),
        create_standard_candidate(
            candidate_id="candidate_lcm_001",
            text="Clear and concise explanation: the process involves three main "
                 "steps that build upon each other to achieve the desired outcome.",
            source=CandidateSource.LCM,
            hrm=0.48,
            lcm=0.94,
            moe=0.62,
            domain="general",
            confidence=0.82
        )
    ]


def create_symbolic_candidates() -> List[Candidate]:
    """
    Create candidates biased toward symbolic/philosophical content.
    """
    return [
        create_standard_candidate(
            candidate_id="candidate_symbolic_001",
            text="The question itself contains the seed of its answer. Consider "
                 "how the seeker and the sought are intertwined in the fabric "
                 "of understanding.",
            source=CandidateSource.HRM,
            hrm=0.95,
            lcm=0.72,
            moe=0.35,
            domain="spiritual",
            confidence=0.84
        ),
        create_standard_candidate(
            candidate_id="candidate_symbolic_002",
            text="Meaning emerges from the interplay of apparent opposites. "
                 "What seems contradictory at one level becomes unified "
                 "at a deeper level of awareness.",
            source=CandidateSource.HRM,
            hrm=0.92,
            lcm=0.68,
            moe=0.28,
            domain="philosophical",
            confidence=0.81
        ),
        create_standard_candidate(
            candidate_id="candidate_practical_001",
            text="To explore these questions, start with daily contemplation "
                 "practice. Set aside 15 minutes each morning for reflection.",
            source=CandidateSource.MOE,
            hrm=0.55,
            lcm=0.88,
            moe=0.75,
            domain="spiritual",
            confidence=0.78
        )
    ]


def fusion_result_to_snapshot_string(result: FusionResult) -> str:
    """
    Convert FusionResult to deterministic snapshot string.
    Formats the output in a human-readable, deterministic format.
    """
    # Sort candidates by ID for deterministic output
    ranked_candidates_sorted = sorted(
        [c.to_dict() for c in result.ranked_candidates],
        key=lambda c: c["id"]
    )

    # Build snapshot structure
    snapshot_data = {
        "selected_candidate": {
            "id": result.selected_candidate.id,
            "text": result.selected_candidate.text,
            "source": result.selected_candidate.source.value,
            "channel_scores": result.selected_candidate.channel_scores,
            "confidence": result.selected_candidate.confidence
        },
        "fusion_score": round(result.fusion_score, 4),
        "routing": result.routing,
        "metadata": result.metadata,
        "ranked_candidate_ids": [c["id"] for c in ranked_candidates_sorted]
    }

    lines = [
        "=" * 70,
        "FUSION ENGINE SNAPSHOT",
        "=" * 70,
        "",
        "--- SELECTED CANDIDATE ---",
        f"ID: {snapshot_data['selected_candidate']['id']}",
        f"Source: {snapshot_data['selected_candidate']['source']}",
        f"Channel Scores: {json.dumps(snapshot_data['selected_candidate']['channel_scores'], sort_keys=True)}",
        f"Confidence: {snapshot_data['selected_candidate']['confidence']}",
        "",
        "Text:",
        snapshot_data['selected_candidate']['text'],
        "",
        "--- FUSION SCORE ---",
        f"Score: {snapshot_data['fusion_score']}",
        "",
        "--- ROUTING DECISIONS ---",
        json.dumps(snapshot_data['routing'], indent=2, sort_keys=True),
        "",
        "--- METADATA ---",
        json.dumps(snapshot_data['metadata'], indent=2, sort_keys=True),
        "",
        "--- RANKED CANDIDATES (by ID) ---",
        json.dumps(snapshot_data['ranked_candidate_ids'], indent=2),
        "",
        "=" * 70
    ]

    return "\n".join(lines)


def fusion_result_to_full_snapshot_string(result: FusionResult) -> str:
    """
    Convert FusionResult to full deterministic snapshot including explain log.
    """
    base_snapshot = fusion_result_to_snapshot_string(result)

    # Add explain section if available
    if result.explain:
        explain_lines = [
            "",
            "--- EXPLANATION LOG ---",
            json.dumps(result.explain, indent=2, sort_keys=True, default=str),
            "",
            "=" * 70
        ]
        return base_snapshot + "\n".join(explain_lines)

    return base_snapshot


# =============================================================================
# TEST 1: STANDARD FUSION MODE SNAPSHOT
# =============================================================================

class TestFusionStandardSnapshot:
    """
    Test standard fusion mode with balanced channel weights.

    Default weights: HRM=0.4, LCM=0.3, MoE=0.3

    Characteristics:
        - Balanced scoring across all channels
        - Standard conflict resolution
        - Auto routing mode
    """

    def test_fusion_standard_snapshot(self):
        """
        Snapshot test for standard fusion with default weights.

        Expected behavior:
            - Candidate with best weighted score selected
            - Clear winner or conflict resolution applied
            - Routing decisions generated
            - Full explainability output
        """
        # Create engine with default weights
        engine = FusionEngine(
            channel_weights={"hrm": 0.4, "lcm": 0.3, "moe": 0.3},
            enable_explanations=True,
            debug_mode=False
        )

        # Create deterministic inputs
        candidates = create_standard_candidates()
        context = create_standard_fusion_context()

        # Run fusion
        result = engine.fuse(candidates, context)

        # Convert to snapshot string
        snapshot_output = fusion_result_to_snapshot_string(result)

        # Assert against snapshot
        snapshot_path = SNAPSHOT_DIR / "fusion_standard.snap"
        assert_snapshot(snapshot_output, snapshot_path)

    def test_fusion_standard_with_explanations_snapshot(self):
        """
        Snapshot test verifying explanation generation.

        Expected behavior:
            - Complete explanation log generated
            - Scoring breakdown per candidate
            - Resolution reason documented
        """
        engine = FusionEngine(
            channel_weights={"hrm": 0.4, "lcm": 0.3, "moe": 0.3},
            enable_explanations=True
        )

        candidates = create_standard_candidates()
        context = create_standard_fusion_context()

        result = engine.fuse(candidates, context)

        # Verify explanation exists
        assert result.explain is not None
        assert len(result.explain) > 0

        snapshot_output = fusion_result_to_full_snapshot_string(result)
        snapshot_path = SNAPSHOT_DIR / "fusion_standard_explained.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 2: SYMBOLIC-HEAVY FUSION MODE SNAPSHOT
# =============================================================================

class TestFusionSymbolicSnapshot:
    """
    Test symbolic-heavy fusion mode with HRM-biased weights.

    Weights: HRM=0.6, LCM=0.25, MoE=0.15

    Characteristics:
        - Favors high-reasoning candidates
        - UPPER tier context
        - Symbolic/philosophical domain
    """

    def test_fusion_symbolic_snapshot(self):
        """
        Snapshot test for symbolic-heavy fusion.

        Expected behavior:
            - HRM-scored candidates favored
            - Symbolic candidates selected
            - Appropriate routing for symbolic content
        """
        # Create engine with HRM-biased weights
        engine = FusionEngine(
            channel_weights={"hrm": 0.6, "lcm": 0.25, "moe": 0.15},
            enable_explanations=True,
            debug_mode=False
        )

        # Create symbolic context and candidates
        candidates = create_symbolic_candidates()
        context = create_symbolic_fusion_context()

        # Run fusion
        result = engine.fuse(candidates, context)

        # Convert to snapshot string
        snapshot_output = fusion_result_to_snapshot_string(result)

        # Assert against snapshot
        snapshot_path = SNAPSHOT_DIR / "fusion_symbolic.snap"
        assert_snapshot(snapshot_output, snapshot_path)

    def test_fusion_symbolic_with_mixed_candidates_snapshot(self):
        """
        Snapshot test for symbolic weights with mixed candidate pool.

        Expected behavior:
            - HRM-weighted scoring applied
            - Symbolic candidates rank higher
            - Practical candidates rank lower
        """
        engine = FusionEngine(
            channel_weights={"hrm": 0.6, "lcm": 0.25, "moe": 0.15},
            enable_explanations=True
        )

        # Mix symbolic and standard candidates
        candidates = create_symbolic_candidates() + create_standard_candidates()[:2]
        context = create_symbolic_fusion_context()

        result = engine.fuse(candidates, context)

        snapshot_output = fusion_result_to_snapshot_string(result)
        snapshot_path = SNAPSHOT_DIR / "fusion_symbolic_mixed.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 3: CONFLICT RESOLUTION SNAPSHOT
# =============================================================================

class TestFusionConflictResolutionSnapshot:
    """
    Test fusion behavior when candidates have close scores.

    Tests conflict resolver activation when:
        top_score - second_score <= 0.2
    """

    def test_fusion_close_competition_snapshot(self):
        """
        Snapshot test for close competition scenario.

        Expected behavior:
            - Conflict resolver activated
            - Resolution reason captured in metadata
            - Deterministic selection among close candidates
        """
        engine = FusionEngine(
            channel_weights={"hrm": 0.4, "lcm": 0.3, "moe": 0.3},
            enable_explanations=True
        )

        # Create candidates with very close scores
        candidates = [
            create_standard_candidate(
                candidate_id="close_candidate_001",
                text="First candidate with balanced scores across all channels.",
                source=CandidateSource.RAG,
                hrm=0.75,
                lcm=0.75,
                moe=0.75,
                confidence=0.85
            ),
            create_standard_candidate(
                candidate_id="close_candidate_002",
                text="Second candidate with nearly identical balanced scores.",
                source=CandidateSource.RAG,
                hrm=0.74,
                lcm=0.76,
                moe=0.74,
                confidence=0.84
            ),
            create_standard_candidate(
                candidate_id="close_candidate_003",
                text="Third candidate also with competitive scores.",
                source=CandidateSource.HRM,
                hrm=0.76,
                lcm=0.73,
                moe=0.75,
                confidence=0.83
            )
        ]

        context = create_standard_fusion_context()
        result = engine.fuse(candidates, context)

        snapshot_output = fusion_result_to_snapshot_string(result)
        snapshot_path = SNAPSHOT_DIR / "fusion_conflict_resolution.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 4: SINGLE CANDIDATE SNAPSHOT
# =============================================================================

class TestFusionSingleCandidateSnapshot:
    """
    Test fusion behavior with single candidate.
    """

    def test_fusion_single_candidate_snapshot(self):
        """
        Snapshot test for single candidate scenario.

        Expected behavior:
            - Single candidate selected (only_candidate reason)
            - Minimal processing overhead
            - Full metadata preserved
        """
        engine = FusionEngine(enable_explanations=True)

        candidates = [
            create_standard_candidate(
                candidate_id="sole_candidate",
                text="This is the only candidate available for fusion.",
                source=CandidateSource.TEMPLATE,
                hrm=0.60,
                lcm=0.70,
                moe=0.65,
                confidence=0.75
            )
        ]

        context = create_standard_fusion_context()
        result = engine.fuse(candidates, context)

        # Verify only_candidate resolution
        assert result.metadata.get("resolution_reason") == "only_candidate"

        snapshot_output = fusion_result_to_snapshot_string(result)
        snapshot_path = SNAPSHOT_DIR / "fusion_single_candidate.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 5: REGULATED MODE SNAPSHOT
# =============================================================================

class TestFusionRegulatedModeSnapshot:
    """
    Test fusion behavior in regulated mode.
    """

    def test_fusion_regulated_snapshot(self):
        """
        Snapshot test for regulated domain fusion.

        Expected behavior:
            - Conservative routing decisions
            - Higher safety thresholds applied
            - Rules renderer preferred
        """
        engine = FusionEngine(
            channel_weights={"hrm": 0.3, "lcm": 0.35, "moe": 0.35},  # Balanced for regulated
            enable_explanations=True
        )

        candidates = [
            create_standard_candidate(
                candidate_id="regulated_candidate_001",
                text="Based on current medical guidelines, please consult with "
                     "a licensed healthcare provider before making any decisions.",
                source=CandidateSource.MOE,
                hrm=0.55,
                lcm=0.88,
                moe=0.92,
                domain="medical",
                confidence=0.90
            ),
            create_standard_candidate(
                candidate_id="regulated_candidate_002",
                text="Important disclaimer: This information is for educational "
                     "purposes only and does not constitute medical advice.",
                source=CandidateSource.TEMPLATE,
                hrm=0.45,
                lcm=0.95,
                moe=0.85,
                domain="medical",
                confidence=0.88
            )
        ]

        context = create_standard_fusion_context(
            tier="LOWER",
            intent="how",
            domain="medical",
            regulated=True
        )

        result = engine.fuse(candidates, context)

        snapshot_output = fusion_result_to_snapshot_string(result)
        snapshot_path = SNAPSHOT_DIR / "fusion_regulated.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 6: WEIGHT UPDATE SNAPSHOT
# =============================================================================

class TestFusionWeightUpdateSnapshot:
    """
    Test that weight updates affect scoring correctly.
    """

    def test_fusion_after_weight_update_snapshot(self):
        """
        Snapshot test verifying weight update affects ranking.

        Expected behavior:
            - Same candidates, different weights, different selection
            - Statistics reflect updated weights
        """
        engine = FusionEngine(
            channel_weights={"hrm": 0.4, "lcm": 0.3, "moe": 0.3},
            enable_explanations=True
        )

        # Update to MoE-heavy weights
        engine.update_channel_weights({"hrm": 0.2, "lcm": 0.2, "moe": 0.6})

        candidates = create_standard_candidates()
        context = create_standard_fusion_context()

        result = engine.fuse(candidates, context)

        # Verify weights were updated
        stats = engine.get_statistics()
        assert stats["channel_weights"]["moe"] == 0.6

        snapshot_output = fusion_result_to_snapshot_string(result)
        snapshot_path = SNAPSHOT_DIR / "fusion_moe_weighted.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 7: LAYER STRUCTURE VERIFICATION
# =============================================================================

class TestFusionStructureIntegrity:
    """
    Verify that fusion output structure matches expected contract.
    """

    def test_fusion_output_structure(self):
        """
        Verify FusionResult contains all required fields.
        """
        engine = FusionEngine()
        candidates = create_standard_candidates()
        context = create_standard_fusion_context()

        result = engine.fuse(candidates, context)

        # Verify required fields
        assert result.selected_candidate is not None
        assert isinstance(result.fusion_score, float)
        assert 0.0 <= result.fusion_score <= 1.0
        assert isinstance(result.ranked_candidates, list)
        assert len(result.ranked_candidates) > 0
        assert isinstance(result.routing, dict)
        assert "render_mode" in result.routing
        assert isinstance(result.metadata, dict)

    def test_fusion_no_input_mutation(self):
        """
        Verify fusion does not mutate input candidates.
        """
        engine = FusionEngine()
        candidates = create_standard_candidates()
        context = create_standard_fusion_context()

        # Capture original state
        original_texts = [c.text for c in candidates]
        original_scores = [c.channel_scores.copy() for c in candidates]

        # Run fusion
        _ = engine.fuse(candidates, context)

        # Verify no mutation
        for i, candidate in enumerate(candidates):
            assert candidate.text == original_texts[i], "Candidate text was mutated"
            assert candidate.channel_scores == original_scores[i], "Candidate scores were mutated"


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
