"""
Insight Suggester
=================

Generates personalized insights for users based on their persona history
and current context. These insights are USER-SPECIFIC and do NOT propagate
to the universal learning store.

Architecture:
    Learning Layer (universal):     Causal chains, 10D structure, pattern types
    Presentation Layer (personal):  Insights generated from persona + context

Key Distinction:
    - Universal patterns transfer across domains for ALL users
    - Personal insights are generated FOR this user based on THEIR history

Critical Design:
    - Insights require STRUCTURAL VALIDATION, not just domain co-occurrence
    - User controls insight mode (recent memory, domain-relative, new possibilities)
    - Without structural match, cross-domain suggestions are advertising, not insight
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Set
from datetime import datetime, timedelta
from enum import Enum

from .persona_tracker import (
    PersonaProfile,
    PersonaStore,
    get_persona_store,
    QueryRecord,
    CrossDomainBridge,
)
from .mirror_pairs import encode_with_events, TaggedEvent
from .encoder import DimensionalVector
from .similarity import cosine_similarity


class InsightMode(Enum):
    """
    User-controlled insight presentation modes.

    The user decides HOW they want insights presented, not the system.
    """
    RECENT_MEMORY = "recent_memory"
    """Prioritize connections to what user was just working on.
    User explicitly wants this context, recency over structural match."""

    DOMAIN_RELATIVE = "domain_relative"
    """Stay focused on current domain only. No cross-domain suggestions.
    Deep dive mode - user wants focus, not distraction."""

    NEW_POSSIBILITIES = "new_possibilities"
    """Show novel cross-domain connections ONLY if structural match exists.
    Requires causal chain or 10D similarity validation.
    This is discovery mode, but grounded in real patterns."""


class InsightType(Enum):
    """Types of personal insights."""
    BRIDGE_OPPORTUNITY = "bridge_opportunity"      # Cross-domain connection (validated)
    PATTERN_CONTINUATION = "pattern_continuation"  # Continuing a pattern user follows
    DOMAIN_DEPTH = "domain_depth"                  # Deeper insight within same domain
    STRUCTURAL_MATCH = "structural_match"          # Novel connection via structure


@dataclass
class StructuralMatch:
    """Evidence that a cross-domain bridge is structurally valid."""
    similarity_10d: float           # Cosine similarity in 10D space
    shared_events: List[str]        # Common event types
    causal_overlap: float           # Causal chain overlap (0-1)
    is_valid: bool                  # Passes threshold for suggestion

    @property
    def combined_score(self) -> float:
        """Weighted score matching learning hierarchy."""
        return (
            self.causal_overlap * 0.6 +
            self.similarity_10d * 0.3 +
            (0.1 if self.shared_events else 0.0)
        )


@dataclass
class PersonalInsight:
    """
    A personalized insight for a specific user.

    NOT for universal storage - only for presentation to this user.
    """
    insight_type: InsightType
    message: str
    confidence: float  # 0.0 to 1.0

    # What triggered this insight
    current_domain: str
    bridge_domain: Optional[str] = None

    # Evidence from persona history
    recent_activity: List[str] = field(default_factory=list)
    shared_events: List[str] = field(default_factory=list)

    # Structural validation (NEW - prevents advertising)
    structural_match: Optional[StructuralMatch] = None

    # For transparency
    reasoning: str = ""
    mode_used: Optional[InsightMode] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.insight_type.value,
            "message": self.message,
            "confidence": self.confidence,
            "current_domain": self.current_domain,
            "bridge_domain": self.bridge_domain,
            "recent_activity": self.recent_activity,
            "shared_events": self.shared_events,
            "structural_match": {
                "similarity_10d": self.structural_match.similarity_10d,
                "causal_overlap": self.structural_match.causal_overlap,
                "is_valid": self.structural_match.is_valid,
            } if self.structural_match else None,
            "reasoning": self.reasoning,
            "mode": self.mode_used.value if self.mode_used else None,
        }


@dataclass
class InsightContext:
    """Context for generating insights."""
    text: str
    domain: str
    events: List[TaggedEvent] = field(default_factory=list)
    vector_10d: Optional[DimensionalVector] = None


# =============================================================================
# Structural Validation (The key to avoiding "advertising")
# =============================================================================

# Minimum thresholds for structural validity
STRUCTURAL_THRESHOLD_10D = 0.5      # Minimum 10D cosine similarity
STRUCTURAL_THRESHOLD_CAUSAL = 0.3   # Minimum causal chain overlap
STRUCTURAL_THRESHOLD_COMBINED = 0.4 # Minimum combined score
STRUCTURAL_THRESHOLD_REFERENT = 0.3 # Minimum referent coherence (S term)


def _compute_structural_match(
    current_vector: DimensionalVector,
    current_events: Set[str],
    target_vector: Optional[DimensionalVector],
    target_events: Set[str],
    target_causal_chain: Optional[List[str]] = None,
    current_causal_chain: Optional[List[str]] = None,
    current_terms: Optional[List[str]] = None,
    target_terms: Optional[List[str]] = None,
) -> StructuralMatch:
    """
    Compute structural match between current context and a target domain pattern.

    This is the key function that prevents "advertising" - it validates that
    a cross-domain connection is structurally grounded, not just co-occurrence.

    Validation axes:
    1. 10D cosine similarity (phonemic-derived)
    2. Causal chain overlap (structural)
    3. Shared events (semantic)
    4. Referent coherence via C × R × S (NON-phonemic, source-independent)

    The referent coherence (S term) provides an orthogonal validation axis
    that is NOT derived from phonemic data, addressing the source correlation
    issue identified in the canonical matching design.
    """
    # 10D similarity
    similarity_10d = 0.0
    if current_vector and target_vector:
        similarity_10d = cosine_similarity(current_vector, target_vector)

    # Event overlap
    shared_events = list(current_events & target_events)

    # Causal chain overlap (LCS-based)
    causal_overlap = 0.0
    if current_causal_chain and target_causal_chain:
        causal_overlap = _compute_lcs_ratio(current_causal_chain, target_causal_chain)

    # Referent coherence via canonical matching (S term - NON-phonemic)
    referent_coherence = _compute_referent_coherence(current_terms, target_terms)

    # Determine validity using all axes
    is_valid = (
        similarity_10d >= STRUCTURAL_THRESHOLD_10D or
        causal_overlap >= STRUCTURAL_THRESHOLD_CAUSAL or
        len(shared_events) >= 2 or
        referent_coherence >= STRUCTURAL_THRESHOLD_REFERENT
    )

    match = StructuralMatch(
        similarity_10d=similarity_10d,
        shared_events=shared_events,
        causal_overlap=causal_overlap,
        is_valid=is_valid,
    )

    # Also check combined score (now includes referent coherence)
    combined = match.combined_score
    if referent_coherence > 0:
        # Boost combined score with referent coherence
        combined = combined * 0.8 + referent_coherence * 0.2
    if combined >= STRUCTURAL_THRESHOLD_COMBINED:
        match.is_valid = True

    return match


def _compute_referent_coherence(
    current_terms: Optional[List[str]],
    target_terms: Optional[List[str]],
) -> float:
    """
    Compute referent coherence between term sets using canonical matching.

    This provides a NON-phonemic validation axis via the S term from
    the C × R × S canonical matching framework.

    Args:
        current_terms: Key terms from current context
        target_terms: Key terms from target domain

    Returns:
        Average S term (referent coherence) across term pairs
    """
    if not current_terms or not target_terms:
        return 0.0

    try:
        from symbolu_core.providers import get_match_provider
        match_provider = get_match_provider("enterprise")

        # Compute pairwise referent coherence (S term only)
        s_scores = []
        for current_term in current_terms[:5]:  # Limit to top 5 terms
            for target_term in target_terms[:5]:
                if current_term.lower() != target_term.lower():
                    result = match_provider.match(current_term, target_term)
                    s_scores.append(result.referent)

        if s_scores:
            return sum(s_scores) / len(s_scores)
        return 0.0

    except ImportError:
        # Canonical matching not available - return neutral
        return 0.0


def _compute_lcs_ratio(chain1: List[str], chain2: List[str]) -> float:
    """Compute longest common subsequence ratio between two chains."""
    if not chain1 or not chain2:
        return 0.0

    m, n = len(chain1), len(chain2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if chain1[i-1].lower() == chain2[j-1].lower():
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    lcs_length = dp[m][n]
    max_length = max(m, n)
    return lcs_length / max_length if max_length > 0 else 0.0


# =============================================================================
# Domain Bridge Templates (only used after structural validation)
# =============================================================================

BRIDGE_TEMPLATES: Dict[Tuple[str, str], str] = {
    # Biology/Biotech + Finance
    ("biology", "finance"): "Structural pattern matches your finance interest.",
    ("biotech", "finance"): "This pattern structurally connects to market dynamics.",
    ("medicine", "finance"): "Healthcare pattern matches your financial analysis style.",

    # Tech + Finance
    ("technology", "finance"): "Tech pattern structurally similar to your market analysis.",
    ("ai", "finance"): "AI development pattern matches investment cycles you track.",

    # History + Current Events
    ("history", "politics"): "Historical pattern structurally matches current dynamics.",
    ("history", "economics"): "Economic cycle pattern detected from your history queries.",

    # Science + Practical
    ("physics", "engineering"): "Physics principle matches engineering patterns you explore.",
    ("chemistry", "manufacturing"): "Chemical process maps to manufacturing patterns.",
}


def _get_bridge_template(domain_a: str, domain_b: str) -> Optional[str]:
    """Get template for a domain bridge, checking both orderings."""
    key1 = (domain_a.lower(), domain_b.lower())
    key2 = (domain_b.lower(), domain_a.lower())
    return BRIDGE_TEMPLATES.get(key1) or BRIDGE_TEMPLATES.get(key2)


# =============================================================================
# Recent Activity Helpers
# =============================================================================

def _get_recent_domains(
    persona: PersonaProfile,
    hours: int = 24,
    limit: int = 5
) -> List[Tuple[str, int]]:
    """Get domains the user has queried recently."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    recent_domains: Dict[str, int] = {}

    for query in reversed(persona.queries):
        try:
            query_time = datetime.fromisoformat(query.timestamp)
            if query_time < cutoff:
                break
            if query.domain:
                recent_domains[query.domain] = recent_domains.get(query.domain, 0) + 1
        except (ValueError, TypeError):
            continue

    sorted_domains = sorted(recent_domains.items(), key=lambda x: -x[1])
    return sorted_domains[:limit]


def _get_recent_events(
    persona: PersonaProfile,
    hours: int = 24
) -> Dict[str, int]:
    """Get event types from recent queries."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    recent_events: Dict[str, int] = {}

    for query in reversed(persona.queries):
        try:
            query_time = datetime.fromisoformat(query.timestamp)
            if query_time < cutoff:
                break
            for event in query.events:
                event_name = event.event_type.value
                recent_events[event_name] = recent_events.get(event_name, 0) + 1
        except (ValueError, TypeError):
            continue

    return recent_events


def _get_recent_vectors(
    persona: PersonaProfile,
    domain: str,
    hours: int = 24,
    limit: int = 5
) -> List[DimensionalVector]:
    """Get 10D vectors from recent queries in a specific domain."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    vectors = []

    for query in reversed(persona.queries):
        if len(vectors) >= limit:
            break
        try:
            query_time = datetime.fromisoformat(query.timestamp)
            if query_time < cutoff:
                break
            if query.domain and query.domain.lower() == domain.lower():
                vectors.append(query.vector)
        except (ValueError, TypeError):
            continue

    return vectors


# =============================================================================
# Core Insight Generation (Mode-Aware)
# =============================================================================

def generate_insights(
    persona_id: str,
    current_context: str,
    current_domain: str,
    mode: InsightMode = InsightMode.NEW_POSSIBILITIES,
    max_insights: int = 3,
    recency_hours: int = 24,
    store: Optional[PersonaStore] = None,
) -> List[PersonalInsight]:
    """
    Generate personalized insights based on persona history and current context.

    USER CONTROLS THE MODE - this is not decided by the system.

    Args:
        persona_id: The user's persona identifier
        current_context: What the user is currently reading/viewing
        current_domain: Domain of the current context
        mode: User-selected insight mode (controls what gets shown)
        max_insights: Maximum number of insights to return
        recency_hours: How far back to look in persona history
        store: Optional PersonaStore (uses global if not provided)

    Returns:
        List of PersonalInsight objects, sorted by confidence

    Modes:
        RECENT_MEMORY: Show connections to recent activity (recency priority)
        DOMAIN_RELATIVE: Stay in current domain (no cross-domain)
        NEW_POSSIBILITIES: Only show cross-domain if STRUCTURALLY validated
    """
    if store is None:
        store = get_persona_store()

    persona = store.get_or_create(persona_id)

    # Not enough history to generate insights
    if persona.total_queries < 3:
        return []

    insights: List[PersonalInsight] = []

    # Encode current context
    current_vector, current_events, _ = encode_with_events(current_context)
    current_event_types = {e.event_type.value for e in current_events}

    # Get recent activity
    recent_domains = _get_recent_domains(persona, hours=recency_hours)
    recent_events = _get_recent_events(persona, hours=recency_hours)

    # ==========================================================================
    # MODE: DOMAIN_RELATIVE - Stay within current domain
    # ==========================================================================
    if mode == InsightMode.DOMAIN_RELATIVE:
        # Only show pattern continuations within the domain
        top_events = sorted(recent_events.items(), key=lambda x: -x[1])[:5]
        for event_type, count in top_events:
            if event_type in current_event_types:
                insights.append(PersonalInsight(
                    insight_type=InsightType.PATTERN_CONTINUATION,
                    message=f"This deepens your {event_type} exploration in {current_domain}.",
                    confidence=min(0.85, 0.5 + (count * 0.05)),
                    current_domain=current_domain,
                    recent_activity=[f"{event_type}: {count} occurrences"],
                    shared_events=[event_type],
                    reasoning=f"Continuing {event_type} pattern within {current_domain}",
                    mode_used=mode,
                ))

        insights.sort(key=lambda x: -x.confidence)
        return insights[:max_insights]

    # ==========================================================================
    # MODE: RECENT_MEMORY - Prioritize recency (user explicitly wants this)
    # ==========================================================================
    if mode == InsightMode.RECENT_MEMORY:
        for recent_domain, query_count in recent_domains:
            if recent_domain.lower() == current_domain.lower():
                continue

            # Get vectors from recent domain for comparison
            recent_vectors = _get_recent_vectors(persona, recent_domain, recency_hours)

            # Check for existing bridge
            bridge_key = "_".join(sorted([current_domain.lower(), recent_domain.lower()]))
            existing_bridge = persona.bridges.get(bridge_key)

            # Structural validation (still compute, but with lower threshold for recent memory)
            target_events = set()
            if existing_bridge:
                target_events = existing_bridge.shared_events

            structural_match = None
            if recent_vectors:
                structural_match = _compute_structural_match(
                    current_vector=current_vector,
                    current_events=current_event_types,
                    target_vector=recent_vectors[0] if recent_vectors else None,
                    target_events=target_events,
                )

            # For RECENT_MEMORY, recency matters more than structure
            confidence = min(0.9, 0.4 + (query_count * 0.1))
            if structural_match and structural_match.is_valid:
                confidence = min(0.95, confidence + 0.1)

            message = f"Your recent {recent_domain} work ({query_count} queries) connects here."
            if structural_match and structural_match.is_valid:
                message += f" (structural match: {structural_match.combined_score:.0%})"

            insights.append(PersonalInsight(
                insight_type=InsightType.BRIDGE_OPPORTUNITY,
                message=message,
                confidence=confidence,
                current_domain=current_domain,
                bridge_domain=recent_domain,
                recent_activity=[f"{recent_domain}: {query_count} queries in {recency_hours}h"],
                shared_events=list(current_event_types & target_events),
                structural_match=structural_match,
                reasoning=f"Recent memory mode: prioritizing recency of {recent_domain} activity",
                mode_used=mode,
            ))

        insights.sort(key=lambda x: -x.confidence)
        return insights[:max_insights]

    # ==========================================================================
    # MODE: NEW_POSSIBILITIES - Only if STRUCTURAL match exists
    # ==========================================================================
    # This is the default and most rigorous mode

    for recent_domain, query_count in recent_domains:
        if recent_domain.lower() == current_domain.lower():
            continue

        # Get vectors from recent domain
        recent_vectors = _get_recent_vectors(persona, recent_domain, recency_hours)

        # Get bridge info
        bridge_key = "_".join(sorted([current_domain.lower(), recent_domain.lower()]))
        existing_bridge = persona.bridges.get(bridge_key)

        target_events = set()
        if existing_bridge:
            target_events = existing_bridge.shared_events

        # STRUCTURAL VALIDATION - the key to avoiding advertising
        structural_match = _compute_structural_match(
            current_vector=current_vector,
            current_events=current_event_types,
            target_vector=recent_vectors[0] if recent_vectors else None,
            target_events=target_events,
        )

        # ONLY suggest if structurally valid
        if not structural_match.is_valid:
            continue  # Skip this domain - no real connection

        # Get template or generate message
        template = _get_bridge_template(current_domain, recent_domain)
        if template:
            message = template
        else:
            message = f"Structural pattern match with your {recent_domain} analysis."

        # Add match score to message for transparency
        message += f" (match: {structural_match.combined_score:.0%})"

        # Confidence based on structural match, not just recency
        confidence = min(0.95, 0.5 + structural_match.combined_score * 0.4)

        insights.append(PersonalInsight(
            insight_type=InsightType.STRUCTURAL_MATCH,
            message=message,
            confidence=confidence,
            current_domain=current_domain,
            bridge_domain=recent_domain,
            recent_activity=[f"{recent_domain}: {query_count} queries"],
            shared_events=structural_match.shared_events,
            structural_match=structural_match,
            reasoning=f"Structural validation passed: 10D={structural_match.similarity_10d:.2f}, causal={structural_match.causal_overlap:.2f}",
            mode_used=mode,
        ))

    # Also add pattern continuations (these don't need cross-domain validation)
    top_events = sorted(recent_events.items(), key=lambda x: -x[1])[:3]
    for event_type, count in top_events:
        if event_type in current_event_types:
            insights.append(PersonalInsight(
                insight_type=InsightType.PATTERN_CONTINUATION,
                message=f"This continues your {event_type} pattern exploration.",
                confidence=min(0.75, 0.4 + (count * 0.05)),
                current_domain=current_domain,
                recent_activity=[f"{event_type}: {count} occurrences"],
                shared_events=[event_type],
                reasoning=f"Pattern continuation within {current_domain}",
                mode_used=mode,
            ))

    # Sort by confidence and limit
    insights.sort(key=lambda x: -x.confidence)
    return insights[:max_insights]


def generate_insight_for_display(
    persona_id: str,
    current_context: str,
    current_domain: str,
    mode: InsightMode = InsightMode.NEW_POSSIBILITIES,
    store: Optional[PersonaStore] = None,
) -> Optional[str]:
    """
    Generate a single insight message for display.

    Convenience function that returns just the top insight message,
    or None if no insights are available.
    """
    insights = generate_insights(
        persona_id=persona_id,
        current_context=current_context,
        current_domain=current_domain,
        mode=mode,
        max_insights=1,
        store=store,
    )

    if insights:
        return insights[0].message
    return None


# =============================================================================
# Insight Transparency
# =============================================================================

def explain_insight(insight: PersonalInsight) -> str:
    """
    Generate a transparent explanation of why this insight was suggested.

    Supports the system's transparency principle: show, don't tell.
    """
    parts = [f"Insight Type: {insight.insight_type.value}"]
    parts.append(f"Confidence: {insight.confidence:.0%}")

    if insight.mode_used:
        parts.append(f"Mode: {insight.mode_used.value}")

    if insight.bridge_domain:
        parts.append(f"Bridge: {insight.current_domain} ↔ {insight.bridge_domain}")

    if insight.structural_match:
        parts.append(
            f"Structural: 10D={insight.structural_match.similarity_10d:.2f}, "
            f"causal={insight.structural_match.causal_overlap:.2f}, "
            f"valid={insight.structural_match.is_valid}"
        )

    if insight.recent_activity:
        parts.append(f"Based on: {', '.join(insight.recent_activity)}")

    if insight.shared_events:
        parts.append(f"Shared patterns: {', '.join(insight.shared_events)}")

    if insight.reasoning:
        parts.append(f"Reasoning: {insight.reasoning}")

    return " | ".join(parts)


__all__ = [
    # Modes (user control)
    "InsightMode",
    # Types
    "InsightType",
    "PersonalInsight",
    "InsightContext",
    "StructuralMatch",
    # Core functions
    "generate_insights",
    "generate_insight_for_display",
    "explain_insight",
    # Thresholds (for transparency)
    "STRUCTURAL_THRESHOLD_10D",
    "STRUCTURAL_THRESHOLD_CAUSAL",
    "STRUCTURAL_THRESHOLD_COMBINED",
]
