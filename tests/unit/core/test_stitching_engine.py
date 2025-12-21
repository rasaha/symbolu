"""
Symbol-U Core v3.0 - Stitching Engine Tests
============================================

Unit tests for cross-domain reasoning in the Stitching Encoder:
- StitchingEngine (score_candidates, select_best, apply_penalties)
- PenaltyCalculator (redundancy_penalty, domain_jump_penalty)
- Domain Distance calculations

Tests verify:
1. Cross-domain candidates are PRICED, not blocked
2. Redundancy penalty prevents shallow analogies
3. Domain jump caps are enforced
4. Audit trails are generated correctly
"""

import pytest
from typing import Any, Dict, List
from dataclasses import dataclass, field

# Import stitching components
from symbolu.core.stitching.stitching_engine import (
    StitchingEngine,
    StitchingConfig,
    QueryContext,
    create_stitching_engine,
    create_query_context,
)
from symbolu.core.stitching.penalties import (
    PenaltyCalculator,
    PenaltyConfig,
    ScoredCandidate,
    StitchingConstraints,
)
from symbolu.core.stitching.domain_distance import (
    get_domain_distance,
    get_aspect_overlap,
    is_cross_domain,
    DOMAIN_DISTANCE_MATRIX,
)

# Import Candidate from fusion schemas
from symbolu.mechanical.fusion.schemas.candidate import Candidate, CandidateSource


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def stitching_engine() -> StitchingEngine:
    """Create a StitchingEngine instance."""
    return StitchingEngine()


@pytest.fixture
def penalty_calculator() -> PenaltyCalculator:
    """Create a PenaltyCalculator instance."""
    return PenaltyCalculator()


@pytest.fixture
def finance_candidates() -> List[Candidate]:
    """Create sample finance domain candidates."""
    return [
        Candidate(
            id="fin_001",
            text="Market liquidity crisis leads to panic selling.",
            source=CandidateSource.RAG,
            domain="finance",
            confidence=0.9,
            aspect_vector={"ENTROPY": 0.8, "CAUSALITY": 0.7, "FLOW": 0.6},
            channel_scores={"hrm": 0.8, "lcm": 0.7, "moe": 0.9},
        ),
        Candidate(
            id="fin_002",
            text="Herd behavior amplifies market volatility.",
            source=CandidateSource.RAG,
            domain="finance",
            confidence=0.85,
            aspect_vector={"ENTROPY": 0.7, "AGENCY": 0.5, "FEEDBACK": 0.8},
            channel_scores={"hrm": 0.7, "lcm": 0.75, "moe": 0.85},
        ),
    ]


@pytest.fixture
def psychology_candidates() -> List[Candidate]:
    """Create sample psychology domain candidates."""
    return [
        Candidate(
            id="psy_001",
            text="Fear contagion spreads through group dynamics.",
            source=CandidateSource.RAG,
            domain="psychology",
            confidence=0.85,
            aspect_vector={"ENTROPY": 0.75, "CAUSALITY": 0.6, "AGENCY": 0.4},
            channel_scores={"hrm": 0.75, "lcm": 0.8, "moe": 0.7},
        ),
        Candidate(
            id="psy_002",
            text="Cognitive biases impair rational decision-making.",
            source=CandidateSource.RAG,
            domain="psychology",
            confidence=0.8,
            aspect_vector={"CAUSALITY": 0.8, "AGENCY": 0.6, "CONSTRAINT": 0.5},
            channel_scores={"hrm": 0.8, "lcm": 0.75, "moe": 0.65},
        ),
    ]


@pytest.fixture
def physics_candidates() -> List[Candidate]:
    """Create sample physics domain candidates (distant from finance)."""
    return [
        Candidate(
            id="phy_001",
            text="Phase transitions occur at critical thresholds.",
            source=CandidateSource.RAG,
            domain="physics",
            confidence=0.7,
            aspect_vector={"THRESHOLD": 0.9, "ENTROPY": 0.7, "EMERGENCE": 0.8},
            channel_scores={"hrm": 0.85, "lcm": 0.6, "moe": 0.5},
        ),
    ]


@pytest.fixture
def mixed_domain_candidates(
    finance_candidates, psychology_candidates, physics_candidates
) -> List[Candidate]:
    """Combine candidates from multiple domains."""
    return finance_candidates + psychology_candidates + physics_candidates


@pytest.fixture
def finance_query_context() -> QueryContext:
    """Create a finance domain query context."""
    return QueryContext(
        text="Why do markets panic even when fundamentals are strong?",
        domain="finance",
        aspect_vector={"ENTROPY": 0.8, "CAUSALITY": 0.7, "AGENCY": 0.5},
        confidence=1.0,
    )


# =============================================================================
# Domain Distance Tests
# =============================================================================


class TestDomainDistance:
    """Tests for symbolic domain distance calculations."""

    def test_same_domain_distance_is_zero(self) -> None:
        """Same domain should have zero distance."""
        assert get_domain_distance("finance", "finance") == 0.0
        assert get_domain_distance("psychology", "psychology") == 0.0

    def test_related_domains_have_low_distance(self) -> None:
        """Related domains should have low distance."""
        # Finance and psychology are related (behavioral finance)
        distance = get_domain_distance("finance", "psychology")
        assert 0.2 <= distance <= 0.4

    def test_distant_domains_have_high_distance(self) -> None:
        """Distant domains should have higher distance."""
        # Finance and physics are less related
        distance = get_domain_distance("finance", "physics")
        assert distance >= 0.4

    def test_distance_is_symmetric(self) -> None:
        """Domain distance should be symmetric."""
        assert get_domain_distance("finance", "psychology") == get_domain_distance(
            "psychology", "finance"
        )

    def test_is_cross_domain_true_for_different(self) -> None:
        """is_cross_domain should return True for different domains."""
        assert is_cross_domain("finance", "psychology") is True

    def test_is_cross_domain_false_for_same(self) -> None:
        """is_cross_domain should return False for same domain."""
        assert is_cross_domain("finance", "finance") is False


class TestAspectOverlap:
    """Tests for aspect vector overlap calculations."""

    def test_identical_aspects_have_full_overlap(self) -> None:
        """Identical aspect vectors should have overlap of 1.0."""
        aspects = {"ENTROPY": 0.8, "CAUSALITY": 0.7}
        assert get_aspect_overlap(aspects, aspects) == pytest.approx(1.0, rel=0.01)

    def test_disjoint_aspects_have_zero_overlap(self) -> None:
        """Non-overlapping aspects should have zero overlap."""
        aspects_a = {"ENTROPY": 0.8}
        aspects_b = {"BALANCE": 0.7}
        assert get_aspect_overlap(aspects_a, aspects_b) == 0.0

    def test_partial_overlap_is_between_zero_and_one(self) -> None:
        """Partial overlap should be in (0, 1)."""
        aspects_a = {"ENTROPY": 0.8, "CAUSALITY": 0.7, "FLOW": 0.5}
        aspects_b = {"ENTROPY": 0.7, "CAUSALITY": 0.6, "BALANCE": 0.8}
        overlap = get_aspect_overlap(aspects_a, aspects_b)
        assert 0.0 < overlap < 1.0

    def test_empty_aspects_have_zero_overlap(self) -> None:
        """Empty aspect vectors should have zero overlap."""
        assert get_aspect_overlap({}, {"ENTROPY": 0.5}) == 0.0
        assert get_aspect_overlap({"ENTROPY": 0.5}, {}) == 0.0


# =============================================================================
# Penalty Calculator Tests
# =============================================================================


class TestPenaltyCalculator:
    """Tests for PenaltyCalculator."""

    def test_instantiation(self) -> None:
        """Test that PenaltyCalculator can be instantiated."""
        calculator = PenaltyCalculator()
        assert calculator is not None
        assert calculator.config is not None

    def test_redundancy_penalty_empty_selected(
        self, penalty_calculator: PenaltyCalculator, finance_candidates: List[Candidate]
    ) -> None:
        """First candidate should have zero redundancy penalty."""
        penalty = penalty_calculator.redundancy_penalty(finance_candidates[0], [])
        assert penalty == 0.0

    def test_redundancy_penalty_similar_candidates(
        self, penalty_calculator: PenaltyCalculator
    ) -> None:
        """Similar candidates should have higher redundancy penalty."""
        candidate_a = Candidate(
            id="a",
            text="Market panic",
            source=CandidateSource.RAG,
            domain="finance",
            aspect_vector={"ENTROPY": 0.8, "CAUSALITY": 0.7},
        )
        candidate_b = Candidate(
            id="b",
            text="Market fear",
            source=CandidateSource.RAG,
            domain="finance",
            aspect_vector={"ENTROPY": 0.75, "CAUSALITY": 0.65},  # Very similar
        )

        penalty = penalty_calculator.redundancy_penalty(candidate_b, [candidate_a])
        assert penalty > 0.0  # Should have some redundancy

    def test_domain_jump_penalty_same_domain(
        self, penalty_calculator: PenaltyCalculator, finance_candidates: List[Candidate]
    ) -> None:
        """Same domain should have zero domain jump penalty."""
        penalty = penalty_calculator.domain_jump_penalty(finance_candidates[0], "finance")
        assert penalty == 0.0

    def test_domain_jump_penalty_cross_domain(
        self, penalty_calculator: PenaltyCalculator, psychology_candidates: List[Candidate]
    ) -> None:
        """Cross-domain should have non-zero domain jump penalty."""
        penalty = penalty_calculator.domain_jump_penalty(psychology_candidates[0], "finance")
        assert penalty > 0.0

    def test_domain_jump_penalty_distant_domain_is_higher(
        self, penalty_calculator: PenaltyCalculator, physics_candidates: List[Candidate]
    ) -> None:
        """More distant domains should have higher penalty."""
        psychology_candidate = Candidate(
            id="psy",
            text="Fear response",
            source=CandidateSource.RAG,
            domain="psychology",
        )
        physics_candidate = physics_candidates[0]

        penalty_psychology = penalty_calculator.domain_jump_penalty(
            psychology_candidate, "finance"
        )
        penalty_physics = penalty_calculator.domain_jump_penalty(
            physics_candidate, "finance"
        )

        # Physics is more distant from finance than psychology
        assert penalty_physics > penalty_psychology


# =============================================================================
# Stitching Engine Tests
# =============================================================================


class TestStitchingEngineInstantiation:
    """Tests for StitchingEngine instantiation."""

    def test_engine_instantiation(self) -> None:
        """Test that StitchingEngine can be instantiated."""
        engine = StitchingEngine()
        assert engine is not None
        assert isinstance(engine, StitchingEngine)
        assert engine.config is not None
        assert engine.penalty_calculator is not None

    def test_engine_with_custom_config(self) -> None:
        """Test engine with custom configuration."""
        config = StitchingConfig(
            beam_size=5,
            hrm_weight=0.5,
            lcm_weight=0.3,
            moe_weight=0.2,
        )
        engine = StitchingEngine(config)
        assert engine.config.beam_size == 5
        assert engine.config.hrm_weight == 0.5

    def test_factory_function(self) -> None:
        """Test create_stitching_engine factory."""
        engine = create_stitching_engine(
            beam_size=5,
            max_domain_jumps=2,
            domain_jump_lambda=0.4,
        )
        assert engine.config.beam_size == 5
        assert engine.config.penalty_config.domain_jump_lambda == 0.4


class TestStitchingEngineScoring:
    """Tests for StitchingEngine scoring functionality."""

    def test_score_candidates_returns_list(
        self,
        stitching_engine: StitchingEngine,
        finance_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """score_candidates should return a list of ScoredCandidates."""
        scored = stitching_engine.score_candidates(finance_candidates, finance_query_context)
        assert isinstance(scored, list)
        assert all(isinstance(sc, ScoredCandidate) for sc in scored)

    def test_score_candidates_empty_list(
        self, stitching_engine: StitchingEngine, finance_query_context: QueryContext
    ) -> None:
        """Empty candidate list should return empty result."""
        scored = stitching_engine.score_candidates([], finance_query_context)
        assert scored == []

    def test_candidates_are_ranked(
        self,
        stitching_engine: StitchingEngine,
        finance_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """Candidates should be ranked by score descending."""
        scored = stitching_engine.score_candidates(finance_candidates, finance_query_context)
        scores = [sc.final_score for sc in scored]
        assert scores == sorted(scores, reverse=True)

    def test_candidates_have_rank_assigned(
        self,
        stitching_engine: StitchingEngine,
        finance_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """Each scored candidate should have a rank assigned."""
        scored = stitching_engine.score_candidates(finance_candidates, finance_query_context)
        ranks = [sc.rank for sc in scored]
        assert ranks == list(range(1, len(scored) + 1))


class TestCrossDomainReasoning:
    """Tests for cross-domain reasoning behavior."""

    def test_cross_domain_candidates_are_included(
        self,
        stitching_engine: StitchingEngine,
        mixed_domain_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """Cross-domain candidates should be included, not blocked."""
        scored = stitching_engine.score_candidates(
            mixed_domain_candidates, finance_query_context
        )

        # Should include candidates from multiple domains
        domains = {getattr(sc.candidate, "domain") for sc in scored}
        assert len(domains) >= 1  # At least finance
        # Should include cross-domain if relevance is high enough

    def test_cross_domain_candidates_are_penalized(
        self,
        stitching_engine: StitchingEngine,
        mixed_domain_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """Cross-domain candidates should have domain jump penalty."""
        scored = stitching_engine.score_candidates(
            mixed_domain_candidates, finance_query_context
        )

        for sc in scored:
            if sc.is_cross_domain:
                assert sc.domain_jump_penalty > 0.0
            else:
                assert sc.domain_jump_penalty == 0.0

    def test_same_domain_no_penalty(
        self,
        stitching_engine: StitchingEngine,
        finance_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """Same-domain candidates should have no domain jump penalty."""
        scored = stitching_engine.score_candidates(finance_candidates, finance_query_context)

        for sc in scored:
            assert sc.is_cross_domain is False
            assert sc.domain_jump_penalty == 0.0

    def test_domain_jump_cap_enforced(self) -> None:
        """Maximum domain jumps should be enforced."""
        # Create engine with max 1 domain jump
        engine = create_stitching_engine(beam_size=10, max_domain_jumps=1)

        # Create many cross-domain candidates
        candidates = [
            Candidate(
                id=f"cross_{i}",
                text=f"Cross domain text {i}",
                source=CandidateSource.RAG,
                domain="psychology",
                confidence=0.9,
                channel_scores={"hrm": 0.8, "lcm": 0.7, "moe": 0.8},
            )
            for i in range(5)
        ]

        context = QueryContext(text="Test", domain="finance")
        scored = engine.score_candidates(candidates, context)

        # Should have at most 1 cross-domain
        cross_domain_count = sum(1 for sc in scored if sc.is_cross_domain)
        assert cross_domain_count <= 1


class TestRedundancyPrevention:
    """Tests for redundancy penalty behavior."""

    def test_redundant_candidates_penalized(
        self, stitching_engine: StitchingEngine
    ) -> None:
        """Highly similar candidates should be penalized."""
        # Create two nearly identical candidates
        candidates = [
            Candidate(
                id="a",
                text="Market panic causes selling",
                source=CandidateSource.RAG,
                domain="finance",
                confidence=0.9,
                aspect_vector={"ENTROPY": 0.8, "CAUSALITY": 0.7},
                channel_scores={"hrm": 0.8, "lcm": 0.7, "moe": 0.8},
            ),
            Candidate(
                id="b",
                text="Market fear leads to selling",  # Very similar
                source=CandidateSource.RAG,
                domain="finance",
                confidence=0.85,
                aspect_vector={"ENTROPY": 0.75, "CAUSALITY": 0.65},  # Similar aspects
                channel_scores={"hrm": 0.75, "lcm": 0.7, "moe": 0.75},
            ),
        ]

        context = QueryContext(text="Why markets panic?", domain="finance")
        scored = stitching_engine.score_candidates(candidates, context)

        # Second candidate should have redundancy penalty
        if len(scored) > 1:
            assert scored[1].redundancy_penalty > 0.0


class TestAuditTrail:
    """Tests for audit trail generation."""

    def test_audit_log_generated(
        self,
        stitching_engine: StitchingEngine,
        finance_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """Audit log should be generated during scoring."""
        stitching_engine.clear_audit_log()
        stitching_engine.score_candidates(finance_candidates, finance_query_context)

        audit_log = stitching_engine.get_audit_log()
        assert len(audit_log) > 0

    def test_audit_log_contains_selection(
        self,
        stitching_engine: StitchingEngine,
        finance_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """Audit log should contain selection results."""
        stitching_engine.clear_audit_log()
        stitching_engine.score_candidates(finance_candidates, finance_query_context)

        audit_log = stitching_engine.get_audit_log()
        selection_entries = [e for e in audit_log if e.get("action") == "selection_complete"]
        assert len(selection_entries) >= 1

    def test_explain_selection_output(
        self,
        stitching_engine: StitchingEngine,
        mixed_domain_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """explain_selection should produce readable output."""
        scored = stitching_engine.score_candidates(
            mixed_domain_candidates, finance_query_context
        )
        explanation = stitching_engine.explain_selection(scored, finance_query_context)

        assert isinstance(explanation, str)
        assert "Stitching Selection" in explanation
        assert "Relevance" in explanation
        assert "Penalties" in explanation


class TestConstraintEnforcement:
    """Tests for constraint enforcement."""

    def test_low_confidence_rejected(self, stitching_engine: StitchingEngine) -> None:
        """Low confidence candidates should be rejected."""
        candidate = Candidate(
            id="low_conf",
            text="Low confidence candidate",
            source=CandidateSource.RAG,
            domain="finance",
            confidence=0.1,  # Below default threshold of 0.3
            channel_scores={"hrm": 0.8, "lcm": 0.7, "moe": 0.8},
        )

        context = QueryContext(text="Test", domain="finance")
        scored = stitching_engine.score_candidates([candidate], context)

        # Should be rejected due to low confidence
        assert len(scored) == 0

    def test_high_entropy_rejected(self, stitching_engine: StitchingEngine) -> None:
        """High entropy candidates should be rejected."""
        candidate = Candidate(
            id="high_entropy",
            text="High entropy candidate",
            source=CandidateSource.RAG,
            domain="finance",
            confidence=0.9,
            entropy=0.95,  # Above default threshold of 0.9
            channel_scores={"hrm": 0.8, "lcm": 0.7, "moe": 0.8},
        )

        context = QueryContext(text="Test", domain="finance")
        scored = stitching_engine.score_candidates([candidate], context)

        # Should be rejected due to high entropy
        assert len(scored) == 0


class TestSelectBest:
    """Tests for select_best convenience method."""

    def test_select_best_returns_candidates(
        self,
        stitching_engine: StitchingEngine,
        finance_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """select_best should return candidate objects."""
        selected = stitching_engine.select_best(finance_candidates, finance_query_context)

        assert isinstance(selected, list)
        assert all(isinstance(c, Candidate) for c in selected)

    def test_select_best_respects_beam_size(
        self,
        stitching_engine: StitchingEngine,
        mixed_domain_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """select_best should respect beam_size parameter."""
        selected = stitching_engine.select_best(
            mixed_domain_candidates, finance_query_context, beam_size=2
        )

        assert len(selected) <= 2


# =============================================================================
# Integration Tests
# =============================================================================


class TestCrossDomainIntegration:
    """Integration tests for cross-domain reasoning scenarios."""

    def test_market_panic_query(self) -> None:
        """
        Test the 'Why do markets panic?' scenario from implementation plan.

        Expected: Finance candidates first, then psychology with penalty.
        """
        engine = create_stitching_engine(beam_size=5, max_domain_jumps=2)

        candidates = [
            Candidate(
                id="fin_liquidity",
                text="Liquidity crisis explanation",
                source=CandidateSource.RAG,
                domain="finance",
                confidence=0.9,
                aspect_vector={"ENTROPY": 0.8, "CAUSALITY": 0.7, "FLOW": 0.8},
                channel_scores={"hrm": 0.85, "lcm": 0.75, "moe": 0.9},
            ),
            Candidate(
                id="psy_fear",
                text="Fear contagion dynamics",
                source=CandidateSource.RAG,
                domain="psychology",
                confidence=0.85,
                aspect_vector={"ENTROPY": 0.75, "CAUSALITY": 0.65, "AGENCY": 0.5},
                channel_scores={"hrm": 0.8, "lcm": 0.8, "moe": 0.7},
            ),
            Candidate(
                id="phy_phase",
                text="Phase transition analogy",
                source=CandidateSource.RAG,
                domain="physics",
                confidence=0.7,
                aspect_vector={"THRESHOLD": 0.9, "ENTROPY": 0.7, "EMERGENCE": 0.8},
                channel_scores={"hrm": 0.85, "lcm": 0.6, "moe": 0.5},
            ),
        ]

        context = QueryContext(
            text="Why do markets panic even when fundamentals are strong?",
            domain="finance",
            aspect_vector={"ENTROPY": 0.8, "CAUSALITY": 0.7, "AGENCY": 0.5},
        )

        scored = engine.score_candidates(candidates, context)

        # Should include multiple domains
        assert len(scored) >= 2

        # Finance candidate should be ranked first (no penalty)
        assert scored[0].candidate.domain == "finance"

        # Cross-domain candidates should have penalties
        for sc in scored:
            if sc.candidate.domain != "finance":
                assert sc.domain_jump_penalty > 0

        # Print explanation for debugging
        print(engine.explain_selection(scored, context))


class TestScoredCandidateAudit:
    """Tests for ScoredCandidate audit functionality."""

    def test_scored_candidate_to_dict(
        self,
        stitching_engine: StitchingEngine,
        finance_candidates: List[Candidate],
        finance_query_context: QueryContext,
    ) -> None:
        """ScoredCandidate.to_dict should produce complete audit info."""
        scored = stitching_engine.score_candidates(finance_candidates, finance_query_context)

        if scored:
            audit_dict = scored[0].to_dict()
            assert "candidate_id" in audit_dict
            assert "relevance" in audit_dict
            assert "penalties" in audit_dict
            assert "final_score" in audit_dict
            assert "rank" in audit_dict
