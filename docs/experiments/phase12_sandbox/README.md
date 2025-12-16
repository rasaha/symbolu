# Phase-12: Governed Generative Layer

## Overview

Phase-12 introduces **probabilistic generation** while preserving the **deterministic governance** established in Phase-11B.

```
┌─────────────────────────────────────────────────────────────────┐
│              GOVERNED GENERATIVE COMPILER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INPUT                                                           │
│    ↓                                                             │
│  Phase-11B.3 ──────────────────────────────────────────────────  │
│    ├── Ontological Routing      (deterministic)                  │
│    ├── PPV Canonicalization     (deterministic)                  │
│    └── Template Registry        (deterministic)                  │
│    ↓                                                             │
│  Phase-12 ─────────────────────────────────────────────────────  │
│    ├── PPV Encoding             (deterministic)                  │
│    ├── Template Retrieval       (deterministic)                  │
│    ├── Context Assembly         (deterministic)                  │
│    ├── LLM Generation           (PROBABILISTIC) ← only here      │
│    └── Verification             (deterministic)                  │
│    ↓                                                             │
│  OUTPUT (or GENERATION_BLOCKED)                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Key Principle

**Probabilistic generation is sandwiched between deterministic layers.**

| Layer | Deterministic | Probabilistic |
|-------|---------------|---------------|
| Ontological Routing | ✅ | |
| PPV Canonicalization | ✅ | |
| PPV Encoding | ✅ | |
| Template Retrieval | ✅ | |
| Context Assembly | ✅ | |
| **LLM Generation** | | ✅ |
| Verification | ✅ | |
| Ledger Recording | ✅ | |

## Schema Components

### 1. PPV Conditioning (`PPVConditioningSignal`)

Converts canonical PPV signature to a format the LLM can use:

```python
class PPVEncodingStrategy(Enum):
    EMBEDDING    # PPV → 64-dim vector
    SOFT_PROMPT  # PPV → 8 learned tokens
    ADAPTER      # PPV → LoRA adapter selection
    TEXT_PREFIX  # PPV → "[PPV:L0_M2_H1_...]" prefix
```

**Critical constraint:** Encoder weights are **frozen**. No back-propagation from output.

### 2. Ontological Context (`OntologicalContext`)

Routing decision from Phase-11B.3:
- Family (THINKING, FORMING, etc.)
- Full path
- Slot plan
- Required VC facts

### 3. Few-Shot Context (`FewShotContext`)

Templates become **examples**, not output:

```python
@dataclass
class RetrievedTemplate:
    template_id: str
    template_text: str
    similarity_score: float
```

### 4. Generation Context (`GenerationContext`)

Everything the LLM needs:
- Request ID, artifact hash
- Ontological context
- PPV conditioning signal
- Few-shot templates
- VC source data
- Mode (OPEN/GOVERNED)

### 5. Verification (`VerificationResult`)

Checks on generated output:
- Structural (length, format)
- Ontological (family markers)
- PPV alignment (style consistency)
- Content policy

**GOVERNED mode** can reject outputs that **OPEN mode** accepts.

## Protocol Interfaces

```python
class PPVEncoder(Protocol):
    def encode(ppv_values, canonical_signature) -> PPVConditioningSignal

class TemplateRetriever(Protocol):
    def retrieve(family, signature, slot_plan) -> Tuple[RetrievedTemplate, ...]

class Generator(Protocol):
    def generate(context) -> RawGenerationResult

class Verifier(Protocol):
    def verify(context, generation) -> VerificationResult
```

## Implementation Status

| # | Task | Status | Tests |
|---|------|--------|-------|
| 1 | Phase12Schema | ✅ Complete | - |
| 2 | PPVConditioningEncoder | ✅ Complete | 31 |
| 3 | Phase12Verifier | ✅ Complete | 32 |
| 4 | TemplateRetriever | ✅ Complete | 23 |
| 5 | LLM Integration PoC | ✅ Complete | 14 |

**Total: 100 tests passing**

## Files

```
phase12_sandbox/
├── README.md                        # This file
├── phase12_schema.py                # Interface contracts ✅
├── phase12_ppv_encoder.py           # PPV → conditioning ✅
├── phase12_verifier.py              # Output verification ✅
├── phase12_retriever.py             # Template retrieval ✅
├── phase12_poc.py                   # End-to-end demo ✅
└── tests/
    ├── __init__.py
    ├── test_phase12_ppv_encoder.py  # 31 tests ✅
    ├── test_phase12_verifier.py     # 32 tests ✅
    ├── test_phase12_retriever.py    # 23 tests ✅
    └── test_phase12_poc.py          # 14 tests ✅
```

## Design Decisions

### Why frozen PPV encoder?

If the encoder learns from generation output, PPV loses its meaning as an independent acoustic/prosodic signal. The encoder must be:
1. Trained separately (if learned)
2. Or defined analytically (if not learned)
3. Never updated during generation

### Why templates → few-shot?

Templates alone cannot handle the full expressiveness needed. But templates:
- Ground generation in structural patterns
- Provide format examples
- Reduce hallucination risk

### Why verification after generation?

The LLM is probabilistic and can produce anything. Verification:
- Catches structural violations
- Enforces ontological consistency
- Enables GOVERNED mode to be stricter than OPEN
- Provides audit trail
