# Symbolic AI Emotional Reasoning: Gap Analysis and Design Directions

**Document Version**: 1.0.0
**Date**: January 2026
**Status**: Design Proposal
**Purpose**: Evaluate missing emotional/affective symbolic AI components in Phase-Quad

---

## Executive Summary

Phase-Quad has several components that touch emotional/affective processing (CSR, DHA, LAM, Kosha, Vritti), but these are primarily **delivery modulation** and **state tracking** systems, not true **emotional reasoning** systems. This document analyzes what exists, what's missing, and proposes concrete extensions for symbolic emotional AI.

### Current vs Target State

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    EMOTIONAL AI CAPABILITY MATRIX                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  LEVEL 1: EMOTIONAL DELIVERY ✅ (Current)                                       │
│  ═══════════════════════════════════════                                        │
│  "Adjust HOW we say things based on context"                                    │
│  • DHA: Tone selection (sweet/jolt/metaphor)                                    │
│  • Expression Modulation: Detail/practical/reflective biases                    │
│  • CSR: Entropy dampening for coherent output                                   │
│                                                                                 │
│  LEVEL 2: EMOTIONAL STATE TRACKING ✅ (Current)                                 │
│  ═══════════════════════════════════════════                                    │
│  "Track emotional trajectory over time"                                         │
│  • LAM: Long-arc emotional trajectory                                           │
│  • Kosha: Manomaya (mental/emotional) layer activation                          │
│  • Vritti: Cognitive state including emotional modes                            │
│                                                                                 │
│  LEVEL 3: EMOTIONAL RECOGNITION ⚠️ (Partial)                                    │
│  ════════════════════════════════════════════                                   │
│  "Identify emotions in input"                                                   │
│  • Implicit via Bhava activation patterns                                       │
│  • Missing: Explicit emotion classification                                     │
│  • Missing: Fine-grained emotion taxonomy                                       │
│                                                                                 │
│  LEVEL 4: EMOTIONAL REASONING ❌ (Missing)                                      │
│  ══════════════════════════════════════════                                     │
│  "Reason ABOUT and WITH emotions"                                               │
│  • Missing: Emotion-logic interaction rules                                     │
│  • Missing: Emotional coherence validation                                      │
│  • Missing: Affective inference chains                                          │
│                                                                                 │
│  LEVEL 5: EMOTIONAL INTELLIGENCE ❌ (Missing)                                   │
│  ══════════════════════════════════════════════                                 │
│  "Understand, empathize, and respond appropriately"                             │
│  • Missing: Theory of Mind for emotions                                         │
│  • Missing: Empathy modeling                                                    │
│  • Missing: Emotional memory continuity                                         │
│  • Missing: Cross-cultural emotional mapping                                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: What Currently Exists

### 1.1 CSR (Constraint-Structure-Resonance)

**Location**: `symbolu/inference/csr_inference.py`

**What it does**:
- **Entropy Sink**: Absorbs high-entropy energy from hidden states
- **Synthesis Gate**: Controls information flow based on coherence
- **Safety Layer**: Monitors generation entropy, applies interventions

**Emotional relevance**:
```
CSR operates at Layer 7 (CSR Alignment) in SRK
→ Phoneme/semantic extraction point
→ Indirectly affects emotional tone through coherence control
→ NOT explicit emotional processing
```

**Limitation**: CSR manages *coherence*, not *emotion*. It prevents divergent output but doesn't understand emotional content.

---

### 1.2 DHA (Delivery Harmonization Algorithm)

**Location**: `symbolu/mechanical/dha/dha_engine.py`

**What it does**:
- **Tone Selection**: sweet / jolt / metaphor
- **Intensity Scalar**: Based on coherence, motion, entropy
- **Restraint Scalar**: Based on risk and escalation

**Emotional relevance**:
```python
# DHA computes delivery modulation D = T × I × R
# where T = tone, I = intensity, R = restraint

# Tone logits:
l_sweet = k1 × sattva - k2 × tamas      # Gentle, harmonious
l_jolt  = k3 × rajas + k4 × contradiction  # Energetic, challenging
l_meta  = k5 × entropy + k6 × rajas      # Abstract, philosophical
```

**Limitation**: DHA modulates *delivery style*, not *emotional understanding*. It's a presentation layer, not a reasoning layer.

---

### 1.3 LAM (Long-Arc Mapper)

**Location**: `symbolu/mechanical/lam/lam_engine.py`

**What it does**:
- **Trajectory Tracking**: Rising/falling/stable emotional arcs
- **Tension Detection**: System in tension vs recovery
- **Pattern Recognition**: Universal emotional patterns across time

**Emotional relevance**:
```
LAM answers:
- "Where is the user coming from emotionally?"
- "Where is the user going emotionally?"
- "Is the trajectory rising, falling, stable?"
- "Is the system in tension or recovery?"
```

**Limitation**: LAM tracks *emotional trajectory* but doesn't *reason about* emotions. It's descriptive, not inferential.

---

### 1.4 Kosha System (Manomaya Layer)

**Location**: `symbolu/sovereign/reasoning_kernel.py` (Kosha dimensions [12:17])

**What it does**:
- **Manomaya (Mental/Emotional)**: Third Kosha layer
- **Processing Depth**: Tracks when emotional processing is active

**Emotional relevance**:
```
Koshas [12:17]:
  [12] ANNAMAYA   - Physical (surface tokens)
  [13] PRANAMAYA  - Vital (energy/flow)
  [14] MANOMAYA   - Mental/Emotional ← EMOTIONAL LAYER
  [15] VIJNANAMAYA - Intellectual (patterns)
  [16] ANANDAMAYA - Blissful (unity)

When MANOMAYA > 0.6:
  → Model is processing at emotional depth
  → But no explicit emotional reasoning rules
```

**Limitation**: Kosha indicates *depth of processing* but not *emotional logic*. High Manomaya means "emotional content present" not "emotional reasoning active."

---

### 1.5 Vritti System (Emotional Modes)

**Location**: `symbolu/sovereign/reasoning_kernel.py` (Vritti dimensions [17:22])

**What it does**:
- **5 Cognitive States**: PRAMANA, VIPARYAYA, VIKALPA, NIDRA, SMRITI
- **Epistemic Validation**: Checks cognitive reliability

**Emotional relevance**:
```
Vrittis [17:22]:
  [17] PRAMANA   - Valid Cognition (factual)
  [18] VIPARYAYA - Misconception (error)
  [19] VIKALPA  - Imagination/Fantasy ← EMOTIONAL CREATIVITY
  [20] NIDRA    - Void/Dormancy
  [21] SMRITI   - Memory/Recall ← EMOTIONAL MEMORY

VIKALPA enables creative/emotional expression
SMRITI enables emotional memory recall
But no explicit emotional reasoning rules
```

**Limitation**: Vrittis track *cognitive mode* (including imaginative), but don't implement *emotional inference*.

---

## Part 2: What's Missing

### Gap 1: Rasa Theory Implementation

**The Gap**: No explicit representation of the 9 Rasas (aesthetic emotions from Sanskrit tradition).

**Why it matters**: Rasa provides a complete, coherent taxonomy of emotional states that maps well to symbolic reasoning.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    THE 9 RASAS (Aesthetic Emotions)                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  1. SHRINGARA (Love/Beauty)     - Romantic, aesthetic appreciation              │
│  2. HASYA (Comedy/Mirth)        - Humor, joy, laughter                          │
│  3. KARUNA (Compassion/Pathos)  - Sorrow, empathy, grief                        │
│  4. RAUDRA (Fury/Anger)         - Rage, indignation, frustration                │
│  5. VEERA (Heroic/Valor)        - Courage, determination, confidence            │
│  6. BHAYANAKA (Terror/Fear)     - Anxiety, dread, worry                         │
│  7. BIBHATSA (Disgust/Aversion) - Revulsion, rejection, distaste               │
│  8. ADBHUTA (Wonder/Amazement)  - Awe, curiosity, surprise                      │
│  9. SHANTA (Peace/Serenity)     - Calm, acceptance, equanimity                  │
│                                                                                 │
│  CURRENT STATE:                                                                 │
│    DHA has: sweet / jolt / metaphor (3 tones)                                   │
│    Rasas provide: 9 distinct emotional dimensions                               │
│                                                                                 │
│  MISSING: Rasa detection, Rasa-based reasoning, Rasa transitions               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### Gap 2: Emotion Recognition Module

**The Gap**: No explicit emotion classification from input text.

**Current state**: Emotions are implicitly captured in Bhava/Kosha activations, but not explicitly labeled.

**What's needed**:
```python
# MISSING: Explicit emotion recognition
class EmotionRecognizer:
    def recognize(self, text: str, context: SovereignState) -> EmotionState:
        """
        Explicit emotion detection, not just implicit Bhava activation.

        Returns:
            EmotionState with:
            - primary_rasa: Dominant emotion (1 of 9)
            - rasa_distribution: [9] probability over all Rasas
            - intensity: 0.0 - 1.0
            - valence: -1.0 (negative) to +1.0 (positive)
            - arousal: 0.0 (calm) to 1.0 (excited)
            - confidence: Recognition confidence
        """
        pass
```

---

### Gap 3: Emotional Reasoning Rules

**The Gap**: No explicit rules for how emotions interact with logic.

**What's needed**:
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    EMOTIONAL REASONING RULES (MISSING)                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  EMOTION-LOGIC INTERACTION RULES:                                               │
│  ════════════════════════════════                                               │
│                                                                                 │
│  Rule 1: Emotional Priming                                                      │
│    IF user_emotion = BHAYANAKA (fear)                                           │
│    THEN boost_reassurance_weight += 0.3                                         │
│    AND reduce_speculation_weight -= 0.2                                         │
│                                                                                 │
│  Rule 2: Emotional Coherence                                                    │
│    IF response_emotion ≠ appropriate_for(user_emotion)                          │
│    THEN flag_emotional_mismatch = True                                          │
│    Example: User sad → Response shouldn't be dismissively cheerful              │
│                                                                                 │
│  Rule 3: Emotional Escalation Prevention                                        │
│    IF user_emotion = RAUDRA (anger) AND intensity > 0.7                         │
│    THEN response_emotion should NOT = RAUDRA                                    │
│    Instead: SHANTA (peace) or KARUNA (compassion)                               │
│                                                                                 │
│  Rule 4: Empathetic Mirroring                                                   │
│    IF user_emotion = KARUNA (grief) AND context = personal_loss                 │
│    THEN response should acknowledge_emotion BEFORE provide_information          │
│                                                                                 │
│  Rule 5: Emotional Transition Logic                                             │
│    Valid transitions: BHAYANAKA → SHANTA (fear → peace via reassurance)         │
│    Invalid transitions: KARUNA → HASYA (grief → comedy without bridge)          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### Gap 4: Theory of Mind for Emotions (ToM-E)

**The Gap**: No model of what the user is *feeling* vs what they're *saying*.

**What's needed**:
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    THEORY OF MIND FOR EMOTIONS (ToM-E)                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  CURRENT: Model responds to surface text                                        │
│  NEEDED:  Model infers emotional state behind text                              │
│                                                                                 │
│  Example:                                                                       │
│    User: "I'm fine, everything is great."                                       │
│    Context: User just lost job, previous messages were anxious                  │
│                                                                                 │
│    Surface emotion: HASYA/SHANTA (stated positive)                              │
│    Inferred emotion: BHAYANAKA/KARUNA (actual fear/grief)                       │
│                                                                                 │
│  ToM-E COMPONENTS:                                                              │
│  ═════════════════                                                              │
│                                                                                 │
│  1. Stated Emotion: What user explicitly expresses                              │
│  2. Implied Emotion: What linguistic cues suggest                               │
│  3. Contextual Emotion: What situation warrants                                 │
│  4. Historical Emotion: What patterns show over time (LAM)                      │
│  5. Inferred True Emotion: Weighted combination                                 │
│                                                                                 │
│  inferred = w1*stated + w2*implied + w3*contextual + w4*historical              │
│                                                                                 │
│  DISCREPANCY FLAG:                                                              │
│    IF |stated - inferred| > threshold                                           │
│    THEN user_may_be_masking = True                                              │
│    → Respond to inferred, not stated                                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### Gap 5: Emotional Memory Continuity

**The Gap**: No persistent emotional memory across sessions.

**Current state**:
- LAM tracks within-session trajectory
- OPB can lock emotional dimensions
- But no cross-session emotional memory

**What's needed**:
```python
# MISSING: Emotional memory that persists
class EmotionalMemory:
    """
    Like AutobiographicalMemory but for emotional patterns.
    """
    def __init__(self, agent_id: str):
        self.agent_id = agent_id

        # User emotional profiles
        self.user_profiles = {}  # user_id → EmotionalProfile

        # Salient emotional events
        self.emotional_events = []  # Significant emotional interactions

        # Emotional patterns
        self.trigger_patterns = {}  # topic → typical emotional response

    def get_user_emotional_context(self, user_id: str) -> EmotionalContext:
        """
        Retrieve emotional context for a user across sessions.

        Returns:
            - typical_rasa_distribution: User's baseline emotional state
            - known_triggers: Topics that evoke strong emotions
            - emotional_history: Trajectory of past interactions
            - rapport_emotional_level: Emotional connection strength
        """
        pass
```

---

### Gap 6: Affective Inference Chains

**The Gap**: No mechanism to chain emotional inferences.

**What's needed**:
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    AFFECTIVE INFERENCE CHAINS                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  LOGICAL INFERENCE (Current - via IMR templates):                               │
│    Premise: A → B                                                               │
│    Premise: A                                                                   │
│    Conclusion: B                                                                │
│                                                                                 │
│  AFFECTIVE INFERENCE (Missing):                                                 │
│    Premise: User lost job (event)                                               │
│    Rule: Job loss → BHAYANAKA (fear) + KARUNA (grief)                           │
│    Rule: BHAYANAKA high → need for SHANTA (reassurance)                         │
│    Conclusion: Response should prioritize emotional support                     │
│                                                                                 │
│  MIXED INFERENCE (Missing):                                                     │
│    Premise: User asks "Should I take the new job offer?"                        │
│    Logical: Analyze pros/cons, salary, growth                                   │
│    Affective: User showing BHAYANAKA (fear of change)                           │
│    Combined: Address fear first, then provide analysis                          │
│                                                                                 │
│  IMPLEMENTATION: Extend IMR templates                                           │
│  ═══════════════════════════════════════                                        │
│                                                                                 │
│  Current IMR templates: DEDUCTION, INDUCTION, ABDUCTION, ANALOGY, SYNTHESIS     │
│                                                                                 │
│  New templates needed:                                                          │
│    EMOTIONAL_INFERENCE: Event → Emotional State                                 │
│    EMPATHETIC_RESPONSE: User_Emotion → Appropriate_Response                     │
│    AFFECTIVE_TRANSITION: Current_Emotion → Target_Emotion → Path                │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### Gap 7: Emotional Coherence Validator

**The Gap**: Vritti Gate validates factual coherence, but not emotional coherence.

**What's needed**:
```python
# MISSING: Emotional coherence validation
class EmotionalCoherenceValidator:
    """
    Like Vritti Gate but for emotional appropriateness.
    """

    def validate_emotional_coherence(
        self,
        user_emotion: RasaState,
        response_emotion: RasaState,
        context: ConversationContext,
    ) -> ValidationResult:
        """
        Check if response emotion is appropriate for user emotion.

        Rules:
        - Don't meet anger with anger (unless appropriate context)
        - Don't dismiss grief with forced cheerfulness
        - Match intensity appropriately
        - Respect cultural emotional norms

        Returns:
            ValidationResult with:
            - is_coherent: bool
            - issues: List of emotional mismatches
            - suggestions: How to improve emotional coherence
        """
        pass

    def validate_emotional_transition(
        self,
        from_emotion: RasaState,
        to_emotion: RasaState,
    ) -> bool:
        """
        Check if emotional transition is valid.

        Invalid: KARUNA (grief) → HASYA (comedy) without bridge
        Valid: KARUNA → SHANTA (grief → peace via acceptance)
        """
        pass
```

---

## Part 3: Proposed Architecture

### Rasa State Integration with Sovereign State

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    EXTENDED SOVEREIGN STATE (40D)                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  CURRENT 32D:                                                                   │
│  ════════════                                                                   │
│  [0:12]   Bhavas (12 ontological aspects)                                       │
│  [12:17]  Koshas (5 depth layers)                                               │
│  [17:22]  Vrittis (5 cognitive states)                                          │
│  [22:28]  Gunas (6 dynamic qualities)                                           │
│  [28:32]  Reserved (toroidal feedback)                                          │
│                                                                                 │
│  PROPOSED 40D (Add 8 for Rasa):                                                 │
│  ══════════════════════════════                                                 │
│  [0:12]   Bhavas (12 ontological aspects)                                       │
│  [12:17]  Koshas (5 depth layers)                                               │
│  [17:22]  Vrittis (5 cognitive states)                                          │
│  [22:28]  Gunas (6 dynamic qualities)                                           │
│  [28:32]  Reserved (toroidal feedback)                                          │
│  [32:41]  Rasas (9 emotional states) ← NEW                                      │
│                                                                                 │
│  RASA DIMENSIONS [32:41]:                                                       │
│  ═══════════════════════                                                        │
│  [32] SHRINGARA (Love)     - Romantic, aesthetic                                │
│  [33] HASYA (Mirth)        - Humor, joy                                         │
│  [34] KARUNA (Compassion)  - Sorrow, empathy                                    │
│  [35] RAUDRA (Fury)        - Anger, frustration                                 │
│  [36] VEERA (Valor)        - Courage, confidence                                │
│  [37] BHAYANAKA (Terror)   - Fear, anxiety                                      │
│  [38] BIBHATSA (Disgust)   - Aversion, rejection                                │
│  [39] ADBHUTA (Wonder)     - Awe, curiosity                                     │
│  [40] SHANTA (Peace)       - Calm, equanimity                                   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Emotional Reasoning Kernel (ERK)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    EMOTIONAL REASONING KERNEL (ERK)                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Parallel to SRK, operates on Rasa dimensions                                   │
│                                                                                 │
│  LAYER 4: EMOTIONAL GROUNDING (Parallel to DNA Bridge)                          │
│  ══════════════════════════════════════════════════════                         │
│  • Detect input emotion from text                                               │
│  • Ground in Rasa space                                                         │
│  • Set initial emotional context                                                │
│                                                                                 │
│  LAYER 7: EMOTIONAL ALIGNMENT (Parallel to CSR)                                 │
│  ═════════════════════════════════════════════════                              │
│  • Align response emotion with appropriate Rasa                                 │
│  • Apply emotional transition rules                                             │
│  • Modulate based on context                                                    │
│                                                                                 │
│  LAYER 9: EMOTIONAL WITNESS (Parallel to Witness Arbitrator)                    │
│  ═══════════════════════════════════════════════════════════                    │
│  • Monitor emotional coherence                                                  │
│  • Detect emotional mismatches                                                  │
│  • Trigger emotional correction if needed                                       │
│                                                                                 │
│  LAYER 11: EMOTIONAL SYNTHESIS (Parallel to Synthesis Gate)                     │
│  ══════════════════════════════════════════════════════════                     │
│  • Final emotional tone check                                                   │
│  • Apply DHA with Rasa-informed parameters                                      │
│  • Ensure emotional-logical coherence                                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Implementation Sketch

```python
@dataclass
class RasaState:
    """9-dimensional emotional state."""
    shringara: float = 0.0  # Love/Beauty
    hasya: float = 0.0      # Mirth/Comedy
    karuna: float = 0.0     # Compassion/Pathos
    raudra: float = 0.0     # Fury/Anger
    veera: float = 0.0      # Valor/Heroic
    bhayanaka: float = 0.0  # Terror/Fear
    bibhatsa: float = 0.0   # Disgust/Aversion
    adbhuta: float = 0.0    # Wonder/Amazement
    shanta: float = 0.0     # Peace/Serenity

    @property
    def dominant_rasa(self) -> str:
        """Return name of dominant Rasa."""
        values = [
            (self.shringara, "SHRINGARA"),
            (self.hasya, "HASYA"),
            (self.karuna, "KARUNA"),
            (self.raudra, "RAUDRA"),
            (self.veera, "VEERA"),
            (self.bhayanaka, "BHAYANAKA"),
            (self.bibhatsa, "BIBHATSA"),
            (self.adbhuta, "ADBHUTA"),
            (self.shanta, "SHANTA"),
        ]
        return max(values, key=lambda x: x[0])[1]

    @property
    def valence(self) -> float:
        """Positive/negative emotional valence."""
        positive = self.shringara + self.hasya + self.veera + self.adbhuta + self.shanta
        negative = self.karuna + self.raudra + self.bhayanaka + self.bibhatsa
        return (positive - negative) / (positive + negative + 1e-6)

    @property
    def arousal(self) -> float:
        """Emotional arousal/activation level."""
        high_arousal = self.raudra + self.bhayanaka + self.adbhuta + self.veera
        low_arousal = self.shanta + self.karuna
        return (high_arousal - low_arousal) / (high_arousal + low_arousal + 1e-6)


class EmotionalReasoningKernel(nn.Module):
    """
    ERK: Emotional reasoning parallel to SRK.
    """

    # Emotional transition rules (symbolic, non-learnable)
    VALID_TRANSITIONS = {
        'RAUDRA': ['SHANTA', 'KARUNA'],  # Anger → Peace or Compassion
        'BHAYANAKA': ['SHANTA', 'VEERA'],  # Fear → Peace or Courage
        'KARUNA': ['SHANTA', 'KARUNA'],  # Grief → Peace or Empathy (not comedy)
        'HASYA': ['HASYA', 'ADBHUTA', 'SHRINGARA'],  # Joy → Joy, Wonder, Love
    }

    # Emotional response rules (symbolic)
    RESPONSE_RULES = {
        'BHAYANAKA': {
            'appropriate_responses': ['SHANTA', 'VEERA', 'KARUNA'],
            'inappropriate_responses': ['HASYA', 'RAUDRA'],
            'priority': 'acknowledge_fear_first',
        },
        'KARUNA': {
            'appropriate_responses': ['KARUNA', 'SHANTA'],
            'inappropriate_responses': ['HASYA'],
            'priority': 'validate_grief_first',
        },
        'RAUDRA': {
            'appropriate_responses': ['SHANTA', 'KARUNA'],
            'inappropriate_responses': ['RAUDRA'],
            'priority': 'de_escalate',
        },
    }

    def __init__(self, config: ERKConfig):
        super().__init__()
        self.config = config

        # Emotion detector (learned)
        self.emotion_detector = EmotionDetector(config.hidden_dim)

        # Emotion projector (to Rasa space)
        self.rasa_projector = nn.Linear(config.hidden_dim, 9)

        # Emotional coherence checker
        self.coherence_checker = EmotionalCoherenceChecker()

        # ToM-E module
        self.theory_of_mind = TheoryOfMindEmotional(config)

    def forward(
        self,
        hidden_states: torch.Tensor,
        user_context: Optional[Dict] = None,
    ) -> Tuple[torch.Tensor, RasaState, Dict]:
        """
        Apply emotional reasoning to hidden states.

        Returns:
            - emotionally_modulated_states
            - detected_rasa_state
            - emotional_reasoning_trace
        """
        # Detect input emotion
        input_rasa = self.detect_emotion(hidden_states)

        # Apply Theory of Mind (infer true emotion)
        if user_context:
            inferred_rasa = self.theory_of_mind.infer(
                stated_emotion=input_rasa,
                context=user_context,
            )
        else:
            inferred_rasa = input_rasa

        # Determine appropriate response emotion
        response_rasa = self.compute_appropriate_response(inferred_rasa)

        # Modulate hidden states toward response emotion
        modulated = self.modulate_toward_rasa(hidden_states, response_rasa)

        # Validate emotional coherence
        coherence = self.coherence_checker.validate(
            user_emotion=inferred_rasa,
            response_emotion=response_rasa,
        )

        trace = {
            'input_rasa': input_rasa,
            'inferred_rasa': inferred_rasa,
            'response_rasa': response_rasa,
            'coherence': coherence,
            'tom_discrepancy': (input_rasa.dominant_rasa != inferred_rasa.dominant_rasa),
        }

        return modulated, response_rasa, trace
```

---

## Part 4: Integration with Existing Filters

### ERK + SRK Integration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SRK + ERK INTEGRATED ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  LAYER 4: DUAL GROUNDING                                                        │
│  ════════════════════════                                                       │
│  • SRK DNA Bridge: Ontological grounding (Bhavas)                               │
│  • ERK Emotion Ground: Emotional grounding (Rasas)                              │
│  • Combined: 40D state initialization                                           │
│                                                                                 │
│  LAYER 7: DUAL ALIGNMENT                                                        │
│  ════════════════════════                                                       │
│  • SRK CSR: Semantic coherence                                                  │
│  • ERK Emotion Align: Emotional coherence                                       │
│  • Combined: Coherent semantic + emotional state                                │
│                                                                                 │
│  LAYER 9: DUAL WITNESS                                                          │
│  ══════════════════════                                                         │
│  • SRK Vritti Gate: Epistemic validation                                        │
│  • ERK Emotion Gate: Emotional validation                                       │
│  • Combined: Reject if factually OR emotionally incoherent                      │
│                                                                                 │
│  LAYER 11: DUAL SYNTHESIS                                                       │
│  ═════════════════════════                                                      │
│  • SRK Synthesis Gate: Logical synthesis                                        │
│  • ERK Emotion Synth: Emotional synthesis                                       │
│  • Combined: Coherent, emotionally appropriate output                           │
│                                                                                 │
│  DHA ENHANCEMENT:                                                               │
│  ════════════════                                                               │
│  Current: D = T × I × R (3 tones)                                               │
│  Enhanced: D = T_rasa × I × R (9 Rasa-informed tones)                           │
│                                                                                 │
│  T_rasa = softmax([l_rasa_1, ..., l_rasa_9])                                    │
│  where l_rasa_i = f(Rasa_i, context, coherence)                                 │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 5: Implementation Roadmap

### Phase 1: Rasa State Extension (0-2 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| Extend Sovereign State to 40D (add Rasa dimensions) | Low | High |
| Implement RasaState dataclass | Low | Medium |
| Add Rasa projector to SRK | Medium | High |
| Update diagnostics for Rasa tracking | Low | Medium |

### Phase 2: Emotion Detection (2-4 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| Emotion Detector module | High | Very High |
| Rasa classification head | Medium | High |
| Training data for emotion detection | High | Very High |
| Integration with Layer 4 (Emotional Grounding) | Medium | High |

### Phase 3: Emotional Reasoning Rules (4-6 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| Emotional transition rules (symbolic) | Medium | High |
| Emotional response rules (symbolic) | Medium | High |
| Emotional Coherence Validator | Medium | High |
| Extend IMR with emotional templates | High | Very High |

### Phase 4: Theory of Mind for Emotions (6-9 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| ToM-E module implementation | Very High | Very High |
| Stated vs Inferred emotion detection | High | High |
| Context integration for emotion inference | High | High |
| Discrepancy handling logic | Medium | High |

### Phase 5: Emotional Memory (9-12 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| Emotional Memory persistence | High | High |
| User emotional profile tracking | Medium | Medium |
| Cross-session emotional continuity | High | High |
| Integration with PAIF (from cognition gaps doc) | Medium | High |

---

## Conclusion

Phase-Quad has strong foundations for emotional AI (CSR coherence, DHA delivery, LAM trajectory, Kosha depth, Vritti modes) but lacks **true emotional reasoning**:

| Aspect | Current Status | Gap |
|--------|---------------|-----|
| Emotional delivery | ✅ DHA tones | Need Rasa-informed tones |
| Emotional tracking | ✅ LAM trajectory | Need persistent memory |
| Emotional depth | ✅ Kosha layers | Need explicit Rasa dimensions |
| Emotional recognition | ⚠️ Implicit | Need explicit detection |
| Emotional reasoning | ❌ Missing | Need ERK with rules |
| Emotional intelligence | ❌ Missing | Need ToM-E |

The proposed **Emotional Reasoning Kernel (ERK)** would:
1. Extend Sovereign State with 9 Rasa dimensions
2. Add explicit emotion detection at Layer 4
3. Implement symbolic emotional reasoning rules
4. Provide Theory of Mind for emotions
5. Enable emotional memory persistence

This would elevate Phase-Quad from **emotional delivery** (Level 1-2) to **emotional intelligence** (Level 4-5), making it a truly emotionally-aware symbolic AI system.

---

*Document prepared for Phase-Quad Architecture Team*
*Symbolu AI Systems*
*January 2026*
