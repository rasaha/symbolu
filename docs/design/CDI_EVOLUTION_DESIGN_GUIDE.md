# Cross-Domain Pattern Transfer: Evolution Design Guide

## From Post-Hoc Classification to Real-Time Recognition and Predictive Anticipation

**Phase**: P38 (proposed)
**Status**: Design
**Date**: February 2026
**Codebase**: Symbol-U V11.1.0
**Prerequisite Phases**: P35 (Drift Forecast), P36 (Identity Memory), P37 (Continuity)

---

## 0. Why This Is the Path to General Intelligence

### The Cognitive Science Foundation

An estimated 90-95% of human cognition is pattern matching. When a doctor diagnoses a patient, they are matching the presented symptoms against patterns from thousands of prior cases. When a financial analyst reads a market chart, they are matching the curve shape against patterns they have seen resolve before. When a parent reads their child's body language, they are matching micro-expressions against emotional patterns accumulated over years. When a chess grandmaster glances at a board, they are not computing moves -- they are matching the position against ~100,000 stored patterns and recognizing which one applies.

This is not a simplification. This is the actual mechanism. Kahneman's System 1 (fast, automatic, effortless) is pattern matching. System 2 (slow, deliberate, effortful) is what happens when pattern matching fails and conscious reasoning must compensate. Expertise in any domain is the accumulation of patterns that are increasingly fine-grained, increasingly context-sensitive, and increasingly transferable across situations.

**The critical insight**: What separates a general intelligence from a narrow one is not the number of patterns, but the ability to **transfer patterns across domains** and to **recognize patterns as they form, before they fully manifest**.

A narrow system recognizes "this patient has pneumonia" from symptoms. A general intelligence recognizes "this organizational structure is showing the same decay pattern I've seen in biological ecosystems and in financial markets" -- and recognizes it while the pattern is still forming, early enough to intervene.

### How Humans Do It: Three Layers of Pattern Cognition

Human pattern matching operates at three distinct temporal layers, each building on the one below:

**Layer 1 -- Recognition (System 1, instant)**: "I've seen this before." The doctor glances at a rash and immediately knows it's shingles. The trader sees a candlestick formation and immediately feels "reversal." This is CDI's current capability -- snapshot classification against a known library.

**Layer 2 -- Tracking (System 1.5, seconds to minutes)**: "This is evolving." The doctor watches the patient's vitals trending over the last hour and recognizes a sepsis trajectory. The trader watches the order book thinning and recognizes liquidity withdrawal forming. This requires temporal memory -- not just "what pattern is active now" but "how is the pattern landscape changing over time." This is what P38 Capabilities 1-3 provide: lifecycle events, boundary trajectories, persistence and volatility.

**Layer 3 -- Anticipation (System 2 informed by System 1, minutes to hours)**: "I know what's coming next." The experienced ER nurse sees the combination of rising heart rate + falling blood pressure + patient anxiety and says "get the crash cart ready" -- the cardiac arrest hasn't happened yet, but the *pattern of patterns* (a sequence) is recognizable and the next step is predictable. The veteran diplomat watches the sequence of diplomatic recalls + trade sanctions + military exercises and says "this is the 1914 pattern, war is 2 steps away." This requires compositional pattern recognition -- sequences, partial matches, and trajectory-to-completion estimation. This is what P38 Capabilities 4-5 provide: sequence grammar with partial matching and boundary proximity estimation.

**The 90-95% claim is structural**: Most human decisions are made at Layer 1 (instant recognition) or Layer 2 (pattern tracking). Only the remaining 5-10% require genuine Layer 3+ reasoning (novel problems, first-principles thinking, creative synthesis). A system that implements Layers 1-3 faithfully is capturing the operational core of human intelligence -- not the exotic frontier (creative genius, philosophical reasoning) but the massive, reliable base that makes everyday expertise possible.

### Why Current LLMs Are Stuck at Layer 1

Standard LLMs have absorbed enormous quantities of patterns from training data. GPT-4, Claude, and Gemini can all recognize that "market crash" and "empire collapse" share structural features -- but only because they've seen humans make that analogy in training text. Their pattern matching is:

- **Implicit**: Encoded in billions of opaque parameters, not in named, inspectable structures
- **Statistical**: Based on co-occurrence frequency, not structural similarity
- **Post-hoc**: They can describe a pattern after it's fully formed, but cannot track partial formation
- **Non-temporal**: They process one prompt at a time with no sliding window over evolving signals
- **Ungrounded**: When they say "this is similar to X," there is no structural basis to verify the claim
- **Non-compositional**: They cannot report "step 2 of a 3-step escalation sequence, next step approaching"

A human expert's pattern matching is different. When a veteran trader says "this feels like 2008," they are matching against a structural pattern (ENTROPY rising + AGENCY falling + FEEDBACK loops forming) that they can partially articulate and that evolves over time. They recognized it before the crash because they were tracking the pattern's *formation*, not waiting for its *completion*.

LLMs are trapped at Layer 1 because they are stateless per-request: each prompt is a fresh snapshot with no temporal accumulation. Even with conversation history in context, they have no sliding window, no signal regression, no lifecycle tracking, no sequence matching. They process text, not signal trajectories.

### Why Cross-Domain Pattern Transfer Is the AGI Core

Symbol-U's `AGI_CAPABILITIES.md` already articulates this vision:

> "Knowledge is stored not as raw content, but as **transferable reasoning patterns**"
> -- Section 6, Experiential Reasoning Objects

> "Don't extract patterns from content. Discover patterns from usage."
> -- Section 4, Persona Query Tracking

The 12D ontological backbone with 5 mirror pairs is designed precisely for this: encoding events in a domain-agnostic structural space where "market crash" and "empire collapse" share the same 10D fingerprint not because of statistical co-occurrence but because they share structural properties (high Acting, high destruction event type, low Absolving, low meaning-resolution).

The cross-domain bridge discovery mechanism in `AGI_CAPABILITIES.md` Section 5 already describes the end goal:

```
BRIDGE DISCOVERED:
  finance ↔ history
  Bridge count: 2
  Shared events: ['destruction', 'collapse']

FUTURE QUERY: "Why did my startup fail?"
  System suggests: Search finance AND history
  Because: User thinks in collapse patterns across both
```

**But the current CDI implementation has not yet realized this vision for real-time and predictive operation.** It can classify a snapshot ("this matches risk_hiding") but cannot track a pattern forming ("risk_hiding is emerging, 2 turns from onset"). It can match a single pattern but cannot recognize a meaningful sequence ("anxiety → masking → chronic stress is a suppression escalation"). It can interpret a pattern in a domain ("risk_hiding in finance means...") but cannot transfer a pattern trajectory ("the ENTROPY-AGENCY aspect trajectory in this finance conversation matches a known medical deterioration pattern").

### What P38 Enables: Layer 2 and Layer 3 for Machines

P38 bridges the gap between the AGI vision (domain-agnostic pattern transfer) and the current implementation (stateless snapshot classification). It implements the three layers of human pattern cognition:

| Human Cognitive Layer | Current CDI (Layer 1 Only) | P38 (Layers 1 + 2 + 3) |
|---|---|---|
| **"I've seen this before"** -- instant recognition | 13 pattern classifications per turn | Same, plus lifecycle events (onset/sustain/exit/recurrence) |
| **"This is starting to look like..."** -- tracking a forming pattern | Not possible (stateless) | Boundary proximity + trajectory ETA: "approaching risk_hiding, ~2 turns" |
| **"This is getting worse"** -- tracking intensity evolution | Not possible (no memory) | Pattern persistence + volatility + stability band over sliding window |
| **"First X, then Y, now Z is coming"** -- sequence anticipation | Not possible (no composition) | Pattern sequence grammar with partial matching + anticipation |
| **"This reminds me of something from a completely different field"** -- cross-domain transfer | Domain interpretation strings (static, manual) | Aspect-mediated trajectory matching: same ENTROPY-AGENCY-BALANCE fingerprint across domains |
| **"Something feels off"** -- pre-conscious pattern signal | Not possible (observer has no output channel) | Soft steering hints: non-binding DHA tone adjustment from anticipated patterns |

### The 90-95% Argument for Prioritization

If 90-95% of human intelligence is pattern matching, then the fastest path to general intelligence is not building better reasoning (the 5-10%) but building better pattern recognition and transfer (the 90-95%). This has direct implications for engineering priority:

1. **Pattern library expansion** (more patterns = more expertise domains) should be prioritized over reasoning chain improvements
2. **Temporal pattern tracking** (Layers 2-3) is more valuable than better single-turn classification (Layer 1), because Layer 1 without Layers 2-3 is like having a doctor who can read a lab result but cannot track a patient's trajectory
3. **Cross-domain pattern transfer** is the multiplier: every pattern that transfers across N domains provides N times the value of a domain-specific pattern
4. **Sequence grammar** is the composition mechanism: M patterns that can form K sequences represent M*K effective capabilities, not M+K

The scaling path is clear: curate patterns, compose them into sequences, track them temporally, transfer them across domains. Each axis multiplies the others. This is how human expertise scales -- not by learning new facts, but by recognizing deeper patterns in what you already know and transferring them to new situations faster than anyone else.

### The Structural Advantage Phase Quad Has

Standard LLMs cannot take this path because patterns are dissolved into weight matrices. You cannot name a pattern in GPT-4, track its lifecycle, compose it with other patterns, or transfer it to a new domain with an audit trail. The pattern exists implicitly as activation patterns across billions of parameters, inaccessible to inspection, composition, or governance.

Phase Quad's structural advantage is that patterns are **first-class objects** -- named, configured, thresholded, domain-interpreted, and governable. This means they can be:
- **Composed**: Pattern A + Pattern B in sequence = Pattern Sequence AB
- **Tracked**: Pattern A entered at turn 3, sustained for 4 turns, exited at turn 7
- **Transferred**: Pattern A in finance has the same aspect fingerprint as Pattern B in medicine
- **Governed**: Pattern A requires confidence >= 0.65, is blocked in fiction→medicine transfers, and is logged with full provenance
- **Anticipated**: Pattern A boundary distance is shrinking at 0.06/turn, ETA 2 turns

This is the architectural moat. It is not easy to retrofit onto a standard LLM, because it requires patterns to exist as inspectable entities rather than as latent statistical regularities. The P38 evolution makes this moat deeper by extending first-class pattern objects from single-turn classification into temporal trajectories, compositional sequences, and cross-domain aspect fingerprints -- the three capabilities that constitute Layers 2 and 3 of the human pattern cognition stack.

---

## 1. Problem Statement

The Cross-Domain Intelligence module (`temporal/cross_domain_intelligence.py`) currently performs **stateless, point-in-time pattern classification**. It answers: "Given these signals right now, which of the 13 patterns match?"

It cannot answer:
- "Is a pattern **forming**?" (onset detection)
- "Is this pattern **intensifying** or **dissipating**?" (lifecycle tracking)
- "Given the current trajectory, which pattern will the signals enter **next**?" (anticipation)
- "Is this pattern sequence meaningful?" (compositional recognition)

The temporal prediction chain (P35 → P36 → P37) tracks signal *drift* and *continuity* over time, but operates on raw signals (drift_fusion_index, schema_drift, coherence_v3_quality, etc.) without awareness of the higher-level *patterns* those signals produce when interpreted through CDI.

**The gap**: The system has temporal intelligence about signals and pattern intelligence about snapshots, but no temporal intelligence about patterns.

---

## 2. Architecture Status Quo

### 2.1 Current Information Flow

```
Raw Signals (per turn)
    │
    ├──→ P35 Drift Trend Analyzer ──→ predicted_drift_score
    │         (drift_trend_analyzer.py:106-174)
    │         Window: 3 snapshots
    │         Output: "stable" | "worsening" | "improving"
    │
    ├──→ P36 Identity Resonance Memory ──→ persistence, volatility, stability_band
    │         (memory_formula.py:99-323)
    │         Window: 5-7 snapshots
    │         Output: resonance_index, "stable"|"soft"|"fragile"
    │
    ├──→ P37 Adaptive Continuity ──→ continuity_score, continuity_pressure
    │         (adaptive_continuity_engine.py:96-120)
    │         Window: 5-7 snapshots (via P36)
    │         Output: continuity_mode, oscillation_detected
    │
    └──→ CDI Pattern Classifier ──→ [(pattern_name, confidence), ...]
              (cross_domain_intelligence.py:332-368)
              Window: NONE (stateless)
              Output: flat list of matched patterns
```

### 2.2 What P35 Already Does Well (Reusable Patterns)

P35's `drift_trend_analyzer.py` demonstrates the right approach for temporal signal analysis:

1. **SignalSnapshot** (line 35-58): Immutable per-turn signal capture
2. **compute_signal_deltas** (line 61-103): Delta computation with quality-signal inversion
3. **classify_trend_direction** (line 106-174): Rule-based trend from averaged deltas over window
4. **analyze_trend_from_histories** (line 177-241): Convenience wrapper for history lists

CDI evolution should follow this same pattern: immutable snapshots, deterministic deltas, rule-based classification over sliding windows.

### 2.3 What P36 Already Does Well (Reusable Patterns)

P36's `memory_formula.py` demonstrates persistence and volatility tracking:

1. **compute_persistence_score** (line 164-190): `1.0 - variance(values)` over window
2. **compute_volatility_index** (line 193-228): `avg(|deltas|)` over window
3. **compute_stability_band** (line 231-259): Rule-based band from persistence + volatility
4. **compute_all_metrics** (line 262-323): Append-and-cap sliding window management

CDI pattern memory should use identical mechanisms: pattern persistence = stable pattern presence; pattern volatility = rapid pattern switching.

---

## 3. Design: Stateful Cross-Domain Pattern Tracker

### 3.1 New Module: `temporal/cross_domain_pattern_tracker.py`

This module wraps `CrossDomainIntelligence` with temporal state.

#### 3.1.1 Pattern Snapshot (Immutable Per-Turn Record)

```python
@dataclass(frozen=True)
class PatternSnapshot:
    """Immutable record of CDI pattern state at one turn."""
    turn_index: int
    active_patterns: FrozenSet[str]           # patterns meeting threshold
    pattern_confidences: Dict[str, float]     # pattern_name -> confidence
    dominant_pattern: Optional[str]           # highest confidence pattern
    dominant_confidence: float                # confidence of dominant
    smi: float                                # input SMI (for boundary distance)
    bhava_id: int                             # input bhava_id
    bhava_direction: str                      # input direction
```

**Design rationale**: Mirrors `SignalSnapshot` from `drift_trend_analyzer.py:35-58`. Frozen for immutability (INV-P35-4 pattern). Stores both the classification result and the raw inputs needed for boundary-distance computation.

#### 3.1.2 Pattern Memory (Sliding Window)

```python
class CrossDomainPatternTracker:
    """
    Stateful temporal tracker for CDI patterns.

    Maintains sliding window of PatternSnapshots and computes:
    - Pattern lifecycle events (onset, sustain, exit)
    - Pattern trajectory (approaching, dwelling, departing)
    - Pattern persistence and volatility (P36 pattern)
    - Pattern sequence matching

    INVARIANTS:
        - INV-P38-1: Deterministic (same inputs -> same outputs)
        - INV-P38-2: Observer-only (never influences decisions)
        - INV-P38-3: No LLM, no ML, no learning
        - INV-P38-4: Sliding window bounded (max 10 snapshots)
    """

    def __init__(self, window_size: int = 10):
        self._cdi = CrossDomainIntelligence()
        self._window: List[PatternSnapshot] = []
        self._window_size = window_size
```

**Design rationale**: Same sliding window pattern as `TemporalBhavaTracker.__init__` (`temporal_bhava_tracker.py:186-199`). Window size 10 matches `CoherenceEngine` default (`coherence_engine.py:45`).

---

### 3.2 Capability 1: Pattern Lifecycle Events

#### Problem
CDI returns a flat list each turn. There is no event when a pattern *appears* for the first time, *persists* across turns, or *disappears*.

#### Design

```python
@dataclass(frozen=True)
class PatternEvent:
    """An event in a pattern's lifecycle."""
    pattern_name: str
    event_type: str       # "onset" | "sustain" | "exit" | "recurrence"
    turn_index: int
    confidence: float
    dwell_turns: int      # how many consecutive turns active (onset=1)
    gap_turns: int        # turns since last active (recurrence only)
```

**Detection logic** (deterministic rule-based, no ML):

```python
def _detect_lifecycle_events(self, current: PatternSnapshot) -> List[PatternEvent]:
    events = []
    prev = self._window[-1] if self._window else None

    for pattern in current.active_patterns:
        if prev is None or pattern not in prev.active_patterns:
            # Pattern was NOT active last turn, IS active now
            # Was it active earlier in the window? (recurrence vs onset)
            gap = self._turns_since_last_active(pattern)
            if gap is not None and gap > 0:
                events.append(PatternEvent(
                    pattern_name=pattern,
                    event_type="recurrence",
                    turn_index=current.turn_index,
                    confidence=current.pattern_confidences[pattern],
                    dwell_turns=1,
                    gap_turns=gap,
                ))
            else:
                events.append(PatternEvent(
                    pattern_name=pattern,
                    event_type="onset",
                    turn_index=current.turn_index,
                    confidence=current.pattern_confidences[pattern],
                    dwell_turns=1,
                    gap_turns=0,
                ))
        else:
            # Pattern was active last turn AND this turn
            dwell = self._consecutive_active_count(pattern)
            events.append(PatternEvent(
                pattern_name=pattern,
                event_type="sustain",
                turn_index=current.turn_index,
                confidence=current.pattern_confidences[pattern],
                dwell_turns=dwell + 1,
                gap_turns=0,
            ))

    # Exit events: patterns that were active last turn but not now
    if prev is not None:
        for pattern in prev.active_patterns - current.active_patterns:
            dwell = self._consecutive_active_count(pattern)
            events.append(PatternEvent(
                pattern_name=pattern,
                event_type="exit",
                turn_index=current.turn_index,
                confidence=0.0,
                dwell_turns=dwell,
                gap_turns=0,
            ))

    return events
```

**Integration point**: This mirrors `TemporalBhavaTracker._compute_tension()` (`temporal_bhava_tracker.py:601-624`) which tracks consecutive high-SMI streaks. Same approach applied to pattern membership instead of raw SMI.

---

### 3.3 Capability 2: Pattern Boundary Distance and Trajectory

#### Problem
CDI uses SMI as a hard filter (`cross_domain_intelligence.py:394-397`): if SMI is outside the pattern's range, confidence is 0.0 -- no partial signal, no "approaching" indicator. A signal at SMI=0.49 gives zero information about `risk_hiding` (range 0.50-0.75), even though it is one tick away from entering.

#### Design

```python
@dataclass(frozen=True)
class BoundaryProximity:
    """How close a signal is to entering a pattern's region."""
    pattern_name: str
    distance_to_entry: float    # 0.0 = at boundary, >0 = outside
    distance_to_center: float   # distance from region center
    entry_dimension: str        # which dimension is closest to entry ("smi" | "bhava")
    direction: str              # "approaching" | "receding" | "stable"
    estimated_turns_to_entry: Optional[int]  # None if receding or stable
```

**Computation** (deterministic, extends existing CDI logic):

```python
def _compute_smi_boundary_distance(
    self, smi: float, pattern_config: PatternConfig,
) -> float:
    """Distance from current SMI to the pattern's SMI range.

    Returns 0.0 if inside the range, positive float if outside.
    """
    smi_min, smi_max = pattern_config.smi_range
    if smi_min <= smi <= smi_max:
        return 0.0
    return min(abs(smi - smi_min), abs(smi - smi_max))


def _estimate_turns_to_entry(
    self, pattern_name: str, current_distance: float,
) -> Optional[int]:
    """Estimate turns until signal enters pattern region.

    Uses linear regression slope from TemporalBhavaTracker pattern.
    Returns None if trajectory is not approaching.

    Reference: temporal_bhava_tracker.py:535-599 (_compute_trajectory)
    """
    if len(self._window) < 2:
        return None

    # Compute distance history for this pattern
    distances = [
        self._compute_smi_boundary_distance(
            snap.smi, self._cdi.get_pattern_config(pattern_name)
        )
        for snap in self._window
    ]
    distances.append(current_distance)

    # Linear regression on distances (same as _compute_trajectory)
    n = len(distances)
    indices = list(range(n))
    mean_x = sum(indices) / n
    mean_y = sum(distances) / n
    cov_xy = sum((indices[i] - mean_x) * (distances[i] - mean_y) for i in range(n)) / n
    var_x = sum((x - mean_x) ** 2 for x in indices) / n

    if var_x == 0:
        return None

    slope = cov_xy / var_x

    # Negative slope = distance decreasing = approaching
    if slope >= -0.01:  # not approaching (stable or receding)
        return None

    # ETA = current_distance / |slope|
    eta = current_distance / abs(slope)
    return max(1, round(eta))
```

**Design rationale**: Reuses the linear regression pattern from `TemporalBhavaTracker._compute_trajectory()` (`temporal_bhava_tracker.py:535-599`). Same math, applied to pattern boundary distance instead of raw SMI. The `SLOPE_EPSILON` threshold (0.02 in `temporal_bhava_tracker.py:184`) is tightened to 0.01 for boundary distance because the scale is smaller.

---

### 3.4 Capability 3: Pattern Persistence and Volatility

#### Problem
P36 computes persistence and volatility for identity resonance. CDI patterns need equivalent metrics: "Is `risk_hiding` stably present or flickering?"

#### Design

Reuse P36's exact formulas (`memory_formula.py:164-259`) applied to pattern presence:

```python
def compute_pattern_persistence(self, pattern_name: str) -> float:
    """Persistence of a specific pattern across the window.

    Formula (reuses P36 pattern):
        presence_values = [1.0 if pattern active else 0.0 for each turn]
        persistence = 1.0 - variance(presence_values)

    High persistence = pattern consistently present or consistently absent.
    Low persistence = pattern flickering on/off.
    """
    if len(self._window) < 2:
        return 1.0

    presence = [
        1.0 if pattern_name in snap.active_patterns else 0.0
        for snap in self._window
    ]
    variance = sum((v - (sum(presence) / len(presence))) ** 2 for v in presence) / len(presence)
    return max(0.0, min(1.0, 1.0 - variance))


def compute_pattern_volatility(self) -> float:
    """Rate of pattern switching across the window.

    Formula (reuses P36 pattern):
        For each consecutive turn pair, count how many patterns changed.
        volatility = avg(|pattern_set_symmetric_difference|) / 13

    Reference: memory_formula.py:193-228 (compute_volatility_index)
    """
    if len(self._window) < 2:
        return 0.0

    diffs = []
    for i in range(1, len(self._window)):
        prev_patterns = self._window[i - 1].active_patterns
        curr_patterns = self._window[i].active_patterns
        symmetric_diff = len(prev_patterns.symmetric_difference(curr_patterns))
        diffs.append(symmetric_diff / 13.0)  # normalize by total pattern count

    return sum(diffs) / len(diffs) if diffs else 0.0
```

**Stability band** (reuses P36 logic from `memory_formula.py:231-259`):

```python
def compute_pattern_stability_band(self) -> str:
    """Overall pattern stability: "stable", "soft", or "fragile".

    Uses same thresholds as P36:
    - "stable": persistence >= 0.75 for dominant pattern AND volatility < 0.20
    - "fragile": persistence < 0.40 for dominant OR volatility >= 0.45
    - "soft": otherwise
    """
    dominant = self._get_dominant_pattern()
    if dominant is None:
        return "soft"

    persistence = self.compute_pattern_persistence(dominant)
    volatility = self.compute_pattern_volatility()

    if persistence < 0.40 or volatility >= 0.45:
        return "fragile"
    if persistence >= 0.75 and volatility < 0.20:
        return "stable"
    return "soft"
```

---

### 3.5 Capability 4: Pattern Sequence Grammar

#### Problem
Patterns are detected independently. `risk_hiding` + `defensive_rationalization` in sequence means something different from either alone, but CDI has no concept of meaningful sequences.

#### Design

Define pattern sequences as first-class objects with deterministic matching:

```python
@dataclass(frozen=True)
class PatternSequenceRule:
    """A known meaningful pattern sequence."""
    name: str
    category: str                           # "escalation" | "resolution" | "entrenchment"
    steps: Tuple[str, ...]                  # ordered pattern names
    max_gap_turns: int                      # max turns between steps (0 = must be consecutive)
    min_confidence: float                   # minimum avg confidence across matched steps
    interpretation: str                     # what this sequence means
```

**Predefined sequences** (hand-curated, deterministic -- same philosophy as the 13 patterns):

```python
PATTERN_SEQUENCES: List[PatternSequenceRule] = [
    # Escalation sequences
    PatternSequenceRule(
        name="suppression_escalation",
        category="escalation",
        steps=("acute_anxiety", "emotional_masking", "chronic_stress"),
        max_gap_turns=2,
        min_confidence=0.60,
        interpretation="Acute distress being suppressed, transitioning to chronic stress pattern",
    ),
    PatternSequenceRule(
        name="entrenchment_spiral",
        category="entrenchment",
        steps=("cognitive_dissonance", "avoidance_pattern", "defensive_rationalization"),
        max_gap_turns=2,
        min_confidence=0.65,
        interpretation="Internal conflict being avoided rather than resolved, rationalizations forming",
    ),
    PatternSequenceRule(
        name="risk_concealment_deepening",
        category="escalation",
        steps=("risk_hiding", "defensive_rationalization"),
        max_gap_turns=1,
        min_confidence=0.65,
        interpretation="Active risk concealment followed by justification -- high concern signal",
    ),

    # Resolution sequences
    PatternSequenceRule(
        name="productive_resolution",
        category="resolution",
        steps=("tension_corridor", "breakthrough_insight", "integrative_growth"),
        max_gap_turns=3,
        min_confidence=0.60,
        interpretation="Sustained tension resolved through insight, leading to integration",
    ),
    PatternSequenceRule(
        name="recovery_arc",
        category="resolution",
        steps=("chronic_stress", "recovery_trajectory", "resilience_pattern"),
        max_gap_turns=3,
        min_confidence=0.60,
        interpretation="Stress pattern resolving through recovery into demonstrated resilience",
    ),
    PatternSequenceRule(
        name="authentic_breakthrough",
        category="resolution",
        steps=("emotional_masking", "authentic_expression", "breakthrough_insight"),
        max_gap_turns=2,
        min_confidence=0.60,
        interpretation="Emotional defense dropping, enabling genuine expression and insight",
    ),

    # Entrenchment sequences
    PatternSequenceRule(
        name="chronic_avoidance",
        category="entrenchment",
        steps=("avoidance_pattern", "emotional_masking", "avoidance_pattern"),
        max_gap_turns=2,
        min_confidence=0.60,
        interpretation="Avoidance recurring after emotional suppression -- deepening entrenchment",
    ),
]
```

**Matching algorithm** (deterministic, greedy forward scan):

```python
def detect_sequences(self) -> List[Tuple[PatternSequenceRule, float, int]]:
    """Detect pattern sequences in the window history.

    Returns list of (matched_rule, avg_confidence, steps_completed).
    Both fully matched sequences (steps_completed == len(steps)) and
    partial matches (steps_completed < len(steps)) are returned.

    Partial matches are the key to anticipation: if 2 of 3 steps are
    matched, the system can signal "this sequence is forming."

    Algorithm:
        For each rule, scan the window left-to-right.
        For each step, find the earliest turn where that pattern was active
        after the previous step's turn, within max_gap_turns.
        Track how many steps matched and with what confidence.
    """
    results = []

    for rule in PATTERN_SEQUENCES:
        steps_matched = 0
        total_confidence = 0.0
        last_turn_index = -1

        for step_pattern in rule.steps:
            found = False
            for snap in self._window:
                if snap.turn_index <= last_turn_index:
                    continue
                if last_turn_index >= 0 and (snap.turn_index - last_turn_index) > rule.max_gap_turns + 1:
                    break  # gap too large
                if step_pattern in snap.active_patterns:
                    steps_matched += 1
                    total_confidence += snap.pattern_confidences[step_pattern]
                    last_turn_index = snap.turn_index
                    found = True
                    break
            if not found:
                break  # sequence broken

        if steps_matched >= 2:  # at least partial match (2+ steps)
            avg_confidence = total_confidence / steps_matched
            if avg_confidence >= rule.min_confidence:
                results.append((rule, avg_confidence, steps_matched))

    return results
```

**Anticipation signal**: When `steps_completed < len(steps)`, the system knows:
- Which sequence is *forming*
- Which *next step* would complete or advance the sequence
- Whether the boundary distance to that next step's pattern is shrinking (from Capability 2)

This is how the system anticipates **before** a pattern fully manifests.

---

### 3.6 Capability 5: Bidirectional CDI ↔ P35 Integration

#### Problem
Currently P35 predicts *that* drift is happening but not *what kind* of pattern is forming. CDI classifies *what* pattern is present but not *whether* it's getting stronger. These two systems need a bidirectional bridge.

#### Design: CDI Pattern Instability Signal → P35

```python
def compute_pattern_instability_signal(self) -> float:
    """Compute a scalar instability signal from pattern dynamics.

    This signal can be consumed by P35 as an additional input alongside
    drift_fusion_index, schema_drift, etc.

    Formula:
        instability = 0.40 * pattern_volatility
                    + 0.30 * (1 - dominant_pattern_persistence)
                    + 0.20 * escalation_pressure
                    + 0.10 * recurrence_rate

    Where:
        pattern_volatility: from compute_pattern_volatility()
        dominant_pattern_persistence: persistence of the most frequent pattern
        escalation_pressure: fraction of detected sequences in "escalation" category
        recurrence_rate: fraction of lifecycle events that are "recurrence" type
    """
    volatility = self.compute_pattern_volatility()
    dominant = self._get_dominant_pattern()
    persistence = self.compute_pattern_persistence(dominant) if dominant else 0.5
    escalation_pressure = self._compute_escalation_pressure()
    recurrence_rate = self._compute_recurrence_rate()

    instability = (
        0.40 * volatility
        + 0.30 * (1.0 - persistence)
        + 0.20 * escalation_pressure
        + 0.10 * recurrence_rate
    )

    return max(0.0, min(1.0, instability))
```

**Integration into P35**: Add `pattern_instability` as an optional 7th signal in `SignalSnapshot` (`drift_trend_analyzer.py:35`). This does NOT change the existing 6 signals or their weights -- it adds an additive bonus (same pattern as the temporal_trend 10% bonus in CDI).

#### Design: P35 Drift Forecast → CDI Threshold Adaptation

```python
def get_context_adjusted_threshold(
    self,
    pattern_config: PatternConfig,
    drift_forecast: float,
    continuity_mode: str,
) -> float:
    """Adjust a pattern's min_confidence threshold based on system context.

    When the system is under drift pressure (P35 forecast high) or
    continuity is strained (P37 mode), lower the detection threshold
    to catch patterns earlier -- earlier detection = earlier intervention.

    Adjustment (deterministic, bounded):
        base_threshold = pattern_config.min_confidence
        adjustment = 0.0

        if drift_forecast > 0.65:    # HIGH drift
            adjustment -= 0.05       # lower threshold (detect earlier)
        if continuity_mode == "fragmenting":
            adjustment -= 0.05

        adjusted = base_threshold + adjustment
        # Never go below 0.50 (hard floor to prevent false positives)
        return max(0.50, min(0.95, adjusted))
    """
```

**Design rationale**: This is a conservative, bounded adaptation. The threshold can drop by at most 0.10 (from two conditions), never below 0.50. This respects the deterministic invariant (same drift_forecast and continuity_mode always produce the same adjustment) while allowing contextual sensitivity.

---

### 3.7 Capability 6: Universal Aspect Wiring

#### Problem
`domain_distance.py:311-322` defines 10 `UNIVERSAL_ASPECTS` and `get_aspect_overlap()` computes cosine similarity, but no code ever computes aspect vectors from content signals.

#### Design: Derive Aspect Vectors from Existing Signals

The 10 universal aspects can be approximated from the signals CDI already receives, without any new inputs:

```python
ASPECT_DERIVATION_RULES: Dict[str, Callable] = {
    # ENTROPY: High SMI = high entropy (semantic mismatch = disorder)
    "ENTROPY": lambda smi, bhava_id, bhava_dir, kosha_id, ontology_id: smi,

    # CAUSALITY: Higher ontology_ids (7-12) map to reasoning/purpose
    "CAUSALITY": lambda smi, bhava_id, bhava_dir, kosha_id, ontology_id:
        max(0.0, (ontology_id - 5) / 7.0) if ontology_id > 5 else 0.0,

    # AGENCY: Higher bhava_ids indicate more agentic states
    "AGENCY": lambda smi, bhava_id, bhava_dir, kosha_id, ontology_id:
        bhava_id / 11.0,

    # BALANCE: Low SMI + centered bhava = balance
    "BALANCE": lambda smi, bhava_id, bhava_dir, kosha_id, ontology_id:
        (1.0 - smi) * (1.0 - abs(bhava_id - 5.5) / 5.5),

    # FLOW: "upward" direction = flow, "neutral" = moderate, "downward" = blocked
    "FLOW": lambda smi, bhava_id, bhava_dir, kosha_id, ontology_id:
        {"upward": 0.8, "neutral": 0.5, "downward": 0.2}.get(bhava_dir, 0.5),

    # CONSTRAINT: High kosha_id = deeper constraint layers
    "CONSTRAINT": lambda smi, bhava_id, bhava_dir, kosha_id, ontology_id:
        kosha_id / 7.0 if kosha_id <= 7 else 1.0,

    # EMERGENCE: Low SMI + high bhava + upward = emergent
    "EMERGENCE": lambda smi, bhava_id, bhava_dir, kosha_id, ontology_id:
        (1.0 - smi) * (bhava_id / 11.0) * (1.0 if bhava_dir == "upward" else 0.3),

    # FEEDBACK: Tension corridor signal (high SMI sustained = feedback loop)
    "FEEDBACK": lambda smi, bhava_id, bhava_dir, kosha_id, ontology_id:
        smi if smi > 0.6 else smi * 0.5,

    # HIERARCHY: Kosha layers are hierarchical by definition
    "HIERARCHY": lambda smi, bhava_id, bhava_dir, kosha_id, ontology_id:
        kosha_id / 7.0 if kosha_id <= 7 else 1.0,

    # THRESHOLD: SMI near pattern boundaries = threshold proximity
    "THRESHOLD": lambda smi, bhava_id, bhava_dir, kosha_id, ontology_id:
        1.0 - min(abs(smi - 0.35), abs(smi - 0.50), abs(smi - 0.65), abs(smi - 0.75)) / 0.20,
}
```

These derived aspect vectors can then be:
1. Tracked temporally in the sliding window (aspect trajectory)
2. Fed into `get_aspect_overlap()` (`domain_distance.py:325-364`) to enable `get_domain_distance_with_context()` (`domain_distance.py:243-281`)
3. Used as domain-agnostic pattern fingerprints for sequence matching

---

## 4. Observer-Only Boundary and Soft Steering

### 4.1 The Current Invariant

P35/P36/P37 enforce strict observer-only behavior:
- `INV-P35-1`: "Forecast never influences current decisions"
- `INV-P35-3`: "Observer-only behavior enforced"
- `INV-P37-1`: "Deterministic output"

P38 (this design) MUST respect these invariants for its prediction and classification outputs.

### 4.2 Proposed Soft-Steering Exception (Requires Governance Review)

The system currently predicts but cannot respond to predictions. A carefully scoped exception would allow pattern anticipation to influence *delivery* without overriding *content*:

**What soft steering can adjust:**
- DHA tone (warmth, directness, formality) -- presentation, not substance
- Kosha depth guidance (suggest deeper/shallower processing) -- not binding
- Response framing (acknowledge vs. challenge) -- style, not facts

**What soft steering CANNOT adjust:**
- Factual content or reasoning chain
- Persona selection or persona parameters
- TTOR routing or mapper activation
- Confidence gates or escalation decisions
- Any decision that was previously gated by P35/P36/P37

**Proposed invariant:**
- `INV-P38-5`: Soft steering adjustments are bounded to DHA tone parameters only
- `INV-P38-6`: Soft steering is logged as a separate audit trail entry with full provenance
- `INV-P38-7`: Soft steering can be globally disabled via `CrossDomainConfig.soft_steering_enabled` flag

**Implementation**: Soft steering emits a `SoftSteeringHint` dataclass that the DHA engine may consume but is never required to obey:

```python
@dataclass(frozen=True)
class SoftSteeringHint:
    """Non-binding delivery hint from pattern anticipation.

    The DHA engine MAY consume this hint to adjust tone.
    The DHA engine MUST NOT treat this as a directive.

    INV-P38-5: Only DHA tone parameters may be hinted.
    INV-P38-6: Every hint is logged with full provenance.
    """
    reason: str                    # e.g. "suppression_escalation sequence 2/3 steps matched"
    suggested_warmth_delta: float  # -0.2 to +0.2 adjustment to DHA warmth
    suggested_directness_delta: float
    source_pattern: str            # which pattern/sequence triggered this
    source_confidence: float       # confidence of the triggering detection
    is_anticipatory: bool          # True if based on partial sequence / trajectory
```

---

## 5. Integration Map

### 5.1 File Dependencies

```
NEW FILES:
    temporal/cross_domain_pattern_tracker.py  (Capabilities 1-4)
    temporal/pattern_sequence_rules.py        (Sequence grammar definitions)
    temporal/pattern_aspect_derivation.py     (Capability 6 aspect wiring)

MODIFIED FILES (additive only):
    temporal/__init__.py                      (export new classes)
    temporal/cross_domain_intelligence.py     (no changes -- consumed as-is)
    core/predictive/persona_drift/
        drift_trend_analyzer.py               (add optional pattern_instability to SignalSnapshot)
    core/stitching/domain_distance.py         (wire aspect vectors to get_domain_distance_with_context)
    ontology/backbone/cross_domain_config.py  (add soft_steering_enabled flag)
```

### 5.2 Data Flow After Integration

```
Raw Signals (per turn)
    │
    ├──→ P35 Drift Trend Analyzer ←─── pattern_instability_signal (NEW)
    │         │
    │         └──→ predicted_drift_score
    │
    ├──→ P36 Identity Resonance Memory
    │         └──→ persistence, volatility
    │
    ├──→ P37 Adaptive Continuity
    │         └──→ continuity_mode, continuity_pressure
    │
    └──→ P38 Cross-Domain Pattern Tracker (NEW)
              │
              ├── CDI classification (existing, unchanged)
              │
              ├── Lifecycle events: onset / sustain / exit / recurrence
              │
              ├── Boundary proximity + trajectory ETA
              │     └── "risk_hiding forming, ETA ~2 turns"
              │
              ├── Pattern persistence + volatility + stability band
              │
              ├── Sequence matching (partial + full)
              │     └── "suppression_escalation: 2/3 steps, next: chronic_stress"
              │
              ├── Aspect vector derivation + temporal tracking
              │
              ├──→ pattern_instability_signal → P35 (feedback loop)
              │
              └──→ SoftSteeringHint → DHA (optional, non-binding)
                    ├── warmth_delta
                    └── directness_delta
```

---

## 6. Testing Strategy

### 6.1 Unit Tests (Mirror Existing Patterns)

Follow the structure of `tests/unit/temporal/test_cross_domain_intelligence.py`:

```
tests/unit/temporal/test_cross_domain_pattern_tracker.py
    TestPatternLifecycle
        test_onset_detected_on_first_appearance
        test_sustain_on_consecutive_turns
        test_exit_when_pattern_disappears
        test_recurrence_after_gap
        test_no_events_on_empty_window

    TestBoundaryProximity
        test_distance_zero_when_inside_range
        test_distance_positive_when_outside
        test_approaching_detected_with_negative_slope
        test_receding_detected_with_positive_slope
        test_eta_computed_from_slope

    TestPatternPersistenceVolatility
        test_high_persistence_for_stable_pattern
        test_low_persistence_for_flickering_pattern
        test_volatility_zero_when_no_changes
        test_volatility_high_when_many_changes
        test_stability_band_classification

    TestSequenceDetection
        test_full_sequence_match
        test_partial_sequence_match
        test_gap_too_large_breaks_sequence
        test_confidence_below_threshold_filtered
        test_multiple_sequences_can_match

    TestP35Integration
        test_pattern_instability_signal_range
        test_instability_increases_with_volatility
        test_instability_increases_with_escalation

    TestSoftSteering
        test_hint_emitted_for_escalation_sequence
        test_no_hint_for_stable_patterns
        test_hint_bounded_to_dha_parameters
        test_hint_logged_with_provenance
```

### 6.2 Invariant Tests

```
tests/unit/temporal/test_p38_invariants.py
    test_inv_p38_1_deterministic_same_input_same_output
    test_inv_p38_2_observer_only_no_state_modification
    test_inv_p38_3_no_ml_no_llm
    test_inv_p38_4_window_bounded
    test_inv_p38_5_soft_steering_dha_only
    test_inv_p38_6_soft_steering_logged
    test_inv_p38_7_soft_steering_disableable
```

---

## 7. Governance Constraints

| Constraint | Mechanism | Enforcement |
|-----------|-----------|-------------|
| **Deterministic** | All formulas are pure arithmetic, no random, no LLM | Unit tests verify same-input-same-output |
| **Observer-only** | P38 emits reports and hints, never modifies upstream state | Invariant test: no write to P35/P36/P37 state |
| **Bounded adaptation** | Threshold adjustment max ±0.10, floor 0.50 | Assert in `get_context_adjusted_threshold` |
| **Soft steering optional** | `SoftSteeringHint` is non-binding, DHA may ignore | Flag: `soft_steering_enabled` in `CrossDomainConfig` |
| **Audit trail** | Every lifecycle event, sequence match, and hint logged | JSONL append-only log with monotonic sequence |
| **Locked formulas** | Weights and thresholds are constants, not learned | Constants defined at module level, not configurable at runtime |
| **No acoustic dependency** | P38 takes CDI signals only, not P22-P24 | No import from acoustic modules (INV-P35-5 extended) |

---

## 8. Implementation Phases

### Phase A: Stateful Pattern Tracker (Capabilities 1 + 3)
- `CrossDomainPatternTracker` with sliding window
- Pattern lifecycle events (onset/sustain/exit/recurrence)
- Pattern persistence and volatility metrics
- Unit tests mirroring `test_cross_domain_intelligence.py` structure
- **No changes to existing modules**

### Phase B: Boundary Distance and Trajectory (Capability 2)
- Boundary proximity computation
- Linear regression-based ETA estimation
- "Approaching pattern X, ~N turns" signal
- **No changes to existing modules**

### Phase C: Pattern Sequence Grammar (Capability 4)
- Predefined sequence rules (7 initial sequences)
- Partial and full sequence matching
- Anticipation signal: "sequence forming, N/M steps matched"
- **No changes to existing modules**

### Phase D: P35 Bidirectional Integration (Capability 5)
- Pattern instability signal → P35 SignalSnapshot
- Drift forecast → CDI threshold adaptation
- **First modification to existing module**: `drift_trend_analyzer.py`

### Phase E: Aspect Wiring (Capability 6)
- Derive aspect vectors from CDI input signals
- Wire to `get_domain_distance_with_context()`
- Temporal aspect tracking in sliding window
- **Modification**: `domain_distance.py` integration

### Phase F: Soft Steering (Requires Governance Approval)
- `SoftSteeringHint` emission
- DHA tone integration
- Audit trail logging
- Global disable flag
- **Modification**: `cross_domain_config.py`, DHA engine consumption point

---

## 9. Success Criteria

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Pattern detection latency | Turn N (post-hoc) | Turn N-2 to N-1 (anticipatory) | Boundary proximity + trajectory ETA |
| Sequence recognition | Not possible | 7 predefined sequences with partial matching | Sequence match rate on synthetic test conversations |
| Pattern persistence tracking | Not possible | Per-pattern persistence + volatility + stability band | New metrics emitted per turn |
| P35 drift prediction enrichment | 6 input signals | 7 signals (+ pattern_instability) | Compare P35 accuracy with/without pattern signal |
| False positive rate | N/A (no anticipation) | < 15% of anticipatory signals are false positives | Track predictions vs. actual pattern onset |
| Determinism | 100% | 100% (no regression) | Invariant test suite |
| Test coverage | CDI: unknown | P38: >= 80% | pytest coverage report |

---

## 10. Innovative Solutions and Industry Best Practices

This section documents the novel approaches in the P38 design and how they relate to (and differentiate from) established best practices in real-time pattern recognition, temporal reasoning, and cross-domain transfer learning.

---

### 10.1 Innovation: Signal-Space Trajectory Prediction Without ML

**The industry standard**: Real-time pattern anticipation in production systems typically requires trained ML models -- HMMs, LSTMs, or transformer-based sequence classifiers -- that learn transition probabilities from labeled data. This creates three problems: (a) training data for pattern *transitions* is scarce and expensive to label, (b) the models are opaque (which dimension drove the prediction?), and (c) they degrade unpredictably on out-of-distribution inputs.

**P38's approach**: Instead of learning transition probabilities, P38 computes *geometric trajectory through signal space* using linear regression on boundary distances (Section 3.3). The signal's path toward a pattern region is computed from its distance to that region's boundary over the sliding window. No training data required. Fully explainable: "SMI decreased at 0.06/turn for 3 turns; at current rate, enters risk_hiding range in ~2 turns."

**Why this is better for governed systems**: The trajectory is deterministic, auditable, and requires no training data. The tradeoff is precision -- linear regression cannot model nonlinear trajectories. But for governed, safety-critical systems where explainability outranks raw accuracy, this is the correct engineering choice. The same philosophy drives P35's drift prediction (weighted formula, not learned model) and P36's persistence scoring (variance, not LSTM hidden state).

**Best practice alignment**:
- **Explainability-first design** (EU AI Act Article 13, FDA AI/ML guidance): Every anticipatory signal decomposes into slope, distance, and window size
- **Conservative prediction** (safety engineering principle): Linear extrapolation underestimates nonlinear acceleration, which means false negatives are more likely than false positives -- the safe failure mode for a governed system
- **Zero cold-start problem**: Works from the first 2 turns (minimum for regression), unlike ML models that require convergence

---

### 10.2 Innovation: Pattern Lifecycle as First-Class Events

**The industry standard**: Most pattern recognition systems output a classification per timestep. State transitions are computed post-hoc by comparing consecutive outputs. The "onset" of a pattern is an inference by the consumer, not a signal from the detector.

**P38's approach**: Pattern lifecycle events (onset, sustain, exit, recurrence) are first-class `PatternEvent` objects emitted by the tracker (Section 3.2). Each event carries its own metadata: dwell_turns, gap_turns, confidence at transition point. The detector doesn't just say "pattern X is active" -- it says "pattern X entered 3 turns ago, has been sustained for 3 turns at average confidence 0.71, and this is a recurrence (gap: 2 turns since last active)."

**Why this matters**: Event-driven architectures process transitions, not states. Lifecycle events enable:
- **Alerting**: "Pattern X just entered" is actionable; "Pattern X is active" (for the 5th turn in a row) is noise
- **Sequence grammar**: Sequences match on events, not states -- "onset of B after sustain of A" is a different signal than "A and B both active"
- **Recurrence detection**: A pattern that keeps returning after exits is qualitatively different from one that appears once, but CDI's current stateless design treats them identically

**Best practice alignment**:
- **Event sourcing pattern** (Martin Fowler): State is derived from an append-only event log, not stored directly. This enables replay, audit, and temporal queries ("what was the pattern landscape 5 turns ago?")
- **Complex Event Processing (CEP)**: Industry standard for real-time pattern detection in financial trading, network intrusion detection, and IoT monitoring. P38 adapts CEP principles to cognitive state monitoring

---

### 10.3 Innovation: Deterministic Sequence Grammar for Pattern Anticipation

**The industry standard**: Sequence pattern mining typically uses algorithms like PrefixSpan, GSP, or neural sequence models. These require historical data to discover patterns and produce probabilistic predictions.

**P38's approach**: Pattern sequences are **hand-curated, named, and frozen** as `PatternSequenceRule` objects (Section 3.5). The 7 initial sequences (suppression_escalation, entrenchment_spiral, productive_resolution, etc.) encode domain expertise about meaningful pattern trajectories. Matching is greedy forward-scan with deterministic gap tolerance.

**The key innovation is partial matching**: When 2 of 3 steps in a sequence are matched, the system knows *which pattern would complete the sequence* and can check boundary proximity to that pattern (Section 3.3). This is how anticipation works without ML:

```
Step 1: Detect that acute_anxiety → emotional_masking has occurred (2/3 of suppression_escalation)
Step 2: Check boundary distance to chronic_stress (the 3rd step)
Step 3: If boundary distance is shrinking, emit anticipation signal:
        "suppression_escalation forming, 2/3 steps matched, chronic_stress approaching ETA ~2 turns"
```

**Why this is novel**: The combination of frozen sequence grammar + partial matching + geometric trajectory creates a prediction pipeline that is fully deterministic, requires zero training data, and provides explainable anticipation signals. Each component alone is a known technique; their composition for governed real-time pattern anticipation is the innovation.

**Best practice alignment**:
- **Domain-Driven Design (DDD)**: Sequences encode domain expertise in a structured, testable format -- same principle as bounded contexts and aggregates
- **Finite State Machines (FSM)**: Each sequence is implicitly an FSM where steps are states and gap_turns is the transition timeout. FSMs are the gold standard for safety-critical state management (avionics, medical devices)
- **Defensive programming**: max_gap_turns prevents stale partial matches from persisting indefinitely; min_confidence prevents low-quality matches from triggering false anticipation

---

### 10.4 Innovation: Bidirectional Observer-Prediction Loop

**The industry standard**: Observer/predictor systems are typically unidirectional: observers collect data, predictors consume it. Feedback loops exist in control theory (PID controllers) but are rare in cognitive/NLP systems because they risk unstable oscillation.

**P38's approach**: The `pattern_instability_signal` feeds from P38 back to P35 (Section 3.6), creating a loop:

```
P35 → drift_forecast → P38 → pattern_instability → P35 (next turn)
```

**Why this doesn't oscillate**: Two safeguards prevent feedback-induced instability:
1. **One-turn delay**: P38's instability signal is computed from the current turn's patterns but consumed by P35 on the *next* turn. This breaks the instantaneous feedback loop.
2. **Bounded influence**: The instability signal is one of 7 inputs to P35, weighted alongside 6 existing signals. Even if the signal oscillates, its influence is diluted by the other signals' stability.

**The threshold adaptation** (P35 drift_forecast → CDI threshold) is similarly bounded: maximum ±0.10 adjustment with a hard floor at 0.50 (Section 3.6). This prevents runaway threshold collapse where lowered thresholds cause more pattern detections, which cause higher instability, which causes even lower thresholds.

**Best practice alignment**:
- **Control theory stability**: One-turn delay + bounded gain = stable feedback loop (Nyquist criterion satisfied for discrete systems with gain < 1.0)
- **Graceful degradation**: If the feedback loop produces unexpected behavior, disabling `pattern_instability` from the P35 snapshot returns the system to its proven pre-P38 behavior with zero code changes
- **Circuit breaker pattern** (Michael Nygard, "Release It!"): The 0.50 threshold floor acts as a circuit breaker -- the system can adapt within bounds but cannot cascade past a safety limit

---

### 10.5 Innovation: Aspect-Mediated Cross-Domain Transfer

**The industry standard**: Cross-domain transfer in NLP typically relies on shared embedding spaces (domain adaptation, multi-task learning) or fine-tuning on target domain data. These approaches are effective but opaque: it's unclear *which aspects* of the source domain transferred and *why* the transfer was valid.

**P38's approach**: The 10 `UNIVERSAL_ASPECTS` (ENTROPY, CAUSALITY, AGENCY, BALANCE, FLOW, CONSTRAINT, EMERGENCE, FEEDBACK, HIERARCHY, THRESHOLD) are derived from the same input signals that CDI already uses (Section 3.7). Each aspect is a deterministic function of (smi, bhava_id, bhava_direction, kosha_id, ontology_id).

**The innovation** is using these aspect vectors as *temporal pattern fingerprints*: instead of tracking "is risk_hiding active?" over time, track "how is the ENTROPY-AGENCY-BALANCE aspect profile evolving?" over time. Two signals from different domains that share the same aspect trajectory are structurally analogous even if their domain-specific interpretations differ.

**Example**: A finance conversation where ENTROPY is rising while AGENCY is falling has the same aspect fingerprint as a medical conversation where diagnostic uncertainty increases while patient autonomy decreases. CDI can surface this structural analogy through `get_aspect_overlap()` without needing domain-specific training.

**Best practice alignment**:
- **Feature disentanglement** (representation learning): Aspects decompose the signal space into interpretable, orthogonal dimensions -- same goal as beta-VAE or InfoGAN, achieved without neural training
- **Ontological grounding** (knowledge engineering): Aspects are grounded in a curated ontology, not learned from data. This makes them stable across domains and robust to distribution shift
- **Transfer learning theory** (Ben-David et al.): Successful domain transfer requires low divergence in a shared representation space. Aspect vectors are that shared space, and `get_aspect_overlap()` measures the divergence

---

### 10.6 Innovation: Soft Steering with Governance Guarantees

**The industry standard**: When a prediction system detects a forming pattern, two options exist: (a) alert a human operator, or (b) automatically intervene. Option (a) is safe but slow. Option (b) is fast but risky -- automated interventions in cognitive systems can cause iatrogenic harm (the intervention makes things worse).

**P38's approach**: Soft steering (Section 4.2) is a third path: the system emits a *non-binding hint* that adjusts *delivery tone* (warmth, directness) without changing *content* (facts, reasoning). The hint is:
- **Bounded**: ±0.20 maximum adjustment to any DHA parameter
- **Optional**: The DHA engine may ignore it (MAY, not MUST)
- **Logged**: Every hint produces an audit trail entry with full provenance
- **Disableable**: Global flag in `CrossDomainConfig`
- **Content-inert**: Cannot modify factual content, persona, routing, or gating decisions

**Why this is novel**: The separation of *content* (what you say) from *delivery* (how you say it) allows the system to respond to anticipated patterns without the risks of content-level intervention. If the system detects a `suppression_escalation` sequence forming, it can slightly increase warmth and decrease directness in delivery -- creating space for the user to self-disclose -- without changing the factual substance of the response.

**Best practice alignment**:
- **Principle of least authority (POLA)**: Soft steering has the minimum permissions needed: DHA tone only, bounded range, non-binding
- **Nudge theory** (Thaler & Sunstein): Subtle environmental adjustments that preserve choice while guiding toward better outcomes -- applied to conversational dynamics
- **Defense in depth**: Four independent safeguards (bounded range + optional consumption + audit logging + global disable) ensure that any single failure cannot cause unintended steering

---

### 10.7 Best Practice: Formula Locking and Governance Versioning

P38 follows the established Symbol-U governance pattern from P35/P36/P37:

**Locked formulas**: All weights and thresholds are module-level constants, not runtime-configurable parameters. This eliminates an entire class of production incidents (misconfigured threshold causes false positive flood) at the cost of requiring a code change to adjust parameters.

**Invariant enforcement**: Each module has numbered invariants (INV-P38-1 through INV-P38-7) with corresponding unit tests. The invariant tests run in CI and block deployment on failure.

**Version pinning**: `P38_VERSION` constant enables consumers to assert compatibility. If the formula changes, the version changes, and downstream consumers must explicitly acknowledge the change.

**Observer-only by default**: New capabilities start as observer-only. They must demonstrate stable behavior before being granted any influence over system output. Soft steering (Section 4.2) requires separate governance approval precisely because it crosses the observer boundary.

**Best practice alignment**:
- **Immutable infrastructure** (HashiCorp principle): Locked formulas are the cognitive equivalent of immutable deployments -- change by replacement, not mutation
- **Change management** (ITIL): Version pinning + invariant tests + governance review = structured change control for cognitive algorithms
- **Safety Integrity Levels (IEC 61508)**: The escalating permission model (observer → soft steering → hard steering) mirrors SIL levels where higher influence requires higher assurance

---

### 10.8 Best Practice: Composable, Testable Architecture

P38's modular design enables incremental adoption:

**Zero-dependency phases**: Implementation Phases A through C require NO changes to existing modules. `CrossDomainPatternTracker` consumes `CrossDomainIntelligence` as a black box. This means P38 can be developed, tested, and deployed alongside the existing system without risk of regression.

**Additive-only modifications**: Phases D and E add optional fields (not required fields) to existing data structures. The `pattern_instability` signal in `SignalSnapshot` is `Optional[float]` -- existing code that doesn't provide it continues to work identically.

**Feature flags**: Soft steering (Phase F) is behind a global flag. The entire P38 module can be present in the codebase but dormant until governance approves activation.

**Best practice alignment**:
- **Strangler fig pattern** (Martin Fowler): New capabilities wrap existing ones without replacing them, allowing gradual migration
- **Feature toggles** (Pete Hodgson): Governance-controlled flags separate deployment from release
- **Contract testing**: Each phase defines its inputs, outputs, and invariants as a contract that upstream and downstream modules can test against independently

---

### 10.9 Anti-Patterns Deliberately Avoided

| Anti-Pattern | Why It's Tempting | Why P38 Avoids It |
|---|---|---|
| **Learned transition probabilities** | Higher accuracy on in-distribution data | Requires training data that doesn't exist for cognitive pattern transitions; opaque; degrades unpredictably |
| **Continuous threshold adaptation** | More responsive to context | Unbounded adaptation risks positive feedback loops and threshold collapse; hard to audit |
| **Direct content intervention** | More impactful response to anticipated patterns | Violates observer-only principle; risk of iatrogenic harm; regulatory exposure |
| **Global shared mutable state** | Simpler data flow | Race conditions in concurrent conversations; impossible to test deterministically |
| **Pattern discovery from data** | Scalable beyond 13 patterns | Discovered patterns lack interpretability guarantees; may encode biases from training data; violates locked-formula principle |
| **Real-time ML inference** | Richer predictions | Latency variance; non-deterministic outputs; GPU dependency; deployment complexity |
| **Over-parameterization** | Tunable system | Every tunable parameter is a production incident waiting to happen; prefer locked constants with governance-controlled versioned updates |

---

### 10.10 Comparison to Industry Systems

| System | Approach | P38 Differentiator |
|--------|----------|-------------------|
| **AWS Lookout for Metrics** | ML-based anomaly detection with auto-grouping | P38 uses deterministic formulas, not learned anomaly bounds; patterns are curated, not discovered |
| **Datadog Watchdog** | ML correlation of metrics + events | P38 operates on cognitive signals (SMI, bhava, kosha), not infrastructure metrics; lifecycle events are first-class |
| **Google Cloud TSMIXER** | Transformer-based time series forecasting | P38 uses linear regression by design -- simpler, deterministic, explainable; trades accuracy for auditability |
| **Palantir Foundry Ontology** | Semantic graph with temporal queries | P38's aspect vectors serve a similar role to ontology properties but are derived deterministically from signals, not curated per-object |
| **Salesforce Einstein** | ML-driven next-best-action | P38 soft steering is non-binding and bounded; Einstein directly drives recommendations with full authority |

The consistent differentiator: P38 optimizes for **governed explainability** over **raw predictive power**. In domains where trust and auditability outweigh accuracy (healthcare, finance, legal, education -- the 6 CDI target domains), this is the correct engineering tradeoff.

---

*Design document for Symbol-U Architecture Team*
*February 2026*
