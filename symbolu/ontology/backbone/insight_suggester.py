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
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
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


class InsightType(Enum):
    """Types of personal insights."""
    BRIDGE_OPPORTUNITY = "bridge_opportunity"   # Current context bridges to recent activity
    PATTERN_CONTINUATION = "pattern_continuation"  # Continuing a pattern the user follows
    DOMAIN_SWITCH = "domain_switch"             # User's interest may have shifted
    ACTION_SUGGESTION = "action_suggestion"     # Specific action based on context


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

    # For transparency
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.insight_type.value,
            "message": self.message,
            "confidence": self.confidence,
            "current_domain": self.current_domain,
            "bridge_domain": self.bridge_domain,
            "recent_activity": self.recent_activity,
            "shared_events": self.shared_events,
            "reasoning": self.reasoning,
        }


@dataclass
class InsightContext:
    """Context for generating insights."""
    text: str
    domain: str
    events: List[TaggedEvent] = field(default_factory=list)


# =============================================================================
# Domain Bridge Templates
# =============================================================================

# Maps domain pairs to insight templates
BRIDGE_TEMPLATES: Dict[Tuple[str, str], str] = {
    # Biology/Biotech + Finance
    ("biology", "finance"): "Are you considering the investment angle?",
    ("biotech", "finance"): "This breakthrough could have market implications.",
    ("medicine", "finance"): "Healthcare stocks might be affected by this.",

    # Tech + Finance
    ("technology", "finance"): "Tech sector implications worth considering?",
    ("ai", "finance"): "AI companies in this space might interest you.",

    # History + Current Events
    ("history", "politics"): "Historical patterns suggest...",
    ("history", "economics"): "Economic cycles show similar patterns.",

    # Science + Practical
    ("physics", "engineering"): "Engineering applications could follow.",
    ("chemistry", "manufacturing"): "Manufacturing implications here.",
}


def _get_bridge_template(domain_a: str, domain_b: str) -> Optional[str]:
    """Get template for a domain bridge, checking both orderings."""
    key1 = (domain_a.lower(), domain_b.lower())
    key2 = (domain_b.lower(), domain_a.lower())
    return BRIDGE_TEMPLATES.get(key1) or BRIDGE_TEMPLATES.get(key2)


# =============================================================================
# Core Insight Generation
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


def generate_insights(
    persona_id: str,
    current_context: str,
    current_domain: str,
    max_insights: int = 3,
    recency_hours: int = 24,
    store: Optional[PersonaStore] = None,
) -> List[PersonalInsight]:
    """
    Generate personalized insights based on persona history and current context.

    This is the main entry point for the insight suggestion system.

    Args:
        persona_id: The user's persona identifier
        current_context: What the user is currently reading/viewing
        current_domain: Domain of the current context
        max_insights: Maximum number of insights to return
        recency_hours: How far back to look in persona history
        store: Optional PersonaStore (uses global if not provided)

    Returns:
        List of PersonalInsight objects, sorted by confidence

    Example:
        >>> insights = generate_insights(
        ...     persona_id="user_123",
        ...     current_context="New CRISPR breakthrough enables gene editing...",
        ...     current_domain="biology"
        ... )
        >>> for insight in insights:
        ...     print(insight.message)
        "Are you considering the investment angle?"
    """
    if store is None:
        store = get_persona_store()

    persona = store.get_or_create(persona_id)

    # Not enough history to generate insights
    if persona.total_queries < 3:
        return []

    insights: List[PersonalInsight] = []

    # Encode current context
    _, current_events, _ = encode_with_events(current_context)
    current_event_types = {e.event_type.value for e in current_events}

    # Get recent activity
    recent_domains = _get_recent_domains(persona, hours=recency_hours)
    recent_events = _get_recent_events(persona, hours=recency_hours)

    # 1. Bridge Opportunity: Current domain differs from recent activity
    for recent_domain, query_count in recent_domains:
        if recent_domain.lower() == current_domain.lower():
            continue

        # Check if there's a template for this bridge
        template = _get_bridge_template(current_domain, recent_domain)

        # Check for existing bridge in persona
        bridge_key = "_".join(sorted([current_domain.lower(), recent_domain.lower()]))
        existing_bridge = persona.bridges.get(bridge_key)

        # Calculate confidence based on query count and bridge history
        confidence = min(0.9, 0.3 + (query_count * 0.1))
        if existing_bridge:
            confidence = min(0.95, confidence + (existing_bridge.bridge_count * 0.05))

        # Find shared events between current context and recent domain
        shared = []
        if existing_bridge:
            shared = list(current_event_types & existing_bridge.shared_events)

        # Generate message
        if template:
            message = template
        else:
            message = f"Your recent {recent_domain} activity might connect here."

        insights.append(PersonalInsight(
            insight_type=InsightType.BRIDGE_OPPORTUNITY,
            message=message,
            confidence=confidence,
            current_domain=current_domain,
            bridge_domain=recent_domain,
            recent_activity=[f"{recent_domain}: {query_count} queries"],
            shared_events=shared,
            reasoning=f"User has been active in {recent_domain} ({query_count} queries in {recency_hours}h)",
        ))

    # 2. Pattern Continuation: User follows certain event patterns
    top_events = sorted(recent_events.items(), key=lambda x: -x[1])[:3]
    for event_type, count in top_events:
        if event_type in current_event_types:
            insights.append(PersonalInsight(
                insight_type=InsightType.PATTERN_CONTINUATION,
                message=f"This follows your interest in {event_type} patterns.",
                confidence=min(0.8, 0.4 + (count * 0.05)),
                current_domain=current_domain,
                recent_activity=[f"{event_type}: {count} occurrences"],
                shared_events=[event_type],
                reasoning=f"User frequently explores {event_type} patterns",
            ))

    # 3. Action Suggestion: Specific suggestions based on domain combination
    for recent_domain, _ in recent_domains[:2]:
        if recent_domain.lower() == current_domain.lower():
            continue

        # Finance-related action suggestions
        if recent_domain.lower() == "finance" and current_domain.lower() in [
            "biology", "biotech", "technology", "ai", "medicine"
        ]:
            insights.append(PersonalInsight(
                insight_type=InsightType.ACTION_SUGGESTION,
                message="Consider researching related stocks or investment opportunities.",
                confidence=0.7,
                current_domain=current_domain,
                bridge_domain="finance",
                recent_activity=["Recent trading/finance activity detected"],
                reasoning="User has recent finance activity and is viewing investment-relevant content",
            ))
            break

    # Sort by confidence and limit
    insights.sort(key=lambda x: -x.confidence)
    return insights[:max_insights]


def generate_insight_for_display(
    persona_id: str,
    current_context: str,
    current_domain: str,
    store: Optional[PersonaStore] = None,
) -> Optional[str]:
    """
    Generate a single insight message for display.

    Convenience function that returns just the top insight message,
    or None if no insights are available.

    Args:
        persona_id: The user's persona identifier
        current_context: What the user is currently reading/viewing
        current_domain: Domain of the current context
        store: Optional PersonaStore

    Returns:
        The top insight message as a string, or None

    Example:
        >>> message = generate_insight_for_display(
        ...     "user_123",
        ...     "CRISPR gene editing breakthrough...",
        ...     "biology"
        ... )
        >>> print(message)
        "Are you considering the investment angle?"
    """
    insights = generate_insights(
        persona_id=persona_id,
        current_context=current_context,
        current_domain=current_domain,
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

    Args:
        insight: The PersonalInsight to explain

    Returns:
        Human-readable explanation string
    """
    parts = [f"Insight Type: {insight.insight_type.value}"]
    parts.append(f"Confidence: {insight.confidence:.0%}")

    if insight.bridge_domain:
        parts.append(f"Bridge: {insight.current_domain} ↔ {insight.bridge_domain}")

    if insight.recent_activity:
        parts.append(f"Based on: {', '.join(insight.recent_activity)}")

    if insight.shared_events:
        parts.append(f"Shared patterns: {', '.join(insight.shared_events)}")

    if insight.reasoning:
        parts.append(f"Reasoning: {insight.reasoning}")

    return " | ".join(parts)


__all__ = [
    # Types
    "InsightType",
    "PersonalInsight",
    "InsightContext",
    # Core functions
    "generate_insights",
    "generate_insight_for_display",
    "explain_insight",
]
