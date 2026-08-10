"""
Stitching-Fusion Boundary Tests
================================

Tests verifying the normative requirements from STITCHING_FUSION_SPECIFICATION.md.

These tests ensure:
1. Repeatability: Same input -> same output
2. Boundary enforcement: Rejected candidates cannot reach Fusion
3. Score separation: Stitching diagnostics not used in Fusion
4. Deterministic tie-breaking: Lexicographic by candidate ID

Reference: Project_documentation/repository/docs/architecture/STITCHING_FUSION_SPECIFICATION.md Section 0.5
"""

import pytest
from dataclasses import dataclass
from typing import Dict, List, Optional

from symbolu.core.stitching import (
    StitchingEngine,
    StitchingConfig,
    QueryContext,
    StitchingDecision,
    StitchingToFusionHandoff,
    create_handoff,
    StitchingConstraints,
    PenaltyConfig,
)
from symbolu.mechanical.fusion.fusion.fusion_engine import FusionEngine
from symbolu.mechanical.fusion.fusion.contracts import FusionRanking
from symbolu.mechanical.fusion.schemas.fusion_result import FusionContext
from symbolu.mechanical.fusion.schemas.candidate import Candidate


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_candidates() -> List[Candidate]:
    """Create sample candidates for testing."""
    return [
        Candidate(
            id="c1_high_confidence",
            text="High confidence candidate",
            source="RAG",
            domain="finance",
            confidence=0.9,
            entropy=0.3,
            channel_scores={"hrm": 0.8, "lcm": 0.7, "moe": 0.9},
            aspect_vector={"ENTROPY": 0.5, "CAUSALITY": 0.7},
        ),
        Candidate(
            id="c2_medium_confidence",
            text="Medium confidence candidate",
            source="RAG",
            domain="finance",
            confidence=0.6,
            entropy=0.4,
            channel_scores={"hrm": 0.7, "lcm": 0.8, "moe": 0.6},
            aspect_vector={"ENTROPY": 0.4, "CAUSALITY": 0.6},
        ),
        Candidate(
            id="c3_low_confidence",
            text="Low confidence candidate - should be rejected",
            source="RAG",
            domain="finance",
            confidence=0.2,  # Below default threshold of 0.3
            entropy=0.2,
            channel_scores={"hrm": 0.9, "lcm": 0.9, "moe": 0.9},
            aspect_vector={"ENTROPY": 0.3, "CAUSALITY": 0.5},
        ),
        Candidate(
            id="c4_cross_domain",
            text="Psychology candidate for cross-domain",
            source="RAG",
            domain="psychology",  # Different from query domain
            confidence=0.8,
            entropy=0.3,
            channel_scores={"hrm": 0.75, "lcm": 0.65, "moe": 0.7},
            aspect_vector={"ENTROPY": 0.6, "CAUSALITY": 0.8},
        ),
    ]


@pytest.fixture
def query_context() -> QueryContext:
    """Create query context for testing."""
    return QueryContext(
        text="Why do markets panic?",
        domain="finance",
        aspect_vector={"ENTROPY": 0.8, "CAUSALITY": 0.7},
    )


@pytest.fixture
def fusion_context() -> FusionContext:
    """Create fusion context for testing."""
    return FusionContext(
        tier="HYBRID",
        intent="WHY",
        domain="finance",
        entropy={"total_entropy": 0.4},
        ontology_mass={"upper_mass": 0.5, "lower_mass": 0.5},
    )


@pytest.fixture
def stitching_engine() -> StitchingEngine:
    """Create stitching engine with default config."""
    return StitchingEngine()


@pytest.fixture
def fusion_engine() -> FusionEngine:
    """Create fusion engine with default config."""
    return FusionEngine()


# =============================================================================
# Test 1: Repeatability Tests
# =============================================================================

class TestRepeatability:
    """
    NORMATIVE REQUIREMENT (Section 0.4):
    - MUST produce identical output given identical input
    """

    def test_stitching_repeatability(
        self,
        stitching_engine: StitchingEngine,
        sample_candidates: List[Candidate],
        query_context: QueryContext,
    ):
        """Same input to Stitching produces same output."""
        # Run evaluate twice with identical inputs
        result_1 = stitching_engine.evaluate(sample_candidates, query_context)
        result_2 = stitching_engine.evaluate(sample_candidates, query_context)

        # Allowed candidate IDs must be identical
        assert result_1.allowed_candidate_ids == result_2.allowed_candidate_ids

        # Decision outcomes must be identical
        for cid in result_1.decisions:
            assert result_1.decisions[cid].allowed == result_2.decisions[cid].allowed

    def test_fusion_repeatability(
        self,
        stitching_engine: StitchingEngine,
        fusion_engine: FusionEngine,
        sample_candidates: List[Candidate],
        query_context: QueryContext,
        fusion_context: FusionContext,
    ):
        """Same handoff to Fusion produces same output."""
        # Create handoff
        decision = stitching_engine.evaluate(sample_candidates, query_context)
        handoff = StitchingToFusionHandoff.from_decision(
            decision, sample_candidates, fusion_context
        )

        # Run rank twice with identical handoff
        ranking_1 = fusion_engine.rank(handoff)
        ranking_2 = fusion_engine.rank(handoff)

        # Selected candidate must be identical
        assert ranking_1.selected_candidate_id == ranking_2.selected_candidate_id

        # Fusion scores must be identical
        assert ranking_1.selected_fusion_score == ranking_2.selected_fusion_score

        # Full ranking order must be identical
        ids_1 = [sc.candidate_id for sc in ranking_1.rankings]
        ids_2 = [sc.candidate_id for sc in ranking_2.rankings]
        assert ids_1 == ids_2


# =============================================================================
# Test 2: Boundary Enforcement Tests
# =============================================================================

class TestBoundaryEnforcement:
    """
    NORMATIVE REQUIREMENT (Section 0.3):
    - MUST NOT allow rejected candidate IDs or metadata to cross the boundary
    - MUST use an explicit handoff object between Stitching and Fusion
    """

    def test_rejected_candidates_not_in_handoff(
        self,
        stitching_engine: StitchingEngine,
        sample_candidates: List[Candidate],
        query_context: QueryContext,
        fusion_context: FusionContext,
    ):
        """Rejected candidates are NOT included in handoff."""
        # Evaluate candidates (c3_low_confidence should be rejected)
        decision = stitching_engine.evaluate(sample_candidates, query_context)

        # Verify c3 was rejected
        assert "c3_low_confidence" not in decision.allowed_candidate_ids
        assert not decision.decisions["c3_low_confidence"].allowed

        # Create handoff
        handoff = StitchingToFusionHandoff.from_decision(
            decision, sample_candidates, fusion_context
        )

        # Verify rejected candidate is NOT in handoff
        handoff_ids = [c.id for c in handoff.allowed_candidates]
        assert "c3_low_confidence" not in handoff_ids

    def test_fusion_cannot_access_stitching_diagnostics(
        self,
        stitching_engine: StitchingEngine,
        sample_candidates: List[Candidate],
        query_context: QueryContext,
        fusion_context: FusionContext,
    ):
        """Handoff does not contain Stitching diagnostic scores."""
        decision = stitching_engine.evaluate(sample_candidates, query_context)
        handoff = StitchingToFusionHandoff.from_decision(
            decision, sample_candidates, fusion_context
        )

        # Handoff should NOT have access to decisions dict
        assert not hasattr(handoff, 'decisions')

        # Handoff should NOT have diagnostic_scores
        handoff_dict = handoff.to_dict()
        assert 'diagnostic_scores' not in handoff_dict
        assert 'rejection_reason' not in handoff_dict

    def test_fusion_rejects_non_handoff_input(
        self,
        fusion_engine: FusionEngine,
        sample_candidates: List[Candidate],
        fusion_context: FusionContext,
    ):
        """Fusion.rank() rejects input that is not StitchingToFusionHandoff."""
        # Attempt to pass raw candidates - should fail
        with pytest.raises(TypeError) as exc_info:
            fusion_engine.rank(sample_candidates)  # type: ignore

        assert "StitchingToFusionHandoff" in str(exc_info.value)

    def test_fusion_rejects_stitching_decision_directly(
        self,
        stitching_engine: StitchingEngine,
        fusion_engine: FusionEngine,
        sample_candidates: List[Candidate],
        query_context: QueryContext,
    ):
        """Fusion.rank() rejects StitchingDecision directly (must use handoff)."""
        decision = stitching_engine.evaluate(sample_candidates, query_context)

        # Attempt to pass StitchingDecision directly - should fail
        with pytest.raises(TypeError) as exc_info:
            fusion_engine.rank(decision)  # type: ignore

        assert "StitchingToFusionHandoff" in str(exc_info.value)


# =============================================================================
# Test 3: Authority Tests
# =============================================================================

class TestAuthorityEnforcement:
    """
    NORMATIVE REQUIREMENT (Section 0.1, 0.2):
    - Stitching: MUST return boolean eligibility
    - Fusion: MUST assume all input candidates are valid by construction
    - Fusion: MUST NOT override or bypass Stitching decisions
    """

    def test_stitching_returns_boolean_eligibility(
        self,
        stitching_engine: StitchingEngine,
        sample_candidates: List[Candidate],
        query_context: QueryContext,
    ):
        """Stitching returns boolean allowed field for each candidate."""
        decision = stitching_engine.evaluate(sample_candidates, query_context)

        for cid, candidate_decision in decision.decisions.items():
            # allowed must be a boolean
            assert isinstance(candidate_decision.allowed, bool)

    def test_fusion_cannot_resurrect_rejected_candidates(
        self,
        stitching_engine: StitchingEngine,
        fusion_engine: FusionEngine,
        sample_candidates: List[Candidate],
        query_context: QueryContext,
        fusion_context: FusionContext,
    ):
        """
        Fusion cannot "rescue" a candidate that Stitching rejected.

        The handoff structurally prevents this by not including rejected candidates.
        """
        decision = stitching_engine.evaluate(sample_candidates, query_context)

        # c3 was rejected
        assert "c3_low_confidence" not in decision.allowed_candidate_ids

        # Create handoff (proper way)
        handoff = StitchingToFusionHandoff.from_decision(
            decision, sample_candidates, fusion_context
        )

        # Fusion receives the handoff
        ranking = fusion_engine.rank(handoff)

        # c3 cannot appear in Fusion output
        ranked_ids = [sc.candidate_id for sc in ranking.rankings]
        assert "c3_low_confidence" not in ranked_ids
        assert ranking.selected_candidate_id != "c3_low_confidence"


# =============================================================================
# Test 4: Deterministic Tie-Breaking Tests
# =============================================================================

class TestDeterministicTieBreaking:
    """
    NORMATIVE REQUIREMENT (Section 0.4):
    - Tie-breaking MUST use deterministic rule (lexicographic candidate ID)
    """

    def test_tie_break_is_lexicographic(
        self,
        fusion_engine: FusionEngine,
        fusion_context: FusionContext,
    ):
        """When scores are tied, winner is determined by lexicographic ID."""
        # Create candidates with identical scores
        tied_candidates = [
            Candidate(
                id="z_candidate",  # Lexicographically last
                text="Candidate Z",
                source="RAG",
                domain="finance",
                confidence=0.8,
                entropy=0.3,
                channel_scores={"hrm": 0.8, "lcm": 0.8, "moe": 0.8},
            ),
            Candidate(
                id="a_candidate",  # Lexicographically first - should win
                text="Candidate A",
                source="RAG",
                domain="finance",
                confidence=0.8,
                entropy=0.3,
                channel_scores={"hrm": 0.8, "lcm": 0.8, "moe": 0.8},
            ),
            Candidate(
                id="m_candidate",  # Lexicographically middle
                text="Candidate M",
                source="RAG",
                domain="finance",
                confidence=0.8,
                entropy=0.3,
                channel_scores={"hrm": 0.8, "lcm": 0.8, "moe": 0.8},
            ),
        ]

        # Create mock handoff directly (for tie-break testing)
        handoff = StitchingToFusionHandoff(
            allowed_candidates=tied_candidates,
            context=fusion_context,
            stitching_audit_id="test_tiebreak",
        )

        ranking = fusion_engine.rank(handoff)

        # Winner should be "a_candidate" (lexicographically first)
        assert ranking.selected_candidate_id == "a_candidate"

        # Tie-break should be marked
        assert ranking.rankings[0].tie_break_applied


# =============================================================================
# Test 5: Score Separation Tests
# =============================================================================

class TestScoreSeparation:
    """
    NORMATIVE REQUIREMENT:
    - Stitching diagnostic scores are for audit only
    - Fusion scores are for ranking only
    - These scores MUST NOT be merged
    """

    def test_stitching_diagnostic_scores_are_not_comparable(
        self,
        stitching_engine: StitchingEngine,
        sample_candidates: List[Candidate],
        query_context: QueryContext,
    ):
        """
        Stitching diagnostic_scores exist but are not used for ranking.

        The scores exist in decisions for audit purposes, but allowed_candidate_ids
        is determined by boolean constraint checks, not score ranking.
        """
        decision = stitching_engine.evaluate(sample_candidates, query_context)

        # All allowed candidates pass constraints - their "rank" by diagnostic score
        # is NOT what determines inclusion
        for cid in decision.allowed_candidate_ids:
            candidate_decision = decision.decisions[cid]
            # diagnostic_scores exist for audit
            assert "relevance" in candidate_decision.diagnostic_scores
            assert "total_diagnostic" in candidate_decision.diagnostic_scores

    def test_fusion_scores_are_independent_of_stitching(
        self,
        stitching_engine: StitchingEngine,
        fusion_engine: FusionEngine,
        sample_candidates: List[Candidate],
        query_context: QueryContext,
        fusion_context: FusionContext,
    ):
        """
        Fusion scores are computed independently using only channel scores.

        Fusion does NOT have access to Stitching's diagnostic_scores.
        """
        decision = stitching_engine.evaluate(sample_candidates, query_context)
        handoff = StitchingToFusionHandoff.from_decision(
            decision, sample_candidates, fusion_context
        )

        ranking = fusion_engine.rank(handoff)

        # Verify Fusion computed its own scores
        for scored in ranking.rankings:
            # Fusion score components are channel-based
            assert "hrm_contribution" in scored.score_components
            assert "lcm_contribution" in scored.score_components
            assert "moe_contribution" in scored.score_components

            # No Stitching diagnostic scores in Fusion output
            assert "relevance" not in scored.score_components
            assert "redundancy_penalty" not in scored.score_components
            assert "domain_jump_penalty" not in scored.score_components


# =============================================================================
# Test 6: Full Pipeline Integration Test
# =============================================================================

class TestFullPipeline:
    """Integration test showing correct orchestration pattern."""

    def test_full_pipeline_flow(
        self,
        sample_candidates: List[Candidate],
        query_context: QueryContext,
        fusion_context: FusionContext,
    ):
        """
        Demonstrate correct pipeline usage per spec:

        1. StitchingEngine.evaluate() -> StitchingDecision
        2. StitchingToFusionHandoff.from_decision() -> Handoff
        3. FusionEngine.rank(handoff) -> FusionRanking
        """
        # Step 1: Stitching evaluates candidates
        stitching = StitchingEngine()
        decision = stitching.evaluate(sample_candidates, query_context)

        # Verify Stitching output
        assert isinstance(decision, StitchingDecision)
        assert len(decision.allowed_candidate_ids) > 0
        assert "c3_low_confidence" not in decision.allowed_candidate_ids  # Rejected

        # Step 2: Create handoff (the ONLY correct way to bridge)
        handoff = StitchingToFusionHandoff.from_decision(
            decision, sample_candidates, fusion_context
        )

        # Verify handoff properties
        assert isinstance(handoff, StitchingToFusionHandoff)
        assert len(handoff.allowed_candidates) == len(decision.allowed_candidate_ids)
        assert handoff.stitching_audit_id is not None

        # Step 3: Fusion ranks from handoff
        fusion = FusionEngine()
        ranking = fusion.rank(handoff)

        # Verify Fusion output
        assert isinstance(ranking, FusionRanking)
        assert ranking.selected_candidate_id in decision.allowed_candidate_ids
        assert len(ranking.rankings) == len(handoff.allowed_candidates)

        # Verify audit trail connection
        assert ranking.metadata["stitching_audit_id"] == handoff.stitching_audit_id
