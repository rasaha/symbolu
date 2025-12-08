"""
SOULPI Persona Engine v2.8.2
=============================

The Persona Engine is SOULPI's expression layer that transforms deterministic
cognitive analysis into persona-styled responses without altering meaning.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Quick Start](#quick-start)
5. [Available Personas](#available-personas)
6. [API Reference](#api-reference)
7. [Testing](#testing)
8. [Examples](#examples)

## Overview

### Purpose

The Persona Engine receives:
- **RendererOutputV3**: Three-layer analysis (symbolic, practical, mirror)
- **DHAResult**: Tone selection (resonance, inverse_jolt, symbolic)
- **Explain Log**: Processing metadata (tier, domain, intent, bhava)

And produces:
- **PersonaResponse**: Persona-styled text with preserved analytical layers

### Pipeline Position

```
MLCR → Hybrid Fusion Engine → FusionRenderer v3.0 → 
DHA Tone Engine v2.8.1 → Persona Engine v2.8.2 → 
LLM Enhancement Layer (optional) → Final Output
```

### Core Principles

1. **NEVER modifies layer contents** - Only controls ordering and framing
2. **Deterministic selection** - No ML, only rule-based logic
3. **Preserves metadata** - Complete audit trail
4. **Tone-aware ordering** - DHA tone overrides persona preferences

## Architecture

### Components

#### 1. PersonaEngine
Main engine that coordinates all operations:
- Persona selection (via PersonaSelector)
- Layer ordering (based on tone + persona)
- Text composition (intro + headers + content + outro)
- Metadata tracking

#### 2. PersonaSelector
Deterministic logic for choosing personas:
- User override (highest priority)
- Regulated domain check
- Domain-specific mapping
- Tier-based selection
- Intent-based selection
- Bhava-based adjustment
- Fallback to neutral

#### 3. PersonaRegistry
Storage and retrieval of persona profiles:
- Default personas (sage, analyst, coach, friendly, regulator, neutral)
- Custom persona registration
- Thread-safe operations

#### 4. Data Models
Pydantic models for type safety:
- PersonaProfile
- RendererOutputV3
- DHAResult
- PersonaResponse
- PersonaMetadata

## Installation

```bash
# Install dependencies
pip install pydantic

# Import the module
from symbolu.mechanical.persona import (
    PersonaEngine,
    PersonaSelector,
    PersonaRegistry,
    get_default_registry
)
```

## Quick Start

```python
from symbolu.mechanical.persona import PersonaEngine
from symbolu.mechanical.persona.models import RendererOutputV3, DHAResult

# Initialize engine
engine = PersonaEngine()

# Create inputs
renderer_output = RendererOutputV3(
    symbolic_layer={"pattern": "seeking certainty"},
    practical_layer={"steps": ["assess risk", "define position"]},
    mirror_truth_layer={"reflection": "avoiding emotion"},
    metadata={
        "tier": "HYBRID",
        "domain": "trading",
        "intent": "how",
        "confidence": {"symbolic": 0.71, "practical": 0.88}
    }
)

dha_result = DHAResult(
    tone="resonance",
    confidence=0.82,
    justification={}
)

explain_log = {
    "meta": {
        "domain": "trading",
        "tier": "HYBRID",
        "intent": "how"
    }
}

# Apply persona styling
response = engine.apply(renderer_output, dha_result, explain_log)

print(f"Persona: {response.persona_id}")
print(f"Text: {response.text}")
```

## Available Personas

### 1. The Sage
- **ID**: `sage`
- **Style**: Symbolic, reflective, philosophical
- **Domains**: spiritual, philosophical, meaning, consciousness
- **Best for**: UPPER tier, "why" intent, upward Bhava
- **Traits**: High metaphor (0.9), low directness (0.3)

### 2. The Analyst
- **ID**: `analyst`
- **Style**: Structured, data-driven, rigorous
- **Domains**: trading, financial, technical, data
- **Best for**: HYBRID/LOWER tier, "how/what" intent
- **Traits**: High structure (0.9), high directness (0.9)

### 3. The Coach
- **ID**: `coach`
- **Style**: Action-oriented, direct, motivational
- **Domains**: execution, action, goals, implementation
- **Best for**: LOWER tier, "how" intent, downward Bhava
- **Traits**: Very high directness (0.95), high warmth (0.6)

### 4. The Friendly Guide
- **ID**: `friendly`
- **Style**: Warm, empathetic, supportive
- **Domains**: emotional, relationship, personal, wellbeing
- **Best for**: Emotional domain, downward Bhava
- **Traits**: Very high warmth (0.95), low structure (0.3)

### 5. The Regulator
- **ID**: `regulator`
- **Style**: Cautious, compliant, risk-aware
- **Domains**: medical, legal, regulatory, compliance
- **Best for**: Regulated domains (always selected)
- **Traits**: Very high caution (0.95), high formality (0.9)

### 6. Neutral Voice
- **ID**: `neutral`
- **Style**: Objective, balanced, minimal personality
- **Domains**: General purpose (fallback)
- **Best for**: Unknown context or explicit neutrality
- **Traits**: All traits at 0.5 (balanced)

## API Reference

### PersonaEngine.apply()

```python
def apply(
    self,
    renderer_output: RendererOutputV3,
    dha_result: DHAResult,
    explain_log: Dict[str, Any],
    user_persona_override: Optional[str] = None
) -> PersonaResponse
```

**Parameters:**
- `renderer_output`: Output from FusionRenderer v3.0
- `dha_result`: Result from DHA Tone Engine v2.8.1
- `explain_log`: MLCR explain log with metadata
- `user_persona_override`: Optional explicit persona request

**Returns:**
- `PersonaResponse` with styled text and preserved layers

### PersonaSelector.auto_select()

```python
def auto_select(
    self,
    explain_log: Dict[str, Any],
    user_override: Optional[str] = None
) -> str
```

**Parameters:**
- `explain_log`: Metadata for selection logic
- `user_override`: Optional explicit persona ID

**Returns:**
- Persona ID (str)

### PersonaRegistry.get()

```python
def get(self, persona_id: str) -> PersonaProfile
```

**Parameters:**
- `persona_id`: Unique persona identifier

**Returns:**
- `PersonaProfile` object

**Raises:**
- `KeyError` if persona not found

## Testing

Run the complete test suite:

```bash
# Run all tests
pytest test_persona_engine.py -v

# Run specific test class
pytest test_persona_engine.py::TestPersonaSelector -v

# Run with coverage
pytest test_persona_engine.py --cov=symbolu.mechanical.persona
```

Test coverage includes:
- ✅ Persona selection logic (domain, tier, intent, bhava)
- ✅ Layer ordering (tone overrides, persona preferences)
- ✅ Text composition (intro, headers, outro)
- ✅ Layer integrity (no mutation)
- ✅ Metadata propagation (complete audit trail)
- ✅ Edge cases (empty inputs, invalid personas)
- ✅ Integration tests (end-to-end scenarios)

## Examples

### Example 1: Trading Analysis

```python
# Analyst persona for trading domain
explain_log = {
    "meta": {
        "domain": "trading",
        "tier": "HYBRID",
        "intent": "how"
    }
}

response = engine.apply(renderer_output, dha_result, explain_log)
# Persona: analyst
# Ordering: practical → symbolic → mirror
# Intro: "Let's break this down step-by-step:"
```

### Example 2: Emotional Support

```python
# Friendly persona for emotional domain
explain_log = {
    "meta": {
        "domain": "emotional",
        "tier": "UPPER",
        "intent": "why"
    }
}

response = engine.apply(renderer_output, dha_result, explain_log)
# Persona: friendly
# Ordering: mirror → symbolic → practical
# Intro: "I understand what you're experiencing:"
```

### Example 3: User Override

```python
# Explicit user request for coach
response = engine.apply(
    renderer_output,
    dha_result,
    explain_log,
    user_persona_override="coach"
)
# Persona: coach (regardless of domain/tier/intent)
# Ordering: mirror → practical → symbolic
# Intro: "Here's what you need to do:"
```

### Example 4: Tone Override

```python
# Inverse jolt tone overrides persona ordering
dha_result = DHAResult(tone="inverse_jolt", confidence=0.92, justification={})

response = engine.apply(renderer_output, dha_result, explain_log)
# Ordering: mirror → practical → symbolic (regardless of persona)
# Header: "● Direct truth:" (for mirror layer)
```

### Example 5: Custom Persona

```python
from symbolu.mechanical.persona.models import PersonaProfile

# Create custom persona
custom_persona = PersonaProfile(
    id="mentor",
    display_name="The Mentor",
    description="Patient, teaching-focused guidance",
    formality=0.6,
    warmth=0.8,
    directness=0.6,
    metaphor_level=0.7,
    structure_level=0.5,
    caution_level=0.5,
    humor_level=0.3,
    preferred_domains=["education", "learning"],
    intro_template="Let's explore this together:\n",
    outro_template="\nTake your time to reflect on these insights."
)

# Register with engine
engine.registry.register(custom_persona)

# Use it
response = engine.apply(
    renderer_output,
    dha_result,
    explain_log,
    user_persona_override="mentor"
)
```

## Version History

- **v2.8.2** (December 2025)
  - Initial release
  - 6 default personas
  - Complete test suite
  - Full documentation

## License

Copyright (c) 2025 Rakesh Mohan
All rights reserved.

## Support

For questions or issues, contact: rakesh@soulpi.com
"""
