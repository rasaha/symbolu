# Graph-Based Generative Model: Feasibility Assessment & Requirements

## Symbol-U Acoustic-Phonetic Generation Implementation Requirements

**Version:** 1.0.0
**Status:** Feasibility Analysis
**Companion To:** `graph_generative_model_spec.md`

---

## Executive Summary

### The Honest Answer

**Does this model need training?**

| Component | Training Required? | Explanation |
|-----------|-------------------|-------------|
| Core Embeddings (32D) | **NO** | Deterministic from articulatory features |
| Vṛtti Mappings | **NO** | Fixed lookup table (already in codebase) |
| Graph Structure | **NO** | Rule-based construction |
| G2P Conversion | **PARTIAL** | Use pretrained/rule-based external tool |
| Message Passing Weights | **OPTIONAL** | Pure rules work, but GNN improves quality |
| Prosodic Contours | **YES (small)** | Pattern learning from examples |
| Coarticulation Strength | **OPTIONAL** | Rules work, ML improves naturalness |

**Bottom Line:**
- **Minimum viable:** ~70% rule-based, needs G2P tool and pronunciation dictionary
- **Production quality:** ~30% learned components for naturalness
- **Training data:** 10-50 hours of aligned speech (not millions of tokens)

---

## 1. What You Can Expect

### 1.1 Realistic Capability Levels

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CAPABILITY PROGRESSION                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Level 1: STRUCTURAL GENERATION (Rule-Based Only)                  │
│  ─────────────────────────────────────────────────────             │
│  - Correct phoneme sequences                                        │
│  - Valid syllable structures                                        │
│  - Basic stress patterns                                            │
│  - Vṛtti vector assignment                                         │
│  Requirements: G2P tool + pronunciation dictionary                  │
│  Training: NONE                                                     │
│  Quality: Robotic but linguistically correct                        │
│                                                                     │
│  Level 2: ACOUSTIC PARAMETERIZATION (+ P10 Integration)            │
│  ─────────────────────────────────────────────────────             │
│  - Pitch ranges applied                                             │
│  - Energy contours                                                  │
│  - Duration allocation                                              │
│  - Regime-appropriate suppression                                   │
│  Requirements: P10 acoustic frame integration                       │
│  Training: NONE                                                     │
│  Quality: Controlled but mechanical                                 │
│                                                                     │
│  Level 3: COARTICULATED GENERATION (+ Rules)                       │
│  ─────────────────────────────────────────────────────             │
│  - Smooth phoneme transitions                                       │
│  - Assimilation applied                                             │
│  - Duration adjustments                                             │
│  Requirements: Coarticulation rule database                         │
│  Training: NONE (rules) or MINIMAL (learned strengths)             │
│  Quality: More natural, still somewhat stiff                        │
│                                                                     │
│  Level 4: PROSODICALLY NATURAL (+ Small Model)                     │
│  ─────────────────────────────────────────────────────             │
│  - Natural pitch contours                                           │
│  - Appropriate phrase breaks                                        │
│  - Rhythm variation                                                 │
│  Requirements: Prosodic pattern database OR small GNN              │
│  Training: 10-50 hours aligned speech                              │
│  Quality: Natural-sounding within constraints                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 What This Architecture CANNOT Do

| Capability | Possible? | Why Not |
|------------|-----------|---------|
| Creative text generation | **NO** | This generates acoustic representation, not content |
| Semantic understanding | **NO** | Meaning comes from upstream phases (P6-P9) |
| Open-domain speech | **NO** | Constrained by regime and discourse act |
| Emotional expression | **LIMITED** | Suppressed by default per P10 |
| Real-time adaptation | **NO** | Deterministic within session |

### 1.3 What This Architecture CAN Do

| Capability | Quality | Notes |
|------------|---------|-------|
| Convert lexical selections to acoustic graph | **High** | Core function |
| Apply regime-appropriate acoustic constraints | **High** | Leverages existing P10 |
| Generate phonetically valid sequences | **High** | Rule-based, reliable |
| Model coarticulation effects | **Medium-High** | Rules + optional learning |
| Generate prosodic contours | **Medium** | Needs pattern database |
| Validate acoustic output | **High** | Constraint checking |

---

## 2. Required Resources (Not Training)

### 2.1 External Tools (Pre-existing, No Training)

```yaml
# Required External Dependencies

grapheme_to_phoneme:
  purpose: Convert text to phoneme sequences
  options:
    - name: g2p_en
      type: Neural (pretrained)
      accuracy: ~95%
      license: MIT
      install: pip install g2p_en

    - name: epitran
      type: Rule-based + IPA
      accuracy: ~90%
      license: MIT
      install: pip install epitran

    - name: espeak-ng
      type: Rule-based (formant synthesis)
      accuracy: ~85%
      license: GPL
      install: apt install espeak-ng

  recommendation: g2p_en for English (already trained, just use it)

syllabification:
  purpose: Segment phonemes into syllables
  options:
    - name: pyphen
      type: Rule-based (hyphenation patterns)
      install: pip install pyphen

    - name: Custom implementation
      type: Onset-maximization algorithm
      note: ~100 lines of code, well-documented

  recommendation: Custom implementation (deterministic, no dependencies)

pronunciation_dictionary:
  purpose: Word → phoneme lookup (backup for G2P failures)
  options:
    - name: CMU Pronouncing Dictionary
      entries: ~134,000 words
      format: ARPABET
      source: http://www.speech.cs.cmu.edu/cgi-bin/cmudict
      license: Public domain

    - name: BEEP Dictionary
      entries: ~250,000 words
      format: SAMPA
      source: British English

  recommendation: CMU dict (industry standard, free)
```

### 2.2 Static Data Resources (Lookup Tables)

```yaml
# Required Static Data

word_stress_database:
  purpose: Lookup stress patterns for words
  source: Derived from CMU dict (stress markers included)
  format: word → [PRIMARY, UNSTRESSED, SECONDARY, ...]
  size: ~134,000 entries
  training_required: NO

phoneme_features:
  purpose: Articulatory feature lookup
  source: IPA chart (standard)
  format: phoneme → {manner, place, voicing, ...}
  size: ~100 phonemes (English subset: ~40)
  training_required: NO
  note: Already partially implemented in codebase

vritti_mapping:
  purpose: Sound class → Vṛtti type
  source: Already exists in symbolu/formulas/vritti_mapper.py
  training_required: NO

coarticulation_rules:
  purpose: Phoneme pair → coarticulation type + strength
  source: Phonetics literature (well-documented)
  format: (phoneme_a, phoneme_b) → {type, strength}
  size: ~1,600 rules (40 × 40 phoneme pairs)
  training_required: NO (rules) or OPTIONAL (learned strengths)

assimilation_rules:
  purpose: Phonological processes
  source: Standard phonology (well-documented)
  examples:
    - /n/ → [ŋ] before velars
    - /t/ → [ʔ] before syllabic /n/
    - Voicing assimilation in clusters
  size: ~50 rules for English
  training_required: NO
```

### 2.3 Knowledge Bases (RAG-Like Retrieval)

```yaml
# Optional RAG-Like Components

prosodic_pattern_database:
  purpose: Retrieve prosodic contours by discourse context
  structure:
    query: (discourse_act, regime, phrase_type)
    retrieval: pitch_contour_template
  examples:
    - (QUESTION, INFORM, FINAL) → rising_contour_template
    - (EXPLANATION, REFLECT, MEDIAL) → continuation_contour_template
  size: ~100-500 patterns
  source: Derived from ToBI-annotated speech corpora
  training_required: NO (lookup) or OPTIONAL (learned retrieval)

duration_model_database:
  purpose: Retrieve duration patterns by context
  structure:
    query: (phoneme, position, stress, speech_rate)
    retrieval: duration_ms
  source: Derived from aligned speech data
  training_required: MINIMAL (statistics from data, not neural)

emphasis_pattern_database:
  purpose: Retrieve emphasis placement patterns
  structure:
    query: (focus_structure, discourse_act)
    retrieval: emphasis_positions
  size: ~50-100 patterns
  training_required: NO
```

---

## 3. Training Requirements (If Any)

### 3.1 What Actually Needs Training

```
┌─────────────────────────────────────────────────────────────────────┐
│              TRAINING REQUIREMENTS BY COMPONENT                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  COMPONENT                    | TRAINING | DATA NEEDED              │
│  ────────────────────────────────────────────────────────────────  │
│  G2P (grapheme-to-phoneme)   | USE PRETRAINED g2p_en               │
│  Syllabification             | NONE (rule-based)                   │
│  Phoneme embeddings          | NONE (deterministic)                │
│  Vṛtti assignment            | NONE (lookup table)                 │
│  Graph construction          | NONE (algorithmic)                  │
│  Hierarchical composition    | NONE (fixed weights)                │
│  Message passing (basic)     | NONE (constraint propagation)       │
│  ────────────────────────────────────────────────────────────────  │
│  Coarticulation strength     | OPTIONAL: 1-5 hours aligned speech  │
│  Duration prediction         | OPTIONAL: 5-10 hours aligned speech │
│  Prosodic contour selection  | OPTIONAL: 10-20 hours aligned speech│
│  Message passing (adaptive)  | OPTIONAL: 20-50 hours aligned speech│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Training Data Sources (If Needed)

```yaml
# Available Speech Corpora for Optional Training

free_corpora:
  - name: LJ Speech
    hours: 24
    speaker: Single female
    alignment: Character-level
    license: Public domain
    use_for: Duration model, prosodic patterns

  - name: LibriTTS
    hours: 585
    speakers: 2,456
    alignment: Word-level
    license: CC BY 4.0
    use_for: Coarticulation statistics, duration

  - name: VCTK
    hours: 44
    speakers: 110
    alignment: Word-level
    license: CC BY 4.0
    use_for: Speaker variation patterns

  - name: Common Voice
    hours: 2,500+
    speakers: Many
    alignment: Sentence-level
    license: CC0
    use_for: G2P validation (not directly useful for acoustic)

minimum_viable_training:
  corpus: LJ Speech (24 hours)
  components_trainable:
    - Duration model (statistics extraction)
    - Prosodic contour clustering
    - Coarticulation strength estimation
  training_time: ~2-4 hours on single GPU
  model_size: < 10MB (not a large neural model)
```

### 3.3 Training Architecture (If Used)

```python
# Optional Small Models (NOT Transformers)

class DurationPredictor(nn.Module):
    """
    Small MLP for phoneme duration prediction.

    Input: 32D acoustic embedding + context features (8D)
    Output: Duration in ms (single float)

    Architecture:
        Linear(40, 64) → ReLU → Linear(64, 32) → ReLU → Linear(32, 1)

    Parameters: ~3,500 (tiny)
    Training: 1-2 hours on CPU
    """

class ProsodySelector(nn.Module):
    """
    Small retrieval model for prosodic pattern selection.

    Input: Discourse context embedding (16D)
    Output: Pattern ID (classification over ~100 patterns)

    Architecture:
        Linear(16, 64) → ReLU → Linear(64, 100) → Softmax

    Parameters: ~7,500 (tiny)
    Training: < 1 hour on CPU
    """

class CoarticulationEstimator(nn.Module):
    """
    Estimate coarticulation strength between phoneme pairs.

    Input: Concatenated embeddings (64D = 32D + 32D)
    Output: Strength in [0, 1]

    Architecture:
        Linear(64, 32) → ReLU → Linear(32, 1) → Sigmoid

    Parameters: ~2,100 (tiny)
    Training: < 1 hour on CPU
    """

# Total trainable parameters: ~13,000 (compare to GPT-2: 117M)
```

---

## 4. RAG-Like Configuration

### 4.1 Knowledge Retrieval Architecture

The system uses **deterministic retrieval** rather than semantic search:

```
┌─────────────────────────────────────────────────────────────────────┐
│                KNOWLEDGE RETRIEVAL ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐                                               │
│  │ Query Context   │                                               │
│  │ - Discourse Act │                                               │
│  │ - Regime        │                                               │
│  │ - Phrase Type   │                                               │
│  │ - Focus Pattern │                                               │
│  └────────┬────────┘                                               │
│           │                                                         │
│           ▼                                                         │
│  ┌─────────────────┐                                               │
│  │  Hash Lookup    │  (NOT embedding similarity)                   │
│  │  key = hash(    │                                               │
│  │    discourse,   │                                               │
│  │    regime,      │                                               │
│  │    phrase_type  │                                               │
│  │  )              │                                               │
│  └────────┬────────┘                                               │
│           │                                                         │
│           ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    KNOWLEDGE STORES                          │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │                                                              │   │
│  │  Pronunciation DB     Prosody Patterns    Duration Stats     │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │   │
│  │  │ word → IPA   │    │ ctx → contour│    │ ctx → ms     │   │   │
│  │  │ "hello" →    │    │ Q+INF+FIN →  │    │ /p/+ONSET →  │   │   │
│  │  │  /həˈloʊ/    │    │  [L*+H H%]   │    │  85ms ± 15   │   │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘   │   │
│  │                                                              │   │
│  │  Coarticulation Rules   Assimilation Rules   Stress DB      │   │
│  │  ┌──────────────┐      ┌──────────────┐    ┌──────────────┐ │   │
│  │  │ (p1,p2) →    │      │ pattern →    │    │ word →       │ │   │
│  │  │  strength    │      │  transform   │    │  [1,0,2,0]   │ │   │
│  │  └──────────────┘      └──────────────┘    └──────────────┘ │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Knowledge Store Implementation

```python
@dataclass(frozen=True)
class KnowledgeStore:
    """
    Deterministic knowledge retrieval for acoustic generation.

    NOT a vector database - uses hash lookup for exact match.
    Falls back to default values if no match (fail-safe).
    """

    # Pronunciation
    pronunciation_db: Dict[str, str]  # word → IPA

    # Prosody patterns (key: discourse_act + regime + phrase_position)
    prosody_patterns: Dict[str, ProsodyPattern]

    # Duration statistics (key: phoneme + position + stress)
    duration_stats: Dict[str, DurationStats]

    # Coarticulation rules (key: phoneme_pair)
    coarticulation_rules: Dict[Tuple[str, str], CoarticulationRule]

    # Stress patterns
    stress_db: Dict[str, Tuple[int, ...]]  # word → stress pattern

    def lookup_pronunciation(self, word: str) -> Optional[str]:
        """Exact match lookup, returns None if not found."""
        return self.pronunciation_db.get(word.lower())

    def lookup_prosody(
        self,
        discourse_act: str,
        regime: str,
        phrase_position: str
    ) -> ProsodyPattern:
        """Lookup prosodic pattern, return default if not found."""
        key = f"{discourse_act}:{regime}:{phrase_position}"
        return self.prosody_patterns.get(key, DEFAULT_PROSODY_PATTERN)

    def lookup_duration(
        self,
        phoneme: str,
        position: str,
        stress: str
    ) -> DurationStats:
        """Lookup duration statistics, return default if not found."""
        key = f"{phoneme}:{position}:{stress}"
        return self.duration_stats.get(key, DEFAULT_DURATION_STATS)

    def lookup_coarticulation(
        self,
        phoneme_a: str,
        phoneme_b: str
    ) -> CoarticulationRule:
        """Lookup coarticulation rule, return default if not found."""
        return self.coarticulation_rules.get(
            (phoneme_a, phoneme_b),
            DEFAULT_COARTICULATION
        )

# Knowledge store is loaded from files at startup (not learned)
def load_knowledge_store(data_dir: Path) -> KnowledgeStore:
    """Load all knowledge stores from static files."""
    return KnowledgeStore(
        pronunciation_db=load_cmu_dict(data_dir / "cmudict.txt"),
        prosody_patterns=load_prosody_patterns(data_dir / "prosody.json"),
        duration_stats=load_duration_stats(data_dir / "durations.json"),
        coarticulation_rules=load_coart_rules(data_dir / "coarticulation.json"),
        stress_db=extract_stress_from_cmu(data_dir / "cmudict.txt"),
    )
```

### 4.3 Data File Formats

```yaml
# /data/acoustic/cmudict.txt (CMU Pronouncing Dictionary)
# Format: WORD  PHONEME PHONEME PHONEME ...
# Stress marked with 0 (no stress), 1 (primary), 2 (secondary)
HELLO  HH AH0 L OW1
WORLD  W ER1 L D
UNDERSTAND  AH2 N D ER0 S T AE1 N D

# /data/acoustic/prosody.json
{
  "patterns": {
    "EXPLANATION:INFORM:FINAL": {
      "pitch_contour": "H* L-L%",
      "boundary_tone": "L%",
      "phrase_accent": "L-",
      "pitch_range_modifier": 1.0
    },
    "QUESTION:CLARIFY:FINAL": {
      "pitch_contour": "L* H-H%",
      "boundary_tone": "H%",
      "phrase_accent": "H-",
      "pitch_range_modifier": 1.2
    }
  }
}

# /data/acoustic/durations.json
{
  "statistics": {
    "P:ONSET:UNSTRESSED": {"mean_ms": 85, "std_ms": 15},
    "P:ONSET:PRIMARY": {"mean_ms": 95, "std_ms": 18},
    "AE:NUCLEUS:PRIMARY": {"mean_ms": 120, "std_ms": 25},
    "AE:NUCLEUS:UNSTRESSED": {"mean_ms": 70, "std_ms": 15}
  }
}

# /data/acoustic/coarticulation.json
{
  "rules": {
    "AE:L": {"type": "VOWEL_DARKENING", "strength": 0.4},
    "N:K": {"type": "PLACE_ASSIMILATION", "strength": 1.0},
    "S:SH": {"type": "FRICATIVE_ASSIMILATION", "strength": 0.6}
  }
}
```

---

## 5. Implementation Priority

### 5.1 Phase 0: Data Preparation (1 week)

```
[ ] Download and process CMU Pronouncing Dictionary
[ ] Extract stress patterns from CMU dict
[ ] Create phoneme feature table (40 phonemes × 15 features)
[ ] Build coarticulation rule database from phonetics literature
[ ] Create prosodic pattern templates (50-100 patterns)
[ ] Set up knowledge store loading infrastructure
```

### 5.2 Phase 1: Minimum Viable System (2 weeks)

```
[ ] Integrate g2p_en for grapheme-to-phoneme
[ ] Implement syllabification algorithm
[ ] Build graph skeleton constructor
[ ] Implement deterministic 32D embeddings
[ ] Implement Vṛtti assignment (use existing code)
[ ] Basic message passing (constraint propagation only)
[ ] Acoustic constraint validation

Expected output: Correct but robotic acoustic graphs
```

### 5.3 Phase 2: Natural Generation (2-3 weeks)

```
[ ] Implement coarticulation rules (from database)
[ ] Implement assimilation rules
[ ] Add prosodic pattern retrieval
[ ] Add duration statistics application
[ ] Lateral message passing for smoothing

Expected output: More natural acoustic representation
```

### 5.4 Phase 3: Optional Learning (2-4 weeks)

```
[ ] Download LJ Speech corpus
[ ] Extract duration statistics from aligned data
[ ] Train small duration predictor (if needed)
[ ] Train prosody selector (if needed)
[ ] Evaluate quality improvement

Expected output: Near-natural quality within constraints
```

---

## 6. Resource Requirements Summary

### 6.1 Minimum Requirements (Rule-Based Only)

| Resource | Size | Source | Cost |
|----------|------|--------|------|
| CMU Dict | 5 MB | cmudict.sourceforge.net | Free |
| g2p_en model | 50 MB | pip install | Free |
| Phoneme features | 10 KB | IPA chart (manual) | Free |
| Coarticulation rules | 100 KB | Phonetics literature | Free |
| Prosody patterns | 50 KB | ToBI conventions | Free |
| **Total** | **~60 MB** | | **Free** |

### 6.2 Enhanced Requirements (With Optional Training)

| Resource | Size | Source | Cost |
|----------|------|--------|------|
| Base requirements | 60 MB | Above | Free |
| LJ Speech corpus | 2.6 GB | ljspeech.org | Free |
| Trained models | 10 MB | Self-trained | Free |
| Training compute | 4 GPU-hours | Cloud or local | ~$4 |
| **Total** | **~2.7 GB** | | **~$4** |

### 6.3 Compute Requirements

```yaml
inference:
  cpu_only: YES
  memory: 2 GB
  latency: < 100ms per utterance

training (if used):
  gpu: Optional (1x consumer GPU)
  memory: 8 GB
  time: 2-4 hours
  can_use_cpu: YES (slower, ~8-16 hours)
```

---

## 7. Comparison with Alternatives

### 7.1 vs. Transformer-Based TTS (Tacotron, FastSpeech)

| Aspect | Our Approach | Transformer TTS |
|--------|-------------|-----------------|
| Training data | 0-50 hours | 20-100+ hours |
| Model size | < 10 MB | 100-500 MB |
| Training time | 2-4 hours | 24-72 hours |
| Inference speed | < 100ms | 100-500ms |
| Control over output | **Full** | Limited |
| Regime compliance | **Built-in** | Requires fine-tuning |
| Determinism | **Guaranteed** | Probabilistic |
| Expressiveness | Limited | Higher |

### 7.2 vs. RAG-Augmented LLM

| Aspect | Our Approach | RAG-LLM |
|--------|-------------|---------|
| Text generation | **NO** (acoustic only) | Yes |
| Semantic search | NO (hash lookup) | Yes |
| Vector database | NO | Required |
| Embedding model | NO (deterministic) | Required |
| Hallucination risk | **NONE** | Present |
| Regime compliance | **Guaranteed** | Uncertain |

---

## 8. Conclusion

### What You Can Expect

1. **Immediate (with rule-based system):**
   - Linguistically correct acoustic graphs
   - Regime-compliant output
   - Deterministic, reproducible generation
   - Quality: Functional but robotic

2. **After knowledge base setup:**
   - Natural coarticulation
   - Appropriate prosodic patterns
   - Duration variation
   - Quality: More natural, still controlled

3. **After optional training:**
   - Smoother transitions
   - Better prosodic selection
   - Context-appropriate duration
   - Quality: Near-natural within constraints

### What You Need to Configure

| Component | Type | Effort |
|-----------|------|--------|
| G2P tool | Install package | 5 minutes |
| CMU dictionary | Download file | 5 minutes |
| Phoneme features | Manual table | 2 hours |
| Coarticulation rules | Manual + literature | 4-8 hours |
| Prosody patterns | Manual + ToBI | 4-8 hours |
| Knowledge store code | Implementation | 8-16 hours |
| **Total setup** | | **~1-2 weeks** |

### Recommendation

**Start with rule-based system** (Level 1-3 in capability progression):
1. Zero training required
2. Full regime compliance guaranteed
3. Establishes foundation for optional learning later
4. Can evaluate quality before investing in training

**Add optional learning later** if quality insufficient:
1. Only ~13,000 parameters (tiny)
2. 2-4 hours training on single GPU
3. Can always fall back to rules

---

**Document Version:** 1.0.0
**Last Updated:** 2025-12-16
**Author:** Symbol-U Architecture Team
