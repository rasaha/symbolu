# Expression Modulation System

**Version:** 1.0
**Status:** Production
**Last Updated:** 2025-12-09

---

## 1. Purpose

This document formally describes the **Expression Modulation System** in Symbol-U, which converts TTOR/MLCR routing signals into **presentation-layer modulation** via MapperProfile.

**Key Principle:** Modulate **EXPRESSION**, not semantic truth.

The expression modulation system:
- **Preserves semantic content** determined by upstream logic (TTOR → MLCR → Fusion/DHA)
- **Modulates presentation style** across three rendering engines (Fusion, DHA, LLM Enhancement)
- **Operates deterministically** with zero LLM involvement in the modulation logic itself
- **Maintains backward compatibility** with all existing routing contracts

---

## 2. MapperProfile Fields and Meaning

The `MapperProfile` dataclass (defined in `symbolu/mechanical/pipeline/models.py:171-200`) contains five fields that control expression modulation:

### 2.1 `resolution_level: str`

**Values:** `"low"` | `"medium"` | `"high"`

**Meaning:**
Controls the granularity of detail in rendered output.

- **`"low"`**: Surface-level, compressed presentation (LCM-driven)
- **`"medium"`**: Balanced presentation (default, no mapper bias)
- **`"high"`**: Fine-grained, expanded presentation (HRM-driven)

**Effects:**
- Low → Collapse symbolic layers, minimize reflection
- Medium → Standard 3-layer rendering
- High → Expand symbolic layers, add precision markers

---

### 2.2 `arc_mode: str`

**Values:** `"none"` | `"temporal"` | `"identity"` | `"deep_context"`

**Meaning:**
Controls long-arc framing and reflection depth.

- **`"none"`**: No long-arc framing (default when LAM inactive)
- **`"temporal"`**: Temporal continuity across sessions (LAM + high tension)
- **`"identity"`**: Identity evolution and self-concept framing (LAM + identity domain)
- **`"deep_context"`**: Deep contextual pattern framing (LAM + high entropy)

**Effects:**
- `none` → No arc markers in mirror layer
- `temporal` → Add "across time", "pattern continuity", "temporal coherence"
- `identity` → Add "identity tension", "self-concept evolution", "ongoing development"
- `deep_context` → Add "trajectory contrast", "context integration", "broader pattern"

---

### 2.3 `detail_bias: float`

**Range:** `0.0 – 1.0`
**Default:** `0.5`

**Meaning:**
Preference for fine-grained detail and nuance.

**Modifiers:**
- HRM: `+0.3`
- LCM: `-0.3`

**Effects:**
- `< 0.3` → Minimal detail, surface-level facts only
- `0.3 – 0.7` → Balanced detail
- `> 0.7` → Fine-grained precision, expanded causal patterns, "examined in detail" markers

---

### 2.4 `practical_bias: float`

**Range:** `0.0 – 1.0`
**Default:** `0.5`

**Meaning:**
Preference for concrete, task-focused, actionable delivery.

**Modifiers:**
- LCM: `+0.4`

**Effects:**
- `< 0.3` → Minimize practical layer, emphasize symbolic/mirror
- `0.3 – 0.7` → Balanced practical focus
- `> 0.7` → Prioritize actionable items, compress symbolic layer, shorten reflection

---

### 2.5 `reflective_bias: float`

**Range:** `0.0 – 1.0`
**Default:** `0.5`

**Meaning:**
Preference for introspective, philosophical, identity-aware framing.

**Modifiers:**
- HRM: `+0.2`
- LCM: `-0.2`
- LAM: `+0.3`

**Effects:**
- `< 0.3` → Minimal introspection, no long-arc reflection
- `0.3 – 0.7` → Standard reflection in mirror layer
- `> 0.7` → Deep introspection, arc-aware framing, identity/trajectory markers

---

## 3. Deterministic Mapping: TTOR/MLCR → MapperProfile

The `compute_mapper_profile()` function (`symbolu/mechanical/mlcr/mapper_profile_builder.py:20-97`) implements **deterministic, rule-based conversion** from `RoutingPlan` to `MapperProfile`.

### 3.1 HRM Effects

**Activation Condition:**
`routing_plan.use_hrm == True`
(Triggered when `tier != LOWER AND normalized_entropy > 0.40`)

**MapperProfile Transformations:**
```python
resolution_level = "high"
detail_bias = min(1.0, detail_bias + 0.3)
reflective_bias = min(1.0, reflective_bias + 0.2)
```

**Semantic Meaning:**
- User query requires **abstract, high-resolution symbolic processing**
- Render with more granularity, precision, and reflective depth
- Expand symbolic layers, add causal nuance
- **Does NOT change semantic truth** — only presentation detail

---

### 3.2 LCM Effects

**Activation Condition:**
`routing_plan.use_lcm == True`
(Triggered when `tier == LOWER AND normalized_entropy > 0.50`)

**MapperProfile Transformations:**
```python
resolution_level = "low"
practical_bias = min(1.0, practical_bias + 0.4)
detail_bias = max(0.0, detail_bias - 0.3)
reflective_bias = max(0.0, reflective_bias - 0.2)
```

**Special Rule:**
If both HRM and LCM are active (rare edge case):
```python
resolution_level = "medium"  # Compromise between high and low
```

**Semantic Meaning:**
- User query requires **procedural, low-context, task-oriented processing**
- Render with surface-level clarity, actionable focus
- Collapse symbolic layers, minimize reflection
- **Does NOT change semantic truth** — only compression level

---

### 3.3 LAM Effects

**Activation Condition:**
`routing_plan.use_lam == True`
(Triggered when `long_arc_tension > 0.50` OR domain-specific conditions met)

**MapperProfile Transformations:**
```python
reflective_bias = min(1.0, reflective_bias + 0.3)

# Determine arc_mode based on routing signals:
if routing_plan.long_arc_tension > 0.6:
    arc_mode = "temporal"
elif _is_identity_domain(routing_plan.domain):
    arc_mode = "identity"
elif routing_plan.normalized_entropy > 0.70:
    arc_mode = "deep_context"
else:
    arc_mode = "temporal"  # Default LAM arc mode
```

**Identity Domain Detection:**
```python
def _is_identity_domain(domain: str) -> bool:
    identity_keywords = ["identity", "therapy", "self", "personal", "relationships"]
    return any(keyword in domain.lower() for keyword in identity_keywords)
```

**Semantic Meaning:**
- User query requires **long-arc temporal continuity, identity grounding, or deep context**
- Render with arc-aware framing, trajectory markers, stabilization notes
- Add identity/temporal reflection to mirror layer
- **Does NOT change semantic truth** — only long-arc framing

---

## 4. Renderer Modulation Logic

Three rendering engines consume `MapperProfile` to modulate expression:

### 4.1 Fusion Renderer

**Location:** `symbolu/mechanical/renderer/fusion_renderer.py:718-960`
**Method:** `apply_mapper_profile(rendered_output, mapper_profile)`

#### LCM Modulation (Collapse)

**Condition:** `practical_bias > 0.6 AND resolution_level == "low"`

**Effects:**
- **Symbolic Layer:**
  - Simplify theme (first sentence only)
  - Set archetype to "Pragmatic - focuses on concrete outcomes"
  - Keep only 1 causal pattern
  - Filter meaning_vectors to `practicality` only
  - Reduce `reasoning_depth` by `-0.3`

- **Practical Layer:**
  - Keep top 3 facts only
  - Keep top 2 constraints
  - Keep all actionable items (task focus)
  - Increase `coherence_score` by `+0.1`

- **Mirror Layer:**
  - Remove contradictions (minimal reflection)
  - Filter entropy measures (only significant ones)
  - Replace tensions with `["Minimal reflection - focus on action"]`
  - Set reflection to `"Practical focus maintained."`

**Guarantee:** Structural keys (`symbolic`, `practical`, `mirror`) remain present; only content is compressed.

---

#### HRM Modulation (Expand)

**Condition:** `detail_bias > 0.6 AND resolution_level == "high"`

**Effects:**
- **Symbolic Layer:**
  - Enhance theme with `"[Examined in detail]"` marker
  - Append archetype with `"(high-resolution analysis)"`
  - Add causal pattern: `"Fine-grained causal nuance detected"`
  - Increase `reasoning_depth` by `+0.2`

- **Practical Layer:**
  - Enhance facts with `"[with nuance]"` suffix
  - Keep all facts, constraints, procedures

- **Mirror Layer:**
  - No changes (HRM doesn't affect mirror layer)

**Guarantee:** All original content preserved; precision markers added.

---

#### LAM Modulation (Arc Framing)

**Condition:** `reflective_bias > 0.6 AND arc_mode != "none"`

**Effects:**
- **Symbolic Layer:**
  - Add arc framing prefix to theme:
    - `temporal`: `"Across time and context: ..."`
    - `identity`: `"In the context of identity evolution: ..."`
    - `deep_context`: `"Within the broader pattern: ..."`
  - Add arc pattern text:
    - `temporal`: `"This fits a broader temporal pattern across sessions."`
    - `identity`: `"This reflects ongoing identity development and evolution."`
    - `deep_context`: `"This emerges from deep contextual understanding."`

- **Mirror Layer:**
  - Add arc markers to tensions:
    - `temporal`: `["Pattern continuity", "Temporal coherence"]`
    - `identity`: `["Identity tension", "Self-concept evolution"]`
    - `deep_context`: `["Trajectory contrast", "Context integration"]`
  - Enhance reflection with arc-specific text:
    - `temporal`: `"Temporal patterns show coherence across sessions."`
    - `identity`: `"Identity tensions reveal ongoing self-development."`
    - `deep_context`: `"Deep context patterns suggest trajectory alignment."`

**Guarantee:** Arc framing added; semantic content unchanged.

---

### 4.2 DHA Engine

**Location:** `symbolu/mechanical/dha/dha_engine.py:411-490`
**Method:** `modulate_dha_depth(insight, mapper_profile)`

**Purpose:** Modulate introspection level, metaphor usage, and framing WITHOUT changing semantic truth.

#### LCM Modulation (Shallow)

**Condition:** `practical_bias > 0.6 AND resolution_level == "low"`

**Effects:**
```python
insight["introspection_level"] = "minimal"
insight["metaphor_allowed"] = False
insight["reflection_depth"] = "surface"
insight["long_range_implications"] = False
insight["framing_note"] = "Focused on immediate practical delivery"
```

**Meaning:**
- Minimal introspection
- No metaphor
- Surface-truth only
- No long-range implications

---

#### HRM Modulation (Deep)

**Condition:** `detail_bias > 0.6 AND resolution_level == "high"`

**Effects:**
```python
insight["introspection_level"] = "deep"
insight["metaphor_allowed"] = True
insight["reflection_depth"] = "detailed"
insight["contrastive_phrasing"] = True
insight["symbolic_mirrors"] = "emphasized"
insight["framing_note"] = "High-resolution analysis with nuanced framing"
```

**Meaning:**
- Deeper introspection
- Contrastive phrasing allowed
- Symbolic mirrors emphasized

---

#### LAM Modulation (Arc-Aware)

**Condition:** `reflective_bias > 0.6 AND arc_mode != "none"`

**Effects:**
```python
insight["introspection_level"] = "arc-aware"
insight["metaphor_allowed"] = True
insight["reflection_depth"] = "identity"
insight["arc_keywords"] = ["trajectory", "momentum", "directionality", "coherence"]
insight["emphasize_coherence"] = True

# Arc-specific framing:
if arc_mode == "temporal":
    insight["arc_framing"] = "This shift seems part of a broader movement across sessions."
elif arc_mode == "identity":
    insight["arc_framing"] = "This reflects ongoing identity development and self-concept evolution."
elif arc_mode == "deep_context":
    insight["arc_framing"] = "This emerges from deep contextual patterns showing trajectory alignment."

# Add stabilization framing if high tension:
if insight.get("long_arc_tension", 0) > 0.7:
    insight["stabilization_framing"] = "Pattern suggests need for integration and stabilization."
```

**Meaning:**
- Long-arc identity-level framing
- Trajectory/momentum keywords allowed
- Emphasize coherence across turns
- Add stabilization framing if tension high

---

### 4.3 LLM Enhancement Renderer

**Location:** `symbolu/mechanical/renderer/llm_renderer.py:74-186`
**Method:** `apply_mapper_tone(text, mapper_profile)`

**Purpose:** Modulate **TONE and CADENCE** only, not semantic content.

**Critical Guarantee:** LLM renderer is **optional** and **non-semantic**. All semantic content is determined by upstream (TTOR → MLCR → Fusion → DHA). The LLM renderer only adjusts:
- Sentence length
- Transition words
- Cadence/rhythm
- Cohesive devices

---

#### LCM Tone (Short, Clipped, Actionable)

**Condition:** `practical_bias > 0.6 AND resolution_level == "low"`

**Effects:**
- Sentence length: **8-12 words**
- Structure: Direct, imperative
- Remove subordinate clauses
- Limit to 3 sentences max
- Avoid: complex transitions

**Example:**
```
Before: "The analysis, which took into account multiple factors, suggests that the optimal approach would be to prioritize efficiency."
After: "Analysis shows efficiency is key. Prioritize it. Act now."
```

---

#### HRM Tone (Clearer Transitions, Deeper Detail)

**Condition:** `detail_bias > 0.6 AND resolution_level == "high"`

**Effects:**
- Sentence length: **15-25 words**
- Structure: Compound-complex, contrastive
- Add transitional phrases: "Furthermore", "Moreover", "Specifically"
- Use parallel constructions

**Example:**
```
Before: "The system works well. It has limitations. Performance varies."
After: "The system works well. Furthermore, it has limitations that affect outcomes. Specifically, performance varies based on context."
```

---

#### LAM Tone (Reflective, Slow Cadence, Stabilizing)

**Condition:** `reflective_bias > 0.6 AND arc_mode != "none"`

**Effects:**
- Sentence length: **18-30 words**
- Structure: Flowing, contemplative
- Add cohesive devices and temporal markers:
  - `temporal`: "Over time", "As patterns emerge", "Through this progression"
  - `identity`: "In this evolution", "Through self-development", "Within this growth"
  - `deep_context`: "In this broader context", "Through these patterns", "Within this framework"
- Avoid therapy language (unless domain=therapy)

**Example:**
```
Before: "Your response shows growth. This is positive."
After: "Through this progression, your response shows growth that reflects ongoing development."
```

---

## 5. Guarantees

The expression modulation system provides the following **immutable guarantees**:

### 5.1 Semantic Preservation

**Guarantee:**
Semantic content is **PURELY** determined by upstream logic (TTOR → MLCR → Fusion/DHA). Modulation changes **expression**, not **meaning**.

**Enforcement:**
- Mapper modulation operates on **structural markers**, not semantic tokens
- All semantic reasoning happens in HRM/LCM/LAM engines (upstream)
- FusionRenderer/DHA/LLM only add **presentation markers** (e.g., `[Examined in detail]`, arc framing prefixes)
- Content tokens are preserved (verified by semantic-shape tests)

---

### 5.2 Structural Consistency

**Guarantee:**
All required structural fields appear consistently across mapper modes.

**Enforcement:**
- **Fusion Renderer:** `symbolic`, `practical`, `mirror` layers ALWAYS present (even if compressed)
- **DHA Output:** `insight` field ALWAYS present (even if introspection level varies)
- **MapperProfile:** All 5 fields ALWAYS set (no `None` values)

---

### 5.3 Determinism

**Guarantee:**
All modulation is **LLM-free** and **deterministic**.

**Enforcement:**
- `compute_mapper_profile()` uses **pure deterministic rules** (no randomness, no LLM)
- Fusion Renderer modulation uses **deterministic string transformations**
- DHA modulation uses **deterministic flag setting**
- LLM Enhancement Renderer uses **deterministic text rules** (split, join, prefix)

**Note:** If LLM is used in production (not in current implementation), it MUST:
- Preserve all content tokens
- Only modify cadence/transitions
- Pass semantic-shape tests (content token preservation)

---

### 5.4 Backward Compatibility

**Guarantee:**
Expression modulation does NOT break existing routing contracts.

**Enforcement:**
- TTOR thresholds (0.40, 0.50, 0.60) unchanged
- MLCR expert router logic unchanged
- All existing snapshots pass (semantic skeleton preserved)
- CI drift tests pass (mapper activation regions unchanged)

---

## 6. Example Flows

### Example 1: LOWER/task (LCM Only)

**Input:**
```python
query = "How do I reverse a list in Python?"
tier = LOWER
normalized_entropy = 0.55
domain = "code"
long_arc_tension = 0.2
```

**TTOR Routing:**
```python
use_hrm = False  # tier == LOWER
use_lcm = True   # tier == LOWER AND normalized_entropy > 0.50
use_lam = False  # long_arc_tension < 0.50
```

**MapperProfile:**
```python
resolution_level = "low"
arc_mode = "none"
detail_bias = 0.2  # 0.5 - 0.3 (LCM)
practical_bias = 0.9  # 0.5 + 0.4 (LCM)
reflective_bias = 0.3  # 0.5 - 0.2 (LCM)
```

**Fusion Renderer:**
- **Symbolic Layer:** Compressed (1 causal pattern, simplified theme)
- **Practical Layer:** Top 3 facts, all actionable items prioritized
- **Mirror Layer:** Minimal reflection ("Practical focus maintained.")

**DHA Engine:**
- Introspection: `"minimal"`
- Metaphor: `False`
- Reflection: `"surface"`

**LLM Tone:**
- Short sentences (8-12 words)
- Direct, imperative
- Example: "Use `reversed()` function. Apply to list. Returns iterator."

**Semantic Content (PRESERVED):**
- `reversed()` function is the solution
- Returns iterator, not list
- Requires `list()` conversion if needed

**Expression (MODULATED):**
- Compressed, actionable, surface-level

---

### Example 2: UPPER/therapy (HRM + LAM)

**Input:**
```python
query = "Why do I keep sabotaging relationships when I finally get close to someone?"
tier = UPPER
normalized_entropy = 0.72
domain = "therapy"
long_arc_tension = 0.65
```

**TTOR Routing:**
```python
use_hrm = True  # tier == UPPER AND normalized_entropy > 0.40
use_lcm = False  # tier != LOWER
use_lam = True  # domain == "therapy" AND normalized_entropy > 0.60
```

**MapperProfile:**
```python
resolution_level = "high"  # HRM
arc_mode = "identity"  # LAM + identity domain
detail_bias = 0.8  # 0.5 + 0.3 (HRM)
practical_bias = 0.5  # No change
reflective_bias = 1.0  # 0.5 + 0.2 (HRM) + 0.3 (LAM)
```

**Fusion Renderer:**
- **Symbolic Layer:**
  - Theme: `"In the context of identity evolution: [original theme] [Examined in detail]"`
  - Archetype: Enhanced with `"(high-resolution analysis)"`
  - Causal patterns: Expanded with identity arc pattern
  - Reasoning depth: High

- **Practical Layer:**
  - Facts: Enhanced with `"[with nuance]"`

- **Mirror Layer:**
  - Tensions: Include `["Identity tension", "Self-concept evolution"]`
  - Reflection: Enhanced with `"Identity tensions reveal ongoing self-development."`

**DHA Engine:**
- Introspection: `"arc-aware"`
- Metaphor: `True`
- Reflection: `"identity"`
- Arc framing: `"This reflects ongoing identity development and self-concept evolution."`
- Arc keywords: `["trajectory", "momentum", "directionality", "coherence"]`

**LLM Tone:**
- Reflective cadence (18-30 words)
- Temporal markers: `"In this evolution..."`
- Flowing, contemplative structure

**Semantic Content (PRESERVED):**
- Pattern of relationship sabotage detected
- Closeness triggers defensive behavior
- Conflict between intimacy desire and vulnerability fear

**Expression (MODULATED):**
- High-resolution, identity-aware, arc framing
- Reflective tone, stabilizing cadence
- Long-arc trajectory markers

---

### Example 3: UPPER/identity (LAM Identity Arc)

**Input:**
```python
query = "I feel like I'm becoming someone different, but I don't know if it's growth or loss."
tier = UPPER
normalized_entropy = 0.68
domain = "identity"
long_arc_tension = 0.45
```

**TTOR Routing:**
```python
use_hrm = True  # tier == UPPER AND normalized_entropy > 0.40
use_lcm = False  # tier != LOWER
use_lam = True  # domain == "identity" AND normalized_entropy > 0.60
```

**MapperProfile:**
```python
resolution_level = "high"  # HRM
arc_mode = "identity"  # LAM + identity domain
detail_bias = 0.8  # 0.5 + 0.3 (HRM)
practical_bias = 0.5  # No change
reflective_bias = 1.0  # 0.5 + 0.2 (HRM) + 0.3 (LAM)
```

**Fusion Renderer:**
- **Symbolic Layer:**
  - Theme: `"In the context of identity evolution: [original theme] [Examined in detail]"`
  - Arc pattern: `"This reflects ongoing identity development and evolution."`

- **Mirror Layer:**
  - Tensions: Include `["Identity tension", "Self-concept evolution"]`
  - Reflection: `"Identity tensions reveal ongoing self-development."`

**DHA Engine:**
- Introspection: `"arc-aware"`
- Arc framing: `"This reflects ongoing identity development and self-concept evolution."`
- Identity keywords emphasized

**LLM Tone:**
- Identity markers: `"Through self-development..."`
- Reflective, stabilizing cadence

**Semantic Content (PRESERVED):**
- Identity shift detected
- Ambiguity: growth vs. loss
- Tension between old self and new self

**Expression (MODULATED):**
- Identity arc framing
- Self-concept evolution markers
- Stabilizing, reflective tone

---

## 7. Integration with Routing Contract

The expression modulation system integrates with the **Routing Contract v2.0** (`docs/routing_contract.md`) as follows:

### 7.1 Upstream Inputs

Expression modulation receives **routing signals** from:
- **TTOR:** `use_hrm`, `use_lcm`, `use_lam`, `normalized_entropy`, `long_arc_tension`, `domain`
- **MLCR:** Identical signals (TTOR and MLCR must be consistent per routing contract)

### 7.2 Mapper Activation Regions

Expression modulation does NOT change mapper activation regions. The canonical thresholds remain:
- **HRM:** `tier != LOWER AND normalized_entropy > 0.40`
- **LCM:** `tier == LOWER AND normalized_entropy > 0.50`
- **LAM:** `long_arc_tension > 0.50 OR (domain in ["therapy", "identity", "spiritual"] AND normalized_entropy > 0.60)`

### 7.3 CI Enforcement

Expression modulation is enforced by:
- **Semantic-Shape Tests:** `symbolu/mechanical/pipeline/integration_tests/test_pipeline_semantic_shape.py`
  - Verify semantic core unchanged across mappers
  - Verify required DHA fields always present
  - Verify structural layers in fusion renderer always present
  - Verify LLM renderer preserves content tokens

- **Routing Drift Tests:** `symbolu/core/drift_tests/test_mapper_activation_regions.py`
  - Verify mapper activation regions unchanged
  - Verify canonical thresholds preserved

---

## 8. Developer Guidelines

### 8.1 Adding New Modulation Rules

When adding new modulation rules:
1. **Update `compute_mapper_profile()`** in `mapper_profile_builder.py`
2. **Update renderer modulation methods** in `fusion_renderer.py`, `dha_engine.py`, `llm_renderer.py`
3. **Add semantic-shape tests** to verify content preservation
4. **Update this documentation** with new rules

### 8.2 Testing Modulation

When testing modulation:
- **Semantic tests:** Verify content tokens preserved
- **Structural tests:** Verify required fields present
- **Determinism tests:** Same inputs → same outputs
- **Snapshot tests:** Verify existing snapshots still pass

### 8.3 Debugging Modulation

When debugging modulation issues:
1. Check `MapperProfile` fields in pipeline context
2. Inspect `routing_plan.debug` dictionary for mapper activation reasons
3. Verify renderer methods receive correct `MapperProfile`
4. Check semantic-shape test failures for content drift

---

## 9. Future Enhancements

### 9.1 Temporal Patterns Integration

**Status:** Planned
**Blocker:** `TemporalBhavaTracker` not yet implemented

When `TemporalBhavaTracker` is integrated:
- `temporal_patterns_detected` will replace hardcoded `False` in TTOR/MLCR
- LAM activation will expand to include detected temporal patterns
- Arc mode selection will use temporal pattern signals

**Impact on Expression Modulation:**
- `arc_mode = "temporal"` will activate more frequently
- Temporal arc framing will appear in more responses
- Stabilization framing will trigger on detected pattern disruption

**Compatibility:** No changes to existing rules; only expanded activation zones.

---

### 9.2 Custom Arc Modes

**Status:** Future consideration

Potential custom arc modes:
- `"creative"`: Creative exploration arc
- `"learning"`: Learning trajectory arc
- `"healing"`: Healing/recovery arc

**Requirements:**
- Define activation conditions
- Add framing rules to renderers
- Add semantic-shape tests
- Update documentation

---

## 10. Summary

The Expression Modulation System provides:

✅ **Deterministic conversion** from TTOR/MLCR routing signals to presentation modulation
✅ **Semantic preservation** across all mapper modes
✅ **Structural consistency** (required fields always present)
✅ **Zero-LLM modulation logic** (deterministic rules only)
✅ **Backward compatibility** with routing contract v2.0
✅ **Three-layer modulation** (Fusion → DHA → LLM Enhancement)
✅ **CI-enforced guarantees** via semantic-shape tests

**Contract Guardians:**
- `symbolu/mechanical/pipeline/integration_tests/test_pipeline_semantic_shape.py`
- `symbolu/core/drift_tests/test_mapper_activation_regions.py`

**Contract Violations:**
Any change causing semantic-shape test failures requires investigation and approval.

---

**End of Expression Modulation Documentation v1.0**
