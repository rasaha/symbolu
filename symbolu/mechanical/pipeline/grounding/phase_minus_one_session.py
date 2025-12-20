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
- Uses CONSTRAINT NARROWING (not confidence boosting)
- Eliminates unlikely interpretations rather than inflating certainty
- Accumulates evidence for disambiguation
- Respects privacy boundaries (no cross-session persistence by default)

Safety Model (Non-Permissions):
- Must NOT override explicit user clarification
- Must NOT invent referents not present in session
- Must NOT change grounding mode when base signals strongly disagree
- Must NOT persist across sessions without explicit user opt-in
- Must NOT apply influence beyond the session window
- Must NOT derive intent beyond what query explicitly states

Phase Boundary Contract:
- Phase -1 outputs are HYPOTHESES, not commitments
- All downstream phases MUST treat them as provisional
- Session context NARROWS possibilities, never DETERMINES outcomes
- Resolution bias affects TIE-BREAKING only, never mode selection

Integration:
- SessionContext feeds into FuzzyQueryClassifier as additional signals
- SessionProjection (read-only) used for decisions
- Prior grounding decisions inform current disambiguation
- Domain context helps resolve ambiguous references
"""

from __future__ import annotations

import math
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, FrozenSet, List, Literal, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .phase_minus_one_schema import (
        ClauseGroundingResult,
        ObservationMode,
        GroundingCandidate,
    )
    from .phase_minus_one_fuzzy import QueryIntentHint, FuzzyQuerySignals


# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================

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


# =============================================================================
# NON-PERMISSIONS (Safety Constraints)
# =============================================================================

class SessionNonPermission(str, Enum):
    """
    Explicit actions that SessionContext must NEVER perform.

    These are hard safety constraints, not soft guidelines.
    """
    OVERRIDE_USER_CLARIFICATION = "override_user_clarification"
    INVENT_REFERENTS = "invent_referents"
    OVERRIDE_STRONG_BASE_SIGNALS = "override_strong_base_signals"
    CROSS_SESSION_PERSISTENCE = "cross_session_persistence"
    EXCEED_INFLUENCE_WINDOW = "exceed_influence_window"
    DERIVE_INTENT_BEYOND_QUERY = "derive_intent_beyond_query"  # NEW: Cannot infer new intent


class SuppressionCause(str, Enum):
    """
    First-class enumeration of why session influence was suppressed.

    Making suppression a typed state (not just a flag) enables:
    - Analytics
    - Debugging
    - Governance reporting
    - Future learning (without authority)
    """
    CONTRADICTION_THRESHOLD = "contradiction_threshold"
    INSUFFICIENT_HISTORY = "insufficient_history"
    STRONG_BASE_SIGNALS = "strong_base_signals"
    OVERCONSTRAINED = "overconstrained"  # All modes would be eliminated
    USER_CLARIFICATION = "user_clarification"  # User explicitly clarified


class ConstraintType(str, Enum):
    """
    Distinguishes hard vs soft constraints.

    HARD: Never violate unless user explicitly clarifies
    SOFT: May be ignored if base signals dominate (above threshold)

    This prevents weak session signals from eliminating valid interpretations,
    especially in noisy early sessions.
    """
    HARD = "hard"
    SOFT = "soft"


# =============================================================================
# ENUMS
# =============================================================================

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
    CONTRADICTION = "contradiction"   # Grounding contradicted prior pattern
    MODE_SWITCH = "mode_switch"       # Observation mode switched


class ResolutionSource(str, Enum):
    """Source of ambiguity resolution - for traceability."""
    LEXICAL = "lexical"                     # Resolved by word-level features
    FUZZY_SIGNALS = "fuzzy_signals"         # Resolved by fuzzy classifier
    SESSION_PROJECTION = "session_projection"  # Resolved by session context
    EXPLICIT_CLARIFICATION = "explicit"     # User provided clarification
    SAFE_DEFAULT = "safe_default"           # Fell back to conservative default


# =============================================================================
# CONSTRAINT NARROWING (replaces confidence boosting)
# =============================================================================

@dataclass(frozen=True)
class SessionConstraintEffect:
    """
    Represents session-based constraint narrowing.

    Instead of boosting confidence, we ELIMINATE unlikely interpretations.
    This makes the system's reasoning more explainable and auditable.

    Constraint Types:
    - HARD: Never violate unless user clarifies explicitly
    - SOFT: May be ignored if base signals are strong (>= threshold)
    """
    eliminated_modes: FrozenSet[str]
    eliminated_domains: FrozenSet[DomainCategory]
    reason: str
    strength: float  # 0.0-1.0, how strongly we believe this constraint
    constraint_type: ConstraintType = ConstraintType.SOFT  # Default: soft

    @classmethod
    def create(
        cls,
        eliminated_modes: List[str] = None,
        eliminated_domains: List[DomainCategory] = None,
        reason: str = "",
        strength: float = 0.5,
        constraint_type: ConstraintType = ConstraintType.SOFT,
    ) -> "SessionConstraintEffect":
        return cls(
            eliminated_modes=frozenset(eliminated_modes or []),
            eliminated_domains=frozenset(eliminated_domains or []),
            reason=reason,
            strength=max(0.0, min(1.0, strength)),
            constraint_type=constraint_type,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eliminated_modes": list(self.eliminated_modes),
            "eliminated_domains": [d.value for d in self.eliminated_domains],
            "reason": self.reason,
            "strength": self.strength,
            "constraint_type": self.constraint_type.value,
        }


# All known observation modes for constraint resolution
ALL_OBSERVATION_MODES: FrozenSet[str] = frozenset({"REFLEXIVE", "RELATIONAL", "DETACHED"})


@dataclass(frozen=True)
class ConstraintResolution:
    """
    Result of combining and resolving multiple constraints.

    Handles constraint interaction to prevent:
    - Over-constraining (eliminating all modes)
    - Conflicting constraints
    - Accidental determinism

    Rule: If all modes would be eliminated → suppress session influence entirely
    """
    eliminated_modes: FrozenSet[str]
    surviving_modes: FrozenSet[str]
    resolution_reason: str
    is_overconstrained: bool  # All modes would be eliminated
    applied_constraints: tuple  # Constraints that were applied
    ignored_constraints: tuple  # Constraints ignored due to conflicts

    @classmethod
    def resolve(
        cls,
        constraints: List[SessionConstraintEffect],
        base_signal_strength: float = 0.0,
    ) -> "ConstraintResolution":
        """
        Combine multiple constraints with conflict detection.

        If constraints would eliminate all modes, returns overconstrained state.
        Soft constraints are ignored if base signals are strong.
        """
        if not constraints:
            return cls(
                eliminated_modes=frozenset(),
                surviving_modes=ALL_OBSERVATION_MODES,
                resolution_reason="no_constraints",
                is_overconstrained=False,
                applied_constraints=(),
                ignored_constraints=(),
            )

        applied: List[SessionConstraintEffect] = []
        ignored: List[SessionConstraintEffect] = []

        # Filter constraints based on type and base signal strength
        for constraint in constraints:
            if constraint.constraint_type == ConstraintType.SOFT:
                if base_signal_strength >= BASE_SIGNAL_OVERRIDE_THRESHOLD:
                    # Strong base signals override soft constraints
                    ignored.append(constraint)
                    continue
            applied.append(constraint)

        # Combine eliminated modes from applied constraints
        eliminated: Set[str] = set()
        for constraint in applied:
            eliminated.update(constraint.eliminated_modes)

        surviving = ALL_OBSERVATION_MODES - eliminated

        # Check for over-constraining
        if not surviving:
            return cls(
                eliminated_modes=frozenset(eliminated),
                surviving_modes=frozenset(),
                resolution_reason="overconstrained_all_modes_eliminated",
                is_overconstrained=True,
                applied_constraints=tuple(applied),
                ignored_constraints=tuple(ignored),
            )

        # Build resolution reason
        reasons = [c.reason for c in applied]
        resolution_reason = "+".join(reasons) if reasons else "no_constraints_applied"

        return cls(
            eliminated_modes=frozenset(eliminated),
            surviving_modes=frozenset(surviving),
            resolution_reason=resolution_reason,
            is_overconstrained=False,
            applied_constraints=tuple(applied),
            ignored_constraints=tuple(ignored),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eliminated_modes": list(self.eliminated_modes),
            "surviving_modes": list(self.surviving_modes),
            "resolution_reason": self.resolution_reason,
            "is_overconstrained": self.is_overconstrained,
            "applied_count": len(self.applied_constraints),
            "ignored_count": len(self.ignored_constraints),
        }


# =============================================================================
# CORE DATA CLASSES
# =============================================================================

@dataclass
class SessionEvent:
    """
    Single event in session history.

    Captures what happened, when, and relevant context.
    """
    event_type: EventType
    timestamp: float
    query_index: int = 0
    query_text: Optional[str] = None
    domain: Optional[DomainCategory] = None
    intent: Optional[str] = None
    grounding_mode: Optional[str] = None
    confidence: float = 0.0
    resolution_source: Optional[ResolutionSource] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "query_index": self.query_index,
            "query_text": self.query_text,
            "domain": self.domain.value if self.domain else None,
            "intent": self.intent,
            "grounding_mode": self.grounding_mode,
            "confidence": self.confidence,
            "resolution_source": self.resolution_source.value if self.resolution_source else None,
            "metadata": self.metadata,
        }


@dataclass
class DomainAccumulator:
    """
    Tracks domain exploration within a session with DECAY.

    Accumulates evidence about which domains/topics have been discussed,
    helping resolve ambiguous references like "this issue" or "the problem".

    Uses exponential decay so early queries don't overweight later ones.
    """
    # Domain visit counts (raw, before decay)
    domain_counts: Dict[DomainCategory, int] = field(default_factory=dict)

    # Domain timestamps for decay calculation
    domain_timestamps: Dict[DomainCategory, List[float]] = field(default_factory=dict)

    # Recent domain sequence (for transition patterns)
    domain_sequence: Deque[DomainCategory] = field(
        default_factory=lambda: deque(maxlen=10)
    )

    # Keywords seen per domain
    domain_keywords: Dict[DomainCategory, Set[str]] = field(default_factory=dict)

    # Primary domain (most discussed, with decay)
    primary_domain: Optional[DomainCategory] = None

    # Domain affinity scores (0.0-1.0, with decay applied)
    domain_affinity: Dict[DomainCategory, float] = field(default_factory=dict)

    # Current query index for decay calculation
    current_query_index: int = 0

    def record_domain(
        self,
        domain: DomainCategory,
        query_index: int,
        keywords: List[str] = None,
    ) -> None:
        """Record a domain visit with optional keywords and decay tracking."""
        self.current_query_index = query_index
        self.domain_counts[domain] = self.domain_counts.get(domain, 0) + 1
        self.domain_sequence.append(domain)

        # Track timestamp for decay
        if domain not in self.domain_timestamps:
            self.domain_timestamps[domain] = []
        self.domain_timestamps[domain].append(time.time())

        if keywords:
            if domain not in self.domain_keywords:
                self.domain_keywords[domain] = set()
            self.domain_keywords[domain].update(keywords)

        self._update_affinity_with_decay()
        self._update_primary()

    def _compute_decay_weight(self, age_in_queries: int) -> float:
        """Compute exponential decay weight based on query age."""
        # weight = exp(-λ * age) where λ = ln(2) / half_life
        decay_rate = math.log(2) / DECAY_HALF_LIFE
        return math.exp(-decay_rate * age_in_queries)

    def _update_affinity_with_decay(self) -> None:
        """Update domain affinity scores with exponential decay."""
        if not self.domain_counts:
            return

        decayed_counts: Dict[DomainCategory, float] = {}

        for domain, count in self.domain_counts.items():
            # Apply decay based on when visits occurred
            decayed_count = 0.0
            timestamps = self.domain_timestamps.get(domain, [])

            # Approximate: use count with position-based decay
            for i in range(count):
                # Estimate age based on position in sequence
                estimated_age = max(0, self.current_query_index - i - 1)
                decayed_count += self._compute_decay_weight(estimated_age)

            decayed_counts[domain] = decayed_count

        total = sum(decayed_counts.values()) or 1.0

        for domain, decayed_count in decayed_counts.items():
            # Affinity with recency bias
            recency_bonus = 0.0
            if self.domain_sequence and self.domain_sequence[-1] == domain:
                recency_bonus = 0.1
            self.domain_affinity[domain] = min(1.0, (decayed_count / total) + recency_bonus)

    def _update_primary(self) -> None:
        """Update primary domain based on highest decayed affinity."""
        if self.domain_affinity:
            self.primary_domain = max(
                self.domain_affinity,
                key=self.domain_affinity.get
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
            "domain_affinity": {k.value: round(v, 3) for k, v in self.domain_affinity.items()},
            "recent_sequence": [d.value for d in self.domain_sequence],
        }


@dataclass
class PersonaSignals:
    """
    Accumulated persona signals from session behavior with DECAY.

    Tracks communication patterns to help interpret queries.
    """
    # Communication style indicators (exponential moving averages)
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

    # Recent emotional values for variance calculation
    _recent_emotional: Deque[float] = field(
        default_factory=lambda: deque(maxlen=10)
    )

    # Query count for weighted updates
    query_count: int = 0

    # Decay factor for exponential moving average
    _ema_alpha: float = 0.3  # Higher = more weight on recent

    def update_from_signals(self, signals: "FuzzyQuerySignals", query_text: str) -> None:
        """Update persona from new query signals with EMA decay."""
        self.query_count += 1
        alpha = self._ema_alpha

        # Exponential moving average update
        def ema_update(old: float, new: float) -> float:
            return alpha * new + (1 - alpha) * old

        # Update from fuzzy signals
        emotional_score = 0.0
        if hasattr(signals, 'intent_scores') and signals.intent_scores:
            from .phase_minus_one_fuzzy import QueryIntentHint
            emotional_score = signals.intent_scores.get(QueryIntentHint.EMOTIONAL, 0.0)

        self.uses_emotional_language = ema_update(
            self.uses_emotional_language,
            emotional_score
        )

        # Track emotional variance
        self._recent_emotional.append(emotional_score)
        if len(self._recent_emotional) >= 3:
            mean = sum(self._recent_emotional) / len(self._recent_emotional)
            variance = sum((x - mean) ** 2 for x in self._recent_emotional) / len(self._recent_emotional)
            self.emotional_variance = math.sqrt(variance)

        # First person usage
        first_person = 1.0 if query_text.lower().startswith("i ") or " i " in query_text.lower() else 0.0
        self.uses_first_person = ema_update(self.uses_first_person, first_person)

        # Query length
        word_count = len(query_text.split())
        self.avg_query_length = ema_update(self.avg_query_length, float(word_count))

        # Question ratio
        is_question = 1.0 if "?" in query_text else 0.0
        self.question_ratio = ema_update(self.question_ratio, is_question)

        # Update emotional baseline
        self.emotional_baseline = ema_update(self.emotional_baseline, emotional_score)

    def get_constraint_effect(self) -> Optional[SessionConstraintEffect]:
        """
        Get constraint effect based on persona patterns.

        Returns constraint narrowing instead of confidence boost.
        """
        # High first-person + emotional = likely reflexive, eliminate DETACHED
        if self.uses_first_person > 0.7 and self.uses_emotional_language > 0.5:
            return SessionConstraintEffect.create(
                eliminated_modes=["DETACHED"],
                reason="consistent_first_person_emotional_pattern",
                strength=0.6,
            )

        # Low emotional, high question ratio = likely informational/detached
        if self.uses_emotional_language < 0.2 and self.question_ratio > 0.7:
            return SessionConstraintEffect.create(
                eliminated_modes=["REFLEXIVE"],
                reason="analytical_questioning_pattern",
                strength=0.5,
            )

        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uses_first_person": round(self.uses_first_person, 3),
            "uses_emotional_language": round(self.uses_emotional_language, 3),
            "question_ratio": round(self.question_ratio, 3),
            "avg_query_length": round(self.avg_query_length, 1),
            "emotional_baseline": round(self.emotional_baseline, 3),
            "emotional_variance": round(self.emotional_variance, 3),
            "query_count": self.query_count,
        }


@dataclass
class PriorGroundingProjection:
    """
    Stores prior grounding decisions for inference on new queries.

    When a query like "what about that?" comes in, we can use prior
    grounding to infer what "that" refers to.

    Includes CONTRADICTION TRACKING to detect pattern breaks.
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

    # CONTRADICTION TRACKING
    contradiction_count: int = 0
    last_mode_switch_at: int = 0
    recent_contradictions: Deque[int] = field(
        default_factory=lambda: deque(maxlen=10)
    )

    # Current query index
    current_query_index: int = 0

    # Previous mode for contradiction detection
    _previous_mode: Optional[str] = None

    def record_grounding(
        self,
        clause_text: str,
        mode: str,
        confidence: float,
        status: str,
        query_index: int,
    ) -> Optional[SessionEvent]:
        """
        Record a grounding decision.

        Returns a CONTRADICTION event if mode switches unexpectedly.
        """
        self.current_query_index = query_index

        entry = {
            "clause_text": clause_text,
            "mode": mode,
            "confidence": confidence,
            "status": status,
            "timestamp": time.time(),
            "query_index": query_index,
        }
        self.grounding_history.append(entry)

        # Update mode counts
        self.mode_counts[mode] = self.mode_counts.get(mode, 0) + 1

        # Detect contradiction (mode switch after streak)
        contradiction_event = None
        if self._previous_mode and self._previous_mode != mode:
            # Check if this breaks a streak
            if (self._previous_mode == "REFLEXIVE" and self.reflexive_streak >= 2) or \
               (self._previous_mode == "RELATIONAL" and self.relational_streak >= 2):
                self.contradiction_count += 1
                self.last_mode_switch_at = query_index
                self.recent_contradictions.append(query_index)

                contradiction_event = SessionEvent(
                    event_type=EventType.CONTRADICTION,
                    timestamp=time.time(),
                    query_index=query_index,
                    grounding_mode=mode,
                    metadata={
                        "previous_mode": self._previous_mode,
                        "broke_streak": True,
                    }
                )

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

        self._previous_mode = mode

        # Update last confident
        if status == "CONFIDENT":
            self.last_confident_grounding = entry

        return contradiction_event

    def get_mode_prior(self) -> Optional[str]:
        """Get most likely mode based on session history."""
        if not self.mode_counts:
            return None
        return max(self.mode_counts, key=self.mode_counts.get)

    def get_constraint_effect(self, query_index: int) -> Optional[SessionConstraintEffect]:
        """
        Get constraint effect based on grounding streaks.

        Uses CONSTRAINT NARROWING instead of confidence boosting.
        """
        # Check if we should suppress due to contradictions
        recent_contradiction_count = sum(
            1 for idx in self.recent_contradictions
            if query_index - idx <= SESSION_INFLUENCE_WINDOW
        )
        if recent_contradiction_count >= CONTRADICTION_THRESHOLD:
            # Too many contradictions - don't apply session constraints
            return None

        # Reflexive streak - eliminate DETACHED/RELATIONAL
        if self.reflexive_streak >= 3:
            return SessionConstraintEffect.create(
                eliminated_modes=["DETACHED"],
                reason=f"reflexive_streak_{self.reflexive_streak}",
                strength=0.7,
            )
        elif self.reflexive_streak >= 2:
            return SessionConstraintEffect.create(
                eliminated_modes=["DETACHED"],
                reason=f"reflexive_streak_{self.reflexive_streak}",
                strength=0.5,
            )

        # Relational streak - eliminate DETACHED
        if self.relational_streak >= 3:
            return SessionConstraintEffect.create(
                eliminated_modes=["DETACHED"],
                reason=f"relational_streak_{self.relational_streak}",
                strength=0.7,
            )
        elif self.relational_streak >= 2:
            return SessionConstraintEffect.create(
                eliminated_modes=["DETACHED"],
                reason=f"relational_streak_{self.relational_streak}",
                strength=0.5,
            )

        return None

    def get_reference_context(self) -> Optional[Dict[str, Any]]:
        """Get context for resolving ambiguous references."""
        if self.last_confident_grounding:
            return self.last_confident_grounding
        if self.grounding_history:
            return self.grounding_history[-1]
        return None

    def is_influence_suppressed(self, query_index: int) -> bool:
        """Check if session influence should be suppressed due to contradictions."""
        recent_contradiction_count = sum(
            1 for idx in self.recent_contradictions
            if query_index - idx <= SESSION_INFLUENCE_WINDOW
        )
        return recent_contradiction_count >= CONTRADICTION_THRESHOLD

    def to_dict(self) -> Dict[str, Any]:
        return {
            "history_length": len(self.grounding_history),
            "mode_counts": self.mode_counts,
            "reflexive_streak": self.reflexive_streak,
            "relational_streak": self.relational_streak,
            "mode_prior": self.get_mode_prior(),
            "contradiction_count": self.contradiction_count,
            "last_mode_switch_at": self.last_mode_switch_at,
        }


# =============================================================================
# SESSION PROJECTION (Read-Only Decision Layer)
# =============================================================================

@dataclass(frozen=True)
class SessionProjection:
    """
    Read-only projection of session state for decision-making.

    Separates evidence accumulation from decision influence.
    Ensures no mutation during decision and provides clear audit boundary.

    Phase Boundary Contract:
    - This projection is a HYPOTHESIS, not a commitment
    - Downstream phases MUST treat this as provisional
    - Resolution bias affects TIE-BREAKING only, never mode selection
    """
    # Derived state (immutable per query)
    dominant_domain: Optional[DomainCategory]
    dominant_mode: Optional[str]
    consistency_score: float  # 0.0-1.0, how consistent the session has been

    # Constraint resolution result
    constraint_resolution: ConstraintResolution

    # Constraints to apply (raw, before resolution)
    constraints: tuple  # Tuple[SessionConstraintEffect, ...]

    # Resolution bias - affects TIE-BREAKING ONLY, never mode selection
    resolution_bias: float  # [-0.20, +0.20]

    # Whether session influence is suppressed
    influence_suppressed: bool
    suppression_cause: Optional[SuppressionCause]  # Typed enum, not string

    # Summary for downstream
    constraint_summary: tuple  # Tuple[str, ...]

    # Query index this projection is for
    query_index: int

    def get_surviving_modes(self) -> FrozenSet[str]:
        """Get modes that survived constraint narrowing."""
        if self.influence_suppressed:
            return ALL_OBSERVATION_MODES
        return self.constraint_resolution.surviving_modes

    def should_apply_bias(self, candidate_mode_count: int) -> bool:
        """
        Resolution bias applies ONLY for tie-breaking.

        If only one mode survives constraints, bias is not applied.
        This keeps Phase -1 non-authoritative and non-optimizing.
        """
        return candidate_mode_count > 1 and not self.influence_suppressed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dominant_domain": self.dominant_domain.value if self.dominant_domain else None,
            "dominant_mode": self.dominant_mode,
            "consistency_score": round(self.consistency_score, 3),
            "constraint_resolution": self.constraint_resolution.to_dict(),
            "constraints": [c.to_dict() for c in self.constraints],
            "resolution_bias": round(self.resolution_bias, 3),
            "influence_suppressed": self.influence_suppressed,
            "suppression_cause": self.suppression_cause.value if self.suppression_cause else None,
            "constraint_summary": list(self.constraint_summary),
            "query_index": self.query_index,
            "surviving_modes": list(self.get_surviving_modes()),
        }


# =============================================================================
# AUDIT INFRASTRUCTURE
# =============================================================================

@dataclass
class SessionAuditEntry:
    """
    Single audit log entry for session-influenced decisions.

    Enables external auditors, later AGI layers, and human review
    without letting the system "decide how to decide".
    """
    decision_id: str
    timestamp: float
    query_index: int

    # What session factors were used
    factors_used: List[str]

    # What factors were available but NOT used (silence is dangerous)
    factors_ignored: List[str]
    ignored_reasons: Dict[str, str]

    # Constraints applied
    constraints_applied: List[SessionConstraintEffect]

    # Final resolution
    resolution_source: ResolutionSource
    resolution_bias_applied: float

    # Explanation
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "query_index": self.query_index,
            "factors_used": self.factors_used,
            "factors_ignored": self.factors_ignored,
            "ignored_reasons": self.ignored_reasons,
            "constraints_applied": [c.to_dict() for c in self.constraints_applied],
            "resolution_source": self.resolution_source.value,
            "resolution_bias_applied": round(self.resolution_bias_applied, 3),
            "reason": self.reason,
        }


@dataclass
class SessionSummary:
    """
    End-of-session summary for analytics.

    Generated only at session end, not used for decisions.
    Prepares for optional persona file persistence.
    """
    session_id: str
    duration_seconds: float
    query_count: int

    # Dominant patterns
    dominant_domain: Optional[DomainCategory]
    dominant_mode: Optional[str]

    # Quality metrics
    ambiguity_rate: float      # Fraction of ambiguous queries
    clarification_rate: float  # Fraction requiring clarification
    volatility_score: float    # How much patterns changed
    contradiction_rate: float  # Fraction of pattern-breaking queries

    # Consistency
    consistency_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "duration_seconds": round(self.duration_seconds, 1),
            "query_count": self.query_count,
            "dominant_domain": self.dominant_domain.value if self.dominant_domain else None,
            "dominant_mode": self.dominant_mode,
            "ambiguity_rate": round(self.ambiguity_rate, 3),
            "clarification_rate": round(self.clarification_rate, 3),
            "volatility_score": round(self.volatility_score, 3),
            "contradiction_rate": round(self.contradiction_rate, 3),
            "consistency_score": round(self.consistency_score, 3),
        }


# =============================================================================
# MAIN SESSION CONTEXT
# =============================================================================

@dataclass
class SessionContext:
    """
    Complete session context for Phase -1 disambiguation.

    Accumulates information across queries within a session to inform
    grounding decisions on new queries.

    Key Design Principles:
    1. Uses CONSTRAINT NARROWING, not confidence boosting
    2. Provides read-only SessionProjection for decisions
    3. Includes exponential decay on all accumulators
    4. Tracks contradictions to suppress influence when patterns break
    5. Maintains audit log for explainability

    Usage:
        session = SessionContext.create()

        # For each query:
        projection = session.create_projection(query_index)
        # ... use projection for decisions (read-only) ...
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

    # Audit log
    audit_log: Deque[SessionAuditEntry] = field(
        default_factory=lambda: deque(maxlen=50)
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
            self.domain_accumulator.record_domain(domain, self.query_count, keywords)

        # Record event
        self.record_event(SessionEvent(
            event_type=EventType.QUERY,
            timestamp=time.time(),
            query_index=self.query_count,
            query_text=query_text,
            domain=domain,
            intent=fuzzy_signals.primary_intent.value if hasattr(fuzzy_signals, 'primary_intent') else None,
        ))

    def record_grounding_result(
        self,
        clause_result: "ClauseGroundingResult",
        resolution_source: ResolutionSource = ResolutionSource.FUZZY_SIGNALS,
    ) -> None:
        """Record grounding result for future projection."""
        if clause_result.selected:
            contradiction_event = self.prior_projections.record_grounding(
                clause_text=clause_result.clause_text,
                mode=clause_result.selected.mode.value,
                confidence=clause_result.selected.confidence,
                status=clause_result.grounding_status.value,
                query_index=self.query_count,
            )

            if contradiction_event:
                self.record_event(contradiction_event)

            self.record_event(SessionEvent(
                event_type=EventType.GROUNDING,
                timestamp=time.time(),
                query_index=self.query_count,
                query_text=clause_result.clause_text,
                grounding_mode=clause_result.selected.mode.value,
                confidence=clause_result.selected.confidence,
                resolution_source=resolution_source,
            ))

        # Track ambiguity
        if clause_result.grounding_status.value == "AMBIGUOUS":
            self.ambiguity_count += 1
            self.record_event(SessionEvent(
                event_type=EventType.AMBIGUITY,
                timestamp=time.time(),
                query_index=self.query_count,
                query_text=clause_result.clause_text,
            ))

        # Track clarification requests
        if clause_result.resolution_policy.value == "ASK_CLARIFY":
            self.clarification_count += 1
            self.record_event(SessionEvent(
                event_type=EventType.CLARIFICATION,
                timestamp=time.time(),
                query_index=self.query_count,
                query_text=clause_result.clause_text,
            ))

    def create_projection(
        self,
        query_index: Optional[int] = None,
        base_signal_strength: float = 0.0,
    ) -> SessionProjection:
        """
        Create a read-only projection of session state for decision-making.

        This is the ONLY way session context should influence decisions.

        Phase Boundary Contract:
        - This projection is a HYPOTHESIS, not a commitment
        - Downstream phases MUST treat it as provisional
        - Resolution bias affects TIE-BREAKING only

        Args:
            query_index: Query index for this projection
            base_signal_strength: Strength of base fuzzy signals (0.0-1.0)
                                 Strong base signals can override soft constraints
        """
        if query_index is None:
            query_index = self.query_count + 1

        # Check if influence should be suppressed (with typed cause)
        influence_suppressed = False
        suppression_cause: Optional[SuppressionCause] = None

        if self.prior_projections.is_influence_suppressed(query_index):
            influence_suppressed = True
            suppression_cause = SuppressionCause.CONTRADICTION_THRESHOLD

        # Only use queries within the influence window
        if not influence_suppressed and query_index > SESSION_INFLUENCE_WINDOW:
            recent_groundings = sum(
                1 for g in self.prior_projections.grounding_history
                if g.get("query_index", 0) > query_index - SESSION_INFLUENCE_WINDOW
            )
            if recent_groundings < 2:
                influence_suppressed = True
                suppression_cause = SuppressionCause.INSUFFICIENT_HISTORY

        # Check if base signals are strong enough to override
        if not influence_suppressed and base_signal_strength >= BASE_SIGNAL_OVERRIDE_THRESHOLD:
            # Don't suppress entirely, but soft constraints will be ignored
            # This is handled in ConstraintResolution.resolve()
            pass

        # Collect constraints
        constraints: List[SessionConstraintEffect] = []
        constraint_summary: List[str] = []

        if not influence_suppressed:
            # Persona-based constraints
            persona_constraint = self.persona_signals.get_constraint_effect()
            if persona_constraint:
                constraints.append(persona_constraint)
                constraint_summary.append(persona_constraint.reason)

            # Grounding history constraints
            grounding_constraint = self.prior_projections.get_constraint_effect(query_index)
            if grounding_constraint:
                constraints.append(grounding_constraint)
                constraint_summary.append(grounding_constraint.reason)

        # Resolve constraints with interaction handling
        constraint_resolution = ConstraintResolution.resolve(
            constraints, base_signal_strength
        )

        # Check for over-constraining (all modes eliminated)
        if constraint_resolution.is_overconstrained:
            influence_suppressed = True
            suppression_cause = SuppressionCause.OVERCONSTRAINED
            # Reset resolution to no constraints
            constraint_resolution = ConstraintResolution.resolve([])

        # Compute resolution bias from applied constraints
        # NOTE: Bias affects TIE-BREAKING only, not mode selection
        resolution_bias = 0.0
        if constraint_resolution.applied_constraints:
            total_strength = sum(c.strength for c in constraint_resolution.applied_constraints)
            resolution_bias = min(MAX_RESOLUTION_BIAS, total_strength * 0.15)

        # Compute consistency score with explicit formula
        consistency_score = self._compute_consistency_score()

        return SessionProjection(
            dominant_domain=self.domain_accumulator.primary_domain,
            dominant_mode=self.prior_projections.get_mode_prior(),
            consistency_score=consistency_score,
            constraint_resolution=constraint_resolution,
            constraints=tuple(constraints),
            resolution_bias=resolution_bias,
            influence_suppressed=influence_suppressed,
            suppression_cause=suppression_cause,
            constraint_summary=tuple(constraint_summary),
            query_index=query_index,
        )

    def record_audit(self, entry: SessionAuditEntry) -> None:
        """Record an audit entry."""
        self.audit_log.append(entry)

    def _compute_consistency_score(self) -> float:
        """
        Compute how consistent session patterns have been.

        Explicit Formula:
            consistency = 1.0 - (
                contradiction_rate * 0.5 +
                mode_switch_rate * 0.3 +
                domain_switch_rate * 0.2
            )

        Where:
        - contradiction_rate = contradictions / query_count
        - mode_switch_rate = mode_switches / query_count (approximated by contradiction)
        - domain_switch_rate = unique_domains / domain_sequence_length

        Returns: Float in range [0.0, 1.0]
        """
        if self.query_count < 3:
            return 0.5  # Not enough data for meaningful score

        # Calculate component rates
        contradiction_rate = (
            self.prior_projections.contradiction_count / self.query_count
            if self.query_count > 0 else 0.0
        )

        # Mode switch rate (use contradiction as proxy)
        mode_switch_rate = contradiction_rate  # Same as contradiction for now

        # Domain switch rate
        domain_switch_rate = 0.0
        if len(self.domain_accumulator.domain_sequence) >= 3:
            unique_domains = len(set(self.domain_accumulator.domain_sequence))
            domain_switch_rate = unique_domains / len(self.domain_accumulator.domain_sequence)

        # Apply the explicit formula
        consistency = 1.0 - (
            contradiction_rate * 0.5 +
            mode_switch_rate * 0.3 +
            domain_switch_rate * 0.2
        )

        return max(0.0, min(1.0, consistency))

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

    def generate_summary(self) -> SessionSummary:
        """Generate end-of-session summary for analytics."""
        duration = time.time() - self.created_at

        ambiguity_rate = self.ambiguity_count / max(1, self.query_count)
        clarification_rate = self.clarification_count / max(1, self.query_count)
        contradiction_rate = self.prior_projections.contradiction_count / max(1, self.query_count)

        # Volatility based on emotional variance and domain switches
        volatility = (
            self.persona_signals.emotional_variance * 0.5 +
            (len(set(self.domain_accumulator.domain_sequence)) / max(1, len(self.domain_accumulator.domain_sequence))) * 0.5
        )

        return SessionSummary(
            session_id=self.session_id,
            duration_seconds=duration,
            query_count=self.query_count,
            dominant_domain=self.domain_accumulator.primary_domain,
            dominant_mode=self.prior_projections.get_mode_prior(),
            ambiguity_rate=ambiguity_rate,
            clarification_rate=clarification_rate,
            volatility_score=volatility,
            contradiction_rate=contradiction_rate,
            consistency_score=self._compute_consistency_score(),
        )

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
            "consistency_score": self._compute_consistency_score(),
            "current_projection": self.create_projection().to_dict(),
        }


# =============================================================================
# SESSION-AWARE FUZZY SIGNALS
# =============================================================================

@dataclass
class SessionAwareFuzzySignals:
    """
    Enhanced fuzzy signals that incorporate session context.

    Combines per-query fuzzy signals with session-level context
    for improved disambiguation using CONSTRAINT NARROWING.
    """
    # Original per-query signals
    base_signals: "FuzzyQuerySignals"

    # Session projection (read-only)
    projection: SessionProjection

    # Combined resolution bias (replaces confidence_adjustment)
    resolution_bias: float = 0.0

    # Context-based hints
    context_hints: List[str] = field(default_factory=list)

    # Constraints applied
    constraints_applied: List[SessionConstraintEffect] = field(default_factory=list)

    # Resolution source tracking
    resolution_source: ResolutionSource = ResolutionSource.FUZZY_SIGNALS

    @classmethod
    def from_context(
        cls,
        base_signals: "FuzzyQuerySignals",
        session: SessionContext,
        query_text: str,
    ) -> "SessionAwareFuzzySignals":
        """Create session-aware signals from context."""
        projection = session.create_projection()

        # Combine base and session bias (capped)
        base_adj = base_signals.confidence_adjustment
        session_bias = projection.resolution_bias if not projection.influence_suppressed else 0.0
        combined_bias = max(-MAX_RESOLUTION_BIAS, min(MAX_RESOLUTION_BIAS, base_adj + session_bias))

        # Gather context hints
        hints = list(projection.constraint_summary)

        if projection.influence_suppressed:
            hints.append(f"session_influence_suppressed:{projection.suppression_reason}")
        else:
            if session.query_count >= 3:
                hints.append(f"session_queries_{session.query_count}")
            if projection.dominant_domain:
                hints.append(f"domain_{projection.dominant_domain.value}")
            if projection.dominant_mode:
                hints.append(f"mode_prior_{projection.dominant_mode.lower()}")

        # Determine resolution source
        resolution_source = ResolutionSource.FUZZY_SIGNALS
        if not projection.influence_suppressed and projection.constraints:
            resolution_source = ResolutionSource.SESSION_PROJECTION

        return cls(
            base_signals=base_signals,
            projection=projection,
            resolution_bias=combined_bias,
            context_hints=hints,
            constraints_applied=list(projection.constraints),
            resolution_source=resolution_source,
        )

    @property
    def confidence_adjustment(self) -> float:
        """Get combined resolution bias (for backward compatibility)."""
        return self.resolution_bias

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

    def get_eliminated_modes(self) -> Set[str]:
        """Get modes eliminated by session constraints."""
        eliminated: Set[str] = set()
        for constraint in self.constraints_applied:
            eliminated.update(constraint.eliminated_modes)
        return eliminated


# =============================================================================
# PUBLIC EXPORTS
# =============================================================================

__all__ = [
    # Configuration
    "SESSION_INFLUENCE_WINDOW",
    "DECAY_HALF_LIFE",
    "CONTRADICTION_THRESHOLD",
    "MAX_RESOLUTION_BIAS",
    # Enums
    "SessionNonPermission",
    "DomainCategory",
    "EventType",
    "ResolutionSource",
    # Core classes
    "SessionContext",
    "SessionEvent",
    "DomainAccumulator",
    "PersonaSignals",
    "PriorGroundingProjection",
    # Constraint narrowing
    "SessionConstraintEffect",
    # Projection layer
    "SessionProjection",
    # Audit
    "SessionAuditEntry",
    "SessionSummary",
    # Session-aware signals
    "SessionAwareFuzzySignals",
]
