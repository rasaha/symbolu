# Symbol-U: Generalizable Cognitive Architecture

## Executive Summary

Symbol-U implements a **12-dimensional ontological backbone** structured as **5 mirror pairs** that enables cross-domain reasoning without domain-specific training. By encoding all knowledge into a universal cognitive-mathematical structure with **event tagging**, **persona-based pattern discovery**, and **phoneme-based consistency validation**, the system can transfer insights across history, science, literature, finance, biology, and any other domain—a foundational capability for domain-agnostic reasoning.

**The key innovation:** The phoneme model provides an orthogonal consistency check—correlating articulation patterns with encoded event structure. Only structurally consistent patterns survive to storage. The system is self-consistent, self-filtering, and self-auditing.

**The AGI Vision:** This architecture represents a deliberate step toward Artificial General Intelligence. While individual claims are conservatively framed (probabilistic validation, consistency checking rather than truth claims), the **end goal is AGI**. The combination of universal representation, cross-domain transfer, and self-filtering validation addresses core AGI requirements that current approaches cannot solve.

---

## The Generalization Gap: Why Current AI Falls Short

| Traditional AI | Symbol-U Approach |
|----------------|-------------------|
| Train separate model per domain | Single 10D encoding for all domains |
| Embeddings are opaque (1536D) | Dimensions are interpretable (10D → 5 pairs) |
| Statistical correlation | Structural causation via mirror balance |
| Cannot explain "why" | Explicit reasoning chains |
| No knowledge transfer | Cross-domain by design |
| User-agnostic | Persona query tracking |
| Extract patterns from content | Discover patterns from usage |
| Single validation layer | Orthogonal validation (semantic + phoneme) |
| Manual curation | Self-filtering (anomalies auto-detected) |

---

## Core Capabilities

### 1. Mirror Pair Architecture (The Simplification)

The 12D space is not 10 independent dimensions—it's **5 mirror pairs** where lower (concrete) dimensions balance with higher (abstract) dimensions:

```
┌─────────────────────────────────────────────────────────────────┐
│                    5 MIRROR PAIRS                               │
├─────────────────────────────────────────────────────────────────┤
│  LOWER (Concrete)              HIGHER (Abstract)                │
│  ─────────────────             ─────────────────                │
│  1D Acting      ←────────→     10D Absolving                    │
│     (Event)                       (Meaning)                     │
│                                                                 │
│  2D Tagging     ←────────→     9D Unifying                      │
│     (Naming)                      (Connecting)                  │
│                                                                 │
│  3D Forming     ←────────→     8D Meta_Observing                │
│     (Structure)                   (Perspective)                 │
│                                                                 │
│  4D Thinking    ←────────→     7D Purposing                     │
│     (Process)                     (Why)                         │
│                                                                 │
│  5D Directing   ←────────→     6D Reasoning                     │
│     (Choice)                      (Justification)               │
└─────────────────────────────────────────────────────────────────┘
```

**Key Insight: Balance Determines Insight Quality**

```
If lower is HIGH and mirror is LOW → Just facts (no meaning)
If lower is LOW and mirror is HIGH → Just theory (no grounding)
If BOTH are balanced → Transferable insight
```

**Balance Score Formula:**
```
balance_score = 1.0 - (Σ |lower[i] - higher[i]| / 5.0)
```

### 2. Event Tagging (Not Entity Identification)

**The Problem:** Traditional NLP clusters around entities (nouns), causing everything to cluster together.

**The Solution:** Tag EVENTS (what happened), not ENTITIES (what it's called).

```
WRONG (Entity-based):
  "Civil War" → IDENTIFICATION = 1.0 (it's a noun!)
  "Depression" → IDENTIFICATION = 1.0 (it's a noun!)
  → Everything clusters together

RIGHT (Event-based):
  "Civil War" → EVENT: conflict, division
  "Depression" → EVENT: collapse, destruction
  → Clusters by WHAT HAPPENED
```

**Event Types:**

| Category | Event Types | Dimension |
|----------|-------------|-----------|
| Action | conflict, creation, destruction, movement, transformation | 1D Acting |
| Relationship | division, union, comparison, exchange | 2D Tagging |
| Structural | formation, collapse, growth, decay | 3D Forming |
| Process | sequence, cycle, recursion, emergence | 4D Thinking |
| Agency | decision, choice, leadership, rebellion | 5D Directing |

### 3. Propagation Mechanism

When a lower dimension is activated but its mirror is not, **propagate upward**:

```
USER QUERY: "War broke out and fighting spread"

Step 1: Encode
  → Acting (1D): HIGH (conflict event)
  → Absolving (10D): LOW (no meaning attached)

Step 2: Detect Imbalance
  → Balance score: 0.6 (below threshold)
  → Propagation needed: ACTION_ABSOLUTE pair

Step 3: Propagate
  → Search for experientials where Acting + Absolving are both high
  → "History shows conflict eventually resolves through..."

Step 4: Result
  → Query now has both EVENT and MEANING
  → Insight is transferable
```

### 4. Persona Query Tracking

**Don't extract patterns from content. Discover patterns from usage.**

```
PERSONA: user_123

Query History:
  "Why did the market crash in 1929?" → finance
  "How did Rome fall?" → history
  "What causes economic recessions?" → finance
  "Why do empires collapse?" → history

DISCOVERED PATTERN:
  Thinks in terms of: destruction, collapse, formation
  Connects: finance ↔ history
  Shared events: ['destruction', 'collapse']
```

The system learns:
1. Which **domains** each persona queries
2. Which **event types** they're interested in
3. Which **cross-domain bridges** they naturally make
4. How to **suggest domains** for new queries

### 5. Cross-Domain Bridge Discovery

Bridges emerge from **user behavior**, not content extraction:

```
USER QUERIES OVER TIME:
  Query 1: "Market crash" (finance) → responded with history
  Query 2: "Empire collapse" (history) → responded with economics
  Query 3: "Company restructuring" (business)

BRIDGE DISCOVERED:
  finance ↔ history
  Bridge count: 2
  Shared events: ['destruction', 'collapse']

FUTURE QUERY: "Why did my startup fail?"
  System suggests: Search finance AND history
  Because: User thinks in collapse patterns across both
```

### 6. Experiential Reasoning Objects

Knowledge is stored not as raw content, but as **transferable reasoning patterns**:

```json
{
  "experiential_id": "exp_ca776dedc22a",
  "vector_10d": [0.82, 0.91, 0.34, 0.67, 0.78, 0.45, 0.56, 0.32, 0.21, 0.12],
  "balance_score": 0.77,
  "source_domain": "history",

  "events_tagged": ["conflict", "division"],
  "pattern_type": "bifurcation",
  "insight": "When opposing forces cannot find middle ground, systems split",

  "causal_chain": ["polarization", "failed_negotiation", "bifurcation", "resolution"],
  "transferable_to": ["politics", "family", "organization", "markets"],

  "mirror_states": {
    "ACTION_ABSOLUTE": "balanced",
    "IDENTIFICATION_SINGULARITY": "balanced",
    "EGO_INTELLECT": "balanced"
  }
}
```

### 7. Phoneme-Based Consistency Validation

**The Problem:** How do you detect when a stored insight may be user-specific, metaphorical, or idiosyncratic rather than structurally consistent?

**The Solution:** Use phonemic patterns as an orthogonal consistency check—detecting mismatches between linguistic form and encoded event structure.

```
Event → Words describing event → Phoneme analysis → Consistent encoding?
                                                          ↓
                                        YES: Structurally consistent (store it)
                                        NO:  Potential anomaly (flag for review)
```

**How It Works:**

1. User describes an event: "The empire was shattered by internal conflict"
2. Extract key words: ["shattered", "conflict"]
3. Get phoneme 12D vectors for each word (from resonance engine)
4. Get event 10D vector (from backbone encoder)
5. Compare: Do the articulation patterns correlate with the event encoding?

```python
validation = validate_event(
    event_text="The empire was shattered by internal conflict",
    event_words=["shattered", "conflict"],
)

if validation.is_consistent:
    # Phoneme patterns correlate with event encoding → Store and transfer
    experiential_store.add(experiential)
else:
    # Mismatch detected → Flag for review (may be metaphorical or idiosyncratic)
    log.info(f"Consistency check: {validation.mismatch_reason}")
```

**Validation Results:**

| Result | Meaning | Action |
|--------|---------|--------|
| `CONSISTENT` | Phoneme patterns correlate with event encoding | Store and transfer |
| `MISMATCH` | Patterns don't correlate | Flag for review |
| `METAPHORICAL` | Partial correlation | Store with lower confidence |
| `INSUFFICIENT` | Not enough data to validate | Skip validation |

**Why This Works (Probabilistically):**

The phoneme model provides a statistical correlation between articulation patterns and semantic encoding. If the word "shattered" has phonemic characteristics associated with "destruction" patterns, and the event also encodes "destruction", there's high correlation. Low correlation may indicate metaphorical, ironic, or idiosyncratic usage.

```
HIGH CORRELATION:
  "shattered" phoneme profile → destruction-associated (0.8)
  Event encoding → destruction (0.75)
  Correlation: 0.92 ✓

LOW CORRELATION:
  "interesting" phoneme profile → thinking, forming
  Event encoding → destruction, conflict
  Correlation: 0.31 ✗ (likely metaphorical/ironic usage)
```

**Self-Filtering System with Orthogonal Validation:**

- Structurally consistent patterns are prioritized for storage
- Mismatches are flagged for review (not automatically discarded)
- **Two orthogonal validation layers:**
  - **Semantic Layer**: Checks logical compatibility (can concepts coexist?)
  - **Phoneme Layer**: Checks articulation-encoding correlation (do patterns align?)
- System is **transparent**: reports WHICH layer flagged and WHY

### 8. Reasoning Synthesis

Multiple experientials combine into unified, actionable output:

```
PROBLEM: "My startup has two co-founders who disagree on direction"

RETRIEVED (via persona pattern):
┌─────────────────────────────────────────────────────────────────┐
│ [History] Civil War bifurcation (balance: 0.77)                 │
│   Events: conflict, division                                    │
│   Insight: Polarity → split if no middle ground                │
├─────────────────────────────────────────────────────────────────┤
│ [Finance] Market crash dynamics (balance: 0.72)                 │
│   Events: collapse, destruction                                 │
│   Insight: Crisis forces restructuring                         │
├─────────────────────────────────────────────────────────────────┤
│ [Biology] Cell division (balance: 0.81)                         │
│   Events: division, formation                                   │
│   Insight: Controlled split creates two healthy units          │
└─────────────────────────────────────────────────────────────────┘

SYNTHESIZED OUTPUT:
─────────────────────────────────────────
**Key Insight**: Systems under pressure either find middle
ground or split—unclear division is worst outcome.

**Cross-Domain Pattern** (from your query history):
  History ↔ Finance ↔ Biology: bifurcation patterns

**Recommended Actions**:
1. Diagnose: Is disagreement ideological or strategic?
2. If strategic: Negotiate clear role boundaries
3. If ideological: Plan clean separation (biology model)

**Warning**: Unclear division destroyed Lear's kingdom.
─────────────────────────────────────────
```

---

## Complete AGI Architecture Diagram

```
                         ┌─────────────────────────┐
                         │      USER PROBLEM       │
                         │  "Co-founders disagree" │
                         └───────────┬─────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │    EVENT TAGGING        │
                         │  conflict, division     │
                         │  (not entity naming)    │
                         └───────────┬─────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │    10D ENCODING         │
                         │  [0.6, 0.8, 0.3, ...]  │
                         └───────────┬─────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │   MIRROR BALANCE CHECK  │
                         │                         │
                         │  Acting ↔ Absolving     │
                         │  Tagging ↔ Unifying     │
                         │  ...                    │
                         │                         │
                         │  Balance: 0.77 ✓        │
                         └───────────┬─────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
          ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
          │   HISTORY   │  │   FINANCE   │  │   BIOLOGY   │
          │             │  │             │  │             │
          │ bifurcation │  │  collapse   │  │  division   │
          │ balance:0.77│  │ balance:0.72│  │ balance:0.81│
          └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
                 │                │                │
                 └────────────────┼────────────────┘
                                  │
                                  ▼
                         ┌─────────────────────────┐
                         │   PERSONA TRACKER       │
                         │                         │
                         │  Pattern: "collapse"    │
                         │  Bridge: finance↔history│
                         │  Suggest: both domains  │
                         └───────────┬─────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │  REASONING SYNTHESIZER  │
                         │                         │
                         │  • Common events        │
                         │  • Mirror-balanced only │
                         │  • Cross-domain links   │
                         └───────────┬─────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │   PERSONALIZED OUTPUT   │
                         │                         │
                         │  Insight + Actions +    │
                         │  Domain bridges shown   │
                         └───────────┬─────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │ PHONEME CONSISTENCY     │
                         │                         │
                         │  Words → Phoneme 10D    │
                         │  Event → Event 10D      │
                         │  Correlate? → Consistent│
                         └───────────┬─────────────┘
                                     │
                        ┌────────────┴────────────┐
                        │                         │
                        ▼                         ▼
              ┌─────────────────┐      ┌─────────────────┐
              │   CONSISTENT    │      │   MISMATCH      │
              │  Store & Use    │      │  Flag/Review    │
              └────────┬────────┘      └─────────────────┘
                       │
                       ▼
                         ┌─────────────────────────┐
                         │      FEEDBACK LOOP      │
                         │                         │
                         │  Updates persona        │
                         │  Strengthens bridges    │
                         │  Refines event weights  │
                         └─────────────────────────┘
```

---

## What Makes This Architecture Generalizable

### ✓ Achieved

| Capability | Implementation |
|------------|----------------|
| Universal representation | 10D as 5 mirror pairs |
| Cross-domain transfer | Balance-based matching |
| Event understanding | Tag events, not entities |
| Pattern discovery | From user queries, not extraction |
| Personalization | Persona query tracking |
| Explainability | Mirror balance visible |
| Zero-shot domain transfer | No retraining needed |
| Insight quality metric | Balance score |
| **Orthogonal consistency check** | **Phoneme-encoding correlation** |
| **Self-filtering data** | **Mismatches flagged for review** |

### ○ Future Extensions

| Capability | Path Forward |
|------------|--------------|
| Self-improvement | Feedback refines event weights |
| Novel insight generation | Combine balanced experientials |
| Active learning | Ask questions when imbalanced |
| Multi-modal | Events in images, audio |
| Real-time adaptation | Stream persona updates |

---

## Mathematical Foundation

### Mirror Pair Mathematics

The 10D backbone maps to fundamental mathematical structures through mirror pairs:

| Lower | Math | Higher | Math | Relationship |
|-------|------|--------|------|--------------|
| 1D Acting | Linear algebra | 10D Absolving | Infinity | Event ↔ Meaning |
| 2D Tagging | Ratios | 9D Unifying | Limits | Naming ↔ Connecting |
| 3D Forming | Geometry | 8D Observing | Probability | Structure ↔ Perspective |
| 4D Thinking | Recursion | 7D Purposing | Topology | Process ↔ Purpose |
| 5D Directing | Boolean | 6D Reasoning | Set theory | Choice ↔ Justification |

**Key Claim:** The mirror pairs create a constraint system where balanced vectors represent transferable insights.

### Balance Computation

```python
def compute_balance(vector):
    pairs = [
        (ACTION, ABSOLUTE),
        (IDENTIFICATION, SINGULARITY),
        (BODY, WITNESS),
        (MIND, SOUL),
        (EGO, INTELLECT),
    ]

    imbalance = sum(abs(vector[low] - vector[high]) for low, high in pairs)
    return 1.0 - (imbalance / 5.0)
```

### Propagation Rule

```python
def propagate(vector):
    for lower, higher in pairs:
        if vector[lower] > 0.6 and vector[higher] < 0.4:
            # Grounded but not abstract → propagate up
            vector[higher] = vector[lower] * 0.7
    return vector
```

---

## Comparison to Other Approaches

| Approach | Limitation | Symbol-U Solution |
|----------|------------|-------------------|
| LLM embeddings | Opaque, no reasoning | Interpretable mirror pairs |
| Knowledge graphs | Domain-specific | Universal 10D ontology |
| Expert systems | Brittle rules | Flexible event matching |
| Neural-symbolic | Hard to integrate | Math-cognitive bridge |
| Transfer learning | Requires fine-tuning | Zero-shot via balance |
| Pattern extraction | Too much data | Pattern discovery via usage |

---

## The Philosophy → Pattern Matching Bridge

This may sound like philosophy, but it's **computable pattern matching**:

```
PHILOSOPHY                          COMPUTATION
───────────                         ───────────
"Action and Meaning are linked"  →  |Acting - Absolving| < threshold
"Grounded insights transfer"     →  balance_score >= 0.6
"Users reveal their patterns"    →  persona.bridges[domain_a][domain_b]++
"Events, not names, matter"      →  tag_events() not extract_entities()
```

---

## Files Reference

```
symbolu/ontology/backbone/
├── __init__.py              # Module exports
├── encoder.py               # 10D encoding (deterministic)
├── extractors.py            # Per-dimension extractors
├── similarity.py            # Cross-domain matching
├── rag_integration.py       # 10D-aware retrieval
├── experiential.py          # ExperientialObject + Store
├── reasoning_extractor.py   # Pattern extraction (legacy)
├── user_inclination.py      # User profiles
├── reasoning_synthesizer.py # Multi-source synthesis
├── mirror_pairs.py          # Mirror pair architecture
├── persona_tracker.py       # Query-based pattern discovery
├── phoneme_validator.py     # Ground truth validation
├── learning_pipeline.py     # Event learning + causal chain matching
├── insight_suggester.py     # Personal insights (presentation layer)
├── cross_domain_config.py   # Admin-level cross-domain policies ← NEW
└── cross_domain_config.json # JSON config for domain pairs ← NEW

symbolu/resonance/
├── phoneme_map.py           # Phoneme → 10D affinities
├── engine.py                # word_to_vector, compute_resonance
├── analyzer.py              # High-level analysis functions
└── varna_bridge.py          # Sanskrit phoneme mappings
```

---

## 9. Event Learning Architecture

The core generalization capability comes from **event learning**—the system learns by observing events, checking consistency, and storing structurally validated patterns for cross-domain transfer.

### Learning vs. Transparency

| Purpose | Mechanism | Signal Type |
|---------|-----------|-------------|
| **User Transparency** | Orthogonal validation (semantic + phoneme) | Multi-valued (which layer, why) |
| **Cross-Domain Learning** | 10D structural encoding | Continuous (similarity scores) |

**Key insight**: Transparency is for users. Learning happens on the 10D structure.

### The Learning Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVENT LEARNING PIPELINE                              │
└─────────────────────────────────────────────────────────────────────────────┘

    Input Event
         │
         ▼
┌─────────────────┐
│ SEMANTIC GATE   │  ← Boolean: Pass/Block
│ (pre-filter)    │     "Is this logically possible?"
└────────┬────────┘
         │ Pass
         ▼
┌─────────────────┐
│ 10D ENCODING    │  ← Continuous: The learning target
│ (structure)     │     This is what transfers across domains
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PHONEME GATE    │  ← Boolean: Store/Discard
│ (post-validate) │     "Is this universally encoded?"
└────────┬────────┘
         │ Pass
         ▼
┌─────────────────┐
│ PATTERN STORE   │  ← Validated universal patterns
│ (experiential)  │     Ready for cross-domain retrieval
└─────────────────┘
```

### Why This Architecture?

1. **Semantic = Pre-filter (Boolean)**
   - Removes logical impossibilities before encoding
   - "fire+cold" blocked before it wastes compute
   - Fast, deterministic, learned knowledge

2. **10D Structure = Learning Target (Continuous)**
   - What actually transfers across domains
   - Cross-domain matching via cosine similarity
   - Structural patterns, not word labels

3. **Phoneme = Post-validation (Boolean)**
   - Checks if articulation patterns correlate with event encoding
   - Probabilistic consistency check, not absolute truth
   - Final gate before storage

### Cross-Domain Retrieval

```python
# Matching happens on 10D STRUCTURE, not validation layers
def find_similar_events(query_vector_10d, threshold=0.7):
    return [
        event for event in pattern_store
        if cosine_similarity(event.vector_10d, query_vector_10d) > threshold
    ]
```

**Example:**
```
Query: "My startup has co-founders who disagree"
       → 10D encoding: [0.2, 0.4, 0.7, 0.3, 0.5, 0.6, 0.4, 0.3, 0.2, 0.1]

Retrieved (by 10D similarity):
├── [History] Civil War bifurcation     (similarity: 0.89)
├── [Biology] Cell division             (similarity: 0.85)
├── [Finance] Company spinoff           (similarity: 0.82)
└── [Physics] Nuclear fission           (similarity: 0.78)

All share structural pattern: "unified entity → internal tension → split"
```

### Learning Hierarchy for Cross-Domain Transfer

**Critical insight**: Not all knowledge propagates equally across domains.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LEARNING HIERARCHY                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Priority 1: CAUSAL CHAINS (Weight: 0.6)
─────────────────────────────────────────
   polarization → conflict → split
   ↑
   These sequences are UNIVERSAL
   Same pattern works for cells, companies, nations, families

Priority 2: 10D STRUCTURAL SIMILARITY (Weight: 0.3)
─────────────────────────────────────────
   [0.2, 0.4, 0.7, 0.3, ...]
   ↑
   FALLBACK when causal chains aren't explicit
   Vector similarity in 12D space

Priority 3: PATTERN TYPE (Weight: 0.1)
─────────────────────────────────────────
   bifurcation, escalation, threshold
   ↑
   DISAMBIGUATION when chains overlap
   Helps distinguish similar but different patterns

EXCLUDED: INSIGHTS (Weight: 0)
─────────────────────────────────────────
   "This reminds me of..."
   ↑
   User-specific reflections
   NOT basis for universal transfer
```

**Why Causal Chains First?**

Causal chains are domain-agnostic:
- `polarization → conflict → split` applies to:
  - Cell biology (mitosis)
  - History (civil wars)
  - Business (company spinoffs)
  - Family (divorce)

The sequence structure transfers, not the domain-specific vocabulary.

**Implementation:**

```python
def retrieve_similar(query, store):
    # Use Longest Common Subsequence (LCS) for chain matching
    chain_similarity = compute_chain_overlap(query_chain, exp_chain)

    # Weighted scoring
    final_score = (
        chain_similarity * 0.6 +      # PRIMARY
        structural_10d_sim * 0.3 +    # FALLBACK
        pattern_type_match * 0.1      # DISAMBIGUATION
    )

    # Insights are NOT included in scoring
    # They're user-specific, not universal
```

**Match Types:**

| Match Type | When Used | Score Weight |
|------------|-----------|--------------|
| `CAUSAL_CHAIN` | Chain overlap ≥ 0.5 | 60% |
| `STRUCTURAL` | 10D similarity ≥ threshold | 30% |
| `PATTERN_TYPE` | Same pattern category | 10% |

### Learning Summary

| Component | Role | Signal |
|-----------|------|--------|
| Semantic Gate | Block impossible combinations | Boolean |
| 10D Encoding | Capture transferable structure | Continuous (10 floats) |
| Phoneme Gate | Validate universal encoding | Boolean |
| Pattern Store | Accumulate validated patterns | Indexed by 10D |
| Retrieval | Match by structural similarity | Cosine on 10D |

The binary gates (semantic, phoneme) are for **validation**.
The continuous space (10D) is for **learning and transfer**.

### Personal Insights (Presentation Layer)

**Critical distinction**: Insights are excluded from LEARNING but valuable for PRESENTATION.

**Critical design**: Without structural validation, cross-domain suggestions become **advertising**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ADVERTISING vs GENUINE INSIGHT                            │
└─────────────────────────────────────────────────────────────────────────────┘

ADVERTISING (Wrong):
    "You looked at finance recently + you're reading biology = BUY STOCKS!"
    ↑ No structural validation, just domain co-occurrence

GENUINE INSIGHT (Right):
    "This biology pattern STRUCTURALLY matches a finance pattern you explored"
    ↑ Validated via 10D similarity, causal chain overlap, or shared events
```

### User-Controlled Insight Modes

**The user decides HOW insights are presented, not the system.**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    USER-CONTROLLED INSIGHT MODES                             │
└─────────────────────────────────────────────────────────────────────────────┘

Mode 1: RECENT_MEMORY
─────────────────────────
    "Show me connections to what I was just working on"
    → Prioritizes recency over structural match
    → User explicitly wants this context
    → Lower structural threshold

Mode 2: DOMAIN_RELATIVE
─────────────────────────
    "Stay focused on this domain"
    → No cross-domain suggestions at all
    → Deep dive mode - focus, not distraction
    → Only pattern continuations within domain

Mode 3: NEW_POSSIBILITIES (Default)
─────────────────────────
    "Show me novel connections I haven't explored"
    → ONLY if STRUCTURAL match exists
    → Requires: 10D similarity ≥ 0.5 OR causal overlap ≥ 0.3
    → This is discovery, but grounded in real patterns
```

### Structural Validation

Before ANY cross-domain insight is shown, the system validates:

```python
structural_match = compute_structural_match(
    current_vector_10d,
    current_events,
    target_vector_10d,
    target_events,
)

# NOT: user.recent_domains contains "finance"
# BUT: structural_match.is_valid == True

if not structural_match.is_valid:
    skip_this_insight()  # Don't show advertising
```

**Validation Thresholds:**

| Metric | Threshold | What It Measures |
|--------|-----------|------------------|
| 10D Similarity | ≥ 0.5 | Vector cosine in 12D space |
| Causal Overlap | ≥ 0.3 | LCS ratio of causal chains |
| Shared Events | ≥ 2 | Common event types |
| Combined Score | ≥ 0.4 | Weighted (0.6×causal + 0.3×10D + 0.1×events) |

### Implementation

```python
from symbolu.ontology.backbone import generate_insights, InsightMode

# User controls the mode
insights = generate_insights(
    persona_id="user_123",
    current_context="CRISPR breakthrough in gene editing...",
    current_domain="biology",
    mode=InsightMode.NEW_POSSIBILITIES  # User choice
)

for insight in insights:
    if insight.structural_match:
        print(f"Match: {insight.structural_match.combined_score:.0%}")
    print(f"💡 {insight.message}")
```

**Insight Types:**

| Type | When | Requires Structural Validation |
|------|------|--------------------------------|
| `STRUCTURAL_MATCH` | Cross-domain with validated structure | YES |
| `BRIDGE_OPPORTUNITY` | Cross-domain in RECENT_MEMORY mode | Computed but lower threshold |
| `PATTERN_CONTINUATION` | Same event type continues | NO (within domain) |
| `DOMAIN_DEPTH` | Deeper in same domain | NO (no cross-domain) |

---

## Conclusion

Symbol-U's architecture represents a **structural approach to generalizable reasoning**—and a deliberate step toward AGI. Built on key insights:

1. **Mirror Pairs**: 10D reduces to 5 balanced pairs—balance determines insight quality
2. **Event Tagging**: Tag what happened, not what it's called—solves clustering
3. **Persona Tracking**: Discover patterns from usage, not extraction—simplifies everything
4. **Orthogonal Validation**: Semantic (pre-filter) + Phoneme (post-validate) with transparency
5. **Event Learning**: 10D structure is the learning target; gates are for validation
6. **Learning Hierarchy**: Causal chains (PRIMARY) → 10D structure (FALLBACK) → Pattern type (DISAMBIGUATION) → Insights (NOT TRANSFERRED)
7. **Personal Insights**: Generated at presentation time from persona history—valuable for THIS user, not for universal learning
8. **User-Controlled Modes**: User decides insight mode (recent memory, domain-relative, new possibilities)—system doesn't assume
9. **Structural Validation**: Cross-domain insights require structural match (10D, causal, events)—without validation it's advertising
10. **Admin-Level Config**: JSON file controls which domain pairs can learn from each other—counters track blocked/successful transfers

### Admin-Level Cross-Domain Config

**System-wide control over cross-domain learning (not per-persona).**

```json
{
  "enabled": true,
  "default_policy": "allow",
  "domain_pairs": {
    "fiction_medicine": {
      "policy": "block",
      "reason": "Fictional medical patterns could be dangerous"
    },
    "finance_politics": {
      "policy": "require_high",
      "min_structural_threshold": 0.75,
      "reason": "Political-financial transfers need high confidence"
    }
  },
  "counters": {
    "blocked_attempts": {"fiction_medicine": 23},
    "successful_transfers": {"biology_finance": 156},
    "threshold_failures": {"ai_philosophy": 12}
  }
}
```

**Policies:**

| Policy | Behavior |
|--------|----------|
| `allow` | Cross-domain learning enabled with default thresholds |
| `block` | Cross-domain learning completely blocked |
| `require_high` | Allowed but requires 1.5× higher thresholds |
| `monitor` | Allowed but closely tracked in counters |

**Counters (Admin Visibility):**

```python
from symbolu.ontology.backbone import get_counters_report

report = get_counters_report()
print(f"Success rate: {report['summary']['success_rate']:.1%}")
print(f"Problem pairs: {report['problem_pairs']}")
```

The system is **self-consistent and self-filtering**:
- Extract events from content
- Encode to 10D with mirror balance
- Check consistency via phoneme-encoding correlation
- Structurally consistent patterns are prioritized
- Cross-domain bridges emerge from user queries

```
Content → Events → 10D → Balance → Orthogonal Validation → Consistent?
                                          ↓
                              ┌───────────┴───────────┐
                              │                       │
                         Semantic Check          Phoneme Check
                         (logical compat?)       (encoding correlation?)
                              │                       │
                              └───────────┬───────────┘
                                          ↓
                                  Both Pass? → Store & Transfer
                                  Either Fail? → Flag for Review (with explanation)
```

**The system is a transparent consistency checker, not an oracle.** It shows its work:
- Semantic layer reports: "These concepts are logical opposites" (structural incompatibility)
- Phoneme layer reports: "Articulation patterns don't correlate with event encoding" (probabilistic mismatch)

Neither layer claims absolute truth. Together they provide orthogonal consistency validation.
The design principle is embedded in the architecture: **show, don't tell.**

### The Path to AGI

This is not a final destination—it is infrastructure for the journey. The architecture provides:

| AGI Requirement | Symbol-U Solution | Status |
|-----------------|-------------------|--------|
| Universal knowledge representation | 10D mirror pairs | ✓ Implemented |
| Cross-domain reasoning | Balance-based transfer | ✓ Implemented |
| Self-improvement capability | Feedback refines weights | ○ Architected |
| Validation without external oracle | Orthogonal consistency | ✓ Implemented |
| Explainable reasoning | Transparent layer reports | ✓ Implemented |
| Novel insight generation | Combine balanced experientials | ○ Architected |

**The claims are conservative. The ambition is not.**

---

*Document Version: 3.8*
*Symbol-U Generalizable Cognitive Architecture — A Step Toward AGI*
*Event Learning + Orthogonal Consistency Validation + Learning Hierarchy + Admin Config*
*Learning Layer: Causal Chains + 10D Structure + Consistency Gates + Admin-Controlled Pairs*
*Presentation Layer: User-Controlled Modes + Structural Validation (No Advertising)*
*Framing: Conservative mechanism claims, ambitious AGI vision*
