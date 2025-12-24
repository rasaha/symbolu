# Phase-12–14 Forensic Architecture Review

**Date:** 2025-12-16
**Scope:** Phase-12 (Governed Generative Pipeline), Phase-13 (K1 Knowledge Layer), Phase-14 (Phonemic-Ontological Accumulator)
**Status:** Post-hoc forensic audit
**Location:** `docs/experiments/phase{12,13,14}_sandbox/`

---

## 1. Phase-by-Phase Inventory

### 1.1 Phase-12: Governed Generative Pipeline

#### Files

| File | Purpose | Lines |
|------|---------|-------|
| `phase12_schema.py` | Contract definitions, data structures, protocol interfaces | 649 |
| `phase12_poc.py` | Proof-of-concept pipeline orchestration | 451 |
| `phase12_ppv_encoder.py` | PPV → conditioning signal encoder | 431 |
| `phase12_retriever.py` | Template retrieval for few-shot context | 433 |
| `phase12_verifier.py` | Output verification layer | 611 |
| `tests/test_phase12_*.py` | Test suite (4 files) | ~500 |

#### Key Classes/Functions

| Component | Type | Purpose |
|-----------|------|---------|
| `Phase12Pipeline` | Class | Main pipeline orchestrator |
| `GovernedGenerativePipeline` | Class | PoC implementation with mock generator |
| `FrozenPPVEncoder` | Class | Deterministic PPV → conditioning encoder |
| `Phase12TemplateRetriever` | Class | Few-shot template retrieval |
| `Phase12Verifier` | Class | Multi-check output verification |
| `MockGenerator` | Class | Stub LLM for testing |
| `PPVConditioningSignal` | Dataclass | Conditioning signal structure |
| `GenerationContext` | Dataclass | Complete generation context |
| `VerificationResult` | Dataclass | Verification outcome |

#### Classification

| Component | Deterministic | Probabilistic | Structural | Generative | Verification |
|-----------|:-------------:|:-------------:|:----------:|:----------:|:------------:|
| `FrozenPPVEncoder` | ✓ | | ✓ | | |
| `Phase12TemplateRetriever` | ✓ | | ✓ | | |
| `MockGenerator` | | ✓ | | ✓ | |
| `Phase12Verifier` | ✓ | | | | ✓ |
| `Phase12Pipeline` | ✓ (orchestration) | | ✓ | | |

---

### 1.2 Phase-13: K1 Knowledge Layer

#### Files

| File | Purpose | Lines |
|------|---------|-------|
| `k1_schema.py` | K1 atom types, slots, discourse acts, query structures | 511 |
| `k1_store.py` | Storage, indexing, ledger, query execution | 477 |
| `tests/test_k1_*.py` | Test suite (2 files) | ~500 |

#### Key Classes/Functions

| Component | Type | Purpose |
|-----------|------|---------|
| `K1Atom` | Dataclass (frozen) | Minimal retrievable knowledge unit |
| `K1Query` | Dataclass (frozen) | Deterministic query specification |
| `K1ResultSet` | Dataclass (frozen) | Query result with replay proof |
| `K1Store` | Class | Storage with composite indices |
| `K1Slot` | Enum | 17 typed slots across 4 tiers |
| `DiscourseAct` | Enum | 14 structural discourse acts |
| `OntologicalLayer` | Enum | 12 ontological layers (O1-O10) |
| `LedgerEntry` | Dataclass | Audit trail entry |
| `RetrievalStep` | Dataclass | Replay proof step |

#### Classification

| Component | Deterministic | Probabilistic | Structural | Generative | Verification |
|-----------|:-------------:|:-------------:|:----------:|:----------:|:------------:|
| `K1Atom` | ✓ | | ✓ | | |
| `K1Query` | ✓ | | ✓ | | |
| `K1Store` | ✓ | | ✓ | | |
| `K1ResultSet` | ✓ | | ✓ | | |

---

### 1.3 Phase-14: Phonemic-Ontological Accumulator

#### Files

| File | Purpose | Lines |
|------|---------|-------|
| `accumulator.py` | Vote-based word→layer tracking | 565 |
| `layer_assigner.py` | POS-based layer assignment | 512 |
| `phoneme_extractor.py` | Word→phoneme conversion + PPV estimation | 620 |
| `character_deriver.py` | Cross-layer character profiles from phonemes | 445 |
| `rag_k1_pipeline.py` | Full RAG-K1 integration pipeline | 571 |
| `tests/test_*.py` | Test suite (4 files) | ~500 |

#### Key Classes/Functions

| Component | Type | Purpose |
|-----------|------|---------|
| `Accumulator` | Class | Word-layer vote counting |
| `LedgeredAccumulator` | Class | Accumulator with audit trail |
| `WordStats` | Dataclass | Per-word statistics |
| `StabilityStatus` | Enum | UNSTABLE/EMERGING/STABLE/CONFLICTED |
| `LayerAssigner` | Class (frozen) | POS→layer mapping |
| `PhonemeExtractor` | Class (frozen) | Dictionary + rule-based phoneme extraction |
| `CharacterDeriver` | Class (frozen) | Phoneme category→layer affinity |
| `RagK1Pipeline` | Class | Full integration pipeline |
| `PhonemeAnalysis` | Dataclass | Phoneme extraction result |
| `CharacterProfile` | Dataclass | Cross-layer propensity profile |

#### Classification

| Component | Deterministic | Probabilistic | Structural | Generative | Verification |
|-----------|:-------------:|:-------------:|:----------:|:----------:|:------------:|
| `Accumulator` | ✓ | | ✓ | | |
| `LayerAssigner` | ✓ | | ✓ | | |
| `PhonemeExtractor` | ✓ | | ✓ | | |
| `CharacterDeriver` | ✓ | | ✓ | | |
| `RagK1Pipeline` | ✓ (orchestration) | | ✓ | | |

---

## 2. Code Capture (Read-Only)

### 2.1 Phase-12: Core Execution Path

#### Entry Point: `GovernedGenerativePipeline.generate()`

```python
def generate(
    self,
    family: OntologicalFamily,
    ppv_values: Tuple[int, ...],
    canonical_signature: str,
    slot_plan: str,
    vc_data: Dict[str, str],
    mode: RenderMode = RenderMode.GOVERNED,
    request_id: Optional[str] = None,
) -> Phase12Response:
    """
    Execute the complete governed generation pipeline.

    Returns Phase12Response with either generated text or GENERATION_BLOCKED.
    """
    # Generate request ID if not provided
    if request_id is None:
        request_id = f"req_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]}"

    # 1. Encode PPV (deterministic)
    ppv_signal = self.ppv_encoder.encode(ppv_values, canonical_signature)

    # 2. Retrieve templates (deterministic)
    few_shot = build_few_shot_context(
        self.retriever,
        family,
        canonical_signature,
        slot_plan,
        max_examples=3,
    )

    # 3. Assemble context (deterministic)
    ontological = OntologicalContext(
        family=family,
        path=(family.value,),
        slot_plan=slot_plan,
        required_vc_facts=tuple(vc_data.keys()),
    )

    context = GenerationContext(
        request_id=request_id,
        artifact_hash=hashlib.sha256(str(vc_data).encode()).hexdigest(),
        ontological=ontological,
        ppv_signal=ppv_signal,
        few_shot=few_shot,
        vc_source_data=vc_data,
        mode=mode,
    )

    # 4. Generate (PROBABILISTIC - only non-deterministic step)
    generation = self.generator.generate(context)

    # 5. Verify (deterministic)
    verification = self.verifier.verify(context, generation)

    # 6. Build response
    if not verification.is_allowed(mode):
        return Phase12Response(
            output_text=GENERATION_BLOCKED,
            blocked=True,
            context_hash=context.context_hash(),
            generation_hash=generation.output_hash(),
            verification=verification,
            routing_trace_hash=ontological.context_hash(),
            mode=mode,
            ledger_span_id=f"span_{request_id[:16]}",
        )

    return Phase12Response(
        output_text=generation.text,
        blocked=False,
        context_hash=context.context_hash(),
        generation_hash=generation.output_hash(),
        verification=verification,
        routing_trace_hash=ontological.context_hash(),
        mode=mode,
        ledger_span_id=f"span_{request_id[:16]}",
    )
```

#### PPV Encoding: `FrozenPPVEncoder.encode()`

```python
def encode(
    self,
    ppv_values: Tuple[int, ...],
    canonical_signature: str,
) -> PPVConditioningSignal:
    """
    Encode PPV values into conditioning signal.
    """
    # Validate inputs
    if len(ppv_values) != PPV_DIM_COUNT:
        raise ValueError(f"ppv_values must have {PPV_DIM_COUNT} elements")

    for i, v in enumerate(ppv_values):
        if not (PPV_VALUE_RANGE[0] <= v <= PPV_VALUE_RANGE[1]):
            raise ValueError(
                f"ppv_values[{i}] = {v} out of range "
                f"[{PPV_VALUE_RANGE[0]}, {PPV_VALUE_RANGE[1]}]"
            )

    # Validate canonical signature format
    parts = canonical_signature.split("_")
    if len(parts) != PPV_DIM_COUNT:
        raise ValueError(
            f"canonical_signature must have {PPV_DIM_COUNT} parts, "
            f"got {len(parts)}"
        )

    for part in parts:
        if part not in CANONICAL_SUBBANDS:
            raise ValueError(
                f"Invalid subband '{part}' in signature. "
                f"Expected one of {CANONICAL_SUBBANDS}"
            )

    # Compute conditioning data based on strategy
    strategy = self._config.strategy

    if strategy == PPVEncodingStrategy.EMBEDDING:
        data = _compute_embedding(ppv_values, canonical_signature, self._config.embedding_dim)
    elif strategy == PPVEncodingStrategy.SOFT_PROMPT:
        data = _compute_soft_prompt(ppv_values, canonical_signature, self._config.num_prompt_tokens)
    elif strategy == PPVEncodingStrategy.ADAPTER:
        data = _compute_adapter_id(ppv_values, canonical_signature)
    elif strategy == PPVEncodingStrategy.TEXT_PREFIX:
        data = _compute_text_prefix(ppv_values, canonical_signature, self._config.prefix_template)
    else:
        raise ValueError(f"Unsupported encoding strategy: {strategy}")

    return PPVConditioningSignal(
        raw_ppv=ppv_values,
        canonical_signature=canonical_signature,
        strategy=strategy,
        conditioning_data=data,
    )
```

#### Verification: `Phase12Verifier.verify()`

```python
def verify(
    self,
    context: GenerationContext,
    generation: RawGenerationResult,
) -> VerificationResult:
    """
    Verify generated output against context requirements.
    """
    # Select thresholds based on mode
    thresholds = (
        self.governed_thresholds
        if context.mode == RenderMode.GOVERNED
        else self.open_thresholds
    )

    # Run all checks
    checks: List[VerificationCheck] = []

    # 1. Structural check
    structural = check_structural(generation.text, thresholds)
    checks.append(structural)

    # 2. Ontological check
    ontological = check_ontological(
        generation.text,
        context.ontological.family,
        thresholds,
    )
    checks.append(ontological)

    # 3. PPV alignment check
    ppv_alignment = check_ppv_alignment(
        generation.text,
        context.ppv_signal.canonical_signature,
        thresholds,
    )
    checks.append(ppv_alignment)

    # 4. Content policy check
    content_policy = check_content_policy(generation.text, thresholds)
    checks.append(content_policy)

    # Determine overall status
    if not structural.passed:
        status = VerificationStatus.FAILED_STRUCTURAL
    elif not ontological.passed:
        status = VerificationStatus.FAILED_ONTOLOGICAL
    elif not ppv_alignment.passed:
        status = VerificationStatus.FAILED_PPV_ALIGNMENT
    elif not content_policy.passed:
        status = VerificationStatus.FAILED_CONTENT_POLICY
    else:
        status = VerificationStatus.PASSED

    # Calculate mode-specific allowance
    allowed_in_open = (
        check_structural(generation.text, self.open_thresholds).passed
        and check_content_policy(generation.text, self.open_thresholds).passed
    )
    allowed_in_governed = status == VerificationStatus.PASSED

    return VerificationResult(
        status=status,
        checks=tuple(checks),
        structural_score=structural.score,
        ontological_score=ontological.score,
        ppv_alignment_score=ppv_alignment.score,
        allowed_in_open=allowed_in_open,
        allowed_in_governed=allowed_in_governed,
    )
```

---

### 2.2 Phase-13: Core Execution Path

#### K1 Atom Structure

```python
@dataclass(frozen=True)
class K1Atom:
    """
    Smallest retrievable unit in K1.

    INVARIANT: K1Atom contains no free text.
    payload_ref is an opaque pointer (hash:xxx, uri:xxx, rag:xxx)
    """
    atom_id: str                    # Hash-stable identifier
    layer: OntologicalLayer         # O1-O10
    slot: K1Slot                    # One of 17 slot types
    discourse_act: DiscourseAct     # One of 14 structural acts
    payload_ref: str                # Opaque pointer (NOT text)
    provenance: str                 # Source identifier

    def atom_hash(self) -> str:
        """Compute deterministic hash of atom (excluding atom_id)."""
        content = (
            f"{self.layer.value}|{self.slot.value}|{self.discourse_act.value}|"
            f"{self.payload_ref}|{self.provenance}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]
```

#### K1 Query Execution: `K1Store.query()`

```python
def query(self, q: K1Query) -> K1ResultSet:
    """
    Execute a query and return results.

    INVARIANT: Same query over same store state → same ordered results.
    """
    steps: List[RetrievalStep] = []

    # Step 1: Initial candidate set from indices
    candidates: Set[str]

    # Use most specific index available
    if q.layer and q.slot and q.discourse_act:
        # Use primary composite index
        key = (q.layer.value, q.slot.value, q.discourse_act.value)
        candidates = self._idx_primary.get(key, set()).copy()
    elif q.layer and q.slot:
        # Intersect layer and slot
        layer_set = self._idx_layer.get(q.layer.value, set())
        slot_set = self._idx_slot.get(q.slot.value, set())
        candidates = layer_set.intersection(slot_set)
    # ... additional index strategies ...
    else:
        candidates = set(self._atoms.keys())

    initial_count = len(candidates)
    steps.append(RetrievalStep(
        step_type="index_lookup",
        input_count=len(self._atoms),
        output_count=initial_count,
        step_hash=hashlib.sha256(f"index:{initial_count}".encode()).hexdigest()[:8],
    ))

    # Step 2: Filter by additional query constraints
    filtered: List[K1Atom] = []
    for atom_id in candidates:
        atom = self._atoms.get(atom_id)
        if atom and q.matches(atom):
            filtered.append(atom)

    # Step 3: Sort by selection rule (deterministic)
    if q.selection_rule == SelectionRule.LEXICOGRAPHIC_ID:
        filtered.sort(key=lambda a: a.atom_id)
    elif q.selection_rule == SelectionRule.TIER_PRIORITY:
        tier_order = {
            "TIER_1_CORE": 1, "TIER_2_CONTROL": 2,
            "TIER_3_FRAMING": 3, "TIER_4_GOVERNANCE": 4,
        }
        filtered.sort(key=lambda a: (tier_order.get(a.get_slot_tier().value, 5), a.atom_id))
    elif q.selection_rule == SelectionRule.LAYER_ORDER:
        filtered.sort(key=lambda a: (a.layer.value, a.atom_id))

    # Step 4: Apply limit
    limited = filtered[:q.limit]

    # Build result with replay proof
    atom_ids = tuple(a.atom_id for a in limited)
    query_hash = q.query_hash()
    result_hash = compute_result_hash(query_hash, atom_ids)

    # Log to ledger
    self._log_operation("QUERY", atom_ids, True, query_hash=query_hash, result_hash=result_hash)

    return K1ResultSet(
        atoms=tuple(limited),
        query_hash=query_hash,
        result_hash=result_hash,
        ledger_span_id=f"span_{...}",
        store_version_id=self.version_id,
        replay_proof=tuple(steps),
    )
```

---

### 2.3 Phase-14: Core Execution Path

#### Accumulator Recording

```python
def record(
    self,
    word: str,
    layer: OntologicalLayer,
    source_doc: str = ""
) -> WordStats:
    """
    Record an observation of word → layer mapping.
    """
    word_lower = word.strip().lower()

    if word_lower not in self._word_stats:
        self._word_stats[word_lower] = WordStats(word=word_lower)

    self._word_stats[word_lower].record_observation(layer, source_doc)
    self._version += 1
    self._total_observations += 1

    return self._word_stats[word_lower]
```

#### Stability Calculation

```python
def get_stability_status(self) -> StabilityStatus:
    """Determine stability status based on observations and confidence."""
    if self.observations < MIN_OBSERVATIONS_UNSTABLE:  # 10
        return StabilityStatus.UNSTABLE

    confidence = self.get_confidence()

    if self.observations >= MIN_OBSERVATIONS_STABLE:  # 50
        if confidence >= CONFIDENCE_STABLE_THRESHOLD:  # 0.8
            return StabilityStatus.STABLE
        elif confidence < CONFIDENCE_CONFLICTED_THRESHOLD:  # 0.5
            return StabilityStatus.CONFLICTED

    return StabilityStatus.EMERGING
```

#### PPV Estimation from Phonemes

```python
def estimate_ppv(phonemes: Tuple[str, ...]) -> Tuple[int, ...]:
    """
    Estimate PPV from phoneme sequence.

    Returns 8-dimensional tuple: (attack, sustain, brightness, warmth, density, flow, resonance, edge)
    Values 0-10 inclusive.
    """
    if not phonemes:
        return (5, 5, 5, 5, 5, 5, 5, 5)  # Neutral default

    # Accumulate weighted contributions
    sums = [0.0] * 8
    count = 0

    for phoneme in phonemes:
        category = get_phoneme_category(phoneme)
        weights = CATEGORY_PPV_WEIGHTS[category]

        # Initial phonemes have more impact on attack
        position_weight = 1.5 if count == 0 else 1.0

        for i in range(8):
            sums[i] += weights[i] * position_weight

        count += 1

    # Average and clamp to 0-10
    if count > 0:
        result = tuple(
            min(10, max(0, int(round(s / count))))
            for s in sums
        )
    else:
        result = (5, 5, 5, 5, 5, 5, 5, 5)

    return result
```

#### Character Derivation

```python
def derive(
    self,
    analysis: PhonemeAnalysis,
    primary_layer: OntologicalLayer
) -> CharacterProfile:
    """
    Derive character profile from phonemic analysis.
    """
    phonemes = analysis.phonemes
    total_phonemes = len(phonemes)

    # Initialize layer scores
    layer_scores: Dict[OntologicalLayer, float] = {
        layer: 0.0 for layer in OntologicalLayer
    }

    # Process each phoneme
    for i, phoneme in enumerate(phonemes):
        category = get_phoneme_category(phoneme)
        affinities = CATEGORY_LAYER_AFFINITY.get(category, {})

        # Get position weights
        init_w, mid_w, final_w = get_position_weight(i, total_phonemes)

        # Add to layer scores
        for layer, base_affinity in affinities.items():
            # Apply position modifiers
            init_mod, final_mod = LAYER_POSITION_MODIFIER[layer]
            position_modifier = 1.0 + (init_w * init_mod) + (final_w * final_mod)

            contribution = base_affinity * position_modifier
            layer_scores[layer] += contribution

    # Normalize scores to 0.0-1.0
    if total_phonemes > 0:
        max_score = max(layer_scores.values()) if layer_scores else 1.0
        if max_score > 0:
            propensities = {
                layer.value: min(1.0, score / max_score)
                for layer, score in layer_scores.items()
            }
        else:
            propensities = {layer.value: 0.5 for layer in OntologicalLayer}
    else:
        propensities = {layer.value: 0.5 for layer in OntologicalLayer}

    # Boost primary layer slightly
    propensities[primary_layer.value] = min(1.0, propensities.get(primary_layer.value, 0.5) * 1.1)

    # Find dominant secondary layer
    secondary_scores = [
        (layer, score) for layer, score in propensities.items()
        if layer != primary_layer.value
    ]
    if secondary_scores:
        dominant_secondary = OntologicalLayer(
            max(secondary_scores, key=lambda x: x[1])[0]
        )
    else:
        dominant_secondary = primary_layer

    return CharacterProfile(
        word=analysis.word,
        primary_layer=primary_layer,
        propensities=propensities,
        dominant_secondary=dominant_secondary,
        phoneme_influence=phoneme_influence,
        profile_hash=compute_profile_hash(analysis.word, propensities),
    )
```

---

## 3. Structural Integrity Analysis

### 3.1 Responsibility Separation

| Criterion | Phase-12 | Phase-13 | Phase-14 |
|-----------|----------|----------|----------|
| Single Responsibility | ✓ Each component has clear purpose | ✓ Schema vs Store cleanly split | ⚠️ RagK1Pipeline does many things |
| Separation of Concerns | ✓ Encoding/Retrieval/Generation/Verification separate | ✓ Atoms/Queries/Store distinct | ⚠️ Deriver tightly coupled to extractor |
| Interface Clarity | ✓ Protocol definitions explicit | ✓ Query/ResultSet contracts clear | ⚠️ Character derivation hypothesis embedded in code |

### 3.2 Probabilistic Behavior Sandboxing

**Phase-12:**
- **Status:** ✓ Properly sandboxed
- `MockGenerator` is the ONLY probabilistic component
- All other components are demonstrably deterministic
- The pipeline explicitly marks generation step as probabilistic

**Phase-13:**
- **Status:** ✓ Fully deterministic
- K1Store query guarantees same query → same results (tested with 100-run invariant)
- All indices rebuild identically
- Replay proof provides step-by-step audit

**Phase-14:**
- **Status:** ✓ Fully deterministic
- Accumulator uses explicit vote counts, not statistical approximations
- Phoneme extraction uses dictionary lookup + rule-based fallback
- Character derivation uses fixed affinity matrices

### 3.3 Invariant Enforcement

| Invariant | Enforced | Implied Only | Location |
|-----------|:--------:|:------------:|----------|
| PPV must have 8 dimensions | ✓ | | `phase12_ppv_encoder.py:283-284` |
| PPV values must be 0-7 | ✓ | | `phase12_ppv_encoder.py:286-291` |
| Canonical signature must have 8 parts | ✓ | | `phase12_ppv_encoder.py:294-299` |
| Same query → same results | ✓ | | `test_k1_store.py:91-102` (100-run test) |
| K1Atom contains no free text | | ⚠️ | Docstring only, not enforced |
| Discourse acts don't imply intent | | ⚠️ | Docstring only, not enforced |
| Phoneme→layer affinity weights | | ⚠️ | Hardcoded constants, no validation |

### 3.4 Hidden Assumptions

**Phase-12:**
1. **Assumption:** Canonical signature format is always `{subband}_{subband}_...` with 8 parts
   - Partially enforced: validation exists but relies on correct Phase-11B.3 integration

2. **Assumption:** `GENERATION_BLOCKED` is a reserved string not appearing in valid output
   - Not enforced: no check prevents generator from producing this string

**Phase-13:**
1. **Assumption:** `payload_ref` is truly opaque
   - Not enforced: no structural validation of payload_ref format

2. **Assumption:** Discourse acts are "structural only"
   - Not enforced: semantic leakage could occur in downstream consumers

**Phase-14:**
1. **Assumption:** POS lexicons are comprehensive
   - Not documented: many words fall through to `UNKNOWN` → `O4_TAGGING`

2. **Assumption:** Phoneme category → layer affinity mappings are valid
   - Explicitly marked as HYPOTHESIS in docstrings, which is appropriate

3. **Assumption:** Mini dictionary covers representative vocabulary
   - Limited: ~370 words, scientific terms added ad-hoc

---

## 4. Ontological & PPV Alignment Check

### 4.1 Ontological Layers as Structural Routing

**Observation:** The implementation treats ontological layers (O1-O10) consistently as routing keys rather than semantic containers.

| Layer Usage | Phase-12 | Phase-13 | Phase-14 |
|-------------|----------|----------|----------|
| Routing/Selection | ✓ Family determines generation head | ✓ Layer is index key | ✓ Layer is vote target |
| Semantic Content | ⚠️ `FAMILY_MARKERS` dictionary introduces semantic expectations | ✓ Layer is opaque enum | ⚠️ `LAYER_OVERRIDE_LEXICON` embeds meaning |

**Flag:** Phase-12's `FAMILY_MARKERS` in `phase12_verifier.py:101-142` creates semantic expectations for each family:

```python
FAMILY_MARKERS: Dict[OntologicalFamily, Tuple[str, ...]] = {
    OntologicalFamily.THINKING: (
        "consider", "perhaps", "might", "reflect", "ponder", "wonder",
        "think", "believe", "suppose", "imagine",
    ),
    # ...
}
```

This is structural leakage: the verifier expects generated text to contain family-specific keywords, which couples output content to ontological classification.

### 4.2 PPV as Conditioning Signal

**Observation:** PPV is used as intended—a conditioning signal that influences but does not determine output.

| PPV Usage | Implementation | Appropriate? |
|-----------|----------------|--------------|
| Phase-12 Encoding | PPV → deterministic embedding/prefix | ✓ Conditioning only |
| Phase-12 Verification | PPV signature → energy level check | ⚠️ Creates expectation of style alignment |
| Phase-14 Estimation | Phonemes → PPV estimate | ✓ No feedback loop |

**Flag:** `check_ppv_alignment()` in `phase12_verifier.py:289-353` creates expectation that output style matches PPV energy:

```python
if dominant == "HIGH":
    expected_markers = HIGH_ENERGY_MARKERS  # ("intensely", "powerfully", ...)
elif dominant == "LOW":
    expected_markers = LOW_ENERGY_MARKERS   # ("quietly", "gently", ...)
```

This couples PPV (a structural conditioning signal) to semantic content expectations.

### 4.3 Phonemes as Terminal Realizations

**Assessment:**

> **Does the current implementation support the hypothesis "phonemes do not carry semantics but acquire character through ontological routing"?**

**Answer: Partially.**

**Supports:**
- Phoneme extraction is deterministic and dictionary-based
- PPV is estimated from phoneme acoustic properties, not meaning
- Character derivation uses phoneme category → layer affinity, not word meaning

**Contradicts:**
- `layer_assigner.py` assigns layers based on POS and semantic lexicons, not phonemic structure
- The pipeline flow is: word → POS → layer → (phonemes contribute character)
- Phonemes influence "secondary character" but primary layer comes from meaning-based POS tagging

The implementation is inverted from the hypothesis: **meaning (via POS) determines primary layer, then phonemes add color**, rather than **phonemes acquiring character through routing**.

---

## 5. Rigor vs Velocity Assessment

### 5.1 Where Speed Produced Genuine Insight

1. **Vote-based Accumulator Design (Phase-14)**
   - Explicit vote counts vs opaque weights is a sound architectural choice
   - Properties (auditable, editable, partial knowledge useful) are real differentiators
   - Stability state machine (UNSTABLE → EMERGING → STABLE/CONFLICTED) is well-conceived

2. **Deterministic Retrieval with Replay Proof (Phase-13)**
   - 100-run invariant test demonstrates commitment to determinism
   - RetrievalStep sequence provides genuine auditability
   - Index strategy selection based on query specificity is sensible

3. **Sandboxed Probabilistic Generation (Phase-12)**
   - Clear separation of deterministic (routing, encoding, verification) from probabilistic (LLM)
   - MockGenerator allows testing without LLM dependency
   - Multiple PPV encoding strategies shows thoughtful flexibility

### 5.2 Where Rigor Was Deferred

1. **Phoneme → Layer Affinity Matrices (Phase-14)**
   - `CATEGORY_LAYER_AFFINITY` contains 80+ hardcoded weights
   - Explicitly marked as "HYPOTHESIS" but no validation mechanism exists
   - No documented basis for specific weight values

2. **POS Lexicons (Phase-14)**
   - ~500+ words manually categorized across 15 POS types
   - No coverage analysis, no handling strategy for domain-specific vocabulary
   - Fallback suffix heuristics are brittle

3. **Semantic Markers in Verification (Phase-12)**
   - `FAMILY_MARKERS` and energy markers embed semantic expectations
   - No justification for specific word lists
   - Threshold values (0.5, 0.8, etc.) appear arbitrary

4. **K1 Slot-Tier Assignment (Phase-14)**
   - `_get_slot_for_layer()` mapping is hardcoded with no documented rationale
   - Example: Why does O3_EXECUTION map to CAUSE but O4_STRUCTURE maps to TARGET?

### 5.3 Surprisingly Solid Components

1. **`K1Store` Index Strategy**
   - Composite primary index + secondary indices is well-engineered
   - Index rebuild from atoms provides recovery mechanism
   - Version tracking enables state snapshots

2. **`FrozenPPVEncoder` Validation**
   - Comprehensive input validation with clear error messages
   - Support for 4 encoding strategies shows extensibility
   - `frozen=True` dataclass enforces immutability

3. **Test Coverage**
   - 100-run determinism test for K1Store
   - End-to-end tests for all major flows
   - Mode (OPEN/GOVERNED) distinction tested

### 5.4 Fragile or Over-Assumed Components

1. **`MockGenerator` Output Generation**
   - Uses `random.choice()` inside what should be deterministic tests
   - Energy level extraction from signature is brittle string parsing

2. **Cross-Phase Import Structure**
   - Multiple `sys.path.insert()` calls for imports
   - Circular dependency potential between sandboxes
   - Phase-11B.3 integration uses try/except ImportError

3. **Stability Thresholds**
   - Fixed constants (10, 50, 0.5, 0.8) are hardcoded
   - No mechanism to tune based on domain or vocabulary size

---

## 6. Risk & Stability Map

### 6.1 Safe to Move to Main Today

| Component | Rationale |
|-----------|-----------|
| `K1Atom`, `K1Query`, `K1ResultSet` | Frozen dataclasses, well-tested, no external dependencies |
| `K1Store` (core operations) | Determinism verified with 100-run test, clean separation |
| `PPVConditioningSignal` | Frozen dataclass, clear contract |
| `VerificationThresholds`, `VerificationCheck`, `VerificationResult` | Configuration and result types only |
| `StabilityStatus` enum | Simple state enumeration |
| `AccumulatorSnapshot` | Frozen audit structure |

### 6.2 Must Remain Experimental

| Component | Risk | Recommended Action |
|-----------|------|-------------------|
| `FAMILY_MARKERS` verification | Semantic coupling | Defer until semantic grounding is designed |
| `CATEGORY_LAYER_AFFINITY` matrices | Unvalidated hypothesis | Require empirical validation before promotion |
| `POS_LEXICON` | Incomplete coverage | Needs domain-specific extension mechanism |
| `LAYER_OVERRIDE_LEXICON` | Semantic embedding | Should be configurable, not hardcoded |
| `PhonemeExtractor.MINI_DICTIONARY` | Limited coverage | Needs expansion or external dictionary integration |
| Cross-phase import structure | Brittle paths | Needs proper package organization |

### 6.3 Should Be Frozen and Observed

| Component | Observation Goal |
|-----------|------------------|
| `Accumulator` vote counting | Track whether stability patterns emerge as expected |
| `CharacterDeriver` affinity calculation | Monitor whether derived characters correlate with human intuition |
| `RagK1Pipeline` integration | Observe end-to-end behavior before refactoring |
| PPV-from-phonemes estimation | Validate whether estimated PPV aligns with intended acoustic properties |

---

## 7. Conclusions (Non-Prescriptive)

### 7.1 What Exists

Three experimental sandboxes implementing a complete pipeline from text input to governed generation:

- **Phase-12:** A governed generative compiler with PPV conditioning, few-shot retrieval, probabilistic generation, and multi-check verification
- **Phase-13:** A minimal knowledge layer (K1) with typed atoms, deterministic retrieval, and full audit trail
- **Phase-14:** A phonemic-ontological accumulation system that derives layer assignments from POS tagging and cross-layer character from phonemic structure

### 7.2 What Works

1. **Determinism guarantees in K1Store** are properly implemented and tested
2. **Separation of probabilistic generation from deterministic verification** in Phase-12 is clean
3. **Vote-based accumulation** provides the claimed properties (auditable, editable, partial knowledge)
4. **Data structures** (frozen dataclasses) enforce immutability where appropriate
5. **Ledger recording** in both K1Store and LedgeredAccumulator provides audit trail

### 7.3 What Is Unproven

1. **Phoneme → layer affinity hypothesis** has no empirical validation
2. **Stability thresholds** (10, 50, 0.8, 0.5) are arbitrary
3. **POS lexicons** coverage and accuracy are unknown
4. **Cross-layer character derivation** has no ground truth comparison
5. **PPV-from-phonemes estimation** accuracy is untested

### 7.4 What Is Misleading If Misunderstood

1. **"Discourse acts are structural, not semantic"** — This is documented but not enforced; consumers could easily interpret acts semantically

2. **"K1Atom contains no free text"** — True, but `payload_ref` is just a string field with no format validation

3. **"Accumulator is like transformers but better"** — The comparison is directional (explicit vs opaque) but the vote-counting mechanism is fundamentally different from statistical learning

4. **"Phonemes acquire character through ontological routing"** — The current implementation inverts this: meaning determines routing, phonemes add color afterward

5. **"Governed mode is stricter than Open"** — True for thresholds, but both modes run identical checks; the difference is only in pass/fail thresholds

---

**End of Forensic Review**

*This document is a forensic snapshot. It describes what exists, not what should exist.*
