# DHA Engine v3.0 - Delivery Harmonization & Adaptation Engine

The DHA Engine determines **HOW** the system should deliver responses to users, adapting message tone and style based on user readiness and resistance levels.

## Purpose

The DHA Engine sits at the end of the SOULPI pipeline, taking rendered output and adapting it for optimal user reception. It analyzes user state signals and selects the most appropriate delivery profile to maximize message impact and minimize defensive reactions.

## Pipeline Position

```
FusionEngine -> PersonaEngine -> FusionRenderer -> DHAEngine -> Final Output
```

## Delivery Profiles

| Profile | When Used | Characteristics |
|---------|-----------|-----------------|
| **SWEET_RESONANCE** | High readiness + Low resistance | Warm, supportive, gentle delivery |
| **INVERSE_JOLT** | High resistance | Direct, compressed, truth-forward |
| **SYMBOLIC_METAPHOR** | Low readiness or medium resistance | Indirect, metaphorical framing |

## Quick Start

```python
from symbolu.mechanical.dha import DHAEngine

# Initialize engine
engine = DHAEngine()

# Prepare inputs
renderer_output = {"text": "You need to examine this pattern in your behavior."}
metadata = {
    "readiness_score": 0.7,      # How ready user is to receive (0-1)
    "resistance_score": 0.3,     # User's resistance level (0-1)
    "emotional_entropy": 0.4,    # Emotional chaos indicator (0-1)
    "ego_state": "receptive",    # User's ego state
    "folded_truths": []          # Previously integrated insights
}

# Run the engine
result = engine.run(
    renderer_output=renderer_output,
    metadata=metadata
)

print(f"Profile: {result.delivery_profile}")
print(f"Adapted: {result.adapted_message}")
```

## Inputs

### Required
- `renderer_output`: Output from FusionRenderer containing text to adapt

### Metadata (all optional, defaults provided)
- `readiness_score` (0-1): User's readiness to receive insights
- `resistance_score` (0-1): User's resistance to change/truth
- `emotional_entropy` (0-1): Measure of emotional chaos
- `ego_state`: User's ego state (open, defensive, neutral, etc.)
- `folded_truths`: List of previously integrated insights

## Outputs

```python
DHAOutput:
    delivery_profile: str      # SWEET_RESONANCE | INVERSE_JOLT | SYMBOLIC_METAPHOR
    adapted_message: str       # Modified text ready for delivery
    original_message: str      # Original text before adaptation
    diagnostics: dict          # Detailed analysis and process info
    timestamp: float           # Processing timestamp
```

## Module Structure

```
dha/
├── __init__.py           # Package exports
├── dha_engine.py         # Main orchestrator
├── tone_selector.py      # Delivery profile selection
├── delivery_modulator.py # Text transformation
├── readiness_analyzer.py # Readiness assessment
├── resistance_detector.py # Resistance detection
├── safety_filters.py     # Safety guardrails
├── adaptation_rules.py   # Shared utilities & constants
├── examples.py           # Usage examples
├── README.md             # This file
└── tests/
    ├── __init__.py
    ├── test_dha_engine.py
    ├── test_tone_selector.py
    └── test_resistance_detector.py
```

## Decision Logic

### Tone Selection Matrix

```
                    ┌─────────────────────────────────────────────────┐
                    │              RESISTANCE LEVEL                    │
                    ├─────────────┬─────────────┬─────────────────────┤
                    │    HIGH     │   MEDIUM    │        LOW          │
┌───────────────────┼─────────────┼─────────────┼─────────────────────┤
│ READINESS: HIGH   │ INVERSE     │ RESONANCE   │ SWEET_RESONANCE     │
├───────────────────┼─────────────┼─────────────┼─────────────────────┤
│ READINESS: MEDIUM │ INVERSE     │ METAPHOR    │ SWEET_RESONANCE     │
├───────────────────┼─────────────┼─────────────┼─────────────────────┤
│ READINESS: LOW    │ INVERSE     │ METAPHOR    │ SYMBOLIC_METAPHOR   │
└───────────────────┴─────────────┴─────────────┴─────────────────────┘
```

**Priority Rules:**
1. High resistance -> INVERSE_JOLT (always)
2. High readiness + Low resistance -> SWEET_RESONANCE
3. Medium resistance + Low readiness -> SYMBOLIC_METAPHOR
4. Default/uncertain -> SYMBOLIC_METAPHOR (safest)

## Integration with Other Modules

```python
from symbolu.mechanical.fusion.fusion_engine import FusionEngine
from symbolu.mechanical.persona.engine import PersonaEngine
from symbolu.mechanical.renderer.fusion_renderer import FusionRenderer
from symbolu.mechanical.dha import DHAEngine

# Full pipeline example
fusion = FusionEngine()
persona = PersonaEngine()
renderer = FusionRenderer()
dha = DHAEngine()

# Process through pipeline
fusion_output = fusion.process(query)
persona_output = persona.apply(fusion_output)
renderer_output = renderer.render(persona_output)
final_output = dha.run(
    fusion_output=fusion_output,
    persona_output=persona_output,
    renderer_output=renderer_output,
    metadata=user_metadata
)
```

## Example Input/Output

### Input
```python
renderer_output = {
    "text": "You need to understand that your current approach has fundamental flaws. The pattern you're repeating is causing problems."
}
metadata = {
    "readiness_score": 0.8,
    "resistance_score": 0.2,
    "ego_state": "open"
}
```

### Output (SWEET_RESONANCE selected)
```python
{
    "delivery_profile": "SWEET_RESONANCE",
    "adapted_message": "Perhaps you might find that your current approach has some areas for growth. Consider that the pattern you're repeating could be addressed in ways that serve you better.\n\nTake your time with this.",
    "diagnostics": {
        "readiness_analysis": {"level": "HIGH", "adjusted_score": 0.9},
        "resistance_analysis": {"level": "LOW", "composite_score": 0.15},
        "tone_selection": {
            "profile": "SWEET_RESONANCE",
            "confidence": 0.95,
            "reasoning": "High readiness with low resistance - optimal conditions for gentle delivery"
        }
    }
}
```

## Running Tests

```bash
# Run all DHA tests
pytest mechanical/dha/tests/ -v

# Run specific test file
pytest mechanical/dha/tests/test_dha_engine.py -v

# Run with coverage
pytest mechanical/dha/tests/ --cov=mechanical/dha
```

## Version History

- **v3.0.0**: Initial full implementation
  - Complete pipeline with 5 sub-modules
  - Three delivery profiles
  - Safety filtering
  - Comprehensive test suite

## Author

Symbol-U AGI Team
