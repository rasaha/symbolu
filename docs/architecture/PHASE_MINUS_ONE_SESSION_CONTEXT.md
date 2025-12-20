# Phase -1 Session Context Architecture

**Version**: 2.1
**Date**: 2025-12-20
**Status**: Implemented

## Overview

This document describes the Session Context Tracker (PO1.S) architecture, which provides session-level context accumulation for enhanced query disambiguation in Phase -1 (PO1) processing.

Modern LLM systems benefit from tracking session history to inform current query interpretation. This feature addresses the need for:

1. **Query Projection**: Using prior grounding decisions to inform disambiguation of new queries
2. **Domain Accumulation**: Tracking explored topics/domains within a session
3. **Persona Modeling**: Building understanding of user communication patterns
4. **Event History**: Remembering conversation events for reference resolution

## Phase Boundary Contract

**Critical**: Phase -1 outputs are **HYPOTHESES**, not commitments.

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE BOUNDARY CONTRACT                      │
├─────────────────────────────────────────────────────────────────┤
│ 1. All Phase -1 outputs are PROVISIONAL                        │
│ 2. Downstream phases MUST treat them as hypotheses             │
│ 3. Session context NARROWS possibilities, never DETERMINES     │
│ 4. Resolution bias affects TIE-BREAKING only                   │
│ 5. Any phase can override Phase -1 with sufficient evidence    │
└─────────────────────────────────────────────────────────────────┘
```

This contract ensures that:
- Phase -1 cannot "lock in" interpretations prematurely
- Later phases maintain full authority to reinterpret
- Session influence is advisory, not prescriptive

## Key Design Principles (v2.1)

### 1. Constraint Narrowing (Not Confidence Boosting)

Instead of "boosting confidence" (which inflates certainty), the system uses **constraint narrowing** to eliminate unlikely interpretations.

**Old approach (v1.0):**
```
"+0.08 confidence due to reflexive streak"
```

**New approach (v2.0+):**
```
"Eliminated DETACHED mode due to reflexive_streak_3"
```

This makes reasoning more explainable and auditable.

### 1a. Constraint Types (NEW in v2.1)

Constraints are categorized as **HARD** or **SOFT**:

```python
class ConstraintType(str, Enum):
    HARD = "hard"   # Always applied, cannot be overridden
    SOFT = "soft"   # Ignored when base signals are strong (≥0.7)
```

| Type | Example | Override Behavior |
|------|---------|-------------------|
| HARD | User explicitly clarified | Never overridden |
| SOFT | Persona pattern suggests | Ignored if base signals strong |

### 1b. Constraint Resolution (NEW in v2.1)

Multiple constraints are combined via `ConstraintResolution`:

```python
@dataclass(frozen=True)
class ConstraintResolution:
    eliminated_modes: FrozenSet[str]      # Union of all eliminations
    surviving_modes: FrozenSet[str]       # What remains after elimination
    resolution_reason: str                 # Primary constraint reason
    is_overconstrained: bool              # True if no modes survive
    applied_constraints: Tuple[...]        # Constraints that were applied
    ignored_constraints: Tuple[...]        # Constraints ignored (soft + strong base)
```

**Over-constraining Detection:**
```python
if len(surviving_modes) == 0:
    # All modes eliminated - this is an error condition
    is_overconstrained = True
    # Fallback: ignore all constraints, use base signals only
```

### 2. Read-Only Projection Layer

Evidence accumulation is separated from decision influence via `SessionProjection`:

```
SessionContext (mutable, accumulates evidence)
      ↓
SessionProjection (frozen, read-only for decisions)
      ↓
AmbiguityResolver
```

This ensures:
- No mutation during decision-making
- Clear audit boundary
- Reproducible decisions

### 3. Exponential Decay on All Accumulators

All accumulators use exponential decay to prevent early queries from overweighting later ones:

```python
effective_weight = raw_weight * exp(-λ * age_in_queries)
# λ = ln(2) / DECAY_HALF_LIFE (default: 4 queries)
```

### 4. Contradiction Tracking

The system tracks when patterns break unexpectedly and suppresses session influence accordingly:

```python
if contradiction_count >= CONTRADICTION_THRESHOLD:  # default: 2
    session_influence = 0  # Suppressed
```

### 5. Hard Safety Constraints (Non-Permissions)

Explicit actions that SessionContext must NEVER perform:

```python
class SessionNonPermission(str, Enum):
    OVERRIDE_USER_CLARIFICATION = "override_user_clarification"
    INVENT_REFERENTS = "invent_referents"
    OVERRIDE_STRONG_BASE_SIGNALS = "override_strong_base_signals"
    CROSS_SESSION_PERSISTENCE = "cross_session_persistence"
    EXCEED_INFLUENCE_WINDOW = "exceed_influence_window"
    DERIVE_INTENT_BEYOND_QUERY = "derive_intent_beyond_query"  # NEW in v2.1
```

**NEW in v2.1**: `DERIVE_INTENT_BEYOND_QUERY` prevents the session from inferring user intent that goes beyond what is explicitly stated in the query. Session context can narrow possibilities but cannot fabricate intent.

### 6. Typed Suppression Causes (NEW in v2.1)

Suppression is now a first-class state with typed causes:

```python
class SuppressionCause(str, Enum):
    CONTRADICTION_THRESHOLD = "contradiction_threshold"   # Too many pattern breaks
    INSUFFICIENT_HISTORY = "insufficient_history"         # Not enough data
    STRONG_BASE_SIGNALS = "strong_base_signals"           # Base signals override
    OVERCONSTRAINED = "overconstrained"                   # All modes eliminated
    USER_CLARIFICATION = "user_clarification"             # User explicitly clarified
```

This enables:
- Analytics on why session influence was suppressed
- Debugging of unexpected behavior
- Pattern detection across sessions

### 7. Resolution Bias as Tie-Breaking Only (NEW in v2.1)

Resolution bias (`-0.20` to `+0.20`) is **strictly for tie-breaking**:

```python
def should_apply_bias(self, candidate_mode_count: int) -> bool:
    """Resolution bias applies ONLY for tie-breaking."""
    return candidate_mode_count > 1 and not self.influence_suppressed
```

| Candidates | Bias Applied? | Reason |
|------------|---------------|--------|
| 1 mode | No | No tie to break |
| 2+ modes | Yes | Bias breaks the tie |
| Suppressed | No | Influence disabled |

### 8. Explicit Consistency Score Formula (NEW in v2.1)

The consistency score is computed with a documented formula:

```python
def _compute_consistency_score(self) -> float:
    """
    Explicit Formula:
        consistency = 1.0 - (
            contradiction_rate * 0.5 +
            mode_switch_rate * 0.3 +
            domain_switch_rate * 0.2
        )

    Where:
        contradiction_rate = contradictions / total_queries
        mode_switch_rate = mode_switches / (total_queries - 1)
        domain_switch_rate = domain_switches / (total_queries - 1)

    Returns:
        float: Consistency score in [0.0, 1.0]
               - 1.0 = Perfect consistency (no switches, no contradictions)
               - 0.0 = Maximum volatility
    """
```

## Architecture

### Component Hierarchy

```
Phase -1 Pipeline (PO1)
├── PO1.0: Observer-Observed Grounding (OOG)
├── PO1.1: Ambiguity Resolver (ARL)
├── PO1.2: Conservative Clause Splitter (CSL)
├── PO1.F: Fuzzy Query Classifier (FQC)  ← Per-query fuzzy signals
└── PO1.S: Session Context Tracker (SCT) ← Session-level accumulation
    ├── DomainAccumulator (with decay)
    ├── PersonaSignals (with EMA)
    ├── PriorGroundingProjection (with contradiction tracking)
    ├── SessionProjection (read-only decision layer)
    │   └── ConstraintResolution (NEW v2.1: constraint interaction)
    ├── SessionConstraintEffect (with ConstraintType: HARD/SOFT)
    ├── SuppressionCause (NEW v2.1: typed suppression reasons)
    └── SessionAuditLog (explainability)
```

### Data Flow (v2.1)

```
                    ┌─────────────────────────────────────────────────────┐
                    │                   SessionContext                    │
                    │  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐  │
                    │  │   Domain    │ │   Persona    │ │    Prior     │  │
                    │  │ Accumulator │ │   Signals    │ │ Projections  │  │
                    │  │ (w/ decay)  │ │  (w/ EMA)    │ │(w/ contradict)│  │
                    │  └─────────────┘ └──────────────┘ └──────────────┘  │
                    └───────────┬───────────────────────────────┬─────────┘
                                │                               │
                                ▼                               │
                      SessionProjection (frozen)                │
                         ├── constraints (HARD/SOFT)            │
                         ├── ConstraintResolution               │
                         └── SuppressionCause                   │
                                │                               │
                                ▼                               │
    Query ──▶ FuzzyQueryClassifier ──▶ SessionAwareFuzzySignals │
                                              │                 │
                          ConstraintResolution.resolve()        │
                          (combines, checks overconstrain)      │
                                              │                 │
                                              ▼                 │
                                       AmbiguityResolver        │
                               (bias = tie-breaking only)       │
                                              │                 │
                                              ▼                 │
                                     ClauseGroundingResult ─────┘
                                              │            (recorded + audit)
                                              ▼
                                     PhaseMinusOneEnvelope
                                       (HYPOTHESES, not commitments)
```

## Configuration Constants

```python
# Session influence window - only last N queries affect decisions
SESSION_INFLUENCE_WINDOW: int = 5

# Decay half-life for accumulator weights (in query count)
DECAY_HALF_LIFE: int = 4

# Contradiction threshold - suppress session influence after N contradictions
CONTRADICTION_THRESHOLD: int = 2

# Maximum resolution bias magnitude
MAX_RESOLUTION_BIAS: float = 0.20

# Base signal disagreement threshold - when to ignore session influence
BASE_SIGNAL_OVERRIDE_THRESHOLD: float = 0.7
```

## Components

### 1. SessionContext

Main container for session state. Stateful across queries.

```python
@dataclass
class SessionContext:
    session_id: str
    created_at: float
    domain_accumulator: DomainAccumulator
    persona_signals: PersonaSignals
    prior_projections: PriorGroundingProjection
    events: Deque[SessionEvent]
    audit_log: Deque[SessionAuditEntry]  # NEW in v2.0
    query_count: int
    clarification_count: int
    ambiguity_count: int
```

**Key Methods:**
- `create()`: Factory method to create new session
- `record_query()`: Record incoming query with fuzzy signals
- `record_grounding_result()`: Record grounding decision with resolution source
- `create_projection()`: **NEW** - Create read-only projection for decisions
- `generate_summary()`: **NEW** - Generate end-of-session analytics
- `record_audit()`: **NEW** - Record audit entry

### 2. SessionProjection (v2.1)

Read-only, frozen projection for decision-making:

```python
@dataclass(frozen=True)
class SessionProjection:
    dominant_domain: Optional[DomainCategory]
    dominant_mode: Optional[str]
    consistency_score: float  # 0.0-1.0

    # Constraints to apply (replaces confidence boost)
    constraints: Tuple[SessionConstraintEffect, ...]

    # Constraint resolution (NEW in v2.1)
    constraint_resolution: ConstraintResolution  # Combined constraint analysis

    # Resolution bias (renamed from confidence_adjustment)
    resolution_bias: float  # [-0.20, +0.20]

    # Suppression tracking (UPDATED in v2.1)
    influence_suppressed: bool
    suppression_cause: Optional[SuppressionCause]  # Typed enum, not string

    constraint_summary: Tuple[str, ...]
    query_index: int

    # NEW in v2.1: Tie-breaking helper
    def should_apply_bias(self, candidate_mode_count: int) -> bool:
        """Resolution bias applies ONLY for tie-breaking."""
        return candidate_mode_count > 1 and not self.influence_suppressed
```

### 3. SessionConstraintEffect (v2.1)

Represents constraint narrowing instead of confidence boosting:

```python
@dataclass(frozen=True)
class SessionConstraintEffect:
    eliminated_modes: FrozenSet[str]       # e.g., {"DETACHED"}
    eliminated_domains: FrozenSet[DomainCategory]
    reason: str                            # e.g., "reflexive_streak_3"
    strength: float                        # 0.0-1.0
    constraint_type: ConstraintType        # NEW in v2.1: HARD or SOFT
```

**Constraint Type Behavior:**
- `HARD`: Always applied, cannot be overridden by base signals
- `SOFT`: Ignored when `base_signal_strength >= BASE_SIGNAL_OVERRIDE_THRESHOLD` (0.7)

### 3a. ConstraintResolution (NEW in v2.1)

Combines multiple constraints and detects over-constraining:

```python
@dataclass(frozen=True)
class ConstraintResolution:
    eliminated_modes: FrozenSet[str]       # Union of all eliminations
    surviving_modes: FrozenSet[str]        # Modes that survive elimination
    resolution_reason: str                  # Primary constraint reason
    is_overconstrained: bool               # True if no modes survive
    applied_constraints: Tuple[SessionConstraintEffect, ...]
    ignored_constraints: Tuple[SessionConstraintEffect, ...]

    @classmethod
    def resolve(cls, constraints: List[SessionConstraintEffect],
                base_signal_strength: float = 0.0) -> "ConstraintResolution":
        """
        Combine constraints, handling:
        1. Soft constraints ignored when base signals strong
        2. Over-constraining detection (no surviving modes)
        """
```

### 4. DomainAccumulator (with Decay)

Tracks domain exploration with exponential decay:

```python
@dataclass
class DomainAccumulator:
    domain_counts: Dict[DomainCategory, int]
    domain_timestamps: Dict[DomainCategory, List[float]]  # NEW
    domain_sequence: Deque[DomainCategory]
    domain_keywords: Dict[DomainCategory, Set[str]]
    primary_domain: Optional[DomainCategory]
    domain_affinity: Dict[DomainCategory, float]  # Decayed
    current_query_index: int  # NEW
```

### 5. PriorGroundingProjection (with Contradiction Tracking)

Stores grounding decisions with pattern break detection:

```python
@dataclass
class PriorGroundingProjection:
    grounding_history: Deque[Dict[str, Any]]
    mode_counts: Dict[str, int]
    last_confident_grounding: Optional[Dict]
    reflexive_streak: int
    relational_streak: int

    # Contradiction tracking (NEW)
    contradiction_count: int
    last_mode_switch_at: int
    recent_contradictions: Deque[int]
```

### 6. ResolutionSource (NEW in v2.0)

Tracks how ambiguity was resolved for traceability:

```python
class ResolutionSource(Enum):
    LEXICAL = "lexical"                     # Word-level features
    FUZZY_SIGNALS = "fuzzy_signals"         # Fuzzy classifier
    SESSION_PROJECTION = "session_projection"  # Session context
    EXPLICIT_CLARIFICATION = "explicit"     # User clarification
    SAFE_DEFAULT = "safe_default"           # Conservative fallback
```

### 7. SessionAuditEntry (NEW in v2.0)

Audit log for explainability:

```python
@dataclass
class SessionAuditEntry:
    decision_id: str
    timestamp: float
    query_index: int
    factors_used: List[str]
    factors_ignored: List[str]          # Silence is dangerous
    ignored_reasons: Dict[str, str]
    constraints_applied: List[SessionConstraintEffect]
    resolution_source: ResolutionSource
    resolution_bias_applied: float
    reason: str
```

### 8. SessionSummary (NEW in v2.0)

End-of-session analytics (not used for decisions):

```python
@dataclass
class SessionSummary:
    session_id: str
    duration_seconds: float
    query_count: int
    dominant_domain: Optional[DomainCategory]
    dominant_mode: Optional[str]
    ambiguity_rate: float
    clarification_rate: float
    volatility_score: float
    contradiction_rate: float
    consistency_score: float
```

## Constraint Narrowing Model (v2.0)

Instead of confidence adjustment, we use constraint elimination:

### Persona-Based Constraints

| Pattern | Constraint | Strength |
|---------|-----------|----------|
| High first-person + emotional | Eliminate DETACHED | 0.6 |
| Low emotional + high questions | Eliminate REFLEXIVE | 0.5 |

### Grounding History Constraints

| Pattern | Constraint | Strength |
|---------|-----------|----------|
| Reflexive streak ≥3 | Eliminate DETACHED | 0.7 |
| Reflexive streak ≥2 | Eliminate DETACHED | 0.5 |
| Relational streak ≥3 | Eliminate DETACHED | 0.7 |
| Relational streak ≥2 | Eliminate DETACHED | 0.5 |

### Suppression Rules

Session influence is **suppressed** when:
1. `contradiction_count >= CONTRADICTION_THRESHOLD` (default: 2)
2. Insufficient recent history in influence window
3. Query index exceeds window without enough data

## API Usage

### Session-Aware Mode (v2.0)

```python
session = SessionContext.create()
pipeline = PhaseMinusOnePipeline()

# First query - establishes context
env1 = pipeline.run_with_session("I feel anxious about my future", session)
# Session learns: emotional domain, reflexive mode

# Second query - constraints applied
env2 = pipeline.run_with_session("I keep worrying about everything", session)
# Constraint: Eliminated DETACHED due to reflexive_streak_2

# Third query - stronger constraints
env3 = pipeline.run_with_session("What should I do about that?", session)
# Constraint: Eliminated DETACHED due to reflexive_streak_3 (strength: 0.7)

# Get read-only projection
projection = session.create_projection()
print(f"Constraints: {[c.reason for c in projection.constraints]}")
print(f"Suppressed: {projection.influence_suppressed}")

# Generate end-of-session summary
summary = session.generate_summary()
print(f"Consistency: {summary.consistency_score}")
```

### Debug Output (v2.0)

```python
envelope.debug["session_context"] = {
    "session_id": "abc123",
    "query_count": 3,
    "consistency_score": 0.782,
    "current_projection": {
        "dominant_mode": "REFLEXIVE",
        "constraints": [
            {
                "eliminated_modes": ["DETACHED"],
                "reason": "reflexive_streak_3",
                "strength": 0.7
            }
        ],
        "resolution_bias": 0.105,
        "influence_suppressed": False
    }
}
```

## Safety Model

### Non-Permissions (Hard Constraints)

The system must NEVER:

1. **Override user clarification**: If user explicitly clarifies, session cannot contradict
2. **Invent referents**: Cannot create references not present in session history
3. **Override strong base signals**: If base fuzzy signals are strong (≥0.7), session cannot flip
4. **Persist across sessions**: No cross-session state without explicit opt-in
5. **Exceed influence window**: Only last N queries (default: 5) can influence

### Influence Suppression

Session influence is automatically suppressed when:

```python
# Too many contradictions in recent window
if sum(1 for c in recent_contradictions if within_window(c)) >= 2:
    influence_suppressed = True
    suppression_reason = "contradictions_exceeded_threshold"
```

### Audit Trail

Every session-influenced decision is logged:

```python
session.record_audit(SessionAuditEntry(
    decision_id="...",
    factors_used=["reflexive_streak", "emotional_pattern"],
    factors_ignored=["domain_affinity"],
    ignored_reasons={"domain_affinity": "below_threshold"},
    constraints_applied=[...],
    resolution_source=ResolutionSource.SESSION_PROJECTION,
    resolution_bias_applied=0.105,
    reason="reflexive_streak_3 eliminated DETACHED mode"
))
```

## Privacy Considerations

1. **No Cross-Session Persistence**: Sessions are ephemeral by default
2. **User Controls**: Application layer can clear/reset sessions
3. **Minimal Storage**: Only grounding-relevant patterns stored
4. **No Content Storage**: Query text in events is optional
5. **Audit for Compliance**: All decisions logged for review

## Future Enhancements

### 1. Persona Files

Persistent persona profiles (requires explicit opt-in):

```python
@dataclass
class PersonaFile:
    communication_style: Dict[str, float]
    domain_preferences: Dict[DomainCategory, float]
    typical_grounding_mode: str
    last_session_summary: SessionSummary
```

### 2. Emotional Arc Tracking

```python
@dataclass
class EmotionalArc:
    baseline: float
    current: float
    trajectory: Literal["escalating", "stable", "de-escalating"]
    peak_moment: Optional[SessionEvent]
```

### 3. Multi-Turn Clarification Memory

```python
def was_already_clarified(self, topic: str) -> bool:
    """Avoid repeating clarification questions."""
    return any(
        e.event_type == EventType.CLARIFICATION and topic in e.query_text
        for e in self.events
    )
```

## File Locations

```
symbolu/mechanical/pipeline/grounding/
├── phase_minus_one_session.py      # Session context (v2.1)
├── phase_minus_one_fuzzy.py        # Fuzzy query classifier
├── phase_minus_one_ambiguity.py    # Ambiguity resolver
├── phase_minus_one_pipeline.py     # Pipeline with run_with_session()
└── __init__.py                     # Exports all session classes
```

## Testing

```bash
python -c "
from symbolu.mechanical.pipeline.grounding import (
    PhaseMinusOnePipeline,
    SessionContext,
    SessionProjection,
    SESSION_INFLUENCE_WINDOW,
)

session = SessionContext.create()
pipeline = PhaseMinusOnePipeline()

# Test constraint narrowing
queries = [
    'I feel anxious about my future',
    'I keep worrying about everything',
    'What should I do about that?',
]

for q in queries:
    env = pipeline.run_with_session(q, session)
    print(f'{q}')
    print(f'  Mode: {env.clauses[0].selected.mode}')

projection = session.create_projection()
print(f'Constraints: {[c.reason for c in projection.constraints]}')
print(f'Consistency: {session._compute_consistency_score():.3f}')
"
```

## Changelog

- **v2.1** (2025-12-20): Constraint interaction and phase boundary refinements
  - Added ConstraintResolution for combining multiple constraints with over-constraining detection
  - Added ConstraintType enum (HARD/SOFT) for constraint classification
  - Added SuppressionCause enum for typed suppression reasons (analytics-friendly)
  - Added DERIVE_INTENT_BEYOND_QUERY non-permission
  - Resolution bias now explicitly for tie-breaking only (should_apply_bias method)
  - Explicit consistency score formula documented
  - Added Phase Boundary Contract defining Phase -1 outputs as hypotheses
  - Soft constraints ignored when base signals strong (≥0.7)
  - Over-constraining fallback: ignore all constraints when no modes survive

- **v2.0** (2025-12-20): Major improvements based on safety/robustness review
  - Replaced confidence boosting with constraint narrowing (SessionConstraintEffect)
  - Added SessionProjection read-only decision layer
  - Added exponential decay to all accumulators
  - Added contradiction tracking and influence suppression
  - Added ResolutionSource for traceability
  - Added SessionNonPermission hard safety constraints
  - Added SessionAuditEntry for explainability
  - Added SessionSummary for end-of-session analytics
  - Renamed confidence_adjustment to resolution_bias
  - Added session influence window (SESSION_INFLUENCE_WINDOW)

- **v1.0** (2025-12-20): Initial implementation
  - SessionContext, DomainAccumulator, PersonaSignals, PriorGroundingProjection
  - SessionAwareFuzzySignals wrapper
  - PhaseMinusOnePipeline.run_with_session() method
  - Integration with existing FuzzyQueryClassifier
