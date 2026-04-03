"""
Persona Query Tracker
=====================

Tracks user queries per persona to discover cross-domain patterns
through USAGE rather than content extraction.

Key Principle:
    Don't extract patterns from content (too much data).
    Let user behavior reveal what patterns matter.

The system learns:
    1. Which domains each persona queries
    2. Which event types they're interested in
    3. Which mirror pairs they activate
    4. Cross-domain bridges they naturally make
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
from collections import defaultdict
import hashlib

from .encoder import DimensionalVector, Dimension, encode_10d
from .mirror_pairs import (
    MirrorPair,
    compute_balance,
    tag_events,
    TaggedEvent,
    EventType,
    encode_with_events,
    BalanceReport,
)


@dataclass
class QueryRecord:
    """
    Record of a single user query.

    Captures the query, its encoding, events, and balance.
    """
    query_id: str
    timestamp: str
    query_text: str
    domain: Optional[str]  # User-specified or inferred domain

    # Analysis
    vector: DimensionalVector
    events: List[TaggedEvent]
    balance: BalanceReport

    # Cross-domain bridge (if this query connected domains)
    bridges_to: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "timestamp": self.timestamp,
            "query_text": self.query_text[:100],
            "domain": self.domain,
            "events": [e.event_type.value for e in self.events],
            "balance_score": self.balance.balance_score,
            "bridges_to": self.bridges_to,
        }


@dataclass
class DomainInterest:
    """
    Tracks interest in a specific domain.
    """
    domain: str
    query_count: int = 0
    total_engagement: float = 0.0
    last_query: str = ""
    common_events: Dict[str, int] = field(default_factory=dict)

    @property
    def average_engagement(self) -> float:
        if self.query_count == 0:
            return 0.0
        return self.total_engagement / self.query_count

    def record_query(self, events: List[TaggedEvent]):
        """Record a query to this domain."""
        self.query_count += 1
        self.total_engagement += 1.0
        self.last_query = datetime.utcnow().isoformat()

        for event in events:
            event_name = event.event_type.value
            self.common_events[event_name] = self.common_events.get(event_name, 0) + 1


@dataclass
class CrossDomainBridge:
    """
    A discovered bridge between two domains for a persona.
    """
    domain_a: str
    domain_b: str
    bridge_count: int = 0
    shared_events: Set[str] = field(default_factory=set)
    example_queries: List[str] = field(default_factory=list)

    @property
    def bridge_id(self) -> str:
        sorted_domains = sorted([self.domain_a, self.domain_b])
        return f"{sorted_domains[0]}_{sorted_domains[1]}"

    def record_bridge(self, query: str, events: List[TaggedEvent]):
        """Record a cross-domain bridge."""
        self.bridge_count += 1
        for event in events:
            self.shared_events.add(event.event_type.value)
        if len(self.example_queries) < 5:
            self.example_queries.append(query[:100])


@dataclass
class PersonaProfile:
    """
    Complete profile of a persona's query patterns.

    Built from observing their queries, not from extraction.
    """
    persona_id: str
    created_at: str = ""
    updated_at: str = ""

    # Query history (limited to recent)
    queries: List[QueryRecord] = field(default_factory=list)
    max_query_history: int = 100

    # Domain interests
    domain_interests: Dict[str, DomainInterest] = field(default_factory=dict)

    # Cross-domain bridges discovered
    bridges: Dict[str, CrossDomainBridge] = field(default_factory=dict)

    # Event type preferences
    event_preferences: Dict[str, int] = field(default_factory=dict)

    # Mirror pair activation patterns
    mirror_activations: Dict[str, int] = field(default_factory=dict)

    # Aggregate stats
    total_queries: int = 0
    avg_balance_score: float = 0.5

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    def record_query(
        self,
        query_text: str,
        domain: Optional[str] = None,
        response_domains: Optional[List[str]] = None,
    ) -> QueryRecord:
        """
        Record a query from this persona.

        Args:
            query_text: The user's query
            domain: Domain of the query (optional, can be inferred)
            response_domains: Domains that were used to respond (for bridge detection)

        Returns:
            QueryRecord of the processed query
        """
        # Encode with event tagging
        vector, events, balance = encode_with_events(query_text)

        # Create record
        query_id = "q_" + hashlib.sha256(
            f"{self.persona_id}:{query_text}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:12]

        # Detect bridges
        bridges_to = []
        if response_domains and domain:
            bridges_to = [d for d in response_domains if d != domain]

        record = QueryRecord(
            query_id=query_id,
            timestamp=datetime.utcnow().isoformat(),
            query_text=query_text,
            domain=domain,
            vector=vector,
            events=events,
            balance=balance,
            bridges_to=bridges_to,
        )

        # Update history
        self.queries.append(record)
        if len(self.queries) > self.max_query_history:
            self.queries = self.queries[-self.max_query_history:]

        # Update domain interest
        if domain:
            if domain not in self.domain_interests:
                self.domain_interests[domain] = DomainInterest(domain=domain)
            self.domain_interests[domain].record_query(events)

        # Update bridges
        for bridge_domain in bridges_to:
            bridge_key = "_".join(sorted([domain or "unknown", bridge_domain]))
            if bridge_key not in self.bridges:
                self.bridges[bridge_key] = CrossDomainBridge(
                    domain_a=domain or "unknown",
                    domain_b=bridge_domain,
                )
            self.bridges[bridge_key].record_bridge(query_text, events)

        # Update event preferences
        for event in events:
            event_name = event.event_type.value
            self.event_preferences[event_name] = self.event_preferences.get(event_name, 0) + 1

        # Update mirror activations
        for pair_balance in balance.pairs:
            if pair_balance.state == "balanced":
                pair_name = pair_balance.pair.name
                self.mirror_activations[pair_name] = self.mirror_activations.get(pair_name, 0) + 1

        # Update aggregate stats
        self.total_queries += 1
        self.avg_balance_score = (
            self.avg_balance_score * (self.total_queries - 1) + balance.balance_score
        ) / self.total_queries

        self.updated_at = datetime.utcnow().isoformat()

        return record

    def get_top_domains(self, top_k: int = 5) -> List[Tuple[str, DomainInterest]]:
        """Get most queried domains."""
        sorted_domains = sorted(
            self.domain_interests.items(),
            key=lambda x: x[1].query_count,
            reverse=True
        )
        return sorted_domains[:top_k]

    def get_top_events(self, top_k: int = 5) -> List[Tuple[str, int]]:
        """Get most common event types."""
        sorted_events = sorted(
            self.event_preferences.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_events[:top_k]

    def get_strongest_bridges(self, top_k: int = 5) -> List[CrossDomainBridge]:
        """Get most-used cross-domain bridges."""
        sorted_bridges = sorted(
            self.bridges.values(),
            key=lambda x: x.bridge_count,
            reverse=True
        )
        return sorted_bridges[:top_k]

    def get_cross_domain_pattern(self) -> str:
        """
        Identify this persona's cross-domain pattern.

        Returns a description of how this persona thinks across domains.
        """
        top_events = self.get_top_events(3)
        top_bridges = self.get_strongest_bridges(2)

        if not top_events:
            return "Insufficient data to determine pattern"

        event_names = [e[0] for e in top_events]

        pattern_parts = []
        pattern_parts.append(f"Thinks in terms of: {', '.join(event_names)}")

        if top_bridges:
            bridge_desc = [f"{b.domain_a}↔{b.domain_b}" for b in top_bridges]
            pattern_parts.append(f"Connects: {', '.join(bridge_desc)}")

        return " | ".join(pattern_parts)

    def suggest_domains(self, query_text: str) -> List[str]:
        """
        Suggest domains to search based on persona's patterns.

        Args:
            query_text: New query

        Returns:
            List of suggested domains to search
        """
        # Encode the query
        vector, events, _ = encode_with_events(query_text)

        suggestions = set()

        # Add top domains the persona uses
        for domain, interest in self.get_top_domains(3):
            suggestions.add(domain)

        # Add bridge targets if query matches bridge events
        query_event_types = {e.event_type.value for e in events}
        for bridge in self.bridges.values():
            if query_event_types & bridge.shared_events:
                suggestions.add(bridge.domain_a)
                suggestions.add(bridge.domain_b)

        return list(suggestions)[:5]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "total_queries": self.total_queries,
            "avg_balance_score": self.avg_balance_score,
            "top_domains": [(d, i.query_count) for d, i in self.get_top_domains(5)],
            "top_events": self.get_top_events(5),
            "bridges": [
                {
                    "domains": [b.domain_a, b.domain_b],
                    "count": b.bridge_count,
                    "shared_events": list(b.shared_events),
                }
                for b in self.get_strongest_bridges(5)
            ],
            "cross_domain_pattern": self.get_cross_domain_pattern(),
        }


# =============================================================================
# Persona Store
# =============================================================================

class PersonaStore:
    """
    Storage for persona profiles.

    Tracks all personas and their query patterns.
    """

    def __init__(self):
        self._personas: Dict[str, PersonaProfile] = {}

    def get_or_create(self, persona_id: str) -> PersonaProfile:
        """Get existing persona or create new one."""
        if persona_id not in self._personas:
            self._personas[persona_id] = PersonaProfile(persona_id=persona_id)
        return self._personas[persona_id]

    def record_query(
        self,
        persona_id: str,
        query_text: str,
        domain: Optional[str] = None,
        response_domains: Optional[List[str]] = None,
    ) -> QueryRecord:
        """
        Record a query for a persona.

        Convenience method that gets/creates persona and records query.
        """
        persona = self.get_or_create(persona_id)
        return persona.record_query(query_text, domain, response_domains)

    def get_all_bridges(self) -> Dict[str, int]:
        """Get aggregate cross-domain bridges across all personas."""
        all_bridges: Dict[str, int] = defaultdict(int)

        for persona in self._personas.values():
            for bridge in persona.bridges.values():
                bridge_key = bridge.bridge_id
                all_bridges[bridge_key] += bridge.bridge_count

        return dict(sorted(all_bridges.items(), key=lambda x: -x[1]))

    def get_global_event_patterns(self) -> Dict[str, int]:
        """Get aggregate event patterns across all personas."""
        all_events: Dict[str, int] = defaultdict(int)

        for persona in self._personas.values():
            for event, count in persona.event_preferences.items():
                all_events[event] += count

        return dict(sorted(all_events.items(), key=lambda x: -x[1]))

    def find_similar_personas(
        self,
        persona_id: str,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Find personas with similar query patterns.

        Uses event preference overlap as similarity metric.
        """
        if persona_id not in self._personas:
            return []

        target = self._personas[persona_id]
        target_events = set(target.event_preferences.keys())

        similarities = []
        for pid, persona in self._personas.items():
            if pid == persona_id:
                continue

            their_events = set(persona.event_preferences.keys())
            overlap = len(target_events & their_events)
            union = len(target_events | their_events)

            if union > 0:
                jaccard = overlap / union
                similarities.append((pid, jaccard))

        similarities.sort(key=lambda x: -x[1])
        return similarities[:top_k]

    @property
    def size(self) -> int:
        return len(self._personas)

    def export(self) -> Dict[str, Any]:
        """Export all personas."""
        return {
            "personas": {pid: p.to_dict() for pid, p in self._personas.items()},
            "global_bridges": self.get_all_bridges(),
            "global_events": self.get_global_event_patterns(),
        }


# =============================================================================
# Global Store
# =============================================================================

_persona_store: Optional[PersonaStore] = None


def get_persona_store() -> PersonaStore:
    """Get or create global persona store."""
    global _persona_store
    if _persona_store is None:
        _persona_store = PersonaStore()
    return _persona_store


# =============================================================================
# Convenience Functions
# =============================================================================

def track_query(
    persona_id: str,
    query_text: str,
    domain: Optional[str] = None,
    response_domains: Optional[List[str]] = None,
) -> QueryRecord:
    """
    Track a query for a persona.

    Main entry point for the tracking system.

    Args:
        persona_id: Unique identifier for the user/persona
        query_text: The query text
        domain: Primary domain of the query
        response_domains: Domains used in the response

    Returns:
        QueryRecord of the processed query
    """
    store = get_persona_store()
    return store.record_query(persona_id, query_text, domain, response_domains)


def get_persona_insights(persona_id: str) -> Dict[str, Any]:
    """
    Get insights about a persona's patterns.

    Args:
        persona_id: The persona to analyze

    Returns:
        Dict with pattern insights
    """
    store = get_persona_store()
    persona = store.get_or_create(persona_id)

    return {
        "cross_domain_pattern": persona.get_cross_domain_pattern(),
        "top_domains": persona.get_top_domains(5),
        "top_events": persona.get_top_events(5),
        "strongest_bridges": [
            {
                "domains": [b.domain_a, b.domain_b],
                "count": b.bridge_count,
                "shared_events": list(b.shared_events)[:5],
            }
            for b in persona.get_strongest_bridges(3)
        ],
        "suggested_domains": lambda q: persona.suggest_domains(q),
    }
