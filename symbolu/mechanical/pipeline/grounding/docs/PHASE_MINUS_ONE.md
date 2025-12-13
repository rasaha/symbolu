# PO1 — Observer–Observed Grounding
*(Implemented as phase_minus_one for backward compatibility)*

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

## Purpose

PO1 establishes the foundational grounding context for all downstream pipeline processing. Before any semantic analysis, discourse planning, or response generation occurs, PO1 answers the fundamental question:

**"WHO is being observed, and HOW is the observation framed?"**

This grounding is essential for:
- Preventing projection of observer's framework onto the observed
- Ensuring appropriate response modalities (care vs. analysis)
- Protecting user autonomy when discussing personal experiences
- Maintaining clear authority chains through the pipeline

## Authority Model

```
Authority flows DOWNWARD
Information flows UPWARD

PO1 (Grounding)
    ↓ [AUTHORITY: constraints are binding]
PO2 (Intent Envelope)
    ↓ [AUTHORITY: determines posture]
PO3 (Action Contract)
    ↓ [AUTHORITY: bounds eligible actions]
PlannerGate (Governance)
    ↓ [AUTHORITY: filters actions]
Downstream Stages
    ↑ [INFORMATION: violations reported]
PO1
```

**Key Invariant:** Downstream stages cannot override PO1 constraints. They can report violations for metrics but must respect the grounding decisions.

## Schema

### ObservedEntity (WHO)
- `SELF`: The speaker/user themselves (first-person perspective)
- `OTHER`: Another person or entity being referenced
- `PHENOMENON`: An abstract concept, event, or general truth

### ObservationMode (HOW)
- `REFLEXIVE`: Self-directed observation (I observe myself)
- `RELATIONAL`: Observation about another in relation to context
- `DETACHED`: Objective/abstract observation (no personal stake)

### ProjectionRisk
- `LOW`: Safe to analyze without projection risk
- `MEDIUM`: Some projection risk; proceed with care
- `HIGH`: High risk of projection; restrict analytical operations

### GroundingStatus
- `CONFIDENT`: Clear grounding established (confidence ≥ 0.70)
- `AMBIGUOUS`: Multiple plausible groundings
- `CONFLICTED`: Contradictory signals

### ResolutionPolicy
- `NONE`: No special handling needed
- `ASK_CLARIFY`: Request clarification from user
- `SAFE_DEFAULT`: Use conservative default

### OverallPolicy
- `SINGLE_CONTEXT`: Single coherent grounding
- `MULTI_CONTEXT`: Multiple clause contexts
- `BLOCKED`: Cannot proceed without clarification

## Components

### PO1.0: Observer-Observed Grounding (OOG)

Deterministic heuristic analysis to produce grounding candidates.

**Heuristics:**
- First-person pronouns (I, me, my) → REFLEXIVE
- Third-person pronouns/names → RELATIONAL
- Abstract nouns (-ness, -tion) → DETACHED
- Internal state verbs (feel, think, worry) → increase projection risk

**Confidence Scoring:**
```
confidence = 0.50 + (0.10 × evidence_count)
capped at 0.95
```

### PO1.1: Ambiguity Resolver (ARL)

Resolves multiple candidates using threshold-based rules.

**Thresholds:**
- `CONFIDENCE_THRESHOLD = 0.70` (for CONFIDENT status)
- `DELTA_THRESHOLD = 0.15` (minimum gap between top 2)
- `SAFE_DEFAULT_MIN_CONFIDENCE = 0.55`

**Rules:**
1. If top.confidence ≥ 0.70 → CONFIDENT
2. If delta < 0.15 → ASK_CLARIFY
3. If confidence ≥ 0.55 and risk ≠ HIGH → SAFE_DEFAULT
4. Otherwise → ASK_CLARIFY

### PO1.2: Conservative Clause Splitter (CSL)

Splits compound sentences ONLY when it improves grounding.

**Split Markers:**
- Causal: "because", "since"
- Contrast: "but", "however"
- Additive: "and" (with pronoun shift)

**Conservative Rule:**
```
Accept split ONLY if:
  gain ≥ 0.20  OR
  unsplit is ASK_CLARIFY but split makes clause CONFIDENT
```

## Action Gating Rules

### REFLEXIVE Mode (SELF observed)

**ALLOWED:**
- CARE
- GROUND
- CLARIFY_SELF
- REFLECT
- VALIDATE
- ASK

**FORBIDDEN:**
- ANALYZE
- EXPLAIN
- DIAGNOSE
- JUDGE
- ASSERT_ABOUT_OTHERS

### RELATIONAL Mode (OTHER observed)

**ALLOWED:**
- ALIGN
- ASK
- REFLECT_BACK
- DE_ESCALATE
- CLARIFY_REFERENCE

**FORBIDDEN:**
- DIAGNOSE_OTHER
- ASSERT_OTHER_STATE
- LABEL
- BLAME
- EXPLAIN_CAUSES

### DETACHED Mode (PHENOMENON observed)

**ALLOWED:**
- EXPLAIN
- ANALYZE
- COMPARE
- SUMMARIZE
- INSTRUCT_GENERAL

**FORBIDDEN:**
- PERSONAL_DIAGNOSIS
- ASSERT_USER_STATE

### Global Constraint

If `analysis_allowed == false`, strip ANALYZE/EXPLAIN from allowed set regardless of mode.

## Examples

### Example 1: Reflexive Input

```
Input: "I am sad."

PO1 Output:
  overall_policy: SINGLE_CONTEXT
  clauses[0]:
    mode: REFLEXIVE
    observed: SELF
    projection_risk: HIGH
    analysis_allowed: false
    confidence: 0.80

PlannerGate:
  ALLOWED: CARE, REFLECT, GROUND
  BLOCKED: ANALYZE, DIAGNOSE
```

### Example 2: Relational Input

```
Input: "You are sad."

PO1 Output:
  overall_policy: SINGLE_CONTEXT
  clauses[0]:
    mode: RELATIONAL
    observed: OTHER
    projection_risk: HIGH
    analysis_allowed: false
    confidence: 0.75

PlannerGate:
  ALLOWED: ALIGN, ASK, REFLECT_BACK
  BLOCKED: DIAGNOSE_OTHER, ASSERT_OTHER_STATE
```

### Example 3: Detached Input

```
Input: "Sadness is common."

PO1 Output:
  overall_policy: SINGLE_CONTEXT
  clauses[0]:
    mode: DETACHED
    observed: PHENOMENON
    projection_risk: LOW
    analysis_allowed: true
    confidence: 0.85

PlannerGate:
  ALLOWED: EXPLAIN, ANALYZE, SUMMARIZE
  BLOCKED: PERSONAL_DIAGNOSIS
```

### Example 4: Multi-Context Input

```
Input: "I'm worried because she seems sad."

PO1 Output:
  overall_policy: MULTI_CONTEXT
  was_split: true
  clauses[0]:
    text: "I'm worried"
    mode: REFLEXIVE
    linkage_hint: NONE
  clauses[1]:
    text: "she seems sad"
    mode: RELATIONAL
    linkage_hint: CAUSAL
```

### Example 5: Ambiguous Input

```
Input: "Feeling tired lately."

PO1 Output:
  overall_policy: BLOCKED
  clauses[0]:
    status: AMBIGUOUS
    policy: ASK_CLARIFY
    selected: null

ClarifyRenderer Output:
  "Are you describing how you feel personally, or describing someone else's experience?"
```

## Metrics

The following metrics are tracked for observability:

| Metric | Description |
|--------|-------------|
| `mode_counts` | Distribution of REFLEXIVE/RELATIONAL/DETACHED |
| `risk_counts` | Distribution of LOW/MEDIUM/HIGH projection risk |
| `analysis_blocked_count` | Times analysis was blocked |
| `ambiguity_rate` | Rate of AMBIGUOUS groundings |
| `safe_default_rate` | Rate of SAFE_DEFAULT selections |
| `blocked_rate` | Rate of BLOCKED policies |
| `violation_count` | Total PlannerGate violations |
| `violation_by_module` | Violations grouped by module |

## Integration

### Pipeline Integration

```python
from symbolu.mechanical.pipeline.phase_minus_one_integration import (
    maybe_run_phase_minus_one,
    is_pipeline_blocked,
)

# In orchestrator, after MLCR:
ctx.phase_minus_one = maybe_run_phase_minus_one(ctx)

if is_pipeline_blocked(ctx):
    # Route to clarification renderer
    return render_clarification(ctx.phase_minus_one)
```

### PipelineContext Field

```python
@dataclass
class PipelineContext:
    # ... existing fields ...
    phase_minus_one: Optional[PhaseMinusOneEnvelope] = None
```

## Testing

Run unit tests:
```bash
pytest symbolu/mechanical/pipeline/tests/grounding/test_phase_minus_one.py -v
```

Run integration tests:
```bash
pytest symbolu/mechanical/pipeline/integration_tests/test_phase_minus_one_integration.py -v
```

## Design Decisions

1. **Deterministic by default**: No LLM calls, no probabilistic sampling. Confidence values are deterministic functions of evidence counts.

2. **Conservative splitting**: The default clause splitting policy is CONSERVATIVE. Splits only occur when they demonstrably improve grounding confidence.

3. **Safety-first resolution**: When in doubt, ask for clarification rather than guessing. High projection risk forces ASK_CLARIFY.

4. **Authority chain enforcement**: Downstream stages cannot override PO1 constraints. This is enforced by PlannerGate.

5. **Minimal invasive integration**: PO1 is added as a wrapper/pre-phase, not by refactoring existing modules.
