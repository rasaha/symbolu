# Symbol-U Pipeline v3.0

> **Note:** This directory documents the execution pipeline and context orchestration.
> It does not define phase logic, authority, or decision-making.
> Phase behavior is documented under `/docs/phases`.

Linear pipeline orchestrator with Option C router hooks for the Symbol-U AGI system.

## Overview

The v3.0 pipeline provides a clean, production-safe sequential flow through all Symbol-U reasoning engines:

```
UserRequest
    |
    v
[1. MLCR]          Multi-Layer Consciousness Routing
    |               -> Intent, Tier, Entropy analysis
    v
[2. Persona]       Communicative Identity Resolution
    |               -> Persona selection (sage/analyst/coach/etc.)
    v
[Router]           Option C Routing Decision
    |               -> v3.0: always "linear"
    v
[3. Fusion]        Multi-Channel Candidate Blending
    |               -> HRM/LCM/MoE channel fusion
    v
[4. DHA]           Delivery Harmonization & Adaptation
    |               -> Readiness/Resistance -> Tone profile
    v
[5. Renderer]      Final Output Surface
    |
    v
RenderedOutput
```

## Quick Start

```python
from mechanical.pipeline import SymbolUPipeline, UserRequest

# Create pipeline
pipeline = SymbolUPipeline()

# Create request
request = UserRequest(
    text="Why do I feel stuck in my career?",
    user_id="user_001",
    render_mode="standard",  # minimal | standard | enhanced | regulated
)

# Run pipeline
result = pipeline.run(request)

# Access output
print(result.raw_text)       # Final adapted text
print(result.mode)           # Render mode used
print(result.meta)           # Pipeline metadata (persona, tone, etc.)
```

## Render Modes

| Mode | Description |
|------|-------------|
| `minimal` | Practical layer only, fastest |
| `standard` | All 3 layers (symbolic, practical, mirror-truth) |
| `enhanced` | Symbolic expanded, practical condensed |
| `regulated` | Compliance-safe, minimal metaphors |

## Pipeline Stages

### 1. MLCR (Multi-Layer Consciousness RAG)
Analyzes the query to understand:
- **Intent**: why / how / what / action
- **Tier**: UPPER (philosophical) / LOWER (practical) / HYBRID
- **Entropy**: H_D (domain), H_G (goal), H_K (knowledge)
- **Ontology Mass**: lower/upper conceptual weights

### 2. Persona Resolution
Selects the appropriate communicative voice:
- `sage` - Philosophical, deep exploration
- `analyst` - Structured, factual analysis
- `coach` - Action-oriented guidance
- `friendly` - Supportive, empathetic
- `regulator` - Compliance-safe (regulated domains)
- `neutral` - Default balanced voice

### 3. Fusion Engine
Blends candidates from three reasoning channels:
- **HRM** (High-Reasoning Module): Symbolic/abstract reasoning
- **LCM** (Linguistic Coherence Module): Semantic clarity
- **MoE** (Mixture of Experts): Domain-specific knowledge

### 4. DHA (Delivery Harmonization & Adaptation)
Adapts delivery based on user state:
- **Readiness Level**: HIGH / MEDIUM / LOW
- **Resistance Detection**: Pattern analysis
- **Delivery Profile**:
  - `SWEET_RESONANCE` - Harmonious, supportive
  - `INVERSE_JOLT` - Direct, pattern-breaking
  - `SYMBOLIC_METAPHOR` - Reframing through metaphor

### 5. Renderer
Generates the final output with:
- Adapted text from DHA
- Mode-specific formatting
- Complete metadata trace

## Option C Router (Future)

v3.0 uses a linear-only router. Future versions (v3.1+) will enable adaptive routing:

| Mode | Description |
|------|-------------|
| `linear` | Sequential flow (v3.0 default) |
| `dha_first` | Early DHA for high-resistance detection |
| `dual_branch` | Parallel symbolic + practical paths |
| `resistance_loop` | Iterative adaptation for difficult cases |
| `entropy_priority` | Dynamic ordering based on uncertainty |

## Customizing the Pipeline

### Custom Readiness/Resistance

```python
request = UserRequest(
    text="I want to change but I'm scared",
    metadata={
        "readiness_score": 0.4,    # 0-1, user's openness
        "resistance_score": 0.7,   # 0-1, defensive patterns
        "ego_state": "defensive",  # open / defensive / etc.
    },
)
```

### Custom Persona Override

```python
request = UserRequest(
    text="Help me understand this",
    metadata={
        "persona_override": "sage",  # Force specific persona
    },
)
```

### Accessing Pipeline Metadata

```python
result = pipeline.run(request)

# Full metadata
print(result.meta["persona_id"])      # Selected persona
print(result.meta["tone_profile"])    # DHA delivery profile
print(result.meta["readiness_level"]) # User readiness assessment
print(result.meta["mlcr_tier"])       # MLCR routing tier
print(result.meta["mlcr_intent"])     # Detected intent
print(result.meta["router_mode"])     # Router decision (always "linear" in v3.0)
```

## Running Examples

```bash
# From project root
python -m mechanical.pipeline.examples
```

## File Structure

```
mechanical/pipeline/
├── __init__.py        # Public exports
├── models.py          # Data models (UserRequest, RenderedOutput, etc.)
├── routing.py         # Option C router abstraction
├── orchestrator.py    # Main SymbolUPipeline class
├── validators.py      # Stage validation utilities
├── examples.py        # Demo script
├── README.md          # This file
└── tests/
    └── test_orchestrator_smoke.py  # Smoke tests
```

## Dependencies

The pipeline orchestrates existing engines:
- `mechanical.mlcr` - MLCR v3.1
- `mechanical.persona` - Persona Engine v2.8.2
- `mechanical.fusion` - Fusion Engine v3.1
- `mechanical.dha` - DHA Engine v3.0
- `mechanical.renderer` - FusionRenderer v3.0

## Version History

- **v3.0**: Linear pipeline with Option C router stub
- **v3.1** (planned): Adaptive routing modes
- **v3.2** (planned): RAG integration for real candidate retrieval

---

*Symbol-U AGI - Consciousness-Aware AI*
