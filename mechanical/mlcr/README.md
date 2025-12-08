# MLCR - Multi-Layer Consciousness RAG

**Version:** v3.1  
**Status:** Production  
**Layer:** Mechanical (No Symbol-U Core dependency)

## Overview

MLCR is a consciousness-aware query routing system that analyzes input text across multiple dimensions to determine the optimal processing tier and expert activation strategy.

## Architecture

```
USER QUERY
    ↓
┌──────────────────┐
│ MLCR Engine      │
└──────────────────┘
    ↓
    ├─→ 1. Ontology Mass Computation
    │      (Lower: 1-5, Upper: 6-10)
    │
    ├─→ 2. Intent Classification
    │      (WHAT/WHY/HOW/etc.)
    │
    ├─→ 3. Entropy Computation
    │      (H_D, H_G, H_K proxies)
    │
    ├─→ 4. Tier Selection
    │      (LOWER/UPPER/HYBRID)
    │
    ├─→ 5. Expert Routing
    │      (HRM/LCM/LAM/MoE)
    │
    ├─→ 6. Renderer Context
    │      (standard/regulated/symbolic/minimal)
    │
    └─→ 7. Audit Logging
           (Complete decision trail)
    ↓
ACTIVATION PLAN
```

## Three-Tier System

### LOWER Tier (Concrete/Factual)
- **Trigger:** `lower_mass > 0.65`
- **Experts:** LCM + MoE (if domain)
- **Examples:**
  - "What is the price of AAPL?"
  - "How many shares were traded?"
  - "What are the symptoms of diabetes?"

### UPPER Tier (Abstract/Symbolic)
- **Trigger:** `upper_mass > 0.65`
- **Experts:** HRM only
- **Examples:**
  - "Why do I keep making the same mistakes?"
  - "What is the meaning of life?"
  - "Reflect on my emotional state"

### HYBRID Tier (Mixed/Complex)
- **Trigger:** Mixed ontology OR high entropy
- **Experts:** HRM + LCM + MoE + FusionEngine
- **Examples:**
  - "Why did Micron fall after strong earnings?"
  - "Should I buy this stock?"
  - "I feel anxious about my trades and wonder why"

## Intent Types

| Intent | Description | Pattern Examples |
|--------|-------------|------------------|
| **WHAT** | Factual queries | "What is...", "Tell me about..." |
| **WHY** | Causal reasoning | "Why did...", "What caused..." |
| **HOW** | Process/method | "How do I...", "What's the process..." |
| **SHOULD** | Decision support | "Should I...", "Is it worth..." |
| **REFLECTION** | Self-reflection | "I feel...why", "Reflect on my..." |
| **FEELING** | Emotional state | "I'm feeling anxious", "I am worried" |
| **WHO** | Identity/persona | "Who is...", "What person..." |
| **COMMAND** | Direct actions | "Create...", "Calculate...", "Show..." |
| **PLAN** | Strategic planning | "What's the best strategy...", "Help me plan..." |
| **META** | Meta-cognitive | "How do you work", "Explain your approach" |
| **UNKNOWN** | Cannot classify | Default fallback |

## Expert Systems

### HRM (High Reasoning Module)
- **Purpose:** Abstract/symbolic reasoning
- **Activates:** UPPER and HYBRID tiers
- **Handles:** WHY queries, philosophical questions

### LCM (Linguistic Coherence Module)
- **Purpose:** Semantic clarity and factual grounding
- **Activates:** LOWER and HYBRID tiers
- **Handles:** WHAT queries, concrete facts

### LAM (Life Anchor Module)
- **Purpose:** Emotional grounding and reflection
- **Activates:** REFLECTION and FEELING queries
- **Handles:** Self-reflection, emotional states

### MoE (Mixture of Experts)
- **Purpose:** Domain-specific knowledge
- **Activates:** When domain is specified
- **Domains:** trading, medical, legal, etc.

## Renderer Modes

| Mode | When | Purpose |
|------|------|---------|
| **standard** | Most queries | Normal rendering |
| **regulated** | Medical/legal domains | Compliance-safe with disclaimers |
| **symbolic** | Reflection/spiritual | Abstract/philosophical language |
| **minimal** | Pure factual | Concise, direct answers |

## Usage

### Basic Routing

```python
from symbolu.mechanical.mlcr import MLCR

mlcr = MLCR()

# Route a query
decision = mlcr.route(
    text="Why did Micron fall after strong earnings?",
    context={"domain": "trading"}
)

# Access results
print(f"Tier: {decision['tier']}")
print(f"Intent: {decision['intent']}")
print(f"Activated experts: {decision['activation_plan']}")
```

### Quick Routing

```python
from symbolu.mechanical.mlcr import route_query

decision = route_query("What is the price?", domain="trading")
```

### Type-Safe ActivationPlan

```python
# Get dataclass instead of dict
plan = mlcr.route_to_activation_plan(
    text="Should I buy this stock?",
    context={"domain": "trading"}
)

# Type-safe access
print(plan.tier)           # TierType.HYBRID
print(plan.intent)         # IntentType.SHOULD
print(plan.use_hrm)        # True
print(plan.experts)        # [ExpertTarget.HRM, ExpertTarget.LCM, ExpertTarget.MoE]
```

### Explain Decision

```python
decision = mlcr.route("Why did the market fall?")
explanation = mlcr.explain(decision)
print(explanation)
```

### Component Testing

```python
# Test individual components

# Ontology mass
mass = mlcr.compute_ontology_mass("Why did the price fall?")
# → {"lower_mass": 0.4, "upper_mass": 0.6, ...}

# Intent classification
intent, metadata = mlcr.classify_intent("What is the price?", domain="trading")
# → (IntentType.WHAT, {"confidence": 0.9, ...})

# Tier selection
tier, metadata = mlcr.select_tier(lower_mass=0.3, upper_mass=0.7)
# → (TierType.UPPER, {"reason": "Upper mass dominant", ...})
```

## Example Queries

### Trading Domain

```python
# Factual query → LOWER tier
mlcr.route("What is the current price of AAPL?", context={"domain": "trading"})
# → Tier: LOWER, Experts: [LCM, MoE]

# Causal query → HYBRID tier
mlcr.route("Why did Micron fall after earnings?", context={"domain": "trading"})
# → Tier: HYBRID, Experts: [HRM, LCM, MoE, Fusion]
```

### Medical Domain (Regulated)

```python
mlcr.route("What are the symptoms of diabetes?", context={"domain": "medical"})
# → Tier: LOWER
# → Renderer Mode: "regulated" (includes disclaimers)
```

### Emotional/Reflection

```python
mlcr.route("I feel anxious about my decisions and don't know why")
# → Tier: HYBRID
# → Experts: [HRM, LAM]
# → Renderer Mode: "symbolic"
```

## Decision Trail Example

```
MLCR ROUTING AUDIT LOG
================================================================================
Timestamp: 2025-12-07T14:30:00.000000

QUERY:
  Text: Why did Micron fall after strong earnings?
  Domain: trading

ONTOLOGY ANALYSIS:
  Lower Mass: 0.400
  Upper Mass: 0.600
  Dominant: Layer 6 (Reasoning)

INTENT CLASSIFICATION:
  Intent: WHY
  Confidence: 0.9

ENTROPY COMPUTATION:
  H_D: 1.585
  H_G: 0.960
  H_K: None (placeholder)

TIER SELECTION:
  Tier: HYBRID
  Reason: Mixed ontology distribution

EXPERT ACTIVATION:
  ✓ use_hrm
  ✓ use_lcm
  ✓ use_moe
  ✓ use_fusion
  ✗ use_lam

RENDERER CONTEXT:
  Mode: standard
  Tone: analytical

DECISION TRAIL:
  Step 1: Compute ontology mass
    → Lower=0.400, Upper=0.600
    Reasoning: Dominant: Reasoning
  Step 2: Classify intent
    → WHY
    Reasoning: Pattern-based classification
  Step 3: Compute entropy
    → H_D=1.585, H_G=0.960
    Reasoning: Mechanical proxy approximations
  Step 4: Select tier
    → HYBRID
    Reasoning: Mixed ontology distribution
  Step 5: Route to experts
    → use_hrm, use_lcm, use_moe
    Reasoning: Based on HYBRID tier logic
  Step 6: Activate FusionEngine
    → Yes
    Reasoning: Multiple experts require blending
================================================================================
```

## Entropy Thresholds

| Entropy | Threshold | Effect |
|---------|-----------|--------|
| **H_D** | > 1.2 | Forces HYBRID tier |
| **H_G** | > 1.1 | Forces HYBRID tier |
| **H_K** | N/A | Placeholder (requires Symbol-U Core) |

## Component Status

```python
mlcr.get_component_status()
# → {
#     "ontology_computer": "active",
#     "intent_classifier": "active",
#     "entropy_adapter": "active (proxies)",
#     "tier_selector": "active",
#     "expert_router": "active",
#     "renderer_context_builder": "active",
#     "explainability_logger": "active",
#     "version": "v3.1"
# }
```

## Important Notes

### Mechanical Layer Only

MLCR operates in the **mechanical layer** and does NOT depend on Symbol-U Core. All entropy computations are mechanical approximations:

- **H_D:** Shannon entropy over layer activations (proxy)
- **H_G:** Mass tension metric (proxy)
- **H_K:** Placeholder (requires Symbol-U Core)

### Expert Placeholders

HRM, LCM, and LAM are **stub implementations** awaiting Symbol-U Core integration:

```python
from symbolu.mechanical.mlcr import get_hrm, get_lcm, get_lam

hrm = get_hrm()
print(hrm.is_available())  # → False (stub)
```

### Compliance Mode

Regulated domains (medical, legal) automatically activate compliance-safe rendering:

```python
decision = mlcr.route("What are diabetes symptoms?", context={"domain": "medical"})
# → renderer_mode: "regulated"
# → disclaimers_required: True
```

## Integration Points

### Downstream Systems

```python
# FusionEngine consumes ActivationPlan
from symbolu.mechanical.mlcr import route_query
from symbolu.fusion import FusionEngine  # (future)

plan = mlcr.route_to_activation_plan("Complex query")
if plan.requires_fusion():
    fusion_engine = FusionEngine()
    result = fusion_engine.blend(plan)
```

### RAG Pipeline

```python
# MLCR as RAG entry point
query = "Why did the stock fall?"
plan = mlcr.route_to_activation_plan(query)

# Route to appropriate retrieval strategy
if plan.tier == TierType.LOWER:
    # Use vector search for concrete queries
    results = vector_db.search(query)
elif plan.tier == TierType.UPPER:
    # Use symbolic search for abstract queries
    results = symbolic_db.search(query)
else:
    # Use hybrid approach
    results = hybrid_search(query)
```

## Version History

- **v3.1** (Current): Production release with complete audit logging
- **v3.0**: Initial MLCR architecture
- **v2.x**: Pre-MLCR routing systems

## License

Part of Symbol-U AGI framework (Patent Protected)

## Contact

Rakesh Mohan - SOULPI/Symbol-U Creator
