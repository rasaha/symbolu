"""
User Inclination Model
======================

Tracks user preferences, affinities, and reasoning styles to personalize
the retrieval and synthesis of experiential objects.

Each user builds a profile over time through:
- Explicit feedback (ratings, useful/not useful)
- Implicit signals (which domains they query, what they engage with)
- Dimensional preferences (which 10D dimensions resonate with them)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from datetime import datetime
import json

from .encoder import Dimension


class ReasoningStyle(Enum):
    """User's preferred reasoning style."""
    ANALYTICAL = "analytical"      # Prefers logic, data, frameworks
    NARRATIVE = "narrative"        # Prefers stories, examples, analogies
    PRACTICAL = "practical"        # Prefers actionable, concrete steps
    CONCEPTUAL = "conceptual"      # Prefers abstract, theoretical
    VISUAL = "visual"              # Prefers diagrams, structures
    BALANCED = "balanced"          # No strong preference


class CommunicationPreference(Enum):
    """How user prefers information delivered."""
    CONCISE = "concise"            # Brief, to the point
    DETAILED = "detailed"          # Comprehensive, thorough
    STRUCTURED = "structured"      # Bullet points, numbered lists
    CONVERSATIONAL = "conversational"  # Flowing prose


@dataclass
class DomainAffinity:
    """User's affinity for a specific domain."""
    domain: str
    affinity_score: float  # 0.0 to 1.0
    interaction_count: int
    success_rate: float    # How often domain content was useful
    last_interaction: str

    def update(self, was_useful: bool):
        """Update affinity based on interaction."""
        self.interaction_count += 1
        # Exponential moving average
        alpha = 0.3
        new_success = 1.0 if was_useful else 0.0
        self.success_rate = self.success_rate * (1 - alpha) + new_success * alpha
        # Update affinity based on success
        self.affinity_score = 0.5 + (self.success_rate - 0.5) * 0.8
        self.last_interaction = datetime.utcnow().isoformat()


@dataclass
class DimensionalPreference:
    """User's preference for specific 10D dimensions."""
    prefers_high: Dict[Dimension, float] = field(default_factory=dict)  # Likes when high
    avoids_high: Dict[Dimension, float] = field(default_factory=dict)   # Dislikes when high

    def get_weight(self, dim: Dimension) -> float:
        """Get weighting factor for a dimension."""
        if dim in self.prefers_high:
            return 1.0 + self.prefers_high[dim]
        elif dim in self.avoids_high:
            return 1.0 - self.avoids_high[dim] * 0.5
        return 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prefers_high": {d.name: v for d, v in self.prefers_high.items()},
            "avoids_high": {d.name: v for d, v in self.avoids_high.items()},
        }


@dataclass
class UserInclinationProfile:
    """
    Complete user profile for personalization.

    Tracks:
    - Domain affinities (which domains resonate)
    - Dimensional preferences (which 10D aspects they prefer)
    - Reasoning style (how they like to think)
    - Communication preferences (how they like info delivered)
    - Interaction history (what worked, what didn't)
    """
    user_id: str
    created_at: str = ""
    updated_at: str = ""

    # Preferences
    reasoning_style: ReasoningStyle = ReasoningStyle.BALANCED
    communication_pref: CommunicationPreference = CommunicationPreference.STRUCTURED

    # Domain affinities
    domain_affinities: Dict[str, DomainAffinity] = field(default_factory=dict)

    # Dimensional preferences
    dimensional_pref: DimensionalPreference = field(default_factory=DimensionalPreference)

    # History
    total_interactions: int = 0
    total_positive_feedback: int = 0
    experiential_history: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # experiential_id -> {"useful": bool, "rating": float, "timestamp": str}

    # Tags the user engages with
    preferred_tags: Dict[str, float] = field(default_factory=dict)  # tag -> affinity

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()

    def get_domain_affinity(self, domain: str) -> float:
        """Get affinity score for a domain."""
        if domain in self.domain_affinities:
            return self.domain_affinities[domain].affinity_score
        return 0.5  # Neutral default

    def update_domain_interaction(self, domain: str, was_useful: bool):
        """Update domain affinity based on interaction."""
        if domain not in self.domain_affinities:
            self.domain_affinities[domain] = DomainAffinity(
                domain=domain,
                affinity_score=0.5,
                interaction_count=0,
                success_rate=0.5,
                last_interaction="",
            )
        self.domain_affinities[domain].update(was_useful)
        self.updated_at = datetime.utcnow().isoformat()

    def record_experiential_feedback(
        self,
        experiential_id: str,
        was_useful: bool,
        rating: float = 0.5,
        domain: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        """Record feedback on an experiential object."""
        self.experiential_history[experiential_id] = {
            "useful": was_useful,
            "rating": rating,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.total_interactions += 1
        if was_useful:
            self.total_positive_feedback += 1

        # Update domain affinity
        if domain:
            self.update_domain_interaction(domain, was_useful)

        # Update tag preferences
        if tags:
            alpha = 0.2
            for tag in tags:
                current = self.preferred_tags.get(tag, 0.5)
                new_value = 0.8 if was_useful else 0.2
                self.preferred_tags[tag] = current * (1 - alpha) + new_value * alpha

        self.updated_at = datetime.utcnow().isoformat()

    def get_tag_weight(self, tag: str) -> float:
        """Get weight for a tag based on user preference."""
        return self.preferred_tags.get(tag, 0.5)

    def compute_experiential_score(
        self,
        experiential_id: str,
        domain: str,
        base_similarity: float,
        tags: List[str],
    ) -> float:
        """
        Compute personalized score for an experiential.

        Combines:
        - Base structural similarity
        - Domain affinity
        - Tag preferences
        - Historical success with this experiential
        """
        score = base_similarity * 0.4

        # Domain affinity
        domain_aff = self.get_domain_affinity(domain)
        score += domain_aff * 0.25

        # Tag preferences
        if tags:
            tag_score = sum(self.get_tag_weight(t) for t in tags) / len(tags)
            score += tag_score * 0.2

        # Historical success
        if experiential_id in self.experiential_history:
            hist = self.experiential_history[experiential_id]
            if hist["useful"]:
                score += hist["rating"] * 0.15
            else:
                score -= 0.1

        return max(0.0, min(1.0, score))

    def get_preferred_domains(self, top_k: int = 3) -> List[str]:
        """Get user's top preferred domains."""
        sorted_domains = sorted(
            self.domain_affinities.items(),
            key=lambda x: x[1].affinity_score,
            reverse=True
        )
        return [d[0] for d in sorted_domains[:top_k]]

    def get_avoided_domains(self, threshold: float = 0.3) -> List[str]:
        """Get domains user tends to avoid."""
        return [
            d for d, aff in self.domain_affinities.items()
            if aff.affinity_score < threshold
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reasoning_style": self.reasoning_style.value,
            "communication_pref": self.communication_pref.value,
            "domain_affinities": {
                d: {
                    "affinity_score": a.affinity_score,
                    "interaction_count": a.interaction_count,
                    "success_rate": a.success_rate,
                }
                for d, a in self.domain_affinities.items()
            },
            "dimensional_pref": self.dimensional_pref.to_dict(),
            "total_interactions": self.total_interactions,
            "total_positive_feedback": self.total_positive_feedback,
            "preferred_tags": self.preferred_tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserInclinationProfile":
        profile = cls(
            user_id=data["user_id"],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            reasoning_style=ReasoningStyle(data.get("reasoning_style", "balanced")),
            communication_pref=CommunicationPreference(data.get("communication_pref", "structured")),
            total_interactions=data.get("total_interactions", 0),
            total_positive_feedback=data.get("total_positive_feedback", 0),
            preferred_tags=data.get("preferred_tags", {}),
        )

        # Restore domain affinities
        for d, a in data.get("domain_affinities", {}).items():
            profile.domain_affinities[d] = DomainAffinity(
                domain=d,
                affinity_score=a["affinity_score"],
                interaction_count=a["interaction_count"],
                success_rate=a["success_rate"],
                last_interaction="",
            )

        return profile


# =============================================================================
# User Store
# =============================================================================

class UserInclinationStore:
    """Storage for user profiles."""

    def __init__(self):
        self._profiles: Dict[str, UserInclinationProfile] = {}

    def get_or_create(self, user_id: str) -> UserInclinationProfile:
        """Get existing profile or create new one."""
        if user_id not in self._profiles:
            self._profiles[user_id] = UserInclinationProfile(user_id=user_id)
        return self._profiles[user_id]

    def get(self, user_id: str) -> Optional[UserInclinationProfile]:
        """Get profile if exists."""
        return self._profiles.get(user_id)

    def save(self, profile: UserInclinationProfile):
        """Save profile to store."""
        self._profiles[profile.user_id] = profile

    def export(self) -> Dict[str, Any]:
        """Export all profiles."""
        return {
            "profiles": {uid: p.to_dict() for uid, p in self._profiles.items()}
        }

    def import_data(self, data: Dict[str, Any]):
        """Import profiles from data."""
        for uid, pdata in data.get("profiles", {}).items():
            self._profiles[uid] = UserInclinationProfile.from_dict(pdata)


# Global store
_user_store: Optional[UserInclinationStore] = None


def get_user_store() -> UserInclinationStore:
    """Get or create global user store."""
    global _user_store
    if _user_store is None:
        _user_store = UserInclinationStore()
    return _user_store
