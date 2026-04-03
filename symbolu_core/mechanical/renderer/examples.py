"""
SOULPI Fusion Renderer v3.0 - Usage Examples
=============================================

Demonstrates various usage scenarios:
1. Basic rendering (all modes)
2. Domain-specific rendering
3. Layer-by-layer access
4. JSON output
5. Statistics tracking
6. Error handling

Run with: python examples.py
"""

import json
from fusion_renderer import (
    FusionRenderer,
    FusionOutput,
    RenderMode,
    Domain,
    render_fusion_output
)


# ============================================================================
# EXAMPLE 1: BASIC RENDERING
# ============================================================================

def example_basic_rendering():
    """Basic rendering with standard mode"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Rendering (Standard Mode)")
    print("="*70)
    
    # Create sample FusionOutput
    fusion_output = FusionOutput(
        query="How can AI improve healthcare?",
        merged_response="AI can improve healthcare through predictive analytics, diagnostic assistance, and personalized treatment. Machine learning models can identify patterns in medical data. However, ethical considerations and regulatory compliance are essential.",
        hrm_content={
            "reasoning": "Healthcare AI represents symbolic integration of data patterns. Therefore, predictive capabilities emerge from pattern recognition. This suggests potential for early intervention.",
            "depth": 0.75
        },
        lcm_content={
            "content": "AI improves diagnostics. Machine learning analyzes medical images. Algorithms predict patient outcomes. Personalized medicine becomes possible.",
            "clarity": 0.85
        },
        moe_content={
            "content": "Healthcare requires FDA approval. Must ensure patient privacy under HIPAA. Step 1: Validate models clinically. Step 2: Obtain regulatory clearance. Cannot replace human judgment.",
            "domain": "healthcare",
            "constraints": [
                "FDA approval required",
                "HIPAA compliance mandatory",
                "Clinical validation needed"
            ],
            "procedures": [
                "Conduct clinical trials",
                "Submit for regulatory review",
                "Implement privacy safeguards"
            ]
        },
        channel_weights={
            "hrm": 0.4,
            "lcm": 0.35,
            "moe": 0.25
        },
        conflict_resolution=[
            {
                "source1": "hrm",
                "source2": "moe",
                "type": "abstraction_vs_regulation",
                "resolution": "Balance symbolic insight with regulatory requirements"
            }
        ],
        metadata={
            "query_type": "applied_research",
            "complexity": "medium-high",
            "domain": "healthcare"
        }
    )
    
    # Render using convenience function
    output = render_fusion_output(fusion_output)
    
    # Display results
    print(f"\nQuery: {output.query}")
    print(f"Mode: {output.mode}")
    print(f"\n--- Symbolic Layer (WHY) ---")
    if output.symbolic_layer:
        print(f"Theme: {output.symbolic_layer.theme}")
        print(f"Archetype: {output.symbolic_layer.archetype}")
        print(f"Causal Patterns: {output.symbolic_layer.causal_patterns}")
        print(f"Dominant Channel: {output.symbolic_layer.dominant_channel}")
    
    print(f"\n--- Practical Layer (WHAT/HOW) ---")
    if output.practical_layer:
        print(f"Key Facts: {output.practical_layer.key_facts}")
        print(f"Constraints: {output.practical_layer.constraints}")
        print(f"Procedures: {output.practical_layer.procedures[:2]}")  # First 2
        print(f"Coherence Score: {output.practical_layer.coherence_score:.2f}")
    
    print(f"\n--- Mirror-Truth Layer (Reflective Synthesis) ---")
    if output.mirror_truth_layer:
        print(f"Contradictions: {len(output.mirror_truth_layer.contradictions)}")
        print(f"Alignment Score: {output.mirror_truth_layer.alignment_score:.2f}")
        print(f"Stability: {output.mirror_truth_layer.stability_indicator}")
        print(f"Reflection: {output.mirror_truth_layer.reflection}")


# ============================================================================
# EXAMPLE 2: MODE COMPARISON
# ============================================================================

def example_mode_comparison():
    """Compare different rendering modes"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Mode Comparison")
    print("="*70)
    
    # Create sample data
    fusion_output = FusionOutput(
        query="What is machine learning?",
        merged_response="Machine learning is a subset of AI that enables systems to learn from data. It involves training algorithms on datasets to make predictions or decisions.",
        hrm_content={
            "reasoning": "ML represents pattern abstraction from experience. Therefore, learning emerges from statistical regularities.",
            "depth": 0.6
        },
        lcm_content={
            "content": "Machine learning trains models. Algorithms learn from data. Predictions improve over time.",
            "clarity": 0.9
        },
        moe_content={
            "content": "Common algorithms include neural networks, decision trees, and SVMs. Must validate on test data. Requires computational resources.",
            "domain": "computer_science"
        },
        channel_weights={"hrm": 0.35, "lcm": 0.40, "moe": 0.25},
        conflict_resolution=[],
        metadata={}
    )
    
    # Test each mode
    modes = [RenderMode.MINIMAL, RenderMode.STANDARD, RenderMode.SYMBOLIC, RenderMode.REGULATED]
    
    for mode in modes:
        print(f"\n--- {mode.value.upper()} MODE ---")
        renderer = FusionRenderer(mode=mode)
        output = renderer.render(fusion_output)
        
        print(f"Symbolic Layer: {'Yes' if output.symbolic_layer else 'No'}")
        print(f"Practical Layer: {'Yes' if output.practical_layer else 'No'}")
        print(f"Mirror-Truth Layer: {'Yes' if output.mirror_truth_layer else 'No'}")
        
        if output.practical_layer:
            print(f"Practical Facts Count: {len(output.practical_layer.key_facts)}")


# ============================================================================
# EXAMPLE 3: DOMAIN-SPECIFIC RENDERING
# ============================================================================

def example_domain_rendering():
    """Demonstrate domain-specific rendering (regulated vs general)"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Domain-Specific Rendering")
    print("="*70)
    
    # Financial domain query
    financial_output = FusionOutput(
        query="What are the risks of cryptocurrency investment?",
        merged_response="Cryptocurrency investments carry high volatility risk, regulatory uncertainty, and cybersecurity concerns. Diversification and risk management are essential.",
        hrm_content={
            "reasoning": "Crypto risk emerges from decentralization paradox. Therefore, freedom implies uncertainty.",
            "depth": 0.7
        },
        lcm_content={
            "content": "Cryptocurrencies are volatile. Prices fluctuate rapidly. Regulatory status varies by country.",
            "clarity": 0.8
        },
        moe_content={
            "content": "SEC regulates certain crypto assets. Must report capital gains. Cannot guarantee returns.",
            "domain": "finance",
            "constraints": ["SEC oversight", "Capital gains taxation", "No FDIC insurance"]
        },
        channel_weights={"hrm": 0.3, "lcm": 0.35, "moe": 0.35},
        conflict_resolution=[],
        metadata={"domain": "finance"}
    )
    
    # Compare general vs regulated rendering
    print("\n--- GENERAL DOMAIN ---")
    general_renderer = FusionRenderer(mode=RenderMode.STANDARD, domain=Domain.GENERAL)
    general_output = general_renderer.render(financial_output)
    print(f"Is Regulated: {general_output.metadata['is_regulated']}")
    if general_output.symbolic_layer:
        print(f"Symbolic Theme: {general_output.symbolic_layer.theme}")
    
    print("\n--- FINANCE DOMAIN (Regulated) ---")
    finance_renderer = FusionRenderer(mode=RenderMode.REGULATED, domain=Domain.FINANCE)
    finance_output = finance_renderer.render(financial_output)
    print(f"Is Regulated: {finance_output.metadata['is_regulated']}")
    if finance_output.symbolic_layer:
        print(f"Symbolic Theme: {finance_output.symbolic_layer.theme}")
    print("(Note: Regulated mode minimizes metaphors)")


# ============================================================================
# EXAMPLE 4: JSON OUTPUT
# ============================================================================

def example_json_output():
    """Generate JSON output for API integration"""
    print("\n" + "="*70)
    print("EXAMPLE 4: JSON Output")
    print("="*70)
    
    fusion_output = FusionOutput(
        query="Explain quantum computing",
        merged_response="Quantum computing uses quantum bits (qubits) that can exist in superposition. This enables parallel processing of multiple states simultaneously.",
        hrm_content={
            "reasoning": "Quantum mechanics enables computational superposition.",
            "depth": 0.9
        },
        lcm_content={
            "content": "Qubits enable superposition. Quantum computers process multiple states. This provides computational advantages.",
            "clarity": 0.7
        },
        moe_content={
            "content": "Requires cryogenic cooling. Error rates are high. Limited practical applications currently.",
            "domain": "quantum_physics"
        },
        channel_weights={"hrm": 0.5, "lcm": 0.3, "moe": 0.2},
        conflict_resolution=[],
        metadata={"complexity": "very_high"}
    )
    
    renderer = FusionRenderer()
    output = renderer.render(fusion_output)
    
    # Generate JSON
    json_output = output.to_json(indent=2)
    print("\nJSON Output (truncated):")
    print(json_output[:500] + "\n...")
    
    # Parse back
    parsed = json.loads(json_output)
    print(f"\nParsed Query: {parsed['query']}")
    print(f"Parsed Mode: {parsed['mode']}")


# ============================================================================
# EXAMPLE 5: LAYER-BY-LAYER ACCESS
# ============================================================================

def example_layer_access():
    """Access individual layers programmatically"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Layer-by-Layer Access")
    print("="*70)
    
    fusion_output = FusionOutput(
        query="How does climate change affect agriculture?",
        merged_response="Climate change impacts agriculture through temperature shifts, precipitation changes, and extreme weather events. Adaptation strategies are necessary.",
        hrm_content={
            "reasoning": "Climate-agriculture coupling creates systemic feedback. Therefore, changes cascade through food systems.",
            "depth": 0.8
        },
        lcm_content={
            "content": "Temperature rises affect crop yields. Rainfall patterns shift. Droughts become more common.",
            "clarity": 0.85
        },
        moe_content={
            "content": "Farmers must adapt crop varieties. Irrigation systems need upgrading. Must monitor soil health.",
            "domain": "agriculture",
            "procedures": [
                "Select drought-resistant varieties",
                "Improve irrigation efficiency",
                "Monitor soil conditions"
            ]
        },
        channel_weights={"hrm": 0.4, "lcm": 0.35, "moe": 0.25},
        conflict_resolution=[],
        metadata={}
    )
    
    renderer = FusionRenderer()
    output = renderer.render(fusion_output)
    
    # Access symbolic layer
    print("\n--- SYMBOLIC LAYER ---")
    if output.symbolic_layer:
        print(f"Reasoning Depth: {output.symbolic_layer.reasoning_depth:.2f}")
        print(f"Meaning Vectors:")
        for key, value in output.symbolic_layer.meaning_vectors.items():
            print(f"  {key}: {value:.2f}")
    
    # Access practical layer
    print("\n--- PRACTICAL LAYER ---")
    if output.practical_layer:
        print(f"Domain: {output.practical_layer.domain}")
        print(f"Coherence: {output.practical_layer.coherence_score:.2f}")
        print(f"Actionable Items:")
        for item in output.practical_layer.actionable_items:
            print(f"  - {item}")
    
    # Access mirror-truth layer
    print("\n--- MIRROR-TRUTH LAYER ---")
    if output.mirror_truth_layer:
        print(f"Alignment: {output.mirror_truth_layer.alignment_score:.2f}")
        print(f"Entropy Measures:")
        for key, value in output.mirror_truth_layer.entropy_measures.items():
            print(f"  {key}: {value:.3f}")


# ============================================================================
# EXAMPLE 6: STATISTICS TRACKING
# ============================================================================

def example_statistics():
    """Track rendering statistics"""
    print("\n" + "="*70)
    print("EXAMPLE 6: Statistics Tracking")
    print("="*70)
    
    renderer = FusionRenderer()
    
    # Create multiple queries
    queries = [
        "What is AI?",
        "How does blockchain work?",
        "Explain neural networks",
        "What is deep learning?",
        "How does NLP work?"
    ]
    
    print("\nProcessing 5 queries...")
    for query in queries:
        fusion_output = FusionOutput(
            query=query,
            merged_response=f"Response to: {query}",
            hrm_content={"reasoning": "Analysis"},
            lcm_content={"content": "Explanation"},
            moe_content={"content": "Details"},
            channel_weights={"hrm": 0.33, "lcm": 0.33, "moe": 0.34},
            conflict_resolution=[],
            metadata={}
        )
        renderer.render(fusion_output)
    
    # Get statistics
    stats = renderer.get_stats()
    print(f"\nTotal Renders: {stats['total_renders']}")
    print(f"Average Render Time: {stats['avg_render_time_ms']:.2f} ms")
    print(f"Mode Counts: {stats['mode_counts']}")


# ============================================================================
# EXAMPLE 7: ERROR HANDLING
# ============================================================================

def example_error_handling():
    """Demonstrate error handling"""
    print("\n" + "="*70)
    print("EXAMPLE 7: Error Handling")
    print("="*70)
    
    # Invalid weights (don't sum to 1.0)
    print("\n--- Testing Invalid Weights ---")
    try:
        invalid_output = FusionOutput(
            query="Test",
            merged_response="Test",
            hrm_content={},
            lcm_content={},
            moe_content={},
            channel_weights={"hrm": 0.5, "lcm": 0.3, "moe": 0.3},  # Sums to 1.1
            conflict_resolution=[],
            metadata={}
        )
        renderer = FusionRenderer()
        renderer.render(invalid_output)
    except ValueError as e:
        print(f"✓ Caught expected error: {e}")
    
    # Valid minimal input (should work)
    print("\n--- Testing Minimal Valid Input ---")
    try:
        minimal_output = FusionOutput(
            query="Test",
            merged_response="Test",
            hrm_content={},
            lcm_content={},
            moe_content={},
            channel_weights={"hrm": 0.33, "lcm": 0.33, "moe": 0.34},
            conflict_resolution=[],
            metadata={}
        )
        renderer = FusionRenderer()
        output = renderer.render(minimal_output)
        print("✓ Minimal input rendered successfully")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("SOULPI FUSION RENDERER v3.0 - USAGE EXAMPLES")
    print("="*70)
    
    examples = [
        ("Basic Rendering", example_basic_rendering),
        ("Mode Comparison", example_mode_comparison),
        ("Domain-Specific Rendering", example_domain_rendering),
        ("JSON Output", example_json_output),
        ("Layer-by-Layer Access", example_layer_access),
        ("Statistics Tracking", example_statistics),
        ("Error Handling", example_error_handling)
    ]
    
    for name, example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"\n✗ Error in {name}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print("ALL EXAMPLES COMPLETED")
    print("="*70)


if __name__ == "__main__":
    main()
