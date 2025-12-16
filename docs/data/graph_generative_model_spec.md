# Graph-Based Generative Model Specification

## Symbol-U Acoustic-Phonetic Generative Architecture

**Version:** 1.0.0
**Status:** Design Specification
**Foundation:** Phase-10 Acoustic Phonetic Model (GCC Disabled)

---

## Executive Summary

This specification defines a **graph-based generative model** for Symbol-U that leverages the existing acoustic-phonetic foundation. The design explicitly rejects transformer-based attention mechanisms in favor of:

1. **Directed Acoustic Graphs (DAG)** - Hierarchical structure from phonemes to utterances
2. **Vṛtti Vector Embeddings** - 5D motion-based acoustic representations
3. **Message Passing Generation** - Graph neural network propagation without attention
4. **Acoustic Unit Tokenization** - Phonetically-grounded tokenization strategy
5. **Deterministic Graph Rewriting** - Rule-based generation with acoustic constraints

---

## 1. Architectural Principles

### 1.1 Why Not Transformers?

| Transformer Property | Graph Alternative | Rationale |
|---------------------|-------------------|-----------|
| Global attention O(n²) | Local message passing O(E) | Acoustic relationships are local/hierarchical |
| Position encodings | Graph structure encodes position | Phonetic sequence is inherent in graph edges |
| Token independence | Phonetic dependencies explicit | Coarticulation requires explicit edge modeling |
| Statistical patterns | Deterministic acoustic rules | Sound physics are governed by articulatory constraints |
| Semantic attention | Acoustic feature propagation | "Sound obeys meaning" - meaning flows downstream |

### 1.2 Core Invariants

```
INVARIANT-1: Sound must obey meaning. Meaning must never obey sound.
INVARIANT-2: Generation follows acoustic physics, not statistical correlation.
INVARIANT-3: All embeddings derive from articulatory/acoustic features, not learned.
INVARIANT-4: Graph structure encodes linguistic hierarchy explicitly.
INVARIANT-5: No probabilistic sampling in core generation path.
```

---

## 2. Graph Structure Definition

### 2.1 Node Taxonomy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ACOUSTIC GENERATIVE GRAPH                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Level 5: UTTERANCE NODE                                           │
│           └── Discourse act, regime, prosodic contour              │
│                                                                     │
│  Level 4: PROSODIC PHRASE NODES                                    │
│           └── Intonation unit, pause boundaries                    │
│                                                                     │
│  Level 3: WORD NODES                                               │
│           └── Lexical selection, stress pattern                    │
│                                                                     │
│  Level 2: SYLLABLE NODES                                           │
│           └── Onset-nucleus-coda, Vṛtti distribution              │
│                                                                     │
│  Level 1: PHONEME NODES (Leaves)                                   │
│           └── Sound class, articulatory features                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Node Schema Definitions

#### 2.2.1 PhonemeNode (Level 1)

```python
@dataclass(frozen=True)
class PhonemeNode:
    """
    Leaf node representing a single phoneme with articulatory features.

    Attributes:
        node_id: Unique identifier (hash of position + phoneme)
        phoneme: IPA symbol or ARPABET representation
        sound_class: SoundClass enum (STOP, FRICATIVE, NASAL, etc.)

        # Articulatory Feature Vector (15D)
        manner: MannerOfArticulation  # STOP, FRICATIVE, AFFRICATE, NASAL, LIQUID, GLIDE, VOWEL
        place: PlaceOfArticulation    # BILABIAL, LABIODENTAL, DENTAL, ALVEOLAR, etc.
        voicing: Voicing              # VOICED, VOICELESS

        # Vowel-specific (if applicable)
        vowel_height: VowelHeight     # HIGH, MID, LOW, NA
        vowel_backness: VowelBackness # FRONT, CENTRAL, BACK, NA
        vowel_rounding: VowelRounding # ROUNDED, UNROUNDED, NA

        # Acoustic Properties
        duration_ms: int              # Intrinsic duration [50-300]
        intensity_db: float           # Relative intensity [0.0-1.0]

        # Vṛtti Assignment (derived)
        vritti_type: VrittiType       # INERTIA, ACTIVATION, OSCILLATION, TENSION, RELEASE
    """
```

#### 2.2.2 SyllableNode (Level 2)

```python
@dataclass(frozen=True)
class SyllableNode:
    """
    Syllable-level node with onset-nucleus-coda structure.

    Attributes:
        node_id: Unique identifier

        # Structure
        onset: Tuple[str, ...]        # Consonant cluster (may be empty)
        nucleus: str                   # Vowel or syllabic consonant
        coda: Tuple[str, ...]         # Consonant cluster (may be empty)

        # Prosodic Properties
        stress: StressLevel           # PRIMARY, SECONDARY, UNSTRESSED
        tone: Optional[ToneContour]   # For tonal languages (None for English)

        # Vṛtti Distribution Vector (5D, normalized)
        vritti_distribution: Tuple[float, float, float, float, float]
        # [inertia, activation, oscillation, tension, release]

        # Acoustic Summary
        total_duration_ms: int
        energy_contour: EnergyContour # RISING, FALLING, LEVEL, PEAK

        # Children
        phoneme_ids: Tuple[str, ...]  # Ordered phoneme node IDs
    """
```

#### 2.2.3 WordNode (Level 3)

```python
@dataclass(frozen=True)
class WordNode:
    """
    Word-level node linking lexical selection to acoustic realization.

    Attributes:
        node_id: Unique identifier

        # Lexical Properties
        lemma: str                    # Base form
        surface_form: str             # Actual realization
        pos_tag: POSTag               # Part of speech

        # From P9 Lexical Selection
        semantic_slot: SemanticSlot   # AGENT, TARGET, STATE, etc.

        # Prosodic Properties
        word_stress_pattern: Tuple[StressLevel, ...]  # Per-syllable stress
        focus: bool                   # Information focus marker

        # Aggregate Vṛtti Vector (weighted sum of syllables)
        vritti_vector: Tuple[float, float, float, float, float]

        # Motion Characteristics
        dominant_motion: MotionPrimitive  # Strongest motion type
        motion_balance: MotionBalance     # BALANCED, CONSTRICTED, AGITATED, OSCILLATORY

        # Children
        syllable_ids: Tuple[str, ...]
    """
```

#### 2.2.4 ProsodicPhraseNode (Level 4)

```python
@dataclass(frozen=True)
class ProsodicPhraseNode:
    """
    Prosodic phrase (intonation unit) containing words.

    Attributes:
        node_id: Unique identifier

        # Prosodic Properties
        phrase_type: PhraseType       # DECLARATIVE, INTERROGATIVE, CONTINUATION
        boundary_tone: BoundaryTone   # L%, H%, LH%, HL%, etc.

        # From P10 Acoustic Parameters
        pitch_range: Tuple[int, int]  # Hz range for this phrase
        speech_rate: float            # Syllables/second
        energy_level: float           # Normalized [0.0-1.0]

        # Pause Structure
        initial_pause_ms: int         # Pause before phrase
        final_pause_ms: int           # Pause after phrase

        # Aggregate Motion
        phrase_vritti: Tuple[float, float, float, float, float]
        motion_trajectory: MotionTrajectory  # ACCELERATING, DECELERATING, STEADY

        # Children
        word_ids: Tuple[str, ...]
    """
```

#### 2.2.5 UtteranceNode (Level 5 - Root)

```python
@dataclass(frozen=True)
class UtteranceNode:
    """
    Root node representing complete utterance with discourse context.

    Attributes:
        node_id: Unique identifier (artifact_hash)

        # From P6/P7
        regime: OperationalRegime     # STABILIZE, REFLECT, INFORM, etc.
        discourse_act: DiscourseAct   # QUESTION, REFLECTION, EXPLANATION, etc.

        # From P10 Acoustic Frame
        acoustic_regime: AcousticRegime  # NEUTRAL, SOFT, FLAT, RESTRAINED
        suppress_emotion: bool
        suppress_emphasis: bool
        suppress_certainty: bool

        # Global Prosodic Envelope
        global_pitch_range: Tuple[int, int]
        global_energy_range: Tuple[float, float]
        total_duration_ms: int

        # Utterance-level Vṛtti (aggregate)
        utterance_vritti: Tuple[float, float, float, float, float]
        overall_motion_character: MotionCharacter

        # Children
        phrase_ids: Tuple[str, ...]
    """
```

### 2.3 Edge Taxonomy

```python
class EdgeType(str, Enum):
    """Types of edges in the Acoustic Generative Graph."""

    # Hierarchical (parent-child)
    CONTAINS = "CONTAINS"              # Parent contains child

    # Sequential (same level)
    PRECEDES = "PRECEDES"              # Temporal sequence

    # Acoustic Dependency
    COARTICULATES = "COARTICULATES"   # Phoneme influences neighbor
    ASSIMILATES = "ASSIMILATES"        # Feature spreading

    # Prosodic
    STRESS_PROJECTS = "STRESS_PROJECTS"    # Stress hierarchy
    TONE_SPREADS = "TONE_SPREADS"          # Tonal coarticulation

    # Motion Flow
    MOTION_CONTINUES = "MOTION_CONTINUES"  # Vṛtti momentum carries
    MOTION_CONTRASTS = "MOTION_CONTRASTS"  # Vṛtti opposition
```

### 2.4 Graph Schema

```python
@dataclass(frozen=True)
class AcousticGenerativeGraph:
    """
    Complete graph structure for acoustic generation.

    Attributes:
        graph_id: Unique identifier (SHA-256 of canonical serialization)

        # Node Collections (immutable)
        utterance: UtteranceNode
        phrases: Tuple[ProsodicPhraseNode, ...]
        words: Tuple[WordNode, ...]
        syllables: Tuple[SyllableNode, ...]
        phonemes: Tuple[PhonemeNode, ...]

        # Edge Collections (immutable)
        hierarchical_edges: Tuple[HierarchicalEdge, ...]
        sequential_edges: Tuple[SequentialEdge, ...]
        acoustic_edges: Tuple[AcousticEdge, ...]
        prosodic_edges: Tuple[ProsodicEdge, ...]
        motion_edges: Tuple[MotionEdge, ...]

        # Graph Metadata
        node_count: int
        edge_count: int
        depth: int  # Always 5 for complete graph

        # Validation
        is_valid: bool
        validation_errors: Tuple[str, ...]
    """
```

---

## 3. Vector Embedding Strategy

### 3.1 Vṛtti Vector Space (5D Foundation)

The core embedding space is derived from the existing **Vṛtti motion primitives**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    VṚTTI VECTOR SPACE (5D)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Dimension 0: INERTIA      [0.0, 1.0]                              │
│               - Sustained energy, continuity                        │
│               - Nasals (m, n, ŋ), long vowels                      │
│                                                                     │
│  Dimension 1: ACTIVATION   [0.0, 1.0]                              │
│               - Sudden release, burst energy                        │
│               - Stops (p, t, k, b, d, g)                           │
│                                                                     │
│  Dimension 2: OSCILLATION  [0.0, 1.0]                              │
│               - Alternating, modulating energy                      │
│               - Liquids (l, r), glides (w, j)                      │
│                                                                     │
│  Dimension 3: TENSION      [0.0, 1.0]                              │
│               - Constrained, turbulent energy                       │
│               - Fricatives (f, s, ʃ), affricates (tʃ, dʒ)         │
│                                                                     │
│  Dimension 4: RELEASE      [0.0, 1.0]                              │
│               - Opening, relaxing energy                            │
│               - Open vowels (a, ɑ), codas                          │
│                                                                     │
│  Constraint: sum(dimensions) = 1.0 (probability simplex)           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Extended Acoustic Embedding (32D)

For richer representation, we extend the 5D Vṛtti space with articulatory features:

```python
@dataclass(frozen=True)
class AcousticEmbedding:
    """
    32-dimensional acoustic embedding vector.

    Components:
        [0-4]:   Vṛtti distribution (5D) - motion primitives
        [5-11]:  Manner features (7D) - one-hot manner of articulation
        [12-20]: Place features (9D) - one-hot place of articulation
        [21-22]: Voicing (2D) - [voiced, voiceless]
        [23-25]: Vowel height (3D) - [high, mid, low]
        [26-28]: Vowel backness (3D) - [front, central, back]
        [29-30]: Vowel rounding (2D) - [rounded, unrounded]
        [31]:    Duration normalized [0.0, 1.0]

    All values are deterministic - no learned weights.
    """
    vector: Tuple[float, ...]  # Length 32

    @staticmethod
    def from_phoneme(phoneme: PhonemeNode) -> 'AcousticEmbedding':
        """Deterministic construction from phoneme features."""
        ...
```

### 3.3 Hierarchical Embedding Composition

```python
def compose_syllable_embedding(
    syllable: SyllableNode,
    phoneme_embeddings: Tuple[AcousticEmbedding, ...]
) -> AcousticEmbedding:
    """
    Compose syllable embedding from phoneme embeddings.

    Algorithm:
        1. Onset contribution: mean(onset_embeddings) * onset_weight
        2. Nucleus contribution: nucleus_embedding * nucleus_weight
        3. Coda contribution: mean(coda_embeddings) * coda_weight

    Weights: onset=0.25, nucleus=0.50, coda=0.25 (fixed, not learned)

    Returns: 32D embedding for syllable
    """
    ...

def compose_word_embedding(
    word: WordNode,
    syllable_embeddings: Tuple[AcousticEmbedding, ...],
    stress_pattern: Tuple[StressLevel, ...]
) -> AcousticEmbedding:
    """
    Compose word embedding from syllable embeddings with stress weighting.

    Algorithm:
        1. Weight stressed syllables higher (PRIMARY=2.0, SECONDARY=1.5, UNSTRESSED=1.0)
        2. Compute weighted mean
        3. Apply word-level normalization

    Returns: 32D embedding for word
    """
    ...
```

### 3.4 Embedding Operations

```python
class EmbeddingOperations:
    """Algebraic operations on acoustic embeddings."""

    @staticmethod
    def distance(e1: AcousticEmbedding, e2: AcousticEmbedding) -> float:
        """
        Compute acoustic distance between embeddings.

        Uses weighted Euclidean distance where:
            - Vṛtti dimensions weighted 2.0x (most important for motion)
            - Manner dimensions weighted 1.5x
            - Other features weighted 1.0x

        Returns: Distance in [0.0, max_distance]
        """
        ...

    @staticmethod
    def interpolate(
        e1: AcousticEmbedding,
        e2: AcousticEmbedding,
        alpha: float  # [0.0, 1.0]
    ) -> AcousticEmbedding:
        """
        Linear interpolation for coarticulation modeling.

        Returns: e1 * (1-alpha) + e2 * alpha
        """
        ...

    @staticmethod
    def contrast(e1: AcousticEmbedding, e2: AcousticEmbedding) -> float:
        """
        Compute acoustic contrast (opposition) between embeddings.

        High contrast = perceptually distinct sounds.
        Used for distinctiveness checking in generation.

        Returns: Contrast score in [0.0, 1.0]
        """
        ...
```

---

## 4. Tokenization Strategy

### 4.1 Acoustic Unit Tokenization

Unlike BPE or WordPiece, our tokenization is **phonetically grounded**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                 ACOUSTIC UNIT TOKENIZATION                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Input Text: "The cat sat on the mat"                              │
│                                                                     │
│  Step 1: Grapheme-to-Phoneme (G2P)                                 │
│          → /ðə kæt sæt ɑn ðə mæt/                                  │
│                                                                     │
│  Step 2: Syllabification                                            │
│          → [ðə] [kæt] [sæt] [ɑn] [ðə] [mæt]                       │
│                                                                     │
│  Step 3: Acoustic Unit Assignment                                   │
│          → AU_001: ð (FRICATIVE, TENSION)                          │
│          → AU_002: ə (VOWEL, RELEASE)                              │
│          → AU_003: k (STOP, ACTIVATION)                            │
│          → AU_004: æ (VOWEL, RELEASE)                              │
│          → AU_005: t (STOP, ACTIVATION)                            │
│          → ...                                                      │
│                                                                     │
│  Step 4: Token Sequence with Vṛtti Tags                            │
│          → [TENSION:ð] [RELEASE:ə] [ACTIVATION:k] [RELEASE:æ] ...  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Token Schema

```python
@dataclass(frozen=True)
class AcousticToken:
    """
    Single token in the acoustic tokenization scheme.

    Attributes:
        token_id: int - Unique token identifier (vocabulary index)
        phoneme: str - IPA representation
        sound_class: SoundClass
        vritti_type: VrittiType
        embedding: AcousticEmbedding

        # Positional Information
        syllable_position: SyllablePosition  # ONSET, NUCLEUS, CODA
        word_position: WordPosition          # INITIAL, MEDIAL, FINAL

        # Duration Hint
        duration_class: DurationClass  # SHORT, MEDIUM, LONG
    """
```

### 4.3 Vocabulary Construction

```python
ACOUSTIC_VOCABULARY = {
    # Stops (ACTIVATION)
    'p': AcousticToken(id=1, phoneme='p', vritti=VrittiType.ACTIVATION, ...),
    'b': AcousticToken(id=2, phoneme='b', vritti=VrittiType.ACTIVATION, ...),
    't': AcousticToken(id=3, phoneme='t', vritti=VrittiType.ACTIVATION, ...),
    'd': AcousticToken(id=4, phoneme='d', vritti=VrittiType.ACTIVATION, ...),
    'k': AcousticToken(id=5, phoneme='k', vritti=VrittiType.ACTIVATION, ...),
    'g': AcousticToken(id=6, phoneme='g', vritti=VrittiType.ACTIVATION, ...),

    # Fricatives (TENSION)
    'f': AcousticToken(id=7, phoneme='f', vritti=VrittiType.TENSION, ...),
    'v': AcousticToken(id=8, phoneme='v', vritti=VrittiType.TENSION, ...),
    'θ': AcousticToken(id=9, phoneme='θ', vritti=VrittiType.TENSION, ...),
    'ð': AcousticToken(id=10, phoneme='ð', vritti=VrittiType.TENSION, ...),
    's': AcousticToken(id=11, phoneme='s', vritti=VrittiType.TENSION, ...),
    'z': AcousticToken(id=12, phoneme='z', vritti=VrittiType.TENSION, ...),
    'ʃ': AcousticToken(id=13, phoneme='ʃ', vritti=VrittiType.TENSION, ...),
    'ʒ': AcousticToken(id=14, phoneme='ʒ', vritti=VrittiType.TENSION, ...),
    'h': AcousticToken(id=15, phoneme='h', vritti=VrittiType.TENSION, ...),

    # Nasals (INERTIA)
    'm': AcousticToken(id=16, phoneme='m', vritti=VrittiType.INERTIA, ...),
    'n': AcousticToken(id=17, phoneme='n', vritti=VrittiType.INERTIA, ...),
    'ŋ': AcousticToken(id=18, phoneme='ŋ', vritti=VrittiType.INERTIA, ...),

    # Liquids (OSCILLATION)
    'l': AcousticToken(id=19, phoneme='l', vritti=VrittiType.OSCILLATION, ...),
    'r': AcousticToken(id=20, phoneme='r', vritti=VrittiType.OSCILLATION, ...),

    # Glides (OSCILLATION)
    'w': AcousticToken(id=21, phoneme='w', vritti=VrittiType.OSCILLATION, ...),
    'j': AcousticToken(id=22, phoneme='j', vritti=VrittiType.OSCILLATION, ...),

    # Vowels (RELEASE) - Front
    'i': AcousticToken(id=23, phoneme='i', vritti=VrittiType.RELEASE, ...),
    'ɪ': AcousticToken(id=24, phoneme='ɪ', vritti=VrittiType.RELEASE, ...),
    'e': AcousticToken(id=25, phoneme='e', vritti=VrittiType.RELEASE, ...),
    'ɛ': AcousticToken(id=26, phoneme='ɛ', vritti=VrittiType.RELEASE, ...),
    'æ': AcousticToken(id=27, phoneme='æ', vritti=VrittiType.RELEASE, ...),

    # Vowels (RELEASE) - Central
    'ə': AcousticToken(id=28, phoneme='ə', vritti=VrittiType.RELEASE, ...),
    'ʌ': AcousticToken(id=29, phoneme='ʌ', vritti=VrittiType.RELEASE, ...),

    # Vowels (RELEASE) - Back
    'u': AcousticToken(id=30, phoneme='u', vritti=VrittiType.RELEASE, ...),
    'ʊ': AcousticToken(id=31, phoneme='ʊ', vritti=VrittiType.RELEASE, ...),
    'o': AcousticToken(id=32, phoneme='o', vritti=VrittiType.RELEASE, ...),
    'ɔ': AcousticToken(id=33, phoneme='ɔ', vritti=VrittiType.RELEASE, ...),
    'ɑ': AcousticToken(id=34, phoneme='ɑ', vritti=VrittiType.RELEASE, ...),

    # Affricates (TENSION)
    'tʃ': AcousticToken(id=35, phoneme='tʃ', vritti=VrittiType.TENSION, ...),
    'dʒ': AcousticToken(id=36, phoneme='dʒ', vritti=VrittiType.TENSION, ...),

    # Special Tokens
    '[SIL]': AcousticToken(id=37, phoneme='[SIL]', vritti=VrittiType.INERTIA, ...),  # Silence
    '[BRK]': AcousticToken(id=38, phoneme='[BRK]', vritti=VrittiType.RELEASE, ...),  # Phrase break
    '[PAD]': AcousticToken(id=39, phoneme='[PAD]', vritti=None, ...),                 # Padding
}

VOCABULARY_SIZE = 40  # Fixed, not learned
```

---

## 5. Graph-Based Generation Algorithm

### 5.1 Message Passing Neural Network (MPNN) Architecture

Instead of transformers, we use **graph message passing**:

```
┌─────────────────────────────────────────────────────────────────────┐
│              MESSAGE PASSING GENERATION NETWORK                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Phase 1: TOP-DOWN PROPAGATION (Meaning → Sound)                   │
│           ┌──────────────────┐                                      │
│           │  Utterance Node  │ ← Regime, Discourse Act             │
│           └────────┬─────────┘                                      │
│                    │ M_down                                         │
│           ┌────────┴─────────┐                                      │
│           │  Phrase Nodes    │ ← Pitch range, energy               │
│           └────────┬─────────┘                                      │
│                    │ M_down                                         │
│           ┌────────┴─────────┐                                      │
│           │   Word Nodes     │ ← Stress, focus                     │
│           └────────┬─────────┘                                      │
│                    │ M_down                                         │
│           ┌────────┴─────────┐                                      │
│           │ Syllable Nodes   │ ← Vṛtti distribution                │
│           └────────┬─────────┘                                      │
│                    │ M_down                                         │
│           ┌────────┴─────────┐                                      │
│           │  Phoneme Nodes   │ ← Acoustic embedding                │
│           └──────────────────┘                                      │
│                                                                     │
│  Phase 2: BOTTOM-UP AGGREGATION (Sound → Validation)               │
│           Phoneme → Syllable → Word → Phrase → Utterance           │
│           Aggregate Vṛtti vectors, validate constraints            │
│                                                                     │
│  Phase 3: LATERAL PROPAGATION (Coarticulation)                     │
│           Phoneme ↔ Phoneme (sequential neighbors)                 │
│           Apply coarticulation rules, smooth transitions           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Message Functions

```python
class AcousticMessagePassing:
    """
    Graph neural network layer for acoustic generation.
    No attention mechanism - uses deterministic message functions.
    """

    def message_down(
        self,
        parent: Node,
        child: Node,
        edge: Edge
    ) -> Message:
        """
        Downward message from parent to child.
        Propagates constraints and context.

        Algorithm:
            1. Extract parent's constraint envelope
            2. Narrow constraints for child's position
            3. Compute child's acoustic target

        No learnable parameters - pure constraint propagation.
        """
        if isinstance(parent, UtteranceNode):
            # Propagate regime constraints to phrases
            return Message(
                pitch_range=narrow_pitch(parent.global_pitch_range, child.phrase_type),
                energy_range=narrow_energy(parent.global_energy_range, child.phrase_type),
                suppress_flags=(parent.suppress_emotion, parent.suppress_emphasis),
            )
        elif isinstance(parent, ProsodicPhraseNode):
            # Propagate prosodic context to words
            return Message(
                local_pitch=compute_word_pitch(parent, child.word_position),
                stress_weight=get_stress_weight(child.focus),
            )
        # ... etc

    def message_up(
        self,
        child: Node,
        parent: Node,
        edge: Edge
    ) -> Message:
        """
        Upward message from child to parent.
        Aggregates acoustic properties for validation.

        Algorithm:
            1. Collect child's realized acoustic values
            2. Aggregate according to composition rules
            3. Return summary for parent validation
        """
        ...

    def message_lateral(
        self,
        node: PhonemeNode,
        neighbor: PhonemeNode,
        edge: Edge
    ) -> Message:
        """
        Lateral message between sequential phonemes.
        Implements coarticulation.

        Algorithm:
            1. Compute coarticulation strength based on features
            2. Interpolate embeddings at boundary
            3. Adjust duration for transition
        """
        coart_strength = compute_coarticulation_strength(node, neighbor)

        return Message(
            adjusted_embedding=interpolate(
                node.embedding,
                neighbor.embedding,
                alpha=coart_strength * COART_WINDOW
            ),
            transition_duration=compute_transition(node, neighbor),
        )
```

### 5.3 Generation Pipeline

```python
class GraphGenerator:
    """
    Main generation pipeline using graph operations.
    """

    def generate(
        self,
        semantic_frame: SemanticFrame,      # From P8
        discourse_envelope: DiscourseEnvelope,  # From P7
        regime_envelope: RegimeEnvelope,    # From P6
        lexical_frame: LexicalFrame,        # From P9
        acoustic_frame: AcousticParameterFrame,  # From P10
    ) -> AcousticGenerativeGraph:
        """
        Generate complete acoustic graph from upstream phases.

        Pipeline:
            1. SCAFFOLD: Build graph skeleton from lexical selections
            2. PARAMETERIZE: Apply acoustic parameters top-down
            3. EXPAND: Generate phoneme-level detail
            4. COARTICULATE: Apply lateral smoothing
            5. VALIDATE: Check all acoustic constraints

        Returns: Complete AcousticGenerativeGraph
        """
        # Step 1: Build skeleton
        skeleton = self._build_skeleton(lexical_frame)

        # Step 2: Apply acoustic parameters
        parameterized = self._propagate_acoustic_params(
            skeleton, acoustic_frame, regime_envelope
        )

        # Step 3: Expand to phoneme level
        expanded = self._expand_phonemes(parameterized)

        # Step 4: Coarticulation pass
        smoothed = self._apply_coarticulation(expanded)

        # Step 5: Validation
        validated = self._validate_constraints(smoothed, acoustic_frame)

        return validated

    def _build_skeleton(self, lexical_frame: LexicalFrame) -> Graph:
        """Build hierarchical graph skeleton from words."""
        graph = Graph()

        # Create utterance root
        utterance = UtteranceNode(...)
        graph.add_node(utterance)

        # For each word in lexical frame
        for slot, word in lexical_frame.selections.items():
            # G2P conversion
            phonemes = grapheme_to_phoneme(word)

            # Syllabification
            syllables = syllabify(phonemes)

            # Create nodes
            word_node = WordNode(surface_form=word, ...)
            graph.add_node(word_node)
            graph.add_edge(utterance, word_node, EdgeType.CONTAINS)

            for syllable in syllables:
                syl_node = SyllableNode(...)
                graph.add_node(syl_node)
                graph.add_edge(word_node, syl_node, EdgeType.CONTAINS)

                for phoneme in syllable:
                    phn_node = PhonemeNode(phoneme=phoneme, ...)
                    graph.add_node(phn_node)
                    graph.add_edge(syl_node, phn_node, EdgeType.CONTAINS)

        # Add sequential edges
        self._add_sequential_edges(graph)

        return graph
```

---

## 6. Graph Rewriting Rules

### 6.1 Deterministic Transformation Rules

Instead of probabilistic decoding, we use **rule-based graph rewriting**:

```python
class GraphRewriteRule:
    """Base class for deterministic graph transformations."""

    @abstractmethod
    def matches(self, subgraph: Graph) -> bool:
        """Check if rule applies to subgraph."""
        ...

    @abstractmethod
    def apply(self, subgraph: Graph) -> Graph:
        """Apply transformation."""
        ...

class CoarticuationRule(GraphRewriteRule):
    """
    Apply coarticulation between adjacent phonemes.

    Pattern: PhonemeNode --PRECEDES--> PhonemeNode

    Condition: Adjacent phonemes share articulatory features

    Action: Insert COARTICULATES edge, adjust embeddings
    """

    def matches(self, subgraph: Graph) -> bool:
        # Check for adjacent phoneme pattern
        if len(subgraph.nodes) != 2:
            return False
        n1, n2 = subgraph.nodes
        if not (isinstance(n1, PhonemeNode) and isinstance(n2, PhonemeNode)):
            return False
        if not subgraph.has_edge(n1, n2, EdgeType.PRECEDES):
            return False
        return True

    def apply(self, subgraph: Graph) -> Graph:
        n1, n2 = subgraph.nodes

        # Compute coarticulation
        coart_type = determine_coarticulation_type(n1, n2)
        coart_strength = compute_coarticulation_strength(n1, n2)

        # Create coarticulation edge
        new_edge = AcousticEdge(
            source=n1.node_id,
            target=n2.node_id,
            edge_type=EdgeType.COARTICULATES,
            coart_type=coart_type,
            strength=coart_strength,
        )

        # Adjust embeddings
        n1_adjusted = PhonemeNode(
            **{**n1.__dict__, 'embedding': adjust_for_following(n1.embedding, n2)}
        )
        n2_adjusted = PhonemeNode(
            **{**n2.__dict__, 'embedding': adjust_for_preceding(n2.embedding, n1)}
        )

        return Graph(nodes=[n1_adjusted, n2_adjusted], edges=[new_edge])

class AssimilationRule(GraphRewriteRule):
    """
    Apply phonological assimilation.

    Example: /n/ → [ŋ] before velars

    Pattern: NasalNode --PRECEDES--> VelarNode

    Action: Change nasal place to velar
    """

    def matches(self, subgraph: Graph) -> bool:
        n1, n2 = subgraph.nodes
        return (
            n1.manner == MannerOfArticulation.NASAL and
            n2.place == PlaceOfArticulation.VELAR
        )

    def apply(self, subgraph: Graph) -> Graph:
        n1, n2 = subgraph.nodes

        # Change nasal to velar
        n1_assimilated = PhonemeNode(
            **{**n1.__dict__,
               'phoneme': 'ŋ',
               'place': PlaceOfArticulation.VELAR}
        )

        return Graph(nodes=[n1_assimilated, n2], edges=subgraph.edges)

class StressProjectionRule(GraphRewriteRule):
    """
    Project word stress to syllable level.

    Pattern: WordNode --CONTAINS--> SyllableNode*

    Action: Assign stress levels based on word pattern
    """
    ...

# Rule Registry
REWRITE_RULES = [
    CoarticuationRule(),
    AssimilationRule(),
    StressProjectionRule(),
    PhraseBreakInsertionRule(),
    PitchContourRule(),
    DurationAdjustmentRule(),
]
```

### 6.2 Rule Application Order

```python
def apply_rewrite_rules(graph: AcousticGenerativeGraph) -> AcousticGenerativeGraph:
    """
    Apply all rewrite rules in canonical order.

    Order is critical - rules are applied in phases:
        Phase 1: Structural rules (stress projection, phrase breaks)
        Phase 2: Phonological rules (assimilation, deletion)
        Phase 3: Acoustic rules (coarticulation, duration)
        Phase 4: Prosodic rules (pitch contours, energy)

    Each phase runs to fixed point before next phase.
    """
    current = graph

    for phase_rules in [STRUCTURAL_RULES, PHONOLOGICAL_RULES,
                        ACOUSTIC_RULES, PROSODIC_RULES]:
        changed = True
        while changed:
            changed = False
            for rule in phase_rules:
                for subgraph in enumerate_subgraphs(current, rule.pattern_size):
                    if rule.matches(subgraph):
                        current = apply_rule(current, subgraph, rule)
                        changed = True

    return current
```

---

## 7. Acoustic Constraint Validation

### 7.1 Constraint System

```python
class AcousticConstraint:
    """Base class for acoustic constraints."""

    @abstractmethod
    def check(self, graph: AcousticGenerativeGraph) -> ConstraintResult:
        """Check if constraint is satisfied."""
        ...

class PitchRangeConstraint(AcousticConstraint):
    """
    Verify all pitch values within P10/P13 bounds.
    """

    def check(self, graph: AcousticGenerativeGraph) -> ConstraintResult:
        min_pitch, max_pitch = graph.utterance.global_pitch_range

        for phrase in graph.phrases:
            phrase_min, phrase_max = phrase.pitch_range
            if phrase_min < min_pitch or phrase_max > max_pitch:
                return ConstraintResult(
                    satisfied=False,
                    violation=f"Phrase pitch {phrase.pitch_range} exceeds bounds {(min_pitch, max_pitch)}"
                )

        return ConstraintResult(satisfied=True)

class EnergyConstraint(AcousticConstraint):
    """
    Verify energy levels within bounds and regime-appropriate.
    """
    ...

class VrittiBalanceConstraint(AcousticConstraint):
    """
    Verify Vṛtti distribution is normalized and balanced.
    """

    def check(self, graph: AcousticGenerativeGraph) -> ConstraintResult:
        for syllable in graph.syllables:
            total = sum(syllable.vritti_distribution)
            if abs(total - 1.0) > 0.001:
                return ConstraintResult(
                    satisfied=False,
                    violation=f"Vṛtti distribution not normalized: sum={total}"
                )

        return ConstraintResult(satisfied=True)

class SuppressionConstraint(AcousticConstraint):
    """
    Verify suppression flags are respected.

    If suppress_emotion=True:
        - No AGITATED motion balance
        - Energy variance < 0.1

    If suppress_emphasis=True:
        - No ACTIVATION spikes
        - max_stressed_tokens=0

    If suppress_certainty=True:
        - No sustained INERTIA dominance
    """
    ...

# Constraint Registry
ACOUSTIC_CONSTRAINTS = [
    PitchRangeConstraint(),
    EnergyConstraint(),
    VrittiBalanceConstraint(),
    SuppressionConstraint(),
    CoarticulationSmoothness(),
    DurationBoundsConstraint(),
    PhraseBreakConstraint(),
]
```

### 7.2 Validation Pipeline

```python
def validate_graph(graph: AcousticGenerativeGraph) -> ValidationResult:
    """
    Run all acoustic constraints.

    Returns:
        ValidationResult with:
            - is_valid: bool
            - violations: List[ConstraintViolation]
            - repair_suggestions: List[RepairSuggestion]  # For soft constraints
    """
    violations = []

    for constraint in ACOUSTIC_CONSTRAINTS:
        result = constraint.check(graph)
        if not result.satisfied:
            violations.append(ConstraintViolation(
                constraint=constraint.__class__.__name__,
                message=result.violation,
                severity=constraint.severity,
            ))

    is_valid = all(v.severity != Severity.HARD for v in violations)

    return ValidationResult(
        is_valid=is_valid,
        violations=tuple(violations),
    )
```

---

## 8. Implementation Roadmap

### 8.1 Phase 1: Foundation (Weeks 1-2)

```
[ ] Define all Node dataclasses (PhonemeNode, SyllableNode, etc.)
[ ] Define Edge types and schemas
[ ] Implement AcousticGenerativeGraph container
[ ] Build 32D AcousticEmbedding with deterministic construction
[ ] Create acoustic vocabulary (40 tokens)
```

### 8.2 Phase 2: Graph Construction (Weeks 3-4)

```
[ ] Implement G2P conversion (use existing library, e.g., g2p_en)
[ ] Implement syllabification algorithm
[ ] Build skeleton construction from lexical frame
[ ] Add hierarchical edge construction
[ ] Add sequential edge construction
```

### 8.3 Phase 3: Message Passing (Weeks 5-6)

```
[ ] Implement top-down message propagation
[ ] Implement bottom-up aggregation
[ ] Implement lateral (coarticulation) messages
[ ] Build MPNN layer without attention
[ ] Integration with P10 acoustic parameters
```

### 8.4 Phase 4: Graph Rewriting (Weeks 7-8)

```
[ ] Implement rule pattern matching
[ ] Implement coarticulation rules
[ ] Implement assimilation rules
[ ] Implement stress projection
[ ] Build rule application engine
```

### 8.5 Phase 5: Validation & Integration (Weeks 9-10)

```
[ ] Implement all constraint checkers
[ ] Build validation pipeline
[ ] Integration testing with full pipeline
[ ] Performance optimization
[ ] Documentation
```

---

## 9. File Structure

```
symbolu/generative/
├── __init__.py
├── graph/
│   ├── __init__.py
│   ├── nodes.py              # Node dataclasses
│   ├── edges.py              # Edge types and schemas
│   ├── acoustic_graph.py     # AcousticGenerativeGraph
│   └── graph_ops.py          # Graph operations
├── embeddings/
│   ├── __init__.py
│   ├── acoustic_embedding.py # 32D embedding
│   ├── vritti_space.py       # 5D Vṛtti operations
│   └── composition.py        # Hierarchical composition
├── tokenization/
│   ├── __init__.py
│   ├── vocabulary.py         # Acoustic vocabulary
│   ├── g2p.py                # Grapheme-to-phoneme
│   └── syllabifier.py        # Syllabification
├── generation/
│   ├── __init__.py
│   ├── message_passing.py    # MPNN layer
│   ├── generator.py          # Main generation pipeline
│   └── skeleton.py           # Graph skeleton building
├── rewriting/
│   ├── __init__.py
│   ├── rules.py              # Rewrite rule base class
│   ├── coarticulation.py     # Coarticulation rules
│   ├── assimilation.py       # Phonological rules
│   └── prosodic.py           # Prosodic rules
├── validation/
│   ├── __init__.py
│   ├── constraints.py        # Constraint classes
│   └── validator.py          # Validation pipeline
└── tests/
    ├── test_graph.py
    ├── test_embeddings.py
    ├── test_generation.py
    └── test_validation.py
```

---

## 10. Summary

This specification defines a **graph-based generative architecture** that:

1. **Rejects transformers** in favor of explicit graph structure and message passing
2. **Uses deterministic embeddings** (32D) derived from articulatory features, not learned
3. **Tokenizes phonetically** using 40 acoustic units, not statistical subwords
4. **Generates via graph operations** - skeleton building, message passing, rule rewriting
5. **Validates acoustically** against P10/P13 constraints
6. **Preserves the invariant**: Sound must obey meaning. Meaning must never obey sound.

The model leverages the existing Vṛtti vector space and acoustic parameter infrastructure from Phase-10, extending it into a full generative framework without introducing probabilistic sampling or attention mechanisms.

---

**Document Version:** 1.0.0
**Last Updated:** 2025-12-16
**Author:** Symbol-U Architecture Team
