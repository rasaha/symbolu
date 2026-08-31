# Pipeline Stage Audit: Three Questions Analysis

## Framework

For every stage, only three questions matter:
1. **Does this stage have a single, unique responsibility?**
2. **Does it mutate state or only annotate?**
3. **Does it have authority, or is it advisory?**

If those are clean → the number of stages is irrelevant.

---

## Stage-by-Stage Audit

### 1. TTOR Router

| Question | Answer | Status |
|----------|--------|--------|
| Single responsibility? | Routes queries to mappers + determines tier/mode | ⚠️ **DUAL** |
| Mutates or annotates? | Annotates only (produces RoutingPlan) | ✅ CLEAN |
| Authority or advisory? | Authoritative | ✅ CLEAN |

**Issue:** TTOR does TWO things:
1. Selects which mappers to activate (HRM/LCM/LAM flags)
2. Determines engine family (Persona/Fusion/DHA/Renderer-only)

**Recommendation:** Split into:
- `MapperRouter` - decides which mappers run
- `EngineRouter` - decides which engine family executes

---

### 2. HRM (High-Resolution Mapper)

| Question | Answer | Status |
|----------|--------|--------|
| Single responsibility? | Maps aspects → conflict zones → resolution hints | ⚠️ **TRIPLE** |
| Mutates or annotates? | Annotates only | ✅ CLEAN |
| Authority or advisory? | Advisory | ✅ CLEAN |

**Issue:** HRM does THREE things:
1. Classifies dominant/suppressed aspects
2. Detects conflict zone patterns
3. Generates resolution hints

**Recommendation:** The aspect classification and conflict detection are tightly coupled (reasonable). But resolution hints could be extracted to a separate `HintGenerator` that takes conflict zones as input.

---

### 3. LCM (Low-Context Mapper)

| Question | Answer | Status |
|----------|--------|--------|
| Single responsibility? | Provides minimal structural classification | ✅ CLEAN |
| Mutates or annotates? | Annotates only | ✅ CLEAN |
| Authority or advisory? | Advisory | ✅ CLEAN |

**Status: CLEAN** - LCM has a single, focused responsibility: fast-path classification for simple queries.

---

### 4. LAM (Long-Arc Mapper)

| Question | Answer | Status |
|----------|--------|--------|
| Single responsibility? | Maps temporal-longitudinal cognitive patterns | ✅ CLEAN |
| Mutates or annotates? | **MUTATES** (TemporalBhavaTracker) | ⚠️ **UNCLEAR** |
| Authority or advisory? | Authoritative for temporal dynamics | ✅ CLEAN |

**Issue:** LAM is the ONLY mapper that mutates state. This breaks the pattern where all mappers are stateless annotators.

**The mutation is intentional** - LAM needs cross-turn context to detect trajectories. But this creates an exception in the architecture.

**Recommendation:** Make the mutation explicit in the architecture:
- Mappers (HRM/LCM): Stateless, annotate only
- Temporal Tracker (LAM): Stateful, authoritative for arc patterns

Or extract the tracker update to a separate `TemporalStateManager` that LAM calls.

---

### 5. Candidate Generation

| Question | Answer | Status |
|----------|--------|--------|
| Single responsibility? | Creates candidates from mapper outputs | ⚠️ **DUAL** |
| Mutates or annotates? | Annotates only | ✅ CLEAN |
| Authority or advisory? | Advisory | ✅ CLEAN |

**Issue:** Candidate Generation does TWO things:
1. Converts mapper outputs to Candidate schema
2. Integrates RAG retrieval results

**Recommendation:** Split into:
- `MapperCandidateFactory` - converts mapper outputs
- `RAGCandidateFactory` - handles retrieval integration
- `CandidateMerger` - combines both (or keep as orchestrator)

---

### 6. Stitching Encoder

| Question | Answer | Status |
|----------|--------|--------|
| Single responsibility? | Decides what candidates are ALLOWED | ✅ CLEAN |
| Mutates or annotates? | Annotates only (produces StitchingResult) | ✅ CLEAN |
| Authority or advisory? | **Authoritative** | ✅ CLEAN |

**Status: CLEAN** - Stitching has a clear, single responsibility:
- Filters candidates via constrained optimization
- Prices domain jumps (doesn't block)
- Produces diagnostic audit trail

**Design principle confirmed:** "Stitching decides what is allowed. Fusion decides what is best."

---

### 7. Fusion Scorer

| Question | Answer | Status |
|----------|--------|--------|
| Single responsibility? | Calculates weighted fusion scores | ⚠️ **OVERLAP** |
| Mutates or annotates? | Annotates only | ✅ CLEAN |
| Authority or advisory? | Advisory (FusionEngine selects) | ⚠️ **CONFUSION** |

**Issue 1:** Fusion Scorer also scores candidates, overlapping with Stitching:
- Stitching: `Score = Relevance - Redundancy - DomainJump`
- Fusion: `Score = α×HRM + β×LCM + γ×MoE + modifiers`

**Issue 2:** Who has authority?
- Fusion Scorer ranks candidates
- FusionEngine makes final selection
- But Stitching already filtered the pool

**Confusion:** Does Fusion re-rank candidates that Stitching already ranked? If so, what's the relationship between Stitching scores and Fusion scores?

**Recommendation:** Clarify the handoff:
- Stitching: Outputs `allowed_candidates` (boolean filter) + `diagnostic_scores`
- Fusion: Takes allowed candidates, applies channel reasoning, outputs `ranked_candidates`

Stitching scores should NOT compete with Fusion scores - Stitching is a gatekeeper, Fusion is a ranker.

---

### 8. DHA (Delivery Harmonization)

| Question | Answer | Status |
|----------|--------|--------|
| Single responsibility? | Determines HOW to deliver response | ⚠️ **DUAL** |
| Mutates or annotates? | **MUTATES TEXT** | ⚠️ **CONCERNING** |
| Authority or advisory? | Authoritative for delivery | ✅ CLEAN |

**Issue 1:** DHA does TWO things:
1. Analyzes readiness/resistance (diagnostic)
2. Modulates message text (transformation)

**Issue 2:** DHA mutates the actual response text. This is concerning because:
- It can change meaning, not just tone
- Changes are not clearly bounded
- Hard to audit what was changed

**Recommendation:** Split DHA into:
- `ReadinessAnalyzer` - produces delivery profile (annotates)
- `DeliveryModulator` - applies profile to text (transforms)

Make the transformation explicit and bounded:
```python
@dataclass
class DeliveryTransform:
    original_text: str
    modulated_text: str
    changes_applied: List[str]  # ["softened_directness", "added_metaphor", etc.]
```

---

### 9. Renderer

| Question | Answer | Status |
|----------|--------|--------|
| Single responsibility? | Structures output into 3 layers | ✅ CLEAN |
| Mutates or annotates? | Annotates only (produces RenderedOutput) | ✅ CLEAN |
| Authority or advisory? | Formatting authority (DHA can override) | ⚠️ **OVERLAP** |

**Issue:** If Renderer has formatting authority, why can DHA override it?

This suggests unclear order of operations:
- Does Renderer run before or after DHA?
- If DHA runs after Renderer, why doesn't DHA just do the formatting?

**Current understanding from docs:**
```
Fusion → DHA → Renderer
```

But DHA "modulates message" suggests it transforms text, while Renderer "structures output" also transforms text.

**Recommendation:** Clarify the sequence:
```
Option A: Fusion → Renderer (structure) → DHA (modulate structured text)
Option B: Fusion → DHA (modulate raw) → Renderer (structure modulated text)
```

Pick one and enforce it.

---

## Summary: Where Architecture is NOT Clean

| Stage | Issues |
|-------|--------|
| TTOR | Dual responsibility (routing + engine selection) |
| HRM | Triple responsibility (aspects + conflicts + hints) |
| LAM | Mutates state (exception to mapper pattern) |
| Candidate Generation | Dual responsibility (mapper + RAG integration) |
| Fusion Scorer | Overlaps with Stitching scoring; advisory vs authority unclear |
| DHA | Dual responsibility; mutates text with unclear bounds |
| Renderer | Authority overlap with DHA |

### Clean Stages

| Stage | Status |
|-------|--------|
| LCM | ✅ Single responsibility, annotates, advisory |
| Stitching | ✅ Single responsibility, annotates, authoritative |

---

## Recommended Refactoring Priority

### High Priority (Clarity Issues)

1. **Stitching ↔ Fusion relationship**
   - Define: Stitching = gatekeeper (boolean), Fusion = ranker (scores)
   - Stitching diagnostic_scores ≠ Fusion ranking_scores

2. **DHA ↔ Renderer sequence**
   - Define: Which runs first?
   - Define: What exactly does each transform?

### Medium Priority (Responsibility Split)

3. **TTOR split**
   - MapperRouter + EngineRouter

4. **DHA split**
   - ReadinessAnalyzer + DeliveryModulator

### Low Priority (Pattern Consistency)

5. **LAM state mutation**
   - Extract TemporalStateManager or document as intentional exception

6. **Candidate Generation**
   - Could split but current coupling is pragmatic

---

## The Clean Architecture Target

```
User Query
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ ROUTING LAYER (Annotates, Authoritative)                        │
│   MapperRouter → which mappers run                              │
│   EngineRouter → which engine family                            │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ MAPPING LAYER (Annotates, Advisory)                             │
│   HRM → conflict zones                                          │
│   LCM → structural classification                               │
│   LAM → temporal patterns [STATEFUL EXCEPTION]                  │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ CANDIDATE LAYER (Annotates, Advisory)                           │
│   CandidateFactory → creates candidates from mappers            │
│   RAGIntegrator → adds retrieval candidates                     │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ SELECTION LAYER                                                 │
│   Stitching (Annotates, Authoritative) → what is ALLOWED        │
│   Fusion (Annotates, Authoritative) → what is BEST              │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ DELIVERY LAYER                                                  │
│   ReadinessAnalyzer (Annotates, Advisory) → delivery profile    │
│   Renderer (Annotates, Authoritative) → structure output        │
│   DeliveryModulator (Mutates, Authoritative) → adapt tone       │
└─────────────────────────────────────────────────────────────────┘
    ↓
Response
```

### Key Principles in Clean Architecture:

1. **Each box has ONE responsibility**
2. **Annotators don't mutate; Mutators are explicit and bounded**
3. **Authority is clear: Authoritative stages make decisions, Advisory stages provide input**
4. **Stateful exceptions (LAM) are documented and intentional**
5. **Handoffs are clean: Stitching outputs → Fusion inputs (no score competition)**
