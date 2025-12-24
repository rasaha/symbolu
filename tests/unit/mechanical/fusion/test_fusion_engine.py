"""
Tests for FusionEngine v3.1
Comprehensive test suite for fusion logic
"""

import pytest
from typing import List, Dict

from symbolu.mechanical.schemas.candidate import Candidate, CandidateSource
from symbolu.mechanical.schemas.fusion_result import FusionContext, FusionResult
from symbolu.mechanical.fusion import FusionEngine


# Test Fixtures

@pytest.fixture
def basic_context():
    """Basic fusion context for testing"""
    return FusionContext(
        tier="HYBRID",
        intent="WHY",
        domain="general",
        entropy={"total_entropy": 0.5, "H_dim": 0.4, "H_Guna": 0.5, "H_Kosha": 0.6},
        ontology_mass={"lower_mass": 0.45, "upper_mass": 0.55}
    )


@pytest.fixture
def regulated_context():
    """Regulated context (high safety requirements)"""
    return FusionContext(
        tier="LOWER",
        intent="HOW",
        domain="medical",
        entropy={"total_entropy": 0.3},
        ontology_mass={"lower_mass": 0.7, "upper_mass": 0.3},
        regulated_mode=True,
        safety_thresholds={"confidence": 0.9}
    )


@pytest.fixture
def sample_candidates():
    """Sample candidates for testing"""
    return [
        Candidate(
            id="hrm_candidate",
            text="This is a philosophical exploration of the concept.",
            source=CandidateSource.HRM,
            channel_scores={"hrm": 0.9, "lcm": 0.6, "moe": 0.4},
            relevance_score=0.8,
            confidence=0.85,
            smi=0.25
        ),
        Candidate(
            id="lcm_candidate",
            text="This is a clear semantic explanation.",
            source=CandidateSource.LCM,
            channel_scores={"hrm": 0.5, "lcm": 0.9, "moe": 0.5},
            relevance_score=0.75,
            confidence=0.9,
            smi=0.15
        ),
        Candidate(
            id="moe_candidate",
            text="This is a domain-specific factual response.",
            source=CandidateSource.MOE,
            channel_scores={"hrm": 0.4, "lcm": 0.6, "moe": 0.95},
            relevance_score=0.85,
            confidence=0.8,
            domain="general",
            smi=0.2
        )
    ]


# Basic Fusion Tests

def test_basic_fusion(basic_context, sample_candidates):
    """Test basic fusion with standard candidates"""
    engine = FusionEngine()
    result = engine.fuse(sample_candidates, basic_context)
    
    # Assertions
    assert isinstance(result, FusionResult)
    assert result.selected_candidate is not None
    assert result.fusion_score > 0
    assert len(result.ranked_candidates) == 3
    assert result.routing is not None


def test_fusion_selects_highest_score(basic_context, sample_candidates):
    """Test that fusion selects highest scoring candidate"""
    engine = FusionEngine()
    result = engine.fuse(sample_candidates, basic_context)
    
    # Top candidate should have highest fusion score
    top_candidate = result.ranked_candidates[0]
    assert result.selected_candidate.id == top_candidate.id


def test_fusion_with_single_candidate(basic_context):
    """Test fusion with only one candidate"""
    candidate = Candidate(
        id="only_one",
        text="Only candidate",
        source=CandidateSource.RAG,
        channel_scores={"hrm": 0.5, "lcm": 0.5, "moe": 0.5},
        confidence=0.7
    )
    
    engine = FusionEngine()
    result = engine.fuse([candidate], basic_context)
    
    assert result.selected_candidate.id == "only_one"
    assert result.metadata["resolution_reason"] == "only_candidate"


def test_fusion_with_empty_candidates_raises_error(basic_context):
    """Test that fusion raises error with no candidates"""
    engine = FusionEngine()
    
    with pytest.raises(ValueError, match="No candidates provided"):
        engine.fuse([], basic_context)


# Channel Scoring Tests

def test_hrm_channel_boost_for_why_intent():
    """Test HRM channel gets boost for WHY intent"""
    # Use candidates with equal confidence and SMI to isolate channel boost effect
    candidates = [
        Candidate(
            id="hrm_candidate",
            text="Philosophical exploration",
            source=CandidateSource.HRM,
            channel_scores={"hrm": 0.9, "lcm": 0.5, "moe": 0.4},
            relevance_score=0.8,
            confidence=0.85,
            smi=0.2
        ),
        Candidate(
            id="other_candidate",
            text="Other response",
            source=CandidateSource.LCM,
            channel_scores={"hrm": 0.4, "lcm": 0.8, "moe": 0.6},
            relevance_score=0.8,
            confidence=0.85,
            smi=0.2
        ),
    ]

    context = FusionContext(
        tier="UPPER",
        intent="WHY",
        domain="philosophy",
        entropy={"total_entropy": 0.4},
        ontology_mass={"lower_mass": 0.3, "upper_mass": 0.7}
    )

    engine = FusionEngine()
    result = engine.fuse(candidates, context)

    # HRM candidate should be favored due to WHY intent boost
    assert result.selected_candidate.id == "hrm_candidate"


def test_moe_channel_boost_for_how_intent():
    """Test MoE channel gets boost for HOW intent"""
    # Use candidates with equal confidence and SMI to isolate channel boost effect
    candidates = [
        Candidate(
            id="moe_candidate",
            text="Domain-specific factual response",
            source=CandidateSource.MOE,
            channel_scores={"hrm": 0.4, "lcm": 0.5, "moe": 0.9},
            relevance_score=0.8,
            confidence=0.85,
            smi=0.2
        ),
        Candidate(
            id="other_candidate",
            text="Other response",
            source=CandidateSource.LCM,
            channel_scores={"hrm": 0.6, "lcm": 0.8, "moe": 0.4},
            relevance_score=0.8,
            confidence=0.85,
            smi=0.2
        ),
    ]

    context = FusionContext(
        tier="LOWER",
        intent="HOW",
        domain="general",
        entropy={"total_entropy": 0.3},
        ontology_mass={"lower_mass": 0.7, "upper_mass": 0.3}
    )

    engine = FusionEngine()
    result = engine.fuse(candidates, context)

    # MoE candidate should be favored due to HOW intent boost
    assert result.selected_candidate.id == "moe_candidate"


def test_lcm_channel_boost_for_what_intent():
    """Test LCM channel gets boost for WHAT intent"""
    # Use candidates with equal confidence and SMI to isolate channel boost effect
    candidates = [
        Candidate(
            id="lcm_candidate",
            text="Clear semantic explanation",
            source=CandidateSource.LCM,
            channel_scores={"hrm": 0.4, "lcm": 0.9, "moe": 0.5},
            relevance_score=0.8,
            confidence=0.85,
            smi=0.2
        ),
        Candidate(
            id="other_candidate",
            text="Other response",
            source=CandidateSource.HRM,
            channel_scores={"hrm": 0.8, "lcm": 0.4, "moe": 0.6},
            relevance_score=0.8,
            confidence=0.85,
            smi=0.2
        ),
    ]

    context = FusionContext(
        tier="HYBRID",
        intent="WHAT",
        domain="general",
        entropy={"total_entropy": 0.4},
        ontology_mass={"lower_mass": 0.5, "upper_mass": 0.5}
    )

    engine = FusionEngine()
    result = engine.fuse(candidates, context)

    # LCM candidate should be favored due to WHAT intent boost
    assert result.selected_candidate.id == "lcm_candidate"


# Conflict Resolution Tests

def test_regulated_mode_filters_low_confidence():
    """Test regulated mode filters out low confidence candidates"""
    candidates = [
        Candidate(
            id="low_conf",
            text="Low confidence response",
            source=CandidateSource.RAG,
            channel_scores={"hrm": 0.8, "lcm": 0.8, "moe": 0.8},
            confidence=0.6,  # Too low for regulated mode
            relevance_score=0.8
        ),
        Candidate(
            id="high_conf",
            text="High confidence response",
            source=CandidateSource.MOE,
            channel_scores={"hrm": 0.7, "lcm": 0.7, "moe": 0.9},
            confidence=0.95,  # Acceptable for regulated mode
            relevance_score=0.75
        )
    ]
    
    context = FusionContext(
        tier="LOWER",
        intent="HOW",
        domain="medical",
        entropy={"total_entropy": 0.2},
        ontology_mass={"lower_mass": 0.8, "upper_mass": 0.2},
        regulated_mode=True
    )
    
    engine = FusionEngine()
    result = engine.fuse(candidates, context)
    
    # Should select high confidence candidate
    assert result.selected_candidate.id == "high_conf"


def test_high_smi_penalty():
    """Test that high SMI (semantic mismatch) reduces score"""
    candidates = [
        Candidate(
            id="low_smi",
            text="Aligned response",
            source=CandidateSource.LCM,
            channel_scores={"hrm": 0.7, "lcm": 0.7, "moe": 0.7},
            confidence=0.8,
            smi=0.2,  # Low mismatch
            relevance_score=0.7
        ),
        Candidate(
            id="high_smi",
            text="Misaligned response",
            source=CandidateSource.HRM,
            channel_scores={"hrm": 0.8, "lcm": 0.8, "moe": 0.8},
            confidence=0.8,
            smi=0.8,  # High mismatch
            relevance_score=0.7
        )
    ]
    
    context = FusionContext(
        tier="HYBRID",
        intent="WHY",
        domain="general",
        entropy={"total_entropy": 0.4},
        ontology_mass={"lower_mass": 0.5, "upper_mass": 0.5}
    )
    
    engine = FusionEngine()
    result = engine.fuse(candidates, context)
    
    # Should penalize high SMI candidate
    # Low SMI should win despite slightly lower channel scores
    assert result.selected_candidate.id == "low_smi"


# Routing Tests

def test_routing_rules_mode_for_high_confidence(regulated_context):
    """Test routing selects rules mode for high confidence"""
    candidate = Candidate(
        id="high_quality",
        text="High quality response",
        source=CandidateSource.MOE,
        channel_scores={"hrm": 0.8, "lcm": 0.9, "moe": 0.95},
        confidence=0.95,
        smi=0.1,
        relevance_score=0.9
    )
    
    engine = FusionEngine()
    result = engine.fuse([candidate], regulated_context)
    
    # Should use rules mode in regulated context with high confidence
    assert result.routing["render_mode"] == "rules"
    assert result.routing["use_rules_renderer"] is True


def test_routing_llm_mode_for_high_entropy():
    """Test routing selects LLM mode for high entropy"""
    context = FusionContext(
        tier="HYBRID",
        intent="WHY",
        domain="philosophy",
        entropy={"total_entropy": 0.8},  # High entropy
        ontology_mass={"lower_mass": 0.4, "upper_mass": 0.6}
    )
    
    candidate = Candidate(
        id="complex",
        text="Complex philosophical response",
        source=CandidateSource.HRM,
        channel_scores={"hrm": 0.7, "lcm": 0.6, "moe": 0.5},
        confidence=0.7,
        relevance_score=0.7
    )
    
    engine = FusionEngine()
    result = engine.fuse([candidate], context)
    
    # Should use LLM mode for high entropy
    assert result.routing["render_mode"] == "llm"
    assert result.routing["use_llm_renderer"] is True


def test_persona_selection():
    """Test persona selection based on domain and intent"""
    # Medical domain should get professional persona
    medical_context = FusionContext(
        tier="LOWER",
        intent="HOW",
        domain="medical",
        entropy={"total_entropy": 0.3},
        ontology_mass={"lower_mass": 0.7, "upper_mass": 0.3}
    )
    
    candidate = Candidate(
        id="medical",
        text="Medical advice",
        source=CandidateSource.MOE,
        channel_scores={"hrm": 0.5, "lcm": 0.7, "moe": 0.9},
        confidence=0.85
    )
    
    engine = FusionEngine()
    result = engine.fuse([candidate], medical_context)
    
    assert result.routing["persona_hint"] == "professional"


def test_dha_tone_selection():
    """Test DHA tone selection based on entropy"""
    # Low entropy should get sweet_resonance
    low_entropy_context = FusionContext(
        tier="LOWER",
        intent="WHAT",
        domain="general",
        entropy={"total_entropy": 0.3},
        ontology_mass={"lower_mass": 0.7, "upper_mass": 0.3}
    )
    
    candidate = Candidate(
        id="clear",
        text="Clear response",
        source=CandidateSource.LCM,
        channel_scores={"hrm": 0.6, "lcm": 0.8, "moe": 0.6},
        confidence=0.85,
        smi=0.2
    )
    
    engine = FusionEngine()
    result = engine.fuse([candidate], low_entropy_context)
    
    assert result.routing["dha_tone_hint"] == "sweet_resonance"


# Explainability Tests

def test_explanations_generated(basic_context, sample_candidates):
    """Test that explanations are generated"""
    engine = FusionEngine(enable_explanations=True)
    result = engine.fuse(sample_candidates, basic_context)
    
    assert "scores" in result.explain
    assert "ranking" in result.explain
    assert "selection" in result.explain
    assert "routing" in result.explain


def test_explanations_disabled(basic_context, sample_candidates):
    """Test that explanations can be disabled"""
    engine = FusionEngine(enable_explanations=False)
    result = engine.fuse(sample_candidates, basic_context)
    
    assert result.explain == {}


def test_score_explanation_format(basic_context, sample_candidates):
    """Test explanation format for scores"""
    engine = FusionEngine(enable_explanations=True)
    result = engine.fuse(sample_candidates, basic_context)
    
    scores_explain = result.explain["scores"]
    
    for candidate in sample_candidates:
        cid = candidate.id
        assert cid in scores_explain
        assert "fusion_score" in scores_explain[cid]
        assert "channel_scores" in scores_explain[cid]
        assert "relevance" in scores_explain[cid]
        assert "confidence" in scores_explain[cid]


# Fallback Tests

def test_fallback_on_failure(basic_context):
    """Test fallback handling when fusion fails"""
    # Create candidates that will all be filtered out
    bad_candidates = [
        Candidate(
            id="bad",
            text="Bad candidate",
            source=CandidateSource.TEMPLATE,
            channel_scores={"hrm": 0.1, "lcm": 0.1, "moe": 0.1},
            confidence=0.2,  # Very low
            relevance_score=0.1
        )
    ]
    
    # Use regulated context with strict thresholds
    strict_context = FusionContext(
        tier="LOWER",
        intent="HOW",
        domain="medical",
        entropy={"total_entropy": 0.2},
        ontology_mass={"lower_mass": 0.8, "upper_mass": 0.2},
        regulated_mode=True
    )
    
    engine = FusionEngine()
    result = engine.fuse_with_fallback(bad_candidates, strict_context)
    
    assert result.selected_candidate.id == "fallback_generic"
    assert result.metadata.get("fallback") is True


# Weight Adaptation Tests

def test_channel_weight_update():
    """Test updating channel weights"""
    engine = FusionEngine()
    
    new_weights = {
        "hrm": 0.5,
        "lcm": 0.3,
        "moe": 0.2
    }
    
    engine.update_channel_weights(new_weights)
    
    assert engine.channel_weights == new_weights


def test_invalid_weights_raise_error():
    """Test that invalid weights raise error"""
    engine = FusionEngine()
    
    invalid_weights = {
        "hrm": 0.5,
        "lcm": 0.3,
        "moe": 0.3  # Sum = 1.1
    }
    
    with pytest.raises(ValueError, match="must sum to 1.0"):
        engine.update_channel_weights(invalid_weights)


# Integration Tests

def test_end_to_end_fusion_pipeline(sample_candidates):
    """Test complete fusion pipeline"""
    context = FusionContext(
        tier="HYBRID",
        intent="WHY",
        domain="philosophy",
        entropy={"total_entropy": 0.5},
        ontology_mass={"lower_mass": 0.4, "upper_mass": 0.6}
    )
    
    engine = FusionEngine(enable_explanations=True, debug_mode=False)
    result = engine.fuse(sample_candidates, context)
    
    # Validate complete result
    assert result.selected_candidate is not None
    assert 0 <= result.fusion_score <= 1
    assert len(result.ranked_candidates) == 3
    assert result.routing["render_mode"] in ["rules", "llm", "hybrid"]
    assert result.routing["persona_hint"] is not None
    assert result.routing["dha_tone_hint"] is not None
    assert "scores" in result.explain
    assert "ranking" in result.explain


def test_statistics():
    """Test engine statistics"""
    engine = FusionEngine()
    stats = engine.get_statistics()
    
    assert stats["version"] == "3.1.0"
    assert "channel_weights" in stats
    assert "components" in stats
