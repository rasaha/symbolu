# Phase -1 Session Context Architecture

**Version**: 1.0
**Date**: 2025-12-20
**Status**: Implemented

## Overview

This document describes the Session Context Tracker (PO1.S) architecture, which provides session-level context accumulation for enhanced query disambiguation in Phase -1 (PO1) processing.

Modern LLM systems benefit from tracking session history to inform current query interpretation. This feature addresses the need for:

1. **Query Projection**: Using prior grounding decisions to inform disambiguation of new queries
2. **Domain Accumulation**: Tracking explored topics/domains within a session
3. **Persona Modeling**: Building understanding of user communication patterns
4. **Event History**: Remembering conversation events for reference resolution

## Architecture

### Component Hierarchy

```
Phase -1 Pipeline (PO1)
├── PO1.0: Observer-Observed Grounding (OOG)
├── PO1.1: Ambiguity Resolver (ARL)
├── PO1.2: Conservative Clause Splitter (CSL)
├── PO1.F: Fuzzy Query Classifier (FQC)  ← Per-query fuzzy signals
└── PO1.S: Session Context Tracker (SCT) ← Session-level accumulation
```

### Data Flow

```
                    ┌─────────────────────────────────────────────────────┐
                    │                   SessionContext                    │
                    │  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐  │
                    │  │   Domain    │ │   Persona    │ │    Prior     │  │
                    │  │ Accumulator │ │   Signals    │ │ Projections  │  │
                    │  └─────────────┘ └──────────────┘ └──────────────┘  │
                    └───────────┬───────────────────────────────┬─────────┘
                                │                               │
                                ▼                               │
    Query ──▶ FuzzyQueryClassifier ──▶ SessionAwareFuzzySignals │
                                              │                 │
                                              ▼                 │
                                       AmbiguityResolver        │
                                              │                 │
                                              ▼                 │
                                     ClauseGroundingResult ─────┘
                                              │            (recorded)
                                              ▼
                                     PhaseMinusOneEnvelope
```

## Components

### 1. SessionContext

Main container for session state. Thread-safe, stateful across queries.

```python
@dataclass
class SessionContext:
    session_id: str
    created_at: float
    domain_accumulator: DomainAccumulator
    persona_signals: PersonaSignals
    prior_projections: PriorGroundingProjection
    events: Deque[SessionEvent]
    query_count: int
    clarification_count: int
    ambiguity_count: int
```

**Key Methods:**
- `create()`: Factory method to create new session
- `record_query()`: Record incoming query with fuzzy signals
- `record_grounding_result()`: Record grounding decision
- `get_context_confidence_adjustment()`: Get session-based confidence modifier
- `get_likely_mode_from_context()`: Infer likely mode from history

### 2. DomainAccumulator

Tracks domain exploration within session.

```python
@dataclass
class DomainAccumulator:
    domain_counts: Dict[DomainCategory, int]
    domain_sequence: Deque[DomainCategory]  # Recent domains
    domain_keywords: Dict[DomainCategory, Set[str]]
    primary_domain: Optional[DomainCategory]
    domain_affinity: Dict[DomainCategory, float]
```

**Domain Categories:**
- `EMOTIONAL`: Feelings, mood, mental state
- `RELATIONAL`: Relationships, social dynamics
- `PROFESSIONAL`: Work, career, colleagues
- `HEALTH`: Physical/mental health
- `FINANCIAL`: Money, finances
- `PHILOSOPHICAL`: Meaning, purpose, values
- `PRACTICAL`: Tasks, logistics, planning

**Use Case:** When query contains "the issue" or "that problem", domain accumulator helps infer which domain is being referenced based on session history.

### 3. PersonaSignals

Accumulated communication patterns.

```python
@dataclass
class PersonaSignals:
    uses_first_person: float      # Frequency of "I" statements
    uses_emotional_language: float # Emotional word density
    question_ratio: float          # Questions vs statements
    avg_query_length: float        # Words per query
    emotional_baseline: float      # Session emotional level
    query_count: int
```

**Use Case:** User who consistently uses first-person emotional language is more likely to be in REFLEXIVE mode for ambiguous queries.

### 4. PriorGroundingProjection

Stores grounding decisions for projection.

```python
@dataclass
class PriorGroundingProjection:
    grounding_history: Deque[Dict[str, Any]]  # Last 20 groundings
    mode_counts: Dict[str, int]               # REFLEXIVE/RELATIONAL/DETACHED counts
    last_confident_grounding: Optional[Dict]  # Most recent confident result
    reflexive_streak: int                     # Consecutive reflexive groundings
    relational_streak: int                    # Consecutive relational groundings
```

**Use Case:** After 3 consecutive REFLEXIVE groundings, confidence is boosted (+0.08) for subsequent queries that appear reflexive.

### 5. SessionAwareFuzzySignals

Wrapper that combines per-query fuzzy signals with session context.

```python
@dataclass
class SessionAwareFuzzySignals:
    base_signals: FuzzyQuerySignals    # From FuzzyQueryClassifier
    session_adjustment: float          # Session-based adjustment
    session_mode_prior: Optional[str]  # Mode from history
    session_domain: Optional[DomainCategory]
    combined_adjustment: float         # Base + session (capped ±0.20)
    context_hints: List[str]           # Session-derived hints
```

## Confidence Adjustment Model

### Per-Query (FuzzyQueryClassifier)

| Factor | Adjustment Range |
|--------|-----------------|
| High intent score (≥0.7) | +0.10 |
| Moderate intent (≥0.5) | +0.05 |
| Low intent (<0.3) | -0.05 |
| High subject clarity (≥0.8) | +0.05 |
| Low subject clarity (≤0.3) | -0.08 |
| High pronoun ambiguity (≥0.6) | -0.07 |
| Low pronoun ambiguity (≤0.2) | +0.03 |
| High complexity (≥0.7) | -0.05 |

**Per-query range: [-0.15, +0.15]**

### Session Context

| Factor | Adjustment Range |
|--------|-----------------|
| First-person + emotional pattern | +0.05 |
| Consistent patterns (3+ queries) | +0.03 |
| Mode streak (≥3 consistent) | +0.08 |
| Mode streak (≥2 consistent) | +0.04 |
| High ambiguity rate (>50%) | -0.05 |

**Session range: [-0.10, +0.10]**

### Combined

Combined adjustment is capped at **±0.20** to prevent over-amplification.

## API Usage

### Stateless Mode (Original)

```python
pipeline = PhaseMinusOnePipeline()
envelope = pipeline.run("I feel anxious")
# No session context, per-query fuzzy only
```

### Session-Aware Mode

```python
session = SessionContext.create()
pipeline = PhaseMinusOnePipeline()

# First query - establishes context
env1 = pipeline.run_with_session("I feel anxious about my future", session)
# Session learns: emotional domain, reflexive mode, first-person pattern

# Second query - session informs disambiguation
env2 = pipeline.run_with_session("What should I do about that?", session)
# "that" can be resolved using prior context
# Session provides: +0.08 confidence boost from reflexive streak

# Third query - pattern reinforced
env3 = pipeline.run_with_session("I keep worrying about it", session)
# Context hints: ["session_queries_3", "reflexive_pattern", "domain_emotional"]
```

### Debug Output

Session context is included in envelope debug info:

```python
envelope.debug["session_context"] = {
    "session_id": "abc123",
    "query_count": 3,
    "domain_accumulator": {
        "primary_domain": "emotional",
        "domain_affinity": {"emotional": 0.8, "relational": 0.2}
    },
    "prior_projections": {
        "mode_prior": "REFLEXIVE",
        "reflexive_streak": 3,
    },
    "context_adjustment": +0.11
}
```

## Privacy Considerations

1. **No Cross-Session Persistence**: Sessions are ephemeral by default
2. **User Controls**: Application layer can clear/reset sessions
3. **Minimal Storage**: Only grounding-relevant patterns stored
4. **No Content Storage**: Query text in events is optional

## Future Enhancements

### 1. Persona Files

Persistent persona profiles across sessions:

```
PersonaFile
├── communication_style: Dict[str, float]
├── domain_preferences: Dict[DomainCategory, float]
├── typical_grounding_mode: str
└── last_session_summary: Dict
```

### 2. Reference Resolution

Explicit anaphora resolution using session context:

```python
def resolve_reference(self, pronoun: str) -> Optional[str]:
    """Resolve 'that', 'this issue', etc. to prior query content."""
    if pronoun in ["that", "this", "it"]:
        return self.prior_projections.last_confident_grounding["clause_text"]
```

### 3. Emotional Arc Tracking

Track emotional trajectory across session:

```python
@dataclass
class EmotionalArc:
    baseline: float           # Session start emotional level
    current: float            # Current emotional level
    trajectory: str           # "escalating", "stable", "de-escalating"
    peak_moment: Optional[SessionEvent]
```

### 4. Multi-Turn Disambiguation

Use prior clarifications to avoid repeating questions:

```python
def was_already_clarified(self, topic: str) -> bool:
    """Check if we've already asked about this topic."""
    for event in self.events:
        if event.event_type == EventType.CLARIFICATION:
            if topic in event.query_text:
                return True
    return False
```

## Integration Points

### With Phase 0 (P0)

Session context can inform P0 routing decisions:

```python
# P0 can access session to inform mode selection
if session.prior_projections.reflexive_streak >= 3:
    # Bias toward reflexive processing path
    pass
```

### With Phase 1+ (P1+)

Session domain can inform topic modeling:

```python
# P1 topic model can use session domain as prior
prior_topic = session.domain_accumulator.primary_domain
```

## File Locations

```
symbolu/mechanical/pipeline/grounding/
├── phase_minus_one_session.py      # Session context implementation
├── phase_minus_one_fuzzy.py        # Fuzzy query classifier
├── phase_minus_one_ambiguity.py    # Ambiguity resolver
├── phase_minus_one_pipeline.py     # Pipeline with run_with_session()
└── __init__.py                     # Exports all session classes
```

## Testing

Test session-aware pipeline:

```bash
python -c "
from symbolu.mechanical.pipeline.grounding import (
    PhaseMinusOnePipeline,
    SessionContext,
)

session = SessionContext.create()
pipeline = PhaseMinusOnePipeline()

# Simulate multi-turn conversation
queries = [
    'I feel anxious about my relationship',
    'She doesn\'t understand me',
    'What should I do about that?',
]

for q in queries:
    env = pipeline.run_with_session(q, session)
    print(f'{q} -> {env.clauses[0].grounding_status}')

print(f'Session context: {session.to_dict()}')
"
```

## Changelog

- **v1.0** (2025-12-20): Initial implementation
  - SessionContext, DomainAccumulator, PersonaSignals, PriorGroundingProjection
  - SessionAwareFuzzySignals wrapper
  - PhaseMinusOnePipeline.run_with_session() method
  - Integration with existing FuzzyQueryClassifier
