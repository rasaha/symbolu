# P14 - Expression Surface Realizer

## Overview

P14 is the first "surface shaping" phase in the Symbol-U pipeline. It converts upstream frames (PO1–P13 + P9 lexical) into a **SurfacePlan**: a deterministic, safe, minimally expressive plan for how an output should look as text.

**Critical**: P14 produces a **plan**, not text. Downstream renderers consume the SurfacePlan.

## Authority Flow

```
PO1 → PO2 → PO3 → PO4 → PO5 → P6 → P7 → P8 → P9 → P10 → P11 → P12 → P13 → P14 → (Renderers)
```

P14 is:
- **Constrained by P13**: Cannot override P13 safety constraints
- **Pre-acoustic**: No phonemes, no TTS, no audio synthesis
- **Pre-renderer**: Output is consumed by downstream formatters

## Key Design Constraints

1. **Deterministic, zero-LLM, no ML**: All decisions are rule-based
2. **Conservative defaults**: When uncertain, choose stricter behavior
3. **Authority-respecting**: Cannot override PO1–P13 constraints
4. **Sound-agnostic**: No acoustic processing
5. **Output is a plan**: Not final text

## SurfacePlan Structure

The `SurfacePlan` is a frozen (immutable) dataclass with the following components:

### Core Policies

| Field | Type | Description |
|-------|------|-------------|
| `style` | `SurfaceStyle` | Overall surface style (MINIMAL, NEUTRAL, GENTLE, FORMAL, DEFERRAL_MINIMAL) |
| `punctuation` | `PunctuationPolicy` | Allowed punctuation (NONE, BASIC_PERIODS, LIMITED_COMMAS, NO_EXCLAMATION, NO_ELLIPSIS) |
| `hedging` | `HedgePolicy` | Hedging requirements (NONE, LIGHT, REQUIRED) |
| `length` | `LengthPolicy` | Length constraints (ONE_SENTENCE, TWO_SENTENCES_MAX, BULLETS_MAX_3, NO_BULLETS) |
| `persona_signals` | `PersonaSignalPolicy` | Persona signals (NONE, SAFE_ACK, SAFE_REFLECT, SAFE_CLARIFY) |

### Allow/Forbid Lists

| Field | Type | Description |
|-------|------|-------------|
| `allowed_connectors` | `tuple[str, ...]` | Bounded allow-list of connector phrases |
| `forbidden_tokens` | `tuple[str, ...]` | Tokens/phrases that must not appear |

### Flags

| Field | Type | Description |
|-------|------|-------------|
| `requires_question` | `bool` | Whether output must be a question |

## Resolution Rules

### Rule 1: HOLD Regime
```
HOLD regime →
  style = DEFERRAL_MINIMAL
  length = ONE_SENTENCE
  requires_question = True
  allowed_connectors = DEFERRAL_CONNECTORS only
```

### Rule 2: Careful Regimes (DE_ESCALATE, STABILIZE, CAREFUL, REFLECT)
```
CAREFUL regimes →
  style = GENTLE
  hedging = REQUIRED (for non-factual claims)
  length = ONE_SENTENCE or TWO_SENTENCES_MAX
  punctuation = NO_EXCLAMATION
```

### Rule 3: REFLECT Posture / REFLECTION Discourse
```
REFLECTION discourse →
  persona_signals = SAFE_REFLECT
  allowed_connectors = REFLECT_CONNECTORS ("It sounds like...", "I hear...")
  forbidden: "diagnose" style wording
```

### Rule 4: DETACHED + INFORM
```
DETACHED + INFORM →
  style = NEUTRAL or FORMAL (depending on discourse)
  hedging = LIGHT (if UNCERTAINTY slot present)
  bullets allowed if EXPLANATION discourse
```

### Rule 5: RELATIONAL Mode
```
RELATIONAL grounding →
  forbidden_tokens += "you are", "you have", "you feel"
  hedging = REQUIRED (for STATE about others)
```

### Rule 6: P13 Safety Synchronization
```
P13 disallows emphasis →
  punctuation = NO_EXCLAMATION (no !, no ...)
  style ≤ GENTLE (cannot be more expressive)
```

## Connector Allow-Lists

P14 uses strictly bounded connector pools:

| Pool | Allowed Connectors |
|------|-------------------|
| `DEFERRAL_CONNECTORS` | "Could you clarify", "What do you mean by", "I'd like to understand", "Could you help me understand" |
| `REFLECT_CONNECTORS` | "It sounds like", "I hear", "It seems like" |
| `ACK_CONNECTORS` | "I understand", "I see", "Noted" |
| `CLARIFY_CONNECTORS` | "To clarify", "Let me understand", "Could you tell me more about" |

**Never allowed** (NEVER_ALLOWED_CONNECTORS):
- "consider", "to clarify" (lowercase), "that said"
- "however", "but", "therefore", "because", "since"
- "obviously", "clearly", "definitely", "absolutely", "certainly"

## Forbidden Tokens

Default forbidden tokens include:
- Certainty markers: "definitely", "obviously", "clearly", "certainly", "absolutely"
- Directive language: "you should", "you must", "you need to"
- Diagnostic language: "diagnosis", "diagnose", "diagnosed"

For RELATIONAL mode, additional forbidden tokens:
- "you are", "you have", "you feel", "you seem", "you appear", "you're"

## Validation Invariants

The `SurfacePlan` enforces these invariants at construction:

1. HOLD regime → style must be DEFERRAL_MINIMAL, length must be ONE_SENTENCE
2. RELATIONAL mode → forbidden_tokens must include second-person assertions
3. P13 disallows emphasis → punctuation must forbid exclamation
4. allowed_connectors must never contain items from NEVER_ALLOWED_CONNECTORS
5. forbidden_tokens must always include DEFAULT_FORBIDDEN_TOKENS

## Usage

### In Pipeline Orchestrator

```python
from symbolu.mechanical.pipeline.p14_surface import maybe_run_p14

# After P13 stage
maybe_run_p14(ctx)
# ctx.p14_surface is now set
```

### Accessing the Plan

```python
from symbolu.mechanical.pipeline.p14_surface import (
    get_p14_surface_plan,
    is_deferral,
    requires_question,
    get_max_sentences,
    is_forbidden,
)

# Get the plan
plan = get_p14_surface_plan(ctx)

# Check properties
if is_deferral(ctx):
    # Handle deferral mode
    pass

if requires_question(ctx):
    # Ensure output is a question
    pass

max_sentences = get_max_sentences(ctx)

# Check if a token is forbidden
if is_forbidden(ctx, "definitely"):
    # Token should not be used
    pass
```

### Direct Resolution (Testing)

```python
from symbolu.mechanical.pipeline.p14_surface import run_p14_directly

plan = run_p14_directly(ctx)
# Plan is returned but NOT attached to context
```

## Non-Goals

P14 does **NOT**:
- Generate final sentence text
- Implement a templating engine (that is downstream)
- Process phonemes
- Require spaCy or other NLP dependencies

## Module Structure

```
symbolu/mechanical/pipeline/p14_surface/
├── __init__.py              # Public API exports
├── p14_surface_schema.py    # SurfacePlan dataclass and enums
├── p14_surface_realizer.py  # P14SurfaceRealizer implementation
├── p14_integration.py       # Pipeline integration (maybe_run_p14)
└── README.md                # This documentation

symbolu/mechanical/pipeline/tests/p14_surface/
├── __init__.py
└── test_p14_surface.py      # Comprehensive test suite (80+ tests)
```

## Test Coverage

The test suite covers:
- HOLD regime behavior (10 tests)
- Careful regime behavior (8 tests)
- REFLEXIVE vs RELATIONAL differences (7 tests)
- UNCERTAINTY slot handling (3 tests)
- P13 safety synchronization (4 tests)
- Determinism (4 tests)
- Connector allow-list enforcement (7 tests)
- Regression tests for forbidden defaults (10 tests)
- Schema validation (9 tests)
- Integration functions (11 tests)
- Resolution function unit tests (12 tests)
- Edge cases (4 tests)
- Helper method tests (5 tests)

**Target: 80+ tests**

## Version

Current version: `P14_VERSION = "1.0.0"`
