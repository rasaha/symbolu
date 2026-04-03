"""
Persona Engine Usage Examples (v2.8.2)
=======================================

Comprehensive examples demonstrating all features of the Persona Engine.
Run this script to see the engine in action.
"""

from models import RendererOutputV3, DHAResult, PersonaProfile
from engine import PersonaEngine
from selector import PersonaSelector
from registry import PersonaRegistry
from default_personas import DEFAULT_PERSONAS


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80 + "\n")


def example_1_basic_usage():
    """Example 1: Basic usage with trading domain."""
    print_section("EXAMPLE 1: Basic Usage - Trading Analysis")
    
    # Initialize engine
    engine = PersonaEngine()
    
    # Create renderer output
    renderer_output = RendererOutputV3(
        symbolic_layer={
            "pattern": "seeking certainty in uncertainty",
            "kosha_state": "VIJNANAMAYA"
        },
        practical_layer={
            "steps": [
                "Assess your risk tolerance",
                "Define position size",
                "Set stop-loss at key support level"
            ]
        },
        mirror_truth_layer={
            "reflection": "avoiding emotional decision-making",
            "bhava_direction": "neutral"
        },
        metadata={
            "tier": "HYBRID",
            "domain": "trading",
            "intent": "how",
            "confidence": {"symbolic": 0.71, "practical": 0.88, "mirror": 0.65}
        }
    )
    
    # Create DHA result
    dha_result = DHAResult(
        tone="resonance",
        confidence=0.82,
        justification={
            "entropy_reason": "Low entropy suggests stability",
            "bhava_reason": "Neutral Bhava supports balanced delivery"
        }
    )
    
    # Create explain log
    explain_log = {
        "meta": {
            "domain": "trading",
            "tier": "HYBRID",
            "intent": "how",
            "bhava_direction": "neutral"
        }
    }
    
    # Apply persona engine
    response = engine.apply(renderer_output, dha_result, explain_log)
    
    # Display results
    print(f"Selected Persona: {response.persona_id} ({response.metadata.persona_name})")
    print(f"DHA Tone: {response.metadata.dha_tone}")
    print(f"\nFormatted Response:\n{'-' * 80}\n{response.text}\n{'-' * 80}")


def example_2_emotional_support():
    """Example 2: Emotional support with friendly persona."""
    print_section("EXAMPLE 2: Emotional Support - Friendly Persona")
    
    engine = PersonaEngine()
    
    renderer_output = RendererOutputV3(
        symbolic_layer={
            "pattern": "grief and acceptance cycle",
            "kosha_state": "MANOMAYA"
        },
        practical_layer={
            "steps": [
                "Acknowledge your feelings without judgment",
                "Reach out to trusted friends or support groups",
                "Allow yourself time to heal"
            ]
        },
        mirror_truth_layer={
            "reflection": "resisting the pain of loss by staying busy",
            "bhava_direction": "downward"
        },
        metadata={
            "tier": "UPPER",
            "domain": "emotional",
            "intent": "why",
            "confidence": {"symbolic": 0.85, "practical": 0.65, "mirror": 0.92}
        }
    )
    
    dha_result = DHAResult(
        tone="resonance",
        confidence=0.88,
        justification={
            "entropy_reason": "Moderate entropy supports gentle delivery"
        }
    )
    
    explain_log = {
        "meta": {
            "domain": "emotional",
            "tier": "UPPER",
            "intent": "why",
            "bhava_direction": "downward"
        }
    }
    
    response = engine.apply(renderer_output, dha_result, explain_log)
    
    print(f"Selected Persona: {response.persona_id} ({response.metadata.persona_name})")
    print(f"Layer Ordering: {list(response.layers.keys())}")
    print(f"\nFormatted Response:\n{'-' * 80}\n{response.text}\n{'-' * 80}")


def example_3_inverse_jolt():
    """Example 3: Inverse jolt tone override."""
    print_section("EXAMPLE 3: Tone Override - Inverse Jolt")
    
    engine = PersonaEngine()
    
    renderer_output = RendererOutputV3(
        symbolic_layer={
            "pattern": "avoiding responsibility through spiritual bypass"
        },
        practical_layer={
            "steps": ["Face the practical consequences", "Take concrete action"]
        },
        mirror_truth_layer={
            "reflection": "You're using spiritual concepts to avoid dealing with reality"
        },
        metadata={
            "tier": "HYBRID",
            "domain": "personal",
            "intent": "how"
        }
    )
    
    # Inverse jolt tone
    dha_result = DHAResult(
        tone="inverse_jolt",
        confidence=0.92,
        justification={
            "entropy_reason": "High entropy requires grounding"
        }
    )
    
    explain_log = {
        "meta": {
            "domain": "personal",
            "tier": "HYBRID",
            "intent": "how"
        }
    }
    
    response = engine.apply(renderer_output, dha_result, explain_log)
    
    print(f"Selected Persona: {response.persona_id}")
    print(f"DHA Tone: {response.metadata.dha_tone} (OVERRIDES persona ordering)")
    print(f"\nNote: Mirror layer comes FIRST with inverse_jolt")
    print(f"\nFormatted Response:\n{'-' * 80}\n{response.text}\n{'-' * 80}")


def example_4_user_override():
    """Example 4: Explicit user persona override."""
    print_section("EXAMPLE 4: User Override - Explicit Persona Request")
    
    engine = PersonaEngine()
    
    # Same renderer output as Example 1 (trading domain)
    renderer_output = RendererOutputV3(
        symbolic_layer={"pattern": "seeking certainty"},
        practical_layer={"steps": ["assess risk", "define position"]},
        mirror_truth_layer={"reflection": "avoiding emotion"},
        metadata={"tier": "HYBRID", "domain": "trading", "intent": "how"}
    )
    
    dha_result = DHAResult(tone="resonance", confidence=0.82, justification={})
    
    explain_log = {
        "meta": {"domain": "trading", "tier": "HYBRID", "intent": "how"}
    }
    
    # User explicitly requests coach persona (instead of default analyst for trading)
    response = engine.apply(
        renderer_output,
        dha_result,
        explain_log,
        user_persona_override="coach"
    )
    
    print(f"Selected Persona: {response.persona_id} (USER OVERRIDE)")
    print(f"Note: Trading domain normally selects 'analyst', but user requested 'coach'")
    print(f"\nFormatted Response:\n{'-' * 80}\n{response.text}\n{'-' * 80}")


def example_5_regulated_domain():
    """Example 5: Regulated domain (medical) always uses regulator."""
    print_section("EXAMPLE 5: Regulated Domain - Medical (Regulator Persona)")
    
    engine = PersonaEngine()
    
    renderer_output = RendererOutputV3(
        symbolic_layer={
            "pattern": "seeking certainty about health condition"
        },
        practical_layer={
            "steps": [
                "Consult with a licensed physician",
                "Request relevant diagnostic tests",
                "Follow medical professional's advice"
            ]
        },
        mirror_truth_layer={
            "reflection": "anxiety about unknown symptoms"
        },
        metadata={
            "tier": "LOWER",
            "domain": "medical",
            "intent": "what"
        }
    )
    
    dha_result = DHAResult(tone="resonance", confidence=0.85, justification={})
    
    explain_log = {
        "meta": {"domain": "medical", "tier": "LOWER", "intent": "what"}
    }
    
    response = engine.apply(renderer_output, dha_result, explain_log)
    
    print(f"Selected Persona: {response.persona_id} (ALWAYS regulator for medical)")
    print(f"Caution Level: 0.95 (highest)")
    print(f"\nFormatted Response:\n{'-' * 80}\n{response.text}\n{'-' * 80}")


def example_6_custom_persona():
    """Example 6: Creating and using a custom persona."""
    print_section("EXAMPLE 6: Custom Persona - The Mentor")
    
    # Create custom persona
    mentor_persona = PersonaProfile(
        id="mentor",
        display_name="The Mentor",
        description="Patient, teaching-focused guidance with emphasis on learning",
        formality=0.6,
        warmth=0.8,
        directness=0.6,
        metaphor_level=0.7,
        structure_level=0.5,
        caution_level=0.5,
        humor_level=0.3,
        preferred_domains=["education", "learning", "teaching"],
        intro_template="Let's explore this together:\n",
        outro_template="\nTake your time to reflect on these insights."
    )
    
    # Register custom persona
    engine = PersonaEngine()
    engine.registry.register(mentor_persona)
    
    renderer_output = RendererOutputV3(
        symbolic_layer={"pattern": "understanding complex concepts"},
        practical_layer={"steps": ["break into components", "practice with examples"]},
        mirror_truth_layer={"reflection": "fear of making mistakes while learning"},
        metadata={"tier": "HYBRID", "domain": "education", "intent": "how"}
    )
    
    dha_result = DHAResult(tone="resonance", confidence=0.80, justification={})
    
    explain_log = {
        "meta": {"domain": "education", "tier": "HYBRID", "intent": "how"}
    }
    
    # Use custom persona
    response = engine.apply(
        renderer_output,
        dha_result,
        explain_log,
        user_persona_override="mentor"
    )
    
    print(f"Selected Persona: {response.persona_id} (CUSTOM)")
    print(f"Persona Name: {response.metadata.persona_name}")
    print(f"\nFormatted Response:\n{'-' * 80}\n{response.text}\n{'-' * 80}")


def example_7_persona_comparison():
    """Example 7: Same content, different personas."""
    print_section("EXAMPLE 7: Persona Comparison - Same Content, Different Styles")
    
    engine = PersonaEngine()
    
    # Same renderer output for all personas
    renderer_output = RendererOutputV3(
        symbolic_layer={"pattern": "fear of failure blocking action"},
        practical_layer={"steps": ["start small", "celebrate progress", "adjust approach"]},
        mirror_truth_layer={"reflection": "perfectionism preventing any movement"},
        metadata={"tier": "HYBRID", "domain": "general", "intent": "how"}
    )
    
    dha_result = DHAResult(tone="resonance", confidence=0.80, justification={})
    
    explain_log = {"meta": {"domain": "general", "tier": "HYBRID", "intent": "how"}}
    
    # Test with different personas
    personas_to_test = ["sage", "analyst", "coach", "friendly"]
    
    for persona_id in personas_to_test:
        response = engine.apply(
            renderer_output,
            dha_result,
            explain_log,
            user_persona_override=persona_id
        )
        
        print(f"\n{persona_id.upper()} PERSONA:")
        print(f"{'-' * 80}")
        print(response.text[:200] + "..." if len(response.text) > 200 else response.text)
        print()


def main():
    """Run all examples."""
    print("\n" + "╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "PERSONA ENGINE v2.8.2 EXAMPLES" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")
    
    # Run examples
    example_1_basic_usage()
    example_2_emotional_support()
    example_3_inverse_jolt()
    example_4_user_override()
    example_5_regulated_domain()
    example_6_custom_persona()
    example_7_persona_comparison()
    
    print("\n" + "=" * 80)
    print(" All examples completed successfully!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
