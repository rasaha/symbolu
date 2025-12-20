"""
PO1.S — Session Context Tracker (SCT)

Provides session-level context accumulation for Phase -1 disambiguation.

Modern LLM systems benefit from tracking:
1. Domain accumulation - Topics/domains explored in session
2. Event history - Conversation events and emotional arcs
3. User persona signals - Communication patterns observed
4. Prior query projections - Previous grounding decisions for inference

Design Philosophy:
- Stateful across queries within a session
- Informs (not replaces) per-query fuzzy classification
- Accumulates evidence for disambiguation
- Respects privacy boundaries (no cross-session persistence by default)

Integration:
- SessionContext feeds into FuzzyQueryClassifier as additional signals
- Prior grounding decisions inform current disambiguation
- Domain context helps resolve ambiguous references
"""

from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .phase_minus_one_schema import (
        ClauseGroundingResult,
        ObservationMode,
        GroundingCandidate,
    )
    from .phase_minus_one_fuzzy import QueryIntentHint, FuzzyQuerySignals


class DomainCategory(str, Enum):
    """Categories of domains that can be tracked in a session."""
    EMOTIONAL = "emotional"           # Feelings, mood, mental state
    RELATIONAL = "relational"         # Relationships, social dynamics
    PROFESSIONAL = "professional"     # Work, career, colleagues
    HEALTH = "health"                 # Physical/mental health
    FINANCIAL = "financial"           # Money, finances
    CREATIVE = "creative"             # Art, creativity, expression
    PHILOSOPHICAL = "philosophical"   # Meaning, purpose, values
    PRACTICAL = "practical"           # Tasks, logistics, planning
    UNKNOWN = "unknown"


class EventType(str, Enum):
    """Types of session events to track."""
    QUERY = "query"                   # User query submitted
    GROUNDING = "grounding"           # Grounding decision made
    CLARIFICATION = "clarification"   # Clarification requested
    EMOTIONAL_SHIFT = "emotional"     # Emotional intensity change
    TOPIC_SHIFT = "topic"             # Topic/domain change
    AMBIGUITY = "ambiguity"           # Ambiguous query detected


@dataclass
class SessionEvent:
    """
    Single event in session history.

    Captures what happened, when, and relevant context.
    """
    event_type: EventType
    timestamp: float
    query_text: Optional[str] = None
    domain: Optional[DomainCategory] = None
    intent: Optional[str] = None
    grounding_mode: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "query_text": self.query_text,
            "domain": self.domain.value if self.domain else None,
            "intent": self.intent,
            "grounding_mode": self.grounding_mode,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class DomainAccumulator:
    """
    Tracks domain exploration within a session.

    Accumulates evidence about which domains/topics have been discussed,
    helping resolve ambiguous references like "this issue" or "the problem".
    """
    # Domain visit counts
    domain_counts: Dict[DomainCategory, int] = field(default_factory=dict)

    # Recent domain sequence (for transition patterns)
    domain_sequence: Deque[DomainCategory] = field(
        default_factory=lambda: deque(maxlen=10)
    )

    # Keywords seen per domain
    domain_keywords: Dict[DomainCategory, Set[str]] = field(default_factory=dict)

    # Primary domain (most discussed)
    primary_domain: Optional[DomainCategory] = None

    # Domain affinity scores (0.0-1.0)
    domain_affinity: Dict[DomainCategory, float] = field(default_factory=dict)

    def record_domain(self, domain: DomainCategory, keywords: List[str] = None) -> None:
        """Record a domain visit with optional keywords."""
        self.domain_counts[domain] = self.domain_counts.get(domain, 0) + 1
        self.domain_sequence.append(domain)

        if keywords:
            if domain not in self.domain_keywords:
                self.domain_keywords[domain] = set()
            self.domain_keywords[domain].update(keywords)

        self._update_affinity()
        self._update_primary()

    def _update_affinity(self) -> None:
        """Update domain affinity scores based on visit frequency."""
        total = sum(self.domain_counts.values()) or 1
        for domain, count in self.domain_counts.items():
            # Affinity with recency bias
            recency_bonus = 0.0
            if self.domain_sequence and self.domain_sequence[-1] == domain:
                recency_bonus = 0.1
            self.domain_affinity[domain] = min(1.0, (count / total) + recency_bonus)

    def _update_primary(self) -> None:
        """Update primary domain based on highest count."""
        if self.domain_counts:
            self.primary_domain = max(
                self.domain_counts,
                key=self.domain_counts.get
            )

    def get_likely_domain(self, keywords: List[str] = None) -> Optional[DomainCategory]:
        """
        Infer likely domain for ambiguous query based on session context.

        Uses keyword overlap and domain affinity.
        """
        if not self.domain_counts:
            return None

        if keywords:
            # Check keyword overlap with known domains
            best_overlap = 0
            best_domain = None
            for domain, known_keywords in self.domain_keywords.items():
                overlap = len(set(keywords) & known_keywords)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_domain = domain
            if best_domain:
                return best_domain

        # Fall back to primary domain
        return self.primary_domain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_counts": {k.value: v for k, v in self.domain_counts.items()},
            "primary_domain": self.primary_domain.value if self.primary_domain else None,
            "domain_affinity": {k.value: v for k, v in self.domain_affinity.items()},
            "recent_sequence": [d.value for d in self.domain_sequence],
        }


@dataclass
class PersonaSignals:
    """
    Accumulated persona signals from session behavior.

    Tracks communication patterns to help interpret queries.
    """
    # Communication style indicators
    uses_first_person: float = 0.0      # Frequency of "I" statements
    uses_emotional_language: float = 0.0 # Emotional word density
    question_ratio: float = 0.0          # Questions vs statements
    avg_query_length: float = 0.0        # Average words per query

    # Behavioral patterns
    seeks_validation: float = 0.0        # Pattern of seeking reassurance
    analytical_tendency: float = 0.0     # Preference for analysis
    action_oriented: float = 0.0         # Focus on doing vs feeling

    # Session-level emotional trajectory
    emotional_baseline: float = 0.5      # 0=low, 1=high emotional content
    emotional_variance: float = 0.0      # How much emotion fluctuates

    # Query count for weighted updates
    query_count: int = 0

    def update_from_signals(self, signals: "FuzzyQuerySignals", query_text: str) -> None:
        """Update persona from new query signals."""
        self.query_count += 1
        n = self.query_count

        # Weighted rolling average
        def update_avg(old: float, new: float) -> float:
            return old + (new - old) / n

        # Update from fuzzy signals
        emotional_score = signals.intent_scores.get("emotional", 0.0) if hasattr(signals, 'intent_scores') else 0.0
        self.uses_emotional_language = update_avg(
            self.uses_emotional_language,
            emotional_score
        )

        # First person usage
        first_person = 1.0 if query_text.lower().startswith("i ") else 0.0
        self.uses_first_person = update_avg(self.uses_first_person, first_person)

        # Query length
        word_count = len(query_text.split())
        self.avg_query_length = update_avg(self.avg_query_length, word_count)

        # Question ratio
        is_question = 1.0 if "?" in query_text else 0.0
        self.question_ratio = update_avg(self.question_ratio, is_question)

        # Update emotional trajectory
        self.emotional_baseline = update_avg(
            self.emotional_baseline,
            signals.intent_scores.get("emotional", 0.0) if hasattr(signals, 'intent_scores') else 0.0
        )

    def get_confidence_modifier(self) -> float:
        """
        Get confidence modifier based on persona patterns.

        Returns adjustment in range [-0.1, +0.1].
        """
        modifier = 0.0

        # High first-person usage + emotional language = likely reflexive
        if self.uses_first_person > 0.7 and self.uses_emotional_language > 0.5:
            modifier += 0.05

        # Consistent patterns = higher confidence
        if self.query_count >= 3 and self.emotional_variance < 0.2:
            modifier += 0.03

        return max(-0.1, min(0.1, modifier))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uses_first_person": self.uses_first_person,
            "uses_emotional_language": self.uses_emotional_language,
            "question_ratio": self.question_ratio,
            "avg_query_length": self.avg_query_length,
            "emotional_baseline": self.emotional_baseline,
            "query_count": self.query_count,
        }


@dataclass
class PriorGroundingProjection:
    """
    Stores prior grounding decisions for inference on new queries.

    When a query like "what about that?" comes in, we can use prior
    grounding to infer what "that" refers to.
    """
    # Recent grounding decisions
    grounding_history: Deque[Dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=20)
    )

    # Mode frequency in session
    mode_counts: Dict[str, int] = field(default_factory=dict)

    # Last confident grounding (for reference resolution)
    last_confident_grounding: Optional[Dict[str, Any]] = None

    # Accumulated grounding patterns
    reflexive_streak: int = 0
    relational_streak: int = 0

    def record_grounding(
        self,
        clause_text: str,
        mode: str,
        confidence: float,
        status: str,
    ) -> None:
        """Record a grounding decision."""
        entry = {
            "clause_text": clause_text,
            "mode": mode,
            "confidence": confidence,
            "status": status,
            "timestamp": time.time(),
        }
        self.grounding_history.append(entry)

        # Update mode counts
        self.mode_counts[mode] = self.mode_counts.get(mode, 0) + 1

        # Track streaks
        if mode == "REFLEXIVE":
            self.reflexive_streak += 1
            self.relational_streak = 0
        elif mode == "RELATIONAL":
            self.relational_streak += 1
            self.reflexive_streak = 0
        else:
            self.reflexive_streak = 0
            self.relational_streak = 0

        # Update last confident
        if status == "CONFIDENT":
            self.last_confident_grounding = entry

    def get_mode_prior(self) -> Optional[str]:
        """Get most likely mode based on session history."""
        if not self.mode_counts:
            return None
        return max(self.mode_counts, key=self.mode_counts.get)

    def get_streak_boost(self) -> float:
        """
        Get confidence boost based on grounding streaks.

        If user has been consistently reflexive/relational, boost that mode.
        """
        if self.reflexive_streak >= 3:
            return 0.08
        elif self.relational_streak >= 3:
            return 0.08
        elif self.reflexive_streak >= 2 or self.relational_streak >= 2:
            return 0.04
        return 0.0

    def get_reference_context(self) -> Optional[Dict[str, Any]]:
        """Get context for resolving ambiguous references."""
        if self.last_confident_grounding:
            return self.last_confident_grounding
        if self.grounding_history:
            return self.grounding_history[-1]
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "history_length": len(self.grounding_history),
            "mode_counts": self.mode_counts,
            "reflexive_streak": self.reflexive_streak,
            "relational_streak": self.relational_streak,
            "mode_prior": self.get_mode_prior(),
        }


@dataclass
class SessionContext:
    """
    Complete session context for Phase -1 disambiguation.

    Accumulates information across queries within a session to inform
    grounding decisions on new queries.

    Usage:
        session = SessionContext.create()

        # For each query:
        context_signals = session.get_context_signals(fuzzy_signals)
        # ... process query ...
        session.record_query_result(clause_result)
    """
    session_id: str
    created_at: float

    # Core accumulators
    domain_accumulator: DomainAccumulator = field(default_factory=DomainAccumulator)
    persona_signals: PersonaSignals = field(default_factory=PersonaSignals)
    prior_projections: PriorGroundingProjection = field(default_factory=PriorGroundingProjection)

    # Event history
    events: Deque[SessionEvent] = field(
        default_factory=lambda: deque(maxlen=100)
    )

    # Session-level metadata
    query_count: int = 0
    clarification_count: int = 0
    ambiguity_count: int = 0

    @classmethod
    def create(cls, session_id: Optional[str] = None) -> "SessionContext":
        """Create a new session context."""
        return cls(
            session_id=session_id or str(uuid.uuid4())[:12],
            created_at=time.time(),
        )

    def record_event(self, event: SessionEvent) -> None:
        """Record a session event."""
        self.events.append(event)

    def record_query(
        self,
        query_text: str,
        fuzzy_signals: "FuzzyQuerySignals",
        domain: Optional[DomainCategory] = None,
    ) -> None:
        """Record a new query being processed."""
        self.query_count += 1

        # Update persona from signals
        self.persona_signals.update_from_signals(fuzzy_signals, query_text)

        # Infer domain if not provided
        if domain is None:
            domain = self._infer_domain(query_text, fuzzy_signals)

        # Record domain
        if domain:
            keywords = query_text.lower().split()
            self.domain_accumulator.record_domain(domain, keywords)

        # Record event
        self.record_event(SessionEvent(
            event_type=EventType.QUERY,
            timestamp=time.time(),
            query_text=query_text,
            domain=domain,
            intent=fuzzy_signals.primary_intent.value if hasattr(fuzzy_signals, 'primary_intent') else None,
        ))

    def record_grounding_result(
        self,
        clause_result: "ClauseGroundingResult",
    ) -> None:
        """Record grounding result for future projection."""
        if clause_result.selected:
            self.prior_projections.record_grounding(
                clause_text=clause_result.clause_text,
                mode=clause_result.selected.mode.value,
                confidence=clause_result.selected.confidence,
                status=clause_result.grounding_status.value,
            )

            self.record_event(SessionEvent(
                event_type=EventType.GROUNDING,
                timestamp=time.time(),
                query_text=clause_result.clause_text,
                grounding_mode=clause_result.selected.mode.value,
                confidence=clause_result.selected.confidence,
            ))

        # Track ambiguity
        if clause_result.grounding_status.value == "AMBIGUOUS":
            self.ambiguity_count += 1
            self.record_event(SessionEvent(
                event_type=EventType.AMBIGUITY,
                timestamp=time.time(),
                query_text=clause_result.clause_text,
            ))

        # Track clarification requests
        if clause_result.resolution_policy.value == "ASK_CLARIFY":
            self.clarification_count += 1
            self.record_event(SessionEvent(
                event_type=EventType.CLARIFICATION,
                timestamp=time.time(),
                query_text=clause_result.clause_text,
            ))

    def get_context_confidence_adjustment(self) -> float:
        """
        Get session-context-based confidence adjustment.

        Combines persona patterns and grounding history to suggest
        a confidence modifier for the current query.

        Returns: Adjustment in range [-0.15, +0.15]
        """
        adjustment = 0.0

        # Persona-based adjustment
        adjustment += self.persona_signals.get_confidence_modifier()

        # Streak-based adjustment
        adjustment += self.prior_projections.get_streak_boost()

        # Penalize if session has high ambiguity rate
        if self.query_count >= 3:
            ambiguity_rate = self.ambiguity_count / self.query_count
            if ambiguity_rate > 0.5:
                adjustment -= 0.05

        return max(-0.15, min(0.15, adjustment))

    def get_likely_mode_from_context(self) -> Optional[str]:
        """
        Get likely grounding mode based on session context.

        Uses prior grounding patterns and persona signals.
        """
        # Check prior projections first
        mode_prior = self.prior_projections.get_mode_prior()
        if mode_prior:
            return mode_prior

        # Infer from persona
        if self.persona_signals.uses_first_person > 0.7:
            return "REFLEXIVE"

        return None

    def get_reference_resolution_context(self) -> Dict[str, Any]:
        """
        Get context for resolving ambiguous references.

        When query contains "that", "this issue", etc., use this
        to infer what they might refer to.
        """
        return {
            "last_grounding": self.prior_projections.get_reference_context(),
            "primary_domain": self.domain_accumulator.primary_domain.value
                if self.domain_accumulator.primary_domain else None,
            "recent_events": [e.to_dict() for e in list(self.events)[-5:]],
        }

    def _infer_domain(
        self,
        query_text: str,
        fuzzy_signals: "FuzzyQuerySignals",
    ) -> Optional[DomainCategory]:
        """Infer domain from query content."""
        text_lower = query_text.lower()

        # Simple keyword-based domain inference
        if any(w in text_lower for w in ["feel", "emotion", "sad", "happy", "anxious", "worried"]):
            return DomainCategory.EMOTIONAL
        if any(w in text_lower for w in ["relationship", "friend", "family", "partner", "they", "she", "he"]):
            return DomainCategory.RELATIONAL
        if any(w in text_lower for w in ["work", "job", "boss", "colleague", "career", "project"]):
            return DomainCategory.PROFESSIONAL
        if any(w in text_lower for w in ["health", "sick", "doctor", "medicine", "pain"]):
            return DomainCategory.HEALTH
        if any(w in text_lower for w in ["money", "budget", "expense", "financial"]):
            return DomainCategory.FINANCIAL
        if any(w in text_lower for w in ["meaning", "purpose", "why", "value", "believe"]):
            return DomainCategory.PHILOSOPHICAL

        # Use fuzzy intent as fallback
        if hasattr(fuzzy_signals, 'primary_intent'):
            intent = fuzzy_signals.primary_intent.value
            if intent == "emotional":
                return DomainCategory.EMOTIONAL
            elif intent == "relational":
                return DomainCategory.RELATIONAL

        return DomainCategory.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "query_count": self.query_count,
            "clarification_count": self.clarification_count,
            "ambiguity_count": self.ambiguity_count,
            "domain_accumulator": self.domain_accumulator.to_dict(),
            "persona_signals": self.persona_signals.to_dict(),
            "prior_projections": self.prior_projections.to_dict(),
            "context_adjustment": self.get_context_confidence_adjustment(),
        }


@dataclass
class SessionAwareFuzzySignals:
    """
    Enhanced fuzzy signals that incorporate session context.

    Combines per-query fuzzy signals with session-level context
    for improved disambiguation.
    """
    # Original per-query signals
    base_signals: "FuzzyQuerySignals"

    # Session-level adjustments
    session_adjustment: float = 0.0
    session_mode_prior: Optional[str] = None
    session_domain: Optional[DomainCategory] = None

    # Combined confidence adjustment
    combined_adjustment: float = 0.0

    # Context-based hints
    context_hints: List[str] = field(default_factory=list)

    @classmethod
    def from_context(
        cls,
        base_signals: "FuzzyQuerySignals",
        session: SessionContext,
        query_text: str,
    ) -> "SessionAwareFuzzySignals":
        """Create session-aware signals from context."""
        session_adj = session.get_context_confidence_adjustment()

        # Combine base and session adjustments (capped)
        combined = base_signals.confidence_adjustment + session_adj
        combined = max(-0.20, min(0.20, combined))

        # Gather context hints
        hints = []
        if session.query_count >= 3:
            hints.append(f"session_queries_{session.query_count}")
        if session.prior_projections.reflexive_streak >= 2:
            hints.append("reflexive_pattern")
        if session.prior_projections.relational_streak >= 2:
            hints.append("relational_pattern")
        if session.domain_accumulator.primary_domain:
            hints.append(f"domain_{session.domain_accumulator.primary_domain.value}")

        return cls(
            base_signals=base_signals,
            session_adjustment=session_adj,
            session_mode_prior=session.get_likely_mode_from_context(),
            session_domain=session.domain_accumulator.primary_domain,
            combined_adjustment=combined,
            context_hints=hints,
        )

    @property
    def confidence_adjustment(self) -> float:
        """Get combined confidence adjustment."""
        return self.combined_adjustment

    @property
    def hints(self) -> List[str]:
        """Get combined hints (base + context)."""
        return self.base_signals.hints + self.context_hints

    @property
    def primary_intent(self):
        """Delegate to base signals."""
        return self.base_signals.primary_intent

    @property
    def subject_clarity(self) -> float:
        """Delegate to base signals."""
        return self.base_signals.subject_clarity

    @property
    def pronoun_ambiguity(self) -> float:
        """Delegate to base signals."""
        return self.base_signals.pronoun_ambiguity

    @property
    def intent_scores(self):
        """Delegate to base signals."""
        return self.base_signals.intent_scores


# Public exports
__all__ = [
    "SessionContext",
    "SessionEvent",
    "EventType",
    "DomainCategory",
    "DomainAccumulator",
    "PersonaSignals",
    "PriorGroundingProjection",
    "SessionAwareFuzzySignals",
]
