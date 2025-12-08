"""
FusionEngine v3.1 - Example Usage
Demonstrates practical usage patterns
"""

from symbolu.mechanical.fusion import FusionEngine
from symbolu.mechanical.schemas import Candidate, CandidateSource, FusionContext


def example_1_basic_fusion():
    """Example 1: Basic fusion with three candidates"""
    print("=" * 70)
    print("Example 1: Basic Fusion")
    print("=" * 70)
    
    # Create context from MLCR decision
    context = FusionContext(
        tier="HYBRID",
        intent="WHY",
        domain="philosophy",
        entropy={"total_entropy": 0.5, "H_dim": 0.4, "H_Guna": 0.5, "H_Kosha": 0.6},
        ontology_mass={"lower_mass": 0.4, "upper_mass": 0.6}
    )
    
    # Create candidates
    candidates = [
        Candidate(
            id="abstract_response",
            text="The essence of consciousness lies in the recursive awareness of self.",
            source=CandidateSource.HRM,
            channel_scores={"hrm": 0.9, "lcm": 0.6, "moe": 0.4},
            confidence=0.85,
            relevance_score=0.8,
            smi=0.25
        ),
        Candidate(
            id="clear_explanation",
            text="Consciousness can be defined as the state of being aware of one's surroundings.",
            source=CandidateSource.LCM,
            channel_scores={"hrm": 0.5, "lcm": 0.9, "moe": 0.5},
            confidence=0.9,
            relevance_score=0.75,
            smi=0.15
        ),
        Candidate(
            id="factual_response",
            text="Studies show consciousness involves thalamocortical circuits in the brain.",
            source=CandidateSource.MOE,
            channel_scores={"hrm": 0.4, "lcm": 0.6, "moe": 0.95},
            confidence=0.8,
            relevance_score=0.85,
            domain="neuroscience",
            smi=0.2
        )
    ]
    
    # Run fusion
    engine = FusionEngine(enable_explanations=True)
    result = engine.fuse(candidates, context)
    
    # Display results
    print(f"\nSelected Candidate: {result.selected_candidate.id}")
    print(f"Fusion Score: {result.fusion_score:.4f}")
    print(f"Selected Text: {result.selected_candidate.text[:80]}...")
    print(f"\nRouting:")
    print(f"  Mode: {result.routing['render_mode']}")
    print(f"  Persona: {result.routing['persona_hint']}")
    print(f"  DHA Tone: {result.routing['dha_tone_hint']}")
    print(f"\nTop 3 Rankings:")
    for i, cand in enumerate(result.ranked_candidates[:3], 1):
        score = result.explain['scores'][cand.id]['fusion_score']
        print(f"  {i}. {cand.id} ({score:.4f})")
    print()


def example_2_regulated_mode():
    """Example 2: Regulated mode (medical domain)"""
    print("=" * 70)
    print("Example 2: Regulated Mode (Medical Domain)")
    print("=" * 70)
    
    # Regulated context
    context = FusionContext(
        tier="LOWER",
        intent="HOW",
        domain="medical",
        entropy={"total_entropy": 0.2},
        ontology_mass={"lower_mass": 0.8, "upper_mass": 0.2},
        regulated_mode=True,
        safety_thresholds={"confidence": 0.9, "smi": 0.3}
    )
    
    # Candidates with varying confidence
    candidates = [
        Candidate(
            id="low_confidence",
            text="This might be related to hypertension, possibly.",
            source=CandidateSource.RAG,
            channel_scores={"hrm": 0.5, "lcm": 0.6, "moe": 0.7},
            confidence=0.6,  # Too low for regulated mode
            relevance_score=0.7
        ),
        Candidate(
            id="high_confidence",
            text="Based on clinical guidelines, monitor blood pressure daily.",
            source=CandidateSource.MOE,
            channel_scores={"hrm": 0.6, "lcm": 0.8, "moe": 0.95},
            confidence=0.95,  # Acceptable
            relevance_score=0.9,
            domain="medical",
            smi=0.15
        )
    ]
    
    # Run fusion
    engine = FusionEngine()
    result = engine.fuse(candidates, context)
    
    # Display results
    print(f"\nSelected: {result.selected_candidate.id}")
    print(f"Confidence: {result.selected_candidate.confidence:.2f}")
    print(f"Render Mode: {result.routing['render_mode']}")
    print(f"Use Rules Renderer: {result.routing['use_rules_renderer']}")
    print(f"\nNote: Low confidence candidate was filtered out in regulated mode")
    print()


def example_3_intent_based_selection():
    """Example 3: Intent-based channel preference"""
    print("=" * 70)
    print("Example 3: Intent-Based Selection")
    print("=" * 70)
    
    # Test different intents
    intents = ["WHY", "WHAT", "HOW"]
    
    for intent in intents:
        context = FusionContext(
            tier="HYBRID",
            intent=intent,
            domain="general",
            entropy={"total_entropy": 0.4},
            ontology_mass={"lower_mass": 0.5, "upper_mass": 0.5}
        )
        
        candidates = [
            Candidate(
                id="hrm_strong",
                text="HRM response",
                source=CandidateSource.HRM,
                channel_scores={"hrm": 0.9, "lcm": 0.5, "moe": 0.4},
                confidence=0.8,
                relevance_score=0.7
            ),
            Candidate(
                id="lcm_strong",
                text="LCM response",
                source=CandidateSource.LCM,
                channel_scores={"hrm": 0.4, "lcm": 0.9, "moe": 0.5},
                confidence=0.8,
                relevance_score=0.7
            ),
            Candidate(
                id="moe_strong",
                text="MoE response",
                source=CandidateSource.MOE,
                channel_scores={"hrm": 0.5, "lcm": 0.4, "moe": 0.9},
                confidence=0.8,
                relevance_score=0.7
            )
        ]
        
        engine = FusionEngine()
        result = engine.fuse(candidates, context)
        
        print(f"\nIntent: {intent}")
        print(f"Selected: {result.selected_candidate.id}")
        print(f"Expected: {'hrm_strong' if intent == 'WHY' else 'lcm_strong' if intent == 'WHAT' else 'moe_strong'}")
    
    print()


def example_4_high_smi_penalty():
    """Example 4: SMI penalty for semantic mismatch"""
    print("=" * 70)
    print("Example 4: Semantic Mismatch (SMI) Penalty")
    print("=" * 70)
    
    context = FusionContext(
        tier="HYBRID",
        intent="WHAT",
        domain="communication",
        entropy={"total_entropy": 0.5},
        ontology_mass={"lower_mass": 0.5, "upper_mass": 0.5}
    )
    
    candidates = [
        Candidate(
            id="aligned",
            text="The message is clear and direct.",
            source=CandidateSource.LCM,
            channel_scores={"hrm": 0.7, "lcm": 0.8, "moe": 0.7},
            confidence=0.85,
            relevance_score=0.75,
            smi=0.15  # Low mismatch
        ),
        Candidate(
            id="misaligned",
            text="The communication exhibits profound existential alignment.",
            source=CandidateSource.HRM,
            channel_scores={"hrm": 0.85, "lcm": 0.75, "moe": 0.7},
            confidence=0.85,
            relevance_score=0.75,
            smi=0.85  # High mismatch - saying something different than meaning
        )
    ]
    
    engine = FusionEngine(enable_explanations=True)
    result = engine.fuse(candidates, context)
    
    print(f"\nSelected: {result.selected_candidate.id}")
    print(f"SMI: {result.selected_candidate.smi:.2f}")
    print(f"\nExplanation:")
    print(f"  'aligned' has low SMI (0.15) - inner and outer layers match")
    print(f"  'misaligned' has high SMI (0.85) - semantic mismatch detected")
    print(f"  Despite higher channel scores, high SMI was penalized")
    print()


def example_5_fallback_handling():
    """Example 5: Fallback when all candidates filtered"""
    print("=" * 70)
    print("Example 5: Fallback Handling")
    print("=" * 70)
    
    # Very strict regulated context
    context = FusionContext(
        tier="LOWER",
        intent="HOW",
        domain="legal",
        entropy={"total_entropy": 0.1},
        ontology_mass={"lower_mass": 0.9, "upper_mass": 0.1},
        regulated_mode=True,
        safety_thresholds={"confidence": 0.95}
    )
    
    # Only low-confidence candidates
    candidates = [
        Candidate(
            id="uncertain",
            text="This might be the right answer.",
            source=CandidateSource.RAG,
            channel_scores={"hrm": 0.6, "lcm": 0.6, "moe": 0.7},
            confidence=0.6,  # Too low
            relevance_score=0.6
        )
    ]
    
    # Use fallback
    engine = FusionEngine()
    result = engine.fuse_with_fallback(candidates, context)
    
    print(f"\nFallback Used: {result.metadata.get('fallback', False)}")
    print(f"Selected: {result.selected_candidate.id}")
    print(f"Routing: {result.routing['render_mode']}")
    print(f"\nNote: All candidates were filtered due to strict safety thresholds")
    print()


def example_6_adaptive_weights():
    """Example 6: Adapting channel weights"""
    print("=" * 70)
    print("Example 6: Adaptive Channel Weights")
    print("=" * 70)
    
    context = FusionContext(
        tier="HYBRID",
        intent="WHY",
        domain="philosophy",
        entropy={"total_entropy": 0.5},
        ontology_mass={"lower_mass": 0.3, "upper_mass": 0.7}
    )
    
    candidates = [
        Candidate(
            id="hrm_dominant",
            text="Abstract philosophical response",
            source=CandidateSource.HRM,
            channel_scores={"hrm": 0.95, "lcm": 0.5, "moe": 0.4},
            confidence=0.85,
            relevance_score=0.8
        ),
        Candidate(
            id="moe_dominant",
            text="Factual neuroscience response",
            source=CandidateSource.MOE,
            channel_scores={"hrm": 0.5, "lcm": 0.6, "moe": 0.95},
            confidence=0.9,
            relevance_score=0.85
        )
    ]
    
    # Default weights
    engine_default = FusionEngine()
    result_default = engine_default.fuse(candidates, context)
    
    # Emphasize HRM
    engine_hrm = FusionEngine(channel_weights={"hrm": 0.6, "lcm": 0.2, "moe": 0.2})
    result_hrm = engine_hrm.fuse(candidates, context)
    
    # Emphasize MoE
    engine_moe = FusionEngine(channel_weights={"hrm": 0.2, "lcm": 0.2, "moe": 0.6})
    result_moe = engine_moe.fuse(candidates, context)
    
    print(f"\nDefault weights (0.4, 0.3, 0.3):")
    print(f"  Selected: {result_default.selected_candidate.id}")
    
    print(f"\nHRM-emphasized weights (0.6, 0.2, 0.2):")
    print(f"  Selected: {result_hrm.selected_candidate.id}")
    
    print(f"\nMoE-emphasized weights (0.2, 0.2, 0.6):")
    print(f"  Selected: {result_moe.selected_candidate.id}")
    
    print(f"\nNote: Different weights lead to different selections")
    print()


def main():
    """Run all examples"""
    examples = [
        example_1_basic_fusion,
        example_2_regulated_mode,
        example_3_intent_based_selection,
        example_4_high_smi_penalty,
        example_5_fallback_handling,
        example_6_adaptive_weights,
    ]
    
    for example in examples:
        example()
        input("Press Enter to continue to next example...")
        print("\n" * 2)


if __name__ == "__main__":
    print("\n" * 2)
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "SOULPI FUSIONENGINE v3.1 EXAMPLES" + " " * 20 + "║")
    print("╚" + "═" * 68 + "╝")
    print("\n")
    
    main()
    
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "All examples completed!" + " " * 26 + "║")
    print("╚" + "═" * 68 + "╝")
    print("\n")
